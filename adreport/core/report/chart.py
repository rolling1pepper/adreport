"""Серверный SVG-график динамики просмотров: WeasyPrint не исполняет JS."""

from __future__ import annotations

from collections.abc import Sequence

from ..models import ViewsPoint

LINE = "#2a78d6"
FILL = "rgba(42,120,214,0.10)"
GRID = "#e3e1d9"
LABEL = "#8a8880"
FONT = "IBM Plex Sans"

_PAD_LEFT = 52  # место под подписи оси Y
_PAD_RIGHT = 10
_PAD_TOP = 8
_PAD_BOTTOM = 24  # место под подписи оси X


def _nice_ceil(value: float) -> int:
    """Ближайший «круглый» потолок вида {1, 2, 2.5, 4, 5, 10}×10^k."""
    if value <= 0:
        return 1
    magnitude = 1
    while magnitude * 10 <= value:
        magnitude *= 10
    for mult in (1, 2, 2.5, 4, 5, 10):
        ceiling = int(mult * magnitude)
        if value <= ceiling:
            return ceiling
    return magnitude * 10


def _fmt_axis(value: float) -> str:
    if value >= 1000:
        short = value / 1000
        return f"{short:g} тыс".replace(".", ",")
    return f"{value:g}"


def views_chart_svg(
    points: Sequence[ViewsPoint], width: int = 640, height: int = 200,
) -> str:
    """Линия с заливкой, сетка по Y, подписи часов по X. Пустая строка, если точек < 2."""
    if len(points) < 2:
        return ""

    max_hours = max(p.hours for p in points)
    if max_hours <= 0:  # вырожденный таймлайн — нечего рисовать
        return ""
    y_max = _nice_ceil(max(p.views for p in points))
    plot_w = width - _PAD_LEFT - _PAD_RIGHT
    plot_h = height - _PAD_TOP - _PAD_BOTTOM

    def x(hours: float) -> float:
        return _PAD_LEFT + hours / max_hours * plot_w

    def y(views: float) -> float:
        return _PAD_TOP + plot_h - views / y_max * plot_h

    coords = [(x(p.hours), y(p.views)) for p in points]
    line_path = " ".join(
        f"{'M' if i == 0 else 'L'}{px:.1f},{py:.1f}" for i, (px, py) in enumerate(coords)
    )
    area_path = (
        line_path
        + f" L{coords[-1][0]:.1f},{_PAD_TOP + plot_h:.1f}"
        + f" L{coords[0][0]:.1f},{_PAD_TOP + plot_h:.1f} Z"
    )

    parts: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
    ]

    # сетка и подписи Y: 4 шага
    steps = 4
    for i in range(steps + 1):
        value = y_max / steps * i
        gy = y(value)
        if i > 0:  # нулевую линию не рисуем — там ось X
            parts.append(
                f'<line x1="{_PAD_LEFT}" y1="{gy:.1f}" x2="{width - _PAD_RIGHT}" '
                f'y2="{gy:.1f}" stroke="{GRID}" stroke-width="1"/>'
            )
        parts.append(
            f'<text x="{_PAD_LEFT - 8}" y="{gy + 3:.1f}" text-anchor="end" '
            f'font-family="{FONT}" font-size="10" fill="{LABEL}">{_fmt_axis(value)}</text>'
        )

    # подписи X каждые max_hours/4 часа
    x_step = max_hours / 4
    for i in range(5):
        hours = x_step * i
        parts.append(
            f'<text x="{x(hours):.1f}" y="{height - 8}" text-anchor="middle" '
            f'font-family="{FONT}" font-size="10" fill="{LABEL}">{hours:g} ч</text>'
        )

    parts.append(f'<path d="{area_path}" fill="{FILL}" stroke="none"/>')
    parts.append(
        f'<path d="{line_path}" fill="none" stroke="{LINE}" stroke-width="2" '
        'stroke-linejoin="round" stroke-linecap="round"/>'
    )

    # маркеры на суточных отметках и последней точке
    marked = {p.hours for p in points if p.hours > 0 and p.hours % 24 == 0}
    marked.add(points[-1].hours)
    for p in points:
        if p.hours in marked:
            parts.append(
                f'<circle cx="{x(p.hours):.1f}" cy="{y(p.views):.1f}" r="3.5" '
                f'fill="{LINE}"/>'
            )

    parts.append("</svg>")
    return "".join(parts)
