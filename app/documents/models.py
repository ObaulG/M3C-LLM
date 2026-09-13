"""Modeles Pydantic pour la consultation des documents et de leurs chunks."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    """Modele de reponse pour un document contenant les informations de base."""
    document_id: int = Field(..., description="Identifiant du document (item, ou document_id")
    source_id: Optional[int] = Field(..., description="Identifiant de la ressource pour requeter le pdf")
    file_name: str = Field(..., description="Nom du fichier")
    title: str = Field(..., description="Titre du document")
    author: str = Field(..., description="Auteur du document")
    created_at: str = Field(..., description="Date de creation")
    updated_at: str = Field(..., description="Date de mise a jour")


class DocumentsListResponse(BaseModel):
    """Modele de reponse pour la liste des documents."""
    documents: List[DocumentResponse] = Field(..., description="Liste des documents")
    count: int = Field(..., description="Nombre total de documents")
    timestamp: str = Field(..., description="Horodatage de la reponse")
