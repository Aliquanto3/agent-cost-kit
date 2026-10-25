# Installation et contenu du kit

[← README](../README.md)

## Installation

```
/plugin marketplace add Aliquanto3/agent-cost-kit
/plugin install agent-cost-kit@agent-cost-kit
```

Ou, pour l'essayer sans installer : `claude --plugin-dir ./agent-cost-kit`.

Sur un nouveau PC, ces deux commandes et un `/cost-kit-install` suffisent : les réglages globaux ne sont pas synchronisés d'une machine à l'autre, le script les réapplique. Après une mise à jour du kit, relancez-le (`uv run --no-project python scripts/installer_global.py`) : il ne remplace que le bloc du kit dans `~/.claude/CLAUDE.md`.

Puis, dans votre projet : `/cost-kit-install`. Le skill :
- une fois par PC, applique avec votre accord les réglages utilisateur (`~/.claude/settings.json`) et les consignes de coût globales (`~/.claude/CLAUDE.md`), par `scripts/installer_global.py` : aperçu d'abord, sauvegarde, rien d'autre n'est touché ; il propose aussi le plugin `pyright-lsp` pour les projets Python et le blocage des connecteurs claude.ai inutiles ;
- propose les réglages du projet (un plugin ne peut pas les imposer) ;
- copie le modèle de contrôle rapide ;
- explique l'enchaînement des agents ;
- pour un projet à interface web, propose en option (expérimental) le sous-agent `verif-front`, un modèle copié dans `.claude/agents/` : après dev-story, il vérifie les critères dans un vrai navigateur (`docs/verif-front.md`) ;
- vous rappelle de redémarrer Claude Code.

## Contenu

| Élément | Rôle |
|---|---|
| `agents/dev-story.md` | Sonnet, `medium`, sans sous-agent (outil retiré) ni arrière-plan (par consigne). Implémente une story dans un worktree, tests ciblés pendant, suite complète une fois à la fin, au plus 3 cycles sur un même échec, rapport de 5 lignes. |
| `agents/second-avis.md` | Haiku, lecture seule. Relecture adversariale du diff pour quelques centimes ; sa liste est transmise au reviewer. |
| `agents/reviewer.md` | Opus, `medium`. Une passe par défaut, relancée seulement après correction d'un constat Important, 3 passes au plus : suit les appelants au-delà du diff, exécute le code, questionne les tests, vérifie ce que la CI installe, corrige les constats Important (medium ou high réels), consigne la revue dans la spec. |
| `agents/lookup.md` | Haiku, `low`, lecture seule. Trouve un symbole, résume un log : 20 bonnes réponses sur 20, comme Sonnet, pour 18 fois moins cher. |
| `skills/cost-kit-install` | Installation guidée : partie globale, réglages du projet, contrôle rapide, enchaînement, vérification. |
| `scripts/installer_global.py` | Partie globale, une fois par PC : fusionne les réglages utilisateur, écrit le bloc de consignes entre marqueurs, signale les réglages contraires. Aperçu par défaut, `--appliquer` pour écrire. Python 3.10+, aucune dépendance. |
| `modeles/agents/verif-front.md` | Modèle d'agent expérimental (Sonnet, `medium`, lecture seule, Playwright MCP 0.0.83 en ligne), copié par `cost-kit-install` dans un projet front ; absent de `agents/` car les sous-agents de plugin ignorent `mcpServers`. |
| `modeles/CLAUDE.global.md` | Les consignes de coût écrites dans `~/.claude/CLAUDE.md`. |
| `commands/mesurer-couts.md` | `/agent-cost-kit:mesurer-couts` : coût réel par agent et par story, pic de contexte, appels, expirations du cache, contrefactuel du TTL. |
| `scripts/mesurer_couts.py` | Le script derrière la commande. Python 3.10+, aucune dépendance. Lit `~/.claude/projects/<projet>/` et la table des prix `plugins/couts-session/donnees/tarifs.json` du dépôt. |
| `commands/avancement-run.md` | `/agent-cost-kit:avancement-run` : synthèse d'avancement d'un run autonome BMAD (taux global, fin estimée, météo, epics, stories). |
| `scripts/avancement_run.py` | Le script derrière la commande. Python 3.10+, aucune dépendance, lecture seule. Lit `sprint-status.yaml`, `run-autonome.md` et `git log`. |
| `scripts/controle_rapide.py` | Modèle de contrôle de fin de story (lint, format, typage), à adapter. |
| `modeles/run-autonome.md` | Modèle du fichier d'état d'un run autonome (périmètre, vagues, contrats partagés, journal), au format lu par `avancement-run`. |
| `scripts/file_prs.py` | Fusion d'une file de PR : contrôles présents, mergeable, relance unique des jobs en échec, PR suivante au lieu de s'arrêter, vérification de `MERGED` (`docs/file-prs.md`). |
| `docs/pieges-runs.md` | Pièges vus en run : tests instables sous charge, SQLite sur macOS, push refusé, `python` nu. |
| `skills/essai-outil`, `docs/experimental.md` | Expérimental : catalogue d'outils de la veille à essayer, et skill (invocation manuelle) qui guide l'essai : lecture avant installation, SkillSpector, installation au niveau projet, retour dans `mesures/essais/`. |
| `bancs/` | Protocole et scripts pour re-tester le kit quand de nouveaux modèles sortent (`bancs/README.md`). |

Le `model` et l'`effort` déclarés dans le frontmatter des agents s'appliquent bien aux agents de plugin. Vérifié : depuis une session Opus en `high`, `lookup` tourne en Haiku `low`.
