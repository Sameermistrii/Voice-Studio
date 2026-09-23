from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from pipeline import F5_VENV, MODELS_DIR, ROOT, SADTALKER_VENV
from pipeline.hardware import detect_ffmpeg
from pipeline.media import run_ffmpeg
from pipeline.tts import Speech, Word, _duration

OMNIVOICE_VENV = MODELS_DIR / "omnivoice-venv"

VOICE_DIR = ROOT / "voice" / "cloned"
CLONE_ID = "clone:mine"
OPENVOICE_DIR = MODELS_DIR / "OpenVoice"
_DEFAULT_LABELS = {"My voice (cloned)", "My voice (VoiceStudio / OmniVoice)"}


def _slug(label: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "-", (label or "").lower()).strip("-")
    return (raw[:40] or "voice").strip("-") or "voice"


def _clone_id(slug: str) -> str:
    return f"clone:{slug}"


def _work_dir(voice: str | None = None) -> Path:
    raw = (voice or CLONE_ID).strip()
    slug = raw.split(":", 1)[-1] if raw.startswith("clone:") else raw
    slug = _slug(slug) if slug else "mine"
    return VOICE_DIR / slug


def _slot_ready(work: Path) -> bool:
    return (work / "prompt.wav").exists() and (work / "prompt.txt").exists()


def _next_voice_slug() -> str:
    n = 2
    while (VOICE_DIR / f"voice-{n}").exists():
        n += 1
    return f"voice-{n}"


def _gpu_python() -> Path:
    for folder in (F5_VENV, SADTALKER_VENV):
        py = folder / "Scripts" / "python.exe"
        if py.exists():
            return py
    raise RuntimeError("F5 GPU venv missing. Run: python gpu_jobs/setup_f5.py")


def _omnivoice_python() -> Path | None:
    py = OMNIVOICE_VENV / "Scripts" / "python.exe"
    if py.exists():
        return py
    return None


def omnivoice_ready() -> bool:
    if _omnivoice_python() is None:
        return False
    site = OMNIVOICE_VENV / "Lib" / "site-packages"
    return (site / "omnivoice").is_dir() or any(site.glob("omnivoice-*.dist-info"))


def cloned_ready(voice: str | None = None) -> bool:
    if voice:
        return _slot_ready(_work_dir(voice))
    if not VOICE_DIR.exists():
        return False
    return any(_slot_ready(path) for path in VOICE_DIR.iterdir() if path.is_dir())


def list_cloned_voices() -> list[dict[str, str]]:
    if not VOICE_DIR.exists():
        return []
    found: list[dict[str, str]] = []
    for folder in sorted(VOICE_DIR.iterdir(), key=lambda p: (p.name != "mine", p.name)):
        if not folder.is_dir() or not _slot_ready(folder):
            continue
        voice_id = _clone_id(folder.name)
        label = "My voice (VoiceStudio / OmniVoice)" if folder.name == "mine" and omnivoice_ready() else folder.name.replace("-", " ").title()
        meta = folder / "meta.json"
        if meta.exists():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                stored = (data.get("label") or "").strip()
                if stored and (folder.name != "mine" or stored not in _DEFAULT_LABELS):
                    label = stored
                elif stored and folder.name == "mine" and stored in _DEFAULT_LABELS and omnivoice_ready():
                    label = "My voice (VoiceStudio / OmniVoice)"
            except json.JSONDecodeError:
                pass
        found.append({"id": voice_id, "label": label})
    return found


