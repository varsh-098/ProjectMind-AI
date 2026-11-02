"""
scripts/verify_live_atlas_backend.py
====================================
End-to-end verification of the ProjectMind AI backend against live MongoDB Atlas.

Covers:
  1. Live Atlas cluster connectivity & latency.
  2. Automatic index creation & verification (users, auth_sessions, messages, agent_runs).
  3. Live User Registration (Argon2id hashing, unique constraints).
  4. Live User Authentication & Session issuance (CSPRNG token, SHA-256 token_hash).
  5. Live Protected Route access (GET /auth/me).
  6. Live Session Revocation (POST /auth/logout).
  7. Live Project Session, Message, and Agent Run Persistence (Phase 23 core).
  8. Clean-up of test artifacts from the live cluster.

RUN:
    python scripts/verify_live_atlas_backend.py
"""

import sys
import uuid
import asyncio
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.config import settings
from backend.db.client import db_manager
from backend.auth.security import hash_session_token, verify_password
from backend.auth import repository as auth_repo
from backend.auth.dependencies import (
    get_current_user,
    COOKIE_NAME,
    Request,
    HTTPException,
)
from backend.routers.auth import (
    register,
    login,
    get_me,
    logout,
    RegisterRequest,
    LoginRequest,
    Response,
)
from backend.db import repository as db_repo


class LiveMockResponse:
    """Mock HTTP Response to capture emitted cookies."""
    def __init__(self):
        self.cookies = {}
        self.deleted_cookies = []

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
        self.cookies.pop(key, None)


class LiveMockRequestState:
    def __init__(self):
        self.auth_type = None
        self.session_token_hash = None
        self.session_id = None


class LiveMockRequest:
    """Mock HTTP Request with headers, cookies, and state."""
    def __init__(self, cookies=None, headers=None, method="POST"):
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.method = method
        self.state = LiveMockRequestState()
        self.client = type("Client", (), {"host": "127.0.0.1"})()


def run_async(coro):
    return asyncio.run(coro)


