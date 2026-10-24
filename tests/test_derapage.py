"""Alerte de dérapage de mesurer_couts.py : agents au-delà de 2 x la médiane d'appels de leur type."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import mesurer_couts as mc


def ligne(type_, appels, cout=1.0):
    return {"type": type_, "appels": appels, "cout_usd": cout}


def test_depassement_de_deux_fois_la_mediane():
    lignes = [ligne("agent-cost-kit:dev-story", n) for n in (10, 12, 14, 30)] + [ligne("agent-cost-kit:dev-story", 40, 5.0)]
    # médiane 14, seuil 28 : 30 et 40 dépassent
    d = mc.derapages(lignes)
    assert [l["appels"] for l in d] == [40, 30] or [l["appels"] for l in d] == [30, 40]
    assert all(l["mediane"] == 14 and l["seuil"] == 28 for l in d)
    assert d[0]["cout_usd"] == 5.0  # tri par coût décroissant


def test_seuil_exclu_et_types_separes():
    lignes = [ligne("dev-story", 10), ligne("dev-story", 20), ligne("dev-story", 10)]  # médiane 10, 20 = seuil, pas un dépassement
    lignes += [ligne("reviewer", 5), ligne("reviewer", 5), ligne("reviewer", 50), ligne("lookup", 500)]
    d = mc.derapages(lignes)
    assert [(l["type"], l["appels"]) for l in d] == [("reviewer", 50)]


def test_sans_agent_du_type():
    assert mc.derapages([ligne("MAIN", 900)]) == []
