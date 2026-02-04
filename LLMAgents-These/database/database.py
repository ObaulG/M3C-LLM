from typing import Optional, List, Dict

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
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO documents (document_id, file_name, file_path, file_size)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (document_id) DO NOTHING
            RETURNING document_id;
            """,
            (document_id, file_name, file_path, file_size),
        )
        return await cur.fetchone()[0] if cur.rowcount > 0 else None

# Fonction pour insérer une stratégie de chunking
async def insert_chunking_strategy(conn, name, description, method, chunk_size, overlap):
    async with conn.cursor() as cur:
        # Vérifier si une stratégie avec les mêmes paramètres existe déjà
        await cur.execute(
            """
            SELECT strategy_id
            FROM chunking_strategies
            WHERE method = %s
              AND chunk_size = %s
              AND overlap = %s
            """,
            (method, chunk_size, overlap),
        )
        result = await cur.fetchone()
        if result:
            return result[0]  # Retourner l'ID de la stratégie existante

        # Sinon, insérer la nouvelle stratégie
        await cur.execute(
            """
            INSERT INTO chunking_strategies (name, description, method, chunk_size, overlap)
            VALUES (%s, %s, %s, %s, %s) RETURNING strategy_id;
            """,
            (name, description, method, chunk_size, overlap),
        )
        return await cur.fetchone()[0]

# Fonction pour insérer des chunks
async def insert_chunks(conn, chunks_data):
    async with conn.cursor() as cur:
        await cur.executemany(
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
    async with conn.cursor() as cur:
        await cur.execute(
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
    async with conn.cursor() as cur:
        await conn.executemany(
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
    async with conn.cursor() as cur:
        try:
            await cur.execute(
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

async def get_question_by_id(question_id, conn):
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT q.question_id, q.content, q.status, q.difficulty_level, q.created_by, q.validated_by
            FROM questions q
            WHERE q.question_id = %s
        """, (question_id,))
        result = await cur.fetchone()
        if result is not None:
            return {
                "question_id": result[0],
                "content": result[1],
                "status": result[2],
                "difficulty_level": result[3],
                "created_by": result[4],
                "validated_by": result[5],
            }
        return None
async def get_chunks_for_document(document_id: str, conn):
    """Récupère tous les chunks d'un document depuis la base de données."""
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT chunk_id, content
            FROM chunks
            WHERE document_id = %s
        """, (document_id,))
        return await cur.fetchall()

async def get_chunks_by_question_id(question_id: int, conn):
    """
    Récupère les chunks associés à une question via la table question_chunks.
    """
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT c.chunk_id, c.content, c.num_page, c.position_in_page
            FROM chunks c
            JOIN question_chunks qc ON c.chunk_id = qc.chunk_id
            WHERE qc.question_id = %s""", (question_id,))
        rows = await cur.fetchall()
        return [{"chunk_id": row[0],
                 "content": row[1],
                 "num_page": row[2],
                 "position_in_page": row[3]} for row in rows]  # Convertit chaque ligne en dictionnaire

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

async def save_question_to_db(
    question: str,
    answer: str,
    chunk_id: str,
    conn,
    difficulty_level: int = 3,
    model: str = '',
) -> None:
    """Enregistre une question, sa réponse et son lien au chunk dans la base de données."""
    async with conn.cursor() as cur:
        # 1. Insérer la question
        await cur.execute("""
            INSERT INTO questions (content, status, difficulty_level, created_by, validated_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING question_id
        """, (question, "generated", difficulty_level, None, None))
        result = await cur.fetchone()
        question_id = result[0]

        # 2. Lier la question au chunk
        await cur.execute("""
            INSERT INTO question_chunks (question_id, chunk_id)
            VALUES (%s, %s)
        """, (question_id, chunk_id))

        # 3. Insérer la réponse
        await cur.execute("""
            INSERT INTO question_answers (question_id, content, is_correct, created_by)
            VALUES (%s, %s, %s, %s)
        """, (question_id, answer, True, None))

        await conn.commit()

