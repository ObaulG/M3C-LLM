from typing import Optional, List, Dict, Any, Tuple
import asyncio
import json
import aiomysql
from qdrant_client import QdrantClient, models

# Configuration de la base de données MySQL
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "db": "m3c_database",
    "user": "OBL",
    "password": "azerty",
    "autocommit": True
}

# Configuration Qdrant
QDRANT_CONFIG = {
    "host": "localhost",
    "port": 6333,
}

# Client Qdrant (synchrone, compatible avec async via threads)
qdrant_client = QdrantClient(**QDRANT_CONFIG)

# Contient les resource_id (table value) dont le champ extracted_text contient un texte valide et vérifié,
# avec un nombre minimum d'artefacts
VALID_TEXT_RESOURCE_ID = [116723, 116789, 116805, 116729, 116806, 116781, 116737, 116732, 116719, 116721,
                          116725, 116735, 116734, 116782, 76715, 116727, 116787, 116738, 116795]
#VALID_TEXT_RESOURCE_ID = [116738, 116782]

# Connexion à la base de données MySQL
async def get_db_connection():
    loop = asyncio.get_event_loop()
    return await aiomysql.connect(**DB_CONFIG, loop=loop)


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
    metadata: dict = None,
    collection_name: str = None
):
    """Insère un embedding pour un chunk dans Qdrant.
    
    Returns:
        Le résultat de l'upsert (UpsertResult du client Qdrant)
    """
    # Utiliser collection_name si fourni, sinon model_name
    final_collection_name = collection_name or model_name
    await ensure_qdrant_collection(final_collection_name, len(embedding))
    print(f"Collection {final_collection_name} vérifiée.")
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
    
    # Insérer le point et retourner le résultat
    return qdrant_client.upsert(
        collection_name=final_collection_name,
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
    collection_name: str,
    k: int = 3, 
    specified_document_id: str = None,
    with_payload: bool = True,
) -> list:
    """
    Récupère les k chunks les plus similaires à un embedding donné.
    
    Args:
        embedding: Embedding de référence sous forme de liste
        collection_name: Nom de la collection Qdrant
        k: Nombre de résultats à retourner
        specified_document_id: Filtre optionnel par document_id
        
    Returns:
        Liste de dicts avec chunk_id, document_id, content, metadata, similarity
    """
    import asyncio
    
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
    
    # Exécuter la recherche de manière asynchrone
    # (qdrant_client.search est bloquant, donc on l'exécute dans un thread)
    results = await asyncio.to_thread(
        qdrant_client.query_points,
        collection_name=collection_name,
        query=embedding,
        limit=k,
        query_filter=query_filter,
        with_payload=with_payload,
    )
    results = results.points

    # Formater les résultats
    return [
        {
            "chunk_id": point.payload.get("chunk_id"),
            "document_id": point.payload.get("document_id"),
            "content": point.payload.get("content"),
            "num_page": point.payload.get("num_page"),
            "position_in_page": point.payload.get("position_in_page"),
            "token_count": point.payload.get("token_count"),
            "metadata": point.payload.get("metadata"),
            "similarity": point.score
        }
        for point in results
    ]


