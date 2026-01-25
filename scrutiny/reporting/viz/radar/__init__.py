from __future__ import annotations
from typing import Any, Dict, Optional
from .default import render_radar_block

def render_radar_variant(
    *,
    section_name: str,
    section: Dict[str, Any],
    idx: int,
    variant: Optional[str] = None,
) -> Any:
    v = (variant or "default").strip().lower()
    if v == "default":
        return render_radar_block(section_name, section, idx)
    return render_radar_block(section_name, section, idx)
