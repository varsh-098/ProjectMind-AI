"""
backend/routers/chat.py
========================
The /chat endpoint — where HTTP requests enter ProjectMind.

THIS IS THE HTTP LAYER. It handles:
    1. Receiving POST requests
    2. Validating the request body (via Pydantic)
    3. Calling the service layer
    4. Returning a proper HTTP response (with correct status codes)

WHAT ARE PYDANTIC MODELS?
    When someone sends a POST request, the body is raw JSON bytes.
    Pydantic models define the SHAPE of the data we expect.

    ChatRequest says: "I expect a JSON object with a 'message' field
    that must be a string."

    If someone sends {"msg": 123}, FastAPI automatically returns a
    422 Unprocessable Entity error with a clear message about what's
    wrong. We don't write a single line of validation code.

    This is one of FastAPI's biggest strengths — automatic validation.

WHAT IS A ROUTER?
    A router groups related endpoints together.
    All chat-related endpoints go in this router.
    The main app includes this router with a prefix.

    This keeps the code organized as the app grows:
        routers/chat.py     → /chat endpoints
        routers/project.py  → /project endpoints (future)
        routers/agent.py    → /agent endpoints (future)

HTTP STATUS CODES USED HERE:
    200 OK                   → Everything worked
    422 Unprocessable Entity → Bad request body (automatic from Pydantic)
    503 Service Unavailable  → LLM server is down
    504 Gateway Timeout      → LLM took too long
    500 Internal Server Error → Something unexpected broke
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.llm_service import get_chat_response


# -------------------------------------------------------
# Pydantic Models — define request/response shapes
# -------------------------------------------------------

class ChatRequest(BaseModel):
    """
    What the client sends to POST /chat.

    Example:
        {"message": "What is an API?"}

    Field(...) means this field is REQUIRED — no default value.
    min_length=1 prevents empty strings.

    'description' shows up in the Swagger docs, helping anyone
    who uses the API understand what to send.
    """
    message: str = Field(
        ...,
        min_length=1,
        description="The message to send to the AI.",
        examples=["What is an API?"],
    )


class ChatResponse(BaseModel):
    """
    What POST /chat returns.

    Example:
        {"response": "An API is..."}
    """
    response: str = Field(
        ...,
        description="The AI-generated response.",
    )


class ErrorResponse(BaseModel):
    """
    Returned when something goes wrong.

    Example:
        {"detail": "Cannot connect to LLM server."}
    """
    detail: str


# -------------------------------------------------------
# Router
# -------------------------------------------------------
# prefix="/chat" means all routes in this router start with /chat.
# tags=["Chat"] groups these endpoints in the Swagger UI.
# -------------------------------------------------------
router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to ProjectMind AI",
    description=(
        "Send a message and receive an AI-generated response. "
        "Currently powered by local Nemotron via llama-server."
    ),
    responses={
        503: {"model": ErrorResponse, "description": "LLM server is not running"},
        504: {"model": ErrorResponse, "description": "LLM timed out"},
    },
)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.

    The flow:
        1. FastAPI receives the POST request
        2. Pydantic validates the body → ChatRequest
        3. We call the service layer
        4. Service calls the LLM provider (Nemotron)
        5. Nemotron provider calls llama-server
        6. llama-server runs Nemotron on your GPU
        7. Response bubbles back up through each layer
        8. We return ChatResponse as JSON

    Why async def?
        This function is a coroutine. When it hits `await`
        (inside get_chat_response), it yields control back
        to the event loop. FastAPI can handle other requests
        while waiting for the LLM. Without async, the server
        would be completely blocked during LLM inference.
    """
    try:
        response_text = await get_chat_response(request.message)
        return ChatResponse(response=response_text)

    except ConnectionError as e:
        # LLM server is not running → 503 Service Unavailable
        # This tells the client: "the server is up, but a dependency is down"
        raise HTTPException(status_code=503, detail=str(e))

    except TimeoutError as e:
        # LLM took too long → 504 Gateway Timeout
        # This tells the client: "we tried, but the upstream service was too slow"
        raise HTTPException(status_code=504, detail=str(e))

    except RuntimeError as e:
        # Unexpected LLM error → 500 Internal Server Error
        raise HTTPException(status_code=500, detail=str(e))
