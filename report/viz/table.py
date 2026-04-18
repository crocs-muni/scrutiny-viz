# scrutiny-viz/report/viz/table.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from dominate import tags

from .contracts import VizPlugin, VizSpec
from .utility import (
    comparison_similarity_percentages,
    first_token,
    format_number,
    format_percent,
    format_pp,
    operation_similarity_percentages,
    render_table_block,
    row_key,
    row_value,
    source_maps,
    state_badge,
    state_border_style,
    toggle_block,
)


def render_cplc_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    source_rows = section.get("source_rows") or {}
    ref_rows = source_rows.get("reference") or []
    test_rows = source_rows.get("tested") or source_rows.get("profile") or []

    ref_map: Dict[str, str] = {}
    test_map: Dict[str, str] = {}

    for row in ref_rows:
        if isinstance(row, dict):
            key = row_key(row)
            if key is not None:
                ref_map[key] = row_value(row)

    for row in test_rows:
        if isinstance(row, dict):
            key = row_key(row)
            if key is not None:
                test_map[key] = row_value(row)

    rows: List[List[Any]] = []
    for key in sorted(set(ref_map.keys()) | set(test_map.keys())):
        ref_value = ref_map.get(key, "Missing")
        test_value = test_map.get(key, "Missing")
        mismatch = (
            ref_value == "Missing"
            or test_value == "Missing"
            or first_token(ref_value) != first_token(test_value)
        )

        if mismatch:
            rows.append([
                key,
                tags.span(ref_value, style="font-weight:700;"),
                tags.span(test_value, style="font-weight:700;"),
            ])
        else:
            rows.append([key, ref_value, test_value])

    headers = ["CPLC Field", f"{ref_name} (reference)", f"{prof_name} (profiled)"]

    container = tags.div()
    with container:
        with toggle_block(
            block_id="cplc_table",
            title="CPLC table",
            button_text="Table",
            button_title="Show/hide table: CPLC",
            hide=False,
        ):
            render_table_block(headers, rows)

    return container

def render_rsabias_confusion_top_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    ref_map, test_map = source_maps(section, "edge_id")
    rows: List[List[Any]] = []

    for key in sorted(set(ref_map.keys()) | set(test_map.keys())):
        ref_row = ref_map.get(key, {})
        test_row = test_map.get(key, {})
        ref_value = ref_row.get("share_pct")
        test_value = test_row.get("share_pct")
        delta = (float(test_value) - float(ref_value)) if (ref_value is not None and test_value is not None) else None

        rows.append([
            ref_row.get("true_group", test_row.get("true_group", "")),
            ref_row.get("pred_group", test_row.get("pred_group", "")),
            format_percent(ref_value),
            format_percent(test_value),
            format_pp(delta),
        ])

    headers = ["True group", "Predicted group", f"{ref_name} share", f"{prof_name} share", "Δ share"]
    return render_table_block(headers, rows)

def render_rsabias_accuracy_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    ref_map, test_map = source_maps(section, "group")
    keys = sorted(
        set(ref_map.keys()) | set(test_map.keys()),
        key=lambda value: (0, int(value)) if str(value).isdigit() else (1, value),
    )

    rows: List[List[Any]] = []
    for key in keys:
        ref_row = ref_map.get(key, {})
        test_row = test_map.get(key, {})
        ref_value = ref_row.get("accuracy_pct")
        test_value = test_row.get("accuracy_pct")
        delta = (float(test_value) - float(ref_value)) if (ref_value is not None and test_value is not None) else None

        rows.append([
            key,
            ref_row.get("correct", ""),
            ref_row.get("wrong", ""),
            ref_row.get("total", ""),
            format_percent(ref_value),
            test_row.get("correct", ""),
            test_row.get("wrong", ""),
            test_row.get("total", ""),
            format_percent(test_value),
            format_pp(delta),
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
    ref_map, test_map = source_maps(section, "edge_id")
    rows: List[List[Any]] = []

    for key in sorted(set(ref_map.keys()) | set(test_map.keys())):
        ref_row = ref_map.get(key, {})
        test_row = test_map.get(key, {})
        ref_value = ref_row.get("share_pct")
        test_value = test_row.get("share_pct")
        delta = (float(test_value) - float(ref_value)) if (ref_value is not None and test_value is not None) else None

        rows.append([
            ref_row.get("true_group", test_row.get("true_group", "")),
            ref_row.get("pred_group", test_row.get("pred_group", "")),
            format_percent(ref_value),
            format_percent(test_value),
            format_pp(delta),
        ])

    headers = ["True group", "Predicted group", f"{ref_name} share", f"{prof_name} share", "Δ share"]
    return render_table_block(headers, rows)


def render_rsabias_matrix_top_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    artifacts = section.get("artifacts") or {}
    changes = artifacts.get("top_changed_cells") or []
    if not changes:
        return None

    rows: List[List[Any]] = []
    for change in changes:
        rows.append([
            change.get("row_label", change.get("row_index", "")),
            change.get("col_label", change.get("col_index", "")),
            format_percent(change.get("ref_value")),
            format_percent(change.get("profile_value")),
            format_pp(change.get("delta_pp")),
        ])

    headers = ["Row", "Column", f"{ref_name} value", f"{prof_name} value", "Δ value"]
    return render_table_block(headers, rows)


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
                "data-value": format_number(value, precision=4, trim=True),
            },
        ):
            if href:
                tags.img(
                    src=href,
                    alt=label,
                    loading="lazy",
                    _class="trace-thumb",
                    style=state_border_style(state),
                )
            else:
                tags.span(label, _class="trace-card-empty")

        tags.div(label, _class="trace-card-name", title=label)
        with tags.div(_class="trace-card-meta"):
            tags.span(f"value: {format_number(value, precision=4, trim=True)}", _class="trace-card-value")
            tags.span(state_badge(state), _class="trace-card-state")
    return box