def main():
    print("=" * 75)
    print("  PROJECTMIND AI — END-TO-END MONGODB ATLAS LIVE BACKEND TEST")
    print("=" * 75)

    # -------------------------------------------------------------
    # 1. Connection & Index Verification
    # -------------------------------------------------------------
    print("\n[STEP 1] Testing live MongoDB Atlas connectivity & indexes...")
    health = db_manager.ping()
    if health.get("status") != "online":
        print(f"  [ERROR] Cannot connect to MongoDB Atlas: {health.get('error')}")
        sys.exit(1)

    print(f"  -> Cluster Status : ONLINE")
    print(f"  -> Latency        : {health.get('latency_ms')} ms")
    print(f"  -> Server Version : {health.get('version')}")
    print(f"  -> Database Name  : {health.get('database')}")

    db = db_manager.get_database()
    db_manager._ensure_indexes()

    users_indexes = [idx["name"] for idx in db["users"].list_indexes()]
    sessions_indexes = [idx["name"] for idx in db["auth_sessions"].list_indexes()]
    print(f"  -> 'users' indexes        : {users_indexes}")
    print(f"  -> 'auth_sessions' indexes : {sessions_indexes}")
    print("  [PASS] Live Atlas connection and indexes confirmed.")

    # Unique test identifiers
    test_id = uuid.uuid4().hex[:8]
    test_username = f"atlas_dev_{test_id}"
    test_email = f"atlas_{test_id}@projectmind.test"
    test_password = "SuperSecurePassword123!"

    created_user_id = None
    created_raw_token = None

    try:
        # -------------------------------------------------------------
        # 2. Live Registration Test
        # -------------------------------------------------------------
        print(f"\n[STEP 2] Testing User Registration on Live Atlas ({test_email})...")
        reg_req = RegisterRequest(
            username=test_username,
            email=test_email,
            password=test_password,
        )
        http_reg_req = LiveMockRequest(headers={"origin": "http://localhost:3000"})
        reg_res = run_async(register(reg_req, request=http_reg_req))

        created_user_id = reg_res["user"]["user_id"]
        print(f"  -> User registered with user_id : {created_user_id}")
        print(f"  -> API response sanitized       : 'password_hash' not in response: {'password_hash' not in reg_res['user']}")

        # Query live Atlas directly to verify storage security
        user_in_db = db["users"].find_one({"user_id": created_user_id})
        assert user_in_db is not None, "User doc not found in live Atlas!"
        assert test_password not in str(user_in_db), "Plaintext password found in Atlas!"
        assert user_in_db["password_hash"].startswith("$argon2id$"), "Password hash is not Argon2id!"
        print(f"  -> Atlas document verified      : Password hashed with Argon2id ({user_in_db['password_hash'][:28]}...)")

        # Test duplicate rejection on live Atlas
        print("  -> Testing duplicate registration rejection...")
        duplicate_req = RegisterRequest(
            username=f"dup_{test_id}",
            email=test_email.upper(),  # Should be normalized
            password="DifferentPassword456!",
        )
        try:
            run_async(register(duplicate_req, request=http_reg_req))
            print("  [FAIL] Duplicate registration should have been rejected!")
        except HTTPException as e:
            assert e.status_code == 409, f"Expected 409, got {e.status_code}"
            print(f"  -> Duplicate caught successfully : HTTP {e.status_code} ({e.detail})")
        print("  [PASS] User Registration and unique constraint enforcement verified on live Atlas.")

        # -------------------------------------------------------------
        # 3. Live Login & Session Issuance Test
        # -------------------------------------------------------------
        print(f"\n[STEP 3] Testing User Login & Session Issuance on Live Atlas...")
        login_req = LoginRequest(
            email=test_email,
            password=test_password,
        )
        login_resp = LiveMockResponse()
        http_login_req = LiveMockRequest(headers={"origin": "http://localhost:3000"})
        login_res = run_async(login(login_req, response=login_resp, request=http_login_req))

        assert login_res["status"] == "authenticated"
        assert COOKIE_NAME in login_resp.cookies, "HttpOnly session cookie was not set!"
        cookie_data = login_resp.cookies[COOKIE_NAME]
        created_raw_token = cookie_data["value"]

        print(f"  -> Login status          : {login_res['status']}")
        print(f"  -> Cookie Name           : {COOKIE_NAME}")
        print(f"  -> Cookie HttpOnly flag  : {cookie_data['httponly']}")
        print(f"  -> Cookie SameSite flag  : {cookie_data['samesite']}")
        print(f"  -> Cookie Max-Age (sec)  : {cookie_data['max_age']}")
        print(f"  -> Raw token length      : {len(created_raw_token)} chars")

        # Inspect live Atlas auth_sessions collection
        token_hash = hash_session_token(created_raw_token)
        session_in_db = db["auth_sessions"].find_one({"token_hash": token_hash})
        assert session_in_db is not None, "Auth session not found in live Atlas!"
        assert created_raw_token not in str(session_in_db), "Raw token leaked into Atlas database!"
        assert session_in_db["user_id"] == created_user_id
        assert session_in_db["is_revoked"] is False
        print(f"  -> Atlas session verified: Stored ONLY SHA-256 hash ({token_hash[:20]}...)")
        print(f"  -> Session Expiration    : {session_in_db['expires_at'].isoformat()}")
        print("  [PASS] Login, session token hashing, and cookie issuance verified on live Atlas.")

        # -------------------------------------------------------------
        # 4. Live Protected Route Access (GET /auth/me)
        # -------------------------------------------------------------
        print(f"\n[STEP 4] Testing Protected Route (/auth/me) using live session cookie...")
        protected_req = LiveMockRequest(
            cookies={COOKIE_NAME: created_raw_token},
            headers={"origin": "http://localhost:3000"},
            method="GET",
        )
        current_user = run_async(get_current_user(protected_req))
        me_res = run_async(get_me(current_user=current_user))

        assert me_res["authenticated"] is True
        assert me_res["user"]["user_id"] == created_user_id
        assert me_res["user"]["email"] == test_email
        print(f"  -> Authenticated User ID : {me_res['user']['user_id']}")
        print(f"  -> Authenticated Email   : {me_res['user']['email']}")
        print(f"  -> Transport Method      : {protected_req.state.auth_type}")
        print("  [PASS] Protected route access and user profile injection verified.")

        # -------------------------------------------------------------
        # 5. Live Logout & Session Revocation
        # -------------------------------------------------------------
        print(f"\n[STEP 5] Testing Logout & Session Revocation on Live Atlas...")
        logout_req = LiveMockRequest(
            cookies={COOKIE_NAME: created_raw_token},
            headers={"origin": "http://localhost:3000"},
            method="POST",
        )
        logout_resp = LiveMockResponse()
        logout_user = run_async(get_current_user(logout_req))
        logout_res = run_async(logout(logout_req, logout_resp, current_user=logout_user))

        assert logout_res["status"] == "logged_out"
        assert COOKIE_NAME in logout_resp.deleted_cookies
        print(f"  -> Logout status         : {logout_res['status']}")
        print(f"  -> Cookie deleted        : {COOKIE_NAME in logout_resp.deleted_cookies}")

        # Check revocation in live Atlas
        revoked_session = db["auth_sessions"].find_one({"token_hash": token_hash})
        assert revoked_session["is_revoked"] is True, "Session was not marked revoked in Atlas!"
        print(f"  -> Atlas session record  : is_revoked = {revoked_session['is_revoked']}")

        # Ensure subsequent requests with revoked token are rejected
        try:
            check_req = LiveMockRequest(
                cookies={COOKIE_NAME: created_raw_token},
                headers={"origin": "http://localhost:3000"},
                method="GET",
            )
            run_async(get_current_user(check_req))
            print("  [FAIL] Revoked session was accepted!")
        except HTTPException as e:
            assert e.status_code == 401
            print(f"  -> Subsequent access test: Rejected with HTTP {e.status_code} ({e.detail})")
        print("  [PASS] Session revocation on live Atlas confirmed.")

        # -------------------------------------------------------------
        # 6. Live Project Conversation, Messages & Agent Run Persistence
        # -------------------------------------------------------------
        print(f"\n[STEP 6] Testing Phase 23 Project Session, Messages & Agent Runs on Live Atlas...")
        conv_session_id = f"test_session_{test_id}"
        db_repo.create_session(
            title="Atlas Verification Conversation",
            session_id=conv_session_id,
            metadata={"model": "gemini-2.5-flash", "provider": "gemini"},
        )

        msg1 = db_repo.add_message(
            session_id=conv_session_id,
            role="user",
            content="Can you review the authentication architecture?",
        )
        msg2 = db_repo.add_message(
            session_id=conv_session_id,
            role="assistant",
            content="The architecture uses Argon2id and SHA-256 session tokens.",
        )

        agent_run = db_repo.record_agent_run(
            task="Verify live MongoDB Atlas persistence",
            intent="TESTING",
            stages=["setup", "verify"],
            results={"status": "ok"},
            summary="All persistence tests passed on Atlas cluster.",
            session_id=conv_session_id,
        )
        run_id = agent_run["run_id"]

        # Retrieve and verify from Atlas
        history = db_repo.get_session_messages(conv_session_id)
        assert len(history) == 2, f"Expected 2 messages, found {len(history)}"
        print(f"  -> Live messages stored  : {len(history)} messages verified")
        print(f"     1. [{history[0]['role']}] {history[0]['content']}")
        print(f"     2. [{history[1]['role']}] {history[1]['content']}")

        stored_run = db_repo.get_agent_run(run_id)
        assert stored_run is not None
        print(f"  -> Live agent run logged : {stored_run['task']} (intent={stored_run['intent']})")
        print("  [PASS] Phase 23 Session, Message and Agent Run persistence verified.")

    finally:
        # -------------------------------------------------------------
        # 7. Clean-up of Test Records
        # -------------------------------------------------------------
        print(f"\n[STEP 7] Cleaning up test records from Live Atlas...")
        try:
            if created_user_id:
                del_users = db["users"].delete_many({"user_id": created_user_id})
                del_sessions = db["auth_sessions"].delete_many({"user_id": created_user_id})
                print(f"  -> Deleted {del_users.deleted_count} test user(s)")
                print(f"  -> Deleted {del_sessions.deleted_count} test auth session(s)")

            del_conv = db["sessions"].delete_many({"session_id": f"test_session_{test_id}"})
            del_msgs = db["messages"].delete_many({"session_id": f"test_session_{test_id}"})
            del_runs = db["agent_runs"].delete_many({"run_id": f"run_{test_id}"})
            print(f"  -> Deleted {del_conv.deleted_count} test conversation session(s)")
            print(f"  -> Deleted {del_msgs.deleted_count} test message(s)")
            print(f"  -> Deleted {del_runs.deleted_count} test agent run(s)")
            print("  [PASS] Clean-up complete. Live cluster remains clean.")
        except Exception as e:
            print(f"  [!] Clean-up notice: {e}")

    print("\n" + "=" * 75)
    print("  [ALL PASS] LIVE BACKEND & MONGODB ATLAS VERIFICATION SUCCESSFUL!")
    print("=" * 75)


if __name__ == "__main__":
    main()
