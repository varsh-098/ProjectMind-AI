"""
backend/routers/auth.py
========================
Stage 2: FastAPI Authentication Router.

ENDPOINTS:
    POST /auth/register   → Register new user with Argon2id password hashing
    POST /auth/login      → Authenticate, issue HttpOnly session cookie & token_hash
    GET  /auth/me         → Protected endpoint returning current authenticated user
    POST /auth/logout     → Revoke session in MongoDB and clear session cookie
"""

from typing import Dict, Any, Optional
import logging

try:
    from fastapi import APIRouter, HTTPException, Depends, Response, Request, status
    from pydantic import BaseModel, EmailStr, Field
except ImportError:
    from backend.auth.dependencies import HTTPException, status, Request, Depends

    class APIRouter:
        def __init__(self, *args, **kwargs): pass
        def get(self, *args, **kwargs): return lambda f: f
        def post(self, *args, **kwargs): return lambda f: f

    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self):
            return dict(self.__dict__)

    def Field(default=None, **kwargs):
        return default

    class Response:
        def __init__(self):
            self.cookies = {}
        def set_cookie(self, *args, **kwargs): pass
        def delete_cookie(self, *args, **kwargs): pass

    class Request:
        pass

from backend.config import settings
from backend.auth.security import (
    hash_password,
    verify_password,
    generate_session_token,
    hash_session_token,
    normalize_email,
    normalize_username,
)
from backend.auth import repository
from backend.auth.dependencies import (
    get_current_user,
    COOKIE_NAME,
    get_allowed_origins_set,
    extract_origin_from_url,
)

logger = logging.getLogger("projectmind.auth")

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def validate_public_auth_origin(request: Optional[Request]) -> None:
    """
    Validates Origin / Referer for public authentication endpoints (register, login)
    to defend against Login CSRF and unauthorized cross-origin credential submissions.

    SECURITY POLICY:
      1. Origin Header Present:
         - 'null', empty, or malformed -> HTTP 403 Forbidden.
         - Valid scheme://netloc: must exact-match settings.cors_allowed_origins.
           If untrusted -> HTTP 403 Forbidden.
      2. Origin Header Absent, Referer Header Present:
         - Malformed -> HTTP 403 Forbidden.
         - Extracted scheme://netloc: must exact-match settings.cors_allowed_origins.
           If untrusted -> HTTP 403 Forbidden.
      3. Neither Origin Nor Referer Present:
         - Browser detection: If browser request metadata is present
           (e.g., 'sec-fetch-mode', 'sec-fetch-site', or 'user-agent' containing browser tokens
           like 'Mozilla/', 'Chrome/', 'Safari/', 'Edge/', 'Firefox/'), the request is identified
           as browser-originated and REJECTED with HTTP 403 Forbidden.
         - Non-Browser API Client Exception: Programmatic API clients (curl, Postman, automated
           backend test runners / SDK scripts) without browser ambient context or browser headers
           are permitted access to public register and login endpoints.
    """
    if request is None:
        return

    origin_header = request.headers.get("origin") if hasattr(request, "headers") else None
    referer_header = request.headers.get("referer") if hasattr(request, "headers") else None

    # 1. Origin header check
    if origin_header is not None:
        trimmed = origin_header.strip()
        if trimmed.lower() == "null" or not trimmed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-origin request forbidden: 'null' or empty Origin header.",
            )
        candidate = extract_origin_from_url(trimmed)
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-origin request forbidden: Malformed Origin header '{trimmed}'.",
            )
        allowed = get_allowed_origins_set()
        if candidate not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-origin request forbidden: Origin '{candidate}' is not authorized.",
            )
        return

    # 2. Referer fallback check
    if referer_header is not None:
        trimmed = referer_header.strip()
        candidate = extract_origin_from_url(trimmed)
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-origin request forbidden: Malformed Referer header.",
            )
        allowed = get_allowed_origins_set()
        if candidate not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-origin request forbidden: Referer origin '{candidate}' is not authorized.",
            )
        return

    # 3. Neither Origin nor Referer provided
    headers = request.headers if hasattr(request, "headers") else {}
    has_sec_fetch = any(k.lower().startswith("sec-fetch-") for k in headers.keys())
    user_agent = headers.get("user-agent", "")
    is_browser_ua = any(token in user_agent for token in ("Mozilla/", "Chrome/", "Safari/", "Edge/", "Firefox/"))

    if has_sec_fetch or is_browser_ua:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-origin security policy: Browser authentication requests must provide an authorized Origin or Referer header.",
        )

    # Documented Non-Browser API Client Exception:
    # Direct programmatic HTTP requests (curl, Postman, test harnesses) with no browser headers
    # are permitted.


# -------------------------------------------------------
# Request & Response Schemas
# -------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, description="Unique username.")
    email: str = Field(..., min_length=5, max_length=120, description="User email address.")
    password: str = Field(..., min_length=8, max_length=128, description="Plaintext password.")


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, description="Email address or username.")
    password: str = Field(..., min_length=8, description="User password.")


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    role: str
    created_at: str
    is_active: bool


