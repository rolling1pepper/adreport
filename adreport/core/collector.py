"""Коллектор: публичный пост по ссылке → сырой снапшот.

Работает от сессии любого аккаунта — публичные счётчики (просмотры,
пересылки, реакции, ответы, подписчики) видны без админ-доступа.
Результат — dict той же формы, что фикстуры v0.1: builder не различает,
пришли данные из Телеграма или из файла.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .gateway import tg

ALBUM_SPAN = 10  # соседи msg_id для поиска остальных сообщений галереи

_LINK_RE = re.compile(
    r"(?:https?://)?(?:t(?:elegram)?\.me|telegram\.dog)/"
    r"(?P<name>[A-Za-z][A-Za-z0-9_]{3,31})/(?P<msg_id>\d+)/?(?:[?#].*)?$"
)
_PRIVATE_LINK_RE = re.compile(r"(?:https?://)?t(?:elegram)?\.me/c/\d+/\d+")


class PostLinkError(ValueError):
    """Ссылка не похожа на публичный пост."""


class PostUnavailableError(RuntimeError):
    """Пост недоступен: удалён, скрыт или канал приватный."""


def parse_post_link(text: str) -> tuple[str, int]:
    """«https://t.me/durov/123» → ('durov', 123)."""
    text = text.strip()
    if _PRIVATE_LINK_RE.match(text):
        raise PostLinkError(
            "Это ссылка на приватный канал (t.me/c/…) — без членства в канале "
            "Телеграм не отдаёт по ней ничего. MVP работает с публичными постами."
        )
    match = _LINK_RE.match(text)
    if not match:
        raise PostLinkError(
            "Не удалось разобрать ссылку. Ожидается вид https://t.me/канал/123."
        )
    return match["name"], int(match["msg_id"])


def media_type_of(message) -> str | None:
    if getattr(message, "grouped_id", None):
        return "album"
    if getattr(message, "photo", None):
        return "photo"
    if getattr(message, "video", None):
        return "video"
    if getattr(message, "media", None):
        return "документ"
    return None


def reactions_of(message) -> list[dict]:
    """Разбивка реакций; кастомные эмодзи каналов идут агрегатом «…»."""
    reactions = getattr(message, "reactions", None)
    if not reactions or not reactions.results:
        return []
    result: list[dict] = []
    custom_total = 0
    for item in reactions.results:
        emoticon = getattr(item.reaction, "emoticon", None)
        if emoticon:
            result.append({"emoji": emoticon, "count": item.count})
        else:  # ReactionCustomEmoji — глифа нет, документ недоступен без клиента
            custom_total += item.count
    if custom_total:
        result.append({"emoji": "…", "count": custom_total})
    return result


def pick_album_anchor(messages: list) -> object:
    """Просмотры Телеграм вешает на первое сообщение галереи — берём min id."""
    return min(messages, key=lambda m: m.id)


def album_caption(messages: list) -> str:
    """Подпись альбома живёт на том сообщении, где есть текст."""
    for message in sorted(messages, key=lambda m: m.id):
        if getattr(message, "message", None):
            return message.message
    return ""


async def collect_post(
    client,
    username: str,
    msg_id: int,
    *,
    media_dir: Path,
    tz: str,
) -> dict:
    """Собрать публичный пост в сырой снапшот (форма — как у фикстур)."""
    entity = await tg(lambda: client.get_entity(username))
    message = await tg(lambda: client.get_messages(entity, ids=msg_id))
    if message is None:
        raise PostUnavailableError(
            f"Пост t.me/{username}/{msg_id} недоступен: удалён или скрыт."
        )

    # альбом: счётчики на первом сообщении галереи, подпись — где есть текст
    album = [message]
    if message.grouped_id:
        lo = max(1, msg_id - ALBUM_SPAN)
        neighbours = await tg(
            lambda: client.get_messages(entity, ids=list(range(lo, msg_id + ALBUM_SPAN + 1)))
        )
        album = [
            m for m in neighbours
            if m is not None and m.grouped_id == message.grouped_id
        ]
    anchor = pick_album_anchor(album)
    text = album_caption(album) if len(album) > 1 else (message.message or "")

    from telethon.tl.functions.channels import GetFullChannelRequest

    full = await tg(lambda: client(GetFullChannelRequest(entity)))
    subscribers = full.full_chat.participants_count or 0

    thumb_path = None
    with_media = next((m for m in sorted(album, key=lambda m: m.id) if m.media), None)
    if with_media is not None:
        media_dir.mkdir(parents=True, exist_ok=True)
        # thumb=-1 — самое крупное превью; скачиваем сразу: file_id протухает
        downloaded = await tg(
            lambda: with_media.download_media(
                file=str(media_dir / f"{username}_{msg_id}"), thumb=-1,
            )
        )
        thumb_path = str(downloaded) if downloaded else None

    zone = ZoneInfo(tz)
    collected_at = datetime.now(zone).isoformat(timespec="seconds")
    published_at = (
        anchor.date.astimezone(zone).isoformat(timespec="seconds")
        if anchor.date else None
    )

    return {
        "data_scope": "public",
        "demo": False,
        "collected_at": collected_at,
        "channel": {
            "title": getattr(entity, "title", username),
            "username": username,
            "subscribers": subscribers,
        },
        "post": {
            "msg_id": msg_id,
            "text": text,
            "media_type": media_type_of(message),
            "thumb_path": thumb_path,
            "published_at": published_at,
        },
        "counters": {
            "views": getattr(anchor, "views", None) or 0,
            "forwards": getattr(anchor, "forwards", None) or 0,
            "replies": anchor.replies.replies if getattr(anchor, "replies", None) else 0,
            "reactions": reactions_of(anchor),
        },
        "views_timeline": [],  # история просмотров — только у админа (v1.2)
    }
