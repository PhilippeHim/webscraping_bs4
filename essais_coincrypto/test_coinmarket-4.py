import time
import json
import re
import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# ----------------------------------------------------------------------
# PARAMÈTRES GLOBAUX
# ----------------------------------------------------------------------
URL_BASE = "https://coinmarketcap.com"
URL_LISTE_CRYPTOS = f"{URL_BASE}/fr/"
NOM_FICHIER_JSON = "cryptomonnaie.json"   # <- demandé
CIBLE_PAGES = 3                           # 3 pages * ~100 résultats
NOMBRE_CIBLE_TOTAL = 300
TIMEOUT_PAGE_LOAD = 15000                 # Playwright (liste) uniquement
PAUSE_ENTRE_PAGES_LISTE = 3               # après le rendu de la liste
PAUSE_ENTRE_REQUETES_DETAIL = 0.7         # politesse réseau
# ----------------------------------------------------------------------

# En-têtes HTTP réalistes pour requests (sans timeout)
BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


# ========== PARTIE A : récupérer les 300 liens via Playwright (pagination JS) ==========

def get_all_hrefs_by_direct_url(url_base: str, total_pages: int):
    """
    Parcourt /?lang=fr&page=X avec Playwright pour obtenir les ~100*pages liens.
    """
    all_links = []
    with sync_playwright() as p:
        browser = None
        try:
            print(f"1/2: Récupération des liens (pagination JS) …")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for page_num in range(1, total_pages + 1):
                url_page = f"{url_base}/?lang=fr&page={page_num}"
                print(f"   → Page {page_num}/{total_pages} : {url_page}")

                page.goto(url_page, wait_until="networkidle", timeout=TIMEOUT_PAGE_LOAD)
                # Attendre que ~100 lignes soient présentes
                page.wait_for_selector("tbody tr:nth-child(100)", timeout=TIMEOUT_PAGE_LOAD)
                time.sleep(PAUSE_ENTRE_PAGES_LISTE)

                soup = BeautifulSoup(page.content(), "html.parser")
                for a in soup.select("tbody tr a.cmc-link"):
                    href = a.get("href")
                    # garder seulement les liens “/currencies/xxx/”
                    if href and "/currencies/" in href and "#" not in href:
                        full = f"{URL_BASE}{href}"
                        if full not in all_links:
                            all_links.append(full)

            return all_links

        except Exception as e:
            print(f"❌ Erreur Playwright (pagination): {e}")
            return all_links
        finally:
            if browser:
                browser.close()


# ========== PARTIE B : scrap “détail” en requests simple (sans timeout) ==========

def build_headers_for(href: str) -> dict:
    """Ajoute un Referer spécifique par requête (certains WAF l'aiment bien)."""
    h = BASE_HEADERS.copy()
    o = urlparse(href)
    h["Referer"] = f"{o.scheme}://{o.netloc}/"
    return h

def fetch_detail_html(href: str) -> str | None:
    """
    Récupère le HTML d'une page de crypto avec requests, **sans timeout**.
    Si 403/5xx, on retente doucement (x2).
    """
    for attempt in range(1, 3):  # 2 tentatives max
        try:
            r = requests.get(href, headers=build_headers_for(href))  # pas de timeout
            if r.status_code == 200 and r.text.strip():
                return r.text
            else:
                print(f"    ⚠️ Status {r.status_code} sur {href} (tentative {attempt})")
        except requests.RequestException as e:
            print(f"    ⚠️ Erreur réseau {e} (tentative {attempt})")
        time.sleep(0.6 * attempt)
    return None

def clean_text(t: str) -> str:
    if not t:
        return ""
    t = t.replace("\xa0", " ").strip()
    t = re.sub(r"\s+", " ", t)
    return t

def extract_details_from_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    out = {"nom": "N/A", "prix": "N/A", "market_cap": "N/A"}

    # NOM
    el_name = (
        soup.select_one('span[data-role="coin-name"]')
        or soup.select_one("h1, h2")
    )
    if el_name:
        out["nom"] = el_name.get_text(strip=True)

    # PRIX
    el_price = (
        soup.select_one('span[data-test="text-cdp-price-display"]')
        or soup.select_one('div[class*="priceValue"]')
    )
    if el_price:
        out["prix"] = el_price.get_text(strip=True)

    # MARKET CAP — nouvelle version robuste
    dt_cap = soup.find("dt", string=re.compile("Capitalisation boursière", re.I))
    if dt_cap:
        span_val = dt_cap.find_next("span")
        if span_val:
            out["market_cap"] = span_val.get_text(strip=True)
    else:
        # Fallback si la structure <dt>/<dd> a changé
        cap_el = soup.select_one(".CoinMetrics_sib-content-wrapper__E8lu8 span") \
                  or soup.select_one('div[class*="CoinMetrics"] span')
        if cap_el:
            out["market_cap"] = cap_el.get_text(strip=True)

    return out



# ========== PARTIE C : orchestration & sauvegarde JSON ==========

def sauvegarder_json(data, filename):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"\n✅ Données sauvegardées dans {filename} ({len(data)} entrées).")
    except Exception as e:
        print(f"❌ Erreur écriture JSON : {e}")

def main():
    # 1) Récupérer les liens (via Playwright, car liste rendue par JS)
    liens = get_all_hrefs_by_direct_url(URL_BASE, CIBLE_PAGES)
    print(f"\n→ {len(liens)} liens collectés. Extraction en requests simple …")

    # 2) Détails “requests only” + parsing
    results = []
    for i, href in enumerate(liens, start=1):
        print(f"[{i:03}/{len(liens)}] {href}")
        html = fetch_detail_html(href)
        if not html:
            print("    ❌ HTML indisponible (403/timeout/JS-only ?)")
        else:
            details = extract_details_from_html(html)
            results.append({
                "nom": details.get("nom", "N/A"),
                "prix": details.get("prix", "N/A"),
                "market_cap": details.get("market_cap", "N/A")
            })
        time.sleep(PAUSE_ENTRE_REQUETES_DETAIL)

    # 3) Sauvegarde finale
    if results:
        # bornage à 300 si plus de liens
        results = results[:NOMBRE_CIBLE_TOTAL]
        sauvegarder_json(results, NOM_FICHIER_JSON)
    else:
        print("❌ Aucun détail exploitable. Rien à sauvegarder.")

if __name__ == "__main__":
    main()
