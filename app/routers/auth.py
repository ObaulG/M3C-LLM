"""Router FastAPI pour l'authentification.

Regroupe les routes /api/auth/* (inscription, connexion, utilisateur
courant, dconnexion). Ces routes taient auparavant dfinies dans
api_server.py.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import auth

router = APIRouter(prefix="/api/auth", tags=["Auth"])

AUTH_COOKIE_NAME = "m3c_api_key"


class AuthRegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    email: str = Field(...)
    password: str = Field(..., min_length=6)


class AuthLoginRequest(BaseModel):
    username: str = Field(...)
    password: str = Field(...)


class AuthUserResponse(BaseModel):
    user_id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[str] = None
    has_mistral_api_key: bool = False


class MistralApiKeyRequest(BaseModel):
    mistral_api_key: Optional[str] = Field(default=None, max_length=255)


class AuthResponse(BaseModel):
    user: AuthUserResponse


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=auth._TOKEN_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")


@router.post("/register", response_model=AuthResponse)
async def register(request: AuthRegisterRequest):
    """Cre un nouveau compte utilisateur dans la table `users`."""
    try:
        user, token = await auth.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
        )
        response = JSONResponse(content=AuthResponse(user=AuthUserResponse(**user)).model_dump(mode="json"))
        _set_auth_cookie(response, token)
        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR inscription: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erreur lors de la cration du compte.")


@router.post("/login", response_model=AuthResponse)
async def login(request: AuthLoginRequest):
    """Connecte un utilisateur existant  partir de son nom d'utilisateur ou email."""
    try:
        user, token = await auth.authenticate_user(request.username, request.password)
        response = JSONResponse(content=AuthResponse(user=AuthUserResponse(**user)).model_dump(mode="json"))
        _set_auth_cookie(response, token)
        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR connexion: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erreur lors de la connexion.")


@router.get("/me")
async def get_current_user(
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None,
):
    """Retourne l'utilisateur associ au cookie de session (ou Bearer token)."""
    user_id = auth.user_id_from_token(m3c_api_key)
    if user_id is None:
        user_id = auth.user_id_from_authorization(authorization)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non authentifi.")
    user = await auth.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable.")
    return {"user": AuthUserResponse(**user)}


def _authenticated_user_id(m3c_api_key: Optional[str], authorization: Optional[str]) -> int:
    user_id = auth.user_id_from_token(m3c_api_key)
    if user_id is None:
        user_id = auth.user_id_from_authorization(authorization)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non authentifie.")
    return user_id


@router.put("/mistral-api-key")
async def save_mistral_api_key(
    request: MistralApiKeyRequest,
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None,
):
    """Enregistre (ou met a jour) la cle API Mistral de l'utilisateur connecte."""
    user_id = _authenticated_user_id(m3c_api_key, authorization)
    api_key = (request.mistral_api_key or "").strip() or None
    updated = await auth.set_user_mistral_api_key(user_id, api_key)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")
    return {"has_mistral_api_key": bool(api_key)}


@router.delete("/mistral-api-key")
async def delete_mistral_api_key(
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None,
):
    """Supprime la cle API Mistral de l'utilisateur connecte."""
    user_id = _authenticated_user_id(m3c_api_key, authorization)
    updated = await auth.set_user_mistral_api_key(user_id, None)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")
    return {"has_mistral_api_key": False}


@router.post("/logout")
async def logout(
    response: Response,
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None,
):
    """Rvoque le token de session (cookie ou Bearer) et efface le cookie."""
    token = m3c_api_key or auth._token_from_authorization(authorization)
    if token:
        auth.revoke_token("Bearer " + token)
    _clear_auth_cookie(response)
    return {"message": "Dconnect."}
