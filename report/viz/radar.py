# scrutiny-viz/report/viz/radar.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from dominate import tags
from dominate.util import raw
import math
import html

from .contracts import VizPlugin, VizSpec


def _pt(cx, cy, r, ang_rad):
    return (cx + r * math.cos(ang_rad), cy + r * math.sin(ang_rad))


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _has_raw(rows: List[Dict[str, Any]]) -> bool:
    for r in rows:
        if "ref_raw" in r and "test_raw" in r:
            return True
    return False


def _scaled_rows_axis_normalized(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        rr = dict(r)
        if "ref_raw" in rr and "test_raw" in rr:
            ref_raw = _safe_float(rr.get("ref_raw"), 0.0)
            test_raw = _safe_float(rr.get("test_raw"), 0.0)
            denom = max(ref_raw, test_raw, 1e-12)
            rr["ref_score"] = _clamp01(ref_raw / denom)
            rr["test_score"] = _clamp01(test_raw / denom)
        else:
            rr["ref_score"] = _clamp01(_safe_float(rr.get("ref_score"), 0.0))
            rr["test_score"] = _clamp01(_safe_float(rr.get("test_score"), 0.0))
        out.append(rr)
    return out


def _scaled_rows_log(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    gmax = 0.0
    for r in rows:
        if "ref_raw" in r:
            gmax = max(gmax, _safe_float(r.get("ref_raw"), 0.0))
        if "test_raw" in r:
            gmax = max(gmax, _safe_float(r.get("test_raw"), 0.0))

    denom = math.log1p(max(gmax, 1e-12))
    out: List[Dict[str, Any]] = []
    for r in rows:
        rr = dict(r)
        if "ref_raw" in rr and "test_raw" in rr and denom > 0.0:
            ref_raw = max(_safe_float(rr.get("ref_raw"), 0.0), 0.0)
            test_raw = max(_safe_float(rr.get("test_raw"), 0.0), 0.0)
            rr["ref_score"] = _clamp01(math.log1p(ref_raw) / denom)
            rr["test_score"] = _clamp01(math.log1p(test_raw) / denom)
        else:
            rr["ref_score"] = _clamp01(_safe_float(rr.get("ref_score"), 0.0))
            rr["test_score"] = _clamp01(_safe_float(rr.get("test_score"), 0.0))
        out.append(rr)
    return out


def _short_label(s: str, *, max_chars: int = 16) -> str:
    s = str(s or "")
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"


def _build_svg(rows: List[Dict[str, Any]], *, show_every: int = 1, title_suffix: str = "") -> str:
    width = 820
    height = 620
    margin = 56
    cx = width / 2
    cy = (height - 50) / 2
    R = min(width, height - 50) / 2 - margin
    n = max(len(rows), 3)

    def angle(i: int) -> float:
        return -math.pi / 2 + 2 * math.pi * (i / n)

    def polygon_path(series_key: str) -> str:
        pts = []
        for i, r in enumerate(rows):
            score = _clamp01(_safe_float(r.get(series_key), 0.0))
            x, y = _pt(cx, cy, R * score, angle(i))
            pts.append((x, y))
        if not pts:
            return ""
        head = f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"
        tail = " ".join(f"L {x:.2f} {y:.2f}" for x, y in pts[1:])
        return f"{head} {tail} Z"

    parts: List[str] = []
    parts.append(f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" class="radar">')

    for frac in (0.2, 0.4, 0.6, 0.8, 1.0):
        pts = []
        for i in range(n):
            x, y = _pt(cx, cy, R * frac, angle(i))
            pts.append(f"{x:.2f},{y:.2f}")
        parts.append(f'<polygon points="{" ".join(pts)}" class="radar-grid"></polygon>')

    for i, r in enumerate(rows):
        ax, ay = _pt(cx, cy, R, angle(i))
        parts.append(f'<line x1="{cx:.2f}" y1="{cy:.2f}" x2="{ax:.2f}" y2="{ay:.2f}" class="radar-axis"></line>')

        if i % max(1, show_every) == 0:
            full_label = str(r.get("key", "") or "")
            label = _short_label(full_label, max_chars=18)
            lx, ly = _pt(cx, cy, R + 18, angle(i))
            ang = angle(i)
            anchor = "middle"
            if -math.pi/2 < ang < math.pi/2:
                anchor = "start"
            elif ang > math.pi/2 or ang < -math.pi/2:
                anchor = "end"
            parts.append(
                f'<text x="{lx:.2f}" y="{ly:.2f}" class="radar-label" text-anchor="{anchor}">'
                f'<title>{html.escape(full_label)}</title>{html.escape(label)}</text>'
            )

    d_ref = polygon_path("ref_score")
    d_test = polygon_path("test_score")
    if d_ref:
        parts.append(f'<path d="{d_ref}" class="radar-ref"></path>')
    if d_test:
        parts.append(f'<path d="{d_test}" class="radar-test"></path>')

    for i, r in enumerate(rows):
        key = r.get("key", "")
        ref_raw = r.get("ref_raw", None)
        test_raw = r.get("test_raw", None)
        for series_key, cls in (("ref_score", "radar-ref"), ("test_score", "radar-test")):
            score = _clamp01(_safe_float(r.get(series_key), 0.0))
            x, y = _pt(cx, cy, R * score, angle(i))
            series_name = series_key.split("_")[0]
            raw_val = ref_raw if series_name == "ref" else test_raw
            if raw_val is not None:
                tlabel = f"{key}: {series_name} raw={raw_val} (score={score:.2f})"
            else:
                tlabel = f"{key}: {series_name} score={score:.2f}"
            parts.append(
                f'<g><title>{html.escape(str(tlabel))}</title>'
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" class="{cls}"></circle></g>'
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

    use_raw = _has_raw(rows)
    rows_default = _scaled_rows_axis_normalized(rows)
    rows_log = _scaled_rows_log(rows) if use_raw else []

    N = 24
    container = tags.div(_class="radar-container", id=f"radar-{idx}")

    if use_raw and len(rows_log) >= 3:
        controls = tags.div(_class="radar-controls")
        controls.add(tags.button("Scale: normal", onclick=f"toggleRadarScale('radar-{idx}')", **{"data-radar-toggle": "scale"}))
        container.add(controls)

    if len(rows_default) <= N:
        normal_view = tags.div(_class="radar-view", **{"data-scale": "normal"})
        normal_view.add(raw(_build_svg(rows_default, show_every=1 if len(rows_default) <= 24 else 2)))
        container.add(normal_view)
        if use_raw and len(rows_log) >= 3:
            log_view = tags.div(_class="radar-view", **{"data-scale": "log", "hidden": ""})
            log_view.add(raw(_build_svg(rows_log, show_every=1 if len(rows_log) <= 24 else 2, title_suffix=" (log)")))
            container.add(log_view)
        return container

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for r in rows_default:
        diff = abs(_safe_float(r.get("test_score"), 0.0) - _safe_float(r.get("ref_score"), 0.0))
        scored.append((diff, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    top_rows = [r for _, r in scored[:N]]

    normal_pane = tags.div(_class="radar-view", **{"data-scale": "normal"})
    normal_pane.add(raw(_build_svg(top_rows, show_every=1)))
    det = tags.details()
    det.add(tags.summary(f"Show all {len(rows_default)} items"))
    det.add(tags.div(raw(_build_svg(rows_default, show_every=max(1, len(rows_default)//24)))))
    normal_pane.add(det)
    container.add(normal_pane)

    if use_raw and len(rows_log) >= 3:
        top_keys = {str(r.get("key")) for r in top_rows}
        top_log = [r for r in rows_log if str(r.get("key")) in top_keys]
        log_pane = tags.div(_class="radar-view", **{"data-scale": "log", "hidden": ""})
        log_pane.add(raw(_build_svg(top_log, show_every=1, title_suffix=" (log)")))
        det_log = tags.details()
        det_log.add(tags.summary(f"Show all {len(rows_log)} items (log)"))
        det_log.add(tags.div(raw(_build_svg(rows_log, show_every=max(1, len(rows_log)//24), title_suffix=" (log)"))))
        log_pane.add(det_log)
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
