"""Create models/f5-venv and install F5-TTS plus faster-whisper (clone fallback)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

os.environ["HF_HUB_DISABLE_XET"] = "1"

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / "models" / "f5-venv"
PY = VENV / "Scripts" / "python.exe"
CFG = VENV / "pyvenv.cfg"
REQ = ROOT / "requirements-f5.txt"


def _isolate_venv() -> None:
    if not CFG.exists():
        return
    text = CFG.read_text(encoding="utf-8")
    patched = text.replace(
        "include-system-site-packages = true",
        "include-system-site-packages = false",
    )
    if patched != text:
        CFG.write_text(patched, encoding="utf-8")


def main() -> None:
    if sys.version_info < (3, 11) or sys.version_info >= (3, 12):
        raise SystemExit("Python 3.11 is required (64-bit Windows).")
    if not PY.exists():
        print("creating f5 venv", flush=True)
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    _isolate_venv()
    subprocess.check_call([str(PY), "-m", "pip", "install", "--upgrade", "pip"])
    print("installing CUDA torch 2.5.1+cu121", flush=True)
    subprocess.check_call(
        [
            str(PY),
            "-m",
            "pip",
            "install",
            "torch==2.5.1+cu121",
            "torchaudio==2.5.1+cu121",
            "--index-url",
            "https://download.pytorch.org/whl/cu121",
        ]
    )
    print("installing F5-TTS + faster-whisper", flush=True)
    subprocess.check_call([str(PY), "-m", "pip", "install", "-r", str(REQ)])
    subprocess.call([str(PY), "-m", "pip", "uninstall", "-y", "hf-xet"])
    subprocess.check_call(
        [
            str(PY),
            "-c",
            "import torch; from f5_tts.api import F5TTS; import faster_whisper; "
            "print('f5 ok', torch.__version__, 'cuda', torch.cuda.is_available())",
        ]
    )


if __name__ == "__main__":
    main()
