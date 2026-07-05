from __future__ import annotations

from verification.cli import build_arg_parser
from verification.comparators import registry as comparator_registry


def _capability_names(spec):
    names = set()
    for capability in spec.visualization_capabilities:
        if capability.variant:
            names.add(f"{capability.visualization_type}:{capability.variant}")
        else:
            names.add(capability.visualization_type)
    return names


def test_builtin_comparators_declare_visualization_capabilities():
    specs_by_name = {spec.name: spec for spec in comparator_registry.list_specs()}

    assert "chart" in _capability_names(specs_by_name["algperf"])
    assert "radar" in _capability_names(specs_by_name["algperf"])
    assert "table" in _capability_names(specs_by_name["basic"])
    assert "table:cplc" in _capability_names(specs_by_name["cplc"])
    assert "table:rsabias_accuracy" in _capability_names(specs_by_name["rsabias"])
    assert "table:rsabias_confusion_top" in _capability_names(specs_by_name["rsabias"])
    assert "table:rsabias_matrix_top" in _capability_names(specs_by_name["rsabias"])
    assert "heatmap" in _capability_names(specs_by_name["rsabias"])
    assert "table:traceclassifier" in _capability_names(specs_by_name["traceclassifier"])
    assert "table:tracescompare" in _capability_names(specs_by_name["tracescompare"])


def test_list_comparators_is_alias_for_list_capabilities():
    parser = build_arg_parser()

    list_capabilities_args = parser.parse_args(["--list-capabilities"])
    list_comparators_args = parser.parse_args(["--list-comparators"])

    assert list_capabilities_args.list_capabilities is True
    assert list_comparators_args.list_capabilities is True
