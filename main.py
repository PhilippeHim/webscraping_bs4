# main.py
from coinmarketcap_scraper import CoinMarketCapScraper

if __name__ == "__main__":
    scraper = CoinMarketCapScraper(
        base_url="https://coinmarketcap.com/",
        out_pages="cmc_pages.html",
        out_detail="cmc_detail.html",
        out_json="cryptomonnaie.json"
    )
    scraper.run(total=300, take=300, threshold=0.3, echo=True)
