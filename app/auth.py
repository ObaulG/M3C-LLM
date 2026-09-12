import hashlib
import secrets
import time
from typing import Optional, Tuple, Dict, Any

from psycopg import AsyncConnection
from psycopg.errors import UniqueViolation

from database.database import DB_CONFIG, get_db_connection


_ACTIVE_TOKENS: Dict[str, int] = {}
_TOKEN_TTL_SECONDS = 60 * 60 * 24


def _hash_password(password: str, salt: bytes) -> str:
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return salt.hex() + ":" + h.hex()


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, expected_hash_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hash_hex)
    except (ValueError, AttributeError):
        return False
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return secrets.compare_digest(h, expected)


def _issue_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    _ACTIVE_TOKENS[token] = user_id
    return token


def _revoke_token(token: str) -> None:
    _ACTIVE_TOKENS.pop(token, None)


def _user_id_from_token(token: Optional[str]) -> Optional[int]:
    if not token:
        return None
    return _ACTIVE_TOKENS.get(token)


def _purge_expired_tokens() -> None:
    now = time.time()
    expired = [t for t, ts in _ACTIVE_TOKENS.items() if now - ts > _TOKEN_TTL_SECONDS]
    for t in expired:
        _ACTIVE_TOKENS.pop(t, None)


VALID_ROLES = ("admin", "validator", "user")


async def create_user(username: str, email: str, password: str, role: str = "user") -> Tuple[Dict[str, Any], str]:
    if role not in VALID_ROLES:
        raise ValueError(f"Rôle invalide : {role}")
    if len(password) < 6:
        raise ValueError("Le mot de passe doit faire au moins 6 caractères.")
    password_hash = _hash_password(password, secrets.token_bytes(16))
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO users (username, email, password_hash, role, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING user_id, username, email, role, is_active, created_at;
                """,
                (username, email, password_hash, role),
            )
            row = await cur.fetchone()
            await conn.commit()
        user = {
            "user_id": row[0],
            "username": row[1],
            "email": row[2],
            "role": row[3],
            "is_active": bool(row[4]),
            "created_at": row[5].isoformat() if row[5] else None,
        }
        token = _issue_token(user["user_id"])
        return user, token
    except UniqueViolation as e:
        await conn.rollback()
        constraint = getattr(e.diag, "constraint_name", "") or ""
        if "username" in constraint:
            raise ValueError("Ce nom d'utilisateur est déjà utilisé.")
        if "email" in constraint:
            raise ValueError("Cet email est déjà utilisé.")
        raise ValueError("Utilisateur déjà existant.")
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()


async def authenticate_user(identifier: str, password: str) -> Tuple[Dict[str, Any], str]:
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT user_id, username, email, password_hash, role, is_active, created_at
                FROM users
                WHERE username = %s OR email = %s;
                """,
                (identifier, identifier),
            )
            row = await cur.fetchone()
        if row is None:
            raise ValueError("Identifiants incorrects.")
        user_id, username, email, password_hash, role, is_active, created_at = row
        if not is_active:
            raise ValueError("Ce compte est désactivé.")
        if not _verify_password(password, password_hash):
            raise ValueError("Identifiants incorrects.")
        user = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "role": role,
            "is_active": bool(is_active),
            "created_at": created_at.isoformat() if created_at else None,
        }
        token = _issue_token(user_id)
        return user, token
    finally:
        await conn.close()


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT user_id, username, email, role, is_active, created_at
                FROM users
                WHERE user_id = %s;
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
    finally:
        await conn.close()


def user_id_from_authorization(authorization: Optional[str]) -> Optional[int]:
    _purge_expired_tokens()
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else parts[0]
    return _user_id_from_token(token)


def revoke_token(authorization: Optional[str]) -> None:
    if not authorization:
        return
    parts = authorization.split(" ", 1)
    token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else parts[0]
    _revoke_token(token)
