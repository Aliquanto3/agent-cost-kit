---
description: "Synthèse d'avancement d'un run autonome BMAD pour un dirigeant : taux global, heure de fin estimée et météo, points à savoir, tableau par epic. Détails de l'estimation avec --detail, tableau par story avec --stories."
argument-hint: "[chemin du projet] [--detail] [--stories] [--json]"
allowed-tools: Bash(python:*), Bash(uv run:*), Read
---

Lance le script d'avancement sur le projet courant (ou celui donné en argument) :

```
uv run --no-project python "${CLAUDE_PLUGIN_ROOT}/scripts/avancement_run.py" . $ARGUMENTS
```

Sans `uv`, lance `python …` (`python3` hors Windows) ; `--no-project` évite que `uv` synchronise l'environnement du projet courant. Le script lit `_bmad-output/implementation-artifacts/sprint-status.yaml`, `run-autonome.md` (périmètre, vagues, journal), `planning-artifacts/epics.md` (titres) et `git log` ; il ne modifie rien.

Le rapport tient déjà lieu de synthèse : taux d'avancement, fin estimée (centrale et fourchette), météo (🟢 dans les temps, 🟡 vigilance, 🔴 bloqué), « Ce qu'il faut savoir », tableau par epic (le détail par story seulement avec `--stories`, ou sans niveau de consolidation). La sortie d'une commande shell est repliée dans l'interface de Claude Code : l'utilisateur ne la voit pas. Reproduis donc le rapport Markdown **intégralement dans ta réponse**, tel que le script l'a produit, sans le modifier, le recalculer ni refaire de tableau.

Ensuite, seulement si tu as un jugement qui n'est pas déjà dans les puces « Ce qu'il faut savoir », ajoute au plus 3 puces sous le titre « Avis » : risque pour la date de fin (chemin critique, story pivot en retard, reprise en cas d'échec), étape humaine qui va bloquer, créneau libre mal employé. Sans jargon technique. S'il n'y a rien à ajouter, n'ajoute rien.

Convention pour une estimation fiable : chaque ligne du journal de `run-autonome.md` porte date et heure, `- AAAA-MM-JJ HH:MM · story · étape · résultat · commit` (étapes : `dev`, `second-avis`, `review`, `PR`, `fusion`, `CI`, `blocked`, `attente humaine`, `report`, `décision` ; `PR` : `- 2026-10-19 21:10 · 6.3 · PR · #104 ouverte · abc1234`). Une story n'est terminée que fusionnée. Les anciennes lignes sans heure restent lues (heure du commit « suivi du run … fusionnée », puis du commit cité, puis interpolation), avec moins de précision ; le rapport le signale. Si les dernières lignes n'ont pas d'heure, rappelle la convention.

N'invente aucune donnée absente du rapport.
