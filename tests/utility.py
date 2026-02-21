# scrutiny-viz/tests/utility.py
from __future__ import annotations
import json
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import yaml


# -------------------------
# Paths
# -------------------------

# Returns repository root (one level above tests/).
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


# Builds an absolute path inside the repo from path parts.
def repo_path(*parts: str) -> Path:
    return project_root().joinpath(*parts)


# Returns production module YAML path under scrutiny/javacard/modules/.
def production_module_yml(name: str) -> Path:
    return repo_path("scrutiny", "schema", name)


# Returns the examples directory path used for fixtures (data/examples).
def examples_dir() -> Path:
    return repo_path("data", "examples")


# Returns the output directory used by report_html.py (results).
def results_dir() -> Path:
    return repo_path("results")


# Returns the report generator script path (report_html.py in repo root).
def report_html_path() -> Path:
    return repo_path("report_html.py")


# -------------------------
# Loaders
# -------------------------

# Loads a YAML file into a dict (fails if the root isn't a mapping).
def load_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"YAML did not parse into dict: {path}")
    return data


# Loads a JSON file into a dict (fails if the root isn't a mapping).
def load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"JSON did not parse into dict: {path}")
    return data


# Checks whether a dict looks like the report JSON consumed by report_html.py.
def is_report_json(d: Dict[str, Any]) -> bool:
    return (
        isinstance(d.get("overall"), str)
        and isinstance(d.get("theme"), str)
        and isinstance(d.get("sections"), dict)
    )


# -------------------------
# Deep merge / schema helpers
# -------------------------

# Recursively merges dict b into dict a (returns a new dict, does not mutate inputs).
def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


