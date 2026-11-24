"""Sessions Mistral Vibe dans mesurer_couts.py : lecture du journal, tarifs Mistral, garde-fou modèle inconnu."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import mesurer_couts as mc


def session_vibe(tmp_path: Path, modele: str = "mistral-large-4-0", records: list | None = None) -> Path:
    """Construit une fausse racine ~/.vibe/logs/session/unified avec une session et son journal."""
    racine = tmp_path / "unified"
    dossier = racine / "sess-0001"
    (dossier / "journal").mkdir(parents=True)
    (dossier / "meta.json").write_text(
        json.dumps(
            {
                "session_id": "sess-0001",
                "start_time": "2026-11-23T21:00:00+00:00",
                "title": "audit repos",
                "config": {"active_model": modele},
            }
        ),
        encoding="utf-8",
    )
    records = records or [
        {
            "sequence": 1,
            "payload": {
                "action_id": "a1",
                "ts": "2026-11-23T21:01:00+00:00",
                "result": {"usage": {"input_tokens": 1000, "cached_input_tokens": 100, "cache_write_tokens": 0, "output_tokens": 50, "reasoning_tokens": 10}},
            },
        },
        {
            "sequence": 2,
            "payload": {
                "action_id": "a2",
                "ts": "2026-11-23T21:02:00+00:00",
                "result": {"usage": {"input_tokens": 2000, "cached_input_tokens": 200, "cache_write_tokens": 0, "output_tokens": 80, "reasoning_tokens": 20}},
            },
        },
    ]
    (dossier / "journal" / "0000000000000001.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    return racine


def test_agents_vibe_une_ligne_main(tmp_path):
    agents = list(mc.agents_vibe(session_vibe(tmp_path)))
    assert len(agents) == 1
    session, ident, chemin, meta, liste = agents[0]
    assert ident == "MAIN"
    assert meta["agentType"] == "MAIN"
    assert "Vibe" in meta["description"] and "audit repos" in meta["description"]
    assert len(liste) == 2


def test_appels_vibe_champs_usage(tmp_path):
    liste = list(mc.agents_vibe(session_vibe(tmp_path)))[0][4]
    a = liste[0]
    # Mistral/Vibe : input_tokens INCLUT le cache -> entree = input - cached ; lu = cached ; sortie = output + reasoning
    assert (a["entree"], a["lu"], a["ecrit_5m"], a["ecrit_1h"]) == (900, 100, 0, 0)
    assert (a["sortie_declaree"], a["sortie"]) == (50, 60)
    assert a["modele"] == "mistral-large-4-0"
    assert a["fam"] == "mistral"


def test_prix_mistral():
    t = mc.prix("mistral-large-4-0")
    assert (t["entree"], t["sortie"], t["lecture"]) == (0.70, 2.10, 0.07)
    assert t["ecriture_cache"] == {"5m": 1.0, "1h": 1.0}
    assert mc.prix("zai-glm-5-3-flash-vibe-free")["entree"] == 0  # offre gratuite Vibe
    assert mc.prix("mistral-modele-pas-encore-la")["entree"] == 0.70  # repli famille mistral
    assert mc.prix("claude-opus-5-5")["entree"] == 4.0  # régression : Anthropic inchangé


def test_prix_inconnu_fait_echouer_la_mesure():
    with pytest.raises(SystemExit):
        mc.prix("modele-inconnu-xyz")


def test_session_vibe_modele_inconnu_fait_echouer(tmp_path):
    with pytest.raises(SystemExit):
        list(mc.agents_vibe(session_vibe(tmp_path, modele="modele-inconnu-xyz")))


def test_cout_session_vibe(tmp_path):
    liste = list(mc.agents_vibe(session_vibe(tmp_path)))[0][4]
    c = mc.couts(liste)
    # entree non cachée (3000 - 300) à 0,70 $ + cache lu 300 à 0,07 $ + sortie 160 (reasoning inclus) à 2,10 $
    attendu = ((3000 - 300) * 0.70 + 300 * 0.07 + 160 * 2.10) / 1e6
    assert c["cout"] == pytest.approx(attendu, rel=1e-9)


def test_bilan_collecter_bruts_vibe(tmp_path):
    import bilan_tokens as bt

    bruts = bt.collecter_bruts_vibe(session_vibe(tmp_path))
    assert len(bruts) == 2
    assert {a["modele"] for a in bruts} == {"mistral-large-4-0"}
    assert sum(a["entree"] for a in bruts) == 2700  # input_tokens (3000) moins le cache (300)


def _bilan_min(sources):
    return {
        "schema": 1, "machine": "pc", "mois": "2026-11", "dossier": None,
        "genere_le": "2026-11-23T00:00:00+00:00", "premier_appel": "2026-11-23T00:00:00Z",
        "dernier_appel": "2026-11-23T00:00:00Z", "mix": mc.MIX_DEFAUT, "methode": mc.METHODE_DEFAUT,
        "modeles": [], "prix": {}, "sources": sources,
    }


def test_page_html_label_vibe_seul():
    import bilan_tokens as bt

    page = bt.page_html(_bilan_min(["vibe"]), "fr")
    assert "Claude Code" not in page
    assert "Mistral Vibe" in page
    assert "~/.vibe/logs/session/unified" in page


def test_page_html_label_claude_code_par_defaut():
    import bilan_tokens as bt

    page = bt.page_html(_bilan_min(["claude-code"]), "fr")
    assert "Claude Code" in page  # comportement historique inchangé hors Vibe
