# Spec 0.15.0 : ménage de clôture d'un run

Source : point 28 de `docs/amelioration-continue.md` (`git show d952e7f`). Livré : `scripts/menage_run.py`, doc `docs/menage-run.md`, étape `ménage` dans `scripts/avancement_run.py`. Principe : l'outil supprime des données, donc « dans le doute, garder ».

## Revue

### Passe 1 (2026-10-27, SHA revu 39a17f8)

Branche à jour de `origin/master` (70975b8, aucun écart). Liste du second avis (Haiku) reprise point par point, chaque défaut reproduit avant correction (git 2.55 sur Windows).

- Important · high · second avis 1 · corrigé · une PR MERGED comptait quelle que soit sa base : une PR empilée fusionnée dans une branche de feature menait au `-D` d'une branche absente de main. `baseRefName` demandé à gh et comparé à la branche par défaut ; PR #10 empilée ajoutée aux fixtures (`unmerged` reste gardée).
- Important · high · second avis 2 · corrigé · reproduit : `git worktree remove` sans `-f` efface un `.env` ignoré. Un worktree avec des fichiers ignorés hors de la liste des régénérables (`git ls-files --others --ignored --exclude-standard --directory`) est gardé, le motif nomme les trois premiers ; test `.env` gardé, `__pycache__` et `.venv` seuls retiré.
- Important · medium · second avis 3 · corrigé · sans gh, `--appliquer` supprimait une branche à PR ouverte (et le test l'exigeait). Sans gh, branches locales et distantes gardées avec le motif « gh indisponible, PR ouvertes non vérifiables » ; worktrees et verrous toujours traités. Test et doc corrigés.
- Important · medium · second avis 4 · corrigé · `push --delete` groupé sans garde. Suppression par branche avec `--force-with-lease=refs/heads/<b>:<sha>` (vérifié sur dépôt nu : refus « stale info » si la branche a bougé) ; refus rapporté, code 1 ; test d'une distante avancée depuis un autre clone.
- Nit · low · second avis 5 · corrigé · une liste de PR qui atteint `--limit 1000` vaut gh indisponible (même effet que le point 3) ; test avec limite abaissée.
- Nit · low · second avis 6 · corrigé · `pid_vivant` Windows : `WinDLL(use_last_error=True)`, `restype`/`argtypes` posés ; seul ERROR_INVALID_PARAMETER (87) vaut « PID inexistant », tout autre échec d'`OpenProcess` ou de `GetExitCodeProcess` vaut vivant ; test sur le PID courant et sur un PID terminé.
- Nit · low · second avis 7 · gardé · le reflog lu pour une distante est celui de la branche locale homonyme : protection en plus, commentaire d'une ligne ajouté.
- Nit · low · second avis 8 · corrigé · l'assertion en `or` est remplacée par un `re.fullmatch` sur la ligne de journal complète.
- Nit · low · second avis 9 · corrigé · `docs/menage-run.md`, docstring du script et entrée 0.15.0 du `CHANGELOG.md` alignés sur 1 à 5.
- Nit · low · reviewer · rejeté · pyright signale `reconfigure` sur `TextIO` et un code inatteignable après la branche Windows de `pid_vivant` : faux positifs (garde `try/except AttributeError` comme dans `file_prs.py` et `controle_rapide.py` ; branche POSIX inatteignable seulement pour l'analyse sur Windows).
- Nit · low · reviewer · reporté · `exclusion` et `contenu` parcourent toutes les PR pour chaque branche : O(branches × PR), au plus 1 000 PR, quelques centaines de milliers de comparaisons de dict en un seul passage, sans impact mesurable. Complexité : 1 constat, non corrigé.
- Reporté · premier usage réel contre `gh` (vraie sortie `gh pr list --json baseRefName`) et sur un vrai dépôt de run : lancer d'abord en simulation et relire les motifs avant `--appliquer`.
