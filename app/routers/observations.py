"""Router FastAPI pour les observations de lecture de documents.

Regroupe les routes /api/observations/* (ouverture et fermeture d'une
session de lecture d'un document PDF). Ces routes taient auparavant
dfinies dans api_server.py.
"""
from typing import Dict, Literal, Optional

from fastapi import APIRouter, Cookie, HTTPException, status
from pydantic import BaseModel, Field

import auth
from database.database import (
    get_db_connection,
    start_document_reading_session,
    close_document_reading_session,
    record_document_reading_open_observation,
    complete_document_reading_observation,
)

router = APIRouter(prefix="/api/observations", tags=["Observations"])


class DocumentReadingOpenRequest(BaseModel):
    """Modle de requte pour enregistrer l'ouverture d'un document PDF"""
    resource_id: int = Field(..., description="resource_id (table value) du document ouvert", ge=1)
    num_page: Optional[int] = Field(None, description="Numro de page cibl  l'ouverture", ge=1)
    anonymous_id: Optional[str] = Field(None, description="Identifiant anonyme persistant (localStorage), ignor si l'utilisateur est connect")
    metadata: Optional[Dict] = Field(None, description="Mtadonnes supplmentaires (session RAG, page d'origine, etc.)")


class DocumentReadingCloseRequest(BaseModel):
    """Modle de requte pour enregistrer la fermeture d'un document PDF"""
    reading_session_id: int = Field(..., description="Identifiant de la session de lecture  clore", ge=1)
    close_reason: Literal["button", "document_change", "page_hide"] = Field(
        "page_hide", description="vnement ayant dclench la fermeture: button, document_change, page_hide")


class DocumentReadingOpenResponse(BaseModel):
    reading_session_id: int = Field(..., description="Identifiant de la session de lecture cre")
    observation_id: Optional[int] = Field(None, description="Identifiant de l'observation de lecture cre (table observations)")


class DocumentReadingCloseResponse(BaseModel):
    reading_session_id: int = Field(..., description="Identifiant de la session de lecture close")
    closed_at: str = Field(..., description="Timestamp de fermeture")
    duration_seconds: int = Field(..., description="Dure de lecture en secondes")


@router.post("/document-open", response_model=DocumentReadingOpenResponse)
async def open_document_observation(
    request: DocumentReadingOpenRequest,
    m3c_api_key: Optional[str] = Cookie(default=None),
):
    """
    Enregistre l'ouverture d'un document PDF dans la table document_reading_sessions.
    Si l'utilisateur est authentifi via le cookie de session, son user_id (int) est
    enregistr et l'identifiant anonyme est ignor. Sinon, l'identifiant anonyme
    persistant fourni par le client est utilis.
    """
    user_id = auth.user_id_from_token(m3c_api_key)
    anonymous_id = None if user_id is not None else request.anonymous_id
    async with await get_db_connection() as conn :
        reading_session_id = await start_document_reading_session(
            conn,
            resource_id=request.resource_id,
            user_id=user_id,
            anonymous_id=anonymous_id,
            num_page=request.num_page,
            metadata=request.metadata,
        )
        if reading_session_id is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Erreur lors de l'enregistrement de l'ouverture du document.")
        observation_id = await record_document_reading_open_observation(
            conn,
            user_id=user_id,
            anonymous_id=anonymous_id,
            resource_id=request.resource_id,
            num_page=request.num_page,
            reading_session_id=reading_session_id,
            metadata=request.metadata,
        )
        return DocumentReadingOpenResponse(
            reading_session_id=reading_session_id,
            observation_id=observation_id,
        )



@router.post("/document-close", response_model=DocumentReadingCloseResponse)
async def close_document_observation(request: DocumentReadingCloseRequest):
    """
    Enregistre la fermeture d'une session de lecture de document PDF.
    La dure de lecture est calcule ct serveur  partir de opened_at.
    Compatible avec navigator.sendBeacon (Content-Type: application/json).
    """
    async with await get_db_connection() as conn:
        result = await close_document_reading_session(
            conn,
            reading_session_id=request.reading_session_id,
            close_reason=request.close_reason,
        )
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Session de lecture introuvable ou dj ferme.")
        await complete_document_reading_observation(
            conn,
            reading_session_id=request.reading_session_id,
            duration_seconds=result["duration_seconds"],
            close_reason=request.close_reason,
        )
    return DocumentReadingCloseResponse(
        reading_session_id=request.reading_session_id,
        closed_at=result["closed_at"],
        duration_seconds=result["duration_seconds"],
    )
