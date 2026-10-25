"""
backend/main.py
Phase 5 -- FastAPI application entry point

WHAT IS THIS FILE?
    This is where the FastAPI application is created and configured.
    It is the TOP of the backend stack.

    Flow:
        uvicorn main:app        <- starts the ASGI server
              |
              v
        FastAPI app (created here)
              |
              v
        Routers registered here
              |
              v
        /api/v1/chat    <- defined in routers/chat.py
        /api/v1/health  <- defined in routers/chat.py

WHAT IS UVICORN?
    FastAPI is a web framework -- it defines routes and handles requests.
    But it cannot serve HTTP connections on its own. It needs an ASGI server.

    uvicorn is that server. It:
        - Listens on a port (e.g., 8000)
        - Accepts incoming HTTP connections
        - Hands each request to FastAPI
        - Sends FastAPI's response back to the client

    The relationship:
        uvicorn (ASGI server)
            |
            v
        FastAPI (web framework)
            |
            v
        Our routes / business logic

    This is the same pattern as nginx/gunicorn in production deployments.
    For development, uvicorn alone is sufficient.

WHAT IS ASGI?
    ASGI (Asynchronous Server Gateway Interface) is the Python standard for
    async web servers and frameworks. FastAPI is an ASGI framework.
    The older standard was WSGI (used by Flask, Django). ASGI is needed
    for async/await support and WebSockets.

WHY A SEPARATE main.py AND routers/?
    main.py should only:
        - Create the app
        - Register configuration/middleware
        - Include routers

    The actual endpoint logic lives in routers/.
    This separation means main.py stays small as the project grows.
    Adding a new feature = adding a new router and one include_router() line.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from backend.routers import chat

# Load environment variables from .env as early as possible,
# before any other module reads os.getenv().
load_dotenv()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
# The lifespan context manager handles startup and shutdown events.
# Code before 'yield' runs when the server starts.
# Code after 'yield' runs when the server shuts down.
#
# Right now we just log startup. Later this is where we will:
#   - Initialize the vector database connection (RAG phase)
#   - Load project memory (Memory phase)
#   - Verify llama-server is reachable
#
# This replaces the older @app.on_event("startup") pattern which is
# deprecated in FastAPI 0.95+.

@asynccontextmanager
async def lifespan(app: FastAPI):
    # -- STARTUP --
    print()
    print("=" * 55)
    print("  ProjectMind AI -- Backend starting")
    print("  Phase 5: FastAPI + Nemotron")
    print("=" * 55)
    print("  Swagger UI:  http://127.0.0.1:8000/docs")
    print("  Health:      http://127.0.0.1:8000/api/v1/health")
    print("  Chat:        POST http://127.0.0.1:8000/api/v1/chat")
    print("=" * 55)
    print()

    yield  # <-- The app runs here. Everything above is startup.

    # -- SHUTDOWN --
    print()
    print("ProjectMind API shutting down.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
# FastAPI() creates the application instance. The arguments here populate
# the auto-generated OpenAPI (Swagger) documentation at /docs.

app = FastAPI(
    title="ProjectMind AI",
    description=(
        "A project-aware AI development workspace. "
        "Phase 5: FastAPI + Nemotron local LLM backend."
    ),
    version="0.1.0",
    lifespan=lifespan
)


# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
# CORS (Cross-Origin Resource Sharing) is a browser security rule.
# When a frontend (e.g., running on port 3000) sends a request to our API
# (running on port 8000), the browser blocks it unless the API explicitly
# allows it via CORS headers.
#
# allow_origins=["*"] means ANY origin can call this API.
# This is fine for local development.
# In production, restrict this to your actual frontend domain.
#
# Note: This CORS config is for OUR FastAPI server. The llama-server
# CORS warning you saw earlier was about THAT server, which we call
# internally from Python -- not from a browser. So it doesn't affect us.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------
# include_router() attaches all the routes defined in chat.py to this app.
# The prefix="/api/v1" prepends that string to every route in the router.
# So router.post("/chat") becomes POST /api/v1/chat on the full app.
#
# WHY /api/v1/?
#   The /api/ prefix distinguishes API routes from any future static files
#   or web pages. The /v1/ prefix allows adding /v2/ later without breaking
#   existing clients. This is standard REST API versioning.

app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
