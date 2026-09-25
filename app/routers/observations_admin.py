"""Router FastAPI pour l'administration manuelle des observations.

Démonstration du système d'observations d'éléments de connaissance :
permet d'appliquer manuellement des observations conformes au schéma
user_knowledge_model.sql (tables observations, observation_payloads,
observation_targets), puis de les consulter.

Routes :
- GET  /api/observations-admin/users      (utilisateurs observables)
- GET  /api/observations-admin/targets    (connaissances, thèmes, entités)
- GET  /api/observations-admin/resources  (ressources pour le contexte)
- POST /api/observations-admin/observations (création manuelle)
- GET  /api/observations-admin/observations (consultation filtrée)
"""
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from database.database import (
    get_db_connection,
    get_observation_users,
    get_observation_target_options,
    get_observation_resource_options,
    create_manual_observation,
    get_manual_observations,
)

router = APIRouter(prefix="/api/observations-admin", tags=["Observations Admin"])

ObservationType = Literal["declarative", "behavioral", "evaluative"]
TargetType = Literal["knowledge", "theme", "entity"]


class ObservationUser(BaseModel):
    """Un utilisateur observable (compte users ou profil user_profiles)"""
    user_id: str = Field(..., description="Identifiant utilisé dans observations.user_id (VARCHAR)")
    label: str = Field(..., description="Libellé affichable (username ou profil)")
    source: str = Field(..., description="Origine : 'users' ou 'user_profiles'")


class ObservationTargetOption(BaseModel):
    """Une cible possible d'une observation"""
    id: int = Field(..., description="Identifiant de la cible")
    label: str = Field(..., description="Libellé de la cible (proposition, nom...)")
    extra: Optional[str] = Field(None, description="Information complémentaire (summary, type...)")


class ObservationResourceOption(BaseModel):
    """Une ressource documentaire pour le contexte d'une observation"""
    id: int = Field(..., description="knowledge_resources.id")
    title: str = Field(..., description="Titre de la ressource")
    uri: Optional[str] = Field(None, description="URI de la ressource")
    resource_type: Optional[str] = Field(None, description="Type de ressource")


class ObservationTargetRequest(BaseModel):
    """Lien entre une observation et un élément de connaissance, thème ou entité"""
    target_type: TargetType = Field(..., description="Type de cible : knowledge, theme ou entity")
    target_id: int = Field(..., description="ID de la cible (knowledge_items.id, themes.id ou entities.id)", ge=1)
    weight: float = Field(1.0, description="Poids de cette cible pour l'observation (0-1)", ge=0, le=1)


class ManualObservationRequest(BaseModel):
    """Requête de création manuelle d'une observation (démo admin)"""
    user_id: str = Field(..., description="Utilisateur observé (observations.user_id)", min_length=1, max_length=100)
    observation_type: ObservationType = Field(..., description="Famille : declarative, behavioral ou evaluative")
    specific_type: str = Field(..., description="Type spécifique (ex: language, click, free_response)", min_length=1, max_length=100)
    context: Dict = Field(default_factory=dict, description="Contexte JSON (page, session_id, resource_id, device...)")
    confidence: float = Field(1.0, description="Fiabilité de l'interprétation (0-1)", ge=0, le=1)
    is_raw: bool = Field(True, description="Vrai si l'observation est une donnée brute")
    payload: Optional[Dict] = Field(None, description="Données brutes ou structurées (observation_payloads)")
    targets: List[ObservationTargetRequest] = Field(default_factory=list, description="Cibles de l'observation")


class ManualObservationResponse(BaseModel):
    """Confirmation de création d'une observation manuelle"""
    observation_id: int = Field(..., description="ID de l'observation créée")
    user_id: str = Field(..., description="Utilisateur observé")
    observation_type: str = Field(..., description="Famille de l'observation")
    specific_type: str = Field(..., description="Type spécifique")
    targets_count: int = Field(..., description="Nombre de cibles enregistrées")
    payload_saved: bool = Field(..., description="Un payload a-t-il été enregistré")


class ObservationPayloadInfo(BaseModel):
    """Payload associé à une observation"""
    payload_type: str = Field(..., description="Type de payload (raw, structured, processed, llm_interpretation)")
    payload: Optional[Dict] = Field(None, description="Contenu du payload")


class ObservationTargetInfo(BaseModel):
    """Cible affichée d'une observation"""
    target_type: str = Field(..., description="knowledge, theme ou entity")
    target_id: int = Field(..., description="ID de la cible")
    weight: float = Field(..., description="Poids de la cible")
    label: Optional[str] = Field(None, description="Libellé de la cible si connue")


