---
title: "agent-cost-kit 0.12.0 : essais expérimentaux et mutation guidée"
status: ready
date: 2026-10-25
source: "veille agents de code, tests T4, T7, T10, T10b, T11 (https://github.com/Aliquanto3/veille-agents-code)"
---

# agent-cost-kit 0.12.0 : essais expérimentaux et mutation guidée

Deux stories, sur la même branche `feat/0.12-experimental`, dans cet ordre. Tout ce qui est ajouté est **expérimental** et **optionnel** : la chaîne par défaut (dev-story, second-avis, reviewer) ne change pas, sauf une consigne d'une ligne dans `dev-story` (story 2).

## Story 1 : catalogue d'essais et skill `essai-outil`

**Pourquoi.** La veille a laissé « à trancher » plusieurs outils qui ne se mesurent qu'avec Anaël présent (questions posées à l'auteur, note à l'aveugle, observation d'un run). Le kit doit permettre de les essayer de façon encadrée, en appliquant la règle du CLAUDE.md global (lire avant d'installer, SkillSpector `--no-llm`, version épinglée, coût de contexte mesuré), et de garder une trace exploitable.

**Livrables.**
1. `docs/experimental.md` : le catalogue. Pour chaque outil, une fiche courte : dépôt et **commit épinglé**, licence, problème visé, quand l'essayer, protocole d'essai (3 à 6 étapes), ce qu'il faut observer, critère pour passer en stable ou l'écarter, ce qu'en dit la veille (une phrase, avec le lien vers le test s'il y en a un). Outils (commits relevés le 2026-10-25) :
   | Outil | Dépôt | Commit | Licence | Ce qui demande Anaël |
   |---|---|---|---|---|
   | grill-with-docs | `mattpocock/skills`, `skills/engineering/grill-with-docs` | `5beb35b040e3de97e54fa9e386d7e42d15c295c2` | MIT | questions posées à l'auteur avant un PRD flou |
   | clarity (rewrite, review, interview) | `addyosmani/clarity` | `e27ceeff60368cf6966b4ea00a5b9b36418ee9a0` | MIT | jugement sur des textes publics ; T11 fait (provisoire : aucun fait inventé, 0,11 $ par réécriture, ne départage pas), note à l'aveugle d'Anaël en attente |
   | humanizer | `blader/humanizer` | `8c307f367c91bd974002f10f2be2965d642c13df` | MIT | idem ; T11 provisoire : aucun fait inventé, 0,13 $, enchaîné après clarity 0,31 $ sans gain mesuré |
   | AOS Dashboard | `tomtomsatnav/agent-orchestration-standard` | `40d270774a275870e1b676b11e8074ec4a746b5f` | MIT | observation d'un run parallèle (conflits de fichiers) ; 19 déclarations de hook asynchrones (3 scripts Node) au commit épinglé, port 4318, Git Bash et make sous Windows |
   | impeccable `detect` | `pbakaus/impeccable` | `936867543ac2576920d663cc9803597f6044f3ac` | Apache-2.0 | selon la note à l'aveugle de T7 ; sans ses hooks ni télémétrie |
   | hallmark | `Nutlope/hallmark` | `7ec868225c6caa040558c321ee0fefa0e73f83a8` | MIT | idem ; flux interactif, lance un sous-agent : jamais en run autonome |
   | diagram-design | `cathrynlavery/diagram-design` | `0b9b10cab3dbf695642fa1a6c4b4f60df9083689` | MIT | livrable client à la demande |
   | hyperframes | `heygen-com/hyperframes` | `7bc363c87c8524e547c5b759d2471d96183b67f3` | Apache-2.0 | vidéo de démo à la demande ; Windows non vérifié |
   | Claude Design | natif (research preview) | n/a | n/a | cadrage UX |
   | Style Concise | natif (`/output-style`) | n/a | n/a | une semaine d'usage, ressenti |
   Ajoute en tête du catalogue la règle d'essai (les cinq contrôles) et ce qui ne s'y trouve pas exprès (packs de méthode concurrents de BMAD : Superpowers, agent-skills, ECC ; renvoi à la veille).
