from adreport.core.models import ReportData
from adreport.core.report.builder import build_report, normalize_preview, top_reactions


def test_full_fixture(demo_full_raw):
    data = build_report(demo_full_raw)
    assert data.report_id == "r_9f2k1x"
    assert data.data_scope == "full"
    assert data.demo is True
    assert data.channel.username == "demo_channel"
    assert data.post.url == "https://t.me/demo_channel/318"
    assert data.metrics.views == 34800
    assert round(data.metrics.reach_pct) == 66
    assert round(data.metrics.err_pct, 1) == 4.0
    assert data.metrics.reactions_total == 1037
    assert data.metrics.age_hours == 48
    assert len(data.views_timeline) == 13
    assert data.views_timeline[-1].views == 34800


def test_public_fixture(demo_public_raw):
    data = build_report(demo_public_raw)
    assert data.data_scope == "public"
    assert data.views_timeline == ()
    assert round(data.metrics.reach_pct) == 54
    assert round(data.metrics.err_pct, 1) == 3.6
    assert data.metrics.age_hours == 26


def test_reactions_aggregated_beyond_four(demo_public_raw):
    # 5 видов реакций → топ-3 + агрегат «…», суммы сходятся
    data = build_report(demo_public_raw)
    assert len(data.reactions) == 4
    assert [r.count for r in data.reactions] == [704, 289, 98, 52]
    assert data.reactions[-1].emoji == "…"
    assert sum(r.count for r in data.reactions) == data.metrics.reactions_total


def test_reactions_four_kinds_kept_as_is(demo_full_raw):
    data = build_report(demo_full_raw)
    assert len(data.reactions) == 4
    assert data.reactions[-1].emoji != "…"


def test_top_reactions_sorted():
    raw = [{"emoji": "❤️", "count": 5}, {"emoji": "👍", "count": 50}]
    assert [r.count for r in top_reactions(raw)] == [50, 5]


def test_normalize_preview_strips_emoji():
    assert normalize_preview("ленты 🧠: показать вам") == "ленты: показать вам"
    assert normalize_preview("сны 😴 — и память") == "сны — и память"


def test_normalize_preview_truncates_on_word_boundary():
    text = "слово " * 60
    preview = normalize_preview(text)
    assert len(preview) <= 161  # 160 + «…»
    assert preview.endswith("…")
    assert not preview.endswith(" …")


def test_report_roundtrip(demo_full_raw):
    data = build_report(demo_full_raw)
    restored = ReportData.from_json(data.to_json())
    assert restored == data


def test_generated_at_defaults_to_collected_at(demo_full_raw):
    # демо воспроизводимо: без явного generated_at берётся время снапшота
    data = build_report(demo_full_raw)
    assert data.generated_at == demo_full_raw["collected_at"]
    assert data.data_as_of == demo_full_raw["collected_at"]
