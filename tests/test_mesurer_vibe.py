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
    # entree = input_tokens (hors cache), lu = cached, ecrit = cache_write, sortie = output + reasoning
    assert (a["entree"], a["lu"], a["ecrit_5m"], a["ecrit_1h"]) == (1000, 100, 0, 0)
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
    attendu = (3000 * 0.70 + 300 * 0.07 + 160 * 2.10) / 1e6  # entree + lecture + sortie(reasoning inclus)
    assert c["cout"] == pytest.approx(attendu, rel=1e-9)
