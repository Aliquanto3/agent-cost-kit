"""Tests de scripts/file_prs.py avec un faux gh (réponses par clé) et un sleep injecté."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import file_prs as fp


def chk(bucket, name="build", run="9"):
    return {"bucket": bucket, "name": name, "workflow": "CI", "link": f"https://github.com/o/r/actions/runs/{run}/job/1"}


class FauxGh:
    """Clé = 'pr checks 1', 'pr view 1 mergeable', 'run rerun 9'... ; valeur = liste de (code, sortie), la dernière reste."""

    def __init__(self, reponses, repo=None):
        self.reponses = {k: list(v) for k, v in reponses.items()}
        self.appels = []
        self.repo = repo

    def __call__(self, args):
        if self.repo:  # chaque appel doit porter --repo en fin, exactement une fois
            assert args[-2:] == ["--repo", self.repo] and args.count("--repo") == 1, args
            args = args[:-2]
        else:
            assert "--repo" not in args, args
        self.appels.append(list(args))
        cle = " ".join(args[:3] + ([args[4]] if args[:2] == ["pr", "view"] else []))
        file = self.reponses.get(cle)
        assert file, f"appel inattendu : {args}"
        rep = file.pop(0) if len(file) > 1 else file[0]
        return (rep[0], rep[1] if isinstance(rep[1], str) else json.dumps(rep[1]))

    def a_appele(self, debut):
        return any(a[: len(debut)] == debut for a in self.appels)


def ok(donnees):
    return (0, donnees)


def ouverte(n):
    return {f"pr view {n} state,mergeCommit": [ok({"state": "OPEN", "mergeCommit": None})]}


def pr_verte(n, commit="abc1234def"):
    return {
        f"pr checks {n}": [ok([chk("pass"), chk("skipping", "opt")])],
        f"pr view {n} mergeable": [ok({"mergeable": "MERGEABLE"})],
        f"pr merge {n}": [ok("")],
        # premier appel : état initial (OPEN) ; second : vérification après merge
        f"pr view {n} state,mergeCommit": [
            ok({"state": "OPEN", "mergeCommit": None}),
            ok({"state": "MERGED", "mergeCommit": {"oid": commit}}),
        ],
    }


def lancer(gh, prs, **kw):
    dormi = []
    kw.setdefault("sleep", dormi.append)
    res = fp.traiter_file(gh, prs, **kw)
    return res, dormi


def test_file_verte():
    gh = FauxGh({**pr_verte("1", "aaa1111"), **pr_verte("2", "bbb2222")})
    res, _ = lancer(gh, ["1", "2"])
    assert [fp.ligne(r) for r in res] == ["#1 fusionnée aaa1111", "#2 fusionnée bbb2222"]


def test_aucun_controle():
    gh = FauxGh({**ouverte("1"), "pr checks 1": [(1, "no checks reported on the 'x' branch")]})
    res, _ = lancer(gh, ["1"])
    assert fp.ligne(res[0]) == "#1 sautée : aucun contrôle (conflit ?)"
    assert not gh.a_appele(["pr", "merge"])


def test_seuls_skipping_compte_comme_aucun_controle():
    gh = FauxGh({**ouverte("1"), "pr checks 1": [ok([chk("skipping")])]})
    res, _ = lancer(gh, ["1"])
    assert "aucun contrôle" in res[0]["detail"]


def test_conflit():
    rep = pr_verte("1")
    rep["pr view 1 mergeable"] = [ok({"mergeable": "CONFLICTING"})]
    gh = FauxGh(rep)
    res, _ = lancer(gh, ["1"])
    assert "non fusionnable" in res[0]["detail"]
    assert not gh.a_appele(["pr", "merge"])


def test_mergeable_unknown_puis_ok():
    rep = pr_verte("1")
    rep["pr view 1 mergeable"] = [ok({"mergeable": "UNKNOWN"}), ok({"mergeable": "MERGEABLE"})]
    res, dormi = lancer(FauxGh(rep), ["1"])
    assert res[0]["statut"] == "fusionnee" and 20 in dormi


def test_rouge_puis_vert_apres_relance():
    rep = pr_verte("1")
    rep["pr checks 1"] = [ok([chk("fail", "tests", "77")]), ok([chk("pass")])]
    rep["run rerun 77"] = [ok("")]
    gh = FauxGh(rep)
    res, _ = lancer(gh, ["1"])
    assert fp.ligne(res[0]) == "#1 fusionnée abc1234 (relancé une fois)"
    assert gh.a_appele(["run", "rerun", "77", "--failed"])


def test_rouge_apres_relance_passe_a_la_suivante():
    rep = {**pr_verte("2", "ccc3333")}
    rep.update(ouverte("1"))
    rep["pr checks 1"] = [ok([chk("fail", "tests", "77")])]
    rep["run rerun 77"] = [ok("")]
    gh = FauxGh(rep)
    res, _ = lancer(gh, ["1", "2"])
    assert fp.ligne(res[0]) == "#1 sautée : rouge après relance (job tests)"
    assert res[1]["statut"] == "fusionnee"
    assert sum(a[:3] == ["run", "rerun", "77"] for a in gh.appels) == 1


def test_echec_du_merge():
    rep = pr_verte("1")
    rep["pr merge 1"] = [(1, "branch protection")]
    res, _ = lancer(FauxGh(rep), ["1"])
    assert "échec du merge" in res[0]["detail"]


def test_etat_non_merged():
    rep = pr_verte("1")
    rep.update(ouverte("1"))
    res, _ = lancer(FauxGh(rep), ["1"])
    assert res[0]["statut"] == "sautee" and "OPEN" in res[0]["detail"]


def test_pending_puis_pass_sans_dormir_reellement():
    rep = pr_verte("1")
    rep["pr checks 1"] = [ok([chk("pending")]), ok([chk("pending")]), ok([chk("pass")])]
    res, dormi = lancer(FauxGh(rep), ["1"], intervalle=60)
    assert res[0]["statut"] == "fusionnee" and dormi == [60, 60]


def test_delai_max():
    rep = pr_verte("1")
    rep["pr checks 1"] = [ok([chk("pending")])]
    temps = iter(range(0, 10**6, 1800))
    res, _ = lancer(FauxGh(rep), ["1"], delai_max=60, horloge=lambda: next(temps))
    assert "délai dépassé" in res[0]["detail"]


def test_a_sec_n_appelle_ni_merge_ni_rerun():
    rep = {**pr_verte("1"), **ouverte("2"), "pr checks 2": [ok([chk("fail", "t", "5")])]}
    gh = FauxGh(rep)
    res, _ = lancer(gh, ["1", "2"], a_sec=True)
    assert not gh.a_appele(["pr", "merge"]) and not gh.a_appele(["run", "rerun"])
    assert [r["statut"] for r in res] == ["prete", "sautee"]
    assert fp.ligne(res[0]) == "#1 prête à fusionner (à sec)"


def test_repo_ajoute_a_chaque_appel():
    rep = pr_verte("1")
    rep["pr checks 1"] = [ok([chk("fail", "tests", "77")]), ok([chk("pass")])]
    rep["run rerun 77"] = [ok("")]
    gh = FauxGh(rep, repo="o/r")
    res, _ = lancer(gh, ["1"], repo="o/r")
    assert res[0]["statut"] == "fusionnee"
    assert {a[0] + " " + a[1] for a in gh.appels} == {"pr checks", "pr view", "run rerun", "pr merge"}


def test_deja_fusionnee_ni_merge_ni_echec(capsys):
    gh = FauxGh({"pr view 101 state,mergeCommit": [ok({"state": "MERGED", "mergeCommit": {"oid": "4364e7cabc"}})]})
    code = fp.main(["101"], gh=gh, sleep=lambda s: None)
    out = capsys.readouterr().out
    assert code == 0 and "#101 déjà fusionnée 4364e7c" in out
    assert gh.appels == [["pr", "view", "101", "--json", "state,mergeCommit"]]


def test_fermee():
    gh = FauxGh({"pr view 1 state,mergeCommit": [ok({"state": "CLOSED", "mergeCommit": None})]})
    res, _ = lancer(gh, ["1"])
    assert fp.ligne(res[0]) == "#1 sautée : fermée sans fusion" and len(gh.appels) == 1


def test_erreur_gh_passagere_puis_ok():
    rep = pr_verte("1")
    rep["pr checks 1"] = [(1, "HTTP 403: API rate limit exceeded"), ok([chk("pass")])]
    res, dormi = lancer(FauxGh(rep), ["1"], intervalle=60)
    assert res[0]["statut"] == "fusionnee" and dormi == [60]


def test_erreur_gh_persistante_n_est_pas_un_conflit():
    gh = FauxGh({**ouverte("1"), "pr checks 1": [(1, "HTTP 403: API rate limit exceeded")]})
    res, dormi = lancer(gh, ["1"])
    assert res[0]["detail"].startswith("contrôles illisibles : HTTP 403") and len(dormi) == fp.ERREURS_GH_MAX - 1


def test_a_sec_code_retour_zero_si_tout_est_pret(capsys):
    code = fp.main(["1", "--a-sec"], gh=FauxGh(pr_verte("1")), sleep=lambda s: None)
    assert code == 0 and "prête à fusionner" in capsys.readouterr().out


def test_main_code_retour_et_json(capsys):
    gh = FauxGh({**pr_verte("1"), **ouverte("2"), "pr checks 2": [(1, "no checks reported")]})
    code = fp.main(["1", "2", "--json", "--intervalle", "5"], gh=gh, sleep=lambda s: None)
    sortie = json.loads(capsys.readouterr().out)
    assert code == 1 and sortie["fusionnees"] == 1 and sortie["total"] == 2


def test_main_texte_toutes_fusionnees(capsys):
    code = fp.main(["#1"], gh=FauxGh(pr_verte("1")), sleep=lambda s: None)
    out = capsys.readouterr().out
    assert code == 0 and "#1 fusionnée abc1234" in out and "Résumé : 1/1" in out
