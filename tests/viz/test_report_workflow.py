# scrutiny-viz/tests/viz/test_report_workflow.py
from __future__ import annotations
import json
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4
import pytest
from scrutiny.reporting.reporting import assemble_report
from tests.utility import (
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
    run_report_workflow,
    safe_unlink,
)


def _clean_result_zips(base: Path) -> None:
    for p in results_dir(base).glob("results_*.zip"):
        safe_unlink(p)


def _expect_single_zip(label: str, base: Path) -> Path:
    zips = sorted(results_dir(base).glob("results_*.zip"), key=str)
    assert len(zips) == 1, f"[REPORT][{label}] Expected exactly 1 zip in {results_dir(base)}, found {len(zips)}: {zips}"
    zip_path = zips[0]
    assert zip_path.is_file(), f"[REPORT][{label}] Zip path is not a file: {zip_path}"
    return zip_path


def _assert_zip_contents(*, label: str, zip_path: Path, html_out_path: Path, report_json_path: Path, link_mode: bool) -> None:
    expected_html = os.path.basename(str(html_out_path))
    expected_report = os.path.basename(str(report_json_path))
    with zipfile.ZipFile(zip_path, "r") as z:
        names = set(z.namelist())
    assert expected_html in names
    assert expected_report in names
    if link_mode:
        assert "script.js" in names and "style.css" in names
    else:
        assert "script.js" not in names and "style.css" not in names


@dataclass(frozen=True)
class HtmlCase:
    label: str
    schema_yml: str


CASES: List[HtmlCase] = [
    HtmlCase(label="jcAIDScan", schema_yml="jcAIDScan.yml"),
    HtmlCase(label="TPMAlgTest", schema_yml="TPMAlgTest.yml"),
]


def _msg(label: str, text: str) -> str:
    return f"[REPORT][{label}] {text}"


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


def _build_jcaidscan_report_json(tmp_path: Path, *, label: str, schema_filename: str) -> Path:
    yml = production_module_yml(schema_filename)
    assert yml.exists(), _msg(label, f"Missing production schema: {yml}")
    schema_yml = load_yaml(yml)
    schema_flat = flatten_prod_schema(schema_yml)
    table_secs = [name for name, cfg in schema_flat.items() if "table" in effective_types(cfg)]
    assert table_secs, _msg(label, "No table-based sections found in schema (expected for jcAIDScan).")
    issue_sec = table_secs[0]
    match_sec = table_secs[1] if len(table_secs) > 1 else table_secs[0]
    compare_results: Dict[str, Any] = {
        issue_sec: {"diffs": [{"key": "k1", "field": "value", "ref": "A", "op": "!=", "test": "B"}], "matches": [{"key": "k2", "field": "value", "value": "OK"}], "stats": {"compared": 10, "changed": 1, "matched": 9, "only_ref": 0, "only_test": 0}, "severity": {"threshold_ratio": 1.0, "threshold_count": 5}},
        match_sec: {"diffs": [], "matches": [{"key": "k3", "field": "value", "value": "OK"}], "stats": {"compared": 10, "changed": 0, "matched": 10, "only_ref": 0, "only_test": 0}},
    }
    report_obj = assemble_report(schema=schema_flat, compare_results=compare_results, reference_name="ref", profile_name="prof")
    out = tmp_path / f"{label.lower()}_report.json"
    out.write_text(json.dumps(report_obj), encoding="utf-8")
    return out


