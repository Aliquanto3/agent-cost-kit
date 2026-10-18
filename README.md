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
| `commands/avancement-run.md` | `/agent-cost-kit:avancement-run` : synthèse d'avancement d'un run autonome BMAD (taux global, fin estimée, météo, epics, stories). |
| `scripts/avancement_run.py` | Le script derrière la commande. Python 3.10+, aucune dépendance, lecture seule. Lit `sprint-status.yaml`, `run-autonome.md` et `git log`. |
| `scripts/controle_rapide.py` | Modèle de contrôle de fin de story (lint, format, typage), à adapter. |
| `bancs/` | Protocole et scripts pour re-tester le kit quand de nouveaux modèles sortent (`bancs/README.md`). |

Le `model` et l'`effort` déclarés dans le frontmatter des agents s'appliquent bien aux agents de plugin. Vérifié : depuis une session Opus en `high`, `lookup` tourne en Haiku `low`.

## Suivre un run autonome

`/agent-cost-kit:avancement-run` (ou `python scripts/avancement_run.py <projet> [--detail] [--json]`) donne une synthèse pour un dirigeant, sans appel de modèle pour les chiffres :
- en tête, le taux d'avancement global (barre et « n / N stories »), l'heure de fin estimée (centrale et fourchette) et une météo : 🟢 dans les temps, 🟡 vigilance (un contrôle automatique rouge ou une story reprise), 🔴 bloqué (une story bloquée, ou une attente humaine sur le chemin critique) ;
- « Ce qu'il faut savoir » : trois à cinq puces sans jargon (faits marquants, points d'attention, décisions attendues d'Anaël) ;
- un tableau par epic (nom tiré de `epics.md`, barre, terminées, en cours, à faire, statut) et, repliable, un tableau par story (état en emoji, pourcentage, ★ pour les pivots) ;
- avec `--detail` : rythme observé (stories fusionnées par heure sur 3 h, durée médiane « dev lancé -> fusion »), vagues, chemin critique, méthode d'estimation, heures interpolées.

La fin estimée retient le plus contraignant de deux calculs : le reste divisé par le débit (plafonné par le parallélisme du plan), et le chemin critique des dépendances restantes. Elle ne compte ni les étapes humaines, ni les limites d'usage, ni les ressources à activer (Ollama, GPU), ni les reprises en cas d'échec.

Il attend le format du plan BMAD de l'orchestrateur : tables `| Vague | Stories en parallèle | Après |` avec dépendances `x.y ← a.b, c.d`, `★` pour un pivot, `(mixte)` pour une story à étape humaine, et une section « Journal ». **Pour une estimation fiable, chaque ligne du journal porte date et heure** : `- AAAA-MM-JJ HH:MM · story · étape · résultat · commit` (étapes : `dev`, `second-avis`, `review`, `fusion`, `CI`, `blocked`, `attente humaine`, `report`). Une ligne sans heure est datée par le commit « suivi du run … (story X fusionnée) », puis par le commit cité, puis par interpolation entre ses voisines : les durées deviennent approximatives.

Barème d'un en-cours : dev lancé 30 %, dev fini (second avis en cours) 60 %, second avis fini (review en cours) 75 %, review finie (fusion en cours) 90 %.

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

## Empreinte environnementale (GreenOps)

