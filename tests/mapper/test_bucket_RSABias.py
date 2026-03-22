# scrutiny-viz/tests/mapper/test_bucket_RSABias.py
from __future__ import annotations

import pytest
from helpers import (
    iter_bucket_dirs,
    run_mapper_source,
    assert_bucket,
    find_schema_for_bucket,
    write_json,
    run_verify,
    assert_verify_ok,
    expected_report_html_path,
)

BUCKET = "rsabias"


@pytest.mark.parametrize("source_dir", iter_bucket_dirs(BUCKET), ids=lambda p: p.name)
def test_rsabias_regression(source_dir, tmp_path):
    payload = run_mapper_source(source_dir, mapper_type="rsabias")
    assert_bucket(BUCKET, payload, csv_path=source_dir)

    schema = find_schema_for_bucket(BUCKET)
    if schema is None:
        pytest.skip("No matching schema found for rsabias")

    profile_path = write_json(tmp_path, source_dir.name, payload)

    proc, out_json = run_verify(schema, profile_path, tmp_path)
    assert_verify_ok(proc, out_json, csv_path=source_dir)

    assert expected_report_html_path(tmp_path).exists()