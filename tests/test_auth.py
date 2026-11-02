"""
tests/test_auth.py
===================
Automated unit tests for Stage 2: Authentication Repository and FastAPI Endpoints.

Tests:
  1. Successful registration.
  2. Duplicate email rejection (409 Conflict).
  3. Duplicate username rejection (409 Conflict).
  4. Invalid email format rejection (400 Bad Request).
  5. Successful login & HttpOnly cookie issuance.
  6. Incorrect password rejection (401 Unauthorized).
  7. Nonexistent user login rejection (401 Unauthorized).
  8. Protected route retrieval of authenticated user (get_current_user).
  9. Access without cookie rejection (401 Unauthorized).
  10. Invalid session token rejection (401 Unauthorized).
  11. Expired session rejection (401 Unauthorized).
  12. Revoked session rejection (401 Unauthorized).
  13. Successful logout & session invalidation.
  14. MongoDB unavailable fail-closed behavior (503 Service Unavailable).
  15. Verification that plaintext passwords and raw tokens are never stored in DB.
  16. Verification that password hashes are never returned by API responses.
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

from backend.auth.security import hash_password, generate_session_token, hash_session_token
from backend.auth import repository
from backend.auth.dependencies import get_current_user, COOKIE_NAME, validate_csrf
from backend.config import settings, validate_security_config
from backend.routers.auth import (
    register,
    login,
    get_me,
    logout,
    RegisterRequest,
    LoginRequest,
    HTTPException,
)


def run_coro(coro):
    """Safely advance coroutines in synchronous test runners."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


class FakeCollection:
    """In-memory collection mock with unique constraint enforcement."""

    def __init__(self, name: str):
        self.name = name
        self.docs = []

    def insert_one(self, doc):
        d = dict(doc)
        if "_id" not in d:
            d["_id"] = len(self.docs) + 1

        # Enforce unique indexes
        if "email" in d and any(x.get("email") == d["email"] for x in self.docs):
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError(f"Duplicate email: {d['email']}")

        if "username" in d and any(x.get("username") == d["username"] for x in self.docs):
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError(f"Duplicate username: {d['username']}")

        if "token_hash" in d and any(x.get("token_hash") == d["token_hash"] for x in self.docs):
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError(f"Duplicate token_hash: {d['token_hash']}")

        self.docs.append(d)
        return MagicMock(inserted_id=d["_id"])

    def find_one(self, query, projection=None):
        for d in self.docs:
            if self._matches(d, query):
                res = dict(d)
                if projection and projection.get("_id") == 0:
                    res.pop("_id", None)
                return res
        return None

    def update_one(self, filter_query, update_doc, upsert=False):
        matched = 0
        modified = 0
        for d in self.docs:
            if self._matches(d, filter_query):
                matched += 1
                if "$set" in update_doc:
                    for k, v in update_doc["$set"].items():
                        if d.get(k) != v:
                            d[k] = v
                            modified += 1
                return MagicMock(matched_count=matched, modified_count=modified)
        return MagicMock(matched_count=0, modified_count=0)

    def update_many(self, filter_query, update_doc):
        modified = 0
        for d in self.docs:
            if self._matches(d, filter_query):
                if "$set" in update_doc:
                    for k, v in update_doc["$set"].items():
                        d[k] = v
                    modified += 1
        return MagicMock(modified_count=modified)

    def delete_one(self, filter_query):
        for i, d in enumerate(self.docs):
            if self._matches(d, filter_query):
                del self.docs[i]
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)

    def _matches(self, doc, query):
        if "$or" in query:
            return any(self._matches(doc, q) for q in query["$or"])
        for k, v in query.items():
            if k == "$or":
                continue
            if doc.get(k) != v:
                return False
        return True


class FakeDatabase:
    """Isolated database holding mock collections for unit tests."""

    def __init__(self):
        self.collections = {
            "users": FakeCollection("users"),
            "auth_sessions": FakeCollection("auth_sessions"),
        }

    def __getitem__(self, name: str):
        if name not in self.collections:
            self.collections[name] = FakeCollection(name)
        return self.collections[name]


