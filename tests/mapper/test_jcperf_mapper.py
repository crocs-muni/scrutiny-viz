# scrutiny-viz/tests/mapper/test_jcperf_mapper.py
from __future__ import annotations

from tests.mapper.helpers import iter_bucket_csvs, run_mapper


def _payload():
    csvs = iter_bucket_csvs("jcAlgPerf")
    assert csvs, "No jcAlgPerf CSV fixtures found"
    return run_mapper(csvs[0], mapper_type="jcperf")


def _perf_sections(payload: dict) -> list[str]:
    return [k for k in payload.keys() if not str(k).startswith("_")]


def test_jcperf_mapper_emits_non_empty_profile():
    payload = _payload()

    assert isinstance(payload, dict)
    assert isinstance(payload.get("_type"), str)
    assert payload["_type"]

    sections = _perf_sections(payload)
    assert sections, "Expected at least one non-meta section"


def test_jcperf_mapper_rows_have_required_perf_fields():
    payload = _payload()
    found = 0

    for section in _perf_sections(payload):
        rows = payload.get(section, [])
        for row in rows:
            assert "algorithm" in row, f"{section}: missing algorithm"
            assert "op_name" in row, f"{section}: missing op_name"
            found += 1

    assert found > 0, "Expected at least one perf record"


def test_jcperf_mapper_numeric_fields_are_normalized():
    payload = _payload()
    checked = 0

    for section in _perf_sections(payload):
        rows = payload.get(section, [])
        for row in rows:
            for field in ("avg_ms", "min_ms", "max_ms"):
                if field in row:
                    assert isinstance(row[field], (int, float)), f"{section}.{field} should be numeric"
                    checked += 1

            if "data_length" in row:
                assert isinstance(row["data_length"], int), f"{section}.data_length should be int"

    assert checked > 0, "Expected at least one numeric timing field"