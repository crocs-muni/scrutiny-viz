# scrutiny-viz/tests/mapper/test_registry.py
from __future__ import annotations

import sys
from pathlib import Path

from mapper import registry
from mapper.mappers.contracts import build_context


def test_registry_has_expected_types():
    types_ = registry.list_types()
    assert "jcperf" in types_
    assert "tpm" in types_
    assert "jcaid" in types_
    assert "jcalgsupport" in types_


def test_registry_aliases_work():
    assert registry.normalize_type("perf") == "jcperf"
    assert registry.normalize_type("performance") == "jcperf"
    assert registry.normalize_type("aid") == "jcaid"
    assert registry.normalize_type("javacard-aid") == "jcaid"
    assert registry.normalize_type("jcalg") == "jcalgsupport"


def test_registry_returns_plugin_object():
    plugin = registry.get_plugin("jcperf")
    assert plugin.spec.name == "jcperf"
    assert callable(plugin.map_groups)
    assert callable(plugin.legacy_map)
