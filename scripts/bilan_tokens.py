"""Bilan mensuel des tokens Claude Code (tous projets ou un dossier donné), par modèle.

Réutilise ``mesurer_couts.py`` (appels, couts, impact_appels, prix, MIX_DEFAUT, GRANDEURS,
ECRITURE, dossier_transcriptions) : ce script ne redéfinit aucune table de prix ni aucun
coefficient d'impact. ``--methode`` (défaut ``impactia``, expérimental, entrée comptée ; ``ecologits`` :
sortie seule) est écrite dans le JSON (champ ``methode``) ; la fusion refuse des méthodes différentes.
Un bilan sans champ ``methode`` (avant 0.9.0) a été calculé en ``ecologits``.

Deux modes :

- **Collecte** (défaut) : parcourt récursivement ``~/.claude/projects`` (ou ``--racine``),
  éventuellement limité aux dossiers de projet dont le nom encodé commence par celui de
  ``--dossier`` (même encodage que ``mesurer_couts.dossier_transcriptions`` : un dossier
  encode son chemin absolu en remplaçant tout caractère hors ``[A-Za-z0-9]`` par ``-``, donc
  un sous-dossier du chemin donné a toujours ce préfixe). Lit tous les ``*.jsonl`` (sessions
  principales et sous-agents), dédoublonne par ``message.id`` sur l'ensemble des fichiers (la
  première occurrence chronologique est gardée), écarte les messages synthétiques
  (``id == "<synthetic>"``, injectés par Claude Code, sans coût réel), garde les appels dont
  l'horodatage (UTC, tel qu'écrit par Claude Code) commence par ``--mois`` (``AAAA-MM``, défaut :
  mois UTC courant), puis agrège par modèle.
- **Fusion** (``--fusionner a.json b.json ...``) : combine plusieurs bilans ``<mois>-<machine>.json``
  du même mois, un par machine, en un ``<mois>-consolide.json`` + ``.html``.

Options de période et de portée : ``--du/--au`` (jours UTC inclus, même mois, exclusif avec ``--mois``) ;
``--racine`` répétable (un appel par ``message.id`` sur l'ensemble) ; ``--detail`` et ``--config`` ajoutent le champ
``detail`` (projet, étape, rôle, recommandations : voir ``bilan_detail.py``). ``--fusionner`` refuse des périodes
différentes et fusionne ``detail`` quand tous les bilans en ont un.

Écrit aussi la page HTML (``skills/bilan-tokens/gabarit.html``) à côté du JSON. Aucun contenu de
transcription n'est recopié : seuls des totaux par modèle.

Usage :
    python bilan_tokens.py --mois 2026-10 --dossier C:/chemin/du/depot
    python bilan_tokens.py --fusionner mesures/pc1.json mesures/pc2.json --out mesures/
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bilan_detail as bd
import bilan_i18n as i18n
import mesurer_couts as mc

UTC = timezone.utc  # noqa: UP017 - datetime.UTC n'existe qu'à partir de Python 3.11
SCHEMA = 1
GABARIT = Path(__file__).resolve().parent.parent / "skills" / "bilan-tokens" / "gabarit.html"
PLACEHOLDER = "const BILAN=/*__BILAN__*/null;"
RACINE_DEFAUT = Path.home() / ".claude" / "projects"


def mois_courant() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def projets_retenus(racine: Path, dossier: Path | None) -> list[Path]:
    """Dossiers de projet sous ``racine`` dont le nom encode le chemin donné, lui ou un sous-dossier."""
    if not racine.is_dir():
        return []
    if dossier is None:
        return [d for d in racine.iterdir() if d.is_dir()]
    prefixe = mc.dossier_transcriptions(dossier, racine).name
    # Le dossier lui-même ou un sous-dossier (séparateur encodé en « - ») : pas un frère comme GitHub2.
    return [d for d in racine.iterdir() if d.is_dir() and (d.name == prefixe or d.name.startswith(prefixe + "-"))]


def liste_racines(options) -> list[Path]:
    """Racines de transcriptions : ``--racine`` répétée (ou une seule valeur), sinon ``~/.claude/projects``."""
    racines = getattr(options, "racine", None)
    if isinstance(racines, Path):
        return [racines]
    return list(racines or [RACINE_DEFAUT])


def verifier_periode(du: str | None, au: str | None) -> None:
    """``--du`` et ``--au`` vont ensemble, sont des dates valides, dans l'ordre et dans le même mois."""
    if du is None and au is None:
        return
    if du is None or au is None:
        sys.exit("--du et --au vont ensemble.")
    for nom, valeur in (("--du", du), ("--au", au)):
        try:
            datetime.strptime(valeur, "%Y-%m-%d")
        except ValueError:
            sys.exit(f"{nom} {valeur!r} : date AAAA-MM-JJ attendue.")
    if du > au:
        sys.exit(f"--du {du} après --au {au}.")
    if du[:7] != au[:7]:
        sys.exit(f"--du {du} et --au {au} doivent être dans le même mois (pas de période à cheval sur deux mois).")


