"""
models.py  —  Data Shape Definitions
═══════════════════════════════════════════════════════════════

Why this file exists:
  FastAPI uses Pydantic models to describe the exact shape of
  data that goes in and out of each API endpoint.

  By defining these shapes here (rather than in app.py), we:
    - Keep app.py focused on logic, not data definitions.
    - Get automatic validation: if React sends wrong data,
      FastAPI returns a clear error message automatically.
    - Get automatic API documentation in /docs.

What Pydantic is:
  Pydantic is a Python library that validates data using type hints.
  When FastAPI receives a JSON body, Pydantic checks that it matches
  the model and raises a clear error if it does not.
"""

# BaseModel is the base class for all Pydantic models
from pydantic import BaseModel


class ChatRequest(BaseModel):
    """
    Describes the JSON body that React sends to POST /chat.

    When the user types "Hello" and clicks Send, React sends:
        { "message": "Hello" }

    Pydantic will check that "message" is present and is a string.
    If it is missing or has the wrong type, FastAPI returns a 422 error.
    """

    # "message" is the text the user typed in the chat input
    message: str


class ChatResponse(BaseModel):
    """
    Describes the JSON body that FastAPI sends back to React.

    After Ollama generates a reply, FastAPI returns:
        { "response": "Hello! How can I help you?" }

    React reads response.data.response to get the AI's text.
    """

    # "response" is the AI's reply text
    response: str
