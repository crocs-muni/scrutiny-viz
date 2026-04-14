# scrutiny-viz/verification/comparators/traceclassifier.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .contracts import ComparatorPlugin, ComparatorSpec, CompareResult
from .utility import get_display_label, load_jsonish, max_state


class TraceClassifierComparator(ComparatorPlugin):
    spec = ComparatorSpec(
        name="traceclassifier",
        aliases=("trace-classifier", "powerclassifier", "classifier"),
        description="Comparator/adapter for already-classified power trace results.",
    )

    def compare(
        self,
        *,
        section: str,
        key_field: str,
        show_field: Optional[str],
        metadata: Dict[str, Any],
        reference: List[Dict[str, Any]],
        tested: List[Dict[str, Any]],
    ) -> CompareResult:
        profile_rows = [
            row for row in (tested or [])
            if isinstance(row, dict) and row.get(key_field) is not None
        ]

        operation_results: List[Dict[str, Any]] = []
        labels: Dict[str, str] = {}
        diffs: List[Dict[str, Any]] = []
        matches: List[Dict[str, Any]] = []
        cards_map: Dict[str, List[Dict[str, Any]]] = {}

        for row in profile_rows:
            operation_code = str(row.get(key_field))
            labels[operation_code] = get_display_label(row, key_field, show_field)

            result = self._compare_operation(row=row, metadata=metadata or {})
            operation_results.append(result)

            if result["comparison_state"] == "MATCH":
                matches.append(
                    {
                        "key": operation_code,
                        "field": "comparison_state",
                        "value": "MATCH",
                    }
                )
            else:
                diffs.append(
                    {
                        "key": operation_code,
                        "field": "comparison_state",
                        "ref": "MATCH",
                        "test": result["comparison_state"],
                    }
                )

            card_code = str(row.get("card_code") or "")
            cards_map.setdefault(card_code, []).append(
                {
                    "operation_code": result["operation_code"],
                    "operation_found": result["operation_present"],
                    "interval_count": result["interval_count"],
                    "best_similarity_value": result["best_similarity_value"],
                    "similarity_value_type": result["similarity_value_type"],
                    "classification_state": result["comparison_state"],
                    "visualized_operations": result["image_path"],
                    "similarity_intervals": result["similarity_intervals"],
                }
            )

        cards = []
        for card_code, operations in cards_map.items():
            card_states = [
                str(op.get("classification_state") or "MATCH")
                for op in operations
                if op.get("operation_found")
            ]
            cards.append(
                {
                    "card_code": card_code,
                    "card_state": max_state(card_states, default="SUSPICIOUS"),
                    "operations": operations,
                }
            )

        counts = {
            "compared": len(operation_results),
            "changed": sum(1 for result in operation_results if result["comparison_state"] != "MATCH"),
            "matched": sum(1 for result in operation_results if result["comparison_state"] == "MATCH"),
            "only_ref": 0,
            "only_test": 0,
        }
        overall = max_state([result["comparison_state"] for result in operation_results], default="SUSPICIOUS")

        return {
            "section": section,
            "counts": counts,
            "stats": dict(counts),
            "labels": labels,
            "key_labels": labels,
            "diffs": diffs,
            "matches": matches,
            "source_rows": {"reference": reference or [], "profile": tested or []},
            "artifacts": {
                "operations": operation_results,
                "cards": cards,  # backward compatibility
            },
            "override_result": overall,
        }

    def _compare_operation(self, *, row: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        operation_code = str(row.get("operation_code") or "")
        found = bool(row.get("operation_found", False))
        metric_type = str(row.get("similarity_value_type") or "")
        best_value = row.get("best_similarity_value")
        intervals = load_jsonish(row.get("similarity_intervals_json"), [])
        interval_count = int(row.get("interval_count", len(intervals)) or 0)

        operation_state = self._classify_operation(
            found=found,
            best_value=best_value,
            metric_type=metric_type,
            metadata=metadata,
        )

        image_path = str(
            row.get("visualized_operations_path")
            or row.get("visualized_operations")
            or ""
        ).strip()
        image_name = str(
            row.get("visualized_operations_name")
            or (Path(image_path).name if image_path else "")
        ).strip()

        match_bound, warn_bound = self._classifier_bounds(metric_type=metric_type, metadata=metadata)

        comparison_rows: List[Dict[str, Any]] = []
        if image_path:
            comparison_rows.append(
                {
                    "distance_value": self._safe_float(best_value),
                    "image_path": image_path,
                    "image_name": image_name,
                    "comparison_state": operation_state,
                }
            )

        pipeline_results: List[Dict[str, Any]] = []
        if found or comparison_rows or intervals:
            pipeline_results.append(
                {
                    "pipeline_code": "traceclassifier",
                    "match_bound": match_bound,
                    "warn_bound": warn_bound,
                    "metric_type": str(metric_type or "").lower(),
                    "comparison_state": operation_state,
                    "comparison_results": comparison_rows,
                    "similarity_intervals": intervals,
                }
            )

        return {
            "operation_code": operation_code,
            "operation_present": found,
            "comparison_results": pipeline_results,
            "exec_time_match_lower_bound": 0.0,
            "exec_time_match_upper_bound": 0.0,
            "exec_time_warn_lower_bound": 0.0,
            "exec_time_warn_upper_bound": 0.0,
            "exec_times": [],
            "comparison_state": operation_state,
            "interval_count": interval_count,
            "best_similarity_value": best_value,
            "similarity_value_type": metric_type,
            "similarity_intervals": intervals,
            "image_path": image_path,
            "image_name": image_name,
        }

    def _classifier_bounds(self, *, metric_type: str, metadata: Dict[str, Any]) -> tuple[float, float]:
        metric = str(metric_type or "").upper()

        if metric in {"CORRELATION", "SIMILARITY"}:
            match_bound = float(metadata.get("match_similarity_min", 0.98) or 0.98)
            warn_bound = float(metadata.get("warn_similarity_min", 0.95) or 0.95)
            return match_bound, warn_bound

        match_bound = float(metadata.get("match_distance_max", 45.0) or 45.0)
        warn_bound = float(metadata.get("warn_distance_max", 55.0) or 55.0)
        return match_bound, warn_bound

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    def _classify_operation(
        self,
        *,
        found: bool,
        best_value: Any,
        metric_type: str,
        metadata: Dict[str, Any],
    ) -> str:
        if not found:
            return "MATCH"

        metric = str(metric_type or "").upper()
        try:
            numeric_value = float(best_value)
        except Exception:
            return "WARN"

        if metric in {"CORRELATION", "SIMILARITY"}:
            match_min = float(metadata.get("match_similarity_min", 0.98) or 0.98)
            warn_min = float(metadata.get("warn_similarity_min", 0.95) or 0.95)
            if numeric_value >= match_min:
                return "MATCH"
            if numeric_value >= warn_min:
                return "WARN"
            return "SUSPICIOUS"

        match_max = float(metadata.get("match_distance_max", 45.0) or 45.0)
        warn_max = float(metadata.get("warn_distance_max", 55.0) or 55.0)
        if numeric_value <= match_max:
            return "MATCH"
        if numeric_value <= warn_max:
            return "WARN"
        return "SUSPICIOUS"


PLUGIN = TraceClassifierComparator()
PLUGINS = [PLUGIN]
