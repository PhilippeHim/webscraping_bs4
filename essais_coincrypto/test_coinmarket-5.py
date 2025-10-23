import time
import json
import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup

# Importations spécifiques à Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# ----------------------------------------------------------------------
# PARAMÈTRES ET CONFIGURATION (FACILES À MODIFIER)
# ----------------------------------------------------------------------
URL_BASE = 'https://coinmarketcap.com' 
NOM_FICHIER_JSON = 'cryptomonnaie_selenium.json' 
CIBLE_PAGES = 3               # 3 pages = 300 cryptos
NOMBRE_CIBLE_TOTAL = 300
RATIO_MAX_FILTRE = 0.3         # Critère : Cap. Marché / FDV <= 0.3

# Liste des labels de statistiques à extraire
STATS_TO_EXTRACT = [
    'Cap. Marché', # Market Cap
    'FDV',         # Fully Diluted Value
    'Volume (24h)',# Volume
    'Offre Totale',
    'Vol/Mkt Cap (24h)' # NOUVELLE STATISTIQUE AJOUTÉE
]

# Timers
TIMEOUT_GENERAL = 20            # 20 secondes max pour les attentes
PAUSE_ENTRE_PAGES_LISTE = 3     # Pause entre les pages de la liste (sec)
PAUSE_ENTRE_REQUETES_DETAIL = 0.5 # Pause entre les pages de détail (sec)
# ----------------------------------------------------------------------


# --- FONCTIONS UTILITAIRES ET SCALABILITÉ -----------------------------

def normalize_value(value_str: str) -> float:
    """
    CONVERSION INTERNE: Convertit la valeur string (ex: '1,92T €') en float normalisé 
    (ex: 1.92e12) UTILISÉ UNIQUEMENT POUR LE CALCUL DU RATIO.
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
            # Gérer le cas du pourcentage (Vol/Mkt Cap), on garde la valeur brute
            if '%' in value_str:
                return float(numeric_part)
            
            return float(numeric_part) * multiplier
    except ValueError:
        pass 
                
    return 0.0

def extract_stat_by_label(soup: BeautifulSoup, label_text: str) -> str:
    """
    Recherche une statistique (comme FDV, Cap. Marché ou Vol/Mkt Cap) par son label dans la page de détail.
    Retourne la chaîne de caractères originale non convertie.
    """
    # Cherche le dt (titre) contenant le texte du label
    # NOTE: Pour 'Vol/Mkt Cap (24h)', l'élément DT contient souvent un long texte.
    dt_element = soup.find('dt', string=lambda t: t and label_text in t)
    
    value = "N/A"
    
    if dt_element:
        # La valeur (dd) est le frère suivant du dt.
        dd_element = dt_element.find_next_sibling('dd')
        
        if dd_element:
            # La valeur peut être dans un span ou un div à l'intérieur du dd.
            value_element = dd_element.find(['span', 'a', 'div'])
            
            # Pour la Vol/Mkt Cap, la valeur est parfois directement dans le dernier div enfant du dd
            if value_element and 'CoinMetrics_overflow-content' in value_element.get('class', []):
                 value = value_element.get_text(strip=True)
            elif value_element:
                # Si la valeur est un lien ou un span
                value = value_element.get_text(strip=True)
            else:
                # Dernier recours : si la valeur est directement dans le dd
                value = dd_element.get_text(strip=True)
            
    # La valeur retournée est la chaîne de caractères brute (ex: "100,00B $", "3,55%")
    return value.replace(' ', '').replace('\n', '').replace('\t', '') # Nettoyage supplémentaire
    
def extract_details_from_page(html_content: str, href: str) -> Dict[str, Any]:
    """
    Analyse le HTML et extrait les données. Calcule le ratio Cap. Marché / FDV en interne.
    Retourne les chaînes de caractères brutes (sauf pour le ratio qui est un float).
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    details = {
        'stats': {},
        'ratio_marketcap_fdv': 'N/A', 
        'nom': 'N/A',
        'prix': 'N/A'
    }

    # 1. Nom et Prix
    nom_element = soup.select_one('span[data-role="coin-name"]')
    details['nom'] = nom_element.get_text(strip=True) if nom_element else "N/A"
    price_element = soup.select_one('span[data-test="text-cdp-price-display"]') 
    details['prix'] = price_element.get_text(strip=True).replace(' ', '') if price_element else "N/A"

    market_cap_float = 0.0
    fdv_float = 0.0
    
    # 2. Extraction des Statistiques et conversion interne pour le calcul
    for label in STATS_TO_EXTRACT:
        stat_value_str = extract_stat_by_label(soup, label)
        key_name = label.lower().replace('.', '').replace(' ', '_').replace('(', '').replace(')', '')
        
        # Conserver la chaîne de caractères originale pour l'exportation finale
        details['stats'][key_name] = stat_value_str 
        
        # Conversion Flottante pour le calcul du filtre uniquement
        if label == 'Cap. Marché':
            market_cap_float = normalize_value(stat_value_str)
        elif label == 'FDV':
            fdv_float = normalize_value(stat_value_str)
    
    # 3. Calcul du Ratio (basé sur les floats internes)
    if fdv_float and fdv_float != 0.0:
        details['ratio_marketcap_fdv'] = market_cap_float / fdv_float
    
    return details
# ----------------------------------------------------------------------


# --- FONCTIONS SPÉCIFIQUES À SELENIUM (REMPLACENT PLAYWRIGHT) ----------

