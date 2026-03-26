# scrutiny-viz/tests/mapper/test_rsabias_mapper.py
from __future__ import annotations

from tests.mapper.helpers import iter_bucket_dirs, run_mapper_source


def _payload():
    dirs = iter_bucket_dirs("rsabias")
    assert dirs, "No RSABias directory fixtures found"
    return run_mapper_source(dirs[0], mapper_type="rsabias")


def test_rsabias_mapper_emits_expected_sections():
    payload = _payload()

    assert payload["_type"] == "rsabias"
    assert "META" in payload
    assert "SUMMARY" in payload

    accuracy_sections = [k for k in payload if str(k).startswith("ACCURACY_N")]
    assert accuracy_sections, "Expected ACCURACY_N* sections from RSABias mapper"


def test_rsabias_mapper_exposes_matrix_metadata_when_available():
    payload = _payload()

    if "CONFUSION_MATRIX_META" not in payload:
        return

    meta = {
        str(row.get("name")): row.get("value")
        for row in payload["CONFUSION_MATRIX_META"]
        if isinstance(row, dict)
    }

    assert "rows" in meta
    assert "cols" in meta


def test_rsabias_mapper_summary_contains_accuracy_entries():
    payload = _payload()

    summary = payload.get("SUMMARY", [])
    assert isinstance(summary, list)
    assert summary, "SUMMARY should not be empty"

    names = {str(row.get("name")) for row in summary if isinstance(row, dict)}
    assert any(name.endswith("_accuracy_pct") for name in names), "Expected aggregated accuracy entries in SUMMARY"