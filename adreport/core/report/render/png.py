"""PNG-карточка: card.html → одностраничный PDF → растр через pypdfium2.

pypdfium2 ставится pip'ом без системных зависимостей, а единый HTML-путь
гарантирует, что PDF и PNG всегда выглядят одинаково.
"""

from __future__ import annotations

from pathlib import Path

from ...models import ReportData
from .pdf import render_pdf

# страница карточки 420px ≈ 315pt; ×3 даёт ~945px по ширине — чётко в чате
PNG_SCALE = 3.0


def render_png(
    data: ReportData,
    out_path: Path,
    template: str = "card.html",
    scale: float = PNG_SCALE,
) -> Path:
    import pypdfium2 as pdfium

    pdf_bytes = render_pdf(data, template=template)
    document = pdfium.PdfDocument(pdf_bytes)
    try:
        page = document[0]
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
    finally:
        document.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    return out_path
