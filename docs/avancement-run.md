# Suivre un run autonome

[← README](../README.md)

## Suivre un run autonome

`/agent-cost-kit:avancement-run` (ou `python scripts/avancement_run.py <projet> [--detail] [--stories] [--json]`) donne une synthèse pour un dirigeant, sans appel de modèle pour les chiffres :
- en tête, le taux d'avancement global (barre et « n / N stories »), l'heure de fin estimée (centrale et fourchette) et une météo : 🟢 dans les temps, 🟡 vigilance (un contrôle automatique rouge ou une story reprise), 🔴 bloqué (une story bloquée, ou une attente humaine sur le chemin critique) ;
- « Ce qu'il faut savoir » : trois à cinq puces sans jargon (faits marquants, points d'attention, décisions attendues d'Anaël) ;
- un tableau par epic (nom tiré de `epics.md`, barre `█░`, terminées, en cours, à faire, statut) ; les stories à signaler (en cours, bloquées, attente humaine) sont dans « Ce qu'il faut savoir ». Le tableau par story (état en emoji, pourcentage, ★ pour les pivots) n'apparaît que sans niveau de consolidation (un seul epic) ou avec `--stories` ;
- avec `--detail` : rythme observé (stories fusionnées par heure sur 3 h, durée médiane « dev lancé -> fusion »), vagues, chemin critique, méthode d'estimation, heures interpolées.

La fin estimée retient le plus contraignant de deux calculs : le reste divisé par le débit (plafonné par le parallélisme du plan), et le chemin critique des dépendances restantes. Elle ne compte ni les étapes humaines, ni les limites d'usage, ni les ressources à activer (Ollama, GPU), ni les reprises en cas d'échec.

Il attend le format du plan BMAD de l'orchestrateur : tables `| Vague | Stories en parallèle | Après |` avec dépendances `x.y ← a.b, c.d`, `★` pour un pivot, `(mixte)` pour une story à étape humaine, et une section « Journal ». **Pour une estimation fiable, chaque ligne du journal porte date et heure** : `- AAAA-MM-JJ HH:MM · story · étape · résultat · commit` (étapes : `dev`, `second-avis`, `review`, `fusion`, `CI`, `blocked`, `attente humaine`, `report`). Une ligne sans heure est datée par le commit « suivi du run … (story X fusionnée) », puis par le commit cité, puis par interpolation entre ses voisines : les durées deviennent approximatives.

Barème d'un en-cours : dev lancé 30 %, dev fini (second avis en cours) 60 %, second avis fini (review en cours) 75 %, review finie (fusion en cours) 90 %.
