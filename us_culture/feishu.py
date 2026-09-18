from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

from us_culture.config import FeishuConfig
from us_culture.models import Briefing

logger = logging.getLogger("us_culture.feishu")


class FeishuClient:
    def __init__(self, config: FeishuConfig):
        if not config.app_id or not config.app_secret:
            raise RuntimeError("缺少 FEISHU_APP_ID / FEISHU_APP_SECRET")
        self.config = config
        self._token = ""
        self._expire_at = 0.0

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.config.base_url}{path}"
        response = httpx.request(method, url, timeout=60, **kwargs)
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"飞书接口失败 {path}：{payload.get('msg') or payload}")
        return payload

    def tenant_token(self) -> str:
        now = time.time()
        if self._token and now < self._expire_at - 60:
            return self._token
        payload = self._request(
            "POST",
            "/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.config.app_id, "app_secret": self.config.app_secret},
        )
        token = payload.get("tenant_access_token")
        if not token:
            raise RuntimeError("飞书未返回 tenant_access_token")
        self._token = token
        self._expire_at = now + int(payload.get("expire") or 7200)
        return self._token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tenant_token()}"}

    def list_chats(self) -> list[dict]:
        payload = self._request(
            "GET",
            "/open-apis/im/v1/chats",
            headers=self._auth_headers(),
            params={"page_size": 50},
        )
        return payload.get("data", {}).get("items") or []

    def upload_opus(self, opus_path: Path, duration_ms: int) -> str:
        with opus_path.open("rb") as fh:
            payload = self._request(
                "POST",
                "/open-apis/im/v1/files",
                headers=self._auth_headers(),
                data={
                    "file_type": "opus",
                    "file_name": opus_path.name,
                    "duration": str(duration_ms),
                },
                files={"file": (opus_path.name, fh, "audio/opus")},
            )
        file_key = payload.get("data", {}).get("file_key")
        if not file_key:
            raise RuntimeError("飞书未返回 file_key")
        return file_key

    def send_message(self, chat_id: str, msg_type: str, content: dict) -> str:
        payload = self._request(
            "POST",
            f"/open-apis/im/v1/messages?receive_id_type={self.config.receive_id_type}",
            headers=self._auth_headers(),
            json={
                "receive_id": chat_id,
                "msg_type": msg_type,
                "content": json.dumps(content, ensure_ascii=False),
            },
        )
        return payload.get("data", {}).get("message_id") or ""

    def push_briefing(self, briefing: Briefing, opus_path: Path, duration_ms: int) -> dict:
        if not self.config.chat_ids:
            raise RuntimeError("缺少 FEISHU_CHAT_IDS")
        file_key = self.upload_opus(opus_path, duration_ms)
        card = build_card(briefing, duration_ms)
        results = []
        for chat_id in self.config.chat_ids:
            card_id = self.send_message(chat_id, "interactive", card)
            audio_id = self.send_message(chat_id, "audio", {"file_key": file_key})
            results.append({"chat_id": chat_id, "card_message_id": card_id, "audio_message_id": audio_id})
            logger.info("已推送到飞书群 %s", chat_id)
        return {"file_key": file_key, "chats": results}


def _md(text: str) -> str:
    return (text or "").replace("*", "＊").replace("~", "～")


def build_card(briefing: Briefing, duration_ms: int) -> dict:
    elements: list[dict] = []
    for section in briefing.sections:
        lines = [f"**{section.category}**"]
        for index, item in enumerate(section.items, start=1):
            lines.append(f"{index}. **{_md(item.headline)}**\n{_md(item.takeaway)}")
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}})
        elements.append({"tag": "hr"})
    elements.append(
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**今日文化信号**\n{_md(briefing.culture_signal)}"},
        }
    )
    elements.append(
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**眼睛产品线观察**\n{_md(briefing.product_insight)}"},
        }
    )
    minutes = max(1, round(duration_ms / 60000))
    elements.append(
        {
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": f"下方语音约 {minutes} 分钟，可在群内直接播放"}],
        }
    )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": briefing.title},
        },
        "elements": elements,
    }