class ObservationRecord(BaseModel):
    """Une observation complète pour l'affichage"""
    id: int = Field(..., description="ID de l'observation")
    user_id: str = Field(..., description="Utilisateur observé")
    observation_type: str = Field(..., description="Famille de l'observation")
    specific_type: str = Field(..., description="Type spécifique")
    timestamp: Optional[str] = Field(None, description="Horodatage de l'observation")
    confidence: float = Field(..., description="Fiabilité de l'interprétation")
    is_raw: bool = Field(..., description="Donnée brute ou interprétée")
    context: Dict = Field(default_factory=dict, description="Contexte JSON de l'observation")
    targets: List[ObservationTargetInfo] = Field(default_factory=list, description="Cibles de l'observation")
    payloads: List[ObservationPayloadInfo] = Field(default_factory=list, description="Payloads de l'observation")


class ManualObservationListResponse(BaseModel):
    """Liste d'observations pour la page de démonstration"""
    observations: List[ObservationRecord]
    count: int = Field(..., description="Nombre d'observations retournées")


@router.get("/users", response_model=List[ObservationUser])
async def list_observation_users():
    """
    Liste les utilisateurs pouvant être observés : comptes de la table users
    et profils user_profiles (schéma user_knowledge_model.sql).
    """
    conn = await get_db_connection()
    try:
        return await get_observation_users(conn)
    except Exception as e:
        print(f"Erreur list_observation_users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des utilisateurs.",
        )
    finally:
        await conn.close()


@router.get("/targets", response_model=List[ObservationTargetOption])
async def list_observation_targets(
    target_type: TargetType = Query(..., description="Type de cible : knowledge, theme ou entity"),
    search: Optional[str] = Query(None, description="Filtre sur le libellé"),
    limit: int = Query(200, description="Nombre maximum de résultats", ge=1, le=1000),
):
    """
    Liste les cibles possibles d'une observation pour un type donné :
    knowledge_items (proposition), themes ou entities.
    """
    conn = await get_db_connection()
    try:
        return await get_observation_target_options(conn, target_type, search, limit)
    except Exception as e:
        print(f"Erreur list_observation_targets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des cibles.",
        )
    finally:
        await conn.close()


@router.get("/resources", response_model=List[ObservationResourceOption])
async def list_observation_resources(
    search: Optional[str] = Query(None, description="Filtre sur le titre"),
    limit: int = Query(100, description="Nombre maximum de résultats", ge=1, le=500),
):
    """
    Liste les ressources documentaires (knowledge_resources) pour renseigner
    le contexte d'une observation.
    """
    conn = await get_db_connection()
    try:
        return await get_observation_resource_options(conn, search, limit)
    except Exception as e:
        print(f"Erreur list_observation_resources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des ressources.",
        )
    finally:
        await conn.close()


@router.post("/observations", response_model=ManualObservationResponse)
async def create_observation(request: ManualObservationRequest):
    """
    Applique manuellement une observation pour la démonstration : insère une
    ligne dans observations, éventuellement un payload structuré dans
    observation_payloads et les cibles dans observation_targets.
    """
    conn = await get_db_connection()
    try:
        result = await create_manual_observation(
            conn,
            user_id=request.user_id,
            observation_type=request.observation_type,
            specific_type=request.specific_type,
            context=request.context,
            confidence=request.confidence,
            is_raw=request.is_raw,
            payload=request.payload,
            targets=[t.model_dump() for t in request.targets],
        )
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de l'enregistrement de l'observation.",
            )
        return ManualObservationResponse(
            observation_id=result["observation_id"],
            user_id=request.user_id,
            observation_type=request.observation_type,
            specific_type=request.specific_type,
            targets_count=result["targets_count"],
            payload_saved=result["payload_saved"],
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erreur create_observation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'enregistrement de l'observation.",
        )
    finally:
        await conn.close()


@router.get("/observations", response_model=ManualObservationListResponse)
async def list_observations(
    user_id: Optional[str] = Query(None, description="Filtre sur l'utilisateur observé"),
    observation_type: Optional[ObservationType] = Query(None, description="Filtre sur la famille d'observation"),
    limit: int = Query(50, description="Nombre maximum d'observations", ge=1, le=500),
):
    """
    Récupère les observations les plus récentes avec leurs cibles et payloads,
    filtrables par utilisateur et par famille, pour la démonstration.
    """
    conn = await get_db_connection()
    try:
        observations = await get_manual_observations(
            conn,
            user_id=user_id,
            observation_type=observation_type,
            limit=limit,
        )
        return ManualObservationListResponse(
            observations=observations,
            count=len(observations),
        )
    except Exception as e:
        print(f"Erreur list_observations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des observations.",
        )
    finally:
        await conn.close()
