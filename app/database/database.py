from typing import Optional, List, Dict, Any

import aiomysql
from qdrant_client import QdrantClient, models

# Configuration de la base de données MySQL
DB_CONFIG = {
    "host": "localhost",
    "port": 8081,
    "db": "m3c_database",
    "user": "root",
    "password": "rootpassword",
    "autocommit": True
}

# Configuration Qdrant
QDRANT_CONFIG = {
    "host": "localhost",
    "port": 6333,
}

# Client Qdrant (synchrone, compatible avec async via threads)
qdrant_client = QdrantClient(**QDRANT_CONFIG)

# Connexion à la base de données MySQL
async def get_db_connection():
    return await aiomysql.connect(**DB_CONFIG)


# ============================================================================
# FONCTIONS QDRANT POUR LES EMBEDDINGS
# ============================================================================

async def ensure_qdrant_collection(model_name: str, vector_size: int):
    """Crée une collection Qdrant si elle n'existe pas."""
    try:
        qdrant_client.get_collection(model_name)
    except:
        qdrant_client.create_collection(
            collection_name=model_name,
            vectors_config=models.VectorParams(
                size=vector_size, 
                distance=models.Distance.COSINE
            )
        )


async def insert_chunk_embedding_qdrant(
    chunk_id: str, 
    document_id: str, 
    model_name: str, 
    embedding: list,
    content: str = None, 
    num_page: int = None, 
    position_in_page: int = None,
    token_count: int = None, 
    metadata: dict = None
):
    """Insère un embedding pour un chunk dans Qdrant."""
    await ensure_qdrant_collection(model_name, len(embedding))
    
    # Préparer le payload
    payload = {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "model_name": model_name,
    }
    if content: payload["content"] = content
    if num_page is not None: payload["num_page"] = num_page
    if position_in_page is not None: payload["position_in_page"] = position_in_page
    if token_count is not None: payload["token_count"] = token_count
    if metadata: payload["metadata"] = metadata
    
    # Insérer le point
    qdrant_client.upsert(
        collection_name=model_name,
        points=[
            models.PointStruct(
                id=str(chunk_id),
                vector=embedding,
                payload=payload
            )
        ]
    )


async def insert_chunk_embeddings_batch_qdrant(embeddings_batch: list):
    """
    Insertion par batch d'embeddings dans Qdrant.
    
    Args:
        embeddings_batch: Liste de dicts avec keys:
            chunk_id, document_id, model_name, embedding, content, 
            num_page, position_in_page, token_count, metadata
    """
    # Grouper par model_name
    by_model = {}
    for item in embeddings_batch:
        model = item["model_name"]
        if model not in by_model:
            by_model[model] = []
        by_model[model].append(item)
    
    # Traiter chaque modèle
    for model_name, items in by_model.items():
        await ensure_qdrant_collection(model_name, len(items[0]["embedding"]))
        
        points = []
        for item in items:
            payload = {
                "chunk_id": item["chunk_id"],
                "document_id": item["document_id"],
                "model_name": model_name,
            }
            if "content" in item and item["content"]: 
                payload["content"] = item["content"]
            if "num_page" in item and item["num_page"] is not None: 
                payload["num_page"] = item["num_page"]
            if "position_in_page" in item and item["position_in_page"] is not None:
                payload["position_in_page"] = item["position_in_page"]
            if "token_count" in item and item["token_count"] is not None:
                payload["token_count"] = item["token_count"]
            if "metadata" in item and item["metadata"]:
                payload["metadata"] = item["metadata"]
            
            points.append(models.PointStruct(
                id=str(item["chunk_id"]),
                vector=item["embedding"],
                payload=payload
            ))
        
        qdrant_client.upsert(
            collection_name=model_name,
            points=points,
            wait=True
        )