async def get_chunk_embeddings_with_metadata_qdrant(
    collection_name: str,
    document_id: str = None,
    limit: int = None
) -> list:
    """
    Récupère les chunks avec leurs embeddings et métadonnées depuis Qdrant.
    
    Args:
        collection_name: Nom de la collection Qdrant
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
        collection_name=collection_name,
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

# Fonction pour insérer un document dans text_documents
async def insert_text_document(conn, source_type: str, source_id: str, content: str) -> int:
    """
    Insère un document dans text_documents et retourne son id.
    Utilise INSERT IGNORE pour éviter les doublons.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT IGNORE INTO text_documents (source_type, source_id, content)
            VALUES (%s, %s, %s)
            """,
            (source_type, source_id, content)
        )
        if cur.rowcount > 0:
            return cur.lastrowid
        else:
            # Document existait déjà, retourner l'ID existant
            await cur.execute(
                "SELECT id FROM text_documents WHERE source_type = %s AND source_id = %s",
                (source_type, source_id)
            )
            result = await cur.fetchone()
            return result[0] if result else None


# Fonction pour récupérer ou créer une stratégie de chunking
async def get_or_create_chunking_strategy(
    conn, 
    name: str, 
    method: str, 
    chunk_size: int = None,
    char_size: int = None, 
    overlap: int = 0
) -> int:
    """
    Récupère ou crée une stratégie de chunking et retourne son id.
    """
    async with conn.cursor() as cur:
        # Vérifier si la stratégie existe déjà
        await cur.execute(
            """
            SELECT id FROM text_chunking_strategies
            WHERE name = %s AND method = %s AND chunk_size = %s AND overlap = %s
            """,
            (name, method, chunk_size, overlap)
        )
        result = await cur.fetchone()
        if result:
            return result[0]
        
        # Créer une nouvelle stratégie
        await cur.execute(
            """
            INSERT INTO text_chunking_strategies (name, description, method, chunk_size, char_size, overlap)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (name, f"{method}_chunk:{chunk_size}_overlap:{overlap}", method, 
             chunk_size, char_size or chunk_size, overlap)
        )
        return cur.lastrowid


