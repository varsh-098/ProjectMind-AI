"""
backend/auth/dependencies.py
=============================
Stage 2: FastAPI Authentication & CSRF Dependencies.

PURPOSE:
    Provides dependency injection for protected routes:
      1. get_current_user: Validates session cookie or Bearer token, enforces expiration,
         and returns the authenticated safe user profile.
      2. get_optional_user: Like get_current_user but returns None if unauthenticated.
      3. validate_csrf_origin: Verifies Origin / Referer for state-changing cookie requests.
"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse

try:
    from fastapi import Request, HTTPException, status, Depends
except ImportError:
    class Request:
        pass

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str = "", headers: dict = None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail
            self.headers = headers

    class status:
        HTTP_201_CREATED = 201
        HTTP_400_BAD_REQUEST = 400
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403
        HTTP_409_CONFLICT = 409
        HTTP_503_SERVICE_UNAVAILABLE = 503

    def Depends(f):
        return f

from backend.config import settings
from backend.auth.security import hash_session_token
from backend.auth import repository

COOKIE_NAME = "pm_session"


def get_allowed_origins_set() -> set[str]:
    """
    Parse configured allowed CORS origins into a normalized set.
    Each origin is stored as exact scheme://netloc (including explicit port if present).
    Wildcard '*' is discarded.
    """
    raw = getattr(settings, "cors_allowed_origins", "")
    origins = set()
    for o in raw.split(","):
        cleaned = o.strip().rstrip("/")
        if cleaned and cleaned != "*":
            origins.add(cleaned)
    return origins


def extract_origin_from_url(url: str) -> Optional[str]:
    """
    Extract exact scheme://netloc origin from a URL, or return None if malformed.
    Requires http or https scheme and a valid network location (host[:port]).
    """
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url.strip())
        if not parsed.scheme or not parsed.netloc:
            return None
        if parsed.scheme not in ("http", "https"):
            return None
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    except Exception:
        return None


def validate_csrf(request: Request) -> None:
    """
    CSRF Defense: Validates Origin / Referer against configured allowed origins
    on state-changing requests (POST, PUT, DELETE, PATCH) when authenticated via browser cookies.

    RULES:
      1. Safe methods (GET, HEAD, OPTIONS) bypass CSRF checking.
      2. If Origin header is present:
         - 'null', empty, or malformed origin -> 403 Forbidden.
         - Untrusted origin not in settings.cors_allowed_origins -> 403 Forbidden.
      3. If Origin is missing:
         - Inspect Referer header: extracted scheme://netloc must exact-match allowed origins.
      4. If BOTH Origin and Referer are missing on an unsafe cookie-authenticated request:
         - Fails closed: reject with 403 Forbidden.
      5. Untrusted client Host headers are NEVER dynamically added to allowed origins.
      6. Comparison is exact (scheme + domain + port), never substring.
    """
    if getattr(request, "method", "POST") in ("GET", "HEAD", "OPTIONS"):
        return

    origin_header = request.headers.get("origin") if hasattr(request, "headers") else None
    referer_header = request.headers.get("referer") if hasattr(request, "headers") else None

    target_origin = None

    if origin_header is not None:
        trimmed = origin_header.strip()
        if trimmed.lower() == "null" or not trimmed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed: 'null' or empty Origin header is forbidden.",
            )
        candidate = extract_origin_from_url(trimmed)
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"CSRF validation failed: Malformed Origin header '{trimmed}'.",
            )
        target_origin = candidate
    elif referer_header is not None:
        trimmed = referer_header.strip()
        candidate = extract_origin_from_url(trimmed)
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed: Malformed Referer header.",
            )
        target_origin = candidate
    else:
        # Fails closed when both Origin and Referer are missing on cookie-authenticated mutations
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed: Missing Origin and Referer headers on cookie-authenticated request.",
        )

    allowed = get_allowed_origins_set()
    # Note: Request 'Host' header is NEVER dynamically added to allowed origins!
    if target_origin not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"CSRF validation failed: Origin '{target_origin}' is not authorized.",
        )


async def get_current_user(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency: Authenticates user from HttpOnly cookie or Bearer token.

    PRIORITY & BEHAVIOR:
      1. Cookie authentication takes precedence if both cookie and Bearer header are provided.
         Sets request.state.auth_type = "cookie".
         Enforces CSRF origin validation on unsafe requests.
      2. If no cookie is present, falls back to Authorization: Bearer <token>.
         Sets request.state.auth_type = "bearer".
         Bypasses cookie CSRF origin validation.

    Returns:
        Safe user profile dictionary (user_id, username, email, role, etc.).

    Raises:
        HTTPException(401): If token is missing, invalid, revoked, or expired.
        HTTPException(403): If CSRF validation fails on cookie requests.
        HTTPException(503): If database is unavailable (fail-closed).
    """
    raw_token = None
    auth_type = None

    # Check for session cookie first (takes precedence)
    cookie_token = request.cookies.get(COOKIE_NAME) if hasattr(request, "cookies") else None
    if cookie_token:
        auth_type = "cookie"
        raw_token = cookie_token
        # Enforce CSRF defense on cookie-authenticated requests
        validate_csrf(request)
    else:
        # Check Bearer authorization header
        auth_header = request.headers.get("authorization") if hasattr(request, "headers") else None
        if auth_header and auth_header.strip().lower().startswith("bearer "):
            auth_type = "bearer"
            raw_token = auth_header.strip()[7:].strip()

    if not raw_token or not auth_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing session cookie or Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Hash token before database lookup
    token_hash = hash_session_token(raw_token)

    # Retrieve session from repository
    try:
        session = repository.get_session_by_token_hash(token_hash)
    except repository.AuthDatabaseUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        ) from e

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Retrieve associated user
    user_id = session.get("user_id")
    try:
        user = repository.get_user_by_id(user_id, include_password_hash=False)
    except repository.AuthDatabaseUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        ) from e

    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Attach session metadata and auth transport discriminator
    if hasattr(request, "state"):
        request.state.auth_type = auth_type
        request.state.session_token_hash = token_hash
        request.state.session_id = session.get("session_id")

    return user


async def get_optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """Optional authentication dependency: returns user if valid, None if not."""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None
