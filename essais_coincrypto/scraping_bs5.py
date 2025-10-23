import time
import json
import re
from playwright.sync_api import sync_playwright, Page, Browser
from bs4 import BeautifulSoup
from typing import List, Dict, Any

# ----------------------------------------------------------------------
# PARAMÈTRES ET CONFIGURATION (FACILES À MODIFIER)
# ----------------------------------------------------------------------
URL_BASE = 'https://coinmarketcap.com' 
NOM_FICHIER_JSON = 'cryptomonnaie.json'
CIBLE_PAGES = 3               # 3 pages = 300 cryptos
NOMBRE_CIBLE_TOTAL = 300
RATIO_MAX_FILTRE = 0.3         # Market Cap / FDV <= 0.3

# Liste des labels de statistiques à extraire
STATS_TO_EXTRACT = [
    'Cap. Marché', # Market Cap
    'FDV',         # Fully Diluted Value
    'Volume (24h)',# Volume
    'Offre Totale',
]

# Timers
TIMEOUT_PAGE_LISTE = 15000     # 15 secondes pour charger la page de liste
TIMEOUT_DETAILS_PAGE = 30000   # 30 secondes pour charger la page de détail (plus longue ici)
PAUSE_ENTRE_PAGES_LISTE = 3    # Pause entre les pages de la liste (sec)
PAUSE_ENTRE_REQUETES_DETAIL = 0.5 # Pause réduite car on utilise le même navigateur (sec)
# ----------------------------------------------------------------------


# --- FONCTIONS UTILITAIRES ET SCALABILITÉ -----------------------------

def normalize_value(value_str: str) -> float:
    """
    Convertit la valeur string (ex: '1,92T €') en float normalisé (ex: 1.92e12) 
    avec une robustesse accrue pour gérer les formats français.
    """
    if not value_str or value_str in ("N/A", "-"):
        return 0.0
    
    # 1. Nettoyage initial : retire les symboles monétaires et les espaces
    cleaned_str = value_str.strip()
    cleaned_str = cleaned_str.replace('€', '').replace('$', '').strip()
    
    # Trouver les multiplicateurs
    multipliers = {'T': 1e12, 'B': 1e9, 'M': 1e6, 'K': 1e3}
    multiplier = 1.0
    
    # Isoler le suffixe et déterminer le multiplicateur
    for suffix, mult_value in multipliers.items():
        if suffix in cleaned_str:
            multiplier = mult_value
            cleaned_str = cleaned_str.replace(suffix, '')
            break
            
    # Maintenant, nettoyer le reste du string pour le rendre floatable
    numeric_part = cleaned_str.replace(',', '.') # Remplacer la virgule par un point
    numeric_part = re.sub(r'[^\d.]', '', numeric_part) # Retirer les autres caractères non numériques

    try:
        if numeric_part:
            return float(numeric_part) * multiplier
    except ValueError:
        pass 
                
    return 0.0

def extract_stat_by_label(soup: BeautifulSoup, label_text: str) -> str:
    """
    Recherche une statistique (comme FDV ou Cap. Marché) par son label dans la page de détail.
    """
    # Cherche le dt (titre) contenant le texte du label
    dt_element = soup.find('dt', string=lambda t: t and label_text in t)
    
    value = "N/A"
    
    if dt_element:
        # La valeur (dd) est le frère suivant du dt.
        dd_element = dt_element.find_next_sibling('dd')
        
        if dd_element:
            # La valeur est souvent dans un span ou un lien à l'intérieur du dd.
            # Ciblage plus générique pour éviter les problèmes de classe changeante
            value_element = dd_element.find(['span', 'a'])
            
            if value_element:
                # Si la valeur est un lien (parfois le cas pour le volume) ou un span
                value = value_element.get_text(strip=True)
            else:
                # Dernier recours : si la valeur est directement dans le dd
                value = dd_element.get_text(strip=True)
            
    return value.replace(' ', '') # Nettoyage des espaces


# --- PARTIE A : EXPLORATION PAR URL DIRECTE (Lien) --------------------

