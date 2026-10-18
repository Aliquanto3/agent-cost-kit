"""Avancement d'un run autonome BMAD : état par epic, vague et story, rythme, estimation de fin.

Sources, en lecture seule, dans le projet :
- ``_bmad-output/implementation-artifacts/sprint-status.yaml`` : statuts (``development_status``) ;
- ``_bmad-output/implementation-artifacts/run-autonome.md`` : périmètre, tables de vagues
  (``| Vague | Stories en parallèle | Après |``) et section « Journal » ;
- ``git log`` : heures de repli pour les lignes du journal sans heure.

Convention du journal : ``- AAAA-MM-JJ HH:MM · story · étape · résultat · commit``. Les lignes sans heure
sont datées, dans l'ordre : par la ligne de commit « suivi du run … (story X fusionnée) » (fusions), par l'heure
du commit cité dans la dernière colonne, puis par interpolation entre les lignes voisines datées.

Python 3.10+, aucune dépendance (le sous-ensemble YAML de ``sprint-status.yaml`` est lu à la main).

Usage : python avancement_run.py [projet] [--json] [--maintenant "AAAA-MM-JJ HH:MM"]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

DOSSIER = Path("_bmad-output") / "implementation-artifacts"
ID = re.compile(r"\d+\.\d+")
FENETRE_H = 3.0

# Barème : dernière étape journalisée -> étape en cours, pourcentage.
BAREME = [
    ("dev lancé", "dev en cours", 30),
    ("dev fini", "second-avis en cours", 60),
    ("second-avis fini", "review en cours", 75),
    ("review finie", "fusion en cours", 90),
    ("fusion faite", "CI de main", 95),
    ("CI rouge", "correctif CI", 85),
]
POURCENT = {"dev lancé": 30, "dev fini": 60, "second-avis fini": 75, "review finie": 90,
            "fusion faite": 95, "CI rouge": 85}
ETAPE = {k: e for k, e, _ in BAREME}


# ----------------------------------------------------------------------------- lecture

def lire_statuts(chemin: Path) -> dict[str, str]:
    """Sous-ensemble YAML : clés plates sous ``development_status:``."""
    statuts: dict[str, str] = {}
    dedans = False
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        brut = ligne.split("#", 1)[0].rstrip()
        if not brut.strip():
            continue
        if not ligne.startswith((" ", "\t")):
            dedans = brut.strip() == "development_status:"
            continue
        if dedans and ":" in brut:
            cle, _, val = brut.strip().partition(":")
            statuts[cle.strip().strip("\"'")] = val.strip().strip("\"'")
    return statuts


def ids_statut(statuts: dict[str, str]) -> dict[str, str]:
    """Clés ``N-M-slug`` -> statut par identifiant ``N.M``."""
    sortie = {}
    for cle, val in statuts.items():
        m = re.match(r"(\d+)-(\d+)-", cle)
        if m:
            sortie[f"{m[1]}.{m[2]}"] = val
    return sortie


def cellules(ligne: str) -> list[str]:
    return [c.strip() for c in ligne.strip().strip("|").split("|")]


def plage_epics(texte: str) -> set[int]:
    m = re.search(r"Epics?\s+(\d+)\s+à\s+(\d+)", texte)
    return set(range(int(m[1]), int(m[2]) + 1)) if m else set()


def lire_plan(texte: str) -> dict:
    """Vagues, dépendances, types, pivots, parallélisme et epics hors run."""
    lignes = texte.splitlines()
    plan = {"vagues": {}, "ordre": [], "sprint": {}, "deps": {}, "pivot": set(), "type": {},
            "parallelisme": 3, "hors_run": set()}
    m = re.search(r"Au plus\s+(\d+)\s+stories", texte)
    if m:
        plan["parallelisme"] = int(m[1])
    sprint = ""
    bruts: dict[str, str] = {}
    for ligne in lignes:
        if ligne.startswith("#"):
            m = re.search(r"Sprint\s+(\d+)", ligne)
            sprint = m[0] if m else ""
            continue
        if not ligne.startswith("|"):
            continue
        c = cellules(ligne)
        if len(c) >= 2 and "Hors run" in c[0]:
            plan["hors_run"] = plage_epics(c[1]) or plan["hors_run"]
        if len(c) >= 3 and re.fullmatch(r"[VW]\d+", c[0]):
            vague = c[0]
            ids = []
            for part in c[1].split("·"):
                m = ID.search(part)
                if not m:
                    continue
                sid = m[0]
                ids.append(sid)
                if "★" in part:
                    plan["pivot"].add(sid)
                t = re.search(r"\((mixte|humaine)\)", part)
                plan["type"][sid] = t[1] if t else "dev"
                plan["sprint"][sid] = sprint
            plan["vagues"][vague] = ids
            plan["ordre"].append(vague)
            bruts[vague] = c[2]
    tous = [s for v in plan["ordre"] for s in plan["vagues"][v]]
    for vague in plan["ordre"]:
        cellule, ids = bruts[vague], plan["vagues"][vague]
        epics = plage_epics(cellule)
        if epics:
            for sid in ids:
                plan["deps"][sid] = {s for s in tous if int(s.split(".")[0]) in epics and s != sid}
        elif "←" in cellule:
            for seg in cellule.split(";"):
                if "←" in seg:
                    gauche, _, droite = seg.partition("←")
                    cible = ID.search(gauche)
                    if cible:
                        plan["deps"][cible[0]] = set(ID.findall(droite))
        else:
            for sid in ids:
                plan["deps"][sid] = set(ID.findall(cellule))
    for sid in tous:
        plan["deps"].setdefault(sid, set())
    return plan


def lire_journal(texte: str) -> list[dict]:
    dedans = False
    evts = []
    for ligne in texte.splitlines():
        if ligne.startswith("#"):
            dedans = ligne.strip("# ").lower().startswith("journal")
            continue
        if not dedans or not ligne.startswith("- "):
            continue
        p = ligne[2:].split(" · ")
        if len(p) < 4:
            continue
        m = re.match(r"(\d{4}-\d\d-\d\d)(?:[ T](\d\d:\d\d))?", p[0].strip())
        if not m:
            continue
        commit = p[-1].strip("` ") if len(p) >= 5 else ""
        resultat = " · ".join(p[3:-1] if len(p) >= 5 else p[3:])
        evts.append({
            "date": m[1], "heure": m[2], "stories": ID.findall(p[1]),
            "etape": normaliser_etape(p[2]), "brut": p[2].strip(), "resultat": resultat.strip(),
            "commit": commit if re.fullmatch(r"[0-9a-f]{7,40}", commit) else "",
            "t": None, "source": "",
        })
    return evts


def normaliser_etape(brut: str) -> str:
    e = brut.strip().lower()
    for cle in ("second-avis", "review", "fusion", "ci", "blocked", "attente humaine", "report",
                "décision", "dev"):
        if e.startswith(cle):
            return cle
    return e


def commits_git(projet: Path) -> list[tuple[str, datetime, str]]:
    try:
        r = subprocess.run(
            ["git", "-C", str(projet), "log", "--all", "--date=format-local:%Y-%m-%d %H:%M",
             "--format=%H|%ad|%s"], capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    sortie = []
    for ligne in r.stdout.splitlines():
        h, _, reste = ligne.partition("|")
        d, _, sujet = reste.partition("|")
        try:
            sortie.append((h, datetime.strptime(d, "%Y-%m-%d %H:%M"), sujet))
        except ValueError:
            continue
    return sortie


# ----------------------------------------------------------------------------- horodatage

def dater(evts: list[dict], commits: list[tuple[str, datetime, str]], repli: datetime | None) -> None:
    """Renseigne ``t`` et ``source`` : journal > suivi du run > commit cité > interpolation > mtime."""
    suivi: dict[str, datetime] = {}
    for _, d, sujet in commits:
        if "suivi du run" in sujet and "fusionn" in sujet:
            for sid in ID.findall(sujet):
                suivi[sid] = min(d, suivi.get(sid, d))  # le plus ancien (le suivi initial)
    par_hash = {h: d for h, d, _ in commits}
    for e in evts:
        if e["heure"]:
            e["t"], e["source"] = datetime.strptime(f"{e['date']} {e['heure']}", "%Y-%m-%d %H:%M"), "journal"
            continue
        if e["etape"] == "fusion" and e["stories"] and all(s in suivi for s in e["stories"]):
            e["t"], e["source"] = max(suivi[s] for s in e["stories"]), "suivi"
            continue
        if e["commit"]:
            for h, d in par_hash.items():
                if h.startswith(e["commit"]):
                    e["t"], e["source"] = d, "commit"
                    break
    # Un repli n'est retenu que s'il garde l'ordre du journal, borné par la prochaine heure explicite.
    suffixe = [None] * (len(evts) + 1)
    for i in range(len(evts) - 1, -1, -1):
        suffixe[i] = evts[i]["t"] if evts[i]["source"] == "journal" else suffixe[i + 1]
    maxi = None
    for i, e in enumerate(evts):
        if e["t"] is not None:
            if e["source"] != "journal" and ((maxi and e["t"] < maxi) or (suffixe[i] and e["t"] > suffixe[i])):
                e["t"], e["source"] = None, ""
            else:
                maxi = max(maxi, e["t"]) if maxi else e["t"]
    ancres = [i for i, e in enumerate(evts) if e["t"] is not None]
    if not ancres and evts and repli:
        evts[-1]["t"], evts[-1]["source"] = repli, "mtime"
        ancres = [len(evts) - 1]
    for i, e in enumerate(evts):
        if e["t"] is not None or not ancres:
            continue
        avant = [a for a in ancres if a < i]
        apres = [a for a in ancres if a > i]
        if avant and apres:
            a, b = evts[avant[-1]]["t"], evts[apres[0]]["t"]
            e["t"] = a + (b - a) * (i - avant[-1]) / (apres[0] - avant[-1])
        else:
            e["t"] = evts[(avant or apres)[-1 if avant else 0]]["t"]
        e["source"] = "interpolé"


# ----------------------------------------------------------------------------- analyse

def etape_story(evts: list[dict]) -> tuple[str, str, int] | None:
    """Dernière étape connue d'une story (jalon, étape en cours, %), None si rien ou non lancée."""
    jalon = None
    for e in evts:
        et, r = e["etape"], e["resultat"].lower()
        if et == "dev":
            jalon = "dev lancé" if "lanc" in r else ("dev fini" if "fini" in r else jalon)
        elif et == "second-avis":
            jalon = "second-avis fini"
        elif et == "review":
            jalon = "review finie"
        elif et == "fusion":
            jalon = "fusion faite"
        elif et == "ci":
            jalon = "CI rouge" if "rouge" in r else ("fusion faite" if jalon else jalon)
        elif et == "report" and "non lancé" in r:
            jalon = None
    return (jalon, ETAPE[jalon], POURCENT[jalon]) if jalon else None


