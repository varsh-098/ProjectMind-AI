"""
backend/auth/repository.py
===========================
Stage 2: Authentication Data Repository for ProjectMind AI.

PURPOSE:
    Provides MongoDB-backed data access for:
      1. User creation, retrieval, and unique identity enforcement.
      2. Session management, secure token_hash storage, and explicit expiration.
      3. Session revocation (logout and security invalidation).

SECURITY CONSTRAINTS:
    - Never creates a second MongoDB connection pool (reuses db_manager).
    - Never stores plaintext passwords or raw session tokens.
    - Fails closed if MongoDB is unconfigured or unreachable.
    - Explicitly checks session expiration in application logic independently of MongoDB TTL.
    - Never exposes password hashes or raw token secrets.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

try:
    from pymongo.errors import DuplicateKeyError, PyMongoError
except ImportError:
    DuplicateKeyError = Exception
    PyMongoError = Exception

from backend.db.client import db_manager
from backend.auth.security import (
    hash_session_token,
    normalize_email,
    normalize_username,
)


class AuthDatabaseUnavailableError(RuntimeError):
    """Raised when authentication operations cannot reach MongoDB (fail-closed)."""
    pass


class UserAlreadyExistsError(ValueError):
    """Raised when an email or username is already registered."""
    pass


def _get_db():
    """Retrieve database or fail closed."""
    if not db_manager.is_configured:
        raise AuthDatabaseUnavailableError(
            "Authentication database is unavailable: MONGODB_URI is not configured."
        )
    try:
        return db_manager.get_database()
    except Exception as e:
        raise AuthDatabaseUnavailableError(
            f"Authentication database connection failed: {e}"
        ) from e


def _clean_user_doc(doc: Dict[str, Any], include_password_hash: bool = False) -> Dict[str, Any]:
    """Sanitize user document by removing MongoDB _id and optionally password_hash."""
    user = dict(doc)
    user.pop("_id", None)
    if not include_password_hash:
        user.pop("password_hash", None)
    return user


# =====================================================================
# 1. User Management
# =====================================================================

def create_user(
    username: str,
    email: str,
    password_hash: str,
    role: str = "developer",
) -> Dict[str, Any]:
    """
    Persist a new user into MongoDB with normalized identifiers.

    Raises:
        UserAlreadyExistsError: If normalized email or username is already registered.
        AuthDatabaseUnavailableError: If MongoDB is unavailable (fails closed).
    """
    clean_email = normalize_email(email)
    clean_username = normalize_username(username)

    db = _get_db()
    users_col = db["users"]

    # Pre-check for duplicate email or username
    existing = users_col.find_one(
        {"$or": [{"email": clean_email}, {"username": clean_username}]},
        {"_id": 0, "email": 1, "username": 1},
    )
    if existing:
        if existing.get("email") == clean_email:
            raise UserAlreadyExistsError("A user with this email address already exists.")
        raise UserAlreadyExistsError("A user with this username already exists.")

    now = datetime.now(timezone.utc)
    user_id = str(uuid.uuid4())

    doc = {
        "user_id": user_id,
        "username": clean_username,
        "email": clean_email,
        "password_hash": password_hash,
        "role": role,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "is_active": True,
    }

    try:
        users_col.insert_one(dict(doc))
    except DuplicateKeyError as e:
        raise UserAlreadyExistsError("Email or username is already registered.") from e
    except PyMongoError as e:
        raise AuthDatabaseUnavailableError(f"Database insertion error: {e}") from e

    return _clean_user_doc(doc, include_password_hash=False)


def get_user_by_email(email: str, include_password_hash: bool = False) -> Optional[Dict[str, Any]]:
    """Retrieve user by normalized email."""
    try:
        clean_email = normalize_email(email)
    except ValueError:
        return None

    db = _get_db()
    doc = db["users"].find_one({"email": clean_email})
    if not doc:
        return None
    return _clean_user_doc(doc, include_password_hash=include_password_hash)


def get_user_by_username(username: str, include_password_hash: bool = False) -> Optional[Dict[str, Any]]:
    """Retrieve user by normalized username."""
    try:
        clean_username = normalize_username(username)
    except ValueError:
        return None

    db = _get_db()
    doc = db["users"].find_one({"username": clean_username})
    if not doc:
        return None
    return _clean_user_doc(doc, include_password_hash=include_password_hash)


def get_user_by_id(user_id: str, include_password_hash: bool = False) -> Optional[Dict[str, Any]]:
    """Retrieve user by user_id."""
    if not user_id:
        return None

    db = _get_db()
    doc = db["users"].find_one({"user_id": user_id})
    if not doc:
        return None
    return _clean_user_doc(doc, include_password_hash=include_password_hash)


# =====================================================================
# 2. Authentication Sessions
# =====================================================================

def create_auth_session(
    user_id: str,
    raw_token: str,
    expires_in_days: int = 7,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Persist an authentication session.
    Stores ONLY the SHA-256 hash of the token. Raw token is never written to DB.
    """
    token_hash = hash_session_token(raw_token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=expires_in_days)
    session_id = str(uuid.uuid4())

    doc = {
        "session_id": session_id,
        "user_id": user_id,
        "token_hash": token_hash,
        "created_at": now,
        "expires_at": expires_at,
        "is_revoked": False,
        "ip_address": ip_address,
        "user_agent": user_agent,
    }

    db = _get_db()
    try:
        db["auth_sessions"].insert_one(dict(doc))
    except PyMongoError as e:
        raise AuthDatabaseUnavailableError(f"Session creation error: {e}") from e

    # Return safe metadata (excluding token_hash and _id)
    return {
        "session_id": session_id,
        "user_id": user_id,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "is_revoked": False,
    }


def get_session_by_token_hash(token_hash: str) -> Optional[Dict[str, Any]]:
    """
    Lookup session by SHA-256 token hash.
    Explicitly checks expiration in application code independently of MongoDB TTL.
    """
    if not token_hash:
        return None

    db = _get_db()
    session = db["auth_sessions"].find_one({"token_hash": token_hash})
    if not session:
        return None

    # Check revocation
    if session.get("is_revoked", False):
        return None

    # Check expiration explicitly
    now = datetime.now(timezone.utc)
    expires_at = session.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            return None

    session.pop("_id", None)
    return session


def revoke_session(token_hash: str) -> bool:
    """Revoke an active session by token hash."""
    if not token_hash:
        return False

    db = _get_db()
    res = db["auth_sessions"].update_one(
        {"token_hash": token_hash},
        {"$set": {"is_revoked": True}},
    )
    return res.modified_count > 0 or res.matched_count > 0


def revoke_user_sessions(user_id: str) -> int:
    """Revoke all sessions belonging to a user (e.g. on password change)."""
    if not user_id:
        return 0

    db = _get_db()
    res = db["auth_sessions"].update_many(
        {"user_id": user_id, "is_revoked": False},
        {"$set": {"is_revoked": True}},
    )
    return res.modified_count

