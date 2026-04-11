# scrutiny-viz/verification/comparators/traceclassifier.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import MapperPlugin, MapperSpec, MappingContext

try:
    from .. import mapper_utils
except ImportError:
    import mapper_utils  # type: ignore


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class TraceClassifierMapper(MapperPlugin):
    spec = MapperSpec(
        name="traceclassifier",
        aliases=("trace-classifier", "powerclassifier", "classifier"),
        description="Map legacy trace-classifier JSON into scrutiny-viz JSON.",
    )

    def ingest(self, source_path: Path) -> dict[str, Any]:
        src = Path(source_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Trace classifier input path does not exist: {src}")
        if not src.is_file():
            raise ValueError(f"Trace classifier mapper expects a JSON file, got: {src}")

        doc = mapper_utils.read_json_file(src)
        if doc is None:
            raise ValueError(f"Failed to parse JSON from: {src}")
        if not isinstance(doc, dict):
            raise ValueError(f"Trace classifier input must be a JSON object: {src}")

        module, ref_name, prof_name, overall_result = self._extract_module(doc)

        return {
            "source_file": src,
            "source_dir": src.parent,
            "module": module,
            "ref_name": ref_name,
            "prof_name": prof_name,
            "overall_result": overall_result,
        }

    def map_groups(self, groups: list[list[str]], context: MappingContext) -> dict[str, Any]:
        raise TypeError("Trace classifier mapper does not support grouped CSV input; use a JSON file.")

    def map_source(self, source: Any, context: MappingContext) -> dict[str, Any]:
        source_file: Path = source["source_file"]
        source_dir: Path = source["source_dir"]
        module: dict[str, Any] = source["module"]
        ref_name = source.get("ref_name")
        prof_name = source.get("prof_name")
        overall_result = source.get("overall_result")

        results = module.get("results") or []

        out: dict[str, Any] = {"_type": "traceclassifier"}

        out["_TRACE_CLASSIFIER_META"] = [
            {"name": "source_file", "value": source_file.name},
            {"name": "source_dir", "value": str(source_dir)},
            {"name": "ref_name", "value": str(ref_name or "")},
            {"name": "prof_name", "value": str(prof_name or "")},
            {"name": "overall_result", "value": str(overall_result or "")},
            {"name": "card_count", "value": str(len(results))},
        ]

        rows: list[dict[str, Any]] = []
        for card in results:
            if not isinstance(card, dict):
                continue

            card_code = str(card.get("card_code") or "")
            operations = card.get("operations_results") or card.get("operation_results") or []

            for op in operations:
                if not isinstance(op, dict):
                    continue

                operation_code = str(op.get("operation_code") or "")
                intervals = self._sanitize_intervals(op.get("similarity_intervals") or [])
                best_value, best_type = self._best_interval(intervals)

                raw_image = str(op.get("visualized_operations") or "")
                resolved_image = self._resolve_asset(source_dir, raw_image)

                rows.append(
                    {
                        "card_code": card_code,
                        "operation_code": operation_code,
                        "operation_found": bool(len(intervals) > 0),
                        "interval_count": len(intervals),
                        "best_similarity_value": best_value,
                        "similarity_value_type": best_type,
                        "visualized_operations": resolved_image,
                        "similarity_intervals_json": _dump(intervals),
                    }
                )

        out["TRACE_CLASSIFIER"] = rows
        return out

    def _extract_module(self, doc: dict[str, Any]) -> tuple[dict[str, Any], str | None, str | None, str | None]:
        # Most common legacy wrapper:
        # {
        #   "ref_name": ...,
        #   "prof_name": ...,
        #   "result": ...,
        #   "contrasts": [
        #       {
        #         "module_name": "Trace Classifier",
        #         "results": [...]
        #       }
        #   ]
        # }
        contrasts = doc.get("contrasts")
        if isinstance(contrasts, list):
            for item in contrasts:
                if not isinstance(item, dict):
                    continue

                module_name = str(item.get("module_name") or "")
                py_object = str(item.get("py/object") or "")

                if "results" in item and (
                    module_name == "Trace Classifier"
                    or py_object.endswith("TraceClassifierContrast")
                ):
                    return (
                        item,
                        doc.get("ref_name"),
                        doc.get("prof_name"),
                        doc.get("result"),
                    )

            # Fallback: any contrast item that has results
            for item in contrasts:
                if isinstance(item, dict) and "results" in item:
                    return (
                        item,
                        doc.get("ref_name"),
                        doc.get("prof_name"),
                        doc.get("result"),
                    )

        # Alternate direct shape:
        # { "module_name": "...", "results": [...] }
        if "results" in doc and isinstance(doc.get("results"), list):
            return (
                doc,
                doc.get("ref_name"),
                doc.get("prof_name"),
                doc.get("result"),
            )

        # Alternate nested module_data shape
        if isinstance(doc.get("module_data"), dict) and "results" in doc["module_data"]:
            return (
                doc["module_data"],
                doc.get("ref_name"),
                doc.get("prof_name"),
                doc.get("result"),
            )

        raise ValueError(
            "Unsupported Trace classifier JSON structure: could not find classifier results"
        )

    def _sanitize_intervals(self, intervals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        for it in intervals:
            if not isinstance(it, dict):
                continue
            cleaned.append(
                {
                    "similarity_value": float(it.get("similarity_value", 0.0) or 0.0),
                    "similarity_value_type": str(it.get("similarity_value_type") or ""),
                    "time_from": float(it.get("time_from", 0.0) or 0.0),
                    "time_to": float(it.get("time_to", 0.0) or 0.0),
                    "indexes_compared": int(it.get("indexes_compared", 0) or 0),
                }
            )
        return cleaned

    def _best_interval(self, intervals: list[dict[str, Any]]) -> tuple[float | None, str | None]:
        if not intervals:
            return None, None

        kinds = {str(x.get("similarity_value_type") or "").upper() for x in intervals}
        if kinds and kinds.issubset({"CORRELATION", "SIMILARITY"}):
            best = max(intervals, key=lambda x: float(x.get("similarity_value", 0.0) or 0.0))
        else:
            best = min(intervals, key=lambda x: float(x.get("similarity_value", 0.0) or 0.0))

        return (
            float(best.get("similarity_value", 0.0) or 0.0),
            str(best.get("similarity_value_type") or ""),
        )

    def _resolve_asset(self, source_dir: Path, raw_path: str) -> str:
        if not raw_path:
            return ""

        p = Path(raw_path)
        if p.is_absolute() and p.exists():
            try:
                return p.resolve().as_uri()
            except Exception:
                return str(p.resolve())

        candidate = (source_dir / raw_path).resolve()
        if candidate.exists():
            try:
                return candidate.as_uri()
            except Exception:
                return str(candidate)

        return raw_path


PLUGIN = TraceClassifierMapper()
PLUGINS = [PLUGIN]