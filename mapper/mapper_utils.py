# scrutiny-viz/mapper/mapper_utils.py
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ---------- IO / grouping ----------

def load_file(path: str) -> Optional[list[list[str]]]:
    try:
        logger.info(f"Loading file: {path}")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return prepare_lines(content.splitlines())
    except FileNotFoundError:
        logger.error(f"File not found: {path}")
    except Exception as e:
        logger.exception(f"An error occurred while reading {path}: {e}")
    return None


def prepare_lines(lines: list[str]) -> list[list[str]]:
    result: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.strip() == "":
            if current:
                result.append(current)
                current = []
        else:
            current.append(line.strip())
    if current:
        result.append(current)
    return result


def flatten_groups(groups: list[list[str]]) -> list[str]:
    out: list[str] = []
    for g in groups:
        out.extend(g)
    return out


# ---------- Simple schema-ish helpers ----------

def create_attribute(name: str, value: str) -> dict[str, str]:
    return {"name": name, "value": value}


def parse_name_value_attributes(
    lines: list[str],
    delimiter: str,
    *,
    allow_single_value: bool = False,
) -> list[dict[str, str]]:
    attrs: list[dict[str, str]] = []
    for line in lines:
        s = (line or "").strip()
        if not s:
            continue
        parts = s.split(delimiter)
        if len(parts) >= 2:
            name = parts[0].strip()
            value = parts[1].strip()
            if name:
                attrs.append(create_attribute(name, value))
        elif allow_single_value:
            attrs.append(create_attribute(s, ""))
    return attrs


# ---------- Exclusions ----------

def load_exclusions(path: str) -> set[str]:
    excluded: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                trimmed = line.strip()
                if not trimmed or trimmed.startswith("#"):
                    continue
                excluded.add(trimmed)
        logger.info(f"Loaded {len(excluded)} excluded propertie(s) from {path}")
    except FileNotFoundError:
        logger.error(f"Exclusion file not found: {path}")
    except Exception as e:
        logger.exception(f"Failed to read exclusion file {path}: {e}")
    return excluded


def apply_exclusions(result: dict, excluded: set[str]) -> dict:
    if not excluded:
        return result

    filtered: dict = {}
    removed_count = 0

    for section, value in result.items():
        if isinstance(section, str) and section.startswith("_"):
            filtered[section] = value
            continue

        if not isinstance(value, list):
            filtered[section] = value
            continue

        if not value or not all(isinstance(x, dict) and "name" in x for x in value):
            filtered[section] = value
            continue

        kept: list[dict] = []
        for attr in value:
            if attr.get("name") in excluded:
                removed_count += 1
                continue
            kept.append(attr)
        filtered[section] = kept

    logger.info(f"Excluded {removed_count} attribute(s) by name")
    return filtered


# ---------- Conversions ----------

def to_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s.replace(",", ".")))
        except ValueError:
            return None


def to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def to_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in {"true", "yes", "y", "1"}:
        return True
    if s in {"false", "no", "n", "0"}:
        return False
    return None


# ---------- Parsing helpers ----------

def parse_kv_pairs(parts: list[str], start: int = 1) -> dict[str, str]:
    out: dict[str, str] = {}
    i = start
    while i < len(parts) - 1:
        k = (parts[i] or "").strip()
        v = (parts[i + 1] or "").strip()
        if k.endswith(":"):
            k = k[:-1].strip()
        if k:
            out[k] = v
        i += 2
    return out


def parse_colon_pairs_line(line: str, delimiter: str) -> dict[str, str]:
    parts = [p.strip() for p in (line or "").split(delimiter)]
    cfg: dict[str, str] = {}
    i = 0
    while i < len(parts) - 1:
        k = parts[i]
        if k.endswith(":"):
            key = k[:-1].strip()
            val = parts[i + 1].strip()
            if key:
                cfg[key] = val
            i += 2
        else:
            i += 1
    return cfg


def compact_config(cfg: dict[str, str], keys: list[str]) -> str:
    chunks: list[str] = []
    for k in keys:
        v = (cfg.get(k) or "").strip()
        if v:
            chunks.append(f"{k}={v}")
    return ";".join(chunks)


def flush_block(
    result: dict[str, Any],
    section: Optional[str],
    lines: list[str],
    parse_fn: Callable[..., Optional[dict]],
    *parse_args: Any,
) -> list[str]:
    if section and lines:
        rec = parse_fn(lines, *parse_args)
        if rec:
            result.setdefault(section, []).append(rec)
    return []