# scrutiny-viz/report/viz/heatmap.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import html

from dominate import tags
from dominate.util import raw

from .contracts import VizPlugin, VizSpec


_ROW_FIELDS = ("row_index", "row", "y")
_COL_FIELDS = ("col_index", "col", "x")
_VALUE_FIELDS = ("value", "share_pct", "score", "weight")
_ROW_LABEL_FIELDS = ("row_label",)
_COL_LABEL_FIELDS = ("col_label",)


def _to_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def _to_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _is_percent_scale(values: list[float], forced_mode: Optional[str]) -> bool:
    if forced_mode == "percent":
        return True
    if forced_mode == "raw":
        return False
    if not values:
        return False
    vmax = max(abs(v) for v in values)
    return vmax <= 1.000001


def _fmt_value(v: Optional[float], *, percent_mode: bool) -> str:
    if v is None:
        return "n/a"
    if percent_mode:
        return f"{v * 100:.2f}%"
    return f"{v:.6g}"


def _fmt_delta(v: Optional[float], *, percent_mode: bool) -> str:
    if v is None:
        return "n/a"
    if percent_mode:
        return f"{v * 100:+.2f} pp"
    return f"{v:+.6g}"


def _color_single(v: float, vmax: float) -> str:
    if vmax <= 0:
        return "#f3f4f6"
    t = max(0.0, min(1.0, v / vmax))
    # light -> dark blue
    r = int(245 - (t * 130))
    g = int(247 - (t * 150))
    b = int(250 - (t * 10))
    return f"rgb({r},{g},{b})"


def _color_delta(v: float, vmax: float) -> str:
    if vmax <= 0:
        return "#f3f4f6"
    t = max(-1.0, min(1.0, v / vmax))
    if t >= 0:
        # white -> red
        g = int(245 - (t * 155))
        b = int(245 - (t * 155))
        return f"rgb(245,{g},{b})"
    else:
        t = abs(t)
        # blue -> white
        r = int(245 - (t * 155))
        g = int(245 - (t * 155))
        return f"rgb({r},{g},245)"


def _safe_dom_id(s: str) -> str:
    out = []
    for ch in s:
        if ch.isalnum() or ch in ("-", "_"):
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)


def _parse_variant(variant: Optional[str]) -> dict[str, bool | str]:
    raw_v = (variant or "").strip().lower()
    tokens = {t.strip() for t in raw_v.replace(",", "+").split("+") if t.strip()}

    return {
        "delta_only": "delta" in tokens and "tabs" not in tokens,
        "force_percent": "percent" in tokens or "probability" in tokens,
        "force_raw": "raw" in tokens,
    }


def _build_cells(section: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    cells: Dict[str, Dict[str, Any]] = {}

    for rec in section.get("matches", []) or []:
        key = str(rec.get("key"))
        field = str(rec.get("field"))
        value = rec.get("value")
        if not key or not field:
            continue

        cell = cells.setdefault(key, {"ref_value": None, "test_value": None})

        if field in _ROW_FIELDS:
            cell["row_index"] = _to_int(value)
        elif field in _COL_FIELDS:
            cell["col_index"] = _to_int(value)
        elif field in _VALUE_FIELDS:
            fv = _to_float(value)
            cell["ref_value"] = fv
            cell["test_value"] = fv
        elif field in _ROW_LABEL_FIELDS:
            cell["row_label"] = "" if value is None else str(value)
        elif field in _COL_LABEL_FIELDS:
            cell["col_label"] = "" if value is None else str(value)

    for rec in section.get("diffs", []) or []:
        if rec.get("field") == "__presence__":
            continue

        key = str(rec.get("key"))
        field = str(rec.get("field"))
        if not key or not field:
            continue

        cell = cells.setdefault(key, {"ref_value": None, "test_value": None})

        rv = rec.get("ref")
        tv = rec.get("test")

        if field in _ROW_FIELDS:
            cell["row_index"] = _to_int(rv if rv is not None else tv)
        elif field in _COL_FIELDS:
            cell["col_index"] = _to_int(rv if rv is not None else tv)
        elif field in _VALUE_FIELDS:
            cell["ref_value"] = _to_float(rv)
            cell["test_value"] = _to_float(tv)
        elif field in _ROW_LABEL_FIELDS:
            value = rv if rv is not None else tv
            cell["row_label"] = "" if value is None else str(value)
        elif field in _COL_LABEL_FIELDS:
            value = rv if rv is not None else tv
            cell["col_label"] = "" if value is None else str(value)

    return cells


def _svg_heatmap(
    *,
    title: str,
    cells: Dict[Tuple[int, int], float],
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

    values = [v for v in cells.values() if v is not None]
    vmax = max((abs(v) for v in values), default=0.0) if mode == "delta" else max(values, default=0.0)

    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" class="heatmap-svg">',
        f'<text x="{pad_left}" y="18" class="heatmap-svg-title">{html.escape(title)}</text>',
    ]

    # row labels
    for r in range(rows):
        label = html.escape(row_labels.get(r, str(r)))
        y = pad_top + (r * cell_size) + (cell_size / 2) + 4
        parts.append(
            f'<text x="{pad_left - 8}" y="{y}" text-anchor="end" class="heatmap-axis-label">{label}</text>'
        )

    # col labels
    for c in range(cols):
        label = html.escape(col_labels.get(c, str(c)))
        x = pad_left + (c * cell_size) + (cell_size / 2)
        y = pad_top - 10
        parts.append(
            f'<text x="{x}" y="{y}" text-anchor="middle" transform="rotate(-45 {x},{y})" class="heatmap-axis-label">{label}</text>'
        )

    for r in range(rows):
        for c in range(cols):
            v = cells.get((r, c))
            x = pad_left + (c * cell_size)
            y = pad_top + (r * cell_size)

            if v is None:
                fill = "#f8f8f8"
                tip = f"row {r}, col {c}: missing"
            else:
                fill = _color_delta(v, vmax) if mode == "delta" else _color_single(v, vmax)
                if mode == "delta":
                    tip = f"row {r}, col {c}: {_fmt_delta(v, percent_mode=percent_mode)}"
                else:
                    tip = f"row {r}, col {c}: {_fmt_value(v, percent_mode=percent_mode)}"

            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" fill="{fill}" stroke="#d9d9d9" class="heatmap-cell">'
                f'<title>{html.escape(tip)}</title>'
                f'</rect>'
            )

    parts.append("</svg>")
    return "".join(parts)


