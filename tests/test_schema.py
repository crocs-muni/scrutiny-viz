# scrutiny-viz/tests/test_schema_modules.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Any, List, Optional
import pytest
from utility import (
    effective_report_types,
    effective_types,
    flatten_prod_schema,
    load_yaml,
    production_module_yml,
)


# Holds one schema test configuration (schema file + required sections + optional extra checks).
@dataclass(frozen=True)
class SchemaCase:
    label: str
    schema_filename: str
    required_sections: List[str]
    check_effective_types: Optional[Callable[[Dict[str, Any]], None]] = None


# Standardized assertion message prefix for schema tests.
def _msg(label: str, text: str) -> str:
    return f"[SCHEMA][{label}] {text}"


# jcAIDScan: verify key sections are table-based via defaults/overrides (effective_report_types).
def _check_jcaidscan_effective_types(schema: Dict[str, Any]) -> None:
    for name in ("packages", "fullPackages"):
        types = effective_report_types(schema, name)
        assert types, _msg("jcAIDScan", f"{name}: no effective report.types found (neither defaults nor override)")
        assert "table" in types, _msg("jcAIDScan", f"{name}: expected 'table' in report.types, got {types}")


# TPMAlgTest: verify TPM_INFO is table-based and at least one TPM2_* has chart/radar.
def _check_tpm_effective_types(schema: Dict[str, Any]) -> None:
    flat = flatten_prod_schema(schema)

    t_info = effective_types(flat["TPM_INFO"])
    assert "table" in t_info, _msg("TPMAlgTest", f"TPM_INFO should include table in report.types, got {t_info}")

    perf_ok = False
    for name, cfg in flat.items():
        if not str(name).startswith("TPM2_"):
            continue
        types = effective_types(cfg)
        if "chart" in types or "radar" in types:
            perf_ok = True
            break

    assert perf_ok, _msg("TPMAlgTest", "Expected at least one TPM2_* section to include chart/radar via report.types")


CASES: List[SchemaCase] = [
    SchemaCase(
        label="jcAIDScan",
        schema_filename="jcAIDScan.yml",
        required_sections=["packages", "fullPackages"],
        check_effective_types=_check_jcaidscan_effective_types,
    ),
    SchemaCase(
        label="TPMAlgTest",
        schema_filename="TPMAlgTest.yml",
        required_sections=["TPM_INFO"],  # TPM2_* is checked in the test body
        check_effective_types=_check_tpm_effective_types,
    ),
]


# Ensures each production schema file parses and contains required sections.
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.label)
def test_production_schema_parses_and_has_expected_sections(case: SchemaCase):
    yml = production_module_yml(case.schema_filename)
    assert yml.exists(), _msg(case.label, f"Missing production schema: {yml}")

    schema = load_yaml(yml)
    assert "schema_version" in schema, _msg(case.label, "schema_version missing")
    assert "sections" in schema and isinstance(schema["sections"], dict), _msg(case.label, "sections missing or not a dict")

    sec = schema["sections"]

    for s in case.required_sections:
        assert s in sec, _msg(case.label, f"Missing required section: {s}")

    if case.label == "TPMAlgTest":
        assert any(str(name).startswith("TPM2_") for name in sec.keys()), _msg(case.label, "Expected at least one TPM2_* section")


# Runs per-schema checks that validate resolved report.types behavior.
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.label)
def test_schema_effective_types_sanity(case: SchemaCase):
    yml = production_module_yml(case.schema_filename)
    schema = load_yaml(yml)

    if case.check_effective_types is None:
        pytest.skip(_msg(case.label, "No effective types checks configured for this schema"))

    case.check_effective_types(schema)
