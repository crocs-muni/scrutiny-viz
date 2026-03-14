# scrutiny-viz/tests/mapper/test_registry.py
from __future__ import annotations

from mapper import registry


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