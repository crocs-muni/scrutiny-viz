# scrutiny-viz/report/viz/heatmap.py
from __future__ import annotations

import html
from typing import Any, Dict, Optional

from dominate import tags
from dominate.util import raw

from .contracts import VizPlugin, VizSpec
from .utility import to_float, to_int


_ROW_FIELDS = ("row_index", "row", "y")
_COL_FIELDS = ("col_index", "col", "x")
_VALUE_FIELDS = ("value", "share_pct", "score", "weight")
_ROW_LABEL_FIELDS = ("row_label",)
_COL_LABEL_FIELDS = ("col_label",)


def _is_percent_scale(values: list[float], forced_mode: Optional[str]) -> bool:
    if forced_mode == "percent":
        return True
    if forced_mode == "raw":
        return False
    if not values:
        return False
    return max(abs(v) for v in values) <= 1.000001


def _fmt_value(value: Optional[float], *, percent_mode: bool) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%" if percent_mode else f"{value:.6g}"


def _fmt_delta(value: Optional[float], *, percent_mode: bool) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:+.2f} pp" if percent_mode else f"{value:+.6g}"


def _color_single(value: float, vmax: float) -> str:
    if vmax <= 0:
        return "#f3f4f6"
    t = max(0.0, min(1.0, value / vmax))
    r = int(245 - (t * 130))
    g = int(247 - (t * 150))
    b = int(250 - (t * 10))
    return f"rgb({r},{g},{b})"


def _color_delta(value: float, vmax: float) -> str:
    if vmax <= 0:
        return "#f3f4f6"

    t = max(-1.0, min(1.0, value / vmax))
    if t >= 0:
        g = int(245 - (t * 155))
        b = int(245 - (t * 155))
        return f"rgb(245,{g},{b})"

    t = abs(t)
    r = int(245 - (t * 155))
    g = int(245 - (t * 155))
    return f"rgb({r},{g},245)"


def _safe_dom_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(value or ""))


def _parse_variant(variant: Optional[str]) -> dict[str, bool]:
    raw_variant = (variant or "").strip().lower()
    tokens = {token.strip() for token in raw_variant.replace(",", "+").split("+") if token.strip()}
    return {
        "delta_only": "delta" in tokens and "tabs" not in tokens,
        "force_percent": "percent" in tokens or "probability" in tokens,
        "force_raw": "raw" in tokens,
    }


