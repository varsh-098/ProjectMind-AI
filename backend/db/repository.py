"""
backend/db/repository.py
=========================
Phase 23 — Data Access Repository for ProjectMind AI.

PURPOSE:
    Provides high-level CRUD operations for:
      1. Sessions: Multi-turn conversation sessions.
      2. Messages: Chat messages with model/tier execution traces.
      3. Agent Runs: Supervisor orchestrations, tool logs, and stage outputs.
      4. Custom Agents: Persistent database storage for custom AI agents.
      5. Hybrid / Fallback support: Automatically uses local in-memory fallback
         during offline unit tests if MongoDB Atlas is unconfigured.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.db.client import db_manager


class InMemoryFallbackStore:
    """Lightweight in-memory fallback store for offline tests and unconfigured setups."""

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.messages: List[Dict[str, Any]] = []
        self.agent_runs: Dict[str, Dict[str, Any]] = {}
        self.custom_agents: Dict[str, Dict[str, Any]] = {}

    def clear(self):
        self.sessions.clear()
        self.messages.clear()
        self.agent_runs.clear()
        self.custom_agents.clear()


_memory_store = InMemoryFallbackStore()


def _is_mongo_active() -> bool:
    """Return True if MongoDB Atlas is configured and reachable."""
    if not db_manager.is_configured:
        return False
    try:
        db_manager.get_client()
        return True
    except Exception:
        return False


# =====================================================================
# 1. Sessions Management
# =====================================================================

def create_session(
    title: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create and persist a new conversation session."""
    sid = session_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "session_id": sid,
        "title": title or "New Conversation",
        "created_at": now,
        "updated_at": now,
        "metadata": metadata or {},
    }

    if _is_mongo_active():
        try:
            db_manager.sessions.update_one(
                {"session_id": sid},
                {"$set": doc},
                upsert=True,
            )
            return doc
        except Exception:
            pass

    _memory_store.sessions[sid] = dict(doc)
    return doc


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session details by ID."""
    if _is_mongo_active():
        try:
            doc = db_manager.sessions.find_one({"session_id": session_id}, {"_id": 0})
            if doc:
                return doc
        except Exception:
            pass

    return _memory_store.sessions.get(session_id)


def list_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    """List recent conversation sessions."""
    if _is_mongo_active():
        try:
            cursor = db_manager.sessions.find({}, {"_id": 0}).sort("updated_at", -1).limit(limit)
            return list(cursor)
        except Exception:
            pass

    sessions = list(_memory_store.sessions.values())
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions[:limit]


def delete_session(session_id: str) -> bool:
    """Delete a session and all its messages."""
    if _is_mongo_active():
        try:
            res = db_manager.sessions.delete_one({"session_id": session_id})
            db_manager.messages.delete_many({"session_id": session_id})
            return res.deleted_count > 0
        except Exception:
            pass

    existed = session_id in _memory_store.sessions
    _memory_store.sessions.pop(session_id, None)
    _memory_store.messages = [m for m in _memory_store.messages if m.get("session_id") != session_id]
    return existed


# =====================================================================
# 2. Messages Management
# =====================================================================

def add_message(
    session_id: str,
    role: str,
    content: str,
    tier_used: Optional[str] = None,
    model_used: Optional[str] = None,
    provider_used: Optional[str] = None,
    latency_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append a message to a session thread with LLM trace metadata."""
    now = datetime.now(timezone.utc).isoformat()
    msg_id = str(uuid.uuid4())
    doc = {
        "message_id": msg_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "tier_used": tier_used,
        "model_used": model_used,
        "provider_used": provider_used,
        "latency_ms": latency_ms,
        "timestamp": now,
        "metadata": metadata or {},
    }

    if _is_mongo_active():
        try:
            db_manager.messages.insert_one(dict(doc))
            # Touch session updated_at
            db_manager.sessions.update_one(
                {"session_id": session_id},
                {"$set": {"updated_at": now}},
                upsert=True,
            )
            doc.pop("_id", None)
            return doc
        except Exception:
            pass

    _memory_store.messages.append(dict(doc))
    if session_id in _memory_store.sessions:
        _memory_store.sessions[session_id]["updated_at"] = now
    return doc