# Fonction pour insérer des chunks
async def insert_chunks(conn, chunks_data):
    """
    Insère des chunks dans text_chunks.
    
    chunks_data: Liste de tuples (id, document_id, strategy_id, content, 
                                  num_page, position_in_page, token_count, character_count)
    """
    async with conn.cursor() as cur:
        # Utiliser INSERT IGNORE pour éviter les doublons
        await cur.executemany(
            """
            INSERT IGNORE INTO text_chunks 
            (id, document_id, strategy_id, content, num_page, position_in_page, token_count, character_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            chunks_data,
        )

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
    """
    Retourne un Dict contenant le titre (1), l'auteur (2), la date (7) d'un resource à partir
    de son id.
    Note: dans la BDD M3C, un resource contient le titre, et d'autres informations.
    Les métadonnées d'un resource sont contenues dans la table value, et dans cette table, on attribue
    à chaque id de property une valeur correspondante.
    Exemple: dans property, les id 1 et 2 sont respectivement "title" et "author"
    Pour récupérer le titre et l'auteur de la resource_id 116738, on ira chercher dans value
    les lignes avec property_id à 1 et 2.
    """
    async with conn.cursor() as cur:
        await cur.execute("""
                          SELECT MAX(CASE WHEN v.property_id = 1 THEN v.value END) as title,
                                 MAX(CASE WHEN v.property_id = 2 THEN v.value END) as creator,
                                 MAX(CASE WHEN v.property_id = 7 THEN v.value END) as date
                          FROM value v
                          WHERE v.resource_id = %s""", (resource_id,))

        result = await cur.fetchone()

        if not result:
            return {"title": None, "creator": None, "created_at": None}

        return {
            "title": result[0],
            "creator": result[1],
            "created_at": result[2]
        }


async def get_resource_full_metadata(conn, resource_id):
    """
    Récupère toutes les métadonnées pertinentes pour un resource.
    Property IDs: 1=title, 2=creator, 3=subject, 4=description, 5=publisher,
                  6=contributor, 7=date, 8=type, 12=language, 19=abstract
    
    Args:
        conn: Connexion à la base de données
        resource_id: L'ID de la ressource
        
    Returns:
        Dict avec toutes les métadonnées et une liste pour les subjects (multi-valued)
    """
    async with conn.cursor() as cur:
        # Récupérer les valeurs simples (une seule valeur attendue)
        await cur.execute("""
                          SELECT 
                              MAX(CASE WHEN v.property_id = 1 THEN v.value END) as title,
                              MAX(CASE WHEN v.property_id = 2 THEN v.value END) as creator,
                              MAX(CASE WHEN v.property_id = 4 THEN v.value END) as description,
                              MAX(CASE WHEN v.property_id = 5 THEN v.value END) as publisher,
                              MAX(CASE WHEN v.property_id = 6 THEN v.value END) as contributor,
                              MAX(CASE WHEN v.property_id = 7 THEN v.value END) as date,
                              MAX(CASE WHEN v.property_id = 8 THEN v.value END) as type,
                              MAX(CASE WHEN v.property_id = 12 THEN v.value END) as language,
                              MAX(CASE WHEN v.property_id = 19 THEN v.value END) as abstract
                          FROM value v
                          WHERE v.resource_id = %s""", (resource_id,))

        result = await cur.fetchone()

        # Récupérer les subjects (multi-valued)
        await cur.execute("""
                          SELECT v.value 
                          FROM value v 
                          WHERE v.resource_id = %s AND v.property_id = 3""", (resource_id,))
        subjects_result = await cur.fetchall()
        subjects = [row[0] for row in subjects_result if row[0]]

        if not result:
            return {
                "title": None, "creator": None, "description": None,
                "publisher": None, "contributor": None, "date": None,
                "type": None, "language": None, "abstract": None,
                "subjects": []
            }

        return {
            "title": result[0],
            "creator": result[1],
            "description": result[2],
            "publisher": result[3],
            "contributor": result[4],
            "date": result[5],
            "type": result[6],
            "language": result[7],
            "abstract": result[8],
            "subjects": subjects
        }


from typing import Dict, List, Optional

async def get_question_by_id(
    conn,
    question_id: int,
    include_answers: bool = True,
) -> Optional[Dict]:
    """
    Récupère une question par son ID, avec éventuellement ses réponses.

    Args:
        conn: Connexion à la base de données asyncpg.
        question_id (int): L'identifiant de la question.
        include_answers (bool): Si True, inclut les réponses associées.

    Returns:
        Optional[Dict]: Dictionnaire représentant la question et ses réponses, ou None si non trouvée.
    """
    async with conn.cursor() as cur:
        # Récupérer la question
        await cur.execute("""
            SELECT q.question_id, q.content, q.status, q.difficulty_level, q.created_by, q.validated_by
            FROM text_questions q
            WHERE q.question_id = %s
        """, (question_id,))
        result = await cur.fetchone()

        if not result:
            return None

        question_id, content, status, difficulty_level, created_by, validated_by = result
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
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT content, is_correct, created_by
                    FROM text_question_answers
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

        return question

async def get_questions_by_ids(
    question_ids: List[str],
    conn,
    include_answers: bool = True,
) -> List[Dict]:
    """
    Récupère les questions correspondant à une liste d'IDs, avec éventuellement leurs réponses.

    Args:
        question_ids: Liste des IDs des questions à récupérer.
        conn: Connexion à la base de données asyncpg.
        include_answers: Si True, inclut les réponses associées.

    Returns:
        Liste de dictionnaires représentant les questions et leurs réponses.
    """
    if not question_ids:
        return []

    placeholders = ", ".join(["%s"] * len(question_ids))
    query = f"""
        SELECT q.question_id, q.content, q.status, q.difficulty_level, q.created_by, q.validated_by
        FROM text_questions q
        WHERE q.question_id IN ({placeholders})
    """

    async with conn.cursor() as cur:
        await cur.execute(query, tuple(question_ids))
        question_rows = await cur.fetchall()

    questions = []
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
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT content, is_correct, created_by
                    FROM text_question_answers
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

async def get_chunk_by_id(chunk_id: int, conn) -> dict:
    """
    Récupère le chunk correspondant à l'id donné.
    """
    async with conn.cursor() as cur:
        await cur.execute("""
                          SELECT c.chunk_id, c.content, c.num_page, c.position_in_page, c.metadata
                          FROM chunks c
                          WHERE c.chunk_id = %s
                          ORDER BY 'num_page' ASC 
                          """, (chunk_id,))
        row = await cur.fetchone()
        return {"chunk_id": row[0],
                 "content": row[1],
                 "num_page": row[2],
                 "position_in_page": row[3],
                 "metadata": row[4]}


async def get_all_text_chunks(conn):
    async with conn.cursor() as cur:
        await cur.execute("""
        SELECT id, content, num_page, position_in_page, character_count, token_count, document_id
        FROM text_chunks
        ORDER BY `document_id` ASC, `num_page` ASC, `position_in_page` ASC;
        """)
        rows = await cur.fetchall()
        return [{
            "id": row[0],
            "content": row[1],
            "num_page": row[2],
            "position_in_page": row[3],
            "character_count": row[4],
            "token_count": row[5],
            "document_id": row[6]} for row in rows]
async def get_chunks_for_document(
    document_id: int,
    conn,
    chunking_strategy_id: int = 1
):
    """Récupère tous les chunks d'un document depuis la base de données.
    Filtre par chunking_strategy_id si fourni.
    Valeurs correspondantes de chunking_strategy_id :
    1 - découpage initial en chunks de 800 tokens et overlap de 100 tokens
    7 - découpage en chunks de 2700 caractères et overlap de 400 caractères
    """

    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT id, content, num_page, position_in_page, character_count, token_count,
            FROM text_chunks
            WHERE document_id = %s
                AND strategy_id = %s
        """, (document_id, chunking_strategy_id))

        rows = await cur.fetchall()
        return [{
            "id": row[0],
            "content": row[1],
            "num_page": row[2],
            "position_in_page": row[3],
            "character_count": row[4],
            "token_count": row[5]} for row in rows]

