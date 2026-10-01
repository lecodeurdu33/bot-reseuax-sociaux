# Bot de veille réseaux sociaux

Chaque jour, le bot cherche les vidéos publiées **aujourd'hui** qui correspondent à vos mots-clés
(prénom, « aura battle », école, ville…) et génère `rapport.html` avec :

- les liens trouvés (YouTube via l'API officielle ; TikTok, Instagram, Snapchat, CapCut, Facebook, X via Google Programmable Search, limité aux dernières 24 h) ;
- un badge **NOUVEAU** pour ce qui n'a pas déjà été vu ;
- des liens de recherche à ouvrir à la main (filtrés « aujourd'hui ») pour chaque plateforme ;
- le lien du formulaire de signalement de chaque plateforme.

> **Limites honnêtes** : TikTok, Instagram, Snapchat et CapCut n'offrent pas de recherche publique par API, et les scraper
> viole leurs conditions et casse vite. Le bot s'appuie donc sur l'indexation Google (les vidéos très récentes ou privées
> peuvent manquer) : **les liens manuels du rapport restent indispensables**. Le bot ne signale ni ne supprime rien lui-même.

## Installation

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml   # puis mettez vos mots-clés
export YOUTUBE_API_KEY=...           # console.cloud.google.com → YouTube Data API v3 (gratuit)
export GOOGLE_API_KEY=...            # même projet : Custom Search API
export GOOGLE_CSE_ID=...             # programmablesearchengine.google.com → « Rechercher sur tout le Web »
python bot.py                        # ouvre ensuite rapport.html
```

Sans clés, le bot fonctionne quand même : le rapport ne contient alors que les liens manuels.
Automatiser (cron, tous les jours à 18 h) : `0 18 * * * cd /chemin/du/bot && python bot.py`

## Quoi faire quand vous trouvez la vidéo

1. Captures d'écran + copie de l'URL (preuves).
2. Signalement via le lien « signaler » : motif **atteinte à la vie privée / mineur / droit à l'image**.
3. En France : **3018** (e-Enfance, gratuit, peut faire retirer les contenus), [internet-signalement.gouv.fr](https://www.internet-signalement.gouv.fr), droit à l'effacement des mineurs (CNIL), et prévenir l'établissement scolaire.

Les liens de signalement changent parfois : vérifiez-les dans `REPORT_LINKS` de `bot.py`.

## Tests

`python -m pytest tests`

## Version Windows (bot.exe)

L'exécutable est compilé par GitHub Actions (onglet **Actions → Build bot.exe → Run workflow**, puis télécharger
l'artefact `bot-reseaux-sociaux`). Dézippez, copiez `config.example.yaml` en `config.yaml` à côté de `bot.exe`,
remplissez les mots-clés (et les clés API dans le même fichier), puis double-cliquez sur `bot.exe` :
le rapport s'ouvre dans le navigateur. Windows peut afficher un avertissement SmartScreen (exécutable non signé) :
« Informations complémentaires → Exécuter quand même ».