def analyser(projet: Path, maintenant: datetime) -> dict:
    dossier = projet / DOSSIER
    fichier_plan, fichier_statut = dossier / "run-autonome.md", dossier / "sprint-status.yaml"
    texte = fichier_plan.read_text(encoding="utf-8")
    plan = lire_plan(texte)
    statuts = ids_statut(lire_statuts(fichier_statut))
    evts = lire_journal(texte)
    repli = datetime.fromtimestamp(fichier_plan.stat().st_mtime)
    dater(evts, commits_git(projet), repli)

    par_story: dict[str, list[dict]] = {}
    for e in evts:
        for s in e["stories"]:
            par_story.setdefault(s, []).append(e)

    stories = {}
    for vague in plan["ordre"]:
        for sid in plan["vagues"][vague]:
            st = statuts.get(sid, "backlog")
            hist = par_story.get(sid, [])
            info = etape_story(hist)
            dernier = hist[-1] if hist else None
            etat = "fait" if st == "done" else ("en cours" if st in ("in-progress", "review") else "à faire")
            pct = 100 if etat == "fait" else 0
            etape = ""
            if etat == "en cours":
                _, etape, pct = info or ("", "dev en cours" if st == "in-progress" else "review en cours",
                                         30 if st == "in-progress" else 75)
            lance = next((e["t"] for e in reversed(hist) if e["etape"] == "dev" and "lanc" in e["resultat"].lower()), None)
            fini = next((e["t"] for e in reversed(hist) if e["etape"] == "fusion"), None)
            if fini is None and etat == "fait":
                fini = next((e["t"] for e in reversed(hist) if e["etape"] == "ci"), None)
            drapeaux = []
            if dernier and dernier["etape"] == "blocked" and etat != "fait":
                drapeaux.append("bloquée")
            if etat != "fait" and any(e["etape"] == "attente humaine" for e in hist[-1:]):
                drapeaux.append("attente humaine")
            if etat == "à faire" and dernier and dernier["etape"] == "report" and "non lancé" in dernier["resultat"].lower():
                drapeaux.append("retenue")
            if etat == "fait" and any(re.search(r"en attente d'Anaël|attente humaine", e["resultat"]) for e in hist):
                drapeaux.append("vérification humaine due")
            stories[sid] = {"vague": vague, "epic": int(sid.split(".")[0]), "statut": st, "etat": etat,
                            "pct": pct, "etape": etape, "type": plan["type"].get(sid, "dev"),
                            "pivot": sid in plan["pivot"], "deps": sorted(plan["deps"][sid], key=cle_id),
                            "lance": lance, "fini": fini if etat == "fait" else None, "drapeaux": drapeaux}
    for sid, s in stories.items():
        manque = [d for d in s["deps"] if stories.get(d, {}).get("etat") != "fait"]
        s["eligible"] = (s["etat"] == "à faire" and not manque and s["type"] != "humaine"
                         and "retenue" not in s["drapeaux"])
        s["attend"] = manque
    decisions = [e["resultat"] for e in evts if "pour anaël" in e["brut"].lower()]
    rythme = rythme_observe(stories, maintenant, evts)
    estimation = estimer(stories, plan["parallelisme"], rythme, maintenant)
    sources = {}
    for e in evts:
        sources[e["source"] or "inconnue"] = sources.get(e["source"] or "inconnue", 0) + 1
    return {"projet": projet.name, "maintenant": maintenant, "plan": plan, "stories": stories,
            "rythme": rythme, "estimation": estimation, "decisions": decisions, "sources_heures": sources,
            "hors_run": sorted(plan["hors_run"])}