async def get_top_k_similar_chunks_qdrant(
    embedding: list, 
    model_name: str, 
    k: int = 3, 
    specified_document_id: str = None
) -> list:
    """
    Récupère les k chunks les plus similaires à un embedding donné.
    
    Args:
        embedding: Embedding de référence sous forme de liste
        model_name: Nom du modèle d'embedding (collection Qdrant)
        k: Nombre de résultats à retourner
        specified_document_id: Filtre optionnel par document_id
        
    Returns:
        Liste de dicts avec chunk_id, document_id, content, metadata, similarity
    """
    # Filtre optionnel par document
    query_filter = None
    if specified_document_id:
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=specified_document_id)
                )
            ]
        )
    
    # Recherche
    results = qdrant_client.search(
        collection_name=model_name,
        query_vector=embedding,
        limit=k,
        query_filter=query_filter,
        with_payload=True,
        with_vectors=False
    )
    
    # Formater les résultats
    return [
        {
            "chunk_id": r.id,
            "document_id": r.payload.get("document_id"),
            "content": r.payload.get("content"),
            "num_page": r.payload.get("num_page"),
            "position_in_page": r.payload.get("position_in_page"),
            "token_count": r.payload.get("token_count"),
            "metadata": r.payload.get("metadata"),
            "similarity": r.score
        }
        for r in results
    ]


async def get_chunk_embeddings_with_metadata_qdrant(
    model_name: str = "mistral-embed",
    document_id: str = None,
    limit: int = None
) -> list:
    """
    Récupère les chunks avec leurs embeddings et métadonnées depuis Qdrant.
    
    Args:
        model_name: Nom du modèle (collection Qdrant)
        document_id: Filtre optionnel par document
        limit: Limite du nombre de résultats
        
    Returns:
        Liste de dicts avec toutes les informations des chunks et leurs embeddings
    """
    # Filtre par document si spécifié
    query_filter = None
    if document_id:
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id)
                )
            ]
        )
    
    # Récupérer tous les points (ou limité)
    points, _ = qdrant_client.scroll(
        collection_name=model_name,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
        with_vectors=True
    )
    
    return [
        {
            "chunk_id": p.id,
            "document_id": p.payload.get("document_id"),
            "embedding": p.vector,
            "content": p.payload.get("content"),
            "num_page": p.payload.get("num_page"),
            "position_in_page": p.payload.get("position_in_page"),
            "token_count": p.payload.get("token_count"),
            "metadata": p.payload.get("metadata")
        }
        for p in points
    ]


# ============================================================================
# FONCTIONS MySQL POUR LES DONNÉES RELATIONNELLES
# ============================================================================

