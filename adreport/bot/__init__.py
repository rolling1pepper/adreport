"""Бот-минимум (aiogram 3): пересланный пост или ссылка → PDF + PNG в ответ.

Чужие апдейты отсекаются whitelist-миддлварью до роутинга. Никаких кампаний,
клавиатур и настроек — это v1.3+. Бот и Telethon-сессия живут в одном
процессе: постоянного демона в MVP нет.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware, Bot, Dispatcher, Router
from aiogram.types import BufferedInputFile, Message

from ..config import Config
from ..core.collector import (
    PostUnavailableError,
    collect_post,
    find_post_link,
)
from ..core.report.builder import build_report
from ..core.storage import Storage

router = Router()


@dataclass
class BotDeps:
    config: Config
    storage: Storage
    client: Any  # подключённый TelegramClient (Telethon)


class WhitelistMiddleware(BaseMiddleware):
    """Апдейты не из ALLOWED_IDS молча игнорируются до роутинга."""

    def __init__(self, allowed_ids: tuple[int, ...]):
        self._allowed = frozenset(allowed_ids)

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None or user.id not in self._allowed:
            return None
        return await handler(event, data)


def extract_post_ref(message: Message) -> tuple[str, int] | str:
    """Пересылка или ссылка → (канал, msg_id); иначе — текст подсказки."""
    origin = message.forward_origin
    if origin is not None:
        chat = getattr(origin, "chat", None)
        if chat is not None and getattr(chat, "type", None) == "channel":
            if chat.username:
                return chat.username, origin.message_id
            return (
                "Канал без публичного @username — по пересылке его счётчики "
                "не достать. Пришлите ссылку вида https://t.me/канал/123."
            )
        return (
            "Источник пересылки скрыт настройками канала. "
            "Пришлите ссылку на пост: https://t.me/канал/123."
        )
    found = find_post_link(message.text or message.caption or "")
    if found is not None:
        return found
    return (
        "Перешлите пост из публичного канала или пришлите ссылку "
        "вида https://t.me/канал/123 — в ответ соберу PDF-отчёт и PNG-карточку."
    )


@router.message()
async def handle_message(message: Message, deps: BotDeps) -> None:
    ref = extract_post_ref(message)
    if isinstance(ref, str):
        await message.answer(ref)
        return
    username, msg_id = ref

    await message.answer(f"Принял: t.me/{username}/{msg_id} — собираю отчёт…")

    config = deps.config
    post_row_id = deps.storage.get_or_create_post(username, msg_id)
    stale_note: str | None = None
    try:
        raw = await collect_post(
            deps.client, username, msg_id,
            media_dir=config.media_dir, tz=config.tz,
        )
        deps.storage.add_snapshot(post_row_id, raw)
    except PostUnavailableError as error:
        raw = deps.storage.latest_snapshot(username, msg_id)
        if raw is None:
            await message.answer(f"{error} Снапшотов этого поста в базе нет.")
            return
        stale_note = raw["collected_at"]

    data = build_report(
        raw,
        contact_link=config.contact_link,
        generated_at=datetime.now(ZoneInfo(config.tz)).isoformat(timespec="seconds"),
    )

    # WeasyPrint синхронный — не блокируем цикл бота
    from ..core.report.render import render_pdf, render_png_bytes

    pdf_bytes = await asyncio.to_thread(render_pdf, data)
    png_bytes = await asyncio.to_thread(render_png_bytes, data)
    deps.storage.save_report(
        post_row_id, data, hashlib.sha256(pdf_bytes).hexdigest()
    )

    stem = f"{username}_{msg_id}"
    caption = f"Отчёт {data.report_id} · данные на момент {data.data_as_of}"
    if stale_note:
        caption += "\nПост уже недоступен — использован последний сохранённый срез."
    await message.answer_photo(
        BufferedInputFile(png_bytes, filename=f"{stem}.png"),
        caption=caption,
    )
    await message.answer_document(
        BufferedInputFile(pdf_bytes, filename=f"{stem}.pdf"),
    )


async def run_bot(config: Config) -> None:
    """Поллинг бота с Telethon-клиентом в том же процессе."""
    import logging

    from telethon import TelegramClient

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    storage = Storage(config.db_path)
    client = TelegramClient(str(config.session_path), config.api_id, config.api_hash)
    async with client:
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Telethon-сессия не авторизована. Сначала выполните "
                "adreport post <ссылка> в интерактивном терминале."
            )
        bot = Bot(token=config.bot_token)
        dispatcher = Dispatcher()
        dispatcher.update.outer_middleware(WhitelistMiddleware(config.allowed_ids))
        dispatcher.include_router(router)
        deps = BotDeps(config=config, storage=storage, client=client)
        await dispatcher.start_polling(bot, deps=deps)