def dans_periode(ts: str, mois: str, du: str | None = None, au: str | None = None) -> bool:
    """Horodatage UTC dans la période ``du``..``au`` (jours inclus) ou, sans elle, dans le mois."""
    return du <= ts[:10] <= au if du and au else ts[:7] == mois


def collecter_bruts(projets: list[Path], detail: bool = False) -> tuple[list[dict], dict[str, dict]]:
    """Appels des ``*.jsonl`` de ``projets`` (sous-agents compris), dédoublonnés par ``message.id``, et infos de fichiers."""
    bruts: list[dict] = []
    infos: dict[str, dict] = {}
    for projet in sorted(projets):
        for chemin in sorted(projet.rglob("*.jsonl")):
            if detail:
                liste, infos[str(chemin)] = bd.lire_fichier(chemin)
            else:
                liste = mc.appels(chemin)
            bruts.extend(liste)
    bruts = [a for a in bruts if a["id"] != "<synthetic>"]
    bruts.sort(key=lambda a: mc.instant(a["ts"]))
    vus: dict[str, dict] = {}
    for a in bruts:
        vus.setdefault(a["id"], a)
    return list(vus.values()), infos


def retenir(appels_uniques: list[dict], mois: str, du: str | None = None, au: str | None = None) -> list[dict]:
    """Appels dans le mois ou dans ``du``..``au``, en ordre chronologique."""
    retenus = [a for a in appels_uniques if dans_periode(a["ts"], mois, du, au)]
    retenus.sort(key=lambda a: mc.instant(a["ts"]))
    return retenus


def collecter(projets: list[Path], mois: str, du: str | None = None, au: str | None = None) -> list[dict]:
    """Tous les appels de ``projets``, dédoublonnés et filtrés sur ``mois`` (ou sur ``du``..``au``)."""
    return retenir(collecter_bruts(projets)[0], mois, du, au)


def par_modele(appels_retenus: list[dict], mix: str, methode: str = mc.METHODE_DEFAUT) -> list[dict]:
    """Un bloc par modèle (identifiant complet), dans l'ordre d'apparition."""
    ordre: list[str] = []
    groupes: dict[str, list[dict]] = {}
    for a in appels_retenus:
        groupes.setdefault(a["modele"], []).append(a)
        if a["modele"] not in ordre:
            ordre.append(a["modele"])
    resultat = []
    for modele in ordre:
        liste = sorted(groupes[modele], key=lambda a: mc.instant(a["ts"]))
        c = mc.couts(liste)
        imp = mc.impact_appels(liste, mix, methode)
        entree = sum(a["entree"] for a in liste)
        ecrit_5m = sum(a["ecrit_5m"] for a in liste)
        ecrit_1h = sum(a["ecrit_1h"] for a in liste)
        lu = sum(a["lu"] for a in liste)
        # Sans cache : tout l'input au prix de base, avec les mêmes majorations que mc.couts
        # (long contexte, inférence US), appel par appel.
        sans_cache = mc.couts(
            [{**a, "entree": a["entree"] + a["ecrit_5m"] + a["ecrit_1h"] + a["lu"], "ecrit_5m": 0, "ecrit_1h": 0, "lu": 0} for a in liste]
        )["parts"]["entree"]
        resultat.append(
            {
                "modele": modele,
                "appels": len(liste),
                "entree": entree,
                "ecrit_5m": ecrit_5m,
                "ecrit_1h": ecrit_1h,
                "lu": lu,
                "sortie_declaree": sum(a["sortie_declaree"] for a in liste),
                "sortie": sum(a["sortie"] for a in liste),
                "cout": {k: round(v, 6) for k, v in c["parts"].items()},
                "cout_sans_cache": round(sans_cache, 6),
                "impact": {g: [imp[g]["min"], imp[g]["max"]] for g in mc.GRANDEURS},
            }
        )
    return resultat


def table_prix(modeles: list[str]) -> dict:
    sortie = {}
    for m in modeles:
        tarif = mc.prix(m)
        entree = {
            "entree": tarif["entree"],
            "ecriture_5m": tarif["entree"] * mc.ECRITURE["5m"],
            "ecriture_1h": tarif["entree"] * mc.ECRITURE["1h"],
            "lecture": tarif["lecture"],
            "sortie": tarif["sortie"],
        }
        if tarif.get("long_contexte"):
            entree["long_contexte"] = tarif["long_contexte"]
        sortie[m] = entree
    return sortie


