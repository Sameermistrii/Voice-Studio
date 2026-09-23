"""Zero-shot voice clone with F5-TTS (speaks as the recorded person)."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import numpy as np
import soundfile as sf
import torch

ROOT = Path(__file__).resolve().parents[1]
F5_DIR = ROOT / "models" / "f5tts"
CKPT = F5_DIR / "F5TTS_v1_Base" / "model_1250000.safetensors"
VOCAB = F5_DIR / "F5TTS_v1_Base" / "vocab.txt"
VOCOS = F5_DIR / "vocos"


def _best_prompt(wav_path: str, dest: Path, seconds: float = 6.0) -> Path:
    import librosa

    y, sr = librosa.load(wav_path, sr=24000, mono=True)
    y, _ = librosa.effects.trim(y, top_db=24)
    if len(y) < sr * 4:
        raise RuntimeError("Need at least 4 seconds of you talking")
    win = int(sr * min(seconds, len(y) / sr))
    hop = int(sr * 0.2)
    best_i = 0
    best_score = -1.0
    last = max(1, len(y) - win)
    for start in range(0, last, hop):
        chunk = y[start : start + win]
        frames = librosa.feature.rms(y=chunk, frame_length=2048, hop_length=512)[0]
        voiced = float(np.mean(frames > 0.015))
        clip_frac = float(np.mean(np.abs(chunk) > 0.98))
        score = float(np.median(frames)) * voiced * (1.0 - min(1.0, clip_frac * 8.0))
        if score > best_score:
            best_score = score
            best_i = start
    prompt = np.asarray(y[best_i : best_i + win], dtype=np.float32)
    rms = float(np.sqrt(np.mean(prompt**2))) if prompt.size else 0.0
    if rms > 1e-6 and rms < 0.11:
        prompt = prompt * (0.11 / rms)
    peak = float(np.max(np.abs(prompt))) if prompt.size else 0.0
    if peak > 0.82:
        prompt = prompt * (0.82 / peak)
    fade = min(int(sr * 0.02), max(1, len(prompt) // 8))
    if fade > 1:
        prompt[:fade] *= np.linspace(0.0, 1.0, fade, dtype=np.float32)
        prompt[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dest), prompt, sr, subtype="PCM_16")
    return dest


def _collapse_repeats(text: str) -> str:
    words = text.split()
    out: list[str] = []
    for w in words:
        if out and w == out[-1]:
            continue
        out.append(w)
    return " ".join(out)


def _transcribe(wav_path: str) -> str:
    from faster_whisper import WhisperModel

    model = WhisperModel("small", device="cpu", compute_type="int8")
    best = ""
    best_lang = ""
    for lang in ("en", "hi"):
        segments, _info = model.transcribe(
            wav_path,
            vad_filter=False,
            beam_size=5,
            language=lang,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.45,
        )
        parts: list[str] = []
        prev = ""
        for seg in segments:
            t = _collapse_repeats((seg.text or "").strip())
            if not t or t == prev:
                continue
            parts.append(t)
            prev = t
        text = _collapse_repeats(" ".join(parts)).strip()
        print(json.dumps({"try_lang": lang, "text": text}), flush=True)
        letters = sum(ch.isascii() and ch.isalpha() for ch in text)
        if lang == "en" and letters >= 24:
            best = text
            best_lang = lang
            break
        if len(text) > len(best):
            best = text
            best_lang = lang
    if len(best) < 8:
        raise RuntimeError("Could not hear words in the voice sample. Record clearer speech.")
    print(json.dumps({"lang": best_lang, "text": best}), flush=True)
    return best


_LEAK_WORDS = re.compile(r"(?i)\bpunch\b|\bgold\b")


def _timed_english(wav_path: str) -> list[tuple[float, float, str]]:
    from faster_whisper import WhisperModel

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _info = model.transcribe(
        wav_path,
        vad_filter=False,
        beam_size=5,
        language="en",
        condition_on_previous_text=False,
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.0,
        no_speech_threshold=0.45,
    )
    out: list[tuple[float, float, str]] = []
    prev = ""
    for seg in segs:
        text = _collapse_repeats((seg.text or "").strip())
        if not text or text == prev:
            continue
        out.append((float(seg.start), float(seg.end), text))
        prev = text
    return out


def _pick_prompt_span(segs: list[tuple[float, float, str]]) -> tuple[float, float, str] | None:
    best: tuple[float, float, float, str] | None = None
    for i, (start, _end0, _t0) in enumerate(segs):
        parts: list[str] = []
        for end, text in ((s[1], s[2]) for s in segs[i:]):
            parts.append(text)
            dur = end - start
            if dur < 4.5:
                continue
            if dur > 8.5:
                break
            blob = _collapse_repeats(" ".join(parts))
            if _LEAK_WORDS.search(blob):
                continue
            letters = sum(ch.isascii() and ch.isalpha() for ch in blob)
            if letters < 24:
                continue
            score = letters / max(dur, 1.0) - abs(dur - 6.0) * 4.0
            if best is None or score > best[0]:
                best = (score, start, end, blob)
    if best is None:
        return None
    return best[1], best[2], best[3]


def _cut_span(wav_path: str, dest: Path, start: float, end: float) -> Path:
    import librosa

    dur = max(3.0, end - start)
    y, sr = librosa.load(wav_path, sr=24000, mono=True, offset=max(0.0, start), duration=dur)
    y, _ = librosa.effects.trim(y, top_db=24)
    if len(y) < sr * 3:
        raise RuntimeError("Need at least 3 seconds of you talking")
    rms = float(np.sqrt(np.mean(y**2))) if y.size else 0.0
    if rms > 1e-6 and rms < 0.11:
        y = y * (0.11 / rms)
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 0.82:
        y = y * (0.82 / peak)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dest), np.asarray(y, dtype=np.float32), sr, subtype="PCM_16")
    return dest


def clone_prompt(reference_wav: str, out_dir: str) -> None:
    work = Path(out_dir)
    work.mkdir(parents=True, exist_ok=True)
    dest = work / "prompt.wav"
    segs = _timed_english(reference_wav)
    span = _pick_prompt_span(segs) if segs else None
    if span:
        start, end, text = span
        prompt = _cut_span(reference_wav, dest, start, end)
        print(json.dumps({"span": [round(start, 2), round(end, 2)], "text": text}), flush=True)
    else:
        prompt = _best_prompt(reference_wav, dest)
        text = _transcribe(str(prompt))
        if _LEAK_WORDS.search(text):
            prompt = _cut_span(reference_wav, dest, 13.0, 19.0)
            text = _transcribe(str(prompt))
    (work / "prompt.txt").write_text(text, encoding="utf-8")
    print(json.dumps({"ok": True, "prompt": str(prompt), "text": text}), flush=True)


def _patch_f5_chunking() -> None:
    import f5_tts.infer.utils_infer as utils_infer

    if getattr(utils_infer, "_pyclips_pace_patch", False):
        return
    orig = utils_infer.chunk_text

    def chunk_text(text, max_chars=135):
        max_chars = max(int(max_chars or 135), 90)
        chunks = orig(text, max_chars=max_chars)
        merged: list[str] = []
        buf = ""
        for chunk in chunks:
            candidate = f"{buf} {chunk}".strip() if buf else chunk
            if buf and len(chunk.encode("utf-8")) < 24:
                buf = candidate
                continue
            if buf:
                merged.append(buf)
            buf = chunk
        if buf:
            if merged and len(buf.encode("utf-8")) < 24:
                merged[-1] = f"{merged[-1]} {buf}".strip()
            else:
                merged.append(buf)
        return merged or chunks or [text]

    utils_infer.chunk_text = chunk_text
    utils_infer._pyclips_pace_patch = True


def _load_tts():
    if not CKPT.exists():
        raise FileNotFoundError("F5-TTS weights missing. Run gpu_jobs/download_f5.py")
    from f5_tts.api import F5TTS

    _patch_f5_chunking()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return F5TTS(
        model="F5TTS_v1_Base",
        ckpt_file=str(CKPT),
        vocab_file=str(VOCAB) if VOCAB.exists() else "",
        vocoder_local_path=str(VOCOS) if (VOCOS / "pytorch_model.bin").exists() else None,
        device=device,
    )


def _normalize_script(text: str) -> str:
    import re

    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    cleaned = re.sub(r"\s+([,;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"\s+\.", ".", cleaned)
    return cleaned


def _punct_chunks(text: str) -> list[tuple[str, str]]:
    """Split on commas and sentence ends so we can insert a human pause after each."""
    import re

    cleaned = _normalize_script(text)
    if not cleaned:
        return []
    if cleaned[-1] not in ".!?":
        cleaned += "."
    pieces = re.split(r"([,!?]|[.])", cleaned)
    chunks: list[tuple[str, str]] = []
    buf = ""
    for piece in pieces:
        if piece is None:
            continue
        token = piece.strip()
        if not token:
            continue
        if token in ",.!?":
            phrase = buf.strip()
            buf = ""
            if not phrase:
                continue
            if chunks and token == "," and len(phrase.split()) < 2:
                prev, _p = chunks[-1]
                chunks[-1] = (f"{prev} {phrase}".strip(), token)
            else:
                chunks.append((phrase, token))
            continue
        buf = f"{buf} {token}".strip()
    if buf.strip():
        chunks.append((buf.strip(), "."))
    out: list[tuple[str, str]] = []
    for phrase, punct in chunks:
        if out and len(phrase.encode("utf-8")) < 12:
            prev, prev_p = out[-1]
            join_p = prev_p if prev_p in ".!?" else punct
            out[-1] = (f"{prev} {phrase}".strip(), join_p)
        else:
            out.append((phrase, punct))
    folded: list[tuple[str, str]] = []
    i = 0
    while i < len(out):
        phrase, punct = out[i]
        if punct == "," and len(phrase.split()) <= 2 and i + 1 < len(out):
            nxt, npunct = out[i + 1]
            folded.append((f"{phrase}, {nxt}", npunct))
            i += 2
            continue
        folded.append((phrase, punct))
        i += 1
    return folded or [(cleaned, ".")]


def _trim_edges(wav: np.ndarray, sr: int) -> np.ndarray:
    wav = np.asarray(wav, dtype=np.float32)
    if wav.size < 16:
        return wav
    mag = np.abs(wav)
    win = max(1, int(sr * 0.012))
    env = np.convolve(mag, np.ones(win) / win, mode="same")
    voiced = np.where(env > 0.012)[0]
    if voiced.size < 8:
        return wav
    pad_lead = int(sr * 0.03)
    pad_tail = int(sr * 0.08)
    start = max(0, int(voiced[0]) - pad_lead)
    end = min(len(wav), int(voiced[-1]) + pad_tail)
    return wav[start:end]


def _soft_gap(sr: int, seconds: float) -> np.ndarray:
    n = max(1, int(sr * seconds))
    fade = min(int(sr * 0.018), n // 3)
    gap = np.zeros(n, dtype=np.float32)
    if fade > 2:
        gap[:fade] = 0.0
    return gap


def _join_calm(left: np.ndarray, right: np.ndarray, sr: int, pause: float) -> np.ndarray:
    fade = max(8, int(sr * 0.016))
    left = np.asarray(left, dtype=np.float32).copy()
    right = np.asarray(right, dtype=np.float32).copy()
    if len(left) > fade:
        left[-fade:] *= np.linspace(1.0, 0.55, fade, dtype=np.float32)
    if len(right) > fade:
        right[:fade] *= np.linspace(0.55, 1.0, fade, dtype=np.float32)
    return np.concatenate([left, _soft_gap(sr, pause), right])


def _peak_limit(wav: np.ndarray, peak: float = 0.82) -> np.ndarray:
    wav = np.asarray(wav, dtype=np.float32)
    if wav.ndim > 1:
        wav = np.mean(wav, axis=-1)
    wav = wav - float(np.mean(wav))
    rms = float(np.sqrt(np.mean(wav**2))) if wav.size else 0.0
    if rms > 1e-6:
        wav = wav * (0.10 / rms)
    mag = float(np.max(np.abs(wav))) if wav.size else 0.0
    if mag > peak:
        wav = wav * (peak / mag)
    return wav


def speak(
    ref_wav: str,
    ref_text: str,
    gen_text: str,
    out_wav: str,
    nfe_step: int = 32,
    speed: float = 1.0,
) -> str:
    out = Path(out_wav)
    out.parent.mkdir(parents=True, exist_ok=True)
    tts = _load_tts()
    speed = max(0.7, min(1.4, float(speed)))
    # Tutorial clones run hot; ease default 1.00 toward a talking-head pace.
    line_speed = max(0.86, min(1.35, float(speed)))
    pieces: list[np.ndarray] = []
    marks: list[str] = []
    sr_out = 24000
    chunks = _punct_chunks(gen_text)
    print(json.dumps({"chunks": [f"{phrase} |{punct}" for phrase, punct in chunks], "speed": round(line_speed, 3)}), flush=True)
    for line, punct in chunks:
        spoken = line if line.endswith((".", "!", "?")) else f"{line}."
        kwargs = dict(
            ref_file=ref_wav,
            ref_text=ref_text,
            gen_text=spoken,
            file_wave=None,
            nfe_step=int(nfe_step),
            cfg_strength=1.5,
            sway_sampling_coef=-1.0,
            speed=line_speed,
            seed=0,
            remove_silence=False,
            cross_fade_duration=0.0,
            target_rms=0.0,
        )
        try:
            wav, sr_out, _ = tts.infer(**kwargs)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            kwargs["nfe_step"] = 16
            wav, sr_out, _ = tts.infer(**kwargs)
        pieces.append(_trim_edges(_peak_limit(np.asarray(wav, dtype=np.float32), 0.82), sr_out))
        marks.append(punct)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    if not pieces:
        raise RuntimeError("No speech generated")
    wav = pieces[0]
    for part, punct in zip(pieces[1:], marks[:-1]):
        pause = 0.16 if punct == "," else 0.32
        wav = _join_calm(wav, part, sr_out, pause)
    wav = _peak_limit(wav, 0.82)
    sf.write(str(out), wav, sr_out, subtype="PCM_16")
    print(str(out), flush=True)
    return str(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("clone")
    c.add_argument("--ref", required=True)
    c.add_argument("--out-dir", required=True)
    s = sub.add_parser("speak")
    s.add_argument("--ref", required=True)
    s.add_argument("--ref-text", required=True)
    s.add_argument("--text", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--nfe", type=int, default=32)
    s.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()
    if args.cmd == "clone":
        clone_prompt(args.ref, args.out_dir)
    else:
        ref_text = args.ref_text
        p = Path(ref_text)
        if p.exists() and p.suffix.lower() == ".txt":
            ref_text = p.read_text(encoding="utf-8").strip()
        speak(args.ref, ref_text, args.text, args.out, nfe_step=args.nfe, speed=args.speed)


if __name__ == "__main__":
    main()
