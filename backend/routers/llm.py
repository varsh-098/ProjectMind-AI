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

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    # Graceful fallback when fastapi or pydantic is not installed in current environment
    class APIRouter:
        def __init__(self, *args, **kwargs):
            self.routes = []
        def get(self, *args, **kwargs):
            return lambda f: f
        def post(self, *args, **kwargs):
            return lambda f: f
        def put(self, *args, **kwargs):
            return lambda f: f
        def delete(self, *args, **kwargs):
            return lambda f: f

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

from backend.llm.router import default_llm_router
from backend.llm.model_registry import model_registry, ModelTier

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


class ConfigureTierRequest(BaseModel):
    tier: str = Field(..., description="Target tier ('fast', 'balanced', 'complex', 'local').")
    provider: Optional[str] = Field(default=None, description="Primary provider for this tier ('groq', 'gemini', 'nemotron').")
    model_name: Optional[str] = Field(default=None, description="Model identifier to run on this tier.")
    description: Optional[str] = Field(default=None, description="Optional updated tier description.")
    fallback_chain: Optional[List[str]] = Field(default=None, description="Failover priority list for this tier.")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.5)


class TierChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Message or prompt to send to the specialized model.")
    system_instruction: Optional[str] = Field(default=None, description="Optional system prompt / persona override.")
    tier: Optional[str] = Field(default=None, description="Target tier: 'fast', 'balanced', 'complex', or 'local'.")
    task_type: Optional[str] = Field(default=None, description="Task category: 'coding', 'review', 'routing', etc.")


class TierChatResponse(BaseModel):
    response: str
    tier: Optional[str] = None
    model_used: Optional[str] = None
    provider_used: Optional[str] = None
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


# -------------------------------------------------------
# Phase 22: Tier Specialization Endpoints
# -------------------------------------------------------

@router.get("/tiers", summary="List all configured model tiers and task mappings")
async def get_model_tiers() -> Dict[str, Any]:
    """
    Retrieve configured tiers (FAST, BALANCED, COMPLEX, LOCAL) and default task mappings.
    """
    return {
        "tiers": model_registry.list_tiers(),
        "task_mappings": model_registry.list_task_mappings(),
    }


@router.post("/tiers/configure", summary="Update model configuration for a specific tier")
async def configure_model_tier(req: ConfigureTierRequest) -> Dict[str, Any]:
    """
    Dynamically update provider, model, or fallback chain assigned to a tier at runtime.
    """
    try:
        updated = model_registry.update_profile(
            tier=req.tier,
            provider=req.provider,
            model_name=req.model_name,
            description=req.description,
            fallback_chain=req.fallback_chain,
            temperature=req.temperature,
        )
        return {
            "status": "updated",
            "tier": updated.to_dict(),
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tiers/route", response_model=TierChatResponse, summary="Execute prompt via specialized model tier")
async def route_tier_chat(req: TierChatRequest) -> TierChatResponse:
    """
    Send prompt to a specialized model tier (e.g. FAST for routing, COMPLEX for coding)
    with automatic failover and execution metadata.
    """
    try:
        response_text = await default_llm_router.chat(
            message=req.message,
            system_instruction=req.system_instruction,
            tier=req.tier,
            task_type=req.task_type,
        )
        meta = default_llm_router.last_execution_meta
        return TierChatResponse(
            response=response_text,
            tier=meta.get("tier_used"),
            model_used=meta.get("model_used"),
            provider_used=meta.get("provider_used"),
            metadata=meta,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

