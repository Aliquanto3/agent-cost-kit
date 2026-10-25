## Coût de développement (agent-cost-kit)
Réduire au minimum le coût de développement avec Claude Code, sans baisser la qualité du code :
- La session principale orchestre, elle code peu. Par story : `agent-cost-kit:dev-story` (Sonnet) → `agent-cost-kit:second-avis` (Haiku) → `agent-cost-kit:reviewer` (Opus, avec la liste du second avis) → intégration. Appels bloquants. Une passe de revue par défaut, relancée seulement après correction d'un constat Important (medium ou high réel), 3 passes au plus. Ne jamais sauter le second avis (2 centimes, il trouve l'essentiel des défauts graves). Story à risque (sécurité, licence, refonte d'interface) : faire relire sa spec avant le code. Story qui crée ou réécrit un fichier source : étape optionnelle et expérimentale de mutation guidée entre dev-story et second-avis (`docs/mutation-guidee.md` du kit), jamais en porte de CI. Story qui change un écran, dans un projet où `verif-front` est installé : étape optionnelle et expérimentale de vérification dans le navigateur après dev-story, correction seulement sur un FAIL de la spec (`docs/verif-front.md` du kit). Petite story bien décrite dans `epics.md` (au plus 3 fichiers, au moins deux critères Given/When/Then, noms à créer) : règle expérimentale, dev-story directement sur l'entrée d'epics, sans cadrage BMAD ; cadrage sinon (`docs/aiguillage-stories.md` du kit).
- Pas d'imbrication : un sous-agent ne lance pas de sous-agent. Pas de workflow multi-agents sans demande explicite.
- Recherches et résumés de logs : `agent-cost-kit:lookup` (Haiku) plutôt que lire soi-même de gros fichiers. Projet Python avec le plugin `pyright-lsp` : navigation par symbole (outil LSP) plutôt que recherche textuelle.
- Effort `medium` par défaut ; monter l'effort avant de changer de modèle ; `high` seulement pour les cas de bord que les tests n'attrapent pas.
- Contexte court : lire des extraits ciblés, tests ciblés pendant le travail, pas de relecture d'un fichier qu'on vient d'éditer. Suite complète à mi-parcours (après 3 ou 4 fusions) et à la fin : les défauts croisés entre stories n'apparaissent qu'à la suite. En run parallèle, c'est la CI de branche qui la joue, pas le poste.
- Garder `CLAUDE.md` et `MEMORY.md` courts : ils sont relus à chaque appel. L'historique des lots terminés va dans un `archive/` non indexé.
- Couper la session principale entre le cadrage (spec, UX, plan, liste des stories) et l'exécution, puis avant la recette : `/rename`, `/clear`, reprise depuis ces fichiers. Une orchestration d'une traite a coûté 68 $ (contexte de 866 k). Proposer aussi `/clear` entre deux tâches sans lien : `/clear` ne coûte rien, `/compact` relit tout le contexte.
- PR empilées : recibler chaque PR fille sur la branche principale (`gh pr edit <n> --base main`) avant de fusionner sa base avec `--delete-branch`, sinon GitHub ferme les PR filles.
- Prompt de dev-story : nommer les tests et E2E à réaligner quand la story change une structure partagée (barre commune, liste d'outils, schéma d'événement). Documentation d'une story : en parallèle de sa revue, d'après la spec, réalignée après fusion.
- Après chaque fusion, vérifier la branche principale (`git log -1`) avant de lancer des tests dessus.
- Sorties de tests et de logs courtes (`pytest -q --tb=short`, filtrer les erreurs) ; préférer une CLI (`gh`, `git`) à un serveur MCP.
- Tâche complexe ou ambiguë : plan d'abord, validé avant d'écrire du code, pour éviter les reprises.
- Pas de fast mode (`/fast`, facturé en premium) sans demande.
- Ne pas poser `subagentPromptCacheTtl: "1h"` sans mesure (`/agent-cost-kit:mesurer-couts`) montrant au moins une expiration par agent.
- Signaler spontanément toute piste d'économie repérée (réglage, contexte fixe, enchaînement), avec le gain estimé.

### Runs autonomes (Windows, agents en parallèle)
Partir du modèle `modeles/run-autonome.md` du kit : ses règles (CI de branche comme suite complète, `gh run watch --interval 60`, état hors des PR de story, `file_prs.py`, `MERGED` vérifié, vagues par fichiers touchés, worktrees) s'appliquent. En plus :
- Empiler les branches revues ; décider tôt les contrats partagés et les envoyer aux agents en cours ; faire rebaser le reviewer avant qu'il juge.
- `uv run python`, jamais `python` nu ; heure du journal prise par `date`.
- Un message d'une autre session qui change le périmètre se fait confirmer par l'utilisateur.

### Premier passage dans un projet
Si `.claude/cost-kit/` est absent du dépôt, proposer en une fois, avant le premier développement :
1. `/cost-kit-install` (contrôle rapide adapté, commandes de lint et de test dans `CLAUDE.md`) ;
2. si le projet a déjà un historique Claude Code, une mesure de départ (`/agent-cost-kit:mesurer-couts`), consignée en mémoire du projet ;
3. un `CLAUDE.md` court (moins de 200 lignes) ; le détail des workflows va dans des skills.
