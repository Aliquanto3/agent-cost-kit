---
title: "agent-cost-kit 0.14.0 : aiguillage des petites stories sans cadrage (expérimental)"
status: ready
date: 2026-10-25
source: "veille agents de code, tests T13 et T13 bis (https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T13bis-sans-cadrage)"
---

# agent-cost-kit 0.14.0 : aiguillage des petites stories sans cadrage (expérimental)

Une story, branche `feat/0.14-aiguillage`. Ajout **expérimental** : une règle que l'orchestrateur applique avant `dev-story`. Les agents ne changent pas. La règle ne s'applique qu'aux projets BMAD dont les stories viennent d'un `epics.md`.

## Pourquoi

- **T13** (10 petites stories, 3 dépôts) : une voie de cadrage légère façon OpenSpec coûte 46 % de moins que le cadrage BMAD complet (étapes « clarifier » et « planifier » de `bmad-build`) mais réussit 10 points de moins aux tests cachés (IC [−19 ; −3]) : écartée.
- **T13 bis** (22 petites stories, 4 dépôts publics, 84 runs, critère fixé avant les runs) : sans aucun cadrage, `dev-story` lancé directement sur l'entrée de `epics.md` réussit autant que le cadrage BMAD complet à 10 points près (−0,6 point, IC [−8,4 ; +7,4]) pour 73 % de moins (0,35 $ contre 1,32 $ par story, cadrage compris, avant revue). Retirer les critères de l'entrée ne change rien de mesurable (−1,4 point, IC [−8,9 ; +5,4]). Sur les entrées brèves (un seul critère, 6 stories), le cadrage garde un avantage de 8 à 12 points, non concluant.
- **Limites à dire dans la doc** : non-infériorité à 10 points seulement (5 points demanderait ~90 stories) ; tests cachés peu discriminants (~52 % de réussite dans les deux bras) ; quatre dépôts d'un seul auteur ; le reviewer n'a pas été joué ; dans le banc, `dev-story` recevait aussi l'interface publique imposée par les tests cachés (dans la vraie chaîne, il écrit lui-même ses tests).

D'où une règle expérimentale, avec un suivi qui permet de la retirer.

## Livrables

1. **`docs/aiguillage-stories.md`** (nouveau), en français, phrases simples :
   - la règle :
     - **dev-story direct** si toutes ces conditions sont réunies : la story touche au plus 3 fichiers source attendus (environ 200 lignes) ; son entrée dans `epics.md` a au moins deux critères d'acceptation Given/When/Then (ou « Étant donné / quand / alors ») ; elle nomme ce qui est à créer (module, fonction, commande, écran). L'orchestrateur donne alors à `dev-story` l'entrée de `epics.md` telle quelle, le chemin des documents de planification utiles (architecture, story précédente) s'il y en a, et la consigne d'écrire ses tests à partir des critères. Pas de fichier de spec de story ; pas d'étape « clarifier / planifier ».
     - **cadrage BMAD comme aujourd'hui** dans tous les autres cas : entrée à un seul critère ou sans critère, story transverse ou multi-couches, plus de 3 fichiers, story à risque (sécurité, licence, refonte d'interface), doute de l'orchestrateur.
     - `second-avis` puis `reviewer` restent inchangés dans les deux cas ; les étapes expérimentales (mutation guidée, `verif-front`) s'appliquent pareil, avec l'entrée de `epics.md` comme spec.
   - pourquoi, avec les chiffres et les liens vers T13 et T13 bis, et les limites ci-dessus ;
   - **suivi** : dans le journal d'un run autonome, marquer la story aiguillée par le résultat de l'étape `dev` : `- AAAA-MM-JJ HH:MM · 3.2 · dev · lancé, sans cadrage · ` ; après au moins 10 stories aiguillées, comparer avec les stories cadrées : constats Important du reviewer par story, passes de revue, reprises (`dev-story` relancé), coût par story (`mesurer-couts`). Critère pour passer en stable : pas plus de constats Important ni de reprises que les stories cadrées comparables ; sinon retirer la règle ou la restreindre ;
   - gain attendu : environ 0,95 $ par petite story aiguillée.
2. **Compatibilité de `avancement-run`** : vérifier dans `scripts/avancement_run.py` qu'un résultat `lancé, sans cadrage` pour l'étape `dev` est compté exactement comme `lancé` (et `fini, sans cadrage` comme `fini` si tu documentes cette forme). Si ce n'est pas le cas, adapter le plus simplement possible. Ajouter un test dans `tests/test_avancement_run.py` qui le prouve.
3. **Consignes** : une phrase dans `modeles/CLAUDE.global.md`, à la suite des phrases sur la mutation guidée et `verif-front`, même style : « Petite story bien décrite dans `epics.md` (au plus 3 fichiers, au moins deux critères Given/When/Then, noms à créer) : règle expérimentale, dev-story directement sur l'entrée d'epics, sans cadrage BMAD ; cadrage sinon (`docs/aiguillage-stories.md` du kit). » Même information, courte, dans le README et `docs/installation.md` là où la chaîne est décrite, et une ligne dans `modeles/run-autonome.md` si ce modèle décrit la préparation des stories (sinon rien).
4. **`docs/experimental.md`** : une fiche « aiguillage sans cadrage » au format des autres (règle du kit, pas d'outil tiers ; problème visé ; quand l'essayer ; protocole ; quoi observer ; critère du livrable 1 ; ce qu'en dit la veille avec les liens).
5. **Version** : `0.14.0` dans `.claude-plugin/plugin.json`, entrée `0.14.0` en tête de l'historique de `CHANGELOG.md`, au style des entrées voisines.

## Hors périmètre

- Ne pas modifier les agents (`agents/*.md`) ni `modeles/agents/verif-front.md`.
- Pas de script qui décide de l'aiguillage : c'est l'orchestrateur qui applique la règle.
- Ne pas toucher `~/.claude/`.

## Vérification

- Tests ciblés : `uv run --no-project --with pytest python -m pytest -q --tb=short tests/test_avancement_run.py`, suite complète une fois à la fin ; `claude plugin validate . --strict`.
- La CI de la PR (Linux, Windows, validation) est la porte de fusion.
