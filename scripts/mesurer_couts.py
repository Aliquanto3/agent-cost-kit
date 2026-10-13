"""Coût réel des agents Claude Code, calculé depuis les transcriptions locales.

Lit ``~/.claude/projects/<projet encodé>/<session>.jsonl`` (session principale) et
``<session>/subagents/agent-<id>.jsonl`` + ``.meta.json`` (sous-agents), puis calcule pour
chaque agent, avec les mêmes règles :

- le coût en équivalent API par catégorie : entrée, écriture du cache (5 min ou 1 h selon
  ``usage.cache_creation``), lecture du cache, sortie ;
- la sortie réestimée : certaines transcriptions ne gardent que l'usage du début de la réponse
  (``output_tokens`` de 3 à 60). On retient max(sortie déclarée, caractères émis / k), borne
  basse puisque la réflexion masquée n'est pas visible ;
- le pic de contexte, le contexte du premier appel, le nombre d'appels, la durée ;
- les expirations du cache (pause plus longue que le TTL, suivie d'une écriture > 20 k tokens) ;
- le coût contrefactuel avec l'autre TTL (5 min <-> 1 h) ;
- les arbres d'agents (racine de profondeur 1 et descendants), pour le coût par story.

Usage :
    python mesurer_couts.py                      # projet = dossier courant, toutes les sessions
    python mesurer_couts.py --projet C:/chemin/du/depot --session 3add3916 --out mesures/
    python mesurer_couts.py --filtre "Banc 6.11"  # agents dont la description contient le motif

Sorties : agents.csv, arbres.csv, resume.md dans --out (par défaut ./mesures-couts/), et un
tableau par agent sur la sortie standard. Aucun contenu de transcription n'est recopié, sauf la
description courte de chaque agent.

Prix vérifiés le 2026-10-13 sur https://platform.claude.com/docs/en/about-claude/pricing.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# $/Mtok : entrée, sortie, lecture du cache. L'écriture coûte 1,25 x l'entrée (5 min) ou 2 x (1 h).
PRIX = {
    "fable": (10.0, 50.0, 0.25),
    "opus": (4.0, 20.0, 0.20),
    "sonnet": (2.0, 10.0, 0.10),
    "haiku": (0.10, 0.50, 0.01),  # prompts de 100 k tokens au plus ; au-delà, tout est x5
}
HAIKU_SEUIL_LONG = 100_000
HAIKU_FACTEUR_LONG = 5.0
ECRITURE = {"5m": 1.25, "1h": 2.0}
TTL_S = {"5m": 300, "1h": 3600}
CARACTERES_PAR_TOKEN = 3.2
SEUIL_REECRITURE = 20_000


def dossier_transcriptions(projet: Path, racine: Path) -> Path:
    """Claude Code encode le chemin du projet en remplaçant tout caractère hors [A-Za-z0-9] par '-'."""
    encode = re.sub(r"[^A-Za-z0-9]", "-", str(projet.resolve()))
    return racine / encode


def famille(modele: str) -> str | None:
    return next((nom for nom in PRIX if nom in modele), None)


def instant(texte: str) -> datetime:
    return datetime.fromisoformat(texte.replace("Z", "+00:00"))


def appels(chemin: Path) -> list[dict]:
    """Un appel par message.id : usage max, caractères émis cumulés sur ses lignes."""
    par_id: dict[str, dict] = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        try:
            entree = json.loads(ligne)
        except ValueError:
            continue
        message = entree.get("message") or {}
        if message.get("role") != "assistant" or not message.get("id"):
            continue
        fam = famille(str(message.get("model", "")))
        if fam is None:
            continue
        appel = par_id.setdefault(
            message["id"],
            {"fam": fam, "ts": entree.get("timestamp", ""), "car": 0, "u": {}},
        )
        for bloc in message.get("content") or []:
            if not isinstance(bloc, dict):
                continue
            if bloc.get("type") == "text":
                appel["car"] += len(bloc.get("text", ""))
            elif bloc.get("type") == "thinking":
                appel["car"] += len(bloc.get("thinking", ""))
            elif bloc.get("type") == "tool_use":
                appel["car"] += len(json.dumps(bloc.get("input"), ensure_ascii=False))
        usage = message.get("usage") or {}
        if usage and int(usage.get("output_tokens") or 0) >= int(appel["u"].get("output_tokens") or 0):
            appel["u"] = usage
    resultat = []
    for appel in par_id.values():
        u = appel["u"]
        ecrit = int(u.get("cache_creation_input_tokens") or 0)
        ecrit_1h = int((u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0)
        sortie_declaree = int(u.get("output_tokens") or 0)
        resultat.append(
            {
                "fam": appel["fam"],
                "ts": appel["ts"],
                "entree": int(u.get("input_tokens") or 0),
                "ecrit_5m": ecrit - ecrit_1h,
                "ecrit_1h": ecrit_1h,
                "lu": int(u.get("cache_read_input_tokens") or 0),
                "sortie_declaree": sortie_declaree,
                "sortie": max(sortie_declaree, int(appel["car"] / CARACTERES_PAR_TOKEN)),
            }
        )
    return sorted((a for a in resultat if a["ts"]), key=lambda a: a["ts"])


def couts(liste: list[dict]) -> dict:
    """Coût réel, expirations et contrefactuel avec l'autre TTL."""
    total: dict[str, float] = defaultdict(float)
    expirations = 0
    reecriture = 0.0
    contrefactuel = 0.0
    precedent = None
    ctx_precedent = 0
    for a in liste:
        p_entree, p_sortie, p_lu = PRIX[a["fam"]]
        ttl = "1h" if a["ecrit_1h"] > a["ecrit_5m"] else "5m"
        autre = "5m" if ttl == "1h" else "1h"
        ecrit = a["ecrit_5m"] + a["ecrit_1h"]
        ctx = a["entree"] + ecrit + a["lu"]
        if a["fam"] == "haiku" and ctx > HAIKU_SEUIL_LONG:
            p_entree, p_sortie, p_lu = (p * HAIKU_FACTEUR_LONG for p in (p_entree, p_sortie, p_lu))
        total["entree"] += a["entree"] * p_entree / 1e6
        total["ecriture"] += (a["ecrit_5m"] * ECRITURE["5m"] + a["ecrit_1h"] * ECRITURE["1h"]) * p_entree / 1e6
        total["lecture"] += a["lu"] * p_lu / 1e6
        total["sortie"] += a["sortie"] * p_sortie / 1e6
        pause = (instant(a["ts"]) - instant(precedent["ts"])).total_seconds() if precedent else 0.0
        nouveau = max(0, ctx - ctx_precedent) if precedent else ecrit
        expire = bool(precedent) and pause > TTL_S[ttl] and ecrit > SEUIL_REECRITURE
        if expire:
            expirations += 1
            reecriture += max(0, ecrit - nouveau) * ECRITURE[ttl] * p_entree / 1e6
        if precedent and pause > TTL_S[autre]:
            alt_ecrit, alt_lu = ctx - a["entree"], 0
        elif expire:
            alt_ecrit, alt_lu = nouveau, ctx - a["entree"] - nouveau
        else:
            alt_ecrit, alt_lu = ecrit, a["lu"]
        contrefactuel += (
            a["entree"] * p_entree + alt_ecrit * ECRITURE[autre] * p_entree + alt_lu * p_lu + a["sortie"] * p_sortie
        ) / 1e6
        precedent = a
        ctx_precedent = ctx + a["sortie"]
    return {
        "cout": sum(total.values()),
        "parts": total,
        "expirations": expirations,
        "reecriture": reecriture,
        "contrefactuel": contrefactuel,
    }


