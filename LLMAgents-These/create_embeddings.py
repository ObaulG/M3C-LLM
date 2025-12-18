import os
import json
import psycopg2
from psycopg2.extras import execute_values
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Configuration de la base de données
DB_CONFIG= {
    "host": "localhost",
    "dbname": "mediationllm",
    "user": "postgres",
    "password": "postgres",
}

# Configuration du modèle
CHUNK_SIZE_BASE = 800
DOCUMENTS_PATH = "documents"
rag_locations = ["documents/test-m3c"]

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
def insert_chunking_strategy(conn, name, description, method, chunk_size, overlap, embedding_model):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chunking_strategies (name, description, method, chunk_size, overlap, embedding_model)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO NOTHING
            RETURNING strategy_id;
            """,
            (name, description, method, chunk_size, overlap, embedding_model),
        )
        return cur.fetchone()[0]

# Fonction pour insérer des chunks
def insert_chunks(conn, chunks_data):
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO chunks (chunk_id, document_id, strategy_id, content, num_page, position_in_page, token_count, metadata)
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
            INSERT INTO chunk_embeddings (chunk_id, embedding)
            VALUES %s
            ON CONFLICT (chunk_id) DO NOTHING;
            """,
            embeddings_data,
        )

if __name__ == '__main__':
    # Vérification de la taille des embeddings
    embed_test = embedder.embed_documents(["get embed size"])
    embedding_size = len(embed_test[0])
    print(f"Embedding size: {embedding_size}")

    # Connexion à la base de données
    conn = get_db_connection()

    # Insertion de la stratégie de chunking
    strategy_id = insert_chunking_strategy(
        conn=conn,
        name="800_tokens_overlap_100",
        description="Stratégie de découpage en chunks de 800 tokens avec un overlap de 100 tokens",
        method="tokens",
        chunk_size=800,
        overlap=100,
        embedding_model="mistral-embed",
    )
    print(f"Stratégie de chunking insérée avec l'ID: {strategy_id}")

    # Initialisation du text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE_BASE,
        chunk_overlap=100,
    )

    documents_created = 0
    for f in rag_locations:
        loc = os.path.join(os.getcwd(), f)
        files = os.listdir(loc)
        for d in files:
            path = os.path.join(loc, d)
            if os.path.isdir(path):
                continue

            print(f"Chargement de {d}")
            loader = PyPDFLoader(path)

            try:
                documents = loader.load()
            except Exception as e:
                print(f"Erreur lors du chargement de {d}: {e}")
                continue

            # Découpage en chunks
            texts = text_splitter.split_documents(documents)
            print(f"{d} découpé en {len(texts)} chunks")

            # Insertion du document
            file_size = os.path.getsize(path)
            document_id = os.path.splitext(d)[0]
            insert_document(conn, document_id, d, path, file_size)

            # Préparation des données pour les chunks
            chunks_data = []
            embeddings_data = []
            for i, text in enumerate(texts):
                chunk_id = f"{document_id}-{i}"
                content = text.page_content
                num_page = text.metadata.get("page", 0)
                position_in_page = i  # Simplification
                token_count = len(text.page_content.split())  # Approximation
                metadata = json.dumps({
                    "source": d,
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
                    metadata,
                ))

                # Génération de l'embedding
                embedding = embedder.embed_documents([content])[0]
                embeddings_data.append((chunk_id, embedding))

            # Insertion des chunks et des embeddings
            insert_chunks(conn, chunks_data)
            insert_embeddings(conn, embeddings_data)

            print(f"{len(texts)} chunks et embeddings insérés pour {d}")

    # Validation des insertions
    conn.commit()
    conn.close()
    print("Traitement terminé.")
