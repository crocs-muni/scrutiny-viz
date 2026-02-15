# scrutiny-viz/tests/test_ingestion_modules.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Tuple
import pytest
from scrutiny.ingest import JsonParser
from utility import (
    assert_required_fields_present,
    build_minimal_raw_json,
    build_parser_schema_from_production_yml,
    examples_dir,
    find_raw_fixture_for_sections,
    load_yaml,
    production_module_yml,
)

# Defines which production schemas to ingestion-test: (schema_filename, label, require_real_example).
MODULES: List[Tuple[str, str, bool]] = [
    ("jcAIDScan.yml", "jcAIDScan", False),   # optional example fixture
    ("TPMAlgTest.yml", "TPMAlgTest", True),  # require a real example fixture
]


# Loads production YAML and converts it into the merged per-section schema expected by JsonParser.
def _parser_schema(schema_filename: str) -> Dict[str, Dict]:
    yml_path = production_module_yml(schema_filename)
    assert yml_path.exists(), f"[INGEST][{schema_filename}] Missing production schema: {yml_path}"
    schema_yml = load_yaml(yml_path)
    return build_parser_schema_from_production_yml(schema_yml)


# Builds a consistent, actionable error/skip message when no raw fixture matches the schema sections.
def _missing_fixture_message(label: str, schema_filename: str, section_names: List[str]) -> str:
    n = len(section_names)
    return (
        f"[INGEST][{label}] No RAW module JSON found under {examples_dir()} matching schema {schema_filename}.\n"
        f"[INGEST][{label}] JsonParser expects RAW shape with ALL {n} sections present:\n"
        f"[INGEST][{label}]   {{ section_name: [ {{...}}, ... ], ... }}\n"
        f"[INGEST][{label}] If a section has no rows, include it as an empty list.\n"
        f"[INGEST][{label}] Missing fixture is OK for some modules (optional), but this module is configured as required."
    )


# Ensures JsonParser accepts a minimal synthetic raw JSON that satisfies match_key + required:true fields.
@pytest.mark.parametrize("schema_filename,label,_require", MODULES)
def test_jsonparser_accepts_minimal_synthetic_raw_json(schema_filename: str, label: str, _require: bool, tmp_path: Path):
    parser_schema = _parser_schema(schema_filename)

    raw = build_minimal_raw_json(parser_schema)
    p = tmp_path / f"synthetic_{label}.json"
    p.write_text(json.dumps(raw), encoding="utf-8")

    parser = JsonParser(parser_schema)
    parsed = parser.parse(str(p))

    assert set(parsed.keys()) == set(parser_schema.keys()), f"[INGEST][{label}] Parsed sections differ from schema sections"
    assert_required_fields_present(parser_schema, parsed)


# If a matching raw fixture exists in data/examples, parses it and verifies required fields are present.
@pytest.mark.parametrize("schema_filename,label,require_real_example", MODULES)
def test_jsonparser_parses_real_example_if_present(schema_filename: str, label: str, require_real_example: bool):
    parser_schema = _parser_schema(schema_filename)
    section_names = list(parser_schema.keys())

    fixture = find_raw_fixture_for_sections(examples_dir(), section_names)
    if fixture is None:
        msg = _missing_fixture_message(label, schema_filename, section_names)
        if require_real_example:
            pytest.fail(msg)
        pytest.skip(msg)

    parser = JsonParser(parser_schema)
    parsed = parser.parse(str(fixture))

    assert set(parsed.keys()) == set(parser_schema.keys()), f"[INGEST][{label}] Parsed sections differ from schema sections"
    assert_required_fields_present(parser_schema, parsed)