async def get_chunks_by_question_id(question_id: int, conn):
    """
    Récupère les chunks associés à une question via la table question_chunks.
    """
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT qc.chunk_id, c.content, c.num_page, c.position_in_page
            FROM text_question_chunks qc
            JOIN text_chunks c ON c.chunk_id = qc.chunk_id
            WHERE qc.question_id = %s""", (question_id,))
        rows = await cur.fetchall()
        return [{"chunk_id": row[0],
                 "content": row[1],
                 "num_page": row[2],
                 "position_in_page": row[3],
                 "question_id": question_id} for row in rows]


async def get_chunks_by_question_ids(
    question_ids: List[int],
    conn,
) -> List[List[Dict]]:
    """
    Récupère les chunks associés à une liste de questions.
    Retourne une liste de listes, où chaque sous-liste contient les chunks d'une question.

    Args:
        question_ids: Liste des IDs des questions.
        conn: Connexion à la base de données asyncpg.

    Returns:
        Liste de listes de dictionnaires, chaque sous-liste représentant les chunks d'une question.
    """
    if not question_ids:
        return []

    placeholders = ", ".join(["%s"] * len(question_ids))
    query = f"""
        SELECT qc.question_id, qc.chunk_id, c.content, c.num_page, c.position_in_page
        FROM text_question_chunks qc
        JOIN text_chunks c ON c.id = qc.chunk_id
        WHERE qc.question_id IN ({placeholders})
        ORDER BY qc.question_id
    """

    async with conn.cursor() as cur:
        await cur.execute(query, tuple(question_ids))
        rows = await cur.fetchall()

    # Regrouper les chunks par question_id
    chunks_by_question = {}
    for row in rows:
        question_id, chunk_id, content, num_page, position_in_page = row
        if question_id not in chunks_by_question:
            chunks_by_question[question_id] = []
        chunks_by_question[question_id].append({
            "chunk_id": chunk_id,
            "content": content,
            "num_page": num_page,
            "position_in_page": position_in_page,
            "question_id": question_id
        })

    # Retourner les chunks dans l'ordre des question_ids demandées
    return [chunks_by_question.get(qid, []) for qid in question_ids]


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
            INSERT INTO text_questions (content, status, difficulty_level, created_by, validated_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (question, "generated", difficulty_level, None, None))
        question_id = cur.lastrowid

        # 2. Lier la question au chunk
        await cur.execute("""
            INSERT INTO text_question_chunks (question_id, chunk_id)
            VALUES (%s, %s)
        """, (question_id, chunk_id))

        # 3. Insérer la réponse
        await cur.execute("""
            INSERT INTO text_question_answers (question_id, content, is_correct, created_by)
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
    cur = await conn.cursor()
    
    # 1. Trouver l'ID interne du document à partir du source_id
    await cur.execute("""
        SELECT id FROM text_documents WHERE source_id = %s
    """, (document_id,))
    doc_result = await cur.fetchone()
    
    if not doc_result:
        return []
    
    internal_document_id = doc_result[0]
    
    # 2. Récupérer tous les chunk_ids pour ce document
    await cur.execute("""
        SELECT id FROM text_chunks WHERE document_id = %s
    """, (internal_document_id,))
    chunk_rows = await cur.fetchall()
    
    if not chunk_rows:
        return []
    
    chunk_ids = [row[0] for row in chunk_rows]
    
    # 3. Récupérer les questions associées à ces chunks
    params = chunk_ids
    placeholders = ",".join(["%s"] * len(chunk_ids))
    query = f"""
        SELECT DISTINCT q.question_id, q.content, q.status, q.difficulty_level, q.created_by, q.validated_by, qc.chunk_id, tc.num_page
        FROM text_question_chunks qc
        JOIN text_questions q ON qc.question_id = q.question_id
        JOIN text_chunks tc ON qc.chunk_id = tc.id
        WHERE qc.chunk_id IN ({placeholders})
    """
    
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

    # 4. Pour chaque question, récupérer les réponses si nécessaire
    for row in question_rows:
        question_id, content, status, difficulty_level, created_by, validated_by, chunk_id, num_page = row
        question = {
            "question_id": question_id,
            "content": content,
            "status": status,
            "difficulty_level": difficulty_level,
            "created_by": created_by,
            "validated_by": validated_by,
            "chunk_id": chunk_id,
            "num_page": num_page,
            "answers": []
        }

        if include_answers:
            # Récupérer les réponses associées
            await cur.execute("""
                SELECT content, is_correct, created_by
                FROM text_question_answers
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

async def get_all_documents(conn) -> List[Dict]:
    """
    Récupère les informations de base des documents :
    - document_id, file_name (construit depuis storage_id + extension),
    - titre (property_id=1), créateur (property_id=2),
    - created_at, updated_at.

    Args:
        conn: Connexion à la base de données.

    Returns:
        List[Dict]: Liste de tous les documents avec leurs métadonnées.
    """
    print("retrieving documents...")
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT
                td.source_id as document_id,
                CONCAT(m.storage_id, '.', m.extension) as file_name,
                v_title.value as title,
                v_creator.value as creator,
                td.created_at,
                td.updated_at
            FROM text_documents td
            LEFT JOIN media m ON td.source_id = m.item_id AND m.extension = "pdf"
            LEFT JOIN value v_title ON td.source_id = v_title.resource_id AND v_title.property_id = 1
            LEFT JOIN value v_creator ON td.source_id = v_creator.resource_id AND v_creator.property_id = 2
            ORDER BY td.created_at DESC
        """)

        results = await cur.fetchall()

        documents = []
        for result in results:
            documents.append({
                "document_id": result[0],
                "file_name": result[1],
                "title": result[2],
                "creator": result[3],
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
                await cur.execute("SELECT COUNT(*) FROM resource WHERE extracted_text IS NOT NULL AND extracted_text != ''")
                count = (await cur.fetchone())[0] or 0
            except Exception:
                # Si la colonne n'existe pas, retourner 0
                await cur.execute("SELECT COUNT(*) FROM resource")
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


async def get_pdf_media_items() -> List[Dict[str, Any]]:
    """
    Récupère tous les médias de type PDF depuis la table media.
    
    Returns:
        Liste de dicts avec item_id, storage_id, extension
    """
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT item_id, storage_id, extension 
                FROM media 
                WHERE LOWER(extension) = 'pdf'
            """)
            rows = await cur.fetchall()
            return [
                {"item_id": row[0], "storage_id": row[1], "extension": row[2]}
                for row in rows
            ]
    finally:
        await conn.close()


async def get_pdf_media_item(item_id: int) -> Optional[Dict[str, Any]]:
    """
    Récupère un seul média PDF depuis la table media par son item_id.
    
    Args:
        item_id: L'identifiant de l'item à récupérer
        
    Returns:
        Dict avec item_id, storage_id, extension ou None si non trouvé
    """
    conn = await get_db_connection()
    try:
        async with conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT item_id, storage_id, extension 
                    FROM media 
                    WHERE item_id = %s AND LOWER(extension) = 'pdf'
                """, (item_id,))
                row = await cur.fetchone()
                if row:
                    return {"item_id": row[0], "storage_id": row[1], "extension": row[2]}
                return None
    except Exception as e:
        print(e)
        return None






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
    
    Note: Non implémentée pour le moment
    """
    raise NotImplementedError("get_admin_stats n'est pas encore implémentée")


# ============================================================================
# FONCTIONS POUR L'INDEXATION DES PDFs DEPUIS M3C
# ============================================================================

# Configuration M3C
M3C_BASE_URL = "https://m3c.universita.corsica/files/original/"


async def get_pdf_name_from_resource_id(conn, resource_id: int) -> str:
    """
    Récupère le nom du PDF avec extension du resource_id fourni.
    """

    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT CONCAT(media.storage_id, ".", extension) AS filename
            FROM media
            WHERE item_id=%s and LOWER(extension) = 'pdf'
        """,(resource_id,))

        filename = (await cur.fetchone())[0]
        return filename

