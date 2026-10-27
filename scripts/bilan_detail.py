"""Détail du bilan des tokens par projet, par étape et par rôle (option ``--detail`` de ``bilan_tokens.py``).

Réutilise ``mesurer_couts`` (appels, couts, impact, prix) ; stdlib seulement. Chaque appel est classé :

- **projet** : premier segment du ``cwd`` sous un dossier parent de dépôts (``parents``), puis ``alias``, puis
  clé du portfolio (nom égal ou préfixe suivi de ``-`` ou ``_``, la plus longue d'abord), sinon le nom tel quel ;
- **étape** : onze familles (``GROUPES``), d'après le skill actif de la session principale ou du sous-agent, le
  type du sous-agent, ses mots (description, premier prompt) ou l'outil de l'appel ;
- **rôle** : orchestrateur (session principale) ou type de sous-agent, avec la sous-clé ``modèle · effort``.

Rien d'un texte de transcription n'est conservé : les descriptions et les prompts des sous-agents servent au
classement, puis sont oubliés. Le résultat (``brut``) est une table de sommes par cellule et par modèle, donc
fusionnable entre PC : les blocs d'affichage et les recommandations se recalculent depuis elle.
"""

from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesurer_couts as mc

# --- Familles d'étapes, dans l'ordre d'affichage ---
GROUPES = [
    ("besoin", "🧭 Cadrage du besoin"), ("specs", "📝 Spécifications"), ("archi", "🏛️ Architecture et plan"),
    ("dev", "🛠️ Développement"), ("relecture", "🔍 Relecture et tests"), ("livraison", "🚀 Intégration et livraison"),
    ("pilotage", "🎛️ Pilotage et orchestration"), ("recherche", "🔎 Recherche et documentation"),
    ("outillage", "🧰 Outillage et mesure"), ("contenus", "🎨 Contenus et communication"),
    ("libre", "💬 Échanges sans étape identifiée"),
]
# Motif sur le nom du skill -> famille (le premier qui correspond l'emporte).
SKILLS = [
    (r"forge-idea|brainstorm|product-brief|prfaq|party-mode|agent-analyst|agent-pm", "besoin"),
    (r"deep-recon|deep-research|claude-api|claude-code-guide|veille", "recherche"),
    (r"prd|bmad-spec|bmad-ux|epics|create-story|user-stories|07-epic|three-amigos|backlog|technical-specs", "specs"),
    (r"architect|spike|01-plan", "archi"),
    (r"build|dev-story|02-implement|agent-dev|refactor", "dev"),
    (r"code-review|bmad-review|05-review|03-assert|qa-|security-review|simplify|walkthrough|chrome|browser", "relecture"),
    (r"aidd-vcs|commit|pull-request", "livraison"),
    (r"sprint-planning|correct-course|retrospective|avancement-run|bmad-help|loop", "pilotage"),
    (r"cost-kit|mesurer-couts|bilan-tokens|plugin|update-config|permission|schedule|workflow-authoring"
     r"|keybindings|statusline|init|project-context|customize|skill-creator|demo-mod", "outillage"),
    (r"wavestone|writing-style|slide|carrousel|linkedin|artifact|dataviz|docs|pptx|docx|credential|propale"
     r"|writing-technical-docs", "contenus"),
]
# Commandes qui ne changent pas de tâche : elles n'interrompent ni ne remplacent le skill actif.
IGNORES = {"plugin", "reload-plugins", "login", "model", "effort", "context", "details", "agents", "rename",
           "raccourcis", "focus", "exit", "usage", "cost", "config", "status", "resume", "compact", "fast"}
COMMANDE_EFFACER = "clear"
# Type de sous-agent explicite -> (famille, sous-libellé fixe).
AGENTS = {
    "agent-cost-kit:dev-story": ("dev", "dev-story (agent-cost-kit)"), "dev-story": ("dev", "dev-story (agent-cost-kit)"),
    "agent-cost-kit:reviewer": ("relecture", "reviewer (agent-cost-kit)"), "reviewer": ("relecture", "reviewer (agent-cost-kit)"),
    "agent-cost-kit:second-avis": ("relecture", "second-avis (agent-cost-kit)"),
    "second-avis": ("relecture", "second-avis (agent-cost-kit)"),
    "agent-cost-kit:lookup": ("recherche", "lookup / Explore"), "lookup": ("recherche", "lookup / Explore"),
    "Explore": ("recherche", "lookup / Explore"), "claude-code-guide": ("recherche", "claude-code-guide"),
    "Plan": ("archi", "Plan (sous-agent)"),
}
# Mots de la description puis du prompt d'un sous-agent -> famille (le premier qui correspond l'emporte).
DESC = [
    (r"review|revue|relecture|audit|hunter|v[ée]rif|recette|e2e|assert|\bqa\b|test|banc", "relecture"),
    (r"recherche|research|search|explor|veille|lookup|investig|analy", "recherche"),
    (r"archi|plan\b|design", "archi"),
    (r"implement|impl[ée]ment|story|fix|lot\b|lot \d|restes|finish|refactor|rewrite|port|corrig", "dev"),
    (r"spec|prd|epic", "specs"),
]
ETIQ = {"relecture": "revue, audit, tests", "recherche": "recherche", "archi": "plan, conception",
        "dev": "implémentation", "specs": "spécification"}
