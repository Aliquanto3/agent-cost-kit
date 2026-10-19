# File de PR : `scripts/file_prs.py`

Fusionne des PR GitHub dans l'ordre, via la CLI `gh` (Python, bibliothèque standard).

```
python scripts/file_prs.py 104 105 106 [--repo OWNER/NOM] [--methode merge|squash|rebase] \
    [--supprimer-branche] [--intervalle 60] [--delai-max 60] [--json] [--a-sec]
```

Par PR : attend les contrôles, relance une fois les jobs en échec (`gh run rerun --failed`), vérifie `mergeable`, fusionne, puis vérifie `state == MERGED`. Une PR non fusionnable est sautée et la file continue. Sortie : une ligne par PR (`#104 fusionnée abc1234`, `#105 sautée : aucun contrôle (conflit ?)`, `#106 sautée : rouge après relance (job x)`) puis un résumé ; code retour 0 si tout est fusionné, 1 sinon. `--a-sec` n'appelle ni merge ni rerun.

## Pourquoi

Points 11, 15 et 24 de `amelioration-continue.md` : sondage espacé (60 s, jamais moins de 30 s) pour ne pas épuiser le quota de l'API ; liste de contrôles vide signalée (PR en conflit, CI non lancée) ; fusion jamais déclarée sans état `MERGED` ; un job instable relancé une fois sans bloquer la file.

## Conseil

Garder les fichiers d'état du run (journal, sprint status) hors des PR de story, dans une PR `chore/etat-run` à part : sinon chaque fusion met les autres branches en conflit, et une PR en conflit n'a pas de CI.
