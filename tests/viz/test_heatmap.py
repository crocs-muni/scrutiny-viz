# scrutiny-viz/tests/viz/test_heatmap.py
from __future__ import annotations

from report.viz import registry as viz_registry


def test_heatmap_plugin_is_registered():
    plugin = viz_registry.get_plugin("heatmap")
    assert plugin is not None
    assert plugin.spec.name == "heatmap"


def test_heatmap_plugin_render_smoke():
    plugin = viz_registry.get_plugin("heatmap")

    rows = [
        {"cell_id": "0:0", "row_index": 0, "col_index": 0, "row_label": "g0", "col_label": "g0", "value": 90.0, "is_diagonal": True},
        {"cell_id": "0:1", "row_index": 0, "col_index": 1, "row_label": "g0", "col_label": "g1", "value": 10.0, "is_diagonal": False},
        {"cell_id": "1:0", "row_index": 1, "col_index": 0, "row_label": "g1", "col_label": "g0", "value": 5.0, "is_diagonal": False},
        {"cell_id": "1:1", "row_index": 1, "col_index": 1, "row_label": "g1", "col_label": "g1", "value": 95.0, "is_diagonal": True},
    ]

    section = {
        "heatmap_rows": rows,
        "source_rows": {"reference": rows, "tested": rows, "profile": rows},
        "artifacts": {"heatmap_rows": rows},
        "report": {"types": [{"type": "heatmap"}]},
    }

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


def test_heatmap_plugin_accepts_matrix_like_input():
    plugin = viz_registry.get_plugin("heatmap")

    rows = [
        {"cell_id": "0:0", "row_index": 0, "col_index": 0, "row_label": "A", "col_label": "A", "value": 100.0, "is_diagonal": True},
    ]

    section = {
        "heatmap_rows": rows,
        "artifacts": {"heatmap_rows": rows},
    }

    node = plugin.render(
        section_name="CONFUSION_MATRIX_CELLS",
        section=section,
        idx=0,
        ref_name="ref",
        prof_name="prof",
        variant=None,
    )

    assert node is not None