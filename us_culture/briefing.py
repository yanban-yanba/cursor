from __future__ import annotations

import json
import logging
import re

from openai import OpenAI

from us_culture.config import CATEGORIES, LlmConfig
from us_culture.models import Briefing, BriefItem, BriefSection, TopicBundle
from us_culture.prompts import SYSTEM_PROMPT, build_user_prompt
from us_culture.fetchers import render_topic_prompt

logger = logging.getLogger("us_culture.briefing")

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _parse_json(text: str) -> dict:
    stripped = _FENCE_RE.sub("", text.strip())
    return json.loads(stripped)


def _validate(raw: dict, us_date: str) -> Briefing:
    missing = [key for key in ("title", "spoken_script", "sections", "culture_signal", "product_insight") if not raw.get(key)]
    if missing:
        raise RuntimeError(f"模型输出缺字段：{', '.join(missing)}")

    sections_raw = raw["sections"]
    if not isinstance(sections_raw, list):
        raise RuntimeError("模型输出 sections 不是列表")

    by_name = {section.get("category"): section for section in sections_raw if isinstance(section, dict)}
    sections: list[BriefSection] = []
    for category in CATEGORIES:
        section = by_name.get(category)
        if not section:
            raise RuntimeError(f"模型输出缺少栏目：{category}")
        items_raw = section.get("items") or []
        items = [
            BriefItem(headline=str(item.get("headline") or "").strip(), takeaway=str(item.get("takeaway") or "").strip())
            for item in items_raw
            if isinstance(item, dict)
        ]
        items = [item for item in items if item.headline]
        if len(items) < 2:
            raise RuntimeError(f"栏目 {category} 有效条目不足 2 条")
        sections.append(BriefSection(category=category, items=items[:3]))

    script = str(raw["spoken_script"]).strip()
    if len(script) < 200:
        raise RuntimeError("口播稿过短，不适合生成音频")

    return Briefing(
        title=str(raw["title"]).strip(),
        us_date=us_date,
        spoken_script=script,
        culture_signal=str(raw["culture_signal"]).strip(),
        product_insight=str(raw["product_insight"]).strip(),
        sections=sections,
    )


def generate_briefing(bundle: TopicBundle, llm: LlmConfig, audience: str, product_line: str, market: str) -> Briefing:
    if not llm.api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY，无法生成文化简报")

    client = OpenAI(api_key=llm.api_key, base_url=llm.base_url)
    user_prompt = build_user_prompt(audience, product_line, market, render_topic_prompt(bundle))
    logger.info("开始生成简报，模型 %s", llm.model)
    response = client.chat.completions.create(
        model=llm.model,
        temperature=0.4,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("模型返回空内容")
    try:
        raw = _parse_json(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"模型输出不是 JSON：{text[:300]}") from exc
    briefing = _validate(raw, bundle.us_date)
    logger.info("简报生成完成：%s", briefing.title)
    return briefing
