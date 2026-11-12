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

def test_rsabias_mapper_accuracy_counts_top1_only():
    import json
    from tests.mapper.helpers import iter_bucket_dirs

    eval_dir = iter_bucket_dirs("rsabias")[0]
    payload = _payload()
    raw = json.loads((eval_dir / "n_1_results.json").read_text())["accuracies"]["1"]

    for row in payload["ACCURACY_N1"]:
        assert row["correct"] == raw[row["group"]]["correct"]
        assert row["wrong"] == raw[row["group"]]["wrong"]


def test_rsabias_mapper_labels_confusion_matrix_by_group():
    payload = _payload()
    meta = {row["name"]: row["value"] for row in payload["CONFUSION_MATRIX_META"]}
    assert meta["labels_mode"] == "group"

    cells = {row["cell_id"]: row for row in payload["CONFUSION_MATRIX_CELLS"]}
    assert [cells[f"11:{g}"]["col_index"] for g in ("1", "2", "10")] == [0, 1, 9]
    assert cells["11:12"]["value"] == 0.55
    assert cells["11:12"]["row_label"] == "11" and cells["11:12"]["col_label"] == "12"
