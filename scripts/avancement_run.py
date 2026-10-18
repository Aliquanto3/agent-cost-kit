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

Usage : python avancement_run.py [projet] [--json] [--detail] [--stories] [--maintenant "AAAA-MM-JJ HH:MM"]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import textwrap
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
    statuts_bruts = lire_statuts(fichier_statut)
    statuts = ids_statut(statuts_bruts)
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
            if etat != "fait" and any(re.search(r"\brepris(e|es)?\b", e["resultat"]) for e in hist):
                drapeaux.append("reprise")
            if etat != "fait" and any(e["etape"] in ("report", "décision") and re.search(r"\bcoupée?\b", e["resultat"])
                                      for e in hist):
                drapeaux.append("coupée")
            if info and info[0] == "CI rouge" and etat != "fait":
                drapeaux.append("CI rouge")
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
    noms = lire_titres(projet, statuts_bruts)
    meteo_ = meteo(stories, estimation)
    return {"projet": projet.name, "maintenant": maintenant, "plan": plan, "stories": stories,
            "noms": noms, "meteo": meteo_,
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
    reste = [s for s in stories.values() if s["etat"] != "fait" and s["type"] != "humaine" and "coupée" not in s["drapeaux"]]
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


def rapport_detail(a: dict) -> str:
    S, plan = a["stories"], a["plan"]
    L = ["## Détails de l'estimation", ""]
    f, c, r, pct = agregat(list(S.values()))
    L += [f"**{f} terminées, {c} en cours, {r} à faire sur {len(S)} stories ({pct:.0f} %).** "
          f"Créneaux de développement : {sum(1 for x in S.values() if x['etat'] == 'en cours' and x['pct'] <= 30)}"
          f"/{plan['parallelisme']} occupés (les stories en second-avis ou en review n'en occupent pas).", ""]
    if a["hors_run"]:
        L += [f"Hors périmètre : epics {', '.join(map(str, a['hors_run']))}.", ""]
    L += ["Barème d'un en-cours (dernière étape journalisée) : "
          + " ; ".join(f"{j} -> {e} {p} %" for j, e, p in BAREME) + ".", ""]
    L += ["### Par vague", "", "| Vague | Stories | Avancement |", "|---|---|---|"]
    for v in plan["ordre"]:
        liste = [S[s] for s in plan["vagues"][v]]
        L.append(f"| {v} | {' · '.join(code(s, S[s]) for s in plan['vagues'][v])} | {agregat(liste)[3]:.0f} % |")
    L += ["", "✓ terminée · ▶n % en cours · · à faire · ★ pivot", ""]
    en_cours = [(sid, s) for sid, s in S.items() if s["etat"] == "en cours"]
    L += ["### En cours", ""]
    if not en_cours:
        L.append("Aucune.")
    for sid, s in en_cours:
        depuis = f", lancée {fmt_t(s['lance'])}" if s["lance"] else ""
        L.append(f"- {sid} ({s['vague']}) : {s['etape']}, ~{s['pct']} %{depuis}")
    ry, es = a["rythme"], a["estimation"]
    L += ["", "### Rythme", "",
          f"- {ry['fusionnees']} stories fusionnées ; {ry['dans_fenetre']} dans les {ry['fenetre_h']:g} dernières heures "
          f"({ry['par_heure']:.1f} par heure) ;",
          f"- durée « dev lancé -> fusion » : médiane {fmt_d(ry['mediane_min'])}, 75e centile {fmt_d(ry['p75_min'])} "
          f"({ry['echantillon']} stories mesurées)."]
    L += ["", "### Calcul de la fin", ""]
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
    L += ["", "### Alertes", ""]
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


# ----------------------------------------------------------------------------- synthèse

def lire_titres(projet: Path, statuts_bruts: dict[str, str]) -> dict:
    """Titres des epics et des stories depuis epics.md ; à défaut, le slug des clés de sprint-status."""
    epics: dict[int, str] = {}
    stories: dict[str, str] = {}
    for cle in statuts_bruts:
        m = re.match(r"(\d+)-(\d+)-(.+)", cle)
        if m:
            stories[f"{m[1]}.{m[2]}"] = m[3].replace("-", " ")
    fichier = projet / "_bmad-output" / "planning-artifacts" / "epics.md"
    if fichier.exists():
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            m = re.match(r"##\s+Epic\s+(\d+)\s*:\s*(.+)", ligne)
            if m:
                epics[int(m[1])] = m[2].strip()
            m = re.match(r"###\s+Story\s+(\d+\.\d+)\s*:\s*(.+)", ligne)
            if m:
                stories[m[1]] = m[2].strip()
    return {"epics": epics, "stories": stories}


def court(texte: str, n: int) -> str:
    if len(texte) <= n:
        return texte
    return texte[:n].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


BARRE_PLEIN, BARRE_VIDE = "█", "░"  # blocs pleins, sans contour : lisibles en clair comme en sombre


def barre(pct: float, n: int = 10) -> str:
    plein = min(n, int(pct / 100 * n + 0.5))
    return BARRE_PLEIN * plein + BARRE_VIDE * (n - plein)


def emoji_story(s: dict) -> str:
    d = s["drapeaux"]
    if s["etat"] == "fait":
        return "✅"
    if "coupée" in d:
        return "✂️"
    if "bloquée" in d:
        return "⛔"
    if "attente humaine" in d:
        return "👤"
    if s["etat"] == "à faire":
        return "⏳"
    if s["pct"] <= 30:
        return "🛠️"
    return "🔍" if s["pct"] <= 60 else "🧪"


def meteo(stories: dict, estimation: dict) -> dict:
    """Règles : rouge si une story est bloquée ou si une attente humaine est sur le chemin critique ;
    jaune si un contrôle automatique est rouge ou si une story a été reprise ; sinon vert."""
    chemin = set(estimation.get("chemin") or [])
    rouge = [f"story {k} bloquée" for k, s in stories.items() if "bloquée" in s["drapeaux"]]
    rouge += [f"story {k} en attente humaine sur le chemin critique" for k, s in stories.items()
              if "attente humaine" in s["drapeaux"] and k in chemin]
    jaune = [f"contrôle automatique rouge sur {k}" for k, s in stories.items() if "CI rouge" in s["drapeaux"]]
    jaune += [f"story {k} reprise" for k, s in stories.items() if "reprise" in s["drapeaux"]]
    if rouge:
        return {"emoji": "🔴", "mot": "bloqué", "raisons": rouge + jaune}
    if jaune:
        return {"emoji": "🟡", "mot": "vigilance", "raisons": jaune}
    return {"emoji": "🟢", "mot": "dans les temps", "raisons": []}


def statut_epic(liste: list[dict]) -> str:
    if all(s["etat"] == "fait" for s in liste):
        return "✅"
    if any("bloquée" in s["drapeaux"] for s in liste):
        return "⛔"
    if any("attente humaine" in s["drapeaux"] for s in liste):
        return "👤"
    if any(s["etat"] != "à faire" for s in liste):
        return "🔄"
    return "⏳"


def puces(a: dict) -> list[str]:
    S, N, es = a["stories"], a["noms"], a["estimation"]
    fait = [k for k, s in S.items() if s["etat"] == "fait"]
    out = []
    epics_finis = [ep for ep in sorted({s["epic"] for s in S.values()})
                   if all(s["etat"] == "fait" for s in S.values() if s["epic"] == ep)]
    fm = f"{len(fait)} stories sur {len(S)} sont livrées"
    if epics_finis:
        fm += " ; terminé : " + ", ".join(f"epic {e} ({court(N['epics'].get(e, ''), 40)})" for e in epics_finis)
    out.append(fm + ".")
    cours = [(k, s) for k, s in S.items() if s["etat"] == "en cours"]
    if cours:
        rel = [k for k, s in cours if s["pct"] > 30]
        dev = [k for k, s in cours if s["pct"] <= 30]
        morceaux = [f"{', '.join(rel)} en relecture" if rel else "", f"{', '.join(dev)} en développement" if dev else ""]
        out.append(f"{len(cours)} stories avancent en ce moment : " + ", ".join(m for m in morceaux if m) + ".")
    att = []
    bloq = [k for k, s in S.items() if "bloquée" in s["drapeaux"]]
    if bloq:
        att.append("bloquée(s) : " + ", ".join(bloq))
    ret = [k for k, s in S.items() if "retenue" in s["drapeaux"]]
    if ret:
        att.append(f"{', '.join(ret)} attend la fin d'une autre story du même module")
    elig = [k for k, s in S.items() if s["eligible"]]
    if elig:
        att.append(f"prête mais pas lancée : {', '.join(elig)}")
    att += a["meteo"]["raisons"]
    out.append("Points d'attention : " + ("; ".join(att) if att else "rien de bloquant") + ".")
    dec = [court(d, 110) for d in a["decisions"]]
    verif = [k for k, s in S.items() if "vérification humaine due" in s["drapeaux"]]
    mixtes = [k for k, s in S.items() if s["type"] != "dev" and s["etat"] != "fait"]
    parts = []
    if dec:
        parts.append("décision à prendre : " + " | ".join(dec))
    if verif:
        parts.append(f"vérification sur poste réel pour {', '.join(verif)}")
    if mixtes:
        parts.append(f"étapes humaines à venir pour {', '.join(mixtes)}")
    out.append("Attendu d'Anaël : " + ("; ".join(parts) if parts else "rien pour l'instant") + ".")
    src = a["sources_heures"]
    if es.get("fin") and src.get("interpolé", 0) * 2 > sum(src.values()):
        out.append("L'heure de fin est approximative : la plupart des lignes du journal n'ont pas d'heure "
                   "(ajouter AAAA-MM-JJ HH:MM à chaque ligne l'affine).")
    return out[:5]


def rapport(a: dict, detail: bool = False, stories: bool = False) -> str:
    S, plan, N, es = a["stories"], a["plan"], a["noms"], a["estimation"]
    f, c, r, pct = agregat(list(S.values()))
    m = a["meteo"]
    L = [f"# {a['projet']} : avancement du run au {fmt_t(a['maintenant'])}", "",
         f"**{barre(pct)} {pct:.0f} %** · {f} / {len(S)} stories terminées ({c} en cours, {r} à faire)", ""]
    if es["reste"] == 0:
        L.append("**Tous les développements prévus sont terminés.**")
    elif es.get("fin"):
        fin = es["fin"]
        L.append(f"**Fin estimée : {fmt_t(fin['centrale'])}** (entre {fmt_t(fin['optimiste'])} et {fmt_t(fin['pessimiste'])})")
    else:
        L.append("**Fin estimée : indisponible** (pas assez de stories terminées pour mesurer un rythme)")
    L += ["", f"**Météo : {m['emoji']} {m['mot']}**", "",
          "Hors estimation : étapes humaines, limites d'usage, reprises en cas d'échec, pauses.", "",
          "## Ce qu'il faut savoir", ""]
    L += [textwrap.fill(f"- {p}", width=118, subsequent_indent="  ") for p in puces(a)]
    epics = sorted({s["epic"] for s in S.values()})
    consolide = len(epics) > 1  # sinon aucun niveau de consolidation : le détail par story tient lieu de tableau
    if consolide:
        L += ["", "## Par epic", "", "| Epic | Avancement | ✅ | 🔄 | ⏳ | |", "|---|---|---|---|---|---|"]
        for ep in epics:
            liste = [s for s in S.values() if s["epic"] == ep]
            fe, ce, re_, pe = agregat(liste)
            nom = court(N["epics"].get(ep, ""), 38)
            L.append(f"| {ep} · {nom} | {barre(pe)} {pe:.0f} % | {fe} | {ce} | {re_} | {statut_epic(liste)} |")
    if stories or not consolide:
        L += ["", "## Détail par story", "", "| Story | Titre | État | % | |", "|---|---|---|---|---|"]
        for v in plan["ordre"]:
            for sid in plan["vagues"][v]:
                s = S[sid]
                L.append(f"| {sid} | {court(N['stories'].get(sid, ''), 52)} | {emoji_story(s)} | {s['pct']} % | "
                         f"{'★' if s['pivot'] else ''} |")
    L += ["", textwrap.fill("✅ terminé · 🧪 en relecture · 🔍 second avis · 🛠️ développement · 🔄 en cours · "
                            "⏳ à faire · ⛔ bloqué · 👤 attente humaine · ✂️ coupée · ★ story pivot", width=110), ""]
    L += [textwrap.fill("Météo : 🔴 si une story est bloquée ou si une attente humaine est sur le chemin critique ; "
                        "🟡 si un contrôle automatique est rouge ou si une story est reprise ; sinon 🟢.", width=110), ""]
    if detail:
        L += [rapport_detail(a)]
    else:
        L += [textwrap.fill("Détails de l'estimation (rythme, chemin critique, vagues, heures interpolées) : option `--detail`."
                            + ("" if stories or not consolide else " Tableau par story : option `--stories`."), width=110)]
    return "\n".join(L).rstrip("\n") + "\n"



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
    ap.add_argument("--detail", action="store_true", help="ajoute les détails de l'estimation (rythme, vagues, sources)")
    ap.add_argument("--stories", action="store_true", help="ajoute le tableau par story (déjà présent sans niveau de consolidation)")
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
        print(rapport(a, args.detail, args.stories), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
