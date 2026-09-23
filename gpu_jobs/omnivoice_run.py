"""Zero-shot clone with k2-fsa OmniVoice — VoiceStudio's default engine."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import numpy as np
import soundfile as sf
import torch

ROOT = Path(__file__).resolve().parents[1]


def _peak_limit(wav: np.ndarray, peak: float = 0.82) -> np.ndarray:
    wav = np.asarray(wav, dtype=np.float32)
    if wav.ndim > 1:
        wav = wav.mean(axis=-1)
    wav = wav - float(np.mean(wav))
    rms = float(np.sqrt(np.mean(wav**2))) if wav.size else 0.0
    if rms > 1e-6:
        wav = wav * (0.10 / rms)
    mag = float(np.max(np.abs(wav))) if wav.size else 0.0
    if mag > peak:
        wav = wav * (peak / mag)
    return wav


def _language(text: str) -> str:
    return "hi" if re.search(r"[\u0900-\u097F]", text or "") else "en"


def _prep_script(text: str) -> str:
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"(?i)pyclips", "PyClips", cleaned)
    cleaned = re.sub(r"(?i)\bdm\b", "D M", cleaned)
    cleaned = re.sub(r"(?i)\bthem adjust\b", "then adjust", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    return cleaned.strip()


def _sentences(text: str) -> list[str]:
    cleaned = _prep_script(text)
    parts = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    out: list[str] = []
    for part in parts:
        line = " ".join(part.split()).strip()
        if not line:
            continue
        if line[-1] not in ".!?":
            line += "."
        out.append(line)
    return out or [cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."]


def _chunks(text: str) -> list[str]:
    """Pack a few sentences together so the model follows the script, not the prompt."""
    lines = _sentences(text)
    packed: list[str] = []
    buf: list[str] = []
    words = 0
    for line in lines:
        buf.append(line)
        words += len(line.split())
        if words >= 22 or len(buf) >= 3:
            packed.append(" ".join(buf))
            buf, words = [], 0
    if buf:
        packed.append(" ".join(buf))
    return packed


def _soft_gap(sr: int, seconds: float) -> np.ndarray:
    return np.zeros(max(1, int(sr * seconds)), dtype=np.float32)


def _load_model():
    from omnivoice import OmniVoice

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device.startswith("cuda") else torch.float32
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    kwargs = dict(
        device_map=device,
        dtype=dtype,
        asr_device="cpu",
        low_cpu_mem_usage=True,
    )
    local = ROOT / "models" / "omnivoice"
    weights = local / "model.safetensors"
    source = str(local) if weights.exists() and weights.stat().st_size > 1_000_000_000 else "k2-fsa/OmniVoice"
    print(json.dumps({"loading": source, "device": device}), flush=True)
    try:
        model = OmniVoice.from_pretrained(source, **kwargs)
    except TypeError:
        kwargs.pop("asr_device", None)
        kwargs.pop("low_cpu_mem_usage", None)
        model = OmniVoice.from_pretrained(source, **kwargs)
    model.eval()
    return model


def _prompt(model, ref_wav: str, ref_text: str):
    from omnivoice import VoiceClonePrompt

    prompt_pt = Path(ref_wav).with_name("omnivoice_prompt.pt")
    if prompt_pt.exists():
        try:
            return VoiceClonePrompt.load(str(prompt_pt))
        except Exception:
            prompt_pt.unlink(missing_ok=True)
    encoded = model.create_voice_clone_prompt(
        ref_audio=ref_wav, ref_text=(ref_text or "").strip()
    )
    try:
        encoded.save(str(prompt_pt))
    except Exception:
        pass
    return encoded


def _generate_line(model, prompt, text: str, speed: float, num_step: int, language: str):
    gen_kwargs = dict(
        text=text,
        voice_clone_prompt=prompt,
        speed=speed,
        num_step=int(num_step),
        language=language,
    )
    try:
        with torch.inference_mode():
            audio = model.generate(**gen_kwargs)
    except TypeError:
        gen_kwargs.pop("num_step", None)
        with torch.inference_mode():
            audio = model.generate(**gen_kwargs)
    wav = audio[0] if isinstance(audio, (list, tuple)) else audio
    return _peak_limit(np.asarray(wav, dtype=np.float32), 0.82)


def speak(
    ref_wav: str,
    ref_text: str,
    gen_text: str,
    out_wav: str,
    speed: float = 1.0,
    num_step: int = 16,
) -> str:
    out = Path(out_wav)
    out.parent.mkdir(parents=True, exist_ok=True)
    speed = max(0.7, min(1.4, float(speed)))
    lines = _chunks(gen_text)
    if not lines:
        raise RuntimeError("Type the text you want spoken")
    language = _language(" ".join(lines))
    print(json.dumps({"language": language, "lines": lines}), flush=True)
    model = _load_model()
    prompt = _prompt(model, ref_wav, ref_text)
    pieces: list[np.ndarray] = []
    try:
        for line in lines:
            pieces.append(_generate_line(model, prompt, line, speed, num_step, language))
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    except torch.cuda.OutOfMemoryError as exc:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        raise RuntimeError(
            "OmniVoice needs more GPU memory than this 4GB card has free. F5-TTS will be used instead."
        ) from exc
    wav = pieces[0]
    for part in pieces[1:]:
        wav = np.concatenate([wav, _soft_gap(24000, 0.28), part])
    wav = _peak_limit(wav, 0.82)
    sf.write(str(out), wav, 24000, subtype="PCM_16")
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print(json.dumps({"ok": True, "out": str(out), "engine": "omnivoice", "seconds": round(len(wav) / 24000, 2)}), flush=True)
    print(str(out), flush=True)
    return str(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", required=True)
    parser.add_argument("--ref-text", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--nfe", type=int, default=16)
    args = parser.parse_args()
    ref_text = args.ref_text
    p = Path(ref_text)
    if p.exists() and p.suffix.lower() == ".txt":
        ref_text = p.read_text(encoding="utf-8").strip()
    gen_text = args.text
    t = Path(gen_text)
    if t.exists() and t.suffix.lower() == ".txt":
        gen_text = t.read_text(encoding="utf-8")
    speak(args.ref, ref_text, gen_text, args.out, speed=args.speed, num_step=args.nfe)


if __name__ == "__main__":
    main()
