"""Router FastAPI pour les retours utilisateurs sur les réponses du chatbot.

Regroupe les routes /api/feedback/* : soumission d'un retour (échelles 1-5 +
commentaire libre) et consultation du retour existant pour un message.

Un message_id ne peut recevoir qu'un seul feedback (contrainte UNIQUE en BDD) :
en cas de double soumission, la route renvoie 409 Conflict.
"""
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, status
from pydantic import BaseModel, Field

import auth
from database.chatbot_feedback_db import (
    insert_chatbot_feedback,
    get_chatbot_feedback,
    chatbot_message_exists,
)

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])


class FeedbackRequest(BaseModel):
    """Modèle de requête pour soumettre un retour sur une réponse du chatbot."""
    message_id: str = Field(..., description="Identifiant du message commenté (UUID)")
    rating_response: Optional[int] = Field(
        None, description="Note 1-5 : 'La réponse vous convient-elle ?'", ge=1, le=5
    )
    rating_relevance: Optional[int] = Field(
        None,
        description="Note 1-5 : 'Les documents fournis sont-ils pertinents par rapport à votre question ?'",
        ge=1, le=5,
    )
    rating_formulation: Optional[int] = Field(
        None,
        description="Note 1-5 : 'Êtes-vous satisfait de la formulation de la réponse ?'",
        ge=1, le=5,
    )
    comment: Optional[str] = Field(
        None, description="Commentaire libre (non modéré)"
    )
    anonymous_id: Optional[str] = Field(
        None,
        description="Identifiant anonyme persistant (localStorage), ignoré si l'utilisateur est connecté",
    )


class FeedbackResponse(BaseModel):
    """Modèle de réponse après soumission d'un retour."""
    feedback_id: int = Field(..., description="Identifiant du feedback créé")
    message_id: str = Field(..., description="Identifiant du message commenté")


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    request: FeedbackRequest,
    m3c_api_key: Optional[str] = Cookie(default=None),
):
    """
    Soumet un retour utilisateur sur une réponse du chatbot.

    Au moins un des trois ratings ou un commentaire doit être fourni. Si
    l'utilisateur est authentifié via le cookie de session, son user_id est
    enregistré et l'identifiant anonyme est ignoré. Sinon, l'identifiant
    anonyme persistant fourni par le client est utilisé.

    Un message_id ne peut recevoir qu'un seul feedback : en cas de double
    soumission, renvoie 409 Conflict.
    """
    # Validation : au moins un rating ou un commentaire non vide
    has_rating = any(v is not None for v in (
        request.rating_response,
        request.rating_relevance,
        request.rating_formulation,
    ))
    has_comment = request.comment is not None and request.comment.strip() != ""
    if not has_rating and not has_comment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Au moins une note ou un commentaire doit être fourni.",
        )

    # Vérifier que le message existe
    if not await chatbot_message_exists(request.message_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucun message trouvé pour message_id={request.message_id}.",
        )

    # Déterminer l'utilisateur : user_id si connecté, sinon anonymous_id
    user_id = auth.user_id_from_token(m3c_api_key)
    if user_id is None:
        user_id = request.anonymous_id

    try:
        feedback_id = await insert_chatbot_feedback(
            message_id=request.message_id,
            user_id=user_id,
            rating_response=request.rating_response,
            rating_relevance=request.rating_relevance,
            rating_formulation=request.rating_formulation,
            comment=request.comment,
        )
    except Exception as e:
        # IntegrityError (UNIQUE(message_id) violé) → 409 Conflict
        # aiomysql.IntegrityError est une sous-classe de pymysql.IntegrityError
        integrity_error_names = {"IntegrityError"}
        if type(e).__name__ in integrity_error_names or "Duplicate" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un retour existe déjà pour ce message.",
            )
        print(f"Erreur lors de l'insertion du feedback pour {request.message_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'enregistrement du retour.",
        )

    if feedback_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'enregistrement du retour.",
        )

    return FeedbackResponse(feedback_id=feedback_id, message_id=request.message_id)


@router.get("/{message_id}")
async def get_feedback(message_id: str):
    """
    Récupère le retour existant pour un message, s'il existe.

    Permet au widget de pré-remplir les champs si l'utilisateur revient sur
    une réponse déjà commentée (le feedback est unique par message).
    """
    feedback = await get_chatbot_feedback(message_id)
    if feedback is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucun retour trouvé pour message_id={message_id}.",
        )
    return feedback
