from __future__ import annotations

import asyncio
import re
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import soundfile as sf

from pipeline.config import load_config
from pipeline.hardware import detect_ffmpeg
from pipeline.media import run_ffmpeg

INDIAN_MALE_VOICES = [
    ("en-IN-PrabhatNeural", "Indian English — Prabhat"),
    ("hi-IN-MadhurNeural", "Hindi — Madhur"),
]
INDIAN_FEMALE_VOICES = [
    ("en-IN-NeerjaNeural", "Indian English — Neerja"),
    ("en-IN-NeerjaExpressive", "Indian English — Neerja Expressive"),
    ("en-IN-AartiNeural", "Indian English — Aarti"),
    ("en-IN-AnanyaNeural", "Indian English — Ananya"),
    ("hi-IN-SwaraNeural", "Hindi — Swara"),
    ("hi-IN-KavyaNeural", "Hindi — Kavya"),
]


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Speech:
    wav_path: Path
    duration: float
    words: list[Word]
    engine: str
    voice: str

    def as_dict(self) -> dict:
        return {
            "wav_path": str(self.wav_path),
            "duration": self.duration,
            "engine": self.engine,
            "voice": self.voice,
            "words": [asdict(w) for w in self.words],
        }


def _duration(path: Path) -> float:
    info = sf.info(str(path))
    return float(info.frames) / float(info.samplerate)


def _ffmpeg_to_wav(src: Path, dest: Path, sample_rate: int) -> None:
    ffmpeg = detect_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    run_ffmpeg(
        [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            str(dest),
        ]
    )


def _clamp_speed(speed: float) -> float:
    try:
        value = float(speed)
    except (TypeError, ValueError):
        value = 1.0
    return max(0.7, min(1.4, value))


def _clamp_pitch(pitch: float) -> float:
    try:
        value = float(pitch)
    except (TypeError, ValueError):
        value = 0.0
    return max(-6.0, min(6.0, value))


def edge_rate_from_speed(speed: float) -> str:
    pct = int(round((_clamp_speed(speed) - 1.0) * 100))
    return f"{pct:+d}%"


def shape_voice(
    src: Path,
    dest: Path,
    sample_rate: int = 24000,
    pitch: float = 0.0,
    de_buzz: bool = False,
) -> None:
    """Peak-limit, optional de-buzz, and shift pitch in semitones without changing speed."""
    ffmpeg = detect_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    src = Path(src)
    dest = Path(dest)
    pitch = _clamp_pitch(pitch)
    filters: list[str] = []
    if de_buzz:
        filters.extend(["highpass=f=80", "lowpass=f=11000"])
    if abs(pitch) >= 0.05:
        factor = 2.0 ** (pitch / 12.0)
        tempo = 1.0 / factor
        tempo = max(0.5, min(2.0, tempo))
        filters.extend(
            [
                f"asetrate={int(sample_rate)}*{factor:.6f}",
                f"aresample={int(sample_rate)}",
                f"atempo={tempo:.6f}",
            ]
        )
    if not filters:
        if src.resolve() != dest.resolve():
            import shutil

            shutil.copy2(src, dest)
        data, sr = sf.read(str(dest), dtype="float32")
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        peak = float(np.max(np.abs(data))) if data.size else 0.0
        if peak > 0.9:
            data = data * (0.9 / peak)
            sf.write(str(dest), data, int(sr), subtype="PCM_16")
        return
    tmp = dest.with_name(dest.stem + "_fx.tmp.wav")
    run_ffmpeg(
        [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-af",
            ",".join(filters),
            str(tmp),
        ]
    )
    tmp.replace(dest)
    data, sr = sf.read(str(dest), dtype="float32")
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak > 0.86:
        data = data * (0.86 / peak)
        sf.write(str(dest), data, int(sr), subtype="PCM_16")


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    out: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) > 280:
            bits = re.split(r"(?<=,)\s+", part)
            buf = ""
            for bit in bits:
                trial = (buf + " " + bit).strip()
                if len(trial) > 280 and buf:
                    out.append(buf)
                    buf = bit
                else:
                    buf = trial
            if buf:
                out.append(buf)
        else:
            out.append(part)
    return out or [cleaned]


def _concat(wavs: list[Path], dest: Path, gap_ms: int) -> None:
    chunks: list[np.ndarray] = []
    sr = 24000
    for i, path in enumerate(wavs):
        data, sr = sf.read(str(path), dtype="float32")
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        chunks.append(data)
        if i < len(wavs) - 1 and gap_ms > 0:
            chunks.append(np.zeros(int(sr * gap_ms / 1000.0), dtype=np.float32))
    sf.write(str(dest), np.concatenate(chunks), sr, subtype="PCM_16")


