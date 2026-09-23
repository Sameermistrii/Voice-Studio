# Voice Studio

Local **Windows** desktop app for **voice cloning**. You drop in a reference recording, clone that speaker (with permission), then generate new speech on your NVIDIA GPU.

No cloud TTS API key is required for cloned voices. Stock Indian voices use Microsoft Edge TTS (needs internet).

Repository: https://github.com/Sameermistrii/Voice-Studio

---

## Complete install requirements

Double-click **`setup.bat`**. It downloads every app file automatically (Python packages, CUDA PyTorch, OmniVoice, F5-TTS, Vocos, Whisper). If Python 3.11 or ffmpeg is missing, it tries to install them with **winget**.

You still need a Windows PC with an **NVIDIA GPU driver** already installed. The installer will not flash a GPU driver.

### Computer (hardware)

| Item | Required | Notes |
| --- | --- | --- |
| OS | Windows 10 or 11, **64-bit** | Not tested on macOS or Linux |
| GPU | NVIDIA GPU, **at least 4 GB VRAM** | Tested on RTX 3050 Laptop (4 GB) |
| RAM | **16 GB** or more | 8 GB will swap and often fail |
| Disk | **~15 GB free** on the drive you install to | Two CUDA venvs + OmniVoice + F5-TTS + Whisper |
| CPU | Any modern 64-bit CPU | Whisper `small` runs on CPU during clone |
| Power | Laptop plugged in | GPU jobs are slow/unstable on battery |

A dedicated GPU is required. CPU-only PyTorch will not run the clone engines as shipped.

### What `setup.bat` downloads for you

Internet is required. Leave the window open (30–90 minutes on first run).

- Python 3.11 (via winget, if missing)
- ffmpeg (via winget, if missing)
- VC++ 2015–2022 x64 (via winget, if missing)
- UI packages (`requirements.txt`)
- OmniVoice venv + **torch 2.5.1+cu121**
- F5-TTS venv + **torch 2.5.1+cu121**
- OmniVoice weights (`k2-fsa/OmniVoice` → `models/omnivoice/`)
- F5-TTS v1 Base + Vocos (`models/f5tts/`)
- Whisper `small` (used when cloning)

### Software that is not auto-installed

1. **NVIDIA Game Ready / Studio driver** — install from NVIDIA, then `nvidia-smi` must work. No CUDA Toolkit needed.
2. **Git** — only if you clone with `git clone`. A GitHub ZIP extract works without Git.
3. **winget / App Installer** — comes with Windows 10/11. Needed for the Python/ffmpeg auto-install.

If winget cannot install Python 3.11: https://www.python.org/downloads/release/python-3119/ (tick **Add python.exe to PATH**, turn off Microsoft Store **python.exe** aliases).

### Python packages (installed for you)

Do not `pip install` these into system Python. The installer creates **three isolated venvs**.

| Venv | File | What it is |
| --- | --- | --- |
| `.venv` | `requirements.txt` | Desktop UI: pywebview, edge-tts, numpy, soundfile, pyyaml, huggingface_hub |
| `models/omnivoice-venv` | `requirements-omnivoice.txt` | k2-fsa OmniVoice + `transformers>=5.3` + **torch 2.5.1+cu121** |
| `models/f5-venv` | `requirements-f5.txt` | F5-TTS, faster-whisper, librosa + **torch 2.5.1+cu121** |

OmniVoice and F5 **cannot share one venv** (conflicting `transformers` versions). Torch is installed twice on purpose.

Pinned CUDA torch (both GPU venvs):

```text
torch==2.5.1+cu121
torchaudio==2.5.1+cu121
index: https://download.pytorch.org/whl/cu121
```

### Model weights (downloaded for you)

| Model | Source | Local path | Size (approx.) |
| --- | --- | --- | --- |
| OmniVoice | `k2-fsa/OmniVoice` | `models/omnivoice/` | ~2.5 GB + tokenizer |
| F5-TTS v1 Base | `SWivid/F5-TTS` | `models/f5tts/F5TTS_v1_Base/` | ~1.3 GB |
| Vocos vocoder | `charactr/vocos-mel-24khz` | `models/f5tts/vocos/` | ~50 MB |
| Whisper small | faster-whisper (`small`) | Hugging Face cache | ~500 MB, downloaded by `setup.bat` |

