# scrutiny-viz/verification/comparators/traceclassifier.py
from __future__ import annotations

from math import sqrt
from statistics import mean, variance
from typing import Any, Dict, List, Optional, Tuple

from .contracts import ComparatorPlugin, ComparatorSpec, CompareResult
from .utility import build_string_key_map, get_display_label, load_jsonish, max_state


T_95_ONE_SIDED = {
    1: 6.3138, 2: 2.9200, 3: 2.3534, 4: 2.1318, 5: 2.0150,
    6: 1.9432, 7: 1.8946, 8: 1.8595, 9: 1.8331, 10: 1.8125,
}
T_99_ONE_SIDED = {
    1: 31.8205, 2: 6.9646, 3: 4.5407, 4: 3.7469, 5: 3.3649,
    6: 3.1427, 7: 2.9980, 8: 2.8965, 9: 2.8214, 10: 2.7638,
}
T_95_TWO_SIDED = {
    1: 12.7062, 2: 4.3027, 3: 3.1824, 4: 2.7764, 5: 2.5706,
    6: 2.4469, 7: 2.3646, 8: 2.3060, 9: 2.2622, 10: 2.2281,
}
T_99_TWO_SIDED = {
    1: 63.6567, 2: 9.9248, 3: 5.8409, 4: 4.6041, 5: 4.0321,
    6: 3.7074, 7: 3.4995, 8: 3.3554, 9: 3.2498, 10: 3.1693,
}
DEAN_DIXON_COEFF = {
    2: 0.8862, 3: 0.5908, 4: 0.4857, 5: 0.4299, 6: 0.3946,
    7: 0.3698, 8: 0.3512, 9: 0.3367, 10: 0.3249,
}


def _t_value(df: int, table: Dict[int, float], fallback: float) -> float:
    if df <= 0:
        return fallback
    if df in table:
        return table[df]
    if df > max(table):
        return fallback
    nearest = max(k for k in table if k <= df)
    return table[nearest]


