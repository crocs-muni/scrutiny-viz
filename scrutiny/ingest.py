# scrutiny-viz/scrutiny/ingest.py
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, List, Optional

from scrutiny import logging as slog

ingest_log = slog.get_logger("INGEST")


class ParsedJson(dict):
    """Dict-like parsed JSON with ingest metadata attached."""

    def __init__(self, *args, ingest_meta: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._ingest_meta: Dict[str, Any] = ingest_meta or {}


class JsonParser:
    """
    Parse JSON according to schema buckets.

    Required behavior:
      - The section's component.match_key is implicitly required.
      - Any field with {required: true} is also required.
      - Values may be null.

    Dynamic sections:
      - If schema metadata enables dynamic_sections and strict_sections is False,
        unknown sections inherit the normalized defaults/template and are added to
        the active schema on the fly.
      - If strict_sections is True, unknown sections are an error.
      - Dynamic sections that do not validate in permissive mode are skipped with
        a warning and tracked in skipped_sections.
      - For every successfully adopted dynamic section, the fully resolved section
        config is stored in ingest metadata under dynamic_section_configs.

    Missing declared sections:
      - If allow_missing_sections is True, missing schema sections become [].
    """

    def __init__(
        self,
        schema: Dict[str, Dict[str, Any]],
        allow_missing_sections: Optional[bool] = None,
        error_on_unknown_sections: Optional[bool] = None,
        dynamic_sections: Optional[bool] = None,
        strict_sections: Optional[bool] = None,
    ):
        self.schema = schema
        self._schema_meta = getattr(schema, "_loader_meta", {}) or {}

        self.allow_missing_sections = (
            self._schema_meta.get("allow_missing_sections", True)
            if allow_missing_sections is None else allow_missing_sections
        )
        self.dynamic_sections = (
            self._schema_meta.get("dynamic_sections", False)
            if dynamic_sections is None else dynamic_sections
        )
        self.strict_sections = (
            self._schema_meta.get("strict_sections", False)
            if strict_sections is None else strict_sections
        )
        self.error_on_unknown_sections = (
            self.strict_sections
            if error_on_unknown_sections is None else error_on_unknown_sections
        )

        msg = (
            f"JsonParser settings: allow_missing_sections={self.allow_missing_sections}, "
            f"dynamic_sections={self.dynamic_sections}, strict_sections={self.strict_sections}, "
            f"error_on_unknown_sections={self.error_on_unknown_sections}"
        )
        ingest_log.info(msg)

    def _validate_entries(
        self,
        section_name: str,
        section_cfg: Dict[str, Any],
        entries: Any,
    ) -> List[Dict[str, Any]]:
        data_cfg = section_cfg["data"]
        field_defs = data_cfg["record_schema"]
        match_key = section_cfg.get("component", {}).get("match_key")

        if not isinstance(entries, list):
            raise TypeError(f"Section '{section_name}' must be a list, got {type(entries).__name__}")

        validated: List[Dict[str, Any]] = []
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise TypeError(f"Entry #{idx} in '{section_name}' is not an object")

            normalized_entry: Dict[str, Any] = dict(entry)

            for fname, fdef in field_defs.items():
                explicitly_required = bool(fdef.get("required", False))
                is_required = (fname == match_key) or explicitly_required

                has_key = fname in entry
                if is_required and not has_key:
                    raise KeyError(f"Entry #{idx} in '{section_name}' missing required field '{fname}'")

                if has_key:
                    normalized_entry[fname] = entry.get(fname, None)

            validated.append(normalized_entry)

        return validated

    def _record_skipped(self, section: str, reason: str) -> None:
        item = {"section": section, "reason": reason}
        skipped = self._schema_meta.setdefault("skipped_sections", [])
        if item not in skipped:
            skipped.append(item)

    def parse(self, json_path: str) -> ParsedJson:
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if not isinstance(raw, dict):
            raise TypeError(f"Top-level JSON must be an object, got {type(raw).__name__}")

        explicit_section_names = [
            k for k in self.schema.keys()
            if isinstance(k, str) and not k.startswith("_")
        ]
        schema_sections = set(explicit_section_names)
        raw_sections = {k for k in raw.keys() if isinstance(k, str) and not k.startswith("_")}
        unknown = sorted(raw_sections - schema_sections)

        parsed = ParsedJson(
            ingest_meta={
                "dynamic_sections": self.dynamic_sections,
                "strict_sections": self.strict_sections,
                "allow_missing_sections": self.allow_missing_sections,
                "applied_dynamic_sections": [],
                "dynamic_section_configs": {},
                "skipped_sections": [],
            }
        )

        # Validate declared schema sections first.
        for section_name in explicit_section_names:
            section_cfg = self.schema[section_name]

            if section_name not in raw:
                if self.allow_missing_sections:
                    parsed[section_name] = []
                    continue
                raise KeyError(f"Missing section: '{section_name}'")

            parsed[section_name] = self._validate_entries(section_name, section_cfg, raw[section_name])

        # Handle previously unknown sections.
        if unknown:
            if self.dynamic_sections:
                if self.strict_sections or self.error_on_unknown_sections:
                    raise KeyError(f"Unknown section(s) not in schema: {unknown}")

                template = self._schema_meta.get("dynamic_template")
                if not isinstance(template, dict):
                    ingest_log.warn(
                        f"Dynamic sections requested but no dynamic template is available. Ignored: {unknown}"
                    )
                else:
                    for section_name in unknown:
                        try:
                            section_cfg = deepcopy(template)
                            validated = self._validate_entries(section_name, section_cfg, raw[section_name])

                            # Extend the active schema so later verification/reporting can see it.
                            self.schema[section_name] = section_cfg

                            # Store validated rows.
                            parsed[section_name] = validated

                            # Track which dynamic sections were adopted.
                            parsed._ingest_meta["applied_dynamic_sections"].append(section_name)

                            # Store the resolved config explicitly for downstream consumers.
                            parsed._ingest_meta["dynamic_section_configs"][section_name] = deepcopy(section_cfg)

                            ingest_log.info(f"Applied defaults dynamically to section '{section_name}'")
                        except Exception as exc:
                            reason = str(exc)
                            ingest_log.warn(f"Skipping dynamic section '{section_name}': {reason}")
                            self._record_skipped(section_name, reason)
                            parsed._ingest_meta["skipped_sections"].append(
                                {"section": section_name, "reason": reason}
                            )
            else:
                if self.error_on_unknown_sections or self.strict_sections:
                    raise KeyError(f"Unknown section(s) not in schema: {unknown}")
                ingest_log.warn(f"JSON contains section(s) not in schema (ignored): {unknown}")

        if parsed._ingest_meta["applied_dynamic_sections"]:
            parsed["_dynamic_sections"] = list(parsed._ingest_meta["applied_dynamic_sections"])
        if parsed._ingest_meta["skipped_sections"]:
            parsed["_skipped_sections"] = list(parsed._ingest_meta["skipped_sections"])

        return parsed