# Fonction pour insérer un document
async def insert_document(conn, document_id, file_name, file_path, file_size):
    async with conn.cursor() as cur:
        # Utiliser INSERT IGNORE pour éviter les doublons
        await cur.execute(
            """
            INSERT IGNORE INTO documents (document_id, file_name, file_path, file_size)
            VALUES (%s, %s, %s, %s)
            """,
            (document_id, file_name, file_path, file_size),
        )
        # Vérifier si l'insertion a réussi
        if cur.rowcount > 0:
            return document_id
        else:
            # Le document existait déjà, retourner l'ID existant
            await cur.execute(
                "SELECT document_id FROM documents WHERE document_id = %s",
                (document_id,)
            )
            result = await cur.fetchone()
            return result[0] if result else None

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
            VALUES (%s, %s, %s, %s, %s)
            """,
            (name, description, method, chunk_size, overlap),
        )
        # MySQL ne supporte pas RETURNING, utiliser LAST_INSERT_ID()
        return cur.lastrowid

# Fonction pour insérer des chunks
async def insert_chunks(conn, chunks_data):
    async with conn.cursor() as cur:
        # Utiliser INSERT IGNORE pour éviter les doublons
        await cur.executemany(
            """
            INSERT IGNORE INTO chunks (chunk_id, document_id, strategy_id, content, num_page, position_in_page, token_count, metadata)
            VALUES %s
            """,
            chunks_data,
        )

# NOTE: Les fonctions suivantes sont OBSOLÈTES et remplacées par les versions Qdrant
# Utiliser à la place: insert_chunk_embedding_qdrant() et insert_chunk_embeddings_batch_qdrant()

# async def insert_chunk_embeddings(conn, chunk_id, model_name, embedding):
#     """OBSOLÈTE - Utiliser insert_chunk_embedding_qdrant()"""
#     pass

# async def insert_chunk_embeddings_batch(conn, embeddings_batch):
#     """OBSOLÈTE - Utiliser insert_chunk_embeddings_batch_qdrant()"""
#     pass

async def insert_embedding_model(conn, model_name, description, dimension):
    """
    Insère un modèle d'embedding dans la table `embedding_models` (MySQL).

    Args:
        conn: Connexion à la base de données MySQL.
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
                INSERT IGNORE INTO embedding_models (model_name, description, dimension)
                VALUES (%s, %s, %s)
                """,
                (model_name, description, dimension),
            )
            return cur.rowcount > 0  # Retourne True si une ligne a été insérée
        except Exception as e:
            print(f"Erreur lors de l'insertion du modèle {model_name}: {e}")
            return False

async def insert_session(
    conn,
    session_id: str,
    user_id: int,
    document_id: str,
    started_at: str = None,
    ended_at: str = None,
    is_active: bool = True
) -> bool:
    """
    Insère une nouvelle session dans la table `sessions`.

    Args:
        conn: Connexion à la base de données PostgreSQL.
        session_id (str): Identifiant unique de la session (clé primaire).
        user_id (int): Identifiant de l'utilisateur associé à la session.
        document_id (str): Identifiant du document associé à la session.
        started_at (str, optionnel): Date de début de la session (format TIMESTAMP). Par défaut, NOW().
        ended_at (str, optionnel): Date de fin de la session (format TIMESTAMP). Par défaut, NULL.
        is_active (bool, optionnel): Indique si la session est active. Par défaut, True.

    Returns:
        bool: True si l'insertion a réussi, False si la session existait déjà ou en cas d'erreur.
    """
    async with conn.cursor() as cur:
        try:
            await cur.execute(
                """
                INSERT IGNORE INTO sessions (session_id, user_id, document_id, started_at, ended_at, is_active)
                VALUES (%s, %s, %s, COALESCE(%s, NOW()), %s, %s)
                """,
                (session_id, user_id, document_id, started_at, ended_at, is_active),
            )
            return cur.rowcount > 0
        except Exception as e:
            print(f"Erreur lors de l'insertion de la session {session_id}: {e}")
            return False

async def insert_session_answer(
    conn,
    session_id: str,
    question_id: int,
    question_text: str,
    answer_text: str,
    llm_comment: str = None,
    llm_rating: int = None,
    llm_model: str = None,
    message_type: str = None,
    answered_at: str = None
) -> bool:
    """
    Insère une réponse de session dans la table `session_answers`.

    Args:
        conn: Connexion à la base de données PostgreSQL.
        session_id (str): Identifiant de la session associée.
        question_id (int): Identifiant de la question associée.
        question_text (str): Texte de la question.
        answer_text (str): Texte de la réponse.
        llm_comment (str, optionnel): Commentaire du LLM.
        llm_rating (int, optionnel): Note attribuée par le LLM.
        llm_model (str, optionnel): Modèle LLM utilisé (ex: "mistral-tiny").
        message_type (str, optionnel): Type de message (ex: "réponse", "demande_renseignement").
        answered_at (str, optionnel): Date de la réponse (format TIMESTAMP). Par défaut, NOW().

    Returns:
        bool: True si l'insertion a réussi, False en cas d'erreur.
    """
    async with conn.cursor() as cur:
        try:
            await cur.execute(
                """
                INSERT INTO session_answers (
                    session_id, question_id, question_text, answer_text,
                    llm_comment, llm_rating, llm_model, message_type, answered_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()))
                """,
                (
                    session_id, question_id, question_text, answer_text,
                    llm_comment, llm_rating, llm_model, message_type, answered_at
                ),
            )
            return cur.rowcount > 0
        except Exception as e:
            print(f"Erreur lors de l'insertion de la réponse pour la session {session_id}: {e}")
            return False

async def get_resource_basic_metadata(conn, resource_id):
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, title, resource_type, owner_id, is_public, created, modified
            FROM resource
            WHERE id = %s
            """,
            (resource_id,)
        )
        result = await cur.fetchone()
        if result:
            return {
                "id": result[0],
                "title": result[1],
                "resource_type": result[2],
                "owner_id": result[3],
                "is_public": bool(result[4]),
                "created": result[5],
                "modified": result[6]
            }
        return None

