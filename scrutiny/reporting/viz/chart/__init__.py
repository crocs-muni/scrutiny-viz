from __future__ import annotations
from typing import Any, Dict, Optional, Tuple

from .default import render_bar_pair_block, render_chart_table_block

def render_chart_variant(
    *,
    section_name: str,
    section: Dict[str, Any],
    idx: int,
    variant: Optional[str] = None,
) -> Tuple[Any, Any]:
    """
    Returns (chart_node, optional_table_node). Either can be None.
    """
    v = (variant or "default").strip().lower()

    if v == "default":
        return (
            render_bar_pair_block(section_name, section, idx),
            render_chart_table_block(section_name, section, idx),
        )

    return (
        render_bar_pair_block(section_name, section, idx),
        render_chart_table_block(section_name, section, idx),
    )
