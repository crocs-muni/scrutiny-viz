# scrutiny-viz/scrutiny/reporting/viz/table/cplc.py
from __future__ import annotations
from typing import Any, Dict, List
from dominate import tags
from .default import render_table_block


def _first_token(s: str) -> str:
    s = (s or "").strip()
    return s.split()[0] if s else ""


def _row_key(row: Dict[str, Any]) -> str | None:
    if not isinstance(row, dict):
        return None
    for key_name in ("field", "name", "key"):
        v = row.get(key_name)
        if v is not None:
            return str(v)
    return None


def _row_value(row: Dict[str, Any]) -> str:
    if not isinstance(row, dict):
        return ""
    v = row.get("value")
    return "" if v is None else str(v)


def render_cplc_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    src = section.get("source_rows") or {}
    ref_rows = src.get("reference") or []
    tst_rows = src.get("tested") or src.get("profile") or []

    ref_map: Dict[str, str] = {}
    tst_map: Dict[str, str] = {}

    for r in ref_rows:
        if isinstance(r, dict):
            k = _row_key(r)
            if k is not None:
                ref_map[k] = _row_value(r)

    for r in tst_rows:
        if isinstance(r, dict):
            k = _row_key(r)
            if k is not None:
                tst_map[k] = _row_value(r)

    keys = sorted(set(ref_map.keys()) | set(tst_map.keys()))

    rows: List[List[Any]] = []
    for k in keys:
        rv = ref_map.get(k, "Missing")
        tv = tst_map.get(k, "Missing")

        mismatch = (rv == "Missing" or tv == "Missing" or _first_token(rv) != _first_token(tv))
        if mismatch:
            rv_node = tags.span(rv, style="font-weight:700;")
            tv_node = tags.span(tv, style="font-weight:700;")
            rows.append([k, rv_node, tv_node])
        else:
            rows.append([k, rv, tv])

    headers = ["CPLC Field", f"{ref_name} (reference)", f"{prof_name} (profiled)"]
    return render_table_block(headers, rows)