"""
backend/routers/chat.py
Phase 5 -- Chat and Health routes

WHAT IS A ROUTER IN FASTAPI?
    A router is a group of related endpoints. Instead of defining all routes
    directly in main.py, we group them by feature. Here, all "chat" related
    routes live together. main.py imports and registers this router.

    This is the same idea as Blueprints in Flask, or Controllers in MVC.
    It keeps the codebase modular -- as ProjectMind grows, we can add
    routers/memory.py, routers/agents.py etc. without touching main.py.

WHAT IS PYDANTIC?
    Pydantic is a data validation library. When FastAPI receives an HTTP
    request body, Pydantic automatically:
        1. Parses the raw JSON
        2. Validates that required fields exist and have the right type
        3. Converts them into a typed Python object
        4. Returns a clear HTTP 422 error if validation fails

    Without Pydantic, you would manually check every field, every type,
    every missing value. Pydantic does this for free.

ASYNC / AWAIT IN FASTAPI:
    FastAPI is built on asyncio. When you define a route with 'async def',
    FastAPI can handle multiple requests concurrently without blocking.

    However: requests.post() (our call to llama-server) is SYNCHRONOUS.
    A sync call inside an async function would block the entire event loop.

    FastAPI fixes this with run_in_executor -- but for now we use a simple
    approach: we define the route as a plain 'def' (not async def).
    FastAPI automatically runs plain def routes in a thread pool so they
    don't block. This is the correct pattern for sync I/O in FastAPI.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Import our Phase 4 service function.
# Note: nemotron.py's if __name__ == "__main__" block does NOT run on import.
# Only ask_nemotron() is imported and made available here.
from backend.services.nemotron import ask_nemotron

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
# APIRouter() creates a group of routes. The prefix="/api/v1" is added by
# main.py when it includes this router. We don't hardcode the prefix here
# so it can be changed centrally without editing this file.

router = APIRouter()


# ---------------------------------------------------------------------------
# Request and Response models
# ---------------------------------------------------------------------------
# These are Pydantic models. They define the SHAPE of the JSON that this
# endpoint accepts and returns.
#
# CHATREQUEST:
#   The client sends:  { "question": "What is an API?" }
#   FastAPI validates this automatically before our function runs.
#   If 'question' is missing: HTTP 422 Unprocessable Entity.
#   If 'question' is not a string: HTTP 422.
#
# CHATRESPONSE:
#   We return:  { "answer": "...", "model": "nemotron", "tokens_used": 98 }
#   Declaring the response model lets FastAPI auto-generate correct docs.

class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question to send to the AI model",
        examples=["What is a REST API?"]
    )
    max_tokens: int = Field(
        default=400,
        ge=50,        # Nemotron needs budget for <think> tokens
        le=2048,
        description="Maximum tokens to generate. Use >=200 for Nemotron (reasoning model)"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature. Low=focused/deterministic, High=creative/varied"
    )
    system_instruction: str = Field(
        default="You are ProjectMind AI, an expert software development assistant.",
        max_length=2000,
        description="System instruction that defines the model's role and behavior"
    )


class ChatResponse(BaseModel):
    answer: str          = Field(description="The model's response text")
    model: str           = Field(description="Which model generated this answer")
    prompt_tokens: int   = Field(description="Tokens consumed by the question")
    answer_tokens: int   = Field(description="Tokens generated in the answer")
    total_tokens: int    = Field(description="Total tokens used")
    finish_reason: str   = Field(description="Why the model stopped: 'stop'=natural end, 'length'=hit max_tokens limit")


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------
# This is the core ProjectMind endpoint.
#
# FLOW:
#   1. Client sends POST /api/v1/chat with JSON body {"question": "..."}
#   2. FastAPI parses + validates the body using ChatRequest
#   3. Our function calls ask_nemotron() from the service layer
#   4. ask_nemotron() sends the HTTP request to llama-server
#   5. llama-server runs Nemotron inference and returns JSON
#   6. We extract the answer and token usage
#   7. We return a ChatResponse
#
# WHY def AND NOT async def?
#   ask_nemotron() uses requests.post() which is synchronous (blocking).
#   In FastAPI, a plain 'def' route runs in a thread pool automatically,
#   which prevents blocking the async event loop. If we used 'async def'
#   with a sync blocking call inside, we would freeze the entire server.
#
# WHY HTTPException?
#   When our service fails (server down, timeout, etc.), we catch those
#   Python exceptions and convert them into proper HTTP error responses.
#   A client expects HTTP -- not a Python stack trace.
#
#   503 Service Unavailable = llama-server is down
#   504 Gateway Timeout     = llama-server took too long
#   500 Internal Error      = unexpected failure

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a question to Nemotron",
    description="Sends a question to the locally running Nemotron model via llama-server and returns the generated answer."
)
def chat(request: ChatRequest):
    try:
        answer, usage, finish_reason = ask_nemotron(
            question=request.question,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system_instruction
        )
        return ChatResponse(
            answer=answer,
            model="nemotron",
            prompt_tokens=usage.get("prompt_tokens", 0),
            answer_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            finish_reason=finish_reason
        )

    except ConnectionError as e:
        # llama-server is not running
        raise HTTPException(
            status_code=503,
            detail=f"Nemotron service unavailable: {str(e)}"
        )
    except TimeoutError as e:
        # Model took too long
        raise HTTPException(
            status_code=504,
            detail=f"Nemotron timed out: {str(e)}"
        )
    except RuntimeError as e:
        # llama-server returned an error response
        raise HTTPException(
            status_code=500,
            detail=f"Nemotron error: {str(e)}"
        )


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------
# A health check endpoint is a standard practice in every backend service.
# It lets load balancers, monitoring tools, and developers quickly verify
# that the service is alive without triggering any real work.
#
# This endpoint checks:
#   1. Is our FastAPI app alive? (always true if we reach this code)
#   2. Is llama-server reachable? (we ping its /health endpoint)
#
# Returning status of dependencies (llama-server) makes this a "deep"
# health check vs a "shallow" one that only checks if FastAPI is alive.

@router.get(
    "/health",
    summary="Check service health",
    description="Returns the health status of the ProjectMind API and the Nemotron backend."
)
def health():
    import requests as req
    import os
    from dotenv import load_dotenv
    load_dotenv()

    nemotron_url = os.getenv("NEMOTRON_URL", "http://127.0.0.1:8081")

    try:
        r = req.get(f"{nemotron_url}/health", timeout=5)
        nemotron_status = "ok" if r.status_code == 200 else "degraded"
    except Exception:
        nemotron_status = "unreachable"

    return {
        "status": "ok",
        "services": {
            "api": "ok",
            "nemotron": nemotron_status
        }
    }
