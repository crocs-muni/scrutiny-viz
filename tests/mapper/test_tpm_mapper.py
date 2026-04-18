# scrutiny-viz/tests/mapper/test_tpm_mapper.py
from __future__ import annotations

from tests.mapper.helpers import iter_bucket_csvs, run_mapper


def _payload():
    csvs = iter_bucket_csvs("TPMAlgTest")
    assert csvs, "No TPMAlgTest CSV fixtures found"
    return run_mapper(csvs[0], mapper_type="tpm")


def _tpm_ops(payload: dict) -> list[str]:
    return [k for k in payload.keys() if isinstance(k, str) and k.startswith("TPM2_")]


def test_tpm_mapper_emits_info_and_operation_sections():
    payload = _payload()

    assert isinstance(payload, dict)
    assert "TPM_INFO" in payload

    ops = _tpm_ops(payload)
    assert ops, "Expected TPM2_* operation sections"


def test_tpm_mapper_rows_have_required_fields():
    payload = _payload()
    found = 0

    for op in _tpm_ops(payload):
        rows = payload.get(op, [])
        for row in rows:
            assert "algorithm" in row, f"{op}: missing algorithm"
            assert "op_name" in row, f"{op}: missing op_name"
            found += 1

    assert found > 0, "Expected at least one TPM operation record"


def test_tpm_mapper_numeric_fields_are_normalized():
    payload = _payload()
    checked = 0

    for op in _tpm_ops(payload):
        rows = payload.get(op, [])
        for row in rows:
            for field in ("avg_ms", "min_ms", "max_ms"):
                if field in row:
                    assert isinstance(row[field], (int, float)), f"{op}.{field} should be numeric"
                    checked += 1

            if "data_length" in row:
                assert isinstance(row["data_length"], int), f"{op}.data_length should be int"

    assert checked > 0, "Expected at least one numeric TPM timing field"