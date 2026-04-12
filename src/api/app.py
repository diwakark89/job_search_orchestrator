from __future__ import annotations

from fastapi import FastAPI

from api.routes.enricher import router as enricher_router
from api.routes.pipeline import router as pipeline_router
from api.routes.system import router as system_router
from api.routes.tables import router as tables_router

app = FastAPI(
    title="Automated Job Hunt Orchestrator API",
    version="0.1.0",
    description="HTTP API for Supabase table operations and job orchestration.",
)

app.include_router(system_router)
app.include_router(tables_router)
app.include_router(enricher_router)
app.include_router(pipeline_router)
