# scrutiny-viz/verification/comparators/basic.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from .contracts import ComparatorPlugin, ComparatorSpec, CompareResult

Scalar = Union[str, int, float, bool, None]


def _is_scalar(x: Any) -> bool:
    return isinstance(x, (str, int, float, bool)) or x is None


def _iterable_like(x: Any) -> bool:
    return isinstance(x, (list, tuple, set))


def _mapping_like(x: Any) -> bool:
    return isinstance(x, dict)


def _normalize_group(x: Any) -> List[Any]:
    if _iterable_like(x):
        try:
            return sorted(list(x), key=lambda v: repr(v))
        except Exception:
            return list(x)
    if _mapping_like(x):
        try:
            items = [{"key": k, "value": x[k]} for k in sorted(x.keys(), key=lambda k: repr(k))]
        except Exception:
            items = [{"key": k, "value": v} for k, v in x.items()]
        return items
    return [x]


def _to_set_for_diff(x: Any) -> Tuple[List[Any], Dict[str, Any]]:
    items = _normalize_group(x)
    index: Dict[str, Any] = {}
    for it in items:
        key = repr(it)
        if key not in index:
            index[key] = it
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
        include_matches: bool = bool(metadata.get("include_matches", False))

        ref_map = {r.get(key_field): r for r in reference if isinstance(r, dict) and r.get(key_field) is not None}
        tst_map = {r.get(key_field): r for r in tested if isinstance(r, dict) and r.get(key_field) is not None}
        keys = sorted(set(ref_map.keys()) | set(tst_map.keys()), key=lambda x: (str(type(x)), str(x)))

        diffs: List[Dict[str, Any]] = []
        matches: List[Dict[str, Any]] = [] if include_matches else []
        labels: Dict[str, str] = {}

        compared = changed = matched = only_ref = only_test = 0

        for k in keys:
            r = ref_map.get(k)
            t = tst_map.get(k)

            if r is None or t is None:
                if r is not None and t is None:
                    only_ref += 1
                    diffs.append({"key": str(k), "field": "__presence__", "ref": True, "op": "!=", "test": False})
                elif t is not None and r is None:
                    only_test += 1
                    diffs.append({"key": str(k), "field": "__presence__", "ref": False, "op": "!=", "test": True})
                continue

            lbl = r.get(show_field or key_field, r.get(key_field, k))
            labels[str(k)] = str(lbl)

            fields = set(r.keys()) | set(t.keys())
            fields.discard(key_field)

            for field in sorted(fields, key=lambda x: str(x)):
                rv = r.get(field, None)
                tv = t.get(field, None)

                if field not in r and field not in t:
                    continue

                if _iterable_like(rv) or _mapping_like(rv) or _iterable_like(tv) or _mapping_like(tv):
                    _, idx_r = _to_set_for_diff(rv if rv is not None else [])
                    _, idx_t = _to_set_for_diff(tv if tv is not None else [])
                    set_r = set(idx_r.keys())
                    set_t = set(idx_t.keys())

                    removed = sorted(list(set_r - set_t))
                    added = sorted(list(set_t - set_r))

                    if not removed and not added:
                        compared += 1
                        matched += 1
                        if include_matches:
                            matches.append({"key": str(k), "field": "__group__", "value": None})
                    else:
                        for rk in removed:
                            diffs.append({"key": str(k), "field": "__group__", "ref": idx_r[rk], "op": "->", "test": None})
                            changed += 1
                            compared += 1
                        for ak in added:
                            diffs.append({"key": str(k), "field": "__group__", "ref": None, "op": "->", "test": idx_t[ak]})
                            changed += 1
                            compared += 1
                    continue

                if _is_scalar(rv) and _is_scalar(tv):
                    compared += 1
                    if rv != tv:
                        changed += 1
                        diffs.append({"key": str(k), "field": field, "ref": rv, "op": "!=", "test": tv})
                    else:
                        matched += 1
                        if include_matches:
                            matches.append({"key": str(k), "field": field, "value": tv})
                    continue

                compared += 1
                changed += 1
                diffs.append({"key": str(k), "field": field, "ref": rv, "op": "!=", "test": tv})

        counts = {
            "compared": compared,
            "changed": changed,
            "matched": matched,
            "only_ref": only_ref,
            "only_test": only_test,
        }

        return {
            "section": section,
            "counts": counts,
            "stats": counts,
            "labels": labels,
            "key_labels": labels,
            "diffs": diffs,
            **({"matches": matches} if include_matches else {}),
            "artifacts": {},
        }


PLUGINS = [BasicComparator()]