def _build_cells(section: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    cells: Dict[str, Dict[str, Any]] = {}

    for record in section.get("matches", []) or []:
        key = str(record.get("key") or "")
        field = str(record.get("field") or "")
        value = record.get("value")
        if not key or not field:
            continue

        cell = cells.setdefault(key, {"ref_value": None, "test_value": None})

        if field in _ROW_FIELDS:
            cell["row_index"] = to_int(value)
        elif field in _COL_FIELDS:
            cell["col_index"] = to_int(value)
        elif field in _VALUE_FIELDS:
            numeric = to_float(value)
            cell["ref_value"] = numeric
            cell["test_value"] = numeric
        elif field in _ROW_LABEL_FIELDS:
            cell["row_label"] = "" if value is None else str(value)
        elif field in _COL_LABEL_FIELDS:
            cell["col_label"] = "" if value is None else str(value)

    for record in section.get("diffs", []) or []:
        field = str(record.get("field") or "")
        if field == "__presence__":
            continue

        key = str(record.get("key") or "")
        if not key or not field:
            continue

        cell = cells.setdefault(key, {"ref_value": None, "test_value": None})
        ref_value = record.get("ref")
        test_value = record.get("test")

        if field in _ROW_FIELDS:
            cell["row_index"] = to_int(ref_value if ref_value is not None else test_value)
        elif field in _COL_FIELDS:
            cell["col_index"] = to_int(ref_value if ref_value is not None else test_value)
        elif field in _VALUE_FIELDS:
            cell["ref_value"] = to_float(ref_value)
            cell["test_value"] = to_float(test_value)
        elif field in _ROW_LABEL_FIELDS:
            value = ref_value if ref_value is not None else test_value
            cell["row_label"] = "" if value is None else str(value)
        elif field in _COL_LABEL_FIELDS:
            value = ref_value if ref_value is not None else test_value
            cell["col_label"] = "" if value is None else str(value)

    return cells


def _svg_heatmap(
    *,
    title: str,
    cells: Dict[tuple[int, int], float],
    rows: int,
    cols: int,
    row_labels: Dict[int, str],
    col_labels: Dict[int, str],
    mode: str,
    percent_mode: bool,
) -> str:
    cell_size = 22
    pad_left = 90
    pad_top = 84
    pad_right = 18
    pad_bottom = 22

    width = pad_left + (cols * cell_size) + pad_right
    height = pad_top + (rows * cell_size) + pad_bottom

    values = list(cells.values())
    vmax = max((abs(v) for v in values), default=0.0) if mode == "delta" else max(values, default=0.0)

    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" class="heatmap-svg">',
        f'<text x="{pad_left}" y="18" class="heatmap-svg-title">{html.escape(title)}</text>',
    ]

    for row in range(rows):
        label = html.escape(row_labels.get(row, str(row)))
        y = pad_top + (row * cell_size) + (cell_size / 2) + 4
        parts.append(
            f'<text x="{pad_left - 8}" y="{y}" text-anchor="end" class="heatmap-axis-label">{label}</text>'
        )

    for col in range(cols):
        label = html.escape(col_labels.get(col, str(col)))
        x = pad_left + (col * cell_size) + (cell_size / 2)
        y = pad_top - 10
        parts.append(
            f'<text x="{x}" y="{y}" text-anchor="middle" transform="rotate(-45 {x},{y})" class="heatmap-axis-label">{label}</text>'
        )

    for row in range(rows):
        for col in range(cols):
            value = cells.get((row, col))
            x = pad_left + (col * cell_size)
            y = pad_top + (row * cell_size)

            if value is None:
                fill = "#f8f8f8"
                tooltip = f"row {row}, col {col}: missing"
            else:
                fill = _color_delta(value, vmax) if mode == "delta" else _color_single(value, vmax)
                tooltip = (
                    f"row {row}, col {col}: {_fmt_delta(value, percent_mode=percent_mode)}"
                    if mode == "delta"
                    else f"row {row}, col {col}: {_fmt_value(value, percent_mode=percent_mode)}"
                )

            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" '
                f'fill="{fill}" stroke="#d9d9d9" class="heatmap-cell">'
                f'<title>{html.escape(tooltip)}</title>'
                f'</rect>'
            )

    parts.append("</svg>")
    return "".join(parts)


def _legend_block(*, delta: bool, percent_mode: bool) -> tags.div:
    box = tags.div(_class="heatmap-legend")
    with box:
        tags.div("Legend", _class="heatmap-legend-title")
        if delta:
            tags.div(
                "Blue = lower than reference, white = no change, red = higher than reference",
                _class="heatmap-legend-line",
            )
            tags.div(
                "Values in tooltip are shown as percentage-point deltas"
                if percent_mode
                else "Values in tooltip are shown as raw deltas",
                _class="heatmap-legend-line",
            )
        else:
            tags.div("Lighter = lower value, darker = higher value", _class="heatmap-legend-line")
            tags.div(
                "Values in tooltip are shown as percentages"
                if percent_mode
                else "Values in tooltip are shown as raw numeric values",
                _class="heatmap-legend-line",
            )
    return box


def _stats_box(
    *,
    rows: int,
    cols: int,
    ref_cells: Dict[tuple[int, int], float],
    test_cells: Dict[tuple[int, int], float],
    delta_cells: Dict[tuple[int, int], float],
    percent_mode: bool,
) -> tags.div:
    ref_values = list(ref_cells.values())
    test_values = list(test_cells.values())
    delta_values = list(delta_cells.values())

    ref_max = max(ref_values, default=0.0)
    test_max = max(test_values, default=0.0)
    delta_max = max((abs(v) for v in delta_values), default=0.0)

    box = tags.div(_class="heatmap-stats")
    with box:
        for label, value in [
            ("Matrix", f"{rows} × {cols}"),
            ("Ref max", _fmt_value(ref_max, percent_mode=percent_mode)),
            ("Profile max", _fmt_value(test_max, percent_mode=percent_mode)),
            ("Δ max", _fmt_delta(delta_max, percent_mode=percent_mode)),
        ]:
            chip = tags.div(_class="heatmap-stat-chip")
            chip.add(tags.span(label, _class="heatmap-stat-label"))
            chip.add(tags.span(value, _class="heatmap-stat-value"))
            box.add(chip)
    return box


