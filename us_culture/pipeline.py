from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from us_culture.briefing import generate_briefing
from us_culture.config import RUNS_DIR, Settings, ensure_dirs, load_settings
from us_culture.fetchers import fetch_topics
from us_culture.feishu import FeishuClient
from us_culture.models import Briefing, TopicBundle
from us_culture.player import play_audio
from us_culture.tts import convert_to_opus, synthesize_mp3

logger = logging.getLogger("us_culture.pipeline")
_job_lock = threading.Lock()


def current_dates(timezone_name: str) -> tuple[str, str]:
    now_local = datetime.now(ZoneInfo(timezone_name))
    now_us = datetime.now(ZoneInfo("America/New_York"))
    return now_local.date().isoformat(), now_us.date().isoformat()


def run_dir_for(run_date: str) -> Path:
    path = RUNS_DIR / run_date
    path.mkdir(parents=True, exist_ok=True)
    return path


def _dump(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_status(run_dir: Path, **fields) -> None:
    path = run_dir / "status.json"
    current = {}
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
    current.update(fields)
    _dump(path, current)


def fetch_today(settings: Settings | None = None) -> TopicBundle:
    if not _job_lock.acquire(blocking=False):
        raise RuntimeError("已有任务在执行")
    try:
        return _fetch_today(settings)
    finally:
        _job_lock.release()


def _fetch_today(settings: Settings | None = None) -> TopicBundle:
    settings = settings or load_settings()
    ensure_dirs()
    run_date, us_date = current_dates(settings.schedule.timezone)
    run_dir = run_dir_for(run_date)
    _write_status(run_dir, step="fetch", started_at=datetime.now().isoformat())
    bundle = fetch_topics(settings.fetch, run_date, us_date)
    _dump(run_dir / "topics.json", bundle.to_dict())
    _write_status(run_dir, step="fetched", topic_count=len(bundle.items))
    return bundle


def run_pipeline(*, push: bool, play: bool) -> Path:
    if not _job_lock.acquire(blocking=False):
        raise RuntimeError("已有任务在执行")
    try:
        return _run_pipeline(push=push, play=play)
    finally:
        _job_lock.release()


def _run_pipeline(*, push: bool, play: bool) -> Path:
    settings = load_settings(require_llm=True, require_feishu=push)
    ensure_dirs()
    run_date, us_date = current_dates(settings.schedule.timezone)
    run_dir = run_dir_for(run_date)
    _write_status(
        run_dir,
        step="start",
        started_at=datetime.now().isoformat(),
        push=push,
        error=None,
        finished_at=None,
    )
    try:
        bundle = fetch_topics(settings.fetch, run_date, us_date)
        _dump(run_dir / "topics.json", bundle.to_dict())
        _write_status(run_dir, step="fetched", topic_count=len(bundle.items))

        briefing = generate_briefing(
            bundle,
            settings.llm,
            settings.brand.audience,
            settings.brand.product_line,
            settings.brand.market,
        )
        _dump(run_dir / "briefing.json", briefing.to_dict())
        (run_dir / "script.txt").write_text(briefing.spoken_script, encoding="utf-8")
        _write_status(run_dir, step="briefed", title=briefing.title)

        mp3_path = run_dir / "briefing.mp3"
        synthesize_mp3(briefing.spoken_script, settings.tts.voice, settings.tts.rate, mp3_path)
        opus_path, duration_ms = convert_to_opus(mp3_path, run_dir / "briefing.opus")
        _write_status(run_dir, step="audio", duration_ms=duration_ms)

        if play:
            play_audio(mp3_path)

        if push:
            result = FeishuClient(settings.feishu).push_briefing(briefing, opus_path, duration_ms)
            _dump(run_dir / "feishu.json", result)
            _write_status(run_dir, step="pushed", feishu=result)

        _write_status(run_dir, step="done", finished_at=datetime.now().isoformat())
        logger.info("流水线完成：%s", run_dir)
        return run_dir
    except Exception as exc:
        _write_status(run_dir, error=str(exc), finished_at=datetime.now().isoformat())
        raise


def load_bundle(run_dir: Path) -> TopicBundle | None:
    path = run_dir / "topics.json"
    if not path.exists():
        return None
    return TopicBundle.from_dict(json.loads(path.read_text(encoding="utf-8")))


def load_briefing(run_dir: Path) -> Briefing | None:
    path = run_dir / "briefing.json"
    if not path.exists():
        return None
    return Briefing.from_dict(json.loads(path.read_text(encoding="utf-8")))


def load_status(run_dir: Path) -> dict:
    path = run_dir / "status.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def list_runs() -> list[str]:
    if not RUNS_DIR.exists():
        return []
    dates = [path.name for path in RUNS_DIR.iterdir() if path.is_dir() and (path / "topics.json").exists()]
    return sorted(dates, reverse=True)


def latest_audio() -> Path:
    for date in list_runs():
        mp3 = RUNS_DIR / date / "briefing.mp3"
        if mp3.exists():
            return mp3
    raise FileNotFoundError("还没有生成过音频简报")
