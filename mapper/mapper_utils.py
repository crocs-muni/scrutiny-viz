# scrutiny-viz/mapper/mapper_utils.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ---------- IO helpers ----------

def read_text_file(path: str | Path) -> Optional[str]:
    try:
        p = Path(path)
        logger.info("Loading text file: %s", p)
        return p.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        logger.error("File not found: %s", path)
    except Exception as e:
        logger.exception("An error occurred while reading %s: %s", path, e)
    return None


def require_text_file(path: str | Path) -> str:
    data = read_text_file(path)
    if data is None:
        raise FileNotFoundError(f"Failed to load text file: {path}")
    return data


def read_json_file(path: str | Path) -> Optional[Any]:
    try:
        p = Path(path)
        logger.info("Loading JSON file: %s", p)
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("JSON file not found: %s", path)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in %s: %s", path, e)
    except Exception as e:
        logger.exception("An error occurred while reading JSON %s: %s", path, e)
    return None


def require_json_file(path: str | Path) -> Any:
    data = read_json_file(path)
    if data is None:
        raise FileNotFoundError(f"Failed to load JSON file: {path}")
    return data


def list_files(path: str | Path) -> list[Path]:
    p = Path(path)
    if not p.exists() or not p.is_dir():
        return []
    return sorted(x for x in p.iterdir() if x.is_file())


def find_files(path: str | Path, pattern: str) -> list[Path]:
    p = Path(path)
    if not p.exists() or not p.is_dir():
        return []
    return sorted(p.glob(pattern))


# ---------- Grouped text ingest ----------

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


def load_file(path: str) -> Optional[list[list[str]]]:
    content = read_text_file(path)
    if content is None:
        return None
    return prepare_lines(content.splitlines())


def flatten_groups(groups: list[list[str]]) -> list[str]:
    out: list[str] = []
    for g in groups:
        out.extend(g)
    return out


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
        logger.info("Loaded %d excluded propertie(s) from %s", len(excluded), path)
    except FileNotFoundError:
        logger.error("Exclusion file not found: %s", path)
    except Exception as e:
        logger.exception("Failed to read exclusion file %s: %s", path, e)
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

    logger.info("Excluded %d attribute(s) by name", removed_count)
    return filtered


# ---------- Generic parsing helpers ----------

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