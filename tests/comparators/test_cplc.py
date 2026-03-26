# scrutiny-viz/tests/comparators/test_cplc.py
from __future__ import annotations

from verification.comparators import registry as comparator_registry


def _stats(result: dict) -> dict:
    return result.get("stats") or result.get("counts") or {}


def test_cplc_comparator_matches_on_first_token_by_default():
    plugin = comparator_registry.get_plugin("cplc")

    reference = [
        {"field": "ICFabricator", "value": "6155 (2016-06-03)"},
    ]
    tested = [
        {"field": "ICFabricator", "value": "6155 (2019-01-01)"},
    ]

    result = plugin.compare(
        section="CPLC",
        key_field="field",
        show_field="field",
        metadata={"include_matches": True},
        reference=reference,
        tested=tested,
    )

    stats = _stats(result)
    assert result["section"] == "CPLC"
    assert stats["matched"] == 1
    assert stats["changed"] == 0
    assert result.get("diffs", []) == []

    matches = result.get("matches", [])
    assert matches
    assert matches[0]["field"] == "value"


def test_cplc_comparator_detects_change_when_first_token_normalization_is_disabled():
    plugin = comparator_registry.get_plugin("cplc")

    reference = [
        {"field": "ICFabricator", "value": "6155 (2016-06-03)"},
    ]
    tested = [
        {"field": "ICFabricator", "value": "6155 (2019-01-01)"},
    ]

    result = plugin.compare(
        section="CPLC",
        key_field="field",
        show_field="field",
        metadata={"compare_first_token": False},
        reference=reference,
        tested=tested,
    )

    stats = _stats(result)
    assert stats["changed"] == 1
    assert stats["compared"] == 1

    diffs = result.get("diffs", [])
    assert len(diffs) == 1
    assert diffs[0]["field"] == "value"
    assert diffs[0]["ref"] == "6155 (2016-06-03)"
    assert diffs[0]["test"] == "6155 (2019-01-01)"


def test_cplc_comparator_detects_missing_rows():
    plugin = comparator_registry.get_plugin("cplc")

    reference = [
        {"field": "ICFabricator", "value": "6155"},
    ]
    tested = []

    result = plugin.compare(
        section="CPLC",
        key_field="field",
        show_field="field",
        metadata={},
        reference=reference,
        tested=tested,
    )

    stats = _stats(result)
    assert stats["only_ref"] == 1
    assert stats["only_test"] == 0
    assert any(d.get("field") == "__presence__" for d in result.get("diffs", []))