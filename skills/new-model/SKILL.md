---
name: new-model
description: "Évalue un nouveau modèle Claude pour le kit : prix et recommandations relevés en ligne, écarts avec tarifs.json, les agents et les réglages, devis des bancs, bancs lancés après accord, réglages proposés. Sans argument, vérifie seulement en ligne s'il existe des modèles à évaluer. Invocation manuelle seulement : /agent-cost-kit:new-model [identifiant du modèle]."
disable-model-invocation: true
---

Tu évalues un nouveau modèle pour Anaël. Argument reçu : `$ARGUMENTS`. Tu ne modifies ni `~/.claude/settings.json`, ni un agent, ni un `CLAUDE.md` sans son accord explicite, et tu ne lances aucune session payante sans devis accepté. Le kit est dans `${CLAUDE_PLUGIN_ROOT}` ; les modifications se font dans son dépôt source, sur une branche.

## Sans argument : veille seulement

1. Relève les modèles publiés et leurs prix sur `https://platform.claude.com/docs/en/about-claude/pricing` et la page des modèles de la même documentation.
2. Compare-les à `prix.modeles` de `plugins/couts-session/donnees/tarifs.json` (date `verifie_le`) et aux modèles des `agents/*.md`.
3. Rends un tableau : modèle, prix d'entrée, de sortie et de lecture du cache, statut (`connu`, `nouveau`, `prix changé`, `retiré`). Pour chaque modèle nouveau, donne la commande `/agent-cost-kit:new-model <identifiant>`. Arrête-toi là : ni banc, ni écriture.

## Avec un identifiant de modèle

### 1. État de l'art (gratuit)

- Page de prix, annonce du modèle, guide de choix de modèle de l'éditeur, journal des versions de Claude Code. Note l'identifiant exact, les prix (entrée, sortie, écriture du cache à 5 min et à 1 h, lecture du cache, seuils de contexte long, fast mode), les usages recommandés et l'effort conseillé.
- `claude --version`, puis vérifie vers quoi pointe l'alias de la famille (`claude -p "ok" --model <alias> --output-format json`, champ `modelUsage`, quelques centimes). Si l'alias vise encore l'ancienne génération, utilise l'identifiant complet partout.
- Cite chaque source avec sa date.

### 2. Écarts (gratuit, lecture seule)

- `tarifs.json` : une génération sans entrée propre prend le tarif d'un préfixe (Fable 5.2 a été compté 5 fois trop cher en lecture du cache). Ajoute l'entrée, lance `generer_tarifs.py`, ajoute une assertion dans `plugins/couts-session/tests/calcul.test.ts`, lance les tests Python ciblés.
- `~/.claude/settings.json` : `model`, `modelSettings` visant un modèle retiré, variables d'alias devenues inutiles.
- `scripts/installer_global.py` (`REGLAGES`), `skills/cost-kit-install/SKILL.md`, descriptions des `agents/*.md`, grille modèle / effort du `CLAUDE.md` global, références datées de `bancs/README.md`.
- Vérifie le point 3 de « Avant de commencer » de `bancs/README.md` (réglages de Claude Code toujours valides).

### 3. Hypothèses et devis

- Par rôle du kit (`dev-story`, `second-avis`, `reviewer`, `lookup`, orchestrateur, hors chaîne), dis si le modèle est candidat, d'après son prix et les usages recommandés. Un modèle plus cher que le titulaire n'est candidat que s'il peut sortir un meilleur code ; un modèle moins cher, que s'il peut tenir la qualité.
- Devis en tableau : banc, question, sessions, coût estimé d'après les références de `bancs/README.md`, décision qui en dépend. Classe du moins cher au plus cher et propose un plafond.
- Demande l'accord sur le devis. Tiens le cumul dépensé à jour, et redemande avant tout dépassement du plafond.

### 4. Bancs

Ordre conseillé, en t'arrêtant dès qu'une question est tranchée :

1. **Relecteur dans la chaîne** (`bancs/banc_relecteur.sh`, section « 1 bis » du README) si le modèle est candidat au rôle de `reviewer`. C'est lui qui décide : le 2026-11-10, la contre-revue isolée donnait 83 % contre 54 % au candidat, et la chaîne aucun écart.
2. **Contre-revue isolée** (section 1) : filtre peu coûteux, ou mesure d'un usage ponctuel hors chaîne. Elle ne suffit jamais à changer `reviewer`.
3. **Développement** (banc 4) si le modèle est candidat à `dev-story` : 3 essais par modèle sur 2 stories du corpus, puis contre-revue de chaque résultat par le relecteur en place.
4. **Orchestration** : ne la rejoue pas à part ; mesure-la sur le prochain run réel avec `/agent-cost-kit:mesurer-couts`.

Règles :

- Stories de `bancs/corpus.json`, 3 essais par cellule, résultats dans un dossier hors du dépôt, clones jetables sans remote.
- Permissions : `--settings bancs/reglages-banc.json`. Jamais `bypassPermissions`. Si des commandes utiles sont refusées aux sessions, relève-les dans les sorties JSON (`permission_denials`) et propose de compléter la liste.
- Deux stories en parallèle au plus, pas de suite de tests complète pendant les essais, `uv run python` et jamais `python` nu.
- Une session en erreur ou hors budget est relancée une fois, puis comptée à part.

### 5. Dépouillement

- `uv run --no-project python bancs/noter.py <dossier>/resultats` : coût par étape, fiches présentes après revue.
- Lis les sections `## Revue` et les diffs des relecteurs : la mesure par fiches peut ne pas départager deux modèles qui corrigent des défauts différents.
- Vérifie toi-même, dans le code, au moins deux défauts « certains » par modèle.
- Un défaut nouveau, signalé au moins deux fois et vérifié, devient une fiche de `bancs/verite-terrain.json` avec `validation: null`. Propose à Anaël de valider les fiches ; un taux publié ne porte que sur les fiches validées.

### 6. Conclusion et propositions

- Applique les « Règles pour conclure » de `bancs/README.md`. Un agent ne change de modèle que si le code sort meilleur de la chaîne, ou aussi bon pour moins cher. Dis les limites du banc (vérificateur, fiches sans objet, taille de l'échantillon).
- Rends un tableau par rôle : réglage proposé, changement, mesure qui le fonde. Puis la liste numérotée de ce qui attend un accord : réglages utilisateur, grille du `CLAUDE.md` global, agents, version du plugin.
- Après accord seulement : applique, mets à jour les références datées de `bancs/README.md` (date, version de Claude Code, prix), `CHANGELOG.md` et la version, lance les tests ciblés, ouvre une PR. Supprime les clones et les branches `banc/*` à la fin.
