# agent-cost-kit

Un plugin Claude Code pour développer par agents en payant 4 à 5 fois moins, sans perdre en qualité de revue. Les choix du kit viennent de mesures sur 109 stories et environ 1 850 $ d'équivalent API ([détail](docs/mesures.md)). Ils ont ensuite été mis à l'épreuve d'une veille de 47 dépôts et de 20 tests pratiques : [d'où vient le kit et ce que les tests ont conclu](docs/genese.md).

![La bande couts-session au-dessus du prompt : coût, tokens lus et écrits, contexte, carbone, puis le tableau par modèle et par sous-agent](docs/demo.svg)

*English summary at the end.*

## Démarrer en 3 commandes

```
/plugin marketplace add Aliquanto3/agent-cost-kit
/plugin install agent-cost-kit@agent-cost-kit
/cost-kit-install
```

`/cost-kit-install` applique, avec votre accord et après un aperçu, les réglages qui économisent (pas d'imbrication d'agents, skills claude.ai désactivés, modèle Haiku 5.5), puis prépare le projet courant. Redémarrez ensuite Claude Code. Détail : [installation et contenu](docs/installation.md).

Pour voir en direct ce que coûte la session, au-dessus du prompt, le mod seul suffit :

```
/plugin install couts-session@agent-cost-kit
```

Le mod exige les mods de code de Claude Code, en accès anticipé : ajoutez `"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"` au bloc `env` de `~/.claude/settings.json`, puis redémarrez Claude Code. Sans cette variable, la bande ne s'affiche pas, sans message d'erreur. Testé avec Claude Code 2.1.280 et 2.1.306.

## Ce que vous obtenez

| Quoi | Pour quoi faire |
|---|---|
| 4 agents : `dev-story` (Sonnet), `second-avis` (Haiku), `reviewer` (Opus), `lookup` (Haiku) | Coder avec Sonnet, relire avec Haiku puis Opus, chercher avec Haiku. Aucun relecteur ne trouve tout seul. |
| Mod `couts-session` | Coût, tokens, contexte et carbone estimé de la session, par modèle et par sous-agent ([doc](docs/couts-session.md)). |
| `/agent-cost-kit:mesurer-couts` | Le coût réel de chaque agent et de chaque story, relu dans vos transcriptions locales, sans appel d'API ([doc](docs/mesurer-couts.md)). |
| `/agent-cost-kit:avancement-run` | La synthèse d'avancement d'un run autonome BMAD ([doc](docs/avancement-run.md)). |
| `scripts/menage_run.py` | Le ménage de clôture d'un run : worktrees, verrous et branches des stories fusionnées, en simulation par défaut ([doc](docs/menage-run.md)). |
| `/bilan-tokens` | Le bilan mensuel des tokens par modèle (coût API équivalent, impact ImpactIA ou EcoLogits), en page HTML, avec consolidation de plusieurs PC. |
| `bancs/` | Les protocoles pour refaire les mesures quand de nouveaux modèles sortent ([bancs/README.md](bancs/README.md)). |

## L'enchaînement par story

```
orchestrateur (Opus, medium) → dev-story (Sonnet) → second-avis (Haiku) → reviewer (Opus) → fusion
```

