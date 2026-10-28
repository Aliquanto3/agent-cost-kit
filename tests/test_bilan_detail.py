"""Tests de scripts/bilan_detail.py et des options --du/--au, --racine, --detail de bilan_tokens.py (tmp_path)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import bilan_detail as bd
import bilan_i18n as i18n
import bilan_tokens as bt
import mesurer_couts as mc

CWD_A = "C:\\Users\\u\\Documents\\GitHub\\depot-a"
OPUS, SONNET, HAIKU = "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"


# --- Fabrication de transcriptions ---
def asst(ts, mid, modele=OPUS, session="S1", cwd=CWD_A, effort="high", outils=(), lu=2000, entree=1000, sortie=50):
    contenu = [{"type": "text", "text": "x" * 220}]
    for nom, detail in outils:
        cle = {"Bash": "command", "PowerShell": "command", "Agent": "subagent_type", "Task": "subagent_type", "Skill": "skill"}.get(nom)
        contenu.append({"type": "tool_use", "name": nom, "input": {cle: detail} if cle else {"file_path": "f"}})
    usage = {"input_tokens": entree, "output_tokens": sortie, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": lu, "inference_geo": "global"}
    return json.dumps({"timestamp": ts, "effort": effort, "cwd": cwd, "sessionId": session,
                       "message": {"role": "assistant", "id": mid, "model": modele, "content": contenu, "usage": usage}})


def user(ts, texte):
    return json.dumps({"timestamp": ts, "message": {"role": "user", "content": texte}})


def ecrire(chemin: Path, lignes: list[str], meta: dict | None = None) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    if meta is not None:
        chemin.with_suffix(".meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return chemin


def monde(racine: Path, tag: str, jour: str = "2026-10-02") -> Path:
    """Une session principale (skill, /clear, édition, push, lancement d'agent) et deux sous-agents."""
    dossier = racine / "proj"
    t = lambda hm: f"{jour}T{hm}:00Z"  # noqa: E731
    ecrire(dossier / f"S{tag}.jsonl", [
        user(t("08:00"), "<command-name>/bmad-prd</command-name>"),
        asst(t("08:01"), f"{tag}-o1", session=f"S{tag}", outils=[("Read", None)], effort="medium"),
        user(t("09:00"), "<command-name>/clear</command-name>"),
        asst(t("09:05"), f"{tag}-o2", session=f"S{tag}", outils=[("Edit", None)]),
        asst(t("09:10"), f"{tag}-o3", session=f"S{tag}", outils=[("Bash", "git push origin main")]),
        asst(t("09:15"), f"{tag}-o4", session=f"S{tag}", outils=[("Agent", "dev-story")]),
    ])
    ecrire(dossier / f"S{tag}" / "subagents" / "agent-d.jsonl", [
        user(t("09:16"), "SECRET_PROMPT du dev"),
        asst(t("09:17"), f"{tag}-d1", SONNET, session=f"S{tag}", effort="medium"),
        asst(t("09:18"), f"{tag}-d2", SONNET, session=f"S{tag}", effort="medium", lu=5000),
    ], {"agentType": "dev-story", "description": "Implement story 2.1 SECRET_DESC"})
    ecrire(dossier / f"S{tag}" / "subagents" / "agent-g.jsonl", [
        user(t("09:20"), "SECRET_PROMPT du banc"),
        asst(t("09:21"), f"{tag}-g1", HAIKU, session=f"S{tag}", effort=None),
    ], {"agentType": "general-purpose", "description": "Banc T3 review SECRET_DESC"})
    return racine


def options(racine, out, **champs):
    base = {"mois": "2026-10", "dossier": None, "racine": racine, "machine": "pc", "out": out,
            "mix": mc.MIX_DEFAUT, "methode": mc.METHODE_DEFAUT}
    return Namespace(**{**base, **champs})


def egal(a, b) -> bool:
    """Égalité récursive, flottants à 1e-3 près."""
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(egal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(egal(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, float) or isinstance(b, float):
        return a == pytest.approx(b, abs=1e-3)
    return a == b


def appel(ts="2026-10-02T10:00:00Z", mid="m", modele=OPUS, session="S1", fichier="/x/S1.jsonl", agent_type=None,
          effort="high", cwd=CWD_A, outils=(), lu=0, entree=0, ecrit_5m=0, sortie=0):
    return {"id": mid, "modele": modele, "fam": mc.famille(modele), "ts": ts, "entree": entree, "ecrit_5m": ecrit_5m,
            "ecrit_1h": 0, "lu": lu, "sortie_declaree": sortie, "sortie": sortie, "geo": None, "effort": effort,
            "cwd": cwd, "session": session, "outils": list(outils), "fichier": fichier, "agent_type": agent_type}


def info(type_agent=None, skills=(), desc=None, prompt=None, premier_ts=None):
    return {"skills": list(skills), "desc": desc, "prompt": prompt, "type": type_agent, "premier_ts": premier_ts}


def classeur(infos, repos=None, **config):
    cfg = {**bd.charger_config(None), **config}
    return bd.Classeur(infos, cfg, {"repos": repos or {}, "statuses": {}, "proprietaire": None, "topic": None, "url": None})


def construire(appels, infos, **config):
    cfg = {**bd.charger_config(None), **config}
    return bd.construire(appels, infos, cfg, mc.MIX_DEFAUT, mc.METHODE_DEFAUT)


def ids_recos(detail):
    return {r["id"] for r in detail["recos"]}


def cout(a):
    return mc.couts([a])["cout"]


# --- mesurer_couts.appels(details=True) ---
def test_appels_details_ne_change_pas_les_champs_existants(tmp_path):
    long = "git push " + "y" * 300
    f = ecrire(tmp_path / "s.jsonl", [
        asst("2026-10-02T10:00:00Z", "a", outils=[("Bash", long), ("Agent", "reviewer"), ("Skill", "bmad-prd"), ("Edit", None)]),
        asst("2026-10-02T10:01:00Z", "b", effort=None, cwd=None),
    ])
    simples, detaillees = mc.appels(f), mc.appels(f, details=True)
    assert [{k: v for k, v in d.items() if k in s} for s, d in zip(simples, detaillees, strict=True)] == simples
    assert set(detaillees[0]) - set(simples[0]) == {"effort", "cwd", "session", "outils"}
    assert (detaillees[0]["effort"], detaillees[0]["cwd"], detaillees[0]["session"]) == ("high", CWD_A, "S1")
    assert detaillees[0]["outils"] == [("Bash", long[:160]), ("Agent", "reviewer"), ("Skill", "bmad-prd"), ("Edit", None)]
    assert len(detaillees[0]["outils"][0][1]) == 160
    assert detaillees[1]["effort"] is None and detaillees[1]["outils"] == []


# --- Période et racines ---
def test_periode_bornes_incluses_et_nom_des_fichiers(tmp_path):
    racine = tmp_path / "projects"
    ecrire(racine / "p" / "s.jsonl", [
        asst("2026-09-30T23:59:59Z", "avant"), asst("2026-10-01T00:00:00Z", "debut"),
        asst("2026-10-15T23:59:59Z", "fin"), asst("2026-10-16T00:00:00Z", "apres"),
    ])
    out = tmp_path / "out"
    assert bt.commande_collecte(options(racine, out, mois=None, du="2026-10-01", au="2026-10-15")) == 0
    bilan = json.loads((out / "2026-10-01_2026-10-15-pc.json").read_text(encoding="utf-8"))
    assert (bilan["mois"], bilan["du"], bilan["au"]) == ("2026-10", "2026-10-01", "2026-10-15")
    assert sum(m["appels"] for m in bilan["modeles"]) == 2
    assert bilan["premier_appel"] == "2026-10-01T00:00:00Z" and bilan["dernier_appel"] == "2026-10-15T23:59:59Z"
    assert (out / "2026-10-01_2026-10-15-pc.html").exists()


def test_sans_periode_le_json_n_a_ni_du_ni_au(tmp_path):
    racine = tmp_path / "projects"
    ecrire(racine / "p" / "s.jsonl", [asst("2026-10-02T10:00:00Z", "a")])
    assert bt.commande_collecte(options(racine, tmp_path / "out")) == 0
    bilan = json.loads((tmp_path / "out" / "2026-10-pc.json").read_text(encoding="utf-8"))
    assert "du" not in bilan and "au" not in bilan and "detail" not in bilan


@pytest.mark.parametrize(("du", "au", "message"), [
    ("2026-10-20", "2026-11-02", "même mois"),
    ("2026-10-20", "2026-10-02", "après --au"),
    ("2026-10-20", None, "vont ensemble"),
    ("2026-13-01", "2026-13-02", "date AAAA-MM-JJ"),
])
def test_periode_refusee(du, au, message, capsys):
    with pytest.raises(SystemExit) as erreur:
        bt.verifier_periode(du, au)
    assert message in str(erreur.value)


def test_mois_et_periode_exclusifs(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["bilan_tokens.py", "--mois", "2026-10", "--du", "2026-10-01", "--au", "2026-10-02"])
    with pytest.raises(SystemExit) as erreur:
        bt.main()
    assert erreur.value.code == 2
    assert "exclusif" in capsys.readouterr().err


def test_racines_multiples_comptent_une_fois_un_meme_message_id(tmp_path):
    ligne_commune = asst("2026-10-02T10:00:00Z", "meme")
    ecrire(tmp_path / "r1" / "p" / "s.jsonl", [ligne_commune, asst("2026-10-02T11:00:00Z", "seul1")])
    ecrire(tmp_path / "r2" / "p" / "s.jsonl", [ligne_commune, asst("2026-10-02T12:00:00Z", "seul2")])
    out = tmp_path / "out"
    assert bt.commande_collecte(options([tmp_path / "r1", tmp_path / "r2"], out)) == 0
    bilan = json.loads((out / "2026-10-pc.json").read_text(encoding="utf-8"))
    assert sum(m["appels"] for m in bilan["modeles"]) == 3


def test_racine_par_defaut_et_valeur_unique():
    assert bt.liste_racines(Namespace(racine=None)) == [bt.RACINE_DEFAUT]
    assert bt.liste_racines(Namespace(racine=Path("x"))) == [Path("x")]
    assert bt.liste_racines(Namespace(racine=[Path("a"), Path("b")])) == [Path("a"), Path("b")]


def test_aucun_dossier_sous_aucune_racine(tmp_path, capsys):
    assert bt.commande_collecte(options([tmp_path / "vide1", tmp_path / "vide2"], tmp_path / "o")) == 1
    err = capsys.readouterr().err
    assert "vide1" in err and "vide2" in err


# --- Projet ---
@pytest.mark.parametrize(("cwd", "attendu"), [
    ("C:\\Users\\u\\Documents\\GitHub\\agent-cost-kit-lot4", "agent-cost-kit"),
    ("/home/u/GitHub/agent-cost-kit-wt-014/sous/dossier", "agent-cost-kit"),
    ("/home/u/dev/WaveStack", "wavestack"),
    ("/home/u/github/wavestack_v2", "wavestack"),
    ("/home/u/GitHub/wavestackx", "wavestackx"),
    ("/home/u/GitHub/agentic-harness-training-demo", "wavestack"),
    ("/home/u/GitHub/autre-depot", "autre-depot"),
    ("/home/u/GitHub", bd.RACINE),
    ("/home/dev/GitHub/agent-cost-kit", "agent-cost-kit"),  # parent suivi d'un parent : le second compte (revue 0.16.0)
    ("/home/u/GitHub/autre-depot/dev/src", "autre-depot"),
    ("C:\\Users\\u\\GitHub\\", bd.RACINE),
    ("/tmp/hors-parent", bd.RACINE),
    ("", bd.RACINE),
    (None, bd.RACINE),
])
def test_projet(cwd, attendu):
    c = classeur({}, repos={"agent-cost": "A", "agent-cost-kit": "Kit", "wavestack": "WaveStack"},
                 alias={"agentic-harness": "wavestack"})
    assert c.projet(cwd) == attendu


def test_projet_sans_portfolio_ni_alias_garde_le_nom():
    assert classeur({}).projet("/home/u/GitHub/mon-depot-x") == "mon-depot-x"
    assert classeur({}, parents=["Projets"]).projet("/home/u/Projets/depot") == "depot"
    assert classeur({}, parents=["Projets"]).projet("/home/u/GitHub/depot") == bd.RACINE


# --- Étape ---
def test_etape_session_skill_clear_livraison_et_outils():
    infos = {"/x/S1.jsonl": info(skills=[("t1", "bmad-prd"), ("t2", "model"), ("t4", "clear")])}
    c = classeur(infos)
    assert c.etape(appel(ts="t0", outils=[("Edit", None)])) == ("dev", "Édition en session principale")
    assert c.etape(appel(ts="t3", outils=[("Read", None)])) == ("specs", "bmad-prd")  # /model ignoré
    assert c.etape(appel(ts="t3", outils=[("Bash", "git push origin x")])) == ("livraison", bd.LIBELLE_LIVRAISON)
    assert c.etape(appel(ts="t5", outils=[("Read", None)])) == ("libre", bd.LIBELLE_LECTURE)  # après /clear
    assert c.etape(appel(ts="t5")) == ("libre", "Réponse ou réflexion sans outil")
    assert c.etape(appel(ts="t5", outils=[("Agent", "x")]))[0] == "pilotage"
    assert c.etape(appel(ts="t5", outils=[("Bash", "uv run pytest -q")])) == ("relecture", "Tests et lint lancés en session")
    assert c.etape(appel(ts="t5", outils=[("WebFetch", None)]))[0] == "recherche"
    assert c.etape(appel(ts="t5", outils=[("Artifact", None)]))[0] == "contenus"


def test_etape_sous_agent_type_explicite_skill_propre_description_puis_prompt():
    f = "/x/S1/subagents/agent-a.jsonl"
    infos = {
        f: info("general-purpose", skills=[("t1", "bmad-architect"), ("t3", "bmad-code-review")], desc="zzz", prompt="zzz"),
        "/x/S1/subagents/d.jsonl": info("dev-story"),
        "/x/S1/subagents/e.jsonl": info("general-purpose", desc="recherche des sources", prompt="Implement"),
        "/x/S1/subagents/h.jsonl": info("general-purpose", desc="zzz", prompt="Implement the story"),
        "/x/S1/subagents/o.jsonl": info("Autre", desc="zzz", prompt="zzz", premier_ts="t2"),
        "/x/S1.jsonl": info(skills=[("t1", "bmad-prd")]),
    }
    c = classeur(infos)
    agent = lambda fichier, t, type_agent: appel(ts=t, fichier=fichier, agent_type=type_agent)  # noqa: E731
    assert c.etape(agent("/x/S1/subagents/d.jsonl", "t9", "dev-story")) == ("dev", "dev-story (agent-cost-kit)")
    assert c.etape(agent(f, "t2", "general-purpose")) == ("archi", "bmad-architect (dans un sous-agent)")
    assert c.etape(agent(f, "t4", "general-purpose")) == ("relecture", "bmad-code-review (dans un sous-agent)")
    assert c.etape(agent("/x/S1/subagents/e.jsonl", "t9", "general-purpose")) == ("recherche", "Sous-agents généralistes (recherche)")
    assert c.etape(agent("/x/S1/subagents/h.jsonl", "t9", "general-purpose")) == ("dev", "Sous-agents généralistes (implémentation)")
    assert c.etape(agent("/x/S1/subagents/o.jsonl", "t9", "Autre")) == ("specs", "Sous-agent Autre lancé par bmad-prd")


def test_balise_command_name_citee_dans_un_texte_n_en_fait_pas_un_skill(tmp_path):
    """Revue 0.16.0 : seul un nom plausible sort d'une balise ; un texte cité ne devient jamais un sous-libellé."""
    f = ecrire(tmp_path / "S1.jsonl", [
        user("2026-10-02T08:00:00Z", "Cite <command-name>Tu implémentes la story, git push et build</command-name> ici"),
        user("2026-10-02T08:01:00Z", "<command-name>/bmad-prd</command-name>"),
        asst("2026-10-02T08:02:00Z", "a1", outils=[("Skill", "texte libre avec espaces")]),
    ])
    assert [nom for _, nom in bd.lire_infos(f)["skills"]] == ["bmad-prd"]


def test_desc_port_ne_capte_ni_report_ni_support():
    assert bd.groupe_desc("Write the monthly report") is None
    assert bd.groupe_desc("Port the parser to Rust") == "dev"


def test_etape_sous_agent_sans_aucun_indice_retombe_sur_dev():
    infos = {"/x/S1/subagents/o.jsonl": info("Autre", desc="zzz", prompt="zzz", premier_ts="t0"), "/x/S1.jsonl": info()}
    assert classeur(infos).etape(appel(fichier="/x/S1/subagents/o.jsonl", agent_type="Autre")) == ("dev", "Sous-agent Autre (autre)")


# --- Rôle et sous-clé ---
def test_role_et_sous_cle_modele_effort():
    assert bd.Classeur.role(appel()) == bd.ORCHESTRATEUR
    assert bd.Classeur.role(appel(agent_type="dev-story")) == "agent-cost-kit:dev-story"
    assert bd.Classeur.role(appel(agent_type="reviewer")) == "agent-cost-kit:reviewer"
    assert bd.Classeur.role(appel(agent_type="agent-cost-kit:lookup")) == "agent-cost-kit:lookup"
    assert bd.Classeur.role(appel(agent_type="general-purpose")) == "general-purpose"
    assert bd.Classeur.sous_cle(appel(modele="claude-opus-5-5", effort="high")) == "Opus 5.5 · effort high"
    assert bd.Classeur.sous_cle(appel(modele="claude-sonnet-5", effort=None)) == "Sonnet 5 · effort ?"
    assert bd.Classeur.sous_cle(appel(modele="claude-haiku-4-5-20251001", effort="low")) == "Haiku 4.5 · effort low"


# --- Agrégation ---
def scenario_mixte():
    infos = {
        "/x/S1.jsonl": info(skills=[("2026-10-02T09:00:00Z", "bmad-prd")]),
        "/x/S1/subagents/d.jsonl": info("dev-story", desc="Implement"),
        "/x/S1/subagents/g.jsonl": info("general-purpose", desc="Banc T1", premier_ts="2026-10-02T10:00:00Z"),
    }
    appels = [
        appel(ts="2026-10-02T10:01:00Z", mid="a", lu=10000, entree=1000, sortie=200, outils=[("Read", None)]),
        appel(ts="2026-10-02T10:02:00Z", mid="b", modele=SONNET, effort="medium", cwd="/h/GitHub/depot-b", lu=500000, entree=300, sortie=80, outils=[("Edit", None)]),
        appel(ts="2026-10-02T10:03:00Z", mid="c", modele=SONNET, effort="medium", fichier="/x/S1/subagents/d.jsonl", agent_type="dev-story", lu=70000, ecrit_5m=900, sortie=40),
        appel(ts="2026-10-02T10:04:00Z", mid="d", modele=HAIKU, effort=None, fichier="/x/S1/subagents/g.jsonl", agent_type="general-purpose", lu=3000, sortie=10),
    ]
    return appels, infos


def test_impact_d_un_bloc_recalcule_depuis_brut_egal_a_impact_appels():
    appels, infos = scenario_mixte()
    detail = construire(appels, infos)
    cellules = detail["brut"]["cellules"]
    attendu = mc.impact_appels(appels, mc.MIX_DEFAUT, mc.METHODE_DEFAUT)
    obtenu = bd.impact_modeles(bd.modeles_de(cellules, bd.DIM_ROLE, bd.ORCHESTRATEUR), mc.MIX_DEFAUT, mc.METHODE_DEFAUT)
    orch = mc.impact_appels([a for a in appels if a["agent_type"] is None], mc.MIX_DEFAUT, mc.METHODE_DEFAUT)
    for g in mc.GRANDEURS:
        for borne in ("min", "max"):
            assert obtenu[g][borne] == pytest.approx(orch[g][borne], rel=1e-9)
    total = detail["total"]
    assert total["gwp"] == [pytest.approx(attendu["gwp_gco2e"]["min"], abs=1e-3), pytest.approx(attendu["gwp_gco2e"]["max"], abs=1e-3)]
    assert total["nrj"][1] == pytest.approx(attendu["energie_wh"]["max"], abs=1e-3)
    assert total["eau"][0] == pytest.approx(attendu["eau_l"]["min"], abs=1e-3)
    assert total["cout"] == pytest.approx(mc.couts(appels)["cout"], abs=1e-4)
    assert total["appels"] == 4 and total["out"] == 330
    assert total["inTot"] == sum(a["entree"] + a["ecrit_5m"] + a["lu"] for a in appels)


def test_blocs_etapes_roles_et_projets_sur_un_scenario_mixte():
    appels, infos = scenario_mixte()
    d = construire(appels, infos)
    etapes = {e["id"]: e for e in d["etapes"]}
    assert [e["id"] for e in d["etapes"]] == [g for g, _ in bd.GROUPES if g in etapes]  # ordre d'affichage
    assert etapes["specs"]["appels"] == 2 and etapes["specs"]["cout_orch"] == pytest.approx(etapes["specs"]["cout"], abs=1e-4)
    assert [s["label"] for s in etapes["dev"]["sous"]] == ["dev-story (agent-cost-kit)"]
    assert etapes["relecture"]["sous"][0]["label"] == "Sous-agents généralistes (revue, audit, tests)"
    assert etapes["relecture"]["cout_orch"] == 0
    roles = {r["label"]: r for r in d["roles"]}
    assert d["roles"][0]["orch"] and d["roles"][0]["label"] == bd.ORCHESTRATEUR
    assert roles["agent-cost-kit:dev-story"]["n_agents"] == 1 and roles["general-purpose"]["n_agents"] == 1
    assert {m["label"] for m in roles[bd.ORCHESTRATEUR]["par_me"]} == {"Opus 5.5 · effort high", "Sonnet 5.5 · effort medium"}
    assert roles["general-purpose"]["par_me"][0]["label"] == "Haiku 5.5 · effort ?"
    assert d["orch"]["appels"] == 2 and d["sous"]["appels"] == 2 and len(d["sous"]["par_me"]) == 2
    projets = {p["cle"]: p for p in d["projets"]}
    assert set(projets) == {"depot-a", "depot-b"} and not projets["depot-a"]["portfolio"]
    assert projets["depot-b"]["nom"] == "depot-b" and projets["depot-b"]["statut"] is None
    assert sum(projets["depot-a"]["par_groupe"].values()) == pytest.approx(projets["depot-a"]["cout"], abs=1e-4)
    assert d["portfolio"] is False and d["portfolio_url"] is None
    assert d["projets"][0]["cout"] >= d["projets"][1]["cout"]


def test_aucun_texte_de_transcription_dans_le_detail(tmp_path):
    racine = monde(tmp_path / "projects", "A")
    out = tmp_path / "out"
    assert bt.commande_collecte(options(racine, out, detail=True)) == 0
    texte = (out / "2026-10-pc.json").read_text(encoding="utf-8") + (out / "2026-10-pc.html").read_text(encoding="utf-8")
    assert "SECRET_DESC" not in texte and "SECRET_PROMPT" not in texte
    assert "git push origin main" not in texte and '"A-o1"' not in texte  # ni commandes ni identifiants d'appels
    bilan = json.loads((out / "2026-10-pc.json").read_text(encoding="utf-8"))
    assert len(json.dumps(bilan["detail"])) < 50_000


def test_collecte_detail_classe_le_monde_synthetique(tmp_path):
    racine = monde(tmp_path / "projects", "A")
    out = tmp_path / "out"
    bt.commande_collecte(options(racine, out, detail=True))
    d = json.loads((out / "2026-10-pc.json").read_text(encoding="utf-8"))["detail"]
    sous = {e["id"]: {s["label"] for s in e["sous"]} for e in d["etapes"]}
    assert sous["specs"] == {"bmad-prd"}  # avant le /clear
    assert sous["livraison"] == {bd.LIBELLE_LIVRAISON} and sous["pilotage"] == {"Lancement et suivi de sous-agents"}
    assert sous["dev"] == {"Édition en session principale", "dev-story (agent-cost-kit)"}
    assert {r["label"] for r in d["roles"]} == {bd.ORCHESTRATEUR, "agent-cost-kit:dev-story", "general-purpose"}
    assert [p["cle"] for p in d["projets"]] == ["depot-a"]
    assert d["recos"] and all(set(r) == {"id", "titre", "mesure", "pratique", "gain"} for r in d["recos"])
    assert "mesure" in {r["id"] for r in d["recos"]}  # « Banc T3 review » correspond au motif par défaut


# --- Fusion ---
def test_fusion_de_deux_bilans_detailles_egale_une_collecte_unique(tmp_path):
    a = monde(tmp_path / "A" / "projects", "A")
    b = monde(tmp_path / "B" / "projects", "B", jour="2026-10-03")
    periode = {"mois": None, "du": "2026-10-01", "au": "2026-10-31", "detail": True}
    for nom, racine in (("a", a), ("b", b)):
        bt.commande_collecte(options(racine, tmp_path / nom, machine=nom, **periode))
    bt.commande_collecte(options([a, b], tmp_path / "unique", machine="u", **periode))
    bt.commande_fusion(Namespace(
        fusionner=[str(tmp_path / n / f"2026-10-01_2026-10-31-{n}.json") for n in ("a", "b")], out=tmp_path / "f", config=None))
    fusion = json.loads((tmp_path / "f" / "2026-10-01_2026-10-31-consolide.json").read_text(encoding="utf-8"))
    unique = json.loads((tmp_path / "unique" / "2026-10-01_2026-10-31-u.json").read_text(encoding="utf-8"))
    assert (fusion["du"], fusion["au"]) == ("2026-10-01", "2026-10-31")
    assert (tmp_path / "f" / "2026-10-01_2026-10-31-consolide.html").exists()
    assert set(fusion["detail"]) == set(unique["detail"]) >= {"brut", "projets", "etapes", "roles", "orch", "sous", "recos", "portfolio_url"}
    for cle in unique["detail"]:
        assert egal(fusion["detail"][cle], unique["detail"][cle]), cle
    assert unique["detail"]["total"]["appels"] == 14


def test_fusion_sans_detail_complet_l_omet_et_avertit(tmp_path, capsys):
    a = monde(tmp_path / "A" / "projects", "A")
    b = monde(tmp_path / "B" / "projects", "B")
    bt.commande_collecte(options(a, tmp_path / "a", machine="a", detail=True))
    bt.commande_collecte(options(b, tmp_path / "b", machine="b"))
    capsys.readouterr()
    bt.commande_fusion(Namespace(fusionner=[str(tmp_path / "a" / "2026-10-a.json"), str(tmp_path / "b" / "2026-10-b.json")], out=tmp_path / "f"))
    assert "n'ont pas de détail" in capsys.readouterr().err
    assert "detail" not in json.loads((tmp_path / "f" / "2026-10-consolide.json").read_text(encoding="utf-8"))


def _min(tmp_path, nom, **champs):
    base = {"schema": 1, "machine": nom, "mois": "2026-10", "dossier": None, "genere_le": "2026-10-23T00:00:00+00:00",
            "premier_appel": "2026-10-01T00:00:00Z", "dernier_appel": "2026-10-01T00:00:00Z", "mix": mc.MIX_DEFAUT,
            "modeles": [], "prix": {}}
    chemin = tmp_path / f"{nom}.json"
    chemin.write_text(json.dumps({**base, **champs}), encoding="utf-8")
    return str(chemin)


def test_fusion_refuse_des_periodes_differentes(tmp_path):
    a = _min(tmp_path, "a", du="2026-10-01", au="2026-10-15")
    b = _min(tmp_path, "b", du="2026-10-01", au="2026-10-20")
    with pytest.raises(SystemExit, match="Périodes différentes"):
        bt.commande_fusion(Namespace(fusionner=[a, b], out=tmp_path / "o"))
    with pytest.raises(SystemExit, match="Périodes différentes"):
        bt.commande_fusion(Namespace(fusionner=[a, _min(tmp_path, "c")], out=tmp_path / "o"))


# --- Config et portfolio ---
def test_config_absente_invalide_et_surcharges(tmp_path):
    defaut = bd.charger_config(tmp_path / "absente.json")
    assert defaut["parents"] == ["GitHub", "dev"] and defaut["alias"] == {} and defaut["portfolio"] == {}
    assert defaut["motif_experiences"] == bd.MOTIF_EXPERIENCES_DEFAUT
    (tmp_path / "c.json").write_text('{"parents": ["Code"], "alias": {"x": "y"}, "inconnu": 1}', encoding="utf-8")
    config = bd.charger_config(tmp_path / "c.json")
    assert config["parents"] == ["Code"] and config["alias"] == {"x": "y"} and "inconnu" not in config
    (tmp_path / "mauvais.json").write_text("{pas du json", encoding="utf-8")
    with pytest.raises(SystemExit, match="illisible"):
        bd.charger_config(tmp_path / "mauvais.json")
    (tmp_path / "regex.json").write_text('{"motif_experiences": "("}', encoding="utf-8")
    with pytest.raises(SystemExit, match="motif_experiences invalide"):
        bd.charger_config(tmp_path / "regex.json")
    (tmp_path / "liste.json").write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit, match="objet JSON"):
        bd.charger_config(tmp_path / "liste.json")


def config_portfolio(tmp_path, **portfolio):
    (tmp_path / "portfolio.json").write_text(json.dumps({
        "topic": "ai-portfolio",
        "statuses": {"status-test": {"fr": "En test"}, "status-dev": {"fr": "En développement"}},
        "repos": {"depot-a": {"name": "Dépôt A"}},
    }), encoding="utf-8")
    return {**bd.charger_config(None), "portfolio": {"fichier": str(tmp_path / "portfolio.json"), "url": "https://github.com/me",
                                                     "proprietaire": "me", **portfolio}}


GH = json.dumps([{"name": "depot-a", "repositoryTopics": [{"name": "ai-portfolio"}, {"name": "status-test"}],
                  "latestRelease": {"tagName": "v1.2.3"}}])


def test_portfolio_etat_et_version_via_gh(tmp_path):
    config = config_portfolio(tmp_path)
    appels = [appel(mid="a", lu=1000), appel(mid="b", cwd="/h/GitHub/hors", lu=500)]
    commandes = []

    def faux_gh(arguments):
        commandes.append(arguments)
        return GH

    d = bd.construire(appels, {"/x/S1.jsonl": info()}, config, mc.MIX_DEFAUT, mc.METHODE_DEFAUT, executer=faux_gh)
    assert commandes == [["repo", "list", "me", "--topic", "ai-portfolio", "--json", "name,repositoryTopics,latestRelease", "--limit", "200"]]
    projets = {p["cle"]: p for p in d["projets"]}
    a = projets["depot-a"]
    assert (a["nom"], a["portfolio"], a["statut"], a["version"], a["url"]) == ("Dépôt A", True, "En test", "v1.2.3", "https://github.com/me/depot-a")
    assert projets["hors"]["portfolio"] is False and projets["hors"]["url"] is None
    assert d["portfolio"] is True and d["portfolio_url"] == "https://github.com/me"


@pytest.mark.parametrize("erreur", [
    FileNotFoundError("gh"), subprocess.CalledProcessError(1, "gh"), subprocess.TimeoutExpired("gh", 30), ValueError("json"),
])
def test_gh_en_echec_pas_d_etat_et_le_bilan_continue(tmp_path, capsys, erreur):
    def en_echec(_):
        raise erreur

    d = bd.construire([appel(mid="a", lu=1000)], {"/x/S1.jsonl": info()}, config_portfolio(tmp_path), mc.MIX_DEFAUT, mc.METHODE_DEFAUT, executer=en_echec)
    p = d["projets"][0]
    assert p["nom"] == "Dépôt A" and p["statut"] is None and p["version"] is None
    assert "états du portfolio indisponibles" in capsys.readouterr().err


def test_gh_sortie_non_json_et_sans_proprietaire(tmp_path, capsys):
    portfolio = bd.lire_portfolio(config_portfolio(tmp_path))
    assert bd.lire_etats(portfolio, executer=lambda _: "pas du json") == {}
    assert "indisponibles" in capsys.readouterr().err
    sans = bd.lire_portfolio(config_portfolio(tmp_path, proprietaire=None))
    assert bd.lire_etats(sans, executer=lambda _: pytest.fail("gh ne doit pas être lancé")) == {}


def test_portfolio_fichier_illisible(tmp_path):
    with pytest.raises(SystemExit, match="Portfolio .* illisible"):
        bd.lire_portfolio({"portfolio": {"fichier": str(tmp_path / "absent.json")}})


# --- Recommandations ---
def agents_cout(fichier, type_agent, n, modele=SONNET, lu=0, desc=None, prompt="zzz", jour=2, sortie=0):
    """n appels d'un sous-agent ; renvoie (appels, infos)."""
    appels = [appel(ts=f"2026-10-{jour:02d}T10:{i:02d}:00Z", mid=f"{fichier}-{i}", modele=modele, fichier=fichier,
                    agent_type=type_agent, lu=lu, sortie=sortie, effort="medium") for i in range(n)]
    return appels, {fichier: info(type_agent, desc=desc, prompt=prompt, premier_ts=appels[0]["ts"])}


def groupe(*lots):
    appels, infos = [], {"/x/S1.jsonl": info()}
    for a, i in lots:
        appels += a
        infos |= i
    return appels, infos


def flotte(prefixe, type_agent, nombre, **params):
    return [agents_cout(f"/x/S1/subagents/{prefixe}{i}.jsonl", type_agent, 1, **params) for i in range(nombre)]


def test_reco_implementation_generaliste_declenchee_avec_son_gain():
    appels, infos = groupe(*flotte("g", "general-purpose", 5, modele=OPUS, lu=5_000_000, desc="Implement story"),
                           *flotte("d", "dev-story", 5, lu=200_000))
    reco = next(r for r in construire(appels, infos)["recos"] if r["id"] == "implementation-generaliste")
    cg, cd = cout(appels[0]), cout(appels[5])
    assert cg > 1.5 * cd
    gain = (round(cg, 2) - round(cd, 2)) * 5
    assert reco["gain"] == [pytest.approx(gain * 0.8, abs=0.02), pytest.approx(gain * 1.2, abs=0.02)]
    assert "5 sous-agents généralistes" in reco["mesure"] and "<code>dev-story</code>" in reco["mesure"]


@pytest.mark.parametrize(("n_gp", "n_ds", "lu_gp"), [(4, 5, 5_000_000), (5, 4, 5_000_000), (5, 5, 100_000)])
def test_reco_implementation_generaliste_non_declenchee(n_gp, n_ds, lu_gp):
    appels, infos = groupe(*flotte("g", "general-purpose", n_gp, modele=OPUS, lu=lu_gp, desc="Implement story"),
                           *flotte("d", "dev-story", n_ds, lu=200_000))
    assert "implementation-generaliste" not in ids_recos(construire(appels, infos))


def test_reco_relecture_par_le_reviewer_sur_opus_et_gain():
    appels, infos = groupe(*flotte("r", "reviewer", 4, modele=OPUS, lu=1_000_000))
    reco = next(r for r in construire(appels, infos)["recos"] if r["id"] == "relecture")
    opus = sum(cout(a) for a in appels)
    assert reco["gain"] == [pytest.approx(0.25 * opus, abs=0.01), pytest.approx(0.25 * opus, abs=0.01)]
    appels, infos = groupe(*flotte("r", "reviewer", 4, modele=SONNET, lu=1_000_000))
    assert "relecture" not in ids_recos(construire(appels, infos))
    appels, infos = groupe(*flotte("r", "reviewer", 2, modele=OPUS, lu=1_000_000), *flotte("s", "reviewer", 2, modele=SONNET, lu=1_000_000))
    assert "relecture" not in ids_recos(construire(appels, infos))  # 50 % exactement : pas plus de 50 %


def test_reco_relecture_par_les_relecteurs_multiples():
    gros = flotte("h", "general-purpose", 2, modele=OPUS, lu=1_000_000, desc="Blind Hunter review")
    autre = agents_cout("/x/S1/subagents/z.jsonl", "lookup", 1, modele=SONNET, lu=10_000_000)
    appels, infos = groupe(*gros, autre)
    reco = next(r for r in construire(appels, infos)["recos"] if r["id"] == "relecture")
    multiples = sum(cout(a) for a in appels[:2])
    assert reco["gain"] == [pytest.approx(0.5 * multiples, abs=0.01), pytest.approx(multiples, abs=0.01)]
    appels, infos = groupe(*flotte("h", "general-purpose", 2, modele=OPUS, lu=100_000, desc="Blind Hunter review"),
                           agents_cout("/x/S1/subagents/z.jsonl", "lookup", 1, modele=SONNET, lu=100_000_000))
    assert "relecture" not in ids_recos(construire(appels, infos))  # sous 3 % du total


def test_reco_contexte_orchestrateur():
    orch = [appel(ts=f"2026-10-02T10:{i:02d}:00Z", mid=f"o{i}", lu=2_000_000, outils=[("Read", None)]) for i in range(3)]
    sous, infos = agents_cout("/x/S1/subagents/a.jsonl", "lookup", 3, lu=100_000)
    d = construire(orch + sous, infos | {"/x/S1.jsonl": info()})
    reco = next(r for r in d["recos"] if r["id"] == "contexte-orchestrateur")
    lecture = sum(cout(a) for a in orch)
    assert reco["gain"] == [pytest.approx(0.4 * lecture, abs=0.01), pytest.approx(0.8 * lecture, abs=0.01)]
    # contexte identique : pas de recommandation
    egaux = [appel(ts=f"2026-10-02T10:{i:02d}:00Z", mid=f"o{i}", lu=100_000, outils=[("Read", None)]) for i in range(3)]
    assert "contexte-orchestrateur" not in ids_recos(construire(egaux + sous, infos | {"/x/S1.jsonl": info()}))
    # orchestrateur sous 20 % du coût : pas de recommandation
    gros_sous, infos2 = agents_cout("/x/S1/subagents/a.jsonl", "lookup", 3, modele=OPUS, lu=100_000, sortie=1_000_000)
    assert "contexte-orchestrateur" not in ids_recos(construire(orch + gros_sous, infos2 | {"/x/S1.jsonl": info()}))


def test_reco_modele_ancien():
    appels = [appel(mid="a", modele="claude-sonnet-5", lu=10_000_000)]
    d = construire(appels, {"/x/S1.jsonl": info()})
    reco = next(r for r in d["recos"] if r["id"] == "modele-ancien")
    lecture = 10_000_000 * 0.2 / 1e6
    assert reco["gain"] == [pytest.approx(0.9 * lecture * 0.5, abs=0.01), pytest.approx(1.1 * lecture * 0.5, abs=0.01)]
    assert "Sonnet 5 " in reco["mesure"] and "Sonnet 5.5" in reco["mesure"]
    assert "modele-ancien" not in ids_recos(construire([appel(mid="a", modele=SONNET, lu=10_000_000)], {"/x/S1.jsonl": info()}))
    # sous 1 % du coût total : ignoré
    petit = [appel(mid="a", modele="claude-sonnet-5", lu=1000), appel(mid="b", modele=OPUS, lu=100_000_000)]
    assert "modele-ancien" not in ids_recos(construire(petit, {"/x/S1.jsonl": info()}))


def test_plus_recent_famille_et_prix():
    assert bd.plus_recent("claude-sonnet-5") == "claude-sonnet-5-5"
    assert bd.plus_recent("claude-opus-4-6") == "claude-opus-5-5"
    assert bd.plus_recent("claude-opus-5-5") is None
    assert bd.plus_recent("claude-haiku-4-5-20251001") == "claude-haiku-5-5"
    assert bd.plus_recent("inconnu") is None


def test_reco_pilotage_session():
    pilotage = [appel(ts=f"2026-10-02T10:{i:02d}:00Z", mid=f"p{i}", lu=1_000_000, outils=[("Agent", "x")]) for i in range(3)]
    reste = appel(mid="r", lu=10_000_000, outils=[("Edit", None)], ts="2026-10-02T11:00:00Z")
    infos = {"/x/S1.jsonl": info()}
    d = construire(pilotage + [reste], infos)
    reco = next(r for r in d["recos"] if r["id"] == "pilotage-session")
    total = sum(cout(a) for a in pilotage)
    assert reco["gain"] == [pytest.approx(0.2 * total, abs=0.01), pytest.approx(0.4 * total, abs=0.01)]
    assert "pilotage-session" not in ids_recos(construire(pilotage + [appel(mid="r", lu=100_000_000, ts="2026-10-02T11:00:00Z")], infos))  # < 5 %
    # pilotage fait surtout par des sous-agents : moins de 80 % en session
    infos2 = {"/x/S1.jsonl": info(), "/x/S1/subagents/l.jsonl": info("general-purpose", skills=[("2026-10-01T00:00:00Z", "avancement-run")], desc="zzz")}
    en_agent = [appel(ts=f"2026-10-02T10:{i:02d}:00Z", mid=f"q{i}", lu=1_000_000, fichier="/x/S1/subagents/l.jsonl", agent_type="general-purpose") for i in range(3)]
    assert "pilotage-session" not in ids_recos(construire(en_agent + pilotage[:1], infos2))


def test_reco_effort_neutre():
    def orch(effort, n, lu):
        return [appel(ts="2026-10-02T10:00:00Z", mid=f"{effort}{i}", effort=effort, lu=lu) for i in range(n)]
    infos = {"/x/S1.jsonl": info()}
    d = construire(orch("medium", 100, 100_000) + orch("high", 100, 105_000), infos)
    reco = next(r for r in d["recos"] if r["id"] == "effort-neutre")
    assert reco["gain"] is None and "medium" in reco["mesure"] and "high" in reco["mesure"]
    assert "effort-neutre" not in ids_recos(construire(orch("medium", 100, 100_000) + orch("high", 100, 200_000), infos))  # écart
    assert "effort-neutre" not in ids_recos(construire(orch("medium", 99, 100_000) + orch("high", 100, 100_000), infos))  # < 100 appels
    assert "effort-neutre" not in ids_recos(construire(orch("medium", 100, 0) + orch("high", 100, 0), infos))  # coût nul : pas de division
    sonnet = [appel(mid=f"s{i}", modele=SONNET, effort=e, lu=100_000) for i in range(100) for e in ("medium", "high")]
    assert "effort-neutre" not in ids_recos(construire(sonnet, infos))  # Opus seulement


def test_reco_amont_neutre():
    infos = {"/x/S1.jsonl": info(skills=[("2026-10-01T00:00:00Z", "bmad-prd")])}
    prd = appel(mid="a", ts="2026-10-02T10:00:00Z", lu=1_000_000)
    dev = appel(mid="b", ts="2026-10-02T10:01:00Z", lu=20_000_000, outils=[("Edit", None)], session="autre")
    d = construire([prd, dev], infos)
    reco = next(r for r in d["recos"] if r["id"] == "amont")
    assert reco["gain"] is None
    gros_prd = appel(mid="a", ts="2026-10-02T10:00:00Z", lu=10_000_000)
    assert "amont" not in ids_recos(construire([gros_prd, dev], infos))  # amont > 15 %
    petit_dev = appel(mid="b", ts="2026-10-02T10:01:00Z", lu=1_000_000, outils=[("Edit", None)], session="autre")
    autre = appel(mid="c", ts="2026-10-02T10:02:00Z", lu=50_000_000, outils=[("Read", None)], session="autre")
    assert "amont" not in ids_recos(construire([prd, petit_dev, autre], infos))  # dev + relecture <= 50 %


def test_reco_mesure_et_motif_configurable():
    appels, infos = groupe(agents_cout("/x/S1/subagents/e.jsonl", "general-purpose", 2, lu=1_000_000, desc="T3 banc de modèles"))
    reco = next(r for r in construire(appels, infos)["recos"] if r["id"] == "mesure")
    assert reco["gain"] is None and "1 agents" in reco["mesure"]
    assert "mesure" not in ids_recos(construire(appels, infos, motif_experiences=r"^Autre"))
    assert "mesure" in ids_recos(construire(appels, infos, motif_experiences=r"modèles$"))
    appels, infos = groupe(agents_cout("/x/S1/subagents/e.jsonl", "general-purpose", 2, lu=1_000_000, desc="Implement"))
    assert "mesure" not in ids_recos(construire(appels, infos))


def test_recos_triees_par_gain_maximal_decroissant_neutres_a_la_fin():
    appels, infos = groupe(*flotte("g", "general-purpose", 5, modele=OPUS, lu=5_000_000, desc="T1 Implement story"),
                           *flotte("d", "dev-story", 5, lu=200_000),
                           [[appel(mid="v", modele="claude-sonnet-5", lu=3_000_000, ts="2026-10-02T12:00:00Z")], {}])
    recos = construire(appels, infos)["recos"]
    ids = [r["id"] for r in recos]
    assert {"implementation-generaliste", "modele-ancien", "mesure"} <= set(ids)
    avec = [r["gain"][1] for r in recos if r["gain"]]
    assert avec == sorted(avec, reverse=True)
    neutres = [i for i, r in enumerate(recos) if r["gain"] is None]
    assert neutres == list(range(len(recos) - len(neutres), len(recos)))


def test_formats_a_la_francaise():
    assert bd.fr(1234567.891, 2) == "1\u202f234\u202f567,89"
    assert bd.usd(1234.6) == "1\u202f235\u00a0$" and bd.usd(2.345) == "2,35\u00a0$"
    assert bd.pct(1, 200) == "0,5\u00a0%" and bd.pct(1, 4) == "25\u00a0%" and bd.pct(1, 0) == ""


# --- Page ---
def test_html_echappe_les_fermetures_de_script_du_detail(tmp_path):
    d = construire([appel(lu=1000)], {"/x/S1.jsonl": info()})
    d["projets"][0]["nom"] = "dep</script>ot"
    chemin = tmp_path / "b.html"
    bt.ecrire_html({"schema": 1, "machine": "m", "mois": "2026-10", "dossier": None, "modeles": [], "detail": d}, chemin)
    html = chemin.read_text(encoding="utf-8")
    assert html.count("</script>") == bt.GABARIT.read_text(encoding="utf-8").count("</script>")
    assert r"dep<\/script>ot" in html


def test_gabarit_sans_detail_ne_change_pas_la_page_existante():
    gabarit = bt.GABARIT.read_text(encoding="utf-8")
    assert gabarit.count("const BILAN=/*__BILAN__*/null;") == 1
    assert "<template" in gabarit and 'id="detail-mount"' in gabarit  # sections 04 à 07 inertes tant que BILAN.detail manque
    for ancre in ('id="projets"', 'id="etapes"', 'id="agents"', 'id="recos"'):
        assert gabarit.index("<template") < gabarit.index(ancre) < gabarit.index("</template>")


STUB_NODE = r"""
const fs=require("fs"),vm=require("vm");
const html=fs.readFileSync(process.argv[2],"utf8");
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const els={};
const mk=()=>({innerHTML:"",textContent:"",style:{},dataset:{},setAttribute(){},getAttribute(){return null},addEventListener(){},
  closest(){return null},insertAdjacentHTML(_,h){this.innerHTML+=h},appendChild(){},querySelector(){return mk()},querySelectorAll(){return[]},
  classList:{add(){},remove(){},toggle(){},contains(){return false}}});
global.document={addEventListener(){},getElementById:id=>els[id]||(els[id]=mk()),querySelector:()=>mk(),querySelectorAll:()=>[],documentElement:{scrollHeight:0},title:""};
global.localStorage={getItem:()=>null,setItem(){}};
const gestionnaires=[];
global.addEventListener=(type,f)=>{if(type==="DOMContentLoaded")gestionnaires.push(f)};
global.innerHeight=0;global.scrollY=0;
for(const s of scripts)vm.runInThisContext(s);
for(const f of gestionnaires)f();
process.stdout.write(JSON.stringify(Object.fromEntries(Object.entries(els).map(([k,v])=>[k,v.innerHTML||v.textContent]))));
"""


def lancer_page(tmp_path, bilan, langue="fr"):
    html = tmp_path / f"page.{langue}.html"
    bt.ecrire_html(bilan, html, langue)
    stub = tmp_path / "stub.js"
    stub.write_text(STUB_NODE, encoding="utf-8")
    resultat = subprocess.run(["node", str(stub), str(html)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert resultat.returncode == 0, resultat.stderr
    return json.loads(resultat.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_page_sections_04_a_07_executees_sous_node(tmp_path):
    racine = monde(tmp_path / "projects", "A")
    config = config_portfolio(tmp_path, proprietaire=None)
    (tmp_path / "cfg.json").write_text(json.dumps({"portfolio": config["portfolio"]}), encoding="utf-8")
    out = tmp_path / "out"
    assert bt.commande_collecte(options(racine, out, detail=True, config=tmp_path / "cfg.json")) == 0
    bilan = json.loads((out / "2026-10-pc.json").read_text(encoding="utf-8"))
    bilan["detail"]["projets"][0]["nom"] = "<img src=x onerror=1>"
    bilan["detail"]["recos"][0]["titre"] = "<b>titre</b>"
    sortie = lancer_page(tmp_path, bilan)
    assert "&lt;img src=x onerror=1&gt;" in sortie["tbl-projets"] and "<img src=x" not in sortie["tbl-projets"]
    assert "&lt;b&gt;titre&lt;/b&gt;" in sortie["liste-recos"] and "<h3><b>titre" not in sortie["liste-recos"]
    assert "Gain" in sortie["liste-recos"]
    assert sortie["titre-projets"] == "Ce qu'a consommé chaque projet du portfolio"
    assert "Portfolio IA" in sortie["tbl-projets"] and "État" in sortie["tbl-projets"]
    assert "legende-etapes" in sortie and "Développement" in sortie["legende-etapes"]
    assert "Édition en session principale" not in sortie["liste-etapes"]  # repliée
    assert "Orchestrateur" in sortie["tbl-roles"] and "agent-cost-kit:dev-story" in sortie["tbl-roles"]
    assert "Orchestrateur (session principale)" in sortie["duo"]
    assert "Projets" in sortie["nav-links"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_page_sans_portfolio_ni_detail(tmp_path):
    racine = monde(tmp_path / "projects", "A")
    out = tmp_path / "out"
    bt.commande_collecte(options(racine, out, detail=True))
    avec = json.loads((out / "2026-10-pc.json").read_text(encoding="utf-8"))
    sortie = lancer_page(tmp_path, avec)
    assert sortie["titre-projets"] == "Ce qu'a consommé chaque dépôt"
    assert "État" not in sortie["tbl-projets"] and "Hors portfolio" not in sortie["tbl-projets"] and "depot-a" in sortie["tbl-projets"]
    sans = {k: v for k, v in avec.items() if k != "detail"}
    sortie = lancer_page(tmp_path, sans)
    assert "tbl-projets" not in sortie and "liste-recos" not in sortie and "nav-links" not in sortie
    assert "detail-mount" not in sortie


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
@pytest.mark.parametrize("langue", ["en", "de"])
def test_page_traduite_executee_sous_node(tmp_path, langue):
    """Page anglaise ou allemande : libellés et recommandations traduits, plus aucun texte français affiché."""
    racine = monde(tmp_path / "projects", "A")
    config = config_portfolio(tmp_path, proprietaire=None)
    (tmp_path / "cfg.json").write_text(json.dumps({"portfolio": config["portfolio"]}), encoding="utf-8")
    out = tmp_path / "out"
    assert bt.commande_collecte(options(racine, out, detail=True, config=tmp_path / "cfg.json")) == 0
    bilan = json.loads((out / "2026-10-pc.json").read_text(encoding="utf-8"))
    sortie = lancer_page(tmp_path, bilan, langue)
    assert i18n.LIBELLES[langue]["Orchestrateur (session principale)"] in sortie["duo"]
    titres = {textes[langue]["titre"] for textes in i18n.RECOS.values()}
    assert bilan["detail"]["recos"] and all(t in titres for t in re.findall(r"<h3>(.*?)</h3>", sortie["liste-recos"]))
    autorises = tuple(i18n.lire_catalogue(langue).get("autorises", []))
    restes = i18n.francais_restant("\n".join(str(v) for v in sortie.values()), autorises)
    assert restes == []
    assert "Orchestrateur (session principale)" in (out / "2026-10-pc.json").read_text(encoding="utf-8")  # le JSON reste en français


def test_recos_traduites_memes_ids_et_gains():
    appels, infos = groupe(*flotte("g", "general-purpose", 5, modele=OPUS, lu=5_000_000, desc="T1 Implement story"),
                           *flotte("d", "dev-story", 5, lu=200_000),
                           [[appel(mid="v", modele="claude-sonnet-5", lu=3_000_000, ts="2026-10-02T12:00:00Z")], {}])
    detail = construire(appels, infos)
    fr = detail["recos"]
    for langue in ("en", "de"):
        traduites = bd.recommandations(detail["brut"], detail, langue)
        assert [(r["id"], r["gain"]) for r in traduites] == [(r["id"], r["gain"]) for r in fr]
        assert all(r["titre"] == i18n.RECOS[r["id"]][langue]["titre"] for r in traduites)
    anglais = {r["id"]: r for r in bd.recommandations(detail["brut"], detail, "en")}
    assert "5 general-purpose sub-agents" in anglais["implementation-generaliste"]["mesure"]
    assert "$" in anglais["implementation-generaliste"]["mesure"] and "\u00a0$" not in anglais["implementation-generaliste"]["mesure"]

