"""Traduction de la page du bilan des tokens (``bilan_tokens.py``) en anglais et en allemand.

Le gabarit (``skills/bilan-tokens/gabarit.html``) reste écrit en français, seule source. Chaque langue a un
catalogue ``skills/bilan-tokens/i18n/<langue>.json`` : une liste de paires [texte français exact, traduction],
appliquées de la plus longue à la plus courte. Une paire qui ne trouve plus son texte dans le gabarit fait échouer
la génération (``CatalogueObsolete``) : modifier une phrase du gabarit oblige à mettre le catalogue à jour.

Les données injectées (libellés d'étapes, de rôles, statuts, recommandations) sont traduites ici, sur une copie :
le JSON écrit sur disque reste en français, donc les bilans de plusieurs PC se fusionnent comme avant.

Stdlib seulement.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

LANGUES = ("fr", "en", "de")
LANGUE_SOURCE = "fr"
DOSSIER_CATALOGUES = Path(__file__).resolve().parent.parent / "skills" / "bilan-tokens" / "i18n"
MARQUE_LANGUES = "<!--LANGUES-->"
HTML_SOURCE = '<html lang="fr">'

NOMS = {"fr": "Français", "en": "English", "de": "Deutsch"}
GROUPE_LANGUES = {"fr": "Langue", "en": "Language", "de": "Sprache"}
# Drapeaux en SVG : Windows n'affiche pas les drapeaux emoji (il montre les lettres FR, GB, DE).
DRAPEAUX = {
    "fr": '<svg class="flag" viewBox="0 0 3 2" aria-hidden="true"><path fill="#002654" d="M0 0h1v2H0z"/>'
          '<path fill="#fff" d="M1 0h1v2H1z"/><path fill="#CE1126" d="M2 0h1v2H2z"/></svg>',
    "en": '<svg class="flag" viewBox="0 0 60 30" aria-hidden="true"><clipPath id="drapeau-gb">'
          '<path d="M30 15h30v15zv15H0zH0V0zV0h30z"/></clipPath><path fill="#012169" d="M0 0v30h60V0z"/>'
          '<path stroke="#fff" stroke-width="6" d="M0 0l60 30m0-30L0 30"/>'
          '<path stroke="#C8102E" stroke-width="4" d="M0 0l60 30m0-30L0 30" clip-path="url(#drapeau-gb)"/>'
          '<path stroke="#fff" stroke-width="10" d="M30 0v30M0 15h60"/>'
          '<path stroke="#C8102E" stroke-width="6" d="M30 0v30M0 15h60"/></svg>',
    "de": '<svg class="flag" viewBox="0 0 5 3" aria-hidden="true"><path d="M0 0h5v3H0z"/>'
          '<path fill="#D00" d="M0 1h5v2H0z"/><path fill="#FFCE00" d="M0 2h5v1H0z"/></svg>',
}


class CatalogueObsolete(ValueError):
    """Des textes du catalogue n'apparaissent plus dans le gabarit."""


# --- Nombres ---
def nombre(v: float, decimales: int = 0, langue: str = LANGUE_SOURCE) -> str:
    """Nombre au format de la langue : 1 234,5 (fr, espace fine insécable), 1,234.5 (en), 1.234,5 (de)."""
    brut = f"{v:,.{decimales}f}"
    if langue == "en":
        return brut
    separateur = " " if langue == "fr" else "."
    return brut.replace(",", "\x00").replace(".", ",").replace("\x00", separateur)


def dollars(v: float, langue: str = LANGUE_SOURCE) -> str:
    montant = nombre(v, 0 if v >= 100 else 2, langue)
    return f"${montant}" if langue == "en" else f"{montant} $"


def part(v: float, total: float, langue: str = LANGUE_SOURCE) -> str:
    if not total:
        return ""
    p = v / total
    valeur = nombre(100 * p, 1 if p < 0.01 else 0, langue)
    return f"{valeur}%" if langue == "en" else f"{valeur} %"


