"""Relanceur d'un run autonome : nouvelle session `claude -p` seulement au-delà d'un seuil de contexte.

Usage : uv run --no-project python -I scripts/relancer_run.py [--projet DOSSIER] [--seuil 100000] [--a-sec] ...

Stdlib seulement ; réutilise ``mesurer_couts`` (lecture des transcriptions). Expérimental : docs/relancer-run.md.
Codes de sortie : 0 FINI, 1 usage, 2 ATTENTE_HUMAINE, 3 BLOQUE / ligne absente / limite atteinte, 4 erreur de la CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesurer_couts as mc

ETAT_DEFAUT = "_bmad-output/implementation-artifacts/run-autonome.md"
ENV_RACINE = "AGENT_COST_KIT_RACINE_TRANSCRIPTIONS"  # surcharge de ~/.claude/projects (tests)
CODES = {"FINI": 0, "ATTENTE_HUMAINE": 2, "BLOQUE": 3}
MOTIF_ETAT = re.compile(r"^\s*ETAT:\s*(CONTINUER|FINI|ATTENTE_HUMAINE|BLOQUE)\b\s*(?:[—–-]+\s*(.*))?$")

REGLE_ARRET = (
    "Tu es lancé par scripts/relancer_run.py : ne t'arrête qu'en fin de vague, aucun agent en cours. "
    "Les agents d'une vague partent dans un même message (appels parallèles et bloquants), jamais en "
    "arrière-plan : en `claude -p`, une notification d'agent arrivée après la fin du tour est perdue."
)
FORMAT_ETAT = "ETAT: CONTINUER|FINI|ATTENTE_HUMAINE|BLOQUE — <raison courte>"
PROMPT_REPRISE = (
    "Relis le fichier d'état du run en entier ({etat}), en particulier la section `## Brief`. "
    "Reprends le run là où le journal s'arrête ; les règles du fichier d'état restent inchangées. "
    f"{REGLE_ARRET} Arrête-toi aussi dès qu'une décision revient à l'utilisateur. "
    "Avant de t'arrêter : réécris `## Brief`, journalise, commite l'état comme d'habitude (PR `chore/etat-run`), "
    f"puis termine par une seule ligne `{FORMAT_ETAT}`."
)
PROMPT_SUITE = f"Continue avec la vague suivante, mêmes règles d'arrêt, même ligne ETAT finale ({FORMAT_ETAT})."


def lire_etat(texte: str) -> tuple[str | None, str]:
    """Dernière ligne « ETAT: … » du résultat : (état, raison), ou (None, '') si absente."""
    trouve: tuple[str | None, str] = (None, "")
    for ligne in texte.splitlines():
        m = MOTIF_ETAT.match(ligne)
        if m:
            trouve = (m.group(1), (m.group(2) or "").strip())
    return trouve


def commande(args, session: str, reprise: bool) -> list[str]:
    claude = args.claude
    base = [sys.executable, claude] if claude.lower().endswith(".py") else [claude]
    return [
        *base, "-p", "--model", args.modele, "--effort", args.effort, "--output-format", "json",
        "--max-budget-usd", str(args.budget_tour), "--permission-mode", args.permission_mode,
        "--resume" if reprise else "--session-id", session,
    ]


def pic_du_tour(dossier: Path, session: str, debut: datetime) -> int:
    """Pic de contexte de la session principale sur les seuls appels postérieurs à ``debut``."""
    chemin = dossier / f"{session}.jsonl"
    if not chemin.is_file():
        return 0
    pics = [a["entree"] + a["lu"] + a["ecrit_5m"] + a["ecrit_1h"] for a in mc.appels(chemin) if mc.instant(a["ts"]) >= debut]
    return max(pics, default=0)


def principal(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--projet", type=Path, default=Path("."))
    ap.add_argument("--etat", type=Path, default=Path(ETAT_DEFAUT), help="fichier d'état (relatif au projet)")
    ap.add_argument("--seuil", type=int, default=100_000, help="pic de contexte (tokens) au-delà duquel on ouvre une nouvelle session")
    ap.add_argument("--max-sessions", type=int, default=12)
    ap.add_argument("--max-tours", type=int, default=40)
    ap.add_argument("--modele", default="claude-opus-5-5")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--budget-tour", type=float, default=10.0, help="$ par tour (--max-budget-usd)")
    ap.add_argument("--permission-mode", default="acceptEdits")
    ap.add_argument("--claude", default=shutil.which("claude"), help="exécutable ; un .py est lancé par l'interpréteur courant (tests)")
    # Racine des transcriptions : sinon variable d'environnement AGENT_COST_KIT_RACINE_TRANSCRIPTIONS, sinon ~/.claude/projects.
    ap.add_argument("--racine", type=Path, default=None, help=argparse.SUPPRESS)
    ap.add_argument("--a-sec", action="store_true", help="affiche les commandes et la décision, n'appelle rien")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    projet = args.projet.resolve()
    etat = args.etat if args.etat.is_absolute() else projet / args.etat
    if not etat.is_file():
        print(f"Fichier d'état introuvable : {etat} (créez-le depuis modeles/run-autonome.md ou passez --etat).", file=sys.stderr)
        return 1
    if not args.a_sec and not args.claude:
        print("Exécutable `claude` introuvable : passez --claude.", file=sys.stderr)
        return 1
    args.claude = args.claude or "claude"
    racine = args.racine or Path(os.environ.get(ENV_RACINE) or Path.home() / ".claude" / "projects")
    dossier = mc.dossier_transcriptions(projet, racine)
    prompt_reprise = PROMPT_REPRISE.format(etat=etat)

    if args.a_sec:
        session = str(uuid.uuid4())
        for titre, reprise, prompt in (("Nouvelle session", False, prompt_reprise), ("Reprise", True, PROMPT_SUITE)):
            print(f"{titre} : {' '.join(commande(args, session, reprise))}\n  prompt : {prompt}")
        print(f"Décision simulée : résultat « ETAT: CONTINUER », pic < {args.seuil} -> reprise ; pic >= {args.seuil} -> nouvelle session.")
        print("A sec : rien n'a été exécuté.")
        return 0

    journal = etat.parent / "relancer-run.jsonl"
    session = None
    cumul_session = 0.0
    pic_precedent = 0
    sessions = tours = relances = 0
    cout = 0.0
    final, raison, code = "BLOQUE", "", 3
    while True:
        nouvelle = session is None or pic_precedent >= args.seuil
        if tours >= args.max_tours:
            final, raison, code = "BLOQUE", f"--max-tours atteint ({args.max_tours})", 3
            break
        if nouvelle and sessions >= args.max_sessions:
            final, raison, code = "BLOQUE", f"--max-sessions atteint ({args.max_sessions})", 3
            break
        if nouvelle:
            if session is not None:
                relances += 1
            session, cumul_session = str(uuid.uuid4()), 0.0
            sessions += 1
        tours += 1
        debut = datetime.now(UTC)
        debut_local = datetime.now().astimezone().isoformat(timespec="seconds")
        proc = subprocess.run(  # aucun délai d'expiration : un tour peut durer des heures
            commande(args, session, not nouvelle),
            input=prompt_reprise if nouvelle else PROMPT_SUITE,
            capture_output=True, text=True, encoding="utf-8", cwd=projet, check=False,
        )
        sortie: dict = {}
        try:
            lu = json.loads(proc.stdout)
            sortie = lu if isinstance(lu, dict) else {}
        except ValueError:
            pass
        cumule = float(sortie.get("total_cost_usd") or 0.0)
        delta = cumule - cumul_session
        cumul_session, cout = cumule, cout + delta
        pic_precedent = pic_du_tour(dossier, session, debut)
        erreur = proc.returncode != 0 or not sortie or bool(sortie.get("is_error")) or str(sortie.get("subtype", "")).startswith("error")
        if erreur:
            etat_lu, raison_lue = "ERREUR", str(sortie.get("result") or proc.stderr or "sortie illisible").strip()[:300]
        else:
            etat_lu, raison_lue = lire_etat(str(sortie.get("result") or ""))
            if etat_lu is None:
                etat_lu, raison_lue = "ABSENT", "ligne « ETAT: … » absente du résultat"
        ligne = {
            "debut": debut_local, "fin": datetime.now().astimezone().isoformat(timespec="seconds"),
            "session": session, "mode": "nouvelle" if nouvelle else "reprise", "pic": pic_precedent,
            "cout_usd": cumule, "cout_delta_usd": round(delta, 6), "etat": etat_lu, "raison": raison_lue, "code": proc.returncode,
        }
        with journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
        if etat_lu == "CONTINUER":
            continue
        final, raison = etat_lu, raison_lue
        code = 4 if etat_lu == "ERREUR" else CODES.get(etat_lu, 3)
        break

    print(f"Sessions : {sessions} ; tours : {tours} ; relances : {relances} ; coût : {cout:.2f} $")
    print(f"État final : {final}" + (f" — {raison}" if raison else "") + f" (code {code})")
    return code


if __name__ == "__main__":
    sys.exit(principal())
