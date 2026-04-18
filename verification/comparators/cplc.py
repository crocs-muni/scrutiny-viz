# scrutiny-viz/verification/comparators/cplc.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .contracts import ComparatorPlugin, ComparatorSpec, CompareResult
from .utility import build_row_map, get_display_label, sort_mixed_keys


class CplcComparator(ComparatorPlugin):
    spec = ComparatorSpec(
        name="cplc",
        aliases=("jc-cplc", "jccplc"),
        description="Comparator for CPLC key/value rows with first-token normalization.",
    )

    @staticmethod
    def _first_token(value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped.split()[0] if stripped else ""

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
        value_field = str(metadata.get("value_field") or "value")
        compare_first_token = bool(metadata.get("compare_first_token", True))
        include_matches = bool(metadata.get("include_matches", False))

        normalize = self._first_token if compare_first_token else (lambda value: value)
        ref_map = build_row_map(reference, key_field)
        test_map = build_row_map(tested, key_field)
        keys = sort_mixed_keys(set(ref_map.keys()) | set(test_map.keys()))

        diffs: List[Dict[str, Any]] = []
        matches: List[Dict[str, Any]] = [] if include_matches else []
        labels: Dict[str, str] = {}
        compared = changed = matched = only_ref = only_test = 0

        for key in keys:
            ref_row = ref_map.get(key)
            test_row = test_map.get(key)

            if ref_row is None or test_row is None:
                if ref_row is not None:
                    only_ref += 1
                    diffs.append({"key": str(key), "field": "__presence__", "ref": True, "op": "!=", "test": False})
                else:
                    only_test += 1
                    diffs.append({"key": str(key), "field": "__presence__", "ref": False, "op": "!=", "test": True})
                continue

            labels[str(key)] = get_display_label(ref_row, key_field, show_field)
            compared += 1

            ref_raw = ref_row.get(value_field)
            test_raw = test_row.get(value_field)
            if normalize(ref_raw) != normalize(test_raw):
                changed += 1
                diffs.append({"key": str(key), "field": value_field, "ref": ref_raw, "op": "!=", "test": test_raw})
                continue

            matched += 1
            if include_matches:
                matches.append({"key": str(key), "field": value_field, "value": test_raw})

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
            "artifacts": {},
        }
        if include_matches:
            result["matches"] = matches
        return result


PLUGINS = [CplcComparator()]
