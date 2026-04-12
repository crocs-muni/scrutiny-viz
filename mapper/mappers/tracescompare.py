# scrutiny-viz/mapper/mappers/tracescompare.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import MapperPlugin, MapperSpec, MappingContext

try:
    from .. import mapper_utils
except ImportError:
    import mapper_utils  # type: ignore


class TracesCompareMapper(MapperPlugin):
    spec = MapperSpec(
        name="tracescompare",
        aliases=("traces-comparer", "ptraces", "powertraces"),
        description="Map scrutiny-power-traces-analyzer Traces comparer JSON into scrutiny-viz JSON.",
    )

    def ingest(self, source_path: Path) -> dict[str, Any]:
        src = mapper_utils.require_existing_file(source_path, kind="traces comparer input")
        doc = mapper_utils.read_json_object(src, label="traces comparer input")

        module_data, card_code, module_name = self._extract_module_data(doc)
        return {
            "source_file": src,
            "source_dir": src.parent,
            "module_data": module_data,
            "card_code": card_code,
            "module_name": module_name,
        }

    def map_groups(self, groups: list[list[str]], context: MappingContext) -> dict[str, Any]:
        raise TypeError("Traces comparer mapper does not support grouped CSV input; use a JSON file.")

    def map_source(self, source: Any, context: MappingContext) -> dict[str, Any]:
        source_file: Path = source["source_file"]
        source_dir: Path = source["source_dir"]
        module_data: dict[str, Any] = source["module_data"]
        card_code = source.get("card_code")
        module_name = source.get("module_name")

        results = module_data.get("results") or []

        out: dict[str, Any] = {"_type": "tracescompare"}
        out["_TRACE_META"] = [
            {"name": "source_file", "value": source_file.name},
            {"name": "source_dir", "value": str(source_dir)},
            {"name": "card_code", "value": str(card_code or "")},
            {"name": "module_name", "value": str(module_name or "")},
            {"name": "operation_count", "value": str(len(results))},
        ]

        rows: list[dict[str, Any]] = []
        for op in results:
            pipeline_comparisons = self._sanitize_pipeline_comparisons(
                op.get("pipeline_comparisons") or [],
                source_dir,
            )
            execution_times = self._sanitize_execution_times(op.get("execution_times") or [])

            rows.append(
                {
                    "operation_code": str(op.get("operation_code") or ""),
                    "operation_present": bool(op.get("operation_present", True)),
                    "pipeline_comparisons_json": mapper_utils.compact_json(pipeline_comparisons),
                    "execution_times_json": mapper_utils.compact_json(execution_times),
                }
            )

        out["TRACE_OPERATIONS"] = rows
        return out

    def _extract_module_data(self, doc: dict[str, Any]) -> tuple[dict[str, Any], str | None, str | None]:
        modules = doc.get("modules")
        if isinstance(modules, dict):
            traces_comparer = modules.get("TRACES_COMPARER")
            if isinstance(traces_comparer, dict):
                module_data = traces_comparer.get("module_data") or {}
                card_code = module_data.get("card_code") or doc.get("name")
                module_name = traces_comparer.get("module_name") or traces_comparer.get("name")
                if isinstance(module_data, dict) and "results" in module_data:
                    return module_data, card_code, module_name

        module_data = doc.get("module_data")
        if isinstance(module_data, dict) and "results" in module_data:
            return module_data, module_data.get("card_code"), doc.get("module_name")

        if "results" in doc:
            return doc, doc.get("card_code"), doc.get("module_name")

        raise ValueError("Unsupported Traces comparer JSON structure: could not find results")

    def _sanitize_pipeline_comparisons(self, pipelines: list[dict[str, Any]], source_dir: Path) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []

        for pipeline in pipelines:
            comparisons: list[dict[str, Any]] = []
            for comparison in pipeline.get("comparisons") or []:
                raw_path = str(comparison.get("file_path") or "")
                resolved_path = mapper_utils.resolve_asset_path(source_dir, raw_path)

                comparisons.append(
                    {
                        "distance": float(comparison.get("distance", 0.0) or 0.0),
                        "file_path": resolved_path,
                        "file_name": Path(raw_path).name if raw_path else "",
                        "raw_file_path": raw_path,
                    }
                )

            cleaned.append(
                {
                    "pipeline": str(pipeline.get("pipeline") or ""),
                    "metric_type": str(pipeline.get("metric_type") or ""),
                    "comparisons": comparisons,
                }
            )

        return cleaned

    def _sanitize_execution_times(self, exec_times: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        for exec_time in exec_times:
            cleaned.append(
                {
                    "unit": str(exec_time.get("unit") or ""),
                    "time": float(exec_time.get("time", 0.0) or 0.0),
                }
            )
        return cleaned


PLUGIN = TracesCompareMapper()
PLUGINS = [PLUGIN]
