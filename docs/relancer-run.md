# Relanceur de run autonome : `scripts/relancer_run.py`

**Expérimental et optionnel** (fiche dans `docs/experimental.md`) : rien ne change dans la chaîne par défaut. Spec : `docs/spec-0.18.0.md`. Stdlib seulement ; réutilise `mesurer_couts.py`.

## Pourquoi

- La nuit, personne ne tape `/clear` : la session d'orchestration grossit sans fin. Sur usine-migration-jira-demo, les 4 plus longues sont montées à 266, 414, 473 et 803 k sans aucune compaction ; une orchestration d'une traite a coûté 68 $ (866 k).
- Test T16 (2026-11-04) : relancer à chaque story coûte +95 % à l'orchestrateur quand son contexte reste petit (43 k pour 4 stories) : chaque nouvelle session repaie l'écriture du cache de son préfixe (~20 k à 1 h).
- Donc : relancer seulement au-delà d'un seuil (défaut 100 k tokens), sinon reprendre la même session (`--resume`, cache chaud). Seuil de rentabilité estimé : retirer au moins 40 à 50 k de contexte par relance.
- Format de reprise validé par T16 (4 reprises sur 4 sans perte) : un « brief » de 40 lignes au plus (tâche quasi verbatim, intention, plan restant, artefacts utiles, pièges), pas un récit (recommandation de l'article arXiv 2611.05306). Il vit dans la section `## Brief` de `modeles/run-autonome.md`.

## Lancement type

```
uv run --no-project python -I <kit>/scripts/relancer_run.py --projet . [--seuil 100000] [--max-sessions 12] [--max-tours 40] \
  [--modele claude-opus-5-5] [--effort medium] [--budget-tour 10] [--permission-mode acceptEdits] [--etat CHEMIN] [--a-sec]
```

`--a-sec` affiche les commandes et la décision sans rien exécuter. Aucun délai d'expiration sur l'appel à `claude` : un tour peut durer des heures. Le prompt passe sur l'entrée standard. Un `--claude` qui finit par `.py` est lancé par l'interpréteur courant (tests). La racine des transcriptions se surcharge par `AGENT_COST_KIT_RACINE_TRANSCRIPTIONS` (tests).

Boucle : un tour est une nouvelle session (prompt de reprise, `--session-id` neuf) à la première fois ou si le pic du tour précédent atteint le seuil, sinon une reprise (`--resume`, prompt de suite). L'orchestrateur ne s'arrête qu'à un point calme (fin de vague, aucun agent en cours, journal à jour) et termine par une ligne `ETAT: CONTINUER|FINI|ATTENTE_HUMAINE|BLOQUE — <raison>`. Le pic est celui de la session principale (sous-agents exclus) : maximum de `input + cache_read + cache_creation` sur les appels postérieurs au début du tour.

## Codes de sortie

| Code | Sens |
|---|---|
| 0 | `FINI` |
| 1 | usage : fichier d'état introuvable, `claude` introuvable |
| 2 | `ATTENTE_HUMAINE` (à brancher sur une notification si besoin) |
| 3 | `BLOQUE`, ligne `ETAT:` absente, `--max-sessions` ou `--max-tours` atteint |
| 4 | erreur de la CLI : code ≠ 0, `is_error`, budget du tour dépassé, sortie illisible |

## `relancer-run.jsonl`

Une ligne JSON par tour, dans le dossier du fichier d'état (le script n'écrit rien d'autre ; l'orchestrateur reste seul à tenir `## Journal`) : `debut`, `fin` (heure locale ISO), `session`, `mode` (`nouvelle` ou `reprise`), `pic` (tokens), `cout_usd` (`total_cost_usd`, **cumulé par session** avec `--resume`), `cout_delta_usd` (coût du tour), `etat`, `raison`, `code` (code de retour de `claude`). Le coût total du résumé final est la somme des deltas.

## Limites

- Un run lancé en interactif puis laissé tourner reste une seule session : lancer le run par le relanceur dès le départ.
- Le relanceur suppose que l'orchestrateur respecte la règle d'arrêt en fin de vague ; sinon un tour peut grossir au-delà du seuil (le seuil est vérifié entre deux tours, pas pendant).
- Les agents d'une vague partent dans un même message (appels parallèles et bloquants), jamais en arrière-plan : en `claude -p`, une notification d'agent arrivée après la fin du tour est perdue.
- Les notifications à l'utilisateur restent celles du run.
- Gain non mesuré : estimation de plusieurs dizaines de dollars sur un run du type 803 k / 531 appels.

## Mesurer le gain au premier run réel

Avec `/agent-cost-kit:mesurer-couts`, relever le coût de l'orchestrateur par story et le comparer aux runs passés du même projet ; le pic par tour de `relancer-run.jsonl` donne la taille de contexte évitée. Critère : coût de l'orchestrateur par story inférieur à celui des runs d'une seule session, sans story reprise à cause d'une perte de contexte.
