from fastapi import FastAPI

from ai_companion.interfaces.whatsapp.whatsapp_response import whatsapp_router

app = FastAPI(
    title="WhatsApp AI Companion",
    description="WhatsApp webhook — 2 routes only: verify + receive messages",
    version="1.0.0",
    docs_url="/docs",
)

app.include_router(whatsapp_router)
