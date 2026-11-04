---
title: "agent-cost-kit 0.18.0 : relanceur des runs autonomes, nouvelle session au-delà d'un seuil de contexte"
status: review
date: 2026-11-04
source: "veille-agents-code, T16 (tests-pratiques/T16-compaction-brief/resultats.md) et arXiv 2611.05306"
---

# agent-cost-kit 0.18.0 : relanceur des runs autonomes

Une story, branche `feat/0.18-relancer-run`. **Expérimental** (catalogue `docs/experimental.md`, rien ne change dans la chaîne par défaut). Numéro 0.18.0 : 0.17.0 est déjà pris par deux branches ouvertes (`feat/0.17-bilan-trilingue`, `feat/0.17-suivi-run`).

## Pourquoi

- La nuit, personne ne tape `/clear` : la session d'orchestration grossit sans fin. Sur usine-migration-jira-demo, les 4 plus longues sont montées à 266, 414, 473 et 803 k **sans aucune compaction**. Une orchestration d'une traite a coûté 68 $ (866 k).
- T16 (2026-11-04) : relancer **à chaque story** coûte +95 % à l'orchestrateur quand son contexte reste petit (43 k pour 4 stories). Chaque nouvelle session repaie l'écriture du cache de son préfixe (~20 k à 1 h).
- Donc : relancer **seulement au-delà d'un seuil** (défaut 100 k), et sinon reprendre la même session (`--resume`, cache chaud). Seuil de rentabilité estimé : retirer au moins 40 à 50 k de contexte par relance.
- Format de reprise validé par T16 (4 reprises sur 4 sans perte) : un « brief » de 40 lignes au plus (tâche quasi verbatim, intention, plan restant, artefacts utiles, pièges), pas un récit. Recommandation de l'article arXiv 2611.05306.

## Principe

Le relanceur pilote l'orchestrateur en sessions `claude -p` successives. Une session ne s'arrête **qu'à un point calme** : fin de vague, aucun agent en cours, journal à jour. Le relanceur ne coupe jamais une session en cours.

```
boucle (au plus --max-sessions sessions, au plus --max-tours tours) :
  tour = nouvelle session (prompt de reprise)   si première fois ou pic du tour précédent ≥ seuil
       = --resume de la même session (prompt de suite)   sinon
  lire la dernière ligne « ETAT: … » du résultat
  CONTINUER → tour suivant ; FINI → sortie 0 ; ATTENTE_HUMAINE → sortie 2 ; BLOQUE ou ligne absente → sortie 3
  erreur de la CLI (is_error, code ≠ 0, budget dépassé) → sortie 4
```

Le pic de contexte d'un tour est celui de la session principale (sous-agents exclus) : `input + cache_read + cache_creation` maximal sur les appels de ce tour, calculé par `mesurer_couts.appels()` sur `~/.claude/projects/<projet encodé>/<session>.jsonl` (`mesurer_couts.dossier_projet` ou équivalent, encodage déjà implémenté ligne ~121). Ne compter que les appels postérieurs au début du tour (horodatage), puisque `--resume` ajoute au même fichier.

## Livrables

### 1. `scripts/relancer_run.py` (stdlib seulement, réutilise `mesurer_couts`)

Options :
- `--projet` (défaut : dossier courant) ; `--etat` (défaut `_bmad-output/implementation-artifacts/run-autonome.md`, erreur claire s'il manque) ;
- `--seuil` en tokens (défaut `100000`) ; `--max-sessions` (défaut `12`) ; `--max-tours` (défaut `40`) ;
- `--modele` (défaut `claude-opus-5-5`), `--effort` (défaut `medium`), `--budget-tour` en $ (transmis à `--max-budget-usd`, défaut `10`) ;
- `--permission-mode` (transmis tel quel, défaut `acceptEdits`), `--claude` (exécutable, défaut `shutil.which("claude")`, utile aux tests) ;
- `--a-sec` : affiche les commandes et la décision sur un résultat simulé, n'appelle rien.

Comportement :
- Commande d'un tour : `claude -p --model … --effort … --output-format json --max-budget-usd … --permission-mode …` plus `--session-id <uuid neuf>` ou `--resume <id>` ; le prompt passe sur l'entrée standard ; aucun délai d'expiration (un tour peut durer des heures).
- **Prompt de reprise** (nouvelle session) : relire le fichier d'état en entier, en particulier `## Brief` ; reprendre le run là où le journal s'arrête ; règles du fichier d'état inchangées ; s'arrêter en fin de vague ou dès qu'une décision revient à l'utilisateur ; avant de s'arrêter, réécrire `## Brief`, journaliser, commiter l'état comme d'habitude (PR `chore/etat-run`), puis terminer par une seule ligne `ETAT: CONTINUER|FINI|ATTENTE_HUMAINE|BLOQUE — <raison courte>`.
- **Prompt de suite** (`--resume`) : « Continue avec la vague suivante, mêmes règles d'arrêt, même ligne ETAT finale. »
- Journal du relanceur : une ligne JSON par tour dans `<dossier de l'état>/relancer-run.jsonl` : `debut`, `fin` (heure locale ISO), `session`, `mode` (`nouvelle`|`reprise`), `pic`, `cout_usd` (`total_cost_usd` ; cumulé par session avec `--resume` : stocker aussi le delta), `etat`, `raison`, `code`. Rien d'autre n'est écrit dans le fichier d'état par le script (l'orchestrateur reste seul à tenir `## Journal`).
- Fin : résumé sur la sortie standard (sessions, tours, relances, coût, état final) ; code de sortie selon le tableau ci-dessus. Windows : `encoding="utf-8"` partout, chemins longs, pas de `python` nu dans la doc (`uv run --no-project python -I`).

