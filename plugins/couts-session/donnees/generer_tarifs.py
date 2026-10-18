"""Génère hooks/tarifs.ts depuis tarifs.json, ou vérifie qu'il est à jour.

Le moteur des mods ne charge que des modules .ts/.js : le JSON y est donc recopié tel quel dans
un module TypeScript généré. ``--verifier`` sort en 1 si le module diffère du JSON, ou si le JSON
diffère des constantes de scripts/mesurer_couts.py (tant que ce script garde les siennes).

Usage : python plugins/couts-session/donnees/generer_tarifs.py [--verifier]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
JSON = DOSSIER / "tarifs.json"
MODULE = DOSSIER.parent / "hooks" / "tarifs.ts"
SCRIPT = DOSSIER.parents[2] / "scripts" / "mesurer_couts.py"


def module(donnees: dict) -> str:
    corps = json.dumps(donnees, ensure_ascii=False, indent=2)
    return (
        "// Généré par donnees/generer_tarifs.py depuis donnees/tarifs.json : ne pas modifier à la main.\n"
        f"export const TARIFS = {corps} as const\n"
    )


def ecarts_script(donnees: dict) -> list[str]:
    """Compare le JSON aux constantes de mesurer_couts.py ; liste vide si le script est absent."""
    if not SCRIPT.exists():
        return []
    sys.path.insert(0, str(SCRIPT.parent))
    import mesurer_couts as m

    prix, eco = donnees["prix"], donnees["ecologits"]
    attendu = {
        "PRIX": {
            f["nom"]: (f["entree"], f["sortie"], f["lecture"]) for f in prix["familles"]
        },
        "ordre PRIX": [f["nom"] for f in prix["familles"]],
        "ECRITURE": prix["ecriture_cache"],
        "HAIKU_SEUIL_LONG": prix["haiku_long_contexte"]["seuil_tokens"],
        "HAIKU_FACTEUR_LONG": prix["haiku_long_contexte"]["facteur"],
        "PARAMETRES": {k: tuple(v) for k, v in eco["parametres"].items()},
        "PARAMETRES_FAMILLE": {
            k: tuple(v) for k, v in eco["parametres_famille"].items()
        },
        "LOT": eco["lot"],
        "GPU_ENERGIE": tuple(eco["gpu_energie_wh_par_token"]),
        "GPU_LATENCE": tuple(eco["gpu_latence_s_par_token"]),
        "GPU_MEMOIRE_GO": eco["gpu_memoire_go"],
        "SERVEUR_PUISSANCE_W": eco["serveur_puissance_w"],
        "SERVEUR_GPUS": eco["serveur_gpus"],
        "DUREE_VIE_S": eco["duree_vie_s"],
        "FAB_SERVEUR": tuple(eco["fabrication_serveur"].values()),
        "FAB_GPU": tuple(eco["fabrication_gpu"].values()),
        "PUE": tuple(eco["pue"]),
        "WUE_SITE": tuple(eco["wue_site_l_par_kwh"]),
        "MIX": {k: tuple(v.values()) for k, v in eco["mix"].items()},
        "MIX_DEFAUT": eco["mix_par_defaut"],
    }
    reel = {nom: getattr(m, nom) for nom in attendu if nom != "ordre PRIX"}
    reel["ordre PRIX"] = list(m.PRIX)
    return [nom for nom, valeur in attendu.items() if reel[nom] != valeur]


def main() -> int:
    donnees = json.loads(JSON.read_text(encoding="utf-8"))
    texte = module(donnees)
    if "--verifier" not in sys.argv:
        MODULE.write_text(texte, encoding="utf-8", newline="\n")
        print(f"écrit : {MODULE}")
        return 0
    erreurs = []
    if not MODULE.exists() or MODULE.read_text(encoding="utf-8") != texte:
        erreurs.append("hooks/tarifs.ts n'est pas à jour : relancer sans --verifier")
    erreurs += [
        f"tarifs.json diffère de mesurer_couts.py : {nom}"
        for nom in ecarts_script(donnees)
    ]
    for erreur in erreurs:
        print(erreur)
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