Chaque appel est bloquant, la revue tient en une passe par défaut (relancée seulement après correction d'un constat Important, medium ou high réel, 3 passes au plus), et un sous-agent ne lance jamais d'autre sous-agent.

Étape optionnelle et expérimentale, après dev-story et avant second-avis, pour une story qui crée ou réécrit un fichier source : la [mutation guidée](docs/mutation-guidee.md) (survivants de cosmic-ray montrés à un second appel `dev-story`).

Autre étape optionnelle et expérimentale, pour une story qui change un écran dans un projet où le modèle `verif-front` est installé : la [vérification dans le navigateur](docs/verif-front.md) après dev-story, correction seulement sur un FAIL de la spec.

Autre règle expérimentale, avant dev-story : une petite story bien décrite dans `epics.md` (au plus 3 fichiers source, au moins deux critères Given/When/Then, noms à créer), ni à risque ni transverse, part directement en développement, sans cadrage BMAD ; cadrage sinon ou dans le doute ([aiguillage](docs/aiguillage-stories.md)).

## Les cinq règles qui comptent

1. **Pas d'agent qui relance des agents.** L'agent intermédiaire pèse 36 à 47 % d'une story.
2. **Garder le cache des sous-agents à 5 min.** Le cache à 1 h coûte 28 à 30 % de plus, et 78 à 86 % des sous-agents n'ont aucune expiration.
3. **Compter les appels et le contexte lu.** Le cache représente environ 80 % du coût ; sur Opus, une story coûte 0,31 à 0,36 $ par million de « pic de contexte × appels ».
4. **Réduire le contexte fixe.** Couper les skills claude.ai retire 8,4 k tokens à chaque agent.
5. **Sonnet pour coder, Opus pour relire, Haiku pour le second avis.** Sur une nuit de 5 stories : 2,36 $ par story en médiane, contre 16,57 $ avec l'ancien setup.

Mesurez votre point de départ avant de changer de méthode : `/agent-cost-kit:mesurer-couts`.

## Pour aller plus loin

- [D'où vient le kit](docs/genese.md) : la facture de départ, la veille, les 20 tests, ce qui a été ajouté et ce qui a été écarté.
- [Les mesures](docs/mesures.md) : corpus, revue, setup mesuré en série, ce qui dépend de votre projet, limites.
- [Mesurer les coûts et l'empreinte](docs/mesurer-couts.md) : le script, les pièges du calcul, l'impact (ImpactIA expérimental, EcoLogits), la mise à jour quand de nouveaux modèles sortent.
- [Bilan mensuel des tokens](docs/bilan-tokens.md) : le script, la page HTML, la consolidation de plusieurs PC.
- [Pièges vus en run autonome](docs/pieges-runs.md) : tests instables sous charge, extension SQLite, push refusé, `python` nu sous Windows.
- [Catalogue d'essais](docs/experimental.md) (expérimental) : outils de la veille à essayer avec le skill `/agent-cost-kit:essai-outil`, commit épinglé et critère de sortie par fiche.
- [Mutation guidée](docs/mutation-guidee.md) (expérimental) : étape optionnelle après dev-story, script `scripts/mutation_story.py`, chiffres de la veille (T4, T10, T10b).
- [Vérification front](docs/verif-front.md) (expérimental) : sous-agent `verif-front` (Playwright MCP) copié par l'installation, chiffres de la veille (T12).
- [Aiguillage sans cadrage](docs/aiguillage-stories.md) (expérimental) : règle de l'orchestrateur pour les petites stories, chiffres de la veille (T13, T13 bis).
- [Historique des versions](CHANGELOG.md).

**Contribuer** : la CI lance les tests sur Linux et Windows et valide le plugin (`claude plugin validate . --strict`) à chaque PR ; `master` est protégé, une PR ne fusionne que si la CI est verte.

## English summary

A Claude Code plugin for agent-based development at a fraction of the cost. Measured on 3 projects, 109 stories and about $1,850 of API-equivalent spend: cache reads and writes make up about 80 % of the cost, an agent that spawns agents takes 36 to 47 % of a story, and a 1-hour subagent cache costs about 30 % more for most subagents. The kit ships Sonnet for coding, a Haiku second opinion, an Opus reviewer, a Haiku lookup agent, a cost-measurement script that reads local transcripts, and a live cost band above the prompt (`couts-session`). Its rules were then checked against a review of 47 public repositories and 20 practical tests (blind human ratings, seeded defects, pre-registered criteria): none of the tools reviewed did strictly better than the simplest option of the setup studied, native Claude Code or BMAD with the kit (`docs/genese.md`). Install with the three commands above. Details are in `docs/` (in French).

## Licence

MIT.
