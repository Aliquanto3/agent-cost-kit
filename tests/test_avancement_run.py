"""Tests de scripts/avancement_run.py sur des copies de l'exemple wavedevsecops (tests/fixtures/avancement)."""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
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
    monkeypatch.setattr(ar, "heures_commit_lignes", lambda _p, _f: {})
    cible = tmp_path / ar.DOSSIER
    cible.mkdir(parents=True)
    for f in FIXTURES.glob("*.*"):
        if f.name not in ("epics-titres.md", "commits.txt"):
            shutil.copy(f, cible / f.name)
    plan_dir = tmp_path / "_bmad-output" / "planning-artifacts"
    plan_dir.mkdir()
    shutil.copy(FIXTURES / "epics-titres.md", plan_dir / "epics.md")
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


def test_rapport_synthese_dirigeant(projet, capsys):
    assert ar.main([str(projet), "--maintenant", "2026-10-18 20:30"]) == 0
    md = capsys.readouterr().out
    lignes = md.splitlines()
    assert lignes[0].startswith("# ") and "2026-10-18 20:30" in lignes[0]
    assert "███░░░░░░░ 26 %" not in md and "13 / 62 stories terminées" in md
    assert "**Fin estimée : 2026-10-" in md and "(entre " in md and "**Météo : 🟢 dans les temps**" in md
    puces = [ln for ln in lignes if ln.startswith("- ")]
    assert 3 <= len(puces) <= 5 and md.index("## Ce qu'il faut savoir") < md.index("## Par epic")
    assert "| 1 · Installer, lancer et diagnostiquer… | ██████████ 100 % | 7 | 0 | 0 | ✅ |" in md
    assert "<details>" not in md and "## Détail par story" not in md and "| 2.4 |" not in md
    assert "Détails de l'estimation" in md and "### Rythme" not in md
    assert max(len(ln) for ln in lignes) <= 120


def test_detail_par_story_avec_option_ou_sans_epics(projet, capsys):
    assert ar.main([str(projet), "--stories", "--maintenant", "2026-10-18 20:30"]) == 0
    md = capsys.readouterr().out
    assert "## Détail par story" in md and "## Par epic" in md
    assert "| 2.4 | Taper de vraies commandes git dans le terminal | 🛠️ | 30 % |  |" in md
    assert "| 2.6 |" in md and "| 🧪 | 75 % | ★ |" in md
    a = ar.analyser(projet, ar.datetime(2026, 10, 18, 20, 30))
    for s in a["stories"].values():
        s["epic"] = 1  # un seul regroupement : pas de niveau de consolidation
    md = ar.rapport(a)
    assert "## Détail par story" in md and "## Par epic" not in md and "| 2.4 |" in md


