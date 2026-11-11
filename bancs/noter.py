"""Dépouille un dossier de résultats de banc_relecteur.sh : coût par étape et fiches restantes par relecteur.

Usage : uv run --no-project python bancs/noter.py <dossier>/resultats [--detail]

Lit les sorties JSON de `claude -p` (dev-*, avis-*, revue-*, verif-*). Une fiche compte comme échappée
quand le vérificateur la dit PRESENT après la revue. Les fiches non validées dans verite-terrain.json sont
comptées à part : un taux publié ne porte que sur les fiches validées.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ETATS = ("PRESENT", "ABSENT", "SANS_OBJET")
NOM = re.compile(r"^(dev|avis|revue|verif)-(.+?)-e(\d+)(?:-(.+)-(low|medium|high|xhigh|max))?$")


def charger(chemin: Path) -> dict | None:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def lignes_verif(texte: str) -> dict[str, str]:
    """`f01 | PRESENT | fichier:ligne | preuve` -> {"f01": "PRESENT"}."""
    etats: dict[str, str] = {}
    for ligne in texte.splitlines():
        champs = [c.strip(" `*") for c in ligne.strip(" -*").split("|")]
        if len(champs) >= 2 and re.fullmatch(r"f\d+", champs[0].lower()) and champs[1].upper() in ETATS:
            etats[champs[0].lower()] = champs[1].upper()
    return etats


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    dossier = Path(argv[0])
    detail = "--detail" in argv
    terrain = charger(Path(__file__).with_name("verite-terrain.json")) or {"fiches": []}
    validees = {f["id"] for f in terrain["fiches"] if f.get("validation")}

    couts: dict[tuple[str, str], list[float]] = defaultdict(list)
    fiches: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    erreurs: list[str] = []
    for chemin in sorted(dossier.glob("*.json")):
        m = NOM.match(chemin.stem)
        if not m:
            continue
        etape, story, essai, modele, effort = m.groups()
        donnees = charger(chemin)
        if donnees is None or donnees.get("is_error"):
            erreurs.append(chemin.name)
            continue
        config = f"{modele}:{effort}" if modele else "-"
        couts[(etape, config)].append(donnees.get("total_cost_usd") or 0.0)
        if etape == "verif":
            etats = lignes_verif(donnees.get("result") or "")
            fiches[(story, config)].append(etats)
            if detail:
                print(f"{story} e{essai} {config} : {etats}")

    print("étape | relecteur | sessions | coût moyen $ | coût total $")
    for (etape, config), valeurs in sorted(couts.items()):
        print(f"{etape} | {config} | {len(valeurs)} | {sum(valeurs) / len(valeurs):.2f} | {sum(valeurs):.2f}")
    print(f"total : {sum(sum(v) for v in couts.values()):.2f} $")

    print("\nstory | relecteur | fiche | présente après revue (essais) | validée")
    bilan: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for (story, config), essais in sorted(fiches.items()):
        for fiche in sorted({f for e in essais for f in e}):
            applicables = [e[fiche] for e in essais if e.get(fiche) in ("PRESENT", "ABSENT")]
            presentes = applicables.count("PRESENT")
            print(f"{story} | {config} | {fiche} | {presentes} sur {len(applicables)} | {'oui' if fiche in validees else 'non'}")
            bilan[config][0] += presentes
            bilan[config][1] += len(applicables)
    for config, (presentes, total) in sorted(bilan.items()):
        print(f"BILAN {config} : {presentes} fiche(s) présente(s) sur {total} cas applicables")
    if erreurs:
        print("\nSessions en erreur ou illisibles :", ", ".join(erreurs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