class MockResponse:
    """Mock for FastAPI Response object capturing cookies."""

    def __init__(self):
        self.cookies = {}
        self.deleted_cookies = []
        self.deleted_cookie_details = {}

    def set_cookie(self, key, value, httponly=True, max_age=None, samesite=None, secure=False, path="/", **kwargs):
        self.cookies[key] = {
            "value": value,
            "httponly": httponly,
            "max_age": max_age,
            "samesite": samesite,
            "secure": secure,
            "path": path,
        }

    def delete_cookie(self, key, path="/", secure=False, httponly=False, samesite=None, **kwargs):
        self.deleted_cookies.append(key)
        self.deleted_cookie_details[key] = {
            "path": path,
            "secure": secure,
            "httponly": httponly,
            "samesite": samesite,
        }
        self.cookies.pop(key, None)


class MockRequestState:
    def __init__(self):
        self.auth_type = None
        self.session_token_hash = None
        self.session_id = None


class MockRequest:
    """Mock for FastAPI Request object."""

    def __init__(self, cookies=None, headers=None, method="POST"):
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.method = method
        self.state = MockRequestState()
        self.client = MagicMock(host="127.0.0.1")


class TestAuthentication(unittest.TestCase):
    """Complete test suite for Stage 2 Authentication system."""

    def setUp(self):
        self.fake_db = FakeDatabase()
        # Patch _get_db in repository to isolate tests from network/Atlas
        self.db_patcher = patch("backend.auth.repository._get_db", return_value=self.fake_db)
        self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()

    # ------------------------------------------------------------------
    # 1. Registration Tests
    # ------------------------------------------------------------------

    def test_successful_registration(self):
        """Verify successful user registration and safe response fields."""
        req = RegisterRequest(
            username="alice_dev",
            email="Alice@Example.com",
            password="StrongPassword123!",
        )
        res = run_coro(register(req))
        self.assertEqual(res["status"], "registered")
        user = res["user"]
        self.assertEqual(user["username"], "alice_dev")
        self.assertEqual(user["email"], "alice@example.com")
        self.assertIn("user_id", user)
        self.assertNotIn("password_hash", user)

    def test_duplicate_email_rejection(self):
        """Verify duplicate email registration raises 409 Conflict."""
        req1 = RegisterRequest(
            username="user_one",
            email="shared@example.com",
            password="Password123!",
        )
        run_coro(register(req1))

        req2 = RegisterRequest(
            username="user_two",
            email="SHARED@example.com",  # Normalized match
            password="Password123!",
        )
        with self.assertRaises(HTTPException) as ctx:
            run_coro(register(req2))
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("email address already exists", ctx.exception.detail)

    def test_duplicate_username_rejection(self):
        """Verify duplicate username registration raises 409 Conflict."""
        req1 = RegisterRequest(
            username="charlie_dev",
            email="charlie1@example.com",
            password="Password123!",
        )
        run_coro(register(req1))

        req2 = RegisterRequest(
            username="CHARLIE_DEV",  # Normalized match
            email="charlie2@example.com",
            password="Password123!",
        )
        with self.assertRaises(HTTPException) as ctx:
            run_coro(register(req2))
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("username already exists", ctx.exception.detail)

    def test_invalid_email_rejection(self):
        """Verify invalid email format raises 400 Bad Request."""
        req = RegisterRequest(
            username="valid_user",
            email="not-an-email",
            password="Password123!",
        )
        with self.assertRaises(HTTPException) as ctx:
            run_coro(register(req))
        self.assertEqual(ctx.exception.status_code, 400)

    # ------------------------------------------------------------------
    # 2. Login Tests
    # ------------------------------------------------------------------

    def test_successful_login(self):
        """Verify login issues HttpOnly session cookie and safe user profile."""
        # 1. Register user
        reg_req = RegisterRequest(
            username="bob_builder",
            email="bob@example.com",
            password="SecretPassword123!",
        )
        run_coro(register(reg_req))

        # 2. Login
        login_req = LoginRequest(email="bob@example.com", password="SecretPassword123!")
        mock_response = MockResponse()
        mock_request = MockRequest()

        res = run_coro(login(login_req, mock_response, mock_request))
        self.assertEqual(res["status"], "authenticated")
        self.assertEqual(res["user"]["username"], "bob_builder")
        self.assertNotIn("password_hash", res["user"])

        # Check HttpOnly cookie
        self.assertIn(COOKIE_NAME, mock_response.cookies)
        cookie = mock_response.cookies[COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "lax")
        self.assertTrue(len(cookie["value"]) >= 40)

    def test_login_with_username(self):
        """Verify users can log in using their username instead of email."""
        reg_req = RegisterRequest(
            username="carol_dev",
            email="carol@example.com",
            password="SecretPassword123!",
        )
        run_coro(register(reg_req))

        login_req = LoginRequest(email="carol_dev", password="SecretPassword123!")
        mock_response = MockResponse()
        mock_request = MockRequest()

        res = run_coro(login(login_req, mock_response, mock_request))
        self.assertEqual(res["status"], "authenticated")
        self.assertEqual(res["user"]["email"], "carol@example.com")

    def test_incorrect_password_rejection(self):
        """Verify incorrect password returns generic 401 Unauthorized."""
        reg_req = RegisterRequest(
            username="dave_dev",
            email="dave@example.com",
            password="CorrectPassword123!",
        )
        run_coro(register(reg_req))

        login_req = LoginRequest(email="dave@example.com", password="WrongPassword999!")
        with self.assertRaises(HTTPException) as ctx:
            run_coro(login(login_req, MockResponse(), MockRequest()))
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Invalid email or password.")

    def test_nonexistent_user_login_rejection(self):
        """Verify non-registered email returns generic 401 Unauthorized."""
        login_req = LoginRequest(email="ghost@example.com", password="Password123!")
        with self.assertRaises(HTTPException) as ctx:
            run_coro(login(login_req, MockResponse(), MockRequest()))
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Invalid email or password.")

    # ------------------------------------------------------------------
    # 3. Protected Route & Session Dependency Tests
    # ------------------------------------------------------------------

    def test_get_current_user_success(self):
        """Verify get_current_user extracts cookie and returns authenticated user."""
        # 1. Register & login
        reg_req = RegisterRequest(
            username="eve_security",
            email="eve@example.com",
            password="Password123!",
        )
        run_coro(register(reg_req))

        login_req = LoginRequest(email="eve@example.com", password="Password123!")
        mock_response = MockResponse()
        run_coro(login(login_req, mock_response, MockRequest()))

        raw_token = mock_response.cookies[COOKIE_NAME]["value"]

        # 2. Authenticated request with cookie
        req = MockRequest(cookies={COOKIE_NAME: raw_token}, method="GET")
        user = run_coro(get_current_user(req))
        self.assertEqual(user["username"], "eve_security")
        self.assertEqual(user["email"], "eve@example.com")
        self.assertNotIn("password_hash", user)

    def test_access_without_cookie_rejected(self):
        """Verify missing authentication token raises 401."""
        req = MockRequest(cookies={}, method="GET")
        with self.assertRaises(HTTPException) as ctx:
            run_coro(get_current_user(req))
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Authentication required", ctx.exception.detail)

    def test_invalid_session_token_rejected(self):
        """Verify fabricated session token raises 401."""
        req = MockRequest(cookies={COOKIE_NAME: "fabricated_fake_token_123"}, method="GET")
        with self.assertRaises(HTTPException) as ctx:
            run_coro(get_current_user(req))
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid or expired session", ctx.exception.detail)

    def test_expired_session_rejection(self):
        """Verify session past expires_at is explicitly rejected in application code."""
        # Insert a pre-expired session into the mock DB
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        expired_time = datetime.now(timezone.utc) - timedelta(hours=2)

        self.fake_db["auth_sessions"].insert_one({
            "session_id": "expired_session_id",
            "user_id": "test_user_id",
            "token_hash": token_hash,
            "created_at": expired_time - timedelta(days=7),
            "expires_at": expired_time,
            "is_revoked": False,
        })

        req = MockRequest(cookies={COOKIE_NAME: raw_token}, method="GET")
        with self.assertRaises(HTTPException) as ctx:
            run_coro(get_current_user(req))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_revoked_session_rejection(self):
        """Verify revoked session is rejected."""
        # 1. Register & login
        reg_req = RegisterRequest(
            username="frank_dev",
            email="frank@example.com",
            password="Password123!",
        )
        run_coro(register(reg_req))

        mock_resp = MockResponse()
        run_coro(login(LoginRequest(email="frank@example.com", password="Password123!"), mock_resp, MockRequest()))
        raw_token = mock_resp.cookies[COOKIE_NAME]["value"]

        # 2. Revoke session manually
        token_hash = hash_session_token(raw_token)
        repository.revoke_session(token_hash)

        # 3. Access endpoint
        req = MockRequest(cookies={COOKIE_NAME: raw_token}, method="GET")
        with self.assertRaises(HTTPException) as ctx:
            run_coro(get_current_user(req))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_successful_logout(self):
        """Verify logout endpoint revokes session and clears cookie."""
        # 1. Register & login
        reg_req = RegisterRequest(
            username="grace_hopper",
            email="grace@example.com",
            password="CompilerPassword123!",
        )
        run_coro(register(reg_req))

        login_resp = MockResponse()
        run_coro(login(LoginRequest(email="grace@example.com", password="CompilerPassword123!"), login_resp, MockRequest()))
        raw_token = login_resp.cookies[COOKIE_NAME]["value"]

        # 2. Call logout with valid Origin for CSRF protection
        req = MockRequest(cookies={COOKIE_NAME: raw_token}, headers={"origin": "http://localhost:3000"}, method="POST")
        current_user = run_coro(get_current_user(req))

        logout_resp = MockResponse()
        res = run_coro(logout(req, logout_resp, current_user=current_user))
        self.assertEqual(res["status"], "logged_out")
        self.assertIn(COOKIE_NAME, logout_resp.deleted_cookies)

        # 3. Confirm session is now revoked in database
        token_hash = hash_session_token(raw_token)
        session_in_db = self.fake_db["auth_sessions"].find_one({"token_hash": token_hash})
        self.assertTrue(session_in_db["is_revoked"])

    # ------------------------------------------------------------------
    # 4. Fail-Closed & Database Security Verification
    # ------------------------------------------------------------------

    def test_mongodb_unavailable_behavior(self):
        """Verify registration and login fail-closed with 503 if MongoDB is down."""
        # Stop fake DB patch and simulate database failure
        with patch("backend.auth.repository._get_db", side_effect=repository.AuthDatabaseUnavailableError("Atlas down")):
            reg_req = RegisterRequest(
                username="offline_user",
                email="offline@example.com",
                password="Password123!",
            )
            with self.assertRaises(HTTPException) as ctx:
                run_coro(register(reg_req))
            self.assertEqual(ctx.exception.status_code, 503)

            login_req = LoginRequest(email="offline@example.com", password="Password123!")
            with self.assertRaises(HTTPException) as ctx:
                run_coro(login(login_req, MockResponse(), MockRequest()))
            self.assertEqual(ctx.exception.status_code, 503)

    def test_no_plaintext_password_or_raw_token_in_db(self):
        """Verify DB documents never store plaintext passwords or raw session tokens."""
        raw_pw = "SuperSecretUnstoredPassword123!"
        reg_req = RegisterRequest(
            username="heidi_audit",
            email="heidi@example.com",
            password=raw_pw,
        )
        run_coro(register(reg_req))

        # Inspect database document
        user_doc = self.fake_db["users"].find_one({"email": "heidi@example.com"})
        self.assertIsNotNone(user_doc)
        # Plaintext password must NOT exist in the document
        self.assertNotIn(raw_pw, str(user_doc))
        self.assertTrue(user_doc["password_hash"].startswith("$argon2id$"))

        # Inspect session document
        mock_resp = MockResponse()
        run_coro(login(LoginRequest(email="heidi@example.com", password=raw_pw), mock_resp, MockRequest()))
        raw_token = mock_resp.cookies[COOKIE_NAME]["value"]

        session_doc = self.fake_db["auth_sessions"].find_one({"user_id": user_doc["user_id"]})
        self.assertIsNotNone(session_doc)
        # Raw token must NOT exist in the database document
        self.assertNotIn(raw_token, str(session_doc))
        self.assertEqual(session_doc["token_hash"], hash_session_token(raw_token))

    def test_password_hash_never_returned_by_api(self):
        """Verify neither register, login, nor me endpoints expose password hashes."""
        reg_res = run_coro(register(RegisterRequest(
            username="ivan_safe",
            email="ivan@example.com",
            password="SafePassword123!",
        )))
        self.assertNotIn("password_hash", reg_res["user"])

        mock_resp = MockResponse()
        login_res = run_coro(login(LoginRequest(email="ivan@example.com", password="SafePassword123!"), mock_resp, MockRequest()))
        self.assertNotIn("password_hash", login_res["user"])

        raw_token = mock_resp.cookies[COOKIE_NAME]["value"]
        req = MockRequest(cookies={COOKIE_NAME: raw_token}, method="GET")
        user = run_coro(get_current_user(req))
        me_res = run_coro(get_me(current_user=user))
        self.assertNotIn("password_hash", me_res["user"])

    # ------------------------------------------------------------------
    # 5. CSRF Defense Tests
    # ------------------------------------------------------------------

    def test_csrf_trusted_origin_accepted(self):
        """Verify state-changing cookie requests with trusted Origin header pass CSRF check."""
        req = MockRequest(
            cookies={COOKIE_NAME: "dummy_session_token_123"},
            headers={"origin": "http://localhost:3000"},
            method="POST",
        )
        # Should not raise HTTPException
        validate_csrf(req)

    def test_csrf_untrusted_origin_rejected(self):
        """Verify state-changing cookie requests with untrusted Origin are rejected with 403."""
        req = MockRequest(
            cookies={COOKIE_NAME: "dummy_session_token_123"},
            headers={"origin": "https://evil-attacker.com"},
            method="POST",
        )
        with self.assertRaises(HTTPException) as ctx:
            validate_csrf(req)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("not authorized", ctx.exception.detail)

    def test_csrf_missing_origin_trusted_referer_accepted(self):
        """Verify trusted Referer header is accepted when Origin is missing."""
        req = MockRequest(
            cookies={COOKIE_NAME: "dummy_session_token_123"},
            headers={"referer": "http://localhost:3000/dashboard/settings"},
            method="POST",
        )
        validate_csrf(req)

    def test_csrf_missing_both_origin_and_referer_rejected(self):
        """Verify cookie-authenticated mutations without Origin or Referer fail closed (403)."""
        req = MockRequest(
            cookies={COOKIE_NAME: "dummy_session_token_123"},
            headers={},
            method="POST",
        )
        with self.assertRaises(HTTPException) as ctx:
            validate_csrf(req)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Missing Origin and Referer", ctx.exception.detail)

    def test_csrf_spoofed_host_cannot_bypass_validation(self):
        """Verify client cannot spoof Host header to bypass CSRF origin verification."""
        req = MockRequest(
            cookies={COOKIE_NAME: "dummy_session_token_123"},
            headers={"origin": "https://attacker.com", "host": "attacker.com"},
            method="POST",
        )
        with self.assertRaises(HTTPException) as ctx:
            validate_csrf(req)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("not authorized", ctx.exception.detail)

    def test_csrf_origin_null_rejected(self):
        """Verify Origin: null (from sandboxed iframes or data URIs) is rejected with 403."""
        req = MockRequest(
            cookies={COOKIE_NAME: "dummy_session_token_123"},
            headers={"origin": "null"},
            method="POST",
        )
        with self.assertRaises(HTTPException) as ctx:
            validate_csrf(req)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("null", ctx.exception.detail.lower())

    def test_csrf_logout_rejects_invalid_csrf(self):
        """Verify logout endpoint rejects state-changing requests with invalid Origin."""
        req = MockRequest(
            cookies={COOKIE_NAME: "dummy_session_token_123"},
            headers={"origin": "https://malicious-site.org"},
            method="POST",
        )
        with self.assertRaises(HTTPException) as ctx:
            run_coro(get_current_user(req))
        self.assertEqual(ctx.exception.status_code, 403)

    # ------------------------------------------------------------------
    # 6. Login and Registration Cross-Origin Protection Tests
    # ------------------------------------------------------------------

    def test_register_untrusted_origin_rejected(self):
        """Verify registration rejects untrusted cross-origin requests with 403."""
        req = RegisterRequest(
            username="untrusted_user",
            email="untrusted@example.com",
            password="Password123!",
        )
        http_req = MockRequest(headers={"origin": "https://attacker-domain.com"})
        with self.assertRaises(HTTPException) as ctx:
            run_coro(register(req, request=http_req))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("not authorized", ctx.exception.detail)

    def test_register_trusted_origin_accepted(self):
        """Verify registration accepts trusted origin requests."""
        req = RegisterRequest(
            username="trusted_reg_user",
            email="trusted_reg@example.com",
            password="Password123!",
        )
        http_req = MockRequest(headers={"origin": "http://localhost:3000"})
        res = run_coro(register(req, request=http_req))
        self.assertEqual(res["status"], "registered")

    def test_login_untrusted_origin_rejected(self):
        """Verify login rejects untrusted cross-origin requests with 403."""
        login_req = LoginRequest(email="some_user@example.com", password="Password123!")
        http_req = MockRequest(headers={"origin": "https://phishing-site.com"})
        with self.assertRaises(HTTPException) as ctx:
            run_coro(login(login_req, MockResponse(), request=http_req))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("not authorized", ctx.exception.detail)

    def test_login_trusted_origin_accepted(self):
        """Verify login accepts requests from trusted origins."""
        reg_req = RegisterRequest(
            username="login_test_user",
            email="logintest@example.com",
            password="Password123!",
        )
        run_coro(register(reg_req, request=MockRequest(headers={"origin": "http://localhost:3000"})))

        login_req = LoginRequest(email="logintest@example.com", password="Password123!")
        http_req = MockRequest(headers={"origin": "http://localhost:3000"})
        resp = MockResponse()
        res = run_coro(login(login_req, resp, request=http_req))
        self.assertEqual(res["status"], "authenticated")

    def test_public_endpoints_missing_headers_policy(self):
        """Verify browser requests without Origin/Referer are rejected; programmatic API clients permitted."""
        # Browser request: identified by browser user-agent
        browser_req = MockRequest(headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        with self.assertRaises(HTTPException) as ctx:
            run_coro(login(LoginRequest(email="a@b.com", password="Password123!"), MockResponse(), request=browser_req))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Browser authentication requests must provide", ctx.exception.detail)

        # Programmatic non-browser client (curl / CLI / script with no browser headers): permitted
        cli_req = MockRequest(headers={})
        res = run_coro(register(RegisterRequest(
            username="cli_automation",
            email="cli_automation@example.com",
            password="Password123!",
        ), request=cli_req))
        self.assertEqual(res["status"], "registered")

    # ------------------------------------------------------------------
    # 7. Authentication Transport Tests (Cookie vs Bearer)
    # ------------------------------------------------------------------

    def test_bearer_authentication_success(self):
        """Verify Bearer token authentication sets auth_type to bearer and authenticates user."""
        # 1. Register user
        reg_req = RegisterRequest(
            username="api_developer",
            email="api_dev@example.com",
            password="Password123!",
        )
        run_coro(register(reg_req, request=MockRequest(headers={"origin": "http://localhost:3000"})))

        # 2. Login to get token
        mock_resp = MockResponse()
        run_coro(login(LoginRequest(email="api_dev@example.com", password="Password123!"), mock_resp, MockRequest(headers={"origin": "http://localhost:3000"})))
        raw_token = mock_resp.cookies[COOKIE_NAME]["value"]

        # 3. Authenticate with Bearer header (no cookie)
        req = MockRequest(cookies={}, headers={"authorization": f"Bearer {raw_token}"}, method="GET")
        user = run_coro(get_current_user(req))
        self.assertEqual(user["username"], "api_developer")
        self.assertEqual(req.state.auth_type, "bearer")

    def test_invalid_bearer_token_rejected(self):
        """Verify invalid or malformed Bearer token raises 401."""
        req = MockRequest(cookies={}, headers={"authorization": "Bearer bogus_token_123"}, method="GET")
        with self.assertRaises(HTTPException) as ctx:
            run_coro(get_current_user(req))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_cookie_precedence_over_bearer(self):
        """Verify cookie authentication takes precedence over Bearer header when both exist."""
        # Create user A
        run_coro(register(RegisterRequest(username="user_cookie", email="cookie@example.com", password="Password123!"), request=MockRequest(headers={"origin": "http://localhost:3000"})))
        resp_a = MockResponse()
        run_coro(login(LoginRequest(email="cookie@example.com", password="Password123!"), resp_a, MockRequest(headers={"origin": "http://localhost:3000"})))
        cookie_token = resp_a.cookies[COOKIE_NAME]["value"]

        # Create user B
        run_coro(register(RegisterRequest(username="user_bearer", email="bearer@example.com", password="Password123!"), request=MockRequest(headers={"origin": "http://localhost:3000"})))
        resp_b = MockResponse()
        run_coro(login(LoginRequest(email="bearer@example.com", password="Password123!"), resp_b, MockRequest(headers={"origin": "http://localhost:3000"})))
        bearer_token = resp_b.cookies[COOKIE_NAME]["value"]

        # Send request with BOTH cookie (user A) and Bearer (user B)
        req = MockRequest(
            cookies={COOKIE_NAME: cookie_token},
            headers={"authorization": f"Bearer {bearer_token}", "origin": "http://localhost:3000"},
            method="POST",
        )
        user = run_coro(get_current_user(req))
        self.assertEqual(user["username"], "user_cookie")
        self.assertEqual(req.state.auth_type, "cookie")

    def test_bearer_only_logout_does_not_clear_cookie(self):
        """Verify logout for a Bearer-authenticated client revokes session without clearing cookies."""
        run_coro(register(RegisterRequest(username="bearer_logout_user", email="bearer_out@example.com", password="Password123!"), request=MockRequest(headers={"origin": "http://localhost:3000"})))
        login_resp = MockResponse()
        run_coro(login(LoginRequest(email="bearer_out@example.com", password="Password123!"), login_resp, MockRequest(headers={"origin": "http://localhost:3000"})))
        raw_token = login_resp.cookies[COOKIE_NAME]["value"]

        # Authenticate via Bearer
        req = MockRequest(cookies={}, headers={"authorization": f"Bearer {raw_token}"}, method="POST")
        current_user = run_coro(get_current_user(req))
        self.assertEqual(req.state.auth_type, "bearer")

        logout_resp = MockResponse()
        res = run_coro(logout(req, logout_resp, current_user=current_user))
        self.assertEqual(res["status"], "logged_out")
        # Cookie was NOT cleared
        self.assertEqual(len(logout_resp.deleted_cookies), 0)

        # Database session was revoked
        token_hash = hash_session_token(raw_token)
        session_doc = self.fake_db["auth_sessions"].find_one({"token_hash": token_hash})
        self.assertTrue(session_doc["is_revoked"])

    def test_cookie_logout_revokes_session_and_clears_cookie(self):
        """Verify cookie-authenticated logout revokes DB session and deletes cookie with matching attributes."""
        run_coro(register(RegisterRequest(username="cookie_logout_user", email="cookie_out@example.com", password="Password123!"), request=MockRequest(headers={"origin": "http://localhost:3000"})))
        login_resp = MockResponse()
        run_coro(login(LoginRequest(email="cookie_out@example.com", password="Password123!"), login_resp, MockRequest(headers={"origin": "http://localhost:3000"})))
        raw_token = login_resp.cookies[COOKIE_NAME]["value"]

        # Authenticate via Cookie
        req = MockRequest(cookies={COOKIE_NAME: raw_token}, headers={"origin": "http://localhost:3000"}, method="POST")
        current_user = run_coro(get_current_user(req))
        self.assertEqual(req.state.auth_type, "cookie")

        logout_resp = MockResponse()
        res = run_coro(logout(req, logout_resp, current_user=current_user))
        self.assertEqual(res["status"], "logged_out")
        self.assertIn(COOKIE_NAME, logout_resp.deleted_cookies)

        token_hash = hash_session_token(raw_token)
        session_doc = self.fake_db["auth_sessions"].find_one({"token_hash": token_hash})
        self.assertTrue(session_doc["is_revoked"])

    # ------------------------------------------------------------------
    # 8. Cookie and Configuration Validation Tests
    # ------------------------------------------------------------------

    def test_secure_cookie_configuration(self):
        """Verify cookie_secure=True and custom samesite settings apply to emitted cookie."""
        with patch.object(settings, "cookie_secure", True), patch.object(settings, "cookie_samesite", "strict"):
            run_coro(register(RegisterRequest(username="secure_cookie_user", email="secure@example.com", password="Password123!"), request=MockRequest(headers={"origin": "http://localhost:3000"})))
            mock_resp = MockResponse()
            run_coro(login(LoginRequest(email="secure@example.com", password="Password123!"), mock_resp, MockRequest(headers={"origin": "http://localhost:3000"})))
            cookie = mock_resp.cookies[COOKIE_NAME]
            self.assertTrue(cookie["secure"])
            self.assertEqual(cookie["samesite"], "strict")

    def test_samesite_none_requires_secure(self):
        """Verify validate_security_config enforces Secure=True when SameSite=None."""
        with self.assertRaises(ValueError) as ctx:
            validate_security_config(cookie_samesite="none", cookie_secure=False, cors_allowed_origins="http://localhost:3000")
        self.assertIn("cookie_samesite='none' requires cookie_secure=True", str(ctx.exception))

        # Secure=True should pass without exception
        validate_security_config(cookie_samesite="none", cookie_secure=True, cors_allowed_origins="http://localhost:3000")

    def test_samesite_rejects_unsupported_values(self):
        """Verify invalid SameSite value raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            validate_security_config(cookie_samesite="invalid_value", cookie_secure=False, cors_allowed_origins="http://localhost:3000")
        self.assertIn("Invalid cookie_samesite value", str(ctx.exception))

    def test_cors_prohibits_wildcard_with_credentials(self):
        """Verify wildcard CORS origin '*' is strictly prohibited."""
        with self.assertRaises(ValueError) as ctx:
            validate_security_config(cookie_samesite="lax", cookie_secure=False, cors_allowed_origins="http://localhost:3000,*")
        self.assertIn("Wildcard CORS origin '*' is prohibited", str(ctx.exception))

    def test_logout_cookie_attributes_match_login(self):
        """Verify delete_cookie uses matching secure, httponly, and samesite attributes."""
        with patch.object(settings, "cookie_secure", True), patch.object(settings, "cookie_samesite", "strict"):
            run_coro(register(RegisterRequest(username="attr_match_user", email="attrmatch@example.com", password="Password123!"), request=MockRequest(headers={"origin": "http://localhost:3000"})))
            login_resp = MockResponse()
            run_coro(login(LoginRequest(email="attrmatch@example.com", password="Password123!"), login_resp, MockRequest(headers={"origin": "http://localhost:3000"})))
            raw_token = login_resp.cookies[COOKIE_NAME]["value"]

            # Authenticate with cookie
            req = MockRequest(cookies={COOKIE_NAME: raw_token}, headers={"origin": "http://localhost:3000"}, method="POST")
            user = run_coro(get_current_user(req))

            logout_resp = MockResponse()
            run_coro(logout(req, logout_resp, current_user=user))

            del_details = logout_resp.deleted_cookie_details[COOKIE_NAME]
            self.assertTrue(del_details["secure"])
            self.assertTrue(del_details["httponly"])
            self.assertEqual(del_details["samesite"], "strict")
            self.assertEqual(del_details["path"], "/")


if __name__ == "__main__":
    unittest.main()
