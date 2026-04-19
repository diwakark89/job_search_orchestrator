from __future__ import annotations

"""API authentication dependency wiring.

Provides FastAPI dependencies for route-level authentication.  The API key is
read from the ``API_KEY`` environment variable.  If the variable is not set,
the security dependency is **disabled** (all requests pass through) — this
allows local development without credentials while making the intention explicit.

Usage in a route::

    from api.security import require_api_key

    @router.post("/my-route", dependencies=[Depends(require_api_key)])
    def my_route() -> ...:
        ...

Usage at router registration (applies to all routes on a router)::

    app.include_router(pipeline_router, dependencies=[Depends(require_api_key)])

Security note (OWASP A01 / A07):
  - Auth is enforced via a shared secret (``X-API-Key`` header).  The key is
    loaded from the environment; it is never logged or embedded in source code.
  - An absent or wrong key returns HTTP 401, not 403, to avoid leaking whether
    the resource exists (deny-by-default principle).
  - Rate limiting and account lockout are the responsibility of the reverse
    proxy / API gateway layer in front of this service.
"""

import os
import secrets

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_ENV_KEY = "API_KEY"


def _get_configured_key() -> str | None:
    """Return the expected API key from environment, or ``None`` if unset."""
    return os.environ.get(_ENV_KEY)


def require_api_key(api_key: str | None = Security(_API_KEY_HEADER)) -> None:
    """FastAPI dependency that enforces API key authentication.

    If ``API_KEY`` environment variable is not configured the dependency is
    a no-op (passes all requests).  This allows unrestricted local development
    while making the auth intent visible in code.

    Args:
        api_key: Value of the ``X-API-Key`` request header, injected by FastAPI.

    Raises:
        HTTPException 401: When ``API_KEY`` is configured and the header is
            missing or does not match (using constant-time comparison to prevent
            timing attacks).
    """
    expected = _get_configured_key()
    if expected is None:
        # Auth disabled — development / unconfigured mode.
        return

    if api_key is None or not secrets.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
