import psycopg
from psycopg import Connection, AsyncConnection

# Configuration de la base de données
DB_CONFIG = {
    "host": "localhost",
    "dbname": "mediationllm",
    "user": "postgres",
    "password": "postgres",
}

# Connexion à la base de données
async def get_db_connection() -> AsyncConnection:
    return await psycopg.AsyncConnection.connect(**DB_CONFIG)

# Fonction pour insérer un document
async def insert_document(conn, document_id, file_name, file_path, file_size):
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
async def insert_chunking_strategy(conn, name, description, method, chunk_size, overlap):
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
async def insert_chunks(conn, chunks_data):
    with conn.cursor() as cur:
        conn.executemany(
            """
            INSERT INTO chunks (chunk_id, document_id, strategy_id, content, num_page, position_in_page, token_count, metadata)
            VALUES %s
            ON CONFLICT (chunk_id) DO NOTHING;
            """,
            chunks_data,
        )

# Fonction pour insérer des embeddings
async def insert_chunk_embeddings(conn, chunk_id, model_name, embedding):
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

async def insert_chunk_embeddings_batch(conn, embeddings_batch):
    """
    Insère un lot d'embeddings pour des chunks et modèles donnés.

    Args:
        conn: Connexion à la base de données PostgreSQL.
        embeddings_batch (list): Liste de tuples (chunk_id, model_name, embedding).
    """
    with conn.cursor() as cur:
        conn.executemany(
            cur,
            """
            INSERT INTO chunk_embeddings (chunk_id, model_name, embedding)
            VALUES %s
            ON CONFLICT (chunk_id, model_name) DO NOTHING;
            """,
            embeddings_batch,
        )

async def insert_embedding_model(conn, model_name, description, dimension):
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

async def get_top_k_similar_chunks(conn, embedding: list[float], model_name: str, k=3):
    """
    Récupère les k meilleurs documents en fonction de la similarité cosinus avec un embedding donné.

    Args:
        conn: Connexion à la base de données PostgreSQL.
        embedding (list): Embedding de référence sous forme de liste.
        model_name (str): Nom du modèle d'embedding utilisé.
        k (int): Nombre de documents similaires à retourner.

    Returns:
        list: Liste des k meilleurs documents avec leur score de similarité.
    """
    print("get_top_k_similar_chunks")
    async with conn.cursor() as cur:
        # Requête pour récupérer les k meilleurs documents
        query = """
                SELECT c.chunk_id, \
                       c.document_id, \
                       c.content, \
                       c.num_page, \
                       c.position_in_page, \
                       c.token_count, \
                       c.metadata, \
                       1 - (ce.embedding <=> %s::vector) AS similarity
                FROM chunk_embeddings ce \
                         JOIN \
                     chunks c ON ce.chunk_id = c.chunk_id
                WHERE ce.model_name = %s
                ORDER BY similarity DESC
                    LIMIT %s;
                """

        # Exécuter la requête
        await cur.execute(query, (embedding, model_name, k))
        rows = await cur.fetchall()

        # Récupérer les noms des colonnes
        column_names = [desc[0] for desc in cur.description]

        # Convertir chaque ligne en dictionnaire
        results = [dict(zip(column_names, row)) for row in rows]
        return results
# Fonction pour extraire le document_id depuis un chunk_id
def extract_document_id(chunk_id):
    return chunk_id.split("-")[0]

# Fonction pour extraire le numéro du chunk depuis un chunk_id
def extract_chunk_position(chunk_id):
    return int(chunk_id.split("-")[1])