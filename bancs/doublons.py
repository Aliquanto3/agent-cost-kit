"""Banc minimal : le dédoublonnage de scripts/mesurer_couts.py (sessions reprises, sous-agent en double).

Fabrique deux sessions synthétiques dans un dossier temporaire : B recopie 2 réponses de A (mêmes
message.id) et un sous-agent figure sous les deux. Vérifie que chaque appel n'est compté qu'une fois,
y compris avec --session B seul (A non retenue : les appels recopiés comptent alors dans B).
Usage : py bancs/doublons.py   (gratuit, sans réseau)
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "mesurer_couts.py"


def ligne(mid: str, ts: str) -> str:
    usage = {"input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 0}
    message = {"role": "assistant", "id": mid, "model": "claude-sonnet-5-5", "content": [], "usage": usage}
    return json.dumps({"timestamp": ts, "message": message})


def ecrire(chemin: Path, ids: list[str]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(ligne(m, f"2026-10-18T10:0{i}:00Z") for i, m in enumerate(ids)) + "\n", encoding="utf-8")


def lancer(racine: Path, projet: Path, *extra: str) -> list[dict]:
    sortie = racine / "out"
    subprocess.run([sys.executable, str(SCRIPT), "--projet", str(projet), "--racine", str(racine / "projets"),
                    "--out", str(sortie), *extra], check=True, capture_output=True)
    with (sortie / "agents.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        racine = Path(tmp)
        projet = racine / "depot"
        projet.mkdir()
        import re
        dossier = racine / "projets" / re.sub(r"[^A-Za-z0-9]", "-", str(projet.resolve()))
        ecrire(dossier / "aaaa1111.jsonl", ["m1", "m2", "m3"])
        ecrire(dossier / "bbbb2222.jsonl", ["m2", "m3", "m4"])  # reprise : recopie m2 et m3
        for session in ("aaaa1111", "bbbb2222"):  # même sous-agent sous les deux sessions
            ecrire(dossier / session / "subagents" / "agent-ffff3333.jsonl", ["s1", "s2"])
        total = lambda lignes: sum(int(l["appels"]) for l in lignes)
        tout = lancer(racine, projet)
        seul = lancer(racine, projet, "--session", "bbbb2222")
        attendu = [
            (total(tout) == 6, f"toutes les sessions : 4 appels principaux + 2 du sous-agent, obtenu {total(tout)}"),
            (total(seul) == 5, f"--session bbbb2222 : 3 appels + 2 du sous-agent, obtenu {total(seul)}"),
            ({l["session"] for l in tout if l["type"] == "MAIN"} == {"aaaa1111", "bbbb2222"}, "sessions d'origine conservées"),
            (sum(1 for l in tout if l["type"] != "MAIN") == 1, "sous-agent en double compté une fois"),
        ]
        echecs = [m for ok, m in attendu if not ok]
        print("\n".join(echecs) or "OK : dédoublonnage conforme")
        return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