def _top_changes(
    delta_cells: Dict[tuple[int, int], float],
    row_labels: Dict[int, str],
    col_labels: Dict[int, str],
    *,
    percent_mode: bool,
) -> tags.div:
    ranked = [(row, col, value) for (row, col), value in delta_cells.items() if abs(value) > 1e-12]
    ranked.sort(key=lambda item: abs(item[2]), reverse=True)

    top_up = [item for item in ranked if item[2] > 0][:5]
    top_down = [item for item in ranked if item[2] < 0][:5]

    box = tags.div(_class="heatmap-change-summary")
    with box:
        tags.div("Top changed cells", _class="heatmap-change-title")

        columns = tags.div(_class="heatmap-change-columns")

        up_col = tags.div(_class="heatmap-change-col")
        up_col.add(tags.div("Increased", _class="heatmap-change-subtitle"))
        if top_up:
            ul = tags.ul(_class="heatmap-change-list")
            for row, col, value in top_up:
                ul.add(
                    tags.li(
                        f"{row_labels.get(row, str(row))} → {col_labels.get(col, str(col))}: "
                        f"{_fmt_delta(value, percent_mode=percent_mode)}"
                    )
                )
            up_col.add(ul)
        else:
            up_col.add(tags.p("No increases."))

        down_col = tags.div(_class="heatmap-change-col")
        down_col.add(tags.div("Decreased", _class="heatmap-change-subtitle"))
        if top_down:
            ul = tags.ul(_class="heatmap-change-list")
            for row, col, value in top_down:
                ul.add(
                    tags.li(
                        f"{row_labels.get(row, str(row))} → {col_labels.get(col, str(col))}: "
                        f"{_fmt_delta(value, percent_mode=percent_mode)}"
                    )
                )
            down_col.add(ul)
        else:
            down_col.add(tags.p("No decreases."))

        columns.add(up_col)
        columns.add(down_col)
        box.add(columns)

    return box


