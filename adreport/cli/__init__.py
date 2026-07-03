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
def post(
    link: str = typer.Argument(..., help="Ссылка на пост: https://t.me/канал/123"),
    pdf: bool = typer.Option(False, "--pdf", help="Только PDF-отчёт."),
    png: bool = typer.Option(False, "--png", help="Только PNG-карточка."),
    out: Path = typer.Option(Path("out"), "--out", help="Каталог для файлов."),
) -> None:
    """Отчёт по реальному публичному посту (нужны API_ID/API_HASH в .env)."""
    import asyncio
    import hashlib

    from ..config import load_config
    from ..core.collector import (
        PostUnavailableError,
        collect_post,
        parse_post_link,
    )
    from ..core.gateway import session_lock
    from ..core.report.render import render_pdf, render_png
    from ..core.storage import Storage

    from ..core.collector import PostLinkError

    try:
        username, msg_id = parse_post_link(link)
    except PostLinkError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2)

    config = load_config()
    if not config.api_id or not config.api_hash:
        typer.echo(
            "Не заданы API_ID/API_HASH. Получите их на https://my.telegram.org, "
            "скопируйте .env.example в .env и заполните.", err=True,
        )
        raise typer.Exit(code=2)
    storage = Storage(config.db_path)
    post_row_id = storage.get_or_create_post(username, msg_id)

    async def _collect() -> dict:
        from telethon import TelegramClient

        client = TelegramClient(str(config.session_path), config.api_id, config.api_hash)
        async with client:  # при первом запуске Telethon спросит телефон и код
            return await collect_post(
                client, username, msg_id,
                media_dir=config.media_dir, tz=config.tz,
            )

    stale_note: str | None = None
    try:
        with session_lock(config.session_path):
            raw = asyncio.run(_collect())
        storage.add_snapshot(post_row_id, raw)
    except PostUnavailableError as error:
        # пассивная защита: пост исчез — строим по последнему срезу
        raw = storage.latest_snapshot(username, msg_id)
        if raw is None:
            typer.echo(f"{error} Снапшотов этого поста в базе нет.", err=True)
            raise typer.Exit(code=1)
        stale_note = raw["collected_at"]

    from zoneinfo import ZoneInfo
    from datetime import datetime

    data = build_report(
        raw,
        contact_link=config.contact_link,
        generated_at=datetime.now(ZoneInfo(config.tz)).isoformat(timespec="seconds"),
    )

    if not pdf and not png:
        pdf = png = True
    sha256_pdf = None
    stem = f"{data.channel.username}_{data.post.msg_id}"
    if pdf:
        path = out / f"{stem}.pdf"
        sha256_pdf = hashlib.sha256(render_pdf(data, path)).hexdigest()
        typer.echo(f"PDF:  {path}")
    if png:
        path = out / f"{stem}.png"
        render_png(data, path)
        typer.echo(f"PNG:  {path}")
    storage.save_report(post_row_id, data, sha256_pdf)
    if stale_note:
        typer.echo(
            f"Пост уже недоступен — отчёт собран из последнего среза от "
            f"{stale_note} (это отражено в футере отчёта)."
        )
    typer.echo(f"Отчёт {data.report_id} сохранён в базе.")


@app.command()
def bot() -> None:
    """Запустить бота: пересланный пост или ссылка → PDF + PNG в ответ."""
    import asyncio

    from ..bot import run_bot
    from ..config import load_config
    from ..core.gateway import session_lock

    config = load_config()
    missing = [
        name for name, value in (
            ("API_ID/API_HASH", config.api_id and config.api_hash),
            ("BOT_TOKEN", config.bot_token),
            ("ALLOWED_IDS", config.allowed_ids),
        ) if not value
    ]
    if missing:
        typer.echo(
            "В .env не заполнено: " + ", ".join(missing) +
            ". См. .env.example.", err=True,
        )
        raise typer.Exit(code=2)

    typer.echo("Бот запущен. Ctrl+C — остановить.")
    with session_lock(config.session_path):
        try:
            asyncio.run(run_bot(config))
        except KeyboardInterrupt:
            typer.echo("Бот остановлен.")


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
