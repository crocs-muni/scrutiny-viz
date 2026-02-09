# scrutiny-viz/scrutiny/comparators/cplc_comparator.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .interface import Comparator, CompareResult
from .registry import register


class CplcComparator(Comparator):
    """
    CPLC comparator.

    Intended JSON row format (per section "CPLC"):
      [
        {"field": "ICFabricator", "value": "8100"},
        {"field": "OperatingSystemReleaseDate", "value": "4001 (2014-01-01)"},
        ...
      ]

    YAML section should set:
      component:
        comparator: cplc
        match_key: field
        show_key: field
      target:
        value_field: value              # optional (default "value")
        compare_first_token: true       # optional (default True)

    Semantics:
      - Presence diffs when a CPLC field exists only in one side.
      - Value diffs compare only the first whitespace token by default:
          "4001 (2014-01-01)" -> compares "4001"
      - Emits diffs using raw values, but mismatch decision uses normalized values.
    """

    @staticmethod
    def _first_token(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return ""
            return s.split()[0]
        return v

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

        value_field: str = str(metadata.get("value_field") or "value")
        compare_first_token: bool = bool(metadata.get("compare_first_token", True))
        include_matches: bool = bool(metadata.get("include_matches", False))

        def norm(v: Any) -> Any:
            return self._first_token(v) if compare_first_token else v

        # Index rows by CPLC field name (key_field)
        ref_map = {
            r.get(key_field): r
            for r in reference
            if isinstance(r, dict) and r.get(key_field) is not None
        }
        tst_map = {
            r.get(key_field): r
            for r in tested
            if isinstance(r, dict) and r.get(key_field) is not None
        }

        keys = sorted(set(ref_map.keys()) | set(tst_map.keys()), key=lambda x: (str(type(x)), str(x)))

        diffs: List[Dict[str, Any]] = []
        matches: List[Dict[str, Any]] = [] if include_matches else []
        labels: Dict[str, str] = {}

        compared = changed = matched = only_ref = only_test = 0

        for k in keys:
            r = ref_map.get(k)
            t = tst_map.get(k)

            # Presence diffs (missing/extra CPLC fields)
            if r is None or t is None:
                if r is not None and t is None:
                    only_ref += 1
                    diffs.append({"key": str(k), "field": "__presence__", "ref": True, "op": "!=", "test": False})
                elif t is not None and r is None:
                    only_test += 1
                    diffs.append({"key": str(k), "field": "__presence__", "ref": False, "op": "!=", "test": True})
                continue

            # Pretty label
            lbl = r.get(show_field or key_field, r.get(key_field, k))
            labels[str(k)] = str(lbl)

            rv_raw = r.get(value_field, None)
            tv_raw = t.get(value_field, None)

            # Compare using normalized value (first token by default)
            rv_cmp = norm(rv_raw)
            tv_cmp = norm(tv_raw)

            compared += 1
            if rv_cmp != tv_cmp:
                changed += 1
                diffs.append({"key": str(k), "field": value_field, "ref": rv_raw, "op": "!=", "test": tv_raw})
            else:
                matched += 1
                if include_matches:
                    matches.append({"key": str(k), "field": value_field, "value": tv_raw})

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


# Self-register as "cplc" (same pattern as basic/algperf)
register("cplc", CplcComparator)
