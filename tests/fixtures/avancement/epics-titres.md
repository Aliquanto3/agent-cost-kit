## Epic 1 : Installer, lancer et diagnostiquer l'application
### Story 1.1 : Amorcer le dépôt et la CI sur trois systèmes
### Story 1.2 : Lancer l'application sur un serveur local protégé
### Story 1.3 : Afficher la coquille d'interface avec l'identité WaveStack
### Story 1.4 : Sonder les outils requis à partir d'un registre unique
### Story 1.5 : Consulter la page Diagnostic et savoir quoi régler
### Story 1.6 : Installer l'application sous Windows sans droits administrateur
### Story 1.7 : Installer l'application sous macOS et Linux sans droits administrateur
## Epic 2 : Taper du vrai git dans un bac à sable et voir l'effet
### Story 2.1 : Préparer un bac à sable déterministe à partir d'un YAML
### Story 2.2 : Faire passer chaque action par la file d'opérations de l'espace
### Story 2.3 : Afficher la disposition principale et gérer les volets
### Story 2.4 : Taper de vraies commandes git dans le terminal
### Story 2.5 : Utiliser les commandes de fichiers, confinées au bac à sable
### Story 2.6 : Calculer l'état du dépôt et un graphe stable côté serveur
### Story 2.7 : Voir le graphe, la liste des commits et l'index
### Story 2.8 : Éditer un fichier dans la vue Code et lire un diff
### Story 2.9 : Voir les vues suivre une modification faite hors de l'application
### Story 2.10 : Suivre un élément d'une vue à l'autre et lire son explication
### Story 2.11 : Préparer les gabarits d'exercice des deux parcours
## Epic 3 : Collaborer dans un GitHub simulé
### Story 3.1 : Tenir un modèle de PR complet, prêt pour les stations
### Story 3.2 : Ouvrir une PR et la merger
### Story 3.3 : Voir le distant et les PR dans la vue Distant + PR
### Story 3.4 : Recevoir la revue et les commits d'un collègue simulé
### Story 3.5 : Protéger une branche pour de vrai par un hook pre-receive
## Epic 4 : Suivre un scénario guidé avec quiz réels et indices
### Story 4.1 : Valider une étape sur l'état réel du dépôt
### Story 4.2 : Enregistrer les faits du premier passage
### Story 4.3 : Prendre des instantanés et rétablir un état exact
### Story 4.4 : Recommencer un scénario sans perdre son score
### Story 4.5 : Exécuter une mauvaise commande de quiz, puis rétablir l'état
### Story 4.6 : Ouvrir des indices par paliers
### Story 4.7 : Lire le bilan à la fin d'un scénario
## Epic 5 : Comprendre ce que l'agent a fait (mode B)
### Story 5.1 : Rejouer les actes de l'agent B de façon déterministe
### Story 5.2 : Corriger une désignation côté serveur, en un seul essai
### Story 5.3 : Désigner un élément dans les vues
### Story 5.4 : Choisir dans une liste ou par SHA
### Story 5.5 : Lire la correction dans les vues et dans le panneau
### Story 5.6 : Le scénario B « `.env` committé »
### Story 5.7 : Le scénario B « `push --force` qui écrase un collègue »
### Story 5.8 : Les scénarios B « stash oublié » et « rebase laissé en conflit »
## Epic 6 : Parcourir le socle git complet dans les deux parcours
### Story 6.1 : Choisir son parcours et parcourir le catalogue
### Story 6.2 : Les scénarios A « add / commit », « push / pull », « branche » et « PR / merge »
### Story 6.3 : Les scénarios A « conflit », « stash », « rebase » et « récupération »
### Story 6.4 : Reprendre le dernier scénario là où on l'a laissé
### Story 6.5 : Exporter mon rapport de progression
### Story 6.6 : Exécuter, en option, le code d'exercice du parcours LLM
### Story 6.7 : Publier la release v0.1.0 et la faire tester par deux collègues
## Epic 7 : Voir le poste local et le pipeline simulé bloquer une PR (stations 1 et 2)
### Story 7.1 : Provisionner les outils de la chaîne pour un usage hors ligne
### Story 7.2 : Lancer ruff et pytest dans le terminal (Station 1 · Poste local)
### Story 7.3 : Être protégé par le hook pre-commit gitleaks
### Story 7.4 : Faire tourner le pipeline simulé sur chaque PR
### Story 7.5 : Voir la revue obligatoire et la protection de `main` bloquer (Station 2 · PR et CI)
### Story 7.6 : Lire le même pipeline en GitHub Actions, Jenkins et GitLab CI
## Epic 8 : Voir les barrières de sécurité et de qualité jouer (station 3)
### Story 8.1 : Bloquer une PR sur du code vulnérable avec bandit (SAST)
### Story 8.2 : Servir une base de vulnérabilités locale et figée
### Story 8.3 : Bloquer une PR sur une dépendance vulnérable et lire le SBOM (SCA)
### Story 8.4 : Bloquer une PR quand la couverture du nouveau code passe sous 80 %
### Story 8.5 : Le scénario LLM « outil trop puissant » (Flow 4)
### Story 8.6 : La clé d'API en dur, le test de config LLM et l'injection de prompt
## Epic 9 : Se situer dans la chaîne et en parler le vocabulaire
### Story 9.1 : Se situer grâce au bandeau de la chaîne
### Story 9.2 : Déplier la carte de la chaîne
### Story 9.3 : Trouver les scénarios de station dans le catalogue
### Story 9.4 : Relier chaque terme du vocabulaire à sa barrière
### Story 9.5 : Publier la release v0.2.0
## Epic 10 : Livrer une version taguée, la promouvoir et revenir en arrière (station 4)
### Story 10.1 : Poser un tag SemVer annoté
### Story 10.2 : Construire la version taguée
### Story 10.3 : Promouvoir une version vers la prod simulée, après approbation
### Story 10.4 : Revenir à la version précédente par un rollback
### Story 10.5 : Les scénarios de la Station 4 · Livraison dans les deux parcours
## Epic 11 : Défendre la chaîne devant un RSSI et repartir avec la fiche
### Story 11.1 : Décrire les barrières, leurs risques et leurs correspondances réglementaires
### Story 11.2 : Répondre à une question du RSSI avec une réponse et une preuve
### Story 11.3 : Passer l'entretien RSSI
### Story 11.4 : Exporter la fiche barrière → risque → preuve
### Story 11.5 : Publier la release v0.3.0
## Epic 12 : Installation complète, finition et présentation de v1.0.0
### Story 12.1 : Vérifier l'installation complète, puis l'usage hors ligne, sur trois postes réels
### Story 12.2 : Mettre à jour l'application sans perdre sa progression
### Story 12.3 : Auditer et corriger l'accessibilité
### Story 12.4 : Intégrer les retours du test v0.1 et des ateliers
### Story 12.5 : Relire les correspondances réglementaires
### Story 12.6 : Chronométrer les séances et finir tous les scénarios sans indice
### Story 12.7 : Mesurer le transfert hors de l'application
### Story 12.8 : Publier v1.0.0 et la présenter
