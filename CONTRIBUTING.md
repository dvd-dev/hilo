# 🤝 Contribuer

Contribuer à ce projet doit être aussi simple et transparent que possible, que ce soit pour :

- Signaler un bug
- Discuter du code existant
- Proposer des corrections
- Suggérer de nouvelles fonctionnalités

## 🚀 GitHub est utilisé pour tout

GitHub est la plateforme principale pour héberger le code, suivre les problèmes et demandes de fonctionnalités, et accepter les pull requests.

Les pull requests sont le meilleur moyen de proposer des modifications du code :

1. **Créez un fork** du dépôt et créez votre branche à partir de `master`.
2. Si vous avez modifié quelque chose, mettez à jour la documentation.
3. Assurez-vous que votre code suit les règles de formatage (utilisation de `ruff`).
4. Testez votre contribution.
5. Soumettez une pull request !

---

## 📜 Activer la journalisation de débogage

Si vous devez signaler un problème, il est recommandé d'activer la journalisation de débogage en ajoutant ceci dans votre fichier `configuration.yaml` :

```yaml
logger:
  default: info
  logs:
    custom_components.hilo: debug
    pyhilo: debug
```

---

## 🛠️ Préparer un environnement de développement via VSCode DevContainer

Pour faciliter le développement, un environnement est disponible via DevContainer de VSCode. Assurez-vous d'avoir **VSCode** et **Docker** installés sur votre ordinateur.

1. Ouvrez le dossier du projet dans VSCode.
2. Installez l'extension **Remote - Containers**.
3. Ouvrez la palette de commandes (**Ctrl+Shift+P** ou **Cmd+Shift+P**) et recherchez :
   ```
   Remote-Containers: Reopen in Container
   ```
4. Attendez que l'environnement soit prêt.
5. Ouvrez un terminal dans VSCode et exécutez :
   ```bash
   scripts/develop
   ```
   pour installer les dépendances et lancer Home Assistant.
6. VSCode devrait vous proposer d'ouvrir un navigateur pour accéder à Home Assistant. Sinon, ouvrez manuellement :
   ```
   http://localhost:8123
   ```
7. Effectuez la configuration initiale de Home Assistant.
8. Ajoutez l'intégration **Hilo** via l'interface utilisateur.
9. Modifiez les fichiers dans le dossier `custom_components/hilo` et observez les changements en temps réel dans Home Assistant.

Dans le terminal où vous avez lancé `scripts/develop`, les journaux de Home Assistant et de l'intégration Hilo devraient défiler.

---

## 🧪 Tester le code

Des tests existent pour s'assurer que les changements ne brisent pas les fonctionalités existantes. Ils sont situés dans le dossier `/tests`. Il est encouragé de créer des nouveaux tests pour les nouvelles fonctionalités.

Pour exécuter les tests:

1. Ouvrez le projet dans l'environement de votre choix (ex: VSCode DevContainer, tel qu'expliquer en haut).
2. Dans le terminal, exécutez `pytest`.
3. Pour mettre à jours les tests "snapshots", exécutez `pytest --update-snapshots`.

Vous devriez voir le résultat des tests dans le terminal ainsi que les statistiques de couverture des tests.

Il est aussi possible d'exécuter les tests à partir de l'interface graphique de VSCode. Il suffit d'utiliser l'onglet "Testing" dans le menu de gauche.


---

## ✅ Avant de soumettre une Pull Request

Il est essentiel de tester vos modifications sur une installation locale. Vous pouvez modifier les fichiers `.py` de l'intégration directement dans votre dossier `custom_components/hilo`.

⚠ **N'oubliez pas votre copie de sauvegarde !**

Si vous devez modifier `python-hilo` pour vos tests, installez votre fork avec la commande suivante :

```bash
uv pip install -e git+https://github.com/VOTRE_FORK_ICI/python-hilo.git#egg=python-hilo
```

Redémarrez ensuite Home Assistant pour que l'installation prenne effet. Pour revenir en arrière :

```bash
uv pip install python-hilo
```

Puis redémarrez Home Assistant.

---

## 🚀 Soumettre une Pull Request

1. **Créez un fork** du dépôt dans votre espace utilisateur.
2. **Clonez-le** sur votre ordinateur.
3. Pour maintenir une certaine standardisation du code, nous utilisons des **linters** et des **validateurs** exécutés via des hooks `pre-commit` :

   ```bash
   pre-commit install --install-hooks
   ```

4. Apportez vos modifications au code.
5. Une fois terminé, ajoutez les fichiers modifiés :

   ```bash
   git add path/to/file
   ```

6. Créez un commit :

   ```bash
   git commit -m "J'ai changé ceci parce que ..."
   ```

7. Poussez les changements vers votre dépôt distant :

   ```bash
   git push
   ```

8. Sur le dépôt d'origine, **GitHub** devrait vous proposer de créer une **Pull Request** (PR). Suivez les instructions.

---

## 🛠️ Utiliser un style de code cohérent

Nous utilisons [ruff](https://github.com/astral-sh/ruff) pour garantir un formatage et un linting uniforme du code. Vous pouvez également utiliser les paramètres `pre-commit` intégrés dans ce dépôt.

Pour activer `pre-commit` :

```bash
pre-commit install
```

Maintenant, les tests `pre-commit` seront exécutés à chaque commit.

Pour les exécuter manuellement sur tous les fichiers :

```bash
pre-commit run --all-files
```

---

## 📜 Licence

En contribuant, vous acceptez que vos contributions soient sous licence MIT, comme le reste du projet. Pour plus d'informations, consultez la [licence MIT](http://choosealicense.com/licenses/mit/).
