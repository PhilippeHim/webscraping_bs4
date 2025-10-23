
# 🪙 Projet de scraping CoinMarketCap

> **Formation IA School – Projet Python / Web Scraping**
> Auteur : *Philippe H.*
> Date : *2025*

---

## 🎯 Objectif du projet

L’objectif de ce projet est de **récupérer automatiquement les données des 300 plus grandes cryptomonnaies** listées sur [**CoinMarketCap**](https://coinmarketcap.com/), afin d’en extraire :

* leur **nom**,
* leur **prix**,
* leur **capitalisation boursière (market cap)**,
* ainsi que plusieurs **indicateurs avancés** (FDV, volume, ratio market_cap / FDV).

Le résultat est enregistré dans un fichier JSON sous la forme :

```json
[
  {
    "nom": "Bitcoin",
    "prix": "$64,500",
    "market_cap": "$1,270,000,000,000",
    "stats": {
      "fdv": "$1,350,000,000,000",
      "volume": "$25,000,000,000",
      "ratio": 0.94
    }
  },
  ...
]
```

Enfin, le script trie les cryptomonnaies ayant un **ratio ≤ 0.3**, signe d’un potentiel risque de **dilution future** du prix.

---

## 🧠 Contexte pédagogique

Ce projet s’inscrit dans le cadre du module de **Web Scraping et automatisation de la collecte de données**.
L’objectif était de :

* comprendre le fonctionnement du protocole HTTP et des restrictions liées au scraping (robots.txt, user-agent),
* tester différentes **approches techniques** (requests, headers, Selenium, etc.),
* apprendre à **structurer un projet** avec une architecture claire, orientée objet, et un **code réutilisable**.

---

## 🧱 Architecture du projet

```
.
├── main.py                    # point d'entrée du script
├── coinmarketcap_scraper.py   # classe principale CoinMarketCapScraper
├── scraping_bs4.py            # fonctions utilitaires de parsing BeautifulSoup
├── .env                       # variables d’environnement (URL, USER_AGENT…)
├── .gitignore                 # exclusion des fichiers inutiles (Mac, venv, etc.)
└── out/                       # répertoire de sortie (HTML, JSON)
```

---

## 🧩 Structure du code

### 1. `scraping_bs4.py` — Parsing et nettoyage HTML

Ce module regroupe toutes les fonctions d’analyse du contenu HTML :

* **`extract_one_crypto()`** → extrait `nom`, `prix`, `market_cap`, `fdv`, `volume`, `ratio` depuis une page détail.
* **`money_to_float()`** → convertit des montants comme `$1.25B` ou `$950M` en nombre réel.
* **`stats_value_box()`** → détecte les valeurs dans les blocs `<dt>/<dd>`.
* **`row_to_href()`** → extrait les URLs de chaque cryptomonnaie depuis la liste principale.

➡️ En clair : c’est la “boîte à outils” BeautifulSoup.
Elle ne télécharge rien, mais sait **comprendre** le HTML récupéré.

---

### 2. `coinmarketcap_scraper.py` — La classe principale

Ce fichier contient la classe **`CoinMarketCapScraper`**, qui orchestre toutes les étapes du scraping :

#### 🔹 Méthodes principales :

| Méthode             | Description                                                                                                                                            |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `crawl_list()`      | Utilise **Selenium** pour parcourir la liste principale (scroll/pagination) et sauvegarder le HTML.                                                    |
| `build_details()`   | Lit le fichier de liste, envoie des **requêtes `requests`** sur chaque URL de cryptomonnaie, affiche la progression en direct, et concatène les pages. |
| `export_json()`     | Extrait les infos (nom, prix, market cap, FDV, etc.) et les enregistre dans `cryptomonnaie.json`.                                                      |
| `filter_by_ratio()` | Filtre les cryptos avec un ratio market_cap / FDV ≤ 0.3 et crée un fichier `cryptomonnaie_ratio_0.3.json`.                                             |
| `run()`             | Point d’entrée : exécute tout le pipeline de bout en bout.                                                                                             |

Cette approche **combine Selenium et requests** :

* Selenium = navigation dynamique pour charger la table JS,
* Requests = récupération rapide des pages détail.

---

### 3. `main.py` — Point d’entrée

Le fichier `main.py` instancie la classe et exécute le scraping complet :

```python
from coinmarketcap_scraper import CoinMarketCapScraper

if __name__ == "__main__":
    scraper = CoinMarketCapScraper()
    scraper.run(total=300, take=300, threshold=0.3, echo=True)
```

Exécution :

```bash
python main.py
```

---

## ⚙️ Bibliothèques utilisées

| Librairie                           | Rôle                                         |
| ----------------------------------- | -------------------------------------------- |
| **requests**                        | Requêtes HTTP rapides sur les pages détail   |
| **selenium**                        | Exécution du JavaScript pour la page liste   |
| **beautifulsoup4**                  | Parsing HTML et extraction des données       |
| **webdriver-manager**               | Gestion automatique du driver Chrome         |
| **dotenv**                          | Chargement des variables d’environnement     |
| **json / re / os / time / pathlib** | Standard Python (fichiers, regex, I/O, etc.) |

---

## 🔐 Fichier `.env` (optionnel)

Exemple :

```bash
URL=https://coinmarketcap.com/
USER_AGENT=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)
SAVE_DIR=out
WAIT_TIME=5
WAIT_TIME_MAX=15
```

Ces valeurs sont chargées automatiquement via `python-dotenv`.

---

## 🧰 Installation et exécution

### 1️⃣ Installation de l’environnement

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2️⃣ Lancer le scraping complet

```bash
python main.py
```

Résultat :

```
cmc_pages.html
cmc_detail.html
cryptomonnaie.json
cryptomonnaie_ratio_0.3.json
```


---

## 🧩 Partie explicative

Voici le récap rapide de tout ce qu’on a tenté pour CoinMarketCap, pourquoi ça bloquait, et pourquoi la dernière approche marche 

# robots.txt
Tout d'abord le fichier robots.txt de CoinMarketCap nous donne la permission de voir les pages publiques de la liste et de détail, mais nous devons utiliser un déguisement (User-Agent) et respecter un délai pour ne pas être bloqués par leurs systèmes de sécurité.

# 1) `requests` “tout simple”, sans en-têtes

* **Idée** : `requests.get(URL)` puis BeautifulSoup sur le HTML.
* **Ce qui s’est passé** : soit **403 Forbidden**, soit **HTML quasi vide** (pas de `<tbody><tr>`).
* **Pourquoi ça échoue** :

  * **Anti-bot/WAF** : absence de User-Agent crédible, pas de cookies ni de navigation “réaliste”.
  * **Rendu client** : la **liste des cryptos est chargée en JavaScript** → le HTML initial ne contient pas les lignes du tableau.

# 2) `requests` avec User-Agent minimal / quelques headers

* **Idée** : même chose mais en ajoutant un `User-Agent` et 2-3 en-têtes.
* **Résultat** : un peu mieux, mais **403** fréquents ou **contenu toujours incomplet**.
* **Pourquoi ça échoue** :

  * Les protections comparent plus de signaux (cookies initiaux, ordre des requêtes, entêtes “navigateur” cohérents, etc.).
  * Même avec accès, **la page liste reste vide sans exécuter le JS**.

# 3) `requests` + “gros” headers (UA réaliste, Referer, Accept-Language…)

* **Idée** : se rapprocher d’un navigateur (headers complets).
* **Résultat** : un peu moins de 403, mais **toujours pas de lignes** dans la page **liste** (DOM rendu côté client).
* **Pourquoi ça échoue** :

  * **Problème structurel** (SPA) : sans moteur JS, le HTML ne contiendra pas les données de la table.
  * Les pages **détail** sont parfois **partiellement SSR**, mais pas fiable à 100% → extraction inconstante.

# 4) Tout faire au navigateur (Playwright/Selenium) — “plein JS”

* **Idée** : ouvrir **chaque** page (liste + détail) avec un navigateur headless, attendre le rendu, puis scraper.
* **Résultat** : **fonctionne** techniquement, mais **trop lent** et plus fragile (timeouts, ressources CPU/RAM, risque de blocage).
* **Pourquoi c’est peu pratique** :

  * Démarrer un moteur pour **des centaines de pages détail** coûte cher.
  * Les temps d’attente et de synchronisation (sélecteurs, `wait_until`, `networkidle`) s’additionnent.

# ✅ 5) Méthode retenue (celle qui marche)

**Selenium pour la liste + `requests` pour les détails + BeautifulSoup partout**

**Pipeline**

1. **Selenium (headless)** sur la **page liste** :

   * scroll/pagination jusqu’à ~300 lignes,
   * on **sauvegarde le HTML** (ex.: `cmc_pages.html`).
2. On **parse ce HTML** (BeautifulSoup) pour **récupérer les URLs** des cryptos (`/currencies/...`).
3. Pour **chaque URL détail**, on envoie une **requête `requests`** (en-têtes réalistes) → souvent **suffisant** car la page détail expose le prix/les stats dans le HTML final (ou des blocs SSR).
4. **BeautifulSoup** extrait :

   * `nom`, `prix`, `market_cap`, et un bloc **`stats`** (FDV, volume 24h, etc.) en s’appuyant sur la **sémantique `<dt>/<dd>`** quand disponible (plus robuste que les classes volatiles).
5. On **sérialise** en `cryptomonnaie.json`, puis on **filtre** les entrées avec **ratio `market_cap / fdv ≤ 0.3`** dans un second JSON.

**Pourquoi ça marche mieux**

* **La liste est 100% JS** → on **doit** passer par un navigateur (Selenium) une seule fois pour collecter les liens.
* Les **pages détail** sont **souvent assez SSR** pour qu’un `requests` + BS4 suffise (rapide, léger, scalable).
* On évite de lancer un navigateur pour chaque détail → **gros gain de performance et de stabilité**.
* Le parsing par **`<dt>/<dd>`** rend le code **résilient** aux changements de classes CSS.

**Ce qu’on a fait pour fiabiliser**

* Headers réalistes (UA, Referer) côté `requests`.
* Attentes explicites côté Selenium (présence de `<tbody>`, scroll jusqu’à stabilisation).
* Fallbacks CSS raisonnables + normalisation des libellés (FR/EN) pour `market_cap`, `FDV`, `volume`.
* Convertisseurs de montants (`$1.92T`, `$420.5B`, etc.) pour calculer les **ratios**.

---

## En Bref

* Les approches **100% `requests`** échouent sur la **liste** car **JS** ➝ **HTML vide** ou **403**.
* Les approches **100% navigateur** marchent mais **lentes** et lourdes.
* La solution **hybride** (Selenium pour la **liste**, `requests` pour les **détails**) est **la seule** qui a réuni **fiabilité + rapidité**, avec un parsing **robuste** via `<dt>/<dd>` et une sortie JSON propre + filtre FDV.

---

## 💬 Conclusion

Ce projet montre que le **scraping n’est pas qu’une question de code**, mais surtout d’**analyse de structure web et de stratégie d’extraction** :
identifier les pages rendues côté client, comprendre le JavaScript, gérer les délais, et surtout, **penser robuste et scalable**.

L’approche retenue — Selenium pour la découverte, requests pour la collecte, BeautifulSoup pour l’analyse — représente un **équilibre optimal entre performance et fiabilité**.

---
