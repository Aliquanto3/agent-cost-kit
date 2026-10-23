"""Tests de scripts/bilan_tokens.py sur des transcriptions jsonl synthétiques (tmp_path)."""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import bilan_tokens as bt
import mesurer_couts as mc


def ligne(ts: str, mid: str, modele: str, texte: str = "x" * 220, **usage) -> str:
    base_usage = {
        "input_tokens": 1000,
        "output_tokens": 50,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 2000,
        "inference_geo": "global",
    }
    base_usage.update(usage)
    entree = {
        "timestamp": ts,
        "message": {
            "role": "assistant",
            "id": mid,
            "model": modele,
            "content": [{"type": "text", "text": texte}],
            "usage": base_usage,
        },
    }
    return json.dumps(entree)


@pytest.fixture()
def racine(tmp_path):
    racine = tmp_path / "projects"
    racine.mkdir()
    depot_a = Path("C:/depot/projetA") if sys.platform == "win32" else Path("/depot/projetA")
    dossier_a = mc.dossier_transcriptions(depot_a, racine)
    dossier_a.mkdir(parents=True)
    (dossier_a / "session1" / "subagents").mkdir(parents=True)

    lignes_session1 = [
        ligne("2026-10-01T10:00:00Z", "msg1", "claude-opus-5-5", input_tokens=1000, cache_creation_input_tokens=500, cache_read_input_tokens=2000, output_tokens=100),
        ligne("2026-10-02T10:00:00Z", "msgDUP", "claude-opus-5-5", input_tokens=200, cache_creation_input_tokens=0, cache_read_input_tokens=300, output_tokens=20),
        ligne("2026-10-01T11:00:00Z", "<synthetic>", "claude-opus-5-5", input_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0, output_tokens=5),
        ligne("2026-09-30T23:00:00Z", "msgSep", "claude-opus-5-5", input_tokens=10, cache_creation_input_tokens=0, cache_read_input_tokens=0, output_tokens=10),
    ]
    (dossier_a / "session1.jsonl").write_text("\n".join(lignes_session1) + "\n", encoding="utf-8")

    lignes_sous_agent = [
        ligne("2026-10-03T09:00:00Z", "msgSub1", "claude-sonnet-5-5", input_tokens=300, cache_creation_input_tokens=100, cache_read_input_tokens=500, output_tokens=30),
        # même id que dans session1.jsonl, mais horodaté plus tard : ne doit pas être recompté.
        ligne("2026-10-02T12:00:00Z", "msgDUP", "claude-opus-5-5", input_tokens=9999, cache_creation_input_tokens=9999, cache_read_input_tokens=9999, output_tokens=9999),
    ]
    (dossier_a / "session1" / "subagents" / "agent-aaa.jsonl").write_text("\n".join(lignes_sous_agent) + "\n", encoding="utf-8")

    depot_b = Path("C:/depot/projetB") if sys.platform == "win32" else Path("/depot/projetB")
    dossier_b = mc.dossier_transcriptions(depot_b, racine)
    dossier_b.mkdir(parents=True)
    (dossier_b / "session2.jsonl").write_text(
        ligne("2026-10-05T08:00:00Z", "msgB1", "claude-haiku-5-5", input_tokens=400, cache_creation_input_tokens=0, cache_read_input_tokens=0, output_tokens=40) + "\n",
        encoding="utf-8",
    )
    return racine, depot_a, depot_b


def test_projets_retenus_filtre_dossier(racine):
    racine_, depot_a, _depot_b = racine
    retenus = bt.projets_retenus(racine_, depot_a)
    assert len(retenus) == 1
    assert retenus[0].name.startswith(mc.dossier_transcriptions(depot_a, racine_).name)
    assert len(bt.projets_retenus(racine_, None)) == 2


def test_collecter_dedoublonne_filtre_mois_et_synthetic(racine):
    racine_, depot_a, _ = racine
    projets = bt.projets_retenus(racine_, depot_a)
    retenus = bt.collecter(projets, "2026-10")
    ids = {a["id"] for a in retenus}
    assert "<synthetic>" not in ids
    assert "msgSep" not in ids  # hors mois
    assert sum(1 for a in retenus if a["id"] == "msgDUP") == 1
    dup = next(a for a in retenus if a["id"] == "msgDUP")
    assert dup["entree"] == 200  # garde la première occurrence chronologique, pas la plus grosse
    assert {a["id"] for a in retenus} == {"msg1", "msgDUP", "msgSub1"}


