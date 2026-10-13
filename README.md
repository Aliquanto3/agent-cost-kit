# agent-cost-kit

Un plugin Claude Code pour développer par agents sans faire exploser la facture : trois sous-agents routés par rôle, un contrôle rapide de fin de story, et un script qui calcule le coût réel de chaque agent et de chaque story depuis vos transcriptions locales, sans aucun appel d'API.

*English summary at the end.*

## Ce que les mesures disent

Trois projets Python différents (une usine de migration de tickets, un pipeline de fine-tuning, un banc de modèles locaux), 109 stories développées par agents sur Claude Code, presque toutes du 10 au 13 octobre 2026, environ 1 800 $ d'équivalent API. Les mêmes règles de calcul pour les trois. Ce corpus historique tourne à 97 % sur Opus, en effort high. Ce qui converge :

| Constat | Projet 1 | Projet 2 | Projet 3 |
|---|---|---|---|
| Écriture du cache / lecture du cache / sortie, en part du coût | 44 / 40 / 16 % | 42 / 39 / 18 % | 41 / 41 / 18 % |
| Part médiane, dans une story, de l'agent intermédiaire (agent qui relance des agents) | 47 % | 40 % | 36 % |
| Corrélation entre le coût d'une story et la somme de (pic de contexte × appels) de ses agents | 0,95 | 0,97 | 0,86 (8 stories) |
| Surcoût du cache à 1 h sur un agent sans expiration | +29 % | +28 % | +30 % |
| Sous-agents sans aucune expiration de cache | 82 % | 78 % | 86 % |

Ce que ça change dans la pratique :

1. **Interdire l'imbrication.** L'agent intermédiaire qui relance un implémenteur et des relecteurs pèse 36 à 47 % d'une story. C'est le plus gros poste identifié. Le gain réel de sa suppression n'a pas été isolé : une partie de son travail passe à la session principale.
2. **Une seule passe de revue par story**, par un seul relecteur. Sur le projet 1, la baisse de 40 % du coût par story du « mode économique » vient surtout de la passe de revue unique.
3. **Ne pas passer le cache des sous-agents à 1 h par réflexe.** Il ne devient rentable qu'à partir d'environ 1 expiration par agent, et 78 à 86 % des sous-agents n'en ont aucune. Le script vous dit où vous en êtes.
4. **Piloter par le nombre d'appels et le pic de contexte.** Sur Opus, une story coûte 0,31 à 0,36 $ par million de « pic × appels » (médiane), dans les trois projets. Réduire les appels et le contexte lu pèse au moins autant que le choix du modèle.
5. **Opus pour décider, Sonnet pour coder et relire, Haiku pour chercher.** Opus est premier en architecture, en spec de story et en recherche web dans les bancs jugés en aveugle, avec 1 essai par case. Sur une story bien cadrée, Sonnet produit la même conception pour 55 % de moins. Haiku convient pour lire et chercher, pas pour concevoir.

Le setup de ce plugin (dev-story Sonnet, puis reviewer Sonnet, sans imbrication, cache par défaut) a été mesuré sur 10 stories de 2 projets : entre 0,50 et 1,38 $ par story, développement et revue compris. Les médianes historiques étaient de 6,35 et 12,81 $ par story, et de 5,5 à 6,9 $ sur les stories des mêmes epics, avec un agent Opus high qui relançait un implémenteur et quatre relecteurs. Sur les mêmes epics, le coût baisse d'un facteur 7 à 8 hors session principale, et d'environ 4 si on impute aux stories tout le coût d'orchestration de la session de test (borne haute). Quatre changements jouent en même temps (imbrication, nombre de relecteurs, modèle, effort) : la mesure ne dit pas lequel compte le plus. Les stories de test sont aussi plus petites que la moyenne d'un run.

## Ce qui dépend de votre projet

- **L'effort.** Sonnet en `high` contre `medium`, 3 essais par case, une story par projet, jugés en aveugle par Opus : sur un projet, aucune différence (8,7 contre 8,7 sur 10) ; sur l'autre, `high` évite les mauvais essais (8,7 contre 7,3, dont un bug réel en `medium`). Dans les deux cas, `high` coûte 50 à 60 % de plus. Le gain d'effort semble dépendre de ce que les tests du dépôt attrapent. Il se mesure, il ne se décrète pas : les agents sont livrés en `medium`, passez `effort: high` sur une story quand elle a des cas de bord que votre suite ne couvre pas.
- **La revue par Opus.** Dans les trois projets, elle n'a trouvé des défauts que Sonnet ou Haiku manquaient que lorsque le défaut ne se lisait ni dans le code ni dans un artefact du dépôt (comportement réel d'un service, d'un matériel, d'une facturation). Ailleurs, Opus classait seulement mieux leur gravité. Les trois projets n'ont pas la même vérité terrain : c'est une tendance, pas une règle.
- **Le seuil de découpage d'une story.** La médiane varie d'un projet à l'autre : 116 appels et 179 k de pic sur le projet 1, 182 appels et 266 k sur le projet 2. Le 90ᵉ percentile coûte environ 2 fois la médiane. Mesurez la vôtre avant de fixer un seuil.

