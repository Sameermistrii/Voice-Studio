"""Download F5-TTS v1 Base + Vocos into models/f5tts (no Xet)."""
from __future__ import annotations

import os

os.environ["HF_HUB_DISABLE_XET"] = "1"

from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
F5 = ROOT / "models" / "f5tts"
CKPT = F5 / "F5TTS_v1_Base"
VOCOS = F5 / "vocos"


def _have(path: Path, min_bytes: int) -> bool:
    return path.exists() and path.stat().st_size >= min_bytes


def main() -> None:
    CKPT.mkdir(parents=True, exist_ok=True)
    VOCOS.mkdir(parents=True, exist_ok=True)
    weights = CKPT / "model_1250000.safetensors"
    vocab = CKPT / "vocab.txt"
    if not _have(weights, 500_000_000):
        print("f5 weights", flush=True)
        hf_hub_download(
            "SWivid/F5-TTS",
            "F5TTS_v1_Base/model_1250000.safetensors",
            local_dir=str(F5),
        )
    else:
        print("f5 weights already present", flush=True)
    if not _have(vocab, 100):
        print("f5 vocab", flush=True)
        hf_hub_download(
            "SWivid/F5-TTS",
            "F5TTS_v1_Base/vocab.txt",
            local_dir=str(F5),
        )
    if not _have(VOCOS / "pytorch_model.bin", 1_000_000):
        print("vocos", flush=True)
        hf_hub_download("charactr/vocos-mel-24khz", "config.yaml", local_dir=str(VOCOS))
        hf_hub_download("charactr/vocos-mel-24khz", "pytorch_model.bin", local_dir=str(VOCOS))
    else:
        print("vocos already present", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
