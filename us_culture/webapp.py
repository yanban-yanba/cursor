from __future__ import annotations

import logging
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, abort, jsonify, render_template, request, send_file

from us_culture.config import CATEGORIES, RUNS_DIR, load_settings
from us_culture.pipeline import (
    current_dates,
    fetch_today,
    list_runs,
    load_briefing,
    load_bundle,
    load_status,
    run_pipeline,
)
from us_culture.scheduler import next_run_iso

logger = logging.getLogger("us_culture.web")

ALLOWED_MEDIA = {"briefing.mp3", "briefing.opus", "script.txt"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _payload_for(date: str) -> dict:
    settings = load_settings()
    run_dir = RUNS_DIR / date
    bundle = load_bundle(run_dir) if run_dir.exists() else None
    briefing = load_briefing(run_dir) if run_dir.exists() else None
    status = load_status(run_dir) if run_dir.exists() else {}
    has_audio = (run_dir / "briefing.mp3").exists()
    next_iso = next_run_iso()
    next_text = None
    if next_iso:
        next_dt = datetime.fromisoformat(next_iso)
        next_text = f"{next_dt.strftime('%Y-%m-%d %H:%M')} {settings.schedule.timezone}"
    return {
        "date": date,
        "categories": list(CATEGORIES),
        "schedule": {
            "hour": settings.schedule.hour,
            "minute": settings.schedule.minute,
            "timezone": settings.schedule.timezone,
            "next_run": next_iso,
            "next_run_text": next_text,
        },
        "brand": {
            "audience": settings.brand.audience,
            "product_line": settings.brand.product_line,
            "market": settings.brand.market,
        },
        "topics": bundle.to_dict() if bundle else None,
        "briefing": briefing.to_dict() if briefing else None,
        "status": status,
        "has_audio": has_audio,
        "audio_url": f"/media/{date}/briefing.mp3" if has_audio else None,
    }


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        settings = load_settings()
        today, us_date = current_dates(settings.schedule.timezone)
        dates = list_runs()
        active = request.args.get("date") or (today if today in dates else (dates[0] if dates else today))
        return render_template(
            "index.html",
            today=today,
            us_date=us_date,
            active_date=active,
            history=dates,
        )

    @app.get("/api/today")
    def api_today():
        settings = load_settings()
        today, _ = current_dates(settings.schedule.timezone)
        date = request.args.get("date") or today
        return jsonify(_payload_for(date))

    @app.get("/api/history")
    def api_history():
        return jsonify({"dates": list_runs()})

    @app.post("/api/fetch")
    def api_fetch():
        try:
            bundle = fetch_today()
        except Exception as exc:
            logger.exception("抓取失败")
            status = 409 if "已有任务在执行" in str(exc) else 500
            return jsonify({"ok": False, "error": str(exc)}), status
        return jsonify({"ok": True, "date": bundle.run_date, "count": len(bundle.items)})

    @app.post("/api/run")
    def api_run():
        push = request.json.get("push", True) if request.is_json else True
        try:
            run_dir = run_pipeline(push=bool(push), play=False)
        except Exception as exc:
            logger.exception("流水线失败")
            status = 409 if "已有任务在执行" in str(exc) else 500
            return jsonify({"ok": False, "error": str(exc)}), status
        return jsonify({"ok": True, "date": run_dir.name})

    @app.get("/media/<date>/<name>")
    def media(date: str, name: str):
        if not _DATE_RE.fullmatch(date) or name not in ALLOWED_MEDIA:
            abort(404)
        path = (RUNS_DIR / date / name).resolve()
        if RUNS_DIR.resolve() not in path.parents or not path.exists():
            abort(404)
        mimetypes = {
            "briefing.mp3": "audio/mpeg",
            "briefing.opus": "audio/opus",
            "script.txt": "text/plain; charset=utf-8",
        }
        return send_file(path, mimetype=mimetypes[name])

    @app.get("/health")
    def health():
        settings = load_settings()
        now = datetime.now(ZoneInfo(settings.schedule.timezone)).isoformat()
        return jsonify({"ok": True, "now": now, "next_run": next_run_iso()})

    return app


def run_web(host: str | None = None, port: int | None = None) -> None:
    settings = load_settings()
    app = create_app()
    app.run(
        host=host or settings.web.host,
        port=port or settings.web.port,
        debug=False,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    run_web()
