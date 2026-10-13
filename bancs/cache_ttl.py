"""Banc : le cache se comporte-t-il comme le contrefactuel du TTL le suppose ?

Pour chaque pause entre deux appels d'un même agent (contexte > 20 k), regarde si l'appel suivant
relit le préfixe (lecture >= 80 % du contexte précédent) ou le réécrit (écriture > 20 k), par TTL
et par durée de pause. Résultat attendu : en TTL 1 h, une pause de 5 min à 1 h est relue ; en TTL
5 min, elle est réécrite.

Usage : python bancs/cache_ttl.py --projet C:/depot1 C:/depot2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


def dossier(projet: Path, racine: Path) -> Path:
    return racine / re.sub(r"[^A-Za-z0-9]", "-", str(projet.resolve()))


def instant(texte: str) -> float:
    return datetime.fromisoformat(texte.replace("Z", "+00:00")).timestamp()


def appels(fichier: Path) -> list[dict]:
    par: dict[str, dict] = {}
    for ligne in fichier.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entree = json.loads(ligne)
        except ValueError:
            continue
        message = entree.get("message") or {}
        if message.get("role") != "assistant" or not message.get("id") or not entree.get("timestamp"):
            continue
        usage = message.get("usage") or {}
        appel = par.setdefault(message["id"], {"ts": instant(entree["timestamp"]), "u": {}})
        if int(usage.get("output_tokens") or 0) >= int(appel["u"].get("output_tokens") or 0):
            appel["u"] = usage
    return sorted(par.values(), key=lambda a: a["ts"])


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    analyseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analyseur.add_argument("--projet", type=Path, nargs="+", default=[Path.cwd()])
    analyseur.add_argument("--racine", type=Path, default=Path.home() / ".claude" / "projects")
    options = analyseur.parse_args()
    resultats: Counter = Counter()
    for projet in options.projet:
        for fichier in dossier(projet, options.racine).rglob("*.jsonl"):
            precedent = None
            for appel in appels(fichier):
                u = appel["u"]
                ecrit = int(u.get("cache_creation_input_tokens") or 0)
                ecrit_1h = int((u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0)
                lu = int(u.get("cache_read_input_tokens") or 0)
                ctx = ecrit + lu + int(u.get("input_tokens") or 0)
                ttl = "1h" if ecrit_1h else ("5m" if ecrit else None)
                if precedent and precedent["ttl"] and precedent["ctx"] > 20_000:
                    pause = appel["ts"] - precedent["ts"]
                    tranche = "<5m" if pause < 300 else ("5m-1h" if pause < 3600 else ">1h")
                    issue = "relu" if lu >= 0.8 * precedent["ctx"] else ("réécrit" if ecrit > 20_000 else "autre")
                    resultats[(precedent["ttl"], tranche, issue)] += 1
                precedent = {"ts": appel["ts"], "ctx": ctx, "ttl": ttl or (precedent["ttl"] if precedent else None)}
    for ttl in ("5m", "1h"):
        for tranche in ("<5m", "5m-1h", ">1h"):
            compte = {i: resultats[(ttl, tranche, i)] for i in ("relu", "réécrit", "autre")}
            total = sum(compte.values())
            if total:
                print(
                    f"TTL {ttl}, pause {tranche:6} : {total:6} pauses ; relu {100 * compte['relu'] / total:5.1f} % ; "
                    f"réécrit {100 * compte['réécrit'] / total:5.1f} %"
                )


if __name__ == "__main__":
    main()
