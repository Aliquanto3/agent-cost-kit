# Amélioration continue : limites vues en run autonome

Points relevés pendant les runs autonomes, avec leur contournement et ce qu'il faudrait changer dans le kit. Chaque entrée porte la source (projet et date). Une entrée traitée passe dans le `CHANGELOG` et sort de cette liste.

Traités en 0.7.0 (voir le `CHANGELOG`) : points 1 à 22, 24 et 25 des runs WaveDevSecOps et wavelocalai v2 (18 et 19 octobre 2026). Les points 6 et 8 n'appelaient pas de changement de code : le 6 figure dans `docs/pieges-runs.md`, le 8 tombe avec le 1. Leur détail (limite, contournement, source) reste lisible dans l'historique : `git show 362165f:docs/amelioration-continue.md`.

## Ouverts

| # | Limite constatée | Contournement appliqué | Amélioration proposée pour le kit |
|---|---|---|---|
| 23 | CI goulot : 16 jobs par PR (3 OS × 2 Python × v1 et v2, plus E2E), puis 16 sur master à chaque fusion ; 5 runners macOS au plus sur un dépôt public. | CI allégée (accord d'Anaël, PR #100) : job « Fichiers touchés », v1 seulement si une PR la touche, PR d'état sans tests, `concurrency` qui annule le run précédent d'une PR ; master toujours complet. | Modèle de workflow « CI de run autonome » dans le kit, proposé par `cost-kit-install`. |
| 26 | `scripts/file_prs.py` n'a été essayé contre le vrai `gh` qu'en lecture (`--a-sec` sur une PR fusionnée et une PR ouverte, 2026-10-19). Fusion et relance réelles testées seulement avec un faux `gh`. | Premier usage en run : surveiller la première fusion et la première relance. | Consigner ici le résultat du premier run réel, puis retirer l'entrée. |
| 26 | `avancement-run` 0.7.1 garde un « contrôle automatique rouge » (météo 🟡) quand la ligne du journal dit « CI · rouge (…) ; corrigé, poussé » : seul le mot « rouge » compte, et l'orchestrateur n'écrit jamais de ligne « CI verte » après la relance. | L'orchestrateur écrit désormais une ligne `CI · verte` après chaque relance réussie. | Lever l'alerte si la même ligne dit « corrigé » ou « relancé », si une ligne `CI · verte` ou `fusion` de la même story suit, ou si la PR citée est fusionnée. |
| 27 | Les préversions (`2.0.0aN` posées dans le manifeste en fin d'epic) ne sont pas suivies : un epic est « terminé » alors que sa préversion n'est pas posée. | Suivi à la main dans le fichier d'état du run. | Lire une étape `version` du journal (« 2.0.0a7 posée ») et afficher, par epic, la préversion attendue et son état. |
