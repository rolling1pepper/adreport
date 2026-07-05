"""Изоляция рендера от цветных emoji-шрифтов системы.

NotoColorEmoji (стандарт на Linux) объявляет в cmap глифы цифр 0-9 — они
нужны ему для keycap-лигатур (1️⃣), но собственных битмапов не имеют.
Fontconfig охотно отдаёт ему цифры и эмодзи вместо запрошенных семейств,
и из PDF молча исчезают все числа. Лечится собственным fontconfig-конфигом:
системный конфиг подключается как есть, а цветные emoji-шрифты отклоняются —
реакции набирает вшитый монохромный Noto Emoji, цифры остаются у Plex.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_REJECT_FAMILIES = (
    "Noto Color Emoji",
    "Segoe UI Emoji",
    "Apple Color Emoji",
    "Twitter Color Emoji",
    "JoyPixels",
)

_CONF_TEMPLATE = """<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
{includes}
  <selectfont>
    <rejectfont>
{patterns}
    </rejectfont>
  </selectfont>
</fontconfig>
"""


def _system_configs() -> list[Path]:
    candidates = [
        Path("/etc/fonts/fonts.conf"),
        Path("/usr/local/etc/fonts/fonts.conf"),
        Path("/opt/homebrew/etc/fonts/fonts.conf"),
    ]
    if sys.platform == "win32" and os.environ.get("FONTCONFIG_PATH"):
        # конфиг GTK-runtime, найденный _winlibs
        candidates.insert(0, Path(os.environ["FONTCONFIG_PATH"]) / "fonts.conf")
    return [c for c in candidates if c.is_file()]


def ensure_fontconfig() -> None:
    """Выставить FONTCONFIG_FILE до первой инициализации fontconfig.

    Уважает уже заданный пользователем FONTCONFIG_FILE. Вызывается перед
    импортом weasyprint — fontconfig читает окружение лениво, при первом
    обращении в процессе.
    """
    if os.environ.get("FONTCONFIG_FILE"):
        return

    includes = "\n".join(
        f'  <include ignore_missing="yes">{c}</include>' for c in _system_configs()
    )
    patterns = "\n".join(
        "      <pattern><patelt name=\"family\">"
        f"<string>{family}</string></patelt></pattern>"
        for family in _REJECT_FAMILIES
    )
    conf_path = Path(tempfile.gettempdir()) / "adreport-fontconfig.conf"
    conf_path.write_text(
        _CONF_TEMPLATE.format(includes=includes, patterns=patterns),
        encoding="utf-8",
    )
    os.environ["FONTCONFIG_FILE"] = str(conf_path)
