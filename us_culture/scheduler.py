from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from us_culture.config import load_settings
from us_culture.pipeline import run_pipeline

logger = logging.getLogger("us_culture.scheduler")

_scheduler: BackgroundScheduler | None = None


def job() -> None:
    logger.info("定时任务启动：抓取并推送今日简报")
    run_pipeline(push=True, play=False)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    settings = load_settings()
    scheduler = BackgroundScheduler(timezone=settings.schedule.timezone)
    scheduler.add_job(
        job,
        CronTrigger(
            hour=settings.schedule.hour,
            minute=settings.schedule.minute,
            timezone=settings.schedule.timezone,
        ),
        id="daily_us_culture_push",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "定时任务已启动：每天 %02d:%02d %s",
        settings.schedule.hour,
        settings.schedule.minute,
        settings.schedule.timezone,
    )
    return scheduler


def next_run_iso() -> str | None:
    if _scheduler is None:
        return None
    job_item = _scheduler.get_job("daily_us_culture_push")
    if job_item is None or job_item.next_run_time is None:
        return None
    return job_item.next_run_time.isoformat()
