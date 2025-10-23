# scraping_bs4.py
import re
from bs4 import BeautifulSoup

RX_MONEY = re.compile(r'\$[\s0-9\.,]+[A-Za-z]*')
RX_PCT   = re.compile(r'[-+]?(\d+(\.\d+)?)\s?%')

def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")

def table_rows(soup: BeautifulSoup):
    tbody = soup.find("tbody")
    if not tbody:
        return []
    rows = tbody.find_all("tr", recursive=False)
    return rows if rows else tbody.find_all("tr")

def row_to_href(tr) -> str | None:
    for a in tr.find_all("a", href=True):
        h = a["href"]
        if re.match(r"^/currencies/[^/]+/?$", h):
            return h
    return None

def money_to_float(v: str | None) -> float | None:
    if not v:
        return None
    x = v.replace("$", "").replace(",", "").strip().upper()
    mult = 1.0
    for suf, m in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if x.endswith(suf):
            mult = m
            x = x[:-1]
            break
    try:
        return float(x) * mult
    except Exception:
        return None

def pick_name(soup: BeautifulSoup) -> str:
    n = soup.find("span", attrs={"data-role": "coin-name"})
    if n:
        return n.get("title") or n.get_text(strip=True)
    h = soup.find("h1") or soup.find("h2")
    return h.get_text(" ", strip=True) if h else "N/A"

def pick_price(soup: BeautifulSoup) -> str:
    n = soup.select_one('span[data-test="text-cdp-price-display"]')
    if n:
        m = RX_MONEY.search(n.get_text(" ", strip=True))
        return m.group(0) if m else n.get_text(" ", strip=True)
    n = soup.find(attrs={"data-testid": "price-value"})
    if n:
        m = RX_MONEY.search(n.get_text(" ", strip=True))
        return m.group(0) if m else n.get_text(" ", strip=True)
    n = soup.find("div", class_=re.compile(r"priceValue", re.I))
    if n:
        m = RX_MONEY.search(n.get_text(" ", strip=True))
        return m.group(0) if m else n.get_text(" ", strip=True)
    return "N/A"

def stats_value_box(soup: BeautifulSoup, label_rx: str, alt_rx: str | None = None) -> tuple[str | None, str | None]:
    r1 = re.compile(label_rx, re.I)
    r2 = re.compile(alt_rx, re.I) if alt_rx else None
    for box in soup.select("div.StatsInfoBox_base__kP2xM"):
        dt = box.find("dt")
        if not dt:
            continue
        lbl = dt.get_text(" ", strip=True)
        if r1.search(lbl) or (r2 and r2.search(lbl)):
            dd = box.find("dd")
            if not dd:
                continue
            txt = dd.get_text(" ", strip=True)
            money = RX_MONEY.search(txt) or RX_MONEY.search((dd.find("span") or dd).get_text(" ", strip=True))
            pct = RX_PCT.search(txt)
            return (money.group(0) if money else None), (pct.group(0) if pct else None)
    return (None, None)

def extract_one_crypto(html: str) -> dict:
    s = soup_from_html(html)
    name = pick_name(s)
    price = pick_price(s)
    mc, _  = stats_value_box(s, r"Capitalisation|Market\s*Cap", r"Cap\.? Marche|Market")
    fdv, _ = stats_value_box(s, r"\bFDV\b|dilut", r"Fully Diluted")
    vol, _ = stats_value_box(s, r"Volume\s*\(24h\)", r"Volume")
    mc_f = money_to_float(mc)
    fdv_f = money_to_float(fdv)
    ratio = (mc_f / fdv_f) if (mc_f and fdv_f and fdv_f != 0) else None
    return {
        "nom": name,
        "prix": price,
        "market_cap": mc or "N/A",
        "stats": {
            "fdv": fdv or "N/A",
            "volume": vol or "N/A",
            "ratio": ratio
        }
    }
