import pdfplumber
from io import StringIO


def extract_text_from_pdf(file_path):
    buffer = StringIO()  # Utilise un buffer pour accumuler le texte
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            texte_page = page.extract_text()
            if texte_page:  # Évite d'ajouter des pages vides
                buffer.write(texte_page)
                buffer.write("\n")  # Ajoute un saut de ligne entre les pages
    return buffer.getvalue()  # Récupère le contenu du buffer sous forme de chaîne
