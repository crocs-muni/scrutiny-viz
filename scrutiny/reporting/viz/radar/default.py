# scrutiny-viz/scrutiny/reporting/viz/radar/default.py
from typing import Dict, Any, List, Tuple
from dominate import tags
from dominate.util import raw
import math, html

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

def _short_label(s: str, *, max_len: int = 30) -> str:
    s = str(s or "")
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"

def _build_svg(rows: List[Dict[str, Any]], *, width=900, height=900, margin=80,
               show_every=1, title_suffix="", viewbox_pad=180, label_max_len=30) -> str:
    """Generate a radar SVG string. show_every=N hides labels except every Nth."""
    n = len(rows)
    if n < 3:
        return ""

    cx = width // 2
    cy = height // 2
    R = min(width, height) // 2 - margin
    grid_steps = 5

    def angle(i):  # [0..n-1], start at -90° (top), clockwise
        return -math.pi/2 + 2 * math.pi * (i / n)

    def path_for(series_key: str) -> str:
        pts = []
        for i, r in enumerate(rows):
            score = _clamp01(_safe_float(r.get(series_key), 0.0))
            x, y = _pt(cx, cy, R * score, angle(i))
            pts.append((x, y))
        if not pts:
            return ""
        d = f"M {pts[0][0]:.2f},{pts[0][1]:.2f} " + " ".join(f"L {x:.2f},{y:.2f}" for x, y in pts[1:]) + " Z"
        return d

    d_ref = path_for("ref_score")
    d_test = path_for("test_score")

    parts: List[str] = []
    parts.append(
        f'<svg width="{width}" height="{height}" '
        f'viewBox="{-viewbox_pad} {-viewbox_pad} {width + 2*viewbox_pad} {height + 2*viewbox_pad}" '
        f'class="radar">'
    )

    # grid rings + labels
    for k in range(1, grid_steps + 1):
        r = R * (k / grid_steps)
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" class="radar-grid"></circle>')
        parts.append(
            f'<text x="{cx}" y="{cy - r:.2f}" class="radar-grid-label" text-anchor="middle">'
            f'{int(100 * k/grid_steps)}%</text>'
        )

    # axes & labels
    for i, r in enumerate(rows):
        ang = angle(i)
        x, y = _pt(cx, cy, R, ang)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.2f}" y2="{y:.2f}" class="radar-axis"></line>')

        # label outside radius; skip most per show_every
        if (i % show_every) == 0:
            lx, ly = _pt(cx, cy, R + 18, ang)
            full_label = str(r.get("key", ""))
            label = _short_label(full_label, max_len=label_max_len)

            anchor = "middle"
            if -math.pi/2 < ang < math.pi/2:
                anchor = "start"
            elif ang > math.pi/2 or ang < -math.pi/2:
                anchor = "end"

            parts.append(
                f'<text x="{lx:.2f}" y="{ly:.2f}" class="radar-label" text-anchor="{anchor}">'
                f'<title>{html.escape(full_label)}</title>{html.escape(label)}</text>'
            )

    # polygons
    if d_ref:
        parts.append(f'<path d="{d_ref}" class="radar-ref"></path>')
    if d_test:
        parts.append(f'<path d="{d_test}" class="radar-test"></path>')

    # points with native tooltips (<title>)
    for i, r in enumerate(rows):
        key = r.get("key", "")
        ref_raw = r.get("ref_raw", None)
        test_raw = r.get("test_raw", None)
        for series_key, cls in (("ref_score", "radar-ref"), ("test_score", "radar-test")):
            score = _clamp01(_safe_float(r.get(series_key), 0.0))
            x, y = _pt(cx, cy, R * score, angle(i))

            series_name = series_key.split("_")[0] 
            if series_name == "ref":
                raw_val = ref_raw
            else:
                raw_val = test_raw

            if raw_val is not None:
                tlabel = f"{key}: {series_name} raw={raw_val} (score={score:.2f})"
            else:
                tlabel = f"{key}: {series_name} score={score:.2f}"

            parts.append(
                f'<g><title>{html.escape(str(tlabel))}</title>'
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" class="{cls}"></circle></g>'
            )

    # legend
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
    rows_default = _scaled_rows_axis_normalized(rows) if use_raw else _scaled_rows_axis_normalized(rows)
    rows_log = _scaled_rows_log(rows) if use_raw else []


    N = 24
    container = tags.div(_class="radar-container", id=f"radar-{idx}")

    if use_raw and len(rows_log) >= 3:
        controls = tags.div(_class="radar-controls")
        controls.add(
            tags.button(
                "Scale: normal",
                onclick=f"toggleRadarScale('radar-{idx}')",
                **{"data-radar-toggle": "scale"},
            )
        )
        container.add(controls)

    # Small case (<=N): no need for "show all" details unless user wants it later.
    if len(rows_default) <= N:
        svg_normal = _build_svg(rows_default, show_every=1 if len(rows_default) <= 24 else 2)
        normal_view = tags.div(_class="radar-view", **{"data-scale": "normal"})
        normal_view.add(raw(svg_normal))
        container.add(normal_view)

        if use_raw and len(rows_log) >= 3:
            svg_log = _build_svg(rows_log, show_every=1 if len(rows_log) <= 24 else 2, title_suffix=" (log)")
            log_view = tags.div(_class="radar-view", **{"data-scale": "log", "hidden": ""})
            log_view.add(raw(svg_log))
            container.add(log_view)

        return container

    # compute score deltas to pick top-N
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for r in rows_default:
        diff = abs(_safe_float(r.get("test_score"), 0.0) - _safe_float(r.get("ref_score"), 0.0))
        scored.append((diff, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    top_rows = [r for _, r in scored[:N]]

    svg_top = _build_svg(top_rows, show_every=1)
    svg_all = _build_svg(rows_default, show_every=max(1, len(rows_default)//24))  # skip labels adaptively

    # Use <details> for a JS-free toggle
    normal_pane = tags.div(_class="radar-view", **{"data-scale": "normal"})
    normal_pane.add(raw(svg_top))
    det = tags.details()
    det.add(tags.summary(f"Show all {len(rows_default)} items"))
    det.add(tags.div(raw(svg_all)))
    normal_pane.add(det)
    container.add(normal_pane)

    # Optional: provide log-scaled view (same top selection) and toggle via JS button.
    if use_raw and len(rows_log) >= 3:
        top_keys = {str(r.get("key")) for r in top_rows}
        top_log = [r for r in rows_log if str(r.get("key")) in top_keys]

        svg_log_top = _build_svg(top_log, show_every=1, title_suffix=" (log)")
        svg_log_all = _build_svg(rows_log, show_every=max(1, len(rows_log)//24), title_suffix=" (log)")

        log_pane = tags.div(_class="radar-view", **{"data-scale": "log", "hidden": ""})
        log_pane.add(raw(svg_log_top))

        det_log = tags.details()
        det_log.add(tags.summary(f"Show all {len(rows_log)} items (log)"))
        det_log.add(tags.div(raw(svg_log_all)))
        log_pane.add(det_log)

        container.add(log_pane)

    return container