# --- Libellés des données ---
LIBELLES = {
    "en": {
        "🧭 Cadrage du besoin": "🧭 Needs framing", "📝 Spécifications": "📝 Specifications",
        "🏛️ Architecture et plan": "🏛️ Architecture and plan", "🛠️ Développement": "🛠️ Development",
        "🔍 Relecture et tests": "🔍 Review and tests", "🚀 Intégration et livraison": "🚀 Integration and delivery",
        "🎛️ Pilotage et orchestration": "🎛️ Steering and orchestration",
        "🔎 Recherche et documentation": "🔎 Research and documentation",
        "🧰 Outillage et mesure": "🧰 Tooling and measurement",
        "🎨 Contenus et communication": "🎨 Content and communication",
        "💬 Échanges sans étape identifiée": "💬 Exchanges with no identified step",
        "Git, PR, CI et release": "Git, PR, CI and release",
        "Lecture du code et commandes": "Code reading and commands",
        "Réponse ou réflexion sans outil": "Answer or thinking without tools",
        "Lancement et suivi de sous-agents": "Launching and monitoring sub-agents",
        "Tests et lint lancés en session": "Tests and lint run in session",
        "Édition en session principale": "Editing in the main session",
        "Recherche web": "Web search", "Pages et artifacts": "Pages and artifacts",
        "Plan (sous-agent)": "Plan (sub-agent)",
        "Racine des dépôts (sessions transverses)": "Repository root (cross-project sessions)",
        "Orchestrateur (session principale)": "Orchestrator (main session)",
        "Sous-agents généralistes (revue, audit, tests)": "General-purpose sub-agents (review, audit, tests)",
        "Sous-agents généralistes (recherche)": "General-purpose sub-agents (research)",
        "Sous-agents généralistes (plan, conception)": "General-purpose sub-agents (plan, design)",
        "Sous-agents généralistes (implémentation)": "General-purpose sub-agents (implementation)",
        "Sous-agents généralistes (spécification)": "General-purpose sub-agents (specification)",
        "🟢 Déployé": "🟢 Deployed", "🟠 En refonte": "🟠 Being reworked", "🔵 En test": "🔵 In testing",
        "🟣 Bancs d'essai": "🟣 Benchmarks", "⚪ En spécification": "⚪ In specification",
    },
    "de": {
        "🧭 Cadrage du besoin": "🧭 Bedarfsklärung", "📝 Spécifications": "📝 Spezifikationen",
        "🏛️ Architecture et plan": "🏛️ Architektur und Plan", "🛠️ Développement": "🛠️ Entwicklung",
        "🔍 Relecture et tests": "🔍 Review und Tests", "🚀 Intégration et livraison": "🚀 Integration und Auslieferung",
        "🎛️ Pilotage et orchestration": "🎛️ Steuerung und Orchestrierung",
        "🔎 Recherche et documentation": "🔎 Recherche und Dokumentation",
        "🧰 Outillage et mesure": "🧰 Werkzeuge und Messung",
        "🎨 Contenus et communication": "🎨 Inhalte und Kommunikation",
        "💬 Échanges sans étape identifiée": "💬 Austausch ohne erkannte Phase",
        "Git, PR, CI et release": "Git, PR, CI und Release",
        "Lecture du code et commandes": "Code lesen und Befehle",
        "Réponse ou réflexion sans outil": "Antwort oder Nachdenken ohne Tool",
        "Lancement et suivi de sous-agents": "Starten und Verfolgen von Sub-Agents",
        "Tests et lint lancés en session": "In der Sitzung gestartete Tests und Lint",
        "Édition en session principale": "Bearbeitung in der Hauptsitzung",
        "Recherche web": "Websuche", "Pages et artifacts": "Seiten und Artifacts",
        "Plan (sous-agent)": "Plan (Sub-Agent)",
        "Racine des dépôts (sessions transverses)": "Repository-Wurzel (übergreifende Sitzungen)",
        "Orchestrateur (session principale)": "Orchestrator (Hauptsitzung)",
        "Sous-agents généralistes (revue, audit, tests)": "General-Purpose-Sub-Agents (Review, Audit, Tests)",
        "Sous-agents généralistes (recherche)": "General-Purpose-Sub-Agents (Recherche)",
        "Sous-agents généralistes (plan, conception)": "General-Purpose-Sub-Agents (Plan, Entwurf)",
        "Sous-agents généralistes (implémentation)": "General-Purpose-Sub-Agents (Implementierung)",
        "Sous-agents généralistes (spécification)": "General-Purpose-Sub-Agents (Spezifikation)",
        "🟢 Déployé": "🟢 Ausgerollt", "🟠 En refonte": "🟠 In Überarbeitung", "🔵 En test": "🔵 Im Test",
        "🟣 Bancs d'essai": "🟣 Benchmarks", "⚪ En spécification": "⚪ In Spezifikation",
    },
}
# Libellés construits avec un nom de skill ou de type d'agent (le premier motif qui correspond l'emporte).
MOTIFS = {
    "en": [(r"^(.+) \(dans un sous-agent\)$", r"\1 (in a sub-agent)"),
           (r"^Sous-agent (\S+) lancé par (.+)$", r"\1 sub-agent launched by \2"),
           (r"^Sous-agent (\S+) \(autre\)$", r"\1 sub-agent (other)"),
           (r"^Sous-agent (\S+)$", r"\1 sub-agent")],
    "de": [(r"^(.+) \(dans un sous-agent\)$", r"\1 (in einem Sub-Agent)"),
           (r"^Sous-agent (\S+) lancé par (.+)$", r"Sub-Agent \1, gestartet von \2"),
           (r"^Sous-agent (\S+) \(autre\)$", r"Sub-Agent \1 (sonstige)"),
           (r"^Sous-agent (\S+)$", r"Sub-Agent \1")],
}


