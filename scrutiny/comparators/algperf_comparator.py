# scrutiny-viz/scrutiny/comparators/algperf.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from .interface import Comparator, CompareResult
from .registry import register


class AlgPerfComparator(Comparator):
    """
    JCAlgTest algorithm performance comparator (refactored).
    """

    KEY_AVG = "avg_ms"
    KEY_MIN = "min_ms"
    KEY_MAX = "max_ms"
    KEY_ERR = "error"

    @staticmethod
    def _num(val: Any) -> float | None:
        try:
            return float(val)
        except Exception:
            return None

    @staticmethod
    def _op(rv: float, tv: float) -> str:
        if rv == tv: return "=="
        return "<" if rv < tv else ">"

    def compare(
        self,
        *,
        section: str,
        key_field: str,
        show_field: Optional[str],
        metadata: Dict[str, Any],
        reference: List[Dict[str, Any]],
        tested: List[Dict[str, Any]]
    ) -> CompareResult:

        ref_map = {r.get(key_field): r for r in reference if isinstance(r, dict) and r.get(key_field) is not None}
        tst_map = {r.get(key_field): r for r in tested   if isinstance(r, dict) and r.get(key_field) is not None}
        keys = sorted(set(ref_map.keys()) | set(tst_map.keys()), key=lambda x: (str(type(x)), str(x)))

        diffs: List[Dict[str, Any]] = []
        matches: List[Dict[str, Any]] = [] if bool(metadata.get("include_matches", False)) else []
        labels: Dict[str, str] = {}
        chart_rows: List[Dict[str, Any]] = []

        compared = changed = matched = only_ref = only_test = 0

        for k in keys:
            r = ref_map.get(k)
            t = tst_map.get(k)

            # presence
            if r is None or t is None:
                if r is not None and t is None:
                    only_ref += 1
                    diffs.append({"key": str(k), "field": "__presence__", "ref": True, "op": "!=", "test": False})
                    chart_rows.append({"key": str(k), "status": "missing", "ref_avg": self._num(r.get(self.KEY_AVG)) if r else None,
                                       "test_avg": None, "delta_ms": None, "delta_pct": None, "note": "present only in reference"})
                elif t is not None and r is None:
                    only_test += 1
                    diffs.append({"key": str(k), "field": "__presence__", "ref": False, "op": "!=", "test": True})
                    chart_rows.append({"key": str(k), "status": "extra", "ref_avg": None,
                                       "test_avg": self._num(t.get(self.KEY_AVG)) if t else None, "delta_ms": None, "delta_pct": None,
                                       "note": "present only in profile"})
                continue

            # label
            lbl = r.get(show_field or key_field, r.get(key_field, k))
            labels[str(k)] = str(lbl)

            r_err = r.get(self.KEY_ERR, None)
            t_err = t.get(self.KEY_ERR, None)

            # error mismatch
            if r_err != t_err:
                changed += 1; compared += 1
                diffs.append({"key": str(k), "field": self.KEY_ERR, "ref": r_err, "op": "!=", "test": t_err})
                chart_rows.append({"key": str(k), "status": "error_mismatch", "ref_avg": None, "test_avg": None,
                                   "delta_ms": None, "delta_pct": None, "note": f"error ref={r_err} vs prof={t_err}"})
                continue

            # both error -> match
            if r_err is not None and t_err is not None:
                matched += 1; compared += 1
                if matches is not None:
                    matches.append({"key": str(k), "field": self.KEY_ERR, "value": r_err})
                chart_rows.append({"key": str(k), "status": "error", "ref_avg": None, "test_avg": None,
                                   "delta_ms": None, "delta_pct": None, "note": f"both failed: {r_err}"})
                continue

            # numeric success path
            r_avg = self._num(r.get(self.KEY_AVG)); t_avg = self._num(t.get(self.KEY_AVG))
            r_min = self._num(r.get(self.KEY_MIN)); r_max = self._num(r.get(self.KEY_MAX))

            if r_avg is None or t_avg is None:
                changed += 1; compared += 1
                diffs.append({"key": str(k), "field": self.KEY_AVG, "ref": r.get(self.KEY_AVG), "op": "!=", "test": t.get(self.KEY_AVG)})
                chart_rows.append({"key": str(k), "status": "data_error", "ref_avg": r_avg, "test_avg": t_avg,
                                   "delta_ms": None, "delta_pct": None, "note": "missing numeric avg"})
                continue

            # fast skip ≤ 2ms
            if r_avg <= 2.0 and t_avg <= 2.0:
                matched += 1; compared += 1
                if matches is not None:
                    matches.append({"key": str(k), "field": f"{self.KEY_AVG} (skipped)", "value": t_avg})
                chart_rows.append({"key": str(k), "status": "skipped", "ref_avg": r_avg, "test_avg": t_avg,
                                   "delta_ms": t_avg - r_avg, "delta_pct": (t_avg - r_avg) / r_avg * 100.0 if r_avg else None,
                                   "note": "both ≤ 2 ms"})
                continue

            avg_diff = abs(r_avg - t_avg)
            ref_spread = (r_max - r_min) if (r_max is not None and r_min is not None) else 0.0
            significant = (avg_diff > ref_spread) and (avg_diff > 0.2 * r_avg)
            is_clearkey = ("clearKey()" in str(k))

            if significant and not ((r_avg <= 10.0 and t_avg <= 10.0) or is_clearkey):
                changed += 1; compared += 1
                diffs.append({"key": str(k), "field": self.KEY_AVG, "ref": r_avg, "op": self._op(r_avg, t_avg), "test": t_avg})
                chart_rows.append({"key": str(k), "status": "mismatch", "ref_avg": r_avg, "test_avg": t_avg,
                                   "delta_ms": t_avg - r_avg, "delta_pct": (t_avg - r_avg) / r_avg * 100.0 if r_avg else None,
                                   "note": "significant diff"})
            else:
                matched += 1; compared += 1
                field_name = self.KEY_AVG if not (r_avg <= 10.0 and t_avg <= 10.0 or is_clearkey) else f"{self.KEY_AVG} (skipped)"
                if matches is not None:
                    matches.append({"key": str(k), "field": field_name, "value": t_avg})
                chart_rows.append({"key": str(k), "status": "match" if field_name == self.KEY_AVG else "skipped",
                                   "ref_avg": r_avg, "test_avg": t_avg,
                                   "delta_ms": t_avg - r_avg, "delta_pct": (t_avg - r_avg) / r_avg * 100.0 if r_avg else None,
                                   "note": "similar" if field_name == self.KEY_AVG else "fast op"})

        counts = {
            "compared": compared, "changed": changed, "matched": matched,
            "only_ref": only_ref, "only_test": only_test
        }

        return {
            "section": section,
            "counts": counts,
            "stats": counts,
            "labels": labels,
            "key_labels": labels,
            "diffs": diffs,
            **({"matches": matches} if matches else {}),
            "artifacts": {"chart_rows": chart_rows},
        }


# Self-register
register("algperf", AlgPerfComparator)
