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
    load_json,
    load_yaml,
    production_module_yml,
    results_dir,
    run_report_workflow,
    safe_unlink,
)


def _clean_result_zips(base: Path) -> None:
    for path in results_dir(base).glob("results_*.zip"):
        safe_unlink(path)


def _expect_single_zip(label: str, base: Path) -> Path:
    zips = sorted(results_dir(base).glob("results_*.zip"), key=str)
    assert len(zips) == 1, (
        f"[REPORT][{label}] Expected exactly 1 zip in {results_dir(base)}, "
        f"found {len(zips)}: {zips}"
    )
    zip_path = zips[0]
    assert zip_path.is_file(), f"[REPORT][{label}] Zip path is not a file: {zip_path}"
    return zip_path


def _assert_zip_contents(
    *,
    label: str,
    zip_path: Path,
    html_out_path: Path,
    report_json_path: Path,
    link_mode: bool,
) -> None:
    expected_html = os.path.basename(str(html_out_path))
    expected_report = os.path.basename(str(report_json_path))

    with zipfile.ZipFile(zip_path, "r") as zip_file:
        names = set(zip_file.namelist())

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


def _type_set_from_report_cfg(report_config: Any) -> set[str]:
    if not isinstance(report_config, dict):
        return set()

    raw_types = report_config.get("types")
    result: set[str] = set()

    if isinstance(raw_types, list):
        for item in raw_types:
            if isinstance(item, str):
                type_name = item.strip().lower()
                if type_name:
                    result.add(type_name)
            elif isinstance(item, dict):
                type_name = str(item.get("type") or "").strip().lower()
                if type_name:
                    result.add(type_name)

    elif isinstance(raw_types, str):
        for item in raw_types.split(","):
            type_name = item.strip().lower()
            if type_name:
                result.add(type_name)

    return result


def _report_format_is_v2(report: Dict[str, Any]) -> bool:
    format_payload = report.get("format")
    if not isinstance(format_payload, dict):
        return False

    return (
        format_payload.get("name") == "scrutiny-viz.verification-report"
        and str(format_payload.get("version") or "") == "2.0"
    )


def is_report_json(report: Any) -> bool:
    if not isinstance(report, dict):
        return False

    if not _report_format_is_v2(report):
        return False

    inputs_payload = report.get("inputs")
    summary_payload = report.get("summary")
    sections_payload = report.get("sections")

    if not isinstance(inputs_payload, dict):
        return False

    if not isinstance(inputs_payload.get("reference"), dict):
        return False

    if not isinstance(inputs_payload.get("profile"), dict):
        return False

    if not isinstance(summary_payload, dict):
        return False

    if not isinstance(sections_payload, dict):
        return False

    for section_payload in sections_payload.values():
        if not isinstance(section_payload, dict):
            return False

        if not isinstance(section_payload.get("meta"), dict):
            return False

        if not isinstance(section_payload.get("original"), dict):
            return False

        results_payload = section_payload.get("results")
        if not isinstance(results_payload, dict):
            return False

        if "state" not in results_payload:
            return False

        if not isinstance(section_payload.get("visualizations"), dict):
            return False

        if not isinstance(section_payload.get("artifacts"), dict):
            return False

    return True


def _section_state(section_payload: Dict[str, Any]) -> str:
    results_payload = section_payload.get("results")
    if not isinstance(results_payload, dict):
        return "WARN"

    return str(results_payload.get("state") or "WARN").upper().strip()


def iter_sections_issues_first_stable(report: Dict[str, Any]):
    issue_sections = []
    matching_sections = []

    for section_name, section_payload in (report.get("sections") or {}).items():
        if _section_state(section_payload) == "MATCH":
            matching_sections.append((section_name, section_payload))
        else:
            issue_sections.append((section_name, section_payload))

    return issue_sections + matching_sections


def _section_report_config(section_payload: Dict[str, Any]) -> Dict[str, Any]:
    meta_payload = section_payload.get("meta")
    if not isinstance(meta_payload, dict):
        return {}

    report_payload = meta_payload.get("report")
    if not isinstance(report_payload, dict):
        return {}

    return report_payload


def _available_visualization_types(section_payload: Dict[str, Any]) -> set[str]:
    visualizations_payload = section_payload.get("visualizations")
    if not isinstance(visualizations_payload, dict):
        return set()

    available_payload = visualizations_payload.get("available")
    if not isinstance(available_payload, dict):
        return set()

    result: set[str] = set()

    for visualization_name, visualization_payload in available_payload.items():
        if not isinstance(visualization_payload, dict):
            continue

        visualization_type = str(
            visualization_payload.get("type") or visualization_name or ""
        ).strip().lower()

        if not visualization_type:
            continue

        rows = visualization_payload.get("rows")
        cells = visualization_payload.get("cells")

        has_rows = isinstance(rows, list) and len(rows) > 0
        has_cells = isinstance(cells, list) and len(cells) > 0
        is_lazy_renderer = visualization_payload.get("producer") == "renderer_lazy"

        if has_rows or has_cells or is_lazy_renderer:
            result.add(visualization_type)

    return result


