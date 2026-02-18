# scrutiny-viz/tests/test_report_html_modules.py
from __future__ import annotations
import json
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
import pytest
from scrutiny.reporting.reporting import assemble_report
from utility import (
    div_is_collapsed,
    effective_types,
    extract_module_order_from_html,
    find_opening_div_tag,
    flatten_prod_schema,
    is_report_json,
    iter_sections_issues_first_stable,
    load_json,
    load_yaml,
    production_module_yml,
    results_dir,
    run_report_html,
    safe_unlink,
)

# -------------------------
# ZIP helpers
# -------------------------

def _clean_result_zips() -> None:
    for p in results_dir().glob("results_*.zip"):
        safe_unlink(p)

def _expect_single_zip(label: str) -> Path:
    zips = sorted(results_dir().glob("results_*.zip"), key=str)
    assert len(zips) == 1, f"[HTML][{label}] Expected exactly 1 zip in {results_dir()}, found {len(zips)}: {zips}"
    zip_path = zips[0]
    assert zip_path.is_file(), f"[HTML][{label}] Zip path is not a file: {zip_path}"
    return zip_path


def _assert_zip_contents(*, label: str, zip_path: Path, html_out_path: Path, report_json_path: Path, link_mode: bool) -> None:
    expected_html = os.path.basename(str(html_out_path))
    expected_report = os.path.basename(str(report_json_path))

    with zipfile.ZipFile(zip_path, "r") as z:
        names = set(z.namelist())

    assert expected_html in names, f"[HTML][{label}] Zip missing HTML: {expected_html}. Has: {sorted(names)}"
    assert expected_report in names, f"[HTML][{label}] Zip missing report JSON: {expected_report}. Has: {sorted(names)}"

    if link_mode:
        # zip test inline=false  (link mode: external assets must be present)
        assert "script.js" in names, f"[HTML][{label}] link_mode zip missing script.js. Has: {sorted(names)}"
        assert "style.css" in names, f"[HTML][{label}] link_mode zip missing style.css. Has: {sorted(names)}"
    else:
        # zip test inline=true  (inline mode: external assets must NOT be present)
        assert "script.js" not in names, f"[HTML][{label}] inline zip should not contain script.js. Has: {sorted(names)}"
        assert "style.css" not in names, f"[HTML][{label}] inline zip should not contain style.css. Has: {sorted(names)}"


# -------------------------
# Test cases + builders
# -------------------------

@dataclass(frozen=True)
class HtmlCase:
    label: str
    schema_yml: str


CASES: List[HtmlCase] = [
    HtmlCase(label="jcAIDScan", schema_yml="jcAIDScan.yml"),
    HtmlCase(label="TPMAlgTest", schema_yml="TPMAlgTest.yml"),
]


# Standardized assertion message prefix for report_html tests.
def _msg(label: str, text: str) -> str:
    return f"[HTML][{label}] {text}"


# Normalizes report.types into a lowercase set (supports string, list[str], list[dict]).
def _type_set_from_report_cfg(rep_cfg: Any) -> set[str]:
    if not isinstance(rep_cfg, dict):
        return set()
    raw = rep_cfg.get("types")
    out: set[str] = set()

    if isinstance(raw, list):
        for t in raw:
            if isinstance(t, str):
                s = t.strip().lower()
                if s:
                    out.add(s)
            elif isinstance(t, dict):
                tp = str(t.get("type") or "").strip().lower()
                if tp:
                    out.add(tp)
    elif isinstance(raw, str):
        for x in raw.split(","):
            s = x.strip().lower()
            if s:
                out.add(s)

    return out


