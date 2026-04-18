# scrutiny-viz/verification/service.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from scrutiny import logging as slog
from scrutiny.ingest import JsonParser
from scrutiny.schemaloader import SchemaLoader
from scrutiny.reporting.reporting import assemble_report

from .comparators.registry import get_plugin as get_comparator_plugin

log = slog.get_logger("VERIFY")
ingest_log = slog.get_logger("INGEST")


def _load_schema(path: str):
    log.step("Loading schema:", path)
    schema = SchemaLoader(path).load()
    log.ok(f"Schema loaded with {len(schema)} section(s).")
    return schema


def _load_json(parser: JsonParser, title: str, path: str):
    log.step(f"Reading {title} JSON:", path)
    data = parser.parse(path)
    log.ok(f"{title} loaded.")
    return data


def _dedupe_dicts(items: List[Dict[str, Any]], keys: List[str]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for item in items:
        marker = tuple(item.get(key) for key in keys)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(item)
    return out


def _normalize_skipped(source: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        out.append({"source": source, "section": item.get("section"), "reason": item.get("reason")})
    return out


def _collect_ingest_meta(schema: Any, data_ref: Any, data_test: Any) -> Dict[str, Any]:
    schema_meta = getattr(schema, "_loader_meta", {}) or {}
    ref_meta = getattr(data_ref, "_ingest_meta", {}) or {}
    test_meta = getattr(data_test, "_ingest_meta", {}) or {}

    ref_dynamic = sorted(set(ref_meta.get("applied_dynamic_sections", []) or []))
    test_dynamic = sorted(set(test_meta.get("applied_dynamic_sections", []) or []))
    skipped_sections = _dedupe_dicts(
        _normalize_skipped("reference", ref_meta.get("skipped_sections", []) or [])
        + _normalize_skipped("profile", test_meta.get("skipped_sections", []) or []),
        ["source", "section", "reason"],
    )

    return {
        "dynamic_sections_enabled": bool(schema_meta.get("dynamic_sections", False)),
        "strict_sections": bool(schema_meta.get("strict_sections", False)),
        "allow_missing_sections": bool(schema_meta.get("allow_missing_sections", True)),
        "applied_dynamic_sections": sorted(set(ref_dynamic) | set(test_dynamic)),
        "applied_dynamic_sections_reference": ref_dynamic,
        "applied_dynamic_sections_profile": test_dynamic,
        "skipped_sections": skipped_sections,
        "skipped_sections_count": len(skipped_sections),
    }


def _merge_dynamic_section_configs(data_ref: Any, data_test: Any) -> Dict[str, Dict[str, Any]]:
    ref_cfgs = (getattr(data_ref, "_ingest_meta", {}) or {}).get("dynamic_section_configs", {}) or {}
    test_cfgs = (getattr(data_test, "_ingest_meta", {}) or {}).get("dynamic_section_configs", {}) or {}
    merged: Dict[str, Dict[str, Any]] = {}

    for section, cfg in ref_cfgs.items():
        if isinstance(cfg, dict):
            merged[section] = cfg
    for section, cfg in test_cfgs.items():
        if section not in merged and isinstance(cfg, dict):
            merged[section] = cfg
    return merged


def _build_effective_schema(
    schema: Dict[str, Any],
    ingest_meta: Dict[str, Any],
    data_ref: Any,
    data_test: Any,
) -> Dict[str, Any]:
    effective_schema: Dict[str, Any] = dict(schema)
    dynamic_cfgs = _merge_dynamic_section_configs(data_ref, data_test)

    for section in ingest_meta.get("applied_dynamic_sections", []) or []:
        if section in effective_schema:
            continue
        cfg = dynamic_cfgs.get(section)
        if not isinstance(cfg, dict):
            ingest_log.warn(f"Dynamic section '{section}' was parsed but has no resolved config; skipping")
            continue
        effective_schema[section] = cfg

    return effective_schema


def _log_ingest_meta(ingest_meta: Dict[str, Any]) -> None:
    dynamic_sections = ingest_meta.get("applied_dynamic_sections", [])
    skipped_sections = ingest_meta.get("skipped_sections", [])

    if dynamic_sections:
        ingest_log.info(f"Applied dynamic sections: {', '.join(dynamic_sections)}")
    if skipped_sections:
        ingest_log.warn(f"Skipped sections: {len(skipped_sections)}")
        for item in skipped_sections:
            ingest_log.warn(
                f"    - {item.get('source', '?')}: {item.get('section', '?')} ({item.get('reason', 'unknown reason')})"
            )


def _fail(exit_code: int, error: str) -> Dict[str, Any]:
    return {"ok": False, "exit_code": int(exit_code), "error": str(error)}


def run_verification(
    *,
    schema_path: str,
    reference_path: str,
    profile_path: str,
    output_file: str = "verification.json",
    emit_matches: bool = False,
    print_diffs: int = 3,
    print_matches: int = 0,
    report: bool = False,
) -> Dict[str, Any]:
    schema = _load_schema(schema_path)
    parser = JsonParser(schema)

    data_ref = _load_json(parser, "reference", reference_path)
    data_test = _load_json(parser, "profile", profile_path)

    ingest_meta = _collect_ingest_meta(schema, data_ref, data_test)
    _log_ingest_meta(ingest_meta)
    effective_schema = _build_effective_schema(schema, ingest_meta, data_ref, data_test)

    all_results: Dict[str, Any] = {}
    section_rows: Dict[str, Any] = {}

    for section, cfg in effective_schema.items():
        comp_cfg = cfg.get("component", {}) or {}
        comparator_name = str(comp_cfg.get("comparator") or "basic").lower()
        match_key = comp_cfg.get("match_key")
        if not match_key:
            log.err(f"[{section}] missing component.match_key in schema")
            return _fail(2, f"[{section}] missing component.match_key in schema")

        show_key = comp_cfg.get("show_key", match_key)
        try:
            comparator = get_comparator_plugin(comparator_name)
        except KeyError:
            log.warn(f"[{section}] comparator '{comparator_name}' not found; falling back to 'basic'")
            comparator = get_comparator_plugin("basic")

        ref_rows = data_ref.get(section, []) or []
        test_rows = data_test.get(section, []) or []
        section_rows[section] = {"reference": ref_rows, "tested": test_rows}

        metadata = {
            "include_matches": bool(comp_cfg.get("include_matches", False) or emit_matches),
            "threshold_ratio": comp_cfg.get("threshold_ratio"),
            "threshold_count": comp_cfg.get("threshold_count"),
            **(cfg.get("target") or {}),
        }

        log.step("Comparing section:", f"[{section}] comparator={comparator.spec.name}")
        result = comparator.compare(
            section=section,
            key_field=match_key,
            show_field=show_key,
            metadata=metadata,
            reference=ref_rows,
            tested=test_rows,
        )

        override_result = str(result.get("override_result", "") or "").upper().strip()
        if override_result:
            result["result"] = override_result
            result["section_result"] = override_result
            log.info(f"    • {section}: forced result {override_result}")
        else:
            counts = result.get("counts", {"compared": 0, "changed": 0})
            log.info(f"    • {section}: diffs {counts.get('changed', 0)}/{counts.get('compared', 0)}")

        diffs = result.get("diffs", []) or []
        for diff in diffs[: max(0, min(print_diffs, len(diffs)))]:
            log.info(
                f"       - {diff.get('key', '')}.{diff.get('field', '')}: {diff.get('ref', '')} "
                f"{diff.get('op', '!=')} {diff.get('test', '')}"
            )

        if print_matches and result.get("matches"):
            for match in result["matches"][: min(print_matches, len(result["matches"]))]:
                log.info(f"       = {match.get('key', '')}.{match.get('field', '')}: {match.get('value', '')}")

        all_results[section] = result

    output_path = Path(output_file).resolve()
    final_json = assemble_report(
        schema=effective_schema,
        compare_results=all_results,
        reference_name=Path(reference_path).stem,
        profile_name=Path(profile_path).stem,
        section_rows=section_rows,
        ingest_meta=ingest_meta,
    )

    log.step("Writing output JSON:", str(output_path))
    try:
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(final_json, handle, indent=2, ensure_ascii=False)
    except Exception as exc:
        log.err(f"Failed to write verification JSON: {exc}")
        return _fail(1, f"Failed to write verification JSON: {exc}")

    report_html_path: str | None = None
    report_zip_path: str | None = None
    if report:
        log.step("Generating HTML report", "comparison.html")
        try:
            from report.service import run_report_html

            report_result = run_report_html(
                verification_profile=str(output_path),
                output_file="comparison.html",
                exclude_style_and_scripts=False,
                no_zip=False,
            )
        except Exception as exc:
            log.err(f"Error while generating HTML report: {exc}")
            return _fail(1, f"Error while generating HTML report: {exc}")

        if not report_result.get("ok", False):
            return _fail(int(report_result.get("exit_code", 1)), report_result.get("error", "Failed to build HTML report"))
        report_html_path = report_result.get("html_path")
        report_zip_path = report_result.get("zip_path")

    return {
        "ok": True,
        "exit_code": 0,
        "output_json_path": str(output_path),
        "overall": str(final_json.get("overall", "WARN")).upper(),
        "report_html_path": report_html_path,
        "report_zip_path": report_zip_path,
    }
