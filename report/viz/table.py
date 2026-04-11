# scrutiny-viz/report/viz/table.py
from __future__ import annotations
import json
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
from dominate import tags

from .contracts import VizPlugin, VizSpec

def _loads_json(raw: Any) -> Any:
    if raw is None:
        return []
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(str(raw))
    except Exception:
        return []

def render_table_block(headers: List[str], rows: List[List[Any]]):
    container = tags.div(_class="table-container")
    with container:
        t = tags.table(_class="report-table")
        with t:
            with tags.thead():
                with tags.tr():
                    for h in headers:
                        tags.th(str(h))
            with tags.tbody():
                for r in rows or []:
                    cells = r if isinstance(r, (list, tuple)) else [r]
                    with tags.tr():
                        for c in cells:
                            if hasattr(c, "__html__") or hasattr(c, "render"):
                                tags.td(c)
                            else:
                                tags.td(str(c))
    return container


def _first_token(s: str) -> str:
    s = (s or "").strip()
    return s.split()[0] if s else ""


def _row_key(row: Dict[str, Any]) -> str | None:
    if not isinstance(row, dict):
        return None
    for key_name in ("field", "name", "key", "group", "edge_id", "cell_id"):
        v = row.get(key_name)
        if v is not None:
            return str(v)
    return None


def _row_value(row: Dict[str, Any]) -> str:
    if not isinstance(row, dict):
        return ""
    v = row.get("value")
    return "" if v is None else str(v)


def _fmt_pct(v: Any) -> str:
    if v is None:
        return ""
    try:
        return f"{float(v):.4f}%"
    except Exception:
        return str(v)


def _fmt_pp(v: Any) -> str:
    if v is None:
        return ""
    try:
        return f"{float(v):+.4f} pp"
    except Exception:
        return str(v)


def _fmt_num(v: Any) -> str:
    if v is None:
        return ""
    try:
        return f"{float(v):.8f}"
    except Exception:
        return str(v)


def _source_maps(section: Dict[str, Any], key_field: str) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    src = section.get("source_rows") or {}
    ref_rows = src.get("reference") or []
    tst_rows = src.get("tested") or src.get("profile") or []

    ref_map: Dict[str, Dict[str, Any]] = {}
    tst_map: Dict[str, Dict[str, Any]] = {}

    for r in ref_rows:
        if isinstance(r, dict) and r.get(key_field) is not None:
            ref_map[str(r[key_field])] = r
    for r in tst_rows:
        if isinstance(r, dict) and r.get(key_field) is not None:
            tst_map[str(r[key_field])] = r

    return ref_map, tst_map


def render_cplc_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    src = section.get("source_rows") or {}
    ref_rows = src.get("reference") or []
    tst_rows = src.get("tested") or src.get("profile") or []

    ref_map: Dict[str, str] = {}
    tst_map: Dict[str, str] = {}
    for r in ref_rows:
        if isinstance(r, dict):
            k = _row_key(r)
            if k is not None:
                ref_map[k] = _row_value(r)
    for r in tst_rows:
        if isinstance(r, dict):
            k = _row_key(r)
            if k is not None:
                tst_map[k] = _row_value(r)

    keys = sorted(set(ref_map.keys()) | set(tst_map.keys()))
    rows: List[List[Any]] = []
    for k in keys:
        rv = ref_map.get(k, "Missing")
        tv = tst_map.get(k, "Missing")
        mismatch = (rv == "Missing" or tv == "Missing" or _first_token(rv) != _first_token(tv))
        if mismatch:
            rv_node = tags.span(rv, style="font-weight:700;")
            tv_node = tags.span(tv, style="font-weight:700;")
            rows.append([k, rv_node, tv_node])
        else:
            rows.append([k, rv, tv])

    headers = ["CPLC Field", f"{ref_name} (reference)", f"{prof_name} (profiled)"]
    return render_table_block(headers, rows)


