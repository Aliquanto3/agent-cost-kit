"""Coût réel des agents Claude Code, calculé depuis les transcriptions locales.

Lit ``~/.claude/projects/<projet encodé>/<session>.jsonl`` (session principale) et
``<session>/subagents/agent-<id>.jsonl`` + ``.meta.json`` (sous-agents), puis calcule pour
chaque agent, avec les mêmes règles :

- le coût en équivalent API par catégorie : entrée, écriture du cache (5 min ou 1 h selon
  ``usage.cache_creation``), lecture du cache, sortie ;
- la sortie réestimée : certaines transcriptions ne gardent que l'usage du début de la réponse
  (``output_tokens`` de 3 à 60). On retient max(sortie déclarée, caractères émis / k), avec
  k = 2,2 caractères par token : valeur mesurée avec l'endpoint count_tokens le 2026-10-13
  (médiane 2,13 sur 200 réponses en français). La réflexion masquée reste invisible : borne basse ;
- le pic de contexte, le contexte du premier appel, le nombre d'appels, la durée ;
- les expirations du cache (pause plus longue que le TTL, suivie d'une écriture > 20 k tokens) ;
- le coût contrefactuel avec l'autre TTL (5 min <-> 1 h) ;
- les arbres d'agents (racine de profondeur 1 et descendants), pour le coût par story ;
- une estimation de l'impact environnemental (énergie, GWP, eau, énergie primaire, ADPe) en
  fourchette min-max, sur les mêmes appels que le coût, selon ``--methode`` :
  ``impactia`` (défaut, expérimental : PR EcoLogits #259 non fusionnée, docs/impact-input-impactia.md)
  ajoute la durée de prefill des tokens d'entrée (lecture du cache : 0 en borne basse, prefill complet
  en borne haute), le réseau et le bâtiment du centre de données ; ``ecologits``
  (https://ecologits.ai/latest/methodology/llm_inference/) ne compte que les tokens de SORTIE.
  La réflexion masquée est absente des tokens comptés :
  l'estimation est une borne basse. Les paramètres des modèles Anthropic ne sont pas publiés,
  EcoLogits les estime (fourchettes). Latence : formule de repli ML.ENERGY d'EcoLogits (la voie
  OpenRouter n'est pas reproductible hors ligne). Mix électrique par défaut : USA (choix d'EcoLogits
  pour Anthropic), option --mix. Aucune dépendance à ``ecologits`` : coefficients intégrés,
  extraits de la librairie (commit d0b76e3, données du 2026-10-14) ; ``bancs/ecologits_ecart.py``
  compare ce calcul à la librairie.

Usage :
    python mesurer_couts.py                      # projet = dossier courant, toutes les sessions
    python mesurer_couts.py --projet C:/chemin/du/depot --session 3add3916 --out mesures/
    python mesurer_couts.py --filtre "Banc 6.11"  # agents dont la description contient le motif

Sorties : agents.csv, arbres.csv, resume.md dans --out (par défaut ./mesures-couts/), et un
tableau par agent sur la sortie standard. Aucun contenu de transcription n'est recopié, sauf la
description courte de chaque agent.

Prix : plugins/couts-session/donnees/tarifs.json, vérifiés sur https://platform.claude.com/docs/en/about-claude/pricing
(date dans le fichier), par identifiant de modèle (l'ancienne génération n'a pas le tarif de la récente).
Multiplicateur x 1,1 des appels dont ``usage.inference_geo`` vaut "us" (modèles 4.6 et suivants) ; les
transcriptions observées ne portent que "global" ou "not_available".
Coefficients d'impact : EcoLogits (https://ecologits.ai), commit d0b76e3, données du 2026-10-14.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Prix et coefficients EcoLogits : une seule table, plugins/couts-session/donnees/tarifs.json
# (partagée avec le mod couts-session). Ce script la lit, il n'a plus de constantes de prix.
TARIFS_JSON = Path(__file__).resolve().parent.parent / "plugins" / "couts-session" / "donnees" / "tarifs.json"
try:
    _TARIFS = json.loads(TARIFS_JSON.read_text(encoding="utf-8"))
except (OSError, ValueError) as erreur:
    sys.exit(f"Table des prix illisible ({TARIFS_JSON}) : {erreur}. Ce script doit rester dans le dépôt agent-cost-kit.")
_PRIX = _TARIFS["prix"]
_ECO = _TARIFS["ecologits"]

PRIX_MODELES = _PRIX["modeles"]  # {préfixe d'identifiant: {entree, sortie, lecture, ...}} en $/Mtok
PRIX_FAMILLES = _PRIX["familles"]  # repli, dans l'ordre : la première famille dont le nom figure dans l'identifiant
ECRITURE = _PRIX["ecriture_cache"]  # l'écriture coûte entrée x 1,25 (5 min) ou x 2 (1 h)
GEO_US_FACTEUR = _PRIX["inference_geo_us"]["facteur"]
TTL_S = {"5m": 300, "1h": 3600}
CARACTERES_PAR_TOKEN = 2.2
SEUIL_REECRITURE = 20_000

# Impact environnemental, méthodologie EcoLogits. Paramètres en milliards :
# (total_min, total_max, actif_min, actif_max). MoE : total fixe ; dense : total = actif.
# Le plus long préfixe de l'identifiant du modèle l'emporte ; à défaut, repli par famille.
PARAMETRES = {k: tuple(v) for k, v in _ECO["parametres"].items()}
PARAMETRES_FAMILLE = {k: tuple(v) for k, v in _ECO["parametres_famille"].items()}
FAMILLE_PAR_DEFAUT = _ECO["famille_par_defaut"]
LOT = _ECO["lot"]  # taille de lot supposée par EcoLogits
GPU_ENERGIE = tuple(_ECO["gpu_energie_wh_par_token"])  # Wh/token
GPU_LATENCE = tuple(_ECO["gpu_latence_s_par_token"])  # s/token
GPU_MEMOIRE_GO = _ECO["gpu_memoire_go"]
SERVEUR_PUISSANCE_W = _ECO["serveur_puissance_w"]
SERVEUR_GPUS = _ECO["serveur_gpus"]
DUREE_VIE_S = _ECO["duree_vie_s"]
# Fabrication : (kgCO2e, MJ, kgSbe) du serveur sans GPU et d'un GPU H100.
FAB_SERVEUR = tuple(_ECO["fabrication_serveur"].values())
FAB_GPU = tuple(_ECO["fabrication_gpu"].values())
PUE = tuple(_ECO["pue"])  # Anthropic
WUE_SITE = tuple(_ECO["wue_site_l_par_kwh"])  # L/kWh, Anthropic
# Mix électrique par kWh : (kgCO2e, MJ d'énergie primaire, kgSbe, L d'eau).
MIX = {k: tuple(v.values()) for k, v in _ECO["mix"].items()}
MIX_DEFAUT = _ECO["mix_par_defaut"]
# Méthode ImpactIA (PR EcoLogits #259, expérimentale) : prefill selon les tokens d'entrée, réseau, bâtiment.
_IMP = _TARIFS["impactia"]
METHODES = ("impactia", "ecologits")
METHODE_DEFAUT = _TARIFS["impact_methode_par_defaut"]
PREFILL_COEF = _IMP["prefill_coef_ref_s_par_token"]  # s/token d'entrée, Mistral 7B (Agrawal et al., 2024)
PREFILL_TTFT_REF = _IMP["prefill_ttft_ref_s"]  # s, TTFT médian OpenRouter de Mistral 7B
PREFILL_ORDONNEE = _IMP["prefill_ordonnee_s"]  # s par appel
RESEAU_W = _IMP["reseau_puissance_w"]
RESEAU_FAB = _IMP["reseau_fabrication_kgco2e"]
RESEAU_VIE_S = _IMP["reseau_duree_vie_s"]
BATIMENT = _IMP["batiment_kgco2e_par_kwh"]
TTFT = _IMP["ttft_s"]
TTFT_FAMILLE = _IMP["ttft_famille_s"]
GRANDEURS = ("energie_wh", "gwp_gco2e", "eau_l", "pe_mj", "adpe_mgsbe")


def dossier_transcriptions(projet: Path, racine: Path) -> Path:
    """Claude Code encode le chemin du projet en remplaçant tout caractère hors [A-Za-z0-9] par '-'."""
    encode = re.sub(r"[^A-Za-z0-9]", "-", str(projet.resolve()))
    return racine / encode


def famille(modele: str) -> str | None:
    return next((nom for nom in PRIX_FAMILLES if nom in modele), None)


def prefixe(modele: str, cle: str) -> bool:
    """``cle`` préfixe ``modele`` sans couper un numéro : claude-opus-4-5 couvre claude-opus-4-5-20251101
    et claude-opus-4-5[1m], pas claude-opus-4-50."""
    return modele.startswith(cle) and not modele[len(cle) : len(cle) + 1].isdigit()


def prix(modele: str) -> dict:
    """Tarif du modèle : plus long préfixe de l'identifiant, sinon repli par famille."""
    candidats = [cle for cle in PRIX_MODELES if prefixe(modele, cle)]
    if candidats:
        return PRIX_MODELES[max(candidats, key=len)]
    return PRIX_FAMILLES[famille(modele) or FAMILLE_PAR_DEFAUT]


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
            {"fam": fam, "modele": str(message.get("model", "")), "ts": entree.get("timestamp", ""), "car": 0, "u": {}},
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
    for mid, appel in par_id.items():
        u = appel["u"]
        ecrit = int(u.get("cache_creation_input_tokens") or 0)
        ecrit_1h = int((u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0)
        sortie_declaree = int(u.get("output_tokens") or 0)
        resultat.append(
            {
                "id": mid,
                "fam": appel["fam"],
                "modele": appel["modele"],
                "geo": u.get("inference_geo"),
                "ts": appel["ts"],
                "entree": int(u.get("input_tokens") or 0),
                "ecrit_5m": ecrit - ecrit_1h,
                "ecrit_1h": ecrit_1h,
                "lu": int(u.get("cache_read_input_tokens") or 0),
                "sortie_declaree": sortie_declaree,
                "sortie": max(sortie_declaree, int(appel["car"] / CARACTERES_PAR_TOKEN)),
            }
        )
    return sorted((a for a in resultat if a["ts"]), key=lambda a: instant(a["ts"]))


def dedoublonner(agents: list[tuple]) -> tuple[list[tuple], int]:
    """Chaque message.id n'est compté qu'une fois sur l'ensemble des transcriptions retenues.

    Une session reprise ou redémarrée recopie les réponses de l'ancienne avec les mêmes message.id, et un
    sous-agent peut figurer sous les deux sessions. On garde la première occurrence chronologique (à égalité,
    la session qui a démarré en premier), rattachée à sa session d'origine ; les agents devenus vides sont
    retirés. Les instants sont comparés parsés (formats « .500Z » et « Z » mêlés).
    ``agents`` : [(session, ident, chemin, meta, appels)]. Retourne ([(session, ident, chemin, meta, gardés,
    tous)], nombre de doublons) : ``tous`` garde les appels retirés, qui restent le « précédent » des
    suivants pour les pauses et les expirations (une reprise qui attend après la réponse recopiée expire).
    """
    debut: dict[str, datetime] = {}
    for session, _, _, _, liste in agents:
        for a in liste:
            t = instant(a["ts"])
            debut[session] = min(debut.get(session, t), t)
    proprietaire: dict[str, tuple] = {}
    for session, ident, _, _, liste in agents:
        for a in liste:
            cle = (instant(a["ts"]), debut[session], session, ident)
            if a["id"] not in proprietaire or cle < proprietaire[a["id"]]:
                proprietaire[a["id"]] = cle
    resultat, doublons = [], 0
    for session, ident, chemin, meta, liste in agents:
        gardes = [a for a in liste if proprietaire[a["id"]][2:] == (session, ident)]
        doublons += len(liste) - len(gardes)
        if gardes:
            resultat.append((session, ident, chemin, meta, gardes, liste))
    return resultat, doublons


def parametres(modele: str) -> tuple[float, float, float, float]:
    """(total_min, total_max, actif_min, actif_max) en milliards de paramètres."""
    candidats = [cle for cle in PARAMETRES if modele.startswith(cle)]
    if candidats:
        return PARAMETRES[max(candidats, key=len)]
    return PARAMETRES_FAMILLE.get(famille(modele) or "", PARAMETRES_FAMILLE[FAMILLE_PAR_DEFAUT])


def ttft(modele: str) -> float:
    """TTFT médian (s) : plus long préfixe de l'identifiant, sinon famille, sinon famille par défaut."""
    candidats = [cle for cle in TTFT if modele.startswith(cle)]
    if candidats:
        return TTFT[max(candidats, key=len)]
    return TTFT_FAMILLE.get(famille(modele) or "", TTFT_FAMILLE[FAMILLE_PAR_DEFAUT])


def impact(
    modele: str, sortie: float, mix: str = MIX_DEFAUT, *, entree: float = 0, lu: float = 0, appels: float = 0,
    methode: str = METHODE_DEFAUT,
) -> dict[str, dict[str, float]]:
    """Impact de ``appels`` appels de ``modele`` : {grandeur: {"min", "max"}}.

    ``sortie`` : tokens générés ; ``entree`` : entrée fraîche + écriture du cache (prefill complet) ;
    ``lu`` : lecture du cache (0 en borne basse, prefill complet en borne haute). ``entree``, ``lu`` et
    ``appels`` ne servent qu'à la méthode impactia ; ``ecologits`` ne compte que la sortie.
    Énergie en Wh, GWP en gCO2e, eau en L, énergie primaire en MJ, ADPe en mgSbe. Grandeurs
    linéaires en chaque argument : on peut donc sommer les tokens et les appels avant d'appeler.
    """
    if methode not in METHODES:
        raise ValueError(f"méthode inconnue : {methode}")
    gwp_kwh, pe_kwh, adpe_kwh, wue_mix = MIX[mix]
    t_min, t_max, a_min, a_max = parametres(modele)
    alpha, beta, gamma = GPU_ENERGIE
    la, lb, lg = GPU_LATENCE
    impactia = methode == "impactia"
    # Prefill (PR #259, llm.py l. 105-144). En ecologits, les zéros ajoutés laissent le calcul identique bit à bit.
    coef = PREFILL_COEF * ttft(modele) / PREFILL_TTFT_REF if impactia else 0.0
    ordonnee = PREFILL_ORDONNEE * appels if impactia else 0.0
    prefill = {"min": coef * entree + ordonnee, "max": coef * (entree + lu) + ordonnee}
    reseau_w = RESEAU_W if impactia else 0.0
    resultat: dict[str, dict[str, float]] = {}
    for borne, total, actif, pue, wue in (
        ("min", t_min, a_min, PUE[0], WUE_SITE[0]),
        ("max", t_max, a_max, PUE[1], WUE_SITE[1]),
    ):
        f_energie = alpha * math.exp(beta * LOT) * actif + gamma
        duree = sortie * (la * actif + lb * LOT + lg) + prefill[borne]
        gpus = 2 ** math.ceil(math.log2(max(1, math.ceil(1.2 * total * 16 / 8 / GPU_MEMOIRE_GO))))
        part = gpus / SERVEUR_GPUS
        e_ti_wh = duree / 3600 * (SERVEUR_PUISSANCE_W + reseau_w) * part / LOT + gpus * sortie * f_energie
        e_wh = pue * e_ti_wh
        e_kwh = e_wh / 1000
        fab = [
            duree / (LOT * DUREE_VIE_S) * (part * serveur + gpus * gpu)
            for serveur, gpu in zip(FAB_SERVEUR, FAB_GPU)
        ]
        if impactia:  # réseau et bâtiment : GWP seulement (llm.py l. 477-546)
            fab[0] += duree / (LOT * RESEAU_VIE_S) * part * RESEAU_FAB + e_ti_wh / 1000 * BATIMENT
        valeurs = {
            "energie_wh": e_wh,
            "gwp_gco2e": (e_kwh * gwp_kwh + fab[0]) * 1000,
            "eau_l": e_ti_wh / 1000 * (wue + pue * wue_mix),
            "pe_mj": e_kwh * pe_kwh + fab[1],
            "adpe_mgsbe": (e_kwh * adpe_kwh + fab[2]) * 1e6,
        }
        for nom, v in valeurs.items():
            resultat.setdefault(nom, {})[borne] = v
    return resultat


def impact_appels(liste: list[dict], mix: str, methode: str = METHODE_DEFAUT) -> dict[str, dict[str, float]]:
    """Somme des impacts d'une liste d'appels (sortie réestimée ; entrée et cache selon la méthode)."""
    tokens: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])  # sortie, entrée + écriture, lecture, appels
    for a in liste:
        t = tokens[a["modele"]]
        t[0] += a["sortie"]
        t[1] += a["entree"] + a["ecrit_5m"] + a["ecrit_1h"]
        t[2] += a["lu"]
        t[3] += 1
    total = {g: {"min": 0.0, "max": 0.0} for g in GRANDEURS}
    for modele, (n, entree, lu, nb) in tokens.items():
        for g, bornes in impact(modele, n, mix, entree=entree, lu=lu, appels=nb, methode=methode).items():
            for b in ("min", "max"):
                total[g][b] += bornes[b]
    return total


