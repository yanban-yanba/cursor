from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("us_culture.player")


def play_audio(path: Path) -> None:
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"音频不存在：{path}")
    logger.info("开始播放 %s", path)
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    opener = "xdg-open" if sys.platform == "linux" else "open"
    subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
