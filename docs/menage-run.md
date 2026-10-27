# Ménage de clôture : `scripts/menage_run.py`

À lancer à la clôture du run, après la dernière fusion : les worktrees et branches des stories fusionnées restent sinon (point 28 de `amelioration-continue.md`). Stdlib seulement, `git` et `gh` (facultatif) en ligne de commande.

```
uv run --no-project python <kit>/scripts/menage_run.py [--depot DOSSIER] [--distant-nom origin] [--branche-defaut main] \
  [--age-min-heures 24] [--fetch] [--appliquer] [--distant] [--json]
```

**Simulation par défaut** : sans `--appliquer`, rien n'est modifié. `--fetch` lance `git fetch --prune` d'abord (sans lui, aucun accès réseau git). Les branches distantes ne sont supprimées qu'avec `--appliquer --distant`, après avoir montré la liste à Anaël. Code de sortie : 0, 1 si une suppression échoue, 2 en cas d'erreur d'usage.

## Critère « contenu dans la branche par défaut »

Pour la tête T d'une branche (référence : `<distant>/<défaut>`, sinon la branche locale) : T est ancêtre de la référence (`ancêtre`) ; ou `git cherry` ne sort aucun `+` (`patchs équivalents`) ; ou une PR fusionnée porte cette branche avec cette tête (`PR #n fusionnée`, un squash par exemple).

## Exclusions (prioritaires)

La branche par défaut et celle du worktree principal ; une PR ouverte sur la branche ; une activité récente : commit de tête ou dernière entrée du reflog de moins de `--age-min-heures` (le reflog protège une branche de story qui vient d'être créée sur une vieille tête). Sans `gh`, le critère PR est sauté et `--distant` est refusé.

## Worktrees et verrous

Un worktree propre dont la tête est contenue est retiré (`git worktree remove`, sans `-f`). Un dossier disparu est traité par `git worktree prune`. Un verrou dont la raison porte un PID (`pid 12345`) est levé si le processus a disparu ; PID vivant ou absent de la raison : verrou laissé. Ordre : verrous, worktrees, prune, branches locales (une branche extraite dans un worktree restant est sautée), branches distantes.

## Exemple

```
## Branches locales
- supprimer `story-3-1` 1a2b3c4 : PR #41 fusionnée
- garder `story-3-2` 5d6e7f8 : PR #42 ouverte
...
- `git branch story-3-1 1a2b3c4d...`   (restauration)
- 2026-10-27 18:00 · run · ménage · 3 worktrees retirés, 1 verrous levés, 12 branches locales, 0 distantes supprimées · —
```

## Restauration

Après `--appliquer`, une ligne `git branch <nom> <sha>` par branche locale supprimée (et `git push <distant> <sha>:refs/heads/<nom>` pour les distantes) permet de la recréer. La dernière ligne est prête à coller dans le journal de `run-autonome.md` : `scripts/avancement_run.py` la lit comme étape `ménage`.
