"""
Services pour l'indexation des PDFs depuis M3C.
"""

import json
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from datetime import datetime

import aiohttp
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import database
from database.database import (
    VALID_TEXT_RESOURCE_ID,
    insert_chunks,
    insert_chunk_embedding_qdrant,
    insert_chunk_embeddings_batch_qdrant,
    get_pdf_url_for_resource,
    insert_text_document,
    get_or_create_chunking_strategy,
    ensure_qdrant_collection,
    qdrant_client
)
from qdrant_client import models
from embedders import get_embedder_instance
from .sse_manager import sse_manager

# Tokenizer pour le comptage des tokens
_TOKENIZER = None


def get_tokenizer():
    """Initialise et retourne le tokenizer Mistral pour le comptage des tokens."""
    global _TOKENIZER
    if _TOKENIZER is None:
        try:
            from transformers import AutoTokenizer
            _TOKENIZER = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-v0.1")
        except ImportError:
            # Fallback : estimer le nombre de tokens comme environ 4 caractères par token
            _TOKENIZER = "fallback"
    return _TOKENIZER


def count_tokens(text: str) -> int:
    """Compte le nombre de tokens dans un texte."""
    tokenizer = get_tokenizer()
    if tokenizer == "fallback":
        # Estimation : environ 4 caractères par token pour l'anglais/français
        return max(1, len(text) // 4)
    return len(tokenizer.tokenize(text))


async def download_pdf(url: str, timeout: int = 300) -> bytes:
    """
    Télécharge un PDF de manière asynchrone.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
            if response.status == 200:
                return await response.read()
            else:
                text = await response.text()
                raise Exception(f"HTTP {response.status} pour {url}: {text[:200]}")


def split_text_into_chunks(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Découpe un texte en chunks avec recouvrement.

    Args:
        text: Texte à découper
        chunk_size: Taille maximale d'un chunk en caractères
        overlap: Nombre de caractères de recouvrement entre les chunks

    Returns:
        Liste des chunks
    """
    if not text or chunk_size <= 0:
        return []

    chunks = []
    start = 0
    overlap = min(overlap, chunk_size)  # Assurer que overlap <= chunk_size

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap

    return chunks

async def process_pdf_from_m3c(resource_id: int, chunk_size: int, overlap: int) -> Tuple[List[dict], str, Optional[str]]:
    """
    Télécharge un PDF depuis M3C, le découpe et retourne les chunks ainsi que le texte complet.
    Returns: (chunks, full_text, error)
    """
    print("process_pdf_from_m3c")
    pdf_url = await get_pdf_url_for_resource(resource_id)
    if not pdf_url:
        return [], "", f"Aucun PDF trouvé pour resource_id {resource_id}"
    print("pdf_url", pdf_url)

    try:
        pdf_content = await download_pdf(pdf_url)
    except Exception as e:
        return [], "", f"Erreur téléchargement PDF depuis {pdf_url}: {str(e)}"
    print("pdf downloaded")

    temp_dir = Path("temp_pdfs")
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / f"{resource_id}.pdf"
    
    try:
        with open(temp_path, 'wb') as f:
            f.write(pdf_content)
        print("document écrit")
        loader = PyPDFLoader(str(temp_path))
        documents = loader.load()
        
        if not documents:
            return [], "", f"Aucun document chargé depuis {pdf_url}"
        print(f"{len(documents)} documents loaded: ", )
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            separators=["\n\n\n", "\n\n", "\n", " ", ""],
            length_function=len,
            keep_separator=False,
        )

        chunks = text_splitter.split_documents(documents)
        print(f"Document découpé en {len(chunks)} chunks")

        result_chunks = []
        for i, chunk in enumerate(chunks):
            page_num = chunk.metadata.get("page", 0)
            content = chunk.page_content
            result_chunks.append({
                "content": content,
                "num_page": page_num + 1,
                "position_in_page": i,
                "token_count": count_tokens(content),
                "character_count": len(content),
                "metadata": {
                    "page": page_num + 1,
                    "resource_id": resource_id
                }
            })
        
        return result_chunks, None
        
    except Exception as e:
        print(e)
        return [], "", f"Erreur traitement PDF: {str(e)}"
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except:
                pass


