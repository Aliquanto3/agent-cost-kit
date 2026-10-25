"""Tests de scripts/fusion_durees.py : fichiers factices dans tmp_path, faux gh injecté, sans réseau."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fusion_durees as fd


def artefact(racine: Path, os_: str, groupe: int, durees: dict) -> None:
    d = racine / f"test-durations-{os_}-{groupe}"
    d.mkdir(parents=True)
    (d / f"test-durations-{os_}.json").write_text(json.dumps(durees), encoding="utf-8")


def test_fusion_par_os(tmp_path):
    src = tmp_path / "src"
    artefact(src, "ubuntu-latest", 1, {"t::a": 1.0, "t::b": 2.0})
    artefact(src, "ubuntu-latest", 2, {"t::c": 3.0, "t::b": 2.5})
    artefact(src, "windows-latest", 1, {"t::a": 10.0})
    out = tmp_path / "out"
    assert fd.principal(["--depuis", str(src), "--dossier", str(out)]) == 0
    ubuntu = json.loads((out / "test-durations-ubuntu-latest.json").read_text(encoding="utf-8"))
    assert ubuntu == {"t::a": 1.0, "t::b": 2.5, "t::c": 3.0}
    assert json.loads((out / "test-durations-windows-latest.json").read_text(encoding="utf-8")) == {"t::a": 10.0}


def test_fichiers_ignores(tmp_path):
    src = tmp_path / "src"
    artefact(src, "ubuntu-latest", 1, {"t::a": 1.0, "t::mauvais": "x", "t::bool": True})
    (src).mkdir(exist_ok=True)
    (src / "autre.json").write_text("{}", encoding="utf-8")
    casse = src / "test-durations-macos-1"
    casse.mkdir()
    (casse / "test-durations-macos.json").write_text("pas du json", encoding="utf-8")
    liste = src / "test-durations-liste-1"
    liste.mkdir()
    (liste / "x.json").write_text("[1, 2]", encoding="utf-8")
    assert fd.lire_durees(src) == {"ubuntu-latest": {"t::a": 1.0}}


def test_repartition_blocs_et_glouton():
    durees = {f"t{i}": d for i, d in enumerate([100, 1, 1, 1, 1, 1, 1, 1])}
    assert sum(fd.repartir(durees, 4, "blocs")) == sum(durees.values())
    glouton = fd.repartir(durees, 2, "glouton")
    assert glouton == [100.0, 7.0]
    assert fd.repartir({"a": 5.0}, 1) == [5.0]


def test_blocs_desequilibres_si_tests_lents_groupes():
    durees = {"a1": 90.0, "a2": 90.0, "b1": 1.0, "b2": 1.0, "c1": 1.0, "c2": 1.0, "d1": 1.0, "d2": 1.0}
    totaux = fd.repartir(durees, 4, "blocs")
    assert max(totaux) - min(totaux) > 60


def test_resume_signale_ecart():
    texte = fd.resume({"windows-latest": {"a": 600.0, "b": 1.0}}, 2, "glouton")
    assert "windows-latest : 2 tests, total 10 min 01" in texte
    assert "à rafraîchir" in texte


def test_run_telecharge_via_gh(tmp_path):
    appels = []

    def faux_gh(args):
        appels.append(args)
        artefact(Path(args[args.index("--dir") + 1]), "ubuntu-latest", 1, {"t::a": 2.0})
        return 0, ""

    out = tmp_path / "out"
    assert fd.principal(["--run", "42", "--repo", "o/r", "--dossier", str(out)], gh=faux_gh) == 0
    assert appels[0][:3] == ["run", "download", "42"]
    assert appels[0][-2:] == ["--repo", "o/r"]
    assert (out / "test-durations-ubuntu-latest.json").exists()


def test_echec_gh_ou_rien_a_fusionner(tmp_path, capsys):
    assert fd.principal(["--run", "1", "--dossier", str(tmp_path)], gh=lambda a: (1, "boom")) == 1
    assert "boom" in capsys.readouterr().err
    assert fd.principal(["--depuis", str(tmp_path / "vide"), "--dossier", str(tmp_path)]) == 1
