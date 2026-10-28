"""
backend/routers/memory.py
==========================
FastAPI endpoints for managing and inspecting Project Memory (Phase 13).

ENDPOINTS:
    GET    /memory            → Stats and overview of facts & decisions
    GET    /memory/context    → Formatted context string ready for LLM prompt injection
    GET    /memory/facts      → List all facts (filter by category / tag)
    GET    /memory/facts/{key}→ Get a single fact by key
    POST   /memory/facts      → Add or update a fact
    DELETE /memory/facts/{key}→ Remove a fact
    GET    /memory/decisions  → List all architectural decisions (ADRs)
    POST   /memory/decisions  → Record a new architectural decision
    POST   /memory/search     → Semantic vector search across memory
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.brain import tools

router = APIRouter(
    prefix="/memory",
    tags=["Memory"],
)


# -------------------------------------------------------
# Pydantic Schemas
# -------------------------------------------------------

class FactCreateRequest(BaseModel):
    key: str = Field(..., min_length=1, description="Unique fact key (e.g. 'database_tech')")
    value: str = Field(..., min_length=1, description="Fact content/description")
    category: str = Field(default="general", description="Category: architecture, tech_stack, conventions, general")
    tags: Optional[List[str]] = Field(default=None, description="Keywords for filtering")


class DecisionCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Short decision title")
    description: str = Field(..., min_length=1, description="What was decided")
    rationale: str = Field(default="", description="Why this choice was made")
    tags: Optional[List[str]] = Field(default=None, description="Keywords for filtering")


class SearchMemoryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Max results to return")


# -------------------------------------------------------
# Endpoints
# -------------------------------------------------------

@router.get("", summary="Get memory stats & summary")
async def get_memory_overview() -> Dict[str, Any]:
    return tools.get_memory_stats()


@router.get("/context", summary="Get formatted memory context block for LLM prompt")
async def get_memory_context(
    category: Optional[str] = Query(default=None, description="Optional category filter"),
    max_chars: int = Query(default=2500, ge=100, le=10000, description="Character limit"),
) -> Dict[str, str]:
    context_block = tools.get_project_memory_context(max_chars=max_chars, category=category)
    return {"context": context_block}


@router.get("/facts", summary="List facts")
async def list_facts(
    category: Optional[str] = Query(default=None, description="Filter by category"),
    tag: Optional[str] = Query(default=None, description="Filter by tag"),
) -> List[Dict[str, Any]]:
    return tools.list_project_facts(category=category, tag=tag)


@router.get("/facts/{key}", summary="Get a fact by key")
async def get_fact(key: str) -> Dict[str, Any]:
    fact = tools.recall_fact(key)
    if not fact:
        raise HTTPException(status_code=404, detail=f"Fact with key '{key}' not found.")
    return fact


@router.post("/facts", summary="Add or update a fact")
async def add_fact(req: FactCreateRequest) -> Dict[str, Any]:
    return tools.remember_fact(
        key=req.key,
        value=req.value,
        category=req.category,
        tags=req.tags,
    )


@router.delete("/facts/{key}", summary="Delete a fact")
async def delete_fact(key: str) -> Dict[str, Any]:
    deleted = tools._memory_manager.delete_fact(key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Fact '{key}' not found.")
    return {"status": "deleted", "key": key}


@router.get("/decisions", summary="List architectural decisions")
async def list_decisions() -> List[Dict[str, Any]]:
    return tools.list_project_decisions()


@router.post("/decisions", summary="Record an architectural decision")
async def record_decision(req: DecisionCreateRequest) -> Dict[str, Any]:
    return tools.record_project_decision(
        title=req.title,
        description=req.description,
        rationale=req.rationale,
        tags=req.tags,
    )


@router.post("/search", summary="Semantic search over memory")
async def search_memory(req: SearchMemoryRequest) -> List[Dict[str, Any]]:
    return tools.search_project_memory(query=req.query, top_k=req.top_k)