def _pipeline_counts(comparisons: List[Dict[str, Any]]) -> tuple[int, int, int]:
    match_count = sum(1 for comp in comparisons if str(comp.get("comparison_state", "")).upper() == "MATCH")
    warn_count = sum(1 for comp in comparisons if str(comp.get("comparison_state", "")).upper() == "WARN")
    suspicious_count = sum(1 for comp in comparisons if str(comp.get("comparison_state", "")).upper() == "SUSPICIOUS")
    return match_count, warn_count, suspicious_count


def render_tracescompare_table(section: Dict[str, Any], ref_name: str, prof_name: str):
    artifacts = section.get("artifacts") or {}
    operations = artifacts.get("operations") or []
    if not operations:
        return None

    operations = sorted(
        operations,
        key=lambda op: (operation_similarity_percentages(op)[2], operation_similarity_percentages(op)[1]),
        reverse=True,
    )

    container = tags.div(_class="table-container")
    with container:
        tags.h3("Operation summary")
        summary_rows: List[List[Any]] = []
        for operation in operations:
            match_pct, warn_pct, suspicious_pct = operation_similarity_percentages(operation)
            summary_rows.append([
                operation.get("operation_code", ""),
                "yes" if operation.get("operation_present", False) else "no",
                state_badge(str(operation.get("comparison_state", ""))),
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

        for operation_idx, operation in enumerate(operations):
            operation_code = str(operation.get("operation_code", ""))
            tags.h3(f"Operation: {operation_code}")

            if not operation.get("operation_present", False):
                tags.p("This operation was not present in the new measured profile, however in the reference it was.")
                continue

            pipeline_results = operation.get("comparison_results") or []
            pipeline_results = sorted(
                pipeline_results,
                key=lambda pipe: (
                    comparison_similarity_percentages(pipe.get("comparison_results") or [])[2],
                    comparison_similarity_percentages(pipe.get("comparison_results") or [])[1],
                ),
                reverse=True,
            )

            pipeline_summary_rows: List[List[Any]] = []
            for pipeline in pipeline_results:
                comparisons = pipeline.get("comparison_results") or []
                match_count, warn_count, suspicious_count = _pipeline_counts(comparisons)
                pipeline_summary_rows.append([
                    str(pipeline.get("pipeline_code", "")),
                    str(pipeline.get("metric_type", "")),
                    format_number(pipeline.get("match_bound"), precision=4, trim=True),
                    format_number(pipeline.get("warn_bound"), precision=4, trim=True),
                    str(len(comparisons)),
                    str(match_count),
                    str(warn_count),
                    str(suspicious_count),
                    state_badge(str(pipeline.get("comparison_state", ""))),
                ])

            if pipeline_summary_rows:
                tags.h4("Pipeline summary")
                container.add(
                    render_table_block(
                        ["Pipeline", "Metric", "Match bound", "Warn bound", "Comparisons", "Match", "Warn", "Suspicious", "State"],
                        pipeline_summary_rows,
                    )
                )

            for pipeline_idx, pipeline in enumerate(pipeline_results):
                pipeline_code = str(pipeline.get("pipeline_code", ""))
                metric_type = str(pipeline.get("metric_type", ""))
                match_bound = format_number(pipeline.get("match_bound"), precision=4, trim=True)
                warn_bound = format_number(pipeline.get("warn_bound"), precision=4, trim=True)

                comparisons = pipeline.get("comparison_results") or []
                comparisons = sorted(
                    comparisons,
                    key=lambda row: float(row.get("distance_value", 0.0) or 0.0),
                    reverse=metric_type.lower() == "distance",
                )

                match_count, warn_count, suspicious_count = _pipeline_counts(comparisons)
                has_issues = (warn_count + suspicious_count) > 0

                tags.h4(f"Pipeline: {pipeline_code}")
                tags.p(
                    f"This pipeline uses metric '{metric_type}'. "
                    f"Match bound is {match_bound} and warn bound is {warn_bound}. "
                    f"Out of {len(comparisons)} comparisons, {match_count} are MATCH, "
                    f"{warn_count} are WARN, and {suspicious_count} are SUSPICIOUS. "
                    f"Overall pipeline state is {str(pipeline.get('comparison_state', ''))}."
                )

                photo_block_id = f"trace_photos_{operation_idx}_{pipeline_idx}"
                photo_title = f"Comparison photos (all: {len(comparisons)}, warn: {warn_count}, suspicious: {suspicious_count})"

                with toggle_block(
                    block_id=photo_block_id,
                    title=photo_title,
                    button_text="Photos",
                    button_title="Show/hide comparison photos",
                    hide=not has_issues,
                ):
                    with tags.div(_class="trace-filterbar", **{"data-trace-filterbar": photo_block_id, "data-active-filter": "all"}):
                        tags.button(f"All ({len(comparisons)})", type="button", _class="trace-filter-btn active", **{"data-filter": "all"})
                        tags.button(f"Issues ({warn_count + suspicious_count})", type="button", _class="trace-filter-btn", **{"data-filter": "issues"})
                        tags.button(f"Warn ({warn_count})", type="button", _class="trace-filter-btn", **{"data-filter": "warn"})
                        tags.button(f"Suspicious ({suspicious_count})", type="button", _class="trace-filter-btn", **{"data-filter": "suspicious"})
                        tags.button(f"Match ({match_count})", type="button", _class="trace-filter-btn", **{"data-filter": "match"})

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
            for exec_idx, exec_time in enumerate(operation.get("exec_times") or [], start=1):
                match_lower = float(operation.get("exec_time_match_lower_bound", 0.0) or 0.0)
                match_upper = float(operation.get("exec_time_match_upper_bound", 0.0) or 0.0)
                warn_lower = float(operation.get("exec_time_warn_lower_bound", 0.0) or 0.0)
                warn_upper = float(operation.get("exec_time_warn_upper_bound", 0.0) or 0.0)
                time_value = float(exec_time.get("time", 0.0) or 0.0)

                state = "SUSPICIOUS"
                if match_lower < time_value < match_upper:
                    state = "MATCH"
                elif warn_lower < time_value < warn_upper:
                    state = "WARN"

                exec_rows.append([
                    f"Execution time {exec_idx}",
                    f"({format_number(match_lower, precision=4, trim=True)}, {format_number(match_upper, precision=4, trim=True)})",
                    f"({format_number(warn_lower, precision=4, trim=True)}, {format_number(warn_upper, precision=4, trim=True)})",
                    f"{format_number(time_value, precision=4, trim=True)} {str(exec_time.get('unit', '')).strip()}".strip(),
                    state_badge(state),
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
    operations = artifacts.get("operations") or []

    # fallback to legacy cards structure if needed
    if not operations:
        cards = artifacts.get("cards") or []
        if not cards:
            return None

        operations = []
        for card in cards:
            for operation in card.get("operations") or []:
                image_path = str(operation.get("visualized_operations", "") or "")
                image_name = image_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] if image_path else ""
                operations.append(
                    {
                        "operation_code": operation.get("operation_code", ""),
                        "operation_present": operation.get("operation_found", False),
                        "comparison_results": [
                            {
                                "pipeline_code": "traceclassifier",
                                "match_bound": 0.0,
                                "warn_bound": 0.0,
                                "metric_type": str(operation.get("similarity_value_type", "")).lower(),
                                "comparison_state": str(operation.get("classification_state", "MATCH")),
                                "comparison_results": (
                                    [{
                                        "distance_value": operation.get("best_similarity_value", 0.0) or 0.0,
                                        "image_path": image_path,
                                        "image_name": image_name,
                                        "comparison_state": str(operation.get("classification_state", "MATCH")),
                                    }]
                                    if image_path else []
                                ),
                                "similarity_intervals": operation.get("similarity_intervals") or [],
                            }
                        ],
                        "exec_time_match_lower_bound": 0.0,
                        "exec_time_match_upper_bound": 0.0,
                        "exec_time_warn_lower_bound": 0.0,
                        "exec_time_warn_upper_bound": 0.0,
                        "exec_times": [],
                        "comparison_state": str(operation.get("classification_state", "MATCH")),
                        "interval_count": int(operation.get("interval_count", 0) or 0),
                        "best_similarity_value": operation.get("best_similarity_value"),
                        "similarity_value_type": operation.get("similarity_value_type", ""),
                        "similarity_intervals": operation.get("similarity_intervals") or [],
                        "image_path": image_path,
                        "image_name": image_name,
                    }
                )

    if not operations:
        return None

    container = tags.div(_class="table-container")
    with container:
        tags.h3("Classifier summary")

        summary_rows: List[List[Any]] = []
        for operation in operations:
            best_value = operation.get("best_similarity_value")
            summary_rows.append([
                operation.get("operation_code", ""),
                "yes" if operation.get("operation_present", False) else "no",
                str(operation.get("interval_count", 0)),
                "" if best_value is None else format_number(best_value, precision=4, trim=True),
                operation.get("similarity_value_type", ""),
                state_badge(str(operation.get("comparison_state", "MATCH"))),
            ])

        container.add(
            render_table_block(
                ["Operation", "Found", "Intervals", "Best similarity", "Type", "State"],
                summary_rows,
            )
        )

        for operation_idx, operation in enumerate(operations):
            if not operation.get("operation_present", False):
                continue

            operation_code = str(operation.get("operation_code", ""))
            best_value = operation.get("best_similarity_value")
            intervals = operation.get("similarity_intervals") or []
            pipeline_results = operation.get("comparison_results") or []

            tags.h4(f"Operation: {operation_code}")
            tags.p(
                f"Detected intervals: {len(intervals)} | "
                f"Best similarity: {'' if best_value is None else format_number(best_value, precision=4, trim=True)} | "
                f"Type: {str(operation.get('similarity_value_type', ''))} | "
                f"State: {str(operation.get('comparison_state', 'MATCH'))}"
            )

            comparisons: List[Dict[str, Any]] = []
            for pipeline in pipeline_results:
                comparisons.extend(pipeline.get("comparison_results") or [])

            if comparisons:
                photo_block_id = f"traceclassifier_photo_{operation_idx}"
                with toggle_block(
                    block_id=photo_block_id,
                    title="Classifier photo",
                    button_text="Photo",
                    button_title="Show/hide classifier image",
                    hide=False,
                ):
                    with tags.div(_class="trace-grid", **{"data-trace-grid": photo_block_id}):
                        first = comparisons[0]
                        tags.div().add(
                            _image_block(
                                str(first.get("image_path", "")),
                                str(first.get("image_name", "")),
                                str(first.get("comparison_state", "")),
                                first.get("distance_value", 0.0),
                            )
                        )

            if intervals:
                interval_rows: List[List[Any]] = []
                for interval in intervals:
                    interval_rows.append([
                        format_number(interval.get("time_from"), precision=4, trim=True),
                        format_number(interval.get("time_to"), precision=4, trim=True),
                        str(interval.get("similarity_value_type", "") or ""),
                        format_number(interval.get("similarity_value"), precision=4, trim=True),
                        int(interval.get("indexes_compared", 0) or 0),
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
    variant_name = (variant or "").strip().lower() if variant else None

    if variant_name == "cplc":
        return render_cplc_table(section, ref_name, prof_name)
    if variant_name == "rsabias_accuracy":
        return render_rsabias_accuracy_table(section, ref_name, prof_name)
    if variant_name == "rsabias_confusion_top":
        return render_rsabias_confusion_top_table(section, ref_name, prof_name)
    if variant_name == "rsabias_matrix_top":
        return render_rsabias_matrix_top_table(section, ref_name, prof_name)
    if variant_name == "tracescompare":
        return render_tracescompare_table(section, ref_name, prof_name)
    if variant_name == "traceclassifier":
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
