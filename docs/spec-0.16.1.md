---
title: "agent-cost-kit 0.16.1 : gabarit du bilan des tokens à la charte générique"
status: review
date: 2026-11-03
---

# agent-cost-kit 0.16.1 : gabarit du bilan des tokens à la charte générique

Le dépôt devient public sans charte de marque. Périmètre : le gabarit `skills/bilan-tokens/gabarit.html`, les textes qui le décrivent, et une surcharge facultative du gabarit. Aucun autre comportement ne change.

1. **Gabarit.** Jetons `--ws-*` remplacés par `--c-*` (fond, surface, texte, primaire bleu pétrole, accent orange, succès, alerte, erreur, focus, `sur-statut`). Les couleurs en dur passent par ces jetons. Les familles `--st-*` suivent la palette catégorielle. Polices système, plus de lien vers un CDN. Le logo devient un pictogramme SVG décoratif suivi du texte « Bilan des tokens ». Pas de thème sombre dans le gabarit.
2. **Surcharge.** Variable `AGENT_COST_KIT_GABARIT_BILAN` (chemin d'un `.html`) lue par `scripts/bilan_tokens.py` (`chemin_gabarit`). Absente : gabarit du plugin. Fichier introuvable ou sans point d'injection : arrêt avec message. Tests dans `tests/test_bilan_tokens.py`.
3. **Textes.** `SKILL.md`, `docs/bilan-tokens.md` (section « Page à votre propre charte »), `docs/impact-input-impactia.md` (chemin de poste retiré). Le motif `wavestone` est retiré de la classification des skills dans `scripts/bilan_detail.py`.
4. **Version.** 0.16.1 dans `.claude-plugin/plugin.json` (`plugins/couts-session` inchangé) et entrée de `CHANGELOG.md`.

Report : le gabarit n'a pas de thème sombre ; en ajouter un serait une évolution à part.
