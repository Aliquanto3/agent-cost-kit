---
title: "agent-cost-kit 0.19.1 : gabarit du bilan des tokens à la charte générique v2.1"
status: review
date: 2026-11-06
source: "story 3.9 de la migration 3.x ; brief-3.x-migrations.md"
---

# agent-cost-kit 0.19.1 : gabarit du bilan des tokens à la charte générique v2.1

Surface : `skills/bilan-tokens/gabarit.html` seulement (plus les catalogues `i18n/en.json` et `de.json` pour les couleurs de l'anneau). Les pages déjà publiées ne changent pas.

## Choix

- Jetons v2.1 copiés de `charte-generique` (`dist/charte.css`) entre deux marqueurs `JETONS charte` / `FIN JETONS` : sombre en `:root`, clair sous `prefers-color-scheme: light` et `[data-theme="clair"|"light"]`, sombre forcé par `[data-theme="sombre"|"dark"]`. Aucun sélecteur de thème dans la page.
- Choix par usage : fonds `fond` / `surface` / `surface-alt`, contours `trait` (décoratif) et `trait-fort` (boutons), états doux pour les familles (entrée, sortie, coût, impact).
- Boutons secondaires en contour `trait-fort` ; l'état enfoncé prend `primaire-doux` avec liseré `primaire`, jamais un aplat bleu. Le numéro des recommandations est en `bouton` / `sur-bouton`.
- Familles de modèles, étapes et anneau de coût : couleurs de série `--cat-*` (plus de `hsl()` en JavaScript). Filet or `accent-aplat` sous le titre ; pictogramme `--picto-*` sans repli bleu ; piles de polices de la charte, sans CDN ; liens soulignés.
- Catalogues : `var(--c-…)` devient `var(--…)`, et l'anneau suit l'ordre `cat-1` à `cat-4`.

## Tests

`tests/test_bilan_charte.py` : contrastes 4,5:1 (texte) et 3:1 (marques) sur des couples explicites dans les deux thèmes, parité des thèmes, aucun hex hors des jetons, aucun repli de `var()`, aucun aplat bleu de bouton, liens soulignés, pas de thème forcé.

## Reports

- Pas de favicon (une image ne lit pas les variables CSS) ; polices non embarquées ; drapeaux du sélecteur de langue en couleurs nationales (dans `scripts/bilan_i18n.py`).
- Bords du `body` (marge par défaut de 8 px visible autour des sections à fond) : antérieur, non touché.
