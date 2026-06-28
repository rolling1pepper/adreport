from adreport.core.metrics import age_hours, err_pct, reach_pct


def test_reach_pct():
    assert round(reach_pct(34800, 52400)) == 66
    assert round(reach_pct(47300, 88130)) == 54


def test_reach_pct_zero_subscribers():
    assert reach_pct(100, 0) == 0.0


def test_err_pct():
    # ERR = (реакции + пересылки + ответы) / просмотры
    assert round(err_pct(34800, 1037, 291, 64), 1) == 4.0
    assert round(err_pct(47300, 1143, 512, 37), 1) == 3.6


def test_err_pct_zero_views():
    assert err_pct(0, 10, 10, 10) == 0.0


def test_age_hours():
    assert age_hours("2026-07-02T12:00:00+03:00", "2026-07-04T12:00:00+03:00") == 48
    assert age_hours("2026-07-03T12:20:00+03:00", "2026-07-04T14:20:00+03:00") == 26


def test_age_hours_cross_timezone():
    # публикация в UTC, срез в московском времени — 3 часа разницы учтены
    assert age_hours("2026-07-04T09:00:00+00:00", "2026-07-04T13:00:00+03:00") == 1
