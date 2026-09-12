"""
Modèles Pydantic pour les requêtes et réponses Solr.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class SolrIndexRequest(BaseModel):
    """Modèle de requête pour lancer un job d'indexation Solr"""
    solr_core: Optional[str] = Field(
        "m3c", 
        description="Nom du core Solr où indexer les documents"
    )
    batch_size: int = Field(
        50, 
        description="Nombre de documents à indexer par batch", 
        ge=1, 
        le=1000
    )
    resource_ids: Optional[List[int]] = Field(
        None, 
        description="Liste spécifique de resource_id à indexer. Si None, utilise VALID_TEXT_RESOURCE_ID"
    )
    commit: bool = Field(
        True, 
        description="Effectuer un commit après chaque batch"
    )
    clear_index: bool = Field(
        False, 
        description="Effacer l'index avant l'indexation (ATTENTION: supprime tout)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "solr_core": "m3c",
                "batch_size": 50,
                "resource_ids": [116723, 116789],
                "commit": True,
                "clear_index": False
            }
        }
    }


class SolrIndexResponse(BaseModel):
    """Modèle de réponse pour un job d'indexation Solr"""
    success: bool = Field(..., description="Indique si le job a été lancé avec succès")
    job_id: str = Field(..., description="ID unique du job d'indexation")
    message: str = Field(..., description="Message de statut")
    total_items: int = Field(0, description="Nombre total de documents à indexer")
    solr_core: str = Field(..., description="Nom du core Solr cible")
    status: str = Field(..., description="Statut actuel du job")
    created_at: str = Field(..., description="Date de création du job")


class SolrIndexStatusResponse(BaseModel):
    """Modèle de réponse pour le statut d'un job d'indexation Solr"""
    job_id: str = Field(..., description="ID unique du job")
    job_type: str = Field(..., description="Type de job")
    status: str = Field(..., description="Statut du job (pending, running, completed, failed, cancelled)")
    total_items: int = Field(0, description="Nombre total de documents à traiter")
    processed_items: int = Field(0, description="Nombre de documents déjà traités")
    progress: Optional[Dict[str, Any]] = Field(
        None, 
        description="Progression détaillée par document"
    )
    error_message: Optional[str] = Field(
        None, 
        description="Message d'erreur si le job a échoué"
    )
    parameters: Dict[str, Any] = Field(
        {}, 
        description="Paramètres du job"
    )
    created_at: str = Field(..., description="Date de création")
    updated_at: str = Field(..., description="Date de dernière mise à jour")


class SolrIndexJobListResponse(BaseModel):
    """Modèle de réponse pour la liste des jobs d'indexation Solr"""
    jobs: List[SolrIndexStatusResponse] = Field(..., description="Liste des jobs")
    count: int = Field(0, description="Nombre total de jobs")


class SolrIndexCancelResponse(BaseModel):
    """Modèle de réponse pour l'annulation d'un job"""
    success: bool = Field(..., description="Indique si l'annulation a réussi")
    job_id: str = Field(..., description="ID du job concerné")
    message: str = Field(..., description="Message de statut")
    previous_status: str = Field(..., description="Statut précédent du job")
