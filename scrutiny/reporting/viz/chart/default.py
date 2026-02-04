# scrutiny-viz/scrutiny/reporting/viz/chart/default.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
import html
from dominate import tags
from dominate.util import raw

def _num(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _fmt_num(v: Any) -> str:
    if v is None:
        return ""
    try:
        fv = float(v)
        s = f"{fv:.6g}"
        if s.endswith(".0"):
            s = s[:-2]
        return s
    except Exception:
        return str(v)

def _trunc(s: str, max_chars: int = 42) -> str:
    s = s or ""
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"

def render_bar_pair_block(section_name: str, section: Dict[str, Any], idx: int):
    """
    Draw a horizontal bar chart comparing ref_avg vs test_avg per key.
    Uses raw SVG like the original report_html implementation.
    """
    rows: List[Dict[str, Any]] = section.get("chart_rows", []) or []
    if not rows:
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

    inner_w = width - label_w - 2 * pad_x - value_pad
    if inner_w < 1:
        inner_w = 1

    x_max_text = x_bars + inner_w + value_pad - 6

    # scale
    values: List[float] = []
    for r in rows:
        ra = _num(r.get("ref_avg"))
        ta = _num(r.get("test_avg"))
        if ra is not None:
            values.append(ra)
        if ta is not None:
            values.append(ta)

    if not values:
        return tags.div()

    vmax = max(values)
    if vmax <= 0:
        vmax = 1.0

    height = pad_y * 2 + len(rows) * row_total + legend_h

    parts: List[str] = []
    parts.append(f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" class="barpair">')

    y = pad_y
    for r in rows:
        full_key = str(r.get("key", "") or "")
        short_key = _trunc(full_key, max_chars=44)

        ref_v = _num(r.get("ref_avg"))
        tst_v = _num(r.get("test_avg"))

        # label centered on the bar-pair; RIGHT-aligned at bar start
        label_y = y + bar_h + bar_gap / 2.0
        x_label = x_bars - 8

        parts.append(
            f'<text x="{x_label}" y="{label_y + bar_h/2}" '
            f'class="chart-label" text-anchor="end" dominant-baseline="middle">'
            f'<title>{html.escape(full_key)}</title>'
            f'{html.escape(short_key)}'
            f'</text>'
        )

        # reference bar
        if ref_v is not None:
            w = max(0.0, (ref_v / vmax) * inner_w)
            parts.append(f'<rect x="{x_bars}" y="{y}" width="{w}" height="{bar_h}" class="bar-ref"></rect>')

            # value AFTER bar, but clamp into allowed area
            x_text = min(x_bars + w + 4, x_max_text)
            parts.append(
                f'<text x="{x_text}" y="{y + bar_h/2}" '
                f'class="bar-value" dominant-baseline="middle">{html.escape(_fmt_num(ref_v))}</text>'
            )

        # profile bar
        yt = y + bar_h + bar_gap
        if tst_v is not None:
            w = max(0.0, (tst_v / vmax) * inner_w)
            parts.append(f'<rect x="{x_bars}" y="{yt}" width="{w}" height="{bar_h}" class="bar-test"></rect>')

            x_text = min(x_bars + w + 4, x_max_text)
            parts.append(
                f'<text x="{x_text}" y="{yt + bar_h/2}" '
                f'class="bar-value" dominant-baseline="middle">{html.escape(_fmt_num(tst_v))}</text>'
            )

        y += row_total

    # Legend
    leg_y = height - pad_y - legend_h / 2
    leg_x = x_bars
    parts.append(f'<rect x="{leg_x}" y="{leg_y - 5}" width="12" height="6" class="bar-ref"></rect>')
    parts.append(
        f'<text x="{leg_x + 18}" y="{leg_y + 2}" class="legend-text" dominant-baseline="middle">reference</text>'
    )
    parts.append(f'<rect x="{leg_x + 110}" y="{leg_y - 5}" width="12" height="6" class="bar-test"></rect>')
    parts.append(
        f'<text x="{leg_x + 128}" y="{leg_y + 2}" class="legend-text" dominant-baseline="middle">profile</text>'
    )

    parts.append("</svg>")

    container = tags.div(_class="chart-container", id=f"chart-{idx}")
    container.add(raw("".join(parts)))
    return container

def render_chart_table_block(section_name: str, section: Dict[str, Any], idx: int):
    rows: List[Dict[str, Any]] = section.get("chart_rows", []) or []
    if not rows:
        return tags.div()

    headers = ["Key", "Ref Avg", "Profile Avg", "Δ ms", "Δ %", "Status", "Note"]

    table = tags.table(_class="chart-table")
    with table:
        with tags.tr():
            for h in headers:
                tags.th(h)

        for r in rows:
            with tags.tr():
                tags.td(str(r.get("key", "")))
                tags.td(_fmt_num(r.get("ref_avg")))
                tags.td(_fmt_num(r.get("test_avg")))
                tags.td(_fmt_num(r.get("delta_ms")))
                tags.td(_fmt_num(r.get("delta_pct")))
                tags.td(str(r.get("status", "")))
                tags.td(str(r.get("note", "")))

    return table