def cle_id(sid: str) -> tuple[int, int]:
    a, b = sid.split(".")
    return int(a), int(b)


def rythme_observe(stories: dict, maintenant: datetime, evts: list[dict]) -> dict:
    fusions = sorted(s["fini"] for s in stories.values() if s["fini"])
    durees = [(s["fini"] - s["lance"]).total_seconds() / 60 for s in stories.values()
              if s["fini"] and s["lance"] and s["fini"] >= s["lance"]]
    debut = min((e["t"] for e in evts if e["etape"] == "dev" and e["t"]), default=None)
    fenetre = FENETRE_H
    if debut:
        fenetre = max(0.25, min(FENETRE_H, (maintenant - debut).total_seconds() / 3600))
    recent = [t for t in fusions if t >= maintenant - timedelta(hours=fenetre)]
    p75 = None
    if durees:
        p75 = statistics.quantiles(durees, n=4)[2] if len(durees) >= 4 else max(durees)
    return {"fusionnees": len(fusions), "fenetre_h": round(fenetre, 2), "dans_fenetre": len(recent),
            "par_heure": len(recent) / fenetre, "echantillon": len(durees),
            "mediane_min": statistics.median(durees) if durees else None, "p75_min": p75}


def chemin_critique(stories: dict) -> tuple[float, list[str]]:
    """Plus long chemin (en stories restantes) dans le graphe des dépendances non terminées."""
    poids = {s: (0 if v["etat"] == "fait" or v["type"] == "humaine" else 1 - v["pct"] / 100)
             for s, v in stories.items()}
    memo: dict[str, tuple[float, list[str]]] = {}

    def f(s: str, pile: frozenset = frozenset()) -> tuple[float, list[str]]:
        if s in memo:
            return memo[s]
        meilleur = (0.0, [])
        for d in stories[s]["deps"]:
            if d in stories and d not in pile and stories[d]["etat"] != "fait":
                c = f(d, pile | {s})
                if c[0] > meilleur[0] or (c[0] == meilleur[0] and len(c[1]) > len(meilleur[1])):
                    meilleur = c
        memo[s] = (meilleur[0] + poids[s], meilleur[1] + ([s] if poids[s] else []))
        return memo[s]

    tous = [f(s) for s, v in stories.items() if v["etat"] != "fait"]
    return max(tous, default=(0.0, []), key=lambda c: c[0])


