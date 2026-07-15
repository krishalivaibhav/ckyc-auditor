"""
signals/main.py — Standalone entry point for the signals package.

Usage:
    python run.py           (from TechMKYC/ root — recommended)
    uvicorn signals.main:app --reload --port 8002  (from TechMKYC/ root)
"""

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .router import router

app = FastAPI(
    title       = "Signals — Adverse Media & Sanctions Monitor",
    description = (
        "Autonomous adverse media monitoring agent for Continuous KYC. "
        "Fetches news via NewsAPI, applies two-stage AI analysis "
        "(Entity Resolution + Adverse Triage via Groq/Llama), "
        "deduplicates, and emits structured risk signals with a full audit trail."
    ),
    version = "2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

app.include_router(router)
