# scrutiny-viz/tests/mapper/test_bucket_TPMAlgTest.py
from __future__ import annotations

import pytest
from helpers import (
    iter_bucket_csvs, run_mapper, assert_bucket,
    find_schema_for_bucket, write_json, run_verify, assert_verify_ok,
    expected_report_html_path
)

BUCKET = "TPMAlgTest"

@pytest.mark.parametrize("csv_path", iter_bucket_csvs(BUCKET))
def test_TPMAlgTest_regression(csv_path, tmp_path):
    payload = run_mapper(csv_path, mapper_type="tpm")
    assert_bucket(BUCKET, payload, csv_path=csv_path)

    schema = find_schema_for_bucket(BUCKET)
    if schema is None:
        pytest.skip("No matching schema found for TPMAlgTest")
    profile_path = write_json(tmp_path, csv_path.stem, payload)

    proc, out_json = run_verify(schema, profile_path, tmp_path)
    assert_verify_ok(proc, out_json, csv_path=csv_path)
    assert (tmp_path / "results" / "comparison.html").exists()