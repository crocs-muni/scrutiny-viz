# scrutiny-viz/report/viz/table.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from dominate import tags

from .contracts import VizPlugin, VizSpec


def render_table_block(headers: List[str], rows: List[List[Any]]):
    container = tags.div(_class="table-container")
    with container:
        t = tags.table(_class="report-table")
        with t:
            with tags.thead():
                with tags.tr():
                    for h in headers:
                        tags.th(str(h))
            with tags.tbody():
                for r in rows or []:
                    cells = r if isinstance(r, (list, tuple)) else [r]
                    with tags.tr():
                        for c in cells:
                            if hasattr(c, "__html__") or hasattr(c, "render"):
                                tags.td(c)
                            else:
                                tags.td(str(c))
    return container


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


def render_table_variant(*, section_name: str, section: Dict[str, Any], ref_name: str, prof_name: str, variant: Optional[str] = None):
    v = (variant or "").strip().lower() if variant else None
    if v == "cplc":
        return render_cplc_table(section, ref_name, prof_name)
    return None


class TableVizPlugin(VizPlugin):
    spec = VizSpec(
        name="table",
        slot="table",
        aliases=(),
        description="Section table renderer, including specialized variants like CPLC.",
    )

    def render(self, **kwargs: Any) -> Any:
        return render_table_variant(
            section_name=kwargs["section_name"],
            section=kwargs["section"],
            ref_name=kwargs["ref_name"],
            prof_name=kwargs["prof_name"],
            variant=kwargs.get("variant"),
        )


PLUGINS = [TableVizPlugin()]
