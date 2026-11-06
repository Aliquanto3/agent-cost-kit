---
title: "agent-cost-kit 0.21.1 : avancement-run, runs hors epics et stories terminées sans fusion"
status: review
date: 2026-11-06
source: "PR #17 (slmsp, 2026-10-20) ; run où l'Epic 0 n'apparaissait pas terminée (story 0.0 poussée sur main, 3.6 close sans fusion)"
---

# agent-cost-kit 0.21.1 : avancement-run, runs hors epics et stories terminées sans fusion

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

## Revue

### Passe 1 (2026-11-06, SHA revu 190721d)

Merge de master 0.21.0 (#43) fait avant de juger : version renumérotée 0.21.1, spec renommée, ajouts de #43 gardés dans `modeles/run-autonome.md`.

- Important, medium, second avis 1 : une story `N.M` du périmètre absente de sprint-status ignorait le journal (`2.1 · fusion` restait « à faire »). Corrigé : toute story absente de sprint-status suit le journal seul ; doc alignée ; test `test_story_numerique_absente_de_sprint_status_suit_le_journal`.
- Important, medium, second avis 2 : « Stories C1 à C3 (sauf C2) » comptait C2. Corrigé : `(sauf …)` exclut, les autres parenthèses restent des notes ; doc et test.
- Nit, low, second avis 3 : `commands/avancement-run.md` disait « n'est terminée que fusionnée ou close » puis comptait le repli. Corrigé (reformulé, idem `docs/avancement-run.md`).
- Nit, low, second avis 4 : `dater` ne date par le commit « suivi du run … fusionnée » que les `fusion`. Rejeté : ce commit date une fusion ; une `clôture` sans heure prend l'heure du commit cité, puis l'interpolation.
- Nit, low, second avis 5 : « dernière étape » = dernière ligne du fichier. Gardé (journal en ajout seul, même convention que le reste du rapport) ; documenté.
- Nit, low, second avis 6 : `V3`, `ADR2` captés dans les sujets de commit par `dater`. Rejeté : ces entrées ne sont lues que pour les stories de la colonne story du journal, sans effet observable.
- Nit, low, second avis 7 : `| Hors run | C5 à C7 |` sans « Stories » ignoré. Corrigé, test.
- Nit, low, second avis 8 : la clé `e2e-tests` donne une entrée `E2e`. Rejeté : entrée jamais lue (aucune story `E2e` au plan ni au journal) ; la syntaxe ne la distingue pas d'une clé `o4a-slug` légitime.
- Nit, low, second avis 9 : tests faibles ou manquants. Corrigé : ordre de `cle_id` testé par un tri, tests `clôture` puis `dev lancé`, CI rouge ou PR ouverte en dernier pour le repli, story `N.M` absente de sprint-status, plage avec `(sauf …)`.
- Complexité : 0 constat (la recherche de `i_fin` et de reprise reste linéaire par story).
