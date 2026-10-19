"""Tests de scripts/controle_rapide.py : encodage, code retour, mécanisme --max-blocages."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import controle_rapide as cr


def lancer(monkeypatch, tmp_path, commandes, args=()):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cr, "COMMANDES", commandes)
    monkeypatch.setattr(sys, "argv", ["controle_rapide.py", *args])
    return cr.main()


def py(code):
    return [sys.executable, "-c", code]


def test_vert_silencieux(monkeypatch, tmp_path, capsys):
    assert lancer(monkeypatch, tmp_path, [py("print('ok')")]) == 0
    assert capsys.readouterr().err == ""


def test_octets_non_utf8_ne_plantent_pas(monkeypatch, tmp_path, capsys):
    code = "import sys; sys.stdout.buffer.write(b'caf\xe9 \x81\x8d\n'); sys.exit(1)"
    assert lancer(monkeypatch, tmp_path, [py(code)]) == 2
    assert "a échoué" in capsys.readouterr().err


def test_emoji_en_sortie(monkeypatch, tmp_path, capsys):
    code = "import sys; print('\U0001F600 erreur'); sys.exit(1)"
    assert lancer(monkeypatch, tmp_path, [py(code)]) == 2
    assert "erreur" in capsys.readouterr().err


def test_commande_introuvable_est_un_echec(monkeypatch, tmp_path, capsys):
    assert lancer(monkeypatch, tmp_path, [["commande-inexistante-xyz"]]) == 2
    assert "commande-inexistante-xyz" in capsys.readouterr().err


def test_max_blocages(monkeypatch, tmp_path):
    rouge = [py("import sys; sys.exit(1)")]
    assert lancer(monkeypatch, tmp_path, rouge, ["--max-blocages", "1"]) == 2
    assert lancer(monkeypatch, tmp_path, rouge, ["--max-blocages", "1"]) == 0
    assert not (tmp_path / ".claude/cost-kit/.blocages").exists()


def test_vert_efface_compteur(monkeypatch, tmp_path):
    assert lancer(monkeypatch, tmp_path, [py("import sys; sys.exit(1)")]) == 2
    assert (tmp_path / ".claude/cost-kit/.blocages").exists()
    assert lancer(monkeypatch, tmp_path, [py("pass")]) == 0
    assert not (tmp_path / ".claude/cost-kit/.blocages").exists()
