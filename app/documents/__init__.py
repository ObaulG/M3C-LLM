"""
Router de consultation des documents et de leurs chunks.

Endpoints exposes sous le prefixe /api/documents :
- GET /                : liste des documents (metadonnees de base)
- GET /{document_id}/chunks : chunks d'un document (contenu + metadonnees)
"""
from .router import router
from .models import DocumentResponse, DocumentsListResponse

__all__ = ["router", "DocumentResponse", "DocumentsListResponse"]
