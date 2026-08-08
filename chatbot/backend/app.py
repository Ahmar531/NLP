"""
app.py  —  The FastAPI Backend
═══════════════════════════════════════════════════════════════

Why this file exists:
  This is the main backend file.
  It creates the FastAPI web server, defines the API routes,
  and connects the chat frontend to the local Ollama AI model.

What it is responsible for:
  1. Starting the FastAPI application.
  2. Allowing the React frontend to call it (CORS setup).
  3. Receiving user messages from the frontend.
  4. Forwarding those messages to the local Ollama server.
  5. Returning the AI reply back to the frontend as JSON.

How it connects to the rest of the project:
  - React calls POST /chat with a JSON body: { "message": "Hello" }
  - This file receives that request, sends it to Ollama, and replies:
      { "response": "Hello! How can I help you?" }
  - models.py defines the shape of those JSON objects.

To start this server, run:
  uvicorn app:app --reload

Then open http://127.0.0.1:8000/docs to see the interactive API docs.
"""

# ── Standard Library Imports ───────────────────────────────────────────────
# "os" gives us access to environment variables and the operating system
from os import getenv

# ── Third-Party Imports ────────────────────────────────────────────────────
# "requests" is a simple library for making HTTP calls to other servers
# We use it to talk to the local Ollama API
import requests

# "load_dotenv" reads the .env file and puts its values into environment
# variables so we can access them with getenv()
from dotenv import load_dotenv

# "FastAPI" is the web framework — it handles routing, validation, and docs
# "HTTPException" lets us return error responses with specific status codes
from fastapi import FastAPI, HTTPException

# "CORSMiddleware" allows the React frontend (on a different port) to call
# this backend. Without CORS, the browser would block the request.
from fastapi.middleware.cors import CORSMiddleware

# Import the Pydantic models that define the shape of our JSON data
from backend.models import ChatRequest, ChatResponse


# ── Load Environment Variables ─────────────────────────────────────────────
# This reads the .env file so we can use the values defined there.
# It must be called before getenv() so the values are available.
load_dotenv()


# ── Configuration ──────────────────────────────────────────────────────────
# All settings come from the .env file so they are easy to change.
# If a variable is not in .env, the second argument is the default value.

# The name of the Ollama model to use.
# Change this in .env to switch models (e.g. gemma3:latest, qwen2.5, mistral)
MODEL_NAME = getenv("MODEL_NAME", "llama3.2:1b")

# The URL where the local Ollama server is running.
# Ollama's default is http://localhost:11434 — you rarely need to change this.
OLLAMA_HOST = getenv("OLLAMA_HOST", "http://localhost:11434")

# The URL of the React development server.
# This is needed so CORS allows the browser to call our backend.
FRONTEND_ORIGIN = getenv("FRONTEND_ORIGIN", "http://localhost:5173")

# Split the origin string in case multiple origins are listed separated by commas
ALLOWED_ORIGINS = [o.strip() for o in FRONTEND_ORIGIN.split(",") if o.strip()]


# ── Create the FastAPI App ─────────────────────────────────────────────────
# "app" is the main FastAPI instance.
# All routes (endpoints) are registered on this object.
app = FastAPI(
    title="Beginner AI Chatbot",
    description="A simple chatbot backend that connects React to Ollama.",
    version="1.0.0",
)


# ── Enable CORS ────────────────────────────────────────────────────────────
# CORS (Cross-Origin Resource Sharing) is a browser security feature.
# By default, browsers block requests from one origin (e.g. localhost:5173)
# to a different origin (e.g. localhost:8000).
# Adding this middleware tells the browser: "it is safe to allow this."
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # Only allow our React app
    allow_credentials=True,
    allow_methods=["*"],             # Allow GET, POST, etc.
    allow_headers=["*"],             # Allow all HTTP headers
)


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTION
# ═══════════════════════════════════════════════════════════════

