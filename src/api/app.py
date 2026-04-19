from __future__ import annotations

from fastapi import Depends, FastAPI

from api.routes.enricher import router as enricher_router
from api.routes.pipeline import router as pipeline_router
from api.routes.system import router as system_router
from api.routes.tables import router as tables_router
from api.security import require_api_key

app = FastAPI(
    title="Automated Job Hunt Orchestrator API",
    version="0.1.0",
    description="HTTP API for Supabase table operations and job orchestration.",
)

# Unauthenticated: health and table discovery are public read-only endpoints.
app.include_router(system_router)

# Authenticated: all write / mutation surfaces require a valid API key.
_auth = [Depends(require_api_key)]
app.include_router(tables_router, dependencies=_auth)
app.include_router(enricher_router, dependencies=_auth)
app.include_router(pipeline_router, dependencies=_auth)

