from __future__ import annotations

from typing import Any, Dict, Optional

from .default import render_table_block
from .cplc import render_cplc_table


def render_table_variant(
    *,
    section_name: str,
    section: Dict[str, Any],
    ref_name: str,
    prof_name: str,
    variant: Optional[str] = None,
):
    """
    Dispatch table rendering based on variant.
    - variant=None -> caller uses generic diff tables (existing report_html behavior)
    - variant='cplc' -> full CPLC side-by-side table
    """
    v = (variant or "").strip().lower() if variant else None
    if v == "cplc":
        return render_cplc_table(section, ref_name, prof_name)

    return None
