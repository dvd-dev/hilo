[![Français][Françaisshield]][Français]
[![English][Englishshield]][English]

[![hacs][hacsbadge]][hacs]
[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![Project Maintenance][maintenance-shield]][user_profile]
[![License][license-shield]][license]
[![pre-commit][pre-commit-shield]][pre-commit]
[![black][black-shield]][black]
[![calver][calver-shield]][calver]
[![discord][discord-shield]][discord]


**BETA**

Ceci est une version Bêta. Il y aura probablements des bogues, irritants, etc. Merci pour votre patience et d'ouvrir des "Issues".

# Hilo
Intégration pour Home Assistant d'[Hilo](https://www.hydroquebec.com/hilo/fr/)

## Introduction

Ceci est l'intégration HACS non-officielle de Hilo sur Home Assistant. [Hilo](https://www.hiloenergie.com/fr-ca/) est une plateforme de domotique développée par une filliale d'[Hydro-Québec](https://www.hydroquebec.com/hilo/fr/).
Cette intégration n'a aucun liens direct avec Hilo ou Hydro Québec. C'est une initiative communautaire. Merci de ne pas contacter Hilo ou Hydro-Québec pour tout problèmes avec cette intégration Home Assistant. Vous pouvez ouvrir un "issue" dans ce "repository" github à la place.

Si vous souhaitez aider avec le développement de cette intégration, vous pouvez toujours soumettre vos commentaires à partir du formulaire de l'app Hilo et demander à ce qu'ils ouvrent leur API publiquement et qu'ils fournissent un environnement de test pour les développeurs.

### Remerciements

Gros merci à [Francis Poisson](https://github.com/francispoisson/) qui est l'auteur de l'intégration originale. Sans le travail qu'il a fait sur cette intégration, je n'aurais probablement jamais considéré utiliser Hilo.

Un autre gros merci à @ic-dev21 pour son implication à plusieurs niveau.

J'ai décidé de déplacer l'intégration ici car la dernière mise à jour de Hilo a brisé l'original et j'ai pris le temps de complètement la récrire. Hilo pousse maintenant les lectures des appareils via websocket de SignalR.

### Caractéristiques.
- Supporte les interrupteurs et gradateurs en tant que lumières.
- Voir la température actuelle et changer la consigne des thermostat.
- Obtenir la consommation énergétique des tous les appareils Hilo.
- Générer les "sensor" de puissance et d'énergie consommée.
- Sensor pour les Défis.
- Sensor pour la passerelle Hilo
- **NOUVEAU**: Configuration est maintenant faite via l'interface utilisateur
- **NOUVEAU**: Mise à jours des lectures plus près du temps réel.

### À faire:
- Ajouter la fonctionnalité pour d'autres appareils.
- Tests fonctionnels
- [Ajouter des "type hints" au code](https://developers.home-assistant.io/docs/development_typing/)
- ~~Documenter la librairie d'appels API à Hilo~~ Maintenant disponible [ici](https://github.com/dvd-dev/python-hilo)
- Ajout automatique des compteurs de consommation électrique

## Installation

### Étape 1: Télécharger les fichiers

#### Option 1: Via HACS

Assurez-vous d'avoir [HACS](https://hacs.xyz/docs/setup/download/) installé.
Sous HACS, cliquer le bouton '+ EXPLORE & DOWNLOAD REPOSITORIES' au bas de la page, rechercher "Hilo", le choisir, et cliquer sur _download_ dans HACS.

#### Option 2: Manuellement

Télécharger et copier le dossier `custom_components/hilo` de la [dernière version](https://github.com/dvd-dev/hilo/releases/latest) dans votre dossier `custom_components` de Home Assistant.

### Étape 2: Ajouter l'intégration à HA (<--- étape souvent oubliée)

Dans HA, aller à  Paramètres > Appareils et services > Intégrations.
Dans le coin inférieur droit, cliquer sur le bouton '+ AJOUTER UNE INTÉGRATION'.

Si l'intégration est correctement installée, vous devriez pouvoir trouver "Hilo" dans la list. Il est possible d'avoir besoin de vider la mémoire cache de votre navigateur pour que l'intégration s'affiche.

## Configuration

La configuration est faite via l'interface utilisateur. Lorsque vous ajoutez l'intégration, votre nom d'utilisateur et mot de passe Hio vous seront demandés. Après, vous devrez assigner une pièce de votre maison à chaque appareil.

### Compteurs de consommation électrique

Les compteurs de consommation électrique sont une nouvelle caractéristique de cette intégration. Nous devions auparavent les générer manuellement avec des "template sensors" et des automatisations mais ils sont maintenant pleinement intégrés dans l'intégration Hilo.

#### Avertissement

Lors de l'activation des compteurs de consommation électrique générés par Hilo, il est recommandé de supprimer ceux générés manuellement pour avoir de meilleures
statistiques, sinon nous pourrions nous retrouver avec des données en double.

Cela n'a pas été testé avec des entités de données et d'énergie déjà actives (par exemple: batterie, gaz, solaire ou même d'autres appareils individuels).
Il est possible que l'activation de cette option brise ou supprime ces capteurs d'origine. Nous ne pouvons être tenus responsables de toute perte de données
ou temps d'arrêt du service, ou tout autre type tel qu'il est décrit dans la licence.

Si vous rencontrez un problème et que vous souhaitez collaborer, veuillez activer le niveau de journalisation "debug" pour cette intégration et fournir une copie
du fichier `home-assistant.log`. Les détails sur la façon d'activer `debug` sont ci-dessous.

#### Procédure

Si vous souhaitez activer la génération automatique des capteurs d'énergie, procédez comme suit:

* Assurez-vous que la plate-forme `utility_meter` est chargée dans votre fichier `configuration.yaml` depuis
Home Assistant. Il vous suffit d'ajouter une ligne comme celle-ci dans votre `configuration.yaml`:

    ```
    utility_meter:
    ```

* Cliquez sur "Configurer" dans l'interface utilisateur de l'intégration et cochez la case "Générer compteurs de consommation électrique".

* Redémarrez Home Assistant et attendez 5 minutes jusqu'à ce que l'entité `sensor.hilo_energy_total_low` soit créée et remplie
  avec des données:
  * Le `status` devrait être `collecting`
  * Le `state` devrait être un nombre supérieur à 0.

* Toutes les entités et capteurs générés seront préfixés par `hilo_energy_` ou `hilo_rate_`.

* Si vous voyez l'erreur suivante dans vos journaux, il s'agit d'un bogue dans Home Assistant et c'est parce que le wattmètre en question a 0 w/h
  utilisation jusqu'à présent. Cela disparaîtra une fois l'utilisation calculée. Il y a un PR en amont [ici](https://github.com/home-assistant/core/pull/60678) pour résoudre ce problème.

    ```
    2021-11-29 22:03:46 ERROR (MainThread) [homeassistant] Error doing job: Task exception was never retrieved
    Traceback (most recent call last):
    [...]
    ValueError: could not convert string to float: 'None'
    ```

Après leur création, il faut manuellement ajouter les capteurs au dashboard Energy.

### Autres options de configuration

D'autres options sont disponibles sous le bouton "Configurer" dans Home Assistant:

- `Générer compteurs de consommation électrique`: Case à cocher

  Générer automatiquement des compteurs de consommation électrique, voir la procédure ci-dessus pour la configuration

- `Générer seulement les compteurs totaux pour chaque appareil`: Case à cocher

  Calculez uniquement le total d'énergie sans diviser entre le coût faible et le coût élevé

- `Enregistrer également les données de demande et les messages Websocket (nécessite un niveau de journal de débogage à la fois sur l'intégration et sur pyhilo)`: Case à cocher

  Permet un niveau de journalisation plus élevé pour les développeurs/le débogage

- `Vérouiller les entités climate lors de défis Hilo, empêchant tout changement lorsqu'un défi est en cours.`: Case à cocher

  Empêche la modification des consignes de température lors des défis Hilo

- `Suivre des sources de consommation inconnues dans un compteur séparé. Ceci est une approximation calculée à partir de la lecture du compteur intelligent.`: Case à cocher

  Toutes les sources d'énergie autres que le matériel Hilo sont regroupées dans un seul capteur. Utilise la lecture du compteur intelligent de la maison.

- `Nom du tarif Hydro Québec ('rate d' ou 'flex d')`: chaîne

  Définissez le nom du plan tarifaire d'Hydro-Québec.
  Seules 2 valeurs sont prises en charge pour le moment:
  - 'rate d'
  - 'flex d'

- `Intervalle de mise à jour (min: 15s)`: Nombre entier

  Nombre de secondes entre chaque mise à jour de l'appareil. Par défaut à 60s. Il n'est pas recommandé d'aller en dessous de 30 car cela pourrait entraîner une suspension de Hilo.

## Exemples d'intégrations Lovelace et d'automatisations

Vous pouvez trouver de nombres exemples et idées pour votre tableau de bord, vos cartes et vos automatisations [dans le wiki du projet](https://github.com/dvd-dev/hilo/wiki/Utilisation)


## Références

Comme indiqué ci-dessus, il s'agit d'une intégration non officielle. Hilo ne prend pas en charge les appels API directs et peut obscurcir le service ou
nous empêcher de l'utiliser.

Pour l'instant, voici les liens Swagger que nous avons trouvés:
* https://wapphqcdev01-automation.azurewebsites.net/swagger/index.html
* https://wapphqcdev01-notification.azurewebsites.net/swagger/index.html
* https://wapphqcdev01-clientele.azurewebsites.net/swagger/index.html

## FAQ

Vous pouvez trouver le FAQ dans le wiki du projet: https://github.com/dvd-dev/hilo/wiki/FAQ

## Contribuer

Rapport tout problème est une bonne manière disponible à tous de contribuer au projet.

Si vous éprouves des problèmes ou voyez des comportements étranges, merci de soumettre un "Issue" et d'y attach vos journaux.

Pour mettre en fonction la journalisation de débogage, vous devez ajouter ceci dans votre fichier `configuration.yaml`:
```
logger:
  default: info
  logs:
     custom_components.hilo: debug
     pyhilo: debug
```

Si vous avez de l'expérience python ou Home Assistant et que vous souhaitez contribuer au code, n'hésitez pas à soumettre une  pull request.

### Soumettre une Pull Request

- D'abord, vous devez créer un `fork` du "repository" dans votre propre espace utilisateur.
- Ensuite, vous pouvez en faire un `clone` sur votre ordinateur.
- Afin de maintenir une sorte de propreté et de standard dans le code, nous avons des linters et des validateurs qui doivent être exécutés via `pre-commit` hooks:
```
pre-commit install --install-hooks
```
- Vous pouvez mainteant procéder à votre modification au code.
- Lorsque vous avez terminé, vous pouvez `stage` les fichiers pour un `commit`:
```
git add path/to/file
```
- Et vous pouvez créer un `commit`:
```
git commit -m "J'ai changé ceci parce que ..."
```
- Finalement, vous pouvez `push` le changement vers votre "upstream repository":
```
git push
```
- Ensuite, si vous visitez le [upstream repository](https://github.com/dvd-dev/hilo), Github devrait vous proposer de créer un "Pull Request" (PR). Vous n'avez qu'à suivre les instructions.

### Collaborateurs initiaux

* [Francis Poisson](https://github.com/francispoisson/)
* [David Vallee Delisle](https://github.com/valleedelisle/)


---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[commits-shield]: https://img.shields.io/github/commit-activity/y/dvd-dev/hilo.svg?style=for-the-badge
[commits]: https://github.com/dvd-dev/hilo/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge
[license]: https://github.com/dvd-dev/hilo/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/dvd-dev/hilo.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40dvd--dev-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/dvd-dev/hilo.svg?style=for-the-badge
[releases]: https://github.com/dvd-dev/hilo/releases
[user_profile]: https://github.com/dvd-dev
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[calver-shield]: https://img.shields.io/badge/calver-YYYY.MM.Micro-22bfda.svg?style=for-the-badge
[calver]: http://calver.org/
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[black]: https://github.com/psf/black
[discord-shield]: https://img.shields.io/badge/discord-Chat-green?logo=discord&style=for-the-badge
[discord]: https://discord.gg/MD5ydRJxpc
[Englishshield]: https://img.shields.io/badge/en-English-red?style=for-the-badge
[English]: https://github.com/dvd-dev/hilo/blob/main/README.en.md
[Françaisshield]: https://img.shields.io/badge/fr-Français-blue?style=for-the-badge
[Français]: https://github.com/dvd-dev/hilo/blob/main/README.md