def libelle(texte: str | None, langue: str) -> str | None:
    """Libellé traduit ; inchangé s'il est inconnu (nom de skill, de modèle ou de dépôt) ou en français."""
    if not texte or langue == LANGUE_SOURCE:
        return texte
    connu = LIBELLES[langue].get(texte)
    if connu:
        return connu
    for motif, remplacement in MOTIFS[langue]:
        if re.match(motif, texte):
            return re.sub(motif, remplacement, texte)
    return texte


def traduire_donnees(bilan: dict, langue: str, recos: list[dict] | None = None) -> dict:
    """Copie du bilan aux libellés traduits (clés, identifiants et chiffres inchangés) ; ``recos`` remplace celles du détail."""
    if langue == LANGUE_SOURCE:
        return bilan
    copie = copy.deepcopy(bilan)
    detail = copie.get("detail")
    if not detail:
        return copie
    for etape in detail.get("etapes", []):
        etape["label"] = libelle(etape["label"], langue)
        for sous in etape.get("sous", []):
            sous["label"] = libelle(sous["label"], langue)
    for role in detail.get("roles", []):
        role["label"] = libelle(role["label"], langue)
        for ligne in role.get("par_me", []):
            ligne["label"] = libelle(ligne["label"], langue)
    for ensemble in (detail.get("orch"), detail.get("sous")):
        for ligne in (ensemble or {}).get("par_me", []):
            ligne["label"] = libelle(ligne["label"], langue)
    for projet in detail.get("projets", []):
        if not projet.get("portfolio"):
            projet["nom"] = libelle(projet["nom"], langue)
        projet["statut"] = libelle(projet.get("statut"), langue)
    if recos is not None:
        detail["recos"] = recos
    return copie


