"""Конфиг из .env: канал-агностик — имя, контакт и таймзона не зашиты в код."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class Config:
    api_id: int | None
    api_hash: str | None
    bot_token: str | None
    allowed_ids: tuple[int, ...]
    channel_name: str | None  # брендинг шапки/футера, не данные канала
    contact_link: str | None
    tz: str
    session_path: Path
    db_path: Path
    media_dir: Path


def load_config() -> Config:
    load_dotenv(REPO_ROOT / ".env")

    api_id = os.environ.get("API_ID", "").strip()
    allowed = os.environ.get("ALLOWED_IDS", "").strip()

    return Config(
        api_id=int(api_id) if api_id else None,
        api_hash=os.environ.get("API_HASH", "").strip() or None,
        bot_token=os.environ.get("BOT_TOKEN", "").strip() or None,
        allowed_ids=tuple(
            int(part) for part in allowed.split(",") if part.strip()
        ),
        channel_name=os.environ.get("CHANNEL_NAME", "").strip() or None,
        contact_link=os.environ.get("CONTACT_LINK", "").strip() or None,
        tz=os.environ.get("TZ", "").strip() or "Europe/Moscow",
        session_path=REPO_ROOT / "adreport.session",
        db_path=REPO_ROOT / "adreport.db",
        media_dir=REPO_ROOT / "media",
    )
