"""Golden-тест рендера: кириллица не превращается в квадраты.

Проверяем двумя способами:
- извлечённый из PDF текст содержит контрольную строку «Ёё Щщ №» —
  ловит потерю текстового слоя и кодировок;
- в PDF реально встроены субсеты IBM Plex Sans — ловит молчаливый фолбэк
  на системный шрифт (главный источник квадратов и faux-bold).
"""

import re

import pypdfium2 as pdfium
import pytest

from adreport.core.models import (
    ChannelInfo,
    Metrics,
    PostInfo,
    Reaction,
    ReportData,
    SCHEMA_VERSION,
)
from adreport.core.report.builder import build_report
from adreport.core.report.render import render_pdf, render_png

CYRILLIC_PROBE = "Ёё Щщ №"


@pytest.fixture(scope="module")
def golden_data() -> ReportData:
    return ReportData(
        schema_version=SCHEMA_VERSION,
        report_id="r_golden",
        generated_at="2026-07-04T12:00:00+03:00",
        data_as_of="2026-07-04T12:00:00+03:00",
        data_scope="public",
        demo=True,
        channel=ChannelInfo(title="Тест-канал", username="test_channel", subscribers=1000),
        post=PostInfo(
            url="https://t.me/test_channel/1",
            msg_id=1,
            text_preview=CYRILLIC_PROBE,
            media_type=None,
            published_at="2026-07-03T12:00:00+03:00",
        ),
        metrics=Metrics(
            views=500, reach_pct=50.0, forwards=10,
            reactions_total=25, replies=5, err_pct=8.0, age_hours=24.0,
        ),
        reactions=(Reaction(emoji="👍", count=25),),
        views_timeline=(),
    )


def _extract_text(pdf_bytes: bytes) -> str:
    document = pdfium.PdfDocument(pdf_bytes)
    try:
        return "\n".join(page.get_textpage().get_text_bounded() for page in document)
    finally:
        document.close()


def _decompressed(pdf_bytes: bytes) -> bytes:
    """PDF со всеми распакованными Flate-потоками: имена шрифтов живут в них."""
    import zlib

    chunks = [pdf_bytes]
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.DOTALL):
        try:
            chunks.append(zlib.decompress(match.group(1)))
        except zlib.error:
            pass
    return b"".join(chunks)


def test_pdf_contains_cyrillic_probe(golden_data):
    text = _extract_text(render_pdf(golden_data))
    assert CYRILLIC_PROBE in text
    assert "Тест-канал" in text


def test_pdf_embeds_vendored_fonts(golden_data):
    raw = _decompressed(render_pdf(golden_data))
    # кириллица набрана вшитым Plex, а не системным фолбэком
    assert b"IBM-Plex-Sans" in raw
    # реакция 👍 набрана вшитым Noto Emoji: без VS15 Pango молча уходит
    # в системный emoji-шрифт, которого нет на чистом CI
    assert b"Noto-Emoji" in raw
    assert b"Segoe-UI-Emoji" not in raw


def test_full_fixture_renders_full_report(demo_full_raw):
    data = build_report(demo_full_raw)
    text = _extract_text(render_pdf(data))
    assert "Полная статистика" in text
    assert "34 800" in text  # неразрывный пробел из fmt_int
    assert "66% подписчиков" in text
    assert "Динамика просмотров" in text


def test_public_fixture_renders_badge_and_note(demo_public_raw):
    data = build_report(demo_public_raw)
    text = _extract_text(render_pdf(data))
    assert "Только публичные данные" in text
    assert "админ-доступе" in text  # плашка вместо графика


def test_png_card_renders(tmp_path, demo_public_raw):
    data = build_report(demo_public_raw)
    out = render_png(data, tmp_path / "card.png")
    from PIL import Image

    with Image.open(out) as image:
        assert image.width == 945  # 420px × 3 (при 96dpi → 315pt)
        # карточка не пустая: есть и светлые, и тёмные пиксели
        grey = image.convert("L")
        extrema = grey.getextrema()
        assert extrema[0] < 100 and extrema[1] > 200
