"""
backend/auth/security.py
=========================
Stage 1: Database and Security Foundation.

PURPOSE:
    Provides cryptographic utilities for user authentication:
      1. Argon2id password hashing and verification.
      2. Cryptographically secure random session token generation.
      3. SHA-256 session token hashing (raw tokens are never persisted).
      4. String normalization (emails, usernames).

SECURITY STANDARDS:
    - OWASP #1 password hashing standard (Argon2id).
    - Session tokens generated with system CSPRNG (secrets module).
    - Database stores token_hash = SHA256(raw_token); raw token lives only in client HttpOnly cookie.
"""

import hashlib
import re
import secrets
from typing import Optional

try:
    from argon2 import PasswordHasher, Type
    from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False
    PasswordHasher = None
    Type = None
    VerifyMismatchError = Exception
    VerificationError = Exception
    InvalidHashError = Exception


# Initialize Argon2id password hasher
# Parameters adhere to OWASP recommendations:
#   - time_cost: 2 iterations
#   - memory_cost: 65536 KiB (64 MiB)
#   - parallelism: 1 thread
#   - hash_len: 32 bytes
#   - type: Type.ID (Argon2id: hybrid resistant to side-channel and GPU attacks)
if HAS_ARGON2:
    _hasher = PasswordHasher(
        time_cost=2,
        memory_cost=65536,
        parallelism=1,
        hash_len=32,
        type=Type.ID,
    )
else:
    _hasher = None


# =====================================================================
# 1. Password Hashing & Verification (Argon2id)
# =====================================================================

def hash_password(plain_password: str) -> str:
    """
    Hash a plain password using Argon2id.

    Raises:
        RuntimeError: If argon2-cffi is not installed.
        ValueError: If password length is invalid (<8 or >128 characters).
    """
    if not HAS_ARGON2 or _hasher is None:
        raise RuntimeError("argon2-cffi is not installed. Install it with: pip install argon2-cffi")

    if not plain_password or len(plain_password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    if len(plain_password) > 128:
        raise ValueError("Password cannot exceed 128 characters.")

    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against an Argon2id hash.
    Safely returns False on mismatch or corrupted hash format without leaking timing.
    """
    if not HAS_ARGON2 or _hasher is None:
        raise RuntimeError("argon2-cffi is not installed. Install it with: pip install argon2-cffi")

    if not plain_password or not hashed_password:
        return False

    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception:
        return False


def check_needs_rehash(hashed_password: str) -> bool:
    """Check if hash parameters are outdated and need rehashing."""
    if not HAS_ARGON2 or _hasher is None or not hashed_password:
        return False
    try:
        return _hasher.check_needs_rehash(hashed_password)
    except Exception:
        return False


# =====================================================================
# 2. Cryptographic Session Token Generation & Hashing
# =====================================================================

def generate_session_token(nbytes: int = 32) -> str:
    """
    Generate a cryptographically secure random session token.
    Uses Python's secrets module (backed by os.urandom CSPRNG).
    Default 32 bytes yields 43 URL-safe characters with 256 bits of entropy.
    """
    return secrets.token_urlsafe(nbytes)


def hash_session_token(raw_token: str) -> str:
    """
    Compute SHA-256 hash of a session token for secure database storage.
    Raw tokens are NEVER stored in the database.
    """
    if not raw_token or not isinstance(raw_token, str):
        raise ValueError("Session token must be a non-empty string.")
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


# =====================================================================
# 3. String Normalization & Input Validation
# =====================================================================

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    """Normalize and validate email address (trimmed, lowercase)."""
    if not email or not isinstance(email, str):
        raise ValueError("Email must be a non-empty string.")
    cleaned = email.strip().lower()
    if not _EMAIL_REGEX.match(cleaned):
        raise ValueError(f"Invalid email address format: '{email}'")
    return cleaned


def normalize_username(username: str) -> str:
    """
    Normalize and validate username (alphanumeric + underscores/hyphens, lowercase).
    """
    if not username or not isinstance(username, str):
        raise ValueError("Username must be a non-empty string.")
    cleaned = username.strip().lower()
    if len(cleaned) < 3 or len(cleaned) > 32:
        raise ValueError("Username must be between 3 and 32 characters long.")
    if not re.match(r"^[a-z0-9_-]+$", cleaned):
        raise ValueError("Username can only contain alphanumeric characters, underscores, and hyphens.")
    return cleaned

