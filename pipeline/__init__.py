from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"
MODELS_DIR = ROOT / "models"
OUTPUT_DIR = ROOT / "output"
UI_DIR = ROOT / "ui"
HARDWARE_PATH = MODELS_DIR / "hardware.json"
F5_VENV = MODELS_DIR / "f5-venv"
SADTALKER_VENV = MODELS_DIR / "sadtalker-venv"
OMNIVOICE_VENV = MODELS_DIR / "omnivoice-venv"
OPENVOICE_DIR = MODELS_DIR / "OpenVoice"
