from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"


def load_config(path: Path | None = None) -> dict:
    with open(path or ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def model_key(cfg: dict, model: str, storage: int) -> Optional[str]:
    for m in cfg["models"]:
        if m["model"].lower() == model.lower() and int(m["storage"]) == int(storage):
            return m["key"]
    return None


def model_info(cfg: dict, key: str) -> dict:
    return next(m for m in cfg["models"] if m["key"] == key)
