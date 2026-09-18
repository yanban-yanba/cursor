from __future__ import annotations

import argparse
import logging
import sys

from us_culture.config import LOG_DIR, ensure_dirs, load_settings
from us_culture.feishu import FeishuClient
from us_culture.pipeline import fetch_today, latest_audio, run_pipeline
from us_culture.player import play_audio
from us_culture.scheduler import start_scheduler
from us_culture.webapp import run_web


def _setup_logging() -> None:
    ensure_dirs()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
        ],
    )


def main() -> None:
    _setup_logging()
    parser = argparse.ArgumentParser(description="美国本土文化音频定时推群")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_parser = sub.add_parser("run", help="抓取热点、生成简报、合成音频并推送飞书群")
    run_parser.add_argument("--skip-push", action="store_true", help="只生成，不推群")
    run_parser.add_argument("--play", action="store_true", help="生成本地播放")

    sub.add_parser("fetch", help="只抓取美区热点")
    sub.add_parser("play", help="播放最近一次音频简报")
    sub.add_parser("chats", help="列出机器人所在飞书群，用来填写 FEISHU_CHAT_IDS")

    serve_parser = sub.add_parser("serve", help="启动语音播放台，并开启每日定时推送")
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)

    args = parser.parse_args()
    if args.cmd == "fetch":
        bundle = fetch_today()
        print(f"已抓取 {len(bundle.items)} 条，日期 {bundle.run_date}")
        return
    if args.cmd == "run":
        path = run_pipeline(push=not args.skip_push, play=args.play)
        print(f"完成：{path}")
        return
    if args.cmd == "play":
        play_audio(latest_audio())
        return
    if args.cmd == "chats":
        settings = load_settings(require_feishu=True, require_chats=False)
        chats = FeishuClient(settings.feishu).list_chats()
        if not chats:
            raise RuntimeError("机器人还不在任何群里，请先把应用机器人拉进目标群")
        for chat in chats:
            print(f"{chat.get('chat_id')}\t{chat.get('name')}")
        return
    if args.cmd == "serve":
        start_scheduler()
        run_web(host=args.host, port=args.port)
        return
    raise RuntimeError(f"未知命令：{args.cmd}")


if __name__ == "__main__":
    main()
