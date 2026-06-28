"""HTML → PDF через WeasyPrint. Один templating-путь обслуживает и PDF, и PNG."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ...models import ReportData
from ..chart import views_chart_svg
from . import filters
from ._winlibs import ensure_gtk

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
    )
    env.filters.update(filters.ALL)
    env.globals["ru_plural"] = filters.ru_plural
    return env


def render_html(data: ReportData, template: str = "post.html") -> str:
    chart_svg = views_chart_svg(data.views_timeline)
    return _env().get_template(template).render(d=data, chart_svg=chart_svg)


def render_pdf(
    data: ReportData,
    out_path: Path | None = None,
    template: str = "post.html",
) -> bytes:
    """Рендер в PDF; при out_path также пишет файл. base_url — каталог шаблонов,
    чтобы @font-face находил шрифты по относительным путям."""
    ensure_gtk()  # до импорта weasyprint: ему нужны DLL Pango в PATH
    import weasyprint

    html = render_html(data, template)
    pdf_bytes = weasyprint.HTML(string=html, base_url=str(TEMPLATES_DIR)).write_pdf()
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(pdf_bytes)
    return pdf_bytes
