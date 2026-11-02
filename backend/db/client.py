"""
backend/db/client.py
=====================
Phase 23 — MongoDB Atlas Client & Connection Manager.

PURPOSE:
    Provides resilient connection management, health probing, and collection
    access for MongoDB Atlas cloud database.
"""

import logging
import time
from typing import Optional, Dict, Any

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    HAS_PYMONGO = True
except ImportError:
    MongoClient = None
    ConnectionFailure = Exception
    ServerSelectionTimeoutError = Exception
    HAS_PYMONGO = False

from backend.config import settings

logger = logging.getLogger("projectmind.db.client")


class MongoDBManager:
    """
    Manages MongoDB Atlas connection, collections, and connection health.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        db_name: Optional[str] = None,
        use_settings: bool = True,
    ):
        self._custom_uri = uri
        self._custom_db_name = db_name
        self._use_settings = use_settings
        self._client: Optional[Any] = None
        self._db: Optional[Any] = None

    @property
    def uri(self) -> Optional[str]:
        if self._custom_uri is not None:
            return self._custom_uri
        if self._use_settings:
            return getattr(settings, "mongodb_uri", None)
        return None

    @property
    def db_name(self) -> str:
        return self._custom_db_name or getattr(settings, "mongodb_db_name", "projectmind")

    @property
    def is_configured(self) -> bool:
        return bool(self.uri and self.uri.strip())

    def get_client(self) -> Any:
        """Get or initialize PyMongo client."""
        if not HAS_PYMONGO:
            raise RuntimeError(
                "pymongo is not installed. Install it with: pip install pymongo dnspython"
            )

        if not self.is_configured:
            raise ValueError(
                "MONGODB_URI is not set. Add your MongoDB Atlas connection string to .env:\n"
                "MONGODB_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority"
            )

        if self._client is None:
            # Set a 5-second server selection timeout to fail fast if offline
            self._client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                appName="ProjectMind-AI",
            )
        return self._client

    def get_database(self) -> Any:
        """Return the active MongoDB database."""
        if self._db is None:
            client = self.get_client()
            self._db = client[self.db_name]
            self._ensure_indexes()
        return self._db

    def _ensure_indexes(self) -> None:
        """Create standard indexes for high-performance querying."""
        try:
            db = self._db
            if db is not None:
                db["messages"].create_index("session_id")
                db["messages"].create_index("timestamp")
                db["agent_runs"].create_index("run_id", unique=True)
                db["agent_runs"].create_index("timestamp")
                db["sessions"].create_index("session_id", unique=True)
                db["custom_agents"].create_index("name", unique=True)
        except Exception as e:
            logger.warning(f"Could not build indexes (might be read-only or connecting): {e}")

    # ------------------------------------------------------------------
    # Health Probing
    # ------------------------------------------------------------------

    def ping(self) -> Dict[str, Any]:
        """
        Ping MongoDB Atlas cluster and return status, latency, and cluster info.
        """
        if not HAS_PYMONGO:
            return {
                "status": "unconfigured",
                "error": "pymongo library is not installed in the environment.",
            }

        if not self.is_configured:
            return {
                "status": "unconfigured",
                "error": "MONGODB_URI is not set in .env.",
            }

        t0 = time.perf_counter()
        try:
            client = self.get_client()
            # Send ping command to admin database
            client.admin.command("ping")
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)

            # Retrieve server build info
            info = client.server_info()
            version = info.get("version", "unknown")

            return {
                "status": "online",
                "latency_ms": latency_ms,
                "database": self.db_name,
                "version": version,
                "connected": True,
            }
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            return {
                "status": "offline",
                "error": f"Could not connect to MongoDB Atlas cluster: {e}",
                "connected": False,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "connected": False,
            }

    # ------------------------------------------------------------------
    # Collection Accessors
    # ------------------------------------------------------------------

    @property
    def sessions(self) -> Any:
        return self.get_database()["sessions"]

    @property
    def messages(self) -> Any:
        return self.get_database()["messages"]

    @property
    def agent_runs(self) -> Any:
        return self.get_database()["agent_runs"]

    @property
    def custom_agents(self) -> Any:
        return self.get_database()["custom_agents"]

    def close(self) -> None:
        """Close connection pool."""
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None


# Global database manager singleton
db_manager = MongoDBManager()