def _legend_block(*, delta: bool, percent_mode: bool) -> tags.div:
    box = tags.div(_class="heatmap-legend")
    with box:
        tags.div("Legend", _class="heatmap-legend-title")
        if delta:
            tags.div("Blue = lower than reference, white = no change, red = higher than reference", _class="heatmap-legend-line")
            tags.div("Values in tooltip are shown as percentage-point deltas" if percent_mode else "Values in tooltip are shown as raw deltas", _class="heatmap-legend-line")
        else:
            tags.div("Lighter = lower value, darker = higher value", _class="heatmap-legend-line")
            tags.div("Values in tooltip are shown as percentages" if percent_mode else "Values in tooltip are shown as raw numeric values", _class="heatmap-legend-line")
    return box


def _stats_box(*, rows: int, cols: int, ref_cells: Dict[Tuple[int, int], float], test_cells: Dict[Tuple[int, int], float], delta_cells: Dict[Tuple[int, int], float], percent_mode: bool) -> tags.div:
    ref_vals = list(ref_cells.values())
    test_vals = list(test_cells.values())
    delta_vals = list(delta_cells.values())

    ref_max = max(ref_vals, default=0.0)
    test_max = max(test_vals, default=0.0)
    delta_max = max((abs(v) for v in delta_vals), default=0.0)

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


def _top_changes(delta_cells: Dict[Tuple[int, int], float], row_labels: Dict[int, str], col_labels: Dict[int, str], *, percent_mode: bool) -> tags.div:
    items = []
    for (r, c), v in delta_cells.items():
        if abs(v) <= 1e-12:
            continue
        items.append((r, c, v))

    items.sort(key=lambda x: abs(x[2]), reverse=True)
    top_up = [x for x in items if x[2] > 0][:5]
    top_down = [x for x in items if x[2] < 0][:5]

    box = tags.div(_class="heatmap-change-summary")
    with box:
        tags.div("Top changed cells", _class="heatmap-change-title")

        cols_wrap = tags.div(_class="heatmap-change-columns")

        up_col = tags.div(_class="heatmap-change-col")
        up_col.add(tags.div("Increased", _class="heatmap-change-subtitle"))
        if top_up:
            ul = tags.ul(_class="heatmap-change-list")
            for r, c, v in top_up:
                rl = row_labels.get(r, str(r))
                cl = col_labels.get(c, str(c))
                ul.add(tags.li(f"{rl} → {cl}: {_fmt_delta(v, percent_mode=percent_mode)}"))
            up_col.add(ul)
        else:
            up_col.add(tags.p("No increases."))

        down_col = tags.div(_class="heatmap-change-col")
        down_col.add(tags.div("Decreased", _class="heatmap-change-subtitle"))
        if top_down:
            ul = tags.ul(_class="heatmap-change-list")
            for r, c, v in top_down:
                rl = row_labels.get(r, str(r))
                cl = col_labels.get(c, str(c))
                ul.add(tags.li(f"{rl} → {cl}: {_fmt_delta(v, percent_mode=percent_mode)}"))
            down_col.add(ul)
        else:
            down_col.add(tags.p("No decreases."))

        cols_wrap.add(up_col)
        cols_wrap.add(down_col)
        box.add(cols_wrap)

    return box


