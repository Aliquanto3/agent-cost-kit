# agent-cost-kit

Un plugin Claude Code pour développer par agents sans faire exploser la facture :
- quatre sous-agents routés par rôle ;
- un contrôle rapide de fin de story ;
- un script qui calcule le coût réel de chaque agent et de chaque story depuis vos transcriptions locales, sans aucun appel d'API ;
- des bancs pour re-tester tout ça quand de nouveaux modèles sortent.

*English summary at the end.*

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

Coût estimé de la revue : environ 0,7 à 1 $ par story. Cet enchaînement n'a pas encore été mesuré en série : refaites le banc A contre kit chez vous (`bancs/README.md`).

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

## Installation

```
/plugin marketplace add Aliquanto3/agent-cost-kit
/plugin install agent-cost-kit@agent-cost-kit
```

Ou, pour l'essayer sans installer : `claude --plugin-dir ./agent-cost-kit`.

Sur un nouveau PC, ces deux commandes et un `/cost-kit-install` suffisent : les réglages globaux ne sont pas synchronisés d'une machine à l'autre, le script les réapplique. Après une mise à jour du kit, relancez-le (`python scripts/installer_global.py`) : il ne remplace que le bloc du kit dans `~/.claude/CLAUDE.md`.

Puis, dans votre projet : `/cost-kit-install`. Le skill :
- une fois par PC, applique avec votre accord les réglages utilisateur (`~/.claude/settings.json`) et les consignes de coût globales (`~/.claude/CLAUDE.md`), par `scripts/installer_global.py` : aperçu d'abord, sauvegarde, rien d'autre n'est touché ; il propose aussi le plugin `pyright-lsp` pour les projets Python et le blocage des connecteurs claude.ai inutiles ;
- propose les réglages du projet (un plugin ne peut pas les imposer) ;
- copie le modèle de contrôle rapide ;
- explique l'enchaînement des agents ;
- vous rappelle de redémarrer Claude Code.

## Contenu

| Élément | Rôle |
|---|---|
| `agents/dev-story.md` | Sonnet, `medium`, sans sous-agent (outil retiré) ni arrière-plan (par consigne). Implémente une story dans un worktree, tests ciblés pendant, suite complète une fois à la fin, au plus 3 cycles sur un même échec, rapport de 5 lignes. |
| `agents/second-avis.md` | Haiku, lecture seule. Relecture adversariale du diff pour quelques centimes ; sa liste est transmise au reviewer. |
| `agents/reviewer.md` | Opus, `medium`. Une passe : suit les appelants au-delà du diff, exécute le code, questionne les tests, vérifie ce que la CI installe, corrige les constats medium et high, consigne la revue dans la spec. |
| `agents/lookup.md` | Haiku, `low`, lecture seule. Trouve un symbole, résume un log : 20 bonnes réponses sur 20, comme Sonnet, pour 18 fois moins cher. |
| `skills/cost-kit-install` | Installation guidée : partie globale, réglages du projet, contrôle rapide, enchaînement, vérification. |
| `scripts/installer_global.py` | Partie globale, une fois par PC : fusionne les réglages utilisateur, écrit le bloc de consignes entre marqueurs, signale les réglages contraires. Aperçu par défaut, `--appliquer` pour écrire. Python 3.10+, aucune dépendance. |
| `modeles/CLAUDE.global.md` | Les consignes de coût écrites dans `~/.claude/CLAUDE.md`. |
| `commands/mesurer-couts.md` | `/agent-cost-kit:mesurer-couts` : coût réel par agent et par story, pic de contexte, appels, expirations du cache, contrefactuel du TTL. |
| `scripts/mesurer_couts.py` | Le script derrière la commande. Python 3.10+, aucune dépendance. Lit `~/.claude/projects/<projet>/`. |
| `scripts/controle_rapide.py` | Modèle de contrôle de fin de story (lint, format, typage), à adapter. |
| `bancs/` | Protocole et scripts pour re-tester le kit quand de nouveaux modèles sortent (`bancs/README.md`). |

Le `model` et l'`effort` déclarés dans le frontmatter des agents s'appliquent bien aux agents de plugin. Vérifié : depuis une session Opus en `high`, `lookup` tourne en Haiku `low`.

## Mesurer avant de changer

```
python scripts/mesurer_couts.py --projet /chemin/du/depot
```

