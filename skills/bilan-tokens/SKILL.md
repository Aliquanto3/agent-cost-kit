---
name: bilan-tokens
description: Refait le bilan mensuel des tokens Claude Code (input détaillé, output, coût API équivalent, impact ImpactIA ou EcoLogits) par modèle, publie une page HTML à la charte Wavestone en français, anglais et allemand, et consolide plusieurs PC. À invoquer avec « bilan tokens », « combien de tokens ce mois », « consommation Claude Code du mois », « consolider mes PC ».
---

Tu rejoues le bilan mensuel des tokens depuis les transcriptions locales, sans appel d'API.

1. **Collecte.** Demande le mois et le périmètre seulement s'ils ne sont pas donnés dans la demande (défaut : mois UTC courant, tous les projets). Lance :

   ```
   uv run --no-project python "${CLAUDE_PLUGIN_ROOT}/scripts/bilan_tokens.py" --mois AAAA-MM [--dossier <chemin>] [--methode impactia|ecologits]
   ```

   `--methode` : `impactia` par défaut (expérimental, d'après la PR EcoLogits #259 non fusionnée : l'input compte, la lecture du cache de 0 en borne basse au prefill complet en borne haute) ; `ecologits` pour l'output seul.

   Période en jours : `--du AAAA-MM-JJ --au AAAA-MM-JJ` (UTC, inclus, même mois, à la place de `--mois`). `--racine` est répétable (une copie des transcriptions d'un PC plus le dossier local du même PC ; un appel n'est compté qu'une fois). `--detail` ajoute au JSON et à la page le détail par projet, étape et rôle, et des recommandations chiffrées ; `--config` désigne `~/.claude/cost-kit/bilan-config.json` (portfolio, alias, dossiers parents). Si cette config est absente et que l'utilisateur parle de son portfolio, propose de la créer d'après l'exemple de `docs/bilan-tokens.md`.

   `--dossier` limite aux projets dont le chemin encodé commence par celui donné (lui et ses sous-dossiers). Le script écrit `<mois>-<machine>.json` et `.html` dans `~/.claude/cost-kit/bilans` (`--out` pour changer) et affiche un tableau par modèle.

2. **Commentaire, 10 lignes maximum.** D'après la sortie du script : input traité (dont la part de lecture de cache), output (déclaré → réestimé), coût total et son premier poste, impact en kgCO2e (fourchette), modèle dominant, une piste d'économie (cache perdu, dossier à exclure, modèle à router vers Sonnet/Haiku). Avec `--detail`, cite la première recommandation de `detail.recos` (titre, gain estimé) plutôt qu'une piste générique.

3. **Publication.** Le script écrit trois pages reliées par un sélecteur de langue : `<base>.html` (français), `<base>.en.html` et `<base>.de.html` (`--langues fr` pour une seule page). Si l'outil Artifact est disponible, publie-les en un seul Artifact multi-fichiers : la page française comme page principale (`file_path`), et les trois fichiers sous leur propre nom dans `files` (`{"<base>.html": …, "<base>.en.html": …, "<base>.de.html": …}`), pour que les liens du sélecteur fonctionnent depuis chaque page. Titre stable du type « Bilan tokens <mois> <année> », description d'une phrase. Sans l'outil Artifact, donne les chemins des fichiers écrits.

   Si la génération échoue avec « Catalogue en/de : texte(s) absent(s) du gabarit », le gabarit a changé sans ses catalogues : mets à jour `skills/bilan-tokens/i18n/en.json` et `de.json` (paires [texte français exact, traduction]) puis relance, ou relance avec `--langues fr` si l'utilisateur ne veut que le français.

4. **Consolidation de plusieurs PC.** Rapatrie d'abord les JSON des autres PC (OneDrive, clé USB, ou un commit dans `mesures/bilans/` d'un dépôt — demande confirmation avant tout commit ou push), puis :

   ```
   uv run --no-project python "${CLAUDE_PLUGIN_ROOT}/scripts/bilan_tokens.py" --fusionner a.json b.json ... --out <dossier>
   ```

   Le script refuse deux fichiers de période (mois, `du`, `au`), de mix ou de méthode d'impact différents, ou une machine présente deux fois. Publie ensuite le `<mois>-consolide.html` comme à l'étape 3.

Rappels à donner si le sujet surprend l'utilisateur : les transcriptions sont lues en local uniquement ; le coût est un équivalent au tarif public de l'API, pas la facture d'un abonnement ; l'impact environnemental suit la méthode indiquée dans la page : ImpactIA (défaut, expérimental) compte l'input, sa fourchette reflète surtout la lecture du cache ; EcoLogits ne compte que l'output, c'est une borne basse.
