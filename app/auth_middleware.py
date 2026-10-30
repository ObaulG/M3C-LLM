"""Middleware d'authentification et d'acces global.

Deux niveaux de controle :

1. Connexion obligatoire pour toutes les fonctionnalites de l'application :
   pages du portail (sauf l'index et la page de connexion) et endpoints API
   (sauf /api/auth/* et /api/health). Les utilisateurs non connectes sont
   rediriges vers la page de connexion (ou 401 pour les appels API).

2. Cle API Mistral obligatoire : un utilisateur connecte qui n'est pas
   global_admin doit avoir enregistre sa cle API Mistral (via la page de
   profil) pour acceder aux outils et aux pages. Tant qu'il ne l'a pas fait,
   il est traite comme non connecte : seules la page d'index, la page de
   connexion et la page de profil (et les endpoints /api/auth/*) restent
   accessibles. Pour les appels API, une erreur 403 est retournee ; pour les
   pages, une redirection vers la page de profil est effectuee.
"""
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

import auth

AUTH_COOKIE_NAME = "m3c_api_key"
LOGIN_PAGE_PATH = "/static/auth.html"
PROFILE_PAGE_PATH = "/static/profile.html"
PUBLIC_HTML_PAGES = ("index.html", "auth.html", "profile.html")
PUBLIC_API_PREFIXES = ("/api/auth/",)
PUBLIC_API_PATHS = ("/api/health",)
PUBLIC_ROOT_PATHS = ("/", "/docs", "/redoc", "/openapi.json", "/favicon.ico")

API_KEY_REQUIRED_MESSAGE = (
    "Cle API Mistral requise. Veuillez la configurer dans votre profil "
    "utilisateur (page Mon Profil)."
)


def _is_public_path(path: str) -> bool:
    if path in PUBLIC_ROOT_PATHS:
        return True
    if path in PUBLIC_API_PATHS or path.startswith(PUBLIC_API_PREFIXES):
        return True
    if path.startswith("/admin"):
        return False
    if path.startswith("/static"):
        name = path.rstrip("/").rsplit("/", 1)[-1]
        if not name:
            return True
        if not name.endswith(".html"):
            return True
        return name in PUBLIC_HTML_PAGES
    if path.startswith("/profile"):
        return True
    return False


def _current_user_id(request: Request) -> Optional[int]:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    user_id = auth.user_id_from_token(token)
    if user_id is None:
        user_id = auth.user_id_from_authorization(request.headers.get("authorization"))
    return user_id


async def _user_may_access(user_id: int) -> bool:
    """True si l'utilisateur peut utiliser les outils (global_admin ou cle API renseignee)."""
    info = await auth.get_user_access_info(user_id)
    if info is None:
        return False
    if info["role"] == auth.GLOBAL_ADMIN_ROLE:
        return True
    return bool(info["has_mistral_api_key"])


def install_auth_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def require_login(request: Request, call_next):
        path = request.url.path
        if _is_public_path(path):
            return await call_next(request)
        user_id = _current_user_id(request)
        if user_id is None:
            if path.startswith("/api/"):
                return JSONResponse(
                    {"detail": "Authentification requise."},
                    status_code=401,
                )
            return RedirectResponse(LOGIN_PAGE_PATH, status_code=302)
        if not await _user_may_access(user_id):
            if path.startswith("/api/"):
                return JSONResponse(
                    {"detail": API_KEY_REQUIRED_MESSAGE},
                    status_code=403,
                )
            return RedirectResponse(PROFILE_PAGE_PATH, status_code=302)
        return await call_next(request)
