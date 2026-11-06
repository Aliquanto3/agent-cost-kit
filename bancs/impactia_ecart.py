"""Banc : la méthode impactia de scripts/mesurer_couts.py reproduit-elle la branche de la PR EcoLogits #259 ?

La PR (https://github.com/mlco2/ecologits/pull/259, branche mlco2/ecologits:feat/impactia) n'est pas
fusionnée : on installe la librairie à son SHA de tête, lu dans tarifs.json (section impactia).

    uv run --no-project --with "ecologits @ git+https://github.com/mlco2/ecologits@4c552f64a1770514525914e2bbebc6368104374f" python bancs/impactia_ecart.py

Pour chaque modèle (Opus, Sonnet, Haiku 5.5), contexte (10 k, 100 k, 500 k tokens d'entrée) et sortie
(100, 2 000 tokens), un appel unique, comparé grandeur par grandeur (min et max) :

- hors cache : script ``impact(entree=C, appels=1)`` contre librairie ``input_token_count=C`` ;
- lecture du cache, borne haute : script ``impact(lu=C, appels=1)["max"]`` contre librairie ``input_token_count=C`` ;
- lecture du cache, borne basse : script ``impact(lu=C, appels=1)["min"]`` contre librairie ``input_token_count=0``.

Mêmes entrées des deux côtés : paramètres, mix et TTFT du script (le ``models.json`` de la PR s'arrête à
Opus 4.8), ``tps=None`` (le script garde la latence de sortie ML.ENERGY, pas 1/TPS OpenRouter). La phase
d'entraînement de la PR, hors total, n'est pas comparée. Sort en erreur si un écart relatif dépasse 5 %.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from ecologits.impacts.llm import compute_llm_impacts
from ecologits.utils.range_value import RangeValue

chemin = Path(__file__).resolve().parent.parent / "scripts" / "mesurer_couts.py"
spec = importlib.util.spec_from_file_location("mesurer_couts", chemin)
script = importlib.util.module_from_spec(spec)
sys.modules["mesurer_couts"] = script
spec.loader.exec_module(script)

MODELES = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
CONTEXTES = [10_000, 100_000, 500_000]
SORTIES = [100, 2_000]
GRANDEURS = {  # nom du script : (attribut librairie, facteur d'unité)
    "energie_wh": ("energy", 1000),
    "gwp_gco2e": ("gwp", 1000),
    "eau_l": ("wcf", 1),
    "pe_mj": ("pe", 1),
    "adpe_mgsbe": ("adpe", 1e6),
}
SEUIL = 0.05


def borne(valeur, nom):
    return getattr(valeur, nom) if isinstance(valeur, RangeValue) else valeur


def librairie(modele: str, sortie: int, entree: int) -> dict[str, tuple[float, float]]:
    t_min, t_max, a_min, a_max = script.parametres(modele)
    gwp, pe, adpe, wue = script.MIX[script.MIX_DEFAUT]
    res = compute_llm_impacts(
        model_active_parameter_count=RangeValue(min=a_min, max=a_max) if a_min != a_max else a_min,
        model_total_parameter_count=RangeValue(min=t_min, max=t_max) if t_min != t_max else t_min,
        output_token_count=sortie,
        input_token_count=entree,
        ttft=script.ttft(modele),
        tps=None,
        if_electricity_mix_adpe=adpe,
        if_electricity_mix_pe=pe,
        if_electricity_mix_gwp=gwp,
        if_electricity_mix_wue=wue,
        datacenter_pue=RangeValue(min=script.PUE[0], max=script.PUE[1]),
        datacenter_wue=RangeValue(min=script.WUE_SITE[0], max=script.WUE_SITE[1]),
    )
    sortie_lib = {}
    for nom, (attribut, facteur) in GRANDEURS.items():
        v = getattr(res, attribut).value
        sortie_lib[nom] = (borne(v, "min") * facteur, borne(v, "max") * facteur)
    return sortie_lib


def ecart(a: float, b: float) -> float:
    return abs(a - b) / abs(b) if b else abs(a)


pire = {"hors cache": 0.0, "lecture max": 0.0, "lecture min": 0.0}
print(f"{'modèle':18} {'contexte':>8} {'sortie':>6} {'cas':12} {'gwp script min-max':>24} {'gwp PR min-max':>24} {'écart max':>9}")
for modele in MODELES:
    for contexte in CONTEXTES:
        for sortie in SORTIES:
            frais = script.impact(modele, sortie, entree=contexte, appels=1, methode="impactia")
            lu = script.impact(modele, sortie, lu=contexte, appels=1, methode="impactia")
            pr = librairie(modele, sortie, contexte)
            pr_zero = librairie(modele, sortie, 0)
            cas = {
                "hors cache": {g: ((frais[g]["min"], frais[g]["max"]), pr[g]) for g in GRANDEURS},
                "lecture max": {g: ((lu[g]["max"],), (pr[g][1],)) for g in GRANDEURS},
                "lecture min": {g: ((lu[g]["min"],), (pr_zero[g][0],)) for g in GRANDEURS},
            }
            for nom, valeurs in cas.items():
                e = max(ecart(m, r) for mien, ref in valeurs.values() for m, r in zip(mien, ref))
                pire[nom] = max(pire[nom], e)
                mien, ref = valeurs["gwp_gco2e"]
                print(
                    f"{modele:18} {contexte:8d} {sortie:6d} {nom:12} "
                    f"{'-'.join(f'{x:.4g}' for x in mien):>24} {'-'.join(f'{x:.4g}' for x in ref):>24} {e:9.2e}"
                )
print("\nÉcart relatif maximal : " + ", ".join(f"{k} {v:.2e}" for k, v in pire.items()))
raise SystemExit(0 if max(pire.values()) < SEUIL else 1)
