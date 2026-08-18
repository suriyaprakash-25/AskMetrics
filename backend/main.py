from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .service import AskService

app = FastAPI(title="AskMetrics API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/schema")
def schema():
    # This endpoint is intentionally small; frontend need not expose it.
    from .config import settings
    from .db import connect_readonly
    from .schema_inspector import get_schema_context
    conn = connect_readonly(settings.database_path)
    try:
        return {"schema": get_schema_context(conn)}
    finally:
        conn.close()

@app.post("/ask")
def ask(request: AskRequest):
    return AskService().ask(request.question)
