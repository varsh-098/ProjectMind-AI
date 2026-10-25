"""
backend/services/nemotron.py
Phase 4 -- Python client for llama-server / Nemotron

ARCHITECTURE AT THIS PHASE:
    This script (Python)
        |
        | requests.post(...)   <-- standard Python HTTP library
        v
    http://127.0.0.1:8081     <-- the port llama-server is listening on
        |
        v
    llama-server              <-- the HTTP wrapper around Nemotron
        |
        v
    Nemotron (GGUF in VRAM)   <-- the actual language model
        |
        v
    JSON response             <-- llama-server sends this back
        |
        v
    Python parses + prints    <-- we extract choices[0].message.content

PURPOSE:
    This is NOT yet the FastAPI layer. This is a standalone script that
    proves Python can talk to llama-server before we add a web framework.
    We isolate each layer so if something breaks, we know exactly where.

WHY 'requests' AND NOT SOMETHING ELSE?
    'requests' is the most widely used Python HTTP library. It handles
    connection pooling, encoding, and JSON serialization cleanly. In Python
    3.11+ there is also 'httpx' (supports async) but we use requests here
    because it is synchronous and simpler to understand at this stage.
"""

import os        # Built into Python. Used to read environment variables.
import requests  # The HTTP client library. Does not come built into Python.
import json      # Built into Python. Used to pretty-print the raw response.
import sys       # Built into Python. Used to exit with an error code.
from dotenv import load_dotenv  # Reads key=value pairs from .env into os.environ

# Load .env file from the project root (two directories up from this file).
# load_dotenv() is a no-op if .env doesn't exist -- it never crashes.
# In production (e.g., Docker, cloud), env vars are set by the platform
# directly and .env is not needed. load_dotenv() handles both cases.
load_dotenv()

# Fix Windows terminal encoding. Windows defaults to cp1252 which cannot
# represent many Unicode characters that LLMs commonly output (smart quotes,
# em-dashes, etc.). This makes stdout always use UTF-8 regardless of the
# terminal's default. FastAPI/uvicorn handles this automatically in Phase 5.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# We read NEMOTRON_URL from the .env file (loaded above) using os.getenv().
# The second argument to os.getenv() is the fallback value used when the
# variable is not set -- useful for running without a .env file.
#
# WHY ENVIRONMENT VARIABLES?
#   Hardcoding URLs makes changing the port require editing source code.
#   Env vars make configuration separate from code. This is "12-factor app"
#   principle #3: store config in the environment. When we later add API keys
#   (Groq, KIE), they MUST come from env vars -- never from source code.

LLAMA_SERVER_URL = os.getenv("NEMOTRON_URL", "http://127.0.0.1:8081")
CHAT_ENDPOINT    = f"{LLAMA_SERVER_URL}/v1/chat/completions"

# Timeout in seconds. If llama-server does not respond within this time,
# requests will raise a Timeout exception. Without a timeout, your program
# would hang forever if the server is slow or unreachable.
TIMEOUT_SECONDS = 120


# ---------------------------------------------------------------------------
# ask_nemotron()
# ---------------------------------------------------------------------------
# This is the core function. It takes a plain string question and returns
# the model's answer as a plain string.
#
# The function does three things:
#   1. Builds the request body (Python dict -> JSON)
#   2. Sends the HTTP POST request to llama-server
#   3. Parses the JSON response and returns the answer text
#
# WHAT IS THE REQUEST BODY STRUCTURE?
#   llama-server uses the OpenAI Chat Completions format:
#
#   {
#       "model": "...",         -- model name (llama-server ignores this value
#                                  but we include it for API compatibility)
#       "messages": [           -- list of conversation turns
#           {
#               "role": "user",
#               "content": "your question here"
#           }
#       ],
#       "max_tokens": 200       -- maximum tokens to generate in the response
#   }
#
# WHY A LIST OF MESSAGES AND NOT JUST A STRING?
#   Chat models are designed for multi-turn conversations. Even for a single
#   question, the API expects the "conversation so far" as a list. Later,
#   when we add memory/history, we extend this list with previous turns.
#
# ---------------------------------------------------------------------------

