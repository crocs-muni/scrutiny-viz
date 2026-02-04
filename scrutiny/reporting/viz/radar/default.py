# scrutiny-viz/scrutiny/reporting/viz/radar/default.py
from typing import Dict, Any, List, Tuple
from dominate import tags
from dominate.util import raw
import math, html

def _pt(cx, cy, r, ang_rad):
    return (cx + r * math.cos(ang_rad), cy + r * math.sin(ang_rad))

def _build_svg(rows: List[Dict[str, Any]], *, width=900, height=900, margin=80,
               show_every=1, title_suffix="") -> str:
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
            score = float(r.get(series_key) or 0.0)
            x, y = _pt(cx, cy, R * score, angle(i))
            pts.append((x, y))
        if not pts:
            return ""
        d = f"M {pts[0][0]:.2f},{pts[0][1]:.2f} " + " ".join(f"L {x:.2f},{y:.2f}" for x, y in pts[1:]) + " Z"
        return d

    d_ref = path_for("ref_score")
    d_test = path_for("test_score")

    parts: List[str] = []
    parts.append(f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" class="radar">')

    # grid rings + labels
    for k in range(1, grid_steps + 1):
        r = R * (k / grid_steps)
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" class="radar-grid"></circle>')
        parts.append(f'<text x="{cx}" y="{cy - r:.2f}" class="radar-grid-label" text-anchor="middle">{int(100 * k/grid_steps)}%</text>')

    # axes & labels
    for i, r in enumerate(rows):
        ang = angle(i)
        x, y = _pt(cx, cy, R, ang)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.2f}" y2="{y:.2f}" class="radar-axis"></line>')

        # label outside radius; skip most per show_every
        if (i % show_every) == 0:
            lx, ly = _pt(cx, cy, R + 18, ang)
            label = html.escape(str(r.get("key", "")))
            anchor = "middle"
            if -math.pi/2 < ang < math.pi/2:
                anchor = "start"
            elif ang > math.pi/2 or ang < -math.pi/2:
                anchor = "end"
            parts.append(f'<text x="{lx:.2f}" y="{ly:.2f}" class="radar-label" text-anchor="{anchor}">{label}</text>')

    # polygons
    if d_ref:
        parts.append(f'<path d="{d_ref}" class="radar-ref"></path>')
    if d_test:
        parts.append(f'<path d="{d_test}" class="radar-test"></path>')

    # points with native tooltips (<title>)
    for i, r in enumerate(rows):
        for series_key, cls in (("ref_score", "radar-ref"), ("test_score", "radar-test")):
            score = float(r.get(series_key) or 0.0)
            x, y = _pt(cx, cy, R * score, angle(i))
            tlabel = f"{r.get('key','')}: {series_key.split('_')[0]}={score:.2f}"
            parts.append(f'<g><title>{html.escape(tlabel)}</title><circle cx="{x:.2f}" cy="{y:.2f}" r="3" class="{cls}"></circle></g>')

    # legend
    parts.append(f'<rect x="{margin}" y="{height - margin + 12}" width="14" height="8" class="radar-ref"></rect>')
    parts.append(f'<text x="{margin + 20}" y="{height - margin + 20}" class="radar-legend">reference</text>')
    parts.append(f'<rect x="{margin + 120}" y="{height - margin + 12}" width="14" height="8" class="radar-test"></rect>')
    parts.append(f'<text x="{margin + 140}" y="{height - margin + 20}" class="radar-legend">profile{title_suffix}</text>')

    parts.append('</svg>')
    return "".join(parts)


def render_radar_block(section_name: str, section: Dict[str, Any], idx: int):
    rows: List[Dict[str, Any]] = section.get("radar_rows", []) or []
    if len(rows) < 3:
        return tags.div()

    # Heuristic: show top-N (by absolute diff) initially; offer "Show all" disclosure
    N = 24
    if len(rows) <= N:
        svg = _build_svg(rows, show_every=1 if len(rows) <= 24 else 2)
        container = tags.div(_class="radar-container", id=f"radar-{idx}")
        container.add(raw(svg))
        return container

    # compute score deltas to pick top-N
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for r in rows:
        try:
            diff = abs(float(r.get("test_score") or 0.0) - float(r.get("ref_score") or 0.0))
        except Exception:
            diff = 0.0
        scored.append((diff, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    top_rows = [r for _, r in scored[:N]]

    svg_top = _build_svg(top_rows, show_every=1)
    svg_all = _build_svg(rows, show_every=max(1, len(rows)//24))  # skip labels adaptively

    # Use <details> for a JS-free toggle
    wrapper = tags.div(_class="radar-container", id=f"radar-{idx}")
    wrapper.add(raw(svg_top))
    det = tags.details()
    det.add(tags.summary(f"Show all {len(rows)} items"))
    det.add(tags.div(raw(svg_all)))
    wrapper.add(det)
    return wrapper
