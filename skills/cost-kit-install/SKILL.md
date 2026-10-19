---
name: cost-kit-install
description: Installe le setup économe de agent-cost-kit sur le PC (réglages utilisateur et consignes globales, une fois par machine) puis dans le projet courant - propose les réglages de settings.json (profondeur d'imbrication, TTL du cache des sous-agents, skills claude.ai), copie le modèle de contrôle rapide, explique l'enchaînement des agents et vérifie l'installation. À invoquer avec "install cost kit", "installer le kit de coût" ou /cost-kit-install.
---

Tu installes le kit sur le PC (partie globale, une fois par machine) puis dans le dépôt courant. Procède dans l'ordre, et demande confirmation avant chaque écriture dans `~/.claude/` ou `.claude/`.

0. **Partie globale, une fois par PC.** Lance `uv run --no-project python ${CLAUDE_PLUGIN_ROOT}/scripts/installer_global.py` (`python` nu ouvre l'alias du Microsoft Store sous Windows ; `--no-project` ne touche pas à l'environnement du projet) : c'est un aperçu, rien n'est écrit. Si tout est « déjà conforme » et « à jour », passe à l'étape 1. Sinon, montre les changements, explique-les (détail à l'étape 1), puis, avec l'accord de l'utilisateur, relance avec `--appliquer`. Le script :
   - fusionne dans `~/.claude/settings.json` : `syncClaudeAiSkills: false`, `effortLevel: "medium"`, `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, `ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-5-5` (sans lui, l'alias `haiku` des agents du kit restait sur Haiku 4.5), effort `high` pour Fable 5.1 seulement (`modelSettings`), sans toucher aux autres clés (proxy, plugins) ;
   - écrit les consignes de coût du kit dans `~/.claude/CLAUDE.md`, entre deux marqueurs : une relance après une mise à jour du kit remplace ce bloc et seulement lui. Les consignes personnelles se mettent hors des marqueurs ;
   - sauvegarde chaque fichier modifié (`.avant-cost-kit-AAAAMMJJ`) ;
   - signale sans les modifier un effort par modèle autre que medium (`modelSettings`, il prime sur `effortLevel`) et un TTL d'une heure. Propose de les corriger à la main.

   Options, à proposer sans les imposer :
   - **Windows** : exclure du scan Defender le dépôt et le cache uv (`Add-MpPreference -ExclusionPath '<dépôt>','<cache uv>'`, PowerShell administrateur). Gain observé : la suite locale passait de 7 à 60 min sous charge parallèle sans l'exclusion. À l'utilisateur de décider : c'est un affaiblissement de la protection.
   - **Projets Python** : le plugin officiel `pyright-lsp` donne à Claude la navigation par symbole et les erreurs de type après chaque modification, au lieu de rechercher puis lire plusieurs fichiers (gain non mesuré par le kit). Sans droits admin : `uv tool install pyright` (ou `pip install --user pyright`), puis `claude plugin install pyright-lsp@claude-plugins-official`.
   - **Connecteurs claude.ai inutiles en développement** : les lister avec `/mcp`, puis les bloquer dans `~/.claude/settings.json` par `"deniedMcpServers": [{ "serverName": "claude.ai Gmail" }, …]`, ou tous par `"disableClaudeAiConnectors": true`. Gain faible (leurs outils ne sont chargés qu'au premier usage, seules leurs consignes le sont toujours), non mesuré.

1. **Réglages du projet.** Si la partie globale est appliquée, il n'y a rien à ajouter ici, sauf retirer `subagentPromptCacheTtl: "1h"` du projet s'il y figure. Sinon, lis `.claude/settings.json` s'il existe et propose d'y fusionner ce bloc, en expliquant chaque ligne :

   ```json
   {
     "env": { "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1" }
   }
   ```

   - `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH = 1` (Claude Code 2.1.217 ou plus récent) : un sous-agent ne peut pas lancer de sous-agents. Mesuré sur trois projets, l'agent intermédiaire qui relance des agents pèse 36 à 47 % du coût d'une story.
   - **Ne pas** poser `subagentPromptCacheTtl: "1h"`. Sur trois projets, 78 à 86 % des sous-agents n'ont jamais d'expiration de cache, et le TTL d'une heure leur coûte 28 à 30 % de plus. Il ne devient rentable qu'à partir d'environ une expiration par agent, seuil confirmé sur le comportement réel du cache. Le proposer seulement si le script de mesure montre une médiane d'au moins 1 expiration par agent. Si le projet le pose déjà, proposer de le retirer.
   - **`"syncClaudeAiSkills": false`** : les skills du compte claude.ai ne sont alors plus rechargés dans chaque agent. Mesuré : 8,4 k tokens de moins au premier appel de chaque agent, soit 5 à 10 % du coût d'une story avec le kit. Ce réglage est **ignoré dans `.claude/settings.json`** : il va dans `.claude/settings.local.json` (non versionné) ou dans `~/.claude/settings.json`. Prévenir que ces skills ne seront plus disponibles dans ce projet.
   - Option, à signaler sans l'imposer : `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` interdit toute commande en arrière-plan dans la session, sous-agents compris. Il n'existe pas de réglage propre à un seul agent. C'est utile si des agents partent en arrière-plan malgré leur consigne.

2. **Contrôle rapide.** Copie `${CLAUDE_PLUGIN_ROOT}/scripts/controle_rapide.py` vers `.claude/cost-kit/controle_rapide.py`, puis adapte la liste `COMMANDES` au projet : lint, format, typage, règles d'architecture. Le tout doit tenir en une dizaine de secondes, jamais la suite de tests complète. L'agent `dev-story` le lance avant son rapport.

3. **Commandes du projet.** Si le dépôt n'a ni `CLAUDE.md` ni `AGENTS.md` indiquant les commandes de test et de lint, propose d'en ajouter quelques lignes. Les agents les y cherchent.

4. **Enchaînement des agents.** Explique à l'utilisateur comment l'orchestrateur (la session principale) doit procéder pour chaque story, avec un appel bloquant à chaque fois :
   1. `agent-cost-kit:dev-story` (Sonnet) implémente et commite dans un worktree ;
   2. `agent-cost-kit:second-avis` (Haiku, lecture seule, environ 0,03 $) relit le diff ;
   3. `agent-cost-kit:reviewer` (Opus) relit le diff, avec la liste du second avis, puis corrige et consigne ;
   4. l'orchestrateur intègre.

   Pour un run autonome sur plusieurs stories : modèle d'état `${CLAUDE_PLUGIN_ROOT}/modeles/run-autonome.md`, fusion de la file de PR par `scripts/file_prs.py`, pièges dans `docs/pieges-runs.md`.

   Pour les recherches dans le dépôt, utiliser `agent-cost-kit:lookup` (Haiku), plutôt que de lire soi-même.

5. **Vérification.** Lance `claude plugin validate` si disponible. Rappelle à l'utilisateur de redémarrer Claude Code, car les agents et les réglages ne se chargent qu'au démarrage, puis de vérifier l'installation : `claude plugin list` doit montrer `agent-cost-kit` activé, et la question « Quels types d'agents peux-tu lancer ? », posée dans une nouvelle session, doit faire apparaître `agent-cost-kit:dev-story`, `second-avis`, `reviewer` et `lookup`. Ne pas renvoyer vers `/agents` : cet assistant a été retiré de Claude Code. `claude agents` ne convient pas non plus, car il gère les agents en arrière-plan et ne liste pas les définitions.

6. **Mesure.** Explique la commande `/agent-cost-kit:mesurer-couts` (ou `uv run --no-project python ${CLAUDE_PLUGIN_ROOT}/scripts/mesurer_couts.py --projet .`). Elle calcule le coût réel de chaque agent et de chaque story depuis les transcriptions locales, sans aucun appel d'API. Conseille une mesure de départ sur 3 à 5 stories avant tout changement de méthode, puis la même mesure après.

Termine par un récapitulatif de 5 lignes au plus : ce qui a été écrit, ce qui a été refusé, et la prochaine étape.
