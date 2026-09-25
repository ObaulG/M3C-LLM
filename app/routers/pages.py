"""Router FastAPI des pages HTML du portail.

Les pages ne sont plus des fichiers statiques dans app/static/ : elles sont
désormais des templates Jinja2 (app/templates/pages/*.j2) rendus par ces routes.
Chaque route sert exactement le contenu qui était auparavant servi par
StaticFiles (app/static/*.html et app/static/admin/*.html), aux mêmes URLs de
type "belle" (/m3c-chatbot au lieu de /static/m3c-chatbot.html).
"""

import os
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# --- Environnement Jinja2 -------------------------------------------------
# Chargé depuis app/templates/ (base.html + macros/ + pages/).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATES_DIR = os.path.join(os.path.dirname(_THIS_DIR), "templates")

templates = Jinja2Templates(directory=_TEMPLATES_DIR)

# Import global des macros : disponibles dans toutes les pages sans `{% import %}`.
_ui = templates.env.get_template("macros/ui.html").module
_nav = templates.env.get_template("macros/header_nav.html").module
_prof = templates.env.get_template("macros/profile.html").module
_qcard = templates.env.get_template("macros/question_card.html").module
templates.env.globals.update(
    ui=_ui,
    header_nav=_nav,
    profile=_prof,
    question_card_mod=_qcard,
    # Alias pratiques d'accès direct aux macros les plus utilisées.
    btn=_ui.btn,
    nav_link=_ui.nav_link,
    nav_separator=_ui.nav_separator,
    message=_ui.message,
    message_input=_ui.message_input,
    chat_zone=_ui.chat_zone,
    loading=_ui.loading,
    bot_response=_ui.bot_response,
    sources_section=_ui.sources_section,
    feature_card=_ui.feature_card,
    section=_ui.section,
    status_badge=_ui.status_badge,
    back_button=_ui.back_button,
    header=_nav.header,
    header_centered=_nav.header_centered,
    nav_bar=_nav.nav_bar,
    profile_widget=_prof.profile_widget,
    difficulty_stars=_qcard.difficulty_stars,
    evaluation_section=_qcard.evaluation_section,
    empty_state=_qcard.empty_state,
    question_card=_qcard.question_card,
)
# static_prefix : préfixe vers la racine des fichiers statiques servis par
# /static. Les liens de page passent par les routes, les assets par /static.
templates.env.globals["static_prefix"] = "/static/"


def render(request: Request, template: str, page_title: str, **context) -> HTMLResponse:
    """Rend une page du portail avec le contexte commun à toutes les pages."""
    ctx = {
        "page_title": page_title,
        "include_profile_widget": True,
    }
    ctx.update(context)
    return templates.TemplateResponse(request, template, ctx)


router = APIRouter(tags=["Pages"])


@router.get("/", response_class=HTMLResponse, summary="Page d'accueil du portail")
async def home_page(request: Request):
    """Accueil : présentation du projet et cartes des interfaces disponibles."""
    return render(request, "pages/index.j2", "LLMAgents - Portail M3C")


@router.get("/tutorials", response_class=HTMLResponse, summary="Tutoriels")
async def tutorials_page(request: Request):
    """Explications : tutoriels sur l'architecture et le fonctionnement du RAG."""
    return render(request, "pages/tutorials.j2", "LLMAgents - Tutoriels")


@router.get("/m3c-chatbot", response_class=HTMLResponse, summary="Chatbot RAG")
async def chatbot_page(request: Request):
    """Chatbot RAG : questions en langage naturel avec sources citées."""
    return render(request, "pages/m3c-chatbot.j2", "Chatbot RAG - M3C")


@router.get("/m3c-chatbot-history", response_class=HTMLResponse, summary="Historique des sessions RAG")
async def chatbot_history_page(request: Request):
    """Historique : consultation des sessions de questions/réponses passées."""
    return render(request, "pages/m3c-chatbot-history.j2", "Historique - Chatbot RAG")


@router.get("/question-session", response_class=HTMLResponse, summary="Chatbot inversé (PDF + chat)")
async def question_session_page(request: Request):
    """Chatbot inversé : sélection d'un document PDF puis questions/réponses."""
    return render(request, "pages/question_session.j2", "Interface PDF et Chat - M3C")


@router.get("/questions-management", response_class=HTMLResponse, summary="Gestion des questions/réponses")
async def questions_management_page(request: Request):
    """Gestion Q/R : création, organisation et évaluation des questions."""
    return render(request, "pages/questions_management.j2", "Gestion des Questions/Réponses")


@router.get("/rag-visualization", response_class=HTMLResponse, summary="Visualisation RAG")
async def rag_visualization_page(request: Request):
    """Visualisation interactive des embeddings (t-SNE / UMAP)."""
    return render(request, "pages/rag_visualization.j2", "RAG Visualization - t-SNE & UMAP")


@router.get("/solr-search", response_class=HTMLResponse, summary="Recherche Solr")
async def solr_search_page(request: Request):
    """Recherche sémantique avancée via Apache Solr."""
    return render(request, "pages/solr_search.j2", "Recherche Solr - M3C")


@router.get("/auth", response_class=HTMLResponse, summary="Connexion / Inscription")
async def auth_page(request: Request):
    """Connexion ou création de compte."""
    return render(request, "pages/auth.j2", "Connexion / Inscription - M3C-LLM")


@router.get(
    "/admin",
    response_class=RedirectResponse,
    summary="Redirection vers l'administration",
)
async def admin_redirect():
    """Redirige /admin vers la page d'indexation (entrée de l'administration)."""
    return RedirectResponse(url="/admin/indexation", status_code=307)


@router.get("/admin/indexation", response_class=HTMLResponse, summary="Admin : indexation")
async def admin_indexation_page(request: Request):
    """Administration : indexation des documents par métadonnées ou contenu."""
    return render(request, "pages/admin/indexation.j2", "Administration - Indexation")


@router.get("/admin/questions-generation", response_class=HTMLResponse, summary="Admin : génération de questions")
async def admin_questions_generation_page(request: Request):
    """Administration : génération de questions à partir des documents validés."""
    return render(
        request,
        "pages/admin/questions_generation.j2",
        "Administration - Génération de Questions",
    )


@router.get(
    "/admin/knowledge-items-generation",
    response_class=HTMLResponse,
    summary="Admin : génération de knowledge items",
)
async def admin_knowledge_items_generation_page(request: Request):
    """Administration : génération de knowledge items à partir d'un chunk."""
    return render(
        request,
        "pages/admin/knowledge_items_generation.j2",
        "Administration - Génération de Knowledge Items",
    )


@router.get(
    "/admin/message-evaluator",
    response_class=HTMLResponse,
    summary="Admin : test du message evaluator",
)
async def admin_message_evaluator_page(request: Request):
    """Administration : évaluation de la précision de l'agent évaluateur."""
    return render(
        request,
        "pages/admin/message_evaluator_admin.j2",
        "Test message_evaluator_agent - M3C",
    )


@router.get("/admin/chatbot", response_class=HTMLResponse, summary="Admin : chatbot (alias)")
async def admin_chatbot_page(request: Request):
    """Administration : alias vers la page d'indexation (chatbot_admin historique)."""
    return render(request, "pages/admin/indexation.j2", "Administration - Indexation")


@router.get("/admin/observations", response_class=HTMLResponse, summary="Admin : observations manuelles")
async def admin_observations_page(request: Request):
    """Administration : application manuelle d'observations de connaissances."""
    return render(
        request,
        "pages/admin/observations_admin.j2",
        "Administration - Observations manuelles",
    )
