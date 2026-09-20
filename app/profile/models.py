"""
Modèles Pydantic pour la page de profil utilisateur.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class KnowledgeStatus(str, Enum):
    """Statut d'une connaissance pour un utilisateur."""
    UNKNOWN = "unknown"
    ENCOUNTERED = "encountered"
    DEVELOPING = "developing"
    DEMONSTRATED = "demonstrated"


class ObservationType(str, Enum):
    """Type d'observation."""
    DECLARATIVE = "declarative"
    BEHAVIORAL = "behavioral"
    EVALUATIVE = "evaluative"


# ============================================================================
# Modèles pour les statistiques
# ============================================================================

class ProfileStats(BaseModel):
    """Statistiques globales du profil utilisateur."""
    user_id: str = Field(..., description="Identifiant de l'utilisateur")
    total_observations: int = Field(default=0, description="Nombre total d'observations")
    total_resource_views: int = Field(default=0, description="Nombre total de vues de ressources")
    total_theme_views: int = Field(default=0, description="Nombre total de vues de thèmes")
    total_evaluations: int = Field(default=0, description="Nombre total d'évaluations")
    total_resources_visited: int = Field(default=0, description="Nombre de ressources différentes consultées")
    total_themes_explored: int = Field(default=0, description="Nombre de thèmes différents explorés")
    total_knowledge_items_encountered: int = Field(default=0, description="Nombre total d'éléments de connaissance rencontrés")
    total_knowledge_demonstrated: int = Field(default=0, description="Nombre d'éléments de connaissance maîtrisés")
    total_knowledge_developing: int = Field(default=0, description="Nombre d'éléments de connaissance en développement")
    total_knowledge_encountered: int = Field(default=0, description="Nombre d'éléments de connaissance rencontrés")
    total_knowledge_unknown: int = Field(default=0, description="Nombre d'éléments de connaissance inconnus")
    first_visit: Optional[datetime] = Field(default=None, description="Date de première visite")
    last_visit: Optional[datetime] = Field(default=None, description="Date de dernière visite")
    profile_created_at: Optional[datetime] = Field(default=None, description="Date de création du profil")
    profile_last_activity: Optional[datetime] = Field(default=None, description="Dernière activité du profil")


# ============================================================================
# Modèles pour les ressources consultées
# ============================================================================

class VisitedResource(BaseModel):
    """Une ressource consultée par l'utilisateur."""
    resource_id: int = Field(..., description="ID de la ressource")
    resource_title: str = Field(..., description="Titre de la ressource")
    resource_uri: Optional[str] = Field(default=None, description="URI de la ressource")
    resource_type: Optional[str] = Field(default=None, description="Type de ressource (pdf, web, book, etc.)")
    author: Optional[str] = Field(default=None, description="Auteur de la ressource")
    publication_date: Optional[str] = Field(default=None, description="Date de publication")
    view_count: int = Field(default=0, description="Nombre de consultations")
    last_viewed_at: Optional[datetime] = Field(default=None, description="Date de dernière consultation")
    first_viewed_at: Optional[datetime] = Field(default=None, description="Date de première consultation")
    avg_confidence: float = Field(default=0.0, description="Confiance moyenne des observations")


# ============================================================================
# Modèles pour les thèmes
# ============================================================================

class ThemeStats(BaseModel):
    """Statistiques pour un thème exploré par l'utilisateur."""
    theme_id: int = Field(..., description="ID du thème")
    theme_name: str = Field(..., description="Nom du thème")
    theme_description: Optional[str] = Field(default=None, description="Description du thème")
    interest_weight: float = Field(default=0.0, description="Poids d'intérêt (0-1)")
    interest_confidence: float = Field(default=0.0, description="Confiance dans l'intérêt (0-1)")
    observation_count: int = Field(default=0, description="Nombre d'observations liées à ce thème")
    behavioral_count: int = Field(default=0, description="Nombre d'observations comportementales")
    evaluative_count: int = Field(default=0, description="Nombre d'observations évaluatives")
    knowledge_items_count: int = Field(default=0, description="Nombre d'éléments de connaissance associés")
    demonstrated_count: int = Field(default=0, description="Nombre de connaissances maîtrisées")
    developing_count: int = Field(default=0, description="Nombre de connaissances en développement")
    encountered_count: int = Field(default=0, description="Nombre de connaissances rencontrées")
    unknown_count: int = Field(default=0, description="Nombre de connaissances inconnues")
    last_interaction_at: Optional[datetime] = Field(default=None, description="Dernière interaction avec ce thème")
    first_interaction_at: Optional[datetime] = Field(default=None, description="Première interaction avec ce thème")


