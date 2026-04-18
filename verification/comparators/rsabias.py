# scrutiny-viz/verification/comparators/rsabias.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .contracts import ComparatorPlugin, ComparatorSpec, CompareResult
from .utility import build_string_key_map, get_display_label, to_float


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _get_opt(metadata: Dict[str, Any], key: str, default: Any) -> Any:
    if key in metadata:
        return metadata[key]
    target = metadata.get("target") or {}
    return target.get(key, default)


class RSABiasComparator(ComparatorPlugin):
    spec = ComparatorSpec(
        name="rsabias",
        aliases=("rsa-bias",),
        description="Comparator for RSABias evaluation sections with numeric tolerance and summary artifacts.",
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
        epsilon = float(_get_opt(metadata, "numeric_epsilon", 1e-9))
        include_matches = bool(metadata.get("include_matches", True))
        top_limit = int(_get_opt(metadata, "artifact_limit", 15))

        ref_map = build_string_key_map(reference or [], key_field)
        test_map = build_string_key_map(tested or [], key_field)
        keys = sorted(set(ref_map) | set(test_map))

        diffs: List[Dict[str, Any]] = []
        matches: List[Dict[str, Any]] = [] if include_matches else []
        labels: Dict[str, str] = {}
        changed_keys: set[str] = set()
        only_ref = only_test = compared = matched = 0

        for key in keys:
            ref_row = ref_map.get(key)
            test_row = test_map.get(key)

            if ref_row is not None:
                labels[key] = get_display_label(ref_row, key_field, show_field)
            elif test_row is not None:
                labels[key] = get_display_label(test_row, key_field, show_field)

            if ref_row is None:
                only_test += 1
                diffs.append({"key": key, "field": "__presence__", "ref": None, "test": True})
                changed_keys.add(key)
                continue
            if test_row is None:
                only_ref += 1
                diffs.append({"key": key, "field": "__presence__", "ref": True, "test": None})
                changed_keys.add(key)
                continue

            compared += 1
            row_changed = False
            for field in sorted(set(ref_row.keys()) | set(test_row.keys())):
                if field == key_field:
                    continue

                ref_value = ref_row.get(field)
                test_value = test_row.get(field)
                if _is_number(ref_value) and _is_number(test_value):
                    equal = abs(float(ref_value) - float(test_value)) <= epsilon
                else:
                    equal = ref_value == test_value

                if equal:
                    if include_matches:
                        matches.append({"key": key, "field": field, "value": ref_value})
                    continue

                diffs.append({"key": key, "field": field, "ref": ref_value, "test": test_value})
                row_changed = True

            if row_changed:
                changed_keys.add(key)
            else:
                matched += 1

        counts = {
            "compared": compared,
            "changed": len(changed_keys),
            "matched": matched,
            "only_ref": only_ref,
            "only_test": only_test,
        }
        result: CompareResult = {
            "section": section,
            "counts": counts,
            "stats": dict(counts),
            "labels": labels,
            "key_labels": labels,
            "diffs": diffs,
            "source_rows": {"reference": reference or [], "profile": tested or []},
            "artifacts": self._build_artifacts(section, ref_map, test_map, top_limit),
        }
        if include_matches:
            result["matches"] = matches
        return result

    def _build_artifacts(
        self,
        section: str,
        ref_map: Dict[str, Dict[str, Any]],
        test_map: Dict[str, Dict[str, Any]],
        top_limit: int,
    ) -> Dict[str, Any]:
        artifacts: Dict[str, Any] = {}
        common_keys = sorted(set(ref_map) & set(test_map))
        if not common_keys:
            return artifacts

        if section.startswith("ACCURACY_N"):
            changes = []
            for key in common_keys:
                ref_value = to_float(ref_map[key].get("accuracy_pct"))
                test_value = to_float(test_map[key].get("accuracy_pct"))
                if ref_value is None or test_value is None:
                    continue
                changes.append(
                    {
                        "group": key,
                        "ref_accuracy_pct": ref_value,
                        "profile_accuracy_pct": test_value,
                        "delta_pp": test_value - ref_value,
                    }
                )
            changes.sort(key=lambda item: abs(float(item["delta_pp"])), reverse=True)
            artifacts["top_accuracy_changes"] = changes[:top_limit]
            return artifacts

        if section == "CONFUSION_TOP":
            changes = []
            for key in common_keys:
                ref_row = ref_map[key]
                test_row = test_map[key]
                ref_value = to_float(ref_row.get("share_pct"))
                test_value = to_float(test_row.get("share_pct"))
                if ref_value is None or test_value is None:
                    continue
                changes.append(
                    {
                        "edge_id": key,
                        "true_group": ref_row.get("true_group", test_row.get("true_group")),
                        "pred_group": ref_row.get("pred_group", test_row.get("pred_group")),
                        "ref_share_pct": ref_value,
                        "profile_share_pct": test_value,
                        "delta_pp": test_value - ref_value,
                    }
                )
            changes.sort(key=lambda item: abs(float(item["delta_pp"])), reverse=True)
            artifacts["top_share_changes"] = changes[:top_limit]
            return artifacts

        if section in {"CONFUSION_MATRIX_CELLS", "CONFUSION_MATRIX_NONZERO"}:
            changes = []
            diag_ref = diag_test = off_ref = off_test = 0.0
            for key in common_keys:
                ref_row = ref_map[key]
                test_row = test_map[key]
                ref_value = to_float(ref_row.get("value"))
                test_value = to_float(test_row.get("value"))
                if ref_value is None or test_value is None:
                    continue

                is_diag = bool(ref_row.get("is_diagonal", test_row.get("is_diagonal", False)))
                if is_diag:
                    diag_ref += ref_value
                    diag_test += test_value
                else:
                    off_ref += ref_value
                    off_test += test_value

                delta = test_value - ref_value
                changes.append(
                    {
                        "cell_id": key,
                        "row_index": ref_row.get("row_index", test_row.get("row_index")),
                        "col_index": ref_row.get("col_index", test_row.get("col_index")),
                        "row_label": ref_row.get("row_label", test_row.get("row_label")),
                        "col_label": ref_row.get("col_label", test_row.get("col_label")),
                        "ref_value": ref_value,
                        "profile_value": test_value,
                        "delta": delta,
                        "delta_pp": delta * 100.0,
                    }
                )

            changes.sort(key=lambda item: abs(float(item["delta"])), reverse=True)
            artifacts.update(
                {
                    "top_changed_cells": changes[:top_limit],
                    "diag_ref": diag_ref,
                    "diag_profile": diag_test,
                    "diag_delta": diag_test - diag_ref,
                    "diag_delta_pp": (diag_test - diag_ref) * 100.0,
                    "offdiag_ref": off_ref,
                    "offdiag_profile": off_test,
                    "offdiag_delta": off_test - off_ref,
                    "offdiag_delta_pp": (off_test - off_ref) * 100.0,
                }
            )

        return artifacts


PLUGINS = [RSABiasComparator()]
