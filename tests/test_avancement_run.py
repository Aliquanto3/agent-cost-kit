"""Tests de scripts/avancement_run.py sur des copies de l'exemple wavedevsecops (tests/fixtures/avancement)."""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import avancement_run as ar

FIXTURES = Path(__file__).parent / "fixtures" / "avancement"
MAINTENANT = datetime(2026, 10, 18, 20, 30)


def commits_exemple():
    sortie = []
    for ligne in (FIXTURES / "commits.txt").read_text(encoding="utf-8").splitlines():
        h, d, sujet = ligne.split("|", 2)
        sortie.append((h, datetime.strptime(d, "%Y-%m-%d %H:%M"), sujet))
    return sortie


@pytest.fixture()
def projet(tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "commits_git", lambda _p: commits_exemple())
    cible = tmp_path / ar.DOSSIER
    cible.mkdir(parents=True)
    for f in FIXTURES.iterdir():
        shutil.copy(f, cible / f.name)
    return tmp_path


@pytest.fixture()
def plan():
    return ar.lire_plan((FIXTURES / "run-autonome.md").read_text(encoding="utf-8"))


def evt(date="2026-10-18", heure=None, stories=(), etape="dev", resultat="", commit=""):
    return {"date": date, "heure": heure, "stories": list(stories), "etape": etape, "brut": etape,
            "resultat": resultat, "commit": commit, "t": None, "source": ""}


def test_statuts_et_identifiants():
    st = ar.ids_statut(ar.lire_statuts(FIXTURES / "sprint-status.yaml"))
    assert st["1.1"] == "done" and st["2.4"] == "in-progress" and st["7.2"] == "backlog"
    assert st["2.10"] == "backlog" and "epic-1" not in st and len(st) >= 80


def test_plan_vagues_et_dependances(plan):
    assert plan["ordre"][0] == "V0" and "W8" in plan["ordre"] and len(plan["ordre"]) == 27
    assert plan["vagues"]["V5"] == ["2.4", "2.7", "3.1"]
    assert plan["deps"]["1.3"] == {"1.2"}  # ← propre à chaque story
    assert plan["deps"]["2.1"] == {"1.4"} and plan["deps"]["1.6"] == {"1.4"}
    assert plan["deps"]["2.10"] == {"2.7", "2.8", "3.3"}
    assert plan["deps"]["1.2"] == {"1.1"} and plan["deps"]["1.4"] == {"1.1"}  # cellule simple : toute la vague
    assert plan["deps"]["8.3"] == {"8.1", "8.2"} and plan["deps"]["1.1"] == set()
    assert "1.1" in plan["deps"]["6.7"] and "6.7" not in plan["deps"]["6.7"] and "6.6" in plan["deps"]["6.7"]
    assert "9.4" in plan["deps"]["9.5"] and "6.1" not in plan["deps"]["9.5"]  # epics 7 à 9 seulement
    assert plan["type"]["6.7"] == "mixte" and plan["type"]["9.5"] == "mixte" and plan["type"]["1.1"] == "dev"
    assert {"1.1", "2.1", "3.1", "4.3", "7.1", "7.4"} <= plan["pivot"] and "1.2" not in plan["pivot"]
    assert plan["parallelisme"] == 3 and plan["hors_run"] == {10, 11, 12}
    assert not any(s.startswith("10.") for s in plan["deps"])


def test_journal_lignes_avec_et_sans_heure():
    evts = ar.lire_journal((FIXTURES / "run-autonome.md").read_text(encoding="utf-8"))
    assert evts[0]["heure"] is None and evts[0]["stories"] == []
    multi = next(e for e in evts if e["stories"] == ["1.2", "1.4"])
    assert multi["etape"] == "dev" and "lanc" in multi["resultat"]
    avec = [e for e in evts if e["heure"]]
    assert avec and avec[0]["heure"] == "19:58" and avec[0]["commit"] == "5bf1f3d"
    assert any("pour Anaël" in e["brut"] for e in evts)


def test_dater_repli_suivi_commit_puis_interpolation():
    evts = [evt(heure="10:00", stories=["1.1"], resultat="lancé"),
            evt(stories=["1.1"], etape="dev", resultat="fini", commit="abc1234"),
            evt(stories=["1.1"], etape="fusion"),
            evt(stories=["1.2"], etape="dev", resultat="lancé"),
            evt(heure="12:00", stories=["1.2"], etape="fusion")]
    commits = [("abc1234" + "0" * 33, datetime(2026, 10, 18, 10, 40), "feat: x"),
               ("f" * 40, datetime(2026, 10, 18, 11, 10), "chore: suivi du run autonome (story 1.1 fusionnée)")]
    ar.dater(evts, commits, None)
    assert [e["source"] for e in evts] == ["journal", "commit", "suivi", "interpolé", "journal"]
    assert evts[1]["t"] == datetime(2026, 10, 18, 10, 40) and evts[2]["t"] == datetime(2026, 10, 18, 11, 10)
    assert evts[3]["t"] == datetime(2026, 10, 18, 11, 35)


def test_dater_ecarte_un_repli_qui_recule():
    evts = [evt(heure="10:00"), evt(commit="abc1234"), evt(heure="10:30")]
    ar.dater(evts, [("abc1234" + "0" * 33, datetime(2026, 10, 18, 9, 0), "x")], None)
    assert evts[1]["source"] == "interpolé" and evts[1]["t"] == datetime(2026, 10, 18, 10, 15)


