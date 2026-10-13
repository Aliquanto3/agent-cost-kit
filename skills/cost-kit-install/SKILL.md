---
name: cost-kit-install
description: Installe le setup économe de agent-cost-kit dans le projet courant - propose les réglages de settings.json (TTL du cache des sous-agents, profondeur d'imbrication, skills claude.ai), copie le modèle de contrôle rapide et vérifie les agents. À invoquer avec "install cost kit", "installer le kit de coût" ou /cost-kit-install.
---

Tu installes le kit dans le dépôt courant. Procède dans l'ordre, et demande confirmation avant chaque écriture dans `.claude/`.

1. **Réglages recommandés.** Lis `.claude/settings.json` s'il existe. Propose d'y fusionner ce bloc, en expliquant chaque ligne :

   ```json
   {
     "env": { "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1" }
   }
   ```

   - `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH = 1` : un sous-agent ne peut pas lancer de sous-agents. Mesuré sur trois projets, l'agent intermédiaire qui relance des agents pèse 36 à 47 % du coût d'une story.
   - **Ne pas** poser `subagentPromptCacheTtl: "1h"` : sur trois projets, 78 à 86 % des sous-agents n'ont aucune expiration de cache, et le TTL d'une heure leur coûte 28 à 30 % de plus. Il ne devient rentable qu'à partir d'une expiration par agent. Le proposer seulement si le script de mesure montre une médiane d'au moins 1 expiration par agent.
   - Dans `.claude/settings.local.json` (non versionné) ou dans les réglages utilisateur : `"syncClaudeAiSkills": false`, pour que les skills du compte claude.ai ne soient pas rechargés dans chaque sous-agent (gain d'environ 5 k tokens par appel, soit 2 % du coût d'une story).

2. **Contrôle rapide.** Copie `${CLAUDE_PLUGIN_ROOT}/scripts/controle_rapide.py` vers `.claude/cost-kit/controle_rapide.py`, puis adapte la liste `COMMANDES` au projet (lint, format, typage, règles d'architecture : environ 10 secondes, jamais la suite de tests complète). L'agent `dev-story` le lance avant son rapport.

3. **Vérification.** Lance `claude plugin validate` si disponible, puis rappelle à l'utilisateur de redémarrer Claude Code (les agents et réglages ne se chargent qu'au démarrage) et de vérifier avec `/agents`.

4. **Mesure.** Explique la commande `/agent-cost-kit:mesurer-couts` (ou `python ${CLAUDE_PLUGIN_ROOT}/scripts/mesurer_couts.py --projet .`) : elle calcule le coût réel de chaque agent et de chaque story depuis les transcriptions locales, sans aucun appel d'API. Conseille une mesure de départ sur 3 à 5 stories avant tout changement de méthode, puis la même mesure après.

Termine par un récapitulatif de 5 lignes au plus : ce qui a été écrit, ce qui a été refusé, et la prochaine étape.
