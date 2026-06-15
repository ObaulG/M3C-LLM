"""Router FastAPI pour la gestion des embedders."""

from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
import json
import aiohttp
from pathlib import Path
from typing import Optional
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .registry import get_embedder_list, get_embedders
from app.embedders import get_embedder_instance
from datetime import datetime

router = APIRouter(prefix="/api/embedders", tags=["Embedders"])


@router.get("", 
           response_model=List[Dict[str, Any]],
           summary="Lister les embedders disponibles",
           description="Retourne la liste des embedders configurés et disponibles.")
async def get_embedders():
    """Retourne la liste de tous les embedders disponibles.
    
    Returns:
        Liste des embedders avec leurs informations (nom, type, modèle, dimension, etc.)
    """
    return get_embedder_list()


@router.get("/dict", 
           response_model=Dict[str, Dict[str, Any]],
           summary="Obtenir le dictionnaire complet des embedders",
           description="Retourne le dictionnaire complet qui mappe nom -> propriétés")
async def get_embedders_dict():
    """Retourne le dictionnaire complet des embedders.
    
    Returns:
        Dictionnaire {nom: propriétés} de tous les embedders
    """
    return get_embedders()


@router.post("/index/documents",
           summary="Indexer les documents PDF valides depuis M3C",
           description="Télécharge les PDFs valides depuis M3C, les découpe en chunks et indexe avec embeddings")
async def index_existing_documents(embedder_name: str, chunk_size: int = 1000, chunk_overlap: int = 200):
    """
    Indexe les documents PDF valides depuis M3C.
    
    Args:
        embedder_name: Nom de l'embedder à utiliser
        chunk_size: Taille des chunks en caractères
        chunk_overlap: Recouvrement entre chunks
        
    Returns:
        Résultat de l'indexation avec statistiques
    """
    embedder = get_embedder_instance(embedder_name)
    
    result = await _index_from_valid_pdf(
        embedder=embedder,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    return {
        "success": len(result["errors"]) == 0,
        "processed_documents": result["processed_documents"],
        "chunks_created": result["chunks_created"],
        "embeddings_generated": result["embeddings_generated"],
        "errors": result["errors"],
        "timestamp": datetime.now().isoformat()
    }


async def _index_from_valid_pdf(
    embedder,
    chunk_size: int,
    chunk_overlap: int
) -> Dict[str, Any]:
    """
    Indexe les PDF valides depuis M3C selon le pipeline du README.
    
    Args:
        embedder: Instance de BaseEmbedder pour generer les embeddings
        chunk_size: Taille maximale des chunks en caracteres
        chunk_overlap: Nombre de caracteres de recouvrement
        
    Returns:
        Dict avec processed_documents, chunks_created, embeddings_generated, errors
    """
    from database.database import (
        VALID_TEXT_RESOURCE_ID,
        get_pdf_url_for_resource,
        insert_chunks,
        insert_chunk_embeddings_batch_qdrant,
        get_db_connection
    )
    
    results = {
        "processed_documents": 0,
        "chunks_created": 0,
        "embeddings_generated": 0,
        "errors": []
    }
    
    conn = None
    try:
        conn = await get_db_connection()
        
        for resource_id in VALID_TEXT_RESOURCE_ID:
            temp_path = None
            try:
                pdf_url = await get_pdf_url_for_resource(resource_id)
                if not pdf_url:
                    results["errors"].append(f"Resource {resource_id}: URL non trouvee")
                    continue
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(pdf_url) as response:
                        if response.status != 200:
                            results["errors"].append(f"Resource {resource_id}: HTTP {response.status}")
                            continue
                        pdf_content = await response.read()
                
                temp_dir = Path("temp_pdfs")
                temp_dir.mkdir(exist_ok=True)
                temp_path = temp_dir / f"{resource_id}.pdf"
                
                with open(temp_path, 'wb') as f:
                    f.write(pdf_content)
                
                loader = PyPDFLoader(str(temp_path))
                documents = loader.load()
                
                if not documents:
                    results["errors"].append(f"Resource {resource_id}: Aucun document charge")
                    continue
                
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
                chunks = text_splitter.split_documents(documents)
                
                if not chunks:
                    results["errors"].append(f"Resource {resource_id}: Aucun chunk genere")
                    continue
                
                document_id = f"m3c_{resource_id}"
                strategy_id = 7
                
                chunks_data = []
                embeddings_batch = []
                
                for i, chunk in enumerate(chunks):
                    chunk_id = f"{document_id}-{strategy_id}-{i}"
                    page_num = chunk.metadata.get("page", 0) + 1
                    chunk_content = chunk.page_content
                    
                    chunks_data.append((
                        chunk_id,
                        document_id,
                        strategy_id,
                        chunk_content,
                        page_num,
                        i,
                        len(chunk_content),
                        json.dumps({"source": f"m3c_{resource_id}", "page": page_num})
                    ))
                    
                    try:
                        embedding = embedder.embed(chunk_content)
                        embeddings_batch.append({
                            "chunk_id": chunk_id,
                            "document_id": document_id,
                            "model_name": embedder.name,
                            "embedding": embedding,
                            "content": chunk_content,
                            "num_page": page_num,
                            "position_in_page": i,
                            "token_count": len(chunk_content),
                            "metadata": {"source": f"m3c_{resource_id}", "page": page_num}
                        })
                    except Exception as e:
                        results["errors"].append(f"Resource {resource_id} chunk {i}: {str(e)}")
                
                if chunks_data:
                    await insert_chunks(conn, chunks_data)
                    results["chunks_created"] += len(chunks_data)
                
                if embeddings_batch:
                    await insert_chunk_embeddings_batch_qdrant(embeddings_batch)
                    results["embeddings_generated"] += len(embeddings_batch)
                
                results["processed_documents"] += 1
                
            except Exception as e:
                results["errors"].append(f"Resource {resource_id}: {str(e)}")
            finally:
                if temp_path and temp_path.exists():
                    try:
                        temp_path.unlink()
                    except:
                        pass
        
        return results
        
    finally:
        if conn:
            await conn.close()

