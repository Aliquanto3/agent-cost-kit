"""Alerte de dérapage de mesurer_couts.py : agents au-delà de 2 x la médiane d'appels de leur type."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import mesurer_couts as mc


def ligne(type_, appels, cout=1.0, description="story"):
    return {"type": type_, "appels": appels, "cout_usd": cout, "session": "abcd1234", "agent": "ef567890", "description": description}


def test_depassement_de_deux_fois_la_mediane():
    lignes = [ligne("agent-cost-kit:dev-story", n) for n in (10, 12, 14, 30)] + [ligne("agent-cost-kit:dev-story", 40, 5.0)]
    # médiane 14, seuil 28 : 30 et 40 dépassent
    d = mc.derapages(lignes)
    assert [l["appels"] for l in d] == [40, 30]  # tri par coût décroissant (5,0 $ puis 1,0 $)
    assert all(l["type"] == "dev-story" and l["mediane"] == 14 and l["seuil"] == 28 for l in d)


def test_seuil_exclu_et_types_separes():
    lignes = [ligne("dev-story", 10), ligne("dev-story", 20), ligne("dev-story", 10)]  # médiane 10, 20 = seuil, pas un dépassement
    lignes += [ligne("reviewer", 5), ligne("reviewer", 5), ligne("reviewer", 50), ligne("lookup", 500)]
    d = mc.derapages(lignes)
    assert [(l["type"], l["appels"]) for l in d] == [("reviewer", 50)]


def test_sans_agent_du_type():
    assert mc.derapages([ligne("MAIN", 900)]) == []


def test_section_rendue_dans_resume():
    lignes = [ligne("dev-story", n) for n in (10, 10, 10)] + [ligne("dev-story", 25, 3.456, "corrige | le\nparseur")]
    s = mc.section_derapage(lignes)
    assert s[1] == "## Alerte de dérapage (plus de 2 x la médiane d'appels du même type)"
    assert s[-1] == r"| dev-story | abcd1234 | ef567890 | 25 | 10 | 3.46 $ | corrige \| le parseur |"


def test_aucun_derapage_pas_de_section():
    assert mc.section_derapage([ligne("dev-story", n) for n in (10, 12, 14)]) == []
    assert mc.section_derapage([]) == []
