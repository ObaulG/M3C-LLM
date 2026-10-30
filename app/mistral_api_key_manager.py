"""
Gestionnaire de clé API Mistral.

Ce module fournit des utilitaires pour :
- Vérifier si une clé API Mistral est valide (format)
- Déterminer quelle clé utiliser pour une requête :
  1. la clé fournie directement par le client (paramètre `mistral_api_key`) ;
  2. sinon, selon le rôle de l'utilisateur authentifié :
     - `global_admin` / `admin` : la clé interne du serveur (MISTRAL_API_KEY) ;
     - `user` / `guest` : la clé personnelle stockée dans la colonne
       `mistral_api_key` de la table `user`.
"""

import os
from typing import Optional, Tuple
from fastapi import HTTPException, status, Cookie
import auth

# Rôles qui utilisent la clé API interne du serveur
SERVER_KEY_ROLES = ("global_admin", "admin")


async def _resolve_user_api_key(user_id: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Retourne (clé API, rôle) pour un utilisateur authentifié.

    - admin/global_admin -> clé du serveur (env MISTRAL_API_KEY)
    - user/guest -> colonne mistral_api_key de la table user
    """
    from database.database import get_db_connection

    async with await get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT role, mistral_api_key FROM user WHERE id = %s",
                (user_id,)
            )
            row = await cursor.fetchone()
    if row is None:
        return None, None
    role, user_key = row[0], row[1]
    if role in SERVER_KEY_ROLES:
        return os.getenv('MISTRAL_API_KEY'), role
    return user_key, role


def get_mistral_api_key_from_request(
    mistral_api_key: Optional[str] = None,
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None
) -> Optional[str]:
    """
    Obtient la clé API Mistral à utiliser pour une requête (version synchrone).

    Ordre de priorité :
    1. Si mistral_api_key est fournie directement, l'utiliser
    2. Sinon, selon le rôle de l'utilisateur connecté :
       admin/global_admin -> clé serveur, user/guest -> clé personnelle en BDD
    3. Sinon, retourner None (la requête sera refusée)
    """
    if mistral_api_key:
        return mistral_api_key

    user_id = auth.user_id_from_token(m3c_api_key)
    if user_id is None:
        user_id = auth.user_id_from_authorization(authorization)

    if user_id is None:
        return None

    import asyncio

    async def resolve():
        return await _resolve_user_api_key(user_id)

    try:
        loop = asyncio.get_event_loop()
        api_key, _role = loop.run_until_complete(resolve())
        return api_key
    except Exception:
        return None


async def async_get_mistral_api_key_from_request(
    mistral_api_key: Optional[str] = None,
    m3c_api_key: Optional[str] = None,
    authorization: Optional[str] = None
) -> Optional[str]:
    """
    Obtient la clé API Mistral à utiliser pour une requête (version asynchrone).

    Ordre de priorité :
    1. Si mistral_api_key est fournie directement, l'utiliser
    2. Sinon, selon le rôle de l'utilisateur connecté :
       admin/global_admin -> clé serveur, user/guest -> clé personnelle en BDD
    3. Sinon, retourner None (la requête sera refusée)
    """
    if mistral_api_key:
        return mistral_api_key

    user_id = auth.user_id_from_token(m3c_api_key)
    if user_id is None:
        user_id = auth.user_id_from_authorization(authorization)

    if user_id is None:
        return None

    api_key, _role = await _resolve_user_api_key(user_id)
    return api_key


def verify_mistral_api_key(api_key: str) -> bool:
    """
    Vérifie si une clé API Mistral est valide.

    Cette vérification est basique et vérifie seulement le format.
    Une clé Mistral valide commence généralement par 'x' et a un format spécifique.

    Args:
        api_key: La clé API à vérifier

    Returns:
        True si la clé semble valide, False sinon
    """
    if not api_key:
        return False

    # Format de base : commence par 'mstrl' et a au moins 30 caractères
    if not api_key.startswith('mstrl'):
        return False

    if len(api_key) < 30:
        return False

    return len(api_key) >= 30


def require_mistral_api_key(
    mistral_api_key: Optional[str] = None,
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None
) -> str:
    """
    Vérifie qu'une clé API Mistral est disponible et valide (version synchrone).

    Si l'utilisateur est admin/global_admin, utilise la clé serveur.
    Si c'est un user/guest, utilise la clé personnelle stockée dans son compte.
    Sinon, la clé doit être fournie dans mistral_api_key.

    Args:
        mistral_api_key: Clé API Mistral fournie directement
        m3c_api_key: Cookie d'authentification M3C
        authorization: Header Authorization Bearer

    Returns:
        La clé API Mistral valide

    Raises:
        HTTPException: Si aucune clé valide n'est disponible
    """
    api_key = get_mistral_api_key_from_request(mistral_api_key, m3c_api_key, authorization)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API Mistral requise. Veuillez configurer votre clé API Mistral dans votre profil utilisateur, ou connectez-vous avec un compte administrateur."
        )

    if not verify_mistral_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clé API Mistral invalide. Vérifiez que vous avez copié la bonne clé."
        )

    return api_key


async def async_require_mistral_api_key(
    mistral_api_key: Optional[str] = None,
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None
) -> str:
    """
    Version asynchrone de require_mistral_api_key.

    Args:
        mistral_api_key: Clé API Mistral fournie directement
        m3c_api_key: Cookie d'authentification M3C
        authorization: Header Authorization Bearer

    Returns:
        La clé API Mistral valide

    Raises:
        HTTPException: Si aucune clé valide n'est disponible
    """
    # Si une clé Mistral est fournie directement, l'utiliser
    if mistral_api_key:
        if not verify_mistral_api_key(mistral_api_key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clé API Mistral invalide. Vérifiez que vous avez copié la bonne clé."
            )
        return mistral_api_key

    # Sinon, identifier l'utilisateur connecté
    user_id = auth.user_id_from_token(m3c_api_key)
    if user_id is None:
        user_id = auth.user_id_from_authorization(authorization)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API Mistral requise. Veuillez configurer votre clé API Mistral dans votre profil utilisateur, ou connectez-vous avec un compte administrateur."
        )

    api_key, role = await _resolve_user_api_key(user_id)

    if role in SERVER_KEY_ROLES and not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="La clé API Mistral du serveur n'est pas configurée. Veuillez contacter l'administrateur."
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API Mistral requise. Veuillez configurer votre clé API Mistral dans votre profil utilisateur."
        )

    if not verify_mistral_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clé API Mistral invalide. Vérifiez que vous avez copié la bonne clé dans votre profil."
        )

    return api_key