### 2. `modeles/run-autonome.md`

- Nouvelle section `## Brief` après `## Contrats partagés en cours` : gabarit de 5 rubriques (tâche du run quasi verbatim ; intention courante ; plan des vagues restantes ; artefacts utiles : fichiers, modules, conventions, décisions ; pièges rencontrés), « 40 lignes au plus, pas de récit ; réécrit à chaque arrêt de session ».
- Une règle dans `## Règles` : « Run lancé par `scripts/relancer_run.py` : s'arrêter seulement en fin de vague, aucun agent en cours, puis Brief + ligne `ETAT:`. Les agents d'une vague partent dans un même message (appels parallèles et bloquants), jamais en arrière-plan : en `claude -p`, une notification d'agent arrivée après la fin du tour est perdue. »
- Le même point va dans le prompt de reprise et dans les limites de `docs/relancer-run.md`.
- **Compatibilité** : `scripts/avancement_run.py` doit ignorer la section `## Brief` (test sur un fichier d'état qui la contient : même sortie qu'avant).

### 3. Documentation

- `docs/relancer-run.md` : pourquoi (chiffres ci-dessus), lancement type, codes de sortie, lecture de `relancer-run.jsonl`, limites (ci-dessous), comment mesurer le gain au premier run réel (`mesurer-couts` : coût de l'orchestrateur par story, comparé aux runs passés du même projet).
- Entrée dans `docs/experimental.md` ; ligne dans `README.md` (section des scripts) ; `CHANGELOG.md` ; version `0.18.0` dans `.claude-plugin/plugin.json` (et `marketplace.json` si elle y figure).

### 4. Tests `tests/test_relancer_run.py`

Un faux `claude` (script Python de fixture, appelé via `--claude`) qui lit un scénario JSON (une entrée par tour : `etat`, `pic`, `cout`, `is_error`) et écrit une transcription minimale au bon endroit (`--racine` des transcriptions surchargeable par variable d'environnement ou option cachée, à documenter dans le test). Cas :
1. Pic sous le seuil → tour suivant en `--resume` de la même session.
2. Pic au-dessus → nouvelle session avec `--session-id` neuf et prompt de reprise.
3. Pic calculé sur les seuls appels du tour (un premier tour à 150 k, un `--resume` qui redescend n'existe pas : vérifier qu'un tour repris ne compte pas les appels des tours précédents).
4. `ETAT: FINI` → code 0 ; `ATTENTE_HUMAINE` → 2 ; `BLOQUE` et ligne absente → 3 ; `is_error` → 4.
5. `--max-sessions` et `--max-tours` atteints → arrêt, code 3, raison explicite.
6. `relancer-run.jsonl` : une ligne par tour, champs présents, delta de coût correct en reprise.
7. `--a-sec` : aucune exécution du faux `claude`.
8. Fichier d'état absent → erreur claire, code 1.
9. `avancement_run.py` inchangé sur un état avec `## Brief`.

## Limites (à écrire dans la doc)

- Un run lancé en interactif puis laissé tourner reste une seule session : il faut lancer le run par le relanceur dès le départ.
- Le relanceur suppose que l'orchestrateur respecte la règle d'arrêt en fin de vague ; sinon un tour peut grossir au-delà du seuil (le seuil est vérifié entre deux tours, pas pendant).
- Les notifications à l'utilisateur restent celles du run (le relanceur sort avec le code 2 sur `ATTENTE_HUMAINE`, à brancher sur un outil de notification si besoin).
- Gain non mesuré : estimation de plusieurs dizaines de dollars sur un run du type 803 k / 531 appels ; à mesurer au premier run réel.

## Hors périmètre

- Pas de compaction en cours de tour, pas de hook, pas de modification du comportement de Claude Code.
- Pas de parallélisme de plusieurs orchestrateurs.
- Pas de changement des agents `dev-story`, `second-avis`, `reviewer`.

## Critères d'acceptation

- **Given** un état `CONTINUER` avec un pic de 60 k, **When** le relanceur prépare le tour suivant, **Then** il utilise `--resume` sur la même session et le prompt de suite.
- **Given** un état `CONTINUER` avec un pic de 140 k, **When** le relanceur prépare le tour suivant, **Then** il ouvre une nouvelle session avec le prompt de reprise, et `relancer-run.jsonl` note `mode: nouvelle`.
- **Given** une ligne `ETAT: ATTENTE_HUMAINE — accord pour couper`, **When** le tour se termine, **Then** le relanceur s'arrête avec le code 2 et affiche la raison.
- **Given** un fichier d'état contenant `## Brief`, **When** on lance `avancement_run.py`, **Then** la sortie est identique à celle du même fichier sans cette section.
- Contrôles : `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`.

## Revue

### Passe 1 (2026-11-04, SHA revu b70e31f)

Base à jour (origin/master 20eae7f, pas de rebase). Second avis Haiku repris point par point.

- **Important**, medium, second avis 1 : `MOTIF_ETAT` refusait `**ETAT: FINI** — ok`, `` `ETAT: …` ``, `ETAT : …`, `- ETAT: …`, `ETAT: FINI.`, `ETAT: FINI (3 vagues)` ; un CONTINUER en gras arrêtait le run (code 3) et un FINI mal reconnu laissait gagner une ligne antérieure. Corrigé : motif tolérant à la mise en forme Markdown et à la casse, tests paramétrés.
- **Important**, medium, second avis 2 : erreur de la CLI sans JSON en reprise → `total_cost_usd` lu 0, delta négatif journalisé, coût total sous-estimé. Corrigé : coût absent → delta 0, cumul inchangé ; test.
- **Important**, medium, second avis 3 : `## Brief` est placé avant `## Sprint 1` ; un plan restant écrit en tableau (`| V1 | … |`) était lu par `lire_plan` (vague écrasée). Corrigé : `lire_plan` saute la section `## Brief` (ses sous-titres `###` compris) ; test qui compare les plans avec et sans Brief (échoue sur l'ancien code).
- **Important**, medium, second avis 4 : transcription absente → pic 0 silencieux ; `CLAUDE_CONFIG_DIR` ignoré. Corrigé : racine `$CLAUDE_CONFIG_DIR/projects` si posée, avertissement sur stderr si la transcription manque ou est illisible ; tests.
- **Nit**, medium ramené à low, second avis 5 : sémantique de `total_cost_usd` en `--resume` (cumulée ou par appel) non vérifiable ici ; n'affecte que le compte rendu (le plafond par tour reste celui de la CLI). Corrigé en partie : une valeur en baisse compte comme coût du seul tour ; limite documentée. **Reporté** : au premier run réel, comparer la somme des `cout_delta_usd` au coût de `mesurer-couts` sur la période.
- **Nit**, low, second avis 6 : `acceptEdits` n'autorise pas Bash en `-p`. Corrigé dans `docs/relancer-run.md` (liste `permissions.allow` : git, gh, uv, Task ; essai `--max-tours 1`).
- **Nit**, low, second avis 7 : `OSError` au lancement ou sortie non UTF-8 → trace, tour non journalisé. Corrigé : `errors="replace"`, `OSError` → code 4 journalisé ; test.
- **Nit**, low, Pyright : `str | None` (l. 139, 152) faux positifs (session toujours posée à ce point) ; `reconfigure` déjà gardé par `hasattr` ; `__doc__.splitlines()` cassait sous `python -OO` : description en dur. Corrigé pour `__doc__`, le reste rejeté (pas de défaut).
- **Nit**, low, revue : `avancement_run.lire_plan` cherche « Au plus N stories » dans tout le texte, Brief compris ; non corrigé (phrase improbable dans un brief).
- Complexité : 0 constat (journal en ajout ; transcription relue une fois par tour, un tour durant une vague).
- Ruff non lancé (pas de config, CI sans ruff, erreurs préexistantes).
