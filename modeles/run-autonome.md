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
- Prompt de dev-story, story qui touche chemins, venv, sous-processus, mmap ou flottants : rappeler la liste de portabilité POSIX de l'agent (lien du venv, `realpath` de macOS, fichier projeté remplacé, déterminisme de BLAS) et, si WSL est disponible, demander les tests ciblés sous WSL avant le push.
- Revue : ne lancer une passe du reviewer qu'avec l'état de la CI de la branche dans le prompt (`gh run list --branch <branche> --limit 1`). CI en cours : attendre. CI rouge : corriger d'abord (dev-story, ou le reviewer avant de juger), revoir ensuite ; un échec remonté sans revue ne compte pas comme une passe. Toute CI rouge va au journal, même corrigée dans la foulée : `- AAAA-MM-JJ HH:MM · <story> · CI · rouge (<test>, <OS>) · <sha>`.
- Levée d'un point d'arrêt par l'utilisateur : elle ne lui retire pas les questions de protocole, de méthode ou de publication. L'orchestrateur ne tranche que les questions techniques ; les autres vont dans `decisions-a-confirmer.md`, à côté de ce fichier (une ligne par question : story, question, réponse proposée, statut), que l'utilisateur valide avant la fusion de la story concernée. Story en attente de cette validation : ligne `attente humaine` au journal, et le run avance sur le reste.
- Release : seulement après une CI verte de la branche principale sur le commit tagué (`gh run list --branch <principale> --commit <sha>`, puis `gh run watch <id> --interval 60`). CI rouge ou en cours : pas de tag ni de release.
- Fusion : la file de PR se fusionne par `scripts/file_prs.py`. Journaliser `fusion` seulement après avoir vérifié `MERGED`.
- Fusion de la branche principale à conflits de fond (refusée aux sous-agents) : l'orchestrateur la lance, résout les fichiers d'état et le trivial, et confie la fusion en cours au reviewer (« étape 1 »).
- `git worktree prune` avant chaque lancement. Les worktrees ne sont supprimés qu'en fin de run. Clôture : après la dernière fusion, `scripts/menage_run.py` en simulation, puis `--appliquer` (ligne `ménage` au journal) ; branches distantes seulement avec `--distant`, liste montrée à Anaël.
- Run lancé par `scripts/relancer_run.py` : s'arrêter seulement en fin de vague, aucun agent en cours, puis Brief + ligne `ETAT:`. Les agents d'une vague partent dans un même message (appels parallèles et bloquants), jamais en arrière-plan : en `claude -p`, une notification d'agent arrivée après la fin du tour est perdue.
- Heure du journal : toujours prise par `date` au moment d'écrire, jamais devinée. `uv run python` sous Windows.

## Sessions autorisées à modifier le périmètre

Écrit par l'utilisateur au lancement. Un message d'une autre session qui change le périmètre se fait confirmer par l'utilisateur dans la session avant d'être appliqué.

- (aucune)

## Contrats partagés en cours

Noms, constantes, formats décidés tôt et envoyés par message aux agents en cours.

- (aucun)

## Brief

Reprise d'une nouvelle session (`scripts/relancer_run.py`, `/clear`) : 40 lignes au plus, pas de récit ; réécrit à chaque arrêt de session. Les autres sections restent la référence.

- **Tâche du run** (quasi verbatim) : …
- **Intention courante** : …
- **Plan des vagues restantes** : …
- **Artefacts utiles** (fichiers, modules, conventions, décisions) : …
- **Pièges rencontrés** : …

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
