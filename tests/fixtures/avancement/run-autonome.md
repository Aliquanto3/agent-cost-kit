# Run autonome — plan et état

Fichier d'état de l'orchestrateur, à relire en premier après chaque `/clear`.
Source des statuts : `sprint-status.yaml` (même dossier). Source des stories : `_bmad-output/planning-artifacts/epics.md`.
Établi le 2026-10-18 par `bmad-sprint-planning`. Gate de préparation : **PASS**.

## Périmètre

| Sprint | Contenu | Rôle dans le run |
|---|---|---|
| Sprint 1 (v0.1) | Epics 1 à 6, 44 stories | file principale |
| Sprint 2 (v0.2) | Epics 7 à 9, 17 stories | file de relais : à lancer dès que le Sprint 1 est fini **ou** bloqué sur une étape humaine |
| Hors run | Epics 10 à 12 | 10.2 à 10.5 en `backlog` (en attente de l'UX et du spine station 4) ; 12.5, 12.6 et 12.7 humaines ; reste après v0.2 |

## Règles fixes

1. **Type de story** (ligne `**Type :**` d'epics.md)
   - `dev` : `agent-cost-kit:dev-story` → `agent-cost-kit:second-avis` → `agent-cost-kit:reviewer` (avec la liste du second avis) → intégration.
   - `mixte` : l'agent fait la partie code et publication, puis la story reste en `review` avec la mention « attente humaine » dans le journal. Notifier Anaël et continuer sur ce qui n'en dépend pas.
   - `humaine` : jamais confiée à un agent. Pas de `dev-story`, pas de changement de statut.
2. **Ressource à activer par Anaël** (Ollama, GPU, compte externe, poste réel) : ne pas improviser. Notifier, noter dans le journal, passer à la story suivante éligible. Les tests du parcours LLM (2.11, 6.6, 8.5, 8.6) remplacent l'appel réseau ; une story qui exigerait un vrai modèle s'arrête là.
3. **Modèle** : `dev-story` sur Sonnet, sauf les stories pivots marquées ★, sur Opus. Reviewer sur Opus. Deux échecs Sonnet sur une story : la reprendre sur Opus. Un échec Opus : story `blocked` dans le journal, notification, on continue.
4. **Pas d'imbrication** : seul l'orchestrateur lance des agents. Tous les appels sont bloquants et attendus. Un agent lancé en arrière-plan sans être attendu fait reprendre la story.
5. **Tests** : tests ciblés pendant le dev, suite complète une fois avant chaque fusion dans `main`, CI verte sur les trois OS avant de passer la story en `done`.
6. **Sorties externes** : push sur `main` et CI autorisés pendant le run. Tag et release GitHub seulement dans les stories de release (6.7, 9.5), suite complète verte sur les trois OS.

## Parallélisme à risque minimal

- **Au plus 3 stories en développement à la fois**, chacune dans son worktree (`dev-story` travaille en worktree et ne fusionne pas).
- **Une vague = des stories qui ne touchent ni le même module, ni le même fichier pivot.** Fichiers pivots : catalogue des `kind` et enveloppes (`contracts/`, `events/`), registre des ops de setup (`content`, AD-7), registre des volets du front (`web/static`), liste blanche des commandes (AD-4), `tools.toml`, `content/pipeline.yaml`, `content/explanations.yaml`, `config.py` (`Settings`). Un ajout d'une ligne dans un registre est toléré ; une refonte ne l'est pas.
- **La dépendance commande** : une story ne part qu'une fois toutes ses dépendances en `done` (colonne « Après »).
- **Intégration en série**, dans l'ordre de la vague : rebase de la branche sur `main`, tests ciblés, suite complète, fusion, push, CI. Puis seulement la branche suivante. Conflit trivial (ajout dans un registre) : l'orchestrateur le résout. Conflit de fond : `dev-story` sur Opus refait le rebase, puis nouveau `second-avis`.
- **Chevauchement** : la revue d'une story peut tourner pendant que les autres de sa vague se développent. La vague suivante peut démarrer story par story, dès que les dépendances de chacune sont en `done`. Il n'y a pas besoin d'attendre la fin de la vague.
- Une story en échec ne bloque que ses dépendantes. Les autres continuent.

## Sprint 1 — v0.1 (Epics 1 à 6)

Ordre conseillé par vagues. ★ = story pivot, `dev-story` sur Opus.

| Vague | Stories en parallèle | Après |
|---|---|---|
| V0 | 1.1 ★ | — |
| V1 | 1.2 · 1.4 | 1.1 |
| V2 | 1.3 · 2.1 ★ · 1.6 | 1.3 ← 1.2 ; 2.1 ← 1.4 (`procs`) ; 1.6 ← 1.4 (`tools.toml`) |
| V3 | 1.5 · 2.2 ★ · 1.7 | 1.5 ← 1.3, 1.4 ; 2.2 ← 1.2, 2.1 ; 1.7 ← 1.6 |
| V4 | 2.3 · 2.6 ★ · 2.11 | 2.3 ← 1.3, 2.2 ; 2.6 ← 2.1, 2.2 ; 2.11 ← 2.1 |
| V5 | 2.4 · 2.7 · 3.1 ★ | 2.4 ← 2.2, 2.3 ; 2.7 ← 2.3, 2.6 ; 3.1 ← 2.1, 2.2 |
| V6 | 2.5 · 3.2 · 4.1 | 2.5 ← 2.4 ; 3.2 ← 3.1, 2.6 ; 4.1 ← 2.6 |
| V7 | 2.8 · 3.3 · 4.2 | 2.8 ← 2.5, 2.3 ; 3.3 ← 3.2, 2.3 ; 4.2 ← 1.2, 4.1 |
| V8 | 2.9 · 3.4 · 4.3 ★ | 2.9 ← 2.8 ; 3.4 ← 3.2 ; 4.3 ← 3.1, 2.2 |
| V9 | 2.10 · 3.5 · 4.4 | 2.10 ← 2.7, 2.8, 3.3 ; 3.5 ← 3.1 ; 4.4 ← 4.2, 4.3 |
| V10 | 4.5 · 5.1 | 4.5 ← 4.3, 2.4 ; 5.1 ← 3.4 (registre d'ops) |
| V11 | 4.6 · 5.2 | 4.6 ← 4.1, 4.2 ; 5.2 ← 4.1, 4.2, 2.6 |
| V12 | 4.7 · 5.3 | 4.7 ← 4.2 ; 5.3 ← 5.2, 2.7 |
| V13 | 5.4 · 6.1 | 5.4 ← 5.2 ; 6.1 ← 2.3, 1.5, 4.2 |
| V14 | 5.5 · 6.4 · 6.6 | 5.5 ← 5.3 ; 6.4 ← 6.1, 4.3 ; 6.6 ← 2.11, 2.2 |
| V15 | 5.6 · 6.2 · 6.5 | 5.6 ← 5.1, 5.5 ; 6.2 ← 6.1, 4.5, 4.6, 3.4 ; 6.5 ← 4.7 |
| V16 | 5.7 · 6.3 | 5.7 ← 5.6, 3.5 ; 6.3 ← 6.2 |
| V17 | 5.8 | 5.7 |
| V18 | 6.7 (mixte) | toutes les stories `dev` des Epics 1 à 6 |

Ligne de coupe v0.1 (epics.md) : en cas de retard ou d'échec, on coupe d'abord 6.6, puis 5.8, puis 6.4. Une story coupée reste en `backlog` et passe au jalon suivant. Couper demande l'accord d'Anaël : la proposer par notification, sans l'appliquer seul.

**6.7** : l'agent prépare la release v0.1.0 (version, notes, README), puis la publie : tag annoté et release GitHub. La story reste en `review` jusqu'au test de SM-1 à SM-4 par Anaël et deux collègues. Notifier Anaël, puis enchaîner sur le Sprint 2.

## Sprint 2 — v0.2 (Epics 7 à 9), file de relais

`content/pipeline.yaml` est le pivot de l'Epic 8 : les stories qui y ajoutent un job (8.1, 8.3, 8.4, 8.6) passent en série et se combinent en parallèle avec l'Epic 9.

| Vague | Stories en parallèle | Après |
|---|---|---|
| W1 | 7.1 ★ · 8.2 · 9.1 | 7.1 ← 1.4, 1.6 ; 8.2 ← 1.2 ; 9.1 ← 2.3 |
| W2 | 7.2 · 7.4 ★ · 9.4 | 7.2 ← 7.1 ; 7.4 ← 7.1, 3.1 ; 9.4 ← 2.10 |
| W3 | 7.3 · 7.5 · 9.2 | 7.3 ← 7.1, 3.5 ; 7.5 ← 7.4 ; 9.2 ← 9.1 |
| W4 | 7.6 · 8.1 · 9.3 | 7.6 ← 7.4 ; 8.1 ← 7.4 ; 9.3 ← 6.1 |
| W5 | 8.3 | 8.1, 8.2 |
| W6 | 8.4 · 8.5 | 8.4 ← 8.3 ; 8.5 ← 8.3 |
| W7 | 8.6 | 8.4 |
| W8 | 9.5 (mixte) | Epics 7 à 9 en `done` |

**9.5** : la mesure des 45 s et SM-9 reviennent à Anaël. L'agent prépare tout et publie la release v0.2.0 seulement si la mesure a été faite. Sinon, il s'arrête et notifie Anaël.

Après le Sprint 2, sans retour d'Anaël : arrêt du run et notification. Les Epics 10 et 11 demandent d'abord l'UX de la station 4.

## Journal

Une ligne par événement : date-heure · story · étape (dev, second-avis, review, fusion, CI, attente humaine, blocked) · résultat · commit.

- 2026-10-18 · — · sprint planning · `sprint-status.yaml` généré (80 stories en `backlog`), plan écrit · —
- 2026-10-18 · — · commit · artefacts BMAD et skills commités sur main · 9e60489
- 2026-10-18 · 1.1 · dev · lancé (dev-story Opus, worktree) · —
- 2026-10-18 · 1.1 · dev · fini, 61 tests verts sous Windows · 08f41f5
- 2026-10-18 · 1.1 · second-avis · 3 medium, 5 low · —
- 2026-10-18 · 1.1 · review · 4 medium corrigés (dont DNS du hook d'audit), point 8 reporté à 1.4 (`--group chain` en CI) · 413664e
- 2026-10-18 · 1.1 · fusion · ff sur main, suite complète 80 passed · 413664e
- 2026-10-18 · 1.1 · CI · verte sur les trois OS, story done · 0429d97
- 2026-10-18 · 1.2, 1.4 · dev · vague V1 lancée (dev-story Sonnet, worktrees) · —
- 2026-10-18 · 1.2 · dev · fini, 94 tests, CI verte sur la branche · c19fdc1
- 2026-10-18 · 1.4 · dev · fini, 126 tests (gitleaks absent du poste, signalé missing) · 6e81819
- 2026-10-18 · 1.2 · second-avis · 2 medium, 5 low · —
- 2026-10-18 · 1.2 · review · 6 corrigés (verrou atomique, OSError, second lancement sans écriture…), vivacité par pid reportée · 6d1c425
- 2026-10-18 · 1.2 · fusion · ff sur main, suite complète 100 passed · 6d1c425
- 2026-10-18 · 1.4 · second-avis · 1 high (terminate_tree n'arrête pas l'arbre si le chef est sorti), 2 medium, 5 low · —
- 2026-10-18 · 1.2 · CI · verte sur les trois OS, story done · 522f9a3
- 2026-10-18 · 1.3 · dev · lancé (dev-story Sonnet, worktree) · —
- 2026-10-18 · 1.4 · review · rebase sur main (config.py unifié sur resolved_data_dir), high corrigé (arrêt d'arbre borné, test enfant+petit-enfant), Job Object Windows reporté à procs.spawn · 78c397a
- 2026-10-18 · 1.4 · fusion · ff sur main, suite complète 150 passed, CI branche verte sur les trois OS · 78c397a
- 2026-10-18 · 1.3 · dev · fini, 120 tests (exclusion des licences OFL du contrôle AD-13 (2)) · 3dcd853
- 2026-10-18 · 2.1, 1.6 · dev · lancés (2.1 dev-story Opus ★, 1.6 Sonnet), 1.3 en revue · —
- 2026-10-18 · 1.3 · second-avis · 2 medium (fetch sans délai, désactivation des actions sans effet réel), 3 low · —
- 2026-10-18 · 1.3 · review · rebase propre, 3 medium corrigés (délai du point de vie, test JS sous Node, contraste du lien d'évitement en sombre + test WCAG) · b9dcac0
- 2026-10-18 · 1.3 · fusion · ff sur main, suite complète 175 passed, CI branche verte sur les trois OS, story done · b9dcac0
- 2026-10-18 · 1.5 · dev · lancé (dev-story Sonnet, worktree) · —
- 2026-10-18 · 1.6 · dev · fini, 165 tests dont 15 en simulation PowerShell 5.1 ; parcours réel (poste Windows non admin, proxy, 10 min) à vérifier par Anaël · 543ef4c
- 2026-10-18 · 1.6 · second-avis · 5 medium (barre de progression, proxy de l'amorçage et d'uv, voie iex cassée en simulation, GPO), 2 low · —
- 2026-10-18 · 1.5 · dev · fini, 194 tests (sans SSE, redirection / → /diagnostic au premier lancement) · 98efad4
- 2026-10-18 · 1.6 · review · rebase propre, 7 constats corrigés (proxy amorçage et uv, voie iex testée, GPO, dossier app protégé) · b5eb587
- 2026-10-18 · 1.6 · CI · rouge sous Windows seulement (sortie PowerShell en page OEM 437 dans 3 tests) ; renvoyé au reviewer · b5eb587
- 2026-10-18 · 1.5 · second-avis · 10 low, aucun high/medium · —
- 2026-10-18 · 2.1 · dev · fini, 192 tests, CI branche verte sur les trois OS (empreintes identiques) · a3274bb
- 2026-10-18 · 2.1 · second-avis · 2 medium prouvés (ignore global XDG non isolé → empreinte, confinement .git contournable sous Windows), 7 low · —
- 2026-10-18 · 1.6 · CI · tests PowerShell forcés en UTF-8, CI branche verte sur les trois OS · 95c0cf9
- 2026-10-18 · 1.6 · fusion · ff sur main, suite complète 195 passed, story done ; vérification sur vrai poste Windows non admin (8 points, section Revue de la spec) en attente d'Anaël · 95c0cf9
- 2026-10-18 · 1.5 · review · 5 low corrigés, aucun medium ; diagnostic_seen à ajouter à AD-5 · c72d1c4
- 2026-10-18 · 1.7 · dev · lancé (dev-story Sonnet, worktree) · —
- 2026-10-18 · 1.5 · fusion · rebase sur 5a51a2a par l'orchestrateur, suite complète 219 passed, CI branche verte sur les trois OS, ff sur main, story done · 0ec4010
- 2026-10-18 · 2.1 · review · 2 rebases (conflit trivial contracts), 3 medium corrigés (ignore/attributs globaux isolés, confinement .git normalisé, étape CI autocrlf qui prouvait à vide), 4 low corrigés ; liens de l'apprenant hors espace reportés à 2.2 · 836eb0d
- 2026-10-18 · 2.1 · fusion · ff sur main, suite complète 272 passed / 2 skipped, CI branche verte sur les trois OS, story done · 836eb0d
- 2026-10-18 · 2.2, 2.11 · dev · lancés (2.2 dev-story Opus ★, 2.11 Sonnet) ; 1.7 en dev · —
- 2026-10-18 · 1.7 · dev · fini, CI verte (installation réelle sur runners ubuntu et macos, shellcheck) · 7f4c23f
- 2026-10-18 · 2.11 · dev · fini, 289 tests, CI verte sur les trois OS, sans réseau ni modèle ; httpx 0.28.1 à ajouter à la table Stack · 23ea199
- 2026-10-18 · 1.7 · second-avis · aucun high, 1 medium/low (voie zip sans provisionnement git, idem install.ps1), 5 low · —
- 2026-10-18 · 2.11 · second-avis · 4 medium (allowed_endpoints contrôlé contre lui-même, AD-13 non imposé au gabarit, chemin httpx jamais testé, tests hors venv verrouillé), 4 low · —
- 2026-10-18 · 2.11 · review · 3 medium corrigés (test loopback par nom d'hôte, tests du gabarit en uv --offline --frozen sur cache préchargé en CI, chemin httpx exécuté), AD-13 des tests du gabarit via toolrun reporté à la station 1 · c2d4573
- 2026-10-18 · 2.11 · fusion · ff sur main, suite complète verte, CI branche verte sur les trois OS, story done · c2d4573
- 2026-10-18 · — · décision pour Anaël · ajouter httpx==0.28.1 à la table Stack du spine et au test de cohérence AD-16 ; diagnostic_seen à ajouter à AD-5 · —
- 2026-10-18 · 1.7 · review · rebase (conflit ci.yml trivial), medium XDG_DATA_HOME sous macOS corrigé, avertissement voie zip sans git (sh et ps1), échange sûr de l'app, délais réseau · ba13fd2
- 2026-10-18 · 2.2 · dev · fini, 316 tests, CI verte sur les trois OS · 9ba966f
- 2026-10-18 · 2.2 · second-avis · 1 high prouvé (close() laisse l'opération tourner → deux écrivains à la réouverture), 2 medium, 5 low · —
- 2026-10-18 · 1.7 · fusion · rebase sur 221000e par l'orchestrateur, suite complète 289 passed / 33 skipped, CI branche verte (5 jobs dont install.sh réel), ff sur main, story done ; Epic 1 done ; vérification poste réel macOS/Linux (9 points) en attente d'Anaël · 8df335e
- 2026-10-18 · — · décision Anaël · relais Sprint 2 autorisé pendant la revue de 2.2 (stories éligibles) · —
- 2026-10-18 · 7.1, 8.2 · dev · lancés (7.1 dev-story Opus ★, 8.2 Sonnet) ; 2.2 en revue · —
- 2026-10-18 · 2.2 · review · 2 rebases sans conflit, high corrigé (réouverture refusée en 409 tant que l'ancien fil tourne, veille LRU au repos d'abord), 2 medium et 5 low corrigés ; interruption de l'opération à la veille reportée à 2.4 · e5eb028
- 2026-10-18 · 2.2 · fusion · ff sur main, suite complète verte, CI branche verte sur les trois OS, story done · e5eb028
- 2026-10-18 · 2.3 · dev · lancé (dev-story Sonnet) ; 2.6 ★ et 3.1 ★ éligibles, en attente d'un créneau (7.1 et 8.2 en dev) · —
- 2026-10-18 · 8.2 · dev · fini, 38 tests dont pip-audit réel sur le serveur local, CI verte · f076b19
- 2026-10-18 · 2.6 · dev · lancé (dev-story Opus ★) · —
- 2026-10-18 · 8.2 · second-avis · 1 medium (corps lu en entier avant la limite de 64 Ko sur route publique), 4 low dont faux positif version locale · —
- 2026-10-18 · 2.3 · dev · fini, 354 tests, CI verte ; rendu réel à voir dans un navigateur · 35841d3
- 2026-10-18 · 3.1 · dev · lancé (dev-story Opus ★) · —
- 2026-10-18 · 2.3 · second-avis · 2 medium (gabarits listés au catalogue, critères DOM testés par grep), 4 low ; décision orchestrateur : scénarios gabarit-* internes, masqués du catalogue · —
- 2026-10-18 · 8.2 · review · rebase (conflit app.py trivial), medium corrigé (corps borné au flux, Origin étrangère refusée), 4 low corrigés (échec fermé, partie locale, extrait atomique) · 1db409a
- 2026-10-18 · 8.2 · fusion · ff sur main, suite complète 386 passed / 34 skipped, CI branche verte, story done · 1db409a
- 2026-10-18 · 7.1 · dev · fini, CI verte sur 6 jobs (install.ps1 réel ajouté), garde réseau .pth dans le venv du gabarit, branchement toolrun reporté à 7.2 · c0d474b
- 2026-10-18 · 7.1 · second-avis · 2 medium prouvés (garde réseau : nom 127.* non résolu autorisé, sendto UDP non audité), 7 low · —
- 2026-10-18 · 2.6 · dev · fini, 389 tests, CI verte ; placement par génération, indépendant des refs · 9dd49eb
- 2026-10-18 · 3.1 · dev · fini, 355 tests, CI verte, 4 empreintes de référence régénérées (github.json inclus) · 61f0532
- 2026-10-18 · 3.1 · second-avis · 1 medium (refresh seulement au setup), 8 low ; décision pour Anaël : une approbation survit-elle à un nouveau push ? (défaut actuel : oui, comme GitHub sans dismiss_stale_reviews) · —
- 2026-10-18 · 2.3 · review · rebase sur de2df2c, 2 medium corrigés (scénarios internes catalogue: false, tests DOM réels sur doublure minidom), 4 low · de83bb3
- 2026-10-18 · 2.6 · second-avis · 1 medium prouvé (placement par date : un commit antidaté déplace les existants), 6 low · —
- 2026-10-18 · 2.3 · fusion · ff sur main, suite complète 409 passed / 36 skipped, CI branche verte, story done ; rendu navigateur à vérifier par Anaël · de83bb3
- 2026-10-18 · 2.4, 9.1 · dev · lancés (Sonnet) · —
- 2026-10-18 19:58 · 9.1 · dev · fini, 412 tests, CI verte · 5bf1f3d
- 2026-10-18 19:58 · — · convention · à partir d'ici chaque ligne du journal porte l'heure (HH:MM) pour l'estimation de fin · —
- 2026-10-18 19:56 · 7.1 · review · 2 rebases sans conflit, 2 medium corrigés (garde réseau : IP loopback littérale seulement, sendto/DNS refusés), 3 low corrigés · 159685f
- 2026-10-18 19:56 · 7.1 · fusion · ff sur main, suite complète verte, CI branche verte sur 6 jobs, story done · 159685f
- 2026-10-18 19:56 · 7.2 · dev · lancé (dev-story Sonnet) · —
- 2026-10-18 19:56 · 7.2 · report · non lancé : même module que 2.4 (terminal, liste blanche AD-4), attend la fusion de 2.4 · —
- 2026-10-18 19:59 · 9.1 · second-avis · 2 medium (hauteurs CSS : min-height et bandeau sur deux lignes font défiler la page), 4 low · —
