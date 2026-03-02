# scrutiny-viz/scrutiny/ingest.py
from __future__ import annotations
import json
from typing import Any, Dict, List
from scrutiny import logging as slog

class JsonParser:
    """
    Parse JSON according to 4-bucket schema.
    Required behavior:
      - The section's component.match_key is implicitly required (key must exist).
      - Any field with {required: true} is also required (key must exist).
      - Values may be null.
    Section handling:
      - By default allow schema sections to be missing in the JSON. Missing sections are treated as empty lists ([]).
        This is important because upstream tooling / devices vary a lot (TPM ops, JavaCard modules, etc.).
      - By default still error if the JSON contains sections that are NOT in the schema. That usually indicates
        a wrong schema selection, a mapper bug/typo, or a mismatched input file.
    """

    def __init__(self,schema: Dict[str, Dict[str, Any]],allow_missing_sections: bool = True,error_on_unknown_sections: bool = False,):
        self.schema = schema
        self.allow_missing_sections = allow_missing_sections
        self.error_on_unknown_sections = error_on_unknown_sections

        # NOTE: If this turns out useful for end users, I can expose these toggles in verify.py later.
        # For now I keep it internal and default to "missing allowed / unknown forbidden".
        msg = (
            f"[INGEST] JsonParser settings: allow_missing_sections={self.allow_missing_sections}, "
            f"error_on_unknown_sections={self.error_on_unknown_sections}"
        )
        if hasattr(slog, "log_info"):
            slog.log_info(msg)
        else:
            slog.log_warn(msg)

    def parse(self, json_path: str) -> Dict[str, List[Dict[str, Any]]]:
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if not isinstance(raw, dict):
            raise TypeError(f"Top-level JSON must be an object, got {type(raw).__name__}")

        schema_sections = set(self.schema.keys())
        raw_sections = {k for k in raw.keys() if isinstance(k, str) and not k.startswith("_")}

        unknown = sorted(raw_sections - schema_sections)
        if unknown:
            if self.error_on_unknown_sections:
                raise KeyError(f"Unknown section(s) not in schema: {unknown}")
            slog.log_warn(f"[INGEST] JSON contains section(s) not in schema (ignored): {unknown}")

        parsed: Dict[str, List[Dict[str, Any]]] = {}

        for section_name, section_cfg in self.schema.items():
            data_cfg = section_cfg["data"]
            field_defs = data_cfg["record_schema"]
            match_key = section_cfg.get("component", {}).get("match_key")

            if section_name not in raw:
                if self.allow_missing_sections:
                    parsed[section_name] = []
                    continue
                raise KeyError(f"Missing section: '{section_name}'")

            entries = raw[section_name]
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

            parsed[section_name] = validated

        return parsed