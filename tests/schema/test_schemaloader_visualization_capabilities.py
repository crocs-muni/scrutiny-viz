from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scrutiny.errors import SchemaError
from scrutiny.schemaloader import SchemaLoader


def _write_schema(tmp_path: Path, *, comparator: str, report_types, schema_version: str = "0.14") -> Path:
    schema_path = tmp_path / "structure.yml"
    schema = {
        "schema_version": schema_version,
        "sections": {
            "PERF": {
                "data": {
                    "type": "list",
                    "record_schema": {
                        "key": "str",
                        "value": "float",
                    },
                },
                "component": {
                    "comparator": comparator,
                    "match_key": "key",
                },
                "report": {
                    "types": report_types,
                },
            }
        },
    }
    schema_path.write_text(yaml.safe_dump(schema, sort_keys=False), encoding="utf-8")
    return schema_path


def test_schemaloader_accepts_declared_algperf_visualizations(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path, comparator="algperf", report_types=["chart", "radar", "table"])

    schema = SchemaLoader(str(schema_path)).load()

    assert schema["PERF"]["report"]["types"] == [
        {"type": "chart", "variant": None},
        {"type": "radar", "variant": None},
        {"type": "table", "variant": None},
    ]
    assert schema._loader_meta["visualization_capability_validation"] is True


def test_schemaloader_rejects_undeclared_visualization_for_comparator(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path, comparator="algperf", report_types=["heatmap"])

    with pytest.raises(SchemaError) as error_info:
        SchemaLoader(str(schema_path)).load()

    message = str(error_info.value)
    assert "Section 'PERF'" in message
    assert "heatmap" in message
    assert "algperf" in message
    assert "--list-capabilities" in message


def test_schemaloader_accepts_colon_variant_string_when_comparator_declares_it(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path, comparator="cplc", report_types=["table:cplc"])

    schema = SchemaLoader(str(schema_path)).load()

    assert schema["PERF"]["report"]["types"] == [{"type": "table", "variant": "cplc"}]


def test_schemaloader_rejects_wrong_table_variant(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path, comparator="cplc", report_types=[{"type": "table", "variant": "wrong"}])

    with pytest.raises(SchemaError) as error_info:
        SchemaLoader(str(schema_path)).load()

    message = str(error_info.value)
    assert "table:wrong" in message
    assert "table:cplc" in message


def test_schemaloader_accepts_unvarianted_table_when_comparator_declares_table_capability(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path, comparator="cplc", report_types=["table"])

    schema = SchemaLoader(str(schema_path)).load()

    assert schema["PERF"]["report"]["types"] == [{"type": "table", "variant": None}]


def test_schemaloader_rejects_unknown_comparator_early(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path, comparator="missing_comparator", report_types=["table"])

    with pytest.raises(SchemaError) as error_info:
        SchemaLoader(str(schema_path)).load()

    message = str(error_info.value)
    assert "unknown component.comparator" in message
    assert "missing_comparator" in message
    assert "--list-capabilities" in message


def test_schema_version_014_is_supported_for_new_schema_validation(tmp_path: Path) -> None:
    schema_path = _write_schema(
        tmp_path,
        comparator="algperf",
        report_types=["chart"],
        schema_version="0.14",
    )

    schema = SchemaLoader(str(schema_path)).load()

    assert schema._loader_meta["schema_version"] == "0.14"
