# scrutiny-viz/scrutiny/reporting/reporting.py
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_ORDER = {"MATCH": 0, "WARN": 1, "SUSPICIOUS": 2}


REPORT_FORMAT_NAME = "scrutiny-viz.verification-report"
REPORT_FORMAT_VERSION = "2.0"
VALID_INPUT_SOURCE_KINDS = {"input_json", "mapper", "manual", "unknown"}


def _calculate_sha256_for_file(path: str | None) -> str | None:
    if not path:
        return None
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as file_handle:
            for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return None


def _normalize_input_source_kind(value: Any) -> str:
    normalized_value = str(value or "").strip().lower()
    return normalized_value if normalized_value in VALID_INPUT_SOURCE_KINDS else "unknown"


def _build_input_descriptor(
    *,
    label: str,
    input_path: str | None,
    source_metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    source_metadata = source_metadata if isinstance(source_metadata, dict) else {}
    input_file_name = Path(input_path).name if input_path else None
    input_sha256 = _calculate_sha256_for_file(input_path)

    source_payload = source_metadata.get("source") if isinstance(source_metadata.get("source"), dict) else source_metadata
    source_kind = _normalize_input_source_kind(source_payload.get("kind") or ("input_json" if input_path else "unknown"))
    mapper_name = source_payload.get("mapper")
    mapper_name = str(mapper_name).strip() if mapper_name is not None and str(mapper_name).strip() else None

    original_file_name = source_payload.get("original_file_name") or input_file_name
    original_file_name = str(original_file_name).strip() if original_file_name is not None and str(original_file_name).strip() else None

    original_sha256 = source_payload.get("original_sha256") or input_sha256
    original_sha256 = str(original_sha256).strip() if original_sha256 is not None and str(original_sha256).strip() else None

    return {
        "label": label,
        "file_name": input_file_name,
        "path": str(input_path) if input_path else None,
        "sha256": input_sha256,
        "source": {
            "kind": source_kind,
            "mapper": mapper_name,
            "original_file_name": original_file_name,
            "original_sha256": original_sha256,
        },
    }


def _convert_statistics_to_version_two(stats: Dict[str, Any]) -> Dict[str, int]:
    return {
        "compared": int(stats.get("compared", 0) or 0),
        "changed": int(stats.get("changed", 0) or 0),
        "matched": int(stats.get("matched", 0) or 0),
        "only_reference": int(stats.get("only_reference", stats.get("only_ref", 0)) or 0),
        "only_profile": int(stats.get("only_profile", stats.get("only_test", 0)) or 0),
    }


def _split_differences_into_result_buckets(diffs: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    changed_differences: List[Dict[str, Any]] = []
    only_reference_differences: List[Dict[str, Any]] = []
    only_profile_differences: List[Dict[str, Any]] = []
    group_differences: List[Dict[str, Any]] = []

    for diff in diffs or []:
        if not isinstance(diff, dict):
            continue
        field_name = diff.get("field")
        if field_name == "__presence__":
            reference_present = bool(diff.get("ref"))
            profile_present = bool(diff.get("test"))
            if reference_present and not profile_present:
                only_reference_differences.append(diff)
            elif profile_present and not reference_present:
                only_profile_differences.append(diff)
            else:
                changed_differences.append(diff)
            continue
        if field_name == "__group__":
            group_differences.append(diff)
            continue
        changed_differences.append(diff)

    return {
        "changed": changed_differences,
        "only_reference": only_reference_differences,
        "only_profile": only_profile_differences,
        "groups": group_differences,
    }


def _normalize_requested_visualizations(report_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    requested: List[Dict[str, Any]] = []
    for visualization_type in report_cfg.get("types") or []:
        if not isinstance(visualization_type, dict):
            continue
        type_name = str(visualization_type.get("type") or "").strip().lower()
        if not type_name:
            continue
        variant = visualization_type.get("variant")
        variant = str(variant).strip().lower() if variant is not None and str(variant).strip() else None
        requested.append({"type": type_name, "variant": variant})
    return requested


def _is_visualization_requested(requested: List[Dict[str, Any]], type_name: str) -> bool:
    return any(item.get("type") == type_name for item in requested or [])


def _get_requested_visualization_variant(requested: List[Dict[str, Any]], type_name: str) -> str | None:
    for item in requested or []:
        if item.get("type") == type_name:
            variant = item.get("variant")
            return str(variant) if variant is not None else None
    return None


def _can_derive_heatmap_visualization(diffs: List[Dict[str, Any]], matches: List[Dict[str, Any]]) -> bool:
    row_fields = {"row_index", "row", "y"}
    col_fields = {"col_index", "col", "x"}
    value_fields = {"value", "share_pct", "score", "weight"}
    fields_by_key: Dict[str, set[str]] = {}

    for record in list(matches or []) + list(diffs or []):
        if not isinstance(record, dict):
            continue
        key = str(record.get("key") or "")
        field = str(record.get("field") or "")
        if not key or not field or field == "__presence__":
            continue
        fields_by_key.setdefault(key, set()).add(field)

    for fields in fields_by_key.values():
        if fields & row_fields and fields & col_fields and fields & value_fields:
            return True
    return False


def _build_section_visualization_payload(
    *,
    requested: List[Dict[str, Any]],
    chart_rows: List[Dict[str, Any]],
    radar_rows: List[Dict[str, Any]],
    diffs: List[Dict[str, Any]],
    matches: List[Dict[str, Any]],
    chart_rows_producer: str,
) -> Dict[str, Any]:
    available: Dict[str, Any] = {}
    unavailable: List[Dict[str, Any]] = []

    if chart_rows:
        available["chart"] = {
            "type": "chart",
            "variant": _get_requested_visualization_variant(requested, "chart"),
            "producer": chart_rows_producer,
            "source": "chart_rows",
            "rows": chart_rows,
        }

    if _is_visualization_requested(requested, "radar"):
        if len(radar_rows) >= 3:
            available["radar"] = {
                "type": "radar",
                "variant": _get_requested_visualization_variant(requested, "radar"),
                "producer": "report_assembler",
                "source": "derived_from_chart_rows_or_results",
                "rows": radar_rows,
            }
        else:
            unavailable.append(
                {
                    "type": "radar",
                    "variant": _get_requested_visualization_variant(requested, "radar"),
                    "reason": "radar visualization requires at least three numeric or boolean comparable items",
                }
            )

    if _is_visualization_requested(requested, "table"):
        available["table"] = {
            "type": "table",
            "variant": _get_requested_visualization_variant(requested, "table"),
            "producer": "renderer_lazy",
            "source": "results_and_original_rows",
        }

    if _is_visualization_requested(requested, "heatmap"):
        if _can_derive_heatmap_visualization(diffs, matches):
            available["heatmap"] = {
                "type": "heatmap",
                "variant": _get_requested_visualization_variant(requested, "heatmap"),
                "producer": "renderer_lazy",
                "source": "results_differences_and_matches",
            }
        else:
            unavailable.append(
                {
                    "type": "heatmap",
                    "variant": _get_requested_visualization_variant(requested, "heatmap"),
                    "reason": "section does not contain row/column/value fields needed for a matrix heatmap",
                }
            )

    for requested_visualization in requested:
        type_name = str(requested_visualization.get("type") or "").strip().lower()
        if not type_name or type_name in available:
            continue
        if type_name in {"chart", "radar", "table", "heatmap"}:
            if type_name == "chart" and not chart_rows:
                unavailable.append(
                    {
                        "type": type_name,
                        "variant": requested_visualization.get("variant"),
                        "reason": "no chart rows were produced by the comparator or report assembler",
                    }
                )
            continue
        unavailable.append(
            {
                "type": type_name,
                "variant": requested_visualization.get("variant"),
                "reason": "visualization type is not produced by the report assembler",
            }
        )

    return {"requested": requested, "available": available, "unavailable": unavailable}


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
    reference_path: str | None = None,
    profile_path: str | None = None,
    input_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sections_out: Dict[str, Any] = {}
    overall = "MATCH"

    overall_counts = {"MATCH": 0, "WARN": 0, "SUSPICIOUS": 0}
    by_section: Dict[str, Dict[str, int]] = {}

    theme = _pick_global_theme(schema)
    ingest_payload = dict(ingest_meta or _default_ingest_meta(schema))
    input_metadata = input_metadata if isinstance(input_metadata, dict) else {}

    result_counts = {"compared": 0, "changed": 0, "matched": 0, "only_reference": 0, "only_profile": 0}

    for section_name, result_payload in (compare_results or {}).items():
        diffs = result_payload.get("diffs", []) or []
        matches = result_payload.get("matches", []) or []
        artifacts = result_payload.get("artifacts", {}) or {}

        chart_rows = result_payload.get("chart_rows")
        chart_rows_producer = "comparator"
        if chart_rows is None:
            chart_rows = artifacts.get("chart_rows", []) or []
            chart_rows_producer = "comparator" if chart_rows else "report_assembler"
        if not isinstance(chart_rows, list):
            chart_rows = []

        provided_stats = result_payload.get("stats")
        if isinstance(provided_stats, dict):
            stats = {
                "compared": int(provided_stats.get("compared", 0) or 0),
                "changed": int(provided_stats.get("changed", 0) or 0),
                "matched": int(provided_stats.get("matched", 0) or 0),
                "only_ref": int(provided_stats.get("only_ref", provided_stats.get("only_reference", 0)) or 0),
                "only_test": int(provided_stats.get("only_test", provided_stats.get("only_profile", 0)) or 0),
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

        stats_v2 = _convert_statistics_to_version_two(stats)
        result_counts["compared"] += stats_v2["compared"]
        result_counts["changed"] += stats_v2["changed"]
        result_counts["matched"] += stats_v2["matched"]
        result_counts["only_reference"] += stats_v2["only_reference"]
        result_counts["only_profile"] += stats_v2["only_profile"]

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

        labels = result_payload.get("key_labels") or result_payload.get("labels") or {}
        requested_visualizations = _normalize_requested_visualizations(report_cfg)
        visualizations_payload = _build_section_visualization_payload(
            requested=requested_visualizations,
            chart_rows=chart_rows,
            radar_rows=radar_rows,
            diffs=diffs,
            matches=matches,
            chart_rows_producer=chart_rows_producer,
        )

        original_payload = {
            "reference": {"rows": []},
            "profile": {"rows": []},
        }
        if isinstance(source_rows, dict):
            original_payload = {
                "reference": {"rows": source_rows.get("reference") or []},
                "profile": {"rows": source_rows.get("profile") or source_rows.get("tested") or []},
            }

        section_output = {
            "meta": {
                "name": section_name,
                "comparator": (schema_section.get("component") or {}).get("comparator") if isinstance(schema_section, dict) else None,
                "match_key": (schema_section.get("component") or {}).get("match_key") if isinstance(schema_section, dict) else None,
                "show_key": (schema_section.get("component") or {}).get("show_key") if isinstance(schema_section, dict) else None,
                "report": report_cfg,
                "severity": _merge_severity_meta(schema, section_name, result_payload),
            },
            "original": original_payload,
            "results": {
                "state": section_result,
                "stats": stats_v2,
                "labels": labels,
                "matches": matches,
                "differences": _split_differences_into_result_buckets(diffs),
                "raw_differences": diffs,
            },
            "visualizations": visualizations_payload,
            "artifacts": artifacts,
        }

        sections_out[section_name] = section_output
        overall = _max_state(overall, section_result)

    total_sections = sum(overall_counts.values())
    state_counts_payload = {
        "MATCH": overall_counts.get("MATCH", 0),
        "WARN": overall_counts.get("WARN", 0),
        "SUSPICIOUS": overall_counts.get("SUSPICIOUS", 0),
        "TOTAL": total_sections,
    }

    reference_input = _build_input_descriptor(
        label=reference_name,
        input_path=reference_path,
        source_metadata=input_metadata.get("reference") if isinstance(input_metadata, dict) else None,
    )
    profile_input = _build_input_descriptor(
        label=profile_name,
        input_path=profile_path,
        source_metadata=input_metadata.get("profile") if isinstance(input_metadata, dict) else None,
    )

    summary = {
        "overall": overall,
        "state_counts": state_counts_payload,
        "result_counts": result_counts,
        "by_section": by_section,
    }

    meta_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": {
            "tool": "scrutiny-viz",
            "component": "scrutiny.reporting.reporting",
            "assembler": "assemble_report",
        },
        "schema": {
            "title": schema.get("title") if isinstance(schema, dict) else None,
        },
        "ingest": ingest_payload,
    }

    return {
        "format": {
            "name": REPORT_FORMAT_NAME,
            "version": REPORT_FORMAT_VERSION,
        },
        "inputs": {
            "reference": reference_input,
            "profile": profile_input,
        },
        "meta": meta_payload,
        "theme": theme,
        "summary": summary,
        "sections": sections_out,
        
    }
