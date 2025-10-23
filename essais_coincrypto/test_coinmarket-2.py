import os, re, time, json, requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "https://coinmarketcap.com/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
F_PAGES = "cmc_pages.html"
F_DETAIL = "cmc_detail.html"
F_JSON = "cryptomonnaie.json"

RX_MONEY = re.compile(r'\$[\s0-9\.,]+[A-Za-z]*')
RX_PCT = re.compile(r'[-+]?(\d+(\.\d+)?)\s?%')

def _rows(s):
    tb = s.find('tbody')
    if not tb: return []
    r = tb.find_all('tr', recursive=False)
    return r if r else tb.find_all('tr')

def _href_from_tr(tr):
    for a in tr.find_all("a", href=True):
        h = a["href"]
        if re.match(r"^/currencies/[^/]+/?$", h):
            return h
    return None

def _save(path, txt):
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)

def crawl_list(url, target=300, wait=20):
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1920,1080")
    drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    w = WebDriverWait(drv, wait)
    parts, tot, page_i = [], 0, 1
    try:
        drv.get(url)
        while tot < target:
            w.until(EC.presence_of_element_located((By.TAG_NAME, "tbody")))
            time.sleep(2)
            last, t0 = 0, time.time()
            while time.time() - t0 < 60:
                drv.execute_script("window.scrollBy(0, document.body.scrollHeight);")
                time.sleep(1.8)
                drv.execute_script("window.scrollBy(0, -200);")
                time.sleep(1.2)
                n = len(drv.find_elements(By.CSS_SELECTOR, "tbody tr"))
                if n == last: break
                last = n
            html = drv.page_source
            nrows = len(drv.find_elements(By.CSS_SELECTOR, "tbody tr"))
            tot += nrows
            parts.append(f"<section data-page='{page_i}'>\n{html}\n</section>")
            nxt = drv.find_elements(By.CSS_SELECTOR, "ul.pagination li.next a[href]")
            if tot >= target or not nxt: break
            drv.get(nxt[0].get_attribute("href"))
            page_i += 1
        _save(F_PAGES, "\n".join(parts))
        return F_PAGES
    finally:
        try: drv.quit()
        except: pass

def build_details(src_file, limit=300):
    with open(src_file, "r", encoding="utf-8") as f:
        s = BeautifulSoup(f, "html.parser")
    secs = s.find_all("section", attrs={"data-page": True})
    trs = []
    if secs:
        for sec in secs:
            trs.extend(_rows(BeautifulSoup(sec.decode_contents(), "html.parser")))
    else:
        trs = _rows(s)
    if limit: trs = trs[:limit]
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    blocs = []
    for i, tr in enumerate(trs, 1):
        h = _href_from_tr(tr)
        if not h: continue
        u = BASE_URL.rstrip("/") + h
        try:
            r = sess.get(u, timeout=20)
            r.raise_for_status()
            blocs.append(f"<section data-crypto='{h.strip('/').split('/')[-1]}'>\n<!-- {u} -->\n{r.text}\n</section>")
            time.sleep(1.2)
        except Exception:
            pass
    sess.close()
    _save(F_DETAIL, "\n".join(blocs))
    return F_DETAIL

def _money_to_float(v):
    if not v: return None
    x = v.replace('$', '').replace(',', '').strip().upper()
    m = 1.0
    for suf, mul in (('T',1e12),('B',1e9),('M',1e6),('K',1e3)):
        if x.endswith(suf):
            m = mul; x = x[:-1]; break
    try: return float(x) * m
    except: return None

def _box_val(soup, lab_rx, alt=None):
    r1 = re.compile(lab_rx, re.I)
    r2 = re.compile(alt, re.I) if alt else None
    for box in soup.select("div.StatsInfoBox_base__kP2xM"):
        dt = box.find("dt")
        if not dt: continue
        lbl = dt.get_text(" ", strip=True)
        if r1.search(lbl) or (r2 and r2.search(lbl)):
            dd = box.find("dd")
            if not dd: continue
            txt = dd.get_text(" ", strip=True)
            money = RX_MONEY.search(txt) or RX_MONEY.search((dd.find("span") or dd).get_text(" ", strip=True))
            pct = RX_PCT.search(txt)
            return (money.group(0) if money else None), (pct.group(0) if pct else None)
    return (None, None)

def _pick_name(sym):
    n = sym.find("span", attrs={"data-role": "coin-name"})
    if n:
        return n.get("title") or n.get_text(strip=True)
    h = sym.find("h1") or sym.find("h2")
    return h.get_text(" ", strip=True) if h else None

def _pick_price(sym):
    n = sym.select_one('span[data-test="text-cdp-price-display"]')
    if n:
        m = RX_MONEY.search(n.get_text(" ", strip=True))
        return m.group(0) if m else n.get_text(" ", strip=True)
    n = sym.find(attrs={"data-testid": "price-value"})
    if n:
        m = RX_MONEY.search(n.get_text(" ", strip=True))
        return m.group(0) if m else n.get_text(" ", strip=True)
    n = sym.find("div", class_=re.compile(r"priceValue", re.I))
    if n:
        m = RX_MONEY.search(n.get_text(" ", strip=True))
        return m.group(0) if m else n.get_text(" ", strip=True)
    return None

def _one_crypto(sec_html):
    s = BeautifulSoup(sec_html, "html.parser")
    name = _pick_name(s) or "N/A"
    price = _pick_price(s) or "N/A"
    mc, _ = _box_val(s, r"Capitalisation|Market\s*Cap", r"Cap\.? Marche|Market")
    fdv, _ = _box_val(s, r"\bFDV\b|dilut", "Fully Diluted")
    vol, _ = _box_val(s, r"Volume\s*\(24h\)", "Volume")
    r = None
    mc_f = _money_to_float(mc)
    fdv_f = _money_to_float(fdv)
    if mc_f and fdv_f and fdv_f != 0:
        r = mc_f / fdv_f
    return {"nom": name, "prix": price, "market_cap": mc or "N/A", "stats": {"fdv": fdv or "N/A", "volume": vol or "N/A", "ratio": r}}

def export_json(detail_file):
    with open(detail_file, "r", encoding="utf-8") as f:
        s = BeautifulSoup(f, "html.parser")
    out = []
    for sec in s.find_all("section", attrs={"data-crypto": True}):
        out.append(_one_crypto(sec.decode_contents()))
    with open(F_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return F_JSON

def run(url=BASE_URL, total=300, take=300):
    pages = crawl_list(url, target=total)
    detail = build_details(pages, limit=take)
    js = export_json(detail)
    print(f"OK → {pages}, {detail}, {js}")

if __name__ == "__main__":
    run()
