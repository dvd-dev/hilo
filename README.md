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

Ceci est une version Bêta. Il y aura probablement des bogues, irritants, etc. Merci pour votre patience et d'ouvrir des "Issues".

# Hilo
Intégration pour Home Assistant d'[Hilo](https://www.hydroquebec.com/hilo/fr/)

## Introduction et base

Ceci est l'intégration HACS non-officielle de Hilo sur Home Assistant. [Hilo](https://www.hiloenergie.com/fr-ca/) est une plateforme de domotique développée par une filliale d'[Hydro-Québec](https://www.hydroquebec.com/hilo/fr/).
Cette intégration n'a aucun liens direct avec Hilo ou Hydro Québec. C'est une initiative communautaire. Merci de ne pas contacter Hilo ou Hydro-Québec pour tout problème avec cette intégration Home Assistant. Vous pouvez ouvrir un "issue" dans ce "repository" github à la place.

Si vous souhaitez aider avec le développement de cette intégration, vous pouvez toujours soumettre vos commentaires à partir du formulaire de l'app Hilo et demander à ce qu'ils ouvrent leur API publiquement et qu'ils fournissent un environnement de test pour les développeurs.

### Version TL:DR ("too long, didn't read")

Voir la configuration minimale recommandée [dans le wiki](https://github.com/dvd-dev/hilo/wiki/FAQ-%E2%80%90-Français#avez-vous-une-configuration-recommandée)


Vous pouvez également trouver des exemples en format YAML [dans la section doc/automations du projet](https://github.com/dvd-dev/hilo/tree/main/doc/automations)
Si vous préférez les blueprints, en voici quelques-uns:
  - [Repo de NumerID](https://github.com/NumerID/blueprint_hilo)
  - [Repo de Arim215](https://github.com/arim215/ha-hilo-blueprints)


### Remerciements

Gros merci à [Francis Poisson](https://github.com/francispoisson/) qui est l'auteur de l'intégration originale. Sans le travail qu'il a fait sur cette intégration, je n'aurais probablement jamais considéré utiliser Hilo.

Un autre gros merci à @ic-dev21 pour son implication à plusieurs niveaux.

J'ai décidé de déplacer l'intégration ici, car la dernière mise à jour de Hilo a brisé l'original et j'ai pris le temps de complètement la récrire. Hilo pousse maintenant les lectures des appareils via websocket de SignalR.

### Caractéristiques.
- Supporte les interrupteurs et gradateurs en tant que lumières.
- Voir la température actuelle et changer la consigne des thermostats.
- Obtenir la consommation énergétique des tous les appareils Hilo.
- Générer les "sensor" de puissance et d'énergie consommée.
- Sensor pour les Défis.
- Sensor pour la passerelle Hilo
- Configuration est maintenant faite via l'interface utilisateur
- Mise à jour des lectures plus près du temps réel.
- **NOUVEAU**: Authentification via le site de Hilo
- **NOUVEAU**: Capteur pour la météo extérieure avec icône changeante comme dans l'app Hilo

### À faire:
- Ajouter la fonctionnalité pour d'autres appareils.
- Tests fonctionnels
- [Ajouter des "type hints" au code](https://developers.home-assistant.io/docs/development_typing/)
- Documentation des appels API à Hilo [ici](https://github.com/dvd-dev/python-hilo)
- Ajout automatique des compteurs de consommation électrique

## Installation

### Étape 0 : Avoir une installation compatible
L'intégration nécessite que l'installation du matériel Hilo soit complétée à votre domicile. Il ne sera pas possible de faire l'installation si ça n'est pas fait.

Cette intégration a été testée par des utilisateurs sous HA OS (bare metal et VM), Docker avec l'image officielle (ghcr.io), Podman. Tout autre type d'installation peut mener à des problèmes de permission pour certains fichiers créés lors de l'installation initiale du custom_component.

### Étape 1 : Télécharger les fichiers

#### Option 1 : Via HACS

[![Ouvrir Hilo dans Home Assistant Community Store (HACS).](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dvd-dev&repository=hilo&category=integration)

Assurez-vous d'avoir [HACS](https://hacs.xyz/docs/setup/download/) d'installé.
Sous HACS, cliquer le bouton '+ EXPLORE & DOWNLOAD REPOSITORIES' au bas de la page, rechercher "Hilo", le choisir, et cliquer sur _download_ dans HACS.

#### Option 2 : Manuellement

Télécharger et copier le dossier `custom_components/hilo` de la [dernière version](https://github.com/dvd-dev/hilo/releases/latest) dans votre dossier `custom_components` de Home Assistant.

### Étape 2 : Ajouter l'intégration à HA (<--- étape souvent oubliée)

[![Ouvrir Home Assistant et démarrer la configuration d'une nouvelle intégration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=hilo)

Dans HA, aller à Paramètres > Appareils et services > Intégrations.
Dans le coin inférieur droit, cliquer sur le bouton '+ AJOUTER UNE INTÉGRATION'.

![Ajout intégration](https://github.com/dvd-dev/hilo/assets/108159253/e0529aca-9b13-40e0-9be4-29e347b980ab)

Si l'intégration est correctement installée, vous devriez pouvoir trouver "Hilo" dans la liste. Il est possible d'avoir besoin de vider la mémoire cache de votre navigateur pour que l'intégration s'affiche.

![Recherche intégration](https://github.com/dvd-dev/hilo/assets/108159253/7003a402-9369-4063-ac02-709bd0294e42)

## Configuration (initiale)

La configuration est faite via l'interface utilisateur. Lorsque vous ajoutez l'intégration, vous êtes redirigés vers le site de connexion d'Hilo afin de vous y authentifier.

![Auth step 1](https://github.com/dvd-dev/hilo/assets/108159253/d2e396ea-e6df-40e6-9a14-626ef3be87c8)

![Auth Hilo](https://github.com/dvd-dev/hilo/assets/108159253/e4e98b32-78d0-4c49-a2d7-3bd0ae95e9e0)

Vous devez ensuite accepter de lier votre compte. Pour ce faire, saisir l'adresse (URL ou IP) de votre instance Home Assistant et appuyer sur Link Account.

![Link](https://github.com/dvd-dev/hilo/assets/108159253/5eb945f7-fa5e-458f-b0fe-ef252aaadf93)

Après, vous devrez assigner une pièce de votre maison à chaque appareil.

## Configuration (mise à jour depuis une version antérieure à v2024.3.1)

Après la mise à jour, vous obtiendrez une erreur comme quoi vous devez vous réauthentifier pour que l'intégration fonctionne.

![Reconfigurer](https://github.com/dvd-dev/hilo/assets/108159253/5b69da7f-d547-4ba7-8b64-8eb1d8f28bdb)

![Réauthentifier](https://github.com/dvd-dev/hilo/assets/108159253/6b1bf2c3-0d7a-4eb8-815b-594401fc09ef)

Après avoir lié votre compte comme montré à la section configuration initiale, le message suivant apparaitra.

![Réauthentifié succès](https://github.com/dvd-dev/hilo/assets/108159253/7708b449-24c3-43c1-843b-8697ae192db1)

### Compteurs de consommation électrique

Les compteurs de consommation électrique sont une fonctionalité de cette intégration. Ils étaient initialement générés
par des capteurs "template" et des automatisations mais sont maintenant intégré dans l'intégration.

#### Avertissement

Lorsque l'on active les compteurs, il est recommandé de retirer les anciens capteurs manuels afin de ne pas avoir de
données en double.

Si vous avez un problème et voulez collaborer, merci de mettre en marche la journalisation `debug` et de fournir
un extrait du fichier `home-assistant.log`. La méthode est expliquée [ci-bas.](https://github.com/dvd-dev/hilo?tab=readme-ov-file#contribuer).


#### Procédure

Si vous souhaitez utiliser la génération automatique des capteurs de consommation électrique, suivez les étapes suivantes:

* S'assurer que la plateforme `utility_meter` est chargée dans votre fichier `configuration.yaml` de
Home Assistant. Vous n'avez qu'à ajouter une ligne au fichier comme suit :

    ```
    utility_meter:
    ```

* Cliquer sur `Configure` dans l'interface utilisateur de l'intégration et cocher `Générer compteurs de consommation électrique`.

* (Optionnel) Redémarrez Home Assistant et attendez 5 minutes environ, l'entité `sensor.hilo_energy_total_low` sera créée
  et contiendra des données:
  * Le `status` devrait être `collecting`
  * L'état `state` devrait être un nombre plus grand que 0.

* Toutes les entités et capteurs créés seront préfixés ou suffixés de `hilo_energy_` ou `hilo_rate_`.

* Si vous voyez l'erreur suivante dans le journal de Home Assistant, ceci est du à un bogue de Home Assistant causé par
  le fait que le compteur n'a pas encore accumulé suffisamment de données pour fonctionner. Elle peut être ignorée.

    ```
    2021-11-29 22:03:46 ERROR (MainThread) [homeassistant] Error doing job: Task exception was never retrieved
    Traceback (most recent call last):
    [...]
    ValueError: could not convert string to float: 'None'
    ```
Une fois créés, les compteurs devront être ajoutés manuellement au tableau de bord "Énergie".


### Autres options de configuration

D'autres options sont disponibles sous le bouton "Configurer" dans Home Assistant:

- `Générer compteurs de consommation électrique`: Case à cocher

  Générer automatiquement des compteurs de consommation électrique, voir la procédure ci-dessus pour la configuration
  Nécessite la ligne suivante dans votre fichier configuration.yaml :
  ```
  utility_meter:
  ```

- `Générer seulement les compteurs totaux pour chaque appareil`: Case à cocher

  Calculez uniquement le total d'énergie sans diviser entre le cout faible et le cout élevé

- `Enregistrer également les données de demande et les messages Websocket (nécessite un niveau de journal de débogage à la fois sur l'intégration et sur pyhilo)`: Case à cocher

  Permets un niveau de journalisation plus élevé pour les développeurs/le débogage

- `Vérouiller les entités climate lors de défis Hilo, empêchant tout changement lorsqu'un défi est en cours.`: Case à cocher

  Empêche la modification des consignes de température lors des défis Hilo

- `Suivre des sources de consommation inconnues dans un compteur séparé. Ceci est une approximation calculée à partir de la lecture du compteur intelligent.`: Case à cocher

  Toutes les sources d'énergie autres que le matériel Hilo sont regroupées dans un seul capteur. Utilise la lecture du compteur intelligent de la maison.

- `Nom du tarif Hydro Québec ('rate d' ou 'flex d')`: chaine

  Définissez le nom du plan tarifaire d'Hydro-Québec.
  Seules 2 valeurs sont prises en charge pour le moment:
  - 'rate d'
  - 'flex d'

- `Intervalle de mise à jour (min: 60s)`: Nombre entier

  Nombre de secondes entre chaque mise à jour de l'appareil. Par défaut à 60s. Il n'est pas recommandé d'aller en dessous de 30, car cela pourrait entrainer une suspension de Hilo. Depuis [2023.11.1](https://github.com/dvd-dev/hilo/releases/tag/v2023.11.1) le minimum est passé de 15s à 60s.

## Exemples d'intégrations Lovelace et d'automatisations

Vous pouvez trouver de nombres exemples et idées pour votre tableau de bord, vos cartes et vos automatisations [dans le wiki du projet](https://github.com/dvd-dev/hilo/wiki/Utilisation)

Vous pouvez également trouver des exemples en format YAML [dans la section doc/automations du projet](https://github.com/dvd-dev/hilo/tree/main/doc/automations)

## Références

Comme indiqué ci-dessus, il s'agit d'une intégration non officielle. Hilo ne prend pas en charge les appels API directs et peut obscurcir le service ou
nous empêcher de l'utiliser.

Pour l'instant, voici les liens Swagger que nous avons trouvés:
* https://wapphqcdev01-automation.azurewebsites.net/swagger/index.html
* https://wapphqcdev01-notification.azurewebsites.net/swagger/index.html
* https://wapphqcdev01-clientele.azurewebsites.net/swagger/index.html

## FAQ

Vous pouvez trouver la FAQ dans le wiki du projet: https://github.com/dvd-dev/hilo/wiki/FAQ

## Contribuer

Rapporter tout problème est une bonne manière disponible à tous de contribuer au projet.

Si vous éprouvez des problèmes ou voyez des comportements étranges, merci de soumettre une "Issue" et d'y attacher vos journaux.

Pour mettre en fonction la journalisation de débogage, vous devez ajouter ceci dans votre fichier `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
     custom_components.hilo: debug
     pyhilo: debug
```

Si vous avez de l'expérience python ou Home Assistant et que vous souhaitez contribuer au code, n'hésitez pas à soumettre un pull request.

### Préparer un environnement de développement via VSCode DevContainer

Pour faciliter le développement, un environnement de développement est disponible via DevContainer de VSCode. Pour l'utiliser, vous devez avoir [VSCode](https://code.visualstudio.com/) et [Docker](https://www.docker.com/) installés sur votre ordinateur.

1. Ouvrir le dossier du projet dans VSCode
2. Installer l'extension [Remote - Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
3. Ouvrir la palette de commande (Ctrl+Shift+P ou Cmd+Shift+P) et chercher "Remote-Containers: Reopen in Container"
4. Attendre que l'environnement soit prêt
5. Ouvrir un terminal dans VSCode et exécuter `scripts/develop` pour installer les dépendances et lancer Home Assistant.
6. VSCode devrait vous proposer d'ouvrir un navigateur pour accéder à Home Assistant. Vous pouvez aussi ouvrir un navigateur manuellement et accéder à [http://localhost:8123](http://localhost:8123).
7. Vous allez devoir faire la configuration initiale de Home Assistant.
8. Vous allez devoir ajouter l'intégration Hilo via l'interface utilisateur.
9. Vous pouvez maintenant modifier les fichiers dans le dossier `custom_components/hilo` et voir les changements en temps réel dans Home Assistant.
10. Dans le terminal ou vous avez lancé `scripts/develop`, les logs de Home Assistant et de l'intégration HILO devraient défiler.

### Avant de soumettre une Pull Request

Il va sans dire qu'il est important de tester vos modifications sur une installation locale. Il est possible de modifier les fichiers .py de l'intégration directement dans votre dossier `custom_components/hilo`.

N'oubliez pas votre copie de sauvegarde!

Si vous devez modifier python-hilo pour vos tests, il est possible d'installer votre "fork" avec la commande suivante dans votre CLI :

```console
$ pip install -e git+https://github.com/VOTRE_FORK_ICI/python-hilo.git#egg=python-hilo
```

Vous devrez ensuite redémarrer Home Assistant pour que votre installation prenne effet. Pour revenir en arrière, il suffit de faire:

```console
$ pip install python-hilo
```

Et redémarrez Home Assistant

### Soumettre une Pull Request

- D'abord, vous devez créer un `fork` du "repository" dans votre propre espace utilisateur.
- Ensuite, vous pouvez en faire un `clone` sur votre ordinateur.
- Afin de maintenir une sorte de propreté et de standard dans le code, nous avons des linters et des validateurs qui doivent être exécutés via `pre-commit` hooks :
```console
$ pre-commit install --install-hooks
```
- Vous pouvez maintenant procéder à votre modification au code.
- Lorsque vous avez terminé, vous pouvez `stage` les fichiers pour un `commit`:
```console
$ git add path/to/file
```
- Et vous pouvez créer un `commit`:
```console
$ git commit -m "J'ai changé ceci parce que ..."
```

- Finalement, vous pouvez `push` le changement vers votre "upstream repository" :
```console
$ git push
```

- Ensuite, si vous visitez le [upstream repository](https://github.com/dvd-dev/hilo), Github devrait vous proposer de créer un "Pull Request" (PR). Vous n'avez qu'à suivre les instructions.

### Collaborateurs initiaux

* [Francis Poisson](https://github.com/francispoisson/)
* [David Vallee Delisle](https://github.com/valleedelisle/)

### Mentions très honorables
* [Ian Couture](https://github.com/ic-dev21/): Il tient cet addon du bout de ces bras depuis un certain temps
* [Hilo](https://www.hiloenergie.com): Merci à Hilo pour son support et ses contributions.

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
