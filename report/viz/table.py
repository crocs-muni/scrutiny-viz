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
    for key_name in ("field", "name", "key", "group", "edge_id", "cell_id"):
        v = row.get(key_name)
        if v is not None:
            return str(v)
    return None


def _row_value(row: Dict[str, Any]) -> str:
    if not isinstance(row, dict):
        return ""
    v = row.get("value")
    return "" if v is None else str(v)


def _fmt_pct(v: Any) -> str:
    if v is None:
        return ""
    try:
        return f"{float(v):.4f}%"
    except Exception:
        return str(v)


def _fmt_pp(v: Any) -> str:
    if v is None:
        return ""
    try:
        return f"{float(v):+.4f} pp"
    except Exception:
        return str(v)


def _fmt_num(v: Any) -> str:
    if v is None:
        return ""
    try:
        return f"{float(v):.8f}"
    except Exception:
        return str(v)


def _source_maps(section: Dict[str, Any], key_field: str) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    src = section.get("source_rows") or {}
    ref_rows = src.get("reference") or []
    tst_rows = src.get("tested") or src.get("profile") or []

    ref_map: Dict[str, Dict[str, Any]] = {}
    tst_map: Dict[str, Dict[str, Any]] = {}

    for r in ref_rows:
        if isinstance(r, dict) and r.get(key_field) is not None:
            ref_map[str(r[key_field])] = r
    for r in tst_rows:
        if isinstance(r, dict) and r.get(key_field) is not None:
            tst_map[str(r[key_field])] = r

    return ref_map, tst_map


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


def render_rsabias_accuracy_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    ref_map, tst_map = _source_maps(section, "group")
    keys = sorted(set(ref_map.keys()) | set(tst_map.keys()), key=lambda x: (0, int(x)) if str(x).isdigit() else (1, x))

    rows: List[List[Any]] = []
    for k in keys:
        rr = ref_map.get(k, {})
        tr = tst_map.get(k, {})
        rv = rr.get("accuracy_pct")
        tv = tr.get("accuracy_pct")
        delta = (float(tv) - float(rv)) if (rv is not None and tv is not None) else None

        rows.append([
            k,
            rr.get("correct", ""),
            rr.get("wrong", ""),
            rr.get("total", ""),
            _fmt_pct(rv),
            tr.get("correct", ""),
            tr.get("wrong", ""),
            tr.get("total", ""),
            _fmt_pct(tv),
            _fmt_pp(delta),
        ])

    headers = [
        "Group",
        f"{ref_name} correct",
        f"{ref_name} wrong",
        f"{ref_name} total",
        f"{ref_name} accuracy",
        f"{prof_name} correct",
        f"{prof_name} wrong",
        f"{prof_name} total",
        f"{prof_name} accuracy",
        "Δ accuracy",
    ]
    return render_table_block(headers, rows)


def render_rsabias_confusion_top_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    ref_map, tst_map = _source_maps(section, "edge_id")
    keys = sorted(set(ref_map.keys()) | set(tst_map.keys()))

    rows: List[List[Any]] = []
    for k in keys:
        rr = ref_map.get(k, {})
        tr = tst_map.get(k, {})
        rv = rr.get("share_pct")
        tv = tr.get("share_pct")
        delta = (float(tv) - float(rv)) if (rv is not None and tv is not None) else None

        true_group = rr.get("true_group", tr.get("true_group", ""))
        pred_group = rr.get("pred_group", tr.get("pred_group", ""))

        rows.append([
            true_group,
            pred_group,
            _fmt_pct(rv),
            _fmt_pct(tv),
            _fmt_pp(delta),
        ])

    headers = ["True group", "Predicted group", f"{ref_name} share", f"{prof_name} share", "Δ share"]
    return render_table_block(headers, rows)


def render_rsabias_matrix_top_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    artifacts = section.get("artifacts") or {}
    changes = artifacts.get("top_changed_cells") or []
    if not changes:
        return None

    rows: List[List[Any]] = []
    for ch in changes:
        rows.append([
            ch.get("row_label", ch.get("row_index", "")),
            ch.get("col_label", ch.get("col_index", "")),
            _fmt_pct((float(ch["ref_value"]) * 100.0) / 100.0) if ch.get("ref_value") is not None else "",
            _fmt_pct((float(ch["profile_value"]) * 100.0) / 100.0) if ch.get("profile_value") is not None else "",
            _fmt_pp(ch.get("delta_pp")),
        ])

    headers = ["Row", "Column", f"{ref_name} value", f"{prof_name} value", "Δ value"]
    return render_table_block(headers, rows)


def render_table_variant(*, section_name: str, section: Dict[str, Any], ref_name: str, prof_name: str, variant: Optional[str] = None):
    v = (variant or "").strip().lower() if variant else None

    if v == "cplc":
        return render_cplc_table(section, ref_name, prof_name)
    if v == "rsabias_accuracy":
        return render_rsabias_accuracy_table(section, ref_name, prof_name)
    if v == "rsabias_confusion_top":
        return render_rsabias_confusion_top_table(section, ref_name, prof_name)
    if v == "rsabias_matrix_top":
        return render_rsabias_matrix_top_table(section, ref_name, prof_name)

    return None


class TableVizPlugin(VizPlugin):
    spec = VizSpec(
        name="table",
        slot="table",
        aliases=(),
        description="Section table renderer, including specialized variants like CPLC and RSABias views.",
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