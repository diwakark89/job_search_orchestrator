"""Architectural guard: only src/scraping/adapters/ may import from the vendored
jobspy_mcp_server package.

This protects the ports-and-adapters boundary established in
plan/architecture-merge-boundaries-1.md and the modularization plan that
followed it. If this test fails, a new module is leaking the vendored
dependency into the orchestrator surface — move that import into an adapter
shim under src/scraping/adapters/ and have the leaking module depend on the
orchestrator-owned wrapper instead (e.g., scraping.output, scraping.models,
scraping.preferences).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"

# Paths permitted to import from jobspy_mcp_server.* directly.
ALLOWED_PREFIXES = (
    SRC_ROOT / "jobspy_mcp_server",  # the vendored package itself
    SRC_ROOT / "scraping" / "adapters",  # adapter-local shims
)

# Compatibility shim that re-exports from mcp_interface (and may transitively
# touch jobspy_mcp_server only through that import). The shim itself does not
# import jobspy_mcp_server directly.
IMPORT_RE = re.compile(r"^\s*(?:from\s+jobspy_mcp_server|import\s+jobspy_mcp_server)", re.MULTILINE)


def _iter_python_files() -> list[Path]:
    return [p for p in SRC_ROOT.rglob("*.py") if p.is_file()]


def _is_allowed(path: Path) -> bool:
    return any(str(path).startswith(str(prefix)) for prefix in ALLOWED_PREFIXES)


def test_no_vendored_imports_outside_adapter_boundary() -> None:
    offenders: list[str] = []
    for path in _iter_python_files():
        if _is_allowed(path):
            continue
        text = path.read_text(encoding="utf-8")
        if IMPORT_RE.search(text):
            offenders.append(str(path.relative_to(SRC_ROOT)))
    assert not offenders, (
        "The following modules import from jobspy_mcp_server.* outside the "
        "adapter boundary. Move the import into src/scraping/adapters/ and "
        "depend on the orchestrator wrapper instead:\n  - "
        + "\n  - ".join(offenders)
    )


@pytest.mark.parametrize(
    "module_path",
    [
        "scraping/output.py",
        "scraping/preferences.py",
        "scraping/models.py",
    ],
)
def test_orchestrator_wrappers_do_not_leak_vendored_imports(module_path: str) -> None:
    text = (SRC_ROOT / module_path).read_text(encoding="utf-8")
    assert not IMPORT_RE.search(text), (
        f"{module_path} must delegate to scraping.adapters.* and not import "
        "from jobspy_mcp_server directly."
    )