Le résumé donne :
- le coût médian d'une story, ses appels et son pic de contexte ;
- les expirations médianes par agent ;
- le coût qu'aurait l'autre TTL.

La méthode : faites 3 à 5 stories avec votre méthode actuelle, installez le kit, refaites 3 à 5 stories, comparez.

Les prix (octobre 2026, vérifiés sur la page de prix officielle) sont dans l'en-tête du script : Opus 5.5 à 4 / 20 $, Sonnet 5.5 à 2 / 10 $ avec une lecture du cache à 0,10 $, Haiku 5.5 à 0,10 / 0,50 $, et 5 fois plus au-delà de 100 k tokens de prompt.

Deux pièges du calcul, que le script corrige :
- certaines transcriptions ne gardent que l'usage du début d'une réponse ; la sortie est alors réestimée à 2,2 caractères par token, valeur mesurée avec l'endpoint `count_tokens` ;
- les écritures en cache de 5 minutes et d'une heure n'ont pas le même prix.

## Quand de nouveaux modèles sortent

Les choix de modèles du kit valent pour Opus, Sonnet et Haiku 5.5, aux prix d'octobre 2026. À chaque nouvelle génération ou changement de prix :
1. mettez à jour les prix du script ;
2. vérifiez que les réglages de Claude Code existent toujours ;
3. rejouez les bancs de `bancs/README.md` sur vos stories : contre-revue par modèle, A contre kit, recherches, effort, caractères par token, cache.

Comptez environ 60 $ pour tout refaire. Ne changez un réglage qu'avec au moins 3 essais par cellule.

## Limites

- Trois projets, un seul développeur, Windows, Python, méthode BMAD. Les constats convergents devraient tenir ailleurs ; les seuils, non.
- Les bancs comptent 1 à 3 essais par case. Les défauts sont jugés par une contre-revue Opus, pas par une vérité terrain postérieure. Ce sont des indications, pas des statistiques.
- L'enchaînement de la version 0.2 (second avis Haiku, puis reviewer Opus) est déduit des bancs de contre-revue. Il n'a pas encore été mesuré en série.
- La session principale pèse 10 à 23 % du total avec l'ancienne méthode. Avec le kit, elle reste modeste (0,3 $ par story sur Opus medium) si elle ne fait qu'orchestrer.

## Historique

- **0.3.0** (2026-10-15) :
  - partie globale de l'installation, une fois par PC (`scripts/installer_global.py`, `modeles/CLAUDE.global.md`) ;
  - options proposées : plugin `pyright-lsp`, blocage des connecteurs claude.ai inutiles.
- **0.2.0** (2026-10-13) :
  - le reviewer passe sur Opus, avec une consigne élargie ;
  - nouvel agent `second-avis` (Haiku) ;
  - sortie réestimée à 2,2 caractères par token (au lieu de 3,2) ;
  - conseils d'installation mesurés ;
  - ajout des bancs de re-test.
- **0.1.0** (2026-10-13) : première version.

## English summary

A Claude Code plugin for agent-based development that keeps the bill under control. Measured on 3 projects, 109 stories, about $1,850 of API-equivalent spend:
- cache writes and reads make up about 80 % of the cost;
- the intermediate agent that spawns other agents takes 36 to 47 % of a story;
- a 1-hour subagent cache costs 28 to 30 % more for the 78 to 86 % of subagents that never hit an expiry (confirmed on real cache behaviour);
- disabling claude.ai skill sync saves 8.4k tokens per agent.

On the same story, 3 runs each, the kit cost $1.18 to $1.60 against $6.77 to $7.31 for the nested Opus setup, orchestration included, at comparable quality. Independent read-only re-reviews showed that a Sonnet reviewer misses most defects (Opus found 11 certain medium+ defects on 10 stories, Sonnet 1, Haiku 2 plus unique ones, and no single reviewer found everything). Version 0.2 therefore ships Sonnet for coding, a Haiku second opinion, an Opus reviewer, and a Haiku lookup agent. A `bancs/` folder holds the protocol and scripts to re-run every benchmark when new models come out. Since 0.3, `/cost-kit-install` also applies the user-level settings and a cost-rules block in `~/.claude/CLAUDE.md`, once per machine, through `scripts/installer_global.py` (dry run by default).

## Licence

MIT.