def _build_tpm_report_json(tmp_path: Path, *, label: str, schema_filename: str) -> Path:
    yml = production_module_yml(schema_filename)
    assert yml.exists(), _msg(label, f"Missing production TPM schema: {yml}")
    schema_yml = load_yaml(yml)
    schema_flat = flatten_prod_schema(schema_yml)
    tpm2_sections = [k for k in schema_flat.keys() if str(k).startswith("TPM2_")]
    assert tpm2_sections, _msg(label, "TPM schema has no TPM2_* sections?")
    perf = [s for s in tpm2_sections if ("chart" in effective_types(schema_flat[s]) or "radar" in effective_types(schema_flat[s]))]
    assert perf, _msg(label, "No TPM2_* section has chart/radar types?")
    issue_sec = perf[0]
    match_sec = perf[1] if len(perf) > 1 else perf[0]
    assert "TPM_INFO" in schema_flat
    compare_results: Dict[str, Any] = {
        issue_sec: {"diffs": [{"key": "X", "field": "avg_ms", "ref": 10.0, "op": "!=", "test": 12.0}], "matches": [{"key": "Y", "field": "avg_ms", "value": 5.0}], "stats": {"compared": 10, "changed": 1, "matched": 9, "only_ref": 0, "only_test": 0}, "artifacts": {"chart_rows": [{"key": "X", "status": "mismatch", "ref_avg": 10.0, "test_avg": 12.0}]}, "severity": {"threshold_ratio": 1.0, "threshold_count": 5}},
        match_sec: {"diffs": [], "matches": [{"key": "A", "field": "avg_ms", "value": 1.0}], "stats": {"compared": 10, "changed": 0, "matched": 10, "only_ref": 0, "only_test": 0}, "artifacts": {"chart_rows": [{"key": "A", "status": "match", "ref_avg": 1.0, "test_avg": 1.0}]}},
        "TPM_INFO": {"diffs": [], "matches": [{"key": "manufacturer", "field": "value", "value": "AcmeTPM"}], "stats": {"compared": 1, "changed": 0, "matched": 1, "only_ref": 0, "only_test": 0}},
    }
    report_obj = assemble_report(schema=schema_flat, compare_results=compare_results, reference_name="ref", profile_name="prof")
    out = tmp_path / "tpm_report.json"
    out.write_text(json.dumps(report_obj), encoding="utf-8")
    return out


def _build_report_json(tmp_path: Path, *, label: str, schema_filename: str) -> Path:
    if schema_filename.lower() == "jcaidscan.yml":
        return _build_jcaidscan_report_json(tmp_path, label=label, schema_filename=schema_filename)
    if schema_filename.lower() == "tpmalgtest.yml":
        return _build_tpm_report_json(tmp_path, label=label, schema_filename=schema_filename)
    raise AssertionError(_msg(label, f"No builder implemented for schema: {schema_filename}"))


@pytest.mark.parametrize("link_mode", [False, True], ids=["inline", "link"])
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.label)
def test_report_workflow_modules_order_and_default_collapse(case: HtmlCase, link_mode: bool, tmp_path: Path):
    report_json_path = _build_report_json(tmp_path, label=case.label, schema_filename=case.schema_yml)
    report = load_json(report_json_path)
    assert is_report_json(report)
    _clean_result_zips(tmp_path)
    mode = "link" if link_mode else "inline"
    out_name = f"pytest_{case.label}_{mode}_{uuid4().hex}.html"
    extra_args = ["-e"] if link_mode else []
    out_path = run_report_workflow(report_json_path, out_name, cwd=tmp_path, extra_args=extra_args)
    assert out_path.exists()
    html = out_path.read_text(encoding="utf-8")
    zip_path = _expect_single_zip(case.label, tmp_path)
    _assert_zip_contents(label=case.label, zip_path=zip_path, html_out_path=out_path, report_json_path=report_json_path, link_mode=link_mode)
    expected_order: List[str] = [name for (name, _sec) in iter_sections_issues_first_stable(report)]
    actual_order = extract_module_order_from_html(html)
    assert actual_order[: len(expected_order)] == expected_order
    idx_of = {name: i for i, name in enumerate(expected_order)}
    for name, sec in report["sections"].items():
        rep_cfg = sec.get("report") or {}
        types = _type_set_from_report_cfg(rep_cfg)
        expects_perf = ("chart" in types) or ("radar" in types)
        if not expects_perf:
            continue
        idx = idx_of[name]
        tag = find_opening_div_tag(html, f"section_{idx}_perf")
        assert tag is not None
        state = str(sec.get("result", "WARN")).upper().strip()
        if state == "MATCH":
            assert div_is_collapsed(tag)
        else:
            assert not div_is_collapsed(tag)
    safe_unlink(out_path)
    safe_unlink(zip_path)