# Builds a minimal jcAIDScan report JSON using production schema + assemble_report().
def _build_jcaidscan_report_json(tmp_path: Path, *, label: str, schema_filename: str) -> Path:
    yml = production_module_yml(schema_filename)
    assert yml.exists(), _msg(label, f"Missing production schema: {yml}")

    schema_yml = load_yaml(yml)
    schema_flat = flatten_prod_schema(schema_yml)

    # Pick two TABLE sections (jcAIDScan is table-oriented).
    table_secs = [name for name, cfg in schema_flat.items() if "table" in effective_types(cfg)]
    assert table_secs, _msg(label, "No table-based sections found in schema (expected for jcAIDScan).")

    issue_sec = table_secs[0]
    match_sec = table_secs[1] if len(table_secs) > 1 else table_secs[0]

    # Minimal compare_results:
    #  - issue_sec: force WARN (not SUSPICIOUS) regardless of defaults
    #  - match_sec: clean MATCH
    compare_results: Dict[str, Any] = {
        issue_sec: {
            "diffs": [{"key": "k1", "field": "value", "ref": "A", "op": "!=", "test": "B"}],
            "matches": [{"key": "k2", "field": "value", "value": "OK"}],
            "stats": {"compared": 10, "changed": 1, "matched": 9, "only_ref": 0, "only_test": 0},
            "severity": {"threshold_ratio": 1.0, "threshold_count": 5},  # ensure WARN
        },
        match_sec: {
            "diffs": [],
            "matches": [{"key": "k3", "field": "value", "value": "OK"}],
            "stats": {"compared": 10, "changed": 0, "matched": 10, "only_ref": 0, "only_test": 0},
        },
    }

    report_obj = assemble_report(
        schema=schema_flat,
        compare_results=compare_results,
        reference_name="ref",
        profile_name="prof",
    )

    out = tmp_path / f"{label.lower()}_report.json"
    out.write_text(json.dumps(report_obj), encoding="utf-8")
    return out


# Builds a minimal TPM report JSON using production schema + assemble_report().
def _build_tpm_report_json(tmp_path: Path, *, label: str, schema_filename: str) -> Path:
    yml = production_module_yml(schema_filename)
    assert yml.exists(), _msg(label, f"Missing production TPM schema: {yml}")

    schema_yml = load_yaml(yml)
    schema_flat = flatten_prod_schema(schema_yml)

    # Pick two TPM2_* sections that have chart/radar in effective types.
    tpm2_sections = [k for k in schema_flat.keys() if str(k).startswith("TPM2_")]
    assert tpm2_sections, _msg(label, "TPM schema has no TPM2_* sections?")

    def has_perf(sec_name: str) -> bool:
        types = effective_types(schema_flat[sec_name])
        return ("chart" in types) or ("radar" in types)

    perf = [s for s in tpm2_sections if has_perf(s)]
    assert perf, _msg(label, "No TPM2_* section has chart/radar types?")

    issue_sec = perf[0]
    match_sec = perf[1] if len(perf) > 1 else perf[0]

    # Ensure TPM_INFO exists and is table-based so we can test matches-collapse behavior.
    assert "TPM_INFO" in schema_flat, _msg(label, "TPM_INFO missing in schema")
    assert "table" in effective_types(schema_flat["TPM_INFO"]), _msg(label, "TPM_INFO must be table-based")

    compare_results: Dict[str, Any] = {
        issue_sec: {
            "diffs": [{"key": "X", "field": "avg_ms", "ref": 10.0, "op": "!=", "test": 12.0}],
            "matches": [{"key": "Y", "field": "avg_ms", "value": 5.0}],
            "stats": {"compared": 10, "changed": 1, "matched": 9, "only_ref": 0, "only_test": 0},
            "artifacts": {"chart_rows": [{"key": "X", "status": "mismatch", "ref_avg": 10.0, "test_avg": 12.0}]},
            "severity": {"threshold_ratio": 1.0, "threshold_count": 5},  # ensure WARN
        },
        match_sec: {
            "diffs": [],
            "matches": [{"key": "A", "field": "avg_ms", "value": 1.0}],
            "stats": {"compared": 10, "changed": 0, "matched": 10, "only_ref": 0, "only_test": 0},
            "artifacts": {"chart_rows": [{"key": "A", "status": "match", "ref_avg": 1.0, "test_avg": 1.0}]},
        },
        "TPM_INFO": {
            "diffs": [],
            "matches": [{"key": "manufacturer", "field": "value", "value": "AcmeTPM"}],
            "stats": {"compared": 1, "changed": 0, "matched": 1, "only_ref": 0, "only_test": 0},
        },
    }

    report_obj = assemble_report(
        schema=schema_flat,
        compare_results=compare_results,
        reference_name="ref",
        profile_name="prof",
    )

    out = tmp_path / "tpm_report.json"
    out.write_text(json.dumps(report_obj), encoding="utf-8")
    return out


