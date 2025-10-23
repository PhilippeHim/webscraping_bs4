# coinmarketcap_scraper.py
import time, json, requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from scraping_bs4 import (
    soup_from_html, table_rows, row_to_href,
    extract_one_crypto
)

class CoinMarketCapScraper:
    def __init__(
        self,
        base_url: str = "https://coinmarketcap.com/",
        user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        out_pages: str = "cmc_pages.html",
        out_detail: str = "cmc_detail.html",
        out_json: str = "cryptomonnaie.json"
    ):
        self.base_url  = base_url.rstrip("/") + "/"
        self.ua        = user_agent
        self.f_pages   = out_pages
        self.f_detail  = out_detail
        self.f_json    = out_json

    @staticmethod
    def _save(path, txt):
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)

    def crawl_list(self, url: str | None = None, target: int = 300, wait: int = 20) -> str:
        url = url or self.base_url
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--window-size=1920,1080")
        drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        w = WebDriverWait(drv, wait)
        parts, total, page_i = [], 0, 1
        try:
            drv.get(url)
            while total < target:
                w.until(EC.presence_of_element_located((By.TAG_NAME, "tbody")))
                time.sleep(2)
                last, t0 = 0, time.time()
                while time.time() - t0 < 60:
                    drv.execute_script("window.scrollBy(0, document.body.scrollHeight);")
                    time.sleep(1.8)
                    drv.execute_script("window.scrollBy(0, -200);")
                    time.sleep(1.2)
                    cnt = len(drv.find_elements(By.CSS_SELECTOR, "tbody tr"))
                    if cnt == last: break
                    last = cnt
                html = drv.page_source
                rows = len(drv.find_elements(By.CSS_SELECTOR, "tbody tr"))
                total += rows
                parts.append(f"<section data-page='{page_i}'>\n{html}\n</section>")
                nxt = drv.find_elements(By.CSS_SELECTOR, "ul.pagination li.next a[href]")
                if total >= target or not nxt: break
                drv.get(nxt[0].get_attribute("href"))
                page_i += 1
            self._save(self.f_pages, "\n".join(parts))
            return self.f_pages
        finally:
            try: drv.quit()
            except: pass

    def build_details(self, src_file: str, limit: int = 300, echo: bool = True) -> str:
        with open(src_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        sections = soup.find_all("section", attrs={"data-page": True})
        trs = []
        if sections:
            for sec in sections:
                trs.extend(table_rows(BeautifulSoup(sec.decode_contents(), "html.parser")))
        else:
            trs = table_rows(soup)
        if limit:
            trs = trs[:limit]

        sess = requests.Session()
        sess.headers.update({"User-Agent": self.ua})
        blocks = []

        for i, tr in enumerate(trs, 1):
            href = row_to_href(tr)
            if not href:
                continue
            url = self.base_url.rstrip("/") + href
            try:
                r = sess.get(url, timeout=20)
                r.raise_for_status()
                if echo:
                    data = extract_one_crypto(r.text)
                    ratio = data["stats"]["ratio"]
                    ratio_txt = f"{ratio:.4f}" if isinstance(ratio, (int, float)) else "N/A"
                    print(f"{i:03} | {data['nom']} | {data['prix']} | MC {data['market_cap']} | FDV {data['stats']['fdv']} | ratio {ratio_txt}")
                blocks.append(f"<section data-crypto='{href.strip('/').split('/')[-1]}'>\n<!-- {url} -->\n{r.text}\n</section>")
                time.sleep(1.0)
            except Exception:
                pass

        sess.close()
        self._save(self.f_detail, "\n".join(blocks))
        return self.f_detail

    def export_json(self, detail_file: str) -> str:
        with open(detail_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        items = []
        for sec in soup.find_all("section", attrs={"data-crypto": True}):
            items.append(extract_one_crypto(sec.decode_contents()))
        with open(self.f_json, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        return self.f_json

    def filter_by_ratio(self, input_json: str | None = None, threshold: float = 0.3) -> str:
        src = input_json or self.f_json
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)
        kept = [c for c in data if isinstance(c.get("stats", {}).get("ratio"), (int, float)) and c["stats"]["ratio"] <= threshold]
        out_path = f"cryptomonnaie_ratio_{threshold}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(kept, f, ensure_ascii=False, indent=2)
        print(f"{len(kept)} cryptos ≤ {threshold} → {out_path}")
        return out_path

    def run(self, total: int = 300, take: int = 300, threshold: float = 0.3, echo: bool = True) -> str:
        pages  = self.crawl_list(self.base_url, target=total)
        detail = self.build_details(pages, limit=take, echo=echo)
        js     = self.export_json(detail)
        print(f"OK → {pages}, {detail}, {js}")
        self.filter_by_ratio(js, threshold)
        return js
