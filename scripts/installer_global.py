"""Partie globale du kit, une fois par PC : réglages utilisateur et consignes de coût.

Sans option, affiche ce qui changerait et n'écrit rien. Avec --appliquer, sauvegarde les fichiers
modifiés (suffixe .avant-cost-kit-AAAAMMJJ), puis :
- fusionne REGLAGES dans ~/.claude/settings.json, sans toucher aux autres clés (proxy, plugins...) ;
- insère ou remplace le bloc du kit entre ses marqueurs dans ~/.claude/CLAUDE.md, sans toucher
  au reste du fichier (les consignes personnelles se mettent hors des marqueurs).
Signale, sans les modifier, les réglages contraires au kit : effort par modèle, TTL d'une heure.

Usage : python installer_global.py [--appliquer] [--claude-dir CHEMIN]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

REGLAGES = {
    "syncClaudeAiSkills": False,
    "effortLevel": "medium",
    "env": {"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1"},
}
DEBUT, FIN = "<!-- agent-cost-kit:debut -->", "<!-- agent-cost-kit:fin -->"
MODELE = Path(__file__).resolve().parent.parent / "modeles" / "CLAUDE.global.md"


def fusionner(actuels: dict, cibles: dict, prefixe: str = "") -> list[str]:
    """Applique `cibles` sur `actuels` (en place) et rend la liste des changements."""
    changements = []
    for cle, valeur in cibles.items():
        if isinstance(valeur, dict):
            changements += fusionner(actuels.setdefault(cle, {}), valeur, f"{prefixe}{cle}.")
        elif actuels.get(cle) != valeur:
            changements.append(f"{prefixe}{cle} : {actuels.get(cle)!r} -> {valeur!r}")
            actuels[cle] = valeur
    return changements


def alertes(reglages: dict) -> list[str]:
    messages = []
    for modele, conf in reglages.get("modelSettings", {}).items():
        effort = conf.get("effortLevel")
        if effort not in (None, "low", "medium"):
            messages.append(
                f"modelSettings.{modele}.effortLevel = {effort!r} prime sur effortLevel pour ce modèle "
                "(les agents du kit sont mesurés en medium)."
            )
    if reglages.get("subagentPromptCacheTtl") == "1h":
        messages.append(
            "subagentPromptCacheTtl = '1h' : rentable seulement à partir d'environ une expiration "
            "par agent ; vérifier avec /agent-cost-kit:mesurer-couts avant de le garder."
        )
    return messages


def avec_bloc(texte: str) -> str:
    bloc = f"{DEBUT}\n{MODELE.read_text(encoding='utf-8').strip()}\n{FIN}"
    if DEBUT in texte and FIN in texte:
        avant, reste = texte.split(DEBUT, 1)
        return avant + bloc + reste.split(FIN, 1)[1]
    return (texte.rstrip() + "\n\n" if texte.strip() else "") + bloc + "\n"


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    analyseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analyseur.add_argument("--appliquer", action="store_true", help="écrire les changements (sinon simple aperçu)")
    analyseur.add_argument("--claude-dir", default="~/.claude", help="dossier de configuration de Claude Code")
    options = analyseur.parse_args()
    racine = Path(options.claude_dir).expanduser()

    chemin_reglages = racine / "settings.json"
    reglages = json.loads(chemin_reglages.read_text(encoding="utf-8-sig")) if chemin_reglages.exists() else {}
    changements = fusionner(reglages, REGLAGES)
    chemin_consignes = racine / "CLAUDE.md"
    consignes = chemin_consignes.read_text(encoding="utf-8-sig") if chemin_consignes.exists() else ""
    nouvelles_consignes = avec_bloc(consignes)

    print(f"{chemin_reglages} :")
    for ligne in changements or ["déjà conforme"]:
        print(f"  {ligne}")
    print(
        f"{chemin_consignes} : "
        + ("bloc du kit à jour" if nouvelles_consignes == consignes else "bloc du kit à écrire")
    )
    for message in alertes(reglages):
        print(f"Attention : {message}")
    if not options.appliquer:
        print("Aperçu seulement : rien n'est écrit. Relancer avec --appliquer.")
        return 0

    suffixe = f".avant-cost-kit-{date.today():%Y%m%d}"
    ecritures = [
        (chemin_reglages, json.dumps(reglages, indent=2, ensure_ascii=False) + "\n", bool(changements)),
        (chemin_consignes, nouvelles_consignes, nouvelles_consignes != consignes),
    ]
    for chemin, contenu, modifie in ecritures:
        if not modifie:
            continue
        if chemin.exists():
            shutil.copy2(chemin, chemin.with_name(chemin.name + suffixe))
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(contenu, encoding="utf-8")
        print(f"Écrit : {chemin}")
    print("Redémarrer Claude Code pour charger les réglages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
