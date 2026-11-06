---
title: "agent-cost-kit 0.20.1 : gabarit du bilan des tokens à la charte générique v2.1"
status: done
date: 2026-11-06
source: "story 3.9 de la migration 3.x ; brief-3.x-migrations.md"
---

# agent-cost-kit 0.20.1 : gabarit du bilan des tokens à la charte générique v2.1

Surface : `skills/bilan-tokens/gabarit.html` seulement (plus les catalogues `i18n/en.json` et `de.json` pour les couleurs de l'anneau). Les pages déjà publiées ne changent pas.

## Choix

- Jetons v2.1 copiés de `charte-generique` (`dist/charte.css`) entre deux marqueurs `JETONS charte` / `FIN JETONS` : sombre en `:root`, clair sous `prefers-color-scheme: light` et `[data-theme="clair"|"light"]`, sombre forcé par `[data-theme="sombre"|"dark"]`, et jetons clairs à l'impression (`@media print, (prefers-color-scheme: light)`). Aucun sélecteur de thème dans la page.
- Choix par usage : fonds `fond` / `surface` / `surface-alt`, contours `trait` (décoratif) et `trait-fort` (boutons), états doux pour les familles (entrée, sortie, coût, impact).
- Boutons secondaires en contour `trait-fort` ; l'état enfoncé prend `primaire-doux` avec liseré `primaire`, jamais un aplat bleu. Le numéro des recommandations est en `texte` sur `primaire-doux`, liseré `primaire`.
- Familles de modèles et anneau de coût : couleurs de série `--cat-*` (plus de `hsl()` en JavaScript). Étapes : trois groupes (cadrage, développement, le reste) en `cat-1` à `cat-3`, chacun avec son motif (plein, hachure, hachure inverse), parts écrites sous la pile de chaque projet. Filet or `accent` sous le titre (marque fine) ; pictogramme `--picto-*` sans repli bleu ; piles de polices de la charte, sans CDN ; liens soulignés.
- Catalogues : `var(--c-…)` devient `var(--…)`, et l'anneau suit l'ordre `cat-1` à `cat-4`.

## Tests

`tests/test_bilan_charte.py` : contrastes 4,5:1 (texte) et 3:1 (marques) sur des couples explicites dans les deux thèmes, parité des thèmes, aucun hex hors des jetons, aucun repli de `var()`, aucun aplat bleu de bouton, liens soulignés, pas de thème forcé.

## Reports

- Pas de favicon (une image ne lit pas les variables CSS) ; polices non embarquées ; drapeaux du sélecteur de langue en couleurs nationales (dans `scripts/bilan_i18n.py`).
- Bords du `body` (marge par défaut de 8 px visible autour des sections à fond) : antérieur, non touché.

## Revue

### Passe 1 (2026-11-06, SHA revu 4446b74)

Base `origin/master` bfa5fe2 à jour, pas de rebase. Aucune des PR ouvertes (#16, #17, #24) ne touche `gabarit.html`.

- Important · high · second avis 1 · corrigé : page sombre par défaut sans règle d'impression (texte clair sur papier blanc, régression sur 0.19.0 qui était claire). La requête du clair devient `@media print, (prefers-color-scheme: light)` ; bloc `@media print` : barre fixe masquée, `print-color-adjust: exact` sur les marques de graphique, `break-inside: avoid`, pastilles en contour. Test `test_impression_en_clair_et_marques_gardees`. Vérifié sur une capture d'impression émulée (recette-3.9).
- Important · medium · second avis 2 · corrigé : le filet sous le titre passe d'`accent-aplat` (1,93:1 en clair, interdit en marque fine) à `accent` (CHARTE § Règles d'usage, Or). Test réécrit : `accent` sur `fond` et `surface` ≥ 3:1 dans les deux thèmes, plus aucun `accent-aplat` hors des jetons.
- Important · medium · second avis 3 · corrigé : pile de 11 couleurs (dont `neutre`, `primaire-vif`, `trait-fort`) sans motif ni étiquette. Les étapes sont regroupées dans les trois groupes déjà affichés en section 05, en `cat-1` à `cat-3`, avec un motif chacun (plein, hachure 135°, hachure 45°) et les parts écrites sous la pile ; la section 05 reprend la couleur et le motif du groupe (lignes déjà étiquetées). Une étape inconnue va dans « le reste ». Catalogues `en`/`de` réalignés (infobulle). Test `test_au_plus_quatre_series_avec_motif`.
- Nit · low · second avis 4 · corrigé : numéro des recommandations en `texte` sur `primaire-doux`, liseré `primaire`, plus d'aplat `bouton`.
- Nit · low · second avis 5 · corrigé : `de.json`, `var(--sans)` remplacé par `var(--police-texte)`.
- Nit · low · second avis 6 · corrigé : `docs/bilan-tokens.md` dit que le gabarit est autonome (seul `const BILAN` est injecté) ; une copie 0.19.0 avec ses `--c-*` reste valable. Pas de liste de variables à fournir : le script n'en exige aucune.
- Nit · low · revue · rejeté : les points des familles de modèles (5 couleurs, dont `cat-6`) sont sur des lignes de tableau nommées ; ce n'est pas un graphique à séries, la couleur n'y porte pas seule le sens.
- Mentions SNCF, Wavestone, Resilio : une seule occurrence, identique sur master (citation de la méthode ImpactIA), aucun habillage. Rien à faire.
- Complexité : 0 constat (gabarit rendu une fois, `groupeDe` en O(11) par étape).

Recette : bilan réel de novembre 2026 sur ce PC, captures Edge sans tête en sombre, clair (différentes) et impression émulée, plus un PDF imprimé (8 pages), dans `_bmad-output/implementation-artifacts/recette-3.9/`.

### Passe 2 (2026-11-06, SHA revu e73ebe2)
- Nit · low · revue : si un hôte pose `data-theme="dark"` sur `<html>` (la page ne le fait jamais), l'impression reste sombre car le bloc `print` exclut ce cas ; non corrigé, car cela obligerait à dupliquer les jetons clairs. Le choix sombre par le système imprime bien en clair.
- Nit · low · revue : `test_au_plus_quatre_series_avec_motif` est un test par chaînes sur le gabarit, aucun test n'exécute le regroupement (étape inconnue). Lecture du code : `groupeDe` renvoie 2 (« le reste », motif `m3` hachure inverse), les onze familles de `bilan_detail.py` sont dans les trois listes, les parts sont calculées sur la même somme (pile à segment unique correcte).
- Vérifié : mutation (hachure 135° retirée) fait échouer le test, restaurée ; 230 tests verts ; `claude plugin validate . --strict` passe ; catalogues EN et DE à jour (test i18n vert).
