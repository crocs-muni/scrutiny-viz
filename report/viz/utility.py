# scrutiny-viz/report/viz/utility.py
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from dominate import tags


_BOOLISH_TRUE = {"true", "yes", "supported", "1"}
_BOOLISH_FALSE = {"false", "no", "unsupported", "0"}


def to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def format_number(value: Any, *, precision: int = 8, trim: bool = False) -> str:
    if value is None:
        return ""
    try:
        result = f"{float(value):.{precision}f}"
        if trim:
            result = result.rstrip("0").rstrip(".")
        return result
    except Exception:
        return str(value)


def format_percent(value: Any, *, precision: int = 4) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.{precision}f}%"
    except Exception:
        return str(value)


def format_pp(value: Any, *, precision: int = 4) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):+.{precision}f} pp"
    except Exception:
        return str(value)


def first_token(value: str) -> str:
    text = (value or "").strip()
    return text.split()[0] if text else ""


def render_table_block(headers: List[str], rows: List[List[Any]]) -> tags.div:
    container = tags.div(_class="table-container")
    with container:
        tbl = tags.table(_class="report-table")
        with tbl:
            with tags.thead():
                with tags.tr():
                    for header in headers:
                        tags.th(str(header))
            with tags.tbody():
                for row in rows or []:
                    cells = row if isinstance(row, (list, tuple)) else [row]
                    with tags.tr():
                        for cell in cells:
                            if hasattr(cell, "__html__") or hasattr(cell, "render"):
                                tags.td(cell)
                            else:
                                tags.td("" if cell is None else str(cell))
    return container


def badge(text: str, kind: str) -> tags.span:
    return tags.span(text, cls=f"badge badge-{kind}")


def state_badge(state: str) -> tags.span:
    state_up = str(state or "").upper()
    kind = "neutral"
    if state_up == "MATCH":
        kind = "ok"
    elif state_up == "WARN":
        kind = "warn"
    elif state_up == "SUSPICIOUS":
        kind = "bad"
    return badge(state_up or "UNKNOWN", kind)


def state_border_style(state: str) -> str:
    state_up = str(state or "").upper()
    if state_up == "MATCH":
        return "border:2px solid var(--green-color);"
    if state_up == "WARN":
        return "border:2px solid var(--yellow-color);"
    return "border:2px solid var(--red-color);"


def bool_to_badge(value: Any) -> tags.span:
    if isinstance(value, bool):
        return badge("Supported", "ok") if value else badge("Unsupported", "bad")

    lowered = str(value).strip().lower()
    if lowered in _BOOLISH_TRUE:
        return badge("Supported", "ok")
    if lowered in _BOOLISH_FALSE:
        return badge("Unsupported", "bad")
    return badge("Unknown", "neutral")


def is_boolish_value(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if value is None:
        return False
    lowered = str(value).strip().lower()
    return lowered in _BOOLISH_TRUE | _BOOLISH_FALSE


def row_key(row: Dict[str, Any]) -> str | None:
    if not isinstance(row, dict):
        return None
    for key_name in ("field", "name", "key", "group", "edge_id", "cell_id"):
        value = row.get(key_name)
        if value is not None:
            return str(value)
    return None


def row_value(row: Dict[str, Any]) -> str:
    if not isinstance(row, dict):
        return ""
    value = row.get("value")
    return "" if value is None else str(value)


def source_maps(section: Dict[str, Any], key_field: str) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    source_rows = section.get("source_rows") or {}
    ref_rows = source_rows.get("reference") or []
    test_rows = source_rows.get("tested") or source_rows.get("profile") or []

    ref_map: Dict[str, Dict[str, Any]] = {}
    test_map: Dict[str, Dict[str, Any]] = {}

    for row in ref_rows:
        if isinstance(row, dict) and row.get(key_field) is not None:
            ref_map[str(row[key_field])] = row

    for row in test_rows:
        if isinstance(row, dict) and row.get(key_field) is not None:
            test_map[str(row[key_field])] = row

    return ref_map, test_map


def comparison_similarity_percentages(comparison_results: List[Dict[str, Any]]) -> tuple[float, float, float]:
    if not comparison_results:
        return (0.0, 0.0, 0.0)

    total = float(len(comparison_results))
    match = sum(1 for row in comparison_results if str(row.get("comparison_state", "")).upper() == "MATCH")
    warn = sum(1 for row in comparison_results if str(row.get("comparison_state", "")).upper() == "WARN")
    suspicious = sum(1 for row in comparison_results if str(row.get("comparison_state", "")).upper() == "SUSPICIOUS")
    return (match / total * 100.0, warn / total * 100.0, suspicious / total * 100.0)


def operation_similarity_percentages(operation: Dict[str, Any]) -> tuple[float, float, float]:
    pipeline_results = operation.get("comparison_results") or []
    if not pipeline_results:
        return (0.0, 0.0, 0.0)

    match_total = 0.0
    warn_total = 0.0
    suspicious_total = 0.0

    for pipeline in pipeline_results:
        match_pct, warn_pct, suspicious_pct = comparison_similarity_percentages(
            pipeline.get("comparison_results") or []
        )
        match_total += match_pct
        warn_total += warn_pct
        suspicious_total += suspicious_pct

    divisor = float(len(pipeline_results))
    return (match_total / divisor, warn_total / divisor, suspicious_total / divisor)


@contextmanager
def toggle_block(
    *,
    block_id: str,
    title: str,
    button_text: str,
    heading_tag: str = "h5",
    button_title: str | None = None,
    hide: bool = False,
):
    with tags.div(cls="toggle-header"):
        getattr(tags, heading_tag)(title, cls="toggle-title")
        tags.button(
            button_text,
            cls="toggle-btn",
            title=(button_title or title),
            onclick=f"hideButton('{block_id}')",
            **{"data-toggle-target": block_id, "aria-expanded": "false"},
        )
    style = "display:none;" if hide else "display:block;"
    with tags.div(
        id=block_id,
        cls="toggle-block",
        style=style,
        **{"data-default": "hide" if hide else "show"},
    ):
        yield