async def get_resource_full_metadata(conn, resource_id):
    async with conn.cursor() as cur:
        # Récupérer les métadonnées de base
        basic_metadata = await get_resource_basic_metadata(conn, resource_id)
        if not basic_metadata:
            return None

        # Récupérer les métadonnées détaillées (champs + valeurs)
        await cur.execute(
            """
            SELECT p.local_name, v.value, v.type, v.lang
            FROM value v
            JOIN property p ON v.property_id = p.id
            WHERE v.resource_id = %s
            """,
            (resource_id,)
        )
        detailed_metadata = await cur.fetchall()

        # Construire un dictionnaire avec les métadonnées
        metadata = {**basic_metadata, "details": {}}
        for row in detailed_metadata:
            field_name, value, value_type, lang = row
            metadata["details"][field_name] = {
                "value": value,
                "type": value_type,
                "lang": lang
            }

        return metadata
async def get_question_by_id(conn,
                             question_id: int,
                             include_answers: bool = False) -> dict:
    question_data = {}
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT q.question_id, q.content, q.status, q.difficulty_level, q.created_by, q.validated_by
            FROM questions q
            WHERE q.question_id = %s
        """, (question_id,))
        result = await cur.fetchone()
        question_data["question_id"] = result[0]
        question_data["content"] = result[1]
        question_data["status"] = result[2]
        question_data["difficulty_level"] = result[3]
        question_data["created_by"] = result[4]
        question_data["validated_by"] = result[5]

        if include_answers:
            # Récupérer les réponses associées
            await cur.execute("""
                              SELECT content, created_by
                              FROM question_answers
                              WHERE question_id = %s
                              """, (question_id,))
            answer_rows = await cur.fetchall()
            question_data["answers"] = [{"content": answer[0],
                                         "created_by": answer[1]}
                                        for answer in answer_rows]
        return question_data

async def get_questions_by_ids(question_ids: list[str], conn) -> list[dict]:
    """
    Récupère les questions correspondant à une liste d'IDs.

    Args:
        question_ids: Liste des IDs des questions à récupérer.
        conn: Connexion à la base de données.

    Returns:
        Liste de dictionnaires représentant les questions trouvées.
        Retourne une liste vide si aucune question n'est trouvée.
    """
    if not question_ids:
        return []

    # MySQL utilise IN au lieu de ANY
    placeholders = ", ".join(["%s"] * len(question_ids))
    query = f"""
        SELECT q.question_id, q.content, q.status, q.difficulty_level, q.created_by, q.validated_by
        FROM questions q
        WHERE q.question_id IN ({placeholders})
    """
    async with conn.cursor() as cur:
        await cur.execute(query, tuple(question_ids))
        rows = await cur.fetchall()

    return [
        {
            "question_id": row[0],
            "content": row[1],
            "status": row[2],
            "difficulty_level": row[3],
            "created_by": row[4],
            "validated_by": row[5],
        }
        for row in rows
    ]

async def get_chunk_by_id(chunk_id: int, conn) -> dict:
    """
    Récupère le chunk correspondant à l'id donné.
    """
    async with conn.cursor() as cur:
        await cur.execute("""
                          SELECT c.chunk_id, c.content, c.num_page, c.position_in_page, c.metadata
                          FROM chunks c
                          WHERE c.chunk_id = %s""", (chunk_id,))
        row = await cur.fetchone()
        return {"chunk_id": row[0],
                 "content": row[1],
                 "num_page": row[2],
                 "position_in_page": row[3],
                 "metadata": row[4]}

async def get_chunks_for_document(
    document_id: str,
    conn,
    chunking_strategy_id: int = 7
):
    """Récupère tous les chunks d'un document depuis la base de données.
    Filtre par chunking_strategy_id si fourni.
    Valeurs correspondantes de chunking_strategy_id :
    1 - découpage initial en chunks de 800 tokens et overlap de 100 tokens
    7 - découpage en chunks de 2700 caractères et overlap de 400 caractères
    """
    query = """
        SELECT chunk_id, content
        FROM chunks
        WHERE document_id = %s
    """
    params = [document_id]

    if chunking_strategy_id is not None:
        query += " AND strategy_id = %s"
        params.append(chunking_strategy_id)

    async with conn.cursor() as cur:
        await cur.execute(query, params)
        return await cur.fetchall()


async def get_chunks_by_question_id(question_id: int, conn):
    """
    Récupère les chunks associés à une question via la table question_chunks.
    """
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT c.chunk_id, c.content, c.num_page, c.position_in_page, qc.question_id
            FROM chunks c
            JOIN question_chunks qc ON c.chunk_id = qc.chunk_id
            WHERE qc.question_id = %s""", (question_id,))
        rows = await cur.fetchall()
        return [{"chunk_id": row[0],
                 "content": row[1],
                 "num_page": row[2],
                 "position_in_page": row[3],
                 "question_id": row[4]} for row in rows]


