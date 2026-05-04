import pdfplumber
from langchain_text_splitters import NLTKTextSplitter

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Charger le modèle pour les embeddings
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')  # Modèle multilingue

def calculate_cosine_similarity(text1: str, text2: str) -> float:
    """
    Calcule la similarité cosinus entre deux textes.
    """
    embeddings = model.encode([text1, text2])
    similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
    return round(similarity, 2)  # Arrondi à 2 décimales

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extraire le texte d'un fichier PDF."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def split_text_in_chunks(text: str, chunk_size: int, chunk_overlap: int = 50) -> list:
    splitter = NLTKTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_text(text)
    return chunks
