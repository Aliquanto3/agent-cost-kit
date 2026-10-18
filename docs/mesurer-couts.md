# Mesurer les coûts et l’empreinte

[← README](../README.md)

## Mesurer avant de changer

```
python scripts/mesurer_couts.py --projet /chemin/du/depot
```

Le résumé donne :
- le coût médian d'une story, ses appels et son pic de contexte ;
- les expirations médianes par agent ;
- le coût qu'aurait l'autre TTL.

La méthode : faites 3 à 5 stories avec votre méthode actuelle, installez le kit, refaites 3 à 5 stories, comparez.

Les prix (octobre 2026, vérifiés sur la page de prix officielle) sont dans l'en-tête du script : Opus 5.5 à 4 / 20 $, Sonnet 5.5 à 2 / 10 $ avec une lecture du cache à 0,10 $, Haiku 5.5 à 0,10 / 0,50 $, et 5 fois plus au-delà de 100 k tokens de prompt.

Trois pièges du calcul, que le script corrige :
- certaines transcriptions ne gardent que l'usage du début d'une réponse ; la sortie est alors réestimée à 2,2 caractères par token, valeur mesurée avec l'endpoint `count_tokens` ;
- les écritures en cache de 5 minutes et d'une heure n'ont pas le même prix ;
- une session reprise ou redémarrée recopie les réponses de l'ancienne (mêmes `message.id`) : chacune ne compte qu'une fois, dans sa session d'origine, mais reste le point de départ des pauses de la reprise (une reprise après plus de 5 min compte son expiration). Avec `--session` ou `--filtre`, le dédoublonnage ne porte que sur les transcriptions retenues : une réponse recopiée compte alors dans la session retenue, et les totaux de deux sélections ne s'additionnent pas. La durée et le premier contexte d'une reprise partent de sa première réponse propre.

## Empreinte environnementale (GreenOps)

Le script estime aussi l'énergie, le GWP (gCO2e, usage et fabrication du matériel), l'eau, l'énergie primaire et l'ADPe des mêmes appels, en fourchette min-max, selon la méthodologie [EcoLogits](https://ecologits.ai/latest/methodology/llm_inference/). Les coefficients sont intégrés au script (données du 2026-10-14) : pas de dépendance. Mix électrique des États-Unis par défaut, `--mix {USA,FRA,SWE,WOR}` pour en changer.

Trois limites, dites dans `resume.md` :
- seuls les tokens de **sortie** comptent, comme dans EcoLogits ; le cache, qui fait environ 85 % du coût en dollars, n'a aucun impact dans ce modèle, donc empreinte et coût ne sont pas proportionnels ;
- la réflexion masquée n'est pas comptée : c'est une borne basse ;
- les tailles des modèles Anthropic sont estimées par EcoLogits, d'où la fourchette.

`bancs/ecologits_ecart.py` vérifie que le calcul du script reproduit la librairie officielle (écart de l'ordre de 1e-16).

## Quand de nouveaux modèles sortent

Les choix de modèles du kit valent pour Opus, Sonnet et Haiku 5.5, aux prix d'octobre 2026. À chaque nouvelle génération ou changement de prix :
1. mettez à jour les prix du script ;
2. vérifiez que les réglages de Claude Code existent toujours ;
3. rejouez les bancs de `bancs/README.md` sur vos stories : contre-revue par modèle, A contre kit, recherches, effort, caractères par token, cache.

Comptez environ 60 $ pour tout refaire. Ne changez un réglage qu'avec au moins 3 essais par cellule.
