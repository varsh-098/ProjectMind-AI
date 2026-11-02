"""
tests/test_auth_security.py
============================
Automated unit tests for Stage 1: Database and Security Foundation.
Tests Argon2id password hashing, verification, session token generation,
SHA-256 token hashing, and normalization.
"""

import unittest
from backend.auth.security import (
    hash_password,
    verify_password,
    check_needs_rehash,
    generate_session_token,
    hash_session_token,
    normalize_email,
    normalize_username,
)
from backend.db.client import MongoDBManager


class TestAuthSecurity(unittest.TestCase):
    """Test suite for Argon2id and cryptographic session primitives."""

    def test_argon2id_hash_format(self):
        """Verify hash_password produces valid Argon2id formatted string."""
        raw_pw = "SuperSecretPassword123!"
        hashed = hash_password(raw_pw)
        self.assertTrue(hashed.startswith("$argon2id$"))
        self.assertIn("m=65536,t=2,p=1", hashed)

    def test_password_verification_success(self):
        """Verify correct password matches Argon2id hash."""
        raw_pw = "ValidPasscode123"
        hashed = hash_password(raw_pw)
        self.assertTrue(verify_password(raw_pw, hashed))

    def test_password_verification_mismatch(self):
        """Verify incorrect password fails verification."""
        raw_pw = "CorrectPassword123"
        wrong_pw = "WrongPassword456"
        hashed = hash_password(raw_pw)
        self.assertFalse(verify_password(wrong_pw, hashed))

    def test_password_length_validation(self):
        """Verify passwords <8 or >128 chars raise ValueError."""
        with self.assertRaises(ValueError):
            hash_password("short")

        long_pw = "a" * 129
        with self.assertRaises(ValueError):
            hash_password(long_pw)

    def test_verify_malformed_hash_returns_false(self):
        """Verify corrupted hash string returns False without crashing."""
        self.assertFalse(verify_password("Password123", "not_a_valid_argon2_hash"))
        self.assertFalse(verify_password("", "$argon2id$v=19$dummy"))
        self.assertFalse(verify_password("Password123", ""))

    def test_session_token_entropy(self):
        """Verify session tokens are non-empty, random, and unique."""
        t1 = generate_session_token()
        t2 = generate_session_token()
        self.assertNotEqual(t1, t2)
        self.assertTrue(len(t1) >= 40)

    def test_session_token_hashing(self):
        """Verify SHA-256 token hashing produces 64-char hex string."""
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        self.assertEqual(len(token_hash), 64)
        # Deterministic check
        self.assertEqual(token_hash, hash_session_token(raw_token))

        # Different tokens yield different hashes
        raw_token_2 = generate_session_token()
        self.assertNotEqual(token_hash, hash_session_token(raw_token_2))

    def test_session_token_empty_raises(self):
        """Verify empty session token raises ValueError."""
        with self.assertRaises(ValueError):
            hash_session_token("")

    def test_normalize_email(self):
        """Verify email normalization lowercases and trims whitespace."""
        self.assertEqual(normalize_email("  User@Example.COM  "), "user@example.com")
        with self.assertRaises(ValueError):
            normalize_email("not-an-email")

    def test_normalize_username(self):
        """Verify username normalization and character restrictions."""
        self.assertEqual(normalize_username("  Alice_99  "), "alice_99")
        with self.assertRaises(ValueError):
            normalize_username("ab")  # Too short (<3)
        with self.assertRaises(ValueError):
            normalize_username("user with spaces!")


class TestDBManagerAuthExtensions(unittest.TestCase):
    """Test suite verifying MongoDBManager has users and auth_sessions properties."""

    def test_manager_has_auth_collections(self):
        """Verify MongoDBManager class defines users and auth_sessions properties."""
        self.assertTrue(isinstance(getattr(MongoDBManager, "users", None), property))
        self.assertTrue(isinstance(getattr(MongoDBManager, "auth_sessions", None), property))


if __name__ == "__main__":
    unittest.main()
