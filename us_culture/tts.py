from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from pathlib import Path

import edge_tts

logger = logging.getLogger("us_culture.tts")


def _run(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return (result.stdout or "").strip()


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("未找到 ffmpeg / ffprobe，请安装后加入 PATH")


async def _synthesize(text: str, voice: str, rate: str, mp3_path: Path) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicate.save(str(mp3_path))


def synthesize_mp3(text: str, voice: str, rate: str, mp3_path: Path) -> Path:
    script = " ".join(text.split())
    if not script:
        raise RuntimeError("口播稿为空，无法合成音频")
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("开始合成语音：%s", voice)
    asyncio.run(_synthesize(script, voice, rate, mp3_path))
    if not mp3_path.exists() or mp3_path.stat().st_size == 0:
        raise RuntimeError("语音文件生成失败")
    logger.info("MP3 已写入 %s", mp3_path)
    return mp3_path


def convert_to_opus(mp3_path: Path, opus_path: Path) -> tuple[Path, int]:
    _require_ffmpeg()
    opus_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(mp3_path),
                "-acodec",
                "libopus",
                "-ac",
                "1",
                "-ar",
                "16000",
                str(opus_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr.strip() or "ffmpeg 转换 opus 失败") from exc
    duration_s = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(opus_path),
        ]
    )
    duration_ms = int(float(duration_s) * 1000)
    logger.info("OPUS 已写入 %s，时长 %s ms", opus_path, duration_ms)
    return opus_path, duration_ms
