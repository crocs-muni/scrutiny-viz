# scrutiny-viz/tests/mapper/helpers.py
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pytest

from mapper import mapper_utils, registry
from mapper.mappers.contracts import build_context
from utility import repo_path, scrutinize_path


THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = repo_path()
TEST_DATA_DIR = THIS_DIR / "test-data"


@dataclass(frozen=True)
class BucketSpec:
    name: str
    folder: str
    mapper_type: str
    schema_patterns: tuple[str, ...]


BUCKETS: dict[str, BucketSpec] = {
    "jcAlgSupport": BucketSpec(
        name="jcAlgSupport",
        folder="jcAlgSupport",
        mapper_type="jcalgsupport",
        schema_patterns=("algsupport", "alg_support", "jcalgsupport"),
    ),
    "jcAlgPerf": BucketSpec(
        name="jcAlgPerf",
        folder="jcAlgPerf",
        mapper_type="jcperf",
        schema_patterns=("jcalgperf", "algperf", "jcperf", "performance"),
    ),
    "jcAIDScan": BucketSpec(
        name="jcAIDScan",
        folder="jcAIDScan",
        mapper_type="jcaid",
        schema_patterns=("jcaidscan", "aidscan", "aidsupport", "jcaid", "aid"),
    ),
    "TPMAlgTest": BucketSpec(
        name="TPMAlgTest",
        folder="TPMAlgTest",
        mapper_type="tpm",
        schema_patterns=("tpm",),
    ),
}


def expected_report_html_path(base: Optional[Path] = None) -> Path:
    root = base or REPO_ROOT
    return root / "results" / "comparison.html"


def iter_bucket_csvs(bucket_name: str) -> list[Path]:
    spec = BUCKETS[bucket_name]
    p = TEST_DATA_DIR / spec.folder
    if not p.exists():
        return []
    return sorted(p.rglob("*.csv"))


# ----------------- mapping -----------------

def run_mapper(csv_path: Path, mapper_type: str, delimiter: str = ";") -> dict[str, Any]:
    groups = mapper_utils.load_file(str(csv_path))
    assert groups is not None, f"Failed to load CSV: {csv_path}"

    plugin = registry.get_plugin(mapper_type)
    out = plugin.map_groups(groups, build_context(delimiter=delimiter))

    assert isinstance(out, dict), f"Mapper '{mapper_type}' did not return dict for {csv_path}"
    assert "_type" in out, f"Missing _type for {csv_path}"
    return out


# ----------------- generic invariants -----------------

def assert_no_nested_lists(payload: dict[str, Any], *, csv_path: Path) -> None:
    for key, val in payload.items():
        if isinstance(key, str) and key.startswith("_"):
            continue
        if isinstance(val, list):
            bad = [type(x) for x in val if not isinstance(x, dict)]
            assert not bad, f"{csv_path.name}: section '{key}' contains non-dicts: {set(bad)}"


def assert_sections_are_lists(payload: dict[str, Any], *, csv_path: Path, bucket: str) -> None:
    for key, val in payload.items():
        if isinstance(key, str) and key.startswith("_"):
            continue

        if bucket == "jcAIDScan" and key == "Key info":
            assert isinstance(val, dict), f"{csv_path.name}: section '{key}' should be dict (got {type(val)})"
            continue

        assert isinstance(val, list), f"{csv_path.name}: section '{key}' is not a list (got {type(val)})"


def assert_non_empty_profile(payload: dict[str, Any], *, csv_path: Path) -> None:
    non_meta = [k for k in payload.keys() if not str(k).startswith("_")]
    assert non_meta, f"{csv_path.name}: profile has no sections"
    total_rows = sum(len(payload[k]) for k in non_meta if isinstance(payload.get(k), list))
    assert total_rows > 0, f"{csv_path.name}: profile has zero rows"


# ----------------- bucket-specific invariants -----------------

def assert_jcalgsupport(payload: dict[str, Any], *, csv_path: Path) -> None:
    assert "Basic information" in payload, f"{csv_path.name}: missing 'Basic information'"
    algo_sections = [
        k for k in payload.keys()
        if k not in {"Basic information", "JCSystem", "CPLC"} and not str(k).startswith("_")
    ]
    assert algo_sections, f"{csv_path.name}: no algorithm sections found"

    found_alg_row = False
    for sec in algo_sections:
        for rec in payload.get(sec, []):
            if "algorithm_name" in rec:
                found_alg_row = True
                assert "is_supported" in rec, f"{csv_path.name}: {sec} algorithm row missing is_supported: {rec}"
    assert found_alg_row, f"{csv_path.name}: did not find any algorithm rows with 'algorithm_name'"


def assert_jcperf(payload: dict[str, Any], *, csv_path: Path) -> None:
    sections = [k for k in payload.keys() if not str(k).startswith("_")]
    assert sections, f"{csv_path.name}: no sections found"

    total_perf_records = 0
    for sec in sections:
        for rec in payload.get(sec, []):
            assert "algorithm" in rec, f"{csv_path.name}: {sec} record missing algorithm: {rec}"
            assert "op_name" in rec, f"{csv_path.name}: {sec} record missing op_name: {rec}"
            total_perf_records += 1

            for f in ("avg_ms", "min_ms", "max_ms"):
                if f in rec:
                    assert isinstance(rec[f], (int, float)), f"{csv_path.name}: {sec}.{f} not numeric: {rec[f]!r}"

            if "data_length" in rec:
                assert isinstance(rec["data_length"], int), f"{csv_path.name}: {sec}.data_length not int: {rec['data_length']!r}"

    assert total_perf_records > 0, f"{csv_path.name}: no perf records parsed"