def render_heatmap_block(
    section_name: str,
    section: Dict[str, Any],
    idx: int,
    *,
    ref_name: str,
    prof_name: str,
    variant: Optional[str] = None,
):
    options = _parse_variant(variant)
    cell_map = _build_cells(section)
    if not cell_map:
        return tags.div()

    rows = 0
    cols = 0
    row_labels: Dict[int, str] = {}
    col_labels: Dict[int, str] = {}
    ref_cells: Dict[tuple[int, int], float] = {}
    test_cells: Dict[tuple[int, int], float] = {}
    delta_cells: Dict[tuple[int, int], float] = {}

    for cell in cell_map.values():
        row_index = cell.get("row_index")
        col_index = cell.get("col_index")
        if row_index is None or col_index is None:
            continue

        row = int(row_index)
        col = int(col_index)
        rows = max(rows, row + 1)
        cols = max(cols, col + 1)

        if "row_label" in cell:
            row_labels[row] = str(cell["row_label"])
        if "col_label" in cell:
            col_labels[col] = str(cell["col_label"])

        ref_value = cell.get("ref_value")
        test_value = cell.get("test_value")
        if ref_value is not None:
            ref_cells[(row, col)] = float(ref_value)
        if test_value is not None:
            test_cells[(row, col)] = float(test_value)
        if ref_value is not None and test_value is not None:
            delta_cells[(row, col)] = float(test_value) - float(ref_value)

    forced_mode = "percent" if options["force_percent"] else ("raw" if options["force_raw"] else None)
    percent_mode = _is_percent_scale(
        list(ref_cells.values()) + list(test_cells.values()) + list(delta_cells.values()),
        forced_mode,
    )
    dom_base = _safe_dom_id(f"heatmap_{idx}_{section_name}")

    container = tags.div(_class="heatmap-block")
    with container:
        tags.h4(f"Heatmap: {section_name}")
        tags.p(
            f"Rows represent source/true matrix indices and columns represent predicted matrix indices. "
            f"Delta is computed as {prof_name} minus {ref_name}.",
            _class="heatmap-note",
        )

        container.add(
            _stats_box(
                rows=rows,
                cols=cols,
                ref_cells=ref_cells,
                test_cells=test_cells,
                delta_cells=delta_cells,
                percent_mode=percent_mode,
            )
        )

        if options["delta_only"]:
            container.add(_legend_block(delta=True, percent_mode=percent_mode))
            pane = tags.div(_class="heatmap-pane")
            pane.add(
                raw(
                    _svg_heatmap(
                        title=f"Δ {prof_name} - {ref_name}",
                        cells=delta_cells,
                        rows=rows,
                        cols=cols,
                        row_labels=row_labels,
                        col_labels=col_labels,
                        mode="delta",
                        percent_mode=percent_mode,
                    )
                )
            )
            container.add(pane)
        else:
            tabs = tags.div(_class="heatmap-tabs")
            tabs.add(
                tags.button(
                    "Delta",
                    _class="heatmap-tab active",
                    type="button",
                    onclick=f"heatmapShow('{dom_base}', 'delta', this); return false;",
                )
            )
            tabs.add(
                tags.button(
                    ref_name,
                    _class="heatmap-tab",
                    type="button",
                    onclick=f"heatmapShow('{dom_base}', 'ref', this); return false;",
                )
            )
            tabs.add(
                tags.button(
                    prof_name,
                    _class="heatmap-tab",
                    type="button",
                    onclick=f"heatmapShow('{dom_base}', 'profile', this); return false;",
                )
            )
            container.add(tabs)

            legends = tags.div(_class="heatmap-legends")

            delta_legend = _legend_block(delta=True, percent_mode=percent_mode)
            delta_legend["id"] = f"{dom_base}_legend_delta"
            legends.add(delta_legend)

            ref_legend = _legend_block(delta=False, percent_mode=percent_mode)
            ref_legend["id"] = f"{dom_base}_legend_ref"
            ref_legend["style"] = "display:none;"
            legends.add(ref_legend)

            profile_legend = _legend_block(delta=False, percent_mode=percent_mode)
            profile_legend["id"] = f"{dom_base}_legend_profile"
            profile_legend["style"] = "display:none;"
            legends.add(profile_legend)

            container.add(legends)

            delta_pane = tags.div(_class="heatmap-pane")
            delta_pane["id"] = f"{dom_base}_pane_delta"
            delta_pane.add(
                raw(
                    _svg_heatmap(
                        title=f"Δ {prof_name} - {ref_name}",
                        cells=delta_cells,
                        rows=rows,
                        cols=cols,
                        row_labels=row_labels,
                        col_labels=col_labels,
                        mode="delta",
                        percent_mode=percent_mode,
                    )
                )
            )
            container.add(delta_pane)

            ref_pane = tags.div(_class="heatmap-pane")
            ref_pane["id"] = f"{dom_base}_pane_ref"
            ref_pane["style"] = "display:none;"
            ref_pane.add(
                raw(
                    _svg_heatmap(
                        title=ref_name,
                        cells=ref_cells,
                        rows=rows,
                        cols=cols,
                        row_labels=row_labels,
                        col_labels=col_labels,
                        mode="single",
                        percent_mode=percent_mode,
                    )
                )
            )
            container.add(ref_pane)

            profile_pane = tags.div(_class="heatmap-pane")
            profile_pane["id"] = f"{dom_base}_pane_profile"
            profile_pane["style"] = "display:none;"
            profile_pane.add(
                raw(
                    _svg_heatmap(
                        title=prof_name,
                        cells=test_cells,
                        rows=rows,
                        cols=cols,
                        row_labels=row_labels,
                        col_labels=col_labels,
                        mode="single",
                        percent_mode=percent_mode,
                    )
                )
            )
            container.add(profile_pane)

        container.add(
            _top_changes(
                delta_cells,
                row_labels,
                col_labels,
                percent_mode=percent_mode,
            )
        )

    return container


class HeatmapVizPlugin(VizPlugin):
    spec = VizSpec(
        name="heatmap",
        slot="section",
        aliases=("matrix",),
        description="Generic heatmap visualization for matrix-like section data.",
    )

    def render(self, **kwargs: Any) -> Any:
        return render_heatmap_block(
            kwargs["section_name"],
            kwargs["section"],
            kwargs["idx"],
            ref_name=kwargs["ref_name"],
            prof_name=kwargs["prof_name"],
            variant=kwargs.get("variant"),
        )


PLUGINS = [HeatmapVizPlugin()]