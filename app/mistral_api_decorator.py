"""
Décorateurs pour la gestion de la clé API Mistral.

Ce module fournit des décorateurs pour simplifier l'ajout de la vérification
de la clé API Mistral aux endpoints FastAPI.
"""

from functools import wraps
from typing import Optional, Callable, Awaitable
from fastapi import HTTPException, status, Cookie, Header

from mistral_api_key_manager import async_require_mistral_api_key


def require_mistral_api_key_decorator(
    mistral_api_key_param: str = "mistral_api_key",
    m3c_api_key_param: str = "m3c_api_key",
    authorization_param: str = "authorization"
) -> Callable:
    """
    Décorateur pour ajouter la vérification de la clé API Mistral à un endpoint.
    
    Args:
        mistral_api_key_param: Nom du paramètre pour la clé API Mistral
        m3c_api_key_param: Nom du paramètre pour le cookie M3C
        authorization_param: Nom du paramètre pour le header Authorization
        
    Returns:
        Décorateur à appliquer aux endpoints
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extraire les paramètres de la requête
            mistral_api_key = kwargs.get(mistral_api_key_param)
            m3c_api_key = kwargs.get(m3c_api_key_param)
            authorization = kwargs.get(authorization_param)
            
            # Vérifier la clé API Mistral
            try:
                api_key = await async_require_mistral_api_key(
                    mistral_api_key, m3c_api_key, authorization
                )
                # Si on arrive ici, la clé est valide
                # On peut ajouter la clé aux kwargs si nécessaire
                kwargs['mistral_api_key'] = api_key
                return await func(*args, **kwargs)
            except HTTPException:
                raise
        
        return wrapper
    return decorator


def require_mistral_api_key_for_query(func: Callable) -> Callable:
    """
    Décorateur simplifié pour les endpoints de query qui acceptent :
    - mistral_api_key: Optional[str] = None
    - m3c_api_key: Optional[str] = Cookie(default=None)
    - authorization: Optional[str] = None
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        mistral_api_key = kwargs.get('mistral_api_key')
        m3c_api_key = kwargs.get('m3c_api_key')
        authorization = kwargs.get('authorization')
        
        try:
            api_key = await async_require_mistral_api_key(
                mistral_api_key, m3c_api_key, authorization
            )
            kwargs['mistral_api_key'] = api_key
            return await func(*args, **kwargs)
        except HTTPException:
            raise
    
    return wrapper
