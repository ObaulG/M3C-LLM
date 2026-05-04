import os
import json
import psycopg2
from psycopg2.extras import execute_values
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import AutoTokenizer

# Configuration de la base de données
DB_CONFIG= {
    "host": "localhost",
    "dbname": "mediationllm",
    "user": "postgres",
    "password": "postgres",
}

CHUNK_CHAR_SIZE = 2700
DOCUMENTS_PATH = "C:\\Users\\xenyi\\Documents\\Ressources-Pro\\Thèse\\M3C-documents"

# Initialisation des modèles
llm = ChatMistralAI(
    model="mistral-medium-latest",
    temperature=0.7,
    max_retries=2,
    mistral_api_key=os.getenv("MISTRAL_API_KEY"),
)

embedder = MistralAIEmbeddings(model="mistral-embed")

# Connexion à la base de données
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# Fonction pour insérer un document
def insert_document(conn, document_id, file_name, file_path, file_size):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (document_id, file_name, file_path, file_size)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (document_id) DO NOTHING
            RETURNING document_id;
            """,
            (document_id, file_name, file_path, file_size),
        )
        return cur.fetchone()[0]

# Fonction pour insérer une stratégie de chunking
def insert_chunking_strategy(conn, name, description, method, chunk_size, char_size, overlap):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chunking_strategies (name, description, method, chunk_size, char_size, overlap)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO NOTHING
            RETURNING strategy_id;
            """,
            (name, description, method, chunk_size, char_size, overlap),
        )
        return cur.fetchone()[0]

# Fonction pour insérer des chunks
def insert_chunks(conn, chunks_data):
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO chunks (chunk_id, document_id, strategy_id, content, num_page, position_in_page, token_count, character_count, metadata)
            VALUES %s
            ON CONFLICT (chunk_id) DO NOTHING;
            """,
            chunks_data,
        )

# Fonction pour insérer des embeddings
def insert_embeddings(conn, embeddings_data):
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO chunk_embeddings (chunk_id, embedding, model_name)
            VALUES %s
            ON CONFLICT (chunk_id) DO NOTHING;
            """,
            embeddings_data,
        )

if __name__ == '__main__':
    FILES_TO_EMBED = [
        "8a672d2ae6f2abfa4434e0f4145a9aa77bbc6d56.pdf",
        "dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d.pdf"
    ]
    tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-Instruct-v0.2")

    # Vérification de la taille des embeddings
    embed_test = embedder.embed_documents(["get embed size"])
    embedding_size = len(embed_test[0])
    print(f"Embedding size: {embedding_size}")

    # Connexion à la base de données
    conn = get_db_connection()

    # Insertion de la stratégie de chunking
    strategy_id = insert_chunking_strategy(
        conn=conn,
        name="2700_char_overlap_400",
        description="Stratégie de découpage en chunks de 2700 caractères avec 400 caractères d'overlap",
        method="characters",
        char_size=CHUNK_CHAR_SIZE,
        chunk_size=0,
        overlap=400
    )
    print(f"Stratégie de chunking insérée avec l'ID: {strategy_id}")

    # Initialisation du text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_CHAR_SIZE,
        chunk_overlap=400,
    )

    documents_created = 0
    for file_name in FILES_TO_EMBED:
        path = os.path.join(DOCUMENTS_PATH, file_name)
        print(f"Chargement de {path}")
        loader = PyPDFLoader(path)

        try:
            documents = loader.load()
        except Exception as e:
            print(f"Erreur lors du chargement de {path}: {e}")
            continue

        # Découpage en chunks
        texts = text_splitter.split_documents(documents)
        print(f"{file_name} découpé en {len(texts)} chunks")

        # Insertion du document
        file_size = os.path.getsize(path)
        document_id = os.path.splitext(file_name)[0]
        #insert_document(conn, document_id, d, path, file_size)

        # Préparation des données pour les chunks
        chunks_data = []
        embeddings_data = []
        for i, text in enumerate(texts):
            chunk_id = f"{document_id}-{strategy_id}-{i}"
            content = text.page_content
            num_page = text.metadata.get("page", 0)
            position_in_page = i  # Simplification
            tokens = tokenizer.tokenize(text.page_content)
            token_count = len(tokens)+2
            character_count = len(text.page_content)
            metadata = json.dumps({
                "source": document_id,
                "page": num_page,
                "position": position_in_page,
            })

            chunks_data.append((
                chunk_id,
                document_id,
                strategy_id,
                content,
                num_page,
                position_in_page,
                token_count,
                character_count,
                metadata,
            ))

            # Génération de l'embedding
            embedding = embedder.embed_documents([content])[0]
            embeddings_data.append((chunk_id, embedding, "mistral-embed"))

        # Insertion des chunks et des embeddings
        insert_chunks(conn, chunks_data)
        insert_embeddings(conn, embeddings_data)

        print(f"{len(texts)} chunks et embeddings insérés pour {document_id}")

    # Validation des insertions
    conn.commit()
    conn.close()
    print("Traitement terminé.")
