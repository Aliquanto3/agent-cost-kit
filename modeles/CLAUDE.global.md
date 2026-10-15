## Coût de développement (agent-cost-kit)
Réduire au minimum le coût de développement avec Claude Code, sans baisser la qualité du code :
- La session principale orchestre, elle code peu. Par story : `agent-cost-kit:dev-story` (Sonnet) → `agent-cost-kit:second-avis` (Haiku) → `agent-cost-kit:reviewer` (Opus, avec la liste du second avis) → intégration. Appels bloquants, une passe de revue.
- Pas d'imbrication : un sous-agent ne lance pas de sous-agent. Pas de workflow multi-agents sans demande explicite.
- Recherches et résumés de logs : `agent-cost-kit:lookup` (Haiku) plutôt que lire soi-même de gros fichiers. Projet Python avec le plugin `pyright-lsp` : navigation par symbole (outil LSP) plutôt que recherche textuelle.
- Effort `medium` par défaut ; monter l'effort avant de changer de modèle ; `high` seulement pour les cas de bord que les tests n'attrapent pas.
- Contexte court : lire des extraits ciblés, tests ciblés pendant le travail et suite complète une fois à la fin, pas de relecture d'un fichier qu'on vient d'éditer.
- Garder `CLAUDE.md` et `MEMORY.md` courts : ils sont relus à chaque appel. L'historique des lots terminés va dans un `archive/` non indexé.
- Proposer `/clear` (après `/rename`) entre deux tâches sans lien : `/clear` ne coûte rien, `/compact` relit tout le contexte.
- Sorties de tests et de logs courtes (`pytest -q --tb=short`, filtrer les erreurs) ; préférer une CLI (`gh`, `git`) à un serveur MCP.
- Tâche complexe ou ambiguë : plan d'abord, validé avant d'écrire du code, pour éviter les reprises.
- Pas de fast mode (`/fast`, facturé en premium) sans demande.
- Ne pas poser `subagentPromptCacheTtl: "1h"` sans mesure (`/agent-cost-kit:mesurer-couts`) montrant au moins une expiration par agent.
- Signaler spontanément toute piste d'économie repérée (réglage, contexte fixe, enchaînement), avec le gain estimé.

### Premier passage dans un projet
Si `.claude/cost-kit/` est absent du dépôt, proposer en une fois, avant le premier développement :
1. `/cost-kit-install` (contrôle rapide adapté, commandes de lint et de test dans `CLAUDE.md`) ;
2. si le projet a déjà un historique Claude Code, une mesure de départ (`/agent-cost-kit:mesurer-couts`), consignée en mémoire du projet ;
3. un `CLAUDE.md` court (moins de 200 lignes) ; le détail des workflows va dans des skills.
