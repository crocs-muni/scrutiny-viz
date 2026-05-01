# scrutiny-viz/scrutiny/schemaloader.py
from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Dict, Optional

import yaml

from scrutiny import logging as slog
from scrutiny.errors import SchemaError
from scrutiny.validation import require_file

log = slog.get_logger("SCHEMA")

_ALLOWED_CATEGORIES = {"ordinal", "nominal", "continuous", "binary", "set"}
_SUPPORTED_SCHEMA_VERSIONS = {"0.11", "0.12", "0.13"}


class LoadedSchema(dict):
    """Dict-like schema with loader metadata attached."""

    def __init__(self, *args, loader_meta: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._loader_meta: Dict[str, Any] = loader_meta or {}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-merge dicts with 'explicit null clears default' semantics."""
    out = deepcopy(base) if base else {}
    for key, value in (override or {}).items():
        if value is None:
            out[key] = None
        elif isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class SchemaLoader:
    """
    Load a YAML schema and normalize it into the structure used by ingestion and verification.
    """

    def __init__(self, yaml_path: str, *, strict: bool = True):
        self.yaml_path = yaml_path
        self.strict = strict

    def _warn_or_raise(self, msg: str, *, fatal: bool = False) -> None:
        if fatal or self.strict:
            log.err(msg)
            raise SchemaError(msg)
        log.warn(msg)

    def _validate_category(self, field_name: str, category: Optional[str], section: str) -> None:
        if category and category not in _ALLOWED_CATEGORIES:
            self._warn_or_raise(
                f"Section '{section}': field '{field_name}' has unknown category '{category}'. "
                f"Allowed: {sorted(_ALLOWED_CATEGORIES)}",
                fatal=False,
            )

    def _normalize_record_schema(self, record_schema: Dict[str, Any], section: str) -> Dict[str, Dict[str, Any]]:
        normalized: Dict[str, Dict[str, Any]] = {}
        for field_name, field_def in (record_schema or {}).items():
            if isinstance(field_def, str):
                normalized[field_name] = {"dtype": field_def}
                continue

            if not isinstance(field_def, dict):
                self._warn_or_raise(
                    f"Section '{section}': record_schema for field '{field_name}' must be string or map.",
                    fatal=True,
                )

            if "dtype" not in field_def:
                self._warn_or_raise(
                    f"Section '{section}': field '{field_name}' requires 'dtype'.",
                    fatal=True,
                )

            field_copy = dict(field_def)
            self._validate_category(field_name, field_copy.get("category"), section)
            normalized[field_name] = field_copy

        return normalized

    def _normalize_theme(self, theme_raw: Any, section: str) -> str | None:
        if theme_raw is None:
            return None
        theme = str(theme_raw).strip().lower()
        if theme not in {"light", "dark"}:
            self._warn_or_raise(
                f"Section '{section}': report.theme must be 'light' or 'dark' if provided.",
                fatal=True,
            )
        return theme

    def _parse_report_types(self, maybe_types: Any, section: str) -> list[Dict[str, Any]] | None:
        if maybe_types is None:
            return None

        if isinstance(maybe_types, dict):
            maybe_types = maybe_types.get("types")
            if maybe_types is None:
                return None

        normalized: list[Dict[str, Any]] = []

        if isinstance(maybe_types, str):
            for item in (piece.strip() for piece in maybe_types.split(",")):
                if item:
                    normalized.append({"type": item.lower(), "variant": None})
            return normalized

        if not isinstance(maybe_types, list):
            self._warn_or_raise(
                f"Section '{section}': report.types must be string/list/null.",
                fatal=True,
            )
            return None

        for item in maybe_types:
            if item is None:
                continue

            if isinstance(item, str):
                value = item.strip().lower()
                if value:
                    normalized.append({"type": value, "variant": None})
                continue

            if not isinstance(item, dict):
                self._warn_or_raise(
                    f"Section '{section}': report.types items must be string or map.",
                    fatal=True,
                )

            type_name = str(item.get("type") or "").strip().lower()
            if not type_name:
                self._warn_or_raise(
                    f"Section '{section}': report.types entry missing 'type'.",
                    fatal=True,
                )

            variant = item.get("variant")
            variant = str(variant).strip().lower() if variant is not None and str(variant).strip() else None
            normalized.append({"type": type_name, "variant": variant})

        return normalized

    def _safe_read_doc(self, rel_path: Any, section: str) -> str | None:
        if rel_path is None:
            return None

        relative_path = str(rel_path).strip()
        if not relative_path:
            return None

        base_dir = os.path.dirname(os.path.abspath(self.yaml_path))
        abs_path = os.path.abspath(os.path.join(base_dir, relative_path))

        if os.path.commonpath([base_dir, abs_path]) != base_dir:
            self._warn_or_raise(
                f"Section '{section}': report.doc path must stay within the schema directory.",
                fatal=True,
            )

        extension = os.path.splitext(abs_path)[1].lower()
        if extension not in {".txt", ".md"}:
            self._warn_or_raise(
                f"Section '{section}': report.doc must point to a .txt or .md file.",
                fatal=True,
            )

        if not os.path.isfile(abs_path):
            self._warn_or_raise(
                f"Section '{section}': report.doc file not found: {relative_path}",
                fatal=True,
            )

        try:
            if os.path.getsize(abs_path) > 64 * 1024:
                self._warn_or_raise(
                    f"Section '{section}': report.doc is too large (>64KB): {relative_path}",
                    fatal=True,
                )
        except Exception:
            pass

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as exc:
            raise SchemaError(f"Section '{section}': failed to read report.doc file: {relative_path} ({exc})") from exc

    def _normalize_defaults(self, defaults: Dict[str, Any]) -> Dict[str, Any]:
        data_defaults = defaults.get("data", {}) or {}
        if data_defaults.get("type") and data_defaults["type"] != "list":
            self._warn_or_raise("defaults.data.type must be 'list' if provided.", fatal=True)

        report_raw = defaults.get("report", {}) or {}
        report_types = self._parse_report_types(
            report_raw.get("types", report_raw) if isinstance(report_raw, dict) else report_raw,
            "defaults",
        )
        theme = self._normalize_theme(
            report_raw.get("theme") if isinstance(report_raw, dict) else None,
            "defaults",
        )
        doc = report_raw.get("doc") if isinstance(report_raw, dict) else None

        component_defaults = defaults.get("component", {}) or {}
        target_defaults = defaults.get("target", {}) or {}

        return {
            "data": {"type": "list", **({} if not data_defaults else data_defaults)},
            "report": {
                "types": report_types,
                "theme": theme,
                "doc": doc,
                "doc_text": None,
            },
            "component": {
                "comparator": component_defaults.get("comparator"),
                "match_key": component_defaults.get("match_key"),
                "show_key": component_defaults.get("show_key"),
                "include_matches": bool(component_defaults.get("include_matches", False)),
                "threshold_ratio": component_defaults.get("threshold_ratio"),
                "threshold_count": component_defaults.get("threshold_count"),
            },
            "target": dict(target_defaults),
        }

    def _normalize_ingest_options(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        ingest_raw = raw.get("ingest", {}) or {}
        if not isinstance(ingest_raw, dict):
            self._warn_or_raise("Top-level 'ingest' must be a mapping if provided.", fatal=True)

        return {
            "dynamic_sections": bool(ingest_raw.get("dynamic_sections", False)),
            "strict_sections": bool(ingest_raw.get("strict_sections", False)),
            "allow_missing_sections": bool(ingest_raw.get("allow_missing_sections", True)),
        }

    def _build_component(
        self,
        *,
        section_name: str,
        component_cfg: Dict[str, Any],
        record_schema_norm: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        comparator = str(component_cfg.get("comparator") or "").strip().lower()
        if not comparator:
            self._warn_or_raise(
                f"Section '{section_name}': component.comparator is mandatory.",
                fatal=True,
            )

        match_key = component_cfg.get("match_key")
        if not match_key:
            self._warn_or_raise(
                f"Section '{section_name}': component.match_key is mandatory.",
                fatal=True,
            )
        if match_key not in record_schema_norm:
            self._warn_or_raise(
                f"Section '{section_name}': component.match_key '{match_key}' must exist in data.record_schema.",
                fatal=True,
            )

        show_key = component_cfg.get("show_key")
        if show_key is not None and show_key not in record_schema_norm:
            self._warn_or_raise(
                f"Section '{section_name}': component.show_key '{show_key}' not in data.record_schema; "
                f"falling back to match_key '{match_key}'.",
                fatal=False,
            )
            show_key = None

        return {
            "comparator": comparator,
            "match_key": match_key,
            "show_key": show_key,
            "include_matches": bool(component_cfg.get("include_matches", False)),
            "threshold_ratio": component_cfg.get("threshold_ratio"),
            "threshold_count": component_cfg.get("threshold_count"),
        }

    def _build_section(
        self,
        section_name: str,
        section_cfg: Dict[str, Any],
        defaults_norm: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = {
            bucket: _deep_merge(defaults_norm.get(bucket, {}), section_cfg.get(bucket, {}))
            for bucket in ("data", "report", "component", "target")
        }

        section_data = section_cfg.get("data") or {}
        if isinstance(section_data, dict) and "record_schema" in section_data:
            merged["data"]["record_schema"] = section_data.get("record_schema")

        data_cfg = merged["data"] or {}
        if data_cfg.get("type") != "list":
            self._warn_or_raise(f"Section '{section_name}': data.type must be 'list'.", fatal=True)

        record_schema = data_cfg.get("record_schema", {})
        if not isinstance(record_schema, dict) or not record_schema:
            self._warn_or_raise(
                f"Section '{section_name}': data.record_schema must be a non-empty map.",
                fatal=True,
            )

        record_schema_norm = self._normalize_record_schema(record_schema, section_name)

        report_cfg = merged["report"] or {}
        report_doc = report_cfg.get("doc")
        report = {
            "types": self._parse_report_types(report_cfg.get("types"), section_name),
            "theme": self._normalize_theme(report_cfg.get("theme"), section_name),
            "doc": report_doc,
            "doc_text": self._safe_read_doc(report_doc, section_name) if report_doc else None,
        }

        component = self._build_component(
            section_name=section_name,
            component_cfg=merged["component"] or {},
            record_schema_norm=record_schema_norm,
        )

        return {
            "data": {"type": "list", "record_schema": record_schema_norm},
            "report": report,
            "component": component,
            "target": merged["target"] or {},
        }

    def load(self) -> LoadedSchema:
        schema_path = require_file(self.yaml_path, label="Schema file", component="SCHEMA")
        try:
            with schema_path.open("r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise SchemaError(f"Schema file is not valid YAML: {schema_path} ({exc})") from exc
        except OSError as exc:
            raise SchemaError(f"Failed to read schema file: {schema_path} ({exc})") from exc

        version = str(raw.get("schema_version", "")).strip()
        if version not in _SUPPORTED_SCHEMA_VERSIONS:
            self._warn_or_raise(
                f"Unsupported or missing schema_version '{version}'. Supported: "
                f"{sorted(_SUPPORTED_SCHEMA_VERSIONS)}",
                fatal=True,
            )

        defaults_norm = self._normalize_defaults(raw.get("defaults", {}) or {})
        ingest_opts = self._normalize_ingest_options(raw)

        sections_raw = raw.get("sections") or {}
        if not isinstance(sections_raw, dict):
            self._warn_or_raise("Top-level 'sections' must be a mapping.", fatal=True)
        if not sections_raw and not ingest_opts["dynamic_sections"]:
            self._warn_or_raise("No sections defined.", fatal=True)

        out: Dict[str, Dict[str, Any]] = {}
        for section_name, section_cfg in sections_raw.items():
            if not isinstance(section_cfg, dict):
                self._warn_or_raise(f"Section '{section_name}' must be a mapping.", fatal=True)
            out[section_name] = self._build_section(section_name, section_cfg, defaults_norm)

        dynamic_template = None
        if ingest_opts["dynamic_sections"]:
            dynamic_template = self._build_section("__dynamic_defaults__", {}, defaults_norm)

        loader_meta = {
            "schema_version": version,
            "defaults": defaults_norm,
            "dynamic_sections": ingest_opts["dynamic_sections"],
            "strict_sections": ingest_opts["strict_sections"],
            "allow_missing_sections": ingest_opts["allow_missing_sections"],
            "dynamic_template": dynamic_template,
            "skipped_sections": [],
        }

        return LoadedSchema(out, loader_meta=loader_meta)
