# scrutiny-viz/tests/viz/test_chart.py
from __future__ import annotations

from report.viz.chart import render_bar_pair_block, render_chart_table_block
from report.viz import registry as viz_registry


def _section():
    return {
        "chart_rows": [
            {
                "key": "ALG_RSA",
                "ref_avg": 10.0,
                "test_avg": 12.0,
                "delta_ms": 2.0,
                "delta_pct": 20.0,
                "status": "mismatch",
                "note": "profile slower",
            },
            {
                "key": "ALG_EC",
                "ref_avg": 5.0,
                "test_avg": 5.0,
                "delta_ms": 0.0,
                "delta_pct": 0.0,
                "status": "match",
                "note": "",
            },
        ]
    }


def test_chart_plugin_is_registered():
    plugin = viz_registry.get_plugin("chart")
    assert plugin is not None
    assert plugin.spec.name == "chart"


def test_render_bar_pair_block_contains_svg_labels_and_values():
    html = str(render_bar_pair_block("PERF", _section(), 0))

    assert "<svg" in html
    assert "ALG_RSA" in html
    assert "ALG_EC" in html
    assert "10" in html
    assert "12" in html
    assert "reference" in html
    assert "profile" in html


def test_render_chart_table_block_contains_headers_and_status():
    html = str(render_chart_table_block("PERF", _section(), 0))

    assert "<table" in html
    assert "Key" in html
    assert "Ref Avg" in html
    assert "Profile Avg" in html
    assert "Δ ms" in html
    assert "Δ %" in html
    assert "Status" in html
    assert "ALG_RSA" in html
    assert "mismatch" in html
    assert "profile slower" in html