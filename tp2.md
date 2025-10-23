### Récupération de données sur le cours des cryptomonnaies

Vous allez créer un script permettant de récupérer des informations sur le site https://coinmarketcap.com/ qui recense des informations sur les cryptomonnaies.

### Règles de livrable

Vous aurez une approche fonctionnelle et veillerez à rendre votre code explicite.
Si votre script effectue différentes requêtes, vous utiliserez les sessions du module requests.
Il est probable que votre approche initiale s'avère impossible, si c'est le cas, ne persistez pas et essayer de changer votre approche. N'Hésitez pas à demander de l'aide à votre super prof qui vous aidera avec plaisir.

### Questions

- Allez consulter le fichier robots.txt, avez vous le droit de scraper les infos du site sans configurer un User-agent ?
Oui, on peut scraper le site sans utiliser un User-agent, toutefois il y a queqlques sections interdites qui sont précédées par disallow.

- Créer un script qui permet de scraper le nom, le prix et la capitalisation de chacune des 300 plus grosses cryptommonaies. Vous les stockerez dans une liste de dictionnaire de la forme suivante :

  ```
  [
    {
      nom : ...,
      prix : ...,
      market_cap : ...
    },
    {
      nom : ...,
      prix : ...,
      market_cap : ...
    },
    ...
  ]
  ```

Les investisseurs en cryptomonnaie sont très attentifs à une métrique en particulier : la FDV (Fully Diluted Value). Elle indique la capitalisation d'une cryptomonnaie si tous les jetons de cette monnaie était en circulation.
Une différence trop importante entre la market_cap et la FDV peut être un indicateur de future dilution du prix.

- Ajoutez une clé "stats" à votre dictionnaire pour avoir des informations plus poussées comme la FDV, le volume etc.

- Finalement, triez votre dictionnaire pour ressortir uniquement les cryptomonnaies ayant un ratio inférieur ou égal à 0.3 (marketcap/fdv)

- Vous avez déjà fini ? Retravailler votre code en créant une class CoinMarketCapScraper qui permettra d'appeler toutes vos fonctions à partir d'un même objet.