def _prep_reference(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = detect_ffmpeg()
    run_ffmpeg(
        [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "24000",
            "-t",
            "60",
            str(dest),
        ]
    )
    return dest


def clone_from_audio(src: Path, label: str = "") -> dict:
    """Cut a clean prompt from a recording and save it as a named cloned voice."""
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError("Pick an audio clip of the voice first")
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    name = (label or "").strip()
    if name:
        slug = "mine" if name.lower() in {"my voice", "me", "mine"} else _slug(name)
    elif _slot_ready(VOICE_DIR / "mine"):
        slug = _next_voice_slug()
        name = f"Cloned voice {slug.split('-')[-1]}"
    else:
        slug = "mine"
        name = "My voice (VoiceStudio / OmniVoice)" if omnivoice_ready() else "My voice (cloned)"
    work = VOICE_DIR / slug
    work.mkdir(parents=True, exist_ok=True)
    ref = _prep_reference(src, work / "reference.wav")
    log = work / "clone_log.txt"
    _run_f5(["clone", "--ref", str(ref), "--out-dir", str(work)], log)
    if not _slot_ready(work):
        tail = log.read_text(encoding="utf-8", errors="replace")[-3000:]
        raise RuntimeError(f"Voice clone failed:\n{tail}")
    prompt_text = (work / "prompt.txt").read_text(encoding="utf-8").strip()
    stale = work / "omnivoice_prompt.pt"
    if stale.exists():
        stale.unlink()
    voice_id = _clone_id(slug)
    meta = {
        "id": voice_id,
        "label": name,
        "reference": str(ref),
        "prompt": str(work / "prompt.wav"),
        "prompt_text": prompt_text,
        "engine": "omnivoice" if omnivoice_ready() else "f5-tts",
        "gender": "male",
    }
    (work / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def _clone_base_voice(text: str) -> str:
    gender = "male"
    meta = VOICE_DIR / "mine" / "meta.json"
    if meta.exists():
        try:
            gender = json.loads(meta.read_text(encoding="utf-8")).get("gender") or gender
        except json.JSONDecodeError:
            pass
    hindi = bool(re.search(r"[\u0900-\u097F]", text or ""))
    if gender == "female":
        return "hi-IN-SwaraNeural" if hindi else "en-IN-NeerjaNeural"
    return "hi-IN-MadhurNeural" if hindi else "en-IN-PrabhatNeural"


def _run_gpu(args: list[str], log: Path, script: str = "openvoice_run.py", cwd: Path | None = None) -> None:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(OPENVOICE_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env["HF_HUB_DISABLE_XET"] = "1"
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(
            [str(_gpu_python()), "-u", str(ROOT / "gpu_jobs" / script), *args],
            stdout=fh,
            stderr=subprocess.STDOUT,
            cwd=str(cwd or OPENVOICE_DIR),
            env=env,
        )
    if proc.returncode != 0:
        tail = log.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(tail)


def _run_f5(args: list[str], log: Path) -> None:
    _run_gpu(args, log, script="f5_run.py", cwd=ROOT)


def _run_omnivoice(args: list[str], log: Path) -> None:
    py = _omnivoice_python()
    if not py:
        raise RuntimeError("OmniVoice venv missing")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["HF_HUB_DISABLE_XET"] = "1"
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(
            [str(py), "-u", str(ROOT / "gpu_jobs" / "omnivoice_run.py"), *args],
            stdout=fh,
            stderr=subprocess.STDOUT,
            cwd=str(ROOT),
            env=env,
        )
    if proc.returncode != 0:
        tail = log.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(tail)


def synthesize_cloned(
    text: str,
    dest: Path,
    voice: str = CLONE_ID,
    speed: float = 1.0,
    pitch: float = 0.0,
) -> Speech:
    from pipeline.tts import _clamp_pitch, _clamp_speed, shape_voice

    work = _work_dir(voice)
    prompt = work / "prompt.wav"
    prompt_txt = work / "prompt.txt"
    if not prompt.exists() or not prompt_txt.exists():
        raise FileNotFoundError("Clone that voice first: upload 10–30 seconds of them talking")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    speed = _clamp_speed(speed)
    pitch = _clamp_pitch(pitch)
    if omnivoice_ready():
        raw = dest.with_name(dest.stem + "_ov.wav")
        log = dest.with_name("omnivoice_log.txt")
        try:
            _run_omnivoice(
                [
                    "--ref",
                    str(prompt),
                    "--ref-text",
                    str(prompt_txt),
                    "--text",
                    text,
                    "--out",
                    str(raw),
                    "--speed",
                    f"{speed:.3f}",
                    "--nfe",
                    "16",
                ],
                log,
            )
            if raw.exists():
                shape_voice(raw, dest, sample_rate=24000, pitch=pitch, de_buzz=False)
                return Speech(dest, _duration(dest), [Word(text, 0.0, _duration(dest))], "omnivoice", voice)
        except Exception as exc:
            log.write_text(
                (log.read_text(encoding="utf-8", errors="replace") if log.exists() else "")
                + f"\nOmniVoice failed, falling back to F5-TTS:\n{exc}\n",
                encoding="utf-8",
            )
    raw = dest.with_name(dest.stem + "_f5.wav")
    log = dest.with_name("f5_log.txt")
    _run_f5(
        [
            "speak",
            "--ref",
            str(prompt),
            "--ref-text",
            str(prompt_txt),
            "--text",
            text,
            "--out",
            str(raw),
            "--nfe",
            "32",
            "--speed",
            f"{speed:.3f}",
        ],
        log,
    )
    if not raw.exists():
        tail = log.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(f"Cloned voice failed:\n{tail}")
    shape_voice(raw, dest, sample_rate=24000, pitch=pitch, de_buzz=False)
    return Speech(dest, _duration(dest), [Word(text, 0.0, _duration(dest))], "f5-tts", voice)