LIVRAISON = re.compile(r"git push|gh pr (create|merge)|gh release|git tag|gh run|git merge|deploy|docker push|gh workflow")
TESTS = re.compile(r"pytest|ruff|mypy|npm (run )?test|playwright|vitest|cargo test|go test")
OUTILS_SOUS_AGENT = ("Agent", "Task", "Workflow", "SendMessage")
OUTILS_EDITION = ("Edit", "Write", "MultiEdit", "NotebookEdit")
OUTILS_WEB = ("WebSearch", "WebFetch")
OUTILS_COMMANDE = mc.OUTILS_COMMANDE
LIBELLE_LIVRAISON = "Git, PR, CI et release"
LIBELLE_LECTURE = "Lecture du code et commandes"
LIBELLE_SANS_OUTIL = "Réponse ou réflexion sans outil"
PROMPT_MAX = 300
COMMANDE = re.compile(r"<command-name>/?([^<]+)</command-name>")

# --- Projets ---
PARENTS_DEFAUT = ["GitHub", "dev"]
RACINE = "_racine"
NOM_RACINE = "Racine des dépôts (sessions transverses)"
ORCHESTRATEUR = "Orchestrateur (session principale)"
PREFIXE_KIT = "agent-cost-kit:"
TYPES_DU_KIT = ("dev-story", "reviewer", "lookup", "second-avis")
ROLE_DEV_STORY = PREFIXE_KIT + "dev-story"
ROLE_REVIEWER = PREFIXE_KIT + "reviewer"
ROLE_GENERALISTE = "general-purpose"
CONFIG_DEFAUT = Path.home() / ".claude" / "cost-kit" / "bilan-config.json"
MOTIF_EXPERIENCES_DEFAUT = r"^(T\d|Banc|banc|Test W)"
MOTIF_RELECTEURS = re.compile(r"hunter|intent alignment|acceptance auditor|adversarial lens", re.I)
DELAI_GH_S = 30

# --- Agrégation ---
STATS = ("appels", "entree", "ecrit_5m", "ecrit_1h", "lu", "sortie_declaree", "sortie")
POSTES = ("entree", "ecriture", "lecture", "sortie")
DIM_PROJET, DIM_ETAPE, DIM_ETAPE_ORCH, DIM_ROLE, DIM_DESC = "projet", "etape", "etape_orch", "role", "desc"
DESC_RELECTEURS, DESC_EXPERIENCES = "relecteurs", "experiences"

# --- Seuils des recommandations ---
IMPL_MIN_GENERALISTES = 5  # sous-agents généralistes classés « dev » (et autant de dev-story) pour comparer
IMPL_FACTEUR_MEDIANE = 1.5
IMPL_MARGE = 0.2
RELECTEURS_PART_MIN = 0.03
REVIEWER_OPUS_PART = 0.5
REVIEWER_GAIN_OPUS = 0.25
RELECTEURS_GAIN_MIN = 0.5
CONTEXTE_FACTEUR = 1.5
CONTEXTE_ORCH_PART_MIN = 0.2
CONTEXTE_GAIN = (0.4, 0.8)
MODELE_PART_MIN = 0.01
MODELE_MARGE = 0.1
PILOTAGE_PART_MIN = 0.05
PILOTAGE_SESSION_MIN = 0.8
PILOTAGE_GAIN = (0.2, 0.4)
EFFORT_APPELS_MIN = 100
EFFORT_ECART = 0.10
AMONT_PART_MAX = 0.15
COEUR_PART_MIN = 0.5


def fr(v: float, decimales: int = 0) -> str:
    """Nombre à la française : séparateur de milliers fin insécable, virgule décimale."""
    return f"{v:,.{decimales}f}".replace(",", " ").replace(".", ",")


def usd(v: float) -> str:
    return f"{fr(v, 0 if v >= 100 else 2)} $"


def pct(v: float, total: float) -> str:
    if not total:
        return ""
    part = v / total
    return f"{fr(100 * part, 1 if part < 0.01 else 0)} %"


