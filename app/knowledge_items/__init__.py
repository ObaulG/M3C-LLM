"""Package knowledge_items : génération de knowledge_items à partir de chunks.

Endpoints exposés sous le préfixe /api/admin/knowledge-items :
- GET  /valid-documents         : liste des documents validés
- GET  /documents/{id}/chunks   : chunks d'un document
- POST /generate                : génération de knowledge_items via LLM pour un chunk
- POST /save                   : sauvegarde en base (knowledge_items + relations)
- GET  /items                   : liste des knowledge_items déjà en base
"""
from .router import router

__all__ = ["router"]
