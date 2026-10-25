# CI découpée pour un run autonome

[← README](../README.md)

Recette pour ramener le job de CI le plus long sous 6 minutes dans un projet Python (uv, pytest), sans toucher aux tests. Source : WaveStack, 2026-10-25, PR #98 et #100 du dépôt Aliquanto3/wavestack. Fichiers du kit : [`modeles/ci-run-autonome.yml`](../modeles/ci-run-autonome.yml) (le workflow) et [`scripts/fusion_durees.py`](../scripts/fusion_durees.py) (les durées).

## Quand le faire

Quand le job le plus long dépasse environ 10 minutes. En run autonome, la CI de branche est la suite complète et la porte de fusion : chaque minute de CI retarde la fusion, et les fusions se font en série. Sous ce seuil, le découpage coûte plus (réglage, fichiers de durées à rafraîchir) qu'il ne rapporte.

## Ce qui a été mesuré (WaveStack, 6 942 tests)

| Étape | Windows | Ubuntu |
|---|---|---|
| Avant : un job par OS, `uv run pytest -q` | 17 min 13 (job de 17 à 18 min) | 9 min 21 |
| 4 groupes, découpés au nombre de tests (sans durées) | de 22 s à 9 min 10 selon le groupe | |
| 4 groupes, avec un fichier de durées par OS (7 132 tests, total de 15,9 min Windows et 9,4 min Ubuntu) | job le plus long 5 min 42 (groupes de 4 min 04 à 5 min 42) | job le plus long 2 min 41 |

Sans durées, les groupes sont déséquilibrés parce que les tests lents se regroupent (même fichier, même dossier) : le découpage au nombre de tests ne vaut presque rien. Les durées sont la moitié du gain.

## Étapes dans l'ordre

1. **Ajouter pytest-split** : `uv add --dev pytest-split==0.11.0`. Version épinglée.
2. **Copier le modèle** `modeles/ci-run-autonome.yml` dans `.github/workflows/ci.yml` et l'adapter (versions d'actions, commande d'installation, liste des OS). Il contient : matrice `os` x `group` [1..4], `fail-fast: false`, ruff dans le groupe 1 seulement, `--splits 4 --group N`, `--durations=40`, `--store-durations --clean-durations`, remontée des durées en artefact et `concurrency` qui annule le run précédent d'une PR.
3. **Valider le workflow** avec actionlint (ou un chargeur YAML qui refuse les clés en double), pas avec PyYAML seul : voir les pièges.
4. **Premier passage** : pousser sans fichiers de durées. Pytest-split découpe au nombre de tests (avertissement attendu) ; les jobs relèvent les durées et les remontent en artefacts `test-durations-<os>-<groupe>`.
5. **Commiter les fichiers par OS** : sur ce run, `uv run python scripts/fusion_durees.py --run <id> --repo OWNER/NOM` télécharge les artefacts (`gh run download`), fusionne les 4 fichiers de chaque OS en `test-durations-<os>.json` et affiche par OS le nombre de tests, le total et l'écart estimé entre groupes. Commiter ces fichiers à la racine (ou là où pointe `--durations-path`).
6. **Passages équilibrés** : les runs suivants lisent ces fichiers. Relire `--durations=40` de chaque groupe, sur les deux OS : un test lent sous Windows seulement signale une opération système, pas une logique lente (voir le cas NTFS ci-dessous).

## Rafraîchir les durées

Quand l'écart entre le groupe le plus long et le plus court dépasse environ 2 minutes, ou après un gros lot de tests : télécharger les artefacts d'une CI récente et refaire l'étape 5 (`fusion_durees.py --run <id>`, ou `--depuis <dossier>` sans `gh`). `--groupes 4` règle le nombre de groupes de l'estimation ; `--algo blocs` (défaut, tranches consécutives, comme pytest-split) ou `glouton`. Les tests sans durée connue reçoivent la moyenne : un lot de tests neufs ne déséquilibre pas durablement.

## Pièges rencontrés

- **Clé `group:` écrite deux fois dans la matrice** : GitHub rejette le workflow sans lancer de job (« workflow file issue »). PyYAML (`yaml.safe_load`) accepte la clé en double sans rien dire. Valider avec actionlint.
- **Artefact sans fichier** : upload-artifact v4 ignore les fichiers cachés (nom qui commence par un point) depuis la v4.4 : « No valid artifacts found ». Nommer le fichier sans point, ou poser `include-hidden-files: true`.
- **PR sans CI** : une PR en conflit n'a pas de CI (« no checks reported »). Cas vu : `.gitignore` modifié des deux côtés. Fusionner la branche principale dans la branche (merge, pas de force-push).
- **Contrôles requis** : le dépôt WaveStack est public (minutes gratuites) et sans protection de branche, donc renommer les jobs ne casse aucun check requis. Avec une protection de branche, mettre à jour les noms des checks requis (`tests (ubuntu-latest, groupe 1/4)`, etc.).
- **Tests instables** : sur WaveStack, 9 CI rouges en 5 jours ; un seul échec au hasard (un tirage aléatoire sans graine), les huit autres étaient de vrais défauts. Ne pas relancer par réflexe.

## Cas trouvé grâce à `--durations=40` : fichier creux sous NTFS

Cinq tests créaient un faux blob GGUF de plusieurs Gio par `f.truncate(size)`, en comptant sur un fichier creux. Sous NTFS, un fichier n'est creux qu'avec le drapeau sparse, et même avec lui `truncate` (SetEndOfFile) coûte 4,3 s pour 5 Gio. En CI Windows, ces tests prenaient de 11 à 33 s chacun, et c'est la comparaison avec Ubuntu qui les a désignés. Mesures locales : de 2,1 à 5,8 s par test, puis moins de 0,2 s ; les deux fichiers de tests passent de 43,8 s à 18,0 s.

Correctif : poser FSCTL_SET_SPARSE sur le fichier (sans droits administrateur), puis `seek(size - 1)` et écrire un octet : moins de 10 ms. Taille réelle conservée, rien de mocké. Si l'appel échoue (FAT, partage réseau), un `warnings.warn` et le fichier reste correct, seulement lent. Ailleurs qu'en Windows, `truncate` seul.

```python
import os
import sys
import warnings

FSCTL_SET_SPARSE = 0x900C4


def make_sparse(f, size: int) -> None:
    """Donne au fichier ouvert en écriture binaire `f` la taille `size` sans écrire de données."""
    if sys.platform == "win32":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        handle = msvcrt.get_osfhandle(f.fileno())
        octets = wintypes.DWORD(0)
        ok = ctypes.windll.kernel32.DeviceIoControl(
            wintypes.HANDLE(handle), FSCTL_SET_SPARSE, None, 0, None, 0, ctypes.byref(octets), None
        )
        if not ok:
            warnings.warn("FSCTL_SET_SPARSE a échoué : fichier plein, création lente", stacklevel=2)
        if size > 0:
            f.seek(size - 1)
            f.write(b"\0")
        f.flush()
    else:
        f.truncate(size)
```

À mettre dans un module d'aide des tests (`conftest.py` ou `tests/helpers.py`), à utiliser partout où un test fabrique un gros fichier factice.

## Reste à faire côté kit

`cost-kit-install` ne propose pas encore ce modèle (entrée 23 de [amélioration continue](amelioration-continue.md)).
