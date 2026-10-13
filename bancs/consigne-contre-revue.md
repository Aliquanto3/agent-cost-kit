Contre-revue indépendante, EN LECTURE SEULE, d'une story déjà implémentée et relue par les agents du setup testé. Objectif : trouver les défauts réels que la première revue a laissé passer.

La spec de la story est dans le diff (`_bmad-output/implementation-artifacts/spec-*.md` ou équivalent) ; sa section `## Revue`, si elle existe, liste les constats déjà trouvés. Lis aussi la story d'origine (epics, ticket) pour vérifier les critères d'acceptation.

Règles strictes :
- Tu ne modifies, ne crées et ne commites AUCUN fichier, ni dans le worktree ni ailleurs. Pas de git checkout/stash/reset. Ne lis jamais `.env`. Aucun appel réseau, aucun téléchargement, aucun LLM réel, aucun calcul GPU.
- Tu peux exécuter du code et des tests pour prouver un défaut : test ciblé, ou petit script Python passé en `python -c "..."` (rien écrit sur disque).
- Pas de sous-agent, rien en arrière-plan.
- Ignore le style. Cherche : critères d'acceptation non couverts, chemins d'erreur, cas limites, régressions, intégration avec le code existant, sécurité/données.

Rapport final (30 lignes max), dans la langue du dépôt :
1. Une ligne par défaut NOUVEAU (absent de `## Revue`) : sévérité (high/medium/low) | fichier:ligne | mécanisme | preuve (test/commande exécuté et résultat, ou raisonnement si non exécutable) | confiance (certain/probable).
2. Une ligne sur les constats de `## Revue` que tu juges mal classés ou mal corrigés, s'il y en a.
3. Verdict : nombre de défauts nouveaux medium+ certains, et « fusionnable en l'état : oui/non ».
N'invente rien : si tu ne trouves rien de medium ou plus, dis-le.
