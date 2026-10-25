---
name: essai-outil
description: "Guide l'essai encadré d'un outil du catalogue docs/experimental.md : lecture avant installation, SkillSpector, mesure du contexte, installation au niveau projet, protocole, retour écrit dans mesures/essais/. Invocation manuelle seulement : « essai outil <nom> », « essayer <nom> » ou /agent-cost-kit:essai-outil."
disable-model-invocation: true
---

Tu guides Anaël dans l'essai d'un outil du catalogue du kit (expérimental). Rien ne s'installe sans sa confirmation, et tu ne touches jamais `~/.claude/settings.json`. Procède dans l'ordre.

1. **Fiche.** Retrouve l'outil demandé dans `${CLAUDE_PLUGIN_ROOT}/docs/experimental.md`. S'il n'y figure pas, refuse l'essai ou propose d'abord d'ajouter sa fiche (dépôt, commit de 40 caractères, licence, protocole, critère de sortie). Relis la règle d'essai en tête du catalogue.
2. **Récupération sans exécution.** Récupère le dépôt au commit épinglé de la fiche dans un dossier neuf et vide, hors du dépôt courant (dans le dossier temporaire). Ne lance aucun script, aucune installation. Pour un outil natif, passe aux étapes 5 et 6.
3. **Lecture.** Lis en entier `SKILL.md`, les hooks, les scripts, les manifestes et `.mcp.json`. Résume à Anaël ce que l'outil installe et exécute : hooks, accès réseau, télémétrie, processus, ports.
4. **SkillSpector.** Passe-le en `--no-llm` s'il est disponible, sinon dis qu'il manque. Rappelle qu'un scan propre ne prouve rien et qu'un scan bruyant (faux positifs) oblige seulement à lire.
5. **Installation mesurée.** Mesure le contexte avant (`/context` ou `claude plugin details`). Avec la confirmation d'Anaël, installe **au niveau projet** (jamais au niveau utilisateur), à la version épinglée. Mesure après.
6. **Essai.** Guide Anaël selon le protocole de la fiche, étape par étape, en notant ce qu'il faut observer.
7. **Retour.** Écris `mesures/essais/AAAA-MM-JJ-<outil>.md` (date prise par `date`) avec ce gabarit :

   ```
   # Essai <outil>, AAAA-MM-JJ
   - Outil et commit :
   - Projet :
   - Contexte avant / après :
   - Ce qui a été fait :
   - Observations :
   - Verdict proposé : passer en stable | garder à la demande | écarter | à refaire
   - Pourquoi :
   ```
8. **Nettoyage.** Si le verdict n'est ni « passer en stable » ni « garder à la demande », propose la désinstallation et fais-la sur confirmation.
