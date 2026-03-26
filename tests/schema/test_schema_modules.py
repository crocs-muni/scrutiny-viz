# scrutiny-viz/tests/plugins/test_schema_modules.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Any, List, Optional
import pytest
from tests.utility import effective_report_types, effective_types, flatten_prod_schema, load_yaml, production_module_yml


@dataclass(frozen=True)
class SchemaCase:
    label: str
    schema_filename: str
    required_sections: List[str]
    check_effective_types: Optional[Callable[[Dict[str, Any]], None]] = None


def _msg(label: str, text: str) -> str:
    return f"[SCHEMA][{label}] {text}"


def _check_jcaidscan_effective_types(schema: Dict[str, Any]) -> None:
    for name in ("packages", "fullPackages"):
        types = effective_report_types(schema, name)
        assert types
        assert "table" in types


def _check_tpm_effective_types(schema: Dict[str, Any]) -> None:
    flat = flatten_prod_schema(schema)
    assert "table" in effective_types(flat["TPM_INFO"])
    perf_ok = False
    for name, cfg in flat.items():
        if not str(name).startswith("TPM2_"):
            continue
        types = effective_types(cfg)
        if "chart" in types or "radar" in types:
            perf_ok = True
            break
    assert perf_ok


def _check_rsabias_effective_types(schema: Dict[str, Any]) -> None:
    types = effective_report_types(schema, "CONFUSION_MATRIX_CELLS")
    assert "heatmap" in types


CASES: List[SchemaCase] = [
    SchemaCase("jcAIDScan", "jcAIDScan.yml", ["Package AID", "Full package AID support"], _check_jcaidscan_effective_types),
    SchemaCase("TPMAlgTest", "TPMAlgTest.yml", ["TPM_INFO"], _check_tpm_effective_types),
    SchemaCase("RSABias", "RSABiasEval.yml", ["META", "SUMMARY", "CONFUSION_MATRIX_CELLS"], _check_rsabias_effective_types),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.label)
def test_production_schema_parses_and_has_expected_sections(case: SchemaCase):
    yml = production_module_yml(case.schema_filename)
    assert yml.exists(), _msg(case.label, f"Missing production schema: {yml}")
    schema = load_yaml(yml)
    assert "schema_version" in schema
    assert "sections" in schema and isinstance(schema["sections"], dict)
    sec = schema["sections"]
    for s in case.required_sections:
        assert s in sec
    if case.label == "TPMAlgTest":
        assert any(str(name).startswith("TPM2_") for name in sec.keys())


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.label)
def test_schema_effective_types_sanity(case: SchemaCase):
    yml = production_module_yml(case.schema_filename)
    schema = load_yaml(yml)
    if case.check_effective_types is None:
        pytest.skip(_msg(case.label, "No effective types checks configured for this schema"))
    case.check_effective_types(schema)
