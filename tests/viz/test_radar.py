# scrutiny-viz/tests/viz/test_radar.py
from __future__ import annotations

from report.viz.radar import render_radar_block
from report.viz import registry as viz_registry


def _section():
    return {
        "radar_rows": [
            {"key": "ALG_RSA", "ref_raw": 10.0, "test_raw": 12.0, "ref_score": 0.83, "test_score": 1.0},
            {"key": "ALG_EC", "ref_raw": 5.0, "test_raw": 5.0, "ref_score": 1.0, "test_score": 1.0},
            {"key": "ALG_AES", "ref_raw": 2.0, "test_raw": 3.0, "ref_score": 0.67, "test_score": 1.0},
        ]
    }


def test_radar_plugin_is_registered():
    plugin = viz_registry.get_plugin("radar")
    assert plugin is not None
    assert plugin.spec.name == "radar"


def test_render_radar_block_contains_svg_labels_and_legend():
    html = str(render_radar_block("PERF", _section(), 0))

    assert "<svg" in html
    assert "ALG_RSA" in html
    assert "ALG_EC" in html
    assert "ALG_AES" in html
    assert "reference" in html
    assert "profile" in html


def test_render_radar_block_returns_empty_div_for_too_few_rows():
    section = {
        "radar_rows": [
            {"key": "ALG_RSA", "ref_score": 0.8, "test_score": 1.0},
            {"key": "ALG_EC", "ref_score": 1.0, "test_score": 1.0},
        ]
    }

    html = str(render_radar_block("PERF", section, 0))
    assert html == "<div></div>"