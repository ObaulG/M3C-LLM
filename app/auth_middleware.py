"""Middleware d'authentification globale.

Force la connexion pour toutes les fonctionnalités de l'application :
pages du portail (sauf l'index et la page de connexion) et endpoints API
(sauf /api/auth/* et /api/health). Les utilisateurs non connectés sont
redirigés vers la page de connexion (ou 401 pour les appels API).
"""
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

import auth

AUTH_COOKIE_NAME = "m3c_api_key"
LOGIN_PAGE_PATH = "/static/auth.html"
PUBLIC_HTML_PAGES = ("index.html", "auth.html")
PUBLIC_API_PREFIXES = ("/api/auth/",)
PUBLIC_API_PATHS = ("/api/health",)
PUBLIC_ROOT_PATHS = ("/", "/docs", "/redoc", "/openapi.json", "/favicon.ico")


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
    return False


def _current_user_id(request: Request) -> Optional[int]:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    user_id = auth.user_id_from_token(token)
    if user_id is None:
        user_id = auth.user_id_from_authorization(request.headers.get("authorization"))
    return user_id


def install_auth_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def require_login(request: Request, call_next):
        path = request.url.path
        if not _is_public_path(path) and _current_user_id(request) is None:
            if path.startswith("/api/"):
                return JSONResponse(
                    {"detail": "Authentification requise."},
                    status_code=401,
                )
            return RedirectResponse(LOGIN_PAGE_PATH, status_code=302)
        return await call_next(request)
