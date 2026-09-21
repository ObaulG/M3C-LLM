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
