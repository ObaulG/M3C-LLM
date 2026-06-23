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
    qdrant_client,
    get_db_connection,
    get_chunks_for_document,
    get_resource_full_metadata
)
from qdrant_client import models
from embedders import get_embedder_instance
from .sse_manager import sse_manager
from app.jobs.manager import (
    create_job as _create_job,
    get_job as _get_job,
    get_jobs_by_type as _get_jobs_by_type,
    get_all_jobs as _get_all_jobs,
    get_latest_job as _get_latest_job,
    update_job as _update_job,
)

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

async def download_pdf_stream(url: str, timeout: int = 300):
    """
    Télécharge un PDF de manière asynchrone en streaming.
    Retourne un générateur asynchrone pour FastAPI.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
            if response.status == 200:
                # On lit le contenu par morceaux
                async for chunk in response.content.iter_chunked(8192):  # 8 Ko par morceau
                    yield chunk
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
# GESTION DES JOBS - Utilise le module central app.jobs
# ============================================================================


def create_indexing_job(job_type: str = "pdf-from-m3c", parameters: dict = None) -> str:
    """
    Crée un nouveau job d'indexation.
    
    Args:
        job_type: Catégorie de documents (ex: "pdf-from-m3c", "all-metadata", "all-with-text")
        parameters: Paramètres du job (chunk_size, chunk_overlap, embedder_name)
    
    Returns:
        job_id: L'ID unique du job créé
    """
    return _create_job(
        job_type="indexing",
        document_categories=[job_type],
        parameters=parameters or {},
        total_items=len(VALID_TEXT_RESOURCE_ID)
    )


def get_indexing_job(job_id: str) -> Optional[dict]:
    """
    Récupère un job par son ID.
    
    Args:
        job_id: L'ID du job à récupérer
    
    Returns:
        Le job sous forme de dict, ou None s'il n'existe pas
    """
    return _get_job(job_id)


def update_indexing_job(
    job_id: str,
    status: str,
    progress: dict = None,
    processed_items: int = None,
    id_embeddings_missing: list = None,
    error_message: str = None
) -> bool:
    """
    Met à jour un job existant.
    
    Args:
        job_id: L'ID du job à mettre à jour
        status: Nouveau statut (pending, running, completed, failed, cancelled)
        progress: Progression détaillée (optionnel)
        processed_items: Nombre d'éléments traités (optionnel)
        id_embeddings_missing: Liste des embeddings manquants (optionnel)
        error_message: Message d'erreur (optionnel)
    
    Returns:
        True si la mise à jour a réussi, False sinon
    """
    update_kwargs = {
        "status": status,
        "progress": progress,
        "processed_items": processed_items,
        "id_embeddings_missing": id_embeddings_missing,
        "error_message": error_message
    }
    return _update_job(job_id, **update_kwargs)


def get_latest_job_by_type(job_type: str, exclude_status: list = None) -> Optional[dict]:
    """
    Récupère le job le plus récent d'un type donné ou d'une catégorie de documents.
    
    Args:
        job_type: Type de tâche (ex: "indexing") OU catégorie de documents (ex: "pdf-from-m3c")
        exclude_status: Liste des statuts à exclure (optionnel)
    
    Returns:
        Le job le plus récent sous forme de dict, ou None si aucun trouvé
    """
    # D'abord essayer de filtrer par job_type (nouvelle nomenclature)
    job = _get_latest_job(job_type, exclude_status)
    if job:
        return job
    
    # Sinon, essayer de filtrer par document_categories (compatibilité)
    # Chercher tous les jobs indexing et filtrer par document_categories
    indexing_jobs = _get_jobs_by_type("indexing")
    matching_jobs = [
        j for j in indexing_jobs 
        if job_type in j.get("document_categories", [])
        and (exclude_status is None or j.get("status") not in exclude_status)
    ]
    
    if matching_jobs:
        return max(matching_jobs, key=lambda j: j.get("created_at", ""))
    
    return None


def get_all_indexing_jobs(status_filter: str = None, category_filter: str = None) -> list:
    """
    Récupère tous les jobs d'indexation.
    
    Args:
        status_filter: Filtre optionnel par statut
        category_filter: Filtre optionnel par catégorie de documents
    
    Returns:
        Liste de tous les jobs
    """
    # Récupérer tous les jobs de type "indexing"
    all_jobs = _get_jobs_by_type("indexing")
    
    # Appliquer les filtres
    if status_filter:
        all_jobs = [job for job in all_jobs if job.get("status") == status_filter]
    
    if category_filter:
        all_jobs = [
            job for job in all_jobs 
            if category_filter in job.get("document_categories", [])
        ]
    
    return all_jobs


def clean_metadata_value(value):
    """
    Nettoie une valeur de métadonnée : trim et normalise les espaces.
    
    Args:
        value: La valeur à nettoyer (peut être None)
        
    Returns:
        La valeur nettoyée ou None si vide
    """
    if not value:
        return None
    # Trim et remplacer les espaces/retours à la ligne multiples par un seul espace
    cleaned = " ".join(str(value).strip().split())
    return cleaned if cleaned else None


def build_metadata_string(metadata: dict) -> str:
    """
    Construit une chaîne de caractères formatée à partir des métadonnées.
    
    Args:
        metadata: Dict contenant les métadonnées avec clés :
            title, creator, description, publisher, contributor, date,
            type, language, abstract, subjects (liste)
            
    Returns:
        Chaîne de caractères formatée pour les embeddings
    """
    lines = []
    
    # Titre
    title = clean_metadata_value(metadata.get("title"))
    if title:
        lines.append(f"Titre: {title}")
    
    # Auteurs (creator et contributor)
    authors = []
    creator = clean_metadata_value(metadata.get("creator"))
    if creator:
        authors.append(creator)
    contributor = clean_metadata_value(metadata.get("contributor"))
    if contributor:
        authors.append(contributor)
    if authors:
        lines.append(f"Auteurs: {", ".join(authors)}")
    
    # Résumé (privilégier abstract si disponible, sinon description)
    abstract = clean_metadata_value(metadata.get("abstract"))
    description = clean_metadata_value(metadata.get("description"))
    summary = abstract or description
    if summary:
        lines.append(f"Résumé: {summary}")
    
    # Éditeur
    publisher = clean_metadata_value(metadata.get("publisher"))
    if publisher:
        lines.append(f"Éditeur: {publisher}")
    
    # Date
    date = clean_metadata_value(metadata.get("date"))
    if date:
        lines.append(f"Date: {date}")
    
    # Type
    type_ = clean_metadata_value(metadata.get("type"))
    if type_:
        lines.append(f"Type: {type_}")
    
    # Langue
    language = clean_metadata_value(metadata.get("language"))
    if language:
        lines.append(f"Langue: {language}")
    
    # Mots-clés (un par ligne)
    subjects = metadata.get("subjects", [])
    if subjects:
        lines.append("Mots-clés:")
        for subject in subjects:
            cleaned_subject = clean_metadata_value(subject)
            if cleaned_subject:
                lines.append(cleaned_subject)
    
    return "\n".join(lines)


async def process_metadata_indexing_job(job_id: str, embedder_name: str):
    """
    Traite un job d'indexation (création d'embeddings) des métadonnées de chaque item.
    
    Pour chaque resource_id, récupère les métadonnées, construit une chaîne formatée,
    génère l'embedding et le sauvegarde dans Qdrant.
    
    Args:
        job_id: L'ID du job à traiter
        embedder_name: Le nom de l'embedding model à utiliser
        
    Returns:
        Dict avec le résultat du traitement
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
    except ValueError as e:
        errors.append(f"embedder_name invalide - {e}")
        return {"success": False, "message": "Job annulé", "job_id": job_id, "processed_items": job["processed_items"], "errors": errors}

    model_name = embedder.name

    for i, resource_id in enumerate(VALID_TEXT_RESOURCE_ID):
        resource_id_str = str(resource_id)
        print(f"Métadonnées {i+1}/{len(VALID_TEXT_RESOURCE_ID)} - resource_id {resource_id_str}")

        # Vérifier si déjà complété
        doc_progress = progress.get(resource_id_str, {})
        if doc_progress.get("status") == "completed":
            processed_count += 1
            print("already completed")
            continue

        # Mettre à jour status en processing sur ce document
        progress[resource_id_str] = {
            "status": "processing",
            "started_at": datetime.now().isoformat()
        }
        update_indexing_job(job_id, "running", progress=progress)

        try:
            # Récupérer les métadonnées
            conn = await get_db_connection()
            metadata = await get_resource_full_metadata(conn, resource_id)
            await conn.close()

            if not metadata or all(v is None or v == [] for k, v in metadata.items()):
                raise ValueError("Aucune métadonnée trouvée pour ce resource_id")

            # Construire la chaîne de métadonnées
            metadata_string = build_metadata_string(metadata)
            
            if not metadata_string:
                raise ValueError("La chaîne de métadonnées est vide")

            # Générer l'embedding pour les métadonnées
            print(f"Génération embedding pour métadonnées de {resource_id_str}")
            embedding = embedder.embed(metadata_string)

            # Créer la collection Qdrant
            vector_size = embedder.dimension
            collection_name = f"MD-{model_name}-{vector_size}"
            
            await ensure_qdrant_collection(collection_name, vector_size)

            # Créer un document_id unique pour les métadonnées
            document_id = f"metadata-{resource_id}"
            chunk_id = f"{document_id}-metadata"

            # Insérer dans Qdrant
            result = await insert_chunk_embedding_qdrant(
                chunk_id=chunk_id,
                document_id=document_id,
                model_name=model_name,
                embedding=embedding,
                content=metadata_string,
                metadata={"resource_id": resource_id, "source": "metadata"},
                collection_name=collection_name
            )
            print(f"Embedding sauvegardé - operation_id: {result.operation_id}")

            progress[resource_id_str] = {
                "status": "completed",
                "chunks_count": 1,
                "embeddings_count": 1,
                "document_id": document_id,
                "processed_at": datetime.now().isoformat()
            }
            processed_count += 1

        except Exception as e:
            errors.append(f"Resource {resource_id}: {str(e)}")
            progress[resource_id_str] = {
                "status": "failed",
                "error": str(e),
                "processed_at": datetime.now().isoformat()
            }
            print(f"Erreur pour {resource_id_str}: {str(e)}")

        if processed_count % 3 == 0 or errors:
            update_indexing_job(
                job_id, "running",
                progress=progress,
                processed_items=processed_count
            )

    total_resources = len(VALID_TEXT_RESOURCE_ID)
    status = "completed" if processed_count == total_resources and not errors else "failed"
    error_msg = "; ".join(errors) if errors else None

    update_indexing_job(
        job_id, status,
        progress=progress,
        processed_items=processed_count,
        error_message=error_msg
    )

    return {
        "success": status == "completed",
        "message": f"Job {status}",
        "job_id": job_id,
        "processed_items": processed_count,
        "total_items": total_resources,
        "errors": errors
    }


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

        # Vérifier si déjà complété
        doc_progress = progress.get(resource_id_str, {})
        if doc_progress.get("status") == "completed":
            processed_count += 1
            print("already completed")
            continue

        # Mettre à jour status en processing sur ce document
        progress[resource_id_str] = {
            "status": "processing",
            "started_at": datetime.now().isoformat()
        }
        update_indexing_job(job_id, "running", progress=progress)

        # Récupérer text_document_id si déjà créé
        text_document_id = doc_progress.get("text_document_id")
        
        # Si les chunks n'existent pas, les créer
        if not text_document_id:

            # Générer les chunks (téléchargement PDF, découpage)
            try:
                chunks_data, error = await process_pdf_from_m3c(resource_id, chunk_size, overlap)
            except OSError as e:
                print(f"La connexion à la DB MySQL a échoué - {e}")
                errors.append(f"La connexion à la DB MySQL a échoué - {e}")
                progress[resource_id_str] = {
                    "status": "failed",
                    "error": f"La connexion à la DB MySQL a échoué - {e}",
                    "processed_at": datetime.now().isoformat()
                }
                continue

            if error:
                progress[resource_id_str] = {
                    "status": "failed",
                    "error": error,
                    "processed_at": datetime.now().isoformat()
                }
                errors.append(f"Resource {resource_id}: {error}")
                continue

            if not chunks_data:
                progress[resource_id_str] = {
                    "status": "failed",
                    "error": "Aucun chunk généré",
                    "processed_at": datetime.now().isoformat()
                }
                errors.append(f"Resource {resource_id}: Aucun chunk généré")
                continue

            print("PDF retrieved")
            
            # Insérer le document texte
            conn = await get_db_connection()
            try:
                text_document_id = await insert_text_document(
                    conn, "pdf", str(resource_id),
                    "".join([chunk["content"] for chunk in chunks_data])
                )
                if not text_document_id:
                    raise ValueError("insert_text_document a retourné None")
            except Exception as e:
                errors.append(f"Resource {resource_id}: {e}")
                progress[resource_id_str] = {
                    "status": "failed",
                    "error": f"Erreur insertion document: {e}",
                    "processed_at": datetime.now().isoformat()
                }
                continue

            # Créer la stratégie de chunking
            strategy_name = f"recursive_char_{chunk_size}_overlap_{overlap}"
            try:
                chunking_strategy_id = await get_or_create_chunking_strategy(
                    conn,
                    strategy_name,
                    "character",
                    chunk_size,
                    chunk_size,
                    overlap
                )
                if not chunking_strategy_id:
                    raise ValueError("get_or_create_chunking_strategy a retourné None")
            except Exception as e:
                errors.append(f"Resource {resource_id}: {e}")
                progress[resource_id_str] = {
                    "status": "failed",
                    "error": f"Erreur création stratégie: {e}",
                    "processed_at": datetime.now().isoformat()
                }
                continue

            # Insérer les chunks en BDD
            try:
                chunks_data_for_db = []
                for chunk_info in chunks_data:
                    chunk_id = str(uuid.uuid4())
                    chunks_data_for_db.append((
                        chunk_id,
                        text_document_id,
                        chunking_strategy_id,
                        chunk_info["content"],
                        chunk_info["num_page"],
                        chunk_info["position_in_page"],
                        chunk_info["token_count"],
                        chunk_info["character_count"]
                    ))
                await insert_chunks(conn, chunks_data_for_db)
                print("chunks inserted in mySQL")
            except Exception as e:
                errors.append(f"Resource {resource_id}: {e}")
                progress[resource_id_str] = {
                    "status": "failed",
                    "error": f"Erreur insertion chunks: {e}",
                    "processed_at": datetime.now().isoformat()
                }
                continue
        else:
            # Les chunks existent déjà
            chunking_strategy_id = doc_progress.get("chunking_strategy_id")
            print(f"Chunking déjà terminé pour {resource_id_str} avec stratégie {chunking_strategy_id}")

        # Dans TOUS les cas, récupérer les chunks depuis la BDD
        try:
            conn = await get_db_connection()
            existing_chunks = await get_chunks_for_document(text_document_id, conn)
            await conn.close()
            
            if not existing_chunks:
                errors.append(f"Resource {resource_id}: Aucun chunk trouvé pour document_id {text_document_id}")
                progress[resource_id_str] = {
                    "status": "failed",
                    "error": "Aucun chunk trouvé en BDD",
                    "processed_at": datetime.now().isoformat()
                }
                continue
            
            # Convertir les chunks au format attendu pour l'embedding
            chunks = []
            chunk_ids = []
            for chunk in existing_chunks:
                chunk_id = chunk.get("id") or str(uuid.uuid4())
                chunk_ids.append(chunk_id)
                chunks.append({
                    "content": chunk.get("content", ""),
                    "num_page": chunk.get("num_page", 0),
                    "position_in_page": chunk.get("position_in_page", 0),
                    "token_count": chunk.get("token_count", 0),
                    "character_count": chunk.get("character_count", 0),
                    "metadata": chunk.get("metadata", {})
                })
            
            print(f"Récupéré {len(chunks)} chunks pour {resource_id_str}")
            
        except Exception as e:
            errors.append(f"Resource {resource_id}: Erreur récupération chunks - {str(e)}")
            progress[resource_id_str] = {
                "status": "failed",
                "error": f"Erreur récupération chunks: {str(e)}",
                "processed_at": datetime.now().isoformat()
            }
            continue

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
            "chunking_completed": True,
            "chunking_strategy_id": chunking_strategy_id,
            "text_document_id": text_document_id,
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

