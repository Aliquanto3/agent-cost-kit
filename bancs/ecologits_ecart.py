"""Banc : le calcul d'impact de scripts/mesurer_couts.py reproduit-il la librairie EcoLogits ?

Compare, pour chaque modèle et pour 1 000 et 100 000 tokens de sortie, l'énergie, le GWP,
l'eau, l'énergie primaire et l'ADPe (min et max) calculés par le script et par ``ecologits``.
Gratuit, aucun appel réseau (la librairie est téléchargée par uv).

    uv run --with ecologits python bancs/ecologits_ecart.py

Sort en erreur si un écart relatif dépasse 1e-6.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from ecologits.electricity_mix_repository import electricity_mixes
from ecologits.impacts.llm import compute_llm_impacts
from ecologits.utils.range_value import RangeValue

chemin = Path(__file__).resolve().parent.parent / "scripts" / "mesurer_couts.py"
spec = importlib.util.spec_from_file_location("mesurer_couts", chemin)
script = importlib.util.module_from_spec(spec)
sys.modules["mesurer_couts"] = script
spec.loader.exec_module(script)

MODELES = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"]
GRANDEURS = {  # nom du script : (attribut librairie, facteur d'unité)
    "energie_wh": ("energy", 1000),
    "gwp_gco2e": ("gwp", 1000),
    "eau_l": ("wcf", 1),
    "pe_mj": ("pe", 1),
    "adpe_mgsbe": ("adpe", 1e6),
}


def borne(valeur, nom):
    return getattr(valeur, nom) if isinstance(valeur, RangeValue) else valeur


pire = 0.0
print(f"{'modèle':18} {'tokens':>8} {'grandeur':11} {'script min-max':>26} {'librairie min-max':>26} {'écart rel.':>10}")
for modele in MODELES:
    t_min, t_max, a_min, a_max = script.parametres(modele)
    for sortie in (1_000, 100_000):
        mien = script.impact(modele, sortie, "USA")
        mix = electricity_mixes.find_electricity_mix("USA")
        lib = compute_llm_impacts(
            model_active_parameter_count=RangeValue(min=a_min, max=a_max) if a_min != a_max else a_min,
            model_total_parameter_count=RangeValue(min=t_min, max=t_max) if t_min != t_max else t_min,
            output_token_count=sortie,
            if_electricity_mix_adpe=mix.adpe,
            if_electricity_mix_pe=mix.pe,
            if_electricity_mix_gwp=mix.gwp,
            if_electricity_mix_wue=mix.wue,
            datacenter_pue=RangeValue(min=script.PUE[0], max=script.PUE[1]),
            datacenter_wue=RangeValue(min=script.WUE_SITE[0], max=script.WUE_SITE[1]),
        )
        for nom, (attribut, facteur) in GRANDEURS.items():
            valeur = getattr(lib, attribut).value
            ref = (borne(valeur, "min") * facteur, borne(valeur, "max") * facteur)
            m = (mien[nom]["min"], mien[nom]["max"])
            ecart = max(abs(m[i] - ref[i]) / abs(ref[i]) for i in (0, 1) if ref[i])
            pire = max(pire, ecart)
            print(f"{modele:18} {sortie:8d} {nom:11} {m[0]:12.5g}-{m[1]:<12.5g} {ref[0]:12.5g}-{ref[1]:<12.5g} {ecart:10.2e}")
print(f"\nÉcart relatif maximal : {pire:.2e}")
raise SystemExit(0 if pire < 1e-6 else 1)
