# scrutiny-viz/tests/comparators/test_algperf.py
from __future__ import annotations

from verification.comparators import registry as comparator_registry


def _stats(result: dict) -> dict:
    return result.get("stats") or result.get("counts") or {}


def test_algperf_comparator_detects_missing_and_extra_rows():
    plugin = comparator_registry.get_plugin("algperf")

    reference = [
        {"algorithm": "ALG_RSA", "avg_ms": 10.0, "min_ms": 9.0, "max_ms": 11.0},
    ]
    tested = [
        {"algorithm": "ALG_EC", "avg_ms": 5.0, "min_ms": 4.5, "max_ms": 5.5},
    ]

    result = plugin.compare(
        section="PERF",
        key_field="algorithm",
        show_field="algorithm",
        metadata={},
        reference=reference,
        tested=tested,
    )

    stats = _stats(result)
    assert result["section"] == "PERF"
    assert stats["only_ref"] == 1
    assert stats["only_test"] == 1
    assert len(result.get("diffs", [])) == 2
    assert all(d.get("field") == "__presence__" for d in result.get("diffs", []))

    chart_rows = result.get("artifacts", {}).get("chart_rows", [])
    statuses = {row.get("status") for row in chart_rows}
    assert "missing" in statuses
    assert "extra" in statuses


def test_algperf_comparator_detects_error_mismatch():
    plugin = comparator_registry.get_plugin("algperf")

    reference = [
        {"algorithm": "ALG_RSA", "avg_ms": 10.0, "min_ms": 9.0, "max_ms": 11.0, "error": "timeout"},
    ]
    tested = [
        {"algorithm": "ALG_RSA", "avg_ms": 10.0, "min_ms": 9.0, "max_ms": 11.0, "error": None},
    ]

    result = plugin.compare(
        section="PERF",
        key_field="algorithm",
        show_field="algorithm",
        metadata={},
        reference=reference,
        tested=tested,
    )

    stats = _stats(result)
    assert stats["changed"] == 1
    assert stats["compared"] == 1
    assert any(d["field"] == "error" for d in result.get("diffs", []))

    chart_rows = result.get("artifacts", {}).get("chart_rows", [])
    assert chart_rows
    assert chart_rows[0]["status"] == "error_mismatch"


def test_algperf_comparator_detects_significant_avg_difference():
    plugin = comparator_registry.get_plugin("algperf")

    reference = [
        {"algorithm": "ALG_RSA", "avg_ms": 100.0, "min_ms": 90.0, "max_ms": 110.0, "error": None},
    ]
    tested = [
        {"algorithm": "ALG_RSA", "avg_ms": 140.0, "min_ms": 138.0, "max_ms": 142.0, "error": None},
    ]

    result = plugin.compare(
        section="PERF",
        key_field="algorithm",
        show_field="algorithm",
        metadata={},
        reference=reference,
        tested=tested,
    )

    stats = _stats(result)
    assert stats["changed"] == 1
    assert stats["compared"] == 1

    diffs = result.get("diffs", [])
    assert len(diffs) == 1
    assert diffs[0]["field"] == "avg_ms"
    assert diffs[0]["op"] == "<"

    chart_rows = result.get("artifacts", {}).get("chart_rows", [])
    assert chart_rows
    assert chart_rows[0]["status"] == "mismatch"
    assert chart_rows[0]["delta_ms"] == 40.0