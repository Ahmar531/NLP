# RAG Agent

A simple retrieval-augmented generation project scaffold.

## Structure

- `app/` contains the FastAPI app, agent logic, RAG components, memory layer, and routes.
- `uploads/` stores uploaded PDFs.
- `qdrant_data/` stores local Qdrant data.

## Quick start

1. Create a virtual environment.
2. Install dependencies:
   `pip install -r requirements.txt`
3. Start the API:
   `uvicorn app.main:app --reload`

## Environment

Create a `.env` file with your local configuration values.