def get_session_messages(session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve message history for a session ordered chronologically."""
    if _is_mongo_active():
        try:
            cursor = (
                db_manager.messages.find({"session_id": session_id}, {"_id": 0})
                .sort("timestamp", 1)
                .limit(limit)
            )
            return list(cursor)
        except Exception:
            pass

    matched = [m for m in _memory_store.messages if m.get("session_id") == session_id]
    matched.sort(key=lambda m: m.get("timestamp", ""))
    return matched[:limit]


# =====================================================================
# 3. Agent Runs & Traces
# =====================================================================

def record_agent_run(
    task: str,
    intent: str,
    stages: List[str],
    results: Dict[str, Any],
    summary: str,
    success: bool = True,
    session_id: Optional[str] = None,
    total_latency_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record a multi-agent orchestration execution run with stage outputs."""
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "run_id": run_id,
        "session_id": session_id,
        "task": task,
        "intent": intent,
        "stages": list(stages),
        "results": results,
        "summary": summary,
        "success": success,
        "total_latency_ms": total_latency_ms,
        "timestamp": now,
        "metadata": metadata or {},
    }

    if _is_mongo_active():
        try:
            db_manager.agent_runs.insert_one(dict(doc))
            doc.pop("_id", None)
            return doc
        except Exception:
            pass

    _memory_store.agent_runs[run_id] = dict(doc)
    return doc


def get_agent_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full execution trace of an agent run."""
    if _is_mongo_active():
        try:
            doc = db_manager.agent_runs.find_one({"run_id": run_id}, {"_id": 0})
            if doc:
                return doc
        except Exception:
            pass

    return _memory_store.agent_runs.get(run_id)


def list_agent_runs(limit: int = 25) -> List[Dict[str, Any]]:
    """List recent supervisor agent execution runs."""
    if _is_mongo_active():
        try:
            cursor = db_manager.agent_runs.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
            return list(cursor)
        except Exception:
            pass

    runs = list(_memory_store.agent_runs.values())
    runs.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return runs[:limit]


# =====================================================================
# 4. Custom Agents Persistence
# =====================================================================

def save_custom_agent_spec(spec_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a custom agent specification to the database."""
    name = spec_dict.get("name")
    if not name:
        raise ValueError("Custom agent spec must have a 'name' field.")

    now = datetime.now(timezone.utc).isoformat()
    doc = dict(spec_dict)
    doc["updated_at"] = now
    if not doc.get("created_at"):
        doc["created_at"] = now

    if _is_mongo_active():
        try:
            db_manager.custom_agents.update_one(
                {"name": name},
                {"$set": doc},
                upsert=True,
            )
            doc.pop("_id", None)
            return doc
        except Exception:
            pass

    _memory_store.custom_agents[name] = dict(doc)
    return doc


def get_custom_agent_spec(name: str) -> Optional[Dict[str, Any]]:
    """Retrieve custom agent spec from database by name."""
    clean = name.strip().lower().replace(" ", "_")
    if _is_mongo_active():
        try:
            doc = db_manager.custom_agents.find_one({"name": clean}, {"_id": 0})
            if doc:
                return doc
        except Exception:
            pass

    return _memory_store.custom_agents.get(clean)


def list_custom_agent_specs() -> List[Dict[str, Any]]:
    """List all custom agents persisted in the database."""
    if _is_mongo_active():
        try:
            cursor = db_manager.custom_agents.find({"is_template": {"$ne": True}}, {"_id": 0})
            return list(cursor)
        except Exception:
            pass

    return [s for s in _memory_store.custom_agents.values() if not s.get("is_template")]


def delete_custom_agent_spec(name: str) -> bool:
    """Delete a custom agent from database."""
    clean = name.strip().lower().replace(" ", "_")
    if _is_mongo_active():
        try:
            res = db_manager.custom_agents.delete_one({"name": clean})
            return res.deleted_count > 0
        except Exception:
            pass

    return bool(_memory_store.custom_agents.pop(clean, None))

