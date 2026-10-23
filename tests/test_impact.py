"""Impact environnemental de mesurer_couts.py : méthodes ecologits (sortie seule) et impactia (entrée comptée)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import mesurer_couts as mc

# Valeurs de la version 0.8.0 (sortie seule), mix USA : (modèle, sortie, énergie Wh min-max, GWP gCO2e min-max).
ANCIENS = [
    ("claude-opus-5-5", 1000, (4.778044014590133, 9.792504712723275), (2.289455745431124, 4.676421444182033)),
    ("claude-sonnet-5-5", 2500, (4.165020787724337, 7.076478495470172), (1.9858911460610258, 3.365680617542787)),
    ("claude-haiku-5-5", 10000, (0.8318457433960033, 2.316363904172596), (0.3949932610345876, 1.096090987578126)),
    ("modele-inconnu", 100, (0.46722371328039874, 0.9792504712723276), (0.22381818799251016, 0.4676421444182033)),
]


@pytest.mark.parametrize(("modele", "sortie", "energie", "gwp"), ANCIENS)
def test_ecologits_identique_a_la_version_precedente(modele, sortie, energie, gwp):
    i = mc.impact(modele, sortie, methode="ecologits", entree=50_000, lu=900_000, appels=7)
    assert (i["energie_wh"]["min"], i["energie_wh"]["max"]) == pytest.approx(energie, rel=1e-12)
    assert (i["gwp_gco2e"]["min"], i["gwp_gco2e"]["max"]) == pytest.approx(gwp, rel=1e-12)


def test_methode_par_defaut_impactia():
    assert mc.METHODE_DEFAUT == "impactia"
    assert mc.impact("claude-opus-5-5", 100, entree=10_000) == mc.impact("claude-opus-5-5", 100, entree=10_000, methode="impactia")
    with pytest.raises(ValueError):
        mc.impact("claude-opus-5-5", 100, methode="autre")


@pytest.mark.parametrize("modele", ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"])
def test_impactia_monotone_en_tokens_d_entree(modele):
    precedent = None
    for entree in (0, 1_000, 10_000, 100_000, 500_000):
        i = mc.impact(modele, 500, entree=entree, appels=1)
        if precedent:
            for g in mc.GRANDEURS:
                for b in ("min", "max"):
                    assert i[g][b] > precedent[g][b]
        precedent = i
    eco = mc.impact(modele, 500, methode="ecologits")
    for g in mc.GRANDEURS:
        assert precedent[g]["max"] > eco[g]["max"]


def test_lecture_du_cache_zero_en_borne_basse_complete_en_borne_haute():
    sans = mc.impact("claude-opus-5-5", 2000, entree=1_000, appels=1)
    lu = mc.impact("claude-opus-5-5", 2000, entree=1_000, lu=200_000, appels=1)
    comme_entree = mc.impact("claude-opus-5-5", 2000, entree=201_000, appels=1)
    for g in mc.GRANDEURS:
        assert lu[g]["min"] == sans[g]["min"]
        assert lu[g]["max"] == pytest.approx(comme_entree[g]["max"], rel=1e-12)
        assert lu[g]["max"] > sans[g]["max"]


def test_prefill_reprend_la_formule_de_la_pr():
    # Sans sortie, la durée est le prefill seul : coef x (TTFT / 0,44) x N + 17,88 ms par appel.
    ttft = mc.ttft("claude-opus-5-5")
    assert ttft == 2.68
    duree = 0.062e-3 * ttft / 0.44 * 100_000 + 17.88e-3
    i = mc.impact("claude-opus-5-5", 0, entree=100_000, appels=1)
    gpus = 32  # 670 Md x 2 octets x 1,2 / 80 Go -> 21 -> puissance de 2
    attendu = mc.PUE[0] * duree / 3600 * (1200 + 161.082) * gpus / 8 / 64
    assert i["energie_wh"]["min"] == pytest.approx(attendu, rel=1e-12)


def test_ttft_repli_par_famille():
    assert mc.ttft("claude-sonnet-5-5-20261001") == 2.21
    assert mc.ttft("claude-opus-4-1") == mc.TTFT_FAMILLE["opus"]
    assert mc.ttft("modele-inconnu") == mc.TTFT_FAMILLE[mc.FAMILLE_PAR_DEFAUT]


def test_impact_appels_compte_entree_ecriture_lecture_et_appels():
    base = {"modele": "claude-sonnet-5-5", "sortie": 300, "entree": 10, "ecrit_5m": 2_000, "ecrit_1h": 1_000, "lu": 40_000}
    total = mc.impact_appels([base, base], mc.MIX_DEFAUT)
    attendu = mc.impact("claude-sonnet-5-5", 600, entree=6_020, lu=80_000, appels=2)
    assert total["gwp_gco2e"]["max"] == pytest.approx(attendu["gwp_gco2e"]["max"], rel=1e-12)
    eco = mc.impact_appels([base, base], mc.MIX_DEFAUT, "ecologits")
    assert eco["gwp_gco2e"] == mc.impact("claude-sonnet-5-5", 600, methode="ecologits")["gwp_gco2e"]
