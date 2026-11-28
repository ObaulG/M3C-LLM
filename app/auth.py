import json
import secrets
import time
from typing import Any, Dict, Optional, Tuple

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


VALID_ROLES = ("global_admin", "admin", "validator", "user", "guest")

# Rôle attribué à tout compte créé via l'inscription publique :
# un simple utilisateur est enregistré comme "guest" (pas "user"),
# et devra renseigner sa propre clé API Mistral pour interroger le serveur.
DEFAULT_REGISTER_ROLE = "guest"

GENDER_OPTIONS = ("Femme", "Homme", "Autre")
AGE_RANGE_OPTIONS = ("Moins de 18 ans", "18-25 ans", "26-40 ans", "41-60 ans", "Plus de 60 ans")
ACADEMIC_STATUS_OPTIONS = ("Étudiant", "Enseignant", "Personnel administratif", "Extérieur")
SEARCH_GOAL_OPTIONS = (
    "Explorer les collections et ressources documentaires",
    "Rechercher des documents sur un sujet précis",
    "Découvrir la culture corse",
    "Utiliser le chatbot / les outils IA",
    "Préparer un cours ou un support pédagogique",
    "Réviser ou m'auto-évaluer",
    "Tester l'application (prototype)",
    "Autre",
)


def _validate_profile_info(
    gender: Optional[str],
    age_range: Optional[str],
    academic_status: Optional[str],
    search_goals: Optional[list],
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[list]]:
    if gender is not None and gender not in GENDER_OPTIONS:
        raise ValueError("Valeur de sexe invalide.")
    if age_range is not None and age_range not in AGE_RANGE_OPTIONS:
        raise ValueError("Tranche d'âge invalide.")
    if academic_status is not None and academic_status not in ACADEMIC_STATUS_OPTIONS:
        raise ValueError("Statut universitaire invalide.")
    goals = None
    if search_goals:
        goals = []
        for goal in search_goals:
            goal = (goal or "").strip()
            if not goal:
                continue
            if goal not in SEARCH_GOAL_OPTIONS:
                raise ValueError("Objectif de recherche invalide.")
            if goal not in goals:
                goals.append(goal)
    return gender, age_range, academic_status, goals


def _encode_search_goals(search_goals: Optional[list]) -> Optional[str]:
    if not search_goals:
        return None
    return json.dumps(search_goals, ensure_ascii=False)


def _decode_search_goals(raw: Any) -> list:
    if not raw:
        return []
    if isinstance(raw, list):
        return list(raw)
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return decoded if isinstance(decoded, list) else []


async def create_user(
    username: str,
    email: str,
    password: str,
    role: str = DEFAULT_REGISTER_ROLE,
    gender: Optional[str] = None,
    age_range: Optional[str] = None,
    academic_status: Optional[str] = None,
    search_goals: Optional[list] = None,
) -> Tuple[Dict[str, Any], str]:
    if role not in VALID_ROLES:
        raise ValueError(f"Rôle invalide : {role}")
    if len(password) < 6:
        raise ValueError("Le mot de passe doit faire au moins 6 caractères.")
    gender, age_range, academic_status, search_goals = _validate_profile_info(
        gender, age_range, academic_status, search_goals
    )
    password_hash = _hash_password(password)
    async with await get_db_connection() as conn :
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO user (name, email, password_hash, role, is_active, created)
                    VALUES (%s, %s, %s, %s, TRUE, NOW())
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

                if gender or age_range or academic_status or search_goals:
                    await _upsert_profile_info(
                        cur, user_id, gender, age_range, academic_status, search_goals
                    )
            user = {
                "user_id": user[0],
                "username": user[1],
                "email": user[2],
                "role": user[3],
                "is_active": bool(user[4]),
                "created_at": user[5].isoformat() if user[5] else None,
                "gender": gender,
                "age_range": age_range,
                "academic_status": academic_status,
                "search_goals": search_goals or [],
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
            raise



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
        user = {
            "user_id": row[0],
            "username": row[1],
            "email": row[2],
            "role": row[3],
            "is_active": bool(row[4]),
            "created_at": row[5].isoformat() if row[5] else None,
        }
        user.update(await get_user_profile_info(user_id) or {})
        return user


async def _upsert_profile_info(
    cur,
    user_id: int,
    gender: Optional[str],
    age_range: Optional[str],
    academic_status: Optional[str],
    search_goals: Optional[list],
) -> None:
    await cur.execute(
        """
        INSERT INTO user_profile_info (user_id, gender, age_range, academic_status, search_goals)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            gender = VALUES(gender),
            age_range = VALUES(age_range),
            academic_status = VALUES(academic_status),
            search_goals = VALUES(search_goals);
        """,
        (
            user_id,
            gender,
            age_range,
            academic_status,
            _encode_search_goals(search_goals),
        ),
    )


async def get_user_profile_info(user_id: int) -> Optional[Dict[str, Any]]:
    """Retourne les informations de profil de la table dediee `user_profile_info`."""
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT gender, age_range, academic_status, search_goals
                FROM user_profile_info
                WHERE user_id = %s;
                """,
                (user_id,),
            )
            row = await cur.fetchone()
    if row is None:
        return None
    return {
        "gender": row[0],
        "age_range": row[1],
        "academic_status": row[2],
        "search_goals": _decode_search_goals(row[3]),
    }


async def update_user_profile_info(
    user_id: int,
    gender: Optional[str],
    age_range: Optional[str],
    academic_status: Optional[str],
    search_goals: Optional[list],
) -> Dict[str, Any]:
    gender, age_range, academic_status, search_goals = _validate_profile_info(
        gender, age_range, academic_status, search_goals
    )
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await _upsert_profile_info(
                cur, user_id, gender, age_range, academic_status, search_goals
            )
    return {
        "gender": gender,
        "age_range": age_range,
        "academic_status": academic_status,
        "search_goals": search_goals or [],
    }



async def get_user_mistral_api_key(user_id: int) -> Optional[str]:
    """Retourne la clé API Mistral de l'utilisateur (table user_mistral_api_keys)."""
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT mistral_api_key FROM user_mistral_api_keys WHERE user_id = %s;",
                (user_id,),
            )
            row = await cur.fetchone()
    if row is None:
        return None
    return row[0]


async def set_user_mistral_api_key(user_id: int, api_key: Optional[str]) -> None:
    """Enregistre (ou efface) la clé API Mistral de l'utilisateur.

    La clé est stockée dans la table dédiée `user_mistral_api_keys`, sans
    modifier la table `user`.
    """
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            if api_key:
                await cur.execute(
                    """
                    INSERT INTO user_mistral_api_keys (user_id, mistral_api_key)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE mistral_api_key = VALUES(mistral_api_key);
                    """,
                    (user_id, api_key),
                )
            else:
                await cur.execute(
                    "DELETE FROM user_mistral_api_keys WHERE user_id = %s;",
                    (user_id,),
                )


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