def estimer(stories: dict, parallelisme: int, rythme: dict, maintenant: datetime) -> dict:
    reste = [s for s in stories.values() if s["etat"] != "fait" and s["type"] != "humaine"]
    effort = sum(1 - s["pct"] / 100 for s in reste)
    longueur, chemin = chemin_critique(stories)
    med, p75 = rythme["mediane_min"], rythme["p75_min"]
    if not reste:
        return {"reste": 0, "effort": 0.0, "fin": {"optimiste": maintenant, "centrale": maintenant, "pessimiste": maintenant}}
    if not med:
        return {"reste": len(reste), "effort": effort, "fin": None, "chemin": chemin, "longueur": longueur}
    p75 = max(p75 or med, med)
    # (a) débit : plafonné par le parallélisme du plan ; pessimiste = débit observé s'il est plus bas.
    r_max, r_max_p = parallelisme / med, parallelisme / p75
    r_obs = rythme["par_heure"] / 60
    a_opt = effort / r_max
    a_pess = effort / (min(r_obs, r_max_p) if r_obs > 0 else r_max_p / 2)
    # (b) chemin critique x durée par story.
    b_opt, b_pess = longueur * med, longueur * p75
    opt, pess = max(a_opt, b_opt), max(a_pess, b_pess)
    horloge = lambda m: maintenant + timedelta(minutes=m)
    return {"reste": len(reste), "effort": effort, "chemin": chemin, "longueur": longueur,
            "debit": {"optimiste_min": a_opt, "pessimiste_min": a_pess},
            "critique": {"optimiste_min": b_opt, "pessimiste_min": b_pess},
            "fin": {"optimiste": horloge(opt), "centrale": horloge((opt + pess) / 2), "pessimiste": horloge(pess)},
            "bornant": "chemin critique" if b_opt >= a_opt else "débit"}


