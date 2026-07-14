"""
Services pour la génération de questions sur les documents validés.
"""
import json
import uuid
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

import database
from database.database import (
    VALID_TEXT_RESOURCE_ID,
    get_db_connection,
    save_question_to_db,
    get_pdf_url_for_resource,
    get_chunk_embeddings_with_metadata_qdrant,
)
from agents.qa_agent import get_qa_agent, QuestionRequestInput, QuestionAnswerList
from agents.mistral_client import check_api_limits
from embedders import get_embedder_instance
from app.jobs.manager import (
    create_job as _create_job,
    get_job as _get_job,
    get_jobs_by_type as _get_jobs_by_type,
    get_all_jobs as _get_all_jobs,
    get_latest_job as _get_latest_job,
    update_job as _update_job,
)


# ============================================================================
# GESTION DES JOBS - Utilise le module central app.jobs
# ============================================================================


def create_question_generation_job(
    num_questions_per_doc: int = 3,
    model_name: str = "mistral-small",
    document_id: Optional[int] = None,
    num_answers_per_question: int = 10
) -> str:
    """
    Crée un nouveau job de génération de questions.
    
    Args:
        num_questions_per_doc: Nombre de questions à générer par chunk
        model_name: Nom du modèle LLM à utiliser
        document_id: ID du document spécifique à traiter (optionnel). Si None, traite tous les documents validés.
        num_answers_per_question: Nombre de réponses à générer par question (défaut: 10)
        
    Returns:
        job_id: L'ID unique du job créé
    """
    # Créer le job via le module central
    job_id = _create_job(
        job_type="qa-generation",
        document_categories=["validated-documents"],
        parameters={
            "num_questions_per_doc": num_questions_per_doc,
            "model_name": model_name,
            "document_id": document_id,
            "num_answers_per_question": num_answers_per_question
        },
        total_documents=0  # sera mis à jour lors du traitement avec le nombre de chunks
    )
    
    # Initialiser avec une progression vide (sera remplie dynamiquement)
    _update_job(job_id, progress={})
    return job_id


def get_question_generation_job(job_id: str) -> Optional[dict]:
    """
    Récupère un job par son ID.
    
    Args:
        job_id: L'ID du job à récupérer
        
    Returns:
        Le job sous forme de dict, ou None s'il n'existe pas
    """
    return _get_job(job_id)


def get_all_question_generation_jobs() -> Dict[str, dict]:
    """
    Récupère tous les jobs.
    
    Returns:
        Dictionnaire de tous les jobs (job_id -> job)
    """
    jobs = _get_jobs_by_type("question_generation")
    return {job["job_id"]: job for job in jobs}


def get_latest_question_generation_job(exclude_status: list = None) -> Optional[dict]:
    """
    Récupère le job le plus récent.
    
    Args:
        exclude_status: Liste des statuts à exclure
        
    Returns:
        Le job le plus récent sous forme de dict, ou None si aucun trouvé
    """
    return _get_latest_job("question_generation", exclude_status)


async def get_all_chunks_from_qdrant(embedder_model: str = "mistral_embed") -> List[Dict]:
    """
    Récupère tous les chunks de tous les documents validés depuis Qdrant.
    
    Returns:
        Liste de dictionnaires représentant les chunks
    """
    embedder = get_embedder_instance(name="mistral-embed")
    collection_name = f"LD-{embedder.name}-{embedder.dimension}"
    
    chunks = await get_chunk_embeddings_with_metadata_qdrant(
        collection_name=collection_name,
        limit=None
    )
    
    valid_doc_ids = set(str(d) for d in VALID_TEXT_RESOURCE_ID)
    all_chunks = []
    for chunk in chunks:
        if chunk.get("document_id") in valid_doc_ids:
            all_chunks.append(chunk)
    
    return all_chunks


