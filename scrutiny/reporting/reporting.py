# scrutiny-viz/scrutiny/reporting/reporting.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

_ORDER = {"MATCH": 0, "WARN": 1, "SUSPICIOUS": 2}


def _max_state(left: str, right: str) -> str:
    return left if _ORDER.get(left, 1) >= _ORDER.get(right, 1) else right


def compute_severity(
    meta: dict,
    changed: int,
    compared: int,
    only_ref: int = 0,
    only_test: int = 0,
) -> str:
    """Return MATCH/WARN/SUSPICIOUS based on thresholds.

    Presence-only differences are treated as SUSPICIOUS immediately.
    """
    if only_ref > 0 or only_test > 0:
        return "SUSPICIOUS"

    if compared == 0 or changed == 0:
        return "MATCH"

    threshold_ratio = meta.get("threshold_ratio")
    threshold_count = meta.get("threshold_count")

    if isinstance(threshold_ratio, (int, float, str)):
        try:
            threshold_ratio = float(threshold_ratio)
        except Exception:
            threshold_ratio = None

    if isinstance(threshold_count, (int, float, str)):
        try:
            threshold_count = int(threshold_count)
        except Exception:
            threshold_count = None

    if isinstance(threshold_ratio, float) and 0 <= threshold_ratio <= 1 and compared > 0:
        ratio = changed / float(compared)
        return "SUSPICIOUS" if ratio >= threshold_ratio else "WARN"

    if isinstance(threshold_count, int) and threshold_count > 0:
        return "SUSPICIOUS" if changed >= threshold_count else "WARN"

    return "WARN"