def render_rsabias_accuracy_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    ref_map, tst_map = _source_maps(section, "group")
    keys = sorted(set(ref_map.keys()) | set(tst_map.keys()), key=lambda x: (0, int(x)) if str(x).isdigit() else (1, x))

    rows: List[List[Any]] = []
    for k in keys:
        rr = ref_map.get(k, {})
        tr = tst_map.get(k, {})
        rv = rr.get("accuracy_pct")
        tv = tr.get("accuracy_pct")
        delta = (float(tv) - float(rv)) if (rv is not None and tv is not None) else None

        rows.append([
            k,
            rr.get("correct", ""),
            rr.get("wrong", ""),
            rr.get("total", ""),
            _fmt_pct(rv),
            tr.get("correct", ""),
            tr.get("wrong", ""),
            tr.get("total", ""),
            _fmt_pct(tv),
            _fmt_pp(delta),
        ])

    headers = [
        "Group",
        f"{ref_name} correct",
        f"{ref_name} wrong",
        f"{ref_name} total",
        f"{ref_name} accuracy",
        f"{prof_name} correct",
        f"{prof_name} wrong",
        f"{prof_name} total",
        f"{prof_name} accuracy",
        "Δ accuracy",
    ]
    return render_table_block(headers, rows)


def render_rsabias_confusion_top_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    ref_map, tst_map = _source_maps(section, "edge_id")
    keys = sorted(set(ref_map.keys()) | set(tst_map.keys()))

    rows: List[List[Any]] = []
    for k in keys:
        rr = ref_map.get(k, {})
        tr = tst_map.get(k, {})
        rv = rr.get("share_pct")
        tv = tr.get("share_pct")
        delta = (float(tv) - float(rv)) if (rv is not None and tv is not None) else None

        true_group = rr.get("true_group", tr.get("true_group", ""))
        pred_group = rr.get("pred_group", tr.get("pred_group", ""))

        rows.append([
            true_group,
            pred_group,
            _fmt_pct(rv),
            _fmt_pct(tv),
            _fmt_pp(delta),
        ])

    headers = ["True group", "Predicted group", f"{ref_name} share", f"{prof_name} share", "Δ share"]
    return render_table_block(headers, rows)


def render_rsabias_matrix_top_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    artifacts = section.get("artifacts") or {}
    changes = artifacts.get("top_changed_cells") or []
    if not changes:
        return None

    rows: List[List[Any]] = []
    for ch in changes:
        rows.append([
            ch.get("row_label", ch.get("row_index", "")),
            ch.get("col_label", ch.get("col_index", "")),
            _fmt_pct((float(ch["ref_value"]) * 100.0) / 100.0) if ch.get("ref_value") is not None else "",
            _fmt_pct((float(ch["profile_value"]) * 100.0) / 100.0) if ch.get("profile_value") is not None else "",
            _fmt_pp(ch.get("delta_pp")),
        ])

    headers = ["Row", "Column", f"{ref_name} value", f"{prof_name} value", "Δ value"]
    return render_table_block(headers, rows)


def _state_badge(state: str):
    s = str(state or "").upper()
    cls = "badge badge-neutral"
    if s == "MATCH":
        cls = "badge badge-ok"
    elif s == "WARN":
        cls = "badge badge-warn"
    elif s == "SUSPICIOUS":
        cls = "badge badge-bad"
    return tags.span(s or "UNKNOWN", cls=cls)


def _state_style(state: str) -> str:
    s = str(state or "").upper()
    if s == "MATCH":
        return "border:2px solid var(--green-color);"
    if s == "WARN":
        return "border:2px solid var(--yellow-color);"
    return "border:2px solid var(--red-color);"


def _comparison_similarity_percentages(comparison_results: List[Dict[str, Any]]) -> tuple[float, float, float]:
    if not comparison_results:
        return (0.0, 0.0, 0.0)
    total = float(len(comparison_results))
    match = sum(1 for r in comparison_results if str(r.get("comparison_state", "")).upper() == "MATCH") / total * 100.0
    warn = sum(1 for r in comparison_results if str(r.get("comparison_state", "")).upper() == "WARN") / total * 100.0
    suspicious = sum(1 for r in comparison_results if str(r.get("comparison_state", "")).upper() == "SUSPICIOUS") / total * 100.0
    return (match, warn, suspicious)


def _operation_similarity_percentages(operation: Dict[str, Any]) -> tuple[float, float, float]:
    pipeline_results = operation.get("comparison_results") or []
    if not pipeline_results:
        return (0.0, 0.0, 0.0)

    sums = [0.0, 0.0, 0.0]
    for pipeline in pipeline_results:
        m, w, s = _comparison_similarity_percentages(pipeline.get("comparison_results") or [])
        sums[0] += m
        sums[1] += w
        sums[2] += s

    n = float(len(pipeline_results))
    return (sums[0] / n, sums[1] / n, sums[2] / n)


