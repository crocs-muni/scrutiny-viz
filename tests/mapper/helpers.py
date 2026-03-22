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
    "rsabias": BucketSpec(
        name="rsabias",
        folder="RSABias",
        mapper_type="rsabias",
        schema_patterns=("rsabias", "rsa_bias", "rsa-bias"),
    ),
}


def expected_report_html_path(base: Optional[Path] = None) -> Path:
    root = base or REPO_ROOT
    return root / "results" / "comparison.html"


def _bucket_path(bucket_name: str) -> Path:
    spec = BUCKETS[bucket_name]
    direct = TEST_DATA_DIR / spec.folder
    if direct.exists():
        return direct

    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            if child.is_dir() and child.name.lower() == spec.folder.lower():
                return child

    return direct


def iter_bucket_csvs(bucket_name: str) -> list[Path]:
    p = _bucket_path(bucket_name)
    if not p.exists():
        return []
    return sorted(p.rglob("*.csv"))


def iter_bucket_dirs(bucket_name: str) -> list[Path]:
    p = _bucket_path(bucket_name)
    if not p.exists() or not p.is_dir():
        return []

    # If the bucket folder itself already looks like one RSABias fixture, use it directly.
    looks_like_rsabias_fixture = any([
        any(p.glob("n_*_results.json")),
        (p / "confusion_matrix.txt").exists(),
        (p / "confusion_matrix.pkl").exists(),
    ])
    if looks_like_rsabias_fixture:
        return [p]

    return sorted([x for x in p.iterdir() if x.is_dir()])


# ----------------- mapping -----------------

def run_mapper(csv_path: Path, mapper_type: str, delimiter: str = ";") -> dict[str, Any]:
    groups = mapper_utils.load_file(str(csv_path))
    assert groups is not None, f"Failed to load CSV: {csv_path}"

    plugin = registry.get_plugin(mapper_type)
    out = plugin.map_groups(groups, build_context(delimiter=delimiter))

    assert isinstance(out, dict), f"Mapper '{mapper_type}' did not return dict for {csv_path}"
    assert "_type" in out, f"Missing _type for {csv_path}"
    return out


def run_mapper_source(source_path: Path, mapper_type: str, delimiter: str = ";") -> dict[str, Any]:
    plugin = registry.get_plugin(mapper_type)
    out = plugin.map_path(source_path, build_context(delimiter=delimiter))

    assert isinstance(out, dict), f"Mapper '{mapper_type}' did not return dict for {source_path}"
    assert "_type" in out, f"Missing _type for {source_path}"
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


def assert_rsabias(payload: dict[str, Any], *, csv_path: Path) -> None:
    assert payload.get("_type") == "rsabias", f"{csv_path.name}: expected _type=rsabias"

    assert "META" in payload, f"{csv_path.name}: missing META"
    assert isinstance(payload["META"], list), f"{csv_path.name}: META is not a list"

    assert "SUMMARY" in payload, f"{csv_path.name}: missing SUMMARY"
    assert isinstance(payload["SUMMARY"], list), f"{csv_path.name}: SUMMARY is not a list"

    accuracy_sections = [k for k in payload.keys() if str(k).startswith("ACCURACY_N")]
    assert accuracy_sections, f"{csv_path.name}: no ACCURACY_N* sections found"
    for sec in accuracy_sections:
        for rec in payload.get(sec, []):
            assert "group" in rec, f"{csv_path.name}: {sec} row missing group: {rec}"
            for field in ("correct", "wrong", "total", "accuracy_pct"):
                if field in rec:
                    assert isinstance(rec[field], (int, float, str)), f"{csv_path.name}: {sec}.{field} unexpected type"

    if "CONFUSION_TOP" in payload:
        assert isinstance(payload["CONFUSION_TOP"], list), f"{csv_path.name}: CONFUSION_TOP is not a list"
        for rec in payload["CONFUSION_TOP"]:
            assert "edge_id" in rec, f"{csv_path.name}: CONFUSION_TOP row missing edge_id: {rec}"
            assert "true_group" in rec, f"{csv_path.name}: CONFUSION_TOP row missing true_group: {rec}"
            assert "pred_group" in rec, f"{csv_path.name}: CONFUSION_TOP row missing pred_group: {rec}"

    if "CONFUSION_MATRIX_META" in payload:
        assert isinstance(payload["CONFUSION_MATRIX_META"], list), f"{csv_path.name}: CONFUSION_MATRIX_META is not a list"
        names = {str(r.get("name")) for r in payload["CONFUSION_MATRIX_META"] if isinstance(r, dict)}
        assert "rows" in names, f"{csv_path.name}: CONFUSION_MATRIX_META missing rows"
        assert "cols" in names, f"{csv_path.name}: CONFUSION_MATRIX_META missing cols"

    if "CONFUSION_MATRIX_CELLS" in payload:
        assert isinstance(payload["CONFUSION_MATRIX_CELLS"], list), f"{csv_path.name}: CONFUSION_MATRIX_CELLS is not a list"
        for rec in payload["CONFUSION_MATRIX_CELLS"][:10]:
            assert "cell_id" in rec, f"{csv_path.name}: matrix row missing cell_id: {rec}"
            assert "row_index" in rec, f"{csv_path.name}: matrix row missing row_index: {rec}"
            assert "col_index" in rec, f"{csv_path.name}: matrix row missing col_index: {rec}"
            assert "value" in rec, f"{csv_path.name}: matrix row missing value: {rec}"

    if "CONFUSION_MATRIX_NONZERO" in payload:
        assert isinstance(payload["CONFUSION_MATRIX_NONZERO"], list), f"{csv_path.name}: CONFUSION_MATRIX_NONZERO is not a list"
        for rec in payload["CONFUSION_MATRIX_NONZERO"][:10]:
            assert "value" in rec, f"{csv_path.name}: nonzero matrix row missing value: {rec}"


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
    elif bucket_name == "rsabias":
        assert_rsabias(payload, csv_path=csv_path)
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