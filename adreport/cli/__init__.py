"""CLI (Typer). В v0.1 — только demo из фикстур: ноль секретов, вход за 30 секунд."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from ..core.report.builder import build_report

app = typer.Typer(
    name="adreport",
    help="Отчёты по постам Telegram-каналов: PDF и PNG вместо скриншотов статистики.",
    add_completion=False,
    no_args_is_help=True,
)

# fixtures/ лежит в корне репозитория рядом с пакетом (editable-установка)
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


@app.callback()
def _root() -> None:
    """Отчёты по постам Telegram-каналов."""
    # callback фиксирует режим субкоманд: `adreport demo` сейчас, `adreport post` в v0.2


def _generate(data, out_dir: Path, pdf: bool, png: bool) -> None:
    # ленивые импорты: рендер тянет WeasyPrint, он нужен не каждой команде
    from ..core.report.render import render_pdf, render_png

    stem = f"{data.channel.username}_{data.post.msg_id}"
    if not pdf and not png:  # без флагов — оба формата
        pdf = png = True
    if pdf:
        path = out_dir / f"{stem}.pdf"
        render_pdf(data, path)
        typer.echo(f"PDF:  {path}")
    if png:
        path = out_dir / f"{stem}.png"
        render_png(data, path)
        typer.echo(f"PNG:  {path}")


@app.command()
def demo(
    pdf: bool = typer.Option(False, "--pdf", help="Только PDF-отчёт."),
    png: bool = typer.Option(False, "--png", help="Только PNG-карточка."),
    public: bool = typer.Option(
        False, "--public",
        help="Фикстура «только публичные данные» вместо полной статистики.",
    ),
    out: Path = typer.Option(Path("out"), "--out", help="Каталог для файлов."),
) -> None:
    """Демо-отчёт из фикстур — без токенов и сессий."""
    fixture_path = FIXTURES_DIR / ("demo_public.json" if public else "demo_full.json")
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    data = build_report(raw)
    _generate(data, out, pdf, png)
    typer.echo(f"Отчёт {data.report_id} собран из фикстуры {fixture_path.name}.")


if __name__ == "__main__":
    app()
