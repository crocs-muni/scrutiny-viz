# scrutiny-viz/tests/workflow/test_report_output_path.py
from __future__ import annotations

from pathlib import Path

from tests.mapper.helpers import find_schema_for_bucket
from tests.utility import repo_path, run_scrutinize


def _verify_tpm_examples(tmp_path: Path) -> Path:
    schema = find_schema_for_bucket("TPMAlgTest")
    assert schema is not None
    out_json = tmp_path / "verify" / "tpm.json"
    proc = run_scrutinize([
        "verify", "-s", str(schema),
        "-r", str(repo_path("examples", "TPM", "tpm_example1.json")),
        "-p", str(repo_path("examples", "TPM", "tpm_example2.json")),
        "-o", str(out_json),
    ], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    return out_json


def test_report_output_with_directory_is_used_as_given(tmp_path):
    verify_json = _verify_tpm_examples(tmp_path)
    proc = run_scrutinize(["report", "-p", str(verify_json), "-o", "out/tpm/report.html"], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "out" / "tpm" / "report.html").is_file()
    assert list((tmp_path / "out" / "tpm").glob("results_*.zip"))
    assert not (tmp_path / "results").exists()


def test_report_output_bare_name_goes_to_results(tmp_path):
    verify_json = _verify_tpm_examples(tmp_path)
    proc = run_scrutinize(["report", "-p", str(verify_json), "-o", "report.html", "--no-zip"], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "results" / "report.html").is_file()


def test_full_report_output_with_directory_is_used_as_given(tmp_path):
    schema = find_schema_for_bucket("TPMAlgTest")
    assert schema is not None
    proc = run_scrutinize([
        "full", "-s", str(schema),
        "-r", str(repo_path("examples", "TPM", "tpm_example1.json")),
        "-p", str(repo_path("examples", "TPM", "tpm_example2.json")),
        "--verify-output", "out/verify.json",
        "--report-output", "out/report.html",
        "--no-zip",
    ], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "out" / "verify.json").is_file()
    assert (tmp_path / "out" / "report.html").is_file()


def test_traceclassifier_report_bundles_images_next_to_html(tmp_path):
    mapped = tmp_path / "classifier.json"
    proc = run_scrutinize([
        "map", "-t", "traceclassifier",
        str(repo_path("examples", "Traces", "Feitian_JAVCOS_TraceClassifier", "traceclassifier.json")),
        "-o", str(mapped),
    ], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    verify_json = tmp_path / "classifier.verify.json"
    proc = run_scrutinize([
        "verify", "-s", str(repo_path("scrutiny", "schemas", "TraceClassifier.yml")),
        "-r", str(repo_path("examples", "Traces", "traceclassifier_stub.json")),
        "-p", str(mapped), "-o", str(verify_json),
    ], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    proc = run_scrutinize(["report", "-p", str(verify_json), "-o", "out/classifier.html", "--no-zip"], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr

    html = (tmp_path / "out" / "classifier.html").read_text(encoding="utf-8")
    assert "file://" not in html
    assert list((tmp_path / "out" / "classifier_assets").rglob("*.png"))
