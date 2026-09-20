"""
Module pour la construction de la page de profil utilisateur.

Ce module contient la fonction principale pour construire et retourner
la page HTML complète du profil utilisateur.
"""
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict, Any
import os

from .services import get_user_profile_data, user_exists, _get_profile_db_connection as get_db_connection
from .models import UserProfileResponse


# Chemin vers le dossier des templates
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

# Initialisation des templates (sera faite au premier appel)
_templates: Optional[Jinja2Templates] = None


def get_templates() -> Jinja2Templates:
    """Retourne l'instance Jinja2Templates (créée à la première utilisation)."""
    global _templates
    if _templates is None:
        _templates = Jinja2Templates(directory=TEMPLATES_DIR)
    return _templates


async def build_profile_page(user_id: str, request: Request) -> HTMLResponse:
    """
    Construit et retourne la page de profil complète pour un utilisateur.
    
    Cette fonction:
    1. Vérifie que l'utilisateur existe
    2. Récupère toutes les données du profil via les services
    3. Prépare le contexte pour le template Jinja2
    4. Rend le template et retourne la réponse HTML
    
    Args:
        user_id: Identifiant de l'utilisateur
        request: Objet Request de FastAPI pour le rendering Jinja2
        
    Returns:
        HTMLResponse: Page HTML rendue
        
    Raises:
        HTTPException: Si l'utilisateur n'existe pas
    """
    # Vérifier que l'utilisateur existe
    async with await get_db_connection() as conn:
        exists = await user_exists(user_id, conn)
        if not exists:
            raise HTTPException(
                status_code=404,
                detail=f"Utilisateur {user_id} introuvable"
            )
        
        # Récupérer toutes les données du profil
        profile_data = await get_user_profile_data(user_id, conn)
    
    # Déterminer le préfixe pour les ressources statiques
    # Si la requête vient de /admin, utiliser ../static/, sinon static/
    path_str = str(request.url.path)
    if "/admin" in path_str or path_str.startswith("/admin"):
        static_prefix = "../static/"
    else:
        static_prefix = "static/"
    
    # Formater les dates pour l'affichage
    def format_date(dt: Any) -> str:
        """Formate une date pour l'affichage."""
        if dt is None:
            return "N/A"
        if hasattr(dt, 'strftime'):
            return dt.strftime("%d/%m/%Y à %H:%M")
        return str(dt)
    
    def format_status(status: str) -> str:
        """Formate le statut d'une connaissance pour l'affichage."""
        status_map = {
            "unknown": "Inconnu",
            "encountered": "Rencontré",
            "developing": "En développement",
            "demonstrated": "Maîtrisé",
        }
        return status_map.get(status.value if hasattr(status, 'value') else status, status)
    
    def format_score(score: float) -> str:
        """Formate un score en pourcentage."""
        if score is None:
            return "0%"
        return f"{round(score * 100)}%"
    
    # Préparer le contexte pour Jinja2
    context: Dict[str, Any] = {
        "request": request,
        "user_id": user_id,
        "profile": profile_data.profile,
        "stats": profile_data.stats,
        "visited_resources": profile_data.visited_resources,
        "theme_stats": profile_data.theme_stats,
        "knowledge_by_theme": profile_data.knowledge_by_theme,
        "static_prefix": static_prefix,
        "page": "profile.j2",
        "page_title": f"Profil de {user_id} - M3C",
        "include_profile_widget": True,
        # Fonctions utilitaires pour les templates
        "format_date": format_date,
        "format_status": format_status,
        "format_score": format_score,
        # Calcul de pourcentages pour les stats de connaissance
        "knowledge_stats": {
            "total": profile_data.stats.total_knowledge_items_encountered,
            "demonstrated_pct": round(
                (profile_data.stats.total_knowledge_demonstrated / max(profile_data.stats.total_knowledge_items_encountered, 1)) * 100, 1
            ) if profile_data.stats.total_knowledge_items_encountered > 0 else 0,
            "developing_pct": round(
                (profile_data.stats.total_knowledge_developing / max(profile_data.stats.total_knowledge_items_encountered, 1)) * 100, 1
            ) if profile_data.stats.total_knowledge_items_encountered > 0 else 0,
            "encountered_pct": round(
                (profile_data.stats.total_knowledge_encountered / max(profile_data.stats.total_knowledge_items_encountered, 1)) * 100, 1
            ) if profile_data.stats.total_knowledge_items_encountered > 0 else 0,
            "unknown_pct": round(
                (profile_data.stats.total_knowledge_unknown / max(profile_data.stats.total_knowledge_items_encountered, 1)) * 100, 1
            ) if profile_data.stats.total_knowledge_items_encountered > 0 else 0,
        },
    }
    
    # Rendre le template
    templates = get_templates()
    return templates.TemplateResponse("pages/profile.j2", context)


