from bs4 import BeautifulSoup

# 1) Ouvrir le fichier HTML et utiliser le parser html5lib
with open("books.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html5lib")

# 2) Récupérer la première balise <h1>
h1_tag = soup.find("h1")

# 3) Récupérer le texte du premier <h1> (en évitant les erreurs)
h1_text = h1_tag.get_text(strip=True) if h1_tag else None
print("Texte du premier <h1>:", h1_text)

# 4) Récupérer le texte de la première balise <p class="price_color">
price_tag = soup.find("p", class_="price_color")
price_text = price_tag.get_text(strip=True) if price_tag else None
print("Texte du premier prix:", price_text)

# 5) Récupérer tous les prix avec find_all
all_prices = [p.get_text(strip=True) for p in soup.find_all("p", class_="price_color")]
print("Tous les prix:", all_prices[:5], "...")  # affiche les 5 premiers

# 6) Créer un sous-objet 'books' pour le conteneur principal
#    Tous les livres sont contenus dans la balise <ol class="row">
books_container = soup.find("ol", class_="row")

if books_container:
    # On crée un sous-objet BeautifulSoup indépendant
    books = BeautifulSoup(str(books_container), "html5lib")
    print("Sous-objet 'books' créé avec succès ✅")
else:
    books = None
    print("⚠️ Conteneur <ol class='row'> introuvable.")

# 7) Exemple : utiliser directement books.find_all sur le sous-objet
if books:
    book_elements = books.find_all("article", class_="product_pod")
    print(f"Nombre de livres trouvés : {len(book_elements)}")

    # Exemple : récupérer les titres
    titles = [b.h3.a.get("title") for b in book_elements if b.h3 and b.h3.a]
    print("Quelques titres:", titles[:5])
