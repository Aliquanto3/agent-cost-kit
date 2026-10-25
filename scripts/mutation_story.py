"""Mutation guidée (expérimental) : cosmic-ray borné aux lignes d'une story.

Mute seulement les lignes ajoutées ou modifiées par la story (`git diff -U0 <base> HEAD`),
lance seulement les tests de la story, sous un budget de temps, puis écrit les survivants
dédoublonnés par ligne (survivants.json et survivants.md). Stdlib seulement ; cosmic-ray est
lancé par `uv run --with cosmic-ray` dans le dépôt cible, sans toucher à son pyproject.

Usage :
  uv run --no-project python scripts/mutation_story.py --worktree <wt> --base <sha> \
      [--modules a.py,b.py] [--tests tests/test_a.py] [--budget-min 10] [--timeout-test 60] [--out <dossier>]

Outillage repris de T4 (`mutation_story.py`) et T10 (`mutation.py`) du dépôt veille-agents-code
(même auteur, Apache-2.0), rendu générique et portable Windows/Linux.
Les sources sont toujours restaurées à la fin, même si le budget tombe pendant un mutant.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
NOTE_EXC = (
    "`CosmicRayTestingException` : classe d'exception jamais levée, donc l'`except` concerné "
    "n'attrape plus rien."
)


def run(cmd, cwd, timeout=None):
    return subprocess.run(
        cmd,
        check=False,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=ENV,
    )


def kill_tree(proc: subprocess.Popen) -> None:
    """Tue le processus et ses descendants (Windows et Linux)."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def est_test(chemin: str) -> bool:
    p = Path(chemin)
    return (
        p.name.startswith("test_") or p.name.endswith("_test.py") or "tests" in p.parts
    )


def fichiers_story(wt: Path, base: str) -> tuple[list[str], list[str]]:
    """(sources, tests) .py ajoutés ou modifiés entre base et HEAD."""
    out = run(
        ["git", "diff", "--name-only", "--diff-filter=AM", base, "HEAD"], wt
    ).stdout
    py = [f for f in out.splitlines() if f.endswith(".py")]
    return [f for f in py if not est_test(f)], [f for f in py if est_test(f)]


def lignes_ajoutees(wt: Path, base: str, module: str) -> set[int]:
    out = run(["git", "diff", "-U0", base, "HEAD", "--", module], wt).stdout
    lignes: set[int] = set()
    for m in re.finditer(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", out, re.MULTILINE):
        debut, n = int(m.group(1)), int(m.group(2) or 1)
        lignes.update(range(debut, debut + n))
    return lignes


def spans_annotations(source: str) -> list[tuple[int, int, int, int]]:
    """Positions des annotations de type : un mutant dedans est sans effet à l'exécution."""
    spans = []
    for node in ast.walk(ast.parse(source)):
        anns = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = node.args
            for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg]:
                if arg is not None and arg.annotation is not None:
                    anns.append(arg.annotation)
            if node.returns is not None:
                anns.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            anns.append(node.annotation)
        spans += [
            (x.lineno, x.col_offset, x.end_lineno, x.end_col_offset) for x in anns
        ]
    return spans


def dans_span(row: int, col: int, spans) -> bool:
    return any((sr, sc) <= (row, col) < (er, ec) for sr, sc, er, ec in spans)


def diff_une_ligne(diff: str) -> list[str]:
    return [
        ligne
        for ligne in (diff or "").splitlines()
        if ligne[:1] in "+-" and not ligne.startswith(("---", "+++"))
    ]


def dedoublonner(survivants: list[dict]) -> list[dict]:
    """Une entrée par ligne de code : la première mutation, plus le nombre des autres."""
    par_ligne: dict[tuple[str, int], dict] = {}
    for s in survivants:
        cle = (s["module"], s["line"])
        if cle in par_ligne:
            par_ligne[cle]["autres_mutations"] += 1
        else:
            par_ligne[cle] = {**s, "autres_mutations": 0}
    return sorted(par_ligne.values(), key=lambda s: (s["module"], s["line"]))


