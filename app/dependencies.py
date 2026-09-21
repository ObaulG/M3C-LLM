"""Dépendances FastAPI partagées.

Fournissent aux endpoints les instances applicatives (pipeline RAG,
évaluateurs) stockées sur ``app.state`` par le lifespan, à la place de
variables globales de module.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from rag_pipeline import RAGPipeline


def get_rag_pipeline(request: Request) -> RAGPipeline:
    """Retourne le pipeline RAG initialisé, ou 503 s'il ne l'est pas encore."""
    pipeline = getattr(request.app.state, "rag_pipeline", None)
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le système RAG n'est pas encore initialisé. Veuillez réessayer dans quelques instants.",
        )
    return pipeline


RagPipelineDep = Annotated[RAGPipeline, Depends(get_rag_pipeline)]