def get_ollama_reply(user_message: str) -> str:
    """
    Send one user message to the local Ollama server and return the reply.

    What this function does:
      1. Builds a JSON payload that Ollama's /api/chat endpoint understands.
      2. Sends the payload using an HTTP POST request.
      3. Reads and returns the AI's text response.

    When it is called:
      It is called by the /chat endpoint every time the user sends a message.

    What it returns:
      A string containing the AI's reply text.

    What can go wrong:
      - requests.RequestException : Ollama is not running or unreachable.
      - ValueError                 : Ollama returned an unexpected JSON format.
    """

    # This is the system prompt — it sets the AI's personality and style.
    # You can change this to make the AI behave differently.
    # For example: "You are a pirate. Always speak like a pirate."
    system_prompt = (
        "You are a helpful, beginner-friendly AI assistant. "
        "Give clear, concise, and accurate answers. "
        "If you are unsure, say so honestly."
    )

    # Build the request body for Ollama's /api/chat endpoint.
    # "model"    — which model to use (set in .env)
    # "messages" — the conversation history as a list of role/content pairs
    # "stream"   — False means we wait for the full reply before returning
    payload = {
        "model": MODEL_NAME,
        "messages": [
            # The system message sets the AI's behaviour
            {"role": "system",    "content": system_prompt},
            # The user message is what the human typed
            {"role": "user",      "content": user_message},
        ],
        # Keep mmap enabled so Ollama does not pass an unsupported
        # --load-mode none flag to llama-server on this setup.
        "options": {
            "use_mmap": True,
        },
        "stream": False,
    }

    # Send the payload to Ollama.
    # timeout=120 means: give up if Ollama takes longer than 2 minutes.
    # This is important for large models that are slow to generate a response.
    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json=payload,
        timeout=120,
    )

    # If Ollama returned a 4xx or 5xx status code, raise an exception.
    # This will be caught by the calling /chat endpoint.
    response.raise_for_status()

    # Parse the JSON body from Ollama's response
    data = response.json()

    # Extract the AI's reply text from the nested JSON structure.
    # Ollama's response looks like:
    #   { "message": { "role": "assistant", "content": "Hello!" } }
    try:
        ai_reply = data["message"]["content"]
    except (KeyError, TypeError) as exc:
        # If the structure is unexpected, raise a clear error
        raise ValueError(
            f"Ollama returned an unexpected response format: {data}"
        ) from exc

    return ai_reply


# ═══════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/")
def read_root():
    """
    GET /  —  A simple health check endpoint.

    Why this endpoint exists:
      It lets you quickly verify that the backend server is running.
      Open http://127.0.0.1:8000 in your browser and you should see
      a short JSON response instead of an error.

    What it returns:
      A JSON object confirming the server is alive.
    """
    return {
        "status": "ok",
        "message": "Chatbot backend is running.",
        "model": MODEL_NAME,
        "docs": "http://127.0.0.1:8000/docs",
    }


@app.get("/health")
def health_check():
    """
    GET /health  —  Check if Ollama is reachable.

    Why this endpoint exists:
      Before sending a chat message, you can call this endpoint
      to verify that both FastAPI and Ollama are running correctly.

    What it returns:
      JSON with the status of both the backend and Ollama.
    """
    # Try to reach Ollama's own health endpoint
    try:
        ollama_response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        ollama_ok = ollama_response.status_code == 200
        available_models = [m["name"] for m in ollama_response.json().get("models", [])]
    except requests.RequestException:
        ollama_ok = False
        available_models = []

    return {
        "backend": "ok",
        "ollama": "ok" if ollama_ok else "not reachable — run: ollama serve",
        "configured_model": MODEL_NAME,
        "available_models": available_models,
    }


# This endpoint receives the user's message from React.
# React sends JSON to POST /chat using Axios.
@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """
    POST /chat  —  The main chat endpoint.

    Why this endpoint exists:
      This is the only endpoint the React frontend needs.
      It receives the user's text and returns the AI's reply.

    Request body (sent by React):
      { "message": "Hello" }

    Response body (returned to React):
      { "response": "Hello! How can I help you?" }

    What it does step by step:
      1. Receives the ChatRequest from React.
      2. Validates that the message is not empty.
      3. Calls get_ollama_reply() to talk to Ollama.
      4. Returns the AI's reply as a ChatResponse.

    What it returns:
      A ChatResponse object with the AI's reply text.
    """

    # Store the user's message after stripping leading/trailing whitespace.
    # strip() removes spaces and newlines that the user might have added by accident.
    user_message = request.message.strip()

    # Reject blank messages early.
    # This keeps the backend simple — we never send empty strings to Ollama.
    if not user_message:
        # HTTPException sends an error back to React with a clear message
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty.",
        )

    try:
        # Send the message to Ollama and wait for the reply.
        # This is the main "magic" step of the whole chatbot.
        ai_response = get_ollama_reply(user_message)

    except requests.ConnectionError:
        # This happens when Ollama is not running at all.
        raise HTTPException(
            status_code=502,
            detail=(
                f"Could not connect to Ollama at {OLLAMA_HOST}. "
                "Please start Ollama by running: ollama serve"
            ),
        )

    except requests.Timeout:
        # This happens when Ollama is running but takes too long to reply.
        raise HTTPException(
            status_code=504,
            detail=(
                "Ollama took too long to respond. "
                "The model may be loading for the first time. "
                "Please try again in a moment."
            ),
        )

    except requests.RequestException as exc:
        # This catches any other HTTP-related error from Ollama.
        raise HTTPException(
            status_code=502,
            detail=f"Ollama error: {exc}",
        ) from exc

    except ValueError as exc:
        # This catches the case where Ollama replies with an unexpected format.
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Return the AI's reply to the React frontend.
    # FastAPI automatically converts this to JSON.
    return ChatResponse(response=ai_response)
