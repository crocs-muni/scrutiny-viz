# scrutiny-viz/report/viz/radar.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import html
import math
from dominate import tags
from dominate.util import raw

from .contracts import VizPlugin, VizSpec
from .utility import to_float


def _point(cx: float, cy: float, radius: float, angle_rad: float) -> tuple[float, float]:
    return (cx + radius * math.cos(angle_rad), cy + radius * math.sin(angle_rad))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _has_raw_values(rows: List[Dict[str, Any]]) -> bool:
    return any("ref_raw" in row and "test_raw" in row for row in rows)


def _safe_float(value: Any, default: float = 0.0) -> float:
    converted = to_float(value)
    return default if converted is None else converted


def _axis_normalized_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        new_row = dict(row)
        if "ref_raw" in new_row and "test_raw" in new_row:
            ref_raw = _safe_float(new_row.get("ref_raw"))
            test_raw = _safe_float(new_row.get("test_raw"))
            denom = max(ref_raw, test_raw, 1e-12)
            new_row["ref_score"] = _clamp01(ref_raw / denom)
            new_row["test_score"] = _clamp01(test_raw / denom)
        else:
            new_row["ref_score"] = _clamp01(_safe_float(new_row.get("ref_score")))
            new_row["test_score"] = _clamp01(_safe_float(new_row.get("test_score")))
        out.append(new_row)
    return out


def _log_scaled_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    global_max = 0.0
    for row in rows:
        if "ref_raw" in row:
            global_max = max(global_max, _safe_float(row.get("ref_raw")))
        if "test_raw" in row:
            global_max = max(global_max, _safe_float(row.get("test_raw")))

    denom = math.log1p(max(global_max, 1e-12))
    out: List[Dict[str, Any]] = []

    for row in rows:
        new_row = dict(row)
        if "ref_raw" in new_row and "test_raw" in new_row and denom > 0.0:
            ref_raw = max(_safe_float(new_row.get("ref_raw")), 0.0)
            test_raw = max(_safe_float(new_row.get("test_raw")), 0.0)
            new_row["ref_score"] = _clamp01(math.log1p(ref_raw) / denom)
            new_row["test_score"] = _clamp01(math.log1p(test_raw) / denom)
        else:
            new_row["ref_score"] = _clamp01(_safe_float(new_row.get("ref_score")))
            new_row["test_score"] = _clamp01(_safe_float(new_row.get("test_score")))
        out.append(new_row)

    return out


def _short_label(text: str, *, max_chars: int = 16) -> str:
    text = str(text or "")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _build_svg(rows: List[Dict[str, Any]], *, show_every: int = 1, title_suffix: str = "") -> str:
    width = 820
    height = 620
    margin = 56
    cx = width / 2
    cy = (height - 50) / 2
    radius = min(width, height - 50) / 2 - margin
    axis_count = max(len(rows), 3)

    def angle(index: int) -> float:
        return -math.pi / 2 + 2 * math.pi * (index / axis_count)

    def polygon_path(series_key: str) -> str:
        points = []
        for index, row in enumerate(rows):
            score = _clamp01(_safe_float(row.get(series_key)))
            x, y = _point(cx, cy, radius * score, angle(index))
            points.append((x, y))
        if not points:
            return ""
        head = f"M {points[0][0]:.2f} {points[0][1]:.2f}"
        tail = " ".join(f"L {x:.2f} {y:.2f}" for x, y in points[1:])
        return f"{head} {tail} Z"

    parts: List[str] = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" class="radar">']

    for fraction in (0.2, 0.4, 0.6, 0.8, 1.0):
        points = []
        for index in range(axis_count):
            x, y = _point(cx, cy, radius * fraction, angle(index))
            points.append(f"{x:.2f},{y:.2f}")
        parts.append(f'<polygon points="{" ".join(points)}" class="radar-grid"></polygon>')

    for index, row in enumerate(rows):
        axis_x, axis_y = _point(cx, cy, radius, angle(index))
        parts.append(f'<line x1="{cx:.2f}" y1="{cy:.2f}" x2="{axis_x:.2f}" y2="{axis_y:.2f}" class="radar-axis"></line>')

        if index % max(1, show_every) == 0:
            full_label = str(row.get("key", "") or "")
            short_label = _short_label(full_label, max_chars=18)
            label_x, label_y = _point(cx, cy, radius + 18, angle(index))
            axis_angle = angle(index)
            anchor = "middle"
            if -math.pi / 2 < axis_angle < math.pi / 2:
                anchor = "start"
            elif axis_angle > math.pi / 2 or axis_angle < -math.pi / 2:
                anchor = "end"
            parts.append(
                f'<text x="{label_x:.2f}" y="{label_y:.2f}" class="radar-label" text-anchor="{anchor}">'
                f'<title>{html.escape(full_label)}</title>{html.escape(short_label)}</text>'
            )

    ref_path = polygon_path("ref_score")
    test_path = polygon_path("test_score")
    if ref_path:
        parts.append(f'<path d="{ref_path}" class="radar-ref"></path>')
    if test_path:
        parts.append(f'<path d="{test_path}" class="radar-test"></path>')

    for index, row in enumerate(rows):
        key = row.get("key", "")
        ref_raw = row.get("ref_raw")
        test_raw = row.get("test_raw")
        for series_key, css_class in (("ref_score", "radar-ref"), ("test_score", "radar-test")):
            score = _clamp01(_safe_float(row.get(series_key)))
            x, y = _point(cx, cy, radius * score, angle(index))
            series_name = series_key.split("_")[0]
            raw_value = ref_raw if series_name == "ref" else test_raw
            if raw_value is not None:
                tooltip = f"{key}: {series_name} raw={raw_value} (score={score:.2f})"
            else:
                tooltip = f"{key}: {series_name} score={score:.2f}"
            parts.append(
                f'<g><title>{html.escape(str(tooltip))}</title>'
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" class="{css_class}"></circle></g>'
            )

    parts.append(f'<rect x="{margin}" y="{height - margin + 12}" width="14" height="8" class="radar-ref"></rect>')
    parts.append(f'<text x="{margin + 20}" y="{height - margin + 20}" class="radar-legend">reference{title_suffix}</text>')
    parts.append(f'<rect x="{margin + 120}" y="{height - margin + 12}" width="14" height="8" class="radar-test"></rect>')
    parts.append(f'<text x="{margin + 140}" y="{height - margin + 20}" class="radar-legend">profile{title_suffix}</text>')
    parts.append('</svg>')
    return "".join(parts)


