---
title: "agent-cost-kit 0.20.2 : avancement-run, runs hors epics et stories terminées sans fusion"
status: review
date: 2026-11-06
source: "PR #17 (slmsp, 2026-10-20) ; run où l'Epic 0 n'apparaissait pas terminée (story 0.0 poussée sur main, 3.6 close sans fusion)"
---

# agent-cost-kit 0.20.2 : avancement-run, runs hors epics et stories terminées sans fusion

Surface : `scripts/avancement_run.py`, ses tests et sa fixture `tests/fixtures/avancement-hors-epics/`, `commands/avancement-run.md`, `docs/avancement-run.md`, `modeles/run-autonome.md`.

## Choix

- Runs hors epics (PR #17, fusionnée avec master 0.20.1) : identifiants `C1`, `O4a`, `E1b` en plus de `N.M` et `N.Mb` ; périmètre « Stories C1 à C9, O1 » (plages développées, notes entre parenthèses ignorées) ; story absente de sprint-status suivie par le journal seul ; `décision` et `report` ne marquent plus « reprise ». Les stories hors epics vont dans un epic sentinelle `HORS_EPIC = -1` (et non 0 : l'Epic 0 existe), affiché « — · Hors epic ».
- Étape `clôture` (`clôture` ou `cloture`) : termine la story comme une `fusion` (jalon « fusion faite », heure de fin).
- Repli : une story `done` sans `fusion` ni `clôture` au journal compte terminée, drapeau « sans fusion journalisée », puce « X terminée(s) sans fusion journalisée (`done` dans sprint-status) : ajouter au journal une ligne `fusion` ou `clôture`. » Pas d'effet sur la météo.
- Le repli ne s'applique pas quand la dernière ligne montre la story en vol : `blocked`, PR ouverte, CI rouge, ou `dev`, `second-avis`, `review` « lancé(e) ». La story reste alors en cours, comme avant (« en attente de fusion »). Cette exception va au-delà du seul `blocked` demandé : sans elle, l'extrait réel du 2026-10-19 (5.4 `done` en second avis) passerait terminé.
- La dernière étape fait foi : une `fusion` ou `clôture` suivie d'un `dev · lancé` rouvre la story (en cours, drapeau « reprise », météo 🟡).

## Tests

`tests/test_avancement_run.py` : tests de #17 ; `clôture` terminée ; repli avec alerte (pluriel et singulier) ; pas d'alerte avec une fusion ; `done` bloquée en dernier reste en cours ; epic 0 terminée quand sa seule story non fusionnée est `done` ; fusion puis `dev · lancé` = reprise. `test_done_sans_fusion_n_est_pas_terminee` : 1.1 passe de « review · finie » à « review · lancée », le cas « revue finie » relevant désormais du repli.

## Reports

- Aucun.
