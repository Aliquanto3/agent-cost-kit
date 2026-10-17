# Nuit autonome de 5 stories, kit 0.3.1 (2026-10-15 au 16)

Première mesure en série de l'enchaînement 0.2 et suivants : `dev-story` (Sonnet) → `second-avis`
(Haiku) → `reviewer` (Opus), orchestré par une session Opus 5.5 en effort medium, sur 2 lanes
parallèles, avec 3 recherches `bmad-deep-recon` (agents Sonnet) en parallèle.

- **Projet** : démonstrateur pédagogique local en Python avec un front web (le « projet 4 »),
  méthode BMAD, Windows, 16 Go de RAM, suite pytest d'environ 6 000 tests et E2E Playwright.
- **Stories** : installeurs Windows et bash, README orienté testeur, démarrage sans scan du
  disque et bouton de recherche, menu des modèles, panneau agrandissable. Elles touchent du
  PowerShell, du bash, du Python, du JS, du CSS et de la doc.
- **Mesure** : `scripts/mesurer_couts.py`, prix d'octobre 2026, sortie réestimée à 2,2 caractères
  par token.

## Coût

| Poste | Agents | Coût | Remarque |
|---|---|---|---|
| Session principale (orchestration, E2E, fusions, vérification finale) | 1 | 8,49 $ | 156 appels, pic de 256 k |
| `dev-story` (Sonnet) | 5 | 6,48 $ | 25 à 91 appels, pic de 95 à 179 k |
| `second-avis` (Haiku) | 5 | 0,08 $ | 10 à 19 appels |
| `reviewer` (Opus) | 5 | 5,08 $ | 13 à 34 appels |
| Recherches (Sonnet) | 3 | 1,11 $ | |
| Fork lancé par erreur | 1 | 0,04 $ | |
| **Total** | 20 | **21,28 $** | |

| Story | dev-story | second-avis | reviewer | Chaîne |
|---|---|---|---|---|
| Installeurs | 0,73 $ | 0,01 $ | 1,67 $ | 2,41 $ |
| README et docs | 0,54 $ | 0,02 $ | 0,65 $ | 1,21 $ |
| Panneau agrandi | 1,43 $ | 0,02 $ | 0,84 $ | 2,29 $ |
| Démarrage sans scan | 1,92 $ | 0,01 $ | 1,44 $ | 3,37 $ |
| Menu des modèles | 1,86 $ | 0,02 $ | 0,48 $ | 2,36 $ |

- **Chaîne d'une story** : 2,36 $ en médiane, hors orchestration. Avec la session principale
  répartie sur les 5 stories, environ 4,0 $ par story.
- **Comparaison** : sur le même projet, la story médiane valait 16,57 $ (P90 61,72 $), avec
  l'ancien setup tout Opus et imbriqué. Le kit est donc environ 4 fois moins cher,
  orchestration comprise.
- **Revue** : 0,49 à 1,69 $ par story (second avis plus reviewer), 0,86 $ en médiane. Cela
  confirme l'estimation du README (0,7 à 1 $).
- **Cache** : 8 expirations sur 20 sous-agents, 0 en médiane. Le TTL d'une heure aurait coûté
  13,46 $ au lieu de 12,92 $ : le garder à 5 minutes.
- **Contexte du premier appel** : 34,5 k en médiane, contre 38 k avec l'ancien setup.

## Qualité

| Story | Second avis (H / M / L) | Reviewer |
|---|---|---|
| Installeurs | 1 / 3 / 2 | les 6 confirmés et corrigés, plus 1 medium à lui |
| README et docs | 2 / 5 / 3 | 9 corrigés, 1 écarté (hors périmètre), plus 2 erreurs à lui |
| Panneau agrandi | 0 / 2 / 4 | 2 medium et 1 low corrigés, 3 low écartés avec motif |
| Démarrage sans scan | 1 / 2 / 1 | le high écarté **par un test**, un medium relevé en high et corrigé, tests ajoutés |
| Menu des modèles | 0 / 0 / 3 | 1 low corrigé, 1 à vérifier à l'œil, 1 laissé à l'orchestrateur |

- **Second avis Haiku** : il a trouvé les défauts les plus graves de la nuit pour 1 à 2 cents :
  - un téléchargement partiel pris pour un modèle complet ;
  - un code de sortie natif ignoré par PowerShell ;
  - un écouteur Échap qui court-circuitait ceux de la page principale.

  Un de ses « high » était faux, et le reviewer l'a réfuté par un test.
- **Reviewer Opus** : il a confirmé ou écarté chaque constat avec un motif. Il a ajouté 4
  défauts à lui : un dossier de données non transmis, deux erreurs de doc, et un sondage
  synchrone sous verrou, relevé de medium à high.
- **Échappé à la chaîne** : un test d'un autre fichier, qui supposait l'ancien comportement.
  La suite complète, lancée une seule fois à la fin, l'a trouvé. Cause : la consigne de la nuit
  interdisait la suite complète par story (poste de 16 Go). Les tests ciblés ne couvraient pas
  ce fichier.
- **E2E** : tous verts après correction. Un échec intermittent préexistant (lecture sans
  attente) a coûté trois passages de diagnostic à l'orchestrateur.

## Incidents et ce qu'ils ont coûté

- **Blocages du flux** : 4 agents (watchdog de 600 s) et 1 coupure réseau, tous repris avec
  leur contexte par `SendMessage`. Les 8 expirations du cache viennent surtout de ces reprises
  (3 sur une même story).
- **Refus du mode auto** : il a refusé `gh pr merge`, la suppression d'une branche distante et
  la sauvegarde d'un fichier de réglages, sans règle d'autorisation explicite.
  - Les PR sont restées empilées jusqu'au matin.
  - À la fusion, la base a été supprimée avant que les PR empilées soient reciblées. GitHub en
    a fermé 3, qu'il a fallu rouvrir ou recréer.
- **Lancement par erreur** : un fork lancé sans tâche, pour 0,04 $.

## Pistes d'économie tirées de la nuit

| Piste | Gain estimé | Où |
|---|---|---|
| Règles d'autorisation explicites pour `gh pr merge` et la suppression de branche distante, quand une nuit autonome est prévue | une nuit sans attente du matin ; environ 0,5 à 1 $ de réparation de PR évitée | `scripts/installer_global.py` (`REGLAGES["permissions"]["allow"]`, avec fusion des listes) |
| Recibler les PR empilées sur `main` avant de fusionner leur base avec `--delete-branch` | 3 PR fermées évitées | `modeles/CLAUDE.global.md` |
| Si la suite complète est interdite par story, faire chercher par le reviewer les tests qui appellent les fonctions modifiées | le défaut échappé de la nuit | `agents/reviewer.md` |
| Rendre robuste un contrôle E2E instable dès son premier échec, au lieu de le rejouer | environ 3 passages E2E, soit 15 à 30 min de session principale | consigne de projet |
