"""Ménage de clôture d'un run autonome : worktrees, verrous et branches des stories fusionnées.

Simulation par défaut : rien n'est modifié sans `--appliquer`. Les branches distantes ne sont supprimées
qu'avec `--appliquer --distant` ; la simulation les liste toujours.

Une branche (ou un worktree) est retirée si sa tête est dans la branche par défaut : ancêtre, patchs
équivalents (`git cherry`), ou PR fusionnée dans la branche par défaut dont la tête est ce commit. Sont toujours
gardés : la branche par défaut, la branche du worktree principal, les branches d'une PR ouverte, toutes les
branches si gh est indisponible, un worktree avec des fichiers ignorés non régénérables, et tout ce qui a eu
une activité (commit ou reflog) de moins de `--age-min-heures`.

Usage : python scripts/menage_run.py [--depot DOSSIER] [--distant-nom origin] [--branche-defaut main]
        [--age-min-heures 24] [--fetch] [--appliquer] [--distant] [--json]

Code de retour : 0 si tout va bien, 1 si une suppression a échoué, 2 en cas d'erreur d'usage.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

Git = Callable[[list[str]], tuple[int, str]]
Gh = Callable[[list[str], Path], tuple[int, str]]
Vivant = Callable[[int], bool]

LIMITE_PR = 1000
# Fichiers ignorés régénérables : un worktree qui n'a que ceux-là est retirable (le reste, `.env` par exemple, le garde).
REGENERABLES = (".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox",
                ".nox", "dist", "build", "*.egg-info", ".coverage", "htmlcov", "*.pyc", ".hypothesis")
SANS_GH = "gh indisponible, PR ouvertes non vérifiables"


class ErreurUsage(Exception):
    """Erreur d'usage (code 2)."""


def git_reel(args: list[str]) -> tuple[int, str]:
    """Seul point d'appel de git : renvoie (code de retour, sortie standard)."""
    try:
        r = subprocess.run(
            ["git", *args], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300
        )
    except (OSError, subprocess.TimeoutExpired) as erreur:
        return 1, f"{type(erreur).__name__} : {erreur}"
    return r.returncode, r.stdout if r.returncode == 0 else (r.stderr.strip() or r.stdout)


def gh_reel(args: list[str], cwd: Path) -> tuple[int, str]:
    """Seul point d'appel de la CLI gh : renvoie (code de retour, sortie)."""
    try:
        r = subprocess.run(
            ["gh", *args], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired) as erreur:
        return 1, f"{type(erreur).__name__} : {erreur}"
    return r.returncode, r.stdout if r.returncode == 0 else (r.stderr.strip() or r.stdout)


