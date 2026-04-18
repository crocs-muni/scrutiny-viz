# scrutiny-viz/tests/comparators/test_rsabias.py
from __future__ import annotations

from verification.comparators import registry as comparator_registry


def _stats(result: dict) -> dict:
    return result.get("stats") or result.get("counts") or {}


def test_rsabias_comparator_detects_accuracy_change():
    plugin = comparator_registry.get_plugin("rsabias")
    reference = [{"group": "24", "correct": 95, "wrong": 5, "total": 100, "accuracy_pct": 95.0}]
    tested = [{"group": "24", "correct": 85, "wrong": 15, "total": 100, "accuracy_pct": 85.0}]
    result = plugin.compare(section="ACCURACY_N10", key_field="group", show_field="group", metadata={"threshold_ratio": 0.05, "threshold_count": 1}, reference=reference, tested=tested)
    stats = _stats(result)
    assert result["section"] == "ACCURACY_N10"
    assert stats["changed"] >= 1
    assert any(d["field"] == "accuracy_pct" for d in result.get("diffs", []))


def test_rsabias_comparator_detects_confusion_matrix_value_change():
    plugin = comparator_registry.get_plugin("rsabias")
    reference = [{"cell_id": "0:0", "row_index": 0, "col_index": 0, "value": 90.0}, {"cell_id": "0:1", "row_index": 0, "col_index": 1, "value": 10.0}]
    tested = [{"cell_id": "0:0", "row_index": 0, "col_index": 0, "value": 80.0}, {"cell_id": "0:1", "row_index": 0, "col_index": 1, "value": 20.0}]
    result = plugin.compare(section="CONFUSION_MATRIX_CELLS", key_field="cell_id", show_field="cell_id", metadata={}, reference=reference, tested=tested)
    stats = _stats(result)
    assert stats["changed"] >= 1
    assert any(d["field"] == "value" for d in result.get("diffs", []))
