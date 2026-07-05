from __future__ import annotations

import json
from pathlib import Path

from scrutiny.reporting.reporting import assemble_report


def test_assemble_report_emits_only_v2_contract(tmp_path: Path) -> None:
    reference_path = tmp_path / "reference.json"
    profile_path = tmp_path / "profile.json"
    reference_path.write_text(json.dumps({"ALGPERF": []}), encoding="utf-8")
    profile_path.write_text(json.dumps({"ALGPERF": []}), encoding="utf-8")

    schema = {
        "ALGPERF": {
            "component": {"comparator": "algperf", "match_key": "algorithm", "show_key": "algorithm"},
            "report": {"types": [{"type": "chart"}, {"type": "radar"}, {"type": "table"}]},
        }
    }
    compare_results = {
        "ALGPERF": {
            "stats": {"compared": 1, "changed": 1, "matched": 0, "only_ref": 0, "only_test": 0},
            "labels": {"RSA": "RSA"},
            "diffs": [{"key": "RSA", "field": "avg_ms", "ref": 1.0, "op": "<", "test": 2.0}],
            "matches": [],
            "artifacts": {"chart_rows": [{"key": "RSA", "ref_avg": 1.0, "test_avg": 2.0}]},
        }
    }

    report = assemble_report(
        schema=schema,
        compare_results=compare_results,
        reference_name="reference",
        profile_name="profile",
        section_rows={"ALGPERF": {"reference": [], "tested": []}},
        reference_path=str(reference_path),
        profile_path=str(profile_path),
    )

    assert report["format"] == {"name": "scrutiny-viz.verification-report", "version": "2.0"}
    assert report["inputs"]["reference"]["file_name"] == "reference.json"
    assert report["inputs"]["profile"]["source"]["kind"] == "input_json"
    assert report["summary"]["overall"] == "WARN"
    assert report["summary"]["state_counts"]["WARN"] == 1

    section = report["sections"]["ALGPERF"]
    assert section["meta"]["comparator"] == "algperf"
    assert section["results"]["state"] == "WARN"
    assert section["results"]["stats"]["only_reference"] == 0
    assert section["visualizations"]["requested"][0]["type"] == "chart"
    assert section["visualizations"]["available"]["chart"]["rows"][0]["key"] == "RSA"

    assert "overall" not in report
    assert "dashboard" not in report
    assert "reference_name" not in report
    assert "profile_name" not in report
    assert "result" not in section
    assert "diffs" not in section
    assert "matches" not in section
    assert "chart_rows" not in section
    assert "radar_rows" not in section
    assert "source_rows" not in section
