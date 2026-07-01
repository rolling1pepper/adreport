"""Хранилище: SQLite, только вставки.

Три таблицы по спеке: posts — идентичность поста, snapshots — append-only
срезы счётчиков, reports — замороженные ReportData с sha256 эталонного PDF.
Отчёт всегда собирается из последнего снапшота; свежий сбор — просто новый
снапшот перед сборкой. Никаких update'ов.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import ForeignKey, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .models import ReportData


class Base(DeclarativeBase):
    pass


class PostRow(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_username: Mapped[str] = mapped_column(index=True)
    msg_id: Mapped[int] = mapped_column(index=True)
    first_seen_at: Mapped[str]  # ISO 8601


class SnapshotRow(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    collected_at: Mapped[str]
    views: Mapped[int]
    forwards: Mapped[int]
    replies: Mapped[int]
    subscribers: Mapped[int]
    thumb_path: Mapped[str | None]
    # полный сырой снапшот: builder читает его, а не отдельные колонки —
    # колонки выше нужны для выборок и будущих срезов (v1.4)
    raw_json: Mapped[str] = mapped_column(Text)


class ReportRow(Base):
    __tablename__ = "reports"

    report_id: Mapped[str] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    schema_version: Mapped[int]
    generated_at: Mapped[str]
    sha256_pdf: Mapped[str | None]  # эталонный PDF; None, если рендерили только PNG
    data_json: Mapped[str] = mapped_column(Text)


class Storage:
    def __init__(self, db_path: Path | str):
        url = "sqlite://" if str(db_path) == ":memory:" else f"sqlite:///{db_path}"
        self._engine = create_engine(url)
        Base.metadata.create_all(self._engine)

    def get_or_create_post(self, channel_username: str, msg_id: int) -> int:
        with Session(self._engine) as session:
            row = session.scalar(
                select(PostRow).where(
                    PostRow.channel_username == channel_username,
                    PostRow.msg_id == msg_id,
                )
            )
            if row is not None:
                return row.id
            row = PostRow(
                channel_username=channel_username,
                msg_id=msg_id,
                first_seen_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            session.add(row)
            session.commit()
            return row.id

    def add_snapshot(self, post_id: int, raw: dict) -> int:
        counters = raw["counters"]
        with Session(self._engine) as session:
            row = SnapshotRow(
                post_id=post_id,
                collected_at=raw["collected_at"],
                views=int(counters["views"]),
                forwards=int(counters.get("forwards", 0)),
                replies=int(counters.get("replies", 0)),
                subscribers=int(raw["channel"]["subscribers"]),
                thumb_path=raw["post"].get("thumb_path"),
                raw_json=json.dumps(raw, ensure_ascii=False),
            )
            session.add(row)
            session.commit()
            return row.id

    def latest_snapshot(self, channel_username: str, msg_id: int) -> dict | None:
        """Последний срез поста — источник отчёта, в том числе по уже удалённому посту."""
        with Session(self._engine) as session:
            row = session.scalar(
                select(SnapshotRow)
                .join(PostRow, SnapshotRow.post_id == PostRow.id)
                .where(
                    PostRow.channel_username == channel_username,
                    PostRow.msg_id == msg_id,
                )
                .order_by(SnapshotRow.id.desc())
                .limit(1)
            )
            return json.loads(row.raw_json) if row else None

    def save_report(
        self, post_id: int, data: ReportData, sha256_pdf: str | None,
    ) -> None:
        """Отчёты иммутабельны: перегенерация — новый report_id, не update."""
        with Session(self._engine) as session:
            session.add(
                ReportRow(
                    report_id=data.report_id,
                    post_id=post_id,
                    schema_version=data.schema_version,
                    generated_at=data.generated_at,
                    sha256_pdf=sha256_pdf,
                    data_json=data.to_json(),
                )
            )
            session.commit()

    def get_report(self, report_id: str) -> ReportData | None:
        with Session(self._engine) as session:
            row = session.get(ReportRow, report_id)
            return ReportData.from_json(row.data_json) if row else None