2. `skills/essai-outil/SKILL.md` : skill à **invocation manuelle seulement** (`disable-model-invocation: true` dans le frontmatter), déclenché par « essai outil <nom> », « essayer <nom> » ou `/agent-cost-kit:essai-outil`. Étapes :
   1. retrouver la fiche dans `docs/experimental.md` (refuser un outil absent du catalogue, ou proposer d'abord d'ajouter sa fiche) ;
   2. récupérer le dépôt au commit épinglé dans un dossier neuf et vide (hors du dépôt courant), sans rien exécuter ;
   3. lire en entier `SKILL.md`, hooks, scripts, manifestes et `.mcp.json` ; résumer à Anaël ce que l'outil installe et exécute (hooks, réseau, télémétrie, processus) ;
   4. passer SkillSpector en `--no-llm` s'il est disponible (le dire sinon) ; rappeler qu'un scan propre ne prouve rien ;
   5. mesurer le contexte avant (`/context` ou `claude plugin details`), installer **au niveau projet** (jamais utilisateur) à la version épinglée, sur confirmation d'Anaël, puis mesurer après ;
   6. guider l'essai selon le protocole de la fiche ;
   7. écrire le retour dans `mesures/essais/AAAA-MM-JJ-<outil>.md` (gabarit : outil et commit, projet, contexte avant et après, ce qui a été fait, observations, verdict proposé parmi « passer en stable », « garder à la demande », « écarter », « à refaire », et pourquoi) ;
   8. désinstaller si le verdict n'est pas « passer en stable » ou « garder à la demande », sur confirmation.
   Le skill n'installe jamais rien sans la confirmation d'Anaël et ne touche pas `~/.claude/settings.json`.
3. `mesures/essais/README.md` : une ligne qui dit à quoi sert le dossier et renvoie au gabarit.
4. README (section « Pour aller plus loin ») et `docs/installation.md` : une ligne chacun vers le catalogue et le skill, marqués expérimentaux.

**Critères d'acceptation.**
- `claude plugin validate .` passe (frontmatter YAML valide, description entre guillemets si elle contient `:`).
- Le skill ne se déclenche pas seul (`disable-model-invocation: true`).
- Chaque fiche a un commit de 40 caractères (sauf les natifs), une licence et un critère de sortie.
- Aucun code tiers copié dans le kit.

### Réalisation