# Builds a report JSON for a case (jcAIDScan vs TPM) from its production schema.
def _build_report_json(tmp_path: Path, *, label: str, schema_filename: str) -> Path:
    if schema_filename.lower() == "jcaidscan.yml":
        return _build_jcaidscan_report_json(tmp_path, label=label, schema_filename=schema_filename)
    if schema_filename.lower() == "tpmalgtest.yml":
        return _build_tpm_report_json(tmp_path, label=label, schema_filename=schema_filename)
    raise AssertionError(_msg(label, f"No builder implemented for schema: {schema_filename}"))


# -------------------------
# Main HTML test
# -------------------------
# Validates report_html.py output: issues-first ordering + perf/matches collapsed defaults where applicable.
@pytest.mark.parametrize("link_mode", [False, True], ids=["inline", "link"])
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.label)
def test_report_html_modules_order_and_default_collapse(case: HtmlCase, link_mode: bool, tmp_path: Path):
    report_json_path = _build_report_json(tmp_path, label=case.label, schema_filename=case.schema_yml)

    report = load_json(report_json_path)
    assert is_report_json(report), _msg(case.label, "Input must be the REPORT JSON consumed by report_html.py")

    _clean_result_zips()

    link = "link"
    if not link_mode:
        link = "inline"

    out_name = f"pytest_{case.label}_{link}_{uuid4().hex}.html"
    extra_args = ["-e"] if link_mode else []   # -e => LINK mode in your report_html.py
    out_path = run_report_html(report_json_path, out_name, extra_args=extra_args)

    assert out_path.exists(), _msg(case.label, f"Expected HTML output not found: {out_path}")
    html = out_path.read_text(encoding="utf-8")

    # ZIP checks
    zip_path = _expect_single_zip(case.label)
    _assert_zip_contents(label=case.label, zip_path=zip_path, html_out_path=out_path, report_json_path=report_json_path, link_mode=link_mode)

    # 1) Order: stable partition (WARN/SUSP first, then MATCH), preserving original order within each group.
    expected_order: List[str] = [name for (name, _sec) in iter_sections_issues_first_stable(report)]
    actual_order = extract_module_order_from_html(html)
    assert actual_order[: len(expected_order)] == expected_order, _msg(
        case.label,
        f"Module order mismatch.\nExpected: {expected_order}\nActual:   {actual_order[:len(expected_order)]}",
    )

    idx_of = {name: i for i, name in enumerate(expected_order)}

    # 2) Perf collapse: only when report.types includes chart/radar; MATCH => collapsed, issues => visible.
    for name, sec in report["sections"].items():
        rep_cfg = sec.get("report") or {}
        types = _type_set_from_report_cfg(rep_cfg)
        expects_perf = ("chart" in types) or ("radar" in types)
        if not expects_perf:
            continue

        idx = idx_of[name]
        tag = find_opening_div_tag(html, f"section_{idx}_perf")
        assert tag is not None, _msg(case.label, f"Expected perf div for {name}: section_{idx}_perf")

        state = str(sec.get("result", "WARN")).upper().strip()
        if state == "MATCH":
            assert div_is_collapsed(tag), _msg(case.label, f"Expected {name} perf collapsed (MATCH), got: {tag}")
        else:
            assert not div_is_collapsed(tag), _msg(case.label, f"Expected {name} perf visible (issue), got: {tag}")

    # 3) Matches collapse: only when report.types includes table AND matches exist; default is collapsed.
    for name, sec in report["sections"].items():
        if not sec.get("matches"):
            continue

        rep_cfg = sec.get("report") or {}
        types = _type_set_from_report_cfg(rep_cfg)
        expects_matches_div = ("table" in types)

        idx = idx_of[name]
        tag = find_opening_div_tag(html, f"section_{idx}_matches")

        if expects_matches_div:
            assert tag is not None, _msg(case.label, f"Matches div section_{idx}_matches not found for table section {name}")
            assert div_is_collapsed(tag), _msg(case.label, f"Expected section_{idx}_matches collapsed, got: {tag}")
        else:
            if tag is not None:
                assert div_is_collapsed(tag), _msg(case.label, f"Matches div exists but should be collapsed, got: {tag}")

    safe_unlink(out_path)
    safe_unlink(zip_path)
