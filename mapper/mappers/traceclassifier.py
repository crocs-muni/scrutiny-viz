# scrutiny-viz/mapper/mappers/traceclassifier.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import MapperPlugin, MapperSpec, MappingContext

try:
    from .. import mapper_utils
except ImportError:
    import mapper_utils  # type: ignore


class TraceClassifierMapper(MapperPlugin):
    spec = MapperSpec(
        name="traceclassifier",
        aliases=("trace-classifier", "powerclassifier", "classifier"),
        description="Map legacy trace-classifier JSON into scrutiny-viz JSON.",
    )

    def ingest(self, source_path: Path) -> dict[str, Any]:
        src = mapper_utils.require_existing_file(source_path, kind="trace classifier input")
        doc = mapper_utils.read_json_object(src, label="trace classifier input")

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
            card_code = str(card.get("card_code") or "")
            operations = card.get("operations_results") or card.get("operation_results") or []

            for op in operations:
                operation_code = str(op.get("operation_code") or "")
                intervals = self._sanitize_intervals(op.get("similarity_intervals") or [])
                best_value, best_type = self._best_interval(intervals)

                raw_image = str(op.get("visualized_operations") or "")
                resolved_image = mapper_utils.resolve_asset_path(source_dir, raw_image)

                rows.append(
                    {
                        "card_code": card_code,
                        "operation_code": operation_code,
                        "operation_found": bool(intervals),
                        "interval_count": len(intervals),
                        "best_similarity_value": best_value,
                        "similarity_value_type": best_type,
                        "visualized_operations": resolved_image,
                        "similarity_intervals_json": mapper_utils.compact_json(intervals),
                    }
                )

        out["TRACE_CLASSIFIER"] = rows
        return out

    def _extract_module(self, doc: dict[str, Any]) -> tuple[dict[str, Any], str | None, str | None, str | None]:
        ref_name = doc.get("ref_name")
        prof_name = doc.get("prof_name")
        overall_result = doc.get("result")

        module = (
            self._extract_from_contrasts(doc)
            or self._extract_from_top_level(doc)
            or self._extract_from_module_data(doc)
            or self._extract_results_recursively(doc)
        )
        if module is None:
            raise ValueError("Unsupported Trace classifier JSON structure: could not find classifier results")

        return module, ref_name, prof_name, overall_result

    def _extract_from_contrasts(self, doc: dict[str, Any]) -> dict[str, Any] | None:
        contrasts = doc.get("contrasts")
        if not isinstance(contrasts, list):
            return None

        for item in contrasts:
            if not isinstance(item, dict):
                continue

            module_name = str(item.get("module_name") or "")
            py_object = str(item.get("py/object") or "")
            results = item.get("results")

            if isinstance(results, list) and (
                module_name == "Trace Classifier"
                or "TraceClassifierContrast" in py_object
                or "traceclassifier" in py_object.lower()
            ):
                return item

        for item in contrasts:
            if isinstance(item, dict) and isinstance(item.get("results"), list):
                return item

        return None

    def _extract_from_top_level(self, doc: dict[str, Any]) -> dict[str, Any] | None:
        return doc if isinstance(doc.get("results"), list) else None

    def _extract_from_module_data(self, doc: dict[str, Any]) -> dict[str, Any] | None:
        module_data = doc.get("module_data")
        if isinstance(module_data, dict) and isinstance(module_data.get("results"), list):
            return module_data
        return None

    def _extract_results_recursively(self, doc: dict[str, Any]) -> dict[str, Any] | None:
        stack: list[Any] = [doc]

        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                if isinstance(current.get("results"), list):
                    return current
                for value in current.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(current, list):
                for value in current:
                    if isinstance(value, (dict, list)):
                        stack.append(value)

        return None

    def _sanitize_intervals(self, intervals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        for interval in intervals:
            cleaned.append(
                {
                    "similarity_value": float(interval.get("similarity_value", 0.0) or 0.0),
                    "similarity_value_type": str(interval.get("similarity_value_type") or ""),
                    "time_from": float(interval.get("time_from", 0.0) or 0.0),
                    "time_to": float(interval.get("time_to", 0.0) or 0.0),
                    "indexes_compared": int(interval.get("indexes_compared", 0) or 0),
                }
            )
        return cleaned

    def _best_interval(self, intervals: list[dict[str, Any]]) -> tuple[float | None, str | None]:
        if not intervals:
            return None, None

        value_types = {str(item.get("similarity_value_type") or "").upper() for item in intervals}
        if value_types and value_types.issubset({"CORRELATION", "SIMILARITY"}):
            best = max(intervals, key=lambda item: float(item.get("similarity_value", 0.0) or 0.0))
        else:
            best = min(intervals, key=lambda item: float(item.get("similarity_value", 0.0) or 0.0))

        return (
            float(best.get("similarity_value", 0.0) or 0.0),
            str(best.get("similarity_value_type") or ""),
        )


PLUGIN = TraceClassifierMapper()
PLUGINS = [PLUGIN]
