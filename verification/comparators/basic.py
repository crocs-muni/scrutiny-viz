# scrutiny-viz/verification/comparators/basic.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .contracts import ComparatorPlugin, ComparatorSpec, CompareResult
from .utility import build_row_map, get_display_label, sort_mixed_keys

def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def _iterable_like(value: Any) -> bool:
    return isinstance(value, (list, tuple, set))


def _mapping_like(value: Any) -> bool:
    return isinstance(value, dict)


def _normalize_group(value: Any) -> List[Any]:
    if _iterable_like(value):
        try:
            return sorted(list(value), key=repr)
        except Exception:
            return list(value)
    if _mapping_like(value):
        try:
            return [{"key": key, "value": value[key]} for key in sorted(value.keys(), key=repr)]
        except Exception:
            return [{"key": key, "value": item} for key, item in value.items()]
    return [value]


def _to_set_for_diff(value: Any) -> Tuple[List[Any], Dict[str, Any]]:
    items = _normalize_group(value)
    index: Dict[str, Any] = {}
    for item in items:
        index.setdefault(repr(item), item)
    return items, index


class BasicComparator(ComparatorPlugin):
    spec = ComparatorSpec(
        name="basic",
        aliases=("default",),
        description="General-purpose comparator for scalar and grouped section rows.",
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
        include_matches = bool(metadata.get("include_matches", False))

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
            fields = set(ref_row.keys()) | set(test_row.keys())
            fields.discard(key_field)

            for field in sorted(fields, key=str):
                ref_value = ref_row.get(field)
                test_value = test_row.get(field)

                if _iterable_like(ref_value) or _mapping_like(ref_value) or _iterable_like(test_value) or _mapping_like(test_value):
                    _, ref_index = _to_set_for_diff(ref_value if ref_value is not None else [])
                    _, test_index = _to_set_for_diff(test_value if test_value is not None else [])

                    removed = sorted(set(ref_index) - set(test_index))
                    added = sorted(set(test_index) - set(ref_index))

                    if not removed and not added:
                        compared += 1
                        matched += 1
                        if include_matches:
                            matches.append({"key": str(key), "field": "__group__", "value": None})
                        continue

                    for removed_key in removed:
                        compared += 1
                        changed += 1
                        diffs.append({"key": str(key), "field": "__group__", "ref": ref_index[removed_key], "op": "->", "test": None})
                    for added_key in added:
                        compared += 1
                        changed += 1
                        diffs.append({"key": str(key), "field": "__group__", "ref": None, "op": "->", "test": test_index[added_key]})
                    continue

                compared += 1
                if _is_scalar(ref_value) and _is_scalar(test_value) and ref_value == test_value:
                    matched += 1
                    if include_matches:
                        matches.append({"key": str(key), "field": field, "value": test_value})
                    continue

                changed += 1
                diffs.append({"key": str(key), "field": field, "ref": ref_value, "op": "!=", "test": test_value})

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


PLUGINS = [BasicComparator()]
