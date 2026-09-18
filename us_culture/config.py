from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
DATA_DIR = ROOT / "data"
RUNS_DIR = DATA_DIR / "runs"
LOG_DIR = DATA_DIR / "logs"

CATEGORIES = ("社会", "科技", "影视", "音乐", "八卦")


@dataclass(frozen=True)
class BrandConfig:
    audience: str
    product_line: str
    market: str


@dataclass(frozen=True)
class ScheduleConfig:
    hour: int
    minute: int
    timezone: str


@dataclass(frozen=True)
class FetchConfig:
    per_category: int
    lookback_hours: int
    timeout_seconds: int


@dataclass(frozen=True)
class TtsConfig:
    voice: str
    rate: str


@dataclass(frozen=True)
class WebConfig:
    host: str
    port: int


@dataclass(frozen=True)
class FeishuConfig:
    base_url: str
    receive_id_type: str
    app_id: str
    app_secret: str
    chat_ids: tuple[str, ...]


@dataclass(frozen=True)
class LlmConfig:
    api_key: str
    base_url: str
    model: str


@dataclass(frozen=True)
class Settings:
    brand: BrandConfig
    schedule: ScheduleConfig
    fetch: FetchConfig
    tts: TtsConfig
    web: WebConfig
    feishu: FeishuConfig
    llm: LlmConfig


def _require(value: str, name: str) -> str:
    if not value:
        raise RuntimeError(f"缺少配置 {name}，请在 .env 中填写")
    return value


def _chat_ids(raw: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def load_settings(
    require_llm: bool = False,
    require_feishu: bool = False,
    require_chats: bool = True,
) -> Settings:
    load_dotenv(ROOT / ".env")
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    llm_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    llm_base = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
    llm_model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    if require_llm:
        _require(llm_key, "OPENAI_API_KEY")

    app_id = (os.getenv("FEISHU_APP_ID") or "").strip()
    app_secret = (os.getenv("FEISHU_APP_SECRET") or "").strip()
    chat_ids = _chat_ids(os.getenv("FEISHU_CHAT_IDS") or "")
    if require_feishu:
        _require(app_id, "FEISHU_APP_ID")
        _require(app_secret, "FEISHU_APP_SECRET")
        if require_chats and not chat_ids:
            raise RuntimeError("缺少配置 FEISHU_CHAT_IDS，请先运行 python -m us_culture chats")

    feishu_raw = raw.get("feishu") or {}
    return Settings(
        brand=BrandConfig(**raw["brand"]),
        schedule=ScheduleConfig(**raw["schedule"]),
        fetch=FetchConfig(**raw["fetch"]),
        tts=TtsConfig(**raw["tts"]),
        web=WebConfig(**raw["web"]),
        feishu=FeishuConfig(
            base_url=(feishu_raw.get("base_url") or "https://open.feishu.cn").rstrip("/"),
            receive_id_type=feishu_raw.get("receive_id_type") or "chat_id",
            app_id=app_id,
            app_secret=app_secret,
            chat_ids=chat_ids,
        ),
        llm=LlmConfig(api_key=llm_key, base_url=llm_base, model=llm_model),
    )


def ensure_dirs() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
