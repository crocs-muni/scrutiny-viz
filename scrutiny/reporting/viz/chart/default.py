# scrutiny/reporting/viz/chart.py
from typing import Dict, Any, List
from dominate import tags
from dominate.util import raw
import html

def _num(v):
    try:
        return float(v)
    except Exception:
        return None


def _fmt_num(v):
    if v is None:
        return ""
    try:
        fv = float(v)
        s = f"{fv:.6g}"
        # trim trailing .0
        if s.endswith(".0"):
            s = s[:-2]
        return s
    except Exception:
        return str(v)


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
    label_w = 320         # room for long labels on left
    bar_h = 8             # each bar height
    bar_gap = 4           # gap between ref and test bars
    row_gap = 10          # gap between pairs
    row_block = (bar_h * 2 + bar_gap)  # vertical space taken by bars for one key
    row_total = row_block + row_gap     # including gap
    legend_h = 18

    values = []
    for r in rows:
        ra = _num(r.get("ref_avg"))
        ta = _num(r.get("test_avg"))
        if ra is not None:
            values.append(ra)
        if ta is not None:
            values.append(ta)

    if not values:
        return tags.div()

    vmax = max(values) or 1.0

    # SVG size (fixed width like the old chart, height based on rows)
    width = 900
    inner_w = max(1, width - label_w - 2 * pad_x)
    height = pad_y * 2 + len(rows) * row_total + legend_h

    # Build raw SVG (no dependency on dominate SVG helpers)
    parts: List[str] = []
    parts.append(f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" class="barpair">')

    # Left column labels + bars
    x_label = pad_x
    x_bars = pad_x + label_w

    y = pad_y
    for r in rows:
        key = html.escape(str(r.get("key", "")))
        ref_v = _num(r.get("ref_avg"))
        tst_v = _num(r.get("test_avg"))

        # Label (aligned with the bar pair)
        # Use middle baseline and offset to sit between the two bars
        label_y = y + bar_h + bar_gap / 2.0
        parts.append(
            f'<text x="{x_label}" y="{label_y + bar_h/2}" '
            f'class="chart-label" text-anchor="start" dominant-baseline="middle">{key}</text>'
        )

        # Reference bar
        if ref_v is not None:
            w = max(0.0, (ref_v / vmax) * inner_w)
            parts.append(f'<rect x="{x_bars}" y="{y}" width="{w}" height="{bar_h}" class="bar-ref"></rect>')
            parts.append(
                f'<text x="{x_bars + w + 4}" y="{y + bar_h/2}" '
                f'class="bar-value" dominant-baseline="middle">{_fmt_num(ref_v)}</text>'
            )

        # Test/profile bar
        yt = y + bar_h + bar_gap
        if tst_v is not None:
            w = max(0.0, (tst_v / vmax) * inner_w)
            parts.append(f'<rect x="{x_bars}" y="{yt}" width="{w}" height="{bar_h}" class="bar-test"></rect>')
            parts.append(
                f'<text x="{x_bars + w + 4}" y="{yt + bar_h/2}" '
                f'class="bar-value" dominant-baseline="middle">{_fmt_num(tst_v)}</text>'
            )

        y += row_total

    # Legend
    leg_y = height - pad_y - legend_h / 2
    leg_x = x_bars
    parts.append(f'<rect x="{leg_x}" y="{leg_y - 5}" width="12" height="6" class="bar-ref"></rect>')
    parts.append(f'<text x="{leg_x + 18}" y="{leg_y + 2}" class="legend-text" dominant-baseline="middle">reference</text>')
    parts.append(f'<rect x="{leg_x + 110}" y="{leg_y - 5}" width="12" height="6" class="bar-test"></rect>')
    parts.append(f'<text x="{leg_x + 128}" y="{leg_y + 2}" class="legend-text" dominant-baseline="middle">profile</text>')

    parts.append('</svg>')

    container = tags.div(_class="chart-container", id=f"chart-{idx}")
    container.add(raw("".join(parts)))
    return container


def render_chart_table_block(section_name: str, section: Dict[str, Any], idx: int):
    rows: List[Dict[str, Any]] = section.get("chart_rows", []) or []
    headers = ["Key", "Ref Avg", "Test Avg", "Δ ms", "Δ %", "Status", "Note"]
    table = tags.table(_class="chart-table")
    with table:
        thead = tags.thead()
        with thead:
            tr = tags.tr()
            for h in headers:
                tags.th(h)
        tbody = tags.tbody()
        with tbody:
            for r in rows:
                tr = tags.tr()
                tags.td(str(r.get("key", "")))
                tags.td(_fmt_num(r.get("ref_avg")))
                tags.td(_fmt_num(r.get("test_avg")))
                tags.td(_fmt_num(r.get("delta_ms")))
                tags.td(_fmt_num(r.get("delta_pct")))
                tags.td(str(r.get("status", "")))
                tags.td(str(r.get("note", "")))
    return table
