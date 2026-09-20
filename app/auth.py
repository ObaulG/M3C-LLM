import secrets
import time
from typing import Optional, Tuple, Dict, Any

import bcrypt
from psycopg import AsyncConnection
from psycopg.errors import UniqueViolation

from database.database import DB_CONFIG, get_db_connection


_ACTIVE_TOKENS: Dict[str, Tuple[int, float]] = {}
_TOKEN_TTL_SECONDS = 60 * 60 * 24


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=10),
    ).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def _issue_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    _ACTIVE_TOKENS[token] = (user_id, time.time())
    return token


def _revoke_token(token: str) -> None:
    _ACTIVE_TOKENS.pop(token, None)


def _user_id_from_token(token: Optional[str]) -> Optional[int]:
    if not token:
        return None
    entry = _ACTIVE_TOKENS.get(token)
    if entry is None:
        return None
    user_id, issued_at = entry
    if time.time() - issued_at > _TOKEN_TTL_SECONDS:
        _ACTIVE_TOKENS.pop(token, None)
        return None
    return user_id


def _purge_expired_tokens() -> None:
    now = time.time()
    expired = [t for t, (_, ts) in _ACTIVE_TOKENS.items() if now - ts > _TOKEN_TTL_SECONDS]
    for t in expired:
        _ACTIVE_TOKENS.pop(t, None)


VALID_ROLES = ("admin", "validator", "user")


async def create_user(username: str, email: str, password: str, role: str = "user") -> Tuple[Dict[str, Any], str]:
    if role not in VALID_ROLES:
        raise ValueError(f"Rôle invalide : {role}")
    if len(password) < 6:
        raise ValueError("Le mot de passe doit faire au moins 6 caractères.")
    password_hash = _hash_password(password)
    async with await get_db_connection() as conn :
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO user (name, email, password_hash, role, is_active)
                    VALUES (%s, %s, %s, %s, TRUE)
                    """,
                    (username, email, password_hash, role),
                )

                user_id = cur.lastrowid

                await cur.execute(
                    """
                    SELECT id, name, email, role, is_active, created
                    FROM user
                    WHERE id = %s
                    """,
                    (user_id,),
                )

                user = await cur.fetchone()
            user = {
                "user_id": user[0],
                "username": user[1],
                "email": user[2],
                "role": user[3],
                "is_active": bool(user[4]),
                "created_at": user[5].isoformat() if user[5] else None,
            }
            token = _issue_token(user["user_id"])
            return user, token
        except UniqueViolation as e:
            await conn.rollback()
            constraint = getattr(e.diag, "constraint_name", "") or ""
            if "name" in constraint:
                raise ValueError("Ce nom d'utilisateur est déjà utilisé.")
            if "email" in constraint:
                raise ValueError("Cet email est déjà utilisé.")
            raise ValueError("Utilisateur déjà existant.")
        except Exception as e:
            print(e)
            await conn.rollback()



async def authenticate_user(identifier: str, password: str) -> Tuple[Dict[str, Any], str]:
    async with await get_db_connection() as conn :
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, name, email, password_hash, role, is_active, created
                FROM user
                WHERE name = %s OR email = %s;
                """,
                (identifier, identifier),
            )
            row = await cur.fetchone()
        if row is None:
            raise ValueError("Identifiants incorrects.")
        user_id, name, email, password_hash, role, is_active, created = row
        if not is_active:
            raise ValueError("Ce compte est désactivé.")
        if not _verify_password(password, password_hash):
            raise ValueError("Identifiants incorrects.")
        user = {
            "user_id": user_id,
            "username": name,
            "email": email,
            "role": role,
            "is_active": bool(is_active),
            "created_at": created.isoformat() if created else None,
        }
        token = _issue_token(user_id)
        return user, token


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    async with await get_db_connection() as conn :
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, name, email, role, is_active, created
                FROM user
                WHERE id = %s;
                """,
                (user_id,),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return {
            "user_id": row[0],
            "username": row[1],
            "email": row[2],
            "role": row[3],
            "is_active": bool(row[4]),
            "created_at": row[5].isoformat() if row[5] else None,
        }



def _token_from_authorization(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    return parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else parts[0]


def user_id_from_token(token: Optional[str]) -> Optional[int]:
    _purge_expired_tokens()
    return _user_id_from_token(token)


def user_id_from_authorization(authorization: Optional[str]) -> Optional[int]:
    return user_id_from_token(_token_from_authorization(authorization))


def revoke_token(authorization: Optional[str]) -> None:
    if not authorization:
        return
    parts = authorization.split(" ", 1)
    token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else parts[0]
    _revoke_token(token)