def _image_block(image_path: str, image_name: str, state: str, value: Any):
    label = image_name or image_path or "image"
    href = image_path or ""
    state_up = str(state or "").upper()

    box = tags.div(_class="trace-card", **{"data-state": state_up.lower()})
    with box:
        with tags.a(
            href=href,
            target="_blank",
            rel="noopener noreferrer",
            _class="trace-preview-link",
            title=label,
            **{
                "data-fullsrc": href,
                "data-fullname": label,
                "data-state": state_up.lower(),
                "data-value": f"{round(float(value), 4)}",
            },
        ):
            if href:
                tags.img(
                    src=href,
                    alt=label,
                    loading="lazy",
                    _class="trace-thumb",
                    style=_state_style(state),
                )
            else:
                tags.span(label, _class="trace-card-empty")

        tags.div(label, _class="trace-card-name", title=label)

        with tags.div(_class="trace-card-meta"):
            tags.span(f"value: {round(float(value), 4)}", _class="trace-card-value")
            tags.span(_state_badge(state), _class="trace-card-state")

    return box


@contextmanager
def _trace_toggle_block(*, block_id: str, title: str, button_text: str, button_title: str | None = None, hide: bool = False):
    with tags.div(cls="toggle-header"):
        tags.h5(title, cls="toggle-title")
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


