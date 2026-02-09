# scrutiny-viz/scrutiny/reporting/viz/chart/__init__.py
from __future__ import annotations
from typing import Any, Dict, Optional
from .default import render_donut_block

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
    v = (variant or "default").strip().lower()
    if v == "default":
        return render_donut_block(
            title, counts,
            segments=segments,
            radius=radius,
            stroke=stroke,
            center_label=center_label,
            legend_labels=legend_labels,
        )
    return render_donut_block(
        title, counts,
        segments=segments,
        radius=radius,
        stroke=stroke,
        center_label=center_label,
        legend_labels=legend_labels,
    )
