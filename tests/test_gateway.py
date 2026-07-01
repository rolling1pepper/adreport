"""Шлюз: ретраи FloodWait и lock сессии."""

import asyncio

import pytest

from adreport.core.gateway import (
    SessionLockedError,
    TelegramBusyError,
    session_lock,
    tg,
)


class _FloodWait(Exception):
    def __init__(self, seconds):
        self.seconds = seconds


@pytest.fixture(autouse=True)
def _patch_floodwait(monkeypatch):
    # не тянем реальный Telethon-эксепшен — важна только форма (атрибут seconds)
    monkeypatch.setattr("adreport.core.gateway.FloodWaitError", _FloodWait)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr("adreport.core.gateway.asyncio.sleep", instant)


def test_tg_retries_then_succeeds():
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise _FloodWait(1)
        return "ok"

    assert asyncio.run(tg(flaky)) == "ok"
    assert len(calls) == 3


def test_tg_gives_friendly_error_after_attempts():
    async def always_busy():
        raise _FloodWait(1)

    with pytest.raises(TelegramBusyError, match="подождать"):
        asyncio.run(tg(always_busy))


def test_tg_does_not_sleep_on_huge_floodwait():
    async def hour_long():
        raise _FloodWait(3600)

    with pytest.raises(TelegramBusyError):
        asyncio.run(tg(hour_long))


def test_session_lock_exclusive(tmp_path):
    session = tmp_path / "adreport.session"
    with session_lock(session):
        with pytest.raises(SessionLockedError):
            with session_lock(session):
                pass
    # после выхода lock снят
    with session_lock(session):
        pass


def test_session_lock_reaps_stale(tmp_path):
    session = tmp_path / "adreport.session"
    lock = session.with_suffix(".session.lock")
    lock.write_text("999999999")  # заведомо мёртвый pid
    with session_lock(session):
        pass