# Cette fonction Reste séparée pour la phase rapide de collecte des liens
def get_all_hrefs_by_direct_url(url_base: str, total_pages: int) -> List[str]:
    """
    Parcourt les pages (1, 2, 3...) en utilisant le paramètre ?page=X dans l'URL pour la collecte de liens.
    """
    all_liens_cryptos = []
    
    with sync_playwright() as p:
        browser = None
        try:
            print(f"1/3: Démarrage de la pagination par URL directe pour récupérer {NOMBRE_CIBLE_TOTAL} liens...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            for page_num in range(1, total_pages + 1):
                url_page = f"{url_base}/fr/?lang=fr&page={page_num}" 
                print(f"   -> Visite de la page {page_num}/{total_pages}")
                
                page.goto(url_page, wait_until="networkidle", timeout=TIMEOUT_PAGE_LISTE) 
                
                # Attente que le tableau de 100 éléments soit stable
                page.wait_for_selector(f'tbody tr:nth-child(100)', timeout=TIMEOUT_PAGE_LISTE)
                time.sleep(PAUSE_ENTRE_PAGES_LISTE) 
                
                html_content = page.content()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Sélecteur ciblant spécifiquement les liens des cryptos
                liens_a = soup.select('tbody tr td:nth-child(3) a.cmc-link') 
                
                for a_tag in liens_a:
                    href_relatif = a_tag.get('href')
                    if href_relatif and '/currencies/' in href_relatif and '#' not in href_relatif:
                        lien_absolu = f"{URL_BASE}{href_relatif}"
                        if lien_absolu not in all_liens_cryptos:
                            all_liens_cryptos.append(lien_absolu)
                
            return all_liens_cryptos

        except Exception as e:
            print(f"❌ Erreur Playwright (Pagination URL) : {e}")
            return all_liens_cryptos if all_liens_cryptos else []
        finally:
            if browser:
                browser.close()

# --- PARTIE B : EXTRACTION DÉTAILLÉE (avec Page Playwright persistante) ---

def extract_details_from_page(html_content: str, href: str) -> Dict[str, Any]:
    """
    Analyse le HTML et utilise la fonction scalable pour extraire toutes les statistiques cibles
    et calculer le ratio.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    details = {}

    # 1. Nom et Prix
    nom_element = soup.select_one('span[data-role="coin-name"]')
    details['nom'] = nom_element.get_text(strip=True) if nom_element else "N/A"
    price_element = soup.select_one('span[data-test="text-cdp-price-display"]') 
    details['prix'] = price_element.get_text(strip=True).replace(' ', '') if price_element else "N/A"

    # 2. Extraction des Statistiques
    details['stats'] = {}
    
    market_cap_float = 0.0
    fdv_float = 0.0
    
    for label in STATS_TO_EXTRACT:
        stat_value_str = extract_stat_by_label(soup, label)
        key_name = label.lower().replace('.', '').replace(' ', '_').replace('(', '').replace(')', '')
        details['stats'][key_name] = stat_value_str
        
        # Capture pour le calcul du ratio
        if label == 'Cap. Marché':
            market_cap_float = normalize_value(stat_value_str)
        elif label == 'FDV':
            fdv_float = normalize_value(stat_value_str)
    
    # 3. Calcul du Ratio
    details['market_cap_float'] = market_cap_float
    details['fdv_float'] = fdv_float
    
    details['ratio_marketcap_fdv'] = (
        market_cap_float / fdv_float 
        if fdv_float and fdv_float != 0.0 
        else "N/A"
    )
    
    return details

# --- PARTIE C : FONCTION MAIN (Écriture en direct) ----------------------------

def main():
    
    # 1. PHASE D'EXPLORATION & PAGINATION
    liens_cryptos = get_all_hrefs_by_direct_url(URL_BASE, CIBLE_PAGES)
        
    print(f"\n✅ {len(liens_cryptos)} liens de cryptomonnaies récupérés. Passage à l'extraction détaillée.")
    
    # 2. INITIALISATION DE L'ÉCRITURE EN DIRECTE ET DE PLAYWRIGHT PERSISTANT
    total_processed = 0
    cryptos_filtrees_count = 0
    
    print(f"\n2/3: DÉMARRAGE DE L'EXTRACTION DÉTAILLÉE (Session Playwright Unique) dans {NOM_FICHIER_JSON}...")

    # Utiliser Playwright une seule fois pour toutes les requêtes de détail
    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Ouverture du fichier JSON
            with open(NOM_FICHIER_JSON, 'w', encoding='utf-8') as f:
                f.write('[\n') # Début du tableau JSON
                
                for i, href in enumerate(liens_cryptos):
                    
                    # Pause de sécurité
                    if i > 0:
                        time.sleep(PAUSE_ENTRE_REQUETES_DETAIL) 
                        
                    print(f"Traitement {i+1:03}/{len(liens_cryptos)} - {href.split('/currencies/')[-1].strip('/')}")
                    
                    html_details = None
                    try:
                        # Visiter la page de détail avec la même session Playwright
                        page.goto(href, wait_until="load", timeout=TIMEOUT_DETAILS_PAGE) 
                        SELECTEUR_PRIX_STABLE = 'span[data-test="text-cdp-price-display"]'
                        page.wait_for_selector(SELECTEUR_PRIX_STABLE, timeout=TIMEOUT_DETAILS_PAGE) 
                        time.sleep(1) # Pause de sécurité pour garantir que le JS a chargé le bloc de stats
                        html_details = page.content()
                    except Exception as e:
                         print(f"  ❌ Échec Playwright ou Timeout pour {href.split('/currencies/')[-1].strip('/')}: {e}")
                         
                    
                    if html_details:
                        details = extract_details_from_page(html_details, href)
                        
                        # --- FILTRAGE et FORMATAGE ---
                        ratio = details.get('ratio_marketcap_fdv')
                        
                        # Appliquer la condition de filtre
                        if isinstance(ratio, float) and ratio <= RATIO_MAX_FILTRE:
                            
                            # 1. Préparer l'objet final 
                            final_output_obj = {
                                'index': cryptos_filtrees_count + 1, 
                                'nom': details.get('nom'), 
                                'prix': details.get('prix'), 
                                'stats': details.get('stats'), 
                                'ratio_marketcap_fdv': ratio,
                                'lien': href
                            }
                            
                            # 2. Ajouter la virgule pour les éléments suivants
                            if cryptos_filtrees_count > 0:
                                f.write(',\n')
                                
                            # 3. Écrire l'objet dans le fichier
                            json.dump(final_output_obj, f, indent=4, ensure_ascii=False)
                            f.flush()
                            
                            cryptos_filtrees_count += 1
                    
                    total_processed += 1
                
                f.write('\n]') # Fin du tableau JSON

        except Exception as e:
            print(f"\n❌ Erreur Fatale dans la boucle principale : {e}")
        finally:
            if browser:
                browser.close()
        
    print("\n--- ÉCRITURE TERMINÉE ---")
    print(f"\n✅ Données filtrées et sauvegardées dans {NOM_FICHIER_JSON} !")
    print(f"Total des cryptomonnaies traitées: {total_processed}")
    print(f"Total des entrées satisfaisant le critère (Ratio <= {RATIO_MAX_FILTRE}): {cryptos_filtrees_count}")

if __name__ == "__main__":
    main()
