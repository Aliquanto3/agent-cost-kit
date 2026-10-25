---
title: "agent-cost-kit 0.13.0 : sous-agent de vérification front (expérimental)"
status: review
date: 2026-10-25
source: "veille agents de code, tests T7 et T12 (https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T12-front)"
---

# agent-cost-kit 0.13.0 : sous-agent de vérification front (expérimental)

Une story, branche `feat/0.13-verif-front`. Tout ce qui est ajouté est **expérimental** et **optionnel** : la chaîne par défaut (dev-story, second-avis, reviewer) ne change pas pour une story qui n'est pas front, ni pour un projet qui n'a pas installé le sous-agent.

## Pourquoi

Test T12 de la veille (stories 7.13 à 7.16 d'usine-migration-jira-demo, `tests-pratiques/T12-front/resultats.md`) :
- un sous-agent Sonnet (effort medium) qui ne voit que le navigateur (Playwright MCP) trouve **22 défauts d'interface semés sur 25** (88 %, IC Wilson 70 à 96 %) que pytest (0 sur 25) et axe-core (0 sur 26) ne voient pas ; **0 faux positif** sur 8 exécutions de versions sans défaut ; **0,141 $ et 60 s** par vérification (maximum 0,299 $), soit 9 à 13 % du coût d'un développement Sonnet ;
- dans la boucle de développement (6 cellules), **aucun gain mesuré** : l'agent tenait déjà les critères, et une correction systématique par reprise de session coûte 0,6 à 1,6 $ même quand le rapport est entièrement PASS ;
- les 3 défauts manqués : contrôles du DOM sans relecture du rendu visuel (2), ordre d'enchaînement des étapes (1) ;
- un vérificateur qui reçoit une fiche plus riche que la spec du développeur produit des FAIL « hors spec » (2 cellules sur 6).

D'où : un filet de sécurité bon marché, à garder expérimental tant qu'on n'a pas compté ce qu'il relève sur de vraies stories front.

**Contrainte de Claude Code** (doc officielle, page « Subagents », section « Choose the subagent scope », relue le 2026-10-25) : « plugin subagents don't support the `hooks`, `mcpServers`, or `permissionMode` frontmatter fields. These fields are ignored when loading agents from a plugin. » Un MCP déclaré dans le `.mcp.json` du plugin s'appliquerait à toutes les sessions de tous les projets. Le sous-agent ne va donc **pas** dans `agents/` du plugin : c'est un **modèle** que `cost-kit-install` copie, sur confirmation, dans `.claude/agents/` d'un projet front, avec son serveur Playwright défini **en ligne** (`mcpServers`), connecté seulement pendant que le sous-agent tourne ; la session principale ne reçoit pas ses outils.

## Livrables

1. **`modeles/agents/verif-front.md`** : le modèle d'agent.
   - Frontmatter : `name: verif-front` ; `description` (une phrase : vérification en lecture seule, dans un vrai navigateur, des critères d'acceptation d'une story front, après dev-story et avant second-avis ; expérimental) ; `model: sonnet` ; `effort: medium` ; `tools: Read, mcp__playwright__*` (ni Bash, ni Edit, ni Write) ; `mcpServers` avec une définition en ligne `playwright` : `type: stdio`, `command: npx`, `args: ["-y", "@playwright/mcp@0.0.83", "--headless", "--isolated", "--output-dir", ".claude/cost-kit/verif-front"]`. Version **épinglée** (0.0.83 est celle relue et passée à SkillSpector en T7, provenance npm vérifiée) ; jamais `@latest`.
   - Corps : reprendre la consigne du vérificateur de T12 (`tests-pratiques/T12-front/scripts/verifier.py`, constante `PROMPT`, dépôt `veille-agents-code`, dossier local `C:\Users\Utilisateur\Documents\GitHub\veille-agents-code`) en la généralisant et en y intégrant les leçons du test :
     - lecture seule : il ne modifie rien, ne lit pas le code source ; seulement le fichier de spec que l'orchestrateur lui désigne (outil Read), et le navigateur ;
     - l'orchestrateur lui donne : l'URL de l'application déjà démarrée, le chemin de la spec de la story (**la même que celle donnée à dev-story**, pas une paraphrase), et s'il y a lieu le mode de lancement ou un compte de test ;
     - il n'ouvre que cette application, au plus 40 appels d'outil ;
     - chaque critère d'acceptation : PASS, FAIL ou NA, avec une preuve observée (texte exact, état, URL, statut HTTP) ; un critère dont une partie échoue est FAIL ; NA si le point n'est pas observable dans le navigateur, sans deviner ;
     - contrôles transverses permanents, sur un ou deux écrans de la story : T1 clavier (ordre de tabulation, focus visible, activation par Entrée ou Espace) ; T2 390 px de large (`browser_resize` 390 x 844, **capture d'écran relue**, pas de défilement horizontal, rien de coupé ou superposé, puis retour à 1280 x 800) ; T3 aucun message d'erreur vide, aucun lien mort ;
     - contrôler la **visibilité** des messages et motifs attendus (capture ou état visible), pas seulement leur présence dans l'arbre d'accessibilité ; vérifier aussi l'ordre des étapes quand un critère décrit un enchaînement ;
     - chaque FAIL est classé `spec` (contredit un critère ou une phrase de la spec, citée) ou `hors-spec` (attente raisonnable que la spec ne formule pas) ;
     - rendu : un tableau Markdown court (id, verdict, classe pour un FAIL, preuve), puis une ligne de synthèse « N FAIL spec, M FAIL hors-spec, K NA ». Pas d'autre texte.
2. **`docs/verif-front.md`** : le mode d'emploi, en français, phrases simples.
   - Pourquoi, avec les chiffres de T12 et le lien vers le test ; ce qu'il n'apporte pas (aucun gain mesuré dans la boucle de développement : c'est un filet de sécurité).
   - Prérequis : Node.js et `npx` ; un Chromium pour Playwright (`npx playwright install chromium`, téléchargement à faire confirmer par l'utilisateur) ; le dossier du projet approuvé dans Claude Code (la doc indique qu'un serveur MCP en ligne d'un agent de `.claude/agents/` ne se charge qu'après cette approbation) ; sous Windows natif, `command: cmd` et `args: ["/c", "npx", ...]` (forme recommandée par la doc MCP pour les serveurs stdio lancés par `npx`).
   - Place dans la chaîne, pour une story qui change un écran : `dev-story` → l'orchestrateur démarre l'application (commande du dépôt, une seule instance, attente du port) → `verif-front` (appel bloquant : URL, chemin de la spec) → **seulement s'il y a au moins un FAIL classé `spec`**, second appel à `dev-story` avec ces seuls FAIL (jamais les `hors-spec`, que l'orchestrateur note pour l'utilisateur) puis nouvelle vérification au plus une fois → l'orchestrateur arrête l'application → `second-avis` → `reviewer`. Rapport tout PASS : rien d'autre à faire (0,10 à 0,15 $ au total).
   - Coût attendu et limites de T12 (défauts semés d'une ligne, rappel probablement optimiste ; une exécution par défaut ; serveur démarré par le banc ; petite application). Claude in Chrome reste l'outil de vérification à la main.
   - Critère pour passer en stable ou retirer : sur les 10 premières stories front réelles, compter les FAIL `spec` confirmés par l'utilisateur ou le reviewer et les faux positifs ; stable si au moins un vrai défaut trouvé et au plus un faux positif, retiré sinon. Retour consigné dans `mesures/essais/` du projet (gabarit de `skills/essai-outil`).
3. **`skills/cost-kit-install/SKILL.md`** : nouvelle étape optionnelle « Projet front (expérimental) », après les étapes existantes. Si le dépôt a une interface web (par exemple `package.json` avec un framework front, des gabarits HTML, des fichiers `.html`, `.tsx`, `.vue` ou `.svelte` servis par l'application), proposer, sans l'imposer : copier `${CLAUDE_PLUGIN_ROOT}/modeles/agents/verif-front.md` vers `.claude/agents/verif-front.md` (forme `cmd /c` sous Windows natif), ajouter `.claude/cost-kit/verif-front/` au `.gitignore`, signaler les prérequis et renvoyer à `docs/verif-front.md`. Confirmation avant chaque écriture, comme les autres étapes. Rien pour un projet sans front.
4. **`docs/experimental.md`** : une fiche `verif-front` dans le catalogue, au format des autres (ici : modèle du kit, `@playwright/mcp` 0.0.83 épinglé, licence Apache-2.0 ; problème visé ; quand l'essayer ; protocole ; quoi observer ; critère du livrable 2 ; ce qu'en dit la veille, avec le lien vers T12).
5. **Chaîne documentée** : une phrase dans `modeles/CLAUDE.global.md` (à la suite de la phrase sur la mutation guidée, même style : « Story qui change un écran, dans un projet où `verif-front` est installé : étape optionnelle et expérimentale de vérification dans le navigateur après dev-story, correction seulement sur un FAIL de la spec (`docs/verif-front.md` du kit). »), et la même information, courte, dans le README et `docs/installation.md` là où la chaîne est décrite.
6. **Test** `tests/test_modele_verif_front.py` (stdlib et pytest, sans dépendance YAML nouvelle) : le modèle existe ; son frontmatter a `name: verif-front`, `model: sonnet`, `effort: medium` ; `tools` contient `mcp__playwright__*` et `Read`, et aucun de `Bash`, `PowerShell`, `Edit`, `Write` ; la version de `@playwright/mcp` est épinglée (motif `@\d+\.\d+\.\d+`, jamais `latest`) ; le corps mentionne les classes `spec` et `hors-spec` et la largeur 390. Le modèle n'est **pas** dans `agents/` (vérifier que `agents/verif-front.md` n'existe pas).
7. **Version** : `0.13.0` dans `.claude-plugin/plugin.json`, entrée `0.13.0` en tête de l'historique de `CHANGELOG.md` (même style que 0.12.0 : ce qui est ajouté, pourquoi, chiffres de T12 avec le lien, la contrainte des plugins et le modèle copié par l'installation).

## Hors périmètre

- Ne pas modifier `agents/dev-story.md`, `agents/second-avis.md`, `agents/reviewer.md`.
- Ne rien installer sur le poste (ni `npx`, ni Chromium), ne pas toucher `~/.claude/`.
- Pas de `.mcp.json` dans le plugin.
- Pas de script qui démarre l'application : c'est l'orchestrateur qui le fait, avec la commande du dépôt.

## Vérification

- `uv run --no-project --with pytest python -m pytest -q --tb=short tests/test_modele_verif_front.py`, puis la suite complète une fois à la fin.
- `claude plugin validate .` si la commande est disponible.

## Revue

Base à jour (`origin/master` `dab6638` ancêtre de la branche). Complexité : 0 constat (aucune structure qui grossit à l'exécution).

- medium · second avis 1 · rejeté · `Path.read_text` ouvre en mode texte (newline universel) : un fichier CRLF est lu en LF, prouvé sur un fichier `---\r\n...` écrit sur disque ; la preuve du second avis portait sur une chaîne en mémoire.
- low · second avis 2 · rejeté · `mcpServers`, T1-T3 et le plafond de 40 appels ne sont pas exigés par le livrable 6 ; la version épinglée, seul point à risque, est testée.
- low · second avis 3 · corrigé · `docs/verif-front.md` : le coût d'un rapport tout PASS est celui de la vérification, en plus de la chaîne.
- low · second avis 4 · rejeté · `command: npx` est la forme demandée par la spec ; la variante `cmd /c` est faite par `cost-kit-install` et documentée dans les prérequis.
- low · second avis 5 · rejeté · choix de la spec (`tools: Read` seul, consigne de ne lire que la spec) ; aucun outil d'écriture ni Bash.
- low · second avis 6 · corrigé · `docs/verif-front.md` étape 4 : revérifier sur l'application redémarrée ou rechargée.
- low · reviewer · reporté · le sous-agent réel (chargement de `mcpServers` en ligne, `npx` et Chromium) n'a pas tourné : à vérifier sur la première story front réelle, en lançant `verif-front` sur l'application démarrée et en contrôlant que les outils `browser_*` sont présents et que la session principale ne les reçoit pas.
