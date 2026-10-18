# Le mod couts-session

[← README](../README.md)

## Le coût de la session en direct (mod `couts-session`)

Un mod Claude Code, installable seul, affiche au-dessus du prompt ce que coûte la session en cours, sans commande à taper :

```
/plugin marketplace add Aliquanto3/agent-cost-kit
/plugin install couts-session@agent-cost-kit
```

La bande a trois niveaux. Un clic sur la ligne (terminal plein écran) ou la touche `1` (prompt vide, ou après ctrl+x tab) passe au niveau suivant puis replie ; `2` remonte d'un niveau. Le niveau choisi est gardé d'une session à l'autre :
1. une ligne discrète : `💰 ≈ 14,5 $ · 📖 17 M lus · 🪶 62 k écrits · 🧠 238 k · 🌱 0,5–1 kgCO₂e estimé` (📖 : tout ce qui est renvoyé au modèle, entrée et cache, tous tours et sous-agents ; 🪶 : sortie ; 🧠 : contexte de la dernière réponse de la session principale, entrée et cache, le `total_input_tokens` de la status line, proche de `/context` sans lui être égal, absent après `/compact` jusqu'à la réponse suivante). Ligne trop large : la mention `⏳` tombe d'abord, puis le 🧠, puis les mots « lus » et « écrits » ; le coût et le carbone restent ;
2. un tableau par modèle (entrée, sortie, lecture et écriture du cache, coût, gCO₂e) suivi d'une ligne d'aide (📖 relu à chaque tour, 🪶 généré), une ligne par sous-agent (type, coût, impact, modèle, description), la source de l'impact, pour comparer le total `/cost` du moteur, et la commande d'analyse complète de la session (`/agent-cost-kit:mesurer-couts --session <id>`, du plugin `agent-cost-kit`), qui relit toutes les transcriptions pour chercher des optimisations ;
3. en plus, le remplissage du contexte façon `/context`, par catégorie (estimation locale, gratuite).

Les cumuls viennent de l'usage de chaque fin de tour, session principale et sous-agents. Ils survivent au rechargement du mod et à `--resume`, et repartent de zéro après `/clear`. Les prix et les coefficients EcoLogits sont dans `plugins/couts-session/donnees/tarifs.json`, les mêmes que ceux de `mesurer_couts.py` ; `donnees/generer_tarifs.py` en tire le module TypeScript du mod (`--verifier` contrôle les deux).

Un sous-agent qui tourne est affiché « en cours » dès son lancement : replié, la ligne ajoute `· ⏳ 2 en cours` avant la flèche (première mention à tomber si la ligne est trop étroite, pour garder le coût visible) ; aux niveaux 2 et 3, il figure au-dessus des terminés avec `⏳ en cours · <durée>` à la place du coût (durée rafraîchie toutes les 30 s environ), et prend ses chiffres à la fin de son tour. Un tour interrompu ou en échec, sans usage, retire la ligne sans la chiffrer ; une reprise par SendMessage le remet en cours. Un sous-agent tué sans fin de tour quitte l'état « en cours » au battement suivant, ou une minute au moins après son lancement s'il n'est plus listé par le moteur.

Limites :
- les tours d'avant le chargement du mod et les tours interrompus (sans usage) ne sont pas comptés ;
- l'écriture du cache est comptée au tarif 5 min : l'usage d'un tour ne sépare pas 5 min et 1 h ;
- le surcoût Haiku au-delà de 100 k tokens de prompt n'est pas appliqué : l'usage d'un tour additionne ses requêtes ;
- l'impact ne compte que les tokens de sortie, comme EcoLogits ; c'est une estimation, en fourchette ;
- les tokens de sortie sont ceux que déclare l'usage du tour, exacts en direct ; `mesurer_couts.py`, qui relit des transcriptions où ce compte est parfois tronqué, les réestime (`max(sortie, caractères / 2,2)`) : les deux totaux peuvent donc différer pour une même session.