def test_par_modele_agrege_et_cout_sans_cache(racine):
    racine_, depot_a, _ = racine
    retenus = bt.collecter(bt.projets_retenus(racine_, depot_a), "2026-10")
    modeles = bt.par_modele(retenus, mc.MIX_DEFAUT)
    noms = {m["modele"] for m in modeles}
    assert noms == {"claude-opus-5-5", "claude-sonnet-5-5"}
    opus = next(m for m in modeles if m["modele"] == "claude-opus-5-5")
    assert opus["appels"] == 2
    assert opus["entree"] == 1200
    tarif = mc.prix("claude-opus-5-5")
    assert opus["cout_sans_cache"] == pytest.approx((1200 + 500 + 2300) * tarif["entree"] / 1e6, rel=1e-6)
    for m in modeles:
        assert set(m["impact"]) == set(mc.GRANDEURS)


def test_commande_collecte_ecrit_json_et_html(racine, tmp_path):
    racine_, depot_a, _ = racine
    out = tmp_path / "out"
    options = Namespace(mois="2026-10", dossier=depot_a, racine=racine_, machine="pc-test", out=out, mix=mc.MIX_DEFAUT)
    assert bt.commande_collecte(options) == 0
    chemin_json = out / "2026-10-pc-test.json"
    chemin_html = out / "2026-10-pc-test.html"
    assert chemin_json.exists() and chemin_html.exists()
    bilan = json.loads(chemin_json.read_text(encoding="utf-8"))
    assert bilan["schema"] == 1
    assert bilan["machine"] == "pc-test"
    assert bilan["mois"] == "2026-10"
    assert bilan["premier_appel"] == "2026-10-01T10:00:00Z"
    assert bilan["dernier_appel"] == "2026-10-03T09:00:00Z"
    assert {m["modele"] for m in bilan["modeles"]} == {"claude-opus-5-5", "claude-sonnet-5-5"}
    assert "claude-opus-5-5" in bilan["prix"]

    html = chemin_html.read_text(encoding="utf-8")
    assert "__BILAN__" not in html
    assert "claude-opus-5-5" in html
    assert '"machine":"pc-test"' in html.replace(" ", "")


def test_fusion_somme_deux_machines(racine, tmp_path):
    racine_, depot_a, _ = racine
    out1, out2, out_fusion = tmp_path / "pc1", tmp_path / "pc2", tmp_path / "fusion"
    bt.commande_collecte(Namespace(mois="2026-10", dossier=depot_a, racine=racine_, machine="pc1", out=out1, mix=mc.MIX_DEFAUT))
    bt.commande_collecte(Namespace(mois="2026-10", dossier=depot_a, racine=racine_, machine="pc2", out=out2, mix=mc.MIX_DEFAUT))
    j1, j2 = out1 / "2026-10-pc1.json", out2 / "2026-10-pc2.json"

    options = Namespace(fusionner=[str(j1), str(j2)], out=out_fusion)
    assert bt.commande_fusion(options) == 0
    chemin_json = out_fusion / "2026-10-consolide.json"
    chemin_html = out_fusion / "2026-10-consolide.html"
    assert chemin_json.exists() and chemin_html.exists()
    consolide = json.loads(chemin_json.read_text(encoding="utf-8"))
    assert consolide["machines"] == ["pc1", "pc2"]
    opus = next(m for m in consolide["modeles"] if m["modele"] == "claude-opus-5-5")
    seul = json.loads(j1.read_text(encoding="utf-8"))
    opus_seul = next(m for m in seul["modeles"] if m["modele"] == "claude-opus-5-5")
    assert opus["appels"] == 2 * opus_seul["appels"]
    assert opus["entree"] == 2 * opus_seul["entree"]
    assert opus["cout"]["entree"] == pytest.approx(2 * opus_seul["cout"]["entree"], rel=1e-9)
    assert len(consolide["par_machine"]) == 2

    html = chemin_html.read_text(encoding="utf-8")
    assert "__BILAN__" not in html
    assert '"machines":["pc1","pc2"]' in html.replace(" ", "")


def test_fusion_refuse_mois_differents_et_machine_en_double(tmp_path):
    base = {
        "schema": 1, "machine": "pc1", "mois": "2026-10", "dossier": None,
        "genere_le": "2026-10-23T00:00:00+00:00", "premier_appel": "2026-10-01T00:00:00Z",
        "dernier_appel": "2026-10-01T00:00:00Z", "mix": mc.MIX_DEFAUT, "modeles": [], "prix": {},
    }
    a = tmp_path / "a.json"
    b_autre_mois = tmp_path / "b.json"
    b_meme_machine = tmp_path / "c.json"
    a.write_text(json.dumps(base), encoding="utf-8")
    b_autre_mois.write_text(json.dumps({**base, "mois": "2026-11", "machine": "pc2"}), encoding="utf-8")
    b_meme_machine.write_text(json.dumps({**base, "machine": "pc1"}), encoding="utf-8")

    with pytest.raises(SystemExit):
        bt.commande_fusion(Namespace(fusionner=[str(a), str(b_autre_mois)], out=tmp_path / "out1"))
    with pytest.raises(SystemExit):
        bt.commande_fusion(Namespace(fusionner=[str(a), str(b_meme_machine)], out=tmp_path / "out2"))
