"""
Router FastAPI pour la consultation des documents et de leurs chunks.

Regroupe les routes permettant de :
- lister tous les documents disponibles avec leurs metadonnees (get_document_list),
- lister les chunks d'un document donne avec leur contenu (get_document_chunks).

Ces routes etaient auparavant eclatees entre api_server.py (liste des documents)
et knowledge_items/router.py (chunks d'un document). Elles sont desormais exposees
sous un prefixe commun /api/documents pour servir les pages HTML de l'interface.
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from database.database import (
    get_db_connection,
    get_all_documents,
    get_all_text_chunks,
)

from .models import DocumentResponse, DocumentsListResponse

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.get(
    "",
    response_model=DocumentsListResponse,
    summary="Liste des documents",
    description=(
        "Recupere la liste de tous les documents disponibles dans la base de donnees, "
        "avec leurs metadonnees (document_id, source_id, file_name, title, author, "
        "dates de creation/mise a jour)."
    ),
)
async def get_document_list():
    """Recupere la liste de tous les documents disponibles dans la base de donnees."""
    try:
        async with await get_db_connection() as conn:
            documents = await get_all_documents(conn)

        document_responses = []
        for doc in documents:
            document_responses.append(DocumentResponse(
                document_id=doc["document_id"],
                source_id=doc["resource_id"],
                file_name=doc["file_name"],
                title=doc["title"],
                author=doc["creator"],
                created_at=str(doc["created_at"]),
                updated_at=str(doc["updated_at"])
            ))

        return DocumentsListResponse(
            documents=document_responses,
            count=len(document_responses),
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR lors de la recuperation des documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recuperation des documents: {str(e)}"
        )


@router.get(
    "/{document_id}/chunks",
    summary="Liste les chunks d'un document",
    description=(
        "Retourne tous les chunks d'un document avec leur contenu "
        "(id, content, num_page, position_in_page, character_count, token_count, "
        "document_id) pour permettre la selection d'un chunk precis."
    ),
)
async def get_document_chunks(document_id: int):
    """Recupere tous les chunks d'un document avec leur contenu."""
    async with await get_db_connection() as conn:
        chunks = await get_all_text_chunks(conn, document_id)

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucun chunk trouve pour le document {document_id}",
        )

    return JSONResponse(content={
        "document_id": document_id,
        "chunks": chunks,
        "count": len(chunks),
    })
