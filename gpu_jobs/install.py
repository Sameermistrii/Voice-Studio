"""One-shot Voice Studio install: deps, GPU venvs, and model weights."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

ROOT = Path(__file__).resolve().parents[1]
UI_VENV = ROOT / ".venv"
UI_PY = UI_VENV / "Scripts" / "python.exe"


def _run(args: list[str]) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.check_call(args, cwd=str(ROOT))


def _refresh_path() -> None:
    chunks: list[str] = []
    for hive, key in (
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, "Environment"),
    ):
        try:
            with winreg.OpenKey(hive, key) as handle:
                value, _ = winreg.QueryValueEx(handle, "Path")
                if value:
                    chunks.append(str(value))
        except OSError:
            continue
    extra = [
        r"C:\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin",
        r"C:\Program Files\Gyan\FFmpeg\bin",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\Scripts"),
        r"C:\Program Files\Python311",
        r"C:\Program Files\Python311\Scripts",
    ]
    seen: set[str] = set()
    merged: list[str] = []
    for part in os.pathsep.join(chunks + [os.environ.get("PATH", "")] + extra).split(os.pathsep):
        item = part.strip().strip('"')
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    os.environ["PATH"] = os.pathsep.join(merged)


def _find_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    patterns = [
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe")),
        ROOT / "ffmpeg" / "ffmpeg.exe",
    ]
    for path in patterns:
        if path.exists():
            os.environ["PATH"] = str(path.parent) + os.pathsep + os.environ.get("PATH", "")
            return str(path)
    winget_root = Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"))
    if winget_root.exists():
        matches = sorted(winget_root.glob("Gyan.FFmpeg*\ffmpeg-*\bin\ffmpeg.exe"))
        if matches:
            os.environ["PATH"] = str(matches[-1].parent) + os.pathsep + os.environ.get("PATH", "")
            return str(matches[-1])
    return ""


def _winget_install(package_id: str) -> bool:
    winget = shutil.which("winget")
    if not winget:
        print("winget not found; cannot auto-install", package_id, flush=True)
        return False
    print(f"installing {package_id} with winget", flush=True)
    proc = subprocess.run(
        [
            winget,
            "install",
            "-e",
            "--id",
            package_id,
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--disable-interactivity",
        ],
        cwd=str(ROOT),
    )
    _refresh_path()
    return proc.returncode in (0, -1978335189)


def _need_python_311() -> None:
    if sys.version_info < (3, 11) or sys.version_info >= (3, 12):
        raise SystemExit(
            "Python 3.11 64-bit is required. setup.bat will try winget, or install from "
            "https://www.python.org/downloads/ and tick \"Add python.exe to PATH\"."
        )


def _ensure_ffmpeg() -> None:
    if _find_ffmpeg():
        print("ffmpeg ok", _find_ffmpeg(), flush=True)
        return
    print("ffmpeg not on PATH — downloading with winget", flush=True)
    _winget_install("Gyan.FFmpeg")
    exe = _find_ffmpeg()
    if exe:
        print("ffmpeg ok", exe, flush=True)
        return
    print("Could not auto-install ffmpeg. Install it, then re-run setup.bat:", flush=True)
    print("  winget install Gyan.FFmpeg", flush=True)
    print("  https://www.gyan.dev/ffmpeg/builds/", flush=True)
    raise SystemExit("ffmpeg missing")


def _ensure_vcredist() -> None:
    dll = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "vcruntime140.dll"
    if dll.exists():
        print("VC++ runtime ok", flush=True)
        return
    _winget_install("Microsoft.VCRedist.2015+.x64")


def _warn_gpu() -> None:
    smi = shutil.which("nvidia-smi")
    if smi:
        print("nvidia-smi ok", flush=True)
        return
    print("WARNING: nvidia-smi not found. Install an NVIDIA Game Ready/Studio driver.", flush=True)
    print("Voice cloning needs a CUDA GPU. The installer will still download files.", flush=True)


def _prefetch_whisper(f5_py: Path) -> None:
    print("downloading Whisper small (used when cloning a voice)", flush=True)
    _run(
        [
            str(f5_py),
            "-c",
            "from faster_whisper import WhisperModel; "
            "WhisperModel('small', device='cpu', compute_type='int8'); "
            "print('whisper small ready')",
        ]
    )


def _ensure_pythonw(venv: Path) -> None:
    dst = venv / "Scripts" / "pythonw.exe"
    if dst.exists():
        return
    src = Path(sys.executable).with_name("pythonw.exe")
    if not src.exists():
        src = Path(sys.base_prefix) / "pythonw.exe"
    if src.exists():
        shutil.copy2(src, dst)
        print("copied pythonw.exe into UI venv", flush=True)
    os.chdir(ROOT)
    _refresh_path()
    _need_python_311()
    _warn_gpu()
    _ensure_vcredist()
    _ensure_ffmpeg()
    (ROOT / "models").mkdir(parents=True, exist_ok=True)
    (ROOT / "output").mkdir(parents=True, exist_ok=True)
    (ROOT / "voice" / "cloned").mkdir(parents=True, exist_ok=True)

    if not UI_PY.exists():
        print("creating UI venv", flush=True)
        _run([sys.executable, "-m", "venv", str(UI_VENV)])
    _ensure_pythonw(UI_VENV)
    _run([str(UI_PY), "-m", "pip", "install", "--upgrade", "pip"])
    _run([str(UI_PY), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])

    _run([sys.executable, str(ROOT / "gpu_jobs" / "setup_omnivoice.py")])
    _run([sys.executable, str(ROOT / "gpu_jobs" / "setup_f5.py")])

    omni_py = ROOT / "models" / "omnivoice-venv" / "Scripts" / "python.exe"
    f5_py = ROOT / "models" / "f5-venv" / "Scripts" / "python.exe"
    _run([str(omni_py), str(ROOT / "gpu_jobs" / "download_omnivoice.py")])
    _run([str(f5_py), str(ROOT / "gpu_jobs" / "download_f5.py")])
    _prefetch_whisper(f5_py)

    print("", flush=True)
    print("Install finished. All app packages and model files are downloaded.", flush=True)
    print("Launch:  .\\.venv\\Scripts\\python.exe app.py", flush=True)
    print("Or double-click Start Voice Studio.bat", flush=True)


if __name__ == "__main__":
    main()
