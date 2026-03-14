# scrutiny-viz/verification/service.py
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from scrutiny.schemaloader import SchemaLoader
from scrutiny.ingest import JsonParser
from scrutiny import logging as slog

from scrutiny.comparators.registry import get as get_comparator
import scrutiny.comparators.basic_comparator
import scrutiny.comparators.algperf_comparator
import scrutiny.comparators.cplc_comparator

from scrutiny.reporting.reporting import assemble_report


def _load_schema(path: str):
    slog.log_step("Loading schema:", path)
    loader = SchemaLoader(path)
    schema = loader.load()
    slog.log_ok(f"Schema loaded with {len(schema)} section(s).")
    return schema


def _load_json(parser: JsonParser, title: str, path: str):
    slog.log_step(f"Reading {title} JSON:", path)
    data = parser.parse(path)
    slog.log_ok(f"{title} loaded.")
    return data


def _dedupe_dicts(items: List[Dict[str, Any]], keys: List[str]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for item in items:
        marker = tuple(item.get(k) for k in keys)
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
        out.append({
            "source": source,
            "section": item.get("section"),
            "reason": item.get("reason"),
        })
    return out


def _collect_ingest_meta(schema: Any, data_ref: Any, data_tst: Any) -> Dict[str, Any]:
    schema_meta = getattr(schema, "_loader_meta", {}) or {}
    ref_meta = getattr(data_ref, "_ingest_meta", {}) or {}
    tst_meta = getattr(data_tst, "_ingest_meta", {}) or {}

    ref_dynamic = sorted(set(ref_meta.get("applied_dynamic_sections", []) or []))
    tst_dynamic = sorted(set(tst_meta.get("applied_dynamic_sections", []) or []))
    all_dynamic = sorted(set(ref_dynamic) | set(tst_dynamic))

    skipped_sections = []
    skipped_sections.extend(_normalize_skipped("reference", ref_meta.get("skipped_sections", []) or []))
    skipped_sections.extend(_normalize_skipped("profile", tst_meta.get("skipped_sections", []) or []))
    skipped_sections = _dedupe_dicts(skipped_sections, ["source", "section", "reason"])

    return {
        "dynamic_sections_enabled": bool(schema_meta.get("dynamic_sections", False)),
        "strict_sections": bool(schema_meta.get("strict_sections", False)),
        "allow_missing_sections": bool(schema_meta.get("allow_missing_sections", True)),
        "applied_dynamic_sections": all_dynamic,
        "applied_dynamic_sections_reference": ref_dynamic,
        "applied_dynamic_sections_profile": tst_dynamic,
        "skipped_sections": skipped_sections,
        "skipped_sections_count": len(skipped_sections),
    }


def _merge_dynamic_section_configs(data_ref: Any, data_tst: Any) -> Dict[str, Dict[str, Any]]:
    ref_meta = getattr(data_ref, "_ingest_meta", {}) or {}
    tst_meta = getattr(data_tst, "_ingest_meta", {}) or {}

    ref_cfgs = ref_meta.get("dynamic_section_configs", {}) or {}
    tst_cfgs = tst_meta.get("dynamic_section_configs", {}) or {}

    merged: Dict[str, Dict[str, Any]] = {}

    for section, cfg in ref_cfgs.items():
        if isinstance(cfg, dict):
            merged[section] = cfg

    for section, cfg in tst_cfgs.items():
        if section not in merged and isinstance(cfg, dict):
            merged[section] = cfg

    return merged


def _build_effective_schema(
    schema: Dict[str, Any],
    ingest_meta: Dict[str, Any],
    data_ref: Any,
    data_tst: Any,
) -> Dict[str, Any]:
    effective_schema: Dict[str, Any] = dict(schema)

    dynamic_sections = ingest_meta.get("applied_dynamic_sections", []) or []
    dynamic_cfgs = _merge_dynamic_section_configs(data_ref, data_tst)

    for section in dynamic_sections:
        if section in effective_schema:
            continue

        cfg = dynamic_cfgs.get(section)
        if not isinstance(cfg, dict):
            slog.log_warn(f"[INGEST] Dynamic section '{section}' was parsed but has no resolved config; skipping")
            continue

        effective_schema[section] = cfg

    return effective_schema


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
) -> int:
    schema = _load_schema(schema_path)
    parser = JsonParser(schema)

    data_ref = _load_json(parser, "reference", reference_path)
    data_tst = _load_json(parser, "profile", profile_path)

    ingest_meta = _collect_ingest_meta(schema, data_ref, data_tst)
    if ingest_meta["applied_dynamic_sections"]:
        slog.log_info(
            f"[INGEST] Applied dynamic sections: {', '.join(ingest_meta['applied_dynamic_sections'])}"
        )
    if ingest_meta["skipped_sections"]:
        slog.log_warn(
            f"[INGEST] Skipped sections: {len(ingest_meta['skipped_sections'])}"
        )
        for item in ingest_meta["skipped_sections"]:
            slog.log_warn(
                f"    - {item.get('source', '?')}: {item.get('section', '?')} ({item.get('reason', 'unknown reason')})"
            )

    effective_schema = _build_effective_schema(schema, ingest_meta, data_ref, data_tst)

    all_results: dict[str, Any] = {}
    section_rows: dict[str, Any] = {}

    for section, cfg in effective_schema.items():
        comp_cfg = cfg.get("component", {}) or {}
        comp_name = (comp_cfg.get("comparator") or "basic").lower()
        match_key = comp_cfg.get("match_key")
        if not match_key:
            slog.log_err(f"[{section}] missing component.match_key in schema")
            return 2

        show_key = comp_cfg.get("show_key", match_key)

        Comparator = get_comparator(comp_name)
        if Comparator is None:
            slog.log_warn(f"[{section}] comparator '{comp_name}' not found; falling back to 'basic'")
            Comparator = get_comparator("basic")

        comparator = Comparator()
        ref_rows = data_ref.get(section, []) or []
        tst_rows = data_tst.get(section, []) or []

        section_rows[section] = {"reference": ref_rows, "tested": tst_rows}

        meta = {
            "include_matches": bool(comp_cfg.get("include_matches", False) or emit_matches),
            "threshold_ratio": comp_cfg.get("threshold_ratio"),
            "threshold_count": comp_cfg.get("threshold_count"),
            **(cfg.get("target") or {}),
        }

        slog.log_step("Comparing section:", f"[{section}] comparator={comp_name}")
        res = comparator.compare(
            section=section,
            key_field=match_key,
            show_field=show_key,
            metadata=meta,
            reference=ref_rows,
            tested=tst_rows,
        )

        counts = res.get("counts", {"compared": 0, "changed": 0})
        slog.log_info(f"    • {section}: diffs {counts.get('changed', 0)}/{counts.get('compared', 0)}")

        diffs = res.get("diffs", []) or []
        to_print = min(print_diffs, len(diffs)) if print_diffs and diffs else 0
        for i in range(to_print):
            d = diffs[i]
            line = (
                f"       - {d.get('key', '')}.{d.get('field', '')}: "
                f"{d.get('ref', '')} {d.get('op', '!=')} {d.get('test', '')}"
            )
            slog.log_info(line)

        if print_matches and res.get("matches"):
            mprint = min(print_matches, len(res["matches"]))
            for i in range(mprint):
                m = res["matches"][i]
                line = f"       = {m.get('key', '')}.{m.get('field', '')}: {m.get('value', '')}"
                slog.log_info(line)

        all_results[section] = res


    reference_label = Path(reference_path).stem
    profile_label = Path(profile_path).stem

    final_json = assemble_report(
        schema=effective_schema,
        compare_results=all_results,
        reference_name=reference_label,
        profile_name=profile_label,
        section_rows=section_rows,
        ingest_meta=ingest_meta,
    )

    slog.log_step("Writing output JSON:", output_file)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_json, f, indent=2, ensure_ascii=False)

    if report:
        slog.log_ok("Generating HTML report")
        report_script = Path(__file__).resolve().parents[1] / "report_html.py"
        if not report_script.exists():
            report_script = Path("report_html.py")

        try:
            subprocess.run(
                [sys.executable, str(report_script), "-p", output_file, "-o", "comparison.html", "-v"],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            slog.log_err(f"Failed to build HTML report: {e}")
        except Exception as e:
            slog.log_err(f"Error while generating HTML report: {e}")
    else:
        slog.log_info("Report generation skipped (use -rep/--report to enable).")

    slog.log_ok("Done.")
    return 0