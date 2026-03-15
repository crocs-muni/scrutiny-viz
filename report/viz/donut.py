# scrutiny-viz/report/viz/donut.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from dominate import tags
from dominate.util import raw
import math
import html

from .contracts import VizPlugin, VizSpec

_DEFAULT_COLORS = {
    "MATCH": "#49b473",
    "WARN": "#c9b400",
    "SUSPICIOUS": "#d3923e",
    "ERROR": "#c04444",
}


def _pct2(value: float, total: float) -> float:
    if total <= 0:
        return 0.0
    pct = (float(value) / float(total)) * 100.0
    if pct < 0:
        pct = 0.0
    elif pct > 100.0:
        pct = 100.0
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
    segments = list(segments or values.keys())
    legend_labels = legend_labels or {}
    colors = {**_DEFAULT_COLORS, **(colors or {})}

    safe_vals: Dict[str, int] = {}
    for k in segments:
        try:
            safe_vals[k] = int(values.get(k, 0) or 0)
        except Exception:
            safe_vals[k] = 0

    total = sum(safe_vals.values())
    if center_label is None:
        center_label = str(total)

    C = 2 * math.pi * (radius - stroke / 2.0)
    view = 2 * (radius + stroke)
    cx = cy = radius + stroke / 2.0

    svg_parts: List[str] = []
    svg_parts.append(
        f'<svg width="{view}" height="{view}" viewBox="0 0 {view} {view}" class="donut">'
    )

    if total <= 0:
        svg_parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{radius - stroke/2:.2f}" '
            f'stroke="#e6e6e6" stroke-width="{stroke}" fill="none"></circle>'
        )
    else:
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

    svg_parts.append(
        f'<text x="{cx}" y="{cy}" dominant-baseline="middle" text-anchor="middle" '
        f'style="font-weight:600; font-size:16px; fill:#2b2b2b">{html.escape(str(center_label))}</text>'
    )
    svg_parts.append("</svg>")

    card = tags.div(_class="donut-card")
    card.add(tags.div(html.escape(title), _class="donut-title"))

    wrap = tags.div(_class="donut-wrap")
    wrap.add(raw("".join(svg_parts)))
    card.add(wrap)

    legend = tags.div(_class="donut-legend")
    for k in segments:
        v = safe_vals.get(k, 0)
        pct = _pct2(v, total)
        row = tags.div(_class="legend-row")

        swatch = tags.span(_class="legend-swatch")
        swatch["style"] = f"background:{colors.get(k, '#888')}"
        row.add(swatch)

        label = legend_labels.get(k, k.title())
        row.add(tags.span(f"{label}: ", _class="legend-text"))
        row.add(tags.span(str(v), _class="legend-text"))
        row.add(tags.span(f" ({pct:.2f}%)", _class="legend-text"))

        legend.add(row)

    card.add(legend)
    return card


def render_donut_variant(
    title: str,
    counts: Dict[str, int],
    *,
    segments,
    radius: int,
    stroke: int,
    center_label: str = "",
    legend_labels: Optional[Dict[str, str]] = None,
    variant: Optional[str] = None,
) -> Any:
    return render_donut_block(
        title,
        counts,
        segments=segments,
        radius=radius,
        stroke=stroke,
        center_label=center_label,
        legend_labels=legend_labels,
    )


class DonutVizPlugin(VizPlugin):
    spec = VizSpec(
        name="donut",
        slot="utility",
        aliases=(),
        description="Donut visualization for dashboard summary cards.",
    )

    def render(self, **kwargs: Any) -> Any:
        return render_donut_variant(
            kwargs["title"],
            kwargs["counts"],
            segments=kwargs["segments"],
            radius=kwargs["radius"],
            stroke=kwargs["stroke"],
            center_label=kwargs.get("center_label", ""),
            legend_labels=kwargs.get("legend_labels"),
            variant=kwargs.get("variant"),
        )


PLUGINS = [DonutVizPlugin()]
