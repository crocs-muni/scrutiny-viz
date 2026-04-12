# scrutiny-viz/verification/comparators/algperf.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .contracts import ComparatorPlugin, ComparatorSpec, CompareResult
from .utility import build_row_map, get_display_label, sort_mixed_keys, to_float


class AlgPerfComparator(ComparatorPlugin):
    spec = ComparatorSpec(
        name="algperf",
        aliases=("jcalgperf", "performance"),
        description="Comparator for algorithm performance rows with avg/min/max/error semantics.",
    )

    KEY_AVG = "avg_ms"
    KEY_MIN = "min_ms"
    KEY_MAX = "max_ms"
    KEY_ERR = "error"

    @staticmethod
    def _op(ref_value: float, test_value: float) -> str:
        if ref_value == test_value:
            return "=="
        return "<" if ref_value < test_value else ">"

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
        ref_map = build_row_map(reference, key_field)
        test_map = build_row_map(tested, key_field)
        keys = sort_mixed_keys(set(ref_map.keys()) | set(test_map.keys()))

        include_matches = bool(metadata.get("include_matches", False))
        diffs: List[Dict[str, Any]] = []
        matches: List[Dict[str, Any]] = [] if include_matches else []
        labels: Dict[str, str] = {}
        chart_rows: List[Dict[str, Any]] = []

        compared = changed = matched = only_ref = only_test = 0

        for key in keys:
            ref_row = ref_map.get(key)
            test_row = test_map.get(key)

            if ref_row is None or test_row is None:
                if ref_row is not None:
                    only_ref += 1
                    diffs.append({"key": str(key), "field": "__presence__", "ref": True, "op": "!=", "test": False})
                    chart_rows.append(
                        {
                            "key": str(key),
                            "status": "missing",
                            "ref_avg": to_float(ref_row.get(self.KEY_AVG)),
                            "test_avg": None,
                            "delta_ms": None,
                            "delta_pct": None,
                            "note": "present only in reference",
                        }
                    )
                else:
                    only_test += 1
                    diffs.append({"key": str(key), "field": "__presence__", "ref": False, "op": "!=", "test": True})
                    chart_rows.append(
                        {
                            "key": str(key),
                            "status": "extra",
                            "ref_avg": None,
                            "test_avg": to_float(test_row.get(self.KEY_AVG)) if test_row else None,
                            "delta_ms": None,
                            "delta_pct": None,
                            "note": "present only in profile",
                        }
                    )
                continue

            labels[str(key)] = get_display_label(ref_row, key_field, show_field)

            ref_error = ref_row.get(self.KEY_ERR)
            test_error = test_row.get(self.KEY_ERR)
            compared += 1

            if ref_error != test_error:
                changed += 1
                diffs.append({"key": str(key), "field": self.KEY_ERR, "ref": ref_error, "op": "!=", "test": test_error})
                chart_rows.append(
                    {
                        "key": str(key),
                        "status": "error_mismatch",
                        "ref_avg": None,
                        "test_avg": None,
                        "delta_ms": None,
                        "delta_pct": None,
                        "note": f"error ref={ref_error} vs prof={test_error}",
                    }
                )
                continue

            if ref_error is not None:
                matched += 1
                if include_matches:
                    matches.append({"key": str(key), "field": self.KEY_ERR, "value": ref_error})
                chart_rows.append(
                    {
                        "key": str(key),
                        "status": "error",
                        "ref_avg": None,
                        "test_avg": None,
                        "delta_ms": None,
                        "delta_pct": None,
                        "note": f"both failed: {ref_error}",
                    }
                )
                continue

            ref_avg = to_float(ref_row.get(self.KEY_AVG))
            test_avg = to_float(test_row.get(self.KEY_AVG))
            ref_min = to_float(ref_row.get(self.KEY_MIN))
            ref_max = to_float(ref_row.get(self.KEY_MAX))

            if ref_avg is None or test_avg is None:
                changed += 1
                diffs.append(
                    {
                        "key": str(key),
                        "field": self.KEY_AVG,
                        "ref": ref_row.get(self.KEY_AVG),
                        "op": "!=",
                        "test": test_row.get(self.KEY_AVG),
                    }
                )
                chart_rows.append(
                    {
                        "key": str(key),
                        "status": "data_error",
                        "ref_avg": ref_avg,
                        "test_avg": test_avg,
                        "delta_ms": None,
                        "delta_pct": None,
                        "note": "missing numeric avg",
                    }
                )
                continue

            delta_ms = test_avg - ref_avg
            delta_pct = (delta_ms / ref_avg * 100.0) if ref_avg else None
            is_fast_op = ref_avg <= 2.0 and test_avg <= 2.0
            is_clearkey = "clearKey()" in str(key)
            small_op_skip = (ref_avg <= 10.0 and test_avg <= 10.0) or is_clearkey
            ref_spread = (ref_max - ref_min) if (ref_max is not None and ref_min is not None) else 0.0
            significant = abs(delta_ms) > ref_spread and abs(delta_ms) > 0.2 * ref_avg

            if is_fast_op:
                matched += 1
                if include_matches:
                    matches.append({"key": str(key), "field": f"{self.KEY_AVG} (skipped)", "value": test_avg})
                chart_rows.append(
                    {
                        "key": str(key),
                        "status": "skipped",
                        "ref_avg": ref_avg,
                        "test_avg": test_avg,
                        "delta_ms": delta_ms,
                        "delta_pct": delta_pct,
                        "note": "both ≤ 2 ms",
                    }
                )
                continue

            if significant and not small_op_skip:
                changed += 1
                diffs.append({"key": str(key), "field": self.KEY_AVG, "ref": ref_avg, "op": self._op(ref_avg, test_avg), "test": test_avg})
                chart_rows.append(
                    {
                        "key": str(key),
                        "status": "mismatch",
                        "ref_avg": ref_avg,
                        "test_avg": test_avg,
                        "delta_ms": delta_ms,
                        "delta_pct": delta_pct,
                        "note": "significant diff",
                    }
                )
                continue

            matched += 1
            match_field = self.KEY_AVG if not small_op_skip else f"{self.KEY_AVG} (skipped)"
            if include_matches:
                matches.append({"key": str(key), "field": match_field, "value": test_avg})
            chart_rows.append(
                {
                    "key": str(key),
                    "status": "match" if match_field == self.KEY_AVG else "skipped",
                    "ref_avg": ref_avg,
                    "test_avg": test_avg,
                    "delta_ms": delta_ms,
                    "delta_pct": delta_pct,
                    "note": "similar" if match_field == self.KEY_AVG else "fast op",
                }
            )

        counts = {
            "compared": compared,
            "changed": changed,
            "matched": matched,
            "only_ref": only_ref,
            "only_test": only_test,
        }
        result: CompareResult = {
            "section": section,
            "counts": counts,
            "stats": counts,
            "labels": labels,
            "key_labels": labels,
            "diffs": diffs,
            "artifacts": {"chart_rows": chart_rows},
        }
        if include_matches:
            result["matches"] = matches
        return result


PLUGINS = [AlgPerfComparator()]