def test_repli_sur_date_de_fichier():
    evts = [evt(), evt()]
    ar.dater(evts, [], datetime(2026, 10, 18, 8, 0))
    assert evts[1]["source"] == "mtime" and evts[0]["t"] == datetime(2026, 10, 18, 8, 0)


def test_etape_story_et_bareme():
    d = [evt(resultat="lancé")]
    assert ar.etape_story(d)[1:] == ("dev en cours", 30)
    d.append(evt(resultat="fini, 12 tests"))
    assert ar.etape_story(d)[2] == 60
    d.append(evt(etape="second-avis"))
    assert ar.etape_story(d)[2] == 75
    d.append(evt(etape="review"))
    assert ar.etape_story(d)[2] == 90
    d.append(evt(etape="ci", resultat="rouge sous Windows"))
    assert ar.etape_story(d)[2] == 85
    assert ar.etape_story([evt(resultat="lancé"), evt(etape="report", resultat="non lancé : attend 2.4")]) is None
    assert ar.etape_story([]) is None


def test_analyse_de_l_exemple(projet):
    a = ar.analyser(projet, MAINTENANT)
    S = a["stories"]
    assert len(S) == 62 and sum(s["etat"] == "fait" for s in S.values()) == 13
    assert {k: (S[k]["etat"], S[k]["pct"]) for k in ("2.4", "9.1", "2.6", "3.1")} == {
        "2.4": ("en cours", 30), "9.1": ("en cours", 75), "2.6": ("en cours", 75), "3.1": ("en cours", 75)}
    assert S["7.2"]["etat"] == "à faire" and "retenue" in S["7.2"]["drapeaux"] and not S["7.2"]["eligible"]
    assert S["6.6"]["eligible"] and not S["2.7"]["eligible"] and S["2.7"]["attend"] == ["2.6"]
    assert not any(k.startswith("10.") for k in S)
    assert "vérification humaine due" in S["1.6"]["drapeaux"]
    assert a["decisions"] and a["rythme"]["fusionnees"] == 13
    es = a["estimation"]
    assert es["fin"]["optimiste"] <= es["fin"]["centrale"] <= es["fin"]["pessimiste"]
    assert es["chemin"][-1] == "6.7" and es["longueur"] > 5


def test_rapport_markdown_et_json(projet, capsys):
    assert ar.main([str(projet), "--maintenant", "2026-10-18 20:30"]) == 0
    md = capsys.readouterr().out
    for titre in ("## Par epic", "## Par vague", "## En cours", "## Estimation de fin", "## Alertes", "Barème"):
        assert titre in md
    assert "| V0 | 1.1★ ✓ |" in md and "2.4 ▶30%" in md and "Non compté" in md
    assert ar.main([str(projet), "--json", "--maintenant", "2026-10-18 20:30"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["stories"]["2.4"]["pct"] == 30 and data["estimation"]["fin"]["centrale"].startswith("2026-10-")


def test_projet_sans_run(tmp_path, capsys):
    assert ar.main([str(tmp_path)]) == 2
    assert "Introuvable" in capsys.readouterr().err


def test_tout_termine_puis_rien_de_mesure(projet):
    sp = projet / ar.DOSSIER / "sprint-status.yaml"
    original = sp.read_text(encoding="utf-8")
    sp.write_text(original.replace(": backlog", ": done").replace(": in-progress", ": done"), encoding="utf-8")
    a = ar.analyser(projet, MAINTENANT)
    assert a["estimation"]["reste"] == 0 and "Tout est terminé" in ar.rapport(a)
    # journal vide : aucune durée mesurable, donc pas d'estimation chiffrée
    run = projet / ar.DOSSIER / "run-autonome.md"
    run.write_text(run.read_text(encoding="utf-8").split("## Journal")[0] + "## Journal\n", encoding="utf-8")
    sp.write_text(original, encoding="utf-8")
    b = ar.analyser(projet, MAINTENANT)
    assert b["estimation"]["fin"] is None and "pas assez de stories" in ar.rapport(b)


@pytest.mark.skipif(shutil.which("git") is None, reason="git absent")
def test_git_reel_pour_les_heures_sans_horodatage(projet, monkeypatch):
    monkeypatch.undo()  # git réel, sans la liste de commits de l'exemple
    run = projet / ar.DOSSIER / "run-autonome.md"
    journal = "## Journal\n\n- 2026-10-18 · 1.1 · dev · lancé · —\n- 2026-10-18 · 1.1 · fusion · ff · —\n"
    run.write_text(run.read_text(encoding="utf-8").split("## Journal")[0] + journal, encoding="utf-8")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_AUTHOR_DATE": "2026-10-18T14:20:00",
           "GIT_COMMITTER_DATE": "2026-10-18T14:20:00"}
    subprocess.run(["git", "init", "-q", str(projet)], check=True, env=env)
    subprocess.run(["git", "-C", str(projet), "add", "."], check=True, env=env)
    subprocess.run(["git", "-C", str(projet), "commit", "-q", "-m",
                    "chore: suivi du run autonome (story 1.1 fusionnée)"], check=True, env=env)
    a = ar.analyser(projet, MAINTENANT)
    assert a["stories"]["1.1"]["fini"] == datetime(2026, 10, 18, 14, 20)
    assert a["sources_heures"].get("suivi") == 1
