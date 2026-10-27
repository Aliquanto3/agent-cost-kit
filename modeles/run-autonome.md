# Run autonome — plan et état

Fichier d'état de l'orchestrateur, à relire en premier après chaque `/clear`. Lu par `/agent-cost-kit:avancement-run`. À copier dans `_bmad-output/implementation-artifacts/run-autonome.md` (nom exact) avant la première story.

## Périmètre

| Périmètre | Epics | Note |
|---|---|---|
| Dans le run | Epics 1 à 3 | |
| Hors run | Epics 4 à 5 | raison |

Au plus 3 stories en développement à la fois, chacune dans son worktree.
Plafond global : 5 agents actifs à la fois sous Windows (développement, revue et rebase confondus).

## Règles

- Types : `dev` (dev-story → second-avis → reviewer → intégration), `mixte` (code par l'agent, puis « attente humaine »), `humaine` (jamais confiée à un agent). ★ = story pivot, dev-story sur Opus.
- Deux stories du même écran ou du même fichier partagé (textes, CSS, API, routes) ne vont jamais dans la même vague. Découper tôt ces fichiers.
- Fichiers d'état du run (ce fichier, sprint status) : jamais dans une PR de story. PR `chore/etat-run` à part. `.gitattributes` : `<chemin du fichier d'état> merge=union` (ajouts du journal) ; une ligne de table modifiée des deux côtés en ressort en double, à vérifier après la fusion.
- Suite complète : pas en local pendant un run parallèle, la CI de branche la joue et sert de porte de fusion. Attente : `gh run watch <id> --interval 60`.
- Fusion : la file de PR se fusionne par `scripts/file_prs.py`. Journaliser `fusion` seulement après avoir vérifié `MERGED`.
- Fusion de la branche principale à conflits de fond (refusée aux sous-agents) : l'orchestrateur la lance, résout les fichiers d'état et le trivial, et confie la fusion en cours au reviewer (« étape 1 »).
- `git worktree prune` avant chaque lancement. Les worktrees ne sont supprimés qu'en fin de run. Clôture : après la dernière fusion, `scripts/menage_run.py` en simulation, puis `--appliquer` (ligne `ménage` au journal) ; branches distantes seulement avec `--distant`, liste montrée à Anaël.
- Heure du journal : toujours prise par `date` au moment d'écrire, jamais devinée. `uv run python` sous Windows.

## Sessions autorisées à modifier le périmètre

Écrit par l'utilisateur au lancement. Un message d'une autre session qui change le périmètre se fait confirmer par l'utilisateur dans la session avant d'être appliqué.

- (aucune)

## Contrats partagés en cours

Noms, constantes, formats décidés tôt et envoyés par message aux agents en cours.

- (aucun)

## Sprint 1 — v0.1 (Epics 1 à 3)

| Vague | Stories en parallèle | Après | Fichiers ou écrans touchés |
|---|---|---|---|
| V0 | 1.1 ★ | — | `src/contrats.py` |
| V1 | 1.2 · 1.3 | 1.2 ← 1.1 ; 1.3 ← 1.1 | 1.2 `src/api/routes.py` ; 1.3 `src/web/accueil.html` |
| V2 | 1.4 (mixte) | 1.4 ← 1.1, 1.2, 1.3 | `docs/guide.md` |

« Après » ne lit que `x ← y` ou `Epics N à M` : une phrase libre (« toutes les stories ») ne crée aucune dépendance.

## Journal

Une ligne par étape : `- AAAA-MM-JJ HH:MM · story · étape · résultat · commit`. Étapes : `dev` (« lancé », puis « fini »), `second-avis`, `review`, `PR`, `fusion` (MERGED vérifié), `CI` (« rouge » si échec), `blocked`, `attente humaine`, `décision`, `report`, `ménage` (clôture, colonne story `run`). Une story est terminée quand sa PR est fusionnée.

- 2026-10-19 09:00 · 1.1 · dev · lancé (dev-story Opus, worktree) · —
- 2026-10-19 09:40 · 1.1 · dev · fini, 61 tests verts · abc1234
- 2026-10-19 09:45 · 1.1 · second-avis · 1 medium, 3 low · —
- 2026-10-19 10:05 · 1.1 · review · 1 medium corrigé · def5678
- 2026-10-19 10:10 · 1.1 · PR · #104 ouverte · def5678
- 2026-10-19 10:30 · 1.1 · CI · verte sur les trois OS · def5678
- 2026-10-19 10:35 · 1.1 · fusion · #104 fusionnée, MERGED vérifié · 0a1b2c3
