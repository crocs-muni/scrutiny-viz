# scrutiny-viz/tests/workflow/test_bucket_RSABias.py
from __future__ import annotations

import pytest
from tests.mapper.helpers import (
    iter_bucket_dirs,
    run_mapper_source,
    assert_bucket,
    find_schema_for_bucket,
    write_json,
    run_verify_and_report_workflow,
    assert_verify_and_report_workflow_ok,
)

BUCKET = "rsabias"


@pytest.mark.parametrize("source_dir", iter_bucket_dirs(BUCKET), ids=lambda p: p.name)
def test_rsabias_workflow(source_dir, tmp_path):
    payload = run_mapper_source(source_dir, mapper_type="rsabias")
    assert_bucket(BUCKET, payload, csv_path=source_dir)
    schema = find_schema_for_bucket(BUCKET)
    if schema is None:
        pytest.skip("No matching schema found for rsabias")
    profile_path = write_json(tmp_path, source_dir.name, payload)
    proc, out_json, out_html = run_verify_and_report_workflow(schema, profile_path, tmp_path)
    assert_verify_and_report_workflow_ok(proc, out_json, out_html, source_path=source_dir)