def render_tracescompare_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    artifacts = section.get("artifacts") or {}
    operations = artifacts.get("operations") or []
    if not operations:
        return None

    operations = sorted(
        operations,
        key=lambda op: (_operation_similarity_percentages(op)[2], _operation_similarity_percentages(op)[1]),
        reverse=True,
    )

    container = tags.div(_class="table-container")
    with container:
        tags.h3("Operation summary")
        summary_rows: List[List[Any]] = []
        for op in operations:
            match_pct, warn_pct, suspicious_pct = _operation_similarity_percentages(op)
            summary_rows.append([
                op.get("operation_code", ""),
                "yes" if op.get("operation_present", False) else "no",
                _state_badge(str(op.get("comparison_state", ""))),
                f"{match_pct:.2f}%",
                f"{warn_pct:.2f}%",
                f"{suspicious_pct:.2f}%",
            ])
        container.add(
            render_table_block(
                ["Operation", "Present in profile", "State", "Match", "Warn", "Suspicious"],
                summary_rows,
            )
        )

        for op_idx, op in enumerate(operations):
            op_code = str(op.get("operation_code", ""))
            tags.h3(f"Operation: {op_code}")

            if not op.get("operation_present", False):
                tags.p("This operation was not present in the new measured profile, however in the reference it was.")
                continue

            pipeline_results = op.get("comparison_results") or []
            pipeline_results = sorted(
                pipeline_results,
                key=lambda p: (
                    _comparison_similarity_percentages(p.get("comparison_results") or [])[2],
                    _comparison_similarity_percentages(p.get("comparison_results") or [])[1],
                ),
                reverse=True,
            )

            # one compact table per operation summarizing all pipelines
            pipeline_summary_rows: List[List[Any]] = []
            for pipeline in pipeline_results:
                pipeline_code = str(pipeline.get("pipeline_code", ""))
                metric_type = str(pipeline.get("metric_type", ""))
                match_bound = round(float(pipeline.get("match_bound", 0.0) or 0.0), 4)
                warn_bound = round(float(pipeline.get("warn_bound", 0.0) or 0.0), 4)
                comparisons = pipeline.get("comparison_results") or []

                match_count = sum(1 for c in comparisons if str(c.get("comparison_state", "")).upper() == "MATCH")
                warn_count = sum(1 for c in comparisons if str(c.get("comparison_state", "")).upper() == "WARN")
                suspicious_count = sum(1 for c in comparisons if str(c.get("comparison_state", "")).upper() == "SUSPICIOUS")

                pipeline_summary_rows.append([
                    pipeline_code,
                    metric_type,
                    str(match_bound),
                    str(warn_bound),
                    str(len(comparisons)),
                    str(match_count),
                    str(warn_count),
                    str(suspicious_count),
                    _state_badge(str(pipeline.get("comparison_state", ""))),
                ])

            if pipeline_summary_rows:
                tags.h4("Pipeline summary")
                container.add(
                    render_table_block(
                        ["Pipeline", "Metric", "Match bound", "Warn bound", "Comparisons", "Match", "Warn", "Suspicious", "State"],
                        pipeline_summary_rows,
                    )
                )

            # now each pipeline gets explanation + photos only
            for pipe_idx, pipeline in enumerate(pipeline_results):
                pipeline_code = str(pipeline.get("pipeline_code", ""))
                metric_type = str(pipeline.get("metric_type", ""))
                match_bound = round(float(pipeline.get("match_bound", 0.0) or 0.0), 4)
                warn_bound = round(float(pipeline.get("warn_bound", 0.0) or 0.0), 4)

                comparisons = pipeline.get("comparison_results") or []
                comparisons = sorted(
                    comparisons,
                    key=lambda r: float(r.get("distance_value", 0.0) or 0.0),
                    reverse=metric_type.lower() == "distance",
                )

                match_count = sum(1 for c in comparisons if str(c.get("comparison_state", "")).upper() == "MATCH")
                warn_count = sum(1 for c in comparisons if str(c.get("comparison_state", "")).upper() == "WARN")
                suspicious_count = sum(1 for c in comparisons if str(c.get("comparison_state", "")).upper() == "SUSPICIOUS")
                has_issues = (warn_count + suspicious_count) > 0

                tags.h4(f"Pipeline: {pipeline_code}")
                tags.p(
                    f"This pipeline uses metric '{metric_type}'. "
                    f"Match bound is {match_bound} and warn bound is {warn_bound}. "
                    f"Out of {len(comparisons)} comparisons, {match_count} are MATCH, "
                    f"{warn_count} are WARN, and {suspicious_count} are SUSPICIOUS. "
                    f"Overall pipeline state is {str(pipeline.get('comparison_state', ''))}."
                )

                photo_block_id = f"trace_photos_{op_idx}_{pipe_idx}"
                photo_title = (
                    f"Comparison photos "
                    f"(all: {len(comparisons)}, warn: {warn_count}, suspicious: {suspicious_count})"
                )

                with _trace_toggle_block(
                    block_id=photo_block_id,
                    title=photo_title,
                    button_text="Photos",
                    button_title="Show/hide comparison photos",
                    hide=not has_issues,
                ):
                    with tags.div(_class="trace-filterbar", **{"data-trace-filterbar": photo_block_id, "data-active-filter": "all"}):
                        tags.button(
                            f"All ({len(comparisons)})",
                            type="button",
                            _class="trace-filter-btn active",
                            **{"data-filter": "all"},
                        )
                        tags.button(
                            f"Issues ({warn_count + suspicious_count})",
                            type="button",
                            _class="trace-filter-btn",
                            **{"data-filter": "issues"},
                        )
                        tags.button(
                            f"Warn ({warn_count})",
                            type="button",
                            _class="trace-filter-btn",
                            **{"data-filter": "warn"},
                        )
                        tags.button(
                            f"Suspicious ({suspicious_count})",
                            type="button",
                            _class="trace-filter-btn",
                            **{"data-filter": "suspicious"},
                        )
                        tags.button(
                            f"Match ({match_count})",
                            type="button",
                            _class="trace-filter-btn",
                            **{"data-filter": "match"},
                        )

                    with tags.div(_class="trace-grid", **{"data-trace-grid": photo_block_id}) as grid:
                        for comparison in comparisons:
                            grid.add(
                                _image_block(
                                    str(comparison.get("image_path", "")),
                                    str(comparison.get("image_name", "")),
                                    str(comparison.get("comparison_state", "")),
                                    comparison.get("distance_value", 0.0),
                                )
                            )

                tags.br()

            tags.h4("Execution times section")
            exec_rows: List[List[Any]] = []
            exec_times = op.get("exec_times") or []
            for idx, et in enumerate(exec_times, start=1):
                etmlb = float(op.get("exec_time_match_lower_bound", 0.0) or 0.0)
                etmub = float(op.get("exec_time_match_upper_bound", 0.0) or 0.0)
                etwlb = float(op.get("exec_time_warn_lower_bound", 0.0) or 0.0)
                etwub = float(op.get("exec_time_warn_upper_bound", 0.0) or 0.0)
                time_value = float(et.get("time", 0.0) or 0.0)

                state = "SUSPICIOUS"
                if etmlb < time_value < etmub:
                    state = "MATCH"
                elif etwlb < time_value < etwub:
                    state = "WARN"

                exec_rows.append([
                    f"Execution time {idx}",
                    f"({round(etmlb, 4)}, {round(etmub, 4)})",
                    f"({round(etwlb, 4)}, {round(etwub, 4)})",
                    f"{round(time_value, 4)} {str(et.get('unit', '')).strip()}".strip(),
                    _state_badge(state),
                ])

            if exec_rows:
                container.add(
                    render_table_block(
                        ["Measurement", "Match bounds", "Warn bounds", "Execution time value", "State"],
                        exec_rows,
                    )
                )

    return container