# Flattens production YAML (defaults + sections) into per-section configs with defaults merged.
def flatten_prod_schema(schema_yml: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    defaults = schema_yml.get("defaults", {}) or {}
    default_section = {
        "data": defaults.get("data", {}) or {},
        "component": defaults.get("component", {}) or {},
        "report": defaults.get("report", {}) or {},
        "target": defaults.get("target", {}) or {},
        "severity": defaults.get("severity", {}) or {},
    }

    sections = schema_yml.get("sections", {}) or {}
    if not isinstance(sections, dict):
        raise AssertionError("schema.sections must be a dict")

    out: Dict[str, Dict[str, Any]] = {}
    for name, sec_cfg in sections.items():
        sec_cfg = sec_cfg or {}
        if not isinstance(sec_cfg, dict):
            raise AssertionError(f"schema.sections.{name} must be dict")

        merged = deep_merge(default_section, sec_cfg)

        # ---- CRITICAL OVERRIDE: record_schema replaces defaults, not merges ----
        if isinstance(sec_cfg.get("data"), dict) and "record_schema" in (sec_cfg.get("data") or {}):
            rs = (sec_cfg["data"] or {}).get("record_schema")
            if rs is not None:
                if not isinstance(merged.get("data"), dict):
                    merged["data"] = {}
                merged["data"]["record_schema"] = deepcopy(rs)

        out[name] = merged

    return out


# Converts production YAML into the per-section schema shape expected by JsonParser (with invariants checked).
def build_parser_schema_from_production_yml(schema_yml: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    flat = flatten_prod_schema(schema_yml)

    # Basic invariants expected by JsonParser
    for name, merged in flat.items():
        if "data" not in merged or not isinstance(merged["data"], dict):
            raise AssertionError(f"{name}: missing data")
        if "record_schema" not in merged["data"] or not isinstance(merged["data"]["record_schema"], dict):
            raise AssertionError(f"{name}: missing data.record_schema")
        comp = merged.get("component", {}) or {}
        if not isinstance(comp, dict):
            raise AssertionError(f"{name}: component must be dict")
        if not comp.get("match_key"):
            raise AssertionError(f"{name}: missing component.match_key")

    return flat


# Extracts report.types from an already-merged section config (flatten_prod_schema output).
def effective_types(section_cfg: Dict[str, Any]) -> List[str]:
    rep = section_cfg.get("report", {}) or {}
    types = rep.get("types")
    flat: List[str] = []

    if isinstance(types, list):
        for t in types:
            if isinstance(t, str):
                flat.append(t.strip().lower())
            elif isinstance(t, dict) and t.get("type"):
                flat.append(str(t["type"]).strip().lower())
    elif isinstance(types, str):
        flat.extend([x.strip().lower() for x in types.split(",") if x.strip()])

    return [x for x in flat if x]


# Resolves report.types for a section using defaults/overrides without flattening the whole schema.
def effective_report_types(schema_yml: Dict[str, Any], section_name: str) -> List[str]:
    defaults = schema_yml.get("defaults", {}) if isinstance(schema_yml.get("defaults"), dict) else {}
    drep = defaults.get("report", {}) if isinstance(defaults.get("report"), dict) else {}
    types = drep.get("types")

    sections = schema_yml.get("sections", {}) or {}
    sec = sections.get(section_name, {}) if isinstance(sections, dict) else {}
    if isinstance(sec, dict):
        rep = sec.get("report", {})
        if isinstance(rep, dict) and rep.get("types") is not None:
            types = rep.get("types")

    flat: List[str] = []
    if isinstance(types, list):
        for t in types:
            if isinstance(t, str):
                flat.append(t.strip().lower())
            elif isinstance(t, dict) and t.get("type"):
                flat.append(str(t["type"]).strip().lower())
    elif isinstance(types, str):
        flat.extend([x.strip().lower() for x in types.split(",") if x.strip()])

    return [x for x in flat if x]


# -------------------------
# Raw fixture discovery for JsonParser
# -------------------------

# Checks whether a raw JSON dict includes ALL required sections as list-valued keys.
def raw_json_matches_all_sections(raw: Dict[str, Any], section_names: Iterable[str]) -> bool:
    if not isinstance(raw, dict):
        return False
    for s in section_names:
        if s not in raw or not isinstance(raw[s], list):
            return False
    return True


# Searches data/examples for a raw JSON fixture containing ALL schema sections (JsonParser input shape).
def find_raw_fixture(examples: Path, section_names: List[str]) -> Optional[Path]:
    for p in sorted(examples.rglob("*.json"), key=lambda x: str(x).lower()):
        try:
            raw = load_json(p)
        except Exception:
            continue
        if raw_json_matches_all_sections(raw, section_names):
            return p
    return None


# Alias kept for readability at call sites (find_raw_fixture already accepts sections).
def find_raw_fixture_for_sections(examples: Path, section_names: List[str]) -> Optional[Path]:
    return find_raw_fixture(examples, section_names)


# Verifies match_key and required:true fields exist in parsed entries (expects flatten_prod_schema output).
def assert_required_fields_flat_schema(flat_schema: Dict[str, Dict[str, Any]], parsed: Dict[str, List[Dict[str, Any]]]) -> None:
    for sec_name, sec_cfg in flat_schema.items():
        entries = parsed.get(sec_name)
        if not isinstance(entries, list):
            raise AssertionError(f"{sec_name}: parsed section must be a list")

        data_cfg = sec_cfg.get("data", {}) or {}
        field_defs = data_cfg.get("record_schema", {}) or {}
        comp = sec_cfg.get("component", {}) or {}
        match_key = comp.get("match_key")

        if not match_key:
            raise AssertionError(f"{sec_name}: missing component.match_key")

        required = []
        for fname, fdef in field_defs.items():
            if fname == match_key or bool((fdef or {}).get("required", False)):
                required.append(fname)

        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise AssertionError(f"{sec_name}[{i}] entry must be dict")
            for rf in required:
                if rf not in entry:
                    raise AssertionError(f"{sec_name}[{i}] missing required field '{rf}'")


# Same required-field check, but named for the parser_schema (which is also a flat schema).
def assert_required_fields_present(parser_schema: Dict[str, Dict[str, Any]], parsed: Dict[str, List[Dict[str, Any]]]) -> None:
    assert_required_fields_flat_schema(parser_schema, parsed)


# Builds a minimal raw JSON that satisfies JsonParser requirements for every section.
def build_minimal_raw_json(parser_schema: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    raw: Dict[str, Any] = {}
    for sec_name, sec_cfg in parser_schema.items():
        data_cfg = sec_cfg.get("data", {}) or {}
        field_defs = data_cfg.get("record_schema", {}) or {}
        match_key = (sec_cfg.get("component") or {}).get("match_key")
        if not match_key:
            raise AssertionError(f"{sec_name}: missing component.match_key")

        entry: Dict[str, Any] = {match_key: "DUMMY"}

        for fname, fdef in field_defs.items():
            if fname == match_key:
                continue
            if bool((fdef or {}).get("required", False)):
                entry[fname] = "DUMMY"

        raw[sec_name] = [entry]
    return raw


# -------------------------
# Report HTML helpers
# -------------------------

# Returns a stable issues-first ordering of sections (WARN/SUSP first, then MATCH), preserving order within groups.
def iter_sections_issues_first_stable(report: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    items = list((report.get("sections") or {}).items())
    issues, matches = [], []
    for name, sec in items:
        st = str(sec.get("result", "WARN")).upper().strip()
        (matches if st == "MATCH" else issues).append((name, sec))
    return issues + matches


# Extracts the rendered module order from report_html.py output by parsing the module headings.
def extract_module_order_from_html(html: str) -> List[str]:
    return re.findall(r">Module:\s*([^<]+)</h2>", html)


# Finds the opening <div ...> tag for a given id (used to check default collapse style).
def find_opening_div_tag(html: str, div_id: str) -> Optional[str]:
    m = re.search(rf'<div[^>]*\bid="{re.escape(div_id)}"[^>]*>', html, flags=re.IGNORECASE)
    return m.group(0) if m else None


# Detects whether a div opening tag contains "display: none" (collapsed by default).
def div_is_collapsed(opening_tag: str) -> bool:
    return re.search(r"display\s*:\s*none", opening_tag, flags=re.IGNORECASE) is not None


# Runs report_html.py on a report JSON input and returns the produced results/<out_name> path.
def run_report_html(
    report_json: Path,
    out_name: str,
    *,
    cwd: Optional[Path] = None,
    extra_args: Optional[List[str]] = None
) -> Path:
    cwd = cwd or project_root()
    extra_args = extra_args or []

    results_dir().mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, str(report_html_path()), "-p", str(report_json), "-o", out_name, *extra_args]
    subprocess.check_call(cmd, cwd=str(cwd))

    return results_dir() / out_name


# Best-effort file delete helper for cleaning up generated artifacts.
def safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except Exception:
        pass
