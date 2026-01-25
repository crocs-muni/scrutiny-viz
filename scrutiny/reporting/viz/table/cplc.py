from __future__ import annotations

from typing import Any, Dict, List
from dominate import tags

from .default import render_table_block


def _first_token(s: str) -> str:
    s = (s or "").strip()
    return s.split()[0] if s else ""


def render_cplc_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    """
    CPLC variant table:
      - Always renders a full side-by-side CPLC table (even when everything matches)
      - Uses section["source_rows"] produced by verify.py / assemble_report (recommended)
    """
    src = section.get("source_rows") or {}
    ref_rows = src.get("reference") or []
    tst_rows = src.get("tested") or src.get("profile") or []

    # Build field->value maps
    ref_map: Dict[str, str] = {}
    tst_map: Dict[str, str] = {}

    for r in ref_rows:
        if isinstance(r, dict) and r.get("field") is not None:
            ref_map[str(r["field"])] = "" if r.get("value") is None else str(r.get("value"))

    for r in tst_rows:
        if isinstance(r, dict) and r.get("field") is not None:
            tst_map[str(r["field"])] = "" if r.get("value") is None else str(r.get("value"))

    keys = sorted(set(ref_map.keys()) | set(tst_map.keys()))

    rows: List[List[Any]] = []
    for k in keys:
        rv = ref_map.get(k, "Missing")
        tv = tst_map.get(k, "Missing")

        mismatch = (rv == "Missing" or tv == "Missing" or _first_token(rv) != _first_token(tv))
        if mismatch:
            # visually emphasize mismatches (no dependency on special table features)
            rv_node = tags.span(rv, style="font-weight:700;")
            tv_node = tags.span(tv, style="font-weight:700;")
            rows.append([k, rv_node, tv_node])
        else:
            rows.append([k, rv, tv])

    headers = ["CPLC Field", f"{ref_name} (reference)", f"{prof_name} (profiled)"]
    return render_table_block(headers, rows)