async def get_pdf_url_for_resource(resource_id: int) -> Optional[str]:
    """
    Récupère l'URL du PDF pour un resource_id donné.
    Hypothèse: resource_id correspond à item_id dans la table media.
    
    Args:
        resource_id: L'identifiant du resource (utilisé comme item_id)
        
    Returns:
        URL complète du PDF ou None si non trouvé
    """
    media = await get_pdf_media_item(resource_id)
    if media:
        return f"{M3C_BASE_URL}{media['storage_id']}.{media['extension']}"
    return None


# ============================================================================
# FONCTIONS DE GESTION DES JOBS D'INDEXATION
# ============================================================================

async def create_indexing_job(
    conn,
    job_id: str,
    job_type: str,
    total_items: int,
    parameters: dict = None
) -> bool:
    """Crée un nouveau job d'indexation dans la base de données."""
    try:
        async with conn.cursor() as cur:
            parameters_json = json.dumps(parameters) if parameters else json.dumps({})
            await cur.execute("""
                INSERT INTO indexing_jobs 
                (job_id, job_type, status, total_items, processed_items, progress, parameters)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                job_id, job_type, "pending", total_items, 0,
                json.dumps({}), parameters_json
            ))
            return cur.rowcount > 0
    except Exception as e:
        print(f"Erreur création job {job_id}: {e}")
        return False


async def get_indexing_job(conn, job_id: str) -> Optional[dict]:
    """Récupère les informations d'un job d'indexation."""
    try:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT job_id, job_type, status, created_at, updated_at,
                       total_items, processed_items, progress, parameters, error_message
                FROM indexing_jobs
                WHERE job_id = %s
            """, (job_id,))
            row = await cur.fetchone()
            if row:
                return {
                    "job_id": row[0], "job_type": row[1], "status": row[2],
                    "created_at": str(row[3]), "updated_at": str(row[4]),
                    "total_items": row[5], "processed_items": row[6],
                    "progress": json.loads(row[7]) if row[7] else {},
                    "parameters": json.loads(row[8]) if row[8] else {},
                    "error_message": row[9]
                }
            return None
    except Exception as e:
        print(f"Erreur récupération job {job_id}: {e}")
        return None


