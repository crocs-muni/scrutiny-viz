# scrutiny-viz/verification/comparators/traceclassifier.py
from __future__ import annotations

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
        profile_rows = [row for row in (tested or []) if isinstance(row, dict) and row.get(key_field) is not None]

        labels: Dict[str, str] = {}
        diffs: List[Dict[str, Any]] = []
        matches: List[Dict[str, Any]] = []
        cards_map: Dict[str, List[Dict[str, Any]]] = {}
        found_states: List[str] = []

        for row in profile_rows:
            operation_code = str(row.get(key_field))
            card_code = str(row.get("card_code") or "")
            labels[operation_code] = get_display_label(row, key_field, show_field)

            intervals = load_jsonish(row.get("similarity_intervals_json"), [])
            found = bool(row.get("operation_found", False))
            metric_type = str(row.get("similarity_value_type") or "")
            best_value = row.get("best_similarity_value")
            operation_state = self._classify_operation(
                found=found,
                best_value=best_value,
                metric_type=metric_type,
                metadata=metadata or {},
            )

            if found:
                found_states.append(operation_state)

            target = matches if operation_state == "MATCH" else diffs
            payload: Dict[str, Any]
            if operation_state == "MATCH":
                payload = {"key": operation_code, "field": "classification_state", "value": "MATCH"}
            else:
                payload = {"key": operation_code, "field": "classification_state", "ref": "MATCH", "test": operation_state}
            target.append(payload)

            cards_map.setdefault(card_code, []).append(
                {
                    "operation_code": operation_code,
                    "operation_found": found,
                    "interval_count": int(row.get("interval_count", len(intervals)) or 0),
                    "best_similarity_value": best_value,
                    "similarity_value_type": metric_type,
                    "classification_state": operation_state,
                    "visualized_operations": str(row.get("visualized_operations") or ""),
                    "similarity_intervals": intervals,
                }
            )

        cards = []
        for card_code, operations in cards_map.items():
            card_states = [str(op.get("classification_state") or "MATCH") for op in operations if op.get("operation_found")]
            cards.append({"card_code": card_code, "card_state": max_state(card_states, default="SUSPICIOUS"), "operations": operations})

        changed = sum(1 for diff in diffs if str(diff.get("test") or "").upper() != "MATCH")
        counts = {
            "compared": len(profile_rows),
            "changed": changed,
            "matched": max(0, len(profile_rows) - changed),
            "only_ref": 0,
            "only_test": 0,
        }

        return {
            "section": section,
            "result": max_state(found_states, default="SUSPICIOUS") if found_states else "SUSPICIOUS",
            "counts": counts,
            "stats": dict(counts),
            "diffs": diffs,
            "matches": matches,
            "labels": labels,
            "key_labels": labels,
            "artifacts": {"cards": cards},
        }

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