- Fichiers : `docs/experimental.md` (règle d'essai, 10 fiches), `skills/essai-outil/SKILL.md` (`disable-model-invocation: true`, 8 étapes de la spec), `mesures/essais/README.md`, une ligne dans `README.md` et dans le tableau de `docs/installation.md`.
- Choix : fiches rédigées d'après le champ `note` de `bilan.json` (veille) ; liens vers T7 et T11 par dossier du dépôt veille ; critères de sortie propres à chaque fiche, formulés comme seuil simple. Commits et licences repris tels quels, aucun code tiers copié.
- Reports : les critères de sortie chiffrés (par exemple « plus de la moitié des constats utiles » pour impeccable) sont des propositions à ajuster après le premier essai ; résultat de T11 à reporter dans les fiches clarity et humanizer quand il sera publié (fait en revue : résultat provisoire reporté, note d'Anaël en attente).

### Revue

Passe 1 (Opus, base `master` à jour en `5c8b575`, commit relu `1785972`).

| Sévérité | Source | Constat | Suite | Motif |
|---|---|---|---|---|
| medium | second avis (high) | Étapes 5 et 8 du skill sans `--scope project` ; `claude plugin install`, `uninstall` et `marketplace add` visent `user` par défaut | corrigé | Confirmé par `--help`. Ramené à medium : la consigne « jamais au niveau utilisateur » était écrite, mais sans la commande. Ajout des commandes avec `--scope project` (marketplace locale depuis la copie épinglée), du cas skill seul (copie dans `.claude/skills/`), et d'une vérification par `claude plugin list` |
| low | second avis | « T11 en cours » périmé dans clarity, humanizer et le tableau de la spec | corrigé | T11 fait le 2026-10-25 (`resultats.md`, `bilan.json`) ; résultat provisoire reporté, note d'Anaël en attente |
| low | second avis | Citation humanizer inexacte | corrigé | Formule réelle de `donnees.json` : « il renforce certains tics de rythme » |
| low | second avis | Citation AOS tronquée | corrigé | « sur un run parallèle » rétabli |
| low | second avis + revue | « 17 hooks asynchrones » | corrigé | Au commit épinglé, `plugin/hooks/hooks.json` déclare 19 hooks, tous `"async": true`, sur 3 scripts (`aos-hook`, `ensure-monitor`, `aos-guard`). Fiche, protocole et tableau corrigés ; l'écart avec le chiffre de la veille (17) est signalé |
| low | second avis | « protocole d'évaluation publié sans résultat » attribué à la veille | corrigé | `evals/JUDGE.md` existe au commit épinglé (protocole, portes dures) sans résultats ; phrase déplacée hors de la ligne « Veille » |
| low | second avis | `.claude/cost-kit/.blocages` commité | corrigé | Retiré du suivi, ajouté au `.gitignore` |
| low | second avis | Étape 7 : dossier `mesures/essais/` ambigu | corrigé | Précisé : racine du projet de l'essai, dossier créé s'il manque |

## Story 2 : mutation guidée (étape optionnelle)

**Pourquoi.** Tests de la veille sur 5 stories de deux dépôts : cosmic-ray borné aux lignes ajoutées par la story trouve un vrai trou de test dans 5 stories sur 5, mais prend 13 à 42 min (T4) : pas de porte de CI. Montrer ensuite les survivants à un agent Sonnet lui fait tuer **134 survivants non équivalents sur 134** pour 0,22 $ par story, contre 59 % avec une simple consigne de renforcement ; il reconnaît seul les mutants équivalents (35 sur 35) (T10b). Une simple consigne explicite de renforcement des tests bouche déjà la moitié des trous (T10). Résultats : `tests-pratiques/T4/resultats-mutation.md`, `tests-pratiques/T10-hypothesis/resultats.md` et `resultats-T10b.md` du dépôt veille-agents-code (lis-les, ainsi que les scripts `T4/mutation_story.py`, `T10-hypothesis/mutation.py` et la consigne `CONSIGNE_C` de `T10-hypothesis/lancer_agent.py`).

**Livrables.**
1. `scripts/mutation_story.py` (stdlib seulement, plus `cosmic-ray` lancé par `uv run --with cosmic-ray` dans le dépôt de la story, sans toucher à son `pyproject`) : à partir de `--base <sha>` (commit avant la story), mute **seulement les lignes ajoutées ou modifiées** par la story dans les fichiers source, lance **seulement les tests de la story** (`--tests` ; par défaut les fichiers de tests touchés par la story), arrêt au premier échec, budget `--budget-min` (défaut 10), délai par test, arbre de processus tué à l'échéance (Windows et Linux). Retire les mutants sur des annotations de type. Sortie : `survivants.json` et un Markdown **dédoublonné par ligne** (une ligne de code, une mutation représentative en diff d'une ligne, fonction englobante), plus les compteurs (générés, exécutés, tués, survivants, non exécutés faute de budget). Restaure toujours les sources (vérifier `git status` propre à la fin). Repars de l'outillage de T4 et T10 plutôt que de réécrire.
2. Tests `tests/test_mutation_story.py` sur un petit dépôt de fixture (une fonction, un test faible) : un survivant attendu, dédoublonnage par ligne, lignes hors diff ignorées, sources restaurées, budget respecté. Marquer `skip` proprement si `uv` n'est pas disponible.
3. `docs/mutation-guidee.md` : l'étape, **expérimentale et optionnelle**, pour l'orchestrateur, avec les chiffres et liens ci-dessus :
   - quand : story qui crée un fichier source ou en réécrit une part importante ; pas pour une story mécanique ou de documentation ; jamais en porte de CI ;
   - où : **après dev-story, avant second-avis** (le reviewer ne peut pas lancer d'agent ; il relit ensuite les tests ajoutés) ;
   - comment : `uv run --no-project python <kit>/scripts/mutation_story.py --worktree <wt> --base <sha> --budget-min 10`, puis un second appel `dev-story` (Sonnet) avec la liste dédoublonnée et la consigne de T10b (reprise mot pour mot ou presque : « Ces mutations du code ne font échouer aucun test existant. Pour chacune qui change un comportement observable, ajoute un test qui échoue sur le code muté et passe sur le code actuel. Si une mutation est équivalente, dis-le sans écrire de test. Ne modifie pas le code source. »), le rapport indiquant pour chaque mutation le test qui la tue ou « équivalente » ;
   - coût et délai mesurés : 3 à 13 min par story (dont 80 à 95 % de mutation), 0,22 $ pour l'agent ;
   - limite : un test qui fige un détail d'implémentation (constante exacte, `frozen=True`) est à trancher par le reviewer ; un mutant non montré à l'agent n'est tué qu'à 71 %.
4. `agents/reviewer.md` : une puce : si la spec signale une étape de mutation guidée, relire les tests ajoutés pour cette étape et rejeter (Nit) ceux qui figent un détail d'implémentation sans comportement observable.
5. `agents/dev-story.md` : une puce, stable : « Écris des tests qui vérifient précisément le comportement attendu : valeurs exactes, bornes, branches d'erreur, messages ; pas seulement que le code s'exécute » (T10 : cette consigne seule bouche la moitié des trous).
6. `modeles/CLAUDE.global.md` et README (« L'enchaînement par story ») : une mention courte de l'étape optionnelle, marquée expérimentale, avec le lien vers `docs/mutation-guidee.md`.

**Critères d'acceptation.**
- `uv run --no-project python -m pytest -q tests/test_mutation_story.py` passe sous Windows ; suite complète du kit verte une fois à la fin ; `claude plugin validate .` passe.
- Le script ne modifie aucun fichier du dépôt cible à la fin (sources restaurées, `git status` propre), y compris si le budget tombe pendant un mutant.
- Rien dans la chaîne par défaut ne lance la mutation tout seul.

### Réalisation

- Fichiers : `scripts/mutation_story.py`, `tests/test_mutation_story.py` (4 tests, `skip` si `uv` ou cosmic-ray manque), `docs/mutation-guidee.md`, une puce dans `agents/dev-story.md` et `agents/reviewer.md`, une mention dans `modeles/CLAUDE.global.md` et le README (enchaînement et « Pour aller plus loin »).
- Choix : repris de T4 (filtre sur les lignes du diff, annotations retirées, budget, arbre tué) et T10 (diff d'une ligne, note `CosmicRayTestingException`) ; cosmic-ray et pytest viennent de `uv run --with` à chaque commande (l'environnement éphémère de uv disparaît entre deux appels, d'où `--python` pour fournir un interpréteur prêt) ; sorties et bases cosmic-ray hors dépôt ; sources sauvegardées en octets et réécrites dans un `finally`.
- Reports : arrêt du budget au milieu d'un mutant couvert par la restauration, mais non testé par un test dédié (le test de budget nul vérifie la restauration, pas l'arrêt en cours d'exécution) ; surcoût de `uv run` par mutant non mesuré ; pas de `--modules` en dehors de Python.

### Revue

Passe 1 (Opus, base `master` `5c8b575` à jour). Complexité : 0 constat (structures bornées par la story, parcours linéaires).

- high · second avis · corrigé · script tué (`taskkill /F`, SIGKILL, timeout de l'appelant) : sources du dépôt laissées mutées. Le script mute désormais une copie jetable (`git worktree add --detach` de HEAD dans `%TEMP%/mutation-story/copies`), retirée à la fin et au démarrage suivant (`nettoyer_copies`) ; Ctrl-C tue l'arbre (`attendre`). Test : script tué en plein mutant, dépôt propre, copie retirée ensuite.
- medium · second avis · corrigé · `uv run` dans le dépôt créait `.venv` et `uv.lock` : il tourne dans la copie, donc avec l'environnement du projet (synchronisé dans la copie) ; le test de fixture a un `pyproject.toml` sans lock et vérifie `git status --porcelain --ignored` vide.
- medium · second avis · corrigé · suite de référence et `cosmic-ray init` hors budget : bornées par l'échéance (`run_borne`, arbre tué), message « budget épuisé pendant… ».
- medium · second avis · corrigé · `except SystemExit → skip` masquait les échecs : saut seulement si `uv` manque ou si `import cosmic_ray` échoue dans l'overlay ; sinon le test échoue.
- medium · second avis · corrigé · budget tombant pendant un mutant, arbre tué et `--tests` non testés : test avec un test de fixture qui dort 300 s sur code muté (durée < budget + 45 s, PID du mutant mort, `budget_depasse`), `--tests` dans tous les tests d'intégration.
- low · second avis · corrigé · `cosmic-ray==8.7.0` épinglé (`COSMIC_RAY`).
- low · second avis · corrigé · consigne de `docs/mutation-guidee.md` complétée par la contrainte du bras C de T10 (nouveaux fichiers `test_renf_*.py`, ni source ni tests existants modifiés).
- low · second avis · corrigé · assertion `survivants >= len(uniques)` : lignes exactes `[5, 6]`, regroupement strict, somme des `autres_mutations`, exclusion hors diff.
- low · second avis · corrigé · « 13 à 42 minutes en plein » : chiffres exacts de T4 (1,7 min ; 13,5 min ; trois au-delà de 20 min, 24 à 42 min estimés).
- low · revue · corrigé · `conftest.py` et aides sous `tests/` passés à pytest comme tests (ou mutés) : seuls `test_*.py` et `*_test.py` sont des tests, rien sous `tests/` n'est muté.
- low · revue · corrigé · `--worktree` donné en sous-dossier : chemins du diff faux ; racine résolue par `git rev-parse --show-toplevel`.
- low · revue · reporté puis corrigé en passe 2 (voir ci-dessous) · au délai par mutant (`--timeout-test`), cosmic-ray tue `uv` mais peut-être pas le pytest petit-enfant.
- low · revue · rejeté · critère « `uv run --no-project python -m pytest` » : pytest absent de l'interpréteur nu (`No module named pytest`) ; la commande qui marche est `uv run --no-project --with pytest python -m pytest -q tests/test_mutation_story.py` (7 tests, environ 100 s).

#### Passe 2

Opus, base `master` `5c8b575` à jour (vérifié après `git fetch`), diff relu `1cd2ad3..fc37de0` hors `84146d1`. Complexité : 0 constat (le parcours de `git worktree list` au démarrage est linéaire et borné par les worktrees du dépôt).

- medium · revue (report de la passe 1) · corrigé · confirmé et aggravé sous Windows : cosmic-ray 8.7.0 (`testing.run_tests`) fait `proc.kill()` sur `uv` seul (`os.killpg` n'existe pas), le pytest petit-enfant survit (`uv` ne le tue pas, vérifié : enfant vivant après `TerminateProcess` de `uv`) et garde le tube de sortie, si bien que `communicate()` bloque : un seul mutant en boucle infinie consommait tout le budget (0 mutant exécuté en 4 min) et laissait un `python` orphelin après la fin du script. Chaque mutant passe désormais par un mode interne `--borne <s> --` du script, qui tue tout l'arbre au délai (`taskkill /T`, groupe de processus sous Linux) ; le délai de cosmic-ray est relevé de 60 s comme filet. Test `test_mutant_au_dela_du_timeout_test_tue_sans_orphelin` (rouge sans le correctif, vert avec : tous les mutants tués, aucun PID vivant).
- medium · revue · corrigé · `nettoyer_copies` retirait toute copie du dossier `copies`, y compris celle d'un passage en cours sur une autre story du même dépôt (les worktrees sont partagés entre worktrees d'un dépôt, cas d'un run parallèle). Un marqueur `<copie>.pid` porte le PID du propriétaire ; seule une copie au PID mort ou sans marqueur est retirée (en cas de doute, la copie reste ; pas de `os.kill(pid, 0)` sous Windows, qui terminerait le processus).
- low · revue · corrigé · garde-fou de chemin par préfixe de chaîne : un worktree `…/mutation-story/copies-x` de l'utilisateur aurait été retiré. Seul un enfant direct de `COPIES` est une copie (`est_copie`, `normcase`). Test `test_nettoyage_epargne_copie_vivante_et_worktrees_hors_copies`.
- low · revue · documenté · modifications non commitées : décision maintenue, la copie part de HEAD (la spec suppose une story commitée), avertissement sur `stderr` et phrase dans `docs/mutation-guidee.md`.
- low · revue · documenté · environnement de la copie : `uv run` y synchronise le `.venv` du projet (groupe `dev` par défaut, depuis le cache de uv sinon par le réseau, comme un `uv sync` ordinaire ; `UV_OFFLINE` respecté), temps compté dans le budget car la suite de référence est bornée par l'échéance. Les extras ne sont pas installés : `--python` pour ce cas, phrase ajoutée à la doc.
- low · revue · rejeté · `tempfile.gettempdir()` en nom court 8.3 (`UTILIS~1`) contre les chemins longs de `git worktree list` : `COPIES.resolve()` développe le nom court, la comparaison tient (vérifié par le test de nettoyage).

## Version et publication (après les deux stories)
- `.claude-plugin/plugin.json` en `0.12.0`, entrée `0.12.0` en tête de `CHANGELOG.md` (format des entrées voisines : ce qui change, d'où ça vient, chiffres, liens), au même niveau de détail que 0.10.0 et 0.11.0.
- L'orchestrateur ouvre la PR, vérifie la CI, fusionne, tague `v0.12.0` (annoté) et publie la release avec ses notes.