def sommer_blocs(blocs: list[list[dict]]) -> list[dict]:
    """Somme plusieurs listes de blocs par modèle (une par machine) en une liste unique."""
    ordre: list[str] = []
    fusion: dict[str, dict] = {}
    for liste in blocs:
        for m in liste:
            if m["modele"] not in fusion:
                ordre.append(m["modele"])
                fusion[m["modele"]] = {
                    "modele": m["modele"],
                    "appels": 0,
                    "entree": 0,
                    "ecrit_5m": 0,
                    "ecrit_1h": 0,
                    "lu": 0,
                    "sortie_declaree": 0,
                    "sortie": 0,
                    "cout": {"entree": 0.0, "ecriture": 0.0, "lecture": 0.0, "sortie": 0.0},
                    "cout_sans_cache": 0.0,
                    "impact": {g: [0.0, 0.0] for g in mc.GRANDEURS},
                }
            dest = fusion[m["modele"]]
            for champ in ("appels", "entree", "ecrit_5m", "ecrit_1h", "lu", "sortie_declaree", "sortie"):
                dest[champ] += m[champ]
            for poste in dest["cout"]:
                dest["cout"][poste] += m["cout"].get(poste, 0.0)
            dest["cout_sans_cache"] += m["cout_sans_cache"]
            for g in mc.GRANDEURS:
                dest["impact"][g][0] += m["impact"][g][0]
                dest["impact"][g][1] += m["impact"][g][1]
    return [fusion[m] for m in ordre]


def totaux_machine(modeles: list[dict]) -> dict:
    """Totaux toutes catégories confondues, pour la ligne d'une machine dans la vue consolidée."""
    t = {
        "appels": 0, "entree": 0, "ecrit_5m": 0, "ecrit_1h": 0, "lu": 0,
        "sortie_declaree": 0, "sortie": 0,
        "cout": {"entree": 0.0, "ecriture": 0.0, "lecture": 0.0, "sortie": 0.0},
        "cout_sans_cache": 0.0,
        "impact": {g: [0.0, 0.0] for g in mc.GRANDEURS},
    }
    for m in modeles:
        for champ in ("appels", "entree", "ecrit_5m", "ecrit_1h", "lu", "sortie_declaree", "sortie"):
            t[champ] += m[champ]
        for poste in t["cout"]:
            t["cout"][poste] += m["cout"].get(poste, 0.0)
        t["cout_sans_cache"] += m["cout_sans_cache"]
        for g in mc.GRANDEURS:
            t["impact"][g][0] += m["impact"][g][0]
            t["impact"][g][1] += m["impact"][g][1]
    return t


def ecrire_html(bilan: dict, chemin: Path, langue: str = i18n.LANGUE_SOURCE, liens: dict[str, str] | None = None) -> None:
    """Page du bilan dans ``langue`` ; ``liens`` {langue: nom de fichier} ajoute le sélecteur de langue."""
    gabarit = GABARIT.read_text(encoding="utf-8")
    if PLACEHOLDER not in gabarit:
        sys.exit(f"Gabarit sans point d'injection attendu ({PLACEHOLDER!r}) : {GABARIT}")
    try:
        page = i18n.traduire_page(gabarit, langue, liens)
    except i18n.CatalogueObsolete as erreur:
        sys.exit(str(erreur))
    detail = bilan.get("detail")
    recos = bd.recommandations(detail["brut"], detail, langue) if detail and langue != i18n.LANGUE_SOURCE else None
    donnees = i18n.traduire_donnees(bilan, langue, recos)
    injection = json.dumps(donnees, ensure_ascii=False).replace("</", "<\\/")
    chemin.write_text(page.replace(PLACEHOLDER, f"const BILAN={injection};"), encoding="utf-8")


def noms_pages(base: str, langues: tuple[str, ...]) -> dict[str, str]:
    """``<base>.html`` pour le français, ``<base>.<langue>.html`` pour les autres."""
    return {l: f"{base}.html" if l == i18n.LANGUE_SOURCE else f"{base}.{l}.html" for l in langues}


def langues_demandees(valeur: str | None) -> tuple[str, ...]:
    """``fr,en,de`` -> ('fr', 'en', 'de') ; le français est toujours écrit, l'ordre suit ``i18n.LANGUES``."""
    demandees = {l.strip() for l in (valeur or ",".join(i18n.LANGUES)).split(",") if l.strip()}
    inconnues = demandees - set(i18n.LANGUES)
    if inconnues:
        sys.exit(f"Langue(s) inconnue(s) : {sorted(inconnues)} (possibles : {', '.join(i18n.LANGUES)}).")
    return tuple(l for l in i18n.LANGUES if l in demandees | {i18n.LANGUE_SOURCE})


