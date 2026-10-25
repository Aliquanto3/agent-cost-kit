# Run autonome — plan et état

Fichier d'état de l'orchestrateur, à relire en premier après chaque `/clear`. Lu par `/agent-cost-kit:avancement-run`. À copier dans `_bmad-output/implementation-artifacts/run-autonome.md` (nom exact) avant la première story.

## Périmètre

| Périmètre | Epics | Note |
|---|---|---|
| Dans le run | Epics 1 à 3 | |
| Hors run | Epics 4 à 5 | raison |

Au plus 3 stories en développement à la fois, chacune dans son worktree.
Plafond global : 5 agents actifs à la fois sous Windows (développement, revue et rebase confondus).
Une vague contient au plus autant de stories que le plafond de développements en parallèle : 17 stories dans une seule vague ont faussé l'estimation de fin de `avancement-run` (WaveStack, 2026-10-25).

## Règles

- Types : `dev` (dev-story → second-avis → reviewer → intégration), `mixte` (code par l'agent, puis « attente humaine »), `humaine` (jamais confiée à un agent). ★ = story pivot, dev-story sur Opus.
- Deux stories du même écran ou du même fichier partagé (textes, CSS, API, routes) ne vont jamais dans la même vague. Découper tôt ces fichiers. Avant de planifier un lot de plus de 5 stories sur le même écran, faire relever les fichiers touchés par chaque story (un agent `lookup`, une minute) : un fichier central bloque les stories d'architecture, et les stories d'onglet n'y touchent pas. Exemple : un fichier JS par onglet, enregistré via `registerTab`, contrat envoyé à l'agent qui crée les onglets pendant qu'il travaille ; le run passe d'une story à deux en parallèle.
- Fichiers d'état du run (ce fichier, sprint status) : jamais dans une PR de story. PR `chore/etat-run` à part. `.gitattributes` : `<chemin du fichier d'état> merge=union` (ajouts du journal) ; une ligne de table modifiée des deux côtés en ressort en double, à vérifier après la fusion.
- Suite complète : pas en local pendant un run parallèle, la CI de branche la joue et sert de porte de fusion. Attente : `gh run watch <id> --interval 60`.
- Fusion : toujours par `scripts/file_prs.py`, jamais un `gh pr merge` à la main ; il ne déclare une fusion qu'après avoir vu `MERGED`. Un échec réseau de `gh` n'est pas une fusion : journaliser `fusion` seulement après avoir vérifié `MERGED`.
- Limite d'usage de l'abonnement : sous cette limite, plus d'agents en parallèle ne fait pas gagner de temps (WaveStack : arrêt de 3 h 33, plus long que toute la CI de la nuit). Réduire les tokens par story ou changer de formule.
- Point de contrôle de spec en cours de story : écrire l'étape `décision`, pas `review` (qui compte la story à 90 %).
- Job de CI de plus de 10 min : le découper ([CI découpée](../docs/ci-run-autonome.md)).
- Fusion de la branche principale à conflits de fond (refusée aux sous-agents) : l'orchestrateur la lance, résout les fichiers d'état et le trivial, et confie la fusion en cours au reviewer (« étape 1 »).
- `git worktree prune` avant chaque lancement. Les worktrees ne sont supprimés qu'en fin de run.
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

Une ligne par étape : `- AAAA-MM-JJ HH:MM · story · étape · résultat · commit`. Étapes : `dev` (« lancé », puis « fini »), `second-avis`, `review`, `PR`, `fusion` (MERGED vérifié), `CI` (« rouge » si échec), `blocked`, `attente humaine`, `décision`, `report`. Une story est terminée quand sa PR est fusionnée.

- 2026-10-19 09:00 · 1.1 · dev · lancé (dev-story Opus, worktree) · —
- 2026-10-19 09:40 · 1.1 · dev · fini, 61 tests verts · abc1234
- 2026-10-19 09:45 · 1.1 · second-avis · 1 medium, 3 low · —
- 2026-10-19 10:05 · 1.1 · review · 1 medium corrigé · def5678
- 2026-10-19 10:10 · 1.1 · PR · #104 ouverte · def5678
- 2026-10-19 10:30 · 1.1 · CI · verte sur les trois OS · def5678
- 2026-10-19 10:35 · 1.1 · fusion · #104 fusionnée, MERGED vérifié · 0a1b2c3