class AuthResponse(BaseModel):
    status: str
    user: Dict[str, Any]
    session_id: Optional[str] = None


# -------------------------------------------------------
# Endpoints
# -------------------------------------------------------

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(req: RegisterRequest, request: Optional[Request] = None) -> Dict[str, Any]:
    """
    Register a new user account.
    Validates origin, credentials, normalizes identifiers, hashes password with Argon2id,
    and inserts user into MongoDB.
    """
    validate_public_auth_origin(request)

    try:
        clean_email = normalize_email(req.email)
        clean_username = normalize_username(req.username)
        hashed_password = hash_password(req.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        user = repository.create_user(
            username=clean_username,
            email=clean_email,
            password_hash=hashed_password,
            role="developer",
        )
        return {
            "status": "registered",
            "message": "User registered successfully.",
            "user": user,
        }
    except repository.UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except repository.AuthDatabaseUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication database is temporarily unavailable.",
        )


@router.post(
    "/login",
    summary="Authenticate user and issue HttpOnly session cookie",
)
async def login(req: LoginRequest, response: Response, request: Optional[Request] = None) -> Dict[str, Any]:
    """
    Authenticate user using Argon2id.
    Validates origin, issues a cryptographically secure random session token,
    stores only its SHA-256 hash in MongoDB, and sets the raw token in a hardened HttpOnly cookie.
    """
    validate_public_auth_origin(request)

    # 1. Lookup user by email or username
    try:
        user = repository.get_user_by_email(req.email, include_password_hash=True)
        if not user:
            user = repository.get_user_by_username(req.email, include_password_hash=True)
    except repository.AuthDatabaseUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication database is temporarily unavailable.",
        )

    # 2. Generic authentication failure (prevent user enumeration)
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )

    if not user or not user.get("password_hash"):
        raise generic_error

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has been deactivated. Please contact administrator.",
        )

    # 3. Verify password hash using Argon2id
    is_valid = verify_password(req.password, user["password_hash"])
    if not is_valid:
        raise generic_error

    # 4. Generate random session token & persist hash
    raw_token = generate_session_token()
    expiry_days = getattr(settings, "session_expiry_days", 7)
    client_ip = getattr(getattr(request, "client", None), "host", None)
    user_agent = request.headers.get("user-agent") if (request and hasattr(request, "headers")) else None

    try:
        session_info = repository.create_auth_session(
            user_id=user["user_id"],
            raw_token=raw_token,
            expires_in_days=expiry_days,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except repository.AuthDatabaseUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication database is temporarily unavailable.",
        )

    # 5. Set hardened HttpOnly cookie
    cookie_secure = getattr(settings, "cookie_secure", False)
    cookie_samesite = getattr(settings, "cookie_samesite", "lax")
    max_age_seconds = expiry_days * 86400

    response.set_cookie(
        key=COOKIE_NAME,
        value=raw_token,
        httponly=True,
        max_age=max_age_seconds,
        expires=max_age_seconds,
        samesite=cookie_samesite,
        secure=cookie_secure,
        path="/",
    )

    safe_user = dict(user)
    safe_user.pop("password_hash", None)

    return {
        "status": "authenticated",
        "message": "Login successful.",
        "user": safe_user,
        "session_id": session_info["session_id"],
        "expires_at": session_info["expires_at"],
    }


@router.get(
    "/me",
    summary="Get current authenticated user profile",
)
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Protected route: Returns the safe profile of the currently authenticated user.
    """
    return {
        "authenticated": True,
        "user": current_user,
    }


@router.post(
    "/logout",
    summary="Log out and invalidate session",
)
async def logout(
    request: Request,
    response: Response,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Log out: Revokes session in MongoDB.
    Clears the HttpOnly cookie with matching attributes only if authenticated via cookie.
    """
    token_hash = getattr(getattr(request, "state", None), "session_token_hash", None)
    if not token_hash and hasattr(request, "cookies"):
        raw_cookie = request.cookies.get(COOKIE_NAME)
        if raw_cookie:
            token_hash = hash_session_token(raw_cookie)

    if token_hash:
        try:
            repository.revoke_session(token_hash)
        except Exception as e:
            logger.warning(f"Error revoking session during logout: {e}")

    # Clear HttpOnly cookie ONLY when authentication used the cookie
    auth_type = getattr(getattr(request, "state", None), "auth_type", None)
    if auth_type is None and hasattr(request, "cookies") and request.cookies.get(COOKIE_NAME):
        auth_type = "cookie"

    if auth_type == "cookie":
        cookie_secure = getattr(settings, "cookie_secure", False)
        cookie_samesite = getattr(settings, "cookie_samesite", "lax")
        response.delete_cookie(
            key=COOKIE_NAME,
            path="/",
            secure=cookie_secure,
            httponly=True,
            samesite=cookie_samesite,
        )

    return {
        "status": "logged_out",
        "message": "Successfully logged out.",
    }
