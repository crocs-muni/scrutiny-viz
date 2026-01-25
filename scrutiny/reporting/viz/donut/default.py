from typing import Dict, Any, List, Optional
from dominate import tags
from dominate.util import raw
import math
import html

# Donut chart (SVG) with modular legend (counts+percent, native <title> tooltips)

_DEFAULT_COLORS = {
    "MATCH": "#49b473",       # green
    "WARN": "#c9b400",        # yellow (contrast-improved)
    "SUSPICIOUS": "#d3923e",  # orange
    "ERROR": "#c04444",       # red (optional)
}

def _pct2(value: float, total: float) -> float:
    """
    Return a percentage with two decimals, clamped to [0, 100].
    Example: value=101, total=100 -> 100.00 (not 101.00)
    """
    if total <= 0:
        return 0.0
    pct = (float(value) / float(total)) * 100.0
    if pct < 0:
        pct = 0.0
    elif pct > 100.0:
        pct = 100.0
    # small epsilon to avoid 99.999999 -> 100.00 surprises
    return round(pct + 1e-12, 2)


def render_donut_block(
    title: str,
    values: Dict[str, int],
    *,
    segments: Optional[List[str]] = None,
    radius: int = 52,
    stroke: int = 18,
    center_label: Optional[str] = None,
    legend_labels: Optional[Dict[str, str]] = None,
    colors: Optional[Dict[str, str]] = None,
) -> tags.div:
    """
    Renders a donut card:
      - title:        card title
      - values:       dict like {"MATCH": 10, "WARN": 2, "SUSPICIOUS": 1}
      - segments:     list of keys to render, in order (e.g., ["MATCH","WARN","SUSPICIOUS"])
      - radius:       outer radius in px (SVG viewBox space)
      - stroke:       ring thickness in px
      - center_label: optional text in the donut center (default = total)
      - legend_labels: map key->text shown in legend (default = key.title())
      - colors:       map key->CSS color (default = _DEFAULT_COLORS)
    """
    segments = list(segments or values.keys())
    legend_labels = legend_labels or {}
    colors = {**_DEFAULT_COLORS, **(colors or {})}

    # sanitize values + total
    safe_vals: Dict[str, int] = {}
    for k in segments:
        try:
            safe_vals[k] = int(values.get(k, 0) or 0)
        except Exception:
            safe_vals[k] = 0
    total = sum(safe_vals.values())
    if center_label is None:
        center_label = str(total)

    # geometry
    C = 2 * math.pi * (radius - stroke / 2.0)
    view = 2 * (radius + stroke)
    cx = cy = radius + stroke / 2.0

    svg_parts: List[str] = []
    svg_parts.append(
        f'<svg width="{view}" height="{view}" viewBox="0 0 {view} {view}" class="donut">'
    )

    if total <= 0:
        # empty ring
        svg_parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{radius - stroke/2:.2f}" '
            f'stroke="#e6e6e6" stroke-width="{stroke}" fill="none"></circle>'
        )
    else:
        # segments (stroke-dasharray trick)
        offset = 0.0
        for k in segments:
            v = safe_vals[k]
            if v <= 0:
                continue
            frac = v / total
            dash = C * frac
            col = colors.get(k, "#888")
            pct = _pct2(v, total)
            title_txt = f"{legend_labels.get(k, k.title())}: {v} ({pct:.2f}%)"
            svg_parts.append(
                f'<g>'
                f'<title>{html.escape(title_txt)}</title>'
                f'<circle cx="{cx}" cy="{cy}" r="{radius - stroke/2:.2f}" '
                f'stroke="{col}" stroke-width="{stroke}" fill="none" '
                f'stroke-dasharray="{dash:.3f} {C - dash:.3f}" '
                f'stroke-dashoffset="{-offset:.3f}" '
                f'transform="rotate(-90 {cx} {cy})"></circle>'
                f'</g>'
            )
            offset += dash

    # center label
    svg_parts.append(
        f'<text x="{cx}" y="{cy}" dominant-baseline="middle" text-anchor="middle" '
        f'style="font-weight:600; font-size:16px; fill:#2b2b2b">{html.escape(center_label)}</text>'
    )
    svg_parts.append("</svg>")

    # compose card: title | donut | legend
    card = tags.div(_class="donut-card")

    card.add(tags.div(html.escape(title), _class="donut-title"))

    wrap = tags.div(_class="donut-wrap")
    wrap.add(raw("".join(svg_parts)))
    card.add(wrap)

    # legend with clamped two-decimal percentages
    legend = tags.div(_class="donut-legend")
    for k in segments:
        v = safe_vals.get(k, 0)
        pct = _pct2(v, total)
        row = tags.div(_class="legend-row")
        swatch = tags.span(_class="legend-swatch")
        swatch['style'] = f"background:{colors.get(k, '#888')}"
        row.add(swatch)
        label = legend_labels.get(k, k.title())
        row.add(tags.span(f"{label}: ", _class="legend-text"))
        row.add(tags.span(str(v), _class="legend-text"))
        row.add(tags.span(f" ({pct:.2f}%)", _class="legend-text"))
        legend.add(row)

    card.add(legend)
    return card
