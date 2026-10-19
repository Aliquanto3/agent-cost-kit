"""Fusionne une file de PR GitHub dans l'ordre, via la CLI `gh`.

Pour chaque PR : attend la fin des contrôles (sondage espacé, pour ne pas épuiser le quota de
l'API), relance une fois les jobs en échec, vérifie `mergeable`, fusionne puis vérifie que l'état
est bien MERGED. Une PR qui ne peut pas être fusionnée est sautée, la file continue.

Usage : python scripts/file_prs.py 104 105 106 [--repo OWNER/NOM] [--methode merge|squash|rebase]
        [--supprimer-branche] [--intervalle 60] [--delai-max 60] [--json] [--a-sec]

Code de retour : 0 si toutes les PR sont fusionnées (ou déjà fusionnées ; prêtes en --a-sec), 1 sinon.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable

INTERVALLE_MIN = 30
ERREURS_GH_MAX = 3  # lectures en erreur consécutives (quota, réseau) avant de sauter la PR
OK = ("fusionnee", "deja_fusionnee")
Gh = Callable[[list[str]], tuple[int, str]]


def gh_reel(args: list[str]) -> tuple[int, str]:
    """Seul point d'appel de la CLI gh : renvoie (code de retour, sortie)."""
    try:
        r = subprocess.run(
            ["gh", *args], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
        )
    except (OSError, subprocess.TimeoutExpired) as erreur:
        return 1, f"{type(erreur).__name__} : {erreur}"
    return r.returncode, r.stdout if r.returncode == 0 or r.stdout.strip() else r.stderr


def _json(gh: Gh, args: list[str], defaut):
    # `gh pr checks` sort en code non nul (8 en attente, 1 en échec) mais imprime quand même le JSON.
    _, sortie = gh(args)
    try:
        return json.loads(sortie)
    except ValueError:
        return defaut


def lire_controles(gh: Gh, pr: str) -> list[dict] | str:
    """Liste des contrôles ; [] si gh dit « no checks reported » ; sinon le message d'erreur (str)."""
    code, sortie = gh(["pr", "checks", pr, "--json", "bucket,name,workflow,link"])
    try:
        donnees = json.loads(sortie)
    except ValueError:
        donnees = None
    if isinstance(donnees, list):
        return donnees
    if "no checks reported" in sortie.lower():
        return []
    return (sortie.strip() or f"code {code}")[:200]


def id_run(lien: str) -> str | None:
    m = re.search(r"/actions/runs/(\d+)", lien or "")
    return m.group(1) if m else None


