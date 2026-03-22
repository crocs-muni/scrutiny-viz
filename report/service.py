# scrutiny-viz/report/service.py
from __future__ import annotations

import json
import os
import re
import zipfile
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dominate import document, tags
from dominate.util import raw

from scrutiny.htmlutils import show_all_button, hide_all_button, default_button
from scrutiny.interfaces import ContrastState
from scrutiny import logging as slog
from scrutiny.paths import REPORT_ASSETS_DIR, results_dir

from report.viz import registry as viz_registry
from report.viz.table import render_table_block

OUT_DIR = "results"
JS_DIR = REPORT_ASSETS_DIR / "script.js"
CSS_DIR = REPORT_ASSETS_DIR / "style.css"

TOOLTIP_TEXT = {
    ContrastState.MATCH: "Devices seem to match",
    ContrastState.WARN: "There seem to be some differences worth checking",
    ContrastState.SUSPICIOUS: "Devices probably don't match",
}

RESULT_TEXT = {
    ContrastState.MATCH: lambda x: "None of the modules raised suspicion during the verification process.",
    ContrastState.WARN: lambda x: f"There seem to be some differences worth checking. {x} module(s) report inconsistencies.",
    ContrastState.SUSPICIOUS: lambda x: (
        f"{x} module(s) report suspicious differences between profiled and reference devices. "
        "The verification process may have been unsuccessful and compared devices are different."),
}

_id_pat = re.compile(r"[^A-Za-z0-9_-]+")
_link_pat = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOOLISH_STRINGS = {"true", "false", "yes", "no", "supported", "unsupported", "1", "0"}


def safe_id(s: str) -> str:
    return _id_pat.sub("_", s)


def state_enum(s: str) -> ContrastState:
    try:
        return ContrastState[s]
    except Exception:
        return ContrastState.WARN


