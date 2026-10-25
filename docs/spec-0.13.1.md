# Spec 0.13.1 : CI de tests et validation

Objectif : aucune PR ne fusionne sur `master` sans contrôle. Workflow `.github/workflows/ci.yml` : `tests (ubuntu-latest)` et `tests (windows-latest)` (suite pytest complète, Python 3.13 via uv, cosmic-ray installé par `uv run --with`) et `validation` (`claude plugin validate . --strict`, Claude Code 2.1.280). `master` protégé par ces trois contrôles.

Critères d'acceptation :

1. La CI tourne sur toute PR et tout push sur `master`.
2. La suite passe sur Linux et sur Windows, sans saut silencieux des tests de mutation.
3. La validation stricte du plugin passe.

## Revue

Base à jour (`origin/master` `feab94d` ancêtre de la branche). Premier passage de la CI (run 40188083371) : `validation` et `tests (windows-latest)` verts, `tests (ubuntu-latest)` rouge sur `test_budget_qui_tombe_pendant_un_mutant_tue_l_arbre`. Complexité : 0 constat (instantané `ps` borné à 20 tours, appelé seulement à l'échéance).

- high · second avis 1 · corrigé · défaut de la 0.12.0 sous POSIX : `--borne` lance le pytest du mutant dans sa propre session, `killpg` du seul groupe de cosmic-ray le laissait orphelin. `kill_tree` gèle l'arbre de descendants (`ps -A -o pid=,ppid=`, SIGSTOP jusqu'à un instantané stable) puis envoie SIGKILL à chacun et à chaque groupe qu'il mène, quel que soit le nombre de sessions imbriquées ; Windows inchangé. Test POSIX `test_kill_tree_tue_les_sessions_imbriquees` (petit-enfant dans sa propre session) et test pur du parcours de `descendants`.
- medium · second avis 2 · corrigé · `test_script_tue_laisse…` vérifie maintenant qu'aucun pytest de mutant ne survit au script tué.
- medium · second avis 3 · corrigé · fixture `outil` : en CI (`CI` défini), un cosmic-ray indisponible fait échouer au lieu de sauter.
- low · second avis 4 · corrigé · `vivant` compte un zombie (état `Z`, `/proc/<pid>/stat` ou `ps -o stat=`) comme mort ; `aucun_vivant` laisse 10 s de grâce (SIGKILL asynchrone).
- low · second avis 5-8 · rejeté · syntaxe du workflow correcte, `validate --strict` vert en CI, fins de ligne sans effet, fichier verrouillé sous Windows non observé.
- reporté · à confirmer par la CI Linux : les trois tests de mutation (budget, délai par mutant, script tué) et le nouveau test de sessions imbriquées passent sous `ubuntu-latest` ; non exécutables en local (Windows sans WSL). macOS non couvert par la CI.