# --- Recommandations ---
# Gabarits par langue ; les valeurs arrivent déjà mises en forme (nombres, montants, parts).
RECOS: dict[str, dict[str, dict[str, str]]] = {
    "implementation-generaliste": {
        "fr": {"titre": "Implémenter avec dev-story, pas avec un sous-agent généraliste",
               "mesure": "{n_gen} sous-agents généralistes ont implémenté du code pour {cout_gen}. "
                         "Coût médian : <b>{med_gen} par agent</b>, contre <b>{med_dev}</b> pour les {n_dev} agents <code>dev-story</code>.",
               "pratique": "Dans l'orchestrateur et dans les skills de run, lancer <code>agent-cost-kit:dev-story</code> (Sonnet, medium). "
                           "Garder Opus pour les stories transverses, en le passant explicitement."},
        "en": {"titre": "Implement with dev-story, not with a general-purpose sub-agent",
               "mesure": "{n_gen} general-purpose sub-agents implemented code for {cout_gen}. "
                         "Median cost: <b>{med_gen} per agent</b>, against <b>{med_dev}</b> for the {n_dev} <code>dev-story</code> agents.",
               "pratique": "In the orchestrator and in run skills, launch <code>agent-cost-kit:dev-story</code> (Sonnet, medium). "
                           "Keep Opus for cross-cutting stories, by passing it explicitly."},
        "de": {"titre": "Mit dev-story implementieren, nicht mit einem General-Purpose-Sub-Agent",
               "mesure": "{n_gen} General-Purpose-Sub-Agents haben Code für {cout_gen} implementiert. "
                         "Mediankosten: <b>{med_gen} pro Agent</b>, gegenüber <b>{med_dev}</b> für die {n_dev} <code>dev-story</code>-Agents.",
               "pratique": "Im Orchestrator und in den Run-Skills <code>agent-cost-kit:dev-story</code> (Sonnet, medium) starten. "
                           "Opus für übergreifende Stories behalten und ausdrücklich angeben."},
    },
    "relecture": {
        "fr": {"titre": "Relire avec second-avis puis un seul reviewer, Opus seulement pour le risque",
               "mesure": "Les relecteurs multiples de <code>bmad-code-review</code> ont coûté {multiples} ({part_multiples} du total). "
                         "Le <code>reviewer</code> a coûté {cout_reviewer}, dont {part_opus} sur Opus.",
               "pratique": "Enchaîner <code>second-avis</code> (Haiku) puis <code>reviewer</code> en une passe. Passer le reviewer en Sonnet "
                           "pour une story courante (−25 % mesuré) et garder Opus pour l'argent, la sécurité et les données."},
        "en": {"titre": "Review with second-avis then a single reviewer, Opus only for risk",
               "mesure": "The multiple reviewers of <code>bmad-code-review</code> cost {multiples} ({part_multiples} of the total). "
                         "The <code>reviewer</code> cost {cout_reviewer}, {part_opus} of it on Opus.",
               "pratique": "Chain <code>second-avis</code> (Haiku) then <code>reviewer</code> in one pass. Switch the reviewer to Sonnet "
                           "for an ordinary story (−25% measured) and keep Opus for money, security and data."},
        "de": {"titre": "Mit second-avis und dann einem einzigen Reviewer prüfen, Opus nur bei Risiko",
               "mesure": "Die mehrfachen Reviewer von <code>bmad-code-review</code> kosteten {multiples} ({part_multiples} der Gesamtkosten). "
                         "Der <code>reviewer</code> kostete {cout_reviewer}, davon {part_opus} auf Opus.",
               "pratique": "<code>second-avis</code> (Haiku) und danach <code>reviewer</code> in einem Durchgang ausführen. Den Reviewer "
                           "bei einer gewöhnlichen Story auf Sonnet stellen (−25 % gemessen), Opus für Geld, Sicherheit und Daten behalten."},
    },
    "contexte-orchestrateur": {
        "fr": {"titre": "Raccourcir le contexte de l'orchestrateur",
               "mesure": "L'orchestrateur relit en moyenne <b>{ctx_orch} tokens par appel</b>, contre {ctx_sous} pour un sous-agent. "
                         "Il pèse {part_orch} du coût. Les lectures de code et les commandes de la session principale, "
                         "hors de toute étape, coûtent à elles seules {lecture}.",
               "pratique": "Faire <code>/clear</code> (après <code>/rename</code>) entre deux tâches sans lien. Confier lectures, recherches et "
                           "résumés de logs à <code>lookup</code> (Haiku). Garder l'état d'un run dans un fichier relisible plutôt que dans l'historique."},
        "en": {"titre": "Shorten the orchestrator's context",
               "mesure": "The orchestrator rereads <b>{ctx_orch} tokens per call</b> on average, against {ctx_sous} for a sub-agent. "
                         "It accounts for {part_orch} of the cost. Code reading and commands in the main session, "
                         "outside any step, cost {lecture} on their own.",
               "pratique": "Run <code>/clear</code> (after <code>/rename</code>) between two unrelated tasks. Hand reading, searches and "
                           "log summaries to <code>lookup</code> (Haiku). Keep a run's state in a rereadable file rather than in the history."},
        "de": {"titre": "Den Kontext des Orchestrators kürzen",
               "mesure": "Der Orchestrator liest im Schnitt <b>{ctx_orch} Token pro Aufruf</b> erneut, gegenüber {ctx_sous} bei einem Sub-Agent. "
                         "Er macht {part_orch} der Kosten aus. Code lesen und Befehle in der Hauptsitzung, "
                         "außerhalb jeder Phase, kosten allein {lecture}.",
               "pratique": "Zwischen zwei unabhängigen Aufgaben <code>/clear</code> ausführen (nach <code>/rename</code>). Lesen, Suchen und "
                           "Log-Zusammenfassungen an <code>lookup</code> (Haiku) übergeben. Den Stand eines Runs in einer lesbaren Datei halten statt im Verlauf."},
    },
    "modele-ancien": {
        "fr": {"titre": "Abandonner les versions anciennes d'un modèle pour la version récente",
               "ligne": "{modele} ({lecture} de lecture du cache à {ancien} $ le million, contre {nouveau} $ pour {recent})",
               "mesure": "Lecture du cache plus chère que sur la version récente de la même famille : {lignes}.",
               "separateur": " ; ",
               "pratique": "Mettre à jour agent-cost-kit sur chaque PC et vérifier le <code>model:</code> des agents du projet."},
        "en": {"titre": "Drop old versions of a model for the recent one",
               "ligne": "{modele} ({lecture} of cache reads at ${ancien} per million, against ${nouveau} for {recent})",
               "mesure": "Cache reads cost more than on the recent version of the same family: {lignes}.",
               "separateur": "; ",
               "pratique": "Update agent-cost-kit on every PC and check the <code>model:</code> of the project's agents."},
        "de": {"titre": "Alte Modellversionen zugunsten der aktuellen aufgeben",
               "ligne": "{modele} ({lecture} Cache-Lesezugriffe zu {ancien} $ pro Million, gegenüber {nouveau} $ bei {recent})",
               "mesure": "Cache-Lesen ist teurer als bei der aktuellen Version derselben Familie: {lignes}.",
               "separateur": "; ",
               "pratique": "agent-cost-kit auf jedem PC aktualisieren und das <code>model:</code> der Agents des Projekts prüfen."},
    },
    "pilotage-session": {
        "fr": {"titre": "Faire le point sur un run dans une session neuve",
               "mesure": "Le pilotage coûte {cout}, dont {part_session} en session principale. "
                         "Faire le point dans une longue session Opus revient à relire tout l'historique à chaque étape.",
               "pratique": "Lancer <code>/agent-cost-kit:avancement-run</code> après un <code>/clear</code> : il repart du fichier d'état du run "
                           "(<code>run-autonome.md</code>) au lieu de tout l'historique."},
        "en": {"titre": "Review a run's progress in a fresh session",
               "mesure": "Steering costs {cout}, {part_session} of it in the main session. "
                         "Checking progress in a long Opus session means rereading the whole history at every step.",
               "pratique": "Run <code>/agent-cost-kit:avancement-run</code> after a <code>/clear</code>: it starts from the run's state file "
                           "(<code>run-autonome.md</code>) instead of the whole history."},
        "de": {"titre": "Den Stand eines Runs in einer neuen Sitzung prüfen",
               "mesure": "Die Steuerung kostet {cout}, davon {part_session} in der Hauptsitzung. "
                         "Den Stand in einer langen Opus-Sitzung zu prüfen heißt, bei jedem Schritt den ganzen Verlauf neu zu lesen.",
               "pratique": "<code>/agent-cost-kit:avancement-run</code> nach einem <code>/clear</code> starten: Es geht von der Statusdatei des Runs "
                           "(<code>run-autonome.md</code>) aus statt vom ganzen Verlauf."},
    },
    "effort-neutre": {
        "fr": {"titre": "Monter l'effort ne coûte presque rien, le contexte si",
               "mesure": "Sur l'orchestrateur Opus, un appel coûte en moyenne {moyen} $ en effort medium et {haut} $ en high. "
                         "Ce coût suit le contexte relu, pas la réflexion.",
               "pratique": "Garder high pour l'architecture et les stories transverses, où il évite des reprises. Chercher les économies "
                           "dans le nombre de tours et la taille du contexte."},
        "en": {"titre": "Raising effort costs almost nothing, context does",
               "mesure": "On the Opus orchestrator, a call costs ${moyen} on average at medium effort and ${haut} at high. "
                         "This cost follows the reread context, not the thinking.",
               "pratique": "Keep high for architecture and cross-cutting stories, where it avoids rework. Look for savings "
                           "in the number of turns and the size of the context."},
        "de": {"titre": "Mehr Effort kostet fast nichts, der Kontext schon",
               "mesure": "Beim Opus-Orchestrator kostet ein Aufruf im Schnitt {moyen} $ bei Effort medium und {haut} $ bei high. "
                         "Diese Kosten folgen dem erneut gelesenen Kontext, nicht dem Nachdenken.",
               "pratique": "high für Architektur und übergreifende Stories behalten, wo es Nacharbeit vermeidet. Einsparungen "
                           "bei der Zahl der Durchgänge und der Kontextgröße suchen."},
    },
    "amont": {
        "fr": {"titre": "Continuer à soigner l'amont, il coûte peu",
               "mesure": "Cadrage, spécifications et architecture ne pèsent que {part_amont} du coût ({amont}). "
                         "Le développement et la relecture en pèsent {part_coeur}.",
               "pratique": "Garder Opus et un plan validé avant le code : une spec plus précise réduit les tours de développement et de revue, "
                           "là où se trouve la dépense."},
        "en": {"titre": "Keep investing upstream, it costs little",
               "mesure": "Framing, specifications and architecture account for only {part_amont} of the cost ({amont}). "
                         "Development and review account for {part_coeur}.",
               "pratique": "Keep Opus and a validated plan before the code: a sharper spec reduces development and review turns, "
                           "which is where the money goes."},
        "de": {"titre": "Weiter in die Vorarbeit investieren, sie kostet wenig",
               "mesure": "Bedarfsklärung, Spezifikationen und Architektur machen nur {part_amont} der Kosten aus ({amont}). "
                         "Entwicklung und Review machen {part_coeur} aus.",
               "pratique": "Opus und einen freigegebenen Plan vor dem Code beibehalten: Eine genauere Spezifikation verringert die "
                           "Entwicklungs- und Review-Durchgänge, wo das Geld ausgegeben wird."},
    },
    "mesure": {
        "fr": {"titre": "Mesurer reste rentable",
               "mesure": "Les campagnes de mesure (bancs, essais de modèles) ont coûté {cout} sur "
                         "{n_agents} agents, {part} du total. "
                         "Elles ont fondé le routage qui produit les gains ci-dessus.",
               "pratique": "Refaire ce bilan chaque mois, et <code>/agent-cost-kit:mesurer-couts</code> après tout changement de méthode, "
                           "avant de le généraliser."},
        "en": {"titre": "Measuring still pays off",
               "mesure": "Measurement campaigns (benchmarks, model trials) cost {cout} across "
                         "{n_agents} agents, {part} of the total. "
                         "They are the basis of the routing that produces the savings above.",
               "pratique": "Redo this report every month, and run <code>/agent-cost-kit:mesurer-couts</code> after any change of method, "
                           "before rolling it out."},
        "de": {"titre": "Messen lohnt sich weiterhin",
               "mesure": "Die Messkampagnen (Benchmarks, Modellversuche) kosteten {cout} über "
                         "{n_agents} Agents, {part} der Gesamtkosten. "
                         "Auf ihnen beruht das Routing, das die obigen Einsparungen bringt.",
               "pratique": "Diesen Bericht jeden Monat neu erstellen und nach jeder Methodenänderung <code>/agent-cost-kit:mesurer-couts</code> "
                           "ausführen, bevor sie verallgemeinert wird."},
    },
}


