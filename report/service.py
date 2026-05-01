# scrutiny-viz/report/service.py
from __future__ import annotations

import json
import os
import re
import zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dominate import document, tags
from dominate.util import raw

from scrutiny import logging as slog
from scrutiny.errors import ReportError, ScrutinyError
from scrutiny.interfaces import ContrastState
from scrutiny.paths import REPORT_ASSETS_DIR, results_dir
from scrutiny.validation import read_json_file

from report.bundle import prepare_report_bundle
from report.viz import registry as viz_registry
from report.viz.table import render_table_block

log = slog.get_logger("REPORT")

JS_DIR = REPORT_ASSETS_DIR / "script.js"
CSS_DIR = REPORT_ASSETS_DIR / "style.css"

TOOLTIP_TEXT = {
    ContrastState.MATCH: "Devices seem to match",
    ContrastState.WARN: "There seem to be some differences worth checking",
    ContrastState.SUSPICIOUS: "Devices probably don't match",
}

RESULT_TEXT = {
    ContrastState.MATCH: lambda count: "None of the modules raised suspicion during the verification process.",
    ContrastState.WARN: lambda count: f"There seem to be some differences worth checking. {count} module(s) report inconsistencies.",
    ContrastState.SUSPICIOUS: lambda count: (
        f"{count} module(s) report suspicious differences between profiled and reference devices. "
        "The verification process may have been unsuccessful and compared devices are different."
    ),
}

_ID_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")
_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOOLISH_STRINGS = {"true", "false", "yes", "no", "supported", "unsupported", "1", "0"}


def safe_id(value: str) -> str:
    return _ID_PATTERN.sub("_", value)


def state_enum(value: str) -> ContrastState:
    try:
        return ContrastState[value]
    except Exception:
        return ContrastState.WARN