async def build_profile_page_with_auth(request: Request) -> HTMLResponse:
    """
    Construit la page de profil en récupérant le user_id depuis l'authentification.
    
    Cette fonction est utilisée comme endpoint FastAPI pour servir la page /profile.
    Elle suppose que le middleware d'authentification a placé le user_id dans request.state.
    
    Args:
        request: Objet Request de FastAPI
        
    Returns:
        HTMLResponse: Page HTML rendue
        
    Raises:
        HTTPException: Si l'utilisateur n'est pas authentifié
    """
    # Récupérer le user_id depuis la session ou l'authentification
    # Plusieurs méthodes possibles selon votre système d'auth
    
    # Méthode 1: Depuis request.state (si le middleware d'auth met user_id là)
    if hasattr(request.state, 'user_id') and request.state.user_id:
        user_id = request.state.user_id
    # Méthode 2: Depuis les cookies ou la session
    elif hasattr(request, 'session') and 'user_id' in request.session:
        user_id = request.session['user_id']
    # Méthode 3: Depuis les headers (pour les requêtes API)
    elif hasattr(request, 'headers') and 'X-User-ID' in request.headers:
        user_id = request.headers['X-User-ID']
    else:
        raise HTTPException(
            status_code=401,
            detail="Non autorisé - Veuillez vous connecter"
        )
    
    return await build_profile_page(user_id, request)


# ============================================================================
# Fonction pour générer le CSV d'export
# ============================================================================

async def generate_profile_csv(user_id: str) -> str:
    """
    Génère un fichier CSV avec les données du profil utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        
    Returns:
        String: Contenu du fichier CSV
    """
    import csv
    import io
    from datetime import datetime
    
    async with await get_db_connection() as conn:
        profile_data = await get_user_profile_data(user_id, conn)
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    # En-tête
    writer.writerow(["M3C - Export Profil Utilisateur"])
    writer.writerow([f"Utilisateur: {user_id}"])
    writer.writerow([f"Date d'export: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"])
    writer.writerow([])  # Ligne vide
    
    # Statistiques globales
    writer.writerow(["STATISTIQUES GLOBALES"])
    writer.writerow(["Métrique", "Valeur"])
    writer.writerow(["Total observations", profile_data.stats.total_observations])
    writer.writerow(["Total vues de ressources", profile_data.stats.total_resource_views])
    writer.writerow(["Total vues de thèmes", profile_data.stats.total_theme_views])
    writer.writerow(["Total évaluations", profile_data.stats.total_evaluations])
    writer.writerow(["Ressources différentes consultées", profile_data.stats.total_resources_visited])
    writer.writerow(["Thèmes différents explorés", profile_data.stats.total_themes_explored])
    writer.writerow(["Éléments de connaissance rencontrés", profile_data.stats.total_knowledge_items_encountered])
    writer.writerow(["Connaissances maîtrisées", profile_data.stats.total_knowledge_demonstrated])
    writer.writerow(["Connaissances en développement", profile_data.stats.total_knowledge_developing])
    writer.writerow(["Connaissances rencontrées", profile_data.stats.total_knowledge_encountered])
    writer.writerow(["Connaissances inconnues", profile_data.stats.total_knowledge_unknown])
    writer.writerow([])
    
    # Ressources consultées
    writer.writerow(["RESSOURCES CONSULTÉES"])
    writer.writerow(["Titre", "Type", "Auteur", "Date publication", "Nb consultations", "Dernière visite"])
    for resource in profile_data.visited_resources:
        last_view = resource.last_viewed_at.strftime('%d/%m/%Y') if resource.last_viewed_at else 'N/A'
        writer.writerow([
            resource.resource_title or '',
            resource.resource_type or '',
            resource.author or '',
            resource.publication_date or '',
            resource.view_count,
            last_view
        ])
    writer.writerow([])
    
    # Statistiques par thème
    writer.writerow(["STATISTIQUES PAR THÈME"])
    writer.writerow(["Thème", "Poids intérêt", "Confiance", "Nb observations", "Connaissances associées", "Maîtrisées", "En développement"])
    for theme in profile_data.theme_stats:
        writer.writerow([
            theme.theme_name,
            round(theme.interest_weight * 100, 1),
            round(theme.interest_confidence * 100, 1),
            theme.observation_count,
            theme.knowledge_items_count,
            theme.demonstrated_count,
            theme.developing_count
        ])
    writer.writerow([])
    
    # Éléments de connaissance
    writer.writerow(["ÉLÉMENTS DE CONNAISSANCE"])
    writer.writerow(["Thème", "Proposition", "Statut", "Score", "Confiance"])
    for theme_name, theme_group in profile_data.knowledge_by_theme.items():
        for ki in theme_group.knowledge_items:
            writer.writerow([
                theme_name,
                ki.proposition[:100] + '...' if len(ki.proposition) > 100 else ki.proposition,
                ki.status.value if hasattr(ki.status, 'value') else ki.status,
                round(ki.score * 100, 1),
                round(ki.confidence * 100, 1)
            ])
    
    return output.getvalue()
