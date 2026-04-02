from __future__ import annotations

import site
import sys
from pathlib import Path


def _safe_add(path: Path) -> None:
    try:
        if path.is_dir() and str(path) not in sys.path:
            sys.path.insert(0, str(path))
    except PermissionError:
        return


ROOT = Path(__file__).resolve().parent
_safe_add(ROOT / "vendorpkgs")

try:
    USER_SITE = Path(site.getusersitepackages())
except Exception:
    USER_SITE = None

if USER_SITE is not None:
    _safe_add(USER_SITE)
