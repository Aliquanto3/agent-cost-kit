"""Gabarit du bilan des tokens : charte générique v2.1 (sombre d'abord, contrastes, aucune couleur hors jetons)."""

import re
from pathlib import Path

import pytest

GABARIT = Path(__file__).resolve().parent.parent / "skills" / "bilan-tokens" / "gabarit.html"
DEBUT, FIN = "/* JETONS charte", "/* FIN JETONS */"


def _page() -> str:
    return GABARIT.read_text(encoding="utf-8")


def _bloc_apres(texte: str, selecteur: str) -> str:
    """Corps (accolades équilibrées) du premier bloc qui commence par ``selecteur``."""
    debut = texte.index(selecteur)
    i = texte.index("{", debut)
    prof = 0
    for j in range(i, len(texte)):
        prof += {"{": 1, "}": -1}.get(texte[j], 0)
        if prof == 0:
            return texte[i + 1 : j]
    raise AssertionError("accolades non équilibrées")


def _jetons(corps: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\b", corps))


def _zone_jetons() -> str:
    page = _page()
    return page[page.index(DEBUT) : page.index(FIN)]


def _themes() -> dict[str, dict[str, str]]:
    zone = _zone_jetons()
    sombre = _jetons(_bloc_apres(zone, ":root {"))
    clair_systeme = _jetons(_bloc_apres(_bloc_apres(zone, "@media (prefers-color-scheme: light)"), ":root:not("))
    clair_force = _jetons(_bloc_apres(zone, '[data-theme="clair"]'))
    sombre_force = _jetons(_bloc_apres(zone, '\n[data-theme="sombre"]'))
    assert clair_systeme == clair_force, "le clair système et le clair forcé diffèrent"
    assert sombre == sombre_force, "le sombre par défaut et le sombre forcé diffèrent"
    return {"sombre": sombre, "clair": clair_force}


def _lin(c: int) -> float:
    x = c / 255
    return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4


def _luminance(hexa: str) -> float:
    r, g, b = (int(hexa[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contraste(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# Couples réellement présents dans le gabarit : (premier plan, fond).
TEXTE = [
    ("texte", "fond"), ("texte", "surface"), ("texte", "surface-alt"),
    ("texte-attenue", "fond"), ("texte-attenue", "surface"), ("texte-attenue", "surface-alt"),
    ("primaire", "surface"), ("primaire", "fond"), ("primaire", "surface-alt"),  # eyebrow, liens, kpi
    ("primaire-vif", "fond"),  # h1 em
    ("primaire", "primaire-doux"), ("texte", "primaire-doux"), ("texte-attenue", "primaire-doux"),
    ("succes", "surface"), ("succes", "succes-doux"), ("texte-attenue", "succes-doux"),
    ("alerte-texte", "surface"), ("alerte-texte", "alerte-doux"), ("texte-attenue", "alerte-doux"),
    ("erreur", "surface"), ("erreur", "erreur-doux"), ("texte-attenue", "erreur-doux"),
    ("sur-bouton", "bouton"),  # numéro des recommandations
]
# Le filet or (accent-aplat) est décoratif : il ne porte aucune information, hors de ces seuils.
MARQUES = [
    ("trait-fort", "surface"), ("trait-fort", "fond"),  # contour des boutons et du sélecteur de langue
    ("focus", "fond"), ("focus", "surface"), ("focus", "surface-alt"),
    ("primaire", "primaire-doux"),  # liseré de l'état enfoncé
    ("primaire", "trait"),  # jauge de part de l'orchestrateur
    ("neutre", "surface"), ("primaire-vif", "surface"),
    ("picto-point", "picto-tuile"), ("sur-primaire", "picto-tuile"),
] + [(f"cat-{n}", "surface") for n in range(1, 9)]


def _valeur(theme: dict[str, str], nom: str) -> str:
    return theme[{"picto-tuile": "pictogramme-tuile", "picto-point": "pictogramme-point"}.get(nom, nom)]


@pytest.mark.parametrize("nom", ["sombre", "clair"])
@pytest.mark.parametrize("premier,fond", TEXTE)
def test_contraste_texte_4_5(nom, premier, fond):
    t = _themes()[nom]
    assert contraste(_valeur(t, premier), _valeur(t, fond)) >= 4.5, (nom, premier, fond)


@pytest.mark.parametrize("nom", ["sombre", "clair"])
@pytest.mark.parametrize("premier,fond", MARQUES)
def test_contraste_marques_3(nom, premier, fond):
    t = _themes()[nom]
    assert contraste(_valeur(t, premier), _valeur(t, fond)) >= 3.0, (nom, premier, fond)


def test_sombre_d_abord_et_clair_selon_le_systeme():
    zone = _zone_jetons()
    assert "color-scheme: dark" in _bloc_apres(zone, ":root {")
    clair = _bloc_apres(zone, "@media (prefers-color-scheme: light)")
    assert "color-scheme: light" in clair
    assert 'not([data-theme="dark"])' in clair
    assert set(_themes()["sombre"]) == set(_themes()["clair"])


def test_valeurs_cles_de_la_charte_v2_1():
    t = _themes()
    assert t["sombre"]["fond"] == "#0F1318" and t["clair"]["fond"] == "#F6F8FB"
    assert t["sombre"]["bouton"] == "#E8ECF2" and t["clair"]["bouton"] == "#121821"
    assert t["sombre"]["primaire"] == "#8DB0F7" and t["clair"]["primaire"] == "#1D5BC2"


def test_aucun_hex_hors_des_jetons():
    page = _page()
    reste = page[: page.index(DEBUT)] + page[page.index(FIN) :]
    assert re.findall(r"#[0-9A-Fa-f]{6,8}\b", reste) == []
    for style in re.findall(r"<style>(.*?)</style>", reste, re.S):
        assert re.findall(r"#[0-9A-Fa-f]{3,4}\b", style) == []
    assert not re.search(r"\b(?:rgb|rgba|hsl|hsla)\(", reste)


def test_aucun_repli_bleu_dans_var():
    assert not re.search(r"var\(--[a-z0-9-]+\s*,\s*#", _page())


def test_aucune_variable_de_l_ancienne_charte():
    page = _page()
    assert "--c-" not in page and "--st-" not in page


def test_le_bleu_n_est_jamais_un_aplat_de_bouton():
    page = _page()
    css = re.sub(r"/\*.*?\*/", "", "\n".join(re.findall(r"<style>(.*?)</style>", page, re.S)), flags=re.S)
    regles = re.findall(r"([^{}]+)\{([^{}]*)\}", css)
    bleu = re.compile(r"var\(--primaire(?:-vif)?\)")
    trouves = []
    for sel, corps in regles:
        if not re.search(r"button|aria-pressed|aria-current|\.lang a", sel):
            continue
        for decl in corps.split(";"):
            prop, _, valeur = decl.partition(":")
            if prop.strip() in ("background", "background-color") and bleu.search(valeur):
                trouves.append(sel.strip())
    assert trouves == []
    # le bouton enfoncé prend le fond doux de la sélection
    assert "button[aria-pressed=\"true\"]{background:var(--primaire-doux)" in page


def test_bouton_secondaire_en_contour_et_focus_visible():
    page = _page()
    assert "border:1px solid var(--trait-fort)" in page
    assert "outline:var(--focus-largeur) solid var(--focus)" in page


def test_liens_soulignes_et_pas_de_theme_force():
    page = _page()
    assert re.search(r"\ba\{text-decoration:underline", page)
    assert "data-theme" not in page.replace(_zone_jetons(), "")
    assert 'name="color-scheme" content="dark light"' in page


def test_filet_or_et_pictogramme_de_la_charte():
    page = _page()
    assert "h1::after" in page and "background:var(--accent-aplat)" in page
    for jeton in ("picto-tuile", "picto-barres", "picto-point"):
        assert f"var(--{jeton})" in page and f"--{jeton}: var(" in page


def test_polices_de_la_charte_sans_cdn():
    page = _page()
    assert "--police-titres: Sora" in page and "'Atkinson Hyperlegible'" in page and "'JetBrains Mono'" in page
    assert "fonts.googleapis" not in page and "@import" not in page
