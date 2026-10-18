# Re-tester le kit quand de nouveaux modèles sortent

Les réglages du kit (Sonnet pour coder, Opus pour relire, Haiku pour le second avis et les recherches, effort medium, cache par défaut) reposent sur des mesures faites avec les modèles d'octobre 2026 : Opus 5.5, Sonnet 5.5, Haiku 5.5. À chaque nouvelle génération, ou à chaque changement de prix, refaites les bancs ci-dessous avant de changer un réglage. Ils tournent sur vos propres dépôts. Comptez environ 60 $ pour tout refaire, dont 50 $ pour le banc A contre kit.

## Avant de commencer

1. **Prix.** Relevez la page officielle (`platform.claude.com/docs/en/about-claude/pricing`) : entrée, écriture du cache à 5 min et à 1 h, lecture du cache, sortie, et seuils de contexte long. Mettez à jour `PRIX` et les constantes Haiku de `scripts/mesurer_couts.py`. Un écart sur la lecture du cache fausse tout : c'est 40 % du coût, et Sonnet a déjà été compté au double par erreur.
2. **Noms des modèles.** `famille()` reconnaît les modèles par le nom de leur famille (`opus`, `sonnet`, `haiku`, `fable`). Ajoutez toute nouvelle famille dans `PRIX`.
3. **Réglages de Claude Code.** Vérifiez dans la doc que `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`, `subagentPromptCacheTtl`, `syncClaudeAiSkills` et les champs `model`, `effort` et `disallowedTools` du frontmatter existent toujours, avec le même sens.
4. **Corpus.** Gardez 5 à 10 stories déjà livrées, sur au moins deux dépôts, avec leur base Git. On rejoue les bancs dessus, chaque story dans son propre worktree.

## Les bancs, par ordre d'utilité

| # | Question | Banc | Coût | Décision qui en dépend |
|---|---|---|---|---|
| 1 | Quel relecteur trouve les défauts ? | Contre-revue (ci-dessous) | 0,03 à 1 $ par story et par modèle | modèle de `reviewer` et de `second-avis` |
| 2 | Quel setup coûte le moins à qualité égale ? | A contre kit (ci-dessous) | 25 à 50 $ | tout le kit |
| 3 | Quel modèle pour les recherches ? | `lookup.py` | moins de 2 $ | modèle de `lookup` |
| 4 | Effort medium ou high pour coder ? | 3 essais par effort sur 2 stories, contre-revue de chaque | environ 10 $ | `effort` de `dev-story` |
| 5 | Combien de caractères par token ? | `caracteres_par_token.py` | gratuit (count_tokens) | `--car-par-token` du script |
| 6 | Le cache à 1 h vaut-il le coup ? | `cache_ttl.py` et `/agent-cost-kit:mesurer-couts` | gratuit | `subagentPromptCacheTtl` |
| 7 | Combien pèse le contexte fixe ? | 2 sessions `claude -p` avec et sans `syncClaudeAiSkills`, puis le script | quelques centimes | conseils d'installation |
| 8 | Le calcul d'impact reproduit-il la librairie EcoLogits ? | `ecologits_ecart.py` | gratuit | confiance dans les chiffres GreenOps |

### 1. Contre-revue : quel modèle pour relire ?

Sur des stories déjà relues par le setup en place, lancez une contre-revue en lecture seule par modèle candidat, avec la même consigne (`consigne-contre-revue.md`). Seul le modèle change :

```bash
cd <worktree de la story>
claude -p "Lis la consigne <chemin>/bancs/consigne-contre-revue.md et applique-la exactement.
Worktree : <chemin>. Diff à relire : git diff <base>..HEAD." \
  --model <opus|sonnet|haiku> --effort medium --permission-mode bypassPermissions \
  --max-budget-usd 3 --output-format json > cr-<story>-<modele>.json
```

