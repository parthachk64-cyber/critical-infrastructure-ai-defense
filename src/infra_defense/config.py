from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "configs" / "default.yaml"
FIXTURE_DIR = REPO_ROOT / "data" / "synthetic"
RUNS_DIR = REPO_ROOT / "runs"


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    with open(path or CONFIG_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not isinstance(cfg, dict):
        raise ValueError("config must be a mapping")
    return cfg


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()