def setup_selenium_driver():
    """ Configure et lance le driver Chrome en mode headless. """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Définit l'agent utilisateur pour éviter la détection (optional mais recommandé)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def get_all_hrefs_by_direct_url(driver: webdriver.Chrome, url_base: str, total_pages: int) -> List[str]:
    """
    Parcourt les pages et collecte les liens des cryptos en utilisant Selenium.
    """
    all_liens_cryptos = []
    
    try:
        print(f"1/3: Démarrage de la pagination par URL directe pour récupérer {NOMBRE_CIBLE_TOTAL} liens...")
        
        for page_num in range(1, total_pages + 1):
            url_page = f"{url_base}/?page={page_num}" 
            print(f"   -> Visite de la page {page_num}/{total_pages}")
            
            driver.get(url_page)
            
            # Attente que l'élément (typiquement la 100ème ligne) soit visible.
            WebDriverWait(driver, TIMEOUT_GENERAL).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'tbody tr:nth-child(100)'))
            )
            time.sleep(PAUSE_ENTRE_PAGES_LISTE) 
            
            html_content = driver.page_source
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
        print(f"❌ Erreur Selenium (Pagination URL) : {e}")
        return all_liens_cryptos if all_liens_cryptos else []

# --- PARTIE C : FONCTION MAIN (Collecte en mémoire et Écriture finale) ------

def main():
    
    # Fonction locale pour gérer l'écriture finale, utilisée aussi en cas d'interruption
    def write_final_json(data_list: List[Dict[str, Any]], filename: str, processed_count: int, ratio_max: float):
        """ Écrit les données collectées dans le fichier JSON, après ré-indexation. """
        
        if not data_list:
            print(f"\n[SAUVEGARDE] Aucune donnée n'a été collectée ou filtrée, création d'un fichier {filename} vide.")
        else:
            # Ré-indexer les résultats finaux
            for idx, item in enumerate(data_list):
                item['index'] = idx + 1
            
            print(f"\n[SAUVEGARDE] Écriture finale de {len(data_list)} entrées filtrées dans {filename}...")

        # Écriture du tableau complet dans le fichier JSON
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data_list, f, indent=4, ensure_ascii=False)
        except Exception as e:
             print(f"\n❌ Erreur lors de l'écriture du JSON : {e}")

        
        print(f"\n--- ÉCRITURE TERMINÉE ---")
        print(f"Total des cryptomonnaies traitées: {processed_count}")
        print(f"Total des entrées satisfaisant le critère (Ratio <= {ratio_max}): {len(data_list)}")


    driver = None
    total_processed = 0
    cryptos_filtrees = [] 
    
    try:
        # Initialisation du Driver Chrome
        driver = setup_selenium_driver()

        # 1. PHASE D'EXPLORATION & PAGINATION
        liens_cryptos = get_all_hrefs_by_direct_url(driver, URL_BASE, CIBLE_PAGES)
            
        print(f"\n✅ {len(liens_cryptos)} liens de cryptomonnaies récupérés. Passage à l'extraction détaillée.")
        
        # 2. DÉMARRAGE DE L'EXTRACTION DÉTAILLÉE
        print(f"\n2/3: DÉMARRAGE DE L'EXTRACTION DÉTAILLÉE (Session Selenium Unique)...")

        for i, href in enumerate(liens_cryptos):
            
            if i > 0:
                time.sleep(PAUSE_ENTRE_REQUETES_DETAIL) 
                
            print(f"Traitement {i+1:03}/{len(liens_cryptos)} - {href.split('/currencies/')[-1].strip('/')}")
            
            html_details = None
            try:
                # Visiter la page de détail avec le même driver
                driver.get(href)
                
                # Attente que l'élément critique (le prix) soit chargé
                SELECTEUR_PRIX_STABLE = 'span[data-test="text-cdp-price-display"]'
                WebDriverWait(driver, TIMEOUT_GENERAL).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, SELECTEUR_PRIX_STABLE))
                )
                
                time.sleep(1) # Pause de sécurité pour garantir que le JS a chargé le bloc de stats
                html_details = driver.page_source
                
            except Exception as e:
                 print(f"  ❌ Échec Selenium ou Timeout pour {href.split('/currencies/')[-1].strip('/')}: {e}")
                 
            
            if html_details:
                details = extract_details_from_page(html_details, href)
                
                # --- FILTRAGE ---
                ratio = details.get('ratio_marketcap_fdv')
                
                # Le ratio doit être un float pour le filtre
                if isinstance(ratio, float) and ratio <= RATIO_MAX_FILTRE:
                    final_output_obj = {
                        'nom': details.get('nom'), 
                        'prix': details.get('prix'), 
                        'stats': details.get('stats'), # Contient les chaînes non converties (ex: "1,92T €")
                        'ratio_marketcap_fdv': ratio,
                        'lien': href
                    }
                    cryptos_filtrees.append(final_output_obj)
            
            total_processed += 1
            
        # --- FIN NORMALE DU SCRAPING ---
            
    # Gérer l'interruption clavier (Ctrl+C)
    except KeyboardInterrupt:
        print("\n\n⚠️ Interruption manuelle détectée (Ctrl+C). Sauvegarde des données collectées...")
    
    except Exception as e:
        # Gérer toute autre erreur inattendue (e.g., échec de l'initialisation du driver)
        print(f"\n❌ Erreur Fatale : {e}")

    finally:
        # 3. ÉCRIRE LES DONNÉES ET FERMER LE NAVIGATEUR
        if driver:
            driver.quit()
            print("Fermeture du navigateur Selenium.")
        
        # Appeler la fonction de sauvegarde, même si le scraping a été interrompu
        write_final_json(
            cryptos_filtrees, 
            NOM_FICHIER_JSON, 
            total_processed, 
            RATIO_MAX_FILTRE
        )
        
if __name__ == "__main__":
    main()
