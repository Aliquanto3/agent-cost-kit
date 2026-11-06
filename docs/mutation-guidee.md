# Mutation guidée (expérimental, optionnel)

Étape facultative que l'orchestrateur ajoute **après dev-story et avant second-avis** : un script mute les lignes que la story vient d'écrire, relève les mutations que les tests de la story ne voient pas, puis un second appel `dev-story` (Sonnet) écrit les tests qui les tuent. La chaîne par défaut ne la lance jamais seule.

## Ce que disent les mesures (veille-agents-code)
- **T4** ([résultats](https://github.com/Aliquanto3/veille-agents-code/blob/main/tests-pratiques/T4/resultats-mutation.md)) : cosmic-ray borné aux lignes de la story trouve un vrai trou de test dans 5 stories sur 5, mais une seule story sur 5 tient sous 10 minutes (1,7 min) ; une autre prend 13,5 min, les trois dernières dépassent le budget de 20 min (24 à 42 min estimés en plein) : pas de porte de CI.
- **T10** ([résultats](https://github.com/Aliquanto3/veille-agents-code/blob/main/tests-pratiques/T10-hypothesis/resultats.md)) : une simple consigne de renforcement des tests bouche déjà la moitié des trous (59 % des cibles non équivalentes tuées).
- **T10b** ([résultats](https://github.com/Aliquanto3/veille-agents-code/blob/main/tests-pratiques/T10-hypothesis/resultats-T10b.md)) : en montrant les survivants dédoublonnés à Sonnet, **134 survivants non équivalents sur 134 tués**, pour 0,22 $ par story (0,15 à 0,34 $) ; il reconnaît seul les mutants équivalents (35 sur 35).
- **Délai** : 3 à 13 minutes par story, dont 80 à 95 % de mutation ; l'agent y passe 1 à 2 minutes.

## Quand
- Story qui **crée un fichier source** ou en **réécrit une part importante**.
- Pas pour une story mécanique ou de documentation. **Jamais en porte de CI** : le délai est trop long et variable.

## Où
Après dev-story, avant second-avis. Le reviewer ne peut pas lancer d'agent : il relit ensuite les tests ajoutés (consigne dans `agents/reviewer.md`). Signaler l'étape dans la spec de la story pour qu'il la voie.

## Comment
1. Relever le commit avant la story (`<sha>`), puis, dans le worktree de la story, commits faits :
   ```
   uv run --no-project python <kit>/scripts/mutation_story.py --worktree <wt> --base <sha> --budget-min 10
   ```
   Par défaut, le script mute les lignes ajoutées ou modifiées des sources du diff (`--modules` pour les choisir), lance seulement les tests touchés par la story (`--tests`), arrête au premier échec, et tue l'arbre de processus à l'échéance du budget (Windows et Linux). Le dépôt n'est jamais muté : le script travaille dans une copie jetable (`git worktree add --detach` de HEAD, dans le dossier temporaire ; les modifications non commitées et les fichiers non suivis n'y sont pas), retirée à la fin, et au démarrage suivant si le script a été tué (jamais la copie d'un passage encore vivant : deux stories du même dépôt peuvent passer en parallèle). Chaque mutant qui dépasse `--timeout-test` est tué avec tout son arbre de processus, y compris sous Windows. Les tests y tournent dans l'environnement du projet (`uv run`, qui crée le `.venv` de la copie) plus `cosmic-ray==8.7.0` et pytest ; `--python` fournit un interpréteur déjà prêt pour un projet qui n'utilise pas uv ou dont les tests demandent des extras. La première synchronisation du `.venv` de la copie (depuis le cache de uv, sinon par le réseau comme tout `uv sync`) compte dans le budget. Le budget couvre tout le passage : suite de référence, `cosmic-ray init` et mutants. Sortie, dans un dossier temporaire hors dépôt ou `--out` : `survivants.json` et `survivants.md` (une ligne de code, une mutation représentative en diff d'une ligne, la fonction englobante, les compteurs générés, exécutés, tués, survivants et non exécutés faute de budget). Les mutants dans des annotations de type sont retirés.
2. Si la liste est vide, passer au second avis. Sinon, second appel `dev-story` (Sonnet) avec le contenu de `survivants.md` et la consigne de T10b :
   > Ces mutations du code ne font échouer aucun test existant. Pour chacune qui change un comportement observable, ajoute un test qui échoue sur le code muté et passe sur le code actuel. Si une mutation est équivalente (aucun comportement observable ne change), dis-le sans écrire de test. Écris les nouveaux tests dans de nouveaux fichiers `test_renf_*.py` du dossier de tests ; ne modifie ni le code source ni les tests existants.

   Le rapport indique, pour chaque mutation Mn, le test qui la tue ou « équivalente » avec la raison en une phrase.
3. Enchaîner avec second-avis, puis reviewer.

## Limites
- Un test qui fige un détail d'implémentation (constante exacte, `frozen=True`) est à trancher par le reviewer.
- Un mutant non montré à l'agent n'est tué qu'à 71 % : la liste dédoublonnée par ligne ne couvre pas toutes les mutations de la ligne.
- Budget épuisé : les mutants non exécutés sont comptés dans le rapport, pas testés.
- Outillage repris de `T4/mutation_story.py` et `T10-hypothesis/mutation.py` (même auteur, Apache-2.0).