def pid_vivant(pid: int) -> bool:
    """Vrai si le processus existe encore (Windows : ctypes ; POSIX : signal 0)."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        noyau = ctypes.WinDLL("kernel32", use_last_error=True)
        noyau.OpenProcess.restype = wintypes.HANDLE
        noyau.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        noyau.GetExitCodeProcess.restype = wintypes.BOOL
        noyau.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        noyau.CloseHandle.argtypes = (wintypes.HANDLE,)
        poignee = noyau.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not poignee:
            # ERROR_INVALID_PARAMETER : PID inexistant ; toute autre erreur (accès refusé...) : dans le doute, vivant.
            return ctypes.get_last_error() != 87
        try:
            code = wintypes.DWORD()
            if not noyau.GetExitCodeProcess(poignee, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            noyau.CloseHandle(poignee)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


@dataclass
class Ctx:
    git: Git
    depot: Path
    distant: str
    defaut: str
    ref: str
    seuil_s: float
    maintenant: float
    prs: list[dict] | None  # None : gh indisponible
    vivant: Vivant = pid_vivant
    principale: str | None = None
    extraits: dict[str, str] = field(default_factory=dict)

    def g(self, args: list[str], cwd: str | Path | None = None) -> tuple[int, str]:
        return self.git(["-C", str(cwd or self.depot), *args])


def court(sha: str) -> str:
    return sha[:7]


def lire_prs(gh: Gh, depot: Path) -> list[dict] | None:
    """Toutes les PR du dépôt, ou None si gh échoue ou si la liste atteint la limite (peut-être tronquée)."""
    champs = "number,state,headRefName,headRefOid,baseRefName,isCrossRepository"
    code, sortie = gh(["pr", "list", "--state", "all", "--limit", str(LIMITE_PR), "--json", champs], depot)
    try:
        donnees = json.loads(sortie)
    except ValueError:
        return None
    if code != 0 or not isinstance(donnees, list) or len(donnees) >= LIMITE_PR:
        return None
    return donnees


def branche_defaut(git: Git, depot: Path, distant: str, demandee: str | None) -> str:
    """Branche par défaut : option, sinon origin/HEAD, sinon main ou master."""
    if demandee:
        return demandee
    code, sortie = git(["-C", str(depot), "symbolic-ref", f"refs/remotes/{distant}/HEAD"])
    prefixe = f"refs/remotes/{distant}/"
    if code == 0 and sortie.strip().startswith(prefixe):
        return sortie.strip()[len(prefixe):]
    for nom in ("main", "master"):
        for ref in (f"refs/heads/{nom}", f"refs/remotes/{distant}/{nom}"):
            if git(["-C", str(depot), "rev-parse", "--verify", "--quiet", ref])[0] == 0:
                return nom
    raise ErreurUsage("branche par défaut introuvable (utiliser --branche-defaut)")


def reference(git: Git, depot: Path, distant: str, defaut: str) -> str:
    """`<distant>/<defaut>` si la ref existe, sinon la branche locale."""
    for ref in (f"refs/remotes/{distant}/{defaut}", f"refs/heads/{defaut}"):
        if git(["-C", str(depot), "rev-parse", "--verify", "--quiet", ref])[0] == 0:
            return ref
    raise ErreurUsage(f"référence de la branche par défaut '{defaut}' introuvable")


def contenu(ctx: Ctx, branche: str | None, tete: str) -> str | None:
    """Motif pour lequel le commit `tete` est dans la branche par défaut, sinon None."""
    if ctx.g(["merge-base", "--is-ancestor", tete, ctx.ref])[0] == 0:
        return "ancêtre"
    code, sortie = ctx.g(["cherry", ctx.ref, tete])
    if code == 0 and not any(ligne.startswith("+") for ligne in sortie.splitlines()):
        return "patchs équivalents"
    for pr in ctx.prs or []:
        if (pr.get("state") == "MERGED" and branche and pr.get("headRefName") == branche
                and pr.get("headRefOid") == tete and pr.get("baseRefName") == ctx.defaut
                and not pr.get("isCrossRepository")):
            return f"PR #{pr['number']} fusionnée"
    return None


def horodatage_reflog(ctx: Ctx, refname: str, cwd: str | Path | None = None) -> float | None:
    """Date de la dernière entrée du reflog de `refname`, None s'il n'y en a pas."""
    code, sortie = ctx.g(["reflog", "show", "-1", "--date=unix", "--format=%gd", refname], cwd)
    m = re.search(r"@\{(\d+)\}", sortie) if code == 0 else None
    return float(m[1]) if m else None


def exclusion(ctx: Ctx, branche: str | None, tete: str, reflog: float | None) -> str | None:
    """Motif d'exclusion (prioritaire sur « contenu »), sinon None."""
    if branche == ctx.defaut:
        return "branche par défaut"
    for pr in ctx.prs or []:
        if (pr.get("state") == "OPEN" and branche and pr.get("headRefName") == branche
                and not pr.get("isCrossRepository")):
            return f"PR #{pr['number']} ouverte"
    code, sortie = ctx.g(["log", "-1", "--format=%ct", tete])
    if code == 0 and sortie.strip().isdigit() and ctx.maintenant - float(sortie.strip()) < ctx.seuil_s:
        return "activité récente (commit)"
    if reflog is not None and ctx.maintenant - reflog < ctx.seuil_s:
        return "activité récente (reflog)"
    return None


def lire_worktrees(ctx: Ctx) -> list[dict]:
    """Worktrees hors principal : {chemin, tete, branche, verrou, prunable}."""
    code, sortie = ctx.g(["worktree", "list", "--porcelain"])
    if code != 0:
        raise ErreurUsage(f"pas un dépôt git : {sortie.strip()[:200]}")
    blocs, courant = [], None
    for ligne in sortie.splitlines():
        if ligne.startswith("worktree "):
            courant = {"chemin": ligne[9:], "tete": "", "branche": None, "verrou": None, "prunable": False}
            blocs.append(courant)
        elif courant is None or not ligne:
            continue
        elif ligne.startswith("HEAD "):
            courant["tete"] = ligne[5:].strip()
        elif ligne.startswith("branch refs/heads/"):
            courant["branche"] = ligne[18:].strip()
        elif ligne == "locked" or ligne.startswith("locked "):
            courant["verrou"] = ligne[7:].strip()
        elif ligne.startswith("prunable"):
            courant["prunable"] = True
    if blocs:
        ctx.principale = blocs[0]["branche"]
    return blocs[1:]


