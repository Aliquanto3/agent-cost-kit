"""Fusionne les durées de tests (pytest-split) remontées en artefacts par la CI, une par OS.

La CI de `modeles/ci-run-autonome.yml` remonte, par OS et par groupe, un artefact
`test-durations-<os>-<groupe>` qui contient `test-durations-<os>.json`. Ce script fusionne les
fichiers d'un même OS en un seul `test-durations-<os>.json` (à commiter), puis affiche par OS le
nombre de tests, le total et l'écart estimé entre les groupes pour N groupes.

Usage : python scripts/fusion_durees.py --run 123456 [--repo OWNER/NOM] [--dossier .] [--groupes 4]
        python scripts/fusion_durees.py --depuis dossier_des_artefacts [--dossier .] [--groupes 4]
        [--algo blocs|glouton]

Bibliothèque standard seulement ; `gh` n'est appelé qu'avec --run. Code de retour : 0 si au moins un
fichier de durées est fusionné, 1 sinon.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

PREFIXE = "test-durations-"
Gh = Callable[[list[str]], tuple[int, str]]


def gh_reel(args: list[str]) -> tuple[int, str]:
    """Seul point d'appel de la CLI gh : renvoie (code de retour, sortie)."""
    try:
        r = subprocess.run(
            ["gh", *args], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600
        )
    except (OSError, subprocess.TimeoutExpired) as erreur:
        return 1, f"{type(erreur).__name__} : {erreur}"
    return r.returncode, r.stdout if r.returncode == 0 else (r.stderr or r.stdout)


def telecharger(gh: Gh, run: str, repo: str | None, cible: Path) -> None:
    """Télécharge tous les artefacts `test-durations-*` du run dans `cible` (un sous-dossier chacun)."""
    args = ["run", "download", run, "--pattern", PREFIXE + "*", "--dir", str(cible)]
    if repo:
        args += ["--repo", repo]
    code, sortie = gh(args)
    if code != 0:
        raise RuntimeError(f"gh run download a échoué : {sortie.strip()[:300]}")


def nom_os(fichier: Path) -> str | None:
    """OS d'un fichier de durées : dossier d'artefact `test-durations-<os>-<n>`, sinon nom du fichier."""
    parent = fichier.parent.name
    if parent.startswith(PREFIXE):
        return re.sub(r"-\d+$", "", parent[len(PREFIXE) :]) or None
    if fichier.stem.startswith(PREFIXE):
        return fichier.stem[len(PREFIXE) :] or None
    return None


def lire_durees(dossier: Path) -> dict[str, dict[str, float]]:
    """{os: {test: durée}} ; un fichier illisible ou qui n'est pas un dict de nombres est ignoré."""
    par_os: dict[str, dict[str, float]] = {}
    for fichier in sorted(dossier.rglob("*.json")):
        os_ = nom_os(fichier)
        if not os_:
            continue
        try:
            donnees = json.loads(fichier.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(donnees, dict):
            continue
        cible = par_os.setdefault(os_, {})
        for test, duree in donnees.items():
            if isinstance(duree, (int, float)) and not isinstance(duree, bool):
                # Deux fichiers qui citent le même test : on garde la plus grande durée.
                cible[test] = max(duree, cible.get(test, 0.0))
    return {os_: d for os_, d in par_os.items() if d}


def repartir(durees: dict[str, float], groupes: int, algo: str = "blocs") -> list[float]:
    """Total de chaque groupe. `blocs` : tranches consécutives de durée voisine (pytest-split, par défaut) ;
    `glouton` : chaque test, du plus long au plus court, dans le groupe le moins chargé."""
    totaux = [0.0] * groupes
    if algo == "glouton":
        for duree in sorted(durees.values(), reverse=True):
            totaux[totaux.index(min(totaux))] += duree
        return totaux
    cible = sum(durees.values()) / groupes
    g = 0
    for test in sorted(durees):
        if g < groupes - 1 and totaux[g] >= cible:
            g += 1
        totaux[g] += durees[test]
    return totaux


def ecrire(par_os: dict[str, dict[str, float]], dossier: Path) -> list[Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    ecrits = []
    for os_, durees in sorted(par_os.items()):
        chemin = dossier / f"{PREFIXE}{os_}.json"
        contenu = {t: round(d, 6) for t, d in sorted(durees.items())}
        chemin.write_text(json.dumps(contenu, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ecrits.append(chemin)
    return ecrits


def minutes(secondes: float) -> str:
    m, s = divmod(round(secondes), 60)
    return f"{m} min {s:02d}"


def resume(par_os: dict[str, dict[str, float]], groupes: int, algo: str) -> str:
    lignes = []
    for os_, durees in sorted(par_os.items()):
        totaux = repartir(durees, groupes, algo)
        ecart = max(totaux) - min(totaux)
        lignes.append(
            f"{os_} : {len(durees)} tests, total {minutes(sum(durees.values()))}, "
            f"{groupes} groupes ({algo}) de {minutes(min(totaux))} à {minutes(max(totaux))}, écart {minutes(ecart)}"
            + (" : à rafraîchir si l'écart dépasse 2 min" if ecart > 120 else "")
        )
    return "\n".join(lignes)


def principal(argv: list[str] | None = None, gh: Gh = gh_reel) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--run", help="identifiant du run GitHub Actions dont on télécharge les artefacts")
    source.add_argument("--depuis", type=Path, help="dossier déjà téléchargé (sans gh)")
    p.add_argument("--repo", help="OWNER/NOM (sinon le dépôt courant)")
    p.add_argument("--dossier", type=Path, default=Path("."), help="où écrire test-durations-<os>.json")
    p.add_argument("--groupes", type=int, default=4)
    p.add_argument("--algo", choices=("blocs", "glouton"), default="blocs")
    a = p.parse_args(argv)
    if a.groupes < 1:
        p.error("--groupes doit être au moins 1")
    try:
        if a.run:
            with tempfile.TemporaryDirectory() as tmp:
                telecharger(gh, a.run, a.repo, Path(tmp))
                par_os = lire_durees(Path(tmp))
        else:
            par_os = lire_durees(a.depuis)
    except RuntimeError as erreur:
        print(erreur, file=sys.stderr)
        return 1
    if not par_os:
        print("Aucun fichier test-durations-<os> exploitable.", file=sys.stderr)
        return 1
    for chemin in ecrire(par_os, a.dossier):
        print(f"écrit : {chemin}")
    print(resume(par_os, a.groupes, a.algo))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
