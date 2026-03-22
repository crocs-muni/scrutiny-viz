# scrutiny-viz/verification/comparators/rsabias.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .contracts import ComparatorPlugin, ComparatorSpec


def _to_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _get_opt(metadata: Dict[str, Any], key: str, default: Any) -> Any:
    if key in metadata:
        return metadata[key]
    target = metadata.get("target") or {}
    return target.get(key, default)


def _display_label(row: Dict[str, Any], key_field: str, show_field: str) -> str:
    if show_field and row.get(show_field) is not None:
        return str(row.get(show_field))
    return str(row.get(key_field))


def _build_map(rows: List[Dict[str, Any]], key_field: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        key = row.get(key_field)
        if key is None:
            continue
        out[str(key)] = row
    return out


def _format_percent_or_raw(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    return float(v)


class RSABiasComparator(ComparatorPlugin):
    spec = ComparatorSpec(
        name="rsabias",
        aliases=("rsa-bias",),
        description="Comparator for RSABias evaluation sections with numeric tolerance and summary artifacts.",
    )

    def compare(
        self,
        *,
        section,
        key_field,
        show_field,
        metadata,
        reference,
        tested,
    ):
        epsilon = float(_get_opt(metadata, "numeric_epsilon", 1e-9))
        include_matches = bool(metadata.get("include_matches", True))
        top_limit = int(_get_opt(metadata, "artifact_limit", 15))

        ref_map = _build_map(reference or [], key_field)
        tst_map = _build_map(tested or [], key_field)

        all_keys = sorted(set(ref_map.keys()) | set(tst_map.keys()))

        diffs: List[Dict[str, Any]] = []
        matches: List[Dict[str, Any]] = []
        labels: Dict[str, str] = {}
        changed_keys: set[str] = set()

        only_ref = 0
        only_test = 0
        compared = 0
        matched = 0

        for key in all_keys:
            rr = ref_map.get(key)
            tr = tst_map.get(key)

            if rr is not None:
                labels[key] = _display_label(rr, key_field, show_field)
            elif tr is not None:
                labels[key] = _display_label(tr, key_field, show_field)

            if rr is None and tr is not None:
                only_test += 1
                diffs.append({"key": key, "field": "__presence__", "ref": None, "test": True})
                changed_keys.add(key)
                continue

            if rr is not None and tr is None:
                only_ref += 1
                diffs.append({"key": key, "field": "__presence__", "ref": True, "test": None})
                changed_keys.add(key)
                continue

            compared += 1
            row_changed = False

            fields = sorted(set(rr.keys()) | set(tr.keys()))
            for field in fields:
                if field == key_field:
                    continue

                rv = rr.get(field)
                tv = tr.get(field)

                equal = False
                if _is_number(rv) and _is_number(tv):
                    equal = abs(float(rv) - float(tv)) <= epsilon
                else:
                    equal = rv == tv

                if equal:
                    if include_matches:
                        matches.append({"key": key, "field": field, "value": rv})
                else:
                    diffs.append({"key": key, "field": field, "ref": rv, "test": tv})
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

        artifacts = self._build_artifacts(section, ref_map, tst_map, top_limit)

        return {
            "section": section,
            "counts": counts,
            "stats": dict(counts),
            "labels": labels,
            "key_labels": labels,
            "diffs": diffs,
            "matches": matches if include_matches else [],
            "source_rows": {"reference": reference or [], "profile": tested or []},
            "artifacts": artifacts,
        }

    def _build_artifacts(
        self,
        section: str,
        ref_map: Dict[str, Dict[str, Any]],
        tst_map: Dict[str, Dict[str, Any]],
        top_limit: int,
    ) -> Dict[str, Any]:
        artifacts: Dict[str, Any] = {}

        common_keys = sorted(set(ref_map.keys()) & set(tst_map.keys()))
        if not common_keys:
            return artifacts

        if section.startswith("ACCURACY_N"):
            changes = []
            for key in common_keys:
                rr = ref_map[key]
                tr = tst_map[key]
                rv = _to_float(rr.get("accuracy_pct"))
                tv = _to_float(tr.get("accuracy_pct"))
                if rv is None or tv is None:
                    continue
                delta = tv - rv
                changes.append(
                    {
                        "group": key,
                        "ref_accuracy_pct": rv,
                        "profile_accuracy_pct": tv,
                        "delta_pp": delta,
                    }
                )
            changes.sort(key=lambda x: abs(float(x["delta_pp"])), reverse=True)
            artifacts["top_accuracy_changes"] = changes[:top_limit]
            return artifacts

        if section == "CONFUSION_TOP":
            changes = []
            for key in common_keys:
                rr = ref_map[key]
                tr = tst_map[key]
                rv = _to_float(rr.get("share_pct"))
                tv = _to_float(tr.get("share_pct"))
                if rv is None or tv is None:
                    continue
                delta = tv - rv
                changes.append(
                    {
                        "edge_id": key,
                        "true_group": rr.get("true_group", tr.get("true_group")),
                        "pred_group": rr.get("pred_group", tr.get("pred_group")),
                        "ref_share_pct": rv,
                        "profile_share_pct": tv,
                        "delta_pp": delta,
                    }
                )
            changes.sort(key=lambda x: abs(float(x["delta_pp"])), reverse=True)
            artifacts["top_share_changes"] = changes[:top_limit]
            return artifacts

        if section in {"CONFUSION_MATRIX_CELLS", "CONFUSION_MATRIX_NONZERO"}:
            changes = []
            diag_ref = 0.0
            diag_tst = 0.0
            off_ref = 0.0
            off_tst = 0.0

            for key in common_keys:
                rr = ref_map[key]
                tr = tst_map[key]

                rv = _to_float(rr.get("value"))
                tv = _to_float(tr.get("value"))
                if rv is None or tv is None:
                    continue

                is_diag = bool(rr.get("is_diagonal", tr.get("is_diagonal", False)))
                if is_diag:
                    diag_ref += rv
                    diag_tst += tv
                else:
                    off_ref += rv
                    off_tst += tv

                delta = tv - rv
                changes.append(
                    {
                        "cell_id": key,
                        "row_index": rr.get("row_index", tr.get("row_index")),
                        "col_index": rr.get("col_index", tr.get("col_index")),
                        "row_label": rr.get("row_label", tr.get("row_label")),
                        "col_label": rr.get("col_label", tr.get("col_label")),
                        "ref_value": rv,
                        "profile_value": tv,
                        "delta": delta,
                        "delta_pp": delta * 100.0,
                    }
                )

            changes.sort(key=lambda x: abs(float(x["delta"])), reverse=True)
            artifacts["top_changed_cells"] = changes[:top_limit]
            artifacts["diag_ref"] = diag_ref
            artifacts["diag_profile"] = diag_tst
            artifacts["diag_delta"] = diag_tst - diag_ref
            artifacts["diag_delta_pp"] = (diag_tst - diag_ref) * 100.0
            artifacts["offdiag_ref"] = off_ref
            artifacts["offdiag_profile"] = off_tst
            artifacts["offdiag_delta"] = off_tst - off_ref
            artifacts["offdiag_delta_pp"] = (off_tst - off_ref) * 100.0
            return artifacts

        return artifacts


PLUGINS = [RSABiasComparator()]