def render_heatmap_block(section_name: str, section: Dict[str, Any], idx: int, *, ref_name: str, prof_name: str, variant: Optional[str] = None):
    opts = _parse_variant(variant)
    cell_map = _build_cells(section)
    if not cell_map:
        return tags.div()

    rows = 0
    cols = 0
    row_labels: Dict[int, str] = {}
    col_labels: Dict[int, str] = {}

    ref_cells: Dict[Tuple[int, int], float] = {}
    test_cells: Dict[Tuple[int, int], float] = {}
    delta_cells: Dict[Tuple[int, int], float] = {}

    for cell in cell_map.values():
        r = cell.get("row_index")
        c = cell.get("col_index")
        if r is None or c is None:
            continue

        rows = max(rows, int(r) + 1)
        cols = max(cols, int(c) + 1)

        if "row_label" in cell:
            row_labels[int(r)] = str(cell["row_label"])
        if "col_label" in cell:
            col_labels[int(c)] = str(cell["col_label"])

        rv = cell.get("ref_value")
        tv = cell.get("test_value")

        if rv is not None:
            ref_cells[(int(r), int(c))] = float(rv)
        if tv is not None:
            test_cells[(int(r), int(c))] = float(tv)
        if rv is not None and tv is not None:
            delta_cells[(int(r), int(c))] = float(tv) - float(rv)

    ref_vals = list(ref_cells.values())
    test_vals = list(test_cells.values())
    delta_vals = list(delta_cells.values())

    forced_mode = "percent" if opts["force_percent"] else ("raw" if opts["force_raw"] else None)
    percent_mode = _is_percent_scale(ref_vals + test_vals + delta_vals, forced_mode)

    dom_base = _safe_dom_id(f"heatmap_{idx}_{section_name}")

    container = tags.div(_class="heatmap-block")
    with container:
        tags.h4(f"Heatmap: {section_name}")
        tags.p(
            f"Rows represent source/true matrix indices and columns represent predicted matrix indices. "
            f"Delta is computed as {prof_name} minus {ref_name}.",
            _class="heatmap-note",
        )

        container.add(_stats_box(
            rows=rows,
            cols=cols,
            ref_cells=ref_cells,
            test_cells=test_cells,
            delta_cells=delta_cells,
            percent_mode=percent_mode,
        ))

        if opts["delta_only"]:
            container.add(_legend_block(delta=True, percent_mode=percent_mode))
            pane = tags.div(_class="heatmap-pane")
            pane.add(raw(_svg_heatmap(
                title=f"Δ {prof_name} - {ref_name}",
                cells=delta_cells,
                rows=rows,
                cols=cols,
                row_labels=row_labels,
                col_labels=col_labels,
                mode="delta",
                percent_mode=percent_mode,
            )))
            container.add(pane)
        else:
            tabs = tags.div(_class="heatmap-tabs")
            tabs.add(tags.button("Delta", _class="heatmap-tab active", onclick=f"heatmapShow('{dom_base}', 'delta', this); return false;"))
            tabs.add(tags.button(ref_name, _class="heatmap-tab", onclick=f"heatmapShow('{dom_base}', 'ref', this); return false;"))
            tabs.add(tags.button(prof_name, _class="heatmap-tab", onclick=f"heatmapShow('{dom_base}', 'profile', this); return false;"))
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
            delta_pane.add(raw(_svg_heatmap(
                title=f"Δ {prof_name} - {ref_name}",
                cells=delta_cells,
                rows=rows,
                cols=cols,
                row_labels=row_labels,
                col_labels=col_labels,
                mode="delta",
                percent_mode=percent_mode,
            )))
            container.add(delta_pane)

            ref_pane = tags.div(_class="heatmap-pane")
            ref_pane["id"] = f"{dom_base}_pane_ref"
            ref_pane["style"] = "display:none;"
            ref_pane.add(raw(_svg_heatmap(
                title=ref_name,
                cells=ref_cells,
                rows=rows,
                cols=cols,
                row_labels=row_labels,
                col_labels=col_labels,
                mode="single",
                percent_mode=percent_mode,
            )))
            container.add(ref_pane)

            profile_pane = tags.div(_class="heatmap-pane")
            profile_pane["id"] = f"{dom_base}_pane_profile"
            profile_pane["style"] = "display:none;"
            profile_pane.add(raw(_svg_heatmap(
                title=prof_name,
                cells=test_cells,
                rows=rows,
                cols=cols,
                row_labels=row_labels,
                col_labels=col_labels,
                mode="single",
                percent_mode=percent_mode,
            )))
            container.add(profile_pane)

            script = f"""
(function() {{
  if (window.heatmapShow) return;
  window.heatmapShow = function(base, mode, btn) {{
    var panes = ['delta', 'ref', 'profile'];
    for (var i = 0; i < panes.length; i++) {{
      var p = panes[i];
      var pane = document.getElementById(base + '_pane_' + p);
      var legend = document.getElementById(base + '_legend_' + p);
      if (pane) pane.style.display = (p === mode ? 'block' : 'none');
      if (legend) legend.style.display = (p === mode ? 'block' : 'none');
    }}
    var group = btn.parentElement;
    var buttons = group.querySelectorAll('.heatmap-tab');
    for (var j = 0; j < buttons.length; j++) {{
      buttons[j].classList.remove('active');
    }}
    btn.classList.add('active');
  }};
}})();
"""
            container.add(tags.script(raw(script), type="text/javascript"))

        container.add(_top_changes(
            delta_cells,
            row_labels,
            col_labels,
            percent_mode=percent_mode,
        ))

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