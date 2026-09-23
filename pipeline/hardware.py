from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from pipeline import HARDWARE_PATH, MODELS_DIR, ROOT


def detect_vram_mb() -> int:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return 0
    try:
        raw = subprocess.check_output(
            [exe, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        line = raw.strip().splitlines()[0].strip()
        return int(float(line))
    except (subprocess.SubprocessError, ValueError, IndexError, OSError):
        return 0


def detect_gpu_name() -> str:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return ""
    try:
        raw = subprocess.check_output(
            [exe, "--query-gpu=name", "--format=csv,noheader"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return raw.strip().splitlines()[0].strip()
    except (subprocess.SubprocessError, IndexError, OSError):
        return ""


def detect_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    local = ROOT / "ffmpeg" / "ffmpeg.exe"
    if local.exists():
        return str(local)
    return ""


def snapshot() -> dict[str, Any]:
    data = {
        "gpu_name": detect_gpu_name(),
        "vram_mb": detect_vram_mb(),
        "ffmpeg": detect_ffmpeg(),
    }
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    HARDWARE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