# ----------------------------------------------------------------------------- rapport

def fmt_t(t: datetime | None) -> str:
    return t.strftime("%Y-%m-%d %H:%M") if t else "?"


def fmt_d(minutes: float | None) -> str:
    if minutes is None:
        return "?"
    h, m = divmod(round(minutes), 60)
    return f"{h} h {m:02d}" if h else f"{m} min"


def code(sid: str, s: dict) -> str:
    marque = "★" if s["pivot"] else ""
    if s["etat"] == "fait":
        return f"{sid}{marque} ✓"
    if s["etat"] == "en cours":
        return f"{sid}{marque} ▶{s['pct']}%"
    return f"{sid}{marque} ·" + (" (retenue)" if "retenue" in s["drapeaux"] else "")


def agregat(liste: list[dict]) -> tuple[int, int, int, float]:
    f = sum(1 for s in liste if s["etat"] == "fait")
    c = sum(1 for s in liste if s["etat"] == "en cours")
    pct = sum(s["pct"] for s in liste) / len(liste) if liste else 0
    return f, c, len(liste) - f - c, pct


def rapport(a: dict) -> str:
    S, plan, now = a["stories"], a["plan"], a["maintenant"]
    L = [f"# Avancement du run : {a['projet']} (au {fmt_t(now)})", ""]
    f, c, r, pct = agregat(list(S.values()))
    L += [f"**{f} terminées, {c} en cours, {r} à faire sur {len(S)} stories ({pct:.0f} %).** "
          f"Créneaux de développement : {sum(1 for x in S.values() if x['etat'] == 'en cours' and x['pct'] <= 30)}"
          f"/{plan['parallelisme']} occupés (les stories en second-avis ou en review n'en occupent pas).", ""]
    if a["hors_run"]:
        L += [f"Hors périmètre : epics {', '.join(map(str, a['hors_run']))}.", ""]
    L += ["Barème d'un en-cours (dernière étape journalisée) : "
          + " ; ".join(f"{j} -> {e} {p} %" for j, e, p in BAREME) + ".", ""]
    L += ["## Par epic", "", "| Epic | Terminées | En cours | À faire | Avancement |", "|---|---|---|---|---|"]
    for ep in sorted({s["epic"] for s in S.values()}):
        f, c, r, pct = agregat([s for s in S.values() if s["epic"] == ep])
        L.append(f"| {ep} | {f} | {c} | {r} | {pct:.0f} % |")
    L += ["", "## Par vague", "", "| Vague | Stories | Avancement |", "|---|---|---|"]
    for v in plan["ordre"]:
        liste = [S[s] for s in plan["vagues"][v]]
        L.append(f"| {v} | {' · '.join(code(s, S[s]) for s in plan['vagues'][v])} | {agregat(liste)[3]:.0f} % |")
    L += ["", "✓ terminée · ▶n % en cours · · à faire · ★ pivot", ""]
    en_cours = [(sid, s) for sid, s in S.items() if s["etat"] == "en cours"]
    L += ["## En cours", ""]
    if not en_cours:
        L.append("Aucune.")
    for sid, s in en_cours:
        depuis = f", lancée {fmt_t(s['lance'])}" if s["lance"] else ""
        L.append(f"- {sid} ({s['vague']}) : {s['etape']}, ~{s['pct']} %{depuis}")
    ry, es = a["rythme"], a["estimation"]
    L += ["", "## Rythme", "",
          f"- {ry['fusionnees']} stories fusionnées ; {ry['dans_fenetre']} dans les {ry['fenetre_h']:g} dernières heures "
          f"({ry['par_heure']:.1f} par heure) ;",
          f"- durée « dev lancé -> fusion » : médiane {fmt_d(ry['mediane_min'])}, 75e centile {fmt_d(ry['p75_min'])} "
          f"({ry['echantillon']} stories mesurées)."]
    L += ["", "## Estimation de fin des développements", ""]
    if es["reste"] == 0:
        L.append("Tout est terminé.")
    elif not es["fin"]:
        L.append(f"Reste {es['reste']} stories ; pas assez de stories terminées pour estimer une durée.")
    else:
        fin = es["fin"]
        L += [f"- **Centrale : {fmt_t(fin['centrale'])}** ; optimiste {fmt_t(fin['optimiste'])}, pessimiste {fmt_t(fin['pessimiste'])}.",
              f"- Reste {es['reste']} stories (~{es['effort']:.1f} en équivalent story) ; contrainte dominante : {es['bornant']}.",
              f"- Débit à {plan['parallelisme']} en parallèle : {fmt_d(es['debit']['optimiste_min'])} à {fmt_d(es['debit']['pessimiste_min'])}.",
              f"- Chemin critique ({es['longueur']:.1f} stories) : {' -> '.join(es['chemin'])} : "
              f"{fmt_d(es['critique']['optimiste_min'])} à {fmt_d(es['critique']['pessimiste_min'])}."]
    L += ["- Non compté : étapes humaines (stories `mixte`/`humaine`, vérifications sur poste réel, accord pour couper "
          "une story), limites d'usage, ressources à activer (Ollama, GPU), CI rouges et reprises Opus, pauses."]
    L += ["", "## Alertes", ""]
    bloq = [sid for sid, s in S.items() if "bloquée" in s["drapeaux"]]
    att = [sid for sid, s in S.items() if "attente humaine" in s["drapeaux"]]
    ret = [sid for sid, s in S.items() if "retenue" in s["drapeaux"]]
    verif = [sid for sid, s in S.items() if "vérification humaine due" in s["drapeaux"]]
    elig = [sid for sid, s in S.items() if s["eligible"]]
    mixtes = [sid for sid, s in S.items() if s["type"] != "dev" and s["etat"] != "fait"]
    libres = plan["parallelisme"] - sum(1 for _, x in en_cours if x["pct"] <= 30)
    L.append(f"- Bloquées : {', '.join(bloq) or 'aucune'}.")
    L.append(f"- En attente humaine : {', '.join(att) or 'aucune'}"
             + (f" ; étapes humaines à venir (mixtes) : {', '.join(mixtes)}" if mixtes else "") + ".")
    L.append(f"- Éligibles non lancées (dépendances terminées) : {', '.join(elig) or 'aucune'}"
             + (" -> créneau libre" if elig and libres > 0 else
                (" (créneaux pleins)" if elig else "")) + ".")
    if ret:
        L.append(f"- Retenues par le journal (report) : {', '.join(ret)}.")
    if verif:
        L.append(f"- Terminées mais avec une vérification humaine citée au journal : {', '.join(verif)}.")
    if a["decisions"]:
        L.append(f"- Décisions pour Anaël notées au journal ({len(a['decisions'])}, résolues ou non ?) : "
                 + " | ".join(d[:90] for d in a["decisions"]) + ".")
    src = a["sources_heures"]
    L += ["", f"Heures du journal : {src.get('journal', 0)} explicites, {src.get('suivi', 0) + src.get('commit', 0)} "
          f"reprises de git, {src.get('interpolé', 0)} interpolées, {src.get('mtime', 0)} sur date de fichier"
          + (" : durées approximatives." if src.get("interpolé") else ".")]
    return "\n".join(L) + "\n"


def serialisable(o):
    if isinstance(o, datetime):
        return o.strftime("%Y-%m-%d %H:%M")
    if isinstance(o, set):
        return sorted(o, key=lambda x: cle_id(x) if isinstance(x, str) else (x, 0))
    raise TypeError(type(o))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("projet", nargs="?", default=".", help="racine du projet (défaut : répertoire courant)")
    ap.add_argument("--json", action="store_true", help="sortie JSON au lieu du Markdown")
    ap.add_argument("--maintenant", help="heure de référence « AAAA-MM-JJ HH:MM » (tests)")
    args = ap.parse_args(argv)
    projet = Path(args.projet).resolve()
    if not (projet / DOSSIER / "run-autonome.md").exists() or not (projet / DOSSIER / "sprint-status.yaml").exists():
        print(f"Introuvable : {projet / DOSSIER} doit contenir run-autonome.md et sprint-status.yaml.", file=sys.stderr)
        return 2
    now = datetime.strptime(args.maintenant, "%Y-%m-%d %H:%M") if args.maintenant else datetime.now().replace(second=0, microsecond=0)
    a = analyser(projet, now)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.json:
        print(json.dumps(a, default=serialisable, ensure_ascii=False, indent=1))
    else:
        print(rapport(a), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
