"""
Gestionnaire de clé API Mistral.

Ce module fournit des utilitaires pour :
- Vérifier si une clé API Mistral est valide
- Obtenir la clé API depuis le localStorage (côté client) ou les cookies
- Vérifier si l'utilisateur est un global_admin
- Déterminer quelle clé utiliser (clé utilisateur ou clé serveur)
"""

import os
from typing import Optional
from fastapi import HTTPException, status, Cookie
import auth


def get_mistral_api_key_from_request(
    mistral_api_key: Optional[str] = None,
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None
) -> Optional[str]:
    """
    Obtient la clé API Mistral à utiliser pour une requête.
    
    Ordre de priorité :
    1. Si mistral_api_key est fourni directement, l'utiliser
    2. Sinon, vérifier si l'utilisateur est un global_admin -> utiliser la clé serveur
    3. Sinon, retourner None (la requête sera refusée)
    
    Args:
        mistral_api_key: Clé API Mistral fournie directement dans les paramètres
        m3c_api_key: Cookie d'authentification M3C
        authorization: Header Authorization Bearer
        
    Returns:
        La clé API Mistral à utiliser, ou None si aucune clé valide n'est disponible
    """
    # Si une clé Mistral est fournie directement, l'utiliser
    if mistral_api_key:
        return mistral_api_key
    
    # Sinon, vérifier si l'utilisateur est connecté
    user_id = auth.user_id_from_token(m3c_api_key)
    if user_id is None:
        user_id = auth.user_id_from_authorization(authorization)
    
    if user_id is None:
        return None
    
    # Vérifier si l'utilisateur est un global_admin ou s'il a enregistré
    # sa propre clé API Mistral dans son compte (table user)
    import asyncio
    from database.database import get_db_connection
    
    async def check_user_role():
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT role, mistral_api_key FROM user WHERE id = %s",
                    (user_id,)
                )
                row = await cursor.fetchone()
                if row and row[0] == 'global_admin':
                    # Retourner la clé serveur
                    return os.getenv('MISTRAL_API_KEY')
                if row and row[1]:
                    # Retourner la clé enregistrée dans le compte utilisateur
                    return row[1]
                return None
    
    # Exécuter la vérification de manière synchrone
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        server_key = loop.run_until_complete(check_user_role())
        if server_key:
            return server_key
    except Exception:
        pass
    
    return None


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
    
    # Format de base : commence par 'x' et a au moins 30 caractères
    if not api_key.startswith('x'):
        return False
    
    if len(api_key) < 30:
        return False
    
    # Format typique : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    parts = api_key.split('-')
    if len(parts) == 5:
        if all(len(part) > 0 for part in parts):
            return True
    
    # Certains formats peuvent ne pas avoir de tirets
    return len(api_key) >= 30


def require_mistral_api_key(
    mistral_api_key: Optional[str] = None,
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None
) -> str:
    """
    Vérifie qu'une clé API Mistral est disponible et valide.
    
    Si l'utilisateur est un global_admin, utilise la clé serveur.
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
            detail="Clé API Mistral requise. Veuillez configurer votre clé API Mistral dans votre profil utilisateur, ou connectez-vous avec un compte administrateur (global_admin)."
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
    
    # Sinon, vérifier si l'utilisateur est connecté
    user_id = auth.user_id_from_token(m3c_api_key)
    if user_id is None:
        user_id = auth.user_id_from_authorization(authorization)
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API Mistral requise. Veuillez configurer votre clé API Mistral dans votre profil utilisateur, ou connectez-vous avec un compte administrateur (global_admin)."
        )
    
    # Vérifier si l'utilisateur est un global_admin (clé serveur) ou s'il
    # a enregistré sa propre clé API Mistral dans son compte
    from database.database import get_db_connection
    
    async with await get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT role, mistral_api_key FROM user WHERE id = %s",
                (user_id,)
            )
            row = await cursor.fetchone()
            if row and row[0] == 'global_admin':
                # Utiliser la clé serveur
                server_key = os.getenv('MISTRAL_API_KEY')
                if not server_key:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="La clé API Mistral du serveur n'est pas configurée. Veuillez contacter l'administrateur."
                    )
                return server_key
            if row and row[1]:
                return row[1]
    
    # Si l'utilisateur n'est pas global_admin et n'a pas enregistré de clé
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Clé API Mistral requise. Veuillez configurer votre clé API Mistral dans votre profil utilisateur."
    )