def afficher_tableau(modeles: list[dict], titre: str) -> None:
    print(f"\n{titre}")
    print(f"{'modèle':28} {'input traité':>14} {'output':>10} {'coût $':>9} {'kgCO2e':>14}")
    for m in modeles:
        entree_tot = m["entree"] + m["ecrit_5m"] + m["ecrit_1h"] + m["lu"]
        cout = sum(m["cout"].values())
        gwp = m["impact"]["gwp_gco2e"]
        print(
            f"{m['modele']:28} {entree_tot / 1e6:12.2f} M {m['sortie'] / 1e6:8.2f} M {cout:9.2f} "
            f"{mc.fourchette(gwp[0] / 1000, gwp[1] / 1000, 1):>14}"
        )


def commande_collecte(options) -> int:
    du, au = getattr(options, "du", None), getattr(options, "au", None)
    detail = getattr(options, "detail", False)
    verifier_periode(du, au)
    mois = du[:7] if du else options.mois or mois_courant()
    libelle = f"{du} au {au}" if du else mois
    racines = liste_racines(options)
    projets = [p for racine in racines for p in projets_retenus(racine, options.dossier)]
    if not projets:
        print(f"Aucun dossier de transcriptions sous {', '.join(map(str, racines))}" + (f" pour {options.dossier}" if options.dossier else ""), file=sys.stderr)
        return 1
    uniques, infos = collecter_bruts(projets, detail)
    retenus = retenir(uniques, mois, du, au)
    if not retenus:
        print(f"Aucun appel pour {libelle}.", file=sys.stderr)
        return 1
    modeles = par_modele(retenus, options.mix, options.methode)
    bilan = {
        "schema": SCHEMA,
        "machine": options.machine,
        "mois": mois,
        **({"du": du, "au": au} if du else {}),
        "dossier": str(options.dossier.resolve()) if options.dossier else None,
        "genere_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "premier_appel": retenus[0]["ts"],
        "dernier_appel": retenus[-1]["ts"],
        "mix": options.mix,
        "methode": options.methode,
        "modeles": modeles,
        "prix": table_prix([m["modele"] for m in modeles]),
    }
    if detail:
        config = bd.charger_config(getattr(options, "config", None))
        bilan["detail"] = bd.construire(retenus, infos, config, options.mix, options.methode)
    ecrire_bilan(bilan, options.out, f"{du}_{au}" if du else mois, options.machine,
                 langues_demandees(getattr(options, "langues", None)))
    afficher_tableau(modeles, f"Bilan {libelle} — {options.machine}")
    return 0


def ecrire_bilan(bilan: dict, out: Path, periode: str, suffixe: str, langues: tuple[str, ...] = i18n.LANGUES) -> None:
    """Écrit ``<periode>-<suffixe>.json``, ``.html`` (français) et ``.<langue>.html`` par autre langue dans ``out``."""
    out.mkdir(parents=True, exist_ok=True)
    base = f"{periode}-{suffixe}"
    chemin_json = out / f"{base}.json"
    chemin_json.write_text(json.dumps(bilan, ensure_ascii=False, indent=2), encoding="utf-8")
    pages = noms_pages(base, langues)
    for langue, nom in pages.items():
        ecrire_html(bilan, out / nom, langue, pages if len(pages) > 1 else None)
    print(f"\nÉcrit : {chemin_json}" + "".join(f"\n        {out / nom}" for nom in pages.values()))


def charger_bilan(chemin: Path) -> dict:
    try:
        bilan = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erreur:
        sys.exit(f"{chemin} illisible : {erreur}")
    if bilan.get("schema") != SCHEMA:
        sys.exit(f"{chemin} : schema {bilan.get('schema')!r} inconnu (attendu {SCHEMA}).")
    return bilan


