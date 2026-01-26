import os
import json
import pickle
import faiss
import psycopg2
from psycopg2.extras import execute_values

# Configuration de la base de données
DB_CONFIG = {
    "host": "localhost",
    "dbname": "mediationllm",
    "user": "postgres",
    "password": "postgres",
}

# Chemin vers les fichiers
FAISS_INDEX_PATH = "faiss_index.bin"
INDEX_MAPPING_PATH = "old/index_to_docstore_id.pkl"
JSON_CHUNKS_DIR = "documents/json_chunks"

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
        return cur.fetchone()[0] if cur.rowcount > 0 else None

# Fonction pour insérer une stratégie de chunking
def insert_chunking_strategy(conn, name, description, method, chunk_size, overlap):
    with conn.cursor() as cur:
        # Vérifier si une stratégie avec les mêmes paramètres existe déjà
        cur.execute(
            """
            SELECT strategy_id
            FROM chunking_strategies
            WHERE method = %s
              AND chunk_size = %s
              AND overlap = %s
            """,
            (method, chunk_size, overlap),
        )
        result = cur.fetchone()
        if result:
            return result[0]  # Retourner l'ID de la stratégie existante

        # Sinon, insérer la nouvelle stratégie
        cur.execute(
            """
            INSERT INTO chunking_strategies (name, description, method, chunk_size, overlap)
            VALUES (%s, %s, %s, %s, %s) RETURNING strategy_id;
            """,
            (name, description, method, chunk_size, overlap),
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
def insert_chunk_embeddings(conn, chunk_id, model_name, embedding):
    """
    Insère un embedding pour un chunk et un modèle donné dans la table `chunk_embeddings`.

    Args:
        conn: Connexion à la base de données PostgreSQL.
        chunk_id (str): Identifiant du chunk.
        model_name (str): Nom du modèle d'embedding.
        embedding (list): Embedding sous forme de liste (converti depuis numpy.ndarray).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chunk_embeddings (chunk_id, model_name, embedding)
            VALUES (%s, %s, %s)
            ON CONFLICT (chunk_id, model_name) DO NOTHING;
            """,
            (chunk_id, model_name, embedding),
        )

def insert_chunk_embeddings_batch(conn, embeddings_batch):
    """
    Insère un lot d'embeddings pour des chunks et modèles donnés.

    Args:
        conn: Connexion à la base de données PostgreSQL.
        embeddings_batch (list): Liste de tuples (chunk_id, model_name, embedding).
    """
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO chunk_embeddings (chunk_id, model_name, embedding)
            VALUES %s
            ON CONFLICT (chunk_id, model_name) DO NOTHING;
            """,
            embeddings_batch,
        )

def insert_embedding_model(conn, model_name, description, dimension):
    """
    Insère un modèle d'embedding dans la table `embedding_models`.

    Args:
        conn: Connexion à la base de données PostgreSQL.
        model_name (str): Nom unique du modèle (clé primaire).
        description (str): Description du modèle.
        dimension (int): Dimension des embeddings générés par ce modèle.

    Returns:
        bool: True si l'insertion a réussi, False si le modèle existait déjà.
    """
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                INSERT INTO embedding_models (model_name, description, dimension)
                VALUES (%s, %s, %s)
                ON CONFLICT (model_name) DO NOTHING;
                """,
                (model_name, description, dimension),
            )
            return cur.rowcount > 0  # Retourne True si une ligne a été insérée
        except Exception as e:
            print(f"Erreur lors de l'insertion du modèle {model_name}: {e}")
            return False


# Fonction pour extraire le document_id depuis un chunk_id
def extract_document_id(chunk_id):
    return chunk_id.split("-")[0]

# Fonction pour extraire le numéro du chunk depuis un chunk_id
def extract_chunk_position(chunk_id):
    return int(chunk_id.split("-")[1])

def main():
    # Charger l'index FAISS et le mapping
    index = faiss.read_index(FAISS_INDEX_PATH)
    print(f"Nombre d'embeddings dans l'index FAISS: {index.ntotal}")

    with open(INDEX_MAPPING_PATH, "rb") as f:
        index_to_docstore_id = pickle.load(f)

    # Connexion à la base de données
    conn = get_db_connection()

    # Insérer la stratégie de chunking (si elle n'existe pas)
    strategy_id = insert_chunking_strategy(
        conn=conn,
        name="800_tokens_overlap_100",
        description="Stratégie de découpage en chunks de 800 tokens avec un overlap de 100 tokens",
        method="tokens",
        chunk_size=800,
        overlap=100,
    )
    print(f"Stratégie de chunking insérée avec l'ID: {strategy_id}")

    model_name = "mistral-embed"
    description = "Modèle d'embedding de Mistral AI, optimisé pour les tâches de RAG et de recherche sémantique."
    dimension = 768  # Dimension des embeddings générés par ce modèle
    success = insert_embedding_model(conn, model_name, description, dimension)


    # Parcourir tous les fichiers JSON de chunks
    json_files = [f for f in os.listdir(JSON_CHUNKS_DIR) if f.endswith("_chunks.json")]
    for json_file in json_files:
        json_path = os.path.join(JSON_CHUNKS_DIR, json_file)
        with open(json_path, "r", encoding="utf-8") as f:
            chunks_data_json = json.load(f)

        document_id = chunks_data_json["document_id"]
        file_name = f"{document_id}.pdf"
        file_path = os.path.join("documents/test-m3c", file_name)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        # Insérer le document
        insert_document(conn, document_id, file_name, file_path, file_size)
        print(f"Document inséré: {document_id}")

        # Préparer les données pour les chunks
        chunks_data = []
        embeddings_batch = []
        for chunk_id, chunk_info in chunks_data_json["chunks"].items():
            content = chunk_info["content"]
            num_page = chunk_info["num_page"]
            position_in_page = extract_chunk_position(chunk_id)
            token_count = len(content.split())  # Approximation
            metadata = json.dumps({
                "source": file_name,
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

            # Récupérer l'embedding depuis FAISS
            faiss_id = None
            for fid, docstore_id in index_to_docstore_id.items():
                if docstore_id == chunk_id:
                    faiss_id = fid
                    break

            if faiss_id is not None:
                # embedding is stored in a numpy.ndarray but it does not work
                # when adding it in postgres.
                embedding = index.reconstruct(faiss_id).tolist()
                embeddings_batch.append((chunk_id, model_name, embedding))

        # Insérer les chunks et les embeddings
        insert_chunks(conn, chunks_data)
        insert_chunk_embeddings_batch(conn, embeddings_batch)
        print(f"{len(chunks_data)} chunks et embeddings insérés pour {document_id}")

    # Valider les insertions
    conn.commit()
    conn.close()
    print("Migration terminée avec succès.")

if __name__ == "__main__":
    main()
