# scrutiny-viz/tests/plugins/test_ingestion.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

from scrutiny.ingest import JsonParser
from scrutiny.schemaloader import SchemaLoader
from tests.utility import (
    assert_required_fields_present,
    build_minimal_raw_json,
    build_parser_schema_from_production_yml,
    examples_dir,
    find_raw_fixture_for_sections,
    load_yaml,
    production_module_yml,
)

MODULES: List[Tuple[str, str, bool]] = [
    ("jcAIDScan.yml", "jcAIDScan", True),
    ("TPMAlgTest.yml", "TPMAlgTest", True),
    ("RSABiasEval.yml", "RSABias", False),
]


def _parser_schema(schema_filename: str) -> Dict[str, Dict]:
    yml_path = production_module_yml(schema_filename)
    assert yml_path.exists(), f"[INGEST][{schema_filename}] Missing production schema: {yml_path}"
    schema_yml = load_yaml(yml_path)
    return build_parser_schema_from_production_yml(schema_yml)


def _missing_fixture_message(label: str, schema_filename: str, section_names: List[str]) -> str:
    n = len(section_names)
    return (
        f"[INGEST][{label}] No RAW module JSON found under {examples_dir()} matching schema {schema_filename}.\n"
        f"[INGEST][{label}] JsonParser expects RAW shape with ALL {n} sections present:\n"
        f"[INGEST][{label}]   {{ section_name: [ {{...}}, ... ], ... }}\n"
        f"[INGEST][{label}] If a section has no rows, include it as an empty list.\n"
        f"[INGEST][{label}] Missing fixture is OK for some modules (optional), but this module is configured as required."
    )


@pytest.mark.parametrize("schema_filename,label,_require", MODULES)
def test_jsonparser_accepts_minimal_synthetic_raw_json(schema_filename: str, label: str, _require: bool, tmp_path: Path):
    parser_schema = _parser_schema(schema_filename)
    raw = build_minimal_raw_json(parser_schema)
    p = tmp_path / f"synthetic_{label}.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    parser = JsonParser(parser_schema)
    parsed = parser.parse(str(p))
    assert set(parsed.keys()) == set(parser_schema.keys())
    assert_required_fields_present(parser_schema, parsed)


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
    assert set(parsed.keys()) == set(parser_schema.keys())
    assert_required_fields_present(parser_schema, parsed)


def _write_dynamic_schema(tmp_path: Path, strict_sections: bool) -> Path:
    yml = tmp_path / "dynamic_sections.yml"
    yml.write_text(f'''
schema_version: "0.13"

ingest:
  dynamic_sections: true
  strict_sections: {"true" if strict_sections else "false"}
  allow_missing_sections: true

defaults:
  data:
    type: list
    record_schema:
      algorithm_name:
        dtype: string
        required: true
        category: nominal
      is_supported:
        dtype: string
        category: binary

  component:
    comparator: basic
    match_key: algorithm_name
    show_key: algorithm_name
    include_matches: true

  report:
    types: ["table", "radar"]
    theme: dark

  target: {{}}

sections:
  "Basic information":
    data:
      type: list
      record_schema:
        name:
          dtype: string
          required: true
          category: nominal
        value:
          dtype: string
          category: nominal
    component:
      comparator: basic
      match_key: name
      show_key: name
      include_matches: true
    report:
      types: ["table"]
'''.strip() + "\n", encoding="utf-8")
    return yml


def _load_dynamic_schema(schema_path: Path):
    return SchemaLoader(str(schema_path)).load()


def _write_dynamic_json(tmp_path: Path, filename: str, payload: dict) -> Path:
    p = tmp_path / filename
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def test_ingestion_dynamic_section_succeeds_in_permissive_mode(tmp_path: Path):
    schema_path = _write_dynamic_schema(tmp_path, strict_sections=False)
    schema = _load_dynamic_schema(schema_path)
    raw = {"Basic information": [{"name": "Card name", "value": "ExampleCard"}], "javacard.crypto.Signature": [{"algorithm_name": "ALG_RSA_SHA_PKCS1", "is_supported": "yes"}, {"algorithm_name": "ALG_RSA_SHA_256_PKCS1", "is_supported": "no"}]}
    raw_path = _write_dynamic_json(tmp_path, "dynamic_ok.json", raw)
    parser = JsonParser(schema)
    parsed = parser.parse(str(raw_path))
    assert "Basic information" in parsed
    assert "javacard.crypto.Signature" in parsed
    assert parsed._ingest_meta["applied_dynamic_sections"] == ["javacard.crypto.Signature"]
    assert "javacard.crypto.Signature" in parsed._ingest_meta["dynamic_section_configs"]
    cfg = parsed._ingest_meta["dynamic_section_configs"]["javacard.crypto.Signature"]
    assert cfg["component"]["match_key"] == "algorithm_name"
    assert cfg["component"]["show_key"] == "algorithm_name"
    assert "javacard.crypto.Signature" in schema


def test_ingestion_dynamic_section_fails_in_strict_mode(tmp_path: Path):
    schema_path = _write_dynamic_schema(tmp_path, strict_sections=True)
    schema = _load_dynamic_schema(schema_path)
    raw = {"Basic information": [{"name": "Card name", "value": "ExampleCard"}], "javacard.crypto.Signature": [{"algorithm_name": "ALG_RSA_SHA_PKCS1", "is_supported": "yes"}]}
    raw_path = _write_dynamic_json(tmp_path, "dynamic_strict_fail.json", raw)
    parser = JsonParser(schema)
    with pytest.raises(KeyError, match="Unknown section"):
        parser.parse(str(raw_path))


def test_ingestion_dynamic_section_invalid_is_skipped(tmp_path: Path):
    schema_path = _write_dynamic_schema(tmp_path, strict_sections=False)
    schema = _load_dynamic_schema(schema_path)
    raw = {"Basic information": [{"name": "Card name", "value": "ExampleCard"}], "javacardx.crypto.Cipher": [{"is_supported": "yes"}]}
    raw_path = _write_dynamic_json(tmp_path, "dynamic_skip.json", raw)
    parser = JsonParser(schema)
    parsed = parser.parse(str(raw_path))
    assert "Basic information" in parsed
    assert "javacardx.crypto.Cipher" not in parsed
    skipped = parsed._ingest_meta["skipped_sections"]
    assert skipped
    assert skipped[0]["section"] == "javacardx.crypto.Cipher"
    assert "missing required field 'algorithm_name'" in skipped[0]["reason"]
    assert parsed._ingest_meta["applied_dynamic_sections"] == []
    assert parsed._ingest_meta["dynamic_section_configs"] == {}