def ask_nemotron(question: str, max_tokens: int = 400,
                 temperature: float = 0.7, system: str = None):
    """
    Send a question to Nemotron via llama-server and return the answer.

    Args:
        question:    The user's question as a plain string.
        max_tokens:  Maximum tokens to generate. Default 400 (Nemotron is a
                     reasoning model -- it needs budget for <think> tokens).
        temperature: Sampling temperature. 0.0=deterministic, 1.0=creative.
                     Default 0.7 for balanced output.
        system:      Optional system instruction. Defines the model's role.
                     If None, no system message is sent.

    Returns:
        Tuple of (answer: str, usage: dict, finish_reason: str)
        finish_reason is 'stop' (natural end) or 'length' (hit max_tokens).
    """

    # Build the message list.
    # If a system instruction was provided, it goes FIRST as role="system".
    # The system message persists across the whole conversation and defines
    # the model's role, persona, and constraints.
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": question})

    payload = {
        "model": "nemotron",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature   # Now controllable per-request
    }

    try:
        # requests.post() sends an HTTP POST request.
        #
        # Arguments:
        #   url=          -- where to send the request
        #   json=         -- automatically serializes the dict to JSON and
        #                    sets Content-Type: application/json header
        #   timeout=      -- seconds before raising requests.Timeout
        #
        # The function blocks (waits) until the server responds or times out.
        # This is synchronous. In Phase 5 (FastAPI), we will use async, but
        # synchronous is easier to understand first.

        response = requests.post(
            url=CHAT_ENDPOINT,
            json=payload,
            timeout=TIMEOUT_SECONDS
        )

        # raise_for_status() checks the HTTP status code.
        # If the server returns 4xx or 5xx, it raises requests.HTTPError.
        # If the server returns 200 OK, nothing happens and we continue.
        # Without this, a 500 error would silently return a response object
        # and we might try to parse an error page as if it were valid JSON.
        response.raise_for_status()

        # Parse the JSON body of the response.
        # The response looks like:
        #
        # {
        #   "id": "...",
        #   "choices": [
        #     {
        #       "message": {
        #         "role": "assistant",
        #         "content": "the model's answer here"
        #       },
        #       "finish_reason": "stop"   or "length" if max_tokens was hit
        #     }
        #   ],
        #   "usage": {
        #     "prompt_tokens": 28,
        #     "completion_tokens": 45,
        #     "total_tokens": 73
        #   }
        # }

        data = response.json()

        answer       = data["choices"][0]["message"]["content"]
        finish_reason = data["choices"][0].get("finish_reason", "unknown")
        usage        = data.get("usage", {})

        return answer, usage, finish_reason

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------
    # Each except block catches a specific failure mode. This matters
    # because the fix for each failure is different:
    #
    #   ConnectionError -> llama-server is not running, start it
    #   Timeout         -> model is too slow, increase timeout or reduce
    #                      max_tokens
    #   HTTPError       -> server returned an error code (4xx/5xx)
    # ------------------------------------------------------------------

    except requests.exceptions.ConnectionError:
        # This happens when nothing is listening on 127.0.0.1:8081.
        # The connection was refused at the TCP level before any HTTP happened.
        raise ConnectionError(
            "Cannot reach llama-server at http://127.0.0.1:8081\n"
            "Make sure llama-server.exe is running in another terminal."
        )

    except requests.exceptions.Timeout:
        raise TimeoutError(
            f"llama-server did not respond within {TIMEOUT_SECONDS} seconds.\n"
            "The model may be overloaded. Try reducing max_tokens."
        )

    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"llama-server returned an HTTP error: {e}\n"
            f"Response body: {response.text}"
        )


# ---------------------------------------------------------------------------
# Main block
# ---------------------------------------------------------------------------
# This only runs when you execute this file directly:
#   python backend/services/nemotron.py
#
# It will NOT run when this file is imported as a module by FastAPI.
# The `if __name__ == "__main__"` guard is the standard Python way to write
# code that is only for standalone execution/testing.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * 50)
    print("  ProjectMind -- Phase 4: Python Client")
    print("=" * 50)
    print()

    # Hardcoded question for the standalone test.
    # In Phase 5, this will come from the HTTP request body sent to FastAPI.
    question = "Explain what a REST API is in two sentences."

    print(f"  Question: {question}")
    print(f"  Sending to Nemotron... (may take 10-30 seconds)")
    print()

    try:
        answer, usage = ask_nemotron(question, max_tokens=200)

        print("  --- Nemotron says ---")
        print(f"  {answer}")
        print("  ---------------------")
        print()
        print("  Token usage:")
        print(f"    Prompt tokens:     {usage.get('prompt_tokens', 'N/A')}")
        print(f"    Completion tokens: {usage.get('completion_tokens', 'N/A')}")
        print(f"    Total tokens:      {usage.get('total_tokens', 'N/A')}")
        print()
        print("=" * 50)
        print("  Phase 4 COMPLETE -- Python client works!")
        print("  Next step: Phase 5 -- FastAPI backend")
        print("=" * 50)

    except (ConnectionError, TimeoutError, RuntimeError) as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print()
