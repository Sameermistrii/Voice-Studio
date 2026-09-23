"""Download k2-fsa/OmniVoice weights (VoiceStudio default engine)."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "models" / "omnivoice"

FILES = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "chat_template.jinja",
    "model.safetensors",
    "audio_tokenizer/config.json",
    "audio_tokenizer/preprocessor_config.json",
    "audio_tokenizer/model.safetensors",
]


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "audio_tokenizer").mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = DEST / name
        if dest.exists() and dest.stat().st_size > 1_000:
            print(f"have {name} ({dest.stat().st_size} bytes)", flush=True)
            continue
        print(f"downloading {name}", flush=True)
        cached = hf_hub_download("k2-fsa/OmniVoice", name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if Path(cached).resolve() != dest.resolve():
            shutil.copy2(cached, dest)
        print(dest, dest.stat().st_size, flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
