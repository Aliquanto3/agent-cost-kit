# Bilan mensuel des tokens

[← README](../README.md)

Statut : en revue.

## Ce que ça fait

`scripts/bilan_tokens.py` (stdlib seulement, réutilise `mesurer_couts.py` sans dupliquer de table de prix) rejoue le bilan mensuel des tokens Claude Code depuis les transcriptions locales : input détaillé (non caché, écriture 5 min / 1 h, lecture), output (déclaré et réestimé), coût en équivalent API par poste, et impact EcoLogits en fourchette, par modèle.

```
python scripts/bilan_tokens.py --mois 2026-10 --dossier C:/chemin/du/depot
```

- `--mois` (défaut : mois UTC courant) filtre sur le préfixe de l'horodatage UTC de chaque appel, tel qu'écrit par Claude Code.
- `--dossier` limite aux dossiers de projet sous `--racine` (défaut `~/.claude/projects`) dont le nom encodé commence par celui du chemin donné (même encodage que `mesurer_couts.dossier_transcriptions`) : il couvre donc ce dossier et ses sous-dossiers. Sans l'option, tous les projets du compte sont comptés.
- Les `*.jsonl` sont parcourus récursivement (sous-agents compris), un appel par `message.id` dédoublonné sur l'ensemble des fichiers retenus (première occurrence chronologique gardée), les messages synthétiques (`id == "<synthetic>"`) écartés.

Écrit `<mois>-<machine>.json` (schéma documenté dans le script, aucun contenu de transcription) puis la page HTML correspondante, à partir du gabarit `skills/bilan-tokens/gabarit.html` : charte Wavestone, un seul point d'injection (`const BILAN=…`), aucun chiffre ni chemin codé en dur dans la page — tout est calculé en JavaScript depuis le JSON.

## Consolider plusieurs PC

```
python scripts/bilan_tokens.py --fusionner 2026-10-pc1.json 2026-10-pc2.json --out mesures/
```

Refuse des bilans de mois différents ou la même machine en double. Écrit `<mois>-consolide.json` (modèles sommés, liste des machines, total par machine) et sa page HTML, avec un bouton supplémentaire pour déplier le détail par PC.

## Limites

- Transcriptions locales uniquement : un PC sans Claude Code dessus n'y figure pas.
- Le coût est un équivalent au tarif public de l'API, pas la facture d'un abonnement.
- L'impact environnemental (EcoLogits) ne compte que les tokens de **sortie**, comme dans `mesurer_couts.py` : c'est une borne basse.

## Skill

`/bilan-tokens` (ou « bilan tokens », « combien de tokens ce mois », « consommation Claude Code du mois », « consolider mes PC ») lance le script, commente le résultat en quelques lignes et publie la page HTML.
