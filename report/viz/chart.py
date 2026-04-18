# scrutiny-viz/report/viz/chart.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import html
from dominate import tags
from dominate.util import raw

from .contracts import VizPlugin, VizSpec
from .utility import format_number, to_float


def _truncate(text: str, max_chars: int = 42) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _chart_values(rows: List[Dict[str, Any]]) -> List[float]:
    values: List[float] = []
    for row in rows:
        ref_avg = to_float(row.get("ref_avg"))
        test_avg = to_float(row.get("test_avg"))
        if ref_avg is not None:
            values.append(ref_avg)
        if test_avg is not None:
            values.append(test_avg)
    return values


def render_bar_pair_block(section_name: str, section: Dict[str, Any], idx: int):
    rows: List[Dict[str, Any]] = section.get("chart_rows", []) or []
    values = _chart_values(rows)
    if not values:
        return tags.div()

    pad_x = 14
    pad_y = 12
    label_w = 380
    value_pad = 90
    bar_h = 8
    bar_gap = 4
    row_gap = 10
    row_block = (bar_h * 2 + bar_gap)
    row_total = row_block + row_gap
    legend_h = 18

    width = 900
    x_bars = pad_x + label_w
    inner_w = max(1, width - label_w - 2 * pad_x - value_pad)
    x_max_text = x_bars + inner_w + value_pad - 6
    vmax = max(values) if max(values) > 0 else 1.0

    height = pad_y * 2 + len(rows) * row_total + legend_h
    parts: List[str] = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" class="barpair">'
    ]

    y = pad_y
    for row in rows:
        full_key = str(row.get("key", "") or "")
        short_key = _truncate(full_key, max_chars=44)
        ref_avg = to_float(row.get("ref_avg"))
        test_avg = to_float(row.get("test_avg"))

        label_y = y + bar_h + bar_gap / 2.0
        parts.append(
            f'<text x="{x_bars - 8}" y="{label_y + bar_h/2}" '
            f'class="chart-label" text-anchor="end" dominant-baseline="middle">'
            f'<title>{html.escape(full_key)}</title>{html.escape(short_key)}</text>'
        )

        if ref_avg is not None:
            ref_width = max(0.0, (ref_avg / vmax) * inner_w)
            parts.append(f'<rect x="{x_bars}" y="{y}" width="{ref_width}" height="{bar_h}" class="bar-ref"></rect>')
            parts.append(
                f'<text x="{min(x_bars + ref_width + 4, x_max_text)}" y="{y + bar_h/2}" '
                f'class="bar-value" dominant-baseline="middle">{html.escape(format_number(ref_avg, precision=6, trim=True))}</text>'
            )

        test_y = y + bar_h + bar_gap
        if test_avg is not None:
            test_width = max(0.0, (test_avg / vmax) * inner_w)
            parts.append(f'<rect x="{x_bars}" y="{test_y}" width="{test_width}" height="{bar_h}" class="bar-test"></rect>')
            parts.append(
                f'<text x="{min(x_bars + test_width + 4, x_max_text)}" y="{test_y + bar_h/2}" '
                f'class="bar-value" dominant-baseline="middle">{html.escape(format_number(test_avg, precision=6, trim=True))}</text>'
            )

        y += row_total

    leg_y = height - pad_y - legend_h / 2
    parts.append(f'<rect x="{x_bars}" y="{leg_y - 5}" width="12" height="6" class="bar-ref"></rect>')
    parts.append(f'<text x="{x_bars + 18}" y="{leg_y + 2}" class="legend-text" dominant-baseline="middle">reference</text>')
    parts.append(f'<rect x="{x_bars + 110}" y="{leg_y - 5}" width="12" height="6" class="bar-test"></rect>')
    parts.append(f'<text x="{x_bars + 128}" y="{leg_y + 2}" class="legend-text" dominant-baseline="middle">profile</text>')
    parts.append("</svg>")

    container = tags.div(_class="chart-container", id=f"chart-{idx}")
    container.add(raw("".join(parts)))
    return container


def render_chart_table_block(section_name: str, section: Dict[str, Any], idx: int):
    rows: List[Dict[str, Any]] = section.get("chart_rows", []) or []
    if not rows:
        return tags.div()

    headers = ["Key", "Ref Avg", "Profile Avg", "Δ ms", "Δ %", "Status", "Note"]
    table = tags.table(_class="chart-table report-table")
    with table:
        with tags.thead():
            with tags.tr():
                for header in headers:
                    tags.th(header)
        with tags.tbody():
            for row in rows:
                with tags.tr():
                    tags.td(str(row.get("key", "")))
                    tags.td(format_number(row.get("ref_avg"), precision=6, trim=True))
                    tags.td(format_number(row.get("test_avg"), precision=6, trim=True))
                    tags.td(format_number(row.get("delta_ms"), precision=6, trim=True))
                    tags.td(format_number(row.get("delta_pct"), precision=6, trim=True))
                    tags.td(str(row.get("status", "")))
                    tags.td(str(row.get("note", "")))
    return table


def render_chart_variant(*, section_name: str, section: Dict[str, Any], idx: int, variant: Optional[str] = None) -> Tuple[Any, Any]:
    return (
        render_bar_pair_block(section_name, section, idx),
        render_chart_table_block(section_name, section, idx),
    )


class ChartVizPlugin(VizPlugin):
    spec = VizSpec(
        name="chart",
        slot="top",
        aliases=("bar",),
        description="Chart visualization for section performance rows.",
    )

    def render(self, **kwargs: Any) -> Any:
        return render_chart_variant(
            section_name=kwargs["section_name"],
            section=kwargs["section"],
            idx=kwargs["idx"],
            variant=kwargs.get("variant"),
        )


PLUGINS = [ChartVizPlugin()]
