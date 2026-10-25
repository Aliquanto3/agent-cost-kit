# Aiguillage des petites stories sans cadrage (expérimental)

Une règle que l'orchestrateur applique avant `dev-story` : une petite story bien décrite dans `epics.md` part directement en développement, sans le cadrage BMAD. **Expérimental et optionnel** : les agents ne changent pas, et la règle ne vise que les projets BMAD dont les stories viennent d'un `epics.md`. Il n'y a pas de script : c'est l'orchestrateur qui décide.

## La règle

**`dev-story` direct** si toutes ces conditions sont réunies :
- la story touche au plus 3 fichiers source attendus (environ 200 lignes) ;
- son entrée dans `epics.md` a au moins deux critères d'acceptation Given/When/Then (ou « Étant donné / quand / alors ») ;
- elle nomme ce qui est à créer (module, fonction, commande, écran).

L'orchestrateur donne alors à `dev-story` :
- l'entrée de `epics.md` telle quelle ;
- le chemin des documents de planification utiles (architecture, story précédente), s'il y en a ;
- la consigne d'écrire ses tests à partir des critères.

Pas de fichier de spec de story, pas d'étape « clarifier » ni « planifier ».

**Cadrage BMAD comme aujourd'hui** dans tous les autres cas :
- entrée à un seul critère ou sans critère ;
- story transverse ou multi-couches ;
- plus de 3 fichiers ;
- story à risque (sécurité, licence, refonte d'interface) ;
- doute de l'orchestrateur.

`second-avis` puis `reviewer` restent inchangés dans les deux cas. Les étapes expérimentales (mutation guidée, `verif-front`) s'appliquent pareil, avec l'entrée de `epics.md` comme spec.

## Pourquoi

Deux tests de la [veille agents de code](https://github.com/Aliquanto3/veille-agents-code) :
- **[T13](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T13-story-legere)** (10 petites stories, 3 dépôts) : une voie de cadrage légère façon OpenSpec coûte 46 % de moins que le cadrage BMAD complet (étapes « clarifier » et « planifier » de `bmad-build`), mais réussit 10 points de moins aux tests cachés (IC [−19 ; −3]). Elle est écartée.
- **[T13 bis](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T13bis-sans-cadrage)** (22 petites stories, 4 dépôts publics, 84 runs, critère fixé avant les runs) : sans aucun cadrage, `dev-story` lancé sur l'entrée de `epics.md` réussit autant que le cadrage BMAD complet à 10 points près (−0,6 point, IC [−8,4 ; +7,4]), pour 73 % de moins (0,35 $ contre 1,32 $ par story, cadrage compris, avant revue). Retirer les critères de l'entrée ne change rien de mesurable (−1,4 point, IC [−8,9 ; +5,4]). Sur les entrées brèves (un seul critère, 6 stories), le cadrage garde un avantage de 8 à 12 points, non concluant : d'où la condition des deux critères.

Gain attendu : environ 0,95 $ par petite story aiguillée.

## Limites

- Non-infériorité à 10 points seulement : la démontrer à 5 points demanderait environ 90 stories.
- Les tests cachés discriminent peu (environ 52 % de réussite dans les deux bras).
- Quatre dépôts, d'un seul auteur.
- Le `reviewer` n'a pas été joué dans le banc.
- Dans le banc, `dev-story` recevait aussi l'interface publique imposée par les tests cachés. Dans la vraie chaîne, il écrit lui-même ses tests.

## Suivi

Dans le journal d'un run autonome, marquer la story aiguillée par le résultat de l'étape `dev` :

```
- 2026-10-25 10:00 · 3.2 · dev · lancé, sans cadrage · —
- 2026-10-25 10:25 · 3.2 · dev · fini, sans cadrage, 14 tests verts · abc1234
```

`avancement-run` compte ces lignes comme `lancé` et `fini` : la mention est libre, un test le garantit.

Après au moins 10 stories aiguillées, comparer avec les stories cadrées : constats Important du reviewer par story, passes de revue, reprises (`dev-story` relancé), coût par story (`mesurer-couts`).

**Stable** si les stories aiguillées n'ont pas plus de constats Important ni de reprises que les stories cadrées comparables. **Sinon**, retirer la règle ou la restreindre.
