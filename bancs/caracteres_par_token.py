"""Banc : combien de caractères par token pour la sortie des agents ?

Tire des réponses complètes (sortie déclarée >= 800 tokens, sans réflexion) et des réponses à
l'usage tronqué (sortie déclarée <= 60 tokens pour >= 1 500 caractères), compte le texte visible de
chacune avec l'endpoint gratuit count_tokens, et compare à la sortie déclarée. Si le rapport
« sortie déclarée / count_tokens » vaut environ 1 sur les réponses complètes, la médiane des
caractères par token est la valeur à mettre dans --car-par-token de mesurer_couts.py.

Clé : variable d'environnement ANTHROPIC_API_KEY (le script ne lit aucun fichier de secrets).
Usage : python bancs/caracteres_par_token.py --projet C:/depot1 C:/depot2 [--n 100]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def dossier(projet: Path, racine: Path) -> Path:
    return racine / re.sub(r"[^A-Za-z0-9]", "-", str(projet.resolve()))


def reponses(dossiers: list[Path]):
    for d in dossiers:
        for fichier in d.rglob("*.jsonl"):
            par: dict[str, dict] = {}
            for ligne in fichier.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    entree = json.loads(ligne)
                except ValueError:
                    continue
                message = entree.get("message") or {}
                modele = str(message.get("model", ""))
                if message.get("role") != "assistant" or not message.get("id") or not modele.startswith("claude-"):
                    continue
                r = par.setdefault(message["id"], {"modele": modele, "texte": [], "reflexion": False, "sortie": 0})
                for bloc in message.get("content") or []:
                    if not isinstance(bloc, dict):
                        continue
                    if bloc.get("type") == "text":
                        r["texte"].append(bloc.get("text", ""))
                    elif bloc.get("type") == "thinking":
                        r["reflexion"] = True
                        r["texte"].append(bloc.get("thinking", ""))
                    elif bloc.get("type") == "tool_use":
                        r["texte"].append(json.dumps(bloc.get("input"), ensure_ascii=False))
                r["sortie"] = max(r["sortie"], int((message.get("usage") or {}).get("output_tokens") or 0))
            for r in par.values():
                r["texte"] = "\n".join(r["texte"])
                yield r


def compter(cle: str, modele: str, texte: str) -> int:
    corps = json.dumps({"model": modele, "messages": [{"role": "user", "content": texte}]}).encode()
    requete = urllib.request.Request(
        "https://api.anthropic.com/v1/messages/count_tokens",
        data=corps,
        headers={"x-api-key": cle, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    for essai in range(5):
        try:
            with urllib.request.urlopen(requete, timeout=60) as reponse:
                return json.load(reponse)["input_tokens"]
        except urllib.error.HTTPError as erreur:
            if erreur.code != 429:
                raise
            time.sleep(5 * (essai + 1))
    raise RuntimeError("count_tokens : 429 persistant")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    analyseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analyseur.add_argument("--projet", type=Path, nargs="+", default=[Path.cwd()])
    analyseur.add_argument("--racine", type=Path, default=Path.home() / ".claude" / "projects")
    analyseur.add_argument("--n", type=int, default=100, help="réponses tirées par lot")
    options = analyseur.parse_args()
    cle = os.environ.get("ANTHROPIC_API_KEY")
    if not cle:
        raise SystemExit("ANTHROPIC_API_KEY absente de l'environnement.")
    tout = list(reponses([dossier(p, options.racine) for p in options.projet]))
    random.seed(13)
    lots = {
        "complètes, sans réflexion": [r for r in tout if not r["reflexion"] and r["sortie"] >= 800 and len(r["texte"]) >= 1500],
        "usage tronqué": [r for r in tout if r["sortie"] <= 60 and len(r["texte"]) >= 1500],
    }
    print(f"{len(tout)} réponses ; " + " ; ".join(f"{nom} : {len(lot)}" for nom, lot in lots.items()))
    base: dict[str, int] = {}
    for nom, lot in lots.items():
        lignes = []
        for r in random.sample(lot, min(options.n, len(lot))):
            if r["modele"] not in base:
                base[r["modele"]] = compter(cle, r["modele"], "a") - 1
            lignes.append((len(r["texte"]), compter(cle, r["modele"], r["texte"]) - base[r["modele"]], r["sortie"]))
            time.sleep(0.2)
        if not lignes:
            continue
        cpt = sorted(c / n for c, n, _ in lignes)
        print(
            f"\n{nom} ({len(lignes)}) : caractères par token, médiane {statistics.median(cpt):.2f} "
            f"(P10 {cpt[len(cpt) // 10]:.2f}, P90 {cpt[9 * len(cpt) // 10]:.2f})"
        )
        if nom.startswith("complètes"):
            rapports = sorted(s / n for _, n, s in lignes)
            print(f"  sortie déclarée / count_tokens : médiane {statistics.median(rapports):.2f} (attendu : environ 1)")


if __name__ == "__main__":
    main()
