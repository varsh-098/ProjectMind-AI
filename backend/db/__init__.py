"""
backend/db/__init__.py
=======================
Phase 23 — Database Layer for ProjectMind AI (MongoDB Atlas).
"""

from backend.db.client import db_manager, MongoDBManager
from backend.db import repository

__all__ = [
    "db_manager",
    "MongoDBManager",
    "repository",
]

