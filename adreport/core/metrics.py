"""Расчёт метрик. Медианы и выровненные срезы — v1.4, здесь только арифметика поста."""

from __future__ import annotations

from datetime import datetime


def reach_pct(views: int, subscribers: int) -> float:
    """Охват — просмотры в процентах от подписчиков."""
    if subscribers <= 0:
        return 0.0
    return views / subscribers * 100


def err_pct(views: int, reactions: int, forwards: int, replies: int) -> float:
    """ERR — (реакции + пересылки + ответы) к просмотрам."""
    if views <= 0:
        return 0.0
    return (reactions + forwards + replies) / views * 100


def age_hours(published_at: str, as_of: str) -> float:
    """Возраст поста между публикацией и срезом, в часах (ISO 8601 с таймзоной)."""
    published = datetime.fromisoformat(published_at)
    snapshot = datetime.fromisoformat(as_of)
    return (snapshot - published).total_seconds() / 3600