class TracesCompareComparator(ComparatorPlugin):
    spec = ComparatorSpec(
        name="tracescompare",
        aliases=("traces-comparer", "ptraces"),
        description="Comparator for scrutiny-power-traces-analyzer Traces comparer data.",
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
        ref_map = build_string_key_map(reference or [], key_field)
        profile_rows = [row for row in (tested or []) if isinstance(row, dict) and row.get(key_field) is not None]

        operation_results: List[Dict[str, Any]] = []
        labels: Dict[str, str] = {}
        diffs: List[Dict[str, Any]] = []
        matches: List[Dict[str, Any]] = []

        for profile_row in profile_rows:
            operation_code = str(profile_row.get(key_field))
            labels[operation_code] = get_display_label(profile_row, key_field, show_field)
            ref_row = ref_map.get(operation_code)
            if ref_row is None:
                continue

            result = self._compare_operation(ref_row, profile_row)
            operation_results.append(result)
            if result["comparison_state"] == "MATCH":
                matches.append({"key": operation_code, "field": "comparison_state", "value": "MATCH"})
            else:
                diffs.append({"key": operation_code, "field": "comparison_state", "ref": "MATCH", "test": result["comparison_state"]})

        counts = {
            "compared": len(operation_results),
            "changed": sum(1 for result in operation_results if result["comparison_state"] != "MATCH"),
            "matched": sum(1 for result in operation_results if result["comparison_state"] == "MATCH"),
            "only_ref": 0,
            "only_test": 0,
        }
        overall = max_state([result["comparison_state"] for result in operation_results])

        return {
            "section": section,
            "counts": counts,
            "stats": dict(counts),
            "labels": labels,
            "key_labels": labels,
            "diffs": diffs,
            "matches": matches,
            "source_rows": {"reference": reference or [], "profile": tested or []},
            "artifacts": {"operations": operation_results},
            "override_result": overall,
        }

    def _compare_operation(self, ref_row: Dict[str, Any], profile_row: Dict[str, Any]) -> Dict[str, Any]:
        ref_pipelines = load_jsonish(ref_row.get("pipeline_comparisons_json"), [])
        profile_pipelines = load_jsonish(profile_row.get("pipeline_comparisons_json"), [])
        ref_exec_times = load_jsonish(ref_row.get("execution_times_json"), [])
        profile_exec_times = load_jsonish(profile_row.get("execution_times_json"), [])
        operation_code = str(ref_row.get("operation_code") or profile_row.get("operation_code") or "")

        if not bool(profile_row.get("operation_present", True)):
            return {
                "operation_code": operation_code,
                "operation_present": False,
                "comparison_results": [],
                "exec_time_match_lower_bound": 0.0,
                "exec_time_match_upper_bound": 0.0,
                "exec_time_warn_lower_bound": 0.0,
                "exec_time_warn_upper_bound": 0.0,
                "exec_times": profile_exec_times,
                "comparison_state": "SUSPICIOUS",
            }

        pipeline_results: List[Dict[str, Any]] = []
        for ref_pipeline in ref_pipelines:
            pipeline_code = str(ref_pipeline.get("pipeline") or "")
            profile_pipeline = next((p for p in profile_pipelines if str(p.get("pipeline") or "") == pipeline_code), None)
            if profile_pipeline is None:
                continue

            metric_type = str(ref_pipeline.get("metric_type") or "distance")
            match_bound = self.get_metric_match_bound(ref_pipeline)
            warn_bound = self.get_metric_warn_bound(ref_pipeline)
            comparisons = []
            for comparison in profile_pipeline.get("comparisons") or []:
                distance_value = float(comparison.get("distance", 0.0) or 0.0)
                comparisons.append(
                    {
                        "distance_value": distance_value,
                        "image_path": str(comparison.get("file_path") or ""),
                        "image_name": str(comparison.get("file_name") or ""),
                        "comparison_state": self.get_state_measurement(distance_value, match_bound, warn_bound, metric_type),
                    }
                )

            pipeline_results.append(
                {
                    "pipeline_code": pipeline_code,
                    "match_bound": match_bound,
                    "warn_bound": warn_bound,
                    "metric_type": metric_type,
                    "comparison_state": self.get_state_comparison_results(comparisons),
                    "comparison_results": comparisons,
                }
            )

        exec_match_lb, exec_match_ub = self.get_exec_time_match_bound(ref_exec_times)
        exec_warn_lb, exec_warn_ub = self.get_exec_time_warn_bound(ref_exec_times)
        return {
            "operation_code": operation_code,
            "operation_present": True,
            "comparison_results": pipeline_results,
            "exec_time_match_lower_bound": exec_match_lb,
            "exec_time_match_upper_bound": exec_match_ub,
            "exec_time_warn_lower_bound": exec_warn_lb,
            "exec_time_warn_upper_bound": exec_warn_ub,
            "exec_times": profile_exec_times,
            "comparison_state": self.get_state_pipeline_results(pipeline_results),
        }

    def get_state_measurement(self, value: float, match_bound: float, warn_bound: float, metric_type: str) -> str:
        if metric_type == "distance":
            if value < match_bound:
                return "MATCH"
            if value < warn_bound:
                return "WARN"
            return "SUSPICIOUS"
        if value > match_bound:
            return "MATCH"
        if value > warn_bound:
            return "WARN"
        return "SUSPICIOUS"

    def get_state_comparison_results(self, comparison_results: List[Dict[str, Any]]) -> str:
        return max_state([str(row.get("comparison_state") or "MATCH") for row in comparison_results])

    def get_state_pipeline_results(self, pipeline_results: List[Dict[str, Any]]) -> str:
        return max_state([str(row.get("comparison_state") or "MATCH") for row in pipeline_results])

    def get_metric_warn_bound(self, ref_pipeline: Dict[str, Any]) -> float:
        values = [float(item.get("distance", 0.0) or 0.0) for item in (ref_pipeline.get("comparisons") or [])]
        return self._metric_bound(values, str(ref_pipeline.get("metric_type") or "distance"), "warn")

    def get_metric_match_bound(self, ref_pipeline: Dict[str, Any]) -> float:
        values = [float(item.get("distance", 0.0) or 0.0) for item in (ref_pipeline.get("comparisons") or [])]
        return self._metric_bound(values, str(ref_pipeline.get("metric_type") or "distance"), "match")

    def _metric_bound(self, values: List[float], metric_type: str, mode: str) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return float(values[0])

        sigma = self.get_sigma(values)
        df = len(values) - 1
        average = mean(values)
        qt = _t_value(df, T_95_ONE_SIDED if mode == "match" else T_99_ONE_SIDED, 1.645 if mode == "match" else 2.326)
        delta = (sigma / sqrt(len(values))) * qt
        return float(average + delta) if metric_type == "distance" else float(average - delta)

    def get_exec_time_warn_bound(self, exec_times: List[Dict[str, Any]]) -> Tuple[float, float]:
        values = [float(item.get("time", 0.0) or 0.0) for item in exec_times]
        return self._exec_time_bounds(values, "warn")

    def get_exec_time_match_bound(self, exec_times: List[Dict[str, Any]]) -> Tuple[float, float]:
        values = [float(item.get("time", 0.0) or 0.0) for item in exec_times]
        return self._exec_time_bounds(values, "match")

    def _exec_time_bounds(self, values: List[float], mode: str) -> Tuple[float, float]:
        if not values:
            return (0.0, 0.0)
        if len(values) == 1:
            value = float(values[0])
            return (value, value)

        sigma = self.get_sigma(values)
        df = len(values) - 1
        average = mean(values)
        qt = _t_value(df, T_95_TWO_SIDED if mode == "match" else T_99_TWO_SIDED, 1.960 if mode == "match" else 2.576)
        delta = (sigma / sqrt(len(values))) * qt
        return (float(average - delta), float(average + delta))

    def get_sigma(self, data: List[float]) -> float:
        count = len(data)
        if count <= 1:
            return 0.0
        if count > 10:
            return sqrt(variance(data))
        return (max(data) - min(data)) * DEAN_DIXON_COEFF.get(count, 1.0)


PLUGINS = [TracesCompareComparator()]
