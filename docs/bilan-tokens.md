# Bilan mensuel des tokens

[← README](../README.md)

Statut : en revue.

## Ce que ça fait

`scripts/bilan_tokens.py` (stdlib seulement, réutilise `mesurer_couts.py` sans dupliquer de table de prix) rejoue le bilan mensuel des tokens Claude Code depuis les transcriptions locales : input détaillé (non caché, écriture 5 min / 1 h, lecture), output (déclaré et réestimé), coût en équivalent API par poste, et impact EcoLogits en fourchette, par modèle.

```
python scripts/bilan_tokens.py --mois 2026-10 --dossier C:/chemin/du/depot
```

- `--mois` (défaut : mois UTC courant) filtre sur le préfixe de l'horodatage UTC de chaque appel, tel qu'écrit par Claude Code.
- `--du AAAA-MM-JJ --au AAAA-MM-JJ` (dates UTC incluses, dans le même mois, exclusif avec `--mois`) remplace le mois entier. Le JSON gagne les champs `du` et `au` (`mois` reste le mois des deux dates) et les fichiers s'appellent `<du>_<au>-<machine>`.
- `--racine` est répétable : toutes les racines sont lues, un appel par `message.id` sur l'ensemble (première occurrence chronologique). Usage : une copie des transcriptions d'un PC plus le dossier local du même PC.
- `--detail` ajoute le détail par projet, étape et rôle (section ci-dessous) ; `--config` (défaut `~/.claude/cost-kit/bilan-config.json`) le règle.
- `--dossier` limite aux dossiers de projet sous `--racine` (défaut `~/.claude/projects`) dont le nom encodé commence par celui du chemin donné (même encodage que `mesurer_couts.dossier_transcriptions`) : il couvre donc ce dossier et ses sous-dossiers, pas un dossier frère au nom plus long (`GitHub2` pour `GitHub`). Sans l'option, tous les projets du compte sont comptés.
- Les `*.jsonl` sont parcourus récursivement (sous-agents compris), un appel par `message.id` dédoublonné sur l'ensemble des fichiers retenus (première occurrence chronologique gardée), les messages synthétiques (`id == "<synthetic>"`) écartés.

Écrit `<mois>-<machine>.json` (schéma documenté dans le script, aucun contenu de transcription) puis la page HTML correspondante, à partir du gabarit `skills/bilan-tokens/gabarit.html` : charte Wavestone, un seul point d'injection (`const BILAN=…`), aucun chiffre ni chemin codé en dur dans la page — tout est calculé en JavaScript depuis le JSON.

## Consolider plusieurs PC

```
python scripts/bilan_tokens.py --fusionner 2026-10-pc1.json 2026-10-pc2.json --out mesures/
```

Refuse des bilans de périodes différentes (`mois`, `du`, `au`), la même machine en double, des mix électriques différents, ou un mélange de bilans « tous les projets » et de bilans limités à un dossier. Les dossiers des PC (chemins propres à chaque machine) sont recopiés dans le consolidé. Écrit `<mois>-consolide.json` (modèles sommés, liste des machines, total par machine) et sa page HTML, avec un bouton supplémentaire pour déplier le détail par PC. Quand une période `--du/--au` a été utilisée, le consolidé s'appelle `<du>_<au>-consolide`. Si **tous** les bilans ont un `detail`, il est fusionné (sommes recalculées, recommandations recalculées avec la config courante) ; sinon le consolidé n'en a pas et un avertissement le dit.

## Détail par projet, étape et rôle

`--detail` ajoute au JSON un champ `detail` et à la page quatre sections : 04 par projet, 05 par étape, 06 par rôle, 07 recommandations. Le code est dans `scripts/bilan_detail.py`. Chaque appel est classé ainsi :