def agents_du_projet(dossier: Path, sessions: list[str] | None):
    for transcription in sorted(dossier.glob("*.jsonl")):
        session = transcription.stem
        if sessions and not any(session.startswith(s) for s in sessions):
            continue
        yield session, "MAIN", transcription, {"agentType": "MAIN", "description": "session principale", "spawnDepth": 0}
        for fichier in sorted((dossier / session / "subagents").glob("agent-*.jsonl")):
            meta_chemin = fichier.with_suffix(".meta.json")
            meta = json.loads(meta_chemin.read_text(encoding="utf-8")) if meta_chemin.exists() else {}
            yield session, fichier.stem[len("agent-") :], fichier, meta


def mediane(valeurs):
    valeurs = [v for v in valeurs if v is not None and v != ""]
    return statistics.median(valeurs) if valeurs else 0


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    analyseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analyseur.add_argument("--projet", type=Path, default=Path.cwd(), help="dossier du dépôt (défaut : dossier courant)")
    analyseur.add_argument("--racine", type=Path, default=Path.home() / ".claude" / "projects")
    analyseur.add_argument("--session", nargs="*", help="préfixes des sessions à retenir (défaut : toutes)")
    analyseur.add_argument("--filtre", help="motif (regex, insensible à la casse) sur la description des agents")
    analyseur.add_argument("--out", type=Path, default=Path("mesures-couts"))
    analyseur.add_argument("--car-par-token", type=float, default=3.2, help="3,2 = borne basse ; 2,2 = médiane observée")
    options = analyseur.parse_args()
    global CARACTERES_PAR_TOKEN
    CARACTERES_PAR_TOKEN = options.car_par_token
    dossier = dossier_transcriptions(options.projet, options.racine)
    if not dossier.is_dir():
        print(f"Aucune transcription sous {dossier}", file=sys.stderr)
        return 1
    motif = re.compile(options.filtre, re.IGNORECASE) if options.filtre else None
    options.out.mkdir(parents=True, exist_ok=True)
    lignes = []
    for session, ident, chemin, meta in agents_du_projet(dossier, options.session):
        description = str(meta.get("description", ""))
        if motif and not motif.search(description):
            continue
        liste = appels(chemin)
        if not liste:
            continue
        c = couts(liste)
        ctxs = [a["entree"] + a["ecrit_5m"] + a["ecrit_1h"] + a["lu"] for a in liste]
        familles = sorted({a["fam"] for a in liste})
        lignes.append(
            {
                "session": session[:8],
                "agent": ident[-8:],
                "parent": str(meta.get("parentAgentId") or "")[-8:],
                "profondeur": meta.get("spawnDepth", ""),
                "type": meta.get("agentType", ""),
                "description": description[:60],
                "jour": liste[0]["ts"][:10],
                "modele": "+".join(familles),
                "appels": len(liste),
                "duree_min": round((instant(liste[-1]["ts"]) - instant(liste[0]["ts"])).total_seconds() / 60, 1),
                "premier_ctx": ctxs[0],
                "pic_ctx": max(ctxs),
                "ecrit_5m": sum(a["ecrit_5m"] for a in liste),
                "ecrit_1h": sum(a["ecrit_1h"] for a in liste),
                "lu": sum(a["lu"] for a in liste),
                "sortie_declaree": sum(a["sortie_declaree"] for a in liste),
                "sortie_estimee": sum(a["sortie"] for a in liste),
                "cout_usd": round(c["cout"], 4),
                "part_ecriture": round(c["parts"]["ecriture"] / c["cout"], 3) if c["cout"] else 0,
                "part_lecture": round(c["parts"]["lecture"] / c["cout"], 3) if c["cout"] else 0,
                "part_sortie": round(c["parts"]["sortie"] / c["cout"], 3) if c["cout"] else 0,
                "expirations": c["expirations"],
                "cout_reecriture_usd": round(c["reecriture"], 4),
                "cout_autre_ttl_usd": round(c["contrefactuel"], 4),
            }
        )
    if not lignes:
        print("Aucun agent retenu.", file=sys.stderr)
        return 1
    with (options.out / "agents.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(lignes[0]))
        writer.writeheader()
        writer.writerows(lignes)

    index = {(l["session"], l["agent"]): l for l in lignes}

    def racine(l):
        vus = 0
        while l["profondeur"] not in (0, 1, "") and l["parent"] and vus < 10:
            parent = index.get((l["session"], l["parent"]))
            if parent is None:
                break
            l, vus = parent, vus + 1
        return l

    arbres: dict = defaultdict(list)
    for l in lignes:
        if l["type"] == "MAIN":
            continue
        r = racine(l)
        arbres[(l["session"], r["agent"])].append(l)
    lignes_arbres = []
    for (session, agent), membres in arbres.items():
        tete = index[(session, agent)]
        cout = sum(m["cout_usd"] for m in membres)
        lignes_arbres.append(
            {
                "session": session,
                "racine": agent,
                "description": tete["description"],
                "jour": tete["jour"],
                "modele": tete["modele"],
                "agents": len(membres),
                "profondeur_max": max(int(m["profondeur"] or 0) for m in membres),
                "appels": sum(m["appels"] for m in membres),
                "pic_ctx": max(m["pic_ctx"] for m in membres),
                "cout_usd": round(cout, 3),
                "part_racine": round(tete["cout_usd"] / cout, 3) if cout and len(membres) > 1 else "",
                "expirations": sum(m["expirations"] for m in membres),
                "cout_reecriture_usd": round(sum(m["cout_reecriture_usd"] for m in membres), 3),
                "cout_autre_ttl_usd": round(sum(m["cout_autre_ttl_usd"] for m in membres), 3),
            }
        )
    if lignes_arbres:
        with (options.out / "arbres.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(lignes_arbres[0]))
            writer.writeheader()
            writer.writerows(lignes_arbres)
    resume(options.out, options.projet, lignes, lignes_arbres)
    # Tableau par agent sur la sortie standard.
    print(f"{'session':8} {'agent':8} {'modèle':7} {'appels':>6} {'min':>6} {'1er ctx':>8} {'pic':>7} {'exp':>3} {'coût $':>8}  description")
    for l in lignes:
        print(
            f"{l['session']:8} {l['agent']:8} {l['modele']:7} {l['appels']:6d} {l['duree_min']:6.1f} "
            f"{l['premier_ctx'] / 1000:6.1f} k {l['pic_ctx'] / 1000:5.0f} k {l['expirations']:3d} {l['cout_usd']:8.3f}  {l['description']}"
        )
    print(f"\nTotal : {sum(l['cout_usd'] for l in lignes):.2f} $ sur {len(lignes)} agents. Détail : {options.out}/")
    return 0


def resume(dossier: Path, projet: Path, lignes: list[dict], arbres: list[dict]) -> None:
    sous = [l for l in lignes if l["type"] != "MAIN"]
    main_ = [l for l in lignes if l["type"] == "MAIN"]
    sortie = [f"# Coût des agents : {projet.name}", ""]
    sortie.append(f"Sortie réestimée à {CARACTERES_PAR_TOKEN} caractères par token (borne basse).")
    sortie.append("")
    sortie.append("| Périmètre | Agents | Coût | Écriture | Lecture | Sortie | Expirations | Coût avec l'autre TTL |")
    sortie.append("|---|---|---|---|---|---|---|---|")
    for nom, groupe in (("Sessions principales", main_), ("Sous-agents", sous)):
        if not groupe:
            continue
        cout = sum(l["cout_usd"] for l in groupe) or 1e-9
        ecr = sum(l["cout_usd"] * l["part_ecriture"] for l in groupe)
        lec = sum(l["cout_usd"] * l["part_lecture"] for l in groupe)
        sor = sum(l["cout_usd"] * l["part_sortie"] for l in groupe)
        sortie.append(
            f"| {nom} | {len(groupe)} | {cout:.2f} $ | {ecr / cout:.0%} | {lec / cout:.0%} | {sor / cout:.0%} "
            f"| {sum(l['expirations'] for l in groupe)} | {sum(l['cout_autre_ttl_usd'] for l in groupe):.2f} $ |"
        )
    gros = [a for a in arbres if a["agents"] > 1]
    if gros:
        couts_ = sorted(a["cout_usd"] for a in gros)
        p90 = couts_[min(len(couts_) - 1, int(0.9 * len(couts_)))]
        sortie += ["", "## Arbres d'agents de plus d'un agent (racine de profondeur 1 et descendants)", ""]
        sortie.append("| Arbres | Coût médian | Coût P90 | Appels médians | Pic médian | Part médiane de la racine | Expirations médianes |")
        sortie.append("|---|---|---|---|---|---|---|")
        sortie.append(
            f"| {len(gros)} | {mediane(couts_):.2f} $ | {p90:.2f} $ | {mediane([a['appels'] for a in gros]):.0f} "
            f"| {mediane([a['pic_ctx'] for a in gros]) / 1000:.0f} k | {mediane([a['part_racine'] for a in gros]):.0%} "
            f"| {mediane([a['expirations'] for a in gros]):.0f} |"
        )
    if sous:
        sortie += ["", "## Contexte du premier appel des sous-agents, par jour (médiane)", ""]
        sortie.append("| Jour | Sous-agents | Premier contexte médian | Pic médian |")
        sortie.append("|---|---|---|---|")
        for jour in sorted({l["jour"] for l in sous}):
            s = [l for l in sous if l["jour"] == jour]
            sortie.append(f"| {jour} | {len(s)} | {mediane([l['premier_ctx'] for l in s]) / 1000:.1f} k | {mediane([l['pic_ctx'] for l in s]) / 1000:.0f} k |")
    (dossier / "resume.md").write_text("\n".join(sortie) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
