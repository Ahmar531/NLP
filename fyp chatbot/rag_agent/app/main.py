from fastapi import FastAPI

from app.api.pdf import router as pdf_router
from app.api.chat import router as chat_router


app = FastAPI(
    title="RAG Agent API",
    description="PDF RAG Agent using FastAPI, LangChain, Groq and Qdrant",
    version="1.0.0",
)


app.include_router(
    pdf_router
)

app.include_router(
    chat_router
)


@app.get("/")
async def root():

    return {
        "message": "RAG Agent API is running."
    }


@app.get("/health")
async def health():

    return {
        "status": "healthy"
    }