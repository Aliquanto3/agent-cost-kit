"""Tests de scripts/mutation_story.py sur un petit dépôt de fixture (une fonction, un test faible)."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import mutation_story as ms

pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="uv absent")

VIEUX = "def vieux(x):\n    return x + 1\n"
NEUF = "\ndef borne(x):\n    if x > 10:\n        return 10\n    return x\n"
TEST_FAIBLE = (
    "from calc import borne\n\n\ndef test_borne():\n    assert borne(5) == 5\n"
)


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
    git(wt, "init", "-q")
    (wt / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    (wt / "calc.py").write_text(VIEUX, encoding="utf-8")
    git(wt, "add", ".")
    git(wt, "commit", "-qm", "base")
    base = git(wt, "rev-parse", "HEAD")
    (wt / "calc.py").write_text(VIEUX + NEUF, encoding="utf-8")
    (wt / "test_calc.py").write_text(TEST_FAIBLE, encoding="utf-8")
    git(wt, "add", ".")
    git(wt, "commit", "-qm", "story")
    return wt, base


def lancer(depot, tmp_path, *extra):
    wt, base = depot
    out = tmp_path / "out"
    rc = ms.main(["--worktree", str(wt), "--base", base, "--out", str(out), *extra])
    return rc, out


def test_survivant_dedoublonne_hors_diff_ignore_et_sources_restaurees(depot, tmp_path):
    wt, _ = depot
    avant = (wt / "calc.py").read_bytes()
    try:
        rc, out = lancer(depot, tmp_path)
    except SystemExit as e:  # cosmic-ray indisponible (hors ligne) : saut explicite
        pytest.skip(f"cosmic-ray indisponible : {e}")
    assert rc == 0
    import json

    res = json.loads((out / "survivants.json").read_text(encoding="utf-8"))
    uniques = res["survivants"]
    assert uniques, "le test faible doit laisser au moins un survivant"
    lignes = [s["line"] for s in uniques]
    assert len(lignes) == len(set(lignes))  # une entrée par ligne
    assert all(s["line"] >= 4 for s in uniques)  # `vieux` (lignes 1 et 2) hors diff
    assert all(s["function"].endswith("borne") for s in uniques)
    assert all(s["diff"] and s["diff"][0].startswith("-") for s in uniques)
    assert res["totaux"]["survivants"] >= len(uniques)
    md = (out / "survivants.md").read_text(encoding="utf-8")
    assert "calc.py" in md and "M1" in md
    assert (wt / "calc.py").read_bytes() == avant
    assert git(wt, "status", "--porcelain") == ""


def test_budget_nul_restaure_les_sources(depot, tmp_path):
    wt, _ = depot
    avant = (wt / "calc.py").read_bytes()
    try:
        rc, out = lancer(depot, tmp_path, "--budget-min", "0")
    except SystemExit as e:
        pytest.skip(f"cosmic-ray indisponible : {e}")
    assert rc == 0
    import json

    res = json.loads((out / "survivants.json").read_text(encoding="utf-8"))
    assert res["totaux"]["executes"] == 0
    assert res["totaux"]["non_executes"] > 0
    assert (wt / "calc.py").read_bytes() == avant
    assert git(wt, "status", "--porcelain") == ""


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