async def get_chunks_by_question_ids(question_ids: list[int], conn):
    """
    Récupère les chunks associés à une liste de questions via la table question_chunks.

    Args:
        question_ids: Liste des identifiants de questions.
        conn: Connexion à la base de données.

    Returns:
        Liste de dictionnaires représentant les chunks associés à chaque question.
    """
    if not question_ids:
        return []

    async with conn.cursor() as cur:
        # MySQL utilise IN au lieu de ANY
        placeholders = ", ".join(["%s"] * len(question_ids))
        query = f"""
            SELECT c.chunk_id, c.content, c.num_page, c.position_in_page, qc.question_id
            FROM chunks c
            JOIN question_chunks qc ON c.chunk_id = qc.chunk_id
            WHERE qc.question_id IN ({placeholders})
        """
        await cur.execute(query, tuple(question_ids))

        rows = await cur.fetchall()
        return [
            {
                "chunk_id": row[0],
                "content": row[1],
                "num_page": row[2],
                "position_in_page": row[3],
                "question_id": row[4]
            }
            for row in rows
        ]


# NOTE: Les fonctions suivantes sont OBSOLÈTES et remplacées par Qdrant
# Utiliser à la place: get_top_k_similar_chunks_qdrant()

# async def get_top_k_similar_chunks_cossim(conn, embedding, model_name, k, specified_document_id):
#     """OBSOLÈTE - Utiliser get_top_k_similar_chunks_qdrant()"""
#     pass