def iter_sections_issues_first(report: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    issues: List[Tuple[str, Dict[str, Any]]] = []
    matches: List[Tuple[str, Dict[str, Any]]] = []

    for name, section in (report.get("sections") or {}).items():
        state = state_enum(section.get("result", "WARN"))
        if state == ContrastState.MATCH:
            matches.append((name, section))
        else:
            issues.append((name, section))
    return issues + matches


def render_status_dot_link(*, section_name: str, state: ContrastState, target_id: str):
    tooltip_text = TOOLTIP_TEXT.get(state, "")
    with tags.a(cls="dot " + state.name.lower(), href=f"#{target_id}", title=section_name):
        label = f"{section_name} — {tooltip_text}" if tooltip_text else section_name
        tags.span(label, cls="tooltiptext " + state.name.lower())


def table(headers: Iterable[str], rows: Iterable[Iterable[Any]]):
    return render_table_block(list(headers), list(rows))


def badge(text: str, kind: str) -> tags.span:
    return tags.span(text, cls=f"badge badge-{kind}")


def bool_to_badge(value: Any) -> tags.span:
    if isinstance(value, bool):
        return badge("Supported", "ok") if value else badge("Unsupported", "bad")
    lowered = str(value).strip().lower()
    if lowered in {"true", "yes", "supported"}:
        return badge("Supported", "ok")
    if lowered in {"false", "no", "unsupported"}:
        return badge("Unsupported", "bad")
    return badge("Unknown", "neutral")


def is_boolish_value(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if value is None:
        return False
    return str(value).strip().lower() in _BOOLISH_STRINGS


def is_support_field(field: Any) -> bool:
    return str(field or "").strip().lower() in {"is_supported", "issupported", "supported"}


def display_key(raw_key: Any, labels: Dict[str, str]) -> str:
    try:
        return labels.get(str(raw_key), str(raw_key))
    except Exception:
        return str(raw_key)


def fast_summary(stats_or_counts: Dict[str, Any]) -> str:
    stats = stats_or_counts or {}
    compared = int(stats.get("compared", 0) or 0)
    changed = int(stats.get("changed", 0) or 0)
    only_ref = int(stats.get("only_ref", 0) or 0)
    only_test = int(stats.get("only_test", 0) or 0)
    return (f"Compared {compared} items. "
        f"Differences: {changed}. "
        f"Missing on profile: {only_ref}. "
        f"Extra on profile: {only_test}.")


def render_info_icon(tooltip_text: str, *, wide: bool = False) -> tags.span:
    tooltip_cls = "tooltiptext info" if wide else "tooltiptext"
    with tags.span(cls="circle circle-small"):
        tags.span("i")
        tags.span(tooltip_text, cls=tooltip_cls)


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
        for match in _LINK_PATTERN.finditer(text):
            if match.start() > pos:
                tags.span(text[pos:match.start()])
            label = (match.group(1) or "").strip() or (match.group(2) or "").strip()
            href = (match.group(2) or "").strip()
            if href:
                tags.a(label, href=href, target="_blank", rel="noopener noreferrer")
            else:
                tags.span(label)
            pos = match.end()
        if pos < len(text):
            tags.span(text[pos:])


def render_doc_text(doc_text: str) -> None:
    if not doc_text:
        return
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", str(doc_text).replace("\r\n", "\n"))]
    for chunk in chunks:
        if chunk:
            _render_paragraph_with_links(chunk)


def normalize_report_types(report_cfg: Dict[str, Any]) -> List[Tuple[str, Optional[str]]]:
    out: List[Tuple[str, Optional[str]]] = []
    for raw_type in report_cfg.get("types") or []:
        if raw_type is None:
            continue
        if isinstance(raw_type, dict):
            type_name = str(raw_type.get("type") or "").strip().lower()
            if not type_name:
                continue
            variant = raw_type.get("variant")
            variant = str(variant).strip().lower() if variant is not None and str(variant).strip() else None
            out.append((type_name, variant))
        else:
            type_name = str(raw_type).strip().lower()
            if type_name:
                out.append((type_name, None))
    return out


def _filter_tuple_for_label(item: Any, key_label: str) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    filtered = {key: value for key, value in item.items() if str(value) != str(key_label)}
    return filtered if filtered else dict(item)


def _tuple_value_text(item: Any, key_label: str) -> str:
    if item is None:
        return ""
    if not isinstance(item, dict):
        return str(item)
    filtered = _filter_tuple_for_label(item, key_label)
    if len(filtered) == 1:
        key, value = next(iter(filtered.items()))
        return f"{key} {value}"
    return ", ".join(f"{key} {value}" for key, value in filtered.items())


def pair_group_changes(removed: List[Dict[str, Any]], added: List[Dict[str, Any]]):
    out = []
    removed_items = removed[:]
    added_items = added[:]
    while removed_items and added_items:
        out.append(("arrow", removed_items.pop(0), added_items.pop(0)))
    for item in removed_items:
        out.append(("removed", item, None))
    for item in added_items:
        out.append(("added", None, item))
    return out


def format_group_value(value: Any) -> tags.span:
    if value is None:
        return tags.span("matched", cls="badge badge-ok")
    if isinstance(value, dict):
        parts = []
        for field, field_value in value.items():
            if isinstance(field_value, (list, tuple, set)):
                parts.append(f"{field}: {', '.join(str(x) for x in field_value)}")
            else:
                parts.append(f"{field}: {field_value}")
        return tags.span("; ".join(parts))
    if isinstance(value, (list, tuple, set)):
        return tags.span(", ".join(str(x) for x in value))
    return tags.span(str(value))


def extract_buckets_for_report(section: Dict[str, Any]) -> Dict[str, Any]:
    labels: Dict[str, str] = (section.get("key_labels") or section.get("labels")) or {}
    diffs = section.get("diffs", []) or []

    boolean_rows_raw = []
    string_rows_raw = []
    missing_rows = []
    extra_rows = []
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    for diff in diffs:
        field = diff.get("field")
        key_raw = diff.get("key")
        item_label = display_key(key_raw, labels)

        if field == "__presence__":
            if diff.get("ref") and not diff.get("test"):
                missing_rows.append([item_label, "present in reference only"])
            elif diff.get("test") and not diff.get("ref"):
                extra_rows.append([item_label, "present in profile only"])
            continue

        if field == "__group__":
            group_bucket = grouped.setdefault(str(key_raw), {"removed": [], "added": []})
            if diff.get("ref") is not None and diff.get("test") is None:
                group_bucket["removed"].append(diff.get("ref"))
            elif diff.get("ref") is None and diff.get("test") is not None:
                group_bucket["added"].append(diff.get("test"))
            continue

        ref_value = diff.get("ref")
        test_value = diff.get("test")
        if is_support_field(field) and is_boolish_value(ref_value) and is_boolish_value(test_value):
            boolean_rows_raw.append((item_label, field, ref_value, test_value))
        elif isinstance(ref_value, bool) or isinstance(test_value, bool):
            boolean_rows_raw.append((item_label, field, ref_value, test_value))
        else:
            string_rows_raw.append((item_label, field, ref_value, test_value))

    for group_key, group_vals in grouped.items():
        item_label = display_key(group_key, labels)
        for kind, removed_item, added_item in pair_group_changes(group_vals["removed"], group_vals["added"]):
            if kind == "arrow":
                ref_dict = _filter_tuple_for_label(removed_item, item_label)
                test_dict = _filter_tuple_for_label(added_item, item_label)
                field_name = ", ".join(sorted(set(ref_dict.keys()) | set(test_dict.keys()))) or "set"
                string_rows_raw.append(
                    (
                        item_label,
                        field_name,
                        _tuple_value_text(removed_item, item_label),
                        _tuple_value_text(added_item, item_label),
                    )
                )
            elif kind == "removed":
                missing_rows.append([item_label, _tuple_value_text(removed_item, item_label)])
            else:
                extra_rows.append([item_label, _tuple_value_text(added_item, item_label)])

    distinct_fields = sorted({field for (_, field, _, _) in string_rows_raw})
    include_field_col = len(distinct_fields) > 1

    boolean_rows = [
        [item, bool_to_badge(ref_value), bool_to_badge(test_value)]
        for item, _field, ref_value, test_value in sorted(boolean_rows_raw, key=lambda row: row[0])
    ]

    if include_field_col:
        string_rows = [
            [item, field, ref_value, test_value]
            for item, field, ref_value, test_value in sorted(string_rows_raw, key=lambda row: (row[0], row[1]))
        ]
    else:
        string_rows = [
            [item, ref_value, test_value]
            for item, _field, ref_value, test_value in sorted(string_rows_raw, key=lambda row: row[0])
        ]

    return {
        "boolean_rows": boolean_rows,
        "string_rows": string_rows,
        "string_include_field": include_field_col,
        "missing_rows": sorted(missing_rows, key=lambda row: row[0]),
        "extra_rows": sorted(extra_rows, key=lambda row: row[0]),
    }


def _add_rendered_node(node: Any) -> None:
    if node is None:
        return
    if isinstance(node, (list, tuple)):
        for sub_node in node:
            _add_rendered_node(sub_node)
        return
    tags.div().add(node)


def _render_viz_plugin(
    name: str,
    *,
    section_name: str,
    section: Dict[str, Any],
    idx: int,
    ref_name: str,
    prof_name: str,
    variant: str | None = None,
) -> Any:
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
        tags.span(state.name, style="font-weight:bold;")

    report_cfg = section.get("report") or {}
    doc_text = (report_cfg.get("doc_text") or "").strip()
    if doc_text:
        with tags.div(cls="module-doc"):
            render_doc_text(doc_text)

    tags.p(fast_summary(section.get("stats") or section.get("counts") or {}))

    types_ordered = normalize_report_types(report_cfg)
    known_types = set(viz_registry.list_types())
    viz_types = [(type_name, variant) for type_name, variant in types_ordered if type_name != "table" and type_name in known_types]

    if viz_types:
        with toggle_block(
            block_id=f"section_{idx}_perf",
            title="Visualizations",
            button_text="Viz",
            button_title="Show/hide visualizations",
            hide=(state == ContrastState.MATCH),
        ):
            for type_name, variant in viz_types:
                _add_rendered_node(
                    _render_viz_plugin(
                        type_name,
                        section_name=section_name,
                        section=section,
                        idx=idx,
                        ref_name=ref_name,
                        prof_name=prof_name,
                        variant=variant,
                    )
                )

    table_variant = next((variant for type_name, variant in types_ordered if type_name == "table"), None)
    if table_variant is not None or any(type_name == "table" for type_name, _variant in types_ordered):
        node = _render_viz_plugin(
            "table",
            section_name=section_name,
            section=section,
            idx=idx,
            ref_name=ref_name,
            prof_name=prof_name,
            variant=table_variant,
        )
        if node is not None:
            tags.div().add(node)
            tags.hr()
            return

        buckets = extract_buckets_for_report(section)
        divname = f"section_{idx}"

        if buckets["boolean_rows"]:
            with toggle_block(
                block_id=f"{divname}_bool",
                title="Boolean / binary differences",
                button_text="Table",
                button_title="Show/hide table: Boolean / binary differences",
                hide=False,
            ):
                tags.p(
                    "If a capability is supported by the reference but not by the profile (or vice versa), the cards likely do not match.",
                    cls="hint",
                )
                table(["Item", "Reference", "Profile"], buckets["boolean_rows"])

        if buckets["string_rows"]:
            with toggle_block(
                block_id=f"{divname}_strings",
                title="Differences in string fields",
                button_text="Table",
                button_title="Show/hide table: Differences in string fields",
                hide=False,
            ):
                headers = ["Item", "Field", "Reference", "Profile"] if buckets["string_include_field"] else ["Item", "Reference", "Profile"]
                table(headers, buckets["string_rows"])

        if buckets["missing_rows"]:
            with toggle_block(
                block_id=f"{divname}_missing",
                title="Missing on profile (present in reference)",
                button_text="Table",
                button_title="Show/hide table: Missing on profile",
                hide=(state == ContrastState.MATCH),
            ):
                table(["Item", "Detail"], buckets["missing_rows"])

        if buckets["extra_rows"]:
            with toggle_block(
                block_id=f"{divname}_extra",
                title="Extra on profile (absent in reference)",
                button_text="Table",
                button_title="Show/hide table: Extra on profile",
                hide=(state == ContrastState.MATCH),
            ):
                table(["Item", "Detail"], buckets["extra_rows"])

        if section.get("matches"):
            with toggle_block(
                block_id=f"{divname}_matches",
                title="Matches",
                button_text="Table",
                button_title="Show/hide table: Matches",
                hide=True,
            ):
                rows = []
                labels = (section.get("key_labels") or section.get("labels") or {})
                for match in section["matches"]:
                    item = display_key(match.get("key"), labels)
                    field = match.get("field")
                    value = match.get("value")
                    if field != "__group__" and value is not None and str(value) == str(item):
                        continue
                    if field == "__group__":
                        pretty_field = "set"
                        value_node = format_group_value(value)
                    else:
                        pretty_field = field
                        field_lower = str(field or "").strip().lower()
                        if field_lower in {"is_supported", "issupported", "supported"} and is_boolish_value(value):
                            value_node = bool_to_badge(value)
                        else:
                            value_node = bool_to_badge(value) if isinstance(value, bool) else tags.span("" if value is None else str(value))
                    rows.append([item, pretty_field, value_node])

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
        with tags.span(
            cls="circle",
            style=(
                "margin-left:8px; background:#333; color:#fff; width:18px; height:18px; line-height:18px; "
                "text-align:center; border-radius:50%; display:inline-block; position:relative; font-size:12px;"
            ),
        ):
            tags.span("i")
            with tags.span(cls="tooltiptext info", style="left:0; transform:translateX(-20%);"):
                tags.strong("Result: ")
                tags.span(RESULT_TEXT[overall_state](suspicions))
                tags.br()
                tags.br()
                tags.strong("Methodology: ")
                tags.span(
                    "WARN when changes are below configured thresholds; SUSPICIOUS when changed/compared exceeds "
                    "the ratio threshold or the change count exceeds the count threshold."
                )

    with tags.div(id="modules"):
        for name, section in iter_sections_issues_first(report):
            render_status_dot_link(section_name=name, state=state_enum(section.get("result", "WARN")), target_id=safe_id(name))
        with tags.div(cls="dot-legend"):
            with tags.span(cls="legend-item"):
                tags.span("", cls="legend-dot match")
                tags.span("Match")
            with tags.span(cls="legend-item"):
                tags.span("", cls="legend-dot warn")
                tags.span("Warn")
            with tags.span(cls="legend-item"):
                tags.span("", cls="legend-dot suspicious")
                tags.span("Suspicious")

    tags.h3("Quick visibility settings")
    tags.button("Show All", onclick="showAllToggles()")
    tags.button("Hide All", onclick="hideAllToggles()")
    tags.button("Default", onclick="defaultToggles()")

    sections = [name for name, _section in iter_sections_issues_first(report)]
    if sections:
        with tags.div():
            tags.label("Jump to module: ", _for="jumpMod")
            select = tags.select(id="jumpMod", onchange="location.hash=this.value")
            for name in sections:
                select.add(tags.option(name, value=safe_id(name)))

    meta = report.get("meta", {}) or {}
    schema_title = meta.get("schema_title")
    details_id = "intro_details"
    with tags.div(cls="intro-details-bar"):
        tags.button(
            "Details",
            cls="toggle-btn",
            title="Show/hide details about inputs and generation",
            onclick=f"hideButton('{details_id}')",
            **{"data-toggle-target": details_id, "aria-expanded": "false"},
        )
    with tags.div(id=details_id, cls="toggle-block", style="display:none;", **{"data-default": "hide"}):
        with tags.div(cls="intro-meta"):
            tags.p(f"Generated on: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            tags.p(f"Generated from: {src_path}")
            tags.p(f"Reference label: {ref_name}")
            tags.p(f"Profile label: {prof_name}")
            if schema_title:
                tags.p(f"Schema: {schema_title}")


def render_intro_right(report: Dict[str, Any]):
    dashboard = report.get("dashboard", {}) or {}
    overall_counts = dashboard.get("overall_state_counts", {}) or {}

    total_matched = 0
    total_diffs = 0
    total_compared = 0
    for section in (report.get("sections", {}) or {}).values():
        stats = section.get("stats") or section.get("counts") or {}
        total_matched += int(stats.get("matched", 0) or 0)
        total_diffs += int(stats.get("changed", 0) or 0) + int(stats.get("only_ref", 0) or 0) + int(stats.get("only_test", 0) or 0)
        total_compared += int(stats.get("compared", 0) or 0)

    donut_plugin = viz_registry.get_plugin("donut")
    tip_modules = "Overall modules: counts how many modules ended as Match/Warn/Suspicious (one verdict per module)."
    tip_results = "Overall results: aggregates all compared items across modules: matches vs differences (including missing/extra)."

    with tags.div(_class="donut-stack"):
        wrap1 = tags.div(cls="donut-card-wrap")
        wrap1.add(
            donut_plugin.render(
                title="Overall modules",
                counts=overall_counts,
                segments=["MATCH", "WARN", "SUSPICIOUS"],
                radius=52,
                stroke=18,
                center_label=str(sum(int(overall_counts.get(k, 0) or 0) for k in ("MATCH", "WARN", "SUSPICIOUS"))),
                legend_labels={"MATCH": "Match", "WARN": "Warn", "SUSPICIOUS": "Suspicious"},
                variant=None,
            )
        )
        with wrap1:
            render_info_icon(tip_modules)

        wrap2 = tags.div(cls="donut-card-wrap")
        wrap2.add(
            donut_plugin.render(
                title="Overall results (matches vs diffs)",
                counts={"MATCH": total_matched, "WARN": total_diffs},
                segments=["MATCH", "WARN"],
                radius=52,
                stroke=18,
                center_label=str(total_compared),
                legend_labels={"MATCH": "Matches", "WARN": "Diffs"},
                variant=None,
            )
        )
        with wrap2:
            render_info_icon(tip_results)

        with tags.div(_class="kpi-row"):
            with tags.div(_class="kpi"):
                tags.div("Compared items", _class="kpi-title")
                tags.div(str(total_compared), _class="kpi-value")
            with tags.div(_class="kpi"):
                tags.div("Total diffs", _class="kpi-title")
                tags.div(str(total_diffs), _class="kpi-value")


def _zip_add_tree(zip_file: zipfile.ZipFile, root_path: str, arc_prefix: str) -> None:
    root = Path(root_path).resolve()
    if not root.exists() or not root.is_dir():
        return

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        arcname = f"{arc_prefix.rstrip('/')}/{rel}" if rel else arc_prefix.rstrip("/")
        zip_file.write(path, arcname=arcname)


def zip_preparation(
    html_report_path: str,
    verification_profile_path: str,
    out_dir: str,
    js_path: str,
    css_path: str,
    link_mode: bool,
    assets_dir: str | None = None,
) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    zip_path = os.path.join(out_dir, f"results_{timestamp}.zip")

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(html_report_path, arcname=os.path.basename(html_report_path))
        zip_file.write(verification_profile_path, arcname=os.path.basename(verification_profile_path))

        if link_mode:
            zip_file.write(js_path, arcname="script.js")
            zip_file.write(css_path, arcname="style.css")

        if assets_dir:
            assets_root = Path(assets_dir).resolve()
            if assets_root.exists() and assets_root.is_dir():
                _zip_add_tree(zip_file, str(assets_root), assets_root.name)

    return zip_path


def _fail(exit_code: int, error: str) -> Dict[str, Any]:
    return {"ok": False, "exit_code": int(exit_code), "error": str(error)}


def _load_text_file(path: Path, *, kind: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return "\n" + handle.read() + "\n"
    except Exception:
        log.err(f"Failed to load {kind}: {path}")
        return ""


def _load_report_json(verification_profile: str) -> Dict[str, Any] | None:
    log.step("Loading report JSON", verification_profile)
    payload = read_json_file(verification_profile, label="Verification profile JSON", component="REPORT")
    if not isinstance(payload, dict):
        raise ReportError(f"Verification profile JSON must contain an object at top level: {verification_profile}")
    return payload


def run_report_html(
    *,
    verification_profile: str,
    output_file: str = "comparison.html",
    exclude_style_and_scripts: bool = False,
    no_zip: bool = False,
) -> Dict[str, Any]:
    try:
        report = _load_report_json(verification_profile)
    except ScrutinyError as exc:
        return _fail(getattr(exc, "exit_code", 1), str(exc))

    out_dir = results_dir()
    os.makedirs(out_dir, exist_ok=True)
    out_path = (out_dir / os.path.basename(output_file)).resolve()

    bundle_result = prepare_report_bundle(
        report,
        source_report_path=verification_profile,
        html_output_path=out_path,
    )
    report = bundle_result["report"]

    if bundle_result.get("tracecompare_detected", False):
        log.info(
            "tracecompare detected: "
            f"copied={bundle_result.get('copied_assets', 0)}, "
            f"rewritten={bundle_result.get('rewritten_paths', 0)}, "
            f"missing={bundle_result.get('missing_assets', 0)}"
        )

    overall_state = state_enum(report.get("overall", "WARN"))
    suspicions = sum(
        1
        for section in report.get("sections", {}).values()
        if state_enum(section.get("result", "WARN")).value >= ContrastState.WARN.value
    )
    log.info(f"Overall state: {overall_state.name}")

    log.step("Loading JS")
    script = _load_text_file(JS_DIR, kind="JS")
    log.step("Loading CSS")
    style = _load_text_file(CSS_DIR, kind="CSS")

    viz_registry.discover_builtin_viz(force=True)
    log.step("Rendering HTML document")
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
                render_intro_left(
                    report,
                    overall_state=overall_state,
                    suspicions=suspicions,
                    src_path=verification_profile,
                )
            with tags.div(cls="intro-right"):
                render_intro_right(report)

        ref_name = report.get("reference_name", "reference")
        prof_name = report.get("profile_name", "profile")
        for idx, (section_name, section) in enumerate(iter_sections_issues_first(report)):
            render_module_card(section_name, section, idx, ref_name=ref_name, prof_name=prof_name)

    log.step("Writing HTML", str(out_dir))
    try:
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(str(doc))
    except Exception:
        log.err(f"Failed to write HTML: {out_path}")
        return _fail(1, f"Failed to write HTML: {out_path}")

    bundled_json_path = bundle_result.get("bundled_json_path")
    json_for_zip = str(Path(bundled_json_path).resolve()) if bundled_json_path else verification_profile
    assets_dir = bundle_result.get("assets_dir")
    assets_dir_str = str(Path(assets_dir).resolve()) if assets_dir else None

    zip_path: str | None = None
    if not no_zip:
        try:
            zip_path = zip_preparation(
                str(out_path),
                json_for_zip,
                str(out_dir),
                str(JS_DIR),
                str(CSS_DIR),
                exclude_style_and_scripts,
                assets_dir=assets_dir_str,
            )
        except Exception as exc:
            log.err(f"Failed to create zip: {exc}")

    return {
        "ok": True,
        "exit_code": 0,
        "html_path": str(out_path),
        "zip_path": str(Path(zip_path).resolve()) if zip_path else None,
    }
