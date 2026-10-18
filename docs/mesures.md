# Les mesures derrière le kit

[← README](../README.md)

## Ce que les mesures disent

Le corpus : trois projets Python différents (une usine de migration de tickets, un pipeline de fine-tuning, un banc de modèles locaux), 109 stories développées par agents sur Claude Code, presque toutes du 10 au 13 octobre 2026, soit environ 1 850 $ d'équivalent API. Les règles de calcul et les prix vérifiés sont les mêmes pour les trois projets. Ce corpus historique tourne à 97 % sur Opus en effort high, avec un agent intermédiaire qui relance un implémenteur puis quatre relecteurs. Ce qui converge :

| Constat | Projet 1 | Projet 2 | Projet 3 |
|---|---|---|---|
| Écriture du cache / lecture du cache / sortie, en part du coût | 42 / 38 / 19 % | 41 / 38 / 21 % | 39 / 40 / 21 % |
| Part médiane, dans une story, de l'agent intermédiaire (agent qui relance des agents) | 47 % | 38 % | 36 % |
| Corrélation entre le coût d'une story et la somme de (pic de contexte × appels) de ses agents | 0,95 | 0,97 | 0,86 (8 stories) |
| Surcoût du cache à 1 h sur un agent sans expiration | +29 % | +28 % | +30 % |
| Sous-agents sans aucune expiration de cache | 82 % | 78 % | 86 % |

Ce que ça change dans la pratique :

1. **Interdire l'imbrication.** L'agent intermédiaire pèse 36 à 47 % d'une story. Sur une même story, l'ancien setup imbriqué coûte 5 fois plus que le kit, orchestration comprise (voir plus bas).
2. **Ne pas passer le cache des sous-agents à 1 h par réflexe.** Il ne devient rentable qu'à partir d'environ 1 expiration par agent, et 78 à 86 % des sous-agents n'en ont aucune. Le comportement réel du cache confirme le calcul : en TTL 1 h, une pause de 5 min à 1 h relit le contexte dans 100 % des cas, alors qu'en TTL 5 min elle le réécrit dans 91 % des cas.
3. **Piloter par le nombre d'appels et le contexte lu.** Sur Opus, une story coûte environ 0,31 à 0,36 $ par million de « pic × appels », dans les trois projets.
4. **Réduire le contexte fixe.** Désactiver les skills du compte claude.ai (`syncClaudeAiSkills: false`) retire 8,4 k tokens au premier appel de chaque agent, soit 5 à 10 % du coût d'une story avec le kit.
5. **Sonnet pour coder, Opus pour relire, Haiku pour le second avis et les recherches.** La revue est le point faible des setups bon marché (section suivante).

Mesuré en série depuis (`mesures/2026-10-16-nuit-autonome-5-stories.md`), sur une nuit autonome de 5 stories d'un quatrième projet, avec le kit 0.3.1 :
- **Coût** : 2,36 $ par story en médiane hors orchestration, environ 4 $ avec, contre 16,57 $ pour la story médiane du même projet avec l'ancien setup, soit 4 fois moins.
- **Revue** : 0,86 $ par story en médiane (second avis plus reviewer). Le second avis Haiku a trouvé les défauts les plus graves pour 1 à 2 cents ; le reviewer Opus a tranché chaque constat et en a ajouté 4. Un seul défaut a échappé à la chaîne, attrapé par la suite complète finale.

## La revue : ce que les mesures ont changé

La version 0.1 confiait la revue à Sonnet. Sur 10 stories livrées avec ce setup, toutes avec des suites vertes, puis fusionnées sans conflit, une contre-revue indépendante en lecture seule a donné ceci, avec la même consigne pour les trois modèles :

| Relecteur | Défauts medium ou high certains trouvés | Coût médian par story |
|---|---|---|
| Opus 5.5 | 11, sur 8 stories | 0,63 $ |
| Sonnet 5.5 | 1, plus 1 probable | 0,27 $ |
| Haiku 5.5 | 2, plus 2 probables et des constats propres | 0,03 $ |

Opus a pourtant manqué le seul défaut qui cassait la CI : une dépendance optionnelle que la CI n'installe pas. Sonnet et Haiku l'ont trouvé. **Aucun relecteur ne suffit seul.** D'où la version 0.2 :
- un second avis Haiku, en lecture seule, pour 3 cents ;
- puis un reviewer Opus, qui reçoit cette liste, vérifie au-delà du diff, exécute le code et corrige.

Coût estimé de la revue : environ 0,7 à 1 $ par story. Mesuré en série sur 5 stories : 0,49 à 1,69 $, 0,86 $ en médiane (`mesures/`). Refaites le banc A contre kit chez vous (`bancs/README.md`).

## Le setup mesuré en série

Même story (mode LLM local d'une usine de migration), même base, 3 essais par setup, coût de la session complète, orchestration comprise :

| Setup | Coût par story | Appels | Défauts medium+ trouvés ensuite par contre-revue Opus |
|---|---|---|---|
| Ancien : agent Opus high qui lance un implémenteur Sonnet et 4 relecteurs Opus (`bmad-build-auto`) | 6,77 à 7,31 $ | 129 à 152 | 1 essai sur 3 (commande de doc cassée) |
| Kit 0.1 : orchestrateur Opus medium, dev-story Sonnet, reviewer Sonnet | **1,18 à 1,60 $** | 36 à 51 | 1 essai sur 3 (requête refusée par le vrai serveur, probable) |

La qualité est comparable, pour un coût 5 fois moindre. Sur 10 autres stories de deux projets, le kit 0.1 coûtait 0,50 à 1,38 $ par story, hors orchestration, contre des médianes historiques de 6,81 et 13,10 $. Ces stories étaient plus petites que la moyenne.

## Ce qui dépend de votre projet

- **L'effort.** Sonnet en `high` contre `medium`, 3 essais par case, une story par projet, jugés en aveugle par Opus :
  - sur un projet, aucune différence (8,7 contre 8,7 sur 10) ;
  - sur l'autre, `high` évite les mauvais essais (8,7 contre 7,3, dont un bug réel en `medium`) ;
  - dans les deux cas, `high` coûte 50 à 60 % de plus.

  Le gain semble dépendre de ce que les tests du dépôt attrapent. Les agents sont livrés en `medium` : passez `effort: high` sur une story qui a des cas de bord que votre suite ne couvre pas.
- **Le seuil de découpage d'une story.** La médiane varie d'un projet à l'autre : 116 appels et 179 k de pic sur le projet 1, 182 appels et 266 k sur le projet 2. Mesurez la vôtre.
- **Le cache à 1 h.** Il devient rentable si vos agents attendent souvent plus de 5 minutes (tests longs, matériel réel). Le script le dit.

## Limites

- Trois projets, un seul développeur, Windows, Python, méthode BMAD. Les constats convergents devraient tenir ailleurs ; les seuils, non.
- Les bancs comptent 1 à 3 essais par case. Les défauts sont jugés par une contre-revue Opus, pas par une vérité terrain postérieure. Ce sont des indications, pas des statistiques.
- L'enchaînement de la version 0.2 (second avis Haiku, puis reviewer Opus) est maintenant mesuré en série, mais sur une seule nuit de 5 stories d'un seul projet, sans contre-revue indépendante après coup.
- La session principale pèse 10 à 23 % du total avec l'ancienne méthode. Avec le kit, elle reste modeste (0,3 $ par story sur Opus medium) si elle ne fait qu'orchestrer.
