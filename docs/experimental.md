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

## clarity (rewrite, review, interview)

- **Dépôt** : [addyosmani/clarity](https://github.com/addyosmani/clarity) · **Commit** : `e27ceeff60368cf6966b4ea00a5b9b36418ee9a0` · **Licence** : MIT
- **Problème visé** : des textes utiles et précis, sans fait inventé.
- **Quand** : sur un texte public réel (LinkedIn, README). Demande Anaël : juger les textes.
- **Protocole** : 1. lire le skill (7,7 k caractères, sans hook ni réseau) ; 2. prendre deux textes publics de longueur différente ; 3. `rewrite` sur chacun ; 4. `review` sur un troisième ; 5. relire avec le texte d'origine à côté et noter toute invention ; 6. lire le résultat de T11 avant de conclure.
- **Observer** : faits inventés (zéro toléré), tics ajoutés ou retirés, fidélité à la voix d'Anaël, en français.
- **Sortie** : stable si aucune invention et textes préférés à l'aveugle ; écarté si l'un des deux échoue.
- **Veille** : skill d'écriture à invocation manuelle, sans hook ni réseau. Résultat provisoire de [T11](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T11-ecriture) : aucun fait inventé selon le juge, chiffres et renvois intacts, 0,11 $ par réécriture ; les textes de départ avaient trop peu de défauts pour départager, la note à l'aveugle d'Anaël tranchera.
- **À noter** : le dépôt publie un protocole d'évaluation (`evals/JUDGE.md`, portes dures sur les faits inventés), sans résultats chiffrés.

## humanizer

- **Dépôt** : [blader/humanizer](https://github.com/blader/humanizer) · **Commit** : `8c307f367c91bd974002f10f2be2965d642c13df` · **Licence** : MIT
- **Problème visé** : retirer les tics d'un texte écrit par une IA.
- **Quand** : à la demande, sur des textes LinkedIn. Seul ou après clarity selon T11. Demande Anaël : juger les textes.
- **Protocole** : 1. lire le skill et ses règles ; 2. reprendre les textes de l'essai clarity ; 3. appliquer humanizer seul ; 4. l'appliquer après clarity ; 5. comparer à l'aveugle les quatre versions.
- **Observer** : tics renforcés plutôt que retirés, faits inventés, perte de précision.
- **Sortie** : garder à la demande si la version enchaînée bat clarity seul ; écarté sinon.
- **Veille** : « il renforce certains tics de rythme ». Résultat provisoire de [T11](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T11-ecriture) : aucun fait inventé, retire le gras décoratif et la moitié des exclamations, mais fond une liste à puces en phrase ; 0,13 $ par réécriture, et 0,31 $ enchaîné après clarity sans gain mesuré. La note à l'aveugle d'Anaël tranchera.

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
- **Quand** : selon la note à l'aveugle de T7. Demande Anaël : la note. Sans ses hooks ni sa télémétrie.
- **Protocole** : 1. lire le détecteur, désactiver hooks et télémétrie ; 2. l'exécuter sur deux pages de projets réels ; 3. noter les constats à l'aveugle ; 4. mesurer le temps d'exécution.
- **Observer** : constats utiles contre règle de la « palette crème » répétée, faux positifs.
- **Sortie** : garder à la demande si plus de la moitié des constats sont utiles ; écarté sinon.
- **Veille** : la skill coûte +15 % sans réduire les violations ; seul `detect` pourrait servir ([T7](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T7), clos par la note d'Anaël).

## hallmark

- **Dépôt** : [Nutlope/hallmark](https://github.com/Nutlope/hallmark) · **Commit** : `7ec868225c6caa040558c321ee0fefa0e73f83a8` · **Licence** : MIT
- **Problème visé** : la qualité visuelle d'une interface.
- **Quand** : selon la note à l'aveugle de T7. Flux interactif qui lance un sous-agent : **jamais en run autonome**.
- **Protocole** : 1. lire le skill et le sous-agent qu'il lance ; 2. SkillSpector (alertes CRITICAL attendues, à vérifier à la main) ; 3. essai dans un projet jetable sur une page ; 4. répondre aux questions du flux ; 5. noter le résultat à l'aveugle contre une version sans skill.
- **Observer** : surcoût, sous-agent lancé, qualité perçue.
- **Sortie** : garder à la demande si la note à l'aveugle est meilleure malgré le surcoût ; écarté sinon.
- **Veille** : « écarter » : +21 % de coût, aucune violation en moins ; seule la note d'Anaël pourrait le repêcher ([T7](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques/T7)).

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
