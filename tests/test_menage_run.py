"""Tests de scripts/menage_run.py sur de vrais dépôts git temporaires (git réel, gh et test de PID injectés)."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import avancement_run as ar
import menage_run as mr

if not shutil.which("git"):
    pytest.skip("git absent", allow_module_level=True)

VIEUX = int(time.time()) - 3 * 86400


class Monde:
    """Dépôt nu `distant.git` + clone de travail `work`, commits vieux de 3 jours."""

    def __init__(self, racine: Path):
        self.racine = racine
        self.distant = racine / "distant.git"
        self.work = racine / "work"

    def g(self, *args, cwd=None, recent=False, env=None):
        e = None
        if recent:
            e = {**os.environ, "GIT_COMMITTER_DATE": f"{int(time.time())} +0000",
                 "GIT_AUTHOR_DATE": f"{int(time.time())} +0000"}
        r = subprocess.run(["git", *args], cwd=cwd or self.work, check=True, capture_output=True, text=True,
                           encoding="utf-8", env=e)
        return r.stdout.strip()

    def commit(self, fichier, msg, recent=False):
        (self.work / fichier).write_text(msg, encoding="utf-8")
        self.g("add", fichier)
        self.g("commit", "-q", "-m", msg, recent=recent)
        return self.g("rev-parse", "HEAD")

    def branche(self, nom, fichier, recent=False):
        self.g("checkout", "-q", "-b", nom, "main")
        sha = self.commit(fichier, nom, recent=recent)
        self.g("checkout", "-q", "main")
        return sha

    def refs(self):
        return self.g("for-each-ref", "--format=%(refname) %(objectname)"), self.g("worktree", "list", "--porcelain")


@pytest.fixture()
def monde(tmp_path, monkeypatch):
    for k, v in {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "T",
                 "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_COMMITTER_DATE": f"{VIEUX} +0000",
                 "GIT_AUTHOR_DATE": f"{VIEUX} +0000", "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
                 "GIT_CONFIG_NOSYSTEM": "1"}.items():
        monkeypatch.setenv(k, v)
    m = Monde(tmp_path)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(m.distant)], check=True)
    m.work.mkdir()
    m.g("init", "-q", "-b", "main")
    m.g("config", "core.autocrlf", "false")
    m.g("remote", "add", "origin", str(m.distant))
    m.commit("a.txt", "base")
    m.g("push", "-q", "origin", "main")
    m.g("remote", "set-head", "origin", "main")
    return m


@pytest.fixture()
def branches(monde):
    """Branches de cas : anc, cher, squash, squash2, openpr, recent, fresh, unmerged."""
    m = monde
    base = m.g("rev-parse", "main")
    for nom in ("anc", "openpr"):
        m.branche(nom, nom + ".txt")
        m.g("merge", "-q", "--no-ff", nom, "-m", "merge " + nom)
    m.branche("recent", "recent.txt", recent=True)
    m.g("merge", "-q", "--no-ff", "recent", "-m", "merge recent")
    sha_cher = m.branche("cher", "cher.txt")
    m.commit("avance.txt", "main avance")  # sinon le cherry-pick redonne exactement le même commit
    m.g("cherry-pick", sha_cher)
    tetes = {"cher": sha_cher}
    for nom in ("squash", "squash2"):
        tetes[nom] = m.branche(nom, nom + ".txt")
        m.g("checkout", "-q", nom)  # deux commits : le squash n'a le patch d'aucun des deux
        tetes[nom] = m.commit(nom + "-bis.txt", nom + " bis")
        m.g("checkout", "-q", "main")
        m.g("merge", "-q", "--squash", nom)
        m.g("commit", "-q", "-m", "squash " + nom)
    m.g("checkout", "-q", "squash2")
    tetes["squash2_avance"] = m.commit("suite.txt", "suite")
    m.g("checkout", "-q", "main")
    m.branche("unmerged", "unmerged.txt")
    m.g("branch", "fresh", base, recent=True)
    m.g("push", "-q", "origin", "main", "anc", "unmerged", "openpr")
    tetes["openpr"] = m.g("rev-parse", "openpr")
    return m, tetes


def prs_de(tetes):
    return [
        {"number": 7, "state": "OPEN", "headRefName": "openpr", "headRefOid": tetes["openpr"], "isCrossRepository": False},
        {"number": 8, "state": "MERGED", "headRefName": "squash", "headRefOid": tetes["squash"], "isCrossRepository": False},
        {"number": 9, "state": "MERGED", "headRefName": "squash2", "headRefOid": tetes["squash2"], "isCrossRepository": False},
    ]


def lancer(m, capsys, *args, prs=(), gh_ok=True, vivant=lambda pid: False):
    def gh(_args, _cwd):
        return (0, json.dumps(list(prs))) if gh_ok else (1, "gh: boom")

    code = mr.main(["--depot", str(m.work), "--json", *args], gh=gh, vivant=vivant)
    sortie = capsys.readouterr().out
    return code, (json.loads(sortie) if sortie.strip().startswith("{") else sortie)


def motifs(plan, cle):
    return {b["nom"]: (b["action"], b["motif"]) for b in plan[cle]}


def locales(m):
    return set(m.g("for-each-ref", "--format=%(refname:short)", "refs/heads").split())


ATTENDU_LOCALES = {
    "anc": ("supprimer", "ancêtre"),
    "cher": ("supprimer", "patchs équivalents"),
    "squash": ("supprimer", "PR #8 fusionnée"),
    "squash2": ("garder", "non fusionnée"),
    "openpr": ("garder", "PR #7 ouverte"),
    "recent": ("garder", "activité récente (commit)"),
    "fresh": ("garder", "activité récente (reflog)"),
    "unmerged": ("garder", "non fusionnée"),
}


def test_simulation_ne_change_rien_et_donne_les_motifs(branches, capsys):
    m, tetes = branches
    avant = m.refs()
    code, plan = lancer(m, capsys, prs=prs_de(tetes))
    assert code == 0 and plan["simulation"] is True
    assert motifs(plan, "locales") == ATTENDU_LOCALES  # main jamais listée
    assert m.refs() == avant


def test_appliquer_supprime_les_seules_branches_contenues(branches, capsys):
    m, tetes = branches
    code, plan = lancer(m, capsys, "--appliquer", prs=prs_de(tetes))
    assert code == 0
    assert locales(m) == {"main", "squash2", "openpr", "recent", "fresh", "unmerged"}
    assert sorted(plan["resultat"]["locales"]) == ["anc", "cher", "squash"]
    assert plan["resultat"]["journal"].endswith("0 worktrees retirés, 0 verrous levés, 3 branches locales, "
                                                 "0 distantes supprimées · —")


def test_distantes_listees_puis_supprimees_seulement_avec_distant(branches, capsys):
    m, tetes = branches
    code, plan = lancer(m, capsys, prs=prs_de(tetes))
    assert motifs(plan, "distantes") == {"anc": ("supprimer", "ancêtre"), "unmerged": ("garder", "non fusionnée"),
                                         "openpr": ("garder", "PR #7 ouverte")}
    lancer(m, capsys, "--appliquer", prs=prs_de(tetes))
    assert set(m.g("branch", "-r", "--format=%(refname:short)").split()) >= {"origin/anc", "origin/unmerged"}
    code, plan = lancer(m, capsys, "--appliquer", "--distant", prs=prs_de(tetes))
    assert code == 0 and plan["resultat"]["distantes"] == ["anc"]
    assert "origin/anc" not in m.g("branch", "-r", "--format=%(refname:short)").split()
    sur_distant = set(m.g("for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=m.distant).split())
    assert sur_distant == {"main", "unmerged", "openpr"}


def test_distant_sans_gh_refuse_code_2_et_rien_supprime(branches, capsys):
    m, _ = branches
    avant = m.refs()
    code, _ = lancer(m, capsys, "--appliquer", "--distant", gh_ok=False)
    assert code == 2 and m.refs() == avant
    assert "origin/anc" in m.g("branch", "-r", "--format=%(refname:short)").split()


def test_sans_gh_le_menage_local_reste_possible(branches, capsys):
    m, _ = branches
    code, plan = lancer(m, capsys, "--appliquer", gh_ok=False)
    assert code == 0
    assert sorted(plan["resultat"]["locales"]) == ["anc", "cher", "openpr"]  # PR ouverte inconnue
    assert "squash" in locales(m)  # critère PR sauté : le squash n'est pas reconnu


def test_depot_invalide_ou_defaut_introuvable_code_2(tmp_path, capsys, monkeypatch):
    assert mr.main(["--depot", str(tmp_path)]) == 2
    assert "n'est pas un dépôt git" in capsys.readouterr().err
    subprocess.run(["git", "init", "-q", "-b", "autre", str(tmp_path / "x")], check=True)
    assert mr.main(["--depot", str(tmp_path / "x")]) == 2
    assert "introuvable" in capsys.readouterr().err


def ajouter_wt(m, nom, *options):
    chemin = m.racine / nom
    m.g("worktree", "add", "-q", *options, str(chemin), "-b", nom, "main")
    return chemin


def test_worktrees_propre_retire_modifie_garde(monde, capsys):
    m = monde
    propre, modifie = ajouter_wt(m, "wt-propre"), ajouter_wt(m, "wt-modifie")
    (modifie / "perdu.txt").write_text("x", encoding="utf-8")
    code, plan = lancer(m, capsys, "--appliquer")
    assert code == 0
    par = {Path(w["chemin"]).name: (w["action"], w["motif"]) for w in plan["worktrees"]}
    assert par == {"wt-propre": ("retirer", "ancêtre"), "wt-modifie": ("garder", "modifié")}
    assert not propre.exists() and modifie.exists()
    assert "wt-propre" not in locales(m) and "wt-modifie" in locales(m)  # branche extraite : gardée
    assert motifs(plan, "locales")["wt-modifie"][1].startswith("extraite dans ")


@pytest.mark.parametrize("raison,vivant,retire,motif", [
    ("claude agent agent-x1 (pid 4242)", False, True, "ancêtre, verrou levé (PID 4242 disparu)"),
    ("claude agent agent-x1 (pid 4242)", True, False, "verrou, PID 4242 vivant"),
    ("posé à la main", False, False, "verrou sans PID"),
])
def test_worktree_verrouille(monde, capsys, raison, vivant, retire, motif):
    m = monde
    chemin = ajouter_wt(m, "wt-verrou", "--lock", "--reason", raison)
    vus = []
    code, plan = lancer(m, capsys, "--appliquer", vivant=lambda pid: vus.append(pid) or vivant)
    assert code == 0
    w = plan["worktrees"][0]
    assert (w["action"] == "retirer", w["motif"]) == (retire, motif)
    assert chemin.exists() is not retire
    assert plan["resultat"]["verrous_leves"] == ([w["chemin"]] if retire else [])
    assert vus == ([] if "posé" in raison else [4242])


def test_worktree_dossier_efface_est_prune(monde, capsys):
    m = monde
    chemin = ajouter_wt(m, "wt-disparu")
    shutil.rmtree(chemin)
    code, plan = lancer(m, capsys, "--appliquer")
    assert code == 0 and plan["resultat"]["pruned"] is True
    assert (plan["worktrees"][0]["action"], plan["worktrees"][0]["motif"]) == ("prune", "dossier disparu")
    assert "wt-disparu" not in m.g("worktree", "list", "--porcelain")
    assert plan["resultat"]["journal"].split(" · ")[3].startswith("1 worktrees retirés")


def test_simulation_worktrees_inchange(monde, capsys):
    m = monde
    ajouter_wt(m, "wt-a", "--lock", "--reason", "agent (pid 99)")
    ajouter_wt(m, "wt-b")
    shutil.rmtree(ajouter_wt(m, "wt-c"))
    avant = m.refs()
    code, plan = lancer(m, capsys)
    assert code == 0 and plan["simulation"] is True and m.refs() == avant
    assert {Path(w["chemin"]).name: w["action"] for w in plan["worktrees"]} == {
        "wt-a": "retirer", "wt-b": "retirer", "wt-c": "prune"}


def test_worktree_non_fusionne_ou_recent_garde(monde, capsys):
    m = monde
    non_fusionne = ajouter_wt(m, "wt-travail")
    (non_fusionne / "t.txt").write_text("t", encoding="utf-8")
    m.g("add", "t.txt", cwd=non_fusionne)
    m.g("commit", "-q", "-m", "travail", cwd=non_fusionne)
    ajouter_wt(m, "wt-frais")
    m.g("commit", "-q", "--allow-empty", "-m", "frais", cwd=m.racine / "wt-frais", recent=True)
    m.g("merge", "-q", "wt-frais")  # contenu dans main, mais le commit est récent
    code, plan = lancer(m, capsys)
    par = {Path(w["chemin"]).name: (w["action"], w["motif"]) for w in plan["worktrees"]}
    assert par == {"wt-travail": ("garder", "non fusionné"), "wt-frais": ("garder", "activité récente (commit)")}


def test_sortie_markdown_et_ligne_de_journal_lue_par_avancement(branches, capsys):
    m, tetes = branches
    mr.main(["--depot", str(m.work)], gh=lambda a, c: (0, json.dumps(prs_de(tetes))))
    texte = capsys.readouterr().out
    assert "## Worktrees" in texte and "## Verrous" in texte and "## Branches locales" in texte
    assert "- supprimer `anc` " in texte and " : ancêtre" in texte
    assert texte.rstrip().endswith("relancer avec `--appliquer`, puis `--appliquer --distant` après avoir montré "
                                   "la liste des branches distantes à Anaël.")
    mr.main(["--depot", str(m.work), "--appliquer"], gh=lambda a, c: (0, json.dumps(prs_de(tetes))))
    texte = capsys.readouterr().out
    ligne = next(x for x in texte.splitlines() if "· run · ménage ·" in x)
    assert ligne.endswith("· 0 worktrees retirés, 0 verrous levés, 3 branches locales, 0 distantes supprimées · —") or \
        "3 branches locales, 0 distantes supprimées · —" in ligne
    assert f"- `git branch cher {tetes['cher']}`" in texte
    evts = ar.lire_journal("## Journal\n\n" + ligne + "\n")
    assert len(evts) == 1 and evts[0]["etape"] == "ménage" and evts[0]["stories"] == []
    assert evts[0]["resultat"].startswith("0 worktrees retirés")
