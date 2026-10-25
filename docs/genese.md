# D'où vient le kit : mesures, veille, tests

[← README](../README.md)

Le kit n'est pas parti d'une liste de bonnes pratiques. Il est né d'une facture, puis il a été mis à l'épreuve d'une veille et de 20 tests pratiques. Ses règles viennent de mesures sur de vrais projets, ou à défaut de sources publiées, dites comme telles. Ce qui n'a pas tenu à la mesure en est sorti.

## 1. La facture (10 au 16 octobre 2026)

Point de départ : 109 stories développées par agents sur trois projets Python, environ 1 850 $ d'équivalent API. Presque tout tournait sur Opus en effort high, avec un agent intermédiaire qui relançait un implémenteur puis quatre relecteurs.

Le script `mesurer_couts.py` a lu les transcriptions locales et montré où partait l'argent :
- le cache (lecture et écriture) fait environ 80 % du coût ;
- l'agent qui relance des agents pèse 36 à 47 % d'une story ;
- le coût d'une story suit, avec une corrélation de 0,86 à 0,97, le produit « pic de contexte × nombre d'appels » de ses agents ;
- le cache d'une heure coûte 28 à 30 % de plus pour la grande majorité des sous-agents, qui n'ont aucune expiration.

D'où les premières versions (0.1.0 à 0.3.x) :
- une chaîne sans imbrication : Sonnet code, Opus relit (à partir de la 0.2.0), avec un second avis Haiku avant la revue ;
- un lookup Haiku pour les recherches ;
- le contexte fixe réduit ;
- le script de mesure.

Sur une nuit autonome de 5 stories, la story médiane est passée de 16,57 $ avec l'ancien setup à environ 4 $ avec le kit, orchestration comprise, soit 4 fois moins (2,36 $ hors orchestration). Le détail est dans [les mesures](mesures.md).

## 2. La veille (24 octobre 2026)

