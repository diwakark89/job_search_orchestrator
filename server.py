from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))

from api.app import app

__all__ = ["app"]