def traiter_pr(
    gh: Gh,
    pr: str,
    *,
    methode: str = "merge",
    supprimer_branche: bool = False,
    intervalle: int = 60,
    delai_max: int = 60,
    a_sec: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    horloge: Callable[[], float] = time.monotonic,
) -> dict:
    """Renvoie {pr, statut: fusionnee|sautee, detail, commit, relance}."""
    resultat = {"pr": pr, "statut": "sautee", "detail": "", "commit": None, "relance": False}
    etat = _json(gh, ["pr", "view", pr, "--json", "state,mergeCommit"], {})
    etat_initial = etat.get("state") if isinstance(etat, dict) else None
    if etat_initial == "MERGED":
        oid = (etat.get("mergeCommit") or {}).get("oid") or ""
        resultat.update(statut="deja_fusionnee", commit=oid[:7])
        return resultat
    if etat_initial == "CLOSED":
        resultat["detail"] = "fermée sans fusion"
        return resultat
    limite = horloge() + delai_max * 60
    erreurs = 0
    while True:
        controles = lire_controles(gh, pr)
        if isinstance(controles, str):
            erreurs += 1
            if erreurs >= ERREURS_GH_MAX or horloge() >= limite:
                resultat["detail"] = f"contrôles illisibles : {controles}"
                return resultat
            sleep(intervalle)
            continue
        erreurs = 0
        actifs = [c for c in controles if c.get("bucket") != "skipping"]
        if not actifs:
            resultat["detail"] = "aucun contrôle (conflit ?)"
            return resultat
        if any(c.get("bucket") == "pending" for c in actifs):
            if horloge() >= limite:
                resultat["detail"] = f"délai dépassé ({delai_max} min) en attente des contrôles"
                return resultat
            sleep(intervalle)
            continue
        rouges = [c for c in actifs if c.get("bucket") != "pass"]
        if not rouges:
            break
        noms = ", ".join(c.get("name") or "?" for c in rouges)
        if resultat["relance"]:
            resultat["detail"] = f"rouge après relance (job {noms})"
            return resultat
        if a_sec:
            resultat["detail"] = f"rouge (job {noms}), à sec : pas de relance"
            return resultat
        runs = sorted({r for c in rouges if (r := id_run(c.get("link", "")))})
        if not runs:
            resultat["detail"] = f"rouge (job {noms}), run introuvable pour relancer"
            return resultat
        for run in runs:
            code, sortie = gh(["run", "rerun", run, "--failed"])
            if code != 0:
                resultat["detail"] = f"rouge (job {noms}), relance impossible : {sortie.strip()[:200]}"
                return resultat
        resultat["relance"] = True
        sleep(intervalle)  # laisse GitHub repasser les jobs en attente avant de relire
    mergeable = "UNKNOWN"
    for essai in range(3):
        etat = _json(gh, ["pr", "view", pr, "--json", "mergeable"], {})
        mergeable = etat.get("mergeable", "UNKNOWN") if isinstance(etat, dict) else "UNKNOWN"
        if mergeable != "UNKNOWN":
            break
        if essai < 2:
            sleep(20)
    if mergeable != "MERGEABLE":
        resultat["detail"] = f"non fusionnable ({mergeable}, conflit ?)"
        return resultat
    if a_sec:
        resultat.update(statut="prete", detail="prête à fusionner (à sec : pas de merge)")
        return resultat
    args = ["pr", "merge", pr, f"--{methode}"] + (["--delete-branch"] if supprimer_branche else [])
    code, sortie = gh(args)
    if code != 0:
        resultat["detail"] = f"échec du merge : {sortie.strip()[:200]}"
        return resultat
    etat = _json(gh, ["pr", "view", pr, "--json", "state,mergeCommit"], {})
    if not isinstance(etat, dict) or etat.get("state") != "MERGED":
        statut = etat.get("state", "?") if isinstance(etat, dict) else "?"
        resultat["detail"] = f"état {statut} après merge, non fusionnée"
        return resultat
    oid = (etat.get("mergeCommit") or {}).get("oid") or ""
    resultat.update(statut="fusionnee", commit=oid[:7], detail="")
    return resultat


def ligne(r: dict) -> str:
    suffixe = " (relancé une fois)" if r["relance"] else ""
    if r["statut"] == "fusionnee":
        return f"#{r['pr']} fusionnée {r['commit']}{suffixe}"
    if r["statut"] == "deja_fusionnee":
        return f"#{r['pr']} déjà fusionnée {r['commit']}"
    if r["statut"] == "prete":
        return f"#{r['pr']} prête à fusionner (à sec){suffixe}"
    return f"#{r['pr']} sautée : {r['detail']}"


def traiter_file(gh: Gh, prs: list[str], repo: str | None = None, **options) -> list[dict]:
    def appel(args: list[str]) -> tuple[int, str]:
        return gh([*args, "--repo", repo] if repo else args)

    return [traiter_pr(appel, pr, **options) for pr in prs]


def main(argv: list[str] | None = None, gh: Gh = gh_reel, **injections) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("prs", nargs="+", help="numéros de PR, dans l'ordre de fusion")
    p.add_argument("--repo", help="OWNER/NOM (défaut : dépôt courant)")
    p.add_argument("--methode", choices=["merge", "squash", "rebase"], default="merge")
    p.add_argument("--supprimer-branche", action="store_true")
    p.add_argument("--intervalle", type=int, default=60, help="secondes entre deux sondages (min 30)")
    p.add_argument("--delai-max", type=int, default=60, help="minutes d'attente max par PR")
    p.add_argument("--json", action="store_true")
    p.add_argument("--a-sec", action="store_true", help="n'appelle ni merge ni rerun")
    o = p.parse_args(argv)
    resultats = traiter_file(
        gh,
        [x.lstrip("#") for x in o.prs],
        o.repo,
        methode=o.methode,
        supprimer_branche=o.supprimer_branche,
        intervalle=max(o.intervalle, INTERVALLE_MIN),
        delai_max=o.delai_max,
        a_sec=o.a_sec,
        **injections,
    )
    fusionnees = sum(r["statut"] in OK for r in resultats)
    reussies = sum(r["statut"] in (*OK, "prete") for r in resultats) if o.a_sec else fusionnees
    if o.json:
        print(json.dumps({"prs": resultats, "fusionnees": fusionnees, "total": len(resultats)}, ensure_ascii=False))
    else:
        for r in resultats:
            print(ligne(r))
        print(f"Résumé : {fusionnees}/{len(resultats)} fusionnée(s).")
    return 0 if reussies == len(resultats) else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
