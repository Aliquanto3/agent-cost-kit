# Pièges vus en run autonome

[← README](../README.md)

Les limites de l'orchestration sont dans [amélioration continue](amelioration-continue.md). Ici, les pièges du code et de la CI.

| Piège | Réponse |
|---|---|
| Tests à seuil de temps et E2E instables sous charge (runs parallèles). | Les relancer seuls, une fois. S'ils passent, ce n'est pas la story ; sinon, c'est un vrai échec. |
| Extension SQLite absente sur la CI macOS (`setup-python` sans `enable_load_extension`). | Repli testé dans le code, tests marqués d'un marqueur de saut (`needs_vec`), valeurs attendues qui suivent la disponibilité réelle. |
| `smtplib.SMTP` appelle `socket.getfqdn()`, lent sur la CI macOS. | Fixer `local_hostname` à la construction. |
| Push refusé passagèrement. | Comparer `main..origin/main` avant de forcer : si la branche principale a bougé, rebaser, sinon relancer. Jamais de `--force` à l'aveugle. |
| `python` nu ouvre l'alias du Microsoft Store sous Windows. | `uv run python`. |
| Faux fichier de plusieurs Gio par `f.truncate(size)` : sous NTFS, creux seulement avec le drapeau sparse, et `truncate` coûte 4,3 s pour 5 Gio (tests de 11 à 33 s en CI Windows, WaveStack 2026-10-25). | FSCTL_SET_SPARSE, puis `seek(size - 1)` et un octet écrit (moins de 10 ms) ; aide `make_sparse` dans [CI découpée](ci-run-autonome.md). Un test lent sous Windows seulement : suspecter une opération système. |
| Workflow GitHub avec une clé en double (`group:` deux fois dans la matrice) : rejeté sans lancer de job (« workflow file issue »), alors que PyYAML `safe_load` l'accepte en silence. | actionlint, ou un chargeur YAML qui refuse les doublons. |
| `upload-artifact` v4 (depuis 4.4) ignore les fichiers cachés : « No valid artifacts found » pour un fichier dont le nom commence par un point. | Nom sans point, ou `include-hidden-files: true`. |
| Sous-agent (reviewer) qui laisse une commande heredoc bloquée sur stdin en arrière-plan. | L'orchestrateur l'arrête par `TaskStop`. Consigne : aucune commande en arrière-plan, heredoc en premier plan seulement. |
| `gh pr merge` échoue sur le réseau (TLS handshake timeout) et le journal note quand même une fusion (« OPEN null »). | Journaliser `fusion` seulement après avoir lu `MERGED` ; utiliser `scripts/file_prs.py`, qui le vérifie. |