def render_traceclassifier_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    artifacts = section.get("artifacts") or {}
    cards = artifacts.get("cards") or []
    if not cards:
        return None

    container = tags.div(_class="table-container")
    with container:
        tags.h3("Classifier summary")

        summary_rows: List[List[Any]] = []
        for card in cards:
            operations = card.get("operations") or []
            found_count = sum(1 for op in operations if op.get("operation_found"))
            summary_rows.append([
                card.get("card_code", ""),
                str(len(operations)),
                str(found_count),
                _state_badge(str(card.get("card_state", "MATCH"))),
            ])

        container.add(
            render_table_block(
                ["Card", "Operations", "Found", "State"],
                summary_rows,
            )
        )

        for card in cards:
            card_code = str(card.get("card_code", ""))
            operations = card.get("operations") or []

            tags.h3(f"Card: {card_code}")

            op_rows: List[List[Any]] = []
            for op in operations:
                best_val = op.get("best_similarity_value")
                best_text = "" if best_val is None else str(round(float(best_val), 4))
                op_rows.append([
                    op.get("operation_code", ""),
                    "yes" if op.get("operation_found", False) else "no",
                    str(op.get("interval_count", 0)),
                    best_text,
                    op.get("similarity_value_type", ""),
                    _state_badge(str(op.get("classification_state", "MATCH"))),
                ])

            container.add(
                render_table_block(
                    ["Operation", "Found", "Intervals", "Best similarity", "Type", "State"],
                    op_rows,
                )
            )

            for op in operations:
                if not op.get("operation_found", False):
                    continue

                operation_code = str(op.get("operation_code", ""))
                best_val = op.get("best_similarity_value")
                best_text = "" if best_val is None else str(round(float(best_val), 4))
                metric_type = str(op.get("similarity_value_type", ""))
                image_path = str(op.get("visualized_operations", "") or "")
                intervals = op.get("similarity_intervals") or []

                tags.h4(f"Operation: {operation_code}")
                tags.p(
                    f"Detected intervals: {len(intervals)} | "
                    f"Best similarity: {best_text} | "
                    f"Type: {metric_type} | "
                    f"State: {str(op.get('classification_state', 'MATCH'))}"
                )

                if image_path:
                    tags.img(
                        src=image_path,
                        alt=image_path,
                        style="display:block;width:100%;margin:8px 0 12px 0;border:1px solid var(--table-border);border-radius:8px;",
                    )

                if intervals:
                    interval_rows: List[List[Any]] = []
                    for it in intervals:
                        interval_rows.append([
                            round(float(it.get("time_from", 0.0) or 0.0), 4),
                            round(float(it.get("time_to", 0.0) or 0.0), 4),
                            str(it.get("similarity_value_type", "") or ""),
                            round(float(it.get("similarity_value", 0.0) or 0.0), 4),
                            int(it.get("indexes_compared", 0) or 0),
                        ])

                    container.add(
                        render_table_block(
                            ["Time from", "Time to", "Comparison type", "Comparison value", "Indexes compared"],
                            interval_rows,
                        )
                    )
                    tags.br()

    return container

def render_table_variant(*, section_name: str, section: Dict[str, Any], ref_name: str, prof_name: str, variant: Optional[str] = None):
    v = (variant or "").strip().lower() if variant else None

    if v == "cplc":
        return render_cplc_table(section, ref_name, prof_name)
    if v == "rsabias_accuracy":
        return render_rsabias_accuracy_table(section, ref_name, prof_name)
    if v == "rsabias_confusion_top":
        return render_rsabias_confusion_top_table(section, ref_name, prof_name)
    if v == "rsabias_matrix_top":
        return render_rsabias_matrix_top_table(section, ref_name, prof_name)
    if v == "tracescompare":
        return render_tracescompare_table(section, ref_name, prof_name)
    if v == "traceclassifier":
        return render_traceclassifier_table(section, ref_name, prof_name)

    return None


class TableVizPlugin(VizPlugin):
    spec = VizSpec(
        name="table",
        slot="table",
        aliases=(),
        description="Section table renderer, including specialized variants like CPLC, RSABias views, and Traces comparer.",
    )

    def render(self, **kwargs: Any) -> Any:
        return render_table_variant(
            section_name=kwargs["section_name"],
            section=kwargs["section"],
            ref_name=kwargs["ref_name"],
            prof_name=kwargs["prof_name"],
            variant=kwargs.get("variant"),
        )


PLUGINS = [TableVizPlugin()]