def markdown(resultat: dict, uniques: list[dict]) -> str:
    c = resultat["totaux"]
    out = [
        "Mutations survivantes (fichier:ligne, fonction, diff) :",
        "",
        (
            f"<!-- générés {c['generes']}, exécutés {c['executes']}, tués {c['tues']}, "
            f"survivants {c['survivants']}, non exécutés faute de budget {c['non_executes']} -->"
        ),
    ]
    for i, s in enumerate(uniques, 1):
        autres = (
            f" (+{s['autres_mutations']} autre(s) sur la ligne)"
            if s["autres_mutations"]
            else ""
        )
        out.append(f"M{i} `{s['module']}:{s['line']}` (`{s['function']}`){autres}")
        out += [f"  {ligne[0]} {ligne[1:].strip()}" for ligne in s["diff"]]
    if any("CosmicRayTestingException" in "".join(s["diff"]) for s in uniques):
        out.append(f"({NOTE_EXC})")
    out += [
        "",
        (
            f"Compteurs : {c['generes']} générés, {c['executes']} exécutés, {c['tues']} tués, "
            f"{c['survivants']} survivants ({len(uniques)} lignes), "
            f"{c['non_executes']} non exécutés faute de budget."
        ),
    ]
    return "\n".join(out) + "\n"


def lanceur(python: str | None) -> list[str]:
    """Préfixe de commande avec cosmic-ray et pytest ajoutés par `uv run --with`, sans toucher au projet.

    L'environnement éphémère de uv disparaît à la fin de chaque commande : on ne garde pas son chemin.
    """
    if python:
        return [python]
    return ["uv", "run", "--with", "cosmic-ray", "--with", "pytest", "python"]


