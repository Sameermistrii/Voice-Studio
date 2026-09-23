from __future__ import annotations

import base64
import shutil
import sys
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "ui" / "runtime"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import webview

from pipeline.hardware import snapshot
from pipeline.tts import list_voices, synthesize
from pipeline.openvoice import clone_from_audio, cloned_ready, omnivoice_ready


def _publish_audio(path: str) -> str:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    dest = RUNTIME / "voice_preview.wav"
    shutil.copy2(path, dest)
    return "runtime/voice_preview.wav"


class Api:
    def __init__(self) -> None:
        self._voice_job = {"state": "idle", "message": "", "output": "", "output_path": ""}
        self._last_clone_id = ""
        self._lock = threading.Lock()

    def state(self) -> dict:
        hw = snapshot()
        gpu = hw.get("gpu_name") or "No NVIDIA GPU"
        vram = hw.get("vram_mb") or 0
        cloned = cloned_ready()
        voices = list_voices()
        last = getattr(self, "_last_clone_id", "") or ""
        default_voice = last if last and any(v["id"] == last for v in voices) else (
            "clone:mine" if any(v["id"] == "clone:mine" for v in voices) else (
                voices[0]["id"] if cloned and voices else "en-IN-NeerjaNeural"
            )
        )
        return {
            "hw": f"{gpu} · {vram} MB VRAM",
            "voices": voices,
            "voice": default_voice,
            "cloned": cloned,
            "audio": self._voice_job.get("output") or "",
            "audio_path": self._voice_job.get("output_path") or "",
        }

    def pick_voice_sample(self, label: str = "") -> dict:
        window = webview.windows[0]
        picked = window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Audio (*.wav;*.mp3;*.m4a;*.flac;*.ogg;*.aac)",),
        )
        if not picked:
            return {"ok": False}
        path = Path(picked[0] if isinstance(picked, (list, tuple)) else picked)
        return self._start_clone(path, label)

    def import_voice_b64(self, name: str, data_url: str, label: str = "") -> dict:
        try:
            raw = data_url.split(",", 1)[1] if "," in data_url else data_url
            blob = base64.b64decode(raw)
            dest = ROOT / "voice" / "inbox" / Path(name).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}
        return self._start_clone(dest, label)

    def _busy(self) -> bool:
        return self._voice_job.get("state") == "running"

    def _start_clone(self, path: Path, label: str = "") -> dict:
        with self._lock:
            if self._busy():
                return {"error": "Wait for the current job to finish"}
            self._voice_job = {"state": "running", "message": "Cloning voice…", "output": "", "output_path": ""}
        thread = threading.Thread(target=self._run_clone, args=(path, label), daemon=True)
        thread.start()
        return {"ok": True}

    def _run_clone(self, path: Path, label: str = "") -> None:
        try:
            meta = clone_from_audio(path, label=label or "")
            self._last_clone_id = meta.get("id") or ""
            shown = (meta.get("label") or "Voice").strip()
            with self._lock:
                self._voice_job = {
                    "state": "cloned",
                    "message": f"Cloned {shown}. Pick it under Speak with.",
                    "output": "",
                    "output_path": "",
                }
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._voice_job = {"state": "error", "message": str(exc), "output": "", "output_path": ""}

    def start_speak(self, script: str, voice: str, speed: float = 1.0, pitch: float = 0.0) -> dict:
        text = (script or "").strip()
        if not text:
            return {"error": "Type the text you want spoken"}
        with self._lock:
            if self._busy():
                return {"error": "Wait for the current job to finish"}
            speak_msg = "Generating voice…"
            if (voice or "").startswith("clone:") and omnivoice_ready():
                speak_msg = "Generating with OmniVoice…"
            self._voice_job = {"state": "running", "message": speak_msg, "output": "", "output_path": ""}
        thread = threading.Thread(target=self._run_speak, args=(text, voice, speed, pitch), daemon=True)
        thread.start()
        return {"ok": True}

    def _run_speak(self, text: str, voice: str, speed: float = 1.0, pitch: float = 0.0) -> None:
        try:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            work = ROOT / "output" / f"voice-{stamp}"
            work.mkdir(parents=True, exist_ok=True)
            speech = synthesize(text, work / "speech.wav", voice=voice or None, speed=speed, pitch=pitch)
            with self._lock:
                self._voice_job = {
                    "state": "done",
                    "message": "Voice ready",
                    "output": _publish_audio(str(speech.wav_path)),
                    "output_path": str(speech.wav_path),
                }
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._voice_job = {"state": "error", "message": str(exc), "output": "", "output_path": ""}

    def voice_job_status(self) -> dict:
        with self._lock:
            return dict(self._voice_job)

    def preview_voice(self, script: str, voice: str) -> dict:
        return self.start_speak(script, voice)


def main() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    ui = str(ROOT / "ui" / "index.html")
    webview.create_window(
        "Voice Studio",
        ui,
        js_api=Api(),
        width=1180,
        height=720,
        min_size=(900, 560),
        background_color="#101214",
    )
    webview.start(http_server=True)


if __name__ == "__main__":
    main()