def fourchette(bas: float, haut: float, chiffres: int = 2) -> str:
    """``chiffres`` décimales ; deux chiffres significatifs si l'arrondi effacerait une valeur non nulle."""

    def texte(v: float) -> str:
        t = f"{v:.{chiffres}f}"
        return f"{v:.2g}" if v and float(t) == 0 else t

    return f"{texte(bas)}-{texte(haut)}"


def hors_liste(modeles) -> list[str]:
    """Identifiants sans entrée dans PARAMETRES : leurs paramètres viennent de la famille."""
    return sorted({m for m in modeles if not any(m.startswith(cle) for cle in PARAMETRES)})


def couts(liste: list[dict], compter: set[str] | None = None) -> dict:
    """Coût réel, expirations et contrefactuel avec l'autre TTL.

    ``compter`` : les message.id à compter (défaut : tous). Les autres appels de ``liste`` (recopiés d'une
    autre session) ne coûtent rien ici mais servent de précédent pour la pause et le contexte.
    """
    total: dict[str, float] = defaultdict(float)
    expirations = 0
    reecriture = 0.0
    contrefactuel = 0.0
    precedent = None
    ctx_precedent = 0
    for a in liste:
        tarif = prix(a["modele"])
        p_entree, p_sortie, p_lu = tarif["entree"], tarif["sortie"], tarif["lecture"]
        ttl = "1h" if a["ecrit_1h"] > a["ecrit_5m"] else "5m"
        autre = "5m" if ttl == "1h" else "1h"
        ecrit = a["ecrit_5m"] + a["ecrit_1h"]
        ctx = a["entree"] + ecrit + a["lu"]
        long = tarif.get("long_contexte")
        if compter is not None and a["id"] not in compter:
            precedent = a
            ctx_precedent = ctx + a["sortie"]
            continue
        if long and ctx > long["seuil_tokens"]:
            p_entree, p_sortie, p_lu = (p * long["facteur"] for p in (p_entree, p_sortie, p_lu))
        if a.get("geo") == "us" and tarif.get("geo_us", True):
            p_entree, p_sortie, p_lu = (p * GEO_US_FACTEUR for p in (p_entree, p_sortie, p_lu))
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