def _requested_visualization_types(section_payload: Dict[str, Any]) -> set[str]:
    visualizations_payload = section_payload.get("visualizations")
    if not isinstance(visualizations_payload, dict):
        return set()

    requested_payload = visualizations_payload.get("requested")
    if not isinstance(requested_payload, list):
        return set()

    result: set[str] = set()

    for item in requested_payload:
        if isinstance(item, dict):
            visualization_type = str(item.get("type") or "").strip().lower()
            if visualization_type:
                result.add(visualization_type)
        elif isinstance(item, str):
            visualization_type = item.strip().lower()
            if visualization_type:
                result.add(visualization_type)

    return result


def _unavailable_visualization_types(section_payload: Dict[str, Any]) -> set[str]:
    visualizations_payload = section_payload.get("visualizations")
    if not isinstance(visualizations_payload, dict):
        return set()

    unavailable_payload = visualizations_payload.get("unavailable")
    if not isinstance(unavailable_payload, list):
        return set()

    result: set[str] = set()

    for item in unavailable_payload:
        if not isinstance(item, dict):
            continue

        visualization_type = str(item.get("type") or "").strip().lower()
        if visualization_type:
            result.add(visualization_type)

    return result


def _available_performance_visualization_types(section_payload: Dict[str, Any]) -> set[str]:
    return _available_visualization_types(section_payload) & {"chart", "radar"}


def _requested_performance_visualization_types(section_payload: Dict[str, Any]) -> set[str]:
    return _requested_visualization_types(section_payload) & {"chart", "radar"}


def _build_jcaidscan_report_json(tmp_path: Path, *, label: str, schema_filename: str) -> Path:
    schema_path = production_module_yml(schema_filename)
    assert schema_path.exists(), _msg(label, f"Missing production schema: {schema_path}")

    schema_yaml = load_yaml(schema_path)
    flattened_schema = flatten_prod_schema(schema_yaml)

    table_sections = [
        section_name
        for section_name, section_config in flattened_schema.items()
        if "table" in effective_types(section_config)
    ]

    assert table_sections, _msg(
        label,
        "No table-based sections found in schema, expected for jcAIDScan.",
    )

    issue_section = table_sections[0]
    match_section = table_sections[1] if len(table_sections) > 1 else table_sections[0]

    compare_results: Dict[str, Any] = {
        issue_section: {
            "diffs": [
                {
                    "key": "k1",
                    "field": "value",
                    "ref": "A",
                    "op": "!=",
                    "test": "B",
                }
            ],
            "matches": [
                {
                    "key": "k2",
                    "field": "value",
                    "value": "OK",
                }
            ],
            "stats": {
                "compared": 10,
                "changed": 1,
                "matched": 9,
                "only_ref": 0,
                "only_test": 0,
            },
            "severity": {
                "threshold_ratio": 1.0,
                "threshold_count": 5,
            },
        },
        match_section: {
            "diffs": [],
            "matches": [
                {
                    "key": "k3",
                    "field": "value",
                    "value": "OK",
                }
            ],
            "stats": {
                "compared": 10,
                "changed": 0,
                "matched": 10,
                "only_ref": 0,
                "only_test": 0,
            },
        },
    }

    report_object = assemble_report(
        schema=flattened_schema,
        compare_results=compare_results,
        reference_name="ref",
        profile_name="prof",
    )

    output_path = tmp_path / f"{label.lower()}_report.json"
    output_path.write_text(json.dumps(report_object), encoding="utf-8")
    return output_path


