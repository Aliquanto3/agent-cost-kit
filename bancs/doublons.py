"""Banc minimal : le dédoublonnage de scripts/mesurer_couts.py (sessions reprises, sous-agent en double).

Fabrique des sessions synthétiques dans un dossier temporaire. La reprise B recopie m2 et m3 de A avec
leurs horodatages d'origine (comme Claude Code), dont un au format « .000Z » contre « Z », puis répond m4
58 min plus tard en réécrivant 50 k tokens de cache. Un sous-agent P figure sous les deux sessions ; son
enfant C n'existe que sous B. Vérifie : session propriétaire de chaque appel, coûts calculés à la main,
expiration de la reprise malgré le retrait des appels recopiés, rattachement de C à l'arbre de P, et le
cas --session B seul (A non retenue : les appels recopiés comptent alors dans B).
Usage : py bancs/doublons.py   (gratuit, sans réseau)
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "mesurer_couts.py"
# claude-sonnet-5-5 : 2 $ / Mtok en entrée, 10 $ en sortie, 0,10 $ en lecture, écriture 5 min à 1,25 x l'entrée.
PETIT = 10 * 2e-6 + 100 * 10e-6 + 1000 * 0.1e-6  # 0,00112 $
REPRISE = 10 * 2e-6 + 100 * 10e-6 + 50_000 * 2e-6 * 1.25  # 0,12602 $


def ligne(mid: str, ts: str, ecrit: int = 0, lu: int = 1000) -> str:
    usage = {"input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": lu, "cache_creation_input_tokens": ecrit}
    message = {"role": "assistant", "id": mid, "model": "claude-sonnet-5-5", "content": [], "usage": usage}
    return json.dumps({"timestamp": ts, "message": message})


def ecrire(chemin: Path, lignes: list[str], meta: dict | None = None) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    if meta:
        chemin.with_suffix(".meta.json").write_text(json.dumps(meta), encoding="utf-8")


def lancer(racine: Path, projet: Path, *extra: str) -> tuple[list[dict], list[dict]]:
    sortie = racine / ("out" + "".join(extra))
    subprocess.run([sys.executable, str(SCRIPT), "--projet", str(projet), "--racine", str(racine / "projets"),
                    "--out", str(sortie), *extra], check=True, capture_output=True)
    with (sortie / "agents.csv").open(encoding="utf-8") as f:
        agents = list(csv.DictReader(f))
    arbres = []
    if (sortie / "arbres.csv").exists():
        with (sortie / "arbres.csv").open(encoding="utf-8") as f:
            arbres = list(csv.DictReader(f))
    return agents, arbres


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        racine = Path(tmp)
        projet = racine / "depot"
        projet.mkdir()
        dossier = racine / "projets" / re.sub(r"[^A-Za-z0-9]", "-", str(projet.resolve()))
        ecrire(dossier / "aaaa1111.jsonl", [ligne("m1", "2026-10-18T10:00:00Z"), ligne("m2", "2026-10-18T10:01:00Z"),
                                            ligne("m3", "2026-10-18T10:02:00.000Z")])
        ecrire(dossier / "bbbb2222.jsonl", [ligne("m2", "2026-10-18T10:01:00.000Z"), ligne("m3", "2026-10-18T10:02:00Z"),
                                            ligne("m4", "2026-10-18T11:00:00Z", ecrit=50_000, lu=0)])
        meta_p = {"agentType": "dev", "description": "parent", "spawnDepth": 1}
        for session in ("aaaa1111", "bbbb2222"):  # même sous-agent P sous les deux sessions
            ecrire(dossier / session / "subagents" / "agent-pppp3333.jsonl",
                   [ligne("s1", "2026-10-18T10:00:30Z"), ligne("s2", "2026-10-18T10:00:40Z")], meta_p)
        ecrire(dossier / "bbbb2222" / "subagents" / "agent-cccc4444.jsonl", [ligne("c1", "2026-10-18T10:00:35Z")],
               {"agentType": "lookup", "description": "enfant", "spawnDepth": 2, "parentAgentId": "pppp3333"})
        tout, arbres = lancer(racine, projet)
        seul, _ = lancer(racine, projet, "--session", "bbbb2222")
        par = {(l["session"], l["agent"]): l for l in tout}
        a, b = par.get(("aaaa1111", "MAIN"), {}), par.get(("bbbb2222", "MAIN"), {})
        b_seul = next((l for l in seul if l["type"] == "MAIN"), {})
        cout = lambda l: float(l.get("cout_usd") or -1)
        proche = lambda x, y: abs(x - y) < 1e-4
        total = lambda lignes: sum(int(l["appels"]) for l in lignes)
        attendu = [
            (total(tout) == 7, f"toutes les sessions : 4 appels principaux + 2 de P + 1 de C, obtenu {total(tout)}"),
            (a.get("appels") == "3" and b.get("appels") == "1", f"A garde m1-m3, B garde m4 : {a.get('appels')} / {b.get('appels')}"),
            (proche(cout(a), 3 * PETIT), f"coût de A {cout(a)} au lieu de {3 * PETIT:.4f}"),
            (proche(cout(b), REPRISE), f"coût de B {cout(b)} au lieu de {REPRISE:.4f}"),
            (b.get("expirations") == "1", f"reprise après 58 min : 1 expiration attendue, obtenu {b.get('expirations')}"),
            (("aaaa1111", "pppp3333") in par and ("bbbb2222", "pppp3333") not in par, "P compté une fois, dans A"),
            (len(arbres) == 1 and arbres[0]["session"] == "aaaa1111" and arbres[0]["agents"] == "2",
             f"C rattaché à l'arbre de P dans A : {[(r['session'], r['racine'], r['agents']) for r in arbres]}"),
            (total(seul) == 6, f"--session bbbb2222 : 3 appels + 2 de P + 1 de C, obtenu {total(seul)}"),
            (b_seul.get("expirations") == "1" and proche(cout(b_seul), 2 * PETIT + REPRISE),
             f"--session bbbb2222 : coût {cout(b_seul)}, expirations {b_seul.get('expirations')}"),
        ]
        echecs = [m for ok, m in attendu if not ok]
        print("\n".join(echecs) or "OK : dédoublonnage conforme")
        return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
