from __future__ import annotations

import json
from pathlib import Path

import yaml

from pipeline import HARDWARE_PATH, ROOT


def load_config() -> dict:
    path = ROOT / "config.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_hardware() -> dict:
    if not HARDWARE_PATH.exists():
        return {}
    try:
        return json.loads(HARDWARE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    h = value.strip().lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