def test_option_detail_et_json(projet, capsys):
    assert ar.main([str(projet), "--detail", "--maintenant", "2026-10-18 20:30"]) == 0
    md = capsys.readouterr().out
    for titre in ("## Détails de l'estimation", "### Par vague", "### Rythme", "### Calcul de la fin", "### Alertes"):
        assert titre in md
    assert "Non compté" in md and "Barème" in md
    assert ar.main([str(projet), "--json", "--maintenant", "2026-10-18 20:30"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["stories"]["2.4"]["pct"] == 30 and data["meteo"]["mot"] == "dans les temps"
    assert data["estimation"]["fin"]["centrale"].startswith("2026-10-")


def test_titres_depuis_epics_md_ou_slug(projet):
    n = ar.lire_titres(projet, ar.lire_statuts(projet / ar.DOSSIER / "sprint-status.yaml"))
    assert n["epics"][3] == "Collaborer dans un GitHub simulé" and n["stories"]["2.2"].startswith("Faire passer")
    (projet / "_bmad-output" / "planning-artifacts" / "epics.md").unlink()
    n = ar.lire_titres(projet, ar.lire_statuts(projet / ar.DOSSIER / "sprint-status.yaml"))
    assert n["epics"] == {} and n["stories"]["2.2"].startswith("faire passer chaque action")


def test_barre_court_et_emojis():
    assert ar.barre(0) == "░" * 10 and ar.barre(100) == "█" * 10 and ar.barre(25) == "███░░░░░░░"
    assert ar.court("un titre assez long pour être coupé", 15) == "un titre assez…" and ar.court("court", 15) == "court"
    base = {"etat": "en cours", "pct": 30, "drapeaux": []}
    assert ar.emoji_story(base) == "🛠️" and ar.emoji_story({**base, "pct": 60}) == "🔍"
    assert ar.emoji_story({**base, "pct": 75}) == "🧪" and ar.emoji_story({**base, "etat": "fait"}) == "✅"
    assert ar.emoji_story({**base, "etat": "à faire", "pct": 0}) == "⏳"
    assert ar.emoji_story({**base, "drapeaux": ["bloquée"]}) == "⛔"
    assert ar.emoji_story({**base, "drapeaux": ["attente humaine"]}) == "👤"
    assert ar.emoji_story({**base, "etat": "à faire", "drapeaux": ["coupée"]}) == "✂️"


def story(etat="à faire", drapeaux=()):
    return {"etat": etat, "pct": 0, "drapeaux": list(drapeaux)}


def test_statut_epic():
    assert ar.statut_epic([story("fait"), story("fait")]) == "✅"
    assert ar.statut_epic([story(), story()]) == "⏳"
    assert ar.statut_epic([story("fait"), story()]) == "🔄"
    assert ar.statut_epic([story("en cours", ["bloquée"]), story()]) == "⛔"
    assert ar.statut_epic([story("en cours", ["attente humaine"]), story()]) == "👤"


def test_meteo_regles():
    sans = {"chemin": ["a"]}
    assert ar.meteo({"a": story()}, sans)["emoji"] == "🟢"
    assert ar.meteo({"a": story("en cours", ["CI rouge"])}, sans)["emoji"] == "🟡"
    assert ar.meteo({"a": story("en cours", ["reprise"])}, sans)["emoji"] == "🟡"
    assert ar.meteo({"a": story("en cours", ["bloquée"])}, sans)["emoji"] == "🔴"
    humaine = {"a": story("en cours", ["attente humaine"]), "b": story()}
    assert ar.meteo(humaine, {"chemin": ["a"]})["emoji"] == "🔴"
    assert ar.meteo(humaine, {"chemin": ["b"]})["emoji"] == "🟢"  # attente humaine hors chemin critique


def test_meteo_depuis_le_journal(projet):
    run = projet / ar.DOSSIER / "run-autonome.md"
    run.write_text(run.read_text(encoding="utf-8") +
                   "- 2026-10-18 20:10 · 2.4 · CI · rouge sous Windows · abc1234\n", encoding="utf-8")
    a = ar.analyser(projet, MAINTENANT)
    assert "CI rouge" in a["stories"]["2.4"]["drapeaux"] and a["meteo"]["emoji"] == "🟡"
    assert "contrôle automatique rouge sur 2.4" in " ".join(ar.rapport(a).split())
    run.write_text(run.read_text(encoding="utf-8") + "- 2026-10-18 20:20 · 2.4 · blocked · deux échecs Opus · —\n", encoding="utf-8")
    a = ar.analyser(projet, MAINTENANT)
    assert a["meteo"]["emoji"] == "🔴" and "⛔" in ar.rapport(a)


def test_projet_sans_run(tmp_path, capsys):
    assert ar.main([str(tmp_path)]) == 2
    assert "Introuvable" in capsys.readouterr().err


def test_tout_termine_puis_rien_de_mesure(projet):
    sp = projet / ar.DOSSIER / "sprint-status.yaml"
    original = sp.read_text(encoding="utf-8")
    sp.write_text(original.replace(": backlog", ": done").replace(": in-progress", ": done"), encoding="utf-8")
    run = projet / ar.DOSSIER / "run-autonome.md"
    journal_initial = run.read_text(encoding="utf-8")
    ids = " ".join(ar.ids_statut(ar.lire_statuts(sp)))
    # une story `done` dont le journal n'a aucune fusion n'est pas terminée : on journalise les fusions
    run.write_text(journal_initial.rstrip("\n") + f"\n- 2026-10-18 20:00 · {ids} · fusion · ok · —\n", encoding="utf-8")
    a = ar.analyser(projet, MAINTENANT)
    assert a["estimation"]["reste"] == 0 and "Tous les développements prévus sont terminés" in ar.rapport(a)
    # journal vide : aucune durée mesurable, donc pas d'estimation chiffrée
    run.write_text(journal_initial.split("## Journal")[0] + "## Journal\n", encoding="utf-8")
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


# ----------------------------------------------------------------------------- S1 : PR, fusion, journal qui prime

def mini(tmp_path, monkeypatch, statuts, journal, maj="10-19-2026 10:00", vagues=None):
    """Projet minimal : `statuts` {id: statut}, `journal` lignes brutes, une vague par story sans dépendance."""
    monkeypatch.setattr(ar, "commits_git", lambda _p: [])
    monkeypatch.setattr(ar, "heures_commit_lignes", lambda _p, _f: {})
    d = tmp_path / ar.DOSSIER
    d.mkdir(parents=True)
    ligne = lambda k, v: f"  {k.replace('.', '-')}-x: {v}"
    (d / "sprint-status.yaml").write_text(
        f"last_updated: {maj}\ndevelopment_status:\n" + "\n".join(ligne(k, v) for k, v in statuts.items()) + "\n",
        encoding="utf-8")
    tab = "\n".join(f"| V{i} | {k} | — |" for i, k in enumerate(statuts))
    (d / "run-autonome.md").write_text(
        "## Sprint 1\n\n| Vague | Stories en parallèle | Après |\n|---|---|---|\n" + tab
        + "\n\n## Journal\n\n" + "\n".join(journal) + "\n", encoding="utf-8")
    return tmp_path


NOW = datetime(2026, 10, 19, 22, 0)


def test_normaliser_etape_pr():
    assert ar.normaliser_etape("PR") == "pr" and ar.normaliser_etape(" pr ouverte") == "pr"
    assert ar.normaliser_etape("PR #104") == "pr"
    assert ar.normaliser_etape("report") == "report" and ar.normaliser_etape("review") == "review"
    assert ar.normaliser_etape("préparation") != "pr"


def test_done_sans_fusion_n_est_pas_terminee(tmp_path, monkeypatch):
    p = mini(tmp_path, monkeypatch, {"1.1": "done", "1.2": "done", "1.3": "done", "1.4": "done"}, [
        "- 2026-10-19 09:00 · 1.1 · dev · lancé · —",
        "- 2026-10-19 09:30 · 1.1 · review · finie · —",
        "- 2026-10-19 09:00 · 1.2 · dev · lancé · —",
        "- 2026-10-19 09:40 · 1.2 · PR · #12 ouverte · abc1234",
        "- 2026-10-19 09:00 · 1.3 · dev · lancé · —",
        "- 2026-10-19 09:50 · 1.3 · fusion · PR #13 fusionnée · abc1235"])  # 1.4 : aucune ligne
    S = ar.analyser(p, NOW)["stories"]
    assert (S["1.1"]["etat"], S["1.1"]["etape"], S["1.1"]["pct"]) == ("en cours", "revue faite", 90)
    assert (S["1.2"]["etat"], S["1.2"]["etape"], S["1.2"]["pct"]) == ("en cours", "fusion en attente", 93)
    assert "PR ouverte" in S["1.2"]["drapeaux"] and "fusion attendue" in S["1.1"]["drapeaux"]
    assert S["1.3"]["etat"] == "fait" and S["1.3"]["pct"] == 100
    assert S["1.4"]["etat"] == "fait"  # compatibilité : aucune ligne de journal
    texte = " ".join(ar.rapport(ar.analyser(p, NOW)).split())
    assert "2 en attente de fusion" in texte and "1.1, 1.2" in texte and "2 / 4 stories terminées" in texte


def test_goulot_fusion_au_dela_de_trois_pr(tmp_path, monkeypatch):
    ids = ["1.1", "1.2", "1.3", "1.4"]
    j = [f"- 2026-10-19 10:0{i} · {s} · PR · #{i} ouverte · —" for i, s in enumerate(ids)]
    p = mini(tmp_path, monkeypatch, {s: "done" for s in ids}, j)
    assert "goulot CI / fusion : 4 PR attendent" in " ".join(ar.rapport(ar.analyser(p, NOW)).split())
    p2 = mini(tmp_path / "b", monkeypatch, {s: "done" for s in ids[:3]}, j[:3])
    assert "goulot" not in ar.rapport(ar.analyser(p2, NOW))


def test_mediane_pr_fusion_et_estimation(tmp_path, monkeypatch):
    statuts = {"1.1": "done", "1.2": "done", "1.3": "done", "1.4": "in-progress", "1.5": "done", "1.6": "done"}
    j = ["- 2026-10-19 08:00 · 1.1 · dev · lancé · —", "- 2026-10-19 08:30 · 1.1 · PR · #1 ouverte · —",
         "- 2026-10-19 09:00 · 1.1 · fusion · ok · —",       # 30 min
         "- 2026-10-19 08:00 · 1.2 · dev · lancé · —", "- 2026-10-19 09:00 · 1.2 · PR · #2 ouverte · —",
         "- 2026-10-19 10:00 · 1.2 · fusion · ok · —",       # 60 min -> médiane 45
         "- 2026-10-19 10:30 · 1.5 · PR · #5 ouverte · —", "- 2026-10-19 10:31 · 1.6 · PR · #6 ouverte · —"]
    a = ar.analyser(mini(tmp_path, monkeypatch, statuts, j), NOW)
    ry = a["rythme"]
    assert ry["pr_fusion_mediane_min"] == 45 and ry["pr_fusion_echantillon"] == 2
    assert "« PR ouverte -> fusion » : médiane 45 min" in ar.rapport(a, detail=True)
    # 2 PR en attente x 45 min = 90 min bornent la fin ; sans les lignes PR, rien ne change
    assert a["estimation"]["bornant"] == "fusions en série"
    assert a["estimation"]["fin"]["optimiste"] >= NOW + timedelta(minutes=90)


def test_journal_prime_sur_sprint_status_en_retard(tmp_path, monkeypatch):
    p = mini(tmp_path, monkeypatch, {"1.1": "ready-for-dev", "1.2": "ready-for-dev", "1.3": "ready-for-dev"}, [
        "- 2026-10-19 11:00 · 1.1 · dev · lancé · —",
        "- 2026-10-19 11:05 · 1.2 · attente humaine · clé API · —",
        "- 2026-10-19 09:00 · 1.3 · dev · lancé · —"])  # plus ancien que last_updated : pas d'écart
    a = ar.analyser(p, NOW)
    S = a["stories"]
    assert S["1.1"]["etat"] == "en cours" and S["1.1"]["etape"] == "dev en cours" and not S["1.1"]["eligible"]
    assert S["1.2"]["etat"] == "à faire" and "attente humaine" in S["1.2"]["drapeaux"] and not S["1.2"]["eligible"]
    assert S["1.3"]["etat"] == "à faire" and S["1.3"]["eligible"]  # journal plus ancien : le statut prime
    assert a["ecarts"] == ["1.1"]
    texte = " ".join(ar.rapport(a).split())
    assert "sprint-status en retard sur le journal pour 1.1" in texte
    assert "prête mais pas lancée : 1.2" not in texte


def test_journal_fusion_plus_recente_que_sprint_status(tmp_path, monkeypatch):
    p = mini(tmp_path, monkeypatch, {"1.1": "review"}, ["- 2026-10-19 11:00 · 1.1 · fusion · ok · —"])
    a = ar.analyser(p, NOW)
    assert a["stories"]["1.1"]["etat"] == "fait" and a["ecarts"] == ["1.1"]


def test_lignes_du_journal_dans_le_futur(tmp_path, monkeypatch):
    p = mini(tmp_path, monkeypatch, {"1.1": "in-progress"}, ["- 2026-10-19 23:30 · 1.1 · dev · lancé · —"])
    a = ar.analyser(p, NOW)
    assert len(a["futures"]) == 1 and a["futures"][0]["stories"] == ["1.1"]
    assert "heure future au journal pour 1.1" in " ".join(ar.rapport(a).split())
    assert "Heure future au journal" in ar.rapport(a, detail=True)
    sans = ar.analyser(p, datetime(2026, 10, 20, 0, 0))
    assert sans["futures"] == [] and "heure future" not in ar.rapport(sans)


# ----------------------------------------------------------------------------- revue S1 : extrait réel anonymisé

PLAN_REEL = """## Sprint 1 — extrait

Au plus 3 stories en développement à la fois

| Vague | Stories en parallèle | Après |
|---|---|---|
| V14 | 4.9 ★ | — |
| V14b | 1.12 · 2.7 | suite du correct course, fusionnées avant 3.6 et 4.9 |
| V18 | 5.4 · 5.7 (mixte) · 6.3 | — |
| V20 | 6.4 · 7.4 | 6.4 ← 6.3 |

## Journal

- 2026-10-19 02:41 · 1.12 · contrôles · verts · 1cdca6a
- 2026-10-19 06:17 · 1.12 · fusion · PR #66 fusionnée · b90056e
- 2026-10-19 01:44 · 2.7 · contrôles · verts ; PR ouverte, fusion après 3.2 · f424965
- 2026-10-19 03:52 · 2.7 · fusion · PR #63 fusionnée · f6e3841
- 2026-10-19 11:52 · 4.9 · PR · #79 ouverte, file de fusion · 47ee04f
- 2026-10-19 12:05 · 4.9 · fusion · PR #79 fusionnée · 1a2b3c4
- 2026-10-19 16:01 · 5.4 · dev · lancé · 2dbb19d
- 2026-10-19 16:56 · 5.4 · second-avis · lancé (Haiku) · —
- 2026-10-19 16:33 · 6.3 · dev · lancé · 19a01bd
- 2026-10-19 16:55 · 6.3 · dev · fini · —
- 2026-10-19 17:11 · 6.3 · fusion master · 6.1 fusionnée sans conflit · aeb37a8
- 2026-10-19 17:11 · 6.3 · review · lancée (Opus) · aeb37a8
- 2026-10-19 17:17 · 6.3 · review · 2 medium corrigés · —
- 2026-10-19 17:42 · 6.3 · PR · #95 ouverte · —
- 2026-10-19 19:39 · 6.3 · CI · verte sur les 3 OS ; PR en conflit après les fusions · —
- 2026-10-19 19:39 · 6.3 · fusion master · conflit résolu ; poussé sur #95 · 7122bc2
- 2026-10-19 17:25 · 6.4 · dev · lancé · 7db423c
- 2026-10-19 18:21 · 6.4 · fusion 6.3 et master · conflit résolu · ff0ce9e
- 2026-10-19 18:21 · 6.4 · review · lancée (Opus) · ff0ce9e
- 2026-10-19 07:09 · 7.4 · fusion · refusée (PR #68 en conflit) ; master à fusionner dans la branche · —
- 2026-10-19 18:32 · 7.4 · fusion master · sans conflit · —
- 2026-10-19 17:37 · 5.7 · attente humaine · données du banc absentes · —
- 2026-10-19 19:31 · 5.7 · décision · Anaël : 5.7 reportée après le run · —
"""


def test_extrait_reel_fusion_master_v14b_decision_pr(tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "commits_git", lambda _p: [])
    monkeypatch.setattr(ar, "heures_commit_lignes", lambda _p, _f: {})
    d = tmp_path / ar.DOSSIER
    d.mkdir(parents=True)
    statuts = {"4.9": "done", "1.12": "done", "2.7": "done", "5.4": "done", "5.7": "backlog",
               "6.3": "done", "6.4": "in-progress", "7.4": "in-progress"}
    (d / "sprint-status.yaml").write_text(
        "last_updated: 10-19-2026 19:56\ndevelopment_status:\n"
        + "".join(f"  {k.replace('.', '-')}-x: {v}\n" for k, v in statuts.items()), encoding="utf-8")
    (d / "run-autonome.md").write_text(PLAN_REEL, encoding="utf-8")
    a = ar.analyser(tmp_path, datetime(2026, 10, 19, 20, 0))
    S = a["stories"]
    assert len(S) == 8 and a["plan"]["ordre"] == ["V14", "V14b", "V18", "V20"]  # V14b lue, dans l'ordre
    assert S["1.12"]["deps"] == [] and S["2.7"]["deps"] == []  # « avant 3.6 et 4.9 » n'est pas une dépendance
    assert sorted(k for k, s in S.items() if s["etat"] == "fait") == ["1.12", "2.7", "4.9"]
    # « fusion master », « fusion 6.3 et master », « refusée » : mise à jour de branche, pas une fusion
    assert (S["6.3"]["etat"], S["6.3"]["pct"]) == ("en cours", 93) and "PR ouverte" in S["6.3"]["drapeaux"]
    assert (S["6.4"]["etat"], S["6.4"]["etape"], S["6.4"]["pct"]) == ("en cours", "review en cours", 75)
    assert S["7.4"]["etat"] == "en cours" and S["7.4"]["pct"] < 95
    # « second-avis · lancé » : second avis en cours (60 %), pas fini
    assert (S["5.4"]["etape"], S["5.4"]["pct"]) == ("second-avis en cours", 60)
    # décision récente sur une story pas lancée : retenue, jamais « prête mais pas lancée »
    assert "retenue" in S["5.7"]["drapeaux"] and not S["5.7"]["eligible"]
    assert "prête mais pas lancée" not in ar.rapport(a)
    # PR -> fusion : ouverture de la PR fusionnée (2.7 : « PR ouverte » dans les contrôles)
    ry = a["rythme"]
    assert ry["pr_fusion_echantillon"] == 2 and ry["pr_fusion_mediane_min"] == (13 + 128) / 2
    assert a["ecarts"] == []  # done sans fusion : pas un retard de sprint-status


def test_last_updated_iso_ou_illisible(tmp_path):
    f = tmp_path / "s.yaml"
    f.write_text("last_updated: '2026-10-19 19:56'\n", encoding="utf-8")
    assert ar.lire_maj(f) == datetime(2026, 10, 19, 19, 56)
    f.write_text("last_updated: hier\n", encoding="utf-8")
    assert ar.lire_maj(f) is None


@pytest.mark.skipif(shutil.which("git") is None, reason="git absent")
def test_heure_posterieure_au_commit_qui_ajoute_la_ligne(tmp_path, monkeypatch):
    p = mini(tmp_path, monkeypatch, {"1.1": "in-progress"}, [
        "- 2026-10-19 19:55 · 1.1 · dev · lancé · —", "- 2026-10-19 21:30 · 1.1 · dev · fini · —"])
    monkeypatch.undo()
    monkeypatch.setattr(ar, "commits_git", lambda _p: [])
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_AUTHOR_DATE": "2026-10-19T20:00:00",
           "GIT_COMMITTER_DATE": "2026-10-19T20:00:00"}
    subprocess.run(["git", "init", "-q", str(p)], check=True, env=env)
    subprocess.run(["git", "-C", str(p), "add", "."], check=True, env=env)
    subprocess.run(["git", "-C", str(p), "commit", "-q", "-m", "chore: état du run"], check=True, env=env)
    a = ar.analyser(p, datetime(2026, 10, 20, 8, 0))  # 21:30 n'est plus « futur », mais postérieur au commit de 20:00
    assert [(f["t"].hour, f["commit_t"]) for f in a["futures"]] == [(21, datetime(2026, 10, 19, 20, 0))]
    assert "après le commit qui l'ajoute (2026-10-19 20:00)" in ar.rapport(a, detail=True)


# ----------------------------------------------------------------------------- 0.7.1 : stories reportées

JOURNAL_DEC = ["- 2026-10-19 08:00 · 1.1 · dev · lancé · —", "- 2026-10-19 09:00 · 1.1 · fusion · ok · —",
               "- 2026-10-19 09:30 · 1.2 · dev · lancé · —", "- 2026-10-19 09:40 · 1.2 · fusion · ok · —"]
STATUTS_DEC = {"1.1": "done", "1.2": "done", "1.3": "backlog", "1.4": "backlog"}


def test_decision_qui_reporte_sort_de_l_estimation(tmp_path, monkeypatch):
    j = JOURNAL_DEC + ["- 2026-10-19 10:00 · 1.3 · décision · Anaël : 1.3 reportée après le run ; prévenir Anaël "
                       "quand Ollama est libre · —"]
    a = ar.analyser(mini(tmp_path, monkeypatch, STATUTS_DEC, j), NOW)
    s = a["stories"]["1.3"]
    assert "retenue" in s["drapeaux"] and "reportée" in s["drapeaux"] and not s["eligible"]
    assert a["estimation"]["reste"] == 1  # seule 1.4 compte
    assert len(a["stories"]) == 4
    r = ar.rapport(a, detail=True)
    assert "1.3 retenue par décision du journal (reportée après le run)" in r
    assert "attend la fin d'une autre story" not in r
    assert "reportée, hors estimation" in r and "reportées hors estimation : 1.3" in r
    assert any("prévenir Anaël" in d for d in a["decisions"])


def test_report_sort_de_l_estimation_mais_decision_simple_reste_comptee(tmp_path, monkeypatch):
    j = JOURNAL_DEC + ["- 2026-10-19 10:00 · 1.3 · report · hors run · —",
                       "- 2026-10-19 10:05 · 1.4 · décision · attendre l'accord sur le schéma · —"]
    a = ar.analyser(mini(tmp_path, monkeypatch, STATUTS_DEC, j), NOW)
    assert "reportée" in a["stories"]["1.3"]["drapeaux"]
    assert a["stories"]["1.4"]["drapeaux"] == ["retenue"]
    assert a["estimation"]["reste"] == 1
    assert "1.4 retenue par décision du journal" in ar.rapport(a) and "1.4 retenue par décision du journal (reportée" not in ar.rapport(a)


def test_chemin_critique_ignore_la_dependance_d_une_story_deja_demarree():
    def st(etat, pct, deps=()):
        return {"etat": etat, "pct": pct, "type": "dev", "drapeaux": [], "deps": list(deps)}
    s = {"1": st("en cours", 93), "2": st("en cours", 30, ["1"]), "3": st("à faire", 0, ["2"])}
    longueur, chemin = ar.chemin_critique(s)
    assert chemin == ["2", "3"] and longueur == pytest.approx(1.7)