# ============================================================================
# Modèles pour les éléments de connaissance
# ============================================================================

class EntityInfo(BaseModel):
    """Information sur une entité liée à une connaissance."""
    entity_id: int = Field(..., description="ID de l'entité")
    entity_name: str = Field(..., description="Nom de l'entité")
    entity_type: str = Field(..., description="Type d'entité (person, place, work, event, practice, other)")
    relevance: float = Field(default=1.0, description="Pertinence de l'entité pour cette connaissance (0-1)")


class SourceInfo(BaseModel):
    """Information sur une source d'une connaissance."""
    source_id: Optional[int] = Field(default=None, description="ID de la ressource source")
    excerpt: Optional[str] = Field(default=None, description="Extrait de la source")
    page: Optional[str] = Field(default=None, description="Page ou section dans la source")
    confidence: float = Field(default=1.0, description="Confiance dans cette source (0-1)")
    resource_title: Optional[str] = Field(default=None, description="Titre de la ressource")


class KnowledgeItem(BaseModel):
    """Un élément de connaissance avec ses métadonnées."""
    knowledge_id: int = Field(..., description="ID de la connaissance")
    proposition: str = Field(..., description="Proposition ou information formulée")
    summary: Optional[str] = Field(default=None, description="Résumé ou titre court")
    status: KnowledgeStatus = Field(default=KnowledgeStatus.UNKNOWN, description="Statut de la connaissance pour l'utilisateur")
    score: float = Field(default=0.0, description="Score de maîtrise estimée (0-1)")
    confidence: float = Field(default=0.5, description="Confiance dans cette estimation (0-1)")
    last_interaction_at: Optional[datetime] = Field(default=None, description="Dernière interaction avec cette connaissance")
    created_at: Optional[datetime] = Field(default=None, description="Date de première détection")
    entities: List[EntityInfo] = Field(default_factory=list, description="Entités liées à cette connaissance")
    sources: List[SourceInfo] = Field(default_factory=list, description="Sources de cette connaissance")


class ThemeKnowledgeGroup(BaseModel):
    """Groupe de connaissances pour un thème."""
    theme_id: int = Field(..., description="ID du thème")
    theme_name: str = Field(..., description="Nom du thème")
    knowledge_items: List[KnowledgeItem] = Field(default_factory=list, description="Liste des éléments de connaissance pour ce thème")


# ============================================================================
# Modèles pour le profil utilisateur
# ============================================================================

class UserProfile(BaseModel):
    """Profil utilisateur de base."""
    user_id: str = Field(..., description="Identifiant unique de l'utilisateur")
    languages: List[str] = Field(default_factory=list, description="Langues préférées")
    visit_goal: Optional[str] = Field(default=None, description="Objectif de visite déclaré")
    detail_level: Optional[str] = Field(default=None, description="Niveau de détail souhaité")
    accessibility_needs: List[str] = Field(default_factory=list, description="Besoins d'accessibilité")
    is_active: bool = Field(default=True, description="Le profil est-il actif ?")
    last_activity_at: Optional[datetime] = Field(default=None, description="Dernière activité")
    created_at: Optional[datetime] = Field(default=None, description="Date de création")


# ============================================================================
# Modèle de réponse complet
# ============================================================================

class UserProfileResponse(BaseModel):
    """Réponse complète pour la page de profil utilisateur."""
    user_id: str = Field(..., description="Identifiant de l'utilisateur")
    profile: UserProfile = Field(..., description="Informations du profil utilisateur")
    stats: ProfileStats = Field(..., description="Statistiques globales")
    visited_resources: List[VisitedResource] = Field(default_factory=list, description="Liste des ressources consultées")
    theme_stats: List[ThemeStats] = Field(default_factory=list, description="Statistiques par thème")
    knowledge_by_theme: Dict[str, ThemeKnowledgeGroup] = Field(
        default_factory=dict,
        description="Éléments de connaissance groupés par thème (clé = theme_name)"
    )


# ============================================================================
# Modèles pour l'export CSV
# ============================================================================

class ProfileCSVRow(BaseModel):
    """Structure pour une ligne du CSV d'export."""
    user_id: str
    section: str  # stats, resources, themes, knowledge
    key: str
    value: str
    details: Optional[str] = None