# async def get_top_k_similar_chunks_cossim_python(conn, embedding, model_name, k):
    """
    Récupère les k meilleurs documents en fonction de la similarité cosinus avec un embedding donné.
    La comparaison est effectuée directement sur Python et non par Postgres.
    Args:
        conn: Connexion à la base de données PostgreSQL.
        embedding (list): Embedding de référence sous forme de liste.
        model_name (str): Nom du modèle d'embedding utilisé.
        k (int): Nombre de documents similaires à retourner.

    Returns:
        list: Liste des k meilleurs documents avec leur score de similarité.
    """
    pass  # OBSOLÈTE - Utiliser get_top_k_similar_chunks_qdrant()


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
        """, (question, "generated", difficulty_level, None, None))
        question_id = cur.lastrowid

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

async def get_document_data_from_chunk_id(chunk_id: str, conn) -> Optional[Dict]:
    """
    Récupère les données d'un document à partir d'un chunk_id.

    Args:
        chunk_id (str): L'identifiant du chunk.
        conn: Connexion à la base de données.

    Returns:
        Optional[Dict]: Dictionnaire contenant les données du document, ou None si non trouvé.
    """
    async with conn.cursor() as cur:
        # Extraire le document_id du chunk_id
        document_id = extract_document_id(chunk_id)

        # Récupérer les données du document
        await cur.execute("""
            SELECT document_id, file_name, file_path, file_size, created_at, updated_at
            FROM documents
            WHERE document_id = %s
        """, (document_id,))

        result = await cur.fetchone()

        if result:
            return {
                "document_id": result[0],
                "file_name": result[1],
                "file_path": result[2],
                "file_size": result[3],
                "created_at": result[4],
                "updated_at": result[5]
            }

        return None

async def get_all_documents(conn) -> List[Dict]:
    """
    Récupère tous les documents de la base de données.

    Args:
        conn: Connexion à la base de données.

    Returns:
        List[Dict]: Liste de tous les documents avec leurs métadonnées.
    """
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT document_id, file_name, file_path, file_size, created_at, updated_at
            FROM documents
            ORDER BY created_at DESC
        """)

        results = await cur.fetchall()

        documents = []
        for result in results:
            documents.append({
                "document_id": result[0],
                "file_name": result[1],
                "file_path": result[2],
                "file_size": result[3],
                "created_at": result[4],
                "updated_at": result[5]
            })

        return documents

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

# NOTE: Fonction OBSOLÈTE - Utiliser get_chunk_embeddings_with_metadata_qdrant()
# async def get_chunk_embeddings_with_metadata(
#     conn,
#     document_id: Optional[str] = None,
#     limit: Optional[int] = None,
#     with_text_content: Optional[bool] = False,
#     model_name: str = "mistral-embed"
# ) -> List[Dict[str, Any]]:
    """
    Récupère les chunks avec leurs embeddings et métadonnées.

    Args:
        conn: Connexion à la base de données PostgreSQL
        document_id: Filtre optionnel par document ID
        limit: Limite optionnelle du nombre de résultats
        model_name: Nom du modèle d'embedding à utiliser

    Returns:
        Liste de dictionnaires contenant chunk_id, document_id, content, embedding,
        num_page, position_in_page, token_count, metadata
    """
#     async with conn.cursor() as cur:


# ============================================================================
# FONCTIONS POUR L'ADMINISTRATION - INDEXATION
# ============================================================================