def commande_fusion(options) -> int:
    bilans = [charger_bilan(Path(c)) for c in options.fusionner]
    mois = {b["mois"] for b in bilans}
    if len(mois) > 1:
        sys.exit(f"Mois différents dans les bilans à fusionner : {sorted(mois)}.")
    periodes = {(b.get("du"), b.get("au")) for b in bilans}
    if len(periodes) > 1:
        sys.exit(f"Périodes différentes dans les bilans à fusionner : {sorted(periodes, key=str)}.")
    du, au = bilans[0].get("du"), bilans[0].get("au")
    machines = [b["machine"] for b in bilans]
    if len(set(machines)) != len(machines):
        sys.exit(f"Machine présente plusieurs fois : {machines}.")
    mixes = {b.get("mix", mc.MIX_DEFAUT) for b in bilans}
    if len(mixes) > 1:
        sys.exit(f"Mix électriques différents dans les bilans à fusionner : {sorted(mixes)}.")
    methodes = {b.get("methode", "ecologits") for b in bilans}
    if len(methodes) > 1:
        sys.exit(f"Méthodes d'impact différentes dans les bilans à fusionner : {sorted(methodes)}. Recalculez-les avec la même --methode.")
    dossiers = [b.get("dossier") for b in bilans]
    if None in dossiers and any(dossiers):
        sys.exit(f"Portées différentes : certains bilans couvrent tous les projets, d'autres un dossier ({dossiers}).")
    distincts = sorted({d for d in dossiers if d})
    mois_unique = next(iter(mois))
    modeles = sommer_blocs([b["modeles"] for b in bilans])
    prix = {}
    for b in bilans:
        prix.update(b.get("prix", {}))
    consolide = {
        "schema": SCHEMA,
        "mois": mois_unique,
        **({"du": du, "au": au} if du else {}),
        "genere_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "premier_appel": min(b["premier_appel"] for b in bilans),
        "dernier_appel": max(b["dernier_appel"] for b in bilans),
        "dossier": " ; ".join(distincts) if distincts else None,
        "mix": mixes.pop(),
        "methode": methodes.pop(),
        "machines": machines,
        "par_machine": [
            {"machine": b["machine"], **totaux_machine(b["modeles"])} for b in bilans
        ],
        "modeles": modeles,
        "prix": prix,
    }
    if all("detail" in b for b in bilans):
        config = bd.charger_config(getattr(options, "config", None))
        consolide["detail"] = bd.fusionner([b["detail"] for b in bilans], config, consolide["mix"], consolide["methode"])
    elif any("detail" in b for b in bilans):
        print("Avertissement : tous les bilans n'ont pas de détail (--detail), le consolidé n'en a pas.", file=sys.stderr)
    periode = f"{du}_{au}" if du else mois_unique
    ecrire_bilan(consolide, options.out, periode, "consolide", langues_demandees(getattr(options, "langues", None)))
    afficher_tableau(modeles, f"Bilan {du + ' au ' + au if du else mois_unique} — consolidé ({', '.join(machines)})")
    return 0


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    analyseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analyseur.add_argument("--mois", help="AAAA-MM (défaut : mois UTC courant)")
    analyseur.add_argument("--dossier", type=Path, help="limite aux projets sous ce chemin (défaut : tous)")
    analyseur.add_argument("--du", metavar="AAAA-MM-JJ", help="premier jour (UTC, inclus), avec --au, dans le même mois ; exclusif avec --mois")
    analyseur.add_argument("--au", metavar="AAAA-MM-JJ", help="dernier jour (UTC, inclus)")
    analyseur.add_argument("--racine", type=Path, action="append", help="racine de transcriptions, répétable (défaut : ~/.claude/projects)")
    analyseur.add_argument("--detail", action="store_true", help="ajoute le détail par projet, étape et rôle (JSON et sections 04 à 07)")
    analyseur.add_argument("--config", type=Path, default=bd.CONFIG_DEFAUT, help="config du détail (défaut : ~/.claude/cost-kit/bilan-config.json)")
    analyseur.add_argument("--machine", default=platform.node())
    analyseur.add_argument("--out", type=Path, default=Path.home() / ".claude" / "cost-kit" / "bilans")
    analyseur.add_argument("--mix", choices=sorted(mc.MIX), default=mc.MIX_DEFAUT)
    analyseur.add_argument("--methode", choices=mc.METHODES, default=mc.METHODE_DEFAUT,
                           help="méthode d'impact : impactia (défaut, entrée comptée, expérimental) ou ecologits (sortie seule)")
    analyseur.add_argument("--langues", default=",".join(i18n.LANGUES),
                           help="pages HTML à écrire, séparées par des virgules (défaut : fr,en,de ; le français est toujours écrit)")
    analyseur.add_argument("--fusionner", nargs="+", metavar="JSON", help="fusionne ces bilans (une machine chacun) au lieu de collecter")
    options = analyseur.parse_args()
    if options.mois and (options.du or options.au):
        analyseur.error("--mois est exclusif avec --du/--au.")
    if options.fusionner:
        return commande_fusion(options)
    return commande_collecte(options)


if __name__ == "__main__":
    raise SystemExit(main())