def regenerable(chemin: str) -> bool:
    """Vrai si un élément du chemin (fichier ou dossier ignoré) est dans REGENERABLES."""
    return any(fnmatch.fnmatch(partie, motif) for partie in chemin.strip("/").split("/") for motif in REGENERABLES)


def analyser_worktree(ctx: Ctx, wt: dict) -> dict:
    """Décision pour un worktree : action retirer|prune|garder, motif, PID de verrou à lever."""
    r = {"chemin": wt["chemin"], "sha": court(wt["tete"]), "branche": wt["branche"], "action": "garder",
         "motif": "", "deverrouiller": None}
    if wt["prunable"]:
        return {**r, "action": "prune", "motif": "dossier disparu"}
    if wt["verrou"] is not None:
        m = re.search(r"pid[ :=]*(\d+)", wt["verrou"], re.IGNORECASE)
        if not m:
            return {**r, "motif": "verrou sans PID"}
        pid = int(m[1])
        if ctx.vivant(pid):
            return {**r, "motif": f"verrou, PID {pid} vivant"}
        r["deverrouiller"] = pid
    code, sortie = ctx.g(["status", "--porcelain"], wt["chemin"])
    if code != 0:
        return {**r, "motif": f"état illisible : {sortie.strip()[:100]}"}
    if sortie.strip():
        return {**r, "motif": "modifié"}
    code, sortie = ctx.g(["ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z"], wt["chemin"])
    if code != 0:
        return {**r, "motif": f"fichiers ignorés illisibles : {sortie.strip()[:100]}"}
    precieux = [f for f in sortie.split("\0") if f and not regenerable(f)]
    if precieux:
        noms = ", ".join(precieux[:3]) + (", ..." if len(precieux) > 3 else "")
        return {**r, "motif": f"fichiers ignorés non régénérables : {noms}"}
    exclu = exclusion(ctx, wt["branche"], wt["tete"], horodatage_reflog(ctx, "HEAD", wt["chemin"]))
    if exclu:
        return {**r, "motif": exclu}
    motif = contenu(ctx, wt["branche"], wt["tete"])
    if not motif:
        return {**r, "motif": "non fusionné"}
    suffixe = f", verrou levé (PID {r['deverrouiller']} disparu)" if r["deverrouiller"] else ""
    return {**r, "action": "retirer", "motif": motif + suffixe}


def analyser_branche(ctx: Ctx, nom: str, sha: str, locale: bool) -> dict:
    """Décision pour une branche locale ou distante : action supprimer|garder, motif."""
    r = {"nom": nom, "sha": court(sha), "tete": sha, "action": "garder", "motif": ""}
    if locale and nom in ctx.extraits:
        return {**r, "motif": f"extraite dans {ctx.extraits[nom]}"}
    if nom == ctx.principale:
        return {**r, "motif": "extraite dans le worktree principal"}
    if ctx.prs is None:
        return {**r, "motif": SANS_GH}
    # Pour une distante aussi, le reflog lu est celui de la branche locale homonyme : protection en plus.
    reflog = horodatage_reflog(ctx, f"refs/heads/{nom}")
    exclu = exclusion(ctx, nom, sha, reflog)
    if exclu:
        return {**r, "motif": exclu}
    motif = contenu(ctx, nom, sha)
    if not motif:
        return {**r, "motif": "non fusionnée"}
    return {**r, "action": "supprimer", "motif": motif}


def lister_refs(ctx: Ctx, prefixe: str) -> list[tuple[str, str]]:
    code, sortie = ctx.g(["for-each-ref", "--format=%(refname)%09%(objectname)", prefixe])
    refs = []
    for ligne in sortie.splitlines() if code == 0 else []:
        ref, _, sha = ligne.partition("\t")
        if ref.startswith(prefixe):
            refs.append((ref[len(prefixe):], sha))
    return refs


