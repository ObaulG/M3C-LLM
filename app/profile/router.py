"""
Router FastAPI pour la page de profil utilisateur.

Ce router expose les endpoints pour :
- Afficher la page de profil (GET /profile)
- Récupérer les données du profil en JSON (GET /api/profile/{user_id})
- Exporter le profil en CSV (GET /api/profile/{user_id}/export/csv)
"""
from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from typing import Optional
import io

from .page_builder import build_profile_page, build_profile_page_with_auth, generate_profile_csv
from .services import get_user_profile_data, user_exists, _get_profile_db_connection as get_db_connection
from .models import UserProfileResponse


# Créer le router avec le préfixe /profile
router = APIRouter(prefix="/profile", tags=["Profile"])


# ============================================================================
# Endpoint pour afficher la page de profil
# ============================================================================

@router.get(
    "/",
    response_class=HTMLResponse,
    summary="Page de profil utilisateur",
    description="Affiche la page de profil avec les statistiques de visite, ressources consultées, thèmes et éléments de connaissance.",
)
async def get_profile_page(request: Request):
    """
    Retourne la page de profil utilisateur rendue avec Jinja2.
    
    Le user_id est récupéré depuis l'authentification (session, state ou headers).
    """
    return await build_profile_page_with_auth(request)


# ============================================================================
# Endpoints API pour récupérer les données du profil
# ============================================================================

@router.get(
    "/api/{user_id}",
    response_model=UserProfileResponse,
    summary="Récupère les données du profil",
    description="Retourne toutes les données du profil utilisateur au format JSON.",
)
async def get_profile_data(user_id: str):
    """
    Récupère toutes les données du profil pour un utilisateur spécifique.
    
    Args:
        user_id: Identifiant de l'utilisateur
        
    Returns:
        UserProfileResponse: Toutes les données du profil
        
    Raises:
        HTTPException: Si l'utilisateur n'existe pas
    """
    async with await get_db_connection() as conn:
        exists = await user_exists(user_id, conn)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Utilisateur {user_id} introuvable"
            )
        
        profile_data = await get_user_profile_data(user_id, conn)
    
    return profile_data


@router.get(
    "/api/{user_id}/stats",
    summary="Récupère les statistiques du profil",
    description="Retourne uniquement les statistiques globales du profil utilisateur.",
)
async def get_profile_stats(user_id: str):
    """
    Récupère les statistiques globales pour un utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        
    Returns:
        JSON avec les statistiques du profil
    """
    from .services import get_profile_stats
    
    async with await get_db_connection() as conn:
        exists = await user_exists(user_id, conn)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Utilisateur {user_id} introuvable"
            )
        
        stats = await get_profile_stats(user_id, conn)
    
    return JSONResponse(content=stats.model_dump())


@router.get(
    "/api/{user_id}/resources",
    summary="Récupère les ressources consultées",
    description="Retourne la liste des ressources consultées par l'utilisateur.",
)
async def get_profile_resources(user_id: str, limit: int = 100):
    """
    Récupère les ressources consultées par un utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        limit: Nombre maximum de ressources à retourner
        
    Returns:
        JSON avec la liste des ressources
    """
    from .services import get_visited_resources
    
    async with await get_db_connection() as conn:
        exists = await user_exists(user_id, conn)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Utilisateur {user_id} introuvable"
            )
        
        resources = await get_visited_resources(user_id, conn, limit)
    
    return JSONResponse(content={
        "user_id": user_id,
        "resources": [r.model_dump() for r in resources],
        "count": len(resources)
    })


@router.get(
    "/api/{user_id}/themes",
    summary="Récupère les statistiques par thème",
    description="Retourne les statistiques pour chaque thème exploré par l'utilisateur.",
)
async def get_profile_themes(user_id: str, limit: int = 50):
    """
    Récupère les statistiques par thème pour un utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        limit: Nombre maximum de thèmes à retourner
        
    Returns:
        JSON avec la liste des statistiques par thème
    """
    from .services import get_theme_stats
    
    async with await get_db_connection() as conn:
        exists = await user_exists(user_id, conn)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Utilisateur {user_id} introuvable"
            )
        
        themes = await get_theme_stats(user_id, conn, limit)
    
    return JSONResponse(content={
        "user_id": user_id,
        "themes": [t.model_dump() for t in themes],
        "count": len(themes)
    })


@router.get(
    "/api/{user_id}/knowledge",
    summary="Récupère les éléments de connaissance",
    description="Retourne les éléments de connaissance groupés par thème pour l'utilisateur.",
)
async def get_profile_knowledge(user_id: str, limit_per_theme: int = 20):
    """
    Récupère les éléments de connaissance groupés par thème pour un utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        limit_per_theme: Nombre maximum de connaissances par thème
        
    Returns:
        JSON avec les connaissances groupées par thème
    """
    from .services import get_knowledge_by_theme
    
    async with await get_db_connection() as conn:
        exists = await user_exists(user_id, conn)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Utilisateur {user_id} introuvable"
            )
        
        knowledge_by_theme = await get_knowledge_by_theme(user_id, conn, limit_per_theme)
    
    # Convertir le dictionnaire en une structure serializable
    result = {}
    for theme_name, theme_group in knowledge_by_theme.items():
        result[theme_name] = {
            "theme_id": theme_group.theme_id,
            "theme_name": theme_group.theme_name,
            "knowledge_items": [ki.model_dump() for ki in theme_group.knowledge_items]
        }
    
    return JSONResponse(content={
        "user_id": user_id,
        "knowledge_by_theme": result,
        "theme_count": len(result)
    })


# ============================================================================
# Endpoint pour exporter le profil en CSV
# ============================================================================

@router.get(
    "/api/{user_id}/export/csv",
    summary="Exporte le profil en CSV",
    description="Génère et télécharge un fichier CSV avec toutes les données du profil.",
)
async def export_profile_csv(user_id: str):
    """
    Exporte les données du profil utilisateur au format CSV.
    
    Args:
        user_id: Identifiant de l'utilisateur
        
    Returns:
        StreamingResponse avec le fichier CSV
    """
    async with await get_db_connection() as conn:
        exists = await user_exists(user_id, conn)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Utilisateur {user_id} introuvable"
            )
    
    # Générer le CSV
    csv_content = await generate_profile_csv(user_id)
    
    # Créer une réponse de streaming
    csv_bytes = io.BytesIO(csv_content.encode('utf-8-sig'))
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        iter([csv_bytes.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=profile_{user_id}_{timestamp}.csv"
        }
    )


@router.get(
    "/api/me",
    response_model=UserProfileResponse,
    summary="Récupère les données du profil de l'utilisateur connecté",
    description="Retourne les données du profil de l'utilisateur actuellement authentifié.",
)
async def get_current_user_profile(request: Request):
    """
    Récupère les données du profil de l'utilisateur actuellement authentifié.
    
    Le user_id est récupéré depuis l'authentification.
    """
    # Récupérer le user_id depuis l'authentification
    user_id = None
    if hasattr(request.state, 'user_id') and request.state.user_id:
        user_id = request.state.user_id
    elif hasattr(request, 'session') and 'user_id' in request.session:
        user_id = request.session['user_id']
    elif hasattr(request, 'headers') and 'X-User-ID' in request.headers:
        user_id = request.headers['X-User-ID']
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non autorisé - Veuillez vous connecter"
        )
    
    async with await get_db_connection() as conn:
        profile_data = await get_user_profile_data(user_id, conn)
    
    return profile_data