def assert_jcaid(payload: dict[str, Any], *, csv_path: Path) -> None:
    assert "Package AID" in payload, f"{csv_path.name}: missing 'Package AID'"
    pkg_rows = payload.get("Package AID", [])
    assert pkg_rows, f"{csv_path.name}: Package AID list is empty"

    keys = []
    for r in pkg_rows:
        assert "package_aid" in r, f"{csv_path.name}: package row missing package_aid: {r}"
        assert "package_name" in r, f"{csv_path.name}: package row missing package_name: {r}"
        assert "version" in r, f"{csv_path.name}: package row missing version: {r}"
        assert "package_key" in r, f"{csv_path.name}: package row missing package_key: {r}"
        keys.append(r["package_key"])

    assert len(keys) == len(set(keys)), f"{csv_path.name}: duplicate package_key values -> comparator will drop rows"

    if "Full package AID support" in payload:
        for r in payload.get("Full package AID support", []):
            assert "full_package_aid" in r, f"{csv_path.name}: full support row missing full_package_aid: {r}"
            assert "supported" in r, f"{csv_path.name}: full support row missing supported: {r}"
            assert isinstance(r["supported"], bool), f"{csv_path.name}: supported not bool: {r['supported']!r}"


def assert_tpm(payload: dict[str, Any], *, csv_path: Path) -> None:
    assert "TPM_INFO" in payload, f"{csv_path.name}: missing TPM_INFO"
    ops = [k for k in payload.keys() if isinstance(k, str) and k.startswith("TPM2_")]
    assert ops, f"{csv_path.name}: no TPM2_* sections found"

    found = 0
    for op in ops:
        rows = payload.get(op, [])
        assert isinstance(rows, list), f"{csv_path.name}: {op} is not a list"
        for r in rows:
            assert "algorithm" in r, f"{csv_path.name}: {op} record missing algorithm: {r}"
            assert "op_name" in r, f"{csv_path.name}: {op} record missing op_name: {r}"
            found += 1
    assert found > 0, f"{csv_path.name}: no TPM records parsed"


def assert_bucket(bucket_name: str, payload: dict[str, Any], *, csv_path: Path) -> None:
    # generic
    assert_sections_are_lists(payload, csv_path=csv_path, bucket=bucket_name)
    assert_no_nested_lists(payload, csv_path=csv_path)
    assert_non_empty_profile(payload, csv_path=csv_path)

    # specific
    if bucket_name == "jcAlgSupport":
        assert_jcalgsupport(payload, csv_path=csv_path)
    elif bucket_name == "jcAlgPerf":
        assert_jcperf(payload, csv_path=csv_path)
    elif bucket_name == "jcAIDScan":
        assert_jcaid(payload, csv_path=csv_path)
    elif bucket_name == "TPMAlgTest":
        assert_tpm(payload, csv_path=csv_path)
    else:
        raise ValueError(f"Unknown bucket: {bucket_name}")


# ----------------- verify -----------------

def find_schema_for_bucket(bucket_name: str) -> Optional[Path]:
    schema_dir = REPO_ROOT / "scrutiny" / "schemas"
    if not schema_dir.exists():
        return None

    yamls = sorted(list(schema_dir.glob("*.yml")) + list(schema_dir.glob("*.yaml")))
    if not yamls:
        return None

    patterns = BUCKETS[bucket_name].schema_patterns
    for pat in patterns:
        for y in yamls:
            if pat.lower() in y.name.lower():
                return y
    return None


def write_json(tmp_dir: Path, stem: str, payload: dict[str, Any]) -> Path:
    p = tmp_dir / f"{stem}.json"
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def run_verify(schema: Path, profile_path: Path, tmp_dir: Path) -> tuple[subprocess.CompletedProcess[str], Path]:
    out_json = tmp_dir / f"{profile_path.stem}.verify.json"

    cmd = [
        sys.executable,
        str(scrutinize_path()),
        "verify",
        "-s", str(schema),
        "-r", str(profile_path),
        "-p", str(profile_path),
        "-o", str(out_json),
        "-rep",
    ]
    proc = subprocess.run(cmd, cwd=tmp_dir, capture_output=True, text=True)
    return proc, out_json


_MISSING_SECTION_RE = re.compile(r"Missing section:\s*'([^']+)'")

def assert_verify_ok(
    proc: subprocess.CompletedProcess[str],
    out_json: Path,
    *,
    csv_path: Path,
) -> None:
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")

    m = _MISSING_SECTION_RE.search(combined)
    if m:
        missing = m.group(1)
        pytest.skip(f"[VERIFY] schema requires section '{missing}' but fixture '{csv_path.name}' does not provide it")

    assert proc.returncode == 0, (
        f"verify failed for {csv_path.name}\n"
        f"STDOUT:\n{proc.stdout}\n"
        f"STDERR:\n{proc.stderr}\n"
    )

    assert out_json.exists(), f"verify did not produce output JSON: {out_json}"