async def get_questions_by_document_id(
    document_id: str,
    conn,
    include_answers: bool = True,
    status_filter: Optional[str] = None,
    difficulty_filter: Optional[int] = None,
    theme_filter: Optional[str] = None,
    nb_limit: Optional[int] = 0,
) -> List[Dict]:
    """
    Récupère les questions associées à un document (via ses chunks).

    Args:
        document_id (str): L'identifiant du document.
        conn (asyncpg.Connection): Connexion à la base de données.
        include_answers (bool): Si True, inclut les réponses associées aux questions.
        status_filter (Optional[str]): Filtre les questions par statut (ex: "generated", "validated").
        difficulty_filter (Optional[int]): Filtre les questions par niveau de difficulté.
        theme_filter (Optional[str]): Filtre les questions par thème.
        nb_limit(Optional[int]): limite du nombre de questions retournées

    Returns:
        List[Dict]: Liste de dictionnaires représentant les questions et leurs réponses.
    """
    questions = []

    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT chunk_id
            FROM chunks
            WHERE document_id = %s
        """, (document_id,))
        chunk_rows = await cur.fetchall()

        if not chunk_rows:
            return questions

        chunk_ids = [row[0] for row in chunk_rows]

        query = """
            SELECT q.question_id, q.content, q.status, q.difficulty_level, q.created_by, q.validated_by, qc.chunk_id
            FROM question_chunks qc
            JOIN questions q ON qc.question_id = q.question_id
            WHERE qc.chunk_id = ANY(%s)
        """
        params = [chunk_ids]

        if status_filter:
            query += " AND q.status = %s"
            params.append(status_filter)

        if difficulty_filter:
            query += " AND q.difficulty_level = %s"
            params.append(difficulty_filter)

        if theme_filter:
            query += " AND q.theme = %s"
            params.append(theme_filter)

        if nb_limit:
            query += " LIMIT %s"
            params.append(nb_limit)

        await cur.execute(query, params)
        question_rows = await cur.fetchall()

        # 3. Pour chaque question, récupérer les réponses si nécessaire
        for row in question_rows:
            question_id, content, status, difficulty_level, created_by, validated_by, chunk_id = row
            question = {
                "question_id": question_id,
                "content": content,
                "status": status,
                "difficulty_level": difficulty_level,
                "created_by": created_by,
                "validated_by": validated_by,
                "chunk_id": chunk_id,
                "answers": []
            }

            if include_answers:
                # Récupérer les réponses associées
                await cur.execute("""
                    SELECT content, is_correct, created_by
                    FROM question_answers
                    WHERE question_id = %s
                """, (question_id,))
                answer_rows = await cur.fetchall()

                for answer_row in answer_rows:
                    answer_content, is_correct, answer_created_by = answer_row
                    question["answers"].append({
                        "content": answer_content,
                        "is_correct": is_correct,
                        "created_by": answer_created_by
                    })

            questions.append(question)

    return questions

async def get_questions_by_chunk_id(
    chunk_id: str,
    conn,
    include_answers: bool = True,
    status_filter: Optional[str] = None
) -> List[Dict]:
    """
    Récupère les questions associées à un chunk de document.

    Args:
        chunk_id (str): L'identifiant du chunk pour lequel récupérer les questions.
        conn (asyncpg.Connection): Connexion à la base de données.
        include_answers (bool): Si True, inclut les réponses associées aux questions.
        status_filter (Optional[str]): Filtre les questions par statut (ex: "generated", "validated").

    Returns:
        List[Dict]: Liste de dictionnaires représentant les questions et leurs réponses.
    """
    questions = []

    async with conn.cursor() as cur:
        # 1. Récupérer les IDs des questions liées au chunk
        query = """
            SELECT q.question_id, q.content, q.status, q.difficulty_level, q.created_by, q.validated_by
            FROM question_chunks qc
            JOIN questions q ON qc.question_id = q.question_id
            WHERE qc.chunk_id = %s
        """
        params = [chunk_id]

        if status_filter:
            query += " AND q.status = %s"
            params.append(status_filter)

        await cur.execute(query, params)
        question_rows = await cur.fetchall()

        # 2. Pour chaque question, récupérer les réponses si nécessaire
        for row in question_rows:
            question_id, content, status, difficulty_level, created_by, validated_by = row
            question = {
                "question_id": question_id,
                "content": content,
                "status": status,
                "difficulty_level": difficulty_level,
                "created_by": created_by,
                "validated_by": validated_by,
                "answers": []
            }

            if include_answers:
                # Récupérer les réponses associées
                await cur.execute("""
                    SELECT content, is_correct, created_by
                    FROM question_answers
                    WHERE question_id = %s
                """, (question_id,))
                answer_rows = await cur.fetchall()

                for answer_row in answer_rows:
                    answer_content, is_correct, answer_created_by = answer_row
                    question["answers"].append({
                        "content": answer_content,
                        "is_correct": is_correct,
                        "created_by": answer_created_by
                    })

            questions.append(question)

    return questions

async def delete_questions_for_pages_1_to_12(
    conn,
    document_id: Optional[str] = None,
    dry_run: bool = False
) -> List[int]:
    """
    Supprime les questions associées aux pages 1 à 12 (sommaire) d'un document.
    Si `document_id` est fourni, ne supprime que pour ce document.
    Si `dry_run` est True, retourne uniquement les IDs des questions à supprimer sans les supprimer.

    Args:
        conn (asyncpg.Connection): Connexion à la base de données.
        document_id (Optional[str]): ID du document (optionnel, pour filtrer par document).
        dry_run (bool): Si True, ne supprime pas, retourne juste les IDs des questions concernées.

    Returns:
        List[int]: Liste des IDs des questions supprimées (ou à supprimer en mode dry_run).
    """
    deleted_question_ids = []

    async with conn.cursor() as cur:
        # 1. Récupérer les chunk_id des pages 1 à 12
        query = """
            SELECT chunk_id
            FROM chunks
            WHERE num_page BETWEEN 1 AND 12
        """
        params = []
        if document_id:
            query += " AND document_id = %s"
            params.append(document_id)

        await cur.execute(query, params)
        chunk_rows = await cur.fetchall()

        if not chunk_rows:
            return deleted_question_ids

        chunk_ids = [row[0] for row in chunk_rows]

        # 2. Récupérer les question_id associées à ces chunk_ids
        await cur.execute("""
            SELECT DISTINCT q.question_id
            FROM question_chunks qc
            JOIN questions q ON qc.question_id = q.question_id
            WHERE qc.chunk_id = ANY(%s)
        """, (chunk_ids,))

        question_rows = await cur.fetchall()
        question_ids_to_delete = [row[0] for row in question_rows]
        print(question_ids_to_delete)
        if dry_run:
            return question_ids_to_delete

        # 3. Supprimer les questions
        for question_id in question_ids_to_delete:
            await cur.execute("""
                DELETE FROM questions
                WHERE question_id = %s
            """, (question_id,))
            deleted_question_ids.append(question_id)
            print(f"question {question_id} was deleted")
    return deleted_question_ids
# Fonction pour extraire le document_id depuis un chunk_id
def extract_document_id(chunk_id):
    return chunk_id.split("-")[0]

# Fonction pour extraire le numéro du chunk depuis un chunk_id
def extract_chunk_position(chunk_id):
    return int(chunk_id.split("-")[1])