Le script estime aussi l'énergie, le GWP (gCO2e, usage et fabrication du matériel), l'eau, l'énergie primaire et l'ADPe des mêmes appels, en fourchette min-max, selon la méthodologie [EcoLogits](https://ecologits.ai/latest/methodology/llm_inference/). Les coefficients sont intégrés au script (données du 2026-10-14) : pas de dépendance. Mix électrique des États-Unis par défaut, `--mix {USA,FRA,SWE,WOR}` pour en changer.

Trois limites, dites dans `resume.md` :
- seuls les tokens de **sortie** comptent, comme dans EcoLogits ; le cache, qui fait environ 85 % du coût en dollars, n'a aucun impact dans ce modèle, donc empreinte et coût ne sont pas proportionnels ;
- la réflexion masquée n'est pas comptée : c'est une borne basse ;
- les tailles des modèles Anthropic sont estimées par EcoLogits, d'où la fourchette.

`bancs/ecologits_ecart.py` vérifie que le calcul du script reproduit la librairie officielle (écart de l'ordre de 1e-16).

## Le coût de la session en direct (mod `couts-session`)

Un mod Claude Code, installable seul, affiche au-dessus du prompt ce que coûte la session en cours, sans commande à taper :

```
/plugin marketplace add Aliquanto3/agent-cost-kit
/plugin install couts-session@agent-cost-kit
```

La bande a trois niveaux. Un clic sur la ligne (terminal plein écran) ou la touche `1` (prompt vide, ou après ctrl+x tab) passe au niveau suivant puis replie ; `2` remonte d'un niveau. Le niveau choisi est gardé d'une session à l'autre :
1. une ligne discrète : `💰 ≈ 2,81 $ · 🪙 3,3 M tok · 🌱 127–251 gCO₂e estimé` ;
2. un tableau par modèle (entrée, sortie, lecture et écriture du cache, coût, gCO₂e), une ligne par sous-agent (type, coût, impact, modèle, description), la source de l'impact, pour comparer le total `/cost` du moteur, et la commande d'analyse complète de la session (`/agent-cost-kit:mesurer-couts --session <id>`, du plugin `agent-cost-kit`), qui relit toutes les transcriptions pour chercher des optimisations ;
3. en plus, le remplissage du contexte façon `/context`, par catégorie (estimation locale, gratuite).

Les cumuls viennent de l'usage de chaque fin de tour, session principale et sous-agents. Ils survivent au rechargement du mod et à `--resume`, et repartent de zéro après `/clear`. Les prix et les coefficients EcoLogits sont dans `plugins/couts-session/donnees/tarifs.json`, les mêmes que ceux de `mesurer_couts.py` ; `donnees/generer_tarifs.py` en tire le module TypeScript du mod (`--verifier` contrôle les deux).

Limites :
- les tours d'avant le chargement du mod et les tours interrompus (sans usage) ne sont pas comptés ;
- l'écriture du cache est comptée au tarif 5 min : l'usage d'un tour ne sépare pas 5 min et 1 h ;
- le surcoût Haiku au-delà de 100 k tokens de prompt n'est pas appliqué : l'usage d'un tour additionne ses requêtes ;
- l'impact ne compte que les tokens de sortie, comme EcoLogits ; c'est une estimation, en fourchette ;
- les tokens de sortie sont ceux que déclare l'usage du tour, exacts en direct ; `mesurer_couts.py`, qui relit des transcriptions où ce compte est parfois tronqué, les réestime (`max(sortie, caractères / 2,2)`) : les deux totaux peuvent donc différer pour une même session.

## Limites

- Trois projets, un seul développeur, Windows, Python, méthode BMAD. Les constats convergents devraient tenir ailleurs ; les seuils, non.
- Les bancs comptent 1 à 3 essais par case. Les défauts sont jugés par une contre-revue Opus, pas par une vérité terrain postérieure. Ce sont des indications, pas des statistiques.
- L'enchaînement de la version 0.2 (second avis Haiku, puis reviewer Opus) est maintenant mesuré en série, mais sur une seule nuit de 5 stories d'un seul projet, sans contre-revue indépendante après coup.
- La session principale pèse 10 à 23 % du total avec l'ancienne méthode. Avec le kit, elle reste modeste (0,3 $ par story sur Opus medium) si elle ne fait qu'orchestrer.

## Historique

- **0.6.0** (2026-10-18) : commande `/agent-cost-kit:avancement-run` et script `avancement_run.py` : synthèse d'avancement d'un run autonome BMAD (taux global, fin estimée en fourchette, météo, tableau par epic, détail par story, `--detail`) ; convention d'heure dans le journal du run ;
- **0.5.0** (2026-10-18) : nouveau plugin `couts-session` 0.1.0, installable seul, un mod qui affiche au-dessus du prompt le coût API estimé, les tokens et l'impact carbone estimé de la session, par modèle et par sous-agent, et le remplissage du contexte ; prix et coefficients dans `plugins/couts-session/donnees/tarifs.json` ;
- **0.4.0** (2026-10-18) : estimation de l'impact environnemental (EcoLogits) dans `mesurer_couts.py` : énergie, GWP, eau, énergie primaire et ADPe en fourchette par agent (`agents.csv`), énergie, GWP et eau par arbre et en résumé ; option `--mix` ; banc `bancs/ecologits_ecart.py` contre la librairie ;
- **0.3.3** (2026-10-17) :
  - tiré de la V1.1 de WaveStack (13 stories, 221 $, `mesures/2026-10-17-wavestack-v1-1.md`) : consignes globales pour couper la session principale entre cadrage, exécution et recette, ne jamais sauter le second avis, relire la spec des stories à risque, lancer la suite complète à mi-parcours, vérifier la branche principale après chaque fusion et documenter en parallèle de la revue ; dev-story réaligne les tests et E2E d'une structure partagée qu'il modifie ; le reviewer cherche les complexités au-delà de O(n) sur les structures qui grossissent ;
  - mesure en série de l'enchaînement 0.2 sur une nuit autonome de 5 stories (`mesures/2026-10-16-nuit-autonome-5-stories.md`) ;
  - l'installeur global autorise `gh pr merge`, `gh pr edit` et la suppression de branche distante (`permissions.allow`, fusionné sans retirer les règles existantes) ;
  - consigne globale : recibler les PR empilées avant de fusionner leur base ;
  - le reviewer cherche les tests qui appellent les fonctions modifiées.
- **0.3.2** (2026-10-17) : l'étape de vérification de `cost-kit-install` ne renvoie plus vers `/agents`, assistant retiré de Claude Code ; elle passe par `claude plugin list` et par la liste des agents vue depuis une session.
- **0.3.1** (2026-10-15) : l'installeur global pose aussi `ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-5-5` (l'alias `haiku` restait sur Haiku 4.5) et l'effort `high` pour Fable 5.1.
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
