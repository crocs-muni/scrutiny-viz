# scrutiny-viz/tests/comparators/test_basic.py
from __future__ import annotations

from verification.comparators import registry as comparator_registry


def _stats(result: dict) -> dict:
    return result.get("stats") or result.get("counts") or {}


def test_basic_comparator_detects_changed_and_extra_rows():
    plugin = comparator_registry.get_plugin("basic")
    reference = [{"name": "A", "value": "x"}, {"name": "B", "value": "y"}]
    tested = [{"name": "A", "value": "x"}, {"name": "B", "value": "z"}, {"name": "C", "value": "w"}]
    result = plugin.compare(section="Example", key_field="name", show_field="name", metadata={}, reference=reference, tested=tested)
    stats = _stats(result)
    assert result["section"] == "Example"
    assert stats["changed"] >= 1
    assert stats["only_test"] >= 1
    assert any(d["key"] == "B" for d in result.get("diffs", []))


def test_basic_comparator_detects_missing_rows():
    plugin = comparator_registry.get_plugin("basic")
    result = plugin.compare(section="Example", key_field="name", show_field="name", metadata={}, reference=[{"name": "A", "value": "x"}], tested=[])
    stats = _stats(result)
    assert stats["only_ref"] >= 1
    assert any(d.get("field") == "__presence__" for d in result.get("diffs", []))