Restait une question : les dizaines de plugins, skills et méthodes qui circulent pour Claude Code font-ils mieux ? La [veille agents de code](https://github.com/Aliquanto3/veille-agents-code) a examiné 47 dépôts et 6 articles sur 10 dimensions : méthode, design front, contexte et mémoire, coûts, routage, revue et sécurité, tests, orchestration, littérature, avis d'utilisateurs. La recherche s'appuie sur 142 sources, et ses affirmations porteuses ont été revérifiées.

Son premier constat : le natif de Claude Code couvre déjà l'essentiel. Mais une lecture ne tranche pas tout : un outil qui promet de « mieux relire » ou de « mieux designer » se mesure. D'où les tests.

## 3. Les tests (24 et 25 octobre 2026)

20 tests pratiques ont été menés sur les projets et les transcriptions d'Anaël, avec quelques règles tenues partout :
- **un critère écrit avant les essais** (par exemple « +0,5 point sur un écran que les règles n'ont pas vu », ou une marge de non-infériorité de 10 points) ;
- **un témoin** : l'option la plus simple, natif ou chaîne du kit, contre laquelle chaque outil est comparé ;
- **des défauts semés quand la vérité terrain manque** : mutants de cosmic-ray, défauts d'interface semés à la main par l'auteur, ce qui donne un majorant ;
- **une note humaine à l'aveugle** pour ce que les métriques ne voient pas (design, écriture), sous des lettres tirées au hasard, avec la correspondance gardée hors du dépôt ;
- **des intervalles de confiance**, par bootstrap apparié par story, et une analyse de puissance quand l'échantillon est petit ;
- **des outils tiers lus avant d'être installés**, passés à SkillSpector, épinglés à un commit et installés au niveau projet seulement.

Le coût des tests dont le montant est noté dépasse 135 $. Les résultats, scripts et données anonymisées sont publics, test par test, dans [`tests-pratiques/`](https://github.com/Aliquanto3/veille-agents-code/tree/main/tests-pratiques).

## 4. Ce que les tests ont ajouté au kit

| Version | Ajout | Mesure qui le justifie |
|---|---|---|
| 0.10.0 | Règles de convergence du reviewer ; consigne anti-mock de `dev-story` | Article d'Anthropic sur la revue de code ; MSR 2026 : 36 % des commits d'agents ajoutent des mocks |
| 0.11.0 | Listes `tools:` explicites ; alerte de dérapage | T1 : 8 outils rarement appelés pèsent 17,8 k tokens dans les définitions ; gain estimé à environ 11 k tokens par agent, pas encore mesuré en A contre B |
| 0.12.0 | Mutation guidée (expérimental) ; catalogue d'essais encadrés | T10b : 134 trous de test non équivalents bouchés sur 134, contre 59 % avec une simple consigne, pour 0,22 $ par story |
| 0.13.0 | Sous-agent `verif-front` dans un vrai navigateur (expérimental) | T12 : 22 défauts d'interface semés sur 25 trouvés, alors que pytest et axe-core n'en voient aucun ; 0,14 $ par vérification. Les défauts ont été semés par l'auteur du test : le taux est un majorant |
| 0.13.1 | CI sur Linux et Windows, `master` protégé | La 0.13.0 avait été fusionnée sans contrôle ; le premier passage sous Linux a révélé un processus orphelin |
| 0.14.0 | Petites stories sans cadrage BMAD (expérimental) | T13 bis : −73 % de coût, réussite égale à 10 points près |
| 0.14.1 | Fiches clarity, humanizer et hallmark retirées | T7 et T11 : sous l'option sans skill, à la note à l'aveugle |

## 5. Ce que les tests ont écarté

Les tests ont aussi servi à refuser des ajouts. Chacun des outils ci-dessous coûtait plus cher, compliquait la chaîne ou ne faisait pas mieux que le témoin :

- **Un relecteur d'une autre famille de modèles.** +6 points de défauts trouvés, non significatif (T5 élargi, 16 défauts semés).
- **La porte empirique.** Elle prouve qu'un défaut se reproduit, pas qu'il est réel : 0 faux constat éliminé sur 2 (T5).
- **Le verrouillage des tests pendant l'implémentation.** Aucune triche observée sur 40 runs (T4 bis).
- **Le conseil d'un modèle plus fort.** `/advisor` ne fait pas mieux que Sonnet seul (T6).
- **Les modèles locaux au quotidien.** Haiku fait mieux pour le lookup (T8).
- **Les modèles de décision.** Jev ne prédit pas le dérapage d'une story : 339 stories, rien à brancher (T9 élargi).
- **Une voie « story légère » façon OpenSpec.** −46 % de coût, mais −10 points de réussite (T13).
- **Le cache d'une heure.** Plus cher pour la plupart des sous-agents (mesures de départ).
- **Les skills de design impeccable et hallmark.** Notées en dessous de l'option sans skill (T7).
- **Les skills de réécriture clarity et humanizer.** La consigne simple « réécris plus clair » fait au moins aussi bien, pour 2 à 5 fois moins cher (T11).
- **Un fichier de règles de design maison.** +0,89 point sur l'écran dont viennent les règles, +0,11 seulement sur un écran nouveau (T7 ter).

## 6. La conclusion

**Aucun des 47 dépôts examinés ne fait strictement mieux que l'option la plus simple de la configuration étudiée** : Claude Code natif, ou BMAD avec le kit. Quand il n'y a pas de gagnant strict, le kit garde l'option la plus simple.

Les gagnants stricts retenus par le bilan de la veille (au moins aussi bons et moins chers, ou plus simples, sur ces données) :
- la chaîne du kit contre `bmad-build-auto` (mesures de départ, une story rejouée trois fois) ;
- la réduction du contexte fixe contre la compression des sorties ;
- Haiku contre les modèles locaux pour le lookup ;
- Sonnet seul contre Sonnet assisté d'un conseiller ;
- la mutation guidée contre une consigne seule.

Ce qui fait baisser la facture n'est pas un outil de plus. C'est **moins de contexte, moins d'appels, le bon modèle à chaque étape**, et une mesure avant chaque changement.

## Limites

- **Échantillon** : un seul développeur et des projets Python pour l'essentiel ; rien n'est encore mesuré sur d'autres langages.
- **Notes humaines** : un seul juge, qui est aussi l'auteur des règles évaluées en T7 ter.
- **Tests conclus « à 10 points près »** : ils n'excluent pas un écart plus petit.
- **Éléments expérimentaux** (`verif-front`, aiguillage, mutation guidée) : ils ont encore un critère de passage en stable à remplir en production (voir le [catalogue d'essais](experimental.md)).
