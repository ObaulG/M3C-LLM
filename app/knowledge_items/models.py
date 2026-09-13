"""Modèles Pydantic pour la génération de knowledge_items à partir de chunks.

Conforme au schéma défini dans app/database/user_knowledge_model.sql
(section 2 : knowledge_items, knowledge_item_entities, knowledge_item_themes,
knowledge_sources, et tables de référence entities / themes / knowledge_resources).
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class EntityCandidateModel(BaseModel):
    """Candidat d'entité associé à une connaissance extraite."""
    name: str = Field(..., description="Nom complet de l'entité")
    type: str = Field(
        default="other",
        description="Type d'entité: person, place, work, event, practice, other"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confiance 0-1")


class ThemeCandidateModel(BaseModel):
    """Candidat de thème associé à une connaissance extraite."""
    name: str = Field(..., description="Nom du thème")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confiance 0-1")


class SourceReferenceModel(BaseModel):
    """Référence vers la source d'une connaissance (chunk/document)."""
    document_id: Optional[str] = Field(default=None, description="Identifiant du document")
    chunk_id: Optional[str] = Field(default=None, description="Identifiant du chunk")
    excerpt: str = Field(default="", description="Extrait exact de la source")
    page: Optional[int] = Field(default=None, description="Numéro de page")
    position_in_page: Optional[int] = Field(default=None, description="Position dans la page")
    position_start: int = Field(default=0, description="Position de début (0-based)")
    position_end: int = Field(default=0, description="Position de fin (0-based)")
    uri: Optional[str] = Field(default=None, description="URI spécifique de la source")


class KnowledgeItemModel(BaseModel):
    """Un knowledge_item candidat extrait par le LLM.

    Les champs correspondent à la table knowledge_items et à ses relations
    (entities, themes, sources) définies dans user_knowledge_model.sql.
    """
    proposition: str = Field(..., description="Proposition ou information formulée et vérifiable")
    summary: Optional[str] = Field(default=None, description="Résumé ou titre court")
    entities: List[EntityCandidateModel] = Field(
        default_factory=list, description="Entités associées (knowledge_item_entities)"
    )
    themes: List[ThemeCandidateModel] = Field(
        default_factory=list, description="Thèmes associés (knowledge_item_themes)"
    )
    source_reference: SourceReferenceModel = Field(
        default_factory=SourceReferenceModel,
        description="Référence à la source (knowledge_sources)"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confiance 0-1")
    is_verified: bool = Field(default=False, description="La connaissance a-t-elle été vérifiée")
    verification_notes: Optional[str] = Field(default=None, description="Notes de vérification")


class KnowledgeGenerationRequest(BaseModel):
    """Requête pour générer des knowledge_items à partir d'un chunk."""
    chunk_id: int = Field(..., description="ID du chunk (text_chunks.id) à analyser")
    document_id: Optional[int] = Field(
        default=None,
        description="ID du document (text_documents.id) auquel appartient le chunk"
    )
    model: str = Field(
        default="mistral-medium",
        description="Modèle LLM à utiliser pour l'extraction"
    )


class KnowledgeGenerationResponse(BaseModel):
    """Réponse contenant les knowledge_items générés pour un chunk."""
    chunk_id: int = Field(..., description="ID du chunk analysé")
    document_id: Optional[int] = Field(default=None, description="ID du document")
    model: str = Field(..., description="Modèle LLM utilisé")
    knowledge_items: List[KnowledgeItemModel] = Field(
        default_factory=list, description="knowledge_items extraits"
    )
    count: int = Field(default=0, description="Nombre de knowledge_items extraits")
    generation_time: float = Field(..., description="Temps de génération en secondes")


class KnowledgeSaveRequest(BaseModel):
    """Requête pour sauvegarder des knowledge_items en base (table knowledge_items et relations)."""
    knowledge_items: List[KnowledgeItemModel] = Field(
        ..., description="knowledge_items à sauvegarder"
    )
    chunk_id: Optional[int] = Field(
        default=None,
        description="ID du chunk source, pour constituer le titre de la ressource"
    )
    document_id: Optional[int] = Field(
        default=None,
        description="ID du document source (text_documents.id)"
    )
    resource_title: Optional[str] = Field(
        default=None,
        description="Titre de la ressource knowledge_resources. Si None, construit à partir du document."
    )
    resource_uri: Optional[str] = Field(default=None, description="URI optionnelle de la ressource")
    resource_type: str = Field(
        default="chunk",
        description="Type de ressource (knowledge_resources.resource_type)"
    )


class KnowledgeSaveResult(BaseModel):
    """Résultat de la sauvegarde d'un knowledge_item."""
    knowledge_id: int = Field(..., description="ID du knowledge_items créé/récupéré")
    proposition: str = Field(..., description="Proposition sauvegardée")
    entities_count: int = Field(default=0, description="Nombre d'entités liées")
    themes_count: int = Field(default=0, description="Nombre de thèmes liés")
    source_saved: bool = Field(default=False, description="Une source a-t-elle été enregistrée")


class KnowledgeSaveResponse(BaseModel):
    """Réponse de la sauvegarde de knowledge_items."""
    success: bool = Field(..., description="Succès de l'opération")
    resource_id: Optional[int] = Field(
        default=None, description="ID de la ressource knowledge_resources créée/récupérée"
    )
    saved_ids: List[int] = Field(
        default_factory=list, description="IDs des knowledge_items sauvegardés"
    )
    results: List[KnowledgeSaveResult] = Field(
        default_factory=list, description="Détail par knowledge_item"
    )
    count: int = Field(default=0, description="Nombre de knowledge_items sauvegardés")
    message: str = Field(default="", description="Message de confirmation")
