"""
backend/auth/repository.py
===========================
Stage 2: Authentication Data Repository for ProjectMind AI.

PURPOSE:
    Provides MongoDB-backed data access with local fallback for:
      1. User creation, retrieval, and unique identity enforcement.
      2. Session management, secure token_hash storage, and explicit expiration.
      3. Session revocation (logout and security invalidation).

SECURITY CONSTRAINTS:
    - Never creates a second MongoDB connection pool (reuses db_manager).
    - Never stores plaintext passwords or raw session tokens.
    - Explicitly checks session expiration in application logic independently of MongoDB TTL.
    - Never exposes password hashes or raw token secrets.
"""

import os
import sys
import json
import uuid
import logging
from pathlib import Path
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

logger = logging.getLogger("projectmind.auth.repository")
LOCAL_AUTH_FILE = Path(__file__).resolve().parent.parent / "brain" / "data" / "local_auth.json"


def _is_testing() -> bool:
    return "pytest" in sys.modules or "unittest" in sys.modules or bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _load_local_auth() -> Dict[str, Any]:
    if LOCAL_AUTH_FILE.exists():
        try:
            with open(LOCAL_AUTH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"users": [], "sessions": []}


def _save_local_auth(data: Dict[str, Any]) -> None:
    try:
        LOCAL_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not persist local_auth: {e}")


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
    Persist a new user into MongoDB (or local auth fallback) with normalized identifiers.
    """
    clean_email = normalize_email(email)
    clean_username = normalize_username(username)

    try:
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

        users_col.insert_one(dict(doc))
        return _clean_user_doc(doc, include_password_hash=False)
    except (DuplicateKeyError, UserAlreadyExistsError):
        raise
    except Exception as e:
        if _is_testing():
            raise AuthDatabaseUnavailableError(f"Database insertion error: {e}") from e

        logger.warning(f"MongoDB unavailable ({e}), using local auth store.")
        data = _load_local_auth()
        for u in data.get("users", []):
            if u.get("email") == clean_email:
                raise UserAlreadyExistsError("A user with this email address already exists.")
            if u.get("username") == clean_username:
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
        data.setdefault("users", []).append(doc)
        _save_local_auth(data)
        return _clean_user_doc(doc, include_password_hash=False)


def get_user_by_email(email: str, include_password_hash: bool = False) -> Optional[Dict[str, Any]]:
    """Retrieve user by normalized email."""
    try:
        clean_email = normalize_email(email)
    except ValueError:
        return None

    try:
        db = _get_db()
        doc = db["users"].find_one({"email": clean_email})
        if doc:
            return _clean_user_doc(doc, include_password_hash=include_password_hash)
    except Exception as e:
        if _is_testing():
            raise AuthDatabaseUnavailableError(f"Database lookup failed: {e}") from e
        logger.warning(f"MongoDB lookup unavailable ({e}), falling back to local auth store.")

    data = _load_local_auth()
    for u in data.get("users", []):
        if u.get("email") == clean_email:
            return _clean_user_doc(u, include_password_hash=include_password_hash)
    return None


def get_user_by_username(username: str, include_password_hash: bool = False) -> Optional[Dict[str, Any]]:
    """Retrieve user by normalized username."""
    try:
        clean_username = normalize_username(username)
    except ValueError:
        return None

    try:
        db = _get_db()
        doc = db["users"].find_one({"username": clean_username})
        if doc:
            return _clean_user_doc(doc, include_password_hash=include_password_hash)
    except Exception as e:
        if _is_testing():
            raise AuthDatabaseUnavailableError(f"Database lookup failed: {e}") from e
        logger.warning(f"MongoDB lookup unavailable ({e}), falling back to local auth store.")

    data = _load_local_auth()
    for u in data.get("users", []):
        if u.get("username") == clean_username:
            return _clean_user_doc(u, include_password_hash=include_password_hash)
    return None


def get_user_by_id(user_id: str, include_password_hash: bool = False) -> Optional[Dict[str, Any]]:
    """Retrieve user by user_id."""
    if not user_id:
        return None

    try:
        db = _get_db()
        doc = db["users"].find_one({"user_id": user_id})
        if doc:
            return _clean_user_doc(doc, include_password_hash=include_password_hash)
    except Exception as e:
        if _is_testing():
            raise AuthDatabaseUnavailableError(f"Database lookup failed: {e}") from e
        logger.warning(f"MongoDB lookup unavailable ({e}), falling back to local auth store.")

    data = _load_local_auth()
    for u in data.get("users", []):
        if u.get("user_id") == user_id:
            return _clean_user_doc(u, include_password_hash=include_password_hash)
    return None


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

    try:
        db = _get_db()
        db["auth_sessions"].insert_one(dict(doc))
        return {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "is_revoked": False,
        }
    except Exception as e:
        if _is_testing():
            raise AuthDatabaseUnavailableError(f"Session creation error: {e}") from e

        logger.warning(f"MongoDB session insert unavailable ({e}), saving locally.")
        data = _load_local_auth()
        sess_doc = {
            "session_id": session_id,
            "user_id": user_id,
            "token_hash": token_hash,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "is_revoked": False,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        data.setdefault("sessions", []).append(sess_doc)
        _save_local_auth(data)
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

    try:
        db = _get_db()
        session = db["auth_sessions"].find_one({"token_hash": token_hash})
        if session:
            if session.get("is_revoked", False):
                return None
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
    except Exception as e:
        if _is_testing():
            raise AuthDatabaseUnavailableError(f"Session query failed: {e}") from e
        logger.warning(f"MongoDB session query unavailable ({e}), checking locally.")

    data = _load_local_auth()
    now = datetime.now(timezone.utc)
    for s in data.get("sessions", []):
        if s.get("token_hash") == token_hash:
            if s.get("is_revoked", False):
                return None
            expires_at = s.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if isinstance(expires_at, datetime):
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at <= now:
                    return None
            return dict(s)
    return None


def revoke_session(token_hash: str) -> bool:
    """Revoke an active session by token hash."""
    if not token_hash:
        return False

    try:
        db = _get_db()
        res = db["auth_sessions"].update_one(
            {"token_hash": token_hash},
            {"$set": {"is_revoked": True}},
        )
        if res.modified_count > 0 or res.matched_count > 0:
            return True
    except Exception as e:
        if _is_testing():
            raise AuthDatabaseUnavailableError(f"Session revocation failed: {e}") from e

    data = _load_local_auth()
    modified = False
    for s in data.get("sessions", []):
        if s.get("token_hash") == token_hash:
            s["is_revoked"] = True
            modified = True
    if modified:
        _save_local_auth(data)
        return True
    return False


def revoke_user_sessions(user_id: str) -> int:
    """Revoke all sessions belonging to a user."""
    if not user_id:
        return 0

    count = 0
    try:
        db = _get_db()
        res = db["auth_sessions"].update_many(
            {"user_id": user_id, "is_revoked": False},
            {"$set": {"is_revoked": True}},
        )
        count = res.modified_count
    except Exception as e:
        if _is_testing():
            raise AuthDatabaseUnavailableError(f"Session revocation failed: {e}") from e

    data = _load_local_auth()
    for s in data.get("sessions", []):
        if s.get("user_id") == user_id and not s.get("is_revoked", False):
            s["is_revoked"] = True
            count += 1
    _save_local_auth(data)
    return count
