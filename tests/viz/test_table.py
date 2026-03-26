# scrutiny-viz/tests/viz/test_table.py
from __future__ import annotations

from report.viz.table import render_table_block, render_cplc_table


def test_render_table_block_contains_headers_and_rows():
    node = render_table_block(headers=["Name", "Value"], rows=[["A", "x"], ["B", "y"]])
    html = str(node)
    assert "<table" in html and "Name" in html and "Value" in html and "A" in html and "x" in html


def test_render_cplc_table_highlights_mismatch():
    section = {"source_rows": {"reference": [{"field": "ICFabricator", "value": "6155"}], "tested": [{"field": "ICFabricator", "value": "9999"}]}}
    html = str(render_cplc_table(section, "ref", "prof"))
    assert "CPLC Field" in html and "ICFabricator" in html and "6155" in html and "9999" in html and "font-weight:700" in html