def update_question_generation_job(
    job_id: str,
    status: str,
    progress: dict = None,
    processed_documents: int = None,
    errors: list = None,
    error_message: str = None
) -> bool:
    """
    Met à jour un job existant.
    
    Args:
        job_id: L'ID du job à mettre à jour
        status: Nouveau statut (pending, running, completed, failed, cancelled)
        progress: Progression détaillée (optionnel)
        processed_documents: Nombre de documents traités (optionnel)
        errors: Liste d'erreurs (optionnel)
        error_message: Message d'erreur global (optionnel)
        
    Returns:
        True si la mise à jour a réussi, False sinon
    """
    update_kwargs = {
        "status": status,
        "progress": progress,
        "processed_documents": processed_documents,
        "errors": errors,
        "error_message": error_message
    }
    return _update_job(job_id, **update_kwargs)


async def get_resource_extracted_text(resource_id: int) -> Optional[str]:
    """
    Récupère le contenu extrait (extracted_text) pour un resource_id donné.
    
    Args:
        resource_id: L'ID du resource
        
    Returns:
        Le texte extrait ou None si non trouvé
    """
    conn = None
    try:
        conn = await get_db_connection()
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT extracted_text 
                FROM resource 
                WHERE item_id = %s
                LIMIT 1
            """, (resource_id,))
            result = await cur.fetchone()
            if result and result[0]:
                return result[0]
            
            # Essayer aussi avec resource_id directement
            await cur.execute("""
                SELECT extracted_text 
                FROM resource 
                WHERE resource_id = %s
                LIMIT 1
            """, (resource_id,))
            result = await cur.fetchone()
            if result and result[0]:
                return result[0]
            
            return None
    except Exception as e:
        print(f"Erreur lors de la récupération de extracted_text pour {resource_id}: {e}")
        return None
    finally:
        if conn:
            await conn.close()


async def get_chunk_id_for_resource(resource_id: int) -> Optional[str]:
    """
    Récupère un chunk_id pour un document resource_id.
    Utilise le premier chunk trouvé pour ce document.
    
    Args:
        resource_id: L'ID du resource
        
    Returns:
        Un chunk_id ou None si non trouvé
    """
    conn = None
    try:
        conn = await get_db_connection()
        async with conn.cursor() as cur:
            # Chercher dans chunks table
            await cur.execute("""
                SELECT id 
                FROM chunks 
                WHERE document_id = %s
                LIMIT 1
            """, (str(resource_id),))
            result = await cur.fetchone()
            if result:
                return str(result[0])
            
            # Chercher dans text_chunks table
            await cur.execute("""
                SELECT id 
                FROM text_chunks 
                WHERE document_id = %s
                LIMIT 1
            """, (str(resource_id),))
            result = await cur.fetchone()
            if result:
                return str(result[0])
            
            return None
    except Exception as e:
        print(f"Erreur lors de la récupération de chunk_id pour {resource_id}: {e}")
        return None
    finally:
        if conn:
            await conn.close()


async def generate_questions_for_chunk(
    chunk_content: str,
    chunk_id: str,
    document_id: str,
    num_questions: int,
    model_name: str,
    num_answers_per_question: int = 10,
    max_retries: int = 5
) -> Tuple[QuestionAnswerList, Optional[str]]:
    """
    Génère des questions pour un chunk spécifique avec retry.
    
    Args:
        chunk_content: Contenu du chunk
        chunk_id: ID du chunk
        document_id: ID du document
        num_questions: Nombre de questions à générer
        model_name: Nom du modèle LLM
        num_answers_per_question: Nombre de réponses à générer par question (défaut: 10)
        max_retries: Nombre maximal de tentatives
        
    Returns:
        Tuple de (QuestionAnswerList, error)
    """
    estimated_tokens = len(chunk_content.split()) + num_questions * 50
    for attempt in range(max_retries):
        try:
            limits = check_api_limits(model_name, estimated_tokens)
            if not limits.get("can_make_call", True):
                wait_time = 60
                print(f"Limite API atteinte, attente de {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
        except Exception as e:
            print(f"Erreur vérification limites: {e}")
        try:
            provider, model = tuple(model_name.split("/"))
            qa_agent = get_qa_agent(model=model, provider=provider, async_mode=False)
            input_schema = QuestionRequestInput(
                message=f"",
                document=chunk_content,
                num_questions=num_questions,
                num_answers_per_question=num_answers_per_question,
            )
            print("qa_agent: ", qa_agent)
            response = qa_agent.run(input_schema)
            questions_generated = len(response.questions_answers) if response else 0
            print(questions_generated, "questions/réponses générées")

            return response, None
        except Exception as e:
            error_msg = str(e)
            if "rate limit" in error_msg.lower() or "429" in error_msg:
                wait_time = min(2 ** attempt, 60)
                print(f"Rate limit, attente {wait_time}s (tentative {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
                continue
            else:
                return None, f"Erreur génération: {error_msg}"
    
    return 0, 0, f"Échec après {max_retries} tentatives"


async def process_question_generation_job(job_id: str):
    """
    Traite un job de génération de questions en arrière-plan.
    Génère des questions pour chaque chunk de chaque document validé, ou pour un document spécifique.
    
    Args:
        job_id: L'ID du job à traiter
    """
    job = get_question_generation_job(job_id)
    if not job:
        print(f"Job {job_id} introuvable")
        return
    
    update_question_generation_job(
        job_id=job_id,
        status="running",
        processed_documents=0
    )
    
    parameters = job.get("parameters", {})
    num_questions = parameters.get("num_questions_per_doc", 3)
    # note: le provider est indiqué comme dans la syntaxe d'instructor
    model_name = parameters.get("model_name", "mistral/mistral-small")
    document_id = parameters.get("document_id")  # ID du document spécifique (optionnel)
    num_answers = parameters.get("num_answers_per_question", 10)  # Nombre de réponses par question
    
    errors = []
    progress = job.get("progress", {})
    processed_chunks = 0


    # Récupérer les id des documents validés
    # (inutile car on peut juste travailler sur les chunks)
    """
    async with await get_db_connection() as conn:
        text_documents = database.get_all_documents(conn)
        if not text_documents:
            update_question_generation_job(
                job_id=job_id,
                status="failed",
                progress=progress,
                processed_documents=processed_chunks,
                errors=errors
            )
    """

    # Récupérer tous les chunks des documents validés
    async with await get_db_connection() as conn:
        all_chunks = await database.get_all_text_chunks(conn, document_id)
        total_chunks = len(all_chunks)
    
    print(f"{total_chunks} chunks à traiter..." + (f" (document {document_id})" if document_id else ""))
    
    update_question_generation_job(
        job_id=job_id,
        status="running",
        processed_documents=0
    )
    
    # Traiter chaque chunk
    for chunk in all_chunks:
        chunk_id = str(chunk.get("id", "unknown"))
        document_id = str(chunk.get("document_id", "unknown"))
        chunk_content = chunk.get("content", "")
        
        # Vérifier si le chunk a déjà au moins 3 questions
        async with await get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT COUNT(*)
                    FROM text_question_chunks qc
                    JOIN text_questions q ON qc.question_id = q.question_id
                    WHERE qc.chunk_id = %s
                """, (chunk_id,))
                result = await cur.fetchone()
                existing_questions_count = result[0] if result else 0
                
            if existing_questions_count >= 3:
                print(f"Chunk {chunk_id} a déjà {existing_questions_count} questions, on saute la génération")
                if chunk_id in progress:
                    progress[chunk_id] = {
                        "chunk_id": chunk_id,
                        "document_id": document_id,
                        "questions_generated": 0,
                        "error": "Déjà 3+ questions existantes",
                        "status": "skipped"
                    }
                processed_chunks += 1
                update_question_generation_job(
                    job_id=job_id,
                    status="running",
                    progress=progress,
                    processed_documents=processed_chunks,
                    errors=errors
                )
                continue
        
        try:
            print(f"Traitement chunk {chunk_id} (doc: {document_id})...")

            # génération des QA
            qa_list, error = await generate_questions_for_chunk(
                chunk_content=chunk_content,
                chunk_id=chunk_id,
                document_id=document_id,
                num_questions=num_questions,
                model_name=model_name,
                num_answers_per_question=num_answers
            )

            # insertion dans MySQL
            async with await get_db_connection() as conn:
                for qa in qa_list.questions_answers:
                    await save_question_to_db(
                        question=qa.question_text,
                        answers=qa.answers_text,
                        chunk_id=chunk_id,
                        conn=conn,
                        difficulty_level=3,
                        model=model_name
                    )

            progress[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "questions_generated": len(qa_list.questions_answers),
                "error": error,
                "status": "completed" if not error else "failed"
            }
            
            if error:
                errors.append(f"chunk {chunk_id} (doc: {document_id}): {error}")
            
            processed_chunks += 1
            update_question_generation_job(
                job_id=job_id,
                status="running",
                progress=progress,
                processed_documents=processed_chunks,
                errors=errors
            )
            
        except Exception as e:
            errors.append(f"chunk {chunk_id} (doc: {document_id}): {str(e)}")
            progress[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "questions_generated": 0,
                "questions_saved": 0,
                "error": str(e),
                "status": "failed"
            }
            processed_chunks += 1
            update_question_generation_job(
                job_id=job_id,
                status="running",
                progress=progress,
                processed_documents=processed_chunks,
                errors=errors
            )
    
    # Job terminé
    final_status = "completed" if not errors else "completed_with_errors"
    update_question_generation_job(
        job_id=job_id,
        status=final_status,
        progress=progress,
        processed_documents=processed_chunks,
        errors=errors
    )
    
    print(f"Job {job_id} terminé: {final_status} ({processed_chunks}/{total_chunks})")


