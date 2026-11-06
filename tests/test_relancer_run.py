"""Tests de scripts/relancer_run.py avec un faux `claude` (script Python de fixture, passé par --claude).

Le faux `claude` lit un scénario JSON (une entrée par tour : etat, pic, cout, is_error), écrit une transcription
minimale sous la racine des transcriptions, et journalise ses appels (argv, entrée standard).
La racine des transcriptions est surchargée par la variable d'environnement
AGENT_COST_KIT_RACINE_TRANSCRIPTIONS (le script a aussi une option cachée --racine) : les tests n'écrivent
jamais dans ~/.claude.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import avancement_run as ar
import relancer_run as rr
from test_avancement_run import commits_exemple, projet  # noqa: F401  (fixture `projet`)

FAUX_CLAUDE = r'''
import json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path

scenario_path = Path(os.environ["FAUX_SCENARIO"])
etat_path = scenario_path.with_suffix(".etat.json")
etat = json.loads(etat_path.read_text(encoding="utf-8")) if etat_path.exists() else {"tour": 0, "cumul": {}}
scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
argv = sys.argv[1:]
prompt = sys.stdin.buffer.read().decode("utf-8")
with open(scenario_path.with_suffix(".appels.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"argv": argv, "prompt": prompt, "cwd": os.getcwd()}) + "\n")
tour = scenario[etat["tour"]]
etat["tour"] += 1
session = argv[argv.index("--resume") + 1] if "--resume" in argv else argv[argv.index("--session-id") + 1]
etat["cumul"][session] = etat["cumul"].get(session, 0.0) + tour.get("cout", 0.0)
etat_path.write_text(json.dumps(etat), encoding="utf-8")
dossier = Path(os.environ["AGENT_COST_KIT_RACINE_TRANSCRIPTIONS"]) / re.sub(r"[^A-Za-z0-9]", "-", str(Path.cwd().resolve()))
dossier.mkdir(parents=True, exist_ok=True)
pic = tour.get("pic", 0)
ligne = {
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "message": {"id": f"msg_{etat['tour']}", "role": "assistant", "model": "claude-opus-5-5",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 10, "cache_read_input_tokens": pic - 30,
                          "cache_creation_input_tokens": 20, "output_tokens": 5}},
}
if not tour.get("sans_transcription"):
    with open(dossier / f"{session}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(ligne) + "\n")
if tour.get("sortie_invalide"):
    print("pas du json")
    sys.exit(1)
print(json.dumps({"type": "result", "is_error": tour.get("is_error", False), "session_id": session,
                  "result": tour.get("etat", ""), "total_cost_usd": tour.get("total", etat["cumul"][session])}))
'''


@pytest.fixture()
def banc(tmp_path, monkeypatch):
    racine = tmp_path / "transcriptions"
    monkeypatch.setenv(rr.ENV_RACINE, str(racine))
    dossier = tmp_path / "projet"
    etat_dir = dossier / "_bmad-output" / "implementation-artifacts"
    etat_dir.mkdir(parents=True)
    (etat_dir / "run-autonome.md").write_text("# Run\n", encoding="utf-8")
    faux = tmp_path / "faux_claude.py"
    faux.write_text(FAUX_CLAUDE, encoding="utf-8")
    scenario = tmp_path / "scenario.json"
    monkeypatch.setenv("FAUX_SCENARIO", str(scenario))

    class Banc:
        projet = dossier
        journal = etat_dir / "relancer-run.jsonl"

        @staticmethod
        def lancer(tours, *options):
            scenario.write_text(json.dumps(tours), encoding="utf-8")
            return rr.principal(["--projet", str(dossier), "--claude", str(faux), *options])

        @staticmethod
        def appels():
            fichier = scenario.with_suffix(".appels.jsonl")
            if not fichier.exists():
                return []
            return [json.loads(x) for x in fichier.read_text(encoding="utf-8").splitlines()]

        @staticmethod
        def lignes():
            return [json.loads(x) for x in Banc.journal.read_text(encoding="utf-8").splitlines()]

    return Banc


def continuer(pic, cout=1.0):
    return {"etat": "ETAT: CONTINUER — vague suivante", "pic": pic, "cout": cout}


FINI = {"etat": "ETAT: FINI — tout est fusionné", "pic": 50_000, "cout": 0.5}


def test_pic_sous_le_seuil_reprend_la_meme_session(banc):
    assert banc.lancer([continuer(60_000), FINI]) == 0
    premier, second = banc.appels()
    assert "--session-id" in premier["argv"] and "--resume" not in premier["argv"]
    session = premier["argv"][premier["argv"].index("--session-id") + 1]
    assert second["argv"][second["argv"].index("--resume") + 1] == session
    assert "--session-id" not in second["argv"]
    assert second["prompt"] == rr.PROMPT_SUITE
    assert [x["mode"] for x in banc.lignes()] == ["nouvelle", "reprise"]


def test_pic_au_dessus_ouvre_une_nouvelle_session(banc, capsys):
    assert banc.lancer([continuer(140_000), FINI]) == 0
    premier, second = banc.appels()
    s1 = premier["argv"][premier["argv"].index("--session-id") + 1]
    s2 = second["argv"][second["argv"].index("--session-id") + 1]
    assert s1 != s2 and "--resume" not in second["argv"]
    assert "## Brief" in second["prompt"] and "run-autonome.md" in second["prompt"]
    assert "ETAT: CONTINUER|FINI|ATTENTE_HUMAINE|BLOQUE" in second["prompt"]
    assert [x["mode"] for x in banc.lignes()] == ["nouvelle", "nouvelle"]
    assert "Sessions : 2 ; tours : 2 ; relances : 1 ; coût : 1.50 $" in capsys.readouterr().out


def test_seuil_exact_ouvre_une_nouvelle_session(banc):
    assert banc.lancer([continuer(100_000), FINI]) == 0
    assert [x["mode"] for x in banc.lignes()] == ["nouvelle", "nouvelle"]


def test_commande_du_tour(banc):
    banc.lancer([FINI], "--modele", "m-x", "--effort", "high", "--budget-tour", "3", "--permission-mode", "plan")
    argv = banc.appels()[0]["argv"]
    assert argv[0] == "-p"
    for option, valeur in (("--model", "m-x"), ("--effort", "high"), ("--output-format", "json"),
                           ("--max-budget-usd", "3.0"), ("--permission-mode", "plan")):
        assert argv[argv.index(option) + 1] == valeur
    assert banc.appels()[0]["cwd"] == str(banc.projet.resolve())


def test_pic_compte_les_seuls_appels_du_tour(banc):
    # Seuil haut : le tour 1 (150 k) est suivi d'une reprise de la même session, dont le pic (60 k)
    # ne doit pas hériter des 150 k du même fichier .jsonl.
    assert banc.lancer([continuer(150_000), FINI | {"pic": 60_000}], "--seuil", "200000") == 0
    assert [x["pic"] for x in banc.lignes()] == [150_000, 60_000]
    assert [x["mode"] for x in banc.lignes()] == ["nouvelle", "reprise"]


@pytest.mark.parametrize(
    "tour, code, texte",
    [
        ({"etat": "ETAT: FINI — ok"}, 0, "État final : FINI — ok (code 0)"),
        ({"etat": "ETAT: ATTENTE_HUMAINE — accord pour couper"}, 2, "ATTENTE_HUMAINE — accord pour couper (code 2)"),
        ({"etat": "ETAT: BLOQUE — CI rouge"}, 3, "BLOQUE — CI rouge (code 3)"),
        ({"etat": "fini sans ligne d'état"}, 3, "ligne « ETAT: … » absente du résultat (code 3)"),
        ({"etat": "ETAT: FINI — ok", "is_error": True}, 4, "ERREUR"),
        ({"sortie_invalide": True}, 4, "sortie illisible"),
    ],
)
def test_codes_de_sortie(banc, capsys, tour, code, texte):
    assert banc.lancer([tour]) == code
    assert texte in capsys.readouterr().out


def test_derniere_ligne_etat_l_emporte(banc):
    tour = {"etat": "ETAT: BLOQUE — ancien\nrésumé\nETAT: FINI — final"}
    assert banc.lancer([tour]) == 0


@pytest.mark.parametrize(
    "texte, attendu",
    [
        ("ETAT: FINI.", ("FINI", "")),
        ("`ETAT: FINI — ok`", ("FINI", "ok")),
        ("**ETAT: FINI** — ok", ("FINI", "ok")),
        ("ETAT : CONTINUER — vague V3", ("CONTINUER", "vague V3")),
        ("- ETAT: BLOQUE — CI rouge", ("BLOQUE", "CI rouge")),
        ("> ETAT: ATTENTE_HUMAINE - accord", ("ATTENTE_HUMAINE", "accord")),
        ("ETAT: FINI (3 vagues)", ("FINI", "(3 vagues)")),
        ("État: fini — ok", ("FINI", "ok")),
        ("ETAT: FINISSANT", (None, "")),
        ("le format est ETAT: FINI", (None, "")),
    ],
)
def test_lire_etat_tolere_la_mise_en_forme(texte, attendu):
    assert rr.lire_etat(texte) == attendu


def test_ligne_finale_en_gras_l_emporte_sur_un_continuer_anterieur():
    assert rr.lire_etat("ETAT: CONTINUER — brouillon\n\n**ETAT: FINI** — tout est fusionné")[0] == "FINI"


def test_erreur_sans_json_en_reprise_ne_rend_pas_le_cout_negatif(banc, capsys):
    assert banc.lancer([continuer(60_000, cout=2.0), {"sortie_invalide": True}]) == 4
    assert [x["cout_delta_usd"] for x in banc.lignes()] == [2.0, 0.0]
    assert "coût : 2.00 $" in capsys.readouterr().out


def test_cout_en_baisse_compte_comme_cout_du_seul_appel(banc, capsys):
    # Si la CLI ne cumulait pas total_cost_usd en --resume, la valeur peut baisser : elle vaut alors le tour.
    assert banc.lancer([continuer(60_000, cout=2.0), FINI | {"total": 0.5}]) == 0
    assert [x["cout_delta_usd"] for x in banc.lignes()] == [2.0, 0.5]
    assert "coût : 2.50 $" in capsys.readouterr().out


def test_executable_introuvable_au_lancement_code_4_journalise(banc, tmp_path, capsys):
    absent = str(tmp_path / "claude-absent.exe")
    assert rr.principal(["--projet", str(banc.projet), "--claude", absent]) == 4
    assert "lancement de claude impossible" in capsys.readouterr().out
    assert [x["etat"] for x in banc.lignes()] == ["ERREUR"]


def test_transcription_absente_avertit(banc, capsys):
    assert banc.lancer([continuer(150_000) | {"sans_transcription": True}, FINI]) == 0
    assert "transcription introuvable" in capsys.readouterr().err
    assert [x["mode"] for x in banc.lignes()] == ["nouvelle", "reprise"]


def test_racine_par_defaut_suit_claude_config_dir(monkeypatch, tmp_path):
    monkeypatch.delenv(rr.ENV_RACINE, raising=False)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    assert rr.racine_par_defaut() == tmp_path / "cfg" / "projects"
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    assert rr.racine_par_defaut() == Path.home() / ".claude" / "projects"


def test_max_sessions_atteint(banc, capsys):
    assert banc.lancer([continuer(150_000)] * 5, "--max-sessions", "2") == 3
    assert len(banc.appels()) == 2
    assert "--max-sessions atteint (2)" in capsys.readouterr().out


def test_max_tours_atteint(banc, capsys):
    assert banc.lancer([continuer(10_000)] * 5, "--max-tours", "3") == 3
    assert len(banc.appels()) == 3
    assert "--max-tours atteint (3)" in capsys.readouterr().out


def test_journal_une_ligne_par_tour_et_delta_de_cout(banc):
    tours = [continuer(60_000, cout=2.0), continuer(70_000, cout=0.5), continuer(140_000, cout=1.0), FINI]
    assert banc.lancer(tours) == 0
    lignes = banc.lignes()
    assert len(lignes) == 4
    for ligne in lignes:
        assert set(ligne) == {"debut", "fin", "session", "mode", "pic", "cout_usd", "cout_delta_usd", "etat", "raison", "code"}
        assert datetime.fromisoformat(ligne["debut"]).tzinfo is not None
    assert [x["mode"] for x in lignes] == ["nouvelle", "reprise", "reprise", "nouvelle"]
    assert [x["cout_usd"] for x in lignes] == [2.0, 2.5, 3.5, 0.5]  # cumulé par session
    assert [x["cout_delta_usd"] for x in lignes] == [2.0, 0.5, 1.0, 0.5]
    assert [x["pic"] for x in lignes] == [60_000, 70_000, 140_000, 50_000]
    assert [x["etat"] for x in lignes] == ["CONTINUER"] * 3 + ["FINI"]
    assert lignes[3]["raison"] == "tout est fusionné"
    assert lignes[0]["session"] == lignes[1]["session"] == lignes[2]["session"] != lignes[3]["session"]
    assert re.fullmatch(r"[0-9a-f-]{36}", lignes[0]["session"])


def test_a_sec_n_execute_rien(banc, capsys):
    code = rr.principal(["--projet", str(banc.projet), "--claude", "claude-qui-nexiste-pas", "--a-sec"])
    sortie = capsys.readouterr().out
    assert code == 0
    assert banc.appels() == [] and not banc.journal.exists()
    assert "--session-id" in sortie and "--resume" in sortie and "A sec : rien n'a été exécuté." in sortie
    assert "pic < 100000 -> reprise" in sortie


def test_etat_absent_erreur_claire(tmp_path, capsys):
    code = rr.principal(["--projet", str(tmp_path), "--claude", "x"])
    assert code == 1
    assert "Fichier d'état introuvable" in capsys.readouterr().err


def test_etat_personnalise(banc):
    (banc.projet / "autre.md").write_text("# autre\n", encoding="utf-8")
    assert banc.lancer([FINI], "--etat", "autre.md") == 0
    assert "autre.md" in banc.appels()[0]["prompt"]
    assert (banc.projet / "relancer-run.jsonl").exists()


def test_avancement_run_ignore_la_section_brief(projet, capsys):  # noqa: F811
    args = [str(projet), "--maintenant", "2026-10-18 20:30"]
    assert ar.main(args) == 0
    avant = capsys.readouterr().out
    fichier = projet / ar.DOSSIER / "run-autonome.md"
    texte = fichier.read_text(encoding="utf-8")
    brief = (
        "## Brief\n\n- Tâche : migrer le module 1.2 puis 1.3 (story 1.2 en cours, vague V1)\n"
        "- Pièges : 3.1 reportée ; | 9.9 | faux | tableau |\n- 2026-10-18 11:11 · 9.9 · fusion · faux · abc1234\n\n"
    )
    assert "## Journal" in texte
    fichier.write_text(texte.replace("## Journal", brief + "## Journal", 1), encoding="utf-8")
    assert ar.main(args) == 0
    assert capsys.readouterr().out == avant


def test_avancement_run_ignore_un_tableau_de_vagues_dans_le_brief(projet, capsys):  # noqa: F811
    # Gabarit : `## Brief` est placé avant `## Sprint 1` ; un plan restant écrit en tableau ne doit pas être lu.
    args = [str(projet), "--maintenant", "2026-10-18 20:30"]
    assert ar.main(args) == 0
    avant = capsys.readouterr().out
    fichier = projet / ar.DOSSIER / "run-autonome.md"
    texte = fichier.read_text(encoding="utf-8")
    brief = (
        "## Brief\n\n### Plan des vagues restantes\n\n| Vague | Stories | Après |\n|---|---|---|\n"
        "| V1 | 9.8 · 9.9 | — |\n| V7 | 9.7 ★ | 9.8 |\n\n"
    )
    assert "## Sprint 1" in texte
    avec_brief = texte.replace("## Sprint 1", brief + "## Sprint 1", 1)
    assert ar.lire_plan(avec_brief) == ar.lire_plan(texte)
    fichier.write_text(avec_brief, encoding="utf-8")
    assert ar.main(args) == 0
    assert capsys.readouterr().out == avant
