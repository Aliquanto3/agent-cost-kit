# Vérification front (expérimental)

Un sous-agent `verif-front` ouvre l'application dans un vrai navigateur et vérifie les critères d'acceptation d'une story front. **Expérimental et optionnel** : la chaîne par défaut (dev-story, second-avis, reviewer) ne change pas pour une story qui n'est pas front, ni pour un projet qui n'a pas installé le sous-agent.

## Pourquoi

Test [T12](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T12-front) de la veille (stories 7.13 à 7.16 d'usine-migration-jira-demo) :
- un sous-agent Sonnet (effort medium) qui ne voit que le navigateur (Playwright MCP) trouve **22 défauts d'interface semés sur 25** (88 %, intervalle de Wilson 70 à 96 %), que pytest (0 sur 25) et axe-core (0 sur 26) ne voient pas ;
- **0 faux positif** sur 8 exécutions de versions sans défaut ;
- **0,141 $ et 60 s** par vérification (maximum 0,299 $), soit 9 à 13 % du coût d'un développement Sonnet ;
- les 3 défauts manqués : contrôles du DOM sans relecture du rendu visuel (2), ordre d'enchaînement des étapes (1).

Ce qu'il n'apporte pas : dans la boucle de développement (6 cellules), **aucun gain mesuré**. L'agent tenait déjà les critères, et une correction systématique par reprise de session coûte 0,6 à 1,6 $ même quand le rapport est entièrement PASS. C'est un filet de sécurité, pas un accélérateur.

## Pourquoi un modèle et pas un agent du plugin

Selon la doc de Claude Code (page « Subagents »), les sous-agents d'un plugin ignorent les champs `hooks`, `mcpServers` et `permissionMode`. Un MCP déclaré dans le `.mcp.json` du plugin s'appliquerait à toutes les sessions de tous les projets. Le sous-agent est donc un **modèle** : `modeles/agents/verif-front.md`. `cost-kit-install` le copie, sur confirmation, dans `.claude/agents/` d'un projet front. Son serveur Playwright est défini en ligne (`mcpServers`) : il ne se connecte que pendant que le sous-agent tourne, et la session principale ne reçoit pas ses outils. Le serveur est `@playwright/mcp@0.0.83`, épinglé (licence Apache-2.0), jamais `latest`.

## Prérequis

- Node.js et `npx`.
- Un Chromium pour Playwright : `npx playwright install chromium` (téléchargement, à faire confirmer par l'utilisateur ; le kit n'installe rien).
- Le dossier du projet approuvé dans Claude Code : la doc indique qu'un serveur MCP en ligne d'un agent de `.claude/agents/` ne se charge qu'après cette approbation.
- Sous Windows natif : `command: cmd` et `args: ["/c", "npx", "-y", "@playwright/mcp@0.0.83", ...]` (forme recommandée par la doc MCP pour les serveurs stdio lancés par `npx`). `cost-kit-install` adapte la copie.
- `.claude/cost-kit/verif-front/` dans le `.gitignore` (captures du navigateur).

## Place dans la chaîne

Pour une story qui change un écran :
1. `dev-story` implémente.
2. L'orchestrateur démarre l'application (commande du dépôt, une seule instance, attente du port).
3. `verif-front`, appel bloquant. Il reçoit l'URL et le chemin de la spec, **la même que celle donnée à `dev-story`**, pas une paraphrase : une fiche plus riche produit des FAIL « hors spec » (2 cellules sur 6 en T12).
4. **Seulement s'il y a au moins un FAIL classé `spec`** : second appel à `dev-story` avec ces seuls FAIL (jamais les `hors-spec`, que l'orchestrateur note pour l'utilisateur), puis nouvelle vérification, une seule fois au plus, sur l'application redémarrée (ou rechargée) pour servir le code corrigé.
5. L'orchestrateur arrête l'application.
6. `second-avis`, puis `reviewer`.

Rapport tout PASS : rien d'autre à faire ; la vérification aura coûté 0,10 à 0,15 $ en plus de la chaîne.

## Coût attendu et limites

0,14 $ en moyenne et 60 s par vérification. Limites de T12 : défauts semés d'une ligne (le rappel de 88 % est probablement optimiste), une exécution par défaut, serveur démarré par le banc, petite application. Claude in Chrome reste l'outil de vérification à la main.

## Passer en stable ou retirer

Sur les 10 premières stories front réelles, compter les FAIL `spec` confirmés par l'utilisateur ou le reviewer, et les faux positifs. **Stable** si au moins un vrai défaut est trouvé et au plus un faux positif ; **retiré** sinon. Le retour va dans `mesures/essais/` du projet (gabarit du skill `essai-outil`).
