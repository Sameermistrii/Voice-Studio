# Voice Studio

Local **Windows** desktop app for **voice cloning**. You drop in a reference recording, clone that speaker (with permission), then generate new speech on your NVIDIA GPU.

No cloud TTS API key is required for cloned voices. Stock Indian voices use Microsoft Edge TTS (needs internet).

Repository: https://github.com/Sameermistrii/Voice-Studio

---

## Complete install requirements

Read this list before you clone the repo. The installer (`setup.bat`) checks Python 3.11 and ffmpeg, then installs everything else.

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

### Software you must install first (not bundled)

1. **Python 3.11 64-bit** (not 3.10, not 3.12, not 3.13)
   - https://www.python.org/downloads/release/python-3119/
   - During setup: tick **Add python.exe to PATH**
   - Disable the Windows **App execution aliases** for `python.exe` / `python3.exe` (Settings → Apps → Advanced app settings → App execution aliases) so the Store stub does not shadow real Python
   - Confirm in a **new** Command Prompt:
     ```bat
     python --version
     ```
     Must print `Python 3.11.x`

2. **Git**
   - https://git-scm.com/download/win
   - Needed only to clone this repository

3. **ffmpeg** (on PATH)
   - Recommended:
     ```bat
     winget install Gyan.FFmpeg
     ```
   - Or https://www.gyan.dev/ffmpeg/builds/ (full build), then add the `bin` folder to PATH
   - Confirm:
     ```bat
     ffmpeg -version
     ```

4. **NVIDIA Game Ready / Studio driver**
   - Recent driver with **CUDA 12.x** user-mode support
   - You do **not** need to install the full CUDA Toolkit or Visual Studio
   - Confirm:
     ```bat
     nvidia-smi
     ```
     Must show your GPU name and driver version

5. **Microsoft Visual C++ Redistributable 2015–2022 (x64)**
   - https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist
   - Needed by PyTorch / pywebview on many clean Windows installs

6. **Internet**
   - First install downloads PyPI packages, PyTorch cu121 wheels, Hugging Face weights, and (on first clone) Whisper `small`
   - Hugging Face: https://huggingface.co must be reachable
   - Stock Edge TTS voices also need internet at generate time

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
| Whisper small | faster-whisper (`small`) | Hugging Face cache | ~500 MB, **first clone only** |

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

1. Refuse to continue unless Python is **3.11** and `ffmpeg` is on PATH
2. Create `.venv` and install `requirements.txt`
3. Create `models/omnivoice-venv`, install CUDA torch + OmniVoice
4. Create `models/f5-venv`, install CUDA torch + F5-TTS + faster-whisper
5. Download OmniVoice and F5-TTS / Vocos weights

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
