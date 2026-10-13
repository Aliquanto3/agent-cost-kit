---
name: cost-kit-install
description: Installe le setup économe de agent-cost-kit dans le projet courant - propose les réglages de settings.json (profondeur d'imbrication, TTL du cache des sous-agents, skills claude.ai), copie le modèle de contrôle rapide, explique l'enchaînement des agents et vérifie l'installation. À invoquer avec "install cost kit", "installer le kit de coût" ou /cost-kit-install.
---

Tu installes le kit dans le dépôt courant. Procède dans l'ordre, et demande confirmation avant chaque écriture dans `.claude/`.

1. **Réglages recommandés.** Lis `.claude/settings.json` s'il existe. Propose d'y fusionner ce bloc, en expliquant chaque ligne :

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

   Pour les recherches dans le dépôt, utiliser `agent-cost-kit:lookup` (Haiku), plutôt que de lire soi-même.

5. **Vérification.** Lance `claude plugin validate` si disponible. Rappelle à l'utilisateur de redémarrer Claude Code, car les agents et les réglages ne se chargent qu'au démarrage, puis de vérifier avec `/agents`.

6. **Mesure.** Explique la commande `/agent-cost-kit:mesurer-couts` (ou `python ${CLAUDE_PLUGIN_ROOT}/scripts/mesurer_couts.py --projet .`). Elle calcule le coût réel de chaque agent et de chaque story depuis les transcriptions locales, sans aucun appel d'API. Conseille une mesure de départ sur 3 à 5 stories avant tout changement de méthode, puis la même mesure après.

Termine par un récapitulatif de 5 lignes au plus : ce qui a été écrit, ce qui a été refusé, et la prochaine étape.
