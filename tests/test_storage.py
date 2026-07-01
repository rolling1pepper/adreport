"""Хранилище: append-only снапшоты и иммутабельные отчёты на in-memory SQLite."""

import pytest

from adreport.core.report.builder import build_report
from adreport.core.storage import Storage


@pytest.fixture()
def storage() -> Storage:
    return Storage(":memory:")


def test_get_or_create_post_is_idempotent(storage):
    first = storage.get_or_create_post("naukaprosto", 1482)
    second = storage.get_or_create_post("naukaprosto", 1482)
    other = storage.get_or_create_post("naukaprosto", 1483)
    assert first == second
    assert other != first


def test_snapshots_append_only_latest_wins(storage, demo_public_raw):
    post_id = storage.get_or_create_post("naukaprosto", 1482)
    storage.add_snapshot(post_id, demo_public_raw)

    fresher = {**demo_public_raw, "collected_at": "2026-07-05T10:00:00+03:00"}
    fresher["counters"] = {**demo_public_raw["counters"], "views": 50100}
    storage.add_snapshot(post_id, fresher)

    latest = storage.latest_snapshot("naukaprosto", 1482)
    assert latest["counters"]["views"] == 50100
    assert latest["collected_at"] == "2026-07-05T10:00:00+03:00"


def test_latest_snapshot_missing_post(storage):
    assert storage.latest_snapshot("nobody", 1) is None


def test_report_roundtrip_through_db(storage, demo_public_raw):
    post_id = storage.get_or_create_post("naukaprosto", 1482)
    data = build_report(demo_public_raw)
    storage.save_report(post_id, data, sha256_pdf="a" * 64)

    restored = storage.get_report(data.report_id)
    assert restored == data


def test_snapshot_raw_roundtrip_builds_same_report(storage, demo_public_raw):
    """Снапшот из базы даёт тот же отчёт, что и исходный dict."""
    post_id = storage.get_or_create_post("naukaprosto", 1482)
    storage.add_snapshot(post_id, demo_public_raw)
    from_db = storage.latest_snapshot("naukaprosto", 1482)
    assert build_report(from_db) == build_report(demo_public_raw)
