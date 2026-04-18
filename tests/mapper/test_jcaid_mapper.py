# scrutiny-viz/tests/mapper/test_jcaid_mapper.py
from __future__ import annotations

from tests.mapper.helpers import iter_bucket_csvs, run_mapper


def _payload():
    csvs = iter_bucket_csvs("jcAIDScan")
    assert csvs, "No jcAIDScan CSV fixtures found"
    return run_mapper(csvs[0], mapper_type="jcaid")


def test_jcaid_mapper_emits_non_empty_profile():
    payload = _payload()

    assert isinstance(payload, dict)
    assert isinstance(payload.get("_type"), str)
    assert payload["_type"] == "javacard-aid"

    non_meta_sections = [k for k in payload.keys() if not str(k).startswith("_")]
    assert non_meta_sections, "Expected non-meta sections in mapped payload"


def test_jcaid_mapper_normalizes_package_rows():
    payload = _payload()

    assert "Package AID" in payload
    rows = payload["Package AID"]
    assert rows, "Package AID rows should not be empty"

    keys = []
    for row in rows:
        assert "package_aid" in row
        assert "package_name" in row
        assert "version" in row
        assert "package_key" in row
        keys.append(row["package_key"])

    assert len(keys) == len(set(keys)), "package_key must be unique for comparison"


def test_jcaid_mapper_normalizes_full_support_bool():
    payload = _payload()

    if "Full package AID support" not in payload:
        return

    rows = payload["Full package AID support"]
    for row in rows:
        assert "full_package_aid" in row
        assert "supported" in row
        assert isinstance(row["supported"], bool)