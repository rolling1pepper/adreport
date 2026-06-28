"""Сборка ReportData из сырого снапшота.

Снапшот — это то, что пишет коллектор (v0.2) или лежит в фикстуре (v0.1):
словарь с каналом, постом, счётчиками и, если есть, историей просмотров.
Builder — единственное место, где считаются метрики и нормализуется текст.
"""

from __future__ import annotations

import re
import secrets

from ..metrics import age_hours, err_pct, reach_pct
from ..models import (
    SCHEMA_VERSION,
    ChannelInfo,
    Metrics,
    PostInfo,
    Reaction,
    ReportData,
    ViewsPoint,
)

PREVIEW_MAX_CHARS = 160
MAX_REACTION_ROWS = 4

# эмодзи вырезаются при нормализации: WeasyPrint не рисует цветные глифы,
# а twemoji-рендеринг отложен в v1.3
_EMOJI_RE = re.compile(
    "["
    "\U0001f000-\U0001faff"  # emoji SMP: смайлы, жесты, объекты
    "\U00002600-\U000027bf"  # misc symbols + dingbats
    "\U00002b00-\U00002bff"  # стрелки, звёзды
    "︎️‍⃣"  # variation selectors, ZWJ, keycap
    "]+"
)


def normalize_preview(text: str, max_chars: int = PREVIEW_MAX_CHARS) -> str:
    """Вырезать эмодзи, схлопнуть пробелы, обрезать по границе слова."""
    text = _EMOJI_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.:;!?…»)])", r"\1", text)  # «ленты  :» после эмодзи → «ленты:»
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if " " in cut:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip(" ,;:—-") + "…"


def top_reactions(raw: list[dict]) -> tuple[Reaction, ...]:
    """Топ реакций по убыванию; хвост длиннее MAX_REACTION_ROWS — в агрегат «…»."""
    ordered = sorted(
        (Reaction(emoji=r["emoji"], count=int(r["count"])) for r in raw),
        key=lambda r: r.count,
        reverse=True,
    )
    if len(ordered) <= MAX_REACTION_ROWS:
        return tuple(ordered)
    head = ordered[: MAX_REACTION_ROWS - 1]
    rest = sum(r.count for r in ordered[MAX_REACTION_ROWS - 1:])
    return (*head, Reaction(emoji="…", count=rest))


def build_report(
    raw: dict,
    *,
    contact_link: str | None = None,
    generated_at: str | None = None,
) -> ReportData:
    """Снапшот → замороженный ReportData.

    generated_at по умолчанию равен collected_at снапшота: демо и golden-тесты
    воспроизводимы байт в байт. Живой сбор (v0.2) передаёт реальное время.
    """
    channel_raw = raw["channel"]
    post_raw = raw["post"]
    counters = raw["counters"]

    reactions = top_reactions(counters.get("reactions", []))
    reactions_total = sum(int(r["count"]) for r in counters.get("reactions", []))
    views = int(counters["views"])
    forwards = int(counters.get("forwards", 0))
    replies = int(counters.get("replies", 0))
    collected_at = raw["collected_at"]
    published_at = post_raw.get("published_at")

    metrics = Metrics(
        views=views,
        reach_pct=reach_pct(views, int(channel_raw["subscribers"])),
        forwards=forwards,
        reactions_total=reactions_total,
        replies=replies,
        err_pct=err_pct(views, reactions_total, forwards, replies),
        age_hours=age_hours(published_at, collected_at) if published_at else None,
    )

    username = channel_raw["username"].lstrip("@")
    msg_id = int(post_raw["msg_id"])

    return ReportData(
        schema_version=SCHEMA_VERSION,
        report_id=raw.get("report_id") or f"r_{secrets.token_hex(3)}",
        generated_at=generated_at or collected_at,
        data_as_of=collected_at,
        data_scope=raw["data_scope"],
        demo=bool(raw.get("demo", False)),
        channel=ChannelInfo(
            title=channel_raw["title"],
            username=username,
            subscribers=int(channel_raw["subscribers"]),
        ),
        post=PostInfo(
            url=f"https://t.me/{username}/{msg_id}",
            msg_id=msg_id,
            text_preview=normalize_preview(post_raw.get("text", "")),
            media_type=post_raw.get("media_type"),
            thumb_path=post_raw.get("thumb_path"),
            published_at=published_at,
        ),
        metrics=metrics,
        reactions=reactions,
        views_timeline=tuple(
            ViewsPoint(hours=float(h), views=int(v))
            for h, v in raw.get("views_timeline", [])
        ),
        contact_link=contact_link,
    )
