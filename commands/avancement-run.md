---
description: Synthèse d'avancement d'un run autonome BMAD pour un dirigeant : taux global, heure de fin estimée et météo, points à savoir, tableau par epic, détail par story. Détails de l'estimation avec --detail.
argument-hint: "[chemin du projet] [--detail] [--json]"
allowed-tools: Bash(python:*), Bash(uv run:*), Read
---

Lance le script d'avancement sur le projet courant (ou celui donné en argument) :

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/avancement_run.py" . $ARGUMENTS
```

Si `python` n'est pas dans le PATH, utilise `uv run python …` ou `.venv/Scripts/python`. Le script lit `_bmad-output/implementation-artifacts/sprint-status.yaml`, `run-autonome.md` (périmètre, vagues, journal), `planning-artifacts/epics.md` (titres) et `git log` ; il ne modifie rien.

Le rapport tient déjà lieu de synthèse : taux d'avancement, fin estimée (centrale et fourchette), météo (🟢 dans les temps, 🟡 vigilance, 🔴 bloqué), « Ce qu'il faut savoir », tableau par epic, détail par story. Affiche-le tel quel, sans le recopier ni le recalculer, et sans refaire de tableau.

Ensuite, seulement si tu as un jugement qui n'est pas déjà dans les puces « Ce qu'il faut savoir », ajoute au plus 3 puces sous le titre « Avis » : risque pour la date de fin (chemin critique, story pivot en retard, reprise en cas d'échec), étape humaine qui va bloquer, créneau libre mal employé. Sans jargon technique. S'il n'y a rien à ajouter, n'ajoute rien.

Convention pour une estimation fiable : chaque ligne du journal de `run-autonome.md` porte date et heure, `- AAAA-MM-JJ HH:MM · story · étape · résultat · commit`. Les anciennes lignes sans heure restent lues (heure du commit « suivi du run … fusionnée », puis du commit cité, puis interpolation), avec moins de précision ; le rapport le signale. Si les dernières lignes n'ont pas d'heure, rappelle la convention.

N'invente aucune donnée absente du rapport.
