"""Jinja-фильтры форматирования: русская типографика чисел, дат и склонений."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

NBSP = " "


def fmt_int(value: int | float) -> str:
    """34800 → «34 800» (неразрывный пробел)."""
    return f"{int(value):,}".replace(",", NBSP)


def fmt_pct0(value: float) -> str:
    """66.41 → «66%»."""
    return f"{round(value)}%"


def fmt_pct1(value: float) -> str:
    """3.577 → «3,6%»."""
    return f"{value:.1f}%".replace(".", ",")


def fmt_dt(iso: str) -> str:
    """ISO 8601 → «04.07.2026, 14:20» (в таймзоне, зафиксированной при сборке)."""
    return datetime.fromisoformat(iso).strftime("%d.%m.%Y, %H:%M")


def fmt_age(hours: float) -> str:
    """26.3 → «26 ч»; трое суток и дольше — в днях."""
    if hours < 1:
        return "меньше часа"
    if hours < 72:
        return f"{round(hours)}{NBSP}ч"
    return f"{round(hours / 24)}{NBSP}дн"


def ru_plural(number: int, one: str, few: str, many: str) -> str:
    """1 реакция / 3 реакции / 37 реакций."""
    tail = number % 100
    if 11 <= tail <= 14:
        return many
    tail %= 10
    if tail == 1:
        return one
    if 2 <= tail <= 4:
        return few
    return many


def initials(title: str) -> str:
    """«Наука простыми словами» → «НП»; «Пример-канал» → «ПК»."""
    words = [w for w in title.replace("-", " ").split() if w]
    return "".join(w[0] for w in words[:2]).upper() or "?"


def file_uri(path: str) -> str:
    return Path(path).absolute().as_uri()


def emoji_text(emoji: str) -> str:
    """Перевести эмодзи в текстовую презентацию (VS15).

    Кластеры с эмодзи-презентацией Pango уводит в системный emoji-шрифт мимо
    запрошенного семейства; VS15 возвращает их нашему вшитому Noto Emoji —
    иначе на машине без Segoe UI Emoji реакции превратятся в квадраты.
    """
    if not emoji or not (0x1F000 <= ord(emoji[0]) <= 0x1FAFF or 0x2600 <= ord(emoji[0]) <= 0x27BF):
        return emoji
    return emoji.replace("️", "") + "︎"


ALL = {
    "fmt_int": fmt_int,
    "fmt_pct0": fmt_pct0,
    "fmt_pct1": fmt_pct1,
    "fmt_dt": fmt_dt,
    "fmt_age": fmt_age,
    "initials": initials,
    "file_uri": file_uri,
    "emoji_text": emoji_text,
}
