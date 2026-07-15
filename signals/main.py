"""
signals/main.py
---------------
Standalone entry point for the signals package.

Run this directly to test your module independently,
without needing any other teammate's code to be ready.

Usage:
    uvicorn signals.main:app --reload --port 8002
"""

from fastapi import FastAPI
from signals.router import router

app = FastAPI(
    title="Signals — Adverse Media Agent",
    description=(
        "Autonomous adverse news monitoring agent for KYC compliance. "
        "Watches a list of corporate entities, fetches news via NewsAPI, "
        "and uses Claude (LLM) to determine if the news is genuinely adverse."
    ),
    version="1.0.0",
)

app.include_router(router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "signals"}
