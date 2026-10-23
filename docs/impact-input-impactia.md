# Impact des tokens d'entrée : méthode ImpactIA

[← README](../README.md)

Statut : en revue (status: review). Méthode expérimentale, d'après la PR EcoLogits [#259](https://github.com/mlco2/ecologits/pull/259) « [Draft] Integrate ImpactIA methodology », ouverte et non fusionnée : à réaligner sur la version officielle quand elle sera fusionnée.

## Pourquoi

EcoLogits (méthode actuelle du kit) ne compte que les tokens de **sortie**. Une session d'agents de code relit surtout du contexte : en octobre 2026, environ 4,6 Md de tokens d'entrée (98 % de lecture du cache) pour 15 M de sortie. L'impact est sous-estimé. L'issue [#267](https://github.com/mlco2/ecologits/issues/267) fait le même constat (médiane d'un appel d'agent : 25 k lus, 250 générés) sans trancher le traitement du cache.

## Source

PR #259, branche `mlco2/ecologits:feat/impactia`, SHA de tête `4c552f64a1770514525914e2bbebc6368104374f`. Fichier `ecologits/impacts/llm.py` à ce SHA :

- l. 22-25 : constantes de prefill (Agrawal et al., 2024, Mistral 7B sur A100 : TTFT[ms] = 0,062 × N_in + 17,88) ;
- l. 105-144 `prefill_latency`, l. 147-183 `generation_latency` ;
- l. 42-62 réseau du centre de données (pare-feu, routeur, commutateur ; ADEME Base Empreinte, ADEME-ARCEP-ARCOM, Resilio DB), l. 66 bâtiment (Hubblo, PCR cloud ADEME) ;
- l. 247 `network_energy`, l. 292 `request_it_energy`, l. 477 `request_network_embodied_gwp`, l. 507 `request_datacenter_embodied_gwp`, l. 527 `request_embodied_gwp`.

Méthode d'origine : [SNCFdevelopers/ImpactIA](https://github.com/SNCFdevelopers/ImpactIA) (SNCF, Wavestone, Resilio).

## Formules reprises (par appel, par borne min / max)

Prefill, en secondes, avec `N_in` les tokens d'entrée de l'appel :

    T_prefill = 0,062e-3 × (TTFT_modèle / 0,44) × N_in + 17,88e-3

Génération : `ΔT = N_out × l(actif) + T_prefill`, où `l(actif)` est la latence par token de sortie déjà utilisée par le kit (régression ML.ENERGY, `gpu_latence_s_par_token`).

Énergie IT (kWh) : `E_IT = ΔT/3600 × (P_serveur + P_réseau) × (GPU/8) / B + GPU × N_out × e(actif)`, avec `P_réseau = 90 W × (0,0358 + 0,286 + 1,468) = 161,082 W`. La part GPU reste celle de la sortie seule : la PR ne modélise pas l'énergie GPU du prefill (limite qu'elle documente), l'entrée n'agit que par la durée (serveur, réseau, fabrication).

Fabrication, GWP : `ΔT/(B × 3 ans) × (part serveur + GPU) + ΔT/(B × 5 ans) × (GPU/8) × 660,092 kgCO2e + E_IT × 0,01 kgCO2e/kWh`. Réseau et bâtiment ne portent que sur le GWP (pas de données ADPe ni PE). Eau, énergie primaire, ADPe : comme EcoLogits, sur `E_IT` qui inclut le réseau.

La phase d'entraînement de la PR (rapportée à part, hors total) n'est pas reprise.

## Ce qui change par rapport à l'actuel

| | EcoLogits (`--methode ecologits`) | ImpactIA (`--methode impactia`, défaut) |
|---|---|---|
| Entrée et cache | ignorés | durée de prefill |
| Réseau du centre de données | non | énergie + fabrication (GWP) |
| Bâtiment | non | 0,01 kgCO2e par kWh IT |
| Ordonnée 17,88 ms | non | une fois par appel |

`--methode ecologits` reste identique bit à bit à la version 0.8.0.

## Cache (décision)

La PR passe au traceur Anthropic `usage.input_tokens`, qui exclut lectures et écritures du cache : elle ne compte donc que l'entrée fraîche. L'issue #267 demande ce découpage sans le trancher. Décision du kit :

