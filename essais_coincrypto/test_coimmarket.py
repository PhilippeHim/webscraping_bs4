import time
import json
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------
# PARAMÈTRES
# ----------------------------------------------------------------------
URL_BASE = 'https://coinmarketcap.com/fr/' 
NOM_FICHIER_JSON = 'cryptomonnaie.json'
NOMBRE_PAGES_CIBLE = 3      # Nous voulons 300 résultats (3 pages de 100)
TIMEOUT_PAGE = 45000        # Temps maximal en ms pour attendre le chargement des éléments (45 secondes)
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# FONCTION DE RÉCUPÉRATION PAR PAGE (Utilise Playwright)
# ----------------------------------------------------------------------
def get_html_content_for_page(url_page):
    """
    Télécharge le contenu HTML final d'une page spécifique (max 100 résultats).
    """
    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            print(f"Chargement de la page : {url_page}")
            
            # Navigation vers l'URL spécifique
            page.goto(url_page.strip(), wait_until="networkidle") 
            
            # --- AMÉLIORATION CRITIQUE DU TIMING ---
            # Au lieu d'un simple sleep, nous attendons que la 100ème ligne soit là.
            print("Attente que la 100ème ligne soit présente...")
            
            # Attend que l'élément (typiquement la 100ème ligne) soit visible.
            page.wait_for_selector('tbody tr:nth-child(100)', timeout=TIMEOUT_PAGE) 
            
            # Pause de sécurité pour garantir que le JS a Rempli les <td> avec les données (votre problème 41/100)
            print("Pause de 5 secondes pour le rendu des données (41 -> 100)...")
            time.sleep(5) 

            # Récupération du code source complet
            html_content = page.content()
            
            # Comptage du nombre réel de lignes trouvées par Playwright
            row_count = page.locator('tbody tr').count()
            print(f"Playwright a détecté {row_count} lignes sur cette page.")
            
            return html_content

        except Exception as e:
            print(f"❌ Erreur Playwright ou Timeout pour {url_page}: {e}")
            return None
        finally:
            if browser:
                browser.close()
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# FONCTION D'EXTRACTION (Utilise BeautifulSoup)
# ----------------------------------------------------------------------
def extraire_cryptos(html_content):
    """
    Parse le contenu HTML et extrait les données de toutes les lignes trouvées.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    cryptomonnaies = []
    
    # Sélecteur critique pour toutes les lignes du corps du tableau
    lignes_crypto = soup.select('tbody tr') 
    
    for ligne in lignes_crypto:
        crypto = {}
        
        # 1. NOM DE LA CRYPTO
        nom_tag = ligne.select_one('p.coin-item-name')
        crypto['nom'] = nom_tag.get_text(strip=True) if nom_tag else "N/A"

        # 2. PRIX
        prix_tag = ligne.select_one('td:nth-child(4) span')
        crypto['prix'] = prix_tag.get_text(strip=True).replace(' ', '') if prix_tag else "N/A"

        # 3. CAP. BOURSIER
        cap_tag = ligne.select_one('span[data-nosnippet="true"]')
        crypto['market_cap'] = cap_tag.get_text(strip=True) if cap_tag else "N/A"
        
        # S'assurer qu'au moins le nom a été trouvé (pour éviter les lignes vides)
        if crypto['nom'] != "N/A":
            cryptomonnaies.append(crypto)

    return cryptomonnaies
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# FONCTION DE SAUVEGARDE JSON (Inchangée)
# ----------------------------------------------------------------------
def sauvegarder_json(data, filename):
    # ... (fonction inchangée) ...
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"\n✅ Données sauvegardées avec succès dans {filename} !")
        print(f"Total des entrées sauvegardées : {len(data)}")
    except Exception as e:
        print(f"\n❌ Erreur lors de la sauvegarde du fichier JSON : {e}")


# ----------------------------------------------------------------------
# POINT D'ENTRÉE PRINCIPAL (BOUCLE DE PAGINATION)
# ----------------------------------------------------------------------
def main():
    
    toutes_les_cryptos = []
    
    # BOUCLE DE 1 à NOMBRE_PAGES_CIBLE (soit 1, 2, 3)
    for page_num in range(1, NOMBRE_PAGES_CIBLE + 1):
        
        # Construction de l'URL pour chaque page
        if page_num == 1:
            # La première page est l'URL de base
            url_actuelle = URL_BASE
        else:
            # Construction de l'URL pour les pages suivantes (ex: .../page/2/)
            url_actuelle = f"{URL_BASE}page/{page_num}/"
        
        # 1. TÉLÉCHARGEMENT DE LA PAGE
        html_content = get_html_content_for_page(url_actuelle)
        
        if html_content:
            # 2. PARSING
            print(f"Parsing des données de la Page {page_num}...")
            cryptos_de_la_page = extraire_cryptos(html_content)
            
            if cryptos_de_la_page:
                print(f"✅ Page {page_num} : {len(cryptos_de_la_page)} cryptos extraites.")
                toutes_les_cryptos.extend(cryptos_de_la_page) # Ajout des résultats à la liste totale
            else:
                print(f"❌ Page {page_num} : Échec du parsing. Aucune donnée trouvée.")
                # Si une page échoue, on continue la boucle
                
        else:
            print(f"❌ Page {page_num} : Échec de la récupération Playwright. Arrêt de la pagination.")
            break # Arrêter si on ne peut pas charger la page

    # 3. SAUVEGARDE FINALE
    if toutes_les_cryptos:
        sauvegarder_json(toutes_les_cryptos, NOM_FICHIER_JSON)
    else:
        print("\n❌ Aucun résultat n'a pu être extrait. Fichier JSON non créé.")

if __name__ == "__main__":
    main()