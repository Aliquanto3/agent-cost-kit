---
title: "agent-cost-kit 0.16.0 : bilan des tokens par projet, par étape et par rôle"
status: review
date: 2026-10-27
source: "bilan d'octobre 2026 (1er au 26, 3 PC, 137 054 appels), fait à la main avec des scripts hors dépôt ; ce lot les intègre au kit"
---

# agent-cost-kit 0.16.0 : bilan des tokens par projet, par étape et par rôle

Une story, branche `feat/0.16-bilan-detail`. Le bilan mensuel (`bilan-tokens`) ne sait aujourd'hui agréger que par modèle et par mois entier. Le bilan d'octobre 2026 a demandé, en plus, une période en jours, plusieurs copies de transcriptions d'un même PC, et quatre sections de page : par projet du portfolio, par étape (besoin, specs, architecture, développement, relecture, livraison…), par rôle (orchestrateur et sous-agents, par modèle et par effort), et des recommandations tirées des mesures. Ce lot l'intègre au kit.

## Implémentation de référence

Écrite et utilisée pour le bilan d'octobre, hors dépôt. À lire avant de coder ; à porter proprement, pas à recopier tel quel (rien de propre à Anaël en dur, sauf les valeurs par défaut documentées ci-dessous) :

- `C:/Users/UTILIS~1/AppData/Local/Temp/claude/C--Users-Utilisateur-Documents-GitHub/3ee2a2fe-610f-485a-9451-784448f335bb/scratchpad/extraire.py` et `extraire2.py` : collecte des appels avec métadonnées (deux passes à fusionner en une) ;
- `.../scratchpad/classer.py` : classement par projet, étape et rôle, agrégation, indicateurs des recommandations ;
- `.../scratchpad/sections.html` : CSS et JS des sections 04 à 07 (à intégrer au gabarit) ;
- `.../scratchpad/bilan_periode.py` : filtre par période.

Résultat attendu sur les données réelles (ordre de grandeur, pour se repérer) : 7 949 $ au total, dont 32 % pour l'orchestrateur ; développement 46 %, relecture et tests 25 % ; WaveStack 2 140 $.

## Ce que les transcriptions fournissent