def texte_reco(ident: str, langue: str) -> dict[str, str]:
    return RECOS[ident][langue]


# --- Page ---
def lire_catalogue(langue: str, dossier: Path = DOSSIER_CATALOGUES) -> dict:
    """Catalogue d'une langue : ``remplacements`` [[source, cible]...] et ``autorises`` (français volontairement gardé)."""
    return json.loads((dossier / f"{langue}.json").read_text(encoding="utf-8"))


def charger_catalogue(langue: str, dossier: Path = DOSSIER_CATALOGUES) -> list[list[str]]:
    paires = lire_catalogue(langue, dossier)["remplacements"]
    sources = [p[0] for p in paires]
    doublons = sorted({s for s in sources if sources.count(s) > 1})
    if doublons:
        raise ValueError(f"Catalogue {langue} : textes source en double : {doublons}")
    return paires


def appliquer_catalogue(html: str, paires: list[list[str]], langue: str) -> str:
    """Remplace chaque texte source par sa traduction, du plus long au plus court ; échoue si un texte manque."""
    manquants = [source for source, _ in paires if source not in html]
    if manquants:
        raise CatalogueObsolete(
            f"Catalogue {langue} : {len(manquants)} texte(s) absent(s) du gabarit, à mettre à jour : "
            + " | ".join(m[:80] for m in manquants[:10])
        )
    for source, cible in sorted(paires, key=lambda p: -len(p[0])):
        html = html.replace(source, cible)
    return html