def render_radar_block(section_name: str, section: Dict[str, Any], idx: int):
    rows: List[Dict[str, Any]] = section.get("radar_rows", []) or []
    if len(rows) < 3:
        return tags.div()

    use_raw = _has_raw_values(rows)
    normalized_rows = _axis_normalized_rows(rows)
    log_rows = _log_scaled_rows(rows) if use_raw else []

    max_visible = 24
    container = tags.div(_class="radar-container", id=f"radar-{idx}")

    if use_raw and len(log_rows) >= 3:
        controls = tags.div(_class="radar-controls")
        controls.add(
            tags.button(
                "Scale: normal",
                onclick=f"toggleRadarScale('radar-{idx}')",
                **{"data-radar-toggle": "scale"},
            )
        )
        container.add(controls)

    if len(normalized_rows) <= max_visible:
        normal_view = tags.div(_class="radar-view", **{"data-scale": "normal"})
        normal_view.add(raw(_build_svg(normalized_rows, show_every=1 if len(normalized_rows) <= 24 else 2)))
        container.add(normal_view)

        if use_raw and len(log_rows) >= 3:
            log_view = tags.div(_class="radar-view", **{"data-scale": "log", "hidden": ""})
            log_view.add(raw(_build_svg(log_rows, show_every=1 if len(log_rows) <= 24 else 2, title_suffix=" (log)")))
            container.add(log_view)
        return container

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for row in normalized_rows:
        diff = abs(_safe_float(row.get("test_score")) - _safe_float(row.get("ref_score")))
        scored.append((diff, row))
    scored.sort(key=lambda item: item[0], reverse=True)

    top_rows = [row for _, row in scored[:max_visible]]

    normal_pane = tags.div(_class="radar-view", **{"data-scale": "normal"})
    normal_pane.add(raw(_build_svg(top_rows, show_every=1)))

    details = tags.details()
    details.add(tags.summary(f"Show all {len(normalized_rows)} items"))
    details.add(tags.div(raw(_build_svg(normalized_rows, show_every=max(1, len(normalized_rows) // 24)))))
    normal_pane.add(details)
    container.add(normal_pane)

    if use_raw and len(log_rows) >= 3:
        top_keys = {str(row.get("key")) for row in top_rows}
        top_log_rows = [row for row in log_rows if str(row.get("key")) in top_keys]

        log_pane = tags.div(_class="radar-view", **{"data-scale": "log", "hidden": ""})
        log_pane.add(raw(_build_svg(top_log_rows, show_every=1, title_suffix=" (log)")))

        log_details = tags.details()
        log_details.add(tags.summary(f"Show all {len(log_rows)} items (log)"))
        log_details.add(tags.div(raw(_build_svg(log_rows, show_every=max(1, len(log_rows) // 24), title_suffix=" (log)"))))
        log_pane.add(log_details)
        container.add(log_pane)

    return container


def render_radar_variant(*, section_name: str, section: Dict[str, Any], idx: int, variant: str | None = None) -> Any:
    return render_radar_block(section_name, section, idx)


class RadarVizPlugin(VizPlugin):
    spec = VizSpec(
        name="radar",
        slot="bottom",
        aliases=(),
        description="Radar visualization for section radar rows.",
    )

    def render(self, **kwargs: Any) -> Any:
        return render_radar_variant(
            section_name=kwargs["section_name"],
            section=kwargs["section"],
            idx=kwargs["idx"],
            variant=kwargs.get("variant"),
        )


PLUGINS = [RadarVizPlugin()]
