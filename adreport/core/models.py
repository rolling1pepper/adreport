"""Замороженный контракт ReportData.

Единственный источник данных для всех рендереров: из одного JSON собирается
и PDF, и PNG-карточка, а старые отчёты рендерятся и через год — поэтому
schema_version и никаких «живых» объектов внутри.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

SCHEMA_VERSION = 1

# бейдж полноты данных
SCOPE_FULL = "full"
SCOPE_PUBLIC = "public"


@dataclass(frozen=True, slots=True)
class ChannelInfo:
    title: str
    username: str  # без @
    subscribers: int


@dataclass(frozen=True, slots=True)
class PostInfo:
    url: str
    msg_id: int
    text_preview: str
    media_type: str | None = None  # photo | video | album | None (текст)
    thumb_path: str | None = None  # локальная миниатюра: file_id протухает вместе с постом
    published_at: str | None = None  # ISO 8601 с таймзоной


@dataclass(frozen=True, slots=True)
class Reaction:
    emoji: str  # «…» — агрегат «прочие»
    count: int


@dataclass(frozen=True, slots=True)
class Metrics:
    views: int
    reach_pct: float
    forwards: int
    reactions_total: int
    replies: int
    err_pct: float
    age_hours: float | None  # возраст поста на момент среза


@dataclass(frozen=True, slots=True)
class ViewsPoint:
    hours: float
    views: int


@dataclass(frozen=True, slots=True)
class ReportData:
    schema_version: int
    report_id: str
    generated_at: str  # ISO 8601
    data_as_of: str  # «данные на момент» — время снапшота
    data_scope: str  # SCOPE_FULL | SCOPE_PUBLIC
    demo: bool
    channel: ChannelInfo
    post: PostInfo
    metrics: Metrics
    reactions: tuple[Reaction, ...]
    views_timeline: tuple[ViewsPoint, ...]  # пусто — истории просмотров нет
    contact_link: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        # сортировка ключей и фиксированные разделители — чтобы sha256 отчёта
        # был стабилен между запусками
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_dict(cls, d: dict) -> "ReportData":
        return cls(
            schema_version=d["schema_version"],
            report_id=d["report_id"],
            generated_at=d["generated_at"],
            data_as_of=d["data_as_of"],
            data_scope=d["data_scope"],
            demo=d["demo"],
            channel=ChannelInfo(**d["channel"]),
            post=PostInfo(**d["post"]),
            metrics=Metrics(**d["metrics"]),
            reactions=tuple(Reaction(**r) for r in d["reactions"]),
            views_timeline=tuple(ViewsPoint(**p) for p in d["views_timeline"]),
            contact_link=d.get("contact_link"),
        )

    @classmethod
    def from_json(cls, raw: str) -> "ReportData":
        return cls.from_dict(json.loads(raw))
