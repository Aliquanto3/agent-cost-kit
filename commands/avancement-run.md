---
description: Avancement d'un run autonome BMAD, à la demande : par epic, par vague et par story (terminé, en cours avec étape et pourcentage, à faire), rythme observé, estimation de l'heure de fin des développements, alertes (bloquées, attente humaine, éligibles non lancées).
argument-hint: "[chemin du projet] [--json]"
allowed-tools: Bash(python:*), Bash(uv run:*), Read
---

Lance le script d'avancement sur le projet courant (ou celui donné en argument) :

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/avancement_run.py" . $ARGUMENTS
```

Si `python` n'est pas dans le PATH, utilise `uv run python …` ou `.venv/Scripts/python`. Le script lit `_bmad-output/implementation-artifacts/sprint-status.yaml`, `run-autonome.md` (périmètre, vagues, journal) et `git log` ; il ne modifie rien.

Affiche le rapport tel quel, sans le recopier à la main ni le recalculer. Ajoute ensuite, en 6 lignes au plus, seulement ce qui exige du jugement :
1. le risque principal pour la date de fin (chemin critique, story pivot en retard, CI rouge, reprise Opus) ;
2. ce qui bloque ou bloquera, et ce qui revient à Anaël (étapes humaines `mixte`/`humaine`, décisions en attente, vérifications sur poste réel) ;
3. si un créneau libre est mal employé (story éligible non lancée) ;
4. si l'estimation est peu fiable : heures du journal surtout interpolées, moins de 5 stories mesurées.

Convention pour une estimation fiable : chaque ligne du journal de `run-autonome.md` porte date et heure, `- AAAA-MM-JJ HH:MM · story · étape · résultat · commit`. Les anciennes lignes sans heure restent lues (heure du commit « suivi du run … fusionnée », puis du commit cité, puis interpolation), mais avec moins de précision. Si les dernières lignes n'ont pas d'heure, dis-le et rappelle la convention.

N'invente aucune donnée absente du rapport.
