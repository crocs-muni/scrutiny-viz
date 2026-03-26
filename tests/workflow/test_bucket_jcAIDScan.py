# scrutiny-viz/tests/workflow/test_bucket_jcAIDScan.py
from __future__ import annotations

import pytest
from tests.mapper.helpers import (
    iter_bucket_csvs,
    run_mapper,
    assert_bucket,
    find_schema_for_bucket,
    write_json,
    run_verify_and_report_workflow,
    assert_verify_and_report_workflow_ok,
)

BUCKET = "jcAIDScan"


@pytest.mark.parametrize("csv_path", iter_bucket_csvs(BUCKET))
def test_jcAIDScan_workflow(csv_path, tmp_path):
    payload = run_mapper(csv_path, mapper_type="jcaid")
    assert_bucket(BUCKET, payload, csv_path=csv_path)
    schema = find_schema_for_bucket(BUCKET)
    if schema is None:
        pytest.skip("No matching schema found for jcAIDScan")
    profile_path = write_json(tmp_path, csv_path.stem, payload)
    proc, out_json, out_html = run_verify_and_report_workflow(schema, profile_path, tmp_path)
    assert_verify_and_report_workflow_ok(proc, out_json, out_html, source_path=csv_path)
