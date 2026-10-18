---
description: Calcule le coût réel des agents Claude Code du projet courant depuis les transcriptions locales (par agent, par story, avec pic de contexte, appels, expirations du cache, contrefactuel du TTL et empreinte environnementale estimée selon EcoLogits).
argument-hint: "[--session <préfixe>] [--filtre <motif>] [--out <dossier>]"
allowed-tools: Bash(python:*), Bash(uv run:*), Read
---

Lance le script de mesure sur le projet courant, puis commente le résultat :

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/mesurer_couts.py" --projet . $ARGUMENTS
```

Si `python` n'est pas dans le PATH, utilise l'interpréteur du projet (`uv run python …` ou `.venv/Scripts/python`).

Lis ensuite `mesures-couts/resume.md` et donne en 12 lignes au plus :
1. le coût total, et la part des sessions principales ;
2. le coût médian d'une story (arbre d'agents), ses appels et son pic de contexte médians ;
3. les expirations médianes par agent, et si le TTL d'une heure serait rentable (il l'est seulement à partir d'environ 1 expiration par agent) ;
4. le contexte médian du premier appel des sous-agents (au-dessus de 40 k, chercher les skills et serveurs MCP superflus) ;
5. les trois agents les plus chers, avec ce qui les distingue (appels, pic, modèle) ;
6. l'empreinte totale en fourchette (gCO2e, Wh, litres d'eau), la part du modèle le plus émetteur, et un rappel : seule la sortie compte dans EcoLogits (le cache n'a pas d'impact), la réflexion masquée n'est pas comptée, c'est une borne basse.

Ne recopie aucun contenu de transcription.
