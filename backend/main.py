"""
Main FastAPI application entry point.
"""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from backend.core.config import settings
from backend.core.database import init_db, close_db
from backend.api.routes import router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    logger.info("Starting Reverse Engineering AI Platform", version=settings.app_version)

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))

    # Ensure workspace directory exists
    import os
    os.makedirs(settings.workspace_dir, exist_ok=True)

    yield  # Application runs here

    # Cleanup
    await close_db()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Agentic AI-Based Automated Software Reverse Engineering Platform",
    description="""
    Upload a software repository and automatically obtain an evidence-backed
    System Reconstruction Report using:
    - Deterministic program analysis (AST, call graph, dependency graph, data flow)
    - Program Knowledge Graph
    - Hybrid RAG retrieval
    - LangGraph multi-agent orchestration
    - Evidence-based verification
    
    No hallucination: every AI claim is linked to source evidence.
    """,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes under /api/v1
app.include_router(router, prefix="/api/v1")


from fastapi.responses import RedirectResponse

@app.get("/health", tags=["System"])
async def root_health():
    from backend.core.database import check_db_health
    from backend.retrieval.service import retrieval_service
    db_res = await check_db_health()
    llm_configured = bool(settings.openai_api_key or settings.google_api_key or settings.anthropic_api_key)
    is_healthy = db_res.get("status") == "healthy"
    return {
        "status": "healthy" if is_healthy else "degraded",
        "backend": "healthy",
        "database": db_res.get("status", "unavailable"),
        "database_dialect": db_res.get("dialect", "unknown"),
        "fallback_active": db_res.get("fallback_active", False),
        "llm": "configured" if llm_configured else "not_configured",
        "retrieval": "ready" if retrieval_service else "unavailable",
        "graph": "ready",
        "version": settings.app_version,
    }


@app.get("/docs", include_in_schema=False)
async def redirect_docs():
    return RedirectResponse(url="/api/docs")


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/api/docs",
        "status": "running",
    }