async def update_indexing_job(
    conn, job_id: str, status: str,
    progress: dict = None, processed_items: int = None,
    error_message: str = None
) -> bool:
    """Met à jour l'état d'un job d'indexation."""
    try:
        async with conn.cursor() as cur:
            updates = ["status = %s"]
            params = [status]
            
            if progress is not None:
                updates.append("progress = %s")
                params.append(json.dumps(progress))
            if processed_items is not None:
                updates.append("processed_items = %s")
                params.append(processed_items)
            if error_message is not None:
                updates.append("error_message = %s")
                params.append(error_message)
            updates.append("updated_at = CURRENT_TIMESTAMP")
            
            query = f"UPDATE indexing_jobs SET {', '.join(updates)} WHERE job_id = %s"
            params.append(job_id)
            await cur.execute(query, tuple(params))
            return cur.rowcount > 0
    except Exception as e:
        print(f"Erreur mise à jour job {job_id}: {e}")
        return False


async def get_latest_job_by_type(conn, job_type: str, exclude_status: list = None) -> Optional[dict]:
    """Récupère le job le plus récent d'un type donné."""
    try:
        async with conn.cursor() as cur:
            query = """
                SELECT job_id, job_type, status, created_at, updated_at,
                       total_items, processed_items, progress, parameters, error_message
                FROM indexing_jobs
                WHERE job_type = %s
            """
            params = [job_type]
            if exclude_status:
                placeholders = ", ".join(["%s"] * len(exclude_status))
                query += f" AND status NOT IN ({placeholders})"
                params.extend(exclude_status)
            query += " ORDER BY created_at DESC LIMIT 1"
            await cur.execute(query, tuple(params))
            row = await cur.fetchone()
            if row:
                return {
                    "job_id": row[0], "job_type": row[1], "status": row[2],
                    "created_at": str(row[3]), "updated_at": str(row[4]),
                    "total_items": row[5], "processed_items": row[6],
                    "progress": json.loads(row[7]) if row[7] else {},
                    "parameters": json.loads(row[8]) if row[8] else {},
                    "error_message": row[9]
                }
            return None
    except Exception as e:
        print(f"Erreur récupération dernier job type {job_type}: {e}")
        return None


async def get_all_indexing_jobs(conn, status_filter: str = None) -> list:
    """Récupère tous les jobs d'indexation."""
    try:
        async with conn.cursor() as cur:
            query = """
                SELECT job_id, job_type, status, created_at, updated_at,
                       total_items, processed_items, progress, parameters, error_message
                FROM indexing_jobs
            """
            params = []
            if status_filter:
                query += " WHERE status = %s"
                params.append(status_filter)
            query += " ORDER BY created_at DESC"
            await cur.execute(query, tuple(params))
            rows = await cur.fetchall()
            return [{
                "job_id": row[0], "job_type": row[1], "status": row[2],
                "created_at": str(row[3]), "updated_at": str(row[4]),
                "total_items": row[5], "processed_items": row[6],
                "progress": json.loads(row[7]) if row[7] else {},
                "parameters": json.loads(row[8]) if row[8] else {},
                "error_message": row[9]
            } for row in rows]
    except Exception as e:
        print(f"Erreur récupération tous les jobs: {e}")
        return []


# Note: La table indexing_jobs doit être créée dans MySQL
# SQL: CREATE TABLE IF NOT EXISTS indexing_jobs (...)

#         # Build the query to fetch chunks with their embeddings
#         query = f"""
#             SELECT