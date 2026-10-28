"""Traduction de la page du bilan (``scripts/bilan_i18n.py``) : catalogues, nombres, libellés, recommandations."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import bilan_i18n as i18n  # noqa: E402

GABARIT = Path(__file__).resolve().parent.parent / "skills" / "bilan-tokens" / "gabarit.html"
CIBLES = [l for l in i18n.LANGUES if l != i18n.LANGUE_SOURCE]
LIENS = {"fr": "b.html", "en": "b.en.html", "de": "b.de.html"}


@pytest.mark.parametrize("langue", CIBLES)
def test_catalogue_a_jour_du_gabarit(langue):
    """Chaque texte du catalogue figure encore dans le gabarit (sinon CatalogueObsolete)."""
    i18n.traduire_page(GABARIT.read_text(encoding="utf-8"), langue, LIENS)


@pytest.mark.parametrize("langue", CIBLES)
def test_plus_de_francais_visible(langue):
    """Une phrase ajoutée au gabarit sans entrée au catalogue reste en français : ce test la signale."""
    page = i18n.traduire_page(GABARIT.read_text(encoding="utf-8"), langue, LIENS)
    autorises = tuple(i18n.lire_catalogue(langue).get("autorises", []))
    assert i18n.francais_restant(page, autorises, langue) == []


@pytest.mark.parametrize("langue", i18n.LANGUES)
def test_scripts_de_la_page_valides(langue, tmp_path):
    if not shutil.which("node"):
        pytest.skip("node absent")
    page = i18n.traduire_page(GABARIT.read_text(encoding="utf-8"), langue, LIENS)
    scripts = re.findall(r"<script>(.*?)</script>", page, re.S)
    assert scripts
    for n, code in enumerate(scripts):
        fichier = tmp_path / f"s{n}.js"
        fichier.write_text(code, encoding="utf-8")
        resultat = subprocess.run(["node", "--check", str(fichier)], capture_output=True, text=True)
        assert resultat.returncode == 0, resultat.stderr


@pytest.mark.parametrize("langue,locale", [("fr", "fr-FR"), ("en", "en-US"), ("de", "de-DE")])
def test_langue_selecteur_et_locale(langue, locale):
    page = i18n.traduire_page(GABARIT.read_text(encoding="utf-8"), langue, LIENS)
    assert f'<html lang="{langue}">' in page and i18n.MARQUE_LANGUES not in page
    assert len(re.findall(r'<a [^>]*aria-current="page"', page)) == 1
    assert re.search(rf'href="{re.escape(LIENS[langue])}"[^>]*aria-current="page"', page)
    assert page.count('class="flag"') == 3
    assert f'"{locale}"' in page and (langue == "fr" or '"fr-FR"' not in page)


def test_sans_liens_pas_de_selecteur():
    page = i18n.traduire_page(GABARIT.read_text(encoding="utf-8"), "fr", {"fr": "b.html"})
    assert 'class="lang"' not in page and i18n.MARQUE_LANGUES not in page


def test_catalogue_obsolete_echoue():
    with pytest.raises(i18n.CatalogueObsolete, match="absent"):
        i18n.appliquer_catalogue("<p>Bonjour</p>", [["Bonsoir", "Good evening"]], "en")


def test_remplacement_du_plus_long_au_plus_court():
    html = "<p>Coût API</p><p>Coût</p>"
    assert i18n.appliquer_catalogue(html, [["Coût", "Cost"], ["Coût API", "API cost"]], "en") == "<p>API cost</p><p>Cost</p>"


def test_nombres_par_langue():
    assert i18n.nombre(1234567.891, 2, "fr") == "1 234 567,89"
    assert i18n.nombre(1234567.891, 2, "en") == "1,234,567.89"
    assert i18n.nombre(1234567.891, 2, "de") == "1.234.567,89"
    assert i18n.dollars(1234.6, "fr") == "1 235 $" and i18n.dollars(2.345, "en") == "$2.35"
    assert i18n.dollars(1234.6, "de") == "1.235 $"
    assert i18n.part(1, 200, "fr") == "0,5 %" and i18n.part(1, 4, "en") == "25%" and i18n.part(1, 0, "de") == ""


@pytest.mark.parametrize("source,langue,attendu", [
    ("🛠️ Développement", "en", "🛠️ Development"),
    ("bmad-ux (dans un sous-agent)", "de", "bmad-ux (in einem Sub-Agent)"),
    ("Sous-agent general-purpose lancé par aidd-pm:05-spike", "en", "general-purpose sub-agent launched by aidd-pm:05-spike"),
    ("Sous-agent general-purpose (autre)", "de", "Sub-Agent general-purpose (sonstige)"),
    ("Opus 5.5 · effort high", "en", "Opus 5.5 · effort high"),
    ("bmad-spec", "de", "bmad-spec"),
    ("🛠️ Développement", "fr", "🛠️ Développement"),
])
def test_libelles(source, langue, attendu):
    assert i18n.libelle(source, langue) == attendu


def test_traduire_donnees_garde_cles_et_source():
    bilan = {"detail": {
        "etapes": [{"id": "dev", "label": "🛠️ Développement", "sous": [{"label": "Recherche web", "cout": 1.0}]}],
        "roles": [{"label": "Orchestrateur (session principale)", "orch": True, "par_me": [{"label": "Opus 5.5 · effort high"}]}],
        "orch": {"par_me": []}, "sous": {"par_me": []},
        "projets": [{"cle": "_racine", "nom": "Racine des dépôts (sessions transverses)", "portfolio": False, "statut": None},
                    {"cle": "x", "nom": "Recherche web", "portfolio": True, "statut": "🔵 En test"}],
        "recos": [{"id": "amont"}],
    }}
    en = i18n.traduire_donnees(bilan, "en", recos=[{"id": "amont", "titre": "T"}])
    d = en["detail"]
    assert d["etapes"][0]["id"] == "dev" and d["etapes"][0]["label"] == "🛠️ Development"
    assert d["etapes"][0]["sous"][0]["label"] == "Web search"
    assert d["roles"][0]["label"] == "Orchestrator (main session)"
    assert d["projets"][0]["nom"] == "Repository root (cross-project sessions)"
    assert d["projets"][1]["nom"] == "Recherche web" and d["projets"][1]["statut"] == "🔵 In testing"
    assert d["recos"] == [{"id": "amont", "titre": "T"}]
    assert bilan["detail"]["etapes"][0]["label"] == "🛠️ Développement"  # source intacte
    assert i18n.traduire_donnees(bilan, "fr") is bilan


@pytest.mark.parametrize("ident", sorted(i18n.RECOS))
def test_recos_memes_champs_dans_chaque_langue(ident):
    """Chaque langue a les mêmes clés et les mêmes champs {valeur} que le français."""
    def champs(texte):
        return set(re.findall(r"\{(\w+)\}", texte))
    fr = i18n.RECOS[ident]["fr"]
    for langue in i18n.LANGUES:
        traduit = i18n.RECOS[ident][langue]
        assert traduit.keys() == fr.keys()
        for cle in fr:
            assert champs(traduit[cle]) == champs(fr[cle]), (ident, langue, cle)
