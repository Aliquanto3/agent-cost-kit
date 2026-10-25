"""Tests de scripts/mutation_story.py sur un petit dépôt de fixture (une fonction, un test faible)."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import mutation_story as ms

VIEUX = "def vieux(x):\n    return x + 1\n"
NEUF = "\ndef borne(x):\n    if x > 10:\n        return 10\n    return x\n"
TEST_FAIBLE = (
    "from calc import borne\n\n\ndef test_borne():\n    assert borne(5) == 5\n"
)
# Test qui s'endort dès que calc.py est muté : un mutant est alors en cours quand le budget tombe.
TEST_LENT = """import os
import time
from pathlib import Path

ORIG = {orig!r}
PID = {pid!r}


def test_lent():
    src = Path(__file__).with_name("calc.py").read_text(encoding="utf-8")
    if src.replace("\\r\\n", "\\n") != ORIG:
        Path(PID).write_text(str(os.getpid()), encoding="utf-8")
        time.sleep(300)
"""
PYPROJECT = '[project]\nname = "fixture"\nversion = "0"\nrequires-python = ">=3.10"\n'


@pytest.fixture(scope="module")
def outil():
    """Saut seulement si uv ou cosmic-ray est réellement indisponible ; tout autre échec fait
    échouer le test."""
    if shutil.which("uv") is None:
        pytest.skip("uv absent")
    p = subprocess.run(
        [
            *ms.lanceur(None)[:-1],
            "--no-project",
            "python",
            "-c",
            "import cosmic_ray, pytest",
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if p.returncode != 0:
        pytest.skip(f"cosmic-ray indisponible : {p.stderr[-300:]}")


def git(wt, *a):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
        cwd=wt,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture(scope="module")
def depot(tmp_path_factory):
    wt = tmp_path_factory.mktemp("fixture")
    pid = tmp_path_factory.mktemp("pid") / "mutant.pid"
    git(wt, "init", "-q")
    (wt / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    # projet uv, sans lock : ni .venv ni uv.lock ne doivent y apparaître
    (wt / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (wt / "calc.py").write_text(VIEUX, encoding="utf-8")
    git(wt, "add", ".")
    git(wt, "commit", "-qm", "base")
    base = git(wt, "rev-parse", "HEAD")
    (wt / "calc.py").write_text(VIEUX + NEUF, encoding="utf-8")
    (wt / "test_calc.py").write_text(TEST_FAIBLE, encoding="utf-8")
    (wt / "test_lent.py").write_text(
        TEST_LENT.format(orig=VIEUX + NEUF, pid=str(pid)), encoding="utf-8"
    )
    (wt / "tests").mkdir()
    (wt / "tests" / "aide.py").write_text("X = 1\n", encoding="utf-8")
    git(wt, "add", ".")
    git(wt, "commit", "-qm", "story")
    return wt, base, pid


def propre(wt):
    """Dépôt intact : rien de modifié ni d'ajouté (.venv, uv.lock), aucune copie enregistrée."""
    assert (wt / "calc.py").read_text(encoding="utf-8") == VIEUX + NEUF
    assert git(wt, "status", "--porcelain", "--ignored") == ""
    assert len(git(wt, "worktree", "list").splitlines()) == 1


