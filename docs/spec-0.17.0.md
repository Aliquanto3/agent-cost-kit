---
title: "agent-cost-kit 0.17.0 : bilan des tokens en français, anglais et allemand"
status: done
date: 2026-10-28
source: "page du bilan d'octobre 2026 traduite à la main en anglais et en allemand ; ce lot porte la génération trilingue dans le kit"
---

# agent-cost-kit 0.17.0 : bilan des tokens en français, anglais et allemand

Une story, branche `feat/0.17-bilan-trilingue`. La page du bilan d'octobre 2026 a été partagée hors de l'équipe française : il a fallu la traduire à la main en anglais et en allemand, et fixer la barre de navigation en haut de l'écran. Ce lot rend la génération trilingue, pour que les bilans suivants sortent directement dans les trois langues.

## Choix

- **Gabarit en français, catalogues par langue.** Le gabarit reste la seule source. Chaque langue a un catalogue de paires [texte français exact, traduction], appliquées du plus long au plus court. Écarté : un gabarit à clés `t('…')`, plus propre mais qui demande de réécrire tout le gabarit (54 Ko), pour un risque de régression visuelle.
- **Dérive détectée.** Une paire dont le texte a disparu du gabarit fait échouer la génération. Un test signale tout texte français restant visible dans une page traduite.
- **JSON inchangé.** Les libellés des données sont traduits sur une copie au moment d'écrire la page ; le JSON reste en français, donc la fusion de plusieurs PC ne change pas.
- **Recommandations rédigées par langue.** Elles portent des montants et des parts mis en forme : chaque langue a ses gabarits de phrases, les nombres suivent son format.
- **Liens par nom de fichier.** `<base>.html`, `<base>.en.html`, `<base>.de.html` : les liens du sélecteur marchent en local comme dans un Artifact multi-fichiers.

## Livrables

1. `scripts/bilan_i18n.py` (stdlib) : `traduire_page`, `traduire_donnees`, `libelle`, formats `nombre`, `dollars`, `part`, gabarits `RECOS`, contrôle `francais_restant`.
2. `skills/bilan-tokens/i18n/en.json` et `de.json`.
3. `gabarit.html` : doctype et `lang`, barre de navigation fixe, emplacement du sélecteur de langue (`<!--LANGUES-->`), section conservée au changement de langue.
4. `bilan_detail.py` : recommandations paramétrées par la langue, texte français inchangé.
5. `bilan_tokens.py` : une page par langue, option `--langues`.
6. Tests, `docs/bilan-tokens.md` (section « Langues »), `SKILL.md` (publication multi-fichiers).

## Critères d'acceptation

- Les tests existants passent sans changement de texte français, hors l'en-tête de la page (doctype).
- Pages anglaise et allemande exécutées sous Node : aucun texte français affiché, hors noms de skills et de fichiers déclarés dans `autorises`.
- Une phrase du gabarit modifiée sans son catalogue fait échouer la génération avec un message qui la cite.