async def get_all_documents_with_details(conn) -> List[Dict]:
    """
    Récupère tous les documents avec leurs détails (extracted_text, metadata).
    Gère automatiquement les cas où ces colonnes n'existent pas.
    
    Args:
        conn: Connexion MySQL
        
    Returns:
        Liste de dictionnaires avec les documents et leurs détails
    """
    async with conn.cursor() as cur:
        # Essayer avec extracted_text et metadata
        try:
            await cur.execute("""
                SELECT document_id, file_name, file_path, file_size, created_at, updated_at, 
                       extracted_text, metadata 
                FROM documents 
                ORDER BY created_at DESC
            """)
            results = await cur.fetchall()
            has_extracted_text_col = True
        except Exception:
            # Si la colonne n'existe pas, essayer sans
            try:
                await cur.execute("""
                    SELECT document_id, file_name, file_path, file_size, created_at, updated_at, 
                           metadata 
                    FROM documents 
                    ORDER BY created_at DESC
                """)
                results = await cur.fetchall()
                has_extracted_text_col = False
            except Exception:
                # Si metadata n'existe pas non plus
                await cur.execute("""
                    SELECT document_id, file_name, file_path, file_size, created_at, updated_at 
                    FROM documents 
                    ORDER BY created_at DESC
                """)
                results = await cur.fetchall()
                has_extracted_text_col = False
    
    documents = []
    for result in results:
        doc = {
            "document_id": result[0],
            "file_name": result[1],
            "file_path": result[2],
            "file_size": result[3],
            "created_at": str(result[4]),
            "updated_at": str(result[5])
        }
        
        # Ajouter extracted_text si disponible
        if has_extracted_text_col and len(result) > 6:
            doc["extracted_text"] = result[6]
        
        # Ajouter metadata si disponible
        if len(result) > 7:
            doc["metadata"] = result[7] if result[7] else {}
        elif len(result) > 6 and not has_extracted_text_col:
            doc["metadata"] = result[6] if result[6] else {}
        
        # Déterminer si le document a du contenu extrait
        doc["has_extracted_text"] = bool(doc.get("extracted_text"))
        
        documents.append(doc)
    
    return documents


async def get_documents_by_ids(conn, document_ids: List[str]) -> Dict[str, Dict]:
    """
    Récupère des documents spécifiques avec leurs détails.
    
    Args:
        conn: Connexion MySQL
        document_ids: Liste des IDs de documents à récupérer
        
    Returns:
        Dictionnaire mapping document_id -> document data
    """
    placeholders = ", ".join(["%s"] * len(document_ids))
    
    async with conn.cursor() as cur:
        # Essayer avec extracted_text et metadata
        try:
            query = f"""
                SELECT document_id, file_name, file_path, file_size, extracted_text, metadata 
                FROM documents 
                WHERE document_id IN ({placeholders})
            """
            await cur.execute(query, tuple(document_ids))
            results = await cur.fetchall()
            has_extracted_text_col = True
        except Exception:
            # Essayer sans extracted_text
            try:
                query = f"""
                    SELECT document_id, file_name, file_path, file_size, metadata 
                    FROM documents 
                    WHERE document_id IN ({placeholders})
                """
                await cur.execute(query, tuple(document_ids))
                results = await cur.fetchall()
                has_extracted_text_col = False
            except Exception:
                # Essayer sans metadata non plus
                query = f"""
                    SELECT document_id, file_name, file_path, file_size 
                    FROM documents 
                    WHERE document_id IN ({placeholders})
                """
                await cur.execute(query, tuple(document_ids))
                results = await cur.fetchall()
                has_extracted_text_col = False
    
    docs_map = {}
    for row in results:
        doc_data = {
            "document_id": row[0],
            "file_name": row[1],
            "file_path": row[2],
            "file_size": row[3]
        }
        
        # Ajouter extracted_text si disponible
        if has_extracted_text_col and len(row) > 4:
            doc_data["extracted_text"] = row[4]
        
        # Ajouter metadata si disponible
        if len(row) > 5:
            doc_data["metadata"] = row[5] if row[5] else {}
        elif len(row) > 4 and not has_extracted_text_col:
            doc_data["metadata"] = row[4] if row[4] else {}
        
        docs_map[row[0]] = doc_data
    
    return docs_map


async def get_all_documents_for_metadata_indexing(conn) -> Dict[str, Dict]:
    """
    Récupère TOUS les documents pour indexation par métadonnées.
    
    Args:
        conn: Connexion MySQL
        
    Returns:
        Dictionnaire mapping document_id -> document data
    """
    all_docs = await get_all_documents_with_details(conn)
    return {doc["document_id"]: doc for doc in all_docs}