# ============================================================================
# RECOMMANDATION DE QUESTIONS - NOUVELLE FONCTIONNALITÉ
# ============================================================================


async def recommend_questions_for_document(
    user_prompt: str,
    document_id: str,
    k: int = 5,
    rag_pipeline=None
) -> List[Dict]:
    """
    Recommande les questions les plus pertinentes d'un document par rapport à un prompt utilisateur.
    
    Utilise un agent spécialisé qui récupère toutes les questions du document et les classe
    par pertinence en utilisant les embeddings du RAG pipeline.
    
    Args:
        user_prompt: Le texte de la requête utilisateur
        document_id: L'ID du document (document_id, pas resource_id)
        k: Nombre de questions à retourner (défaut: 5)
        rag_pipeline: Instance de RAGPipeline à utiliser. Si None, en crée une nouvelle.
                     Il est fortement recommandé de passer l'instance existante depuis api_server
                     pour éviter de réinitialiser les modèles LLM et embedders.
    
    Returns:
        Liste de dictionnaires représentant les questions recommandées, avec :
        - question_id: ID de la question
        - question_text: Texte de la question
        - answers: Liste des réponses
        - relevance_score: Score de pertinence (0-1)
        - chunk_id: ID du chunk associé
        - num_page: Numéro de page
        
    Raises:
        ValueError: Si le document_id est invalide
    """
    from ..agents.question_recommender_agent import (
        QuestionRecommenderAgent,
        QuestionRecommendationInput
    )
    from ..rag_pipeline import RAGPipeline
    
    # Si aucun pipeline RAG n'est fourni, en créer un nouveau
    # WARNING: Cela initialise tous les modèles LLM, ce qui est coûteux
    if rag_pipeline is None:
        print("WARNING: Creating new RAGPipeline instance. Consider passing an existing one.")
        rag_pipeline = RAGPipeline(load_local=False, embedder_name="mistral-embed")
    
    # Créer et exécuter l'agent
    recommender_agent = QuestionRecommenderAgent(rag_pipeline=rag_pipeline)
    
    input_data = QuestionRecommendationInput(
        user_prompt=user_prompt,
        document_id=document_id,
        k=k
    )
    
    result = await recommender_agent.run(input_data)
    
    # Convertir en liste de dict pour la compatibilité
    return result.to_dict_list()
