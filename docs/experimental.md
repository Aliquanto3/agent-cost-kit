# Catalogue d'essais expérimentaux

Outils que la [veille](https://github.com/Aliquanto3/veille-agents-code) a laissés « à trancher » : ils ne se mesurent qu'avec quelqu'un devant l'écran (questions posées à l'auteur, note à l'aveugle, observation d'un run). **Expérimental et optionnel** : rien ici ne change la chaîne par défaut (dev-story, second-avis, reviewer). Le skill `/agent-cost-kit:essai-outil <nom>` (invocation manuelle) guide l'essai fiche par fiche ; les retours vont dans `mesures/essais/`.

## Règle d'essai

Cinq contrôles avant tout essai, sans exception :
1. **Lire avant d'installer** : `SKILL.md`, hooks, scripts, manifestes, `.mcp.json`, dans un dossier neuf hors du dépôt, sans rien exécuter.
2. **SkillSpector `--no-llm`** : garde-fou bruyant (faux positifs fréquents), jamais une preuve d'innocuité.
3. **Version épinglée** : le commit de la fiche, pas une branche.
4. **Contexte mesuré** avant et après (`/context`, `claude plugin details <nom>`).
5. **Niveau projet, avec confirmation** : jamais dans `~/.claude/`, et désinstallation si le verdict n'est pas favorable.

Absents exprès : les packs de méthode qui revendiquent les étapes de BMAD (Superpowers, agent-skills d'addyosmani, ECC). Les raisons sont dans la veille.

Commits et licences relevés le 2026-10-25. Un nouveau commit n'est pas essayé sans nouvelle lecture.

## grill-with-docs

- **Dépôt** : [mattpocock/skills](https://github.com/mattpocock/skills), `skills/engineering/grill-with-docs` · **Commit** : `5beb35b040e3de97e54fa9e386d7e42d15c295c2` · **Licence** : MIT
- **Problème visé** : un PRD flou ; le skill interroge l'auteur avant d'écrire.
- **Quand** : avant un brief ou un PRD dont l'idée n'est pas arrêtée. Demande Anaël : répondre aux questions.
- **Protocole** : 1. lire la fiche du skill (environ 2,3 k caractères, sans hook) ; 2. choisir une idée floue réelle ; 3. lancer le skill en invocation manuelle, dans un projet de bac à sable ; 4. répondre aux questions jusqu'au bout ; 5. comparer le PRD obtenu avec ce que `bmad-prd` ou `bmad-forge-idea` donnent seuls.
- **Observer** : nombre et pertinence des questions, doublon avec `bmad-forge-idea`, conflit avec BMAD, tokens consommés.
- **Sortie** : stable si les questions font apparaître au moins une décision que BMAD seul laissait implicite ; écarté s'il double `bmad-forge-idea`.
- **Veille** : jugé « à intégrer », non testé, car presque gratuit à essayer.

## AOS Dashboard

- **Dépôt** : [tomtomsatnav/agent-orchestration-standard](https://github.com/tomtomsatnav/agent-orchestration-standard) · **Commit** : `40d270774a275870e1b676b11e8074ec4a746b5f` · **Licence** : MIT
- **Problème visé** : l'alerte de conflit de fichiers entre agents d'un run parallèle (son seul apport neuf par rapport à `mesurer-couts`).
- **Quand** : pendant un run parallèle, en bac à sable. Demande Anaël : observer le run. Réserves : 19 déclarations de hook, toutes `"async": true`, sur 3 scripts Node (un processus par événement), port 4318 (celui de l'export OpenTelemetry), Git Bash et make sous Windows.
- **Protocole** : 1. lire `plugin/hooks/hooks.json`, les 3 scripts de hooks et le serveur ; 2. SkillSpector, puis noter la liste des hooks et des ports ; 3. installer dans un dépôt jetable, sur un port libre ; 4. lancer un petit run parallèle de deux stories qui touchent un même fichier ; 5. regarder si l'alerte de conflit arrive avant la fusion ; 6. mesurer la charge du poste et le contexte ajouté.
- **Observer** : alerte utile et à temps, ralentissement du poste, données qui sortent, collision de port.
- **Sortie** : garder à la demande si l'alerte précède le conflit sans ralentir le run ; écarté sinon.
- **Veille** : moniteur en lecture seule, une semaine d'existence, qui recoupe `mesurer-couts` ; « à essayer en bac à sable sur un run parallèle, après lecture des hooks et SkillSpector ». La veille compte 17 hooks ; le manifeste au commit épinglé en déclare 19.

## impeccable `detect`

- **Dépôt** : [pbakaus/impeccable](https://github.com/pbakaus/impeccable) · **Commit** : `936867543ac2576920d663cc9803597f6044f3ac` · **Licence** : Apache-2.0
- **Problème visé** : repérer les défauts de design d'une page (`impeccable detect <url>`), utilisable en CI.
- **Quand** : en CI d'un projet front, sur les pages servies par les tests, sans les hooks ni la télémétrie d'impeccable. La skill elle-même est écartée (voir plus bas) ; seul le détecteur reste à essayer.
- **Protocole** : 1. lire le détecteur, désactiver hooks et télémétrie ; 2. l'exécuter sur deux pages de projets réels ; 3. noter les constats à l'aveugle ; 4. mesurer le temps d'exécution.
- **Observer** : constats utiles contre règle de la « palette crème » répétée, faux positifs.
- **Sortie** : garder à la demande si plus de la moitié des constats sont utiles ; écarté sinon.
- **Veille** : la skill coûte +15 % sans réduire les violations, et la note à l'aveugle d'Anaël la place sous l'absence de skill (3,67 sur 5 contre 4,00, [T7](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T7)). Le détecteur a repéré un des deux contours colorés de bloc d'erreurs reprochés par Anaël, mais surtout la règle « palette crème » ; en [T7 ter](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T7ter-design-md), il a signalé plus de motifs sur les rendus que la note préférait.

## diagram-design

- **Dépôt** : [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) · **Commit** : `0b9b10cab3dbf695642fa1a6c4b4f60df9083689` · **Licence** : MIT
- **Problème visé** : un diagramme soigné pour un livrable client ; Mermaid reste le format de la doc versionnée.
- **Quand** : un livrable client à la demande.
- **Protocole** : 1. lire le skill ; 2. choisir un schéma réel de livrable ; 3. le générer avec le skill ; 4. le comparer à la version Mermaid ; 5. vérifier l'export (format, taille).
- **Observer** : lisibilité, retouches manuelles restantes, taille du contexte.
- **Sortie** : garder à la demande si le client peut le recevoir sans retouche ; écarté sinon.
- **Veille** : « à intégrer » à la demande, non testé, sans enjeu de coût.

## hyperframes

- **Dépôt** : [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) · **Commit** : `7bc363c87c8524e547c5b759d2471d96183b67f3` · **Licence** : Apache-2.0
- **Problème visé** : une vidéo de démo produite par code.
- **Quand** : une vidéo de démo à la demande. Windows non vérifié.
- **Protocole** : 1. lire le dépôt, noter les dépendances natives et les appels réseau ; 2. SkillSpector ; 3. installer en projet jetable et vérifier que le rendu fonctionne sous Windows ; 4. produire une démo de 15 secondes ; 5. noter le temps de rendu et le résultat.
- **Observer** : fonctionnement sous Windows, dépendances à installer, qualité de la vidéo.
- **Sortie** : garder à la demande si le rendu marche sous Windows sans bricolage ; écarté sinon.
- **Veille** : « à intégrer » à la demande ; Windows non vérifié.

## Claude Design (natif)

- **Dépôt** : natif, research preview · **Commit** : n/a · **Licence** : n/a
- **Problème visé** : le cadrage UX par maquette.
- **Quand** : au prochain cadrage UX. Demande Anaël : la session.
- **Protocole** : 1. ouvrir Claude Design sur un cadrage réel ; 2. produire une maquette ; 3. la comparer à `bmad-ux` ; 4. noter le temps passé et ce qui est repris dans `DESIGN.md`.
- **Observer** : gain de temps, maquette réutilisable, doublon avec `bmad-ux`.
- **Sortie** : garder à la demande si la maquette alimente `DESIGN.md` ; écarté sinon.
- **Veille** : « à trancher » : research preview inclus dans Max, non évalué.

## Style Concise (natif)

- **Dépôt** : natif (`/output-style`) · **Commit** : n/a · **Licence** : n/a
- **Problème visé** : des réponses plus courtes, donc moins de tokens de sortie.
- **Quand** : une semaine d'usage normal. Demande Anaël : le ressenti.
- **Protocole** : 1. noter l'output d'une semaine habituelle (`/agent-cost-kit:bilan-tokens`) ; 2. activer le style Concise par `/output-style` ; 3. travailler une semaine ; 4. refaire le bilan ; 5. noter les cas où une réponse trop courte a coûté une relance.
- **Observer** : output par jour, relances, perte de détail dans les revues.
- **Sortie** : stable si l'output baisse sans relance en plus ; écarté sinon.
- **Veille** : « à intégrer » : couvre l'essentiel d'i-have-adhd sans dépendance.

## verif-front

- **Dépôt** : modèle du kit (`modeles/agents/verif-front.md`) + `@playwright/mcp` 0.0.83 épinglé · **Commit** : n/a (version npm épinglée) · **Licence** : Apache-2.0
- **Problème visé** : les défauts d'interface que ni pytest ni axe-core ne voient (rendu, mobile, clavier, ordre des étapes).
- **Quand** : une story qui change un écran, dans un projet front avec Node.js et Chromium. Demande Anaël : confirmer les FAIL `spec`.
- **Protocole** : 1. copier le modèle par `cost-kit-install` (étape « Projet front ») ; 2. après `dev-story`, démarrer l'application et lancer `verif-front` avec l'URL et la spec ; 3. ne renvoyer à `dev-story` que les FAIL `spec` ; 4. noter pour chaque FAIL s'il est confirmé ou faux ; détail dans `docs/verif-front.md`.
- **Observer** : FAIL `spec` confirmés, faux positifs, FAIL `hors-spec` utiles, coût et durée par vérification.
- **Sortie** : sur les 10 premières stories front, stable si au moins un vrai défaut trouvé et au plus un faux positif ; retiré sinon.
- **Veille** : [T12](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T12-front) : 22 défauts semés sur 25 trouvés, 0 faux positif sur 8 versions sans défaut, 0,141 $ et 60 s ; aucun gain mesuré dans la boucle de développement.

## aiguillage sans cadrage

- **Dépôt** : règle du kit (`docs/aiguillage-stories.md`), pas d'outil tiers · **Commit** : n/a · **Licence** : MIT (celle du kit)
- **Problème visé** : le cadrage BMAD complet d'une petite story coûte environ 1 $ de plus que le développement, sans gain de réussite mesuré.
- **Quand** : un projet BMAD, une petite story dont l'entrée de `epics.md` a au moins deux critères Given/When/Then, au plus 3 fichiers source, et nomme ce qui est à créer. Pas pour une story à risque ni transverse.
- **Protocole** : 1. l'orchestrateur applique la règle avant `dev-story` ; 2. si elle est remplie, `dev-story` reçoit l'entrée de `epics.md` telle quelle, sans fichier de spec ; 3. journaliser l'étape `dev` avec la mention `lancé, sans cadrage` ; 4. `second-avis` et `reviewer` comme d'habitude.
- **Observer** : constats Important du reviewer, passes de revue, reprises de `dev-story`, coût par story (`mesurer-couts`), à comparer aux stories cadrées.
- **Sortie** : après au moins 10 stories aiguillées, stable si elles n'ont pas plus de constats Important ni de reprises que les stories cadrées comparables ; sinon règle retirée ou restreinte.
- **Veille** : [T13](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T13-story-legere) : voie légère à −46 % de coût mais 10 points de moins, écartée ; [T13 bis](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T13bis-sans-cadrage) : sans cadrage, −0,6 point (IC [−8,4 ; +7,4]) pour 73 % de moins, non-infériorité à 10 points seulement.

## Écartés après essai

Retirés du catalogue quand la veille a tranché contre eux. Ils ne s'essaient plus sans nouveau motif.

- **clarity** et **humanizer** ([T11](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T11-ecriture), 2026-10-25) : note à l'aveugle d'Anaël sur 24 réécritures. Sans skill 4,25 sur 5, clarity 4,17, clarity puis humanizer 4,17, humanizer 3,92. Une simple consigne « réécris plus clair » fait au moins aussi bien pour deux à cinq fois moins cher. Seul le mode réécriture de clarity a été testé, pas ses modes revue et interview. Versions essayées : [addyosmani/clarity](https://github.com/addyosmani/clarity) `e27ceeff60368cf6966b4ea00a5b9b36418ee9a0` (MIT), [blader/humanizer](https://github.com/blader/humanizer) `8c307f367c91bd974002f10f2be2965d642c13df` (MIT).
- **hallmark** ([T7](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T7), 2026-10-25) : note à l'aveugle 3,50 sur 5, contre 4,00 sans skill et 4,17 pour frontend-design, pour +21 % de coût. Son flux interactif ne convient pas aux runs autonomes. Version de la fiche retirée : [Nutlope/hallmark](https://github.com/Nutlope/hallmark) `7ec868225c6caa040558c321ee0fefa0e73f83a8` (MIT).
- **impeccable** (la skill, [T7](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T7)) : 3,67 sur 5, +15 % de coût. Son détecteur garde sa fiche ci-dessus.
