"""
Services pour la génération de questions sur les documents validés.
"""
import json
import uuid
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from instructor import Mode

import database
from database.database import (
    VALID_TEXT_RESOURCE_ID,
    get_db_connection,
    save_question_to_db,
    get_pdf_url_for_resource,
    get_chunk_embeddings_with_metadata_qdrant,
)
import agents.qa_agent as qa_agent
import agents.qa_single_agent as qa_single_agent
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
    model_name: str = "mistral-small-2603",
    document_id: Optional[int] = None,
    num_answers_per_question: int = 1,
    chunk_id: Optional[int] = None,
    user_prompt: Optional[str] = None,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    use_batch: bool = False,
    generate_facts: bool = False
) -> str:
    """
    Crée un nouveau job de génération de questions.
    
    Args:
        num_questions_per_doc: Nombre de questions à générer par chunk
        model_name: Nom du modèle LLM à utiliser
        document_id: ID du document spécifique à traiter (optionnel). Si None, traite tous les documents validés.
        num_answers_per_question: Nombre de réponses à générer par question (défaut: 10)
        chunk_id: ID du chunk spécifique à traiter (optionnel). Prioritaire sur document_id.
        user_prompt: Instructions personnalisées de l'utilisateur (optionnel), transmises à l'agent QA
        start_page: Première page (num_page) à traiter (optionnel), pour exclure le sommaire
        end_page: Dernière page (num_page) à traiter (optionnel), pour exclure la fin du livre
        use_batch: Utiliser l'API Batch de Mistral (environ 50% moins cher) pour la génération en masse
        generate_facts: Extraire les faits des réponses de référence générées
        
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
            "num_answers_per_question": num_answers_per_question,
            "chunk_id": chunk_id,
            "user_prompt": user_prompt,
            "start_page": start_page,
            "end_page": end_page,
            "use_batch": use_batch,
            "generate_facts": generate_facts
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
    jobs = _get_jobs_by_type("qa-generation") + _get_jobs_by_type("question_generation")
    return {job["job_id"]: job for job in jobs}


def get_latest_question_generation_job(exclude_status: list = None) -> Optional[dict]:
    """
    Récupère le job le plus récent.
    
    Args:
        exclude_status: Liste des statuts à exclure
        
    Returns:
        Le job le plus récent sous forme de dict, ou None si aucun trouvé
    """
    return _get_latest_job("qa-generation", exclude_status)


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
    try:
        async with await get_db_connection() as conn:
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


async def get_chunk_id_for_resource(resource_id: int) -> Optional[str]:
    """
    Récupère un chunk_id pour un document resource_id.
    Utilise le premier chunk trouvé pour ce document.
    
    Args:
        resource_id: L'ID du resource
        
    Returns:
        Un chunk_id ou None si non trouvé
    """
    try:
        async with await get_db_connection() as conn:
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


async def generate_questions_single_answer_for_chunk(
    chunk_content: str,
    chunk_id: str,
    document_id: str,
    num_questions: int,
    model_name: str,
    max_retries: int = 2,
    user_prompt: Optional[str] = None,
    usage_sink: Optional[list] = None
) -> Tuple[qa_single_agent.QuestionAnswerList, Optional[str]]:
    import instructor
    """
    Génère des questions avec une réponse unique pour un chunk spécifique avec retry.
    
    Args:
        chunk_content: Contenu du chunk
        chunk_id: ID du chunk
        document_id: ID du document
        num_questions: Nombre de questions à générer
        model_name: Nom du modèle LLM
        max_retries: Nombre maximal de tentatives
    user_prompt: Instructions personnalisées de l'utilisateur (optionnel), intégrées au message de l'agent
        
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
            agent = qa_single_agent.get_qa_agent(model=model,
                                    provider=provider,
                                    async_mode=False,
                                    instructor_mode=instructor.Mode.JSON)

            input_schema = qa_single_agent.QuestionRequestInput(
                message=f"",
                document=chunk_content,
                num_questions=num_questions
            )
            print("Essai de génération :")
            from agents.token_monitor import monitor_agent_call
            response, usage_info = monitor_agent_call(agent, input_schema)
            if usage_sink is not None:
                usage_sink.append(usage_info.to_metadata())
            questions_generated = len(response.QA_list) if response else 0
            print(questions_generated, "questions/réponses générées")
            print(type(response), response)
            return response, None
        except Exception as e:
            error_msg = str(e)
            print(error_msg)
            if "rate limit" in error_msg.lower() or "429" in error_msg:
                wait_time = min(2 ** attempt, 60)
                print(f"Rate limit, attente {wait_time}s (tentative {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
                continue
            else:
                print("other error: ", error_msg)
                return None, f"Erreur génération: {error_msg}"
    
    return None, f"Échec après {max_retries} tentatives"


def filter_chunks_by_page_range(
    chunks: List[Dict],
    start_page: Optional[int],
    end_page: Optional[int],
) -> List[Dict]:
    """
    Filtre les chunks sur une plage de pages (num_page), pour exclure
    les pages de sommaire (borne inférieure) et de fin de livre (borne supérieure).

    Args:
        chunks: Liste des chunks (doivent contenir num_page)
        start_page: Première page incluse (optionnel)
        end_page: Dernière page incluse (optionnel)

    Returns:
        Liste filtrée des chunks
    """
    if start_page is None and end_page is None:
        return chunks
    filtered = []
    for chunk in chunks:
        num_page = chunk.get("num_page")
        if num_page is None:
            continue
        if start_page is not None and num_page < start_page:
            continue
        if end_page is not None and num_page > end_page:
            continue
        filtered.append(chunk)
    return filtered


async def save_qa_list_for_chunk(
    qa_items: List[Any],
    chunk_id: str,
    model_name: str,
    generate_facts: bool = False,
    facts_model_name: str = "mistral/mistral-medium",
) -> Tuple[int, int, Optional[str]]:
    """
    Sauvegarde une liste de questions/réponses pour un chunk, avec extraction
    optionnelle des faits (affirmations) de chaque réponse de référence.

    Args:
        qa_items: Liste de dicts {"question", "answer"} ou d'objets avec attributs question/answer
        chunk_id: ID du chunk
        model_name: Modèle ayant généré les questions/réponses
        generate_facts: Si True, extrait et enregistre les faits de chaque réponse
        facts_model_name: Modèle pour l'extraction des faits (format <provider>/<model>)

    Returns:
        Tuple (questions_sauvegardées, faits_sauvegardés, erreur)
    """
    from database.database import insert_answer_facts
    from agents import fact_extractor

    questions_saved = 0
    facts_saved = 0
    error = None

    async with await get_db_connection() as conn:
        for qa in qa_items:
            if isinstance(qa, dict):
                question = qa.get("question")
                answer = qa.get("answer")
            else:
                question = qa.question
                answer = qa.answer
            if not question or not answer:
                continue
            question_id = await save_question_to_db(
                question=question,
                answers=[answer],
                chunk_id=chunk_id,
                conn=conn,
                difficulty_level=3,
                model=model_name
            )
            questions_saved += 1

            if not generate_facts:
                continue
            try:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT answer_id, content
                        FROM text_question_answers
                        WHERE question_id = %s
                    """, (question_id,))
                    rows = await cur.fetchall()
                if not rows:
                    continue
                facts_agent = fact_extractor.get_answer_facts_agent(
                    model=facts_model_name.split("/")[-1]
                )
                for answer_id, answer_content in rows:
                    facts_output = facts_agent.run(
                        fact_extractor.FactExtractionInput(paragraph=answer_content)
                    )
                    facts = [
                        {
                            "content": f.content,
                            "importance": f.importance if f.importance in ("essential", "optional") else "essential"
                        }
                        for f in facts_output.facts
                    ]
                    if facts:
                        await insert_answer_facts(
                            answer_id, facts, conn, model=facts_model_name
                        )
                        facts_saved += len(facts)
            except Exception as e:
                error = f"Erreur extraction faits (question {question_id}): {e}"
                print(error)

    return questions_saved, facts_saved, error


async def process_question_generation_job_batch(
    job_id: str,
    all_chunks: List[Dict],
    num_questions: int,
    model_name: str,
    user_prompt: Optional[str] = None,
    generate_facts: bool = False,
):
    """
    Traite un job de génération de questions via l'API Batch de Mistral.

    Construit une requête par chunk, soumet le batch, suit son avancement,
    puis sauvegarde les questions/réponses en base. Si demandé, les faits
    des réponses sont extraits via un second batch.

    Args:
        job_id: L'ID du job concerné
        all_chunks: Liste des chunks à traiter (déjà filtrés par plage de pages)
        num_questions: Nombre de questions à générer par chunk
        model_name: Modèle au format <provider>/<model>
        user_prompt: Instructions personnalisées (optionnel)
        generate_facts: Extraire les faits des réponses générées (optionnel)
    """
    from .batch_generation import (
        build_qa_batch_requests,
        run_mistral_batch,
        parse_qa_response,
        build_answer_facts_batch_requests,
        parse_answer_facts_response,
    )
    from database.database import insert_answer_facts

    model = model_name.split("/")[-1]
    total_chunks = len(all_chunks)
    errors = []
    progress = {}
    processed_chunks = 0

    _update_job(job_id, total_documents=total_chunks)

    def on_batch_poll(phase: str, info: dict):
        print(f"Batch Mistral {info.get('batch_id')}: statut {info.get('status')}")
        update_question_generation_job(
            job_id=job_id,
            status="running",
            progress={
                "batch": {
                    "batch_id": info.get("batch_id"),
                    "status": info.get("status"),
                    "counts": info.get("counts"),
                    "mode": "batch"
                }
            },
            processed_documents=processed_chunks,
            errors=errors
        )

    try:
        qa_requests = build_qa_batch_requests(all_chunks, num_questions, user_prompt)
        qa_results = await run_mistral_batch(qa_requests, model, on_progress=on_batch_poll)
    except Exception as e:
        error_msg = f"Erreur API Batch: {e}"
        update_question_generation_job(
            job_id=job_id,
            status="failed",
            progress=progress,
            processed_documents=0,
            errors=[error_msg],
            error_message=error_msg
        )
        print(error_msg)
        return

    facts_to_generate = []

    for chunk in all_chunks:
        chunk_id = str(chunk.get("id", "unknown"))
        document_id = str(chunk.get("document_id", "unknown"))
        result = qa_results.get(f"qa::{chunk_id}")
        questions_generated = 0
        error = None

        if result is None:
            error = "Aucun résultat retourné par le batch pour ce chunk"
        elif result.get("error") or result.get("status") == "failed":
            error = f"Échec de la requête batch: {result.get('error') or result.get('status')}"
        else:
            qa_list = parse_qa_response(result.get("content", ""))
            if qa_list:
                questions_generated, _, save_error = await save_qa_list_for_chunk(
                    qa_items=qa_list,
                    chunk_id=chunk_id,
                    model_name=model_name,
                    generate_facts=False
                )
                if save_error:
                    error = save_error
                if generate_facts:
                    async with await get_db_connection() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute("""
                                SELECT a.answer_id, a.content
                                FROM text_question_answers a
                                JOIN text_question_chunks qc ON qc.question_id = a.question_id
                                WHERE qc.chunk_id = %s
                                  AND a.answer_id NOT IN (SELECT answer_id FROM text_answer_facts)
                            """, (chunk_id,))
                            rows = await cur.fetchall()
                    facts_to_generate.extend(
                        {"answer_id": row[0], "content": row[1]} for row in rows
                    )
            else:
                error = "Aucune question générée par le modèle"

        progress[chunk_id] = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "questions_generated": questions_generated,
            "error": error,
            "status": "completed" if not error else "failed",
            "mode": "batch"
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

    # Extraction des faits via un second batch (facturation également réduite)
    if generate_facts and facts_to_generate:
        try:
            facts_requests = build_answer_facts_batch_requests(facts_to_generate)
            facts_results = await run_mistral_batch(facts_requests, model, on_progress=on_batch_poll)
            async with await get_db_connection() as conn:
                for answer in facts_to_generate:
                    result = facts_results.get(f"facts::{answer['answer_id']}")
                    if result is None or result.get("error") or result.get("status") == "failed":
                        errors.append(f"faits answer {answer['answer_id']}: "
                                      f"{(result or {}).get('error') or 'requête batch échouée'}")
                        continue
                    facts = parse_answer_facts_response(result.get("content", ""))
                    if facts:
                        await insert_answer_facts(
                            answer["answer_id"], facts, conn, model=model_name
                        )
                progress["facts"] = {
                    "answers_processed": len(facts_to_generate),
                    "mode": "batch"
                }
                update_question_generation_job(
                    job_id=job_id,
                    status="running",
                    progress=progress,
                    processed_documents=processed_chunks,
                    errors=errors
                )
        except Exception as e:
            errors.append(f"Extraction des faits (batch): {e}")

    final_status = "completed" if not errors else "completed_with_errors"
    update_question_generation_job(
        job_id=job_id,
        status=final_status,
        progress=progress,
        processed_documents=processed_chunks,
        errors=errors
    )
    print(f"Job batch {job_id} terminé: {final_status} ({processed_chunks}/{total_chunks})")


async def process_question_generation_job(job_id: str):
    """
    Traite un job de génération de questions en arrière-plan.
    Génère des questions pour chaque chunk de chaque document validé, ou pour un document spécifique, ou pour un chunk spécifique.
    
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
    model_name = parameters.get("model_name") or "mistral/mistral-small-2603"
    document_id = parameters.get("document_id")  # ID du document spécifique (optionnel)
    chunk_id = parameters.get("chunk_id")  # ID du chunk spécifique (optionnel, prioritaire)
    num_answers = parameters.get("num_answers_per_question", 1)  # Nombre de réponses par question
    user_prompt = parameters.get("user_prompt")  # Instructions personnalisées de l'utilisateur (optionnel)
    start_page = parameters.get("start_page")  # Première page à traiter (optionnel)
    end_page = parameters.get("end_page")  # Dernière page à traiter (optionnel)
    use_batch = parameters.get("use_batch", False)  # Génération via l'API Batch de Mistral
    generate_facts = parameters.get("generate_facts", False)  # Extraction des faits des réponses
    
    errors = []
    progress = job.get("progress", {})
    processed_chunks = 0

    # Si un chunk_id spécifique est fourni, ne traiter que ce chunk
    if chunk_id:
        async with await get_db_connection() as conn:
            chunk = await database.get_chunk_by_id(conn, chunk_id)
        
        if chunk:
            all_chunks = [chunk]
            total_chunks = 1
        else:
            # Chunk non trouvé, met à jour le job avec une erreur
            errors.append(f"Chunk {chunk_id} introuvable")
            update_question_generation_job(
                job_id=job_id,
                status="failed",
                progress=progress,
                processed_documents=0,
                errors=errors,
                error_message=f"Chunk {chunk_id} introuvable"
            )
            print(f"Chunk {chunk_id} introuvable, job {job_id} échoué")
            return
    else:
        # Récupérer tous les chunks des documents validés ou d'un document spécifique
        async with await get_db_connection() as conn:
            all_chunks = await database.get_all_text_chunks(conn, document_id)
        # Filtrer par plage de pages (exclusion du sommaire et des pages de fin)
        all_chunks = filter_chunks_by_page_range(all_chunks, start_page, end_page)
        total_chunks = len(all_chunks)
        
        # Mode Batch : traitement en masse via l'API Batch de Mistral
        if use_batch:
            await process_question_generation_job_batch(
                job_id=job_id,
                all_chunks=all_chunks,
                num_questions=num_questions,
                model_name=model_name,
                user_prompt=user_prompt,
                generate_facts=generate_facts
            )
            return
    
    print(f"{total_chunks} chunks à traiter..." + (f" (chunk {chunk_id})" if chunk_id else (f" (document {document_id})" if document_id else "")))

    _update_job(job_id, total_documents=total_chunks)

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
            # attention : il y a deux agents séparés pour la génération de QA
            qa_list, error = await generate_questions_single_answer_for_chunk(
                chunk_content=chunk_content,
                chunk_id=chunk_id,
                document_id=document_id,
                num_questions=num_questions,
                model_name=model_name,
                user_prompt=user_prompt
            )

            questions_generated = 0
            if qa_list is not None and getattr(qa_list, "QA_list", None):
                # insertion dans MySQL (+ extraction des faits si demandée)
                questions_generated, _, facts_error = await save_qa_list_for_chunk(
                    qa_items=qa_list.QA_list,
                    chunk_id=chunk_id,
                    model_name=model_name,
                    generate_facts=generate_facts
                )
                if facts_error:
                    error = facts_error
            elif not error:
                error = "Aucune question générée par le modèle"

            progress[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "questions_generated": questions_generated,
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
