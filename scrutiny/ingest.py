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
    """

    def __init__(self, schema: Dict[str, Dict[str, Any]]):
        self.schema = schema

    def parse(self, json_path: str) -> Dict[str, List[Dict]]:
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        parsed: Dict[str, List[Dict]] = {}
        for section_name, section_cfg in self.schema.items():
            data_cfg = section_cfg["data"]
            field_defs = data_cfg["record_schema"]
            match_key = section_cfg.get("component", {}).get("match_key")

            if section_name not in raw:
                raise KeyError(f"Missing section: '{section_name}'")

            entries = raw[section_name]
            if not isinstance(entries, list):
                raise TypeError(f"Section '{section_name}' must be a list, got {type(entries).__name__}")

            validated: List[Dict] = []
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