OmniVoice **weights are CC-BY-NC-4.0** (non-commercial). See `NOTICE`.

### Optional environment variables

| Variable | When to set |
| --- | --- |
| `HF_HOME` | Put the Hugging Face cache on another drive (example: `D:\HuggingFace`) if `C:` is small |
| `HF_HUB_DISABLE_XET=1` | Already set by the installer and launcher. Stops broken Xet downloads. |
| `HF_TOKEN` | Only if Hugging Face starts requiring login for a model |

`Start Voice Studio.bat` sets `HF_HOME=D:\HuggingFace` automatically **if that folder already exists**.

---

## Install (Windows)

Open **Command Prompt** or PowerShell in a folder with 15 GB free.

```bat
git clone https://github.com/Sameermistrii/Voice-Studio.git
cd Voice-Studio
setup.bat
```

Or:

```powershell
python gpu_jobs\install.py
```

The installer will:

1. Install Python 3.11 and ffmpeg with winget if they are missing
2. Create `.venv` and install `requirements.txt`
3. Create `models/omnivoice-venv`, install CUDA torch + OmniVoice
4. Create `models/f5-venv`, install CUDA torch + F5-TTS + faster-whisper
5. Download OmniVoice, F5-TTS, Vocos, and Whisper weights

Expect **30–90 minutes** depending on GPU driver, disk, and network. PyTorch wheels are large.

### Launch

Double-click **`Start Voice Studio.bat`**

or:

```bat
.venv\Scripts\python.exe app.py
```

---

## Manual install (same result, step by step)

Use this if `setup.bat` fails and you need to rerun one step.

```bat
python --version
ffmpeg -version
nvidia-smi

python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

python gpu_jobs\setup_omnivoice.py
python gpu_jobs\setup_f5.py

models\omnivoice-venv\Scripts\python.exe gpu_jobs\download_omnivoice.py
models\f5-venv\Scripts\python.exe gpu_jobs\download_f5.py

.venv\Scripts\python.exe app.py
```

---

## Use

1. Launch Voice Studio
2. **Clone** — pick a WAV/MP3 of the speaker (clean speech, **at least ~6 seconds**, one person, little music)
3. Name the clone (you can keep several named voices)
4. **Generate** — paste script, pick the clone, optional speed / pitch
5. WAV is written under `output/voice-YYYYMMDD-HHMMSS/speech.wav`

Clone other people **only with permission**.

If OmniVoice is missing, generate falls back to F5-TTS.

---

## Layout after install

```text
Voice-Studio/
  app.py / desktop.py     launcher + pywebview UI
  ui/                     HTML / JS / CSS
  pipeline/               clone + TTS glue
  gpu_jobs/               venv setup, downloads, GPU workers
  requirements*.txt
  .venv/                  UI Python (created)
  models/omnivoice-venv/  OmniVoice GPU env (created)
  models/f5-venv/         F5-TTS GPU env (created)
  models/omnivoice/       OmniVoice weights (downloaded)
  models/f5tts/           F5-TTS + Vocos (downloaded)
  voice/cloned/           your clones (local only, gitignored)
  output/                 generated WAV (gitignored)
```

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `python` opens Microsoft Store | Turn off App execution aliases; reinstall Python 3.11 with PATH |
| `Python 3.11 is required` | You are on 3.12/3.13. Install 3.11 and call it explicitly: `py -3.11 gpu_jobs\install.py` |
| `ffmpeg missing` | `winget install Gyan.FFmpeg`, close and reopen the terminal |
| `CUDA venv` / F5 missing | `python gpu_jobs\setup_f5.py` |
| `torch.cuda.is_available()` is False | Update NVIDIA driver; do not use CPU torch; venvs must **not** use system-site-packages |
| Hugging Face download stuck at 0 bytes | Keep `HF_HUB_DISABLE_XET=1`; retry the matching `download_*.py` |
| Out of VRAM | Close games / Chrome GPU tabs; generate shorter paragraphs |
| Clone sounds like another language | Use an English reference with no background music; keep scripts in the same language as the sample |
| Edge TTS voices fail | Need internet; cloned voices do not use Edge |

---

## License

Application code: **MIT** (`LICENSE`).

Upstream models: see **`NOTICE`**. OmniVoice weights are **CC-BY-NC**. Do not ship those weights inside a paid product without a license from the weight owners.
