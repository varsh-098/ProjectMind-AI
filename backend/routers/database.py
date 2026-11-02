"""
backend/routers/database.py
============================
Phase 23 — FastAPI Endpoints for MongoDB Atlas Database Persistence.

ENDPOINTS:
    GET    /db/status                      → Probe MongoDB Atlas cluster status, latency & counts
    GET    /db/sessions                    → List conversation sessions
    POST   /db/sessions                    → Create a new conversation session
    GET    /db/sessions/{session_id}       → Get session metadata
    DELETE /db/sessions/{session_id}       → Delete a session and its message thread
    GET    /db/sessions/{session_id}/messages → Get chronological message history
    POST   /db/sessions/{session_id}/messages → Append message with LLM metadata
    GET    /db/runs                        → List Supervisor orchestration runs
    GET    /db/runs/{run_id}               → Get full trace for an agent run
"""

from typing import List, Dict, Any, Optional

try:
    from fastapi import APIRouter, HTTPException, Query
    from pydantic import BaseModel, Field
except ImportError:
    class APIRouter:
        def __init__(self, *args, **kwargs): pass
        def get(self, *args, **kwargs): return lambda f: f
        def post(self, *args, **kwargs): return lambda f: f
        def delete(self, *args, **kwargs): return lambda f: f

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str = ""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self) -> Dict[str, Any]:
            return dict(self.__dict__)

    def Field(default=None, **kwargs):
        return default

    def Query(default=None, **kwargs):
        return default

from backend.db.client import db_manager
from backend.db import repository

router = APIRouter(
    prefix="/db",
    tags=["Database Persistence"],
)


# -------------------------------------------------------
# Schemas
# -------------------------------------------------------

class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field(default="New Conversation", description="Session title.")
    session_id: Optional[str] = Field(default=None, description="Optional custom session UUID.")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AddMessageRequest(BaseModel):
    role: str = Field(..., description="Message author ('user', 'assistant', 'system').")
    content: str = Field(..., min_length=1, description="Message text.")
    tier_used: Optional[str] = Field(default=None, description="Model tier ('fast', 'complex', etc.).")
    model_used: Optional[str] = Field(default=None, description="Model name executed.")
    provider_used: Optional[str] = Field(default=None, description="Provider used ('groq', 'gemini').")
    latency_ms: Optional[float] = Field(default=None, description="LLM execution latency.")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


# -------------------------------------------------------
# Endpoints
# -------------------------------------------------------

@router.get("/status", summary="Probe MongoDB Atlas cluster status")
async def get_database_status() -> Dict[str, Any]:
    """Check connectivity to MongoDB Atlas cluster and return collection counts."""
    health = db_manager.ping()
    counts = {}
    if health.get("status") == "online":
        try:
            counts = {
                "sessions": db_manager.sessions.count_documents({}),
                "messages": db_manager.messages.count_documents({}),
                "agent_runs": db_manager.agent_runs.count_documents({}),
                "custom_agents": db_manager.custom_agents.count_documents({}),
            }
        except Exception:
            pass

    return {
        "health": health,
        "collections": counts,
    }


@router.get("/sessions", summary="List conversation sessions")
async def list_conversation_sessions(limit: int = 50) -> Dict[str, Any]:
    """Retrieve list of conversation sessions ordered by last active."""
    sessions = repository.list_sessions(limit=limit)
    return {"count": len(sessions), "sessions": sessions}


@router.post("/sessions", summary="Create conversation session")
async def create_conversation_session(req: CreateSessionRequest) -> Dict[str, Any]:
    """Create a new conversation session thread in the database."""
    session = repository.create_session(
        title=req.title,
        session_id=req.session_id,
        metadata=req.metadata,
    )
    return {"status": "created", "session": session}


@router.get("/sessions/{session_id}", summary="Get session metadata")
async def get_conversation_session(session_id: str) -> Dict[str, Any]:
    """Retrieve a single session by ID."""
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return session


@router.delete("/sessions/{session_id}", summary="Delete conversation session")
async def delete_conversation_session(session_id: str) -> Dict[str, Any]:
    """Delete a session and all associated messages."""
    existed = repository.delete_session(session_id)
    if not existed:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {"status": "deleted", "session_id": session_id}


@router.get("/sessions/{session_id}/messages", summary="Get session messages")
async def get_session_message_history(session_id: str, limit: int = 100) -> Dict[str, Any]:
    """Get chronological message history for a session."""
    messages = repository.get_session_messages(session_id, limit=limit)
    return {
        "session_id": session_id,
        "count": len(messages),
        "messages": messages,
    }


@router.post("/sessions/{session_id}/messages", summary="Add message to session")
async def add_session_message(session_id: str, req: AddMessageRequest) -> Dict[str, Any]:
    """Append a message to a session thread with LLM trace metadata."""
    msg = repository.add_message(
        session_id=session_id,
        role=req.role,
        content=req.content,
        tier_used=req.tier_used,
        model_used=req.model_used,
        provider_used=req.provider_used,
        latency_ms=req.latency_ms,
        metadata=req.metadata,
    )
    return {"status": "added", "message": msg}


@router.get("/runs", summary="List supervisor execution runs")
async def list_supervisor_runs(limit: int = 25) -> Dict[str, Any]:
    """List recent agent orchestration runs stored in MongoDB Atlas."""
    runs = repository.list_agent_runs(limit=limit)
    return {"count": len(runs), "runs": runs}


@router.get("/runs/{run_id}", summary="Get agent run trace")
async def get_supervisor_run(run_id: str) -> Dict[str, Any]:
    """Retrieve complete execution trace of an agent run."""
    run = repository.get_agent_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Agent run '{run_id}' not found.")
    return run

