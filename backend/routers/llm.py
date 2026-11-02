"""
backend/routers/llm.py
=======================
FastAPI endpoints for Phase 21: LLM Abstraction Layer & Failover Router.

ENDPOINTS:
    GET  /llm/health   → Probes all LLM providers and returns real-time online status & latency
    GET  /llm/config   → Current active provider, fallback chain, and configuration
    POST /llm/config   → Dynamically switch active provider or update failover priority
    POST /llm/chat     → Send message through resilient router with failover metadata
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.llm.router import default_llm_router

router = APIRouter(
    prefix="/llm",
    tags=["LLM Abstraction"],
)


# -------------------------------------------------------
# Pydantic Schemas
# -------------------------------------------------------

class RouterConfigRequest(BaseModel):
    active_provider: Optional[str] = Field(
        default=None,
        description="Switch primary provider ('groq', 'gemini', 'nemotron').",
        examples=["gemini"],
    )
    fallback_chain: Optional[List[str]] = Field(
        default=None,
        description="Set failover priority chain (e.g. ['groq', 'gemini', 'nemotron']).",
        examples=[["groq", "gemini", "nemotron"]],
    )


class LLMChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Message or prompt to send to the LLM.")
    system_instruction: Optional[str] = Field(
        default=None,
        description="Optional custom system instructions / persona override.",
    )


class LLMChatResponse(BaseModel):
    response: str
    metadata: Dict[str, Any]


# -------------------------------------------------------
# Endpoints
# -------------------------------------------------------

@router.get("/health", summary="Probe health of all LLM providers")
async def get_llm_health() -> Dict[str, Any]:
    """
    Ping all supported LLM providers and return latency and availability status.
    """
    return await default_llm_router.check_health()


@router.get("/config", summary="Get router configuration")
async def get_router_config() -> Dict[str, Any]:
    """
    Return the active provider, fallback chain, and last execution details.
    """
    return default_llm_router.get_config()


@router.post("/config", summary="Update router configuration dynamically")
async def update_router_config(req: RouterConfigRequest) -> Dict[str, Any]:
    """
    Switch active provider or fallback chain at runtime without restarting the server.
    """
    try:
        if req.active_provider:
            default_llm_router.set_active_provider(req.active_provider)
        if req.fallback_chain:
            default_llm_router.set_fallback_chain(req.fallback_chain)

        return {
            "status": "updated",
            "config": default_llm_router.get_config(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/chat", response_model=LLMChatResponse, summary="Send chat through resilient failover router")
async def router_chat(req: LLMChatRequest) -> LLMChatResponse:
    """
    Route message through the fallback chain and return response with execution trace.
    """
    try:
        response_text = await default_llm_router.chat(
            message=req.message,
            system_instruction=req.system_instruction,
        )
        return LLMChatResponse(
            response=response_text,
            metadata=default_llm_router.last_execution_meta,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