def _tally_stats(diffs: List[Dict[str, Any]], matches: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Infer stats from diffs/matches:
      - presence diffs (field == "__presence__") increment only_ref/only_test
      - all other diffs increment changed
      - matches length → matched
      - compared = changed + matched + only_ref + only_test
    """
    only_ref = 0
    only_test = 0
    changed = 0

    for diff in diffs or []:
        if diff.get("field") != "__presence__":
            changed += 1
            continue

        ref_value = diff.get("ref")
        test_value = diff.get("test")
        if isinstance(ref_value, bool) and isinstance(test_value, bool):
            if ref_value and not test_value:
                only_ref += 1
            elif test_value and not ref_value:
                only_test += 1
            else:
                changed += 1
        else:
            changed += 1

    matched = len(matches or [])
    compared = changed + matched + only_ref + only_test
    return {
        "compared": compared,
        "changed": changed,
        "matched": matched,
        "only_ref": only_ref,
        "only_test": only_test,
    }


def _merge_severity_meta(schema: Dict[str, Any], section_name: str, section_res: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge severity thresholds with precedence:
      1) schema.sections[section].component.*
      2) section_res.report.severity
      3) section_res.severity
    """
    merged: Dict[str, Any] = {}

    if isinstance(schema, dict):
        section_cfg = schema.get(section_name, {}) or {}
        if isinstance(section_cfg, dict):
            component_cfg = section_cfg.get("component", {}) or {}
            if isinstance(component_cfg, dict):
                if component_cfg.get("threshold_ratio") is not None:
                    merged["threshold_ratio"] = component_cfg.get("threshold_ratio")
                if component_cfg.get("threshold_count") is not None:
                    merged["threshold_count"] = component_cfg.get("threshold_count")

    report_cfg = section_res.get("report", {})
    if isinstance(report_cfg, dict):
        report_severity = report_cfg.get("severity", {})
        if isinstance(report_severity, dict):
            merged.update(report_severity)

    severity_cfg = section_res.get("severity", {})
    if isinstance(severity_cfg, dict):
        merged.update(severity_cfg)

    return merged


def _parse_boolish(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return 1.0 if float(value) != 0.0 else 0.0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"yes", "true", "1"}:
            return 1.0
        if lowered in {"no", "false", "0"}:
            return 0.0
    return None


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except Exception:
            return None
    return None


def _collect_numeric_pairs_from_chart(chart_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pairs: List[Dict[str, Any]] = []
    for row in chart_rows or []:
        ref_raw = _parse_number(row.get("ref_avg"))
        test_raw = _parse_number(row.get("test_avg"))
        if ref_raw is None and test_raw is None:
            continue
        pairs.append(
            {
                "key": str(row.get("key", "")),
                "ref_raw": ref_raw,
                "test_raw": test_raw,
                "kind": "numeric",
            }
        )
    return pairs


def _collect_pairs_from_rows(diffs: List[Dict[str, Any]], matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fallback extraction (when no chart_rows):
      - Prefer explicit ref/test in diffs
      - For matches, use value for both ref/test
      - Parse as bool first; else numeric; else drop
    """
    buffer: Dict[str, Dict[str, Any]] = {}

    for diff in diffs or []:
        key = str(diff.get("key", ""))
        item = buffer.setdefault(key, {})
        item.setdefault("ref_raw", diff.get("ref"))
        item.setdefault("test_raw", diff.get("test"))

    for match in matches or []:
        key = str(match.get("key", ""))
        value = match.get("value")
        item = buffer.setdefault(key, {})
        item.setdefault("ref_raw", value)
        item.setdefault("test_raw", value)

    pairs: List[Dict[str, Any]] = []
    for key, payload in buffer.items():
        ref_raw = payload.get("ref_raw")
        test_raw = payload.get("test_raw")

        ref_bool = _parse_boolish(ref_raw)
        test_bool = _parse_boolish(test_raw)
        if ref_bool is not None or test_bool is not None:
            pairs.append(
                {
                    "key": key,
                    "ref_raw": ref_bool if ref_bool is not None else 0.0,
                    "test_raw": test_bool if test_bool is not None else 0.0,
                    "kind": "bool",
                }
            )
            continue

        ref_num = _parse_number(ref_raw)
        test_num = _parse_number(test_raw)
        if ref_num is None and test_num is None:
            continue

        pairs.append(
            {
                "key": key,
                "ref_raw": ref_num if ref_num is not None else 0.0,
                "test_raw": test_num if test_num is not None else 0.0,
                "kind": "numeric",
            }
        )

    return pairs


def _normalize_pairs(pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Produce ref_score/test_score in [0,1], preserve raw values and kind.
      - bool: already 0/1
      - numeric: divide by max of all raw (across ref+test)
    """
    if not pairs:
        return []

    max_value = 0.0
    for pair in pairs:
        if pair.get("kind") != "numeric":
            continue
        for field in ("ref_raw", "test_raw"):
            value = pair.get(field)
            if isinstance(value, (int, float)) and float(value) > max_value:
                max_value = float(value)

    if max_value <= 0:
        max_value = 1.0

    normalized: List[Dict[str, Any]] = []
    for pair in pairs:
        kind = pair.get("kind", "numeric")
        ref_raw = float(pair.get("ref_raw") or 0.0)
        test_raw = float(pair.get("test_raw") or 0.0)

        if kind == "bool":
            ref_score = 1.0 if ref_raw >= 0.5 else 0.0
            test_score = 1.0 if test_raw >= 0.5 else 0.0
        else:
            ref_score = ref_raw / max_value
            test_score = test_raw / max_value

        normalized.append(
            {
                "key": str(pair.get("key", "")),
                "ref_score": ref_score,
                "test_score": test_score,
                "ref_raw": ref_raw,
                "test_raw": test_raw,
                "kind": kind,
            }
        )

    return normalized


def _normalize_types_from_schema(explicit_types: Any) -> List[Dict[str, Any]]:
    if explicit_types is None:
        return []

    normalized: List[Dict[str, Any]] = []

    if isinstance(explicit_types, list):
        for item in explicit_types:
            if isinstance(item, str):
                value = item.strip().lower()
                if value:
                    normalized.append({"type": value, "variant": None})
            elif isinstance(item, dict):
                type_name = str(item.get("type") or "").strip().lower()
                if not type_name:
                    continue
                variant = item.get("variant")
                variant = str(variant).strip().lower() if variant is not None and str(variant).strip() else None
                normalized.append({"type": type_name, "variant": variant})
        return normalized

    if isinstance(explicit_types, str):
        for item in explicit_types.split(","):
            value = item.strip().lower()
            if value:
                normalized.append({"type": value, "variant": None})

    return normalized


def _pick_global_theme(schema: Dict[str, Any]) -> str:
    if not isinstance(schema, dict):
        return "light"

    for section_cfg in schema.values():
        if not isinstance(section_cfg, dict):
            continue
        report_cfg = section_cfg.get("report") or {}
        if not isinstance(report_cfg, dict):
            continue
        theme = report_cfg.get("theme")
        if isinstance(theme, str) and theme.strip():
            normalized = theme.strip().lower()
            if normalized in {"light", "dark"}:
                return normalized

    return "light"


def _default_ingest_meta(schema: Dict[str, Any]) -> Dict[str, Any]:
    schema_meta = getattr(schema, "_loader_meta", {}) or {}
    return {
        "dynamic_sections_enabled": bool(schema_meta.get("dynamic_sections", False)),
        "strict_sections": bool(schema_meta.get("strict_sections", False)),
        "allow_missing_sections": bool(schema_meta.get("allow_missing_sections", True)),
        "applied_dynamic_sections": [],
        "applied_dynamic_sections_reference": [],
        "applied_dynamic_sections_profile": [],
        "skipped_sections": [],
        "skipped_sections_count": 0,
    }


def assemble_report(
    *,
    schema: Dict[str, Any],
    compare_results: Dict[str, Dict[str, Any]],
    reference_name: str,
    profile_name: str,
    section_rows: Dict[str, Any] | None = None,
    ingest_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sections_out: Dict[str, Any] = {}
    overall = "MATCH"

    overall_counts = {"MATCH": 0, "WARN": 0, "SUSPICIOUS": 0}
    by_section: Dict[str, Dict[str, int]] = {}

    theme = _pick_global_theme(schema)
    ingest_payload = dict(ingest_meta or _default_ingest_meta(schema))

    for section_name, result_payload in (compare_results or {}).items():
        diffs = result_payload.get("diffs", []) or []
        matches = result_payload.get("matches", []) or []
        artifacts = result_payload.get("artifacts", {}) or {}

        chart_rows = result_payload.get("chart_rows")
        if chart_rows is None:
            chart_rows = artifacts.get("chart_rows", []) or []
        if not isinstance(chart_rows, list):
            chart_rows = []

        provided_stats = result_payload.get("stats")
        if isinstance(provided_stats, dict):
            stats = {
                "compared": int(provided_stats.get("compared", 0) or 0),
                "changed": int(provided_stats.get("changed", 0) or 0),
                "matched": int(provided_stats.get("matched", 0) or 0),
                "only_ref": int(provided_stats.get("only_ref", 0) or 0),
                "only_test": int(provided_stats.get("only_test", 0) or 0),
            }
            if stats["compared"] == 0 and (diffs or matches):
                stats = _tally_stats(diffs, matches)
        else:
            stats = _tally_stats(diffs, matches)

        override_result = str(
            result_payload.get("result") or result_payload.get("section_result") or ""
        ).upper().strip()
        if override_result in _ORDER:
            section_result = override_result
        else:
            severity_meta = _merge_severity_meta(schema, section_name, result_payload)
            section_result = compute_severity(
                severity_meta,
                stats["changed"],
                stats["compared"],
                stats["only_ref"],
                stats["only_test"],
            )

        overall_counts[section_result] = overall_counts.get(section_result, 0) + 1
        by_section[section_name] = {
            "MATCH": 1 if section_result == "MATCH" else 0,
            "WARN": 1 if section_result == "WARN" else 0,
            "SUSPICIOUS": 1 if section_result == "SUSPICIOUS" else 0,
            "TOTAL": 1,
        }

        pairs = _collect_numeric_pairs_from_chart(chart_rows)
        if not pairs:
            pairs = _collect_pairs_from_rows(diffs, matches)
        radar_rows = _normalize_pairs(pairs)

        schema_section = (schema.get(section_name, {}) or {}) if isinstance(schema, dict) else {}
        schema_report = dict(schema_section.get("report", {}) or {})
        result_report = dict(result_payload.get("report") or {})
        report_cfg = {**schema_report, **result_report}

        report_cfg["types"] = _normalize_types_from_schema(report_cfg.get("types"))
        if schema_report.get("doc_text"):
            report_cfg["doc_text"] = schema_report.get("doc_text")
        if report_cfg.get("theme") is None:
            report_cfg["theme"] = theme

        source_rows = section_rows.get(section_name) if isinstance(section_rows, dict) else None
        if source_rows is None:
            source_rows = result_payload.get("source_rows")

        section_output = {
            "result": section_result,
            "stats": stats,
            "stats_display": dict(stats),
            "key_labels": result_payload.get("key_labels") or result_payload.get("labels") or {},
            "diffs": diffs,
            "matches": matches,
            "chart_rows": chart_rows,
            "radar_rows": radar_rows,
            "report": report_cfg,
            "artifacts": artifacts,
        }
        if source_rows is not None:
            section_output["source_rows"] = source_rows

        sections_out[section_name] = section_output
        overall = _max_state(overall, section_result)

    total_sections = sum(overall_counts.values())
    dashboard = {
        "overall_state_counts": {
            "MATCH": overall_counts.get("MATCH", 0),
            "WARN": overall_counts.get("WARN", 0),
            "SUSPICIOUS": overall_counts.get("SUSPICIOUS", 0),
            "TOTAL": total_sections,
        },
        "by_section": by_section,
    }

    return {
        "reference_name": reference_name,
        "profile_name": profile_name,
        "theme": theme,
        "overall": overall,
        "sections": sections_out,
        "dashboard": dashboard,
        "meta": {
            "generated_by": "assemble_report",
            "schema_title": schema.get("title") if isinstance(schema, dict) else None,
            "ingest": ingest_payload,
        },
    }