## Installation

```
/plugin marketplace add anael-yahi/agent-cost-kit
/plugin install agent-cost-kit@agent-cost-kit
```

Ou, pour l'essayer sans installer : `claude --plugin-dir ./agent-cost-kit`.

Puis, dans votre projet : `/cost-kit-install`. Le skill propose les réglages à copier dans `.claude/settings.json` (un plugin ne peut pas les imposer), copie le modèle de contrôle rapide, et vous rappelle de redémarrer Claude Code.

## Contenu

| Élément | Rôle |
|---|---|
| `agents/dev-story.md` | Sonnet, `medium`, sans sous-agent (outil retiré) ni arrière-plan (par consigne). Implémente une story dans un worktree, tests ciblés pendant, suite complète une fois à la fin, au plus 3 cycles sur un même échec, rapport de 5 lignes. Passez `model: opus` ou `effort: high` par appel quand la story le mérite. |
| `agents/reviewer.md` | Sonnet, `medium`. Une passe, corrige les constats medium et high, consigne la revue dans la spec. |
| `agents/lookup.md` | Haiku, `low`, lecture seule. Trouve un symbole, résume un log. |
| `skills/cost-kit-install` | Installation guidée : réglages, contrôle rapide, vérification. |
| `commands/mesurer-couts.md` | `/agent-cost-kit:mesurer-couts` : coût réel par agent et par story, pic de contexte, appels, expirations du cache, contrefactuel du TTL. |
| `scripts/mesurer_couts.py` | Le script derrière la commande. Python 3.10+, aucune dépendance. Lit `~/.claude/projects/<projet>/`. |
| `scripts/controle_rapide.py` | Modèle de contrôle de fin de story (lint, format, typage), à adapter. |

## Mesurer avant de changer

```
python scripts/mesurer_couts.py --projet /chemin/du/depot
```

Le résumé donne le coût médian d'une story, ses appels et son pic de contexte, les expirations médianes par agent et le coût qu'aurait l'autre TTL. Faites 3 à 5 stories avec votre méthode actuelle, installez le kit, refaites 3 à 5 stories, comparez. Les prix (octobre 2026, vérifiés sur la page de prix officielle) sont dans l'en-tête du script : Opus 5.5 à 4 / 20 $, Sonnet 5.5 à 2 / 10 $ avec une lecture du cache à 0,10 $, Haiku 5.5 à 0,10 / 0,50 $ et 5 fois plus au-delà de 100 k tokens de prompt.

Deux pièges du calcul, corrigés par le script : certaines transcriptions ne gardent que l'usage du début d'une réponse (la sortie est réestimée depuis les caractères émis, borne basse), et les écritures en cache de 5 minutes et d'une heure n'ont pas le même prix.

## Limites

- Trois projets, un seul développeur, Windows, Python, méthode BMAD. Les constats convergents devraient tenir ailleurs ; les seuils, non.
- Les bancs de qualité comptent 1 à 3 essais par case, jugés par un LLM en aveugle. Ce sont des indications, pas des statistiques.
- Le setup n'a été mesuré que sur 10 stories, sans vérité terrain postérieure : on ne sait pas encore ce que les revues Sonnet ont laissé passer.
- La session principale (l'orchestrateur) n'est pas comptée dans les coûts par story. Elle pesait 10 à 23 % du total avec l'ancienne méthode. Avec le kit, elle reprend une partie du travail de l'agent intermédiaire et pèserait environ 30 % sur Opus. Le plugin ne la réduit pas.

## English summary

A Claude Code plugin for agent-based development that keeps the bill under control. Measured on 3 projects, 109 stories, about $1,800 of API-equivalent spend (97 % on Opus): cache writes and reads make up 82 to 84 % of the cost, the intermediate agent that spawns other agents takes 36 to 47 % of a story, story cost correlates with the sum of (peak context × calls) at r = 0.86 to 0.97, and a 1-hour subagent cache costs 28 to 30 % more for the 78 to 86 % of subagents that never hit an expiry. The kit ships three role-routed agents (Sonnet dev-story and reviewer, Haiku lookup), an install skill, and a dependency-free script that computes the real cost per agent and per story from your local transcripts. On 10 stories across 2 projects, it cost $0.50 to $1.38 per story (dev + review), against historical medians of $5.5 to $6.9 on stories from the same epics: 7 to 8 times cheaper excluding the main session, about 4 times cheaper with all orchestration cost charged to the stories. Several changes happened at once, and there is no post-merge ground truth yet.

## Licence

MIT.
