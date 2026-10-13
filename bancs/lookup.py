"""Banc : un modèle est-il fiable pour chercher dans le dépôt (agent lookup) ?

Deux sous-commandes :
- ``questions`` génère 20 questions à réponse vérifiable sur un dépôt Python (définitions,
  constantes, fichiers utilisateurs d'un symbole) ;
- ``noter`` note les réponses JSON de ``claude -p --output-format json`` (une par question et par
  modèle, nommées ``r<i>-<modele>.json``). Relire à la main les cas notés faux : le corrigé peut se
  tromper (mot présent seulement dans une docstring, échappement d'une regex).

Usage :
    python bancs/lookup.py questions --depot C:/depot --src src/paquet --out bancs-lookup/
    # pour chaque question i et chaque modèle m (voir bancs/README.md) :
    #   claude -p "<question>" --model m --effort low --append-system-prompt "<consigne de agents/lookup.md>" ...
    python bancs/lookup.py noter --out bancs-lookup/ --modeles haiku sonnet
"""

from __future__ import annotations

import argparse
import ast
import json
import random
import re
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path


def generer(depot: Path, src: str, out: Path) -> None:
    random.seed(7)
    defs, consts = [], []
    for fichier in sorted((depot / src).rglob("*.py")):
        rel = fichier.relative_to(depot).as_posix()
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for n in arbre.body:
            if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and not n.name.startswith("_"):
                defs.append((n.name, rel, n.lineno, "classe" if isinstance(n, ast.ClassDef) else "fonction"))
            if (
                isinstance(n, ast.Assign)
                and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id.isupper()
                and isinstance(n.value, ast.Constant)
                and isinstance(n.value.value, (int, float, str))
                and len(str(n.value.value)) < 40
            ):
                consts.append((n.targets[0].id, rel, n.lineno, str(n.value.value)))
    uniques_d = Counter(d[0] for d in defs)
    uniques_c = Counter(c[0] for c in consts)
    defs = [d for d in defs if uniques_d[d[0]] == 1]
    consts = [c for c in consts if uniques_c[c[0]] == 1]
    questions = []
    for nom, rel, ligne, genre in random.sample(defs, 8):
        questions.append({"q": f"Où est définie la {genre} `{nom}` ? Donne `chemin:ligne`.", "type": "def", "fichier": rel, "ligne": ligne})
    for nom, rel, ligne, valeur in random.sample(consts, 6):
        questions.append(
            {"q": f"Quelle est la valeur de la constante `{nom}`, et où est-elle définie (`chemin:ligne`) ?",
             "type": "const", "fichier": rel, "ligne": ligne, "valeur": valeur}
        )
    random.shuffle(defs)
    for nom, rel, _, _ in defs:
        if sum(q["type"] == "usages" for q in questions) == 6:
            break
        trouves = subprocess.run(["git", "-C", str(depot), "grep", "-l", "-w", nom, "--", src], capture_output=True, text=True, check=False).stdout.split()
        usages = sorted(set(trouves) - {rel})
        if 1 <= len(usages) <= 3:
            questions.append(
                {"q": f"Quels fichiers de `{src}/` (hors celui qui la définit) utilisent `{nom}` ? Donne la liste complète des chemins.",
                 "type": "usages", "fichiers": usages, "definition": rel}
            )
    out.mkdir(parents=True, exist_ok=True)
    (out / "questions.json").write_text(json.dumps(questions, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(questions)} questions dans {out / 'questions.json'}")


def noter(out: Path, modeles: list[str]) -> None:
    questions = json.loads((out / "questions.json").read_text(encoding="utf-8"))

    def refs(texte: str) -> list[tuple[str, int]]:
        return [(m.group(1).replace("\\", "/").split("/")[-1], int(m.group(2))) for m in re.finditer(r"([\w./\\-]+\.py):(\d+)", texte)]

    for modele in modeles:
        justes, couts, a_relire = 0, [], []
        for i, q in enumerate(questions):
            chemin = out / f"r{i}-{modele}.json"
            donnees = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() and chemin.stat().st_size else {}
            reponse = donnees.get("result", "") or ""
            couts.append(donnees.get("total_cost_usd", 0))
            if q["type"] in ("def", "const"):
                bon = any(f == q["fichier"].split("/")[-1] and abs(n - q["ligne"]) <= 2 for f, n in refs(reponse))
                if q["type"] == "const":
                    bon = bon and q["valeur"] in reponse.replace("\\\\", "\\")
            else:
                cites = set(re.findall(r"[\w/]+\.py", reponse.replace("\\", "/"))) - {q["definition"]}
                bon = {c for c in cites if "/" in c} == set(q["fichiers"])
            justes += bon
            if not bon:
                a_relire.append(f"q{i} : {reponse[:120]!r}")
        print(f"{modele} : {justes}/{len(questions)} justes ; coût {sum(couts):.3f} $ (médiane {statistics.median(couts):.4f} $)")
        for ligne in a_relire:
            print("   à relire :", ligne)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    analyseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = analyseur.add_subparsers(dest="commande", required=True)
    q = sous.add_parser("questions")
    q.add_argument("--depot", type=Path, required=True)
    q.add_argument("--src", required=True, help="dossier du code, relatif au dépôt (ex. src/paquet)")
    q.add_argument("--out", type=Path, default=Path("bancs-lookup"))
    n = sous.add_parser("noter")
    n.add_argument("--out", type=Path, default=Path("bancs-lookup"))
    n.add_argument("--modeles", nargs="+", default=["haiku", "sonnet"])
    options = analyseur.parse_args()
    if options.commande == "questions":
        generer(options.depot, options.src, options.out)
    else:
        noter(options.out, options.modeles)


if __name__ == "__main__":
    main()