def selecteur(langue: str, liens: dict[str, str]) -> str:
    """Sélecteur de langue de la barre de navigation, langue courante marquée."""
    items = "".join(
        f'<a href="{liens[l]}" hreflang="{l}" lang="{l}" title="{NOMS[l]}"'
        + (' aria-current="page"' if l == langue else "") + f">{DRAPEAUX[l]}{l.upper()}</a>"
        for l in LANGUES if l in liens
    )
    return f'<div class="lang" role="group" aria-label="{GROUPE_LANGUES[langue]}">{items}</div>'


def traduire_page(gabarit: str, langue: str, liens: dict[str, str] | None = None,
                  paires: list[list[str]] | None = None) -> str:
    """Gabarit dans la langue voulue, avec le sélecteur de langue (aucun si ``liens`` est vide)."""
    html = gabarit if langue == LANGUE_SOURCE else appliquer_catalogue(
        gabarit, paires if paires is not None else charger_catalogue(langue), langue)
    html = html.replace(HTML_SOURCE, f'<html lang="{langue}">', 1)
    return html.replace(MARQUE_LANGUES, selecteur(langue, liens) if liens and len(liens) > 1 else "", 1)


# --- Contrôle du français restant ---
_MOTS_FR = re.compile(r"\b(les|des|du|une|est|pour|avec|sur|dans|par|cette|chaque|aussi|depuis|selon|sans)\b")
_ACCENTS = re.compile(r"[éèêàçùûôîœ«»]")


def texte_visible(html: str) -> str:
    """Texte et chaînes du gabarit hors styles, commentaires et point d'injection des données."""
    html = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(r"/\*.*?\*/", " ", html, flags=re.S)
    return "\n".join(l for l in html.splitlines() if not l.strip().startswith("//"))


def francais_restant(html: str, autorises: tuple[str, ...] = ()) -> list[str]:
    """Lignes qui portent encore des marques du français (accents, mots courants), hors ``autorises``."""
    restes = []
    for ligne in texte_visible(html).splitlines():
        propre = ligne
        for a in autorises:
            propre = propre.replace(a, "")
        if _ACCENTS.search(propre) or _MOTS_FR.search(propre):
            restes.append(ligne.strip()[:160])
    return restes