async def _edge_chunk(text: str, voice: str, rate: str, pitch: str, dest: Path, sample_rate: int) -> list[Word]:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    words: list[Word] = []
    chunks = bytearray()
    async for item in communicate.stream():
        kind = item.get("type")
        if kind == "audio":
            chunks.extend(item["data"])
        elif kind == "WordBoundary":
            start = float(item["offset"]) / 10_000_000.0
            dur = float(item["duration"]) / 10_000_000.0
            words.append(Word(text=str(item.get("text") or ""), start=start, end=start + dur))
    if not chunks:
        raise RuntimeError("Voice engine returned no audio")
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(bytes(chunks))
        mp3_path = Path(tmp.name)
    try:
        _ffmpeg_to_wav(mp3_path, dest, sample_rate)
    finally:
        mp3_path.unlink(missing_ok=True)
    duration = _duration(dest)
    if words:
        words[-1].end = max(words[-1].end, duration)
    return words


def list_voices() -> list[dict[str, str]]:
    from pipeline.openvoice import list_cloned_voices

    cloned = list_cloned_voices()
    stock = [{"id": vid, "label": label} for vid, label in INDIAN_FEMALE_VOICES]
    return cloned + stock


def synthesize_edge(
    text: str,
    dest: Path,
    voice: str,
    fallbacks: list[str] | None = None,
    rate: str | None = None,
    pitch: str | None = None,
) -> Speech:
    cfg = load_config()
    tts_cfg = cfg.get("tts") or {}
    sample_rate = int(tts_cfg.get("sample_rate") or 24000)
    rate = rate if rate is not None else str(tts_cfg.get("rate") or "-8%")
    pitch = pitch if pitch is not None else str(tts_cfg.get("pitch") or "+1Hz")
    gap_ms = int(tts_cfg.get("sentence_gap_ms") or 110)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sentences = _sentences(text)
    if not sentences:
        raise ValueError("Write a script first")
    voices_to_try = [voice] + [v for v in (fallbacks or []) if v != voice]
    all_words: list[Word] = []
    parts: list[Path] = []
    errors: list[str] = []
    chosen = None
    for candidate in voices_to_try:
        try:
            all_words = []
            parts = []
            offset = 0.0
            for i, sentence in enumerate(sentences):
                part = dest.with_name(f"{dest.stem}_p{i}.wav")
                words = asyncio.run(_edge_chunk(sentence, candidate, rate, pitch, part, sample_rate))
                for word in words:
                    all_words.append(Word(word.text, word.start + offset, word.end + offset))
                offset += _duration(part) + gap_ms / 1000.0
                parts.append(part)
            chosen = candidate
            break
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{candidate}: {exc}")
            continue
    if chosen is None:
        raise RuntimeError("Voice engine failed: " + " | ".join(errors))
    import shutil

    if len(parts) == 1:
        if parts[0].resolve() != dest.resolve():
            shutil.copy2(parts[0], dest)
            parts[0].unlink(missing_ok=True)
    else:
        _concat(parts, dest, gap_ms)
        for part in parts:
            part.unlink(missing_ok=True)
    return Speech(dest, _duration(dest), all_words, "edge", chosen)


def synthesize(
    text: str,
    dest: Path,
    voice: str | None = None,
    speed: float = 1.0,
    pitch: float = 0.0,
) -> Speech:
    cfg = load_config()
    tts_cfg = cfg.get("tts") or {}
    voice = voice or tts_cfg.get("voice") or "en-IN-NeerjaNeural"
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    speed = _clamp_speed(speed)
    pitch = _clamp_pitch(pitch)
    if str(voice).startswith("clone:"):
        from pipeline.openvoice import synthesize_cloned

        return synthesize_cloned(text, dest, voice=str(voice), speed=speed, pitch=pitch)
    fallbacks = [v for v, _ in INDIAN_FEMALE_VOICES + INDIAN_MALE_VOICES if v != voice]
    speech = synthesize_edge(
        text,
        dest,
        voice,
        fallbacks=fallbacks,
        rate=edge_rate_from_speed(speed),
        pitch="+0Hz",
    )
    if abs(pitch) >= 0.05:
        shape_voice(dest, dest, sample_rate=int(tts_cfg.get("sample_rate") or 24000), pitch=pitch)
        speech = Speech(dest, _duration(dest), speech.words, speech.engine, speech.voice)
    return speech