Sur chaque ligne `assistant` : `effort` (`low`, `medium`, `high`…), `cwd`, `sessionId`, `attributionSkill` (rarement rempli, ne pas s'en servir), et dans `message.content` les blocs `tool_use` (`name`, `input`). Sur les lignes `user` : `<command-name>/nom</command-name>` quand on tape un skill ou une commande. Un sous-agent est un fichier `<session>/subagents/agent-<id>.jsonl` accompagné de `agent-<id>.meta.json` (`agentType`, `description`). L'outil `Skill` (`input.skill`) marque aussi l'invocation d'un skill.

## Livrables

### 1. `scripts/bilan_tokens.py` : période, racines multiples, `--detail`

- `--du AAAA-MM-JJ --au AAAA-MM-JJ` (dates UTC incluses), exclusif avec `--mois` ; les deux dates dans le même mois (sinon erreur claire). JSON : champs `du` et `au` en plus de `mois` (le mois des deux dates) ; fichiers nommés `<du>_<au>-<machine>.json/html` au lieu de `<mois>-<machine>`. Sans `--du/--au`, rien ne change, au champ près.
- `--racine` répétable (`action="append"`, défaut `~/.claude/projects`) : toutes les racines sont lues, un appel par `message.id` sur l'ensemble (première occurrence chronologique). Usage : une copie des transcriptions d'un PC plus le dossier local du même PC.
- `--detail` : ajoute au JSON un champ `detail` (livrable 2) et à la page les sections 04 à 07 (livrable 4). `--config` (défaut `~/.claude/cost-kit/bilan-config.json`, absent = valeurs par défaut).
- `--fusionner` : refuse des bilans de périodes différentes (`mois`, `du`, `au`) ; nomme le consolidé `<du>_<au>-consolide` quand il y a une période ; fusionne `detail` quand **tous** les bilans en ont un (livrable 3), sinon le consolidé n'en a pas et un avertissement le dit.
- Pas de nouvelle dépendance : stdlib seulement, comme aujourd'hui.

### 2. Nouveau `scripts/bilan_detail.py` (stdlib, réutilise `mesurer_couts`)

**Collecte en une passe.** Étendre `mc.appels(chemin)` par un paramètre `details: bool = False` qui ajoute à chaque appel `effort`, `cwd`, `session`, `outils` (liste de `(nom, détail)` : la commande pour `Bash`/`PowerShell` tronquée à 160 caractères, `subagent_type` pour `Agent`/`Task`, `skill` pour `Skill`), sans rien changer aux champs existants (test : mêmes champs et mêmes valeurs qu'avec `details=False`). La chronologie des skills d'un fichier (`(ts, nom)` depuis `<command-name>` et l'outil `Skill`), la description et le début du premier prompt d'un sous-agent (300 caractères) sont lus dans la même passe par `bilan_detail`.

**Projet.** Le dépôt d'un appel est le premier segment de son `cwd` sous un dossier parent de dépôts (`parents`, défaut `["GitHub", "dev"]`, comparaison insensible à la casse). Puis, dans l'ordre : `alias` (préfixe de nom → clé de dépôt), clé du portfolio égale au nom ou préfixe suivi de `-` ou `_` (la plus longue d'abord, pour les worktrees `depot-lot4`, `depot-wt-014`), sinon le nom tel quel, hors portfolio. `cwd` hors de tout parent ou égal au parent : « Racine des dépôts (sessions transverses) ».

**Étape.** Onze familles, dans cet ordre d'affichage : `besoin` (🧭 Cadrage du besoin), `specs` (📝 Spécifications), `archi` (🏛️ Architecture et plan), `dev` (🛠️ Développement), `relecture` (🔍 Relecture et tests), `livraison` (🚀 Intégration et livraison), `pilotage` (🎛️ Pilotage et orchestration), `recherche` (🔎 Recherche et documentation), `outillage` (🧰 Outillage et mesure), `contenus` (🎨 Contenus et communication), `libre` (💬 Échanges sans étape identifiée). Règles, tables de motifs et sous-libellés : reprendre `SKILLS`, `IGNORES`, `AGENTS`, `DESC`, `LIVRAISON`, `TESTS`, `act_outils` et `activite` de `classer.py`, en constantes nommées et documentées :
- session principale : le dernier skill invoqué (hors `IGNORES`) vaut jusqu'au skill suivant ou à `/clear` ; une commande de livraison (`LIVRAISON`) l'emporte toujours ; sans skill, l'outil de l'appel décide (`act_outils`) ;
- sous-agent : type explicite (`AGENTS`), sinon skill actif **dans le sous-agent au moment de l'appel**, sinon motifs `DESC` sur la description puis sur le prompt (dans cet ordre, la description d'abord), sinon skill de la session parente au lancement, sinon `dev`.
- le sous-libellé ne contient jamais de texte de transcription : nom de skill, type d'agent, ou libellé fixe (« Sous-agents généralistes (implémentation) », « Git, PR, CI et release »…).

**Rôle.** `Orchestrateur (session principale)` ou le type du sous-agent (`dev-story` → `agent-cost-kit:dev-story`, idem `reviewer`, `lookup`). Sous-clé : `<Modèle> · effort <effort>` (`Opus 5.5 · effort high`, `?` si absent).

**Agrégation fusionnable.** Ne pas garder les appels dans le JSON. Pour chaque cellule (dimension, clé, sous-clé), garder **par modèle** les sommes brutes `appels, entree, ecrit_5m, ecrit_1h, lu, sortie_declaree, sortie` et les parts de coût de `mc.couts` (`entree, ecriture, lecture, sortie`). L'impact d'un bloc se recalcule à partir de ces sommes (`mc.impact` est linéaire en chaque argument : voir sa docstring) avec la même méthode et le même mix que `mc.impact_appels`. Les coûts s'additionnent. Garder aussi, par rôle de sous-agent, la liste des coûts par agent (un nombre par fichier de sous-agent, arrondi au centime) pour recalculer médiane et nombre d'agents après fusion. Le JSON `detail` contient ces données brutes (`brut`) et les blocs d'affichage calculés (`projets`, `etapes`, `roles`, `orch`, `sous`, `recos`, `portfolio_url`), recalculés à la fusion depuis `brut`. Test exigé : bilan(A) fusionné avec bilan(B) donne les mêmes blocs qu'un bilan unique sur A et B (racines disjointes).

**Portfolio** (config, section `portfolio`, toute absente → pas de notion de portfolio, une ligne par dépôt) : `url` (lien affiché), `fichier` (un `portfolio.json` au format du profil Aliquanto3 : `repos.<clé>.name`, `statuses.<topic>.fr`), `proprietaire` et `topic` pour lire états et versions par `gh repo list <proprietaire> --topic <topic> --json name,repositoryTopics,latestRelease --limit 200` (fonction d'exécution injectable pour les tests ; `gh` absent, en erreur ou hors délai de 30 s → pas d'état, un avertissement, le bilan continue). État = libellé `fr` du premier topic `status-*` connu ; version = `latestRelease.tagName`.

**Recommandations.** Calculées en Python depuis les blocs (donc aussi après fusion), en français, chiffres formatés à la française. Chacune : `id`, `titre`, `mesure`, `pratique` (HTML court autorisé : `<b>`, `<code>`), `gain` (`[min, max]` en $ ou `null` pour neutre). Une recommandation n'apparaît que si sa condition est remplie. Triées par gain max décroissant, neutres à la fin. Seuils en constantes nommées :
1. `implementation-generaliste` : au moins 5 sous-agents `general-purpose` classés `dev` et leur coût médian > 1,5 × celui de `dev-story` (au moins 5 `dev-story`). Gain : (médiane généraliste − médiane `dev-story`) × nombre de généralistes, ±20 %.
2. `relecture` : relecteurs multiples de `bmad-code-review` (description `hunter|intent alignment|acceptance auditor|adversarial lens`) ≥ 3 % du total, ou `reviewer` à plus de 50 % des appels sur Opus. Gain : min = 0,25 × coût Opus du `reviewer` + 0,5 × coût des relecteurs multiples ; max = 0,25 × coût Opus du `reviewer` + coût des relecteurs multiples.
3. `contexte-orchestrateur` : contexte moyen par appel de l'orchestrateur ≥ 1,5 × celui des sous-agents et orchestrateur ≥ 20 % du coût. Gain : 0,4 à 0,8 × coût de la sous-étape « Lecture du code et commandes ».
4. `modele-ancien` : pour chaque modèle ≥ 1 % du coût dont une version plus récente de la même famille, connue de `tarifs.json`, a une lecture du cache moins chère. Gain : coût de lecture × (1 − prix récent / prix ancien), ±10 %.
5. `pilotage-session` : pilotage ≥ 5 % du coût et ≥ 80 % de son coût en session principale. Gain : 0,2 à 0,4 × coût du pilotage.
6. `effort-neutre` (neutre) : orchestrateur Opus avec au moins 100 appels en `medium` et 100 en `high`, coût par appel à moins de 10 % d'écart.
7. `amont` (neutre) : besoin + specs + archi < 15 % du coût et dev + relecture > 50 %.
8. `mesure` (neutre) : sous-agents dont la description correspond à `motif_experiences` (config, défaut `^(T\d|Banc|banc|Test W)`) ; coût > 0.
Textes : reprendre ceux de `sections.html` (fonction `recos`), au présent, sans tiret cadratin.

**Config** `~/.claude/cost-kit/bilan-config.json`, documentée dans `docs/bilan-tokens.md` avec un exemple : `portfolio` (`url`, `fichier`, `proprietaire`, `topic`), `alias` (objet), `parents` (liste), `motif_experiences` (regex). JSON invalide → erreur claire.

### 3. Fusion du détail

`commande_fusion` additionne `brut` cellule par cellule et modèle par modèle, concatène les listes de coûts par agent, puis recalcule les blocs et les recommandations avec la config courante (portfolio relu pour les états). Les mêmes refus qu'aujourd'hui s'appliquent.

### 4. `skills/bilan-tokens/gabarit.html`

Intégrer les sections 04 (« Par projet »), 05 (« Par étape », avec le `<details>` de méthode), 06 (« Par rôle ») et 07 (« Recommandations », avec l'encadré des bancs d'essai du 13 octobre, et un lien vers `docs/genese.md` sur GitHub) de `sections.html`, et les liens de navigation. Affichées seulement si `BILAN.detail` existe ; sinon la page est identique à aujourd'hui. Section 04 : titre « Ce qu'a consommé chaque projet du portfolio » et lien vers `detail.portfolio_url` quand un portfolio est configuré ; sinon « Ce qu'a consommé chaque dépôt », sans colonne État. Recommandations rendues depuis `detail.recos` (le JS ne calcule plus les textes). Tout texte venu du JSON passe par `esc` (sauf `mesure` et `pratique`, produits par le script). Le script de ces sections s'exécute après celui du gabarit (fonctions `esc`, `tok`, `usd`, `nf`, `rng`, `pct`). Pas de nouvelle bibliothèque.

### 5. Documentation et version

- `docs/bilan-tokens.md` : nouvelles options ; section « Détail par projet, étape et rôle » qui explique le classement (règles ci-dessus, en phrases simples), la config avec un exemple, les limites (un skill reste attribué jusqu'au suivant : le pilotage est surestimé après `avancement-run` ; frontière entre familles voisines à quelques pourcents près ; seuls des noms de skills, de types d'agents et de dépôts sortent des transcriptions, jamais leur texte).
- `skills/bilan-tokens/SKILL.md` : `--du/--au`, `--racine` répétable, `--detail`, la config (proposer de la créer si absente et qu'un portfolio est mentionné), commentaire de 10 lignes qui cite la première recommandation.
- `README.md` : une ligne là où le bilan est décrit.
- `CHANGELOG.md` : entrée `0.16.0` en tête, au style des voisines. `.claude-plugin/plugin.json` : `0.16.0`.

### 6. Tests (`tests/test_bilan_detail.py`, et `tests/test_bilan_tokens.py` pour les options)

Sur des transcriptions synthétiques dans `tmp_path`, comme `test_bilan_tokens.py` : filtre `--du/--au` (bornes incluses, refus de deux mois) ; `--racine` répétée avec un même `message.id` dans deux racines compté une fois ; `mc.appels(details=True)` identique sur les champs communs ; projet (parent, alias, worktree `depot-lot4`, racine, hors portfolio) ; étape (skill tapé puis `/clear`, commande `git push` sous un skill actif, `Edit` sans skill, sous-agent `dev-story`, sous-agent généraliste au skill qui change en cours de route, description avant prompt, repli sur le skill parent) ; rôle et sous-clé modèle · effort ; impact d'un bloc recalculé depuis `brut` égal à `mc.impact_appels` sur les mêmes appels ; équivalence fusion / collecte unique ; chaque recommandation déclenchée et non déclenchée par ses seuils ; `gh` en échec → pas d'état, bilan écrit ; page : JS des sections exécuté sous Node avec un DOM simulé (voir la ligne « info » de la revue 0.8.0 dans `docs/bilan-tokens.md`) si `node` est présent, sinon test sauté ; échappement de `</` dans `detail`.

## Hors périmètre

- Ne pas changer `mesurer_couts.py` au-delà du paramètre `details`, ni les agents, ni `tarifs.json`.
- Ne pas toucher `~/.claude/` ni écrire la config de l'utilisateur.
- Pas de période à cheval sur deux mois.
