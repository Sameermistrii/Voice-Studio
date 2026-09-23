from __future__ import annotations

import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def run_ffmpeg(args: list[str], timeout: int | None = None) -> None:
    try:
        proc = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"ffmpeg timed out: {' '.join(args[:6])}") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-4000:]
        raise FFmpegError(tail or f"ffmpeg failed ({proc.returncode})")


def probe_duration(ffmpeg: str, path: Path) -> float:
    ffprobe = ffmpeg.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
    cmd = [
        ffprobe if Path(ffprobe).exists() or ffprobe.endswith("ffprobe") else ffmpeg,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    if not (ffprobe.endswith("ffprobe") or ffprobe.endswith("ffprobe.exe")):
        cmd = [
            ffmpeg,
            "-i",
            str(path),
            "-f",
            "null",
            "-",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        for line in (proc.stderr or "").splitlines()[::-1]:
            if "Duration:" in line:
                stamp = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = stamp.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
        return 0.0
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float((proc.stdout or "0").strip().splitlines()[0])
    except (ValueError, IndexError):
        return 0.0
