# scrutiny-viz/scrutiny/comparators/basic.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Iterable, Tuple, Union

from .interface import Comparator, CompareResult
from .registry import register

Scalar = Union[str, int, float, bool, None]


def _is_scalar(x: Any) -> bool:
    return isinstance(x, (str, int, float, bool)) or x is None


def _iterable_like(x: Any) -> bool:
    # Treat list/tuple/set as "group" comparable containers
    return isinstance(x, (list, tuple, set))


def _mapping_like(x: Any) -> bool:
    return isinstance(x, dict)


def _normalize_group(x: Any) -> List[Any]:
    """
    Convert list/tuple/set/dict into a list of comparable items (stable order)
    while preserving original item structure so the HTML report can render it.
    - list/tuple/set -> list(items) with stable sort by repr
    - dict -> list of {"key": k, "value": v} pairs, stable sort by key repr
    """
    if _iterable_like(x):
        try:
            return sorted(list(x), key=lambda v: repr(v))
        except Exception:
            return list(x)  # best effort, original order
    if _mapping_like(x):
        try:
            items = [{"key": k, "value": x[k]} for k in sorted(x.keys(), key=lambda k: repr(k))]
        except Exception:
            items = [{"key": k, "value": v} for k, v in x.items()]
        return items
    # Fallback: wrap scalar (rare for group comparison)
    return [x]


def _to_set_for_diff(x: Any) -> Tuple[List[Any], Dict[str, Any]]:
    """
    Prepare a container for diffing:
      returns (list_of_items, index) where index maps a stable repr to the original item.
      This lets us set-diff by repr while preserving original item for the report.
    """
    items = _normalize_group(x)
    index: Dict[str, Any] = {}
    for it in items:
        key = repr(it)
        # keep first occurrence only for stability; duplicates ignored by set semantics
        if key not in index:
            index[key] = it
    return items, index


class BasicComparator(Comparator):
    """
    General-purpose comparator for YAML-driven sections (e.g., jcAIDScan, jcAlgSupport).

    Features:
      • Presence diffs for rows (missing/extra keys).
      • Per-field scalar equality diffs (string/number/bool).
      • Group diffs for list/tuple/set/dict fields:
          - emits '__group__' diffs with individual removed/added items.
          - reporter/HTML pairs them visually.
      • 'matches' emitted when include_matches=True.

    Counts semantics:
      - 'compared' counts the number of fields compared (excl. presence).
      - 'changed' increments per diff emitted (each group item change counts).
      - 'matched' increments per successful field (or grouped set fully matched).
      - 'only_ref' / 'only_test' count rows present in one side only.
    """

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

        include_matches: bool = bool(metadata.get("include_matches", False))

        # Index rows by key
        ref_map = {r.get(key_field): r for r in reference if isinstance(r, dict) and r.get(key_field) is not None}
        tst_map = {r.get(key_field): r for r in tested   if isinstance(r, dict) and r.get(key_field) is not None}
        keys = sorted(set(ref_map.keys()) | set(tst_map.keys()), key=lambda x: (str(type(x)), str(x)))

        diffs: List[Dict[str, Any]] = []
        matches: List[Dict[str, Any]] = [] if include_matches else []
        labels: Dict[str, str] = {}

        compared = changed = matched = only_ref = only_test = 0

        for k in keys:
            r = ref_map.get(k)
            t = tst_map.get(k)

            # Presence diffs
            if r is None or t is None:
                if r is not None and t is None:
                    only_ref += 1
                    diffs.append({"key": str(k), "field": "__presence__", "ref": True, "op": "!=", "test": False})
                elif t is not None and r is None:
                    only_test += 1
                    diffs.append({"key": str(k), "field": "__presence__", "ref": False, "op": "!=", "test": True})
                continue

            # Label (pretty display name)
            lbl = r.get(show_field or key_field, r.get(key_field, k))
            labels[str(k)] = str(lbl)

            # Determine fields to compare: union of field names minus the match key
            fields = set(r.keys()) | set(t.keys())
            if key_field in fields:
                fields.remove(key_field)

            for field in sorted(fields, key=lambda x: str(x)):
                rv = r.get(field, None)
                tv = t.get(field, None)

                # If both missing, skip
                if field not in r and field not in t:
                    continue

                # Group comparison for containers
                if _iterable_like(rv) or _mapping_like(rv) or _iterable_like(tv) or _mapping_like(tv):
                    # If one side is missing container or types differ -> treat as full container diff
                    # Compute set-like diffs by repr to remain stable
                    _, idx_r = _to_set_for_diff(rv if rv is not None else [])
                    _, idx_t = _to_set_for_diff(tv if tv is not None else [])
                    set_r = set(idx_r.keys())
                    set_t = set(idx_t.keys())

                    removed = sorted(list(set_r - set_t))
                    added   = sorted(list(set_t - set_r))

                    if not removed and not added:
                        # full match
                        compared += 1
                        matched += 1
                        if include_matches:
                            matches.append({"key": str(k), "field": "__group__", "value": None})
                    else:
                        # every removed/added counts as a change
                        for rk in removed:
                            diffs.append({"key": str(k), "field": "__group__", "ref": idx_r[rk], "op": "->", "test": None})
                            changed += 1
                            compared += 1
                        for ak in added:
                            diffs.append({"key": str(k), "field": "__group__", "ref": None, "op": "->", "test": idx_t[ak]})
                            changed += 1
                            compared += 1
                    continue

                # Scalar comparison path
                if _is_scalar(rv) and _is_scalar(tv):
                    compared += 1
                    if rv != tv:
                        changed += 1
                        diffs.append({"key": str(k), "field": field, "ref": rv, "op": "!=",
                                      "test": tv})
                    else:
                        matched += 1
                        if include_matches:
                            matches.append({"key": str(k), "field": field, "value": tv})
                    continue

                # Type mismatch (one scalar, one container, or unknown)
                compared += 1
                changed += 1
                diffs.append({"key": str(k), "field": field, "ref": rv, "op": "!=",
                              "test": tv})

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
            "artifacts": {},  # basic comparator has no special artifacts; HTML uses diffs/matches/labels
        }


# Self-register as the default "basic" comparator
register("basic", BasicComparator)