# ============================================================================
# GESTION LOCALE DES JOBS (remplace MySQL)
# ============================================================================

JOBS_FILE = Path("app/indexing/jobs.json")


def _ensure_jobs_file():
    """Crée le fichier jobs.json s'il n'existe pas."""
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not JOBS_FILE.exists():
        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)


def _load_jobs() -> Dict[str, dict]:
    """Charge tous les jobs depuis le fichier JSON."""
    _ensure_jobs_file()
    try:
        with open(JOBS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save_jobs(jobs: Dict[str, dict]) -> None:
    """Sauvegarde tous les jobs dans le fichier JSON."""
    _ensure_jobs_file()
    with open(JOBS_FILE, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)


def create_indexing_job(job_type: str = "pdf-from-m3c", parameters: dict = None) -> str:
    """
    Crée un nouveau job d'indexation.
    
    Args:
        job_type: Type de job (ex: "pdf-from-m3c")
        parameters: Paramètres du job (chunk_size, chunk_overlap, embedder_name)
    
    Returns:
        job_id: L'ID unique du job créé
    """
    jobs = _load_jobs()
    job_id = str(uuid.uuid4())
    
    now = datetime.now().isoformat()
    job = {
        "job_id": job_id,
        "job_type": job_type,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "total_items": len(VALID_TEXT_RESOURCE_ID),
        "processed_items": 0,
        "progress": {},
        "parameters": parameters or {},
        "error_message": None
    }
    
    jobs[job_id] = job
    _save_jobs(jobs)
    return job_id


def get_indexing_job(job_id: str) -> Optional[dict]:
    """
    Récupère un job par son ID.
    
    Args:
        job_id: L'ID du job à récupérer
    
    Returns:
        Le job sous forme de dict, ou None s'il n'existe pas
    """
    jobs = _load_jobs()
    return jobs.get(job_id)


def update_indexing_job(
    job_id: str,
    status: str,
    progress: dict = None,
    processed_items: int = None,
    id_embeddings_missing: list = [],
    error_message: str = None
) -> bool:
    """
    Met à jour un job existant.
    
    Args:
        job_id: L'ID du job à mettre à jour
        status: Nouveau statut (pending, running, completed, failed, cancelled)
        progress: Progression détaillée (optionnel)
        processed_items: Nombre d'éléments traités (optionnel)
        error_message: Message d'erreur (optionnel)
    
    Returns:
        True si la mise à jour a réussi, False sinon
    """
    jobs = _load_jobs()
    
    if job_id not in jobs:
        return False
    
    job = jobs[job_id]
    job["status"] = status
    job["updated_at"] = datetime.now().isoformat()
    job["id_embeddings_missing"] = id_embeddings_missing
    if progress is not None:
        job["progress"] = progress
    if processed_items is not None:
        job["processed_items"] = processed_items
    if error_message is not None:
        job["error_message"] = error_message
    
    _save_jobs(jobs)
    return True


def get_latest_job_by_type(job_type: str, exclude_status: list = None) -> Optional[dict]:
    """
    Récupère le job le plus récent d'un type donné.
    
    Args:
        job_type: Type de job à filtrer (ex: "pdf-from-m3c")
        exclude_status: Liste des statuts à exclure (optionnel)
    
    Returns:
        Le job le plus récent sous forme de dict, ou None si aucun trouvé
    """
    jobs = _load_jobs()
    matching_jobs = [job for job in jobs.values() if job.get("job_type") == job_type]
    
    if exclude_status:
        matching_jobs = [job for job in matching_jobs if job.get("status") not in exclude_status]
    
    if not matching_jobs:
        return None
    
    return max(matching_jobs, key=lambda j: j.get("created_at", ""))


def get_all_indexing_jobs(status_filter: str = None) -> list:
    """
    Récupère tous les jobs d'indexation.
    
    Args:
        status_filter: Filtre optionnel par statut
    
    Returns:
        Liste de tous les jobs
    """
    jobs = _load_jobs()
    all_jobs = list(jobs.values())
    
    if status_filter:
        all_jobs = [job for job in all_jobs if job.get("status") == status_filter]
    
    return all_jobs


async def process_pdf_indexing_job(job_id: str, chunk_size: int, overlap: int, embedder_name: str):
    """
    Traite un job d'indexation de PDFs depuis M3C avec reprise automatique.
    """
    from database.database import get_db_connection
    
    job = get_indexing_job(job_id)
    if not job:
        raise Exception(f"Job {job_id} non trouvé")

    if job["status"] == "completed":
        return {"success": True, "message": "Job déjà terminé", "job_id": job_id, "processed_items": job["processed_items"]}
    
    if job["status"] == "cancelled":
        return {"success": False, "message": "Job annulé", "job_id": job_id, "processed_items": job["processed_items"]}
    
    # Autoriser la reprise des jobs "failed" ou "running" - les mettre à jour en "running"
    update_indexing_job(job_id, "running")
    
    progress = job.get("progress", {})
    if not progress:
        progress = {}
    
    processed_count = job.get("processed_items", 0)
    errors = []
    all_missing_embeddings = []

    # récupérer l'embedder
    try:
        embedder = get_embedder_instance(embedder_name)
        print(embedder)
    except ValueError as e:
        print(f"embedder_name invalide - {e}")
        errors.append(f"embedder_name invalide - {e}")
        return {"success": False, "message": "Job annulé", "job_id": job_id, "processed_items": job["processed_items"], errors: errors}

    model_name = embedder.name

    for i, resource_id in enumerate(VALID_TEXT_RESOURCE_ID):
        resource_id_str = str(resource_id)
        print(f"Document {i+1}/{len(VALID_TEXT_RESOURCE_ID)} - resource_id {resource_id_str}")

        if resource_id_str in progress and progress[resource_id_str].get("status") == "completed":
            processed_count += 1
            print("already completed")
            continue

        progress[resource_id_str] = {
            "status": "processing",
            "started_at": datetime.now().isoformat()
        }
        update_indexing_job(job_id, "running", progress=progress)

        try:
            # Générer les chunks pour ce document et récupérer le texte complet
            chunks, error = await process_pdf_from_m3c(resource_id, chunk_size, overlap)
        except OSError as e:
            print(f"La connexion à la DB MySQL a échoué - {e}")
            errors.append(f"La connexion à la DB MySQL a échoué - {e}")

        if error:
            progress[resource_id_str] = {
                "status": "failed",
                "error": error,
                "processed_at": datetime.now().isoformat()
            }
            errors.append(f"Resource {resource_id}: {error}")
            continue

        if not chunks:
            progress[resource_id_str] = {
                "status": "failed",
                "error": "Aucun chunk généré",
                "processed_at": datetime.now().isoformat()
            }
            errors.append(f"Resource {resource_id}: Aucun chunk généré")
            continue

        print("PDF retrieved")
        # 1. Insérer le document dans text_documents AVANT la boucle sur les chunks
        conn = await get_db_connection()
        try:
            text_document_id = await insert_text_document(conn, "pdf", str(resource_id), "".join([chunk["content"] for chunk in chunks]))
            if not text_document_id:
                raise ValueError
        except Exception as e:
            errors.append(f"Resource {resource_id}: {e}")
            progress[resource_id_str] = {
                "status": "failed",
                "error": f"Erreur insertion document pour resource_id {resource_id}",
                "processed_at": datetime.now().isoformat()
            }
            continue

        # 2. Obtenir ou créer la stratégie de chunking
        strategy_name = f"recursive_char_{chunk_size}_overlap_{overlap}"
        try:
            strategy_id = await get_or_create_chunking_strategy(
                conn,
                strategy_name,
                "character",
                chunk_size,
                chunk_size,
                overlap
            )
            if not strategy_id:
                raise ValueError
        except Exception as e:
            errors.append(f"Resource {resource_id}: {e}")
            progress[resource_id_str] = {
                "status": "failed",
                "error": f"Erreur création ou récupération de strategy_name pour resource_id {resource_id}",
                "processed_at": datetime.now().isoformat()
            }
            continue

        # 3. Préparer les chunks pour insertion
        chunks_data = []
        chunk_ids = []
        for i, chunk_info in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)
            chunks_data.append((
                chunk_id,
                text_document_id,
                strategy_id,
                chunk_info["content"],
                chunk_info["num_page"],
                chunk_info["position_in_page"],
                chunk_info["token_count"],
                chunk_info["character_count"]
            ))

        # 4. Insérer les chunks dans text_chunks
        await insert_chunks(conn, chunks_data)
        print("chunks inserted in mySQL")

        # 5. Créer la collection Qdrant avec le bon format
        vector_size = embedder.dimension
        collection_name = f"LD-{model_name}-{vector_size}"

        try:
            await ensure_qdrant_collection(collection_name, vector_size)
        except Exception as e:
            errors.append(f"Resource {resource_id}: Erreur création collection Qdrant - {str(e)}")
            progress[resource_id_str] = {
                "status": "failed",
                "error": f"Erreur création collection Qdrant",
                "processed_at": datetime.now().isoformat()
            }
            continue

        # 6. Traiter les embeddings 1 par 1
        id_missing_embeddings = []
        for i, chunk_info in enumerate(chunks):
            chunk_id = chunk_ids[i]
            print("chunk", i)
            try:
                # Générer l'embedding
                embedding = embedder.embed(chunk_info["content"])
                
                # Insérer dans Qdrant
                result = await insert_chunk_embedding_qdrant(
                    chunk_id=chunk_id,
                    document_id=text_document_id,
                    model_name=model_name,
                    embedding=embedding,
                    content=chunk_info["content"],
                    num_page=chunk_info["num_page"],
                    position_in_page=chunk_info["position_in_page"],
                    token_count=chunk_info["token_count"],
                    metadata=chunk_info.get("metadata", {}),
                    collection_name=collection_name
                )
                print(f"chunk {i} - operation_id: {result.operation_id}")
                
            except Exception as e:
                errors.append(f"Resource {resource_id} chunk {i}: Erreur - {str(e)}")
                id_missing_embeddings.append(chunk_id)

        all_missing_embeddings.extend(id_missing_embeddings)

        progress[resource_id_str] = {
            "status": "completed",
            "chunks_count": len(chunks),
            "id_missing_embeddings": id_missing_embeddings,
            "processed_at": datetime.now().isoformat()
        }
        processed_count += 1

        if processed_count % 3 == 0 or errors:
            update_indexing_job(
                job_id, "running",
                progress=progress,
                processed_items=processed_count
            )

    total_resources = len(VALID_TEXT_RESOURCE_ID)
    status = "completed" if processed_count == total_resources and not all_missing_embeddings else "failed"
    error_msg = "; ".join(errors) if errors else None

    update_indexing_job(
        job_id, status,
        progress=progress,
        processed_items=processed_count,
        error_message=error_msg
    )

    # Envoyer notification SSE
    await sse_manager.send_event(
        job_id,
        "job_completed",
        {
            "job_id": job_id,
            "status": status,
            "processed_items": processed_count,
            "total_items": total_resources,
            "missing_embeddings_count": len(all_missing_embeddings),
            "timestamp": datetime.now().isoformat()
        }
    )

    return {
        "success": status == "completed",
        "job_id": job_id,
        "processed_items": processed_count,
        "total_items": total_resources,
        "errors": errors
    }