- Comptez par story les défauts medium et high certains, et notez ceux que chaque modèle trouve seul.
- Vérifiez vous-même au moins deux défauts « certains » par modèle : un rapport peut se tromper.
- Lancez aussi une fusion de toutes les branches dans un worktree jetable, puis la suite complète, **avec la même installation que la CI**. Un `uv sync` différent de la CI a déjà masqué un vrai défaut.
- Référence d'octobre 2026, sur 10 stories : Opus 11 défauts certains (0,63 $ par story), Sonnet 1 (0,27 $), Haiku 2 plus des constats propres (0,03 $). Aucun relecteur n'a tout trouvé.

### 2. A contre kit : le setup complet

Une même story, 3 essais par setup, chacun dans un worktree partant de la même base :
- l'ancien setup (ou un concurrent), lancé tel quel ;
- le kit, chargé tel quel : `--plugin-dir <agent-cost-kit>`, orchestrateur en `--effort medium`, `--settings '{"subagentPromptCacheTtl":"5m","env":{"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH":"1"}}'`.

Mesurez chaque session complète, orchestration comprise, avec `python scripts/mesurer_couts.py --projet <worktree>`. Puis passez chaque résultat en contre-revue Opus (banc 1) pour comparer la qualité.

Référence d'octobre 2026 (jira 6.12) : ancien setup de 6,77 à 7,31 $, kit (reviewer Sonnet) de 1,18 à 1,60 $. Dans chaque setup, 1 essai sur 3 avait un défaut medium ou plus.

### 3. Recherches dans le dépôt

```bash
python bancs/lookup.py questions --depot <dépôt> --src <dossier du code> --out bancs-lookup
# pour chaque question i et chaque modèle m :
claude -p "<question i>" --model m --effort low \
  --append-system-prompt "<corps de agents/lookup.md>" \
  --allowedTools "Read Grep Glob Bash(git grep:*) Bash(grep:*)" --output-format json > bancs-lookup/r<i>-<m>.json
python bancs/lookup.py noter --out bancs-lookup --modeles haiku sonnet
```

Relisez les cas notés faux, car le corrigé peut se tromper. Référence : Haiku et Sonnet à 20 sur 20, pour 0,07 $ contre 1,22 $.

### 8. Écart avec EcoLogits

`uv run --with ecologits python bancs/ecologits_ecart.py` compare, pour chaque modèle et pour 1 000 et 100 000 tokens de sortie, l'énergie, le GWP, l'eau, l'énergie primaire et l'ADPe du script à ceux de la librairie officielle, et sort en erreur au-delà de 1e-6 d'écart relatif. À relancer quand EcoLogits change ses coefficients ou ses paramètres de modèles : mettez alors à jour `PARAMETRES` et les constantes d'impact de `scripts/mesurer_couts.py`. Référence du 2026-10-18 (ecologits 0.11.3) : écart maximal 4e-16.

### 5 à 7. Mesures gratuites

```bash
ANTHROPIC_API_KEY=... python bancs/caracteres_par_token.py --projet <dépôt1> <dépôt2>
python bancs/cache_ttl.py --projet <dépôt1> <dépôt2>
```

Références : 2,13 caractères par token. En TTL 1 h, une pause de 5 min à 1 h est relue dans 100 % des cas ; en TTL 5 min, elle est réécrite dans 91 % des cas. Sans les skills claude.ai, le premier contexte baisse de 8,4 k tokens.

## Règles pour conclure

- Au moins 3 essais par cellule avant de changer un réglage. Un essai unique a déjà donné des conclusions inverses d'un projet à l'autre.
- Comparez la qualité avec une contre-revue indépendante, jamais avec la revue du setup testé.
- Mesurez le coût de la session principale avec le reste : quand les sous-agents deviennent bon marché, c'est elle qui pèse.
- Notez la date, les versions de modèles, la version de Claude Code et les prix utilisés à côté de chaque résultat, et mettez à jour les références de ce fichier.
