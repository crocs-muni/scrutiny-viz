from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRUTINIZE = ROOT / "scrutinize.py"


def run_scrutinize(*args: object) -> subprocess.CompletedProcess[str]:
    """Run the project CLI from the repository root and return the completed process."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, str(SCRUTINIZE), *(str(arg) for arg in args)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def combined_output(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


def assert_clean_cli_error(proc: subprocess.CompletedProcess[str], expected_text: str) -> None:
    combined = combined_output(proc)
    assert proc.returncode != 0
    assert expected_text in combined
    assert "Traceback (most recent call last)" not in combined


def write_simple_schema(path: Path, *, comparator: str = "basic", allow_missing_sections: bool = False) -> Path:
    path.write_text(
        f'''
schema_version: "0.13"

ingest:
  dynamic_sections: false
  strict_sections: false
  allow_missing_sections: {"true" if allow_missing_sections else "false"}

defaults:
  data:
    type: list
  report:
    types: ["table"]
  component:
    comparator: basic
    include_matches: true
  target: {{}}

sections:
  SIMPLE:
    data:
      type: list
      record_schema:
        name:
          dtype: string
          required: true
          category: nominal
        value:
          dtype: string
          required: true
          category: nominal
    component:
      comparator: {comparator}
      match_key: name
      show_key: name
      include_matches: true
    report:
      types: ["table"]
'''.strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def write_valid_raw_json(path: Path) -> Path:
    path.write_text(
        json.dumps({"SIMPLE": [{"name": "example", "value": "1"}]}, indent=2),
        encoding="utf-8",
    )
    return path


def test_verify_missing_schema_is_clean_error() -> None:
    missing_schema = ROOT / "scrutiny" / "schemas" / "DOES_NOT_EXIST.yml"
    reference = ROOT / "examples" / "missing_reference.json"
    profile = ROOT / "examples" / "missing_profile.json"

    proc = run_scrutinize(
        "verify",
        "-s",
        missing_schema,
        "-r",
        reference,
        "-p",
        profile,
        "-v",
    )

    assert_clean_cli_error(proc, "Schema file does not exist")
    assert "[VERIFY][ERROR]" in combined_output(proc)


def test_full_missing_reference_json_is_clean_error() -> None:
    schema = ROOT / "scrutiny" / "schemas" / "TPMAlgTest.yml"
    if not schema.exists():
        pytest.skip(f"Required schema fixture not present: {schema}")

    missing_reference = ROOT / "examples" / "TPM" / "does_not_exist_reference.json"
    missing_profile = ROOT / "examples" / "TPM" / "does_not_exist_profile.json"

    proc = run_scrutinize(
        "full",
        "-s",
        schema,
        "-r",
        missing_reference,
        "-p",
        missing_profile,
        "-v",
    )

    assert_clean_cli_error(proc, "Reference JSON input does not exist")
    assert "[FULL][ERROR]" in combined_output(proc)


def test_full_missing_profile_json_is_clean_error(tmp_path: Path) -> None:
    schema = write_simple_schema(tmp_path / "simple.yml")
    reference = write_valid_raw_json(tmp_path / "reference.json")
    missing_profile = tmp_path / "missing_profile.json"

    proc = run_scrutinize("full", "-s", schema, "-r", reference, "-p", missing_profile, "-v")

    assert_clean_cli_error(proc, "Profile JSON input does not exist")
    assert "[FULL][ERROR]" in combined_output(proc)


def test_full_csv_without_mapper_type_is_clean_error(tmp_path: Path) -> None:
    schema = write_simple_schema(tmp_path / "simple.yml")
    reference_csv = tmp_path / "reference.csv"
    profile_csv = tmp_path / "profile.csv"
    reference_csv.write_text("name;value\nexample;1\n", encoding="utf-8")
    profile_csv.write_text("name;value\nexample;1\n", encoding="utf-8")

    proc = run_scrutinize("full", "-s", schema, "-r", reference_csv, "-p", profile_csv, "-v")

    assert_clean_cli_error(proc, "mapper type is required")
    assert "[FULL][ERROR]" in combined_output(proc)


def test_full_unsupported_reference_extension_is_clean_error(tmp_path: Path) -> None:
    schema = write_simple_schema(tmp_path / "simple.yml")
    reference_txt = tmp_path / "reference.txt"
    profile_json = write_valid_raw_json(tmp_path / "profile.json")
    reference_txt.write_text("not a supported input extension", encoding="utf-8")

    proc = run_scrutinize("full", "-s", schema, "-r", reference_txt, "-p", profile_json, "-v")

    assert_clean_cli_error(proc, "reference input must be .json or .csv")
    assert "[FULL][ERROR]" in combined_output(proc)


def test_report_missing_verification_json_is_clean_error() -> None:
    missing_report_json = ROOT / "results" / "does_not_exist.verify.json"

    proc = run_scrutinize("report", "-p", missing_report_json, "-v")

    assert_clean_cli_error(proc, "Verification profile JSON does not exist")
    assert "[REPORT][ERROR]" in combined_output(proc)


def test_map_unknown_mapper_type_is_clean_error(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    source.write_text("name;value\nexample;1\n", encoding="utf-8")

    proc = run_scrutinize("map", "-t", "does-not-exist", source, "-v")

    assert_clean_cli_error(proc, "Unknown mapper type")
    assert "--list-mappers" in combined_output(proc)
    assert "[MAPPER][ERROR]" in combined_output(proc)


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("map", "--list-mappers"), "Available mapper plugins:"),
        (("verify", "--list-comparators"), "Available comparator plugins:"),
        (("report", "--list-viz"), "Available viz plugins:"),
    ],
)
def test_plugin_listing_commands_still_work(args: tuple[str, ...], expected: str) -> None:
    proc = run_scrutinize(*args)
    combined = combined_output(proc)

    assert proc.returncode == 0
    assert expected in combined
    assert "Traceback (most recent call last)" not in combined


def test_verify_invalid_profile_json_is_clean_error(tmp_path: Path) -> None:
    schema = write_simple_schema(tmp_path / "simple.yml")
    reference = write_valid_raw_json(tmp_path / "reference.json")
    bad_profile = tmp_path / "bad_profile.json"
    bad_profile.write_text("{ this is not valid json", encoding="utf-8")

    proc = run_scrutinize("verify", "-s", schema, "-r", reference, "-p", bad_profile, "-v")

    assert_clean_cli_error(proc, "not valid JSON")
    assert "[VERIFY][ERROR]" in combined_output(proc)


def test_verify_unknown_comparator_is_clean_error(tmp_path: Path) -> None:
    schema = write_simple_schema(tmp_path / "bad_comparator.yml", comparator="does-not-exist")
    reference = write_valid_raw_json(tmp_path / "reference.json")
    profile = write_valid_raw_json(tmp_path / "profile.json")

    proc = run_scrutinize("verify", "-s", schema, "-r", reference, "-p", profile, "-v")

    assert_clean_cli_error(proc, "unknown comparator")
    assert "--list-comparators" in combined_output(proc)
    assert "[VERIFY][ERROR]" in combined_output(proc)


def test_verify_missing_required_section_is_clean_error(tmp_path: Path) -> None:
    schema = write_simple_schema(tmp_path / "simple.yml", allow_missing_sections=False)
    reference = write_valid_raw_json(tmp_path / "reference.json")
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({}), encoding="utf-8")

    proc = run_scrutinize("verify", "-s", schema, "-r", reference, "-p", profile, "-v")

    assert_clean_cli_error(proc, "Missing section")
    assert "[VERIFY][ERROR]" in combined_output(proc)


def test_report_invalid_json_is_clean_error(tmp_path: Path) -> None:
    bad_report_json = tmp_path / "bad_verify.json"
    bad_report_json.write_text("{ this is not valid json", encoding="utf-8")

    proc = run_scrutinize("report", "-p", bad_report_json, "-v")

    assert_clean_cli_error(proc, "not valid JSON")
    assert "[REPORT][ERROR]" in combined_output(proc)


def test_report_top_level_array_is_clean_error(tmp_path: Path) -> None:
    bad_report_json = tmp_path / "array_verify.json"
    bad_report_json.write_text(json.dumps([]), encoding="utf-8")

    proc = run_scrutinize("report", "-p", bad_report_json, "-v")

    assert_clean_cli_error(proc, "must contain an object at top level")
    assert "[REPORT][ERROR]" in combined_output(proc)


def test_map_missing_source_path_is_clean_error(tmp_path: Path) -> None:
    missing_source = tmp_path / "missing.csv"

    proc = run_scrutinize("map", "-t", "tpm", missing_source, "-v")

    assert_clean_cli_error(proc, "Mapper source path does not exist")
    assert "[MAPPER][ERROR]" in combined_output(proc)


def test_batch_missing_profiles_dir_is_clean_error(tmp_path: Path) -> None:
    schema = write_simple_schema(tmp_path / "simple.yml")
    reference = write_valid_raw_json(tmp_path / "reference.json")
    missing_profiles_dir = tmp_path / "missing_profiles"

    proc = run_scrutinize(
        "batch-verify",
        "-s",
        schema,
        "-r",
        reference,
        "--profiles-dir",
        missing_profiles_dir,
        "-v",
    )

    assert_clean_cli_error(proc, "Profiles directory does not exist")
    assert "[BATCH][ERROR]" in combined_output(proc)