def _build_tpm_report_json(tmp_path: Path, *, label: str, schema_filename: str) -> Path:
    schema_path = production_module_yml(schema_filename)
    assert schema_path.exists(), _msg(label, f"Missing production TPM schema: {schema_path}")

    schema_yaml = load_yaml(schema_path)
    flattened_schema = flatten_prod_schema(schema_yaml)

    tpm2_sections = [
        section_name
        for section_name in flattened_schema.keys()
        if str(section_name).startswith("TPM2_")
    ]

    assert tpm2_sections, _msg(label, "TPM schema has no TPM2_* sections?")

    performance_sections = [
        section_name
        for section_name in tpm2_sections
        if (
            "chart" in effective_types(flattened_schema[section_name])
            or "radar" in effective_types(flattened_schema[section_name])
        )
    ]

    assert performance_sections, _msg(label, "No TPM2_* section has chart/radar types?")

    issue_section = performance_sections[0]
    match_section = performance_sections[1] if len(performance_sections) > 1 else performance_sections[0]

    assert "TPM_INFO" in flattened_schema

    compare_results: Dict[str, Any] = {
        issue_section: {
            "diffs": [
                {
                    "key": "X",
                    "field": "avg_ms",
                    "ref": 10.0,
                    "op": "!=",
                    "test": 12.0,
                }
            ],
            "matches": [
                {
                    "key": "Y",
                    "field": "avg_ms",
                    "value": 5.0,
                }
            ],
            "stats": {
                "compared": 10,
                "changed": 1,
                "matched": 9,
                "only_ref": 0,
                "only_test": 0,
            },
            "artifacts": {
                "chart_rows": [
                    {
                        "key": "X",
                        "status": "mismatch",
                        "ref_avg": 10.0,
                        "test_avg": 12.0,
                    }
                ]
            },
            "severity": {
                "threshold_ratio": 1.0,
                "threshold_count": 5,
            },
        },
        match_section: {
            "diffs": [],
            "matches": [
                {
                    "key": "A",
                    "field": "avg_ms",
                    "value": 1.0,
                }
            ],
            "stats": {
                "compared": 10,
                "changed": 0,
                "matched": 10,
                "only_ref": 0,
                "only_test": 0,
            },
            "artifacts": {
                "chart_rows": [
                    {
                        "key": "A",
                        "status": "match",
                        "ref_avg": 1.0,
                        "test_avg": 1.0,
                    }
                ]
            },
        },
        "TPM_INFO": {
            "diffs": [],
            "matches": [
                {
                    "key": "manufacturer",
                    "field": "value",
                    "value": "AcmeTPM",
                }
            ],
            "stats": {
                "compared": 1,
                "changed": 0,
                "matched": 1,
                "only_ref": 0,
                "only_test": 0,
            },
        },
    }

    report_object = assemble_report(
        schema=flattened_schema,
        compare_results=compare_results,
        reference_name="ref",
        profile_name="prof",
    )

    output_path = tmp_path / "tpm_report.json"
    output_path.write_text(json.dumps(report_object), encoding="utf-8")
    return output_path


def _build_report_json(tmp_path: Path, *, label: str, schema_filename: str) -> Path:
    if schema_filename.lower() == "jcaidscan.yml":
        return _build_jcaidscan_report_json(
            tmp_path,
            label=label,
            schema_filename=schema_filename,
        )

    if schema_filename.lower() == "tpmalgtest.yml":
        return _build_tpm_report_json(
            tmp_path,
            label=label,
            schema_filename=schema_filename,
        )

    raise AssertionError(_msg(label, f"No builder implemented for schema: {schema_filename}"))


@pytest.mark.parametrize("link_mode", [False, True], ids=["inline", "link"])
@pytest.mark.parametrize("case", CASES, ids=lambda html_case: html_case.label)
def test_report_workflow_modules_order_and_default_collapse(
    case: HtmlCase,
    link_mode: bool,
    tmp_path: Path,
):
    report_json_path = _build_report_json(
        tmp_path,
        label=case.label,
        schema_filename=case.schema_yml,
    )

    report = load_json(report_json_path)
    assert is_report_json(report)

    _clean_result_zips(tmp_path)

    mode = "link" if link_mode else "inline"
    output_name = f"pytest_{case.label}_{mode}_{uuid4().hex}.html"
    extra_args = ["--exclude-style-and-scripts"] if link_mode else []

    output_path = run_report_workflow(
        report_json_path,
        output_name,
        cwd=tmp_path,
        extra_args=extra_args,
    )

    assert output_path.exists()

    html = output_path.read_text(encoding="utf-8")

    zip_path = _expect_single_zip(case.label, tmp_path)

    _assert_zip_contents(
        label=case.label,
        zip_path=zip_path,
        html_out_path=output_path,
        report_json_path=report_json_path,
        link_mode=link_mode,
    )

    expected_order: List[str] = [
        section_name
        for section_name, _section_payload in iter_sections_issues_first_stable(report)
    ]

    actual_order = extract_module_order_from_html(html)
    assert actual_order[: len(expected_order)] == expected_order

    section_index_by_name = {
        section_name: index
        for index, section_name in enumerate(expected_order)
    }

    for section_name, section_payload in report["sections"].items():
        section_index = section_index_by_name[section_name]
        performance_tag = find_opening_div_tag(
            html,
            f"section_{section_index}_perf",
        )

        available_performance_types = _available_performance_visualization_types(section_payload)
        requested_performance_types = _requested_performance_visualization_types(section_payload)

        if not available_performance_types:
            unavailable_types = _unavailable_visualization_types(section_payload)

            if requested_performance_types:
                assert requested_performance_types <= unavailable_types, (
                    f"{section_name} requested performance visualizations "
                    f"{sorted(requested_performance_types)}, but none were available "
                    f"and they were not reported as unavailable. "
                    f"Unavailable={sorted(unavailable_types)}"
                )

            assert performance_tag is None, (
                f"{section_name} has no available performance visualization, "
                f"but HTML still contains section_{section_index}_perf."
            )
            continue

        assert performance_tag is not None, (
            f"{section_name} has available performance visualizations "
            f"{sorted(available_performance_types)}, but HTML does not contain "
            f"section_{section_index}_perf. This means report/service.py is still "
            f"not rendering from v2 visualizations.available."
        )

        section_state = _section_state(section_payload)

        if section_state == "MATCH":
            assert div_is_collapsed(performance_tag)
        else:
            assert not div_is_collapsed(performance_tag)

    safe_unlink(output_path)
    safe_unlink(zip_path)