def vivant(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        return f" {pid} " in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def args(depot, tmp_path, *extra):
    wt, base, _ = depot
    return [
        "--worktree",
        str(wt),
        "--base",
        base,
        "--out",
        str(tmp_path / "out"),
        *extra,
    ]


def test_fichiers_story_ignore_les_aides_de_tests(depot):
    wt, base, _ = depot
    assert ms.fichiers_story(wt, base) == (
        ["calc.py"],
        ["test_calc.py", "test_lent.py"],
    )


def test_survivant_dedoublonne_hors_diff_ignore_et_depot_intact(outil, depot, tmp_path):
    wt, _, _ = depot
    assert ms.main(args(depot, tmp_path, "--tests", "test_calc.py")) == 0
    res = json.loads((tmp_path / "out" / "survivants.json").read_text(encoding="utf-8"))
    assert res["tests"] == ["test_calc.py"]
    uniques = res["survivants"]
    # borne(5) == 5 ne voit ni la comparaison `x > 10` (ligne 5) ni la valeur 10 (ligne 6) ;
    # `vieux` (lignes 1 et 2) est hors diff.
    assert [s["line"] for s in uniques] == [5, 6]
    assert all(
        s["module"] == "calc.py" and s["function"].endswith("borne") for s in uniques
    )
    assert all(
        s["diff"][0].startswith("-") and s["diff"][1].startswith("+") for s in uniques
    )
    t = res["totaux"]
    assert t["survivants"] > len(uniques)  # plusieurs mutations de `x > 10` regroupées
    assert t["survivants"] == sum(1 + s["autres_mutations"] for s in uniques)
    assert t["non_executes"] == 0 and t["executes"] == t["tues"] + t["survivants"]
    assert res["par_module"][0]["exclus_hors_diff"] > 0
    md = (tmp_path / "out" / "survivants.md").read_text(encoding="utf-8")
    assert "M1 `calc.py:5`" in md and "M2 `calc.py:6`" in md
    propre(wt)


def test_budget_qui_tombe_pendant_un_mutant_tue_l_arbre(outil, depot, tmp_path):
    wt, _, pid = depot
    pid.unlink(missing_ok=True)
    t0 = time.time()
    rc = ms.main(
        args(
            depot,
            tmp_path,
            "--tests",
            "test_lent.py",
            "--budget-min",
            "1",
            "--timeout-test",
            "600",
        )
    )
    duree = time.time() - t0
    assert rc == 0
    assert duree < 60 + 45  # le mutant dort 300 s : il a bien été interrompu
    assert pid.exists(), "aucun mutant n'était en cours à l'échéance"
    assert not vivant(int(pid.read_text(encoding="utf-8")))  # arbre tué, pas d'orphelin
    res = json.loads((tmp_path / "out" / "survivants.json").read_text(encoding="utf-8"))
    assert res["par_module"][0]["budget_depasse"] is True
    assert res["totaux"]["executes"] == 0 and res["totaux"]["non_executes"] > 0
    propre(wt)


def test_budget_nul_borne_aussi_la_suite_de_reference(outil, depot, tmp_path):
    wt, _, _ = depot
    with pytest.raises(SystemExit, match="budget épuisé pendant la suite de référence"):
        ms.main(args(depot, tmp_path, "--tests", "test_calc.py", "--budget-min", "0"))
    propre(wt)


def test_script_tue_laisse_le_depot_propre_et_copie_retiree_ensuite(
    outil, depot, tmp_path
):
    wt, _, pid = depot
    pid.unlink(missing_ok=True)
    script = Path(ms.__file__).resolve()
    proc = ms.popen(
        [
            sys.executable,
            str(script),
            *args(depot, tmp_path, "--tests", "test_lent.py"),
        ],
        wt,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        fin = time.time() + 300
        while not pid.exists() and time.time() < fin and proc.poll() is None:
            time.sleep(0.5)
        assert pid.exists(), "le mutant lent n'a pas démarré"
    finally:
        # équivalent de taskkill /F /T ou SIGKILL : aucun finally du script ne tourne
        ms.kill_tree(proc)
    assert (wt / "calc.py").read_text(encoding="utf-8") == VIEUX + NEUF
    assert git(wt, "status", "--porcelain", "--ignored") == ""
    assert len(git(wt, "worktree", "list").splitlines()) == 2  # la copie tuée traîne
    ms.nettoyer_copies(wt)  # ce que fait le démarrage suivant
    propre(wt)


def test_dedoublonnage_pur():
    s = [
        {"module": "a.py", "line": 3, "function": "f", "diff": ["-x", "+y"]},
        {"module": "a.py", "line": 3, "function": "f", "diff": ["-x", "+z"]},
        {"module": "a.py", "line": 5, "function": "f", "diff": ["-p", "+q"]},
    ]
    u = ms.dedoublonner(s)
    assert [(x["line"], x["autres_mutations"]) for x in u] == [(3, 1), (5, 0)]
    assert u[0]["diff"] == ["-x", "+y"]


def test_annotations_exclues():
    src = "def f(a: int = 1) -> int:\n    return a\n"
    spans = ms.spans_annotations(src)
    assert ms.dans_span(1, 9, spans)  # `int` de l'argument
    assert not ms.dans_span(2, 11, spans)
