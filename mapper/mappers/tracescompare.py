# scrutiny-viz/mapper/mappers/tracescompare.py
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


class TracesCompareMapper(MapperPlugin):
    spec = MapperSpec(
        name="tracescompare",
        aliases=("traces-comparer", "ptraces", "powertraces"),
        description="Map scrutiny-power-traces-analyzer Traces comparer JSON into scrutiny-viz JSON.",
    )

    def ingest(self, source_path: Path) -> dict[str, Any]:
        src = Path(source_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Traces comparer input path does not exist: {src}")
        if not src.is_file():
            raise ValueError(f"Traces comparer mapper expects a JSON file, got: {src}")

        doc = mapper_utils.read_json_file(src)
        if doc is None:
            raise ValueError(f"Failed to parse JSON from: {src}")

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
                    "pipeline_comparisons_json": _dump(pipeline_comparisons),
                    "execution_times_json": _dump(execution_times),
                }
            )

        out["TRACE_OPERATIONS"] = rows
        return out

    def _extract_module_data(self, doc: dict[str, Any]) -> tuple[dict[str, Any], str | None, str | None]:
        if isinstance(doc.get("modules"), dict):
            modules = doc["modules"]
            tc = modules.get("TRACES_COMPARER")
            if isinstance(tc, dict):
                module_data = tc.get("module_data") or {}
                card_code = module_data.get("card_code") or doc.get("name")
                module_name = tc.get("module_name") or tc.get("name")
                if isinstance(module_data, dict) and "results" in module_data:
                    return module_data, card_code, module_name

        if isinstance(doc.get("module_data"), dict) and "results" in doc["module_data"]:
            module_data = doc["module_data"]
            return module_data, module_data.get("card_code"), doc.get("module_name")

        if "results" in doc:
            return doc, doc.get("card_code"), doc.get("module_name")

        raise ValueError("Unsupported Traces comparer JSON structure: could not find results")

    def _sanitize_pipeline_comparisons(self, pipelines: list[dict[str, Any]], source_dir: Path) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        for pipeline in pipelines:
            comparisons = []
            for comp in (pipeline.get("comparisons") or []):
                raw_path = str(comp.get("file_path") or "")
                resolved_path = self._resolve_asset(source_dir, raw_path)
                comparisons.append(
                    {
                        "distance": float(comp.get("distance", 0.0) or 0.0),
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
        for et in exec_times:
            cleaned.append(
                {
                    "unit": str(et.get("unit") or ""),
                    "time": float(et.get("time", 0.0) or 0.0),
                }
            )
        return cleaned

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


PLUGIN = TracesCompareMapper()
PLUGINS = [PLUGIN]