"""Le modèle d'agent verif-front (expérimental) : forme, outils, version épinglée."""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
MODELE = RACINE / "modeles" / "agents" / "verif-front.md"


def _parties():
    texte = MODELE.read_text(encoding="utf-8")
    assert texte.startswith("---\n")
    entete, corps = texte[4:].split("\n---\n", 1)
    return entete, corps


def _champ(entete, nom):
    m = re.search(rf"^{nom}:\s*(.+)$", entete, re.M)
    assert m, nom
    return m.group(1).strip()


def test_modele_existe_et_pas_dans_agents():
    assert MODELE.is_file()
    assert not (RACINE / "agents" / "verif-front.md").exists()


def test_frontmatter():
    entete, _ = _parties()
    assert _champ(entete, "name") == "verif-front"
    assert _champ(entete, "model") == "sonnet"
    assert _champ(entete, "effort") == "medium"


def test_outils_lecture_seule():
    entete, _ = _parties()
    outils = [o.strip() for o in _champ(entete, "tools").split(",")]
    assert "Read" in outils and "mcp__playwright__*" in outils
    for interdit in ("Bash", "PowerShell", "Edit", "Write"):
        assert interdit not in outils


def test_playwright_epingle():
    entete, _ = _parties()
    m = re.search(r"@playwright/mcp(@[^\"'\s,\]]+)", entete)
    assert m, "version absente"
    assert re.fullmatch(r"@\d+\.\d+\.\d+", m.group(1))
    assert "latest" not in entete


def test_corps():
    _, corps = _parties()
    assert "`spec`" in corps and "`hors-spec`" in corps
    assert "390" in corps
