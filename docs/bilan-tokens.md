# Bilan mensuel des tokens

[← README](../README.md)

Statut : en revue.

## Ce que ça fait

`scripts/bilan_tokens.py` (stdlib seulement, réutilise `mesurer_couts.py` sans dupliquer de table de prix) rejoue le bilan mensuel des tokens Claude Code depuis les transcriptions locales : input détaillé (non caché, écriture 5 min / 1 h, lecture), output (déclaré et réestimé), coût en équivalent API par poste, et impact EcoLogits en fourchette, par modèle.

```
python scripts/bilan_tokens.py --mois 2026-10 --dossier C:/chemin/du/depot
```

- `--mois` (défaut : mois UTC courant) filtre sur le préfixe de l'horodatage UTC de chaque appel, tel qu'écrit par Claude Code.
- `--dossier` limite aux dossiers de projet sous `--racine` (défaut `~/.claude/projects`) dont le nom encodé commence par celui du chemin donné (même encodage que `mesurer_couts.dossier_transcriptions`) : il couvre donc ce dossier et ses sous-dossiers, pas un dossier frère au nom plus long (`GitHub2` pour `GitHub`). Sans l'option, tous les projets du compte sont comptés.
- Les `*.jsonl` sont parcourus récursivement (sous-agents compris), un appel par `message.id` dédoublonné sur l'ensemble des fichiers retenus (première occurrence chronologique gardée), les messages synthétiques (`id == "<synthetic>"`) écartés.

Écrit `<mois>-<machine>.json` (schéma documenté dans le script, aucun contenu de transcription) puis la page HTML correspondante, à partir du gabarit `skills/bilan-tokens/gabarit.html` : charte Wavestone, un seul point d'injection (`const BILAN=…`), aucun chiffre ni chemin codé en dur dans la page — tout est calculé en JavaScript depuis le JSON.

## Consolider plusieurs PC

```
python scripts/bilan_tokens.py --fusionner 2026-10-pc1.json 2026-10-pc2.json --out mesures/
```

Refuse des bilans de mois différents, la même machine en double, des mix électriques différents, ou un mélange de bilans « tous les projets » et de bilans limités à un dossier. Les dossiers des PC (chemins propres à chaque machine) sont recopiés dans le consolidé. Écrit `<mois>-consolide.json` (modèles sommés, liste des machines, total par machine) et sa page HTML, avec un bouton supplémentaire pour déplier le détail par PC.

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