TYPES_ALERTE = ("dev-story", "reviewer")
FACTEUR_ALERTE = 2


def derapages(lignes: list[dict], types=TYPES_ALERTE, facteur: float = FACTEUR_ALERTE) -> list[dict]:
    """Agents dont le nombre d'appels dépasse `facteur` x la médiane des agents du même type (alerte, jamais une coupure)."""
    sortie = []
    for t in types:
        groupe = [l for l in lignes if str(l["type"]).split(":")[-1] == t]
        if not groupe:
            continue
        med = mediane([l["appels"] for l in groupe])
        sortie += [
            {"type": t, "mediane": med, "seuil": facteur * med, **l}
            for l in groupe
            if l["appels"] > facteur * med
        ]
    return sorted(sortie, key=lambda l: (l["type"], -l["cout_usd"]))


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    analyseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analyseur.add_argument("--projet", type=Path, default=Path.cwd(), help="dossier du dépôt (défaut : dossier courant)")
    analyseur.add_argument("--racine", type=Path, default=Path.home() / ".claude" / "projects")
    analyseur.add_argument("--session", nargs="*", help="préfixes des sessions à retenir (défaut : toutes)")
    analyseur.add_argument("--filtre", help="motif (regex, insensible à la casse) sur la description des agents")
    analyseur.add_argument("--out", type=Path, default=Path("mesures-couts"))
    analyseur.add_argument("--mix", choices=sorted(MIX), default=MIX_DEFAUT, help="mix électrique pour l'impact (défaut : USA, choix d'EcoLogits pour Anthropic)")
    analyseur.add_argument("--methode", choices=METHODES, default=METHODE_DEFAUT,
                           help="méthode d'impact : impactia (défaut, entrée comptée, expérimental) ou ecologits (sortie seule)")
    analyseur.add_argument("--car-par-token", type=float, default=2.2, help="caractères par token pour la sortie réestimée (2,2 mesuré, voir bancs/)")
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
    par_modele: dict = defaultdict(lambda: {g: {"min": 0.0, "max": 0.0} for g in GRANDEURS})
    identifiants: set[str] = set()
    retenus = []
    for session, ident, chemin, meta in agents_du_projet(dossier, options.session):
        if motif and not motif.search(str(meta.get("description", ""))):
            continue
        liste = appels(chemin)
        if liste:
            retenus.append((session, ident, chemin, meta, liste))
    retenus, doublons = dedoublonner(retenus)
    for session, ident, chemin, meta, liste, tous in retenus:
        description = str(meta.get("description", ""))
        c = couts(tous, {a["id"] for a in liste})
        imp = impact_appels(liste, options.mix, options.methode)
        identifiants |= {a["modele"] for a in liste}
        est_main = ident == "MAIN"
        for fam in {a["fam"] for a in liste}:
            part = impact_appels([a for a in liste if a["fam"] == fam], options.mix, options.methode)
            for g in GRANDEURS:
                for b in ("min", "max"):
                    par_modele[(est_main, fam)][g][b] += part[g][b]
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
                "methode_impact": options.methode,
                **{f"{g}_{b}": float(f"{imp[g][b]:.4g}") for g in GRANDEURS for b in ("min", "max")},
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
    # Parent dont tous les appels sont rattachés à une autre session (dédoublonnage) : on le cherche là.
    par_agent = {l["agent"]: l for l in lignes if l["type"] != "MAIN"}

    def racine(l):
        vus = 0
        while l["profondeur"] not in (0, 1, "") and l["parent"] and vus < 10:
            parent = index.get((l["session"], l["parent"])) or par_agent.get(l["parent"])
            if parent is None:
                break
            l, vus = parent, vus + 1
        return l

    arbres: dict = defaultdict(list)
    for l in lignes:
        if l["type"] == "MAIN":
            continue
        r = racine(l)
        arbres[(r["session"], r["agent"])].append(l)
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
                **{
                    f"{g}_{b}": float(f"{sum(m[f'{g}_{b}'] for m in membres):.4g}")
                    for g in ("energie_wh", "gwp_gco2e", "eau_l")
                    for b in ("min", "max")
                },
            }
        )
    if lignes_arbres:
        with (options.out / "arbres.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(lignes_arbres[0]))
            writer.writeheader()
            writer.writerows(lignes_arbres)
    resume(options.out, options.projet, lignes, lignes_arbres, par_modele, options.mix, hors_liste(identifiants), doublons,
           bool(options.session or options.filtre), options.methode)
    # Tableau par agent sur la sortie standard.
    print(f"{'session':8} {'agent':8} {'modèle':7} {'appels':>6} {'min':>6} {'1er ctx':>8} {'pic':>7} {'exp':>3} {'coût $':>8} {'gCO2e':>11}  description")
    for l in lignes:
        print(
            f"{l['session']:8} {l['agent']:8} {l['modele']:7} {l['appels']:6d} {l['duree_min']:6.1f} "
            f"{l['premier_ctx'] / 1000:6.1f} k {l['pic_ctx'] / 1000:5.0f} k {l['expirations']:3d} {l['cout_usd']:8.3f} {fourchette(l['gwp_gco2e_min'], l['gwp_gco2e_max'], 1):>11}  {l['description']}"
        )
    gwp_bas, gwp_haut = (sum(l[f"gwp_gco2e_{b}"] for l in lignes) for b in ("min", "max"))
    nrj_bas, nrj_haut = (sum(l[f"energie_wh_{b}"] for l in lignes) for b in ("min", "max"))
    eau_bas, eau_haut = (sum(l[f"eau_l_{b}"] for l in lignes) for b in ("min", "max"))
    print(
        f"\nTotal : {sum(l['cout_usd'] for l in lignes):.2f} $ sur {len(lignes)} agents. "
        f"Impact ({NOM_METHODE[options.methode]}, mix {options.mix}) : {fourchette(gwp_bas, gwp_haut, 0)} gCO2e, "
        f"{fourchette(nrj_bas, nrj_haut, 0)} Wh, {fourchette(eau_bas, eau_haut, 1)} L d'eau. Détail : {options.out}/"
    )
    return 0


NOM_METHODE = {"impactia": "ImpactIA, expérimental", "ecologits": "EcoLogits, sortie seule"}
MISE_EN_GARDE_ENTREE = {
    "impactia": "- L'entrée compte par la durée de prefill (serveur, réseau, fabrication ; pas l'énergie GPU, que la PR ne "
    "modélise pas). Lecture du cache : 0 en borne basse (le KV cache n'est pas recalculé), prefill complet en borne haute ; "
    "la fourchette porte donc surtout cette incertitude. `--methode ecologits` : sortie seule, comme EcoLogits.",
    "ecologits": "- Seuls les tokens de **sortie** comptent, comme dans EcoLogits : ni l'entrée ni le cache n'ont d'impact "
    "dans ce modèle. Or le cache fait environ 85 % du coût en dollars : l'empreinte n'est pas proportionnelle au coût. "
    "`--methode impactia` (défaut) compte l'entrée.",
}


def resume(
    dossier: Path, projet: Path, lignes: list[dict], arbres: list[dict], par_modele: dict, mix: str, replis: list[str] | None = None, doublons: int = 0,
    partiel: bool = False, methode: str = METHODE_DEFAUT,
) -> None:
    sous = [l for l in lignes if l["type"] != "MAIN"]
    main_ = [l for l in lignes if l["type"] == "MAIN"]
    sortie = [f"# Coût des agents : {projet.resolve().name}", ""]
    sortie.append(f"Sortie réestimée à {CARACTERES_PAR_TOKEN} caractères par token (réflexion masquée non comptée).")
    if doublons:
        sortie.append(
            f"{doublons} appels dédoublonnés : sessions reprises ou redémarrées qui recopient les réponses "
            "d'une autre (même message.id), comptées une seule fois, dans leur session d'origine."
        )
    if partiel:
        sortie.append(
            "Sélection partielle (--session ou --filtre) : le dédoublonnage ne porte que sur les transcriptions "
            "retenues, une réponse recopiée compte dans la session retenue ; les totaux de plusieurs sélections "
            "ne s'additionnent pas."
        )
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
    derives = derapages(sous)
    if derives:
        sortie += ["", f"## Alerte de dérapage (plus de {FACTEUR_ALERTE} x la médiane d'appels du même type)", ""]
        sortie.append("Information seulement : aucune coupure (une story coupée doit être reprise, et les plus longues sont souvent les plus difficiles).")
        sortie += ["", "| Type | Session | Agent | Appels | Médiane du type | Coût | Description |", "|---|---|---|---|---|---|---|"]
        for l in derives:
            sortie.append(
                f"| {l['type']} | {l['session']} | {l['agent']} | {l['appels']} | {l['mediane']:.0f} "
                f"| {l['cout_usd']:.2f} $ | {l['description']} |"
            )
    sortie += ["", f"## Impact environnemental ({NOM_METHODE[methode]})", ""]
    if methode == "impactia":
        sortie.append(
            f"Estimation en fourchette min-max, mix électrique {mix}, méthode ImpactIA **expérimentale**, d'après la PR "
            "[EcoLogits #259](https://github.com/mlco2/ecologits/pull/259) non fusionnée (docs/impact-input-impactia.md), "
            "sur les données [EcoLogits](https://ecologits.ai/latest/methodology/llm_inference/) du 2026-10-14."
        )
    else:
        sortie.append(
            f"Estimation en fourchette min-max, mix électrique {mix}, méthodologie "
            "[EcoLogits](https://ecologits.ai/latest/methodology/llm_inference/) (données du 2026-10-14)."
        )
    sortie.append("")
    sortie.append("| Périmètre | Énergie | GWP (usage + fabrication) | Eau |")
    sortie.append("|---|---|---|---|")
    for nom, groupe in (("Sessions principales", main_), ("Sous-agents", sous), ("Total", lignes)):
        if not groupe:
            continue
        v = {g: tuple(sum(l[f"{g}_{b}"] for l in groupe) for b in ("min", "max")) for g in ("energie_wh", "gwp_gco2e", "eau_l")}
        sortie.append(
            f"| {nom} | {fourchette(*v['energie_wh'], 1)} Wh | {fourchette(*v['gwp_gco2e'], 1)} gCO2e "
            f"| {fourchette(*v['eau_l'], 2)} L |"
        )
    gros_impact = [a for a in arbres if a["agents"] > 1]
    if gros_impact:
        sortie += ["", "Médiane par arbre d'agents de plus d'un agent : "
                   f"{fourchette(mediane([a['energie_wh_min'] for a in gros_impact]), mediane([a['energie_wh_max'] for a in gros_impact]), 1)} Wh, "
                   f"{fourchette(mediane([a['gwp_gco2e_min'] for a in gros_impact]), mediane([a['gwp_gco2e_max'] for a in gros_impact]), 1)} gCO2e, "
                   f"{fourchette(mediane([a['eau_l_min'] for a in gros_impact]), mediane([a['eau_l_max'] for a in gros_impact]), 2)} L."]
    total_gwp = sum(m["gwp_gco2e"]["max"] + m["gwp_gco2e"]["min"] for m in par_modele.values()) or 1e-9
    familles = sorted({fam for (_, fam) in par_modele})
    sortie += ["", "| Modèle | Part du GWP (moyenne min-max) | GWP |", "|---|---|---|"]
    for fam in sorted(familles, key=lambda f: -sum(par_modele[(m, f)]["gwp_gco2e"]["max"] for m in (True, False) if (m, f) in par_modele)):
        bas = sum(par_modele[(m, fam)]["gwp_gco2e"]["min"] for m in (True, False) if (m, fam) in par_modele)
        haut = sum(par_modele[(m, fam)]["gwp_gco2e"]["max"] for m in (True, False) if (m, fam) in par_modele)
        sortie.append(f"| {fam} | {(bas + haut) / total_gwp:.0%} | {fourchette(bas, haut, 1)} gCO2e |")
    sortie += [
        "",
        "Mises en garde :",
        "",
        MISE_EN_GARDE_ENTREE[methode],
        "- La réflexion masquée n'est pas dans les tokens comptés : l'estimation est une borne basse.",
        "- Les paramètres des modèles Anthropic ne sont pas publiés ; EcoLogits les estime et le signale "
        "(avertissement « architecture non publiée »), d'où la fourchette. "
        "Latence : formule de repli ML.ENERGY (pas de mesure).",
        f"- Mix électrique {mix} (USA : choix d'EcoLogits pour Anthropic) ; changez-le avec `--mix`. "
        "La fabrication du matériel est incluse dans le GWP, pas dans l'eau.",
    ]
    if replis:
        sortie.append(
            "- Modèles absents de la table du script, estimés avec les paramètres de leur famille : "
            + ", ".join(f"`{m}`" for m in replis) + "."
        )
    (dossier / "resume.md").write_text("\n".join(sortie) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