def analyser(ctx: Ctx) -> dict:
    """Plan complet du ménage (sans rien modifier)."""
    wts = [analyser_worktree(ctx, wt) for wt in lire_worktrees(ctx)]
    ctx.extraits = {w["branche"]: w["chemin"] for w in wts if w["branche"] and w["action"] == "garder"}
    locales = [analyser_branche(ctx, n, s, True) for n, s in lister_refs(ctx, "refs/heads/") if n != ctx.defaut]
    distantes = [analyser_branche(ctx, n, s, False) for n, s in lister_refs(ctx, f"refs/remotes/{ctx.distant}/")
                 if n not in ("HEAD", ctx.defaut)]
    return {"worktrees": wts, "locales": locales, "distantes": distantes}


def appliquer(ctx: Ctx, plan: dict, avec_distant: bool) -> dict:
    """Exécute le plan dans l'ordre : verrous, worktrees, prune, branches locales, distantes."""
    res = {"verrous_leves": [], "retires": [], "pruned": False, "locales": [], "distantes": [], "erreurs": []}
    for w in plan["worktrees"]:
        if w["deverrouiller"]:
            code, sortie = ctx.g(["worktree", "unlock", w["chemin"]])
            if code == 0:
                res["verrous_leves"].append(w["chemin"])
            else:
                res["erreurs"].append(f"déverrouillage de {w['chemin']} : {sortie.strip()[:200]}")
                w.update(action="garder", motif="verrou non levé")
    for w in plan["worktrees"]:
        if w["action"] != "retirer":
            continue
        code, sortie = ctx.g(["worktree", "remove", w["chemin"]])
        if code == 0:
            res["retires"].append(w["chemin"])
        else:
            res["erreurs"].append(f"retrait de {w['chemin']} : {sortie.strip()[:200]}")
            w.update(action="garder", motif="retrait refusé")
            if w["branche"]:
                ctx.extraits[w["branche"]] = w["chemin"]
    if any(w["action"] == "prune" for w in plan["worktrees"]):
        code, sortie = ctx.g(["worktree", "prune"])
        if code == 0:
            res["pruned"] = True
        else:
            res["erreurs"].append(f"worktree prune : {sortie.strip()[:200]}")
    for b in plan["locales"]:
        if b["action"] != "supprimer":
            continue
        if b["nom"] in ctx.extraits:
            b.update(action="garder", motif=f"extraite dans {ctx.extraits[b['nom']]}")
            continue
        option = "-d" if b["motif"] == "ancêtre" else "-D"
        code, sortie = ctx.g(["branch", option, b["nom"]])
        if code == 0:
            res["locales"].append(b)
        else:
            res["erreurs"].append(f"branche {b['nom']} : {sortie.strip()[:200]}")
    for b in plan["distantes"] if avec_distant else []:
        if b["action"] != "supprimer":
            continue
        # Bail sur le sha analysé : si la branche a bougé sur le distant, git refuse la suppression.
        ref = f"refs/heads/{b['nom']}"
        code, sortie = ctx.g(["push", f"--force-with-lease={ref}:{b['tete']}", ctx.distant, f":{ref}"])
        if code == 0:
            res["distantes"].append(b)
        else:
            res["erreurs"].append(f"distante {b['nom']} non supprimée : {sortie.strip()[:300]}")
    return res


def ligne_journal(res: dict, quand: datetime) -> str:
    """Ligne prête à coller dans le journal de run-autonome.md."""
    n = len(res["retires"]) + (1 if res["pruned"] else 0)
    return (f"- {quand:%Y-%m-%d %H:%M} · run · ménage · {n} worktrees retirés, {len(res['verrous_leves'])} verrous levés, "
            f"{len(res['locales'])} branches locales, {len(res['distantes'])} distantes supprimées · —")


