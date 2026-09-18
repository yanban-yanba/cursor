from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Topic:
    category: str
    title: str
    summary: str
    source: str
    url: str
    published_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "Topic":
        return cls(
            category=raw["category"],
            title=raw["title"],
            summary=raw.get("summary") or "",
            source=raw.get("source") or "",
            url=raw.get("url") or "",
            published_at=raw.get("published_at"),
        )


@dataclass
class TopicBundle:
    run_date: str
    us_date: str
    items: list[Topic] = field(default_factory=list)

    def by_category(self) -> dict[str, list[Topic]]:
        grouped: dict[str, list[Topic]] = {}
        for item in self.items:
            grouped.setdefault(item.category, []).append(item)
        return grouped

    def to_dict(self) -> dict:
        return {
            "run_date": self.run_date,
            "us_date": self.us_date,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "TopicBundle":
        return cls(
            run_date=raw["run_date"],
            us_date=raw["us_date"],
            items=[Topic.from_dict(item) for item in raw.get("items") or []],
        )


@dataclass
class BriefItem:
    headline: str
    takeaway: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "BriefItem":
        return cls(headline=raw["headline"], takeaway=raw.get("takeaway") or "")


@dataclass
class BriefSection:
    category: str
    items: list[BriefItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"category": self.category, "items": [item.to_dict() for item in self.items]}

    @classmethod
    def from_dict(cls, raw: dict) -> "BriefSection":
        return cls(
            category=raw["category"],
            items=[BriefItem.from_dict(item) for item in raw.get("items") or []],
        )


@dataclass
class Briefing:
    title: str
    us_date: str
    spoken_script: str
    culture_signal: str
    product_insight: str
    sections: list[BriefSection] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "us_date": self.us_date,
            "spoken_script": self.spoken_script,
            "culture_signal": self.culture_signal,
            "product_insight": self.product_insight,
            "sections": [section.to_dict() for section in self.sections],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Briefing":
        return cls(
            title=raw["title"],
            us_date=raw["us_date"],
            spoken_script=raw["spoken_script"],
            culture_signal=raw.get("culture_signal") or "",
            product_insight=raw.get("product_insight") or "",
            sections=[BriefSection.from_dict(section) for section in raw.get("sections") or []],
        )
