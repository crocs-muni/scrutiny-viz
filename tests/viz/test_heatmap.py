# scrutiny-viz/tests/viz/test_heatmap.py
from __future__ import annotations

from typing import Any, Dict, List

from report.viz import registry as viz_registry


def _matrix_rows() -> List[Dict[str, Any]]:
    return [
        {"cell_id": "0:0", "row_index": 0, "col_index": 0, "row_label": "g0", "col_label": "g0", "value": 90.0, "is_diagonal": True},
        {"cell_id": "0:1", "row_index": 0, "col_index": 1, "row_label": "g0", "col_label": "g1", "value": 10.0, "is_diagonal": False},
        {"cell_id": "1:0", "row_index": 1, "col_index": 0, "row_label": "g1", "col_label": "g0", "value": 5.0, "is_diagonal": False},
        {"cell_id": "1:1", "row_index": 1, "col_index": 1, "row_label": "g1", "col_label": "g1", "value": 95.0, "is_diagonal": True},
    ]


def _matches_from_matrix_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for row in rows:
        cell_key = str(row["cell_id"])
        for field_name in ("row_index", "col_index", "row_label", "col_label", "value"):
            matches.append({"key": cell_key, "field": field_name, "value": row[field_name]})
    return matches


def _section_from_matrix_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "meta": {
            "report": {
                "types": [{"type": "heatmap", "variant": None}],
            }
        },
        "original": {
            "reference": {"rows": rows},
            "profile": {"rows": rows},
        },
        "results": {
            "state": "MATCH",
            "stats": {
                "compared": len(rows),
                "changed": 0,
                "matched": len(rows),
                "only_reference": 0,
                "only_profile": 0,
            },
            "labels": {},
            "matches": _matches_from_matrix_rows(rows),
            "differences": {"changed": [], "groups": [], "only_reference": [], "only_profile": []},
            "raw_differences": [],
        },
        "visualizations": {
            "requested": [{"type": "heatmap", "variant": None}],
            "available": {},
            "unavailable": [],
        },
        "artifacts": {},
    }


def test_heatmap_plugin_is_registered():
    plugin = viz_registry.get_plugin("heatmap")
    assert plugin is not None
    assert plugin.spec.name == "heatmap"


def test_heatmap_plugin_render_smoke():
    plugin = viz_registry.get_plugin("heatmap")
    section = _section_from_matrix_rows(_matrix_rows())

    node = plugin.render(
        section_name="CONFUSION_MATRIX_CELLS",
        section=section,
        idx=0,
        ref_name="ref",
        prof_name="prof",
        variant=None,
    )

    html = str(node)
    assert isinstance(html, str)
    assert html.startswith("<div")
    assert html.endswith("</div>")
    assert "Heatmap: CONFUSION_MATRIX_CELLS" in html
    assert "<svg" in html
    assert "g0" in html
    assert "g1" in html


def test_heatmap_plugin_accepts_matrix_like_input():
    plugin = viz_registry.get_plugin("heatmap")
    section = _section_from_matrix_rows(
        [
            {"cell_id": "0:0", "row_index": 0, "col_index": 0, "row_label": "A", "col_label": "A", "value": 100.0, "is_diagonal": True},
        ]
    )

    node = plugin.render(
        section_name="CONFUSION_MATRIX_CELLS",
        section=section,
        idx=0,
        ref_name="ref",
        prof_name="prof",
        variant=None,
    )

    html = str(node)
    assert node is not None
    assert "Heatmap: CONFUSION_MATRIX_CELLS" in html
    assert "<svg" in html
    assert "A" in html