def rapport(ctx: Ctx, plan: dict, res: dict | None, avec_distant: bool, quand: datetime) -> str:
    """Rapport Markdown du plan (simulation) ou du résultat."""
    def puce(verbe: str, nom: str, sha: str, motif: str) -> str:
        return f"- {verbe} `{nom}` {sha} : {motif}"

    L = [f"# Ménage de clôture ({'appliqué' if res else 'simulation'}) : référence `{ctx.ref}`", "", "## Worktrees", ""]
    for w in plan["worktrees"]:
        verbe = {"retirer": "retirer", "prune": "prune", "garder": "garder"}[w["action"]]
        L.append(puce(verbe, w["chemin"], w["sha"], w["motif"]))
    if not plan["worktrees"]:
        L.append("- aucun")
    L += ["", "## Verrous", ""]
    verrous = [w for w in plan["worktrees"] if w["deverrouiller"] or "verrou" in w["motif"]]
    for w in verrous:
        L.append(puce("lever" if w["deverrouiller"] else "laisser", w["chemin"], w["sha"], w["motif"]))
    if not verrous:
        L.append("- aucun")
    for titre, cle in (("Branches locales", "locales"), ("Branches distantes", "distantes")):
        L += ["", f"## {titre}", ""]
        for b in plan[cle]:
            L.append(puce("supprimer" if b["action"] == "supprimer" else "garder", b["nom"], b["sha"], b["motif"]))
        if not plan[cle]:
            L.append("- aucune")
    L.append("")
    if res is None:
        suite = "relancer avec `--appliquer`"
        if any(b["action"] == "supprimer" for b in plan["distantes"]):
            suite += ", puis `--appliquer --distant` après avoir montré la liste des branches distantes à Anaël"
        L.append(f"Simulation : rien n'a été modifié ; {suite}.")
        return "\n".join(L) + "\n"
    if res["erreurs"]:
        L += ["## Erreurs", ""] + [f"- {e}" for e in res["erreurs"]] + [""]
    restauration = [f"git branch {b['nom']} {b['tete']}" for b in res["locales"]]
    restauration += [f"git push {ctx.distant} {b['tete']}:refs/heads/{b['nom']}" for b in res["distantes"]]
    if restauration:
        L += ["## Restauration", ""] + [f"- `{ligne}`" for ligne in restauration] + [""]
    if not avec_distant and any(b["action"] == "supprimer" for b in plan["distantes"]):
        L += ["Branches distantes non supprimées (`--distant` absent).", ""]
    L += ["Ligne de journal :", "", ligne_journal(res, quand)]
    return "\n".join(L) + "\n"


def construire(argv: list[str] | None, git: Git, gh: Gh, vivant: Vivant, maintenant: float) -> tuple[argparse.Namespace, Ctx]:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--depot", type=Path, default=Path.cwd())
    p.add_argument("--distant-nom", default="origin")
    p.add_argument("--branche-defaut")
    p.add_argument("--age-min-heures", type=float, default=24)
    p.add_argument("--fetch", action="store_true", help="git fetch --prune avant l'analyse")
    p.add_argument("--appliquer", action="store_true")
    p.add_argument("--distant", action="store_true", help="avec --appliquer : supprime aussi les branches distantes")
    p.add_argument("--json", action="store_true")
    o = p.parse_args(argv)
    depot = o.depot.resolve()
    if git(["-C", str(depot), "rev-parse", "--git-dir"])[0] != 0:
        raise ErreurUsage(f"{depot} n'est pas un dépôt git")
    if o.fetch:
        code, sortie = git(["-C", str(depot), "fetch", "--prune", o.distant_nom])
        if code != 0:
            print(f"Avertissement : fetch en échec ({sortie.strip()[:200]}).", file=sys.stderr)
    defaut = branche_defaut(git, depot, o.distant_nom, o.branche_defaut)
    ref = reference(git, depot, o.distant_nom, defaut)
    prs = lire_prs(gh, depot)
    if prs is None:
        print(f"Avertissement : gh indisponible ou plus de {LIMITE_PR - 1} PR ; aucune branche ne sera supprimée "
              "(worktrees et verrous seulement).", file=sys.stderr)
        if o.distant:
            raise ErreurUsage("--distant refusé sans gh (PR ouvertes non vérifiables)")
    ctx = Ctx(git, depot, o.distant_nom, defaut, ref, o.age_min_heures * 3600, maintenant, prs, vivant)
    return o, ctx


def main(argv: list[str] | None = None, git: Git = git_reel, gh: Gh = gh_reel, vivant: Vivant = pid_vivant,
         maintenant: Callable[[], float] = time.time) -> int:
    try:
        o, ctx = construire(argv, git, gh, vivant, maintenant())
        plan = analyser(ctx)
        res = appliquer(ctx, plan, o.distant) if o.appliquer else None
    except ErreurUsage as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 2
    quand = datetime.fromtimestamp(maintenant())
    if o.json:
        sortie = {"simulation": res is None, "reference": ctx.ref, **plan}
        if res is not None:
            sortie["resultat"] = {**res, "locales": [b["nom"] for b in res["locales"]],
                                  "distantes": [b["nom"] for b in res["distantes"]],
                                  "journal": ligne_journal(res, quand)}
        print(json.dumps(sortie, ensure_ascii=False))
    else:
        print(rapport(ctx, plan, res, o.distant, quand), end="")
    return 1 if res and res["erreurs"] else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