- **Projet.** Le dépôt est le premier segment du dossier de travail (`cwd`) sous un dossier parent de dépôts (`parents`, défaut `GitHub` et `dev`, sans tenir compte de la casse). On applique ensuite `alias` (préfixe de nom vers clé de dépôt), puis la clé du portfolio dont le nom est égal ou préfixe suivi de `-` ou `_` (la plus longue d'abord, pour les worktrees `depot-lot4`), sinon le nom tel quel, hors portfolio. Un dossier hors de tout parent, ou le parent lui-même, va dans « Racine des dépôts (sessions transverses) ».
- **Étape**, onze familles : cadrage du besoin, spécifications, architecture et plan, développement, relecture et tests, intégration et livraison, pilotage, recherche et documentation, outillage et mesure, contenus, échanges sans étape. Dans la session principale, le dernier skill invoqué (commande tapée ou outil `Skill`) vaut jusqu'au skill suivant ou à `/clear` ; une commande git ou gh de livraison l'emporte toujours ; sans skill, l'outil de l'appel décide (édition : développement, pytest ou ruff : tests, lancement d'agent : pilotage…). Pour un sous-agent, le type explicite (`dev-story`, `reviewer`, `second-avis`, `lookup`, `Explore`, `Plan`) décide ; sinon le skill qu'il exécute au moment de l'appel ; sinon les mots de sa description, puis de son premier prompt ; sinon le skill de la session qui l'a lancé ; sinon le développement.
- **Rôle.** L'orchestrateur (session principale) ou le type du sous-agent, avec la sous-clé `modèle · effort`.

Le JSON ne garde pas les appels : `detail.brut` contient des sommes par cellule (dimension, clé, sous-clé) et par modèle, plus le coût de chaque sous-agent arrondi au centime. C'est ce qui permet la fusion de plusieurs PC. Les blocs d'affichage (`projets`, `etapes`, `roles`, `orch`, `sous`, `total`) et les `recos` se recalculent depuis `brut`. Aucun texte de transcription n'en sort : seulement des noms de skills, de types d'agents et de dépôts ; les descriptions et premiers prompts des sous-agents servent au classement puis sont oubliés.

**Recommandations.** Huit, calculées en Python et affichées seulement si leur condition est remplie, triées par gain maximal décroissant (les neutres à la fin) : implémenter avec `dev-story` plutôt qu'un généraliste, simplifier la relecture, raccourcir le contexte de l'orchestrateur, quitter une version ancienne d'un modèle, faire le point d'un run dans une session neuve, et trois constats neutres (effort, amont, mesure). Les seuils sont des constantes nommées de `bilan_detail.py`.

**Config** `~/.claude/cost-kit/bilan-config.json` (absente : valeurs par défaut ; JSON invalide : erreur) :

```json
{
  "portfolio": {
    "url": "https://github.com/Aliquanto3",
    "fichier": "C:/chemin/vers/portfolio.json",
    "proprietaire": "Aliquanto3",
    "topic": "ai-portfolio"
  },
  "alias": {"ancien-nom-du-depot": "cle-du-depot"},
  "parents": ["GitHub", "dev"],
  "motif_experiences": "^(T\\d|Banc|banc|Test W)"
}
```

- `portfolio.fichier` : un `portfolio.json` au format du profil Aliquanto3 (`repos.<clé>.name`, `statuses.<topic>.fr`). `proprietaire` et `topic` servent à lire l'état (premier topic `status-*` connu) et la version (dernière release) par `gh repo list` ; si `gh` manque, échoue ou dépasse 30 s, le bilan continue sans état et avertit. Sans section `portfolio`, la page liste un dépôt par ligne, sans colonne État. `url` est le lien affiché.
- `motif_experiences` : description des sous-agents de bancs d'essai (recommandation « Mesurer reste rentable »).

Limites du classement :

- Un skill reste attribué jusqu'au suivant : le pilotage est surestimé après `avancement-run`, dont la session continue de compter comme pilotage même quand l'orchestrateur y relance des stories.
- La frontière entre familles voisines n'est fiable qu'à quelques pourcents près ; les ordres de grandeur le sont.
- La fusion applique la config courante aux états du portfolio et aux recommandations, mais le classement (projet, étape) a été fait à la collecte, avec la config de chaque PC.
- Seuls des noms de skills, de types d'agents et de dépôts sortent des transcriptions, jamais leur texte.
- Pas de période à cheval sur deux mois.

## Limites

- Transcriptions locales uniquement : un PC sans Claude Code dessus n'y figure pas.
- Le coût est un équivalent au tarif public de l'API, pas la facture d'un abonnement.
- Impact environnemental : `--methode impactia` (défaut, expérimental, PR EcoLogits #259 non fusionnée) compte l'input, la lecture du cache de 0 (borne basse) au prefill complet (borne haute) ; `--methode ecologits` ne compte que les tokens de **sortie** (borne basse). La méthode est écrite dans le JSON (`methode`) et dans la page ; `--fusionner` refuse des bilans de méthodes différentes (un bilan sans `methode`, d'avant 0.9.0, compte comme `ecologits`). Voir [impact-input-impactia.md](impact-input-impactia.md).

## Skill

`/bilan-tokens` (ou « bilan tokens », « combien de tokens ce mois », « consommation Claude Code du mois », « consolider mes PC ») lance le script, commente le résultat en quelques lignes et publie la page HTML.

## Revue

Revue du commit a9e2687 (2026-10-23), avec le second avis.

| Sévérité | Source | Constat | Suite |
|---|---|---|---|
| medium | second avis 1 | Pas de `<meta charset="utf-8">` : mojibake en `file://` | Corrigé |
| medium | second avis 2 | Fusion : portée (`dossier`) perdue, page « tous les projets » à tort | Corrigé : portée recopiée, mélange tous projets / dossier refusé. Chemins différents acceptés (un même dépôt a un chemin propre à chaque PC) |
| medium | second avis 3 | `cout_sans_cache` sans majoration long contexte (Haiku 5.5 ×5) ni inférence US | Corrigé : calcul par appel via `mc.couts`, test à valeurs fixes |
| medium | second avis 4 | `datetime.UTC` exige Python 3.11, docs promettent 3.10+ | Corrigé (`timezone.utc`) |
| medium | second avis 5 | `--dossier` en préfixe nu attrape les dossiers frères | Corrigé + test |
| medium | second avis 6 | Chemin et nom de machine dans la page | Rejeté : artefact privé, affichage voulu |
| low | second avis 7 | Mix non vérifié à la fusion | Corrigé (refus) |
| low | second avis 8 | Pas de test d'échappement `</` | Corrigé (test ajouté) |
| low | second avis 9 | Dossier, machine, identifiant de modèle inconnu injectés sans échappement en `innerHTML` | Corrigé (`esc`) |
| low | second avis 10 | Ordre à égalité d'instant dépendant de `rglob` | Corrigé (parcours trié) |
| info | revue | Complexité : `par_modele` et `sommer_blocs` en O(n), `ordre` linéaire sur quelques modèles seulement | Rien à corriger |
| info | revue | JS du gabarit exécuté sous Node (DOM simulé) sur le bilan réel d'octobre et sur une fusion : aucune erreur, 4,64 Md input, 15,1 M output, 1 665 $ | Vérifié |

### 0.16.0, passe 1 (2026-10-27, SHA revu c0d253d)

Revue après rebase sur `origin/master` (0.15.0), avec le second avis.

| Étiquette | Sévérité | Source | Constat | Suite |
|---|---|---|---|---|
| Important | medium | second avis 1 | Une balise `<command-name>` citée dans un texte utilisateur faisait d'un texte libre un « skill », repris comme sous-libellé d'étape dans le JSON | Corrigé : seul un nom plausible (`[\w:.-]{1,80}`) est retenu, aussi pour l'outil `Skill` ; test |
| Important | medium | second avis 2 | `projet()` prenait le premier parent : `/home/dev/GitHub/depot` donnait « GitHub » | Corrigé : premier parent suivi d'un segment qui n'est pas un parent (un sous-dossier `dev` d'un dépôt reste sans effet) ; tests |
| Nit | medium | second avis 3 | Base en retard de 5 commits | Traité par le rebase (conflits `CHANGELOG.md`, `plugin.json`, `README.md` résolus) |
| Nit | low | second avis 4 | `reco_effort` : division par un coût medium nul | Corrigé (garde) ; test |
| Nit | low | second avis 5 | `reco_implementation` avec une médiane `dev-story` nulle | Corrigé (garde) |
| Nit | low | second avis 6 | `relecture` déclenchée par un seul appel `reviewer` Opus | Rejeté : condition de la spec (plus de 50 % des appels sur Opus), sans seuil de gain demandé |
| Nit | low | second avis 7 | Motifs `DESC` non ancrés (`port` dans « report », « support ») | Corrigé pour `\bport` ; les autres restent ceux de la référence (frontière à quelques pourcents, voir Limites) |
| Nit | low | second avis 8 | `executer` non transmis depuis les commandes | Rejeté : injection exigée au niveau de `bilan_detail` et utilisée par les tests ; aucun test de commande n'a de propriétaire, donc aucun ne lance `gh` |
| Nit | low | second avis 9 | Double lecture des fichiers avec `--detail` | Accepté : 56 s de lecture sur 87 491 appels réels, classement 1,8 s |
| Nit | low | dev-story | `modele-ancien` en une seule recommandation pour tous les modèles ; part Opus non affichée dans `implementation-generaliste` ; à la fusion, classement figé par PC | Acceptés : présentation, et le classement ne peut se refaire sans les transcriptions |
| info | revue | Complexité : `skill_a` linéaire sur la chronologie d'une session (10 entrées au plus sur ce PC), agrégation en O(n) | Rien à corriger |
| info | revue | Bilan réel du 1er au 26 octobre (`--detail`) : JS des sections 04 à 07 exécuté sous Node sans erreur, 7 recommandations ; aucun `git push`, `Tu implémentes` ni `command-name` dans le JSON ; page sans `detail` identique au rendu de master (mêmes contenus sous Node) | Vérifié |
