"""One-shot Voice Studio install: UI venv, OmniVoice, F5-TTS, and model weights."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

ROOT = Path(__file__).resolve().parents[1]
UI_VENV = ROOT / ".venv"
UI_PY = UI_VENV / "Scripts" / "python.exe"


def _run(args: list[str]) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.check_call(args, cwd=str(ROOT))


def _need_python_311() -> None:
    if sys.version_info < (3, 11) or sys.version_info >= (3, 12):
        raise SystemExit(
            "Python 3.11 64-bit is required. Install from https://www.python.org/downloads/ "
            "and tick \"Add python.exe to PATH\"."
        )


def _need_ffmpeg() -> None:
    if shutil.which("ffmpeg"):
        print("ffmpeg ok", flush=True)
        return
    print("ffmpeg is not on PATH.", flush=True)
    print("Install it, then re-run this installer:", flush=True)
    print("  winget install Gyan.FFmpeg", flush=True)
    print("  https://www.gyan.dev/ffmpeg/builds/", flush=True)
    raise SystemExit("ffmpeg missing")


def main() -> None:
    os.chdir(ROOT)
    _need_python_311()
    _need_ffmpeg()
    (ROOT / "models").mkdir(parents=True, exist_ok=True)
    (ROOT / "output").mkdir(parents=True, exist_ok=True)
    (ROOT / "voice" / "cloned").mkdir(parents=True, exist_ok=True)

    if not UI_PY.exists():
        print("creating UI venv", flush=True)
        _run([sys.executable, "-m", "venv", str(UI_VENV)])
    _run([str(UI_PY), "-m", "pip", "install", "--upgrade", "pip"])
    _run([str(UI_PY), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])

    _run([sys.executable, str(ROOT / "gpu_jobs" / "setup_omnivoice.py")])
    _run([sys.executable, str(ROOT / "gpu_jobs" / "setup_f5.py")])

    omni_py = ROOT / "models" / "omnivoice-venv" / "Scripts" / "python.exe"
    f5_py = ROOT / "models" / "f5-venv" / "Scripts" / "python.exe"
    _run([str(omni_py), str(ROOT / "gpu_jobs" / "download_omnivoice.py")])
    _run([str(f5_py), str(ROOT / "gpu_jobs" / "download_f5.py")])

    print("", flush=True)
    print("Install finished.", flush=True)
    print("Launch:  .\\.venv\\Scripts\\python.exe app.py", flush=True)
    print("Or double-click Start Voice Studio.bat", flush=True)


if __name__ == "__main__":
    main()
