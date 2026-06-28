"""Поиск DLL Pango/GObject для WeasyPrint на Windows.

pip не ставит нативные библиотеки GTK; официальный способ — MSYS2 или
GTK-runtime. Дев-удобство для локального запуска: если рядом с репозиторием
лежит .gtk3/bin (см. README), добавляем его в PATH до импорта weasyprint.
cffi игнорирует флаги поиска LoadLibrary, поэтому WEASYPRINT_DLL_DIRECTORIES
недостаточно — работает именно PATH.
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

_PROBE_DLL = "gobject-2.0-0.dll"

# то, что dlopen'ит WeasyPrint (см. weasyprint/text/ffi.py), в именах gvsbuild —
# без префикса lib, поэтому предзагружаем по полному пути: загруженный модуль
# дальше находится по любому из имён-кандидатов через кэш загрузчика
_PRELOAD_DLLS = (
    "gobject-2.0-0.dll",
    "fontconfig-1.dll",
    "harfbuzz.dll",
    "harfbuzz-subset.dll",
    "pango-1.0-0.dll",
    "pangoft2-1.0-0.dll",
)

INSTALL_HINT = (
    "WeasyPrint не нашёл библиотеки GTK (Pango/GObject).\n"
    "Варианты установки:\n"
    "  1) распаковать GTK3-runtime (github.com/wingtk/gvsbuild, релизы) в .gtk3/ "
    "в корне репозитория, чтобы DLL лежали в .gtk3/bin;\n"
    "  2) или указать каталог с DLL в переменной ADREPORT_GTK_BIN;\n"
    "  3) или установить MSYS2 с pango (см. документацию WeasyPrint)."
)


def _loadable() -> bool:
    # winmode=0 — классический поиск LoadLibrary с PATH: так же грузит DLL cffi,
    # которым пользуется WeasyPrint (поиск по умолчанию у ctypes PATH не смотрит)
    try:
        ctypes.WinDLL(_PROBE_DLL, winmode=0)
        return True
    except OSError:
        return False


def ensure_gtk() -> None:
    """Добавить GTK-DLL в PATH, если они ещё не находятся. No-op вне Windows."""
    if sys.platform != "win32" or _loadable():
        return

    candidates = [os.environ.get("ADREPORT_GTK_BIN")]
    # корень репозитория при editable-установке: render/ → report/ → core/ → adreport/ → корень
    repo_root = Path(__file__).resolve().parents[4]
    candidates.append(repo_root / ".gtk3" / "bin")
    candidates.append(Path.cwd() / ".gtk3" / "bin")

    for candidate in candidates:
        if not candidate:
            continue
        bin_dir = Path(candidate)
        if not (bin_dir / _PROBE_DLL).exists():
            continue
        # PATH — для транзитивных зависимостей (glib, freetype, ...)
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
        # молчим про отсутствующий fonts.conf, если конфиг лежит рядом
        fonts_conf = bin_dir.parent / "etc" / "fonts"
        if fonts_conf.is_dir() and "FONTCONFIG_PATH" not in os.environ:
            os.environ["FONTCONFIG_PATH"] = str(fonts_conf)
        for dll in _PRELOAD_DLLS:
            path = bin_dir / dll
            if path.exists():
                ctypes.WinDLL(str(path), winmode=0)
        if _loadable():
            return

    raise OSError(INSTALL_HINT)
