"""Шлюз к Телеграму: ретраи FloodWait и защита сессии от параллельного запуска.

Второе подключение одной сессии — конфликты и красный флаг антифрода
Телеграма, поэтому на файл сессии берётся эксклюзивный lock. Семафор для
массовых обходов появится вместе с /all (v1.4).
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from pathlib import Path

from telethon.errors import FloodWaitError

MAX_ATTEMPTS = 3
MAX_FLOOD_WAIT_S = 120  # дольше не спим — честно просим зайти позже


class TelegramBusyError(RuntimeError):
    """Телеграм просит подождать — дружелюбная ошибка после исчерпания ретраев."""


class SessionLockedError(RuntimeError):
    """Сессия уже используется другим процессом adreport."""


async def tg[T](call: Callable[[], Awaitable[T]], *, attempts: int = MAX_ATTEMPTS) -> T:
    """Выполнить вызов Телеграма, пересыпая FloodWait с джиттером."""
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except FloodWaitError as error:
            if attempt == attempts or error.seconds > MAX_FLOOD_WAIT_S:
                raise TelegramBusyError(
                    f"Телеграм просит подождать {error.seconds} с — "
                    "попробуйте повторить позже."
                ) from error
            await asyncio.sleep(error.seconds + random.uniform(0.5, 2.0))
    raise AssertionError("unreachable")


@contextmanager
def session_lock(session_path: Path):
    """Эксклюзивный lock-файл рядом с .session (кросс-платформенный аналог flock)."""
    lock_path = session_path.with_suffix(".session.lock")
    _reap_stale(lock_path)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SessionLockedError(
            "Сессия уже используется другим процессом adreport (бот или CLI). "
            f"Если это не так — удалите {lock_path}."
        ) from None
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def _reap_stale(lock_path: Path) -> None:
    """Убрать lock, чей процесс уже мёртв (после падения или kill)."""
    try:
        pid = int(lock_path.read_text())
    except (FileNotFoundError, ValueError):
        return
    if not _pid_alive(pid):
        lock_path.unlink(missing_ok=True)


def _pid_alive(pid: int) -> bool:
    # на Windows os.kill(pid, 0) не проверяет, а УБИВАЕТ процесс —
    # поэтому там спрашиваем ядро через OpenProcess
    if sys.platform == "win32":
        import ctypes

        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information, False, pid
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
