"""
backend/main.py
================
FastAPI application entry point — where everything comes together.

WHAT IS FASTAPI?
    FastAPI is a web framework. It listens for HTTP requests and routes
    them to your Python functions. It is NOT the LLM. It is NOT the
    database. It is the "traffic controller" that sits between the
    client (browser/curl) and your application logic.

WHAT IS UVICORN?
    Uvicorn is the ASGI server that actually runs FastAPI.
    Think of it this way:
        - FastAPI = your application (the code that decides what to do)
        - Uvicorn = the server (the thing that listens on a port and
                    passes incoming HTTP requests to your application)

    You run it with:
        uvicorn backend.main:app --reload

    "backend.main" = the Python module path to this file
    "app" = the name of the FastAPI instance in this file
    "--reload" = restart automatically when you save code changes

WHAT IS --reload?
    During development, --reload watches your files. When you save a change,
    uvicorn automatically restarts the server with the new code.
    NEVER use --reload in production — it's a development convenience.

WHAT HAPPENS WHEN THE SERVER STARTS?
    1. Uvicorn starts listening on http://localhost:8000
    2. FastAPI loads this file and creates the `app` object
    3. The router from chat.py is registered (adds the /chat endpoint)
    4. Swagger docs are auto-generated at /docs
    5. Now any POST to http://localhost:8000/chat goes through:
       chat.py → llm_service.py → factory.py → nemotron.py → llama-server

SWAGGER / OPENAPI:
    FastAPI automatically generates interactive API docs at /docs.
    You can test endpoints directly from your browser — no curl needed.
    This is one of FastAPI's killer features.
"""

from fastapi import FastAPI
from backend.routers import chat, project, memory

# -------------------------------------------------------
# Create the FastAPI application
# -------------------------------------------------------
# These metadata fields populate the Swagger UI at /docs:
#   title → shown as the page heading
#   description → shown below the heading
#   version → shown next to the title
# -------------------------------------------------------
app = FastAPI(
    title="ProjectMind AI",
    description=(
        "A project-aware AI development workspace. "
        "Currently powered by local Nemotron via llama-server."
    ),
    version="0.1.0",
)


# -------------------------------------------------------
# Register routers
# -------------------------------------------------------
# include_router() adds all the endpoints from chat.router
# to the main app. The prefix="/chat" from the router means
# the endpoint becomes POST /chat.
#
# As we build more features, we'll add more routers:
#   app.include_router(project.router)   → /project endpoints
#   app.include_router(agent.router)     → /agent endpoints
# -------------------------------------------------------
app.include_router(chat.router)
app.include_router(project.router)
app.include_router(memory.router)


# -------------------------------------------------------
# Health check endpoint
# -------------------------------------------------------
# A simple GET / that returns basic info about the server.
# Used to verify the server is running without calling the LLM.
#
# Example:
#   curl http://localhost:8000/
#   → {"status": "running", "project": "ProjectMind AI", "version": "0.1.0"}
# -------------------------------------------------------
@app.get(
    "/",
    summary="Health check",
    description="Check if the ProjectMind AI server is running.",
)
async def health_check():
    return {
        "status": "running",
        "project": "ProjectMind AI",
        "version": "0.1.0",
    }
