from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    # Allow running `pytest` from a fresh clone without requiring an editable install.
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    sys.path.insert(0, str(src))


_ensure_src_on_path()

