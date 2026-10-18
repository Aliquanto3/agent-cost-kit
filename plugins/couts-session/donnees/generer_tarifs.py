"""Génère hooks/tarifs.ts depuis tarifs.json, ou vérifie qu'il est à jour.

Le moteur des mods ne charge que des modules .ts/.js : le JSON y est donc recopié tel quel dans
un module TypeScript généré. ``--verifier`` sort en 1 si le module diffère du JSON. Le JSON est la seule
source des prix et des coefficients : scripts/mesurer_couts.py le lit directement.

Usage : python plugins/couts-session/donnees/generer_tarifs.py [--verifier]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
JSON = DOSSIER / "tarifs.json"
MODULE = DOSSIER.parent / "hooks" / "tarifs.ts"


def module(donnees: dict) -> str:
    corps = json.dumps(donnees, ensure_ascii=False, indent=2)
    return (
        "// Généré par donnees/generer_tarifs.py depuis donnees/tarifs.json : ne pas modifier à la main.\n"
        f"export const TARIFS = {corps} as const\n"
    )


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
    for erreur in erreurs:
        print(erreur)
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
