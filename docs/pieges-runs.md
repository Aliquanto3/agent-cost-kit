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
