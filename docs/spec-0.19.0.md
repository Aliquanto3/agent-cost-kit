---
title: "agent-cost-kit 0.19.0 : bilan des tokens en français, anglais et allemand"
status: done
date: 2026-11-06
source: "page du bilan d'octobre 2026 traduite à la main en anglais et en allemand ; ce lot porte la génération trilingue dans le kit"
---

# agent-cost-kit 0.19.0 : bilan des tokens en français, anglais et allemand

Une story, branche `feat/0.17-bilan-trilingue` (nom historique : le lot était d'abord prévu en 0.17, puis renuméroté en 0.19.0 après la fusion de `master` 0.18.2). La page du bilan d'octobre 2026 a été partagée hors de l'équipe française : il a fallu la traduire à la main en anglais et en allemand, et fixer la barre de navigation en haut de l'écran. Ce lot rend la génération trilingue, pour que les bilans suivants sortent directement dans les trois langues.

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

## Revue

### Passe 1 (2026-11-06, SHA revu b1bc9da)

- Fusion de `master` 0.18.2 vérifiée sur `gabarit.html` et `bilan_tokens.py` : toutes les lignes ajoutées des deux côtés sont présentes, sauf celles remplacées à dessein (barre `sticky` devenue `fixed`, signature `ecrire_html` réunissant `langue` et `gabarit`, jetons `--ws-*` du sélecteur repris en `--c-*`). Aucun jeton `--ws-*` restant.
- Important · medium · second avis · corrigé : gabarit personnalisé, seule la page française écrite, sans test ni documentation. Test `test_gabarit_de_remplacement_page_francaise_seule`, paragraphe dans « Page à votre propre charte », CHANGELOG.
- Important · low · second avis · corrigé : un catalogue obsolète arrêtait après l'écriture du JSON et de la page française. Les pages sont construites (`page_html`) avant toute écriture ; test `test_catalogue_obsolete_arrete_avant_toute_sortie`.
- Nit · low · second avis · rejeté : `_MOTS_AUSSI` retire « des » pour l'allemand seulement, et « des » est bien un article allemand (génitif) : la règle est déjà limitée à la langue où le mot existe.
- Nit · low · second avis · corrigé : nom de branche `feat/0.17-…` présenté comme historique.
- Nit · low · second avis · corrigé : `subprocess.run(..., encoding="utf-8")` dans `test_bilan_i18n.py`.
- Nit · low · revue · reporté : avec un gabarit personnalisé, les `.en.html` et `.de.html` d'une génération précédente restent sur le disque (documenté).
- Pre-existing · low · revue : sous ~500 px, le contenu de la page déborde à droite (même rendu avec le gabarit de `master`) ; Edge headless impose une largeur minimale, à revérifier sur un vrai mobile.
- Complexité : 0 constat.