async def get_all_documents_with_extracted_text(conn) -> Dict[str, Dict]:
    """
    Récupère TOUS les documents qui ont un extracted_text pour indexation par contenu.
    
    Args:
        conn: Connexion MySQL
        
    Returns:
        Dictionnaire mapping document_id -> document data (seulement ceux avec extracted_text)
    """
    all_docs = await get_all_documents_with_details(conn)
    # Filtrer pour garder seulement ceux avec extracted_text
    return {doc["document_id"]: doc for doc in all_docs if doc.get("has_extracted_text")}


async def count_documents_with_extracted_text(conn) -> int:
    """
    Compte le nombre de documents qui ont un extrait_text.
    
    Args:
        conn: Connexion MySQL
        
    Returns:
        Nombre de documents avec extracted_text
    """
    try:
        async with conn.cursor() as cur:
            try:
                await cur.execute("SELECT COUNT(*) FROM documents WHERE extracted_text IS NOT NULL AND extracted_text != ''")
                count = (await cur.fetchone())[0] or 0
            except Exception:
                # Si la colonne n'existe pas, retourner 0
                await cur.execute("SELECT COUNT(*) FROM documents")
                count = (await cur.fetchone())[0] or 0
        return count
    except Exception:
        return 0


async def get_documents_with_extracted_text_count() -> int:
    """
    Récupère le nombre de documents avec un champ extracted_text.
    Ouvre et ferme sa propre connexion à la base de données.
    
    Returns:
        Nombre de documents avec extracted_text
    """
    conn = await get_db_connection()
    try:
        return await count_documents_with_extracted_text(conn)
    finally:
        await conn.close()


async def get_db_stats() -> Dict[str, Any]:
    """
    Récupère les statistiques MySQL pour l'administration.
    
    Returns:
        Dictionnaire avec:
        - documents_count: Nombre de documents
        - chunks_count: Nombre de chunks
        - documents_with_extracted_text_count: Nombre de documents avec extracted_text
    """
    conn = await get_db_connection()
    
    try:
        async with conn.cursor() as cur:
            # Compter les documents
            await cur.execute("SELECT COUNT(*) FROM documents")
            documents_count = (await cur.fetchone())[0] or 0
            
            # Compter les chunks
            await cur.execute("SELECT COUNT(*) FROM chunks")
            chunks_count = (await cur.fetchone())[0] or 0
            
            # Compter les documents avec extracted_text
            try:
                await cur.execute("SELECT COUNT(*) FROM documents WHERE extracted_text IS NOT NULL AND extracted_text != ''")
                docs_with_text = (await cur.fetchone())[0] or 0
            except Exception:
                docs_with_text = 0
        
        return {
            "documents_count": documents_count,
            "chunks_count": chunks_count,
            "documents_with_extracted_text_count": docs_with_text
        }
    finally:
        await conn.close()


async def get_qdrant_stats() -> Dict[str, int]:
    """
    Récupère les statistiques Qdrant (nombre d'embeddings par collection).
    
    Returns:
        Dictionnaire mapping collection_name -> nombre de points
    """
    embeddings_count = {}
    try:
        collections = qdrant_client.get_collections()
        for collection in collections.collections:
            collection_name = collection.name
            points_count = qdrant_client.get_collection(collection_name).points_count or 0
            embeddings_count[collection_name] = points_count
    except Exception as e:
        print(f"Erreur lors de la récupération des stats Qdrant: {e}")
    
    return embeddings_count


async def get_admin_stats() -> Dict[str, Any]:
    """
    Récupère les statistiques d'indexation pour l'administration.
    
    Returns:
        Dictionnaire avec:
        - documents_count: Nombre de documents
        - chunks_count: Nombre de chunks
        - embeddings_count: Dictionnaire {model_name: count}
        - documents_with_extracted_text_count: Nombre de documents avec extracted_text
    """
    db_stats = await get_db_stats()
    embeddings_count = await get_qdrant_stats()
    
    return {
        **db_stats,
        "embeddings_count": embeddings_count
    }
#         # Build the query to fetch chunks with their embeddings
#         query = f"""
#             SELECT