# --- Lecture des transcriptions ---
def lire_infos(chemin: Path) -> dict:
    """Skills invoqués (horodatés), type, description et début du premier prompt d'un fichier."""
    sous_agent = "subagents" in chemin.parts
    info: dict = {"skills": [], "desc": None, "prompt": None, "type": None, "premier_ts": None}
    if sous_agent:
        info["type"] = "?"
        meta = chemin.with_suffix(".meta.json")
        if meta.exists():
            try:
                donnees = json.loads(meta.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                donnees = {}
            if isinstance(donnees, dict):
                info["type"] = donnees.get("agentType") or "?"
                info["desc"] = donnees.get("description")
    for ligne in chemin.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entree = json.loads(ligne)
        except ValueError:
            continue
        message = entree.get("message")
        if not isinstance(message, dict):
            continue
        ts, contenu = entree.get("timestamp", ""), message.get("content")
        if message.get("role") == "user":
            texte = contenu if isinstance(contenu, str) else " ".join(
                b.get("text", "") for b in (contenu or []) if isinstance(b, dict) and b.get("type") == "text"
            )
            if sous_agent and info["prompt"] is None and texte and not entree.get("isMeta"):
                info["prompt"] = texte[:PROMPT_MAX]
            info["skills"].extend((ts, nom.strip()) for nom in COMMANDE.findall(texte or ""))
        elif message.get("role") == "assistant":
            for bloc in contenu or []:
                if isinstance(bloc, dict) and bloc.get("type") == "tool_use" and bloc.get("name") == "Skill":
                    saisie = bloc.get("input") if isinstance(bloc.get("input"), dict) else {}
                    info["skills"].append((ts, str(saisie.get("skill"))))
    return info


def lire_fichier(chemin: Path) -> tuple[list[dict], dict]:
    """Appels détaillés d'un fichier (avec ``fichier`` et ``agent_type``) et ses informations de classement."""
    liste = mc.appels(chemin, details=True)
    info = lire_infos(chemin)
    info["premier_ts"] = liste[0]["ts"] if liste else None
    for a in liste:
        a["fichier"], a["agent_type"] = str(chemin), info["type"]
    return liste, info


# --- Config ---
def charger_config(chemin: Path | None) -> dict:
    """Config du bilan ; fichier absent = valeurs par défaut, JSON invalide = erreur claire."""
    config: dict = {"portfolio": {}, "alias": {}, "parents": list(PARENTS_DEFAUT), "motif_experiences": MOTIF_EXPERIENCES_DEFAUT}
    if chemin is None or not chemin.exists():
        return config
    try:
        lue = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erreur:
        sys.exit(f"Config {chemin} illisible : {erreur}")
    if not isinstance(lue, dict):
        sys.exit(f"Config {chemin} : un objet JSON est attendu.")
    config.update({k: v for k, v in lue.items() if k in config})
    try:
        re.compile(config["motif_experiences"])
    except re.error as erreur:
        sys.exit(f"Config {chemin} : motif_experiences invalide ({erreur}).")
    return config


def lire_portfolio(config: dict) -> dict:
    """Portfolio de la config : ``repos`` {clé: nom}, ``statuses`` {topic: libellé}, ``proprietaire``, ``topic``, ``url``."""
    section = config.get("portfolio") or {}
    portfolio = {"repos": {}, "statuses": {}, "proprietaire": section.get("proprietaire"),
                 "topic": section.get("topic"), "url": section.get("url")}
    if section.get("fichier"):
        try:
            donnees = json.loads(Path(section["fichier"]).expanduser().read_text(encoding="utf-8"))
        except (OSError, ValueError) as erreur:
            sys.exit(f"Portfolio {section['fichier']} illisible : {erreur}")
        portfolio["repos"] = {cle: v.get("name", cle) for cle, v in (donnees.get("repos") or {}).items()}
        portfolio["statuses"] = {t: v.get("fr", t) for t, v in (donnees.get("statuses") or {}).items()}
        portfolio["topic"] = portfolio["topic"] or donnees.get("topic")
    return portfolio


def executer_gh(arguments: list[str]) -> str:
    """Exécute ``gh`` (30 s au plus) et renvoie sa sortie ; lève en cas d'échec."""
    resultat = subprocess.run(
        ["gh", *arguments], capture_output=True, text=True, encoding="utf-8", timeout=DELAI_GH_S, check=True
    )
    return resultat.stdout


def lire_etats(portfolio: dict, executer=None) -> dict[str, dict]:
    """{nom de dépôt en minuscules: {statut, version}} lus par ``gh`` ; vide (avec avertissement) en cas d'échec."""
    if not portfolio["proprietaire"] or not portfolio["topic"]:
        return {}
    commande = ["repo", "list", portfolio["proprietaire"], "--topic", portfolio["topic"],
                "--json", "name,repositoryTopics,latestRelease", "--limit", "200"]
    try:
        depots = json.loads((executer or executer_gh)(commande))
    except (OSError, ValueError, subprocess.SubprocessError) as erreur:
        print(f"Avertissement : états du portfolio indisponibles ({type(erreur).__name__}), le bilan continue.", file=sys.stderr)
        return {}
    etats: dict[str, dict] = {}
    for depot in depots if isinstance(depots, list) else []:
        topics = [t.get("name") or (t.get("topic") or {}).get("name") for t in depot.get("repositoryTopics") or []]
        statut = next((portfolio["statuses"][t] for t in topics if t in portfolio["statuses"]), None)
        version = (depot.get("latestRelease") or {}).get("tagName")
        etats[str(depot.get("name", "")).lower()] = {"statut": statut, "version": version}
    return etats


# --- Classement ---
def groupe_skill(skill: str | None) -> str | None:
    for motif, groupe in SKILLS:
        if re.search(motif, skill or "", re.I):
            return groupe
    return None


def groupe_desc(texte: str) -> str | None:
    for motif, groupe in DESC:
        if re.search(motif, texte, re.I):
            return groupe
    return None


def chronologie(skills: list[tuple[str, str]]) -> list[tuple[str, str | None]]:
    """Skills triés par instant, sans les commandes ignorées ; ``/clear`` remet le skill actif à zéro."""
    return sorted(
        ((ts, None if nom == COMMANDE_EFFACER else nom) for ts, nom in skills if nom not in IGNORES),
        key=lambda e: e[0],
    )


def skill_a(chrono: list[tuple[str, str | None]], ts: str) -> str | None:
    actif = None
    for instant, nom in chrono:
        if instant > ts:
            break
        actif = nom
    return actif


def activite_outils(outils: list[tuple[str, str | None]]) -> tuple[str, str]:
    """Famille et sous-libellé d'un appel de la session principale d'après ses outils."""
    noms = [n for n, _ in outils]
    commandes = " ".join(d or "" for n, d in outils if n in OUTILS_COMMANDE)
    if LIVRAISON.search(commandes):
        return "livraison", LIBELLE_LIVRAISON
    if any(n in OUTILS_SOUS_AGENT for n in noms):
        return "pilotage", "Lancement et suivi de sous-agents"
    if TESTS.search(commandes):
        return "relecture", "Tests et lint lancés en session"
    if any(n in OUTILS_EDITION for n in noms):
        return "dev", "Édition en session principale"
    if any(n in OUTILS_WEB for n in noms):
        return "recherche", "Recherche web"
    if "Artifact" in noms:
        return "contenus", "Pages et artifacts"
    return ("libre", LIBELLE_LECTURE) if noms else ("libre", LIBELLE_SANS_OUTIL)


def nom_modele(modele: str) -> str:
    """``claude-opus-5-5`` -> ``Opus 5.5`` (identifiant inchangé s'il est inconnu)."""
    r = re.match(r"claude-(opus|sonnet|haiku|fable|mythos)-(\d+)(?:-(\d+))?", modele)
    if not r:
        return modele
    return f"{r.group(1).capitalize()} {r.group(2)}" + (f".{r.group(3)}" if r.group(3) and len(r.group(3)) < 3 else "")


class Classeur:
    """Classe les appels (projet, étape, rôle) avec les infos de fichiers et la config."""

    def __init__(self, infos: dict[str, dict], config: dict, portfolio: dict):
        self.infos = infos
        self.parents = {p.lower() for p in config.get("parents") or []}
        self.alias = {k.lower(): v for k, v in (config.get("alias") or {}).items()}
        self.cles = sorted(portfolio["repos"], key=len, reverse=True)
        self.session: dict[str, list] = defaultdict(list)
        self.propre: dict[str, list] = {}
        for fichier, info in infos.items():
            chrono = chronologie(info["skills"])
            if info["type"] is None:
                self.session[Path(fichier).stem].extend(chrono)
            self.propre[fichier] = chrono
        for chrono in self.session.values():
            chrono.sort(key=lambda e: e[0])

    def projet(self, cwd: str | None) -> str:
        segments = [s for s in (cwd or "").replace("\\", "/").split("/") if s]
        rang = next((i for i, s in enumerate(segments) if s.lower() in self.parents), None)
        if rang is None or rang + 1 >= len(segments):
            return RACINE
        nom = segments[rang + 1]
        bas = nom.lower()
        for prefixe, cle in self.alias.items():
            if bas.startswith(prefixe):
                return cle
        for cle in self.cles:
            if bas == cle.lower() or bas.startswith((cle.lower() + "-", cle.lower() + "_")):
                return cle
        return nom

    def etape_session(self, a: dict) -> tuple[str, str]:
        outils = a.get("outils") or []
        commandes = " ".join(d or "" for n, d in outils if n in OUTILS_COMMANDE)
        if LIVRAISON.search(commandes):
            return "livraison", LIBELLE_LIVRAISON
        skill = skill_a(self.session.get(a["session"], []), a["ts"])
        if skill and groupe_skill(skill):
            return groupe_skill(skill), skill  # type: ignore[return-value]
        return activite_outils(outils)

    def etape_agent(self, a: dict) -> tuple[str, str]:
        type_agent = a["agent_type"]
        if type_agent in AGENTS:
            return AGENTS[type_agent]
        info = self.infos[a["fichier"]]
        propre = skill_a(self.propre[a["fichier"]], a["ts"])
        if propre and groupe_skill(propre):
            return groupe_skill(propre), f"{propre} (dans un sous-agent)"  # type: ignore[return-value]
        for texte in (info.get("desc") or "", info.get("prompt") or ""):
            groupe = groupe_desc(texte)
            if groupe:
                libelle = f"Sous-agents généralistes ({ETIQ[groupe]})" if type_agent == ROLE_GENERALISTE else f"Sous-agent {type_agent}"
                return groupe, libelle
        parent = skill_a(self.session.get(a["session"], []), info.get("premier_ts") or a["ts"])
        if parent and groupe_skill(parent):
            return groupe_skill(parent), f"Sous-agent {type_agent} lancé par {parent}"  # type: ignore[return-value]
        return "dev", f"Sous-agent {type_agent} (autre)"

    def etape(self, a: dict) -> tuple[str, str]:
        return self.etape_session(a) if a["agent_type"] is None else self.etape_agent(a)

    @staticmethod
    def role(a: dict) -> str:
        type_agent = a["agent_type"]
        if type_agent is None:
            return ORCHESTRATEUR
        return PREFIXE_KIT + type_agent if type_agent in TYPES_DU_KIT else type_agent

    @staticmethod
    def sous_cle(a: dict) -> str:
        return f"{nom_modele(a['modele'])} · effort {a['effort'] or '?'}"


# --- Agrégation fusionnable ---
def stats_vides() -> dict:
    return {**dict.fromkeys(STATS, 0), "cout": dict.fromkeys(POSTES, 0.0)}


def ajouter_stats(dest: dict, source: dict) -> None:
    for champ in STATS:
        dest[champ] += source[champ]
    for poste in POSTES:
        dest["cout"][poste] += source["cout"].get(poste, 0.0)


def stats_appel(a: dict, parts: dict) -> dict:
    s = {champ: a[champ] for champ in STATS if champ != "appels"}
    return {"appels": 1, **s, "cout": {p: parts.get(p, 0.0) for p in POSTES}}


def fusionner_brut(brut_a: dict, brut_b: dict) -> dict:
    """Somme deux ``brut`` : cellule par cellule et modèle par modèle, listes de coûts concaténées."""
    cellules: dict = {}
    for brut in (brut_a, brut_b):
        for dim, cles in brut["cellules"].items():
            for cle, sous in cles.items():
                for sous_cle, modeles in sous.items():
                    for modele, stats in modeles.items():
                        dest = cellules.setdefault(dim, {}).setdefault(cle, {}).setdefault(sous_cle, {}).setdefault(modele, stats_vides())
                        ajouter_stats(dest, stats)
    agents: dict = {}
    for brut in (brut_a, brut_b):
        for cle, couts in brut["agents"].items():
            agents.setdefault(cle, []).extend(couts)
    return {"cellules": cellules, "agents": {k: sorted(v) for k, v in agents.items()}}


def agreger(appels: list[dict], infos: dict[str, dict], config: dict, portfolio: dict) -> dict:
    """Table de sommes par cellule (dimension, clé, sous-clé) et par modèle, plus les coûts par agent."""
    classeur = Classeur(infos, config, portfolio)
    motif_experiences = re.compile(config["motif_experiences"])
    cellules: dict = {}
    par_agent: dict[str, dict] = defaultdict(lambda: defaultdict(float))  # clé -> fichier -> coût

    def ajouter(dim: str, cle: str, sous: str, a: dict, s: dict) -> None:
        dest = cellules.setdefault(dim, {}).setdefault(cle, {}).setdefault(sous, {}).setdefault(a["modele"], stats_vides())
        ajouter_stats(dest, s)

    for a in appels:
        etape, sous = classeur.etape(a)
        role = classeur.role(a)
        s = stats_appel(a, mc.couts([a])["parts"])
        cout = sum(s["cout"].values())
        ajouter(DIM_PROJET, classeur.projet(a.get("cwd")), etape, a, s)
        ajouter(DIM_ETAPE, etape, sous, a, s)
        ajouter(DIM_ROLE, role, classeur.sous_cle(a), a, s)
        if a["agent_type"] is None:
            ajouter(DIM_ETAPE_ORCH, etape, "", a, s)
            continue
        par_agent[f"role:{role}"][a["fichier"]] += cout
        par_agent[f"role_etape:{role}|{etape}"][a["fichier"]] += cout
        description = classeur.infos[a["fichier"]].get("desc") or ""
        for nom, correspond in ((DESC_RELECTEURS, MOTIF_RELECTEURS.search(description)),
                                (DESC_EXPERIENCES, motif_experiences.search(description))):
            if correspond:
                ajouter(DIM_DESC, nom, "", a, s)
                par_agent[f"{DIM_DESC}:{nom}"][a["fichier"]] += cout
    for dim in cellules.values():
        for cle in dim.values():
            for sous in cle.values():
                for stats in sous.values():
                    stats["cout"] = {p: round(v, 6) for p, v in stats["cout"].items()}
    agents = {cle: sorted(round(c, 2) for c in fichiers.values()) for cle, fichiers in par_agent.items()}
    return {"cellules": cellules, "agents": agents}


# --- Blocs d'affichage ---
def sommer_modeles(liste: list[dict]) -> dict:
    """Fusionne plusieurs {modèle: stats} en un seul."""
    total: dict = {}
    for modeles in liste:
        for modele, stats in modeles.items():
            ajouter_stats(total.setdefault(modele, stats_vides()), stats)
    return total


def impact_modeles(modeles: dict, mix: str, methode: str) -> dict[str, dict[str, float]]:
    """Impact d'un bloc depuis ses sommes, même calcul que ``mc.impact_appels`` (``mc.impact`` est linéaire)."""
    total = {g: {"min": 0.0, "max": 0.0} for g in mc.GRANDEURS}
    for modele, s in modeles.items():
        entree = s["entree"] + s["ecrit_5m"] + s["ecrit_1h"]
        for g, bornes in mc.impact(modele, s["sortie"], mix, entree=entree, lu=s["lu"], appels=s["appels"], methode=methode).items():
            for borne in ("min", "max"):
                total[g][borne] += bornes[borne]
    return total


def cout_modeles(modeles: dict) -> float:
    return sum(sum(s["cout"].values()) for s in modeles.values())


def bloc(modeles: dict, mix: str, methode: str) -> dict:
    """Chiffres d'affichage d'un ensemble d'appels : volumes, coût par poste, carbone, énergie, eau."""
    total = stats_vides()
    for s in modeles.values():
        ajouter_stats(total, s)
    imp = impact_modeles(modeles, mix, methode)
    return {
        "appels": total["appels"],
        "inTot": total["entree"] + total["ecrit_5m"] + total["ecrit_1h"] + total["lu"],
        "lu": total["lu"],
        "ecrit": total["ecrit_5m"] + total["ecrit_1h"],
        "out": total["sortie"],
        "cout": round(sum(total["cout"].values()), 4),
        "cout_parts": {p: round(v, 4) for p, v in total["cout"].items()},
        "gwp": [round(imp["gwp_gco2e"]["min"], 3), round(imp["gwp_gco2e"]["max"], 3)],
        "nrj": [round(imp["energie_wh"]["min"], 3), round(imp["energie_wh"]["max"], 3)],
        "eau": [round(imp["eau_l"]["min"], 3), round(imp["eau_l"]["max"], 3)],
    }


def modeles_de(cellules: dict, dim: str, cle: str) -> dict:
    """Tous les modèles d'une clé, sous-clés confondues."""
    return sommer_modeles(list(cellules.get(dim, {}).get(cle, {}).values()))


def mediane_centimes(couts: list[float]) -> float:
    return round(statistics.median(couts), 2) if couts else 0.0


def blocs_par_sous_cle(sous: dict, mix: str, methode: str) -> list[dict]:
    lignes = [{**bloc(modeles, mix, methode), "label": cle} for cle, modeles in sous.items()]
    return sorted(lignes, key=lambda b: (-b["cout"], b["label"]))


def blocs_projets(cellules: dict, portfolio: dict, etats: dict, mix: str, methode: str) -> list[dict]:
    projets = []
    for cle, par_etape in cellules.get(DIM_PROJET, {}).items():
        b = bloc(sommer_modeles(list(par_etape.values())), mix, methode)
        dans = cle in portfolio["repos"]
        etat = etats.get(cle.lower(), {}) if dans else {}
        url = f"https://github.com/{portfolio['proprietaire']}/{cle}" if dans and portfolio["proprietaire"] else None
        b.update(
            cle=cle, nom=portfolio["repos"][cle] if dans else (NOM_RACINE if cle == RACINE else cle), portfolio=dans, url=url,
            statut=etat.get("statut"), version=etat.get("version"),
            par_groupe={g: round(cout_modeles(m), 4) for g, m in par_etape.items()},
        )
        projets.append(b)
    return sorted(projets, key=lambda b: (-b["cout"], b["nom"]))


def blocs_etapes(cellules: dict, mix: str, methode: str) -> list[dict]:
    etapes = []
    for gid, libelle in GROUPES:
        sous = cellules.get(DIM_ETAPE, {}).get(gid)
        if not sous:
            continue
        orch = modeles_de(cellules, DIM_ETAPE_ORCH, gid)
        etapes.append({
            **bloc(sommer_modeles(list(sous.values())), mix, methode), "id": gid, "label": libelle,
            "sous": blocs_par_sous_cle(sous, mix, methode), "cout_orch": round(cout_modeles(orch), 4),
        })
    return etapes


def blocs_roles(cellules: dict, agents: dict, mix: str, methode: str) -> tuple[list[dict], dict, dict]:
    """Rôles, bloc de l'orchestrateur et bloc de l'ensemble des sous-agents (avec leurs ``par_me``)."""
    roles = []
    for role, sous in cellules.get(DIM_ROLE, {}).items():
        b = {**bloc(sommer_modeles(list(sous.values())), mix, methode), "label": role, "orch": role == ORCHESTRATEUR}
        if not b["orch"]:
            liste = agents.get(f"role:{role}", [])
            b["n_agents"], b["cout_median"] = len(liste), mediane_centimes(liste)
        b["par_me"] = blocs_par_sous_cle(sous, mix, methode)
        roles.append(b)
    roles.sort(key=lambda b: (not b["orch"], -b["cout"], b["label"]))

    def ensemble(orch: bool) -> dict:
        choisis = [cellules[DIM_ROLE][r["label"]] for r in roles if r["orch"] == orch]
        fusion: dict = defaultdict(list)
        for sous in choisis:
            for cle, modeles in sous.items():
                fusion[cle].append(modeles)
        par_cle = {cle: sommer_modeles(liste) for cle, liste in fusion.items()}
        return {**bloc(sommer_modeles(list(par_cle.values())), mix, methode), "par_me": blocs_par_sous_cle(par_cle, mix, methode)}

    return roles, ensemble(True), ensemble(False)


# --- Recommandations ---
def version_modele(identifiant: str) -> tuple[str, tuple[int, int]] | None:
    r = re.match(r"claude-(opus|sonnet|haiku|fable|mythos)-(\d+)(?:-(\d{1,2}))?(?!\d)", identifiant)
    return (r.group(1), (int(r.group(2)), int(r.group(3) or 0))) if r else None


def plus_recent(modele: str) -> str | None:
    """Version la plus récente de la même famille connue de tarifs.json si sa lecture du cache est moins chère."""
    actuel = version_modele(modele)
    if actuel is None:
        return None
    candidats = [(v[1], cle) for cle in mc.PRIX_MODELES if (v := version_modele(cle)) and v[0] == actuel[0] and v[1] > actuel[1]]
    if not candidats:
        return None
    recent = max(candidats)[1]
    return recent if mc.prix(recent)["lecture"] < mc.prix(modele)["lecture"] else None


def reco(ident: str, titre: str, mesure: str, pratique: str, gain: list[float] | None) -> dict:
    return {"id": ident, "titre": titre, "mesure": mesure, "pratique": pratique,
            "gain": [round(gain[0], 2), round(gain[1], 2)] if gain else None}


def reco_implementation(agents: dict) -> dict | None:
    generalistes, dev_story = agents.get(f"role_etape:{ROLE_GENERALISTE}|dev", []), agents.get(f"role:{ROLE_DEV_STORY}", [])
    if len(generalistes) < IMPL_MIN_GENERALISTES or len(dev_story) < IMPL_MIN_GENERALISTES:
        return None
    mg, md = mediane_centimes(generalistes), mediane_centimes(dev_story)
    if mg <= IMPL_FACTEUR_MEDIANE * md:
        return None
    gain = (mg - md) * len(generalistes)
    return reco(
        "implementation-generaliste", "Implémenter avec dev-story, pas avec un sous-agent généraliste",
        f"{fr(len(generalistes))} sous-agents généralistes ont implémenté du code pour {usd(sum(generalistes))}. "
        f"Coût médian : <b>{usd(mg)} par agent</b>, contre <b>{usd(md)}</b> pour les {fr(len(dev_story))} agents <code>dev-story</code>.",
        "Dans l'orchestrateur et dans les skills de run, lancer <code>agent-cost-kit:dev-story</code> (Sonnet, medium). "
        "Garder Opus pour les stories transverses, en le passant explicitement.",
        [gain * (1 - IMPL_MARGE), gain * (1 + IMPL_MARGE)],
    )


def part_opus(modeles: dict, champ: str = "cout") -> tuple[float, float]:
    """(valeur sur Opus, valeur totale) du coût ou du nombre d'appels."""
    def valeur(s: dict) -> float:
        return sum(s["cout"].values()) if champ == "cout" else s["appels"]
    return (sum(valeur(s) for m, s in modeles.items() if mc.famille(m) == "opus"), sum(valeur(s) for s in modeles.values()))


def reco_relecture(cellules: dict, total: float) -> dict | None:
    multiples = cout_modeles(modeles_de(cellules, DIM_DESC, DESC_RELECTEURS))
    reviewer = modeles_de(cellules, DIM_ROLE, ROLE_REVIEWER)
    cout_opus, cout_reviewer = part_opus(reviewer)
    appels_opus, appels_reviewer = part_opus(reviewer, "appels")
    sur_opus = appels_reviewer > 0 and appels_opus / appels_reviewer > REVIEWER_OPUS_PART
    if not (total and multiples / total >= RELECTEURS_PART_MIN or sur_opus):
        return None
    base = REVIEWER_GAIN_OPUS * cout_opus
    return reco(
        "relecture", "Relire avec second-avis puis un seul reviewer, Opus seulement pour le risque",
        f"Les relecteurs multiples de <code>bmad-code-review</code> ont coûté {usd(multiples)} ({pct(multiples, total)} du total). "
        f"Le <code>reviewer</code> a coûté {usd(cout_reviewer)}, dont {pct(cout_opus, cout_reviewer)} sur Opus.",
        "Enchaîner <code>second-avis</code> (Haiku) puis <code>reviewer</code> en une passe. Passer le reviewer en Sonnet "
        "pour une story courante (−25 % mesuré) et garder Opus pour l'argent, la sécurité et les données.",
        [base + RELECTEURS_GAIN_MIN * multiples, base + multiples],
    )


def contexte_moyen(b: dict) -> float:
    return b["inTot"] / max(b["appels"], 1)


def reco_contexte(cellules: dict, orch: dict, sous: dict, total: float) -> dict | None:
    if not total or not sous["appels"] or contexte_moyen(orch) < CONTEXTE_FACTEUR * contexte_moyen(sous):
        return None
    if orch["cout"] < CONTEXTE_ORCH_PART_MIN * total:
        return None
    lecture = cout_modeles(cellules.get(DIM_ETAPE, {}).get("libre", {}).get(LIBELLE_LECTURE, {}))

    def fr_ctx(b: dict) -> str:
        return fr(round(contexte_moyen(b)))

    return reco(
        "contexte-orchestrateur", "Raccourcir le contexte de l'orchestrateur",
        f"L'orchestrateur relit en moyenne <b>{fr_ctx(orch)} tokens par appel</b>, contre {fr_ctx(sous)} pour un sous-agent. "
        f"Il pèse {pct(orch['cout'], total)} du coût. Les lectures de code et les commandes de la session principale, "
        f"hors de toute étape, coûtent à elles seules {usd(lecture)}.",
        "Faire <code>/clear</code> (après <code>/rename</code>) entre deux tâches sans lien. Confier lectures, recherches et "
        "résumés de logs à <code>lookup</code> (Haiku). Garder l'état d'un run dans un fichier relisible plutôt que dans l'historique.",
        [CONTEXTE_GAIN[0] * lecture, CONTEXTE_GAIN[1] * lecture],
    )


def reco_modele_ancien(modeles_total: dict, total: float) -> dict | None:
    lignes, gain = [], 0.0
    for modele, s in sorted(modeles_total.items()):
        recent = plus_recent(modele)
        if not recent or not total or sum(s["cout"].values()) / total < MODELE_PART_MIN:
            continue
        ancien, nouveau = mc.prix(modele)["lecture"], mc.prix(recent)["lecture"]
        gain += s["cout"]["lecture"] * (1 - nouveau / ancien)
        lignes.append(f"{nom_modele(modele)} ({usd(s['cout']['lecture'])} de lecture du cache à {fr(ancien, 2)} $ le million, "
                      f"contre {fr(nouveau, 2)} $ pour {nom_modele(recent)})")
    if not lignes:
        return None
    return reco(
        "modele-ancien", "Abandonner les versions anciennes d'un modèle pour la version récente",
        "Lecture du cache plus chère que sur la version récente de la même famille : " + " ; ".join(lignes) + ".",
        "Mettre à jour agent-cost-kit sur chaque PC et vérifier le <code>model:</code> des agents du projet.",
        [gain * (1 - MODELE_MARGE), gain * (1 + MODELE_MARGE)],
    )


def reco_pilotage(etapes: dict, total: float) -> dict | None:
    pilotage = etapes.get("pilotage")
    if not pilotage or not total or pilotage["cout"] < PILOTAGE_PART_MIN * total:
        return None
    if pilotage["cout_orch"] < PILOTAGE_SESSION_MIN * pilotage["cout"]:
        return None
    return reco(
        "pilotage-session", "Faire le point sur un run dans une session neuve",
        f"Le pilotage coûte {usd(pilotage['cout'])}, dont {pct(pilotage['cout_orch'], pilotage['cout'])} en session principale. "
        "Faire le point dans une longue session Opus revient à relire tout l'historique à chaque étape.",
        "Lancer <code>/agent-cost-kit:avancement-run</code> après un <code>/clear</code> : il repart du fichier d'état du run "
        "(<code>run-autonome.md</code>) au lieu de tout l'historique.",
        [PILOTAGE_GAIN[0] * pilotage["cout"], PILOTAGE_GAIN[1] * pilotage["cout"]],
    )


def reco_effort(orch: dict) -> dict | None:
    par_effort: dict[str, list[float]] = {}
    for ligne in orch["par_me"]:
        r = re.match(r"^Opus .* · effort (\w+)$", ligne["label"])
        if r:
            cumul = par_effort.setdefault(r.group(1), [0, 0.0])
            cumul[0] += ligne["appels"]
            cumul[1] += ligne["cout"]
    moyen, haut = par_effort.get("medium"), par_effort.get("high")
    if not moyen or not haut or min(moyen[0], haut[0]) < EFFORT_APPELS_MIN:
        return None
    cm, ch = moyen[1] / moyen[0], haut[1] / haut[0]
    if abs(ch - cm) / cm >= EFFORT_ECART:
        return None
    return reco(
        "effort-neutre", "Monter l'effort ne coûte presque rien, le contexte si",
        f"Sur l'orchestrateur Opus, un appel coûte en moyenne {fr(cm, 3)} $ en effort medium et {fr(ch, 3)} $ en high. "
        "Ce coût suit le contexte relu, pas la réflexion.",
        "Garder high pour l'architecture et les stories transverses, où il évite des reprises. Chercher les économies "
        "dans le nombre de tours et la taille du contexte.",
        None,
    )


def reco_amont(etapes: dict, total: float) -> dict | None:
    def somme(ids: tuple[str, ...]) -> float:
        return sum(etapes[i]["cout"] for i in ids if i in etapes)
    amont, coeur = somme(("besoin", "specs", "archi")), somme(("dev", "relecture"))
    if not total or amont >= AMONT_PART_MAX * total or coeur <= COEUR_PART_MIN * total:
        return None
    return reco(
        "amont", "Continuer à soigner l'amont, il coûte peu",
        f"Cadrage, spécifications et architecture ne pèsent que {pct(amont, total)} du coût ({usd(amont)}). "
        f"Le développement et la relecture en pèsent {pct(coeur, total)}.",
        "Garder Opus et un plan validé avant le code : une spec plus précise réduit les tours de développement et de revue, "
        "là où se trouve la dépense.",
        None,
    )


def reco_mesure(cellules: dict, agents: dict, total: float) -> dict | None:
    cout = cout_modeles(modeles_de(cellules, DIM_DESC, DESC_EXPERIENCES))
    if cout <= 0:
        return None
    return reco(
        "mesure", "Mesurer reste rentable",
        f"Les campagnes de mesure (bancs, essais de modèles) ont coûté {usd(cout)} sur "
        f"{fr(len(agents.get(f'{DIM_DESC}:{DESC_EXPERIENCES}', [])))} agents, {pct(cout, total)} du total. "
        "Elles ont fondé le routage qui produit les gains ci-dessus.",
        "Refaire ce bilan chaque mois, et <code>/agent-cost-kit:mesurer-couts</code> après tout changement de méthode, "
        "avant de le généraliser.",
        None,
    )


def recommandations(brut: dict, blocs: dict) -> list[dict]:
    """Recommandations dont la condition est remplie, triées par gain maximal décroissant, neutres à la fin."""
    cellules, agents, total = brut["cellules"], brut["agents"], blocs["total"]["cout"]
    etapes = {e["id"]: e for e in blocs["etapes"]}
    modeles_total = sommer_modeles([sommer_modeles(list(sous.values())) for sous in cellules.get(DIM_ROLE, {}).values()])
    trouvees = [
        reco_implementation(agents), reco_relecture(cellules, total),
        reco_contexte(cellules, blocs["orch"], blocs["sous"], total), reco_modele_ancien(modeles_total, total),
        reco_pilotage(etapes, total), reco_effort(blocs["orch"]), reco_amont(etapes, total), reco_mesure(cellules, agents, total),
    ]
    retenues = [r for r in trouvees if r]
    return sorted(retenues, key=lambda r: (r["gain"] is None, -(r["gain"][1] if r["gain"] else 0)))


# --- Assemblage ---
def assembler(brut: dict, config: dict, mix: str, methode: str, executer=None) -> dict:
    """Champ ``detail`` : ``brut`` plus les blocs d'affichage et les recommandations recalculés depuis lui."""
    portfolio = lire_portfolio(config)
    cellules = brut["cellules"]
    roles, orch, sous = blocs_roles(cellules, brut["agents"], mix, methode)
    detail = {
        "brut": brut,
        "total": bloc(sommer_modeles([modeles_de(cellules, DIM_ROLE, r["label"]) for r in roles]), mix, methode),
        "portfolio": bool(portfolio["repos"]),
        "portfolio_url": portfolio["url"],
        "projets": blocs_projets(cellules, portfolio, lire_etats(portfolio, executer), mix, methode),
        "etapes": blocs_etapes(cellules, mix, methode),
        "roles": roles, "orch": orch, "sous": sous,
    }
    detail["recos"] = recommandations(brut, detail)
    return detail


def construire(appels: list[dict], infos: dict[str, dict], config: dict, mix: str, methode: str, executer=None) -> dict:
    """Détail complet des appels retenus (déjà dédoublonnés et filtrés sur la période)."""
    brut = agreger(appels, infos, config, lire_portfolio(config))
    return assembler(brut, config, mix, methode, executer)


def fusionner(details: list[dict], config: dict, mix: str, methode: str, executer=None) -> dict:
    """Fusionne les ``detail`` de plusieurs bilans et recalcule blocs et recommandations avec la config courante."""
    brut = details[0]["brut"]
    for autre in details[1:]:
        brut = fusionner_brut(brut, autre["brut"])
    return assembler(brut, config, mix, methode, executer)
