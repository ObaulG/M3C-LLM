"""
Modèles Pydantic pour la gestion des jobs d'indexation.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class IndexDocumentsRequest(BaseModel):
    """Requête pour l'indexation des documents existants"""
    indexation_type: str = Field(
        ...,
        description="Type d'indexation: 'metadata-only' pour TOUS les docs par métadonnées, 'selected-metadata' pour une sélection de docs par métadonnées, 'all-with-text' pour docs avec extracted_text, 'pdf-from-m3c' pour télécharger depuis M3C",
        pattern="^(metadata-only|selected-metadata|all-metadata|all-with-text|pdf-from-m3c)$"
    )
    resource_ids: Optional[List[int]] = Field(
        None,
        description="Liste des resource_ids à indexer (requis pour 'selected-metadata', ignoré sinon)"
    )
    chunk_size: int = Field(
        2700,
        description="Taille des chunks en caractères (utilisé pour 'all-with-text' et 'pdf-from-m3c')",
        ge=100,
        le=10000
    )
    chunk_overlap: int = Field(
        400,
        description="Recouvrement entre chunks en caractères (utilisé pour 'all-with-text' et 'pdf-from-m3c')",
        ge=0,
        le=5000
    )
    force_restart: bool = Field(
        False,
        description="Forcer le redémarrage même si un job existe (utilisé pour 'pdf-from-m3c')"
    )
    embedder_name: Optional[str] = Field(
        None,
        description="Nom du modèle d'embedding à utiliser (ex: 'mistral-embed', 'docker-BAAI/bge-large-en-v1.5')"
    )


class IndexDocumentsResponse(BaseModel):
    """Réponse pour l'indexation des documents"""
    success: bool = Field(..., description="Indique si l'indexation a réussi")
    processed_documents: int = Field(..., description="Nombre de documents traités")
    chunks_created: int = Field(0, description="Nombre de chunks créés")
    embeddings_generated: int = Field(0, description="Nombre d'embeddings générés")
    chunks_by_document: Dict[str, int] = Field(
        default_factory=dict,
        description="Nombre de chunks créés par document"
    )
    errors: List[str] = Field(default_factory=list, description="Liste des erreurs éventuelles")
    timestamp: str = Field(..., description="Horodatage de la réponse")


class IndexJobRequest(BaseModel):
    """Requête pour créer un job d'indexation de PDFs depuis M3C"""
    indexation_type: str = Field(
        "pdf-from-m3c",
        description="Type d'indexation: 'pdf-from-m3c' pour télécharger depuis M3C, 'metadata-only' pour les métadonnées, 'selected-metadata' pour les métadonnées d'une sélection",
        pattern="^(pdf-from-m3c|metadata-only|selected-metadata)$"
    )
    resource_ids: Optional[List[int]] = Field(
        None,
        description="Liste des resource_ids à indexer (utilisé pour 'selected-metadata')"
    )
    chunk_size: int = Field(
        2700,
        description="Taille des chunks en caractères",
        ge=100,
        le=10000
    )
    chunk_overlap: int = Field(
        400,
        description="Recouvrement entre chunks en caractères",
        ge=0,
        le=5000
    )
    force_restart: bool = Field(
        False,
        description="Forcer le redémarrage même si un job existe déjà"
    )
    embedder_name: Optional[str] = Field(
        None,
        description="Nom du modèle d'embedding à utiliser"
    )


class IndexJobStatusResponse(BaseModel):
    """Statut d'un job d'indexation"""
    job_id: str = Field(..., description="Identifiant unique du job")
    job_type: str = Field(..., description="Type de job")
    status: str = Field(..., description="Statut actuel du job")
    total_items: int = Field(..., description="Nombre total d'éléments à traiter")
    processed_items: int = Field(..., description="Nombre d'éléments déjà traités")
    progress: Dict[str, Any] = Field(
        default_factory=dict,
        description="Progression détaillée par resource_id"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Paramètres du job"
    )
    created_at: str = Field(..., description="Date de création du job")
    updated_at: str = Field(..., description="Dernière mise à jour")
    error_message: Optional[str] = Field(
        None,
        description="Message d'erreur si le job a échoué"
    )


class IndexJobControlResponse(BaseModel):
    """Réponse pour les opérations de contrôle de job"""
    success: bool = Field(..., description="Indique si l'opération a réussi")
    job_id: Optional[str] = Field(
        None,
        description="Identifiant du job"
    )
    message: str = Field(..., description="Message de retour")
    job_status: Optional[IndexJobStatusResponse] = Field(
        None,
        description="Statut du job si applicable"
    )


class IndexJobListResponse(BaseModel):
    """Réponse pour la liste des jobs"""
    jobs: List[IndexJobStatusResponse] = Field(
        default_factory=list,
        description="Liste des jobs"
    )
    count: int = Field(..., description="Nombre total de jobs")


class IndexedDocumentStatus(BaseModel):
    """État d'indexation d'un document"""
    resource_id: str = Field(..., description="Identifiant de la ressource M3C")
    document_id: Optional[int] = Field(
        None,
        description="Identifiant interne du document (text_documents.id)"
    )
    title: Optional[str] = Field(None, description="Titre du document")
    creator: Optional[str] = Field(None, description="Auteur du document")
    chunks_count: int = Field(
        0,
        description="Nombre de chunks créés pour ce document"
    )
    content_embedders: List[str] = Field(
        default_factory=list,
        description="Embedders utilisés pour indexer le contenu (collections LD-*)"
    )
    metadata_embedders: List[str] = Field(
        default_factory=list,
        description="Embedders utilisés pour indexer les métadonnées (collections MD-*)"
    )
    metadata_indexed: bool = Field(
        False,
        description="Indique si les métadonnées de ce document ont été indexées"
    )


class IndexedDocumentsStatusResponse(BaseModel):
    """Réponse pour l'état d'indexation des documents"""
    documents: List[IndexedDocumentStatus] = Field(
        default_factory=list,
        description="État d'indexation de chaque document"
    )
    count: int = Field(..., description="Nombre total de documents indexés")
