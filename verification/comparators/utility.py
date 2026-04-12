# scrutiny-viz/verification/comparators/utility.py
from __future__ import annotations

import json
from typing import Any, Iterable, List, Optional


STATE_ORDER = {"MATCH": 0, "WARN": 1, "SUSPICIOUS": 2}


def to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def sort_mixed_keys(values: Iterable[Any]) -> list[Any]:
    return sorted(values, key=lambda x: (str(type(x)), str(x)))


def build_row_map(rows: list[dict[str, Any]], key_field: str) -> dict[Any, dict[str, Any]]:
    return {
        row.get(key_field): row
        for row in rows
        if isinstance(row, dict) and row.get(key_field) is not None
    }


def build_string_key_map(rows: list[dict[str, Any]], key_field: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        key = row.get(key_field)
        if key is None:
            continue
        out[str(key)] = row
    return out


def get_display_label(row: dict[str, Any], key_field: str, show_field: Optional[str]) -> str:
    if show_field and row.get(show_field) is not None:
        return str(row.get(show_field))
    return str(row.get(key_field))


def load_jsonish(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, type(default)):
        return raw
    try:
        return json.loads(str(raw))
    except Exception:
        return default


def max_state(states: List[str], *, default: str = "MATCH") -> str:
    if not states:
        return default
    return max((str(s).upper() for s in states), key=lambda s: STATE_ORDER.get(s, 0))