def iter_sections_issues_first(report: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    items = list((report.get("sections") or {}).items())
    issues: List[Tuple[str, Dict[str, Any]]] = []
    matches: List[Tuple[str, Dict[str, Any]]] = []
    for name, sec in items:
        st = state_enum(sec.get("result", "WARN"))
        if st == ContrastState.MATCH:
            matches.append((name, sec))
        else:
            issues.append((name, sec))
    return issues + matches


def render_status_dot_link(*, section_name: str, state: ContrastState, target_id: str):
    tip = TOOLTIP_TEXT.get(state, "")
    with tags.a(cls="dot " + state.name.lower(), href=f"#{target_id}", title=section_name):
        tooltip = f"{section_name} — {tip}" if tip else section_name
        tags.span(tooltip, cls="tooltiptext " + state.name.lower())


def table(headers: Iterable[str], rows: Iterable[Iterable[Any]]):
    return render_table_block(list(headers), list(rows))


def badge(text: str, kind: str) -> tags.span:
    return tags.span(text, cls=f"badge badge-{kind}")


def bool_to_badge(value: Any) -> tags.span:
    if isinstance(value, bool):
        return badge("Supported", "ok") if value else badge("Unsupported", "bad")
    sval = str(value).strip().lower()
    if sval in {"true", "yes", "supported"}:
        return badge("Supported", "ok")
    if sval in {"false", "no", "unsupported"}:
        return badge("Unsupported", "bad")
    return badge("Unknown", "neutral")


def is_boolish_value(v: Any) -> bool:
    if isinstance(v, bool):
        return True
    if v is None:
        return False
    return str(v).strip().lower() in _BOOLISH_STRINGS


def is_support_field(field: Any) -> bool:
    s = str(field or "").strip().lower()
    return s in {"is_supported", "issupported", "supported"}


def display_key(raw_key: Any, labels: Dict[str, str]) -> str:
    try:
        return labels.get(str(raw_key), str(raw_key))
    except Exception:
        return str(raw_key)


def fast_summary(stats_or_counts: Dict[str, Any]) -> str:
    s = stats_or_counts or {}
    compared = int(s.get("compared", 0) or 0)
    changed = int(s.get("changed", 0) or 0)
    only_ref = int(s.get("only_ref", 0) or 0)
    only_test = int(s.get("only_test", 0) or 0)
    return (f"Compared {compared} items. "
            f"Differences: {changed}. "
            f"Missing on profile: {only_ref}. "
            f"Extra on profile: {only_test}.")


def render_info_icon(tooltip_text: str, *, wide: bool = False) -> tags.span:
    cls = "tooltiptext info" if wide else "tooltiptext"
    with tags.span(cls="circle circle-small"):
        tags.span("i")
        tags.span(tooltip_text, cls=cls)


@contextmanager
def toggle_block(*, block_id: str, title: str, button_text: str, button_title: str | None = None, hide: bool = False):
    with tags.div(cls="toggle-header"):
        tags.h3(title, cls="toggle-title")
        tags.button(
            button_text,
            cls="toggle-btn",
            title=(button_title or title),
            onclick=f"hideButton('{block_id}')",
            **{"data-toggle-target": block_id, "aria-expanded": "false"},
        )
    style = "display:none;" if hide else "display:block;"
    with tags.div(id=block_id, cls="toggle-block", style=style, **{"data-default": "hide" if hide else "show"}):
        yield


def _render_paragraph_with_links(text: str) -> None:
    if not text:
        return
    with tags.p():
        pos = 0
        for m in _link_pat.finditer(text):
            if m.start() > pos:
                tags.span(text[pos:m.start()])
            label = (m.group(1) or "").strip() or (m.group(2) or "").strip()
            href = (m.group(2) or "").strip()
            if href:
                tags.a(label, href=href, target="_blank", rel="noopener noreferrer")
            else:
                tags.span(label)
            pos = m.end()
        if pos < len(text):
            tags.span(text[pos:])


def render_doc_text(doc_text: str) -> None:
    if not doc_text:
        return
    chunks = [c.strip() for c in re.split(r"\n\s*\n", str(doc_text).replace("\r\n", "\n"))]
    for c in chunks:
        if c:
            _render_paragraph_with_links(c)


def normalize_report_types(rep_cfg: Dict[str, Any]) -> List[Tuple[str, Optional[str]]]:
    raw_types = rep_cfg.get("types") or []
    out: List[Tuple[str, Optional[str]]] = []
    for t in raw_types:
        if t is None:
            continue
        if isinstance(t, dict):
            tp = str(t.get("type") or "").strip().lower()
            if not tp:
                continue
            v = t.get("variant")
            v = str(v).strip().lower() if v is not None and str(v).strip() else None
            out.append((tp, v))
        else:
            tp = str(t).strip().lower()
            if tp:
                out.append((tp, None))
    return out


def _filter_tuple_for_label(item: Any, key_label: str) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    filtered = {k: v for k, v in item.items() if str(v) != str(key_label)}
    return filtered if filtered else dict(item)


def _tuple_value_text(item: Any, key_label: str) -> str:
    if item is None:
        return ""
    if not isinstance(item, dict):
        return str(item)
    d = _filter_tuple_for_label(item, key_label)
    if len(d) == 1:
        k, v = next(iter(d.items()))
        return f"{k} {v}"
    return ", ".join(f"{k} {v}" for k, v in d.items())


def pair_group_changes(removed: List[Dict[str, Any]], added: List[Dict[str, Any]]):
    out = []
    r = removed[:]
    a = added[:]
    while r and a:
        out.append(("arrow", r.pop(0), a.pop(0)))
    for x in r:
        out.append(("removed", x, None))
    for y in a:
        out.append(("added", None, y))
    return out


def format_group_value(v: Any) -> tags.span:
    if v is None:
        return tags.span("matched", cls="badge badge-ok")
    if isinstance(v, dict):
        parts = []
        for f, vv in v.items():
            if isinstance(vv, (list, tuple, set)):
                parts.append(f"{f}: {', '.join(str(x) for x in vv)}")
            else:
                parts.append(f"{f}: {vv}")
        return tags.span("; ".join(parts))
    if isinstance(v, (list, tuple, set)):
        return tags.span(", ".join(str(x) for x in v))
    return tags.span(str(v))


def extract_buckets_for_report(section: Dict[str, Any]) -> Dict[str, Any]:
    labels: Dict[str, str] = (section.get("key_labels") or section.get("labels")) or {}
    diffs = section.get("diffs", []) or []

    boolean_rows_raw = []
    string_rows_raw = []
    missing_rows = []
    extra_rows = []
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    for d in diffs:
        field = d.get("field")
        key_raw = d.get("key")
        item_label = display_key(key_raw, labels)

        if field == "__presence__":
            if d.get("ref") and not d.get("test"):
                missing_rows.append([item_label, "present in reference only"])
            elif d.get("test") and not d.get("ref"):
                extra_rows.append([item_label, "present in profile only"])
            continue

        if field == "__group__":
            g = grouped.setdefault(str(key_raw), {"removed": [], "added": []})
            if d.get("ref") is not None and d.get("test") is None:
                g["removed"].append(d.get("ref"))
            elif d.get("ref") is None and d.get("test") is not None:
                g["added"].append(d.get("test"))
            continue

        ref_v, test_v = d.get("ref"), d.get("test")
        if is_support_field(field) and is_boolish_value(ref_v) and is_boolish_value(test_v):
            boolean_rows_raw.append((item_label, field, ref_v, test_v))
        elif isinstance(ref_v, bool) or isinstance(test_v, bool):
            boolean_rows_raw.append((item_label, field, ref_v, test_v))
        else:
            string_rows_raw.append((item_label, field, ref_v, test_v))

    for k, grp in grouped.items():
        item_label = display_key(k, labels)
        pairs = pair_group_changes(grp["removed"], grp["added"])
        for kind, rdict, tdict in pairs:
            if kind == "arrow":
                rd = _filter_tuple_for_label(rdict, item_label)
                td = _filter_tuple_for_label(tdict, item_label)
                keys = sorted(set(rd.keys()) | set(td.keys())) or ["set"]
                field_name = ", ".join(keys)
                string_rows_raw.append((item_label, field_name, _tuple_value_text(rdict, item_label), _tuple_value_text(tdict, item_label)))
            elif kind == "removed":
                missing_rows.append([item_label, _tuple_value_text(rdict, item_label)])
            else:
                extra_rows.append([item_label, _tuple_value_text(tdict, item_label)])

    distinct_fields = sorted({f for (_, f, _, _) in string_rows_raw})
    include_field_col = len(distinct_fields) > 1

    boolean_rows = []
    for (item, _field, ref_v, test_v) in sorted(boolean_rows_raw, key=lambda x: x[0]):
        boolean_rows.append([item, bool_to_badge(ref_v), bool_to_badge(test_v)])

    if include_field_col:
        string_rows = [[item, field, ref_v, test_v] for (item, field, ref_v, test_v) in sorted(string_rows_raw, key=lambda x: (x[0], x[1]))]
    else:
        string_rows = [[item, ref_v, test_v] for (item, _field, ref_v, test_v) in sorted(string_rows_raw, key=lambda x: x[0])]

    return {
        "boolean_rows": boolean_rows,
        "string_rows": string_rows,
        "string_include_field": include_field_col,
        "missing_rows": sorted(missing_rows, key=lambda x: x[0]),
        "extra_rows": sorted(extra_rows, key=lambda x: x[0]),
    }


def _add_rendered_node(node: Any) -> None:
    if node is None:
        return
    if isinstance(node, (list, tuple)):
        for sub in node:
            _add_rendered_node(sub)
        return
    parent = tags.div()
    parent.add(node)


def _render_viz_plugin(name: str, *, section_name: str, section: Dict[str, Any], idx: int, ref_name: str, prof_name: str, variant: str | None = None) -> Any:
    plugin = viz_registry.get_plugin(name)
    return plugin.render(
        section_name=section_name,
        section=section,
        idx=idx,
        ref_name=ref_name,
        prof_name=prof_name,
        variant=variant,
    )


def render_module_card(section_name: str, section: Dict[str, Any], idx: int, *, ref_name: str, prof_name: str):
    state = state_enum(section.get("result", "WARN"))
    anchor_id = safe_id(section_name)

    tags.h2(f"Module: {section_name}", id=anchor_id)
    with tags.div():
        tags.span(f"{state.name}", style="font-weight:bold;")

    rep_cfg = section.get("report") or {}
    doc_text = (rep_cfg.get("doc_text") or "").strip()
    if doc_text:
        with tags.div(cls="module-doc"):
            render_doc_text(doc_text)

    stats_display = (section.get("stats") or section.get("counts") or {})
    tags.p(fast_summary(stats_display))

    types_ordered = normalize_report_types(rep_cfg)
    viz_types  = [(t, v) for (t, v) in types_ordered if t != "table" and t in viz_registry.list_types()]
    if viz_types :
        with toggle_block(
            block_id=f"section_{idx}_perf",
            title="Visualizations",
            button_text="Viz",
            button_title="Show/hide visualizations",
            hide=(state == ContrastState.MATCH),
        ):
            for t, v in viz_types :
                rendered = _render_viz_plugin(t, section_name=section_name, section=section, idx=idx, ref_name=ref_name, prof_name=prof_name, variant=v)
                _add_rendered_node(rendered)

    table_variant = None
    if any(t == "table" for (t, _v) in types_ordered):
        for (t, v) in types_ordered:
            if t == "table":
                table_variant = v
        node = _render_viz_plugin("table", section_name=section_name, section=section, idx=idx, ref_name=ref_name, prof_name=prof_name, variant=table_variant)
        if node is not None:
            container = tags.div()
            container.add(node)
            tags.hr()
            return

        buckets = extract_buckets_for_report(section)
        divname = f"section_{idx}"

        if buckets["boolean_rows"]:
            with toggle_block(block_id=f"{divname}_bool", title="Boolean / binary differences", button_text="Table", button_title="Show/hide table: Boolean / binary differences", hide=False):
                tags.p("If a capability is supported by the reference but not by the profile (or vice versa), the cards likely do not match.", cls="hint")
                table(["Item", "Reference", "Profile"], buckets["boolean_rows"])

        if buckets["string_rows"]:
            with toggle_block(block_id=f"{divname}_strings", title="Differences in string fields", button_text="Table", button_title="Show/hide table: Differences in string fields", hide=False):
                headers = ["Item", "Field", "Reference", "Profile"] if buckets["string_include_field"] else ["Item", "Reference", "Profile"]
                table(headers, buckets["string_rows"])

        if buckets["missing_rows"]:
            with toggle_block(block_id=f"{divname}_missing", title="Missing on profile (present in reference)", button_text="Table", button_title="Show/hide table: Missing on profile", hide=True):
                table(["Item", "Detail"], buckets["missing_rows"])

        if buckets["extra_rows"]:
            with toggle_block(block_id=f"{divname}_extra", title="Extra on profile (absent in reference)", button_text="Table", button_title="Show/hide table: Extra on profile", hide=True):
                table(["Item", "Detail"], buckets["extra_rows"])

        if section.get("matches"):
            with toggle_block(block_id=f"{divname}_matches", title="Matches", button_text="Table", button_title="Show/hide table: Matches", hide=True):
                rows = []
                labels = (section.get("key_labels") or section.get("labels") or {})
                for m in section["matches"]:
                    item = display_key(m.get("key"), labels)
                    field = m.get("field")
                    val = m.get("value")
                    if field != "__group__" and val is not None and str(val) == str(item):
                        continue
                    if field == "__group__":
                        pretty_field, val_node = "set", format_group_value(val)
                    else:
                        pretty_field = field
                        field_l = str(field or "").strip().lower()
                        if (field_l in {"is_supported", "issupported", "supported"}) and is_boolish_value(val):
                            val_node = bool_to_badge(val)
                        else:
                            val_node = bool_to_badge(val) if isinstance(val, bool) else tags.span("" if val is None else str(val))
                    rows.append([item, pretty_field, val_node])
                if rows:
                    table(["Item", "Field", "Value"], rows)
                else:
                    tags.p("No relevant matches to display (filtered noisy fields).")

    tags.hr()


def render_intro_left(report: Dict[str, Any], *, overall_state: ContrastState, suspicions: int, src_path: str):
    ref_name = report.get("reference_name", "reference")
    prof_name = report.get("profile_name", "profile")

    tags.h1("Verification of profile against")
    with tags.p(cls="intro-oneline"):
        tags.strong("Reference:")
        tags.span(" baseline measurement used as the expected/known-good comparison point. ")
        tags.strong("Profile:")
        tags.span(" the measured device/dataset being checked.")

    with tags.div():
        tags.h2("Verification results")
        with tags.span(cls="circle", style=("margin-left:8px; background:#333; color:#fff; width:18px; height:18px; line-height:18px; text-align:center; border-radius:50%; display:inline-block; position:relative; font-size:12px;")):
            tags.span("i")
            with tags.span(cls="tooltiptext info", style="left:0; transform:translateX(-20%);"):
                tags.strong("Result: ")
                tags.span(RESULT_TEXT[overall_state](suspicions))
                tags.br(); tags.br()
                tags.strong("Methodology: ")
                tags.span("WARN when changes are below configured thresholds; SUSPICIOUS when changed/compared exceeds the ratio threshold or the change count exceeds the count threshold.")

    with tags.div(id="modules"):
        for name, sec in iter_sections_issues_first(report):
            st = state_enum(sec.get("result", "WARN"))
            render_status_dot_link(section_name=name, state=st, target_id=safe_id(name))
        with tags.div(cls="dot-legend"):
            with tags.span(cls="legend-item"):
                tags.span("", cls="legend-dot match"); tags.span("Match")
            with tags.span(cls="legend-item"):
                tags.span("", cls="legend-dot warn"); tags.span("Warn")
            with tags.span(cls="legend-item"):
                tags.span("", cls="legend-dot suspicious"); tags.span("Suspicious")

    tags.h3("Quick visibility settings")
    show_all_button(); hide_all_button(); default_button()

    sections = [name for (name, _sec) in iter_sections_issues_first(report)]
    if sections:
        with tags.div():
            tags.label("Jump to module: ", _for="jumpMod")
            sel = tags.select(id="jumpMod", onchange="location.hash=this.value")
            for name in sections:
                sel.add(tags.option(name, value=safe_id(name)))

    meta = report.get("meta", {}) or {}
    schema_title = meta.get("schema_title")
    gen_ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    details_id = "intro_details"
    with tags.div(cls="intro-details-bar"):
        tags.button("Details", cls="toggle-btn", title="Show/hide details about inputs and generation", onclick=f"hideButton('{details_id}')", **{"data-toggle-target": details_id, "aria-expanded": "false"})
    with tags.div(id=details_id, cls="toggle-block", style="display:none;", **{"data-default": "hide"}):
        with tags.div(cls="intro-meta"):
            tags.p(f"Generated on: {gen_ts}")
            tags.p(f"Generated from: {src_path}")
            tags.p(f"Reference label: {ref_name}")
            tags.p(f"Profile label: {prof_name}")
            if schema_title:
                tags.p(f"Schema: {schema_title}")


def render_intro_right(report: Dict[str, Any]):
    dashboard = report.get("dashboard", {}) or {}
    overall_counts = dashboard.get("overall_state_counts", {}) or {}

    sections = report.get("sections", {}) or {}
    total_matched = total_diffs = total_compared = 0
    for sec in sections.values():
        s = (sec.get("stats") or sec.get("counts") or {})
        total_matched += int(s.get("matched", 0) or 0)
        total_diffs += int(s.get("changed", 0) or 0) + int(s.get("only_ref", 0) or 0) + int(s.get("only_test", 0) or 0)
        total_compared += int(s.get("compared", 0) or 0)

    tip_modules = "Overall modules: counts how many modules ended as Match/Warn/Suspicious (one verdict per module)."
    tip_results = "Overall results: aggregates all compared items across modules: matches vs differences (including missing/extra)."

    donut_plugin = viz_registry.get_plugin("donut")
    with tags.div(_class="donut-stack"):
        wrap1 = tags.div(cls="donut-card-wrap")
        wrap1.add(donut_plugin.render(
            title="Overall modules",
            counts=overall_counts,
            segments=["MATCH", "WARN", "SUSPICIOUS"],
            radius=52,
            stroke=18,
            center_label=str(sum(int(overall_counts.get(k, 0) or 0) for k in ("MATCH", "WARN", "SUSPICIOUS"))),
            legend_labels={"MATCH": "Match", "WARN": "Warn", "SUSPICIOUS": "Suspicious"},
            variant=None,
        ))
        with wrap1:
            render_info_icon(tip_modules)

        wrap2 = tags.div(cls="donut-card-wrap")
        wrap2.add(donut_plugin.render(
            title="Overall results (matches vs diffs)",
            counts={"MATCH": total_matched, "WARN": total_diffs},
            segments=["MATCH", "WARN"],
            radius=52,
            stroke=18,
            center_label=str(total_compared),
            legend_labels={"MATCH": "Matches", "WARN": "Diffs"},
            variant=None,
        ))
        with wrap2:
            render_info_icon(tip_results)

        with tags.div(_class="kpi-row"):
            with tags.div(_class="kpi"):
                tags.div("Compared items", _class="kpi-title")
                tags.div(str(total_compared), _class="kpi-value")
            with tags.div(_class="kpi"):
                tags.div("Total diffs", _class="kpi-title")
                tags.div(str(total_diffs), _class="kpi-value")


def zip_preparation(html_report_path: str, verification_profile_path: str, out_dir: str, js_path: str, css_path: str, link_mode: bool) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    zip_name = f"results_{ts}.zip"
    zip_path = os.path.join(out_dir, zip_name)
    compression = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(zip_path, mode="w", compression=compression) as z:
        z.write(html_report_path, arcname=os.path.basename(html_report_path))
        z.write(verification_profile_path, arcname=os.path.basename(verification_profile_path))
        if link_mode:
            z.write(js_path, arcname="script.js")
            z.write(css_path, arcname="style.css")
    return zip_path


def run_report_html(*, verification_profile: str, output_file: str = "comparison.html", exclude_style_and_scripts: bool = False, no_zip: bool = False) -> int:
    slog.log_step("Loading report JSON", verification_profile)
    try:
        with open(verification_profile, "r", encoding="utf-8") as f:
            report = json.load(f)
    except Exception:
        slog.log_err("Failed to load report json from path", verification_profile)
        return 1

    overall_state = state_enum(report.get("overall", "WARN"))
    suspicions = sum(1 for s in report.get("sections", {}).values() if state_enum(s.get("result", "WARN")).value >= ContrastState.WARN.value)
    slog.log_info(f"Overall state: {overall_state.name}")

    script = ""
    style = ""
    slog.log_step("Loading JS")
    try:
        with open(JS_DIR, "r", encoding="utf-8") as js:
            script = "\n" + js.read() + "\n"
    except Exception:
        slog.log_err("Failed to load JS", JS_DIR)

    slog.log_step("Loading CSS")
    try:
        with open(CSS_DIR, "r", encoding="utf-8") as css:
            style = "\n" + css.read() + "\n"
    except Exception:
        slog.log_err("Failed to load CSS")

    viz_registry.discover_builtin_viz(force=True)
    slog.log_step("Rendering HTML document")
    doc = document(title="Comparison of smart cards")
    with doc.head:
        if exclude_style_and_scripts:
            tags.link(rel="stylesheet", href="style.css")
            tags.script(type="text/javascript", src="script.js")
        else:
            tags.style(raw(style))
            tags.script(raw(script), type="text/javascript")

    with doc:
        theme = str(report.get("theme", "light")).strip().lower()
        if theme not in {"light", "dark"}:
            theme = "light"
        doc.body["data-theme"] = theme
        tags.button("Back to Top", onclick="backToTop()", id="topButton", cls="floatingbutton")
        with tags.div(cls="intro-grid"):
            with tags.div(cls="intro-left", id="intro"):
                render_intro_left(report, overall_state=overall_state, suspicions=suspicions, src_path=verification_profile)
            with tags.div(cls="intro-right"):
                render_intro_right(report)
        ref_name = report.get("reference_name", "reference")
        prof_name = report.get("profile_name", "profile")
        for idx, (section_name, sec) in enumerate(iter_sections_issues_first(report)):
            render_module_card(section_name, sec, idx, ref_name=ref_name, prof_name=prof_name)

    out_dir = results_dir()
    os.makedirs(out_dir, exist_ok=True)
    out_path = str(out_dir / os.path.basename(output_file))
    slog.log_step("Writing HTML", str(out_dir))
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(str(doc))
    except Exception:
        slog.log_err("Failed to write HTML", out_path)
        return 1

    if not no_zip:
        try:
            zip_preparation(out_path, verification_profile, str(out_dir), str(JS_DIR), str(CSS_DIR), exclude_style_and_scripts)
        except Exception as e:
            slog.log_err(f"Failed to create zip: {e}")
    slog.log_ok("HTML report generated")
    return 0