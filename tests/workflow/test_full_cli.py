# scrutiny-viz/tests/workflow/test_full_cli.py
from __future__ import annotations

from tests.mapper.helpers import find_schema_for_bucket, iter_bucket_csvs, expected_report_output_path
from tests.utility import repo_path, run_scrutinize


def test_full_cli_csv_to_verify_and_report_jcaid(tmp_path):
    schema = find_schema_for_bucket("jcAIDScan")
    csvs = iter_bucket_csvs("jcAIDScan")
    assert schema is not None
    assert csvs, "No jcAIDScan CSV fixtures found"
    csv_path = csvs[0]
    out_json = tmp_path / "jcaid.verify.json"
    proc = run_scrutinize([
        "full", "-s", str(schema), "-r", str(csv_path), "-p", str(csv_path), "-t", "jcaid", "-vo", str(out_json), "-ro", "comparison.html",
    ], cwd=tmp_path)
    assert proc.returncode == 0, f"full failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert out_json.exists()
    assert expected_report_output_path(tmp_path).exists()


def test_full_cli_json_passthrough_tpm_examples(tmp_path):
    schema = find_schema_for_bucket("TPMAlgTest")
    assert schema is not None
    ref_json = repo_path("examples", "tpm_example1.json")
    prof_json = repo_path("examples", "tpm_example2.json")
    assert ref_json.exists()
    assert prof_json.exists()
    out_json = tmp_path / "tpm.verify.json"
    proc = run_scrutinize([
        "full", "-s", str(schema), "-r", str(ref_json), "-p", str(prof_json), "-vo", str(out_json), "-ro", "comparison.html",
    ], cwd=tmp_path)
    assert proc.returncode == 0, f"full failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert out_json.exists()
    assert expected_report_output_path(tmp_path).exists()