def muter_module(wt, module, py, tests, test_cmd, args, deadline, tmp) -> dict:
    nom = Path(module).stem
    cfg, db = tmp / f"cr-{nom}.toml", tmp / f"cr-{nom}.sqlite"
    db.unlink(missing_ok=True)
    cfg.write_text(
        "[cosmic-ray]\n"
        f"module-path = {json.dumps(module)}\n"
        f"timeout = {args.timeout_test}\n"
        "excluded-modules = []\n"
        f"test-command = {json.dumps(test_cmd)}\n\n"
        '[cosmic-ray.distributor]\nname = "local"\n',
        encoding="utf-8",
    )
    cr = [*py, "-m", "cosmic_ray.cli"]
    p = run([*cr, "init", str(cfg), str(db)], wt)
    if p.returncode != 0:
        sys.exit(f"cosmic-ray init a échoué : {p.stdout[-400:]} {p.stderr[-400:]}")

    con = sqlite3.connect(db)
    rows = con.execute(
        "select job_id, start_pos_row, start_pos_col from mutation_specs"
    ).fetchall()
    spans = spans_annotations((wt / module).read_text(encoding="utf-8"))
    garde = None if args.no_diff_filter else lignes_ajoutees(wt, args.base, module)
    retirer, ann, hors = [], 0, 0
    for job, row, col in rows:
        if dans_span(row, col, spans):
            retirer.append(job)
            ann += 1
        elif garde is not None and row not in garde:
            retirer.append(job)
            hors += 1
    for job in retirer:
        con.execute("delete from mutation_specs where job_id=?", (job,))
        con.execute("delete from work_items where job_id=?", (job,))
    con.commit()
    con.close()
    effectifs = len(rows) - len(retirer)

    restant = deadline - time.time()
    budget_depasse = False
    if effectifs and restant > 5:
        kw = {"start_new_session": True} if os.name != "nt" else {}
        proc = subprocess.Popen(
            [*cr, "exec", str(cfg), str(db)],
            cwd=wt,
            env=ENV,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kw,
        )
        try:
            proc.wait(timeout=restant)
        except subprocess.TimeoutExpired:
            kill_tree(proc)
            budget_depasse = True
    elif effectifs:
        budget_depasse = True

    con = sqlite3.connect(db)
    res = con.execute(
        "select w.test_outcome, w.diff, s.start_pos_row, s.operator_name, s.definition_name "
        "from work_results w join mutation_specs s using (job_id) order by s.job_id"
    ).fetchall()
    con.close()
    surv = [
        {
            "module": module,
            "line": r[2],
            "operator": r[3],
            "function": r[4],
            "diff": diff_une_ligne(r[1]),
        }
        for r in res
        if r[0] == "SURVIVED"
    ]
    return {
        "module": module,
        "generes": len(rows),
        "exclus_annotations": ann,
        "exclus_hors_diff": hors,
        "effectifs": effectifs,
        "executes": len(res),
        "tues": sum(1 for r in res if r[0] == "KILLED"),
        "survivants": len(surv),
        "non_executes": effectifs - len(res),
        "budget_depasse": budget_depasse,
        "liste_survivants": surv,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--worktree", required=True, help="dépôt (ou worktree) de la story")
    ap.add_argument("--base", required=True, help="commit avant la story")
    ap.add_argument(
        "--modules",
        help="sources à muter, séparées par des virgules (défaut : sources du diff)",
    )
    ap.add_argument(
        "--tests",
        help="fichiers de tests de la story (défaut : tests touchés par le diff)",
    )
    ap.add_argument("--budget-min", type=float, default=10.0)
    ap.add_argument(
        "--timeout-test", type=float, default=60.0, help="secondes par mutant"
    )
    ap.add_argument(
        "--out", help="dossier de sortie (défaut : dossier temporaire, hors dépôt)"
    )
    ap.add_argument(
        "--python",
        help="interpréteur déjà prêt (cosmic-ray et pytest installés), au lieu de uv run --with",
    )
    ap.add_argument(
        "--no-diff-filter", action="store_true", help="garde les mutants hors diff"
    )
    args = ap.parse_args(argv)

    wt = Path(args.worktree).resolve()
    out = (
        Path(args.out)
        if args.out
        else Path(tempfile.gettempdir()) / "mutation-story" / wt.name
    )
    out.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + args.budget_min * 60

    sources, tests_diff = fichiers_story(wt, args.base)
    modules = [m for m in args.modules.split(",") if m] if args.modules else sources
    tests = [t for t in args.tests.split(",") if t] if args.tests else tests_diff
    if not modules or not tests:
        sys.exit(
            f"rien à muter ou aucun test de story (sources {modules}, tests {tests})"
        )

    py = lanceur(args.python)
    test_cmd = " ".join(
        [
            *(shlex.quote(Path(c).as_posix() if os.sep in c else c) for c in py),
            "-m",
            "pytest",
            "-x",
            "-q",
            "--tb=no",
            "-p",
            "no:cacheprovider",
            *(shlex.quote(t) for t in tests),
        ]
    )
    # suite cible hors mutation : doit être verte
    t0 = time.time()
    p = run(
        [*py, "-m", "pytest", "-x", "-q", "--tb=no", "-p", "no:cacheprovider", *tests],
        wt,
    )
    if p.returncode != 0:
        sys.exit(f"suite cible rouge sans mutation :\n{p.stdout[-500:]}")
    duree_tests = round(time.time() - t0, 1)

    sauvegarde = {m: (wt / m).read_bytes() for m in modules}
    resultats = []
    try:
        with tempfile.TemporaryDirectory(prefix="cr-") as t:
            for m in modules:
                resultats.append(
                    muter_module(wt, m, py, tests, test_cmd, args, deadline, Path(t))
                )
    finally:
        for m, brut in sauvegarde.items():
            (wt / m).write_bytes(brut)

    survivants = [s for r in resultats for s in r["liste_survivants"]]
    uniques = dedoublonner(survivants)
    totaux = {
        "generes": sum(r["generes"] for r in resultats),
        "executes": sum(r["executes"] for r in resultats),
        "tues": sum(r["tues"] for r in resultats),
        "survivants": len(survivants),
        "non_executes": sum(r["non_executes"] for r in resultats),
    }
    resultat = {
        "base": args.base,
        "tests": tests,
        "modules": modules,
        "secondes_tests": duree_tests,
        "budget_min": args.budget_min,
        "secondes_total": round(time.time() - (deadline - args.budget_min * 60), 1),
        "totaux": totaux,
        "par_module": [
            {k: v for k, v in r.items() if k != "liste_survivants"} for r in resultats
        ],
        "survivants": uniques,
    }
    (out / "survivants.json").write_text(
        json.dumps(resultat, ensure_ascii=False, indent=1), "utf-8"
    )
    (out / "survivants.md").write_text(markdown(resultat, uniques), "utf-8")
    print(markdown(resultat, uniques))
    print(f"Sorties : {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
