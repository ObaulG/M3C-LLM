"""Fonctions d'accès aux tables de retours utilisateurs sur les réponses
du chatbot (schéma chatbot_feedback.sql).

Tables :
    chatbot_messages         : une ligne par réponse LLM générée.
    chatbot_message_chunks   : chunks utilisés quand le RAG est actif.
    chatbot_feedbacks        : un retour utilisateur (échelles 1-5 + commentaire),
                               unique par message_id.

Ce module importe get_db_connection depuis database.database pour réutiliser
la même configuration MySQL que le reste de l'application.
"""
from typing import Optional, List, Dict

import aiomysql

from database.database import get_db_connection


async def insert_chatbot_message(
    message_id: str,
    user_id: Optional[str],
    session_id: Optional[str],
    question: str,
    answer: str,
    model: str,
    use_rag: bool,
    use_reranking: bool,
    k: Optional[int],
    total_time: Optional[float],
    consumed_energy_Wh: Optional[float],
    token_usage: Optional[Dict],
) -> bool:
    """Insère une ligne dans chatbot_messages (une réponse LLM générée).

    Args:
        message_id: UUID généré côté serveur, clé primaire.
        user_id: users.id (connecté) ou anonymous_id, ou None.
        session_id: session RAG si applicable.
        question: Requête utilisateur en amont.
        answer: Réponse générée par le LLM.
        model: Nom du modèle utilisé.
        use_rag, use_reranking, k: Paramètres de la requête.
        total_time: Temps total en secondes.
        consumed_energy_Wh: Énergie consommée (modèles locaux), ou None.
        token_usage: Dict {input_tokens, output_tokens, total_tokens}.

    Returns:
        True si l'insertion a réussi, False sinon.
    """
    import json
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO chatbot_messages
                    (message_id, user_id, session_id, question, answer, model,
                     use_rag, use_reranking, k, total_time, consumed_energy_Wh,
                     token_usage, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    message_id,
                    user_id,
                    session_id,
                    question,
                    answer,
                    model,
                    bool(use_rag),
                    bool(use_reranking),
                    k,
                    total_time,
                    consumed_energy_Wh,
                    json.dumps(token_usage) if token_usage else None,
                ),
            )
        await conn.commit()
        return True
    except Exception as e:
        print(f"Erreur lors de l'insertion du chatbot_message {message_id}: {e}")
        await conn.rollback()
        return False
    finally:
        conn.close()


async def insert_chatbot_message_chunks(
    message_id: str,
    sources: List[Dict],
) -> bool:
    """Insère les chunks associés à une réponse RAG dans chatbot_message_chunks.

    Args:
        message_id: Identifiant du message parent.
        sources: Liste de dicts {chunk_id, score_cossim, score_bm25} extraits
                 des RAGSource (métadonnées).

    Returns:
        True si l'insertion a réussi, False sinon.
    """
    if not sources:
        return True
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            for position, source in enumerate(sources):
                chunk_id = source.get("chunk_id")
                if not chunk_id:
                    continue
                await cur.execute(
                    """
                    INSERT IGNORE INTO chatbot_message_chunks
                        (message_id, chunk_id, position, score_cossim, score_bm25)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        message_id,
                        str(chunk_id),
                        position,
                        source.get("score_cossim"),
                        source.get("score_bm25"),
                    ),
                )
        await conn.commit()
        return True
    except Exception as e:
        print(f"Erreur lors de l'insertion des chunks pour le message {message_id}: {e}")
        await conn.rollback()
        return False
    finally:
        conn.close()


async def insert_chatbot_feedback(
    message_id: str,
    user_id: Optional[str],
    rating_response: Optional[int],
    rating_relevance: Optional[int],
    rating_formulation: Optional[int],
    comment: Optional[str],
) -> Optional[int]:
    """Insère un retour utilisateur sur un message dans chatbot_feedbacks.

    La contrainte UNIQUE(message_id) garantit qu'un seul feedback est possible
    par message : en cas de double soumission, aiomysql.IntegrityError est levée
    et propagée à l'appelant pour qu'il réponde 409 Conflict.

    Args:
        message_id: Identifiant du message commenté.
        user_id: users.id ou anonymous_id.
        rating_response: Note 1-5 sur la pertinence générale, ou None.
        rating_relevance: Note 1-5 sur la pertinence des documents, ou None.
        rating_formulation: Note 1-5 sur la formulation, ou None.
        comment: Commentaire libre, ou None.

    Returns:
        feedback_id (int) si l'insertion a réussi.

    Raises:
        aiomysql.IntegrityError: si un feedback existe déjà pour ce message_id.
    """
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO chatbot_feedbacks
                    (message_id, user_id, rating_response, rating_relevance,
                     rating_formulation, comment, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    message_id,
                    user_id,
                    rating_response,
                    rating_relevance,
                    rating_formulation,
                    comment,
                ),
            )
            feedback_id = cur.lastrowid
        await conn.commit()
        return feedback_id
    except aiomysql.IntegrityError:
        await conn.rollback()
        raise
    except Exception:
        await conn.rollback()
        raise
    finally:
        conn.close()


async def get_chatbot_feedback(message_id: str) -> Optional[Dict]:
    """Récupère le feedback associé à un message, s'il existe.

    Args:
        message_id: Identifiant du message.

    Returns:
        Dict {feedback_id, message_id, user_id, rating_response,
        rating_relevance, rating_formulation, comment, created_at} ou None.
    """
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT feedback_id, message_id, user_id, rating_response,
                       rating_relevance, rating_formulation, comment, created_at
                FROM chatbot_feedbacks
                WHERE message_id = %s
                """,
                (message_id,),
            )
            row = await cur.fetchone()
        if not row:
            return None
        return {
            "feedback_id": row[0],
            "message_id": row[1],
            "user_id": row[2],
            "rating_response": row[3],
            "rating_relevance": row[4],
            "rating_formulation": row[5],
            "comment": row[6],
            "created_at": str(row[7]) if row[7] else None,
        }
    finally:
        conn.close()


async def chatbot_message_exists(message_id: str) -> bool:
    """Vérifie qu'un message_id existe dans chatbot_messages.

    Args:
        message_id: Identifiant du message.

    Returns:
        True si le message existe, False sinon.
    """
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM chatbot_messages WHERE message_id = %s",
                (message_id,),
            )
            row = await cur.fetchone()
        return row is not None
    finally:
        conn.close()
