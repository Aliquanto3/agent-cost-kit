---
title: "agent-cost-kit 0.16.1 : gabarit du bilan des tokens à la charte générique"
status: review
date: 2026-11-03
---

# agent-cost-kit 0.16.1 : gabarit du bilan des tokens à la charte générique

Le dépôt devient public sans charte de marque. Périmètre : le gabarit `skills/bilan-tokens/gabarit.html`, les textes qui le décrivent, et une surcharge facultative du gabarit. Aucun autre comportement ne change.

1. **Gabarit.** Jetons `--ws-*` remplacés par `--c-*` (fond, surface, texte, primaire bleu pétrole, accent orange, succès, alerte, erreur, focus, `sur-statut`). Les couleurs en dur passent par ces jetons. Les familles `--st-*` suivent la palette catégorielle. Polices système, plus de lien vers un CDN. Le logo devient un pictogramme SVG décoratif suivi du texte « Bilan des tokens ». Pas de thème sombre dans le gabarit.
2. **Surcharge.** Variable `AGENT_COST_KIT_GABARIT_BILAN` (chemin d'un `.html`) lue par `scripts/bilan_tokens.py` (`chemin_gabarit`). Absente : gabarit du plugin. `~` développé, chemin relatif résolu depuis le dossier courant. Fichier introuvable, dossier, fichier non UTF-8 ou sans point d'injection : arrêt avec message, avant toute écriture. Tests dans `tests/test_bilan_tokens.py`.
3. **Textes.** `SKILL.md`, `docs/bilan-tokens.md` (section « Page à votre propre charte »), `docs/impact-input-impactia.md` (chemin de poste retiré). Le nom de l'ancienne charte est retiré des motifs de classification des skills dans `scripts/bilan_detail.py` ; les skills de pages web (suffixe `-web` sauf `aidd-web`, `site-web`, `landing`, `webdesign`) restent classés en « contenus ».
4. **Version.** 0.16.1 dans `.claude-plugin/plugin.json` (`plugins/couts-session` inchangé) et entrée de `CHANGELOG.md`.

Report : le gabarit n'a pas de thème sombre ; en ajouter un serait une évolution à part.

## Revue

### Passe 1 (2026-11-03, SHA revu 0689d34)

- Important · medium · second avis · corrigé · `wavestone-web` ne tombait plus en « contenus » : motif générique `site-web|landing|webdesign|(?<!aidd)-web$` ; `web-search`, `webapp`, `aidd-web` non captés (test paramétré dans `tests/test_bilan_detail.py`).
- Nit · low · second avis · corrigé · `var(--c-…)` dans des attributs de présentation SVG (`fill`, `stroke`), ignoré par certains navigateurs : passage par `style=` (logo et anneau du coût).
- Nit · low · second avis · corrigé · chemins de poste dans `docs/spec-0.13.0.md` et `docs/spec-0.16.0.md`.
- Nit · low · second avis · corrigé · mot de marque dans cette spec, remplacé par « ancienne charte ».
- Important · low · second avis · corrigé · gabarit lu et validé après l'écriture du JSON (sortie partielle) : `lire_gabarit()` appelée en tête de `ecrire_bilan` ; dossier et fichier non UTF-8 ont un message clair ; test sans sortie créée.
- Nit · low · second avis · corrigé · résolution d'un chemin relatif (dossier courant) documentée, test de `~` et du chemin relatif.
- Nit · low · second avis · corrigé · teintes `HUES` d'Opus (262) et Fable (265) proches de l'ancien violet : 205 et 0, hors 240-290°, distinctes des autres familles.
- Nit · low · second avis · corrigé · tranche « Input non caché » à 2,17:1 : `--c-cat-8` #9A7400 (4,31:1 sur la surface). `st-libre` écarté : il désigne l'espace sans étape, pas une donnée à lire.
- Nit · low · second avis · corrigé · `docs/bilan-tokens.md` explique comment garder la charte Wavestone (copie privée `agent-cost-kit-wavestone`, copie hors du plugin, variable, point d'injection à garder).
- Important · low · second avis · corrigé · une variable `AGENT_COST_KIT_GABARIT_BILAN` posée sur le poste faisait échouer les tests qui comparent au gabarit du plugin : fixture autouse `delenv` dans les deux fichiers de test ; test de cohérence du gabarit (aucun `--ws-`, chaque `var(--x)` défini, point d'injection unique, pas de `var()` en attribut SVG).
- Pre-existing · low · revue · noté · `ruff check` (configuration globale du poste, le dépôt n'en a pas et la CI ne le lance pas) signale ISC004, FURB167, RUF100 dans `scripts/` et `tests/`, hors périmètre.
