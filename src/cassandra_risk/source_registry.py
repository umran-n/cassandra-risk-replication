from __future__ import annotations

import os
from pathlib import Path

from .config import load_json


def load_source_registry(root: Path) -> dict:
    return load_json(root / "config" / "source_registry.json")


def source_settings(registry: dict, source_name: str) -> dict:
    return dict(registry.get("sources", {}).get(source_name, {}))


def source_priority(registry: dict, source_name: str) -> int:
    settings = source_settings(registry, source_name)
    return int(settings.get("priority", 999))


def source_has_credentials(settings: dict) -> bool:
    token_env_var = settings.get("token_env_var")
    if not token_env_var:
        return True
    return bool(os.environ.get(str(token_env_var), "").strip())


def theme_policy(registry: dict, theme: str | None) -> dict:
    theme_name = str(theme or "")
    return dict(registry.get("theme_policies", {}).get(theme_name, {}))
