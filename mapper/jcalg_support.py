# scrutiny-viz/mapper/jcalg_parser.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from mapper_utils import create_attribute, to_float, to_int, to_bool

BASIC_INFO = "Basic information"
END_OF_BASIC_INFO = "JavaCard support version"


def _split_group_and_alg(first_cell: str) -> Tuple[str, Optional[str]]:
    s = (first_cell or "").strip()
    if "." in s:
        group, alg = s.split(".", 1)
        return group.strip(), (alg.strip() or None)
    return s, None


def _parse_basic_line(line: str, delimiter: str) -> Optional[dict]:
    parts = (line or "").split(delimiter)
    if len(parts) < 2:
        return None
    name = parts[0].strip()
    value = parts[1].strip()
    if not name:
        return None
    return create_attribute(name, value)


def _looks_like_alg_name(s: str) -> bool:
    s = (s or "").strip()
    if not s:
        return False
    low = s.lower()
    if low in {"yes", "no", "true", "false", "0", "1"}:
        return False
    if s.startswith(("ALG_", "TYPE_", "CIPHER_")):
        return True
    return ("_" in s) and (" " not in s)


def _norm_supported(s: str) -> Optional[str]:
    raw = (s or "").strip()
    b = to_bool(raw)
    if b is None:
        return None
    return "yes" if b else "no"


def _parse_alg_row(parts: list[str], section_name: str) -> Optional[dict]:
    if len(parts) < 2:
        return None

    # ----- Format C: Algorithm;yes;time -----
    # Example: ALG_DES_ECB_NOPAD;yes;0.045000
    if _looks_like_alg_name(parts[0]):
        sup = _norm_supported(parts[1])
        if sup is not None:
            return {"algorithm_name": parts[0].strip(), "is_supported": sup}

    # ----- Format A / B -----
    first = parts[0].strip()
    g_from_cell, alg_from_cell = _split_group_and_alg(first)

    if alg_from_cell is not None:
        # A) Group.Algorithm;yes;time
        algorithm_name = alg_from_cell
        supported_raw = parts[1].strip() if len(parts) > 1 else ""
    else:
        # B) Group;Algorithm;yes;time
        if len(parts) < 3:
            return None
        algorithm_name = parts[1].strip()
        supported_raw = parts[2].strip()

    if not (g_from_cell or section_name):
        return None
    if not _looks_like_alg_name(algorithm_name):
        return None

    sup = _norm_supported(supported_raw)
    if sup is None:
        return None

    return {"algorithm_name": algorithm_name, "is_supported": sup}


def _detect_section_name(group: list[str], delimiter: str) -> Tuple[Optional[str], list[str]]:
    if not group:
        return None, []

    first_line = (group[0] or "").strip()
    if delimiter not in first_line:
        return first_line, group[1:]

    parts = first_line.split(delimiter)
    section, _ = _split_group_and_alg(parts[0])
    return (section or None), group


def convert_to_map_jcalgsupport(groups: list[list[str]], delimiter: str) -> dict:
    result: Dict[str, Any] = {"_type": "javacard-alg-support"}
    basic_attrs: list[dict] = []

    finished_basic = False

    for group in groups:
        if not group:
            continue

        if not finished_basic:
            for line in group:
                if END_OF_BASIC_INFO in (line or ""):
                    finished_basic = True
                attr = _parse_basic_line(line, delimiter)
                if attr:
                    basic_attrs.append(attr)
            continue

        section, data_lines = _detect_section_name(group, delimiter)
        if not section:
            continue

        if section in {"JCSystem", "CPLC"}:
            kvs: list[dict] = []
            for line in data_lines:
                attr = _parse_basic_line(line, delimiter)
                if attr:
                    kvs.append(attr)
            if kvs:
                result.setdefault(section, []).extend(kvs)
            continue

        out_rows: list[dict] = []
        for line in data_lines:
            parts = [p.strip() for p in (line or "").split(delimiter)]
            if len(parts) < 2:
                continue
            if parts[0].strip() == END_OF_BASIC_INFO:
                continue

            rec = _parse_alg_row(parts, section)
            if rec:
                out_rows.append(rec)

        if out_rows:
            result.setdefault(section, []).extend(out_rows)

    if basic_attrs:
        result[BASIC_INFO] = basic_attrs

    return result


# Backwards-compatible aliases
convert_to_map = convert_to_map_jcalgsupport
convert_to_map_jcalg_support = convert_to_map_jcalgsupport