- entrée fraîche et **écriture** du cache : prefill complet (le KV cache est calculé) ;
- **lecture** du cache : borne basse 0 (le KV cache n'est pas recalculé), borne haute prefill complet.

`N_in(min) = entrée + écriture`, `N_in(max) = entrée + écriture + lecture`. La fourchette min-max existante (paramètres actifs, PUE, WUE) porte aussi cette incertitude.

## Trous de la PR et replis

- **TTFT** : la PR lit le TTFT médian OpenRouter dans son `models.json`, qui s'arrête à Opus 4.8. Le kit prend les TTFT de la même source que ses paramètres (EcoLogits 0.11.3, commit d0b76e3, données du 2026-10-14 : Opus 5.5 2,68 s, Sonnet 5.5 2,21 s, Haiku 5.5 1,75 s, Fable 5.1 3,89 s…), par plus long préfixe ; à défaut, le TTFT du modèle le plus récent de la famille (même règle que les prix), sinon Opus. Le repli de la PR par paramètres actifs (`P_actif / 7,3`) donnerait 1,6 à 4,5 fois plus pour Opus 5.5 (70 à 200 Md actifs contre un ratio TTFT de 6,1) : écarté, il contredit l'échelle des TTFT mesurés.
- **Latence de sortie** : la PR utilise `1/TPS` OpenRouter quand il existe ; le kit garde la régression ML.ENERGY (reproductible hors ligne, déjà retenue en 0.4.0). Le banc compare donc à la librairie avec `tps=None`.
- **Unités** : aucune erreur relevée (constantes en s et kW, coefficient en s/token).
- **Mod couts-session** : il ne connaît que des cumuls par modèle, pas le nombre d'appels ; l'ordonnée de 17,88 ms par appel est omise (0,5 à 0,7 % du prefill d'un appel de 10 k tokens d'entrée selon le modèle, 0,2 à 0,3 % à 25 k, moins de 0,1 % à 100 k ; davantage rapporté à la borne basse quand l'appel lit surtout le cache).

## Où

- `plugins/couts-session/donnees/tarifs.json`, section `impactia` (constantes, TTFT, source et SHA) et `impact_methode_par_defaut`.
- `scripts/mesurer_couts.py` : `impact(..., entree, lu, appels, methode)`, `--methode`.
- `scripts/bilan_tokens.py` : `--methode`, champ `methode` du JSON, fusion refusée si les méthodes diffèrent ; `skills/bilan-tokens/gabarit.html`.
- Mod `couts-session` 0.2.0 : même calcul, libellé « ImpactIA » dans le pied.
- `bancs/ecologits_ecart.py` : ecologits contre la librairie publiée, impactia contre la branche de la PR.

## Résultat du banc

`uv run --no-project --with "ecologits @ git+https://github.com/mlco2/ecologits@4c552f64a1770514525914e2bbebc6368104374f" python bancs/impactia_ecart.py` : la librairie de la PR s'installe. Opus, Sonnet et Haiku 5.5, contextes 10 k / 100 k / 500 k, sorties 100 / 2 000, cinq grandeurs, min et max : écart relatif maximal 4,5e-16 hors cache, de même pour la lecture du cache en borne haute (librairie avec `input_token_count = contexte`) et en borne basse (librairie avec 0). Cible de 5 % tenue. `bancs/ecologits_ecart.py` (méthode `ecologits` contre ecologits 0.11.3) : 3,6e-16.

Bilan d'octobre 2026 (`bilan_tokens.py --mois 2026-10 --dossier C:/Users/anael.yahi/Documents/GitHub`, 4,66 Md tokens d'entrée, 15,2 M de sortie, mix USA) :

| Méthode | GWP | Énergie | Eau |
|---|---|---|---|
| ecologits | 29,3 – 59,7 kgCO2e | 61,2 – 125,0 kWh | 199 – 501 L |
| impactia | 32,0 – 86,2 kgCO2e | 65,4 – 169,1 kWh | 213 – 678 L |

L'écart reste modéré : avec le coefficient de la PR, un token de sortie d'Opus 5.5 (0,175 s par token, régression ML.ENERGY) pèse autant qu'environ 460 tokens d'entrée (3,8e-4 s par token), et l'énergie GPU ne dépend que de la sortie.

## Revue

Revue du 2026-10-23 (Opus), base `origin/master` 4cf9fd3 à jour, pas de rebase nécessaire.

- medium · second avis · corrigé · parité avec la PR : banc réexécuté contre `ecologits@4c552f64` (écart max 4,5e-16 hors cache et lecture max, 3,7e-16 lecture min ; `ecologits_ecart.py` 3,6e-16). Recoupé dans `llm.py` de la PR : réseau 0,09 kW × 1,7898 = 161,082 W, fabrication 660,092 kgCO2e sur 5 ans, bâtiment sur `request_it_energy` (avant PUE, l. 523), ordonnée 17,88 ms même à 0 token, unités s et kW. Le test qui réimplémentait la formule (32 GPU en dur) est remplacé par des valeurs produites par la librairie de la PR, figées dans `tests/test_impact.py`.
- low · second avis · corrigé · ordonnée omise par le mod : 0,47 % (Opus) à 0,72 % (Haiku) du prefill à 10 k tokens, pas « moins de 0,1 % » ; commentaire de `calcul.ts` et section « Trous de la PR » corrigés.
- low · second avis · corrigé · `register.tsx` `compteurs()` sans garde : un champ absent donnait NaN, qui contamine désormais aussi ecologits (`0 × NaN`). Garde `nombre()` (exportée d'`historique.ts`) et test dans `bande.test.ts`.
- low · second avis · corrigé · `impactia` par défaut dans `impact`, `impact_appels`, `par_modele` : aucun appelant du dépôt ne s'appuie sur l'ancien défaut ; changement d'API noté au CHANGELOG.
- low · second avis · corrigé · « bit à bit » : vérifié sur 252 cas (6 modèles, 7 sorties, tous les mix) contre le script de master, égalité exacte ; le test passe de `approx(1e-12)` à `==`.
- low · second avis · écarté · tests TS non exécutés : `claude plugin test` 53/53, `claude plugin validate --strict` OK.
- Complexité : 0 constat (agrégation `impact_appels` en O(n), rendu du mod sur les cumuls par modèle).
