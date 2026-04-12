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
        file_path = Path(path)
        logger.info("Loading text file: %s", file_path)
        return file_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        logger.error("File not found: %s", path)
    except Exception as exc:
        logger.exception("An error occurred while reading %s: %s", path, exc)
    return None


def require_existing_file(path: str | Path, *, kind: str = "file") -> Path:
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"{kind.capitalize()} does not exist: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Expected a file for {kind}, got: {file_path}")
    return file_path


def read_json_file(path: str | Path) -> Optional[Any]:
    try:
        file_path = Path(path)
        logger.info("Loading JSON file: %s", file_path)
        with file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        logger.error("JSON file not found: %s", path)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in %s: %s", path, exc)
    except Exception as exc:
        logger.exception("An error occurred while reading JSON %s: %s", path, exc)
    return None


def read_json_object(path: str | Path, *, label: str = "JSON input") -> dict[str, Any]:
    file_path = require_existing_file(path, kind=label)
    doc = read_json_file(file_path)
    if doc is None:
        raise ValueError(f"Failed to parse JSON from: {file_path}")
    if not isinstance(doc, dict):
        raise ValueError(f"{label.capitalize()} must be a JSON object: {file_path}")
    return doc


def list_files(path: str | Path) -> list[Path]:
    folder_path = Path(path)
    if not folder_path.exists() or not folder_path.is_dir():
        return []
    return sorted(entry for entry in folder_path.iterdir() if entry.is_file())


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def resolve_asset_path(source_dir: Path, raw_path: str) -> str:
    if not raw_path:
        return ""

    asset_path = Path(raw_path)
    if asset_path.is_absolute() and asset_path.exists():
        try:
            return asset_path.resolve().as_uri()
        except Exception:
            return str(asset_path.resolve())

    candidate = (source_dir / raw_path).resolve()
    if candidate.exists():
        try:
            return candidate.as_uri()
        except Exception:
            return str(candidate)

    return raw_path


# ---------- Grouped text ingest ----------

def prepare_lines(lines: list[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    current_group: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == "":
            if current_group:
                groups.append(current_group)
                current_group = []
            continue
        current_group.append(stripped)

    if current_group:
        groups.append(current_group)

    return groups


def load_file(path: str) -> Optional[list[list[str]]]:
    content = read_text_file(path)
    if content is None:
        return None
    return prepare_lines(content.splitlines())


def flatten_groups(groups: list[list[str]]) -> list[str]:
    flattened: list[str] = []
    for group in groups:
        flattened.extend(group)
    return flattened


# ---------- Exclusions ----------

def load_exclusions(path: str) -> set[str]:
    excluded: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                trimmed = line.strip()
                if not trimmed or trimmed.startswith("#"):
                    continue
                excluded.add(trimmed)
        logger.info("Loaded %d excluded propertie(s) from %s", len(excluded), path)
    except FileNotFoundError:
        logger.error("Exclusion file not found: %s", path)
    except Exception as exc:
        logger.exception("Failed to read exclusion file %s: %s", path, exc)
    return excluded


def apply_exclusions(result: dict[str, Any], excluded: set[str]) -> dict[str, Any]:
    if not excluded:
        return result

    filtered: dict[str, Any] = {}
    removed_count = 0

    for section, value in result.items():
        if isinstance(section, str) and section.startswith("_"):
            filtered[section] = value
            continue

        if not isinstance(value, list):
            filtered[section] = value
            continue

        if not value or not all(isinstance(item, dict) and "name" in item for item in value):
            filtered[section] = value
            continue

        kept: list[dict[str, Any]] = []
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
        stripped = (line or "").strip()
        if not stripped:
            continue

        parts = stripped.split(delimiter)
        if len(parts) >= 2:
            name = parts[0].strip()
            value = parts[1].strip()
            if name:
                attrs.append(create_attribute(name, value))
            continue

        if allow_single_value:
            attrs.append(create_attribute(stripped, ""))

    return attrs


def parse_name_value_attributes_filtered(
    lines: list[str],
    delimiter: str,
    *,
    allow_single_value: bool = False,
    skip_prefixes: tuple[str, ...] = (),
    stop_prefixes: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    attrs: list[dict[str, str]] = []

    for line in lines:
        stripped = (line or "").strip()
        if not stripped:
            continue

        if stop_prefixes and stripped.startswith(stop_prefixes):
            break
        if skip_prefixes and stripped.startswith(skip_prefixes):
            continue

        parts = stripped.split(delimiter)
        if len(parts) >= 2:
            name = parts[0].strip()
            value = parts[1].strip()
            if name:
                attrs.append(create_attribute(name, value))
        elif allow_single_value and parts[0].strip():
            attrs.append(create_attribute(parts[0].strip(), ""))

    return attrs


def to_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None

    stripped = str(value).strip()
    if not stripped:
        return None

    try:
        return int(stripped)
    except ValueError:
        try:
            return int(float(stripped.replace(",", ".")))
        except ValueError:
            return None


def to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None

    stripped = str(value).strip()
    if not stripped:
        return None

    try:
        return float(stripped.replace(",", "."))
    except ValueError:
        return None


def to_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None

    stripped = str(value).strip().lower()
    if stripped in {"true", "yes", "y", "1"}:
        return True
    if stripped in {"false", "no", "n", "0"}:
        return False
    return None


def parse_kv_pairs(parts: list[str], start: int = 1) -> dict[str, str]:
    out: dict[str, str] = {}
    index = start

    while index < len(parts) - 1:
        key = (parts[index] or "").strip()
        value = (parts[index + 1] or "").strip()
        if key.endswith(":"):
            key = key[:-1].strip()
        if key:
            out[key] = value
        index += 2

    return out


def parse_colon_pairs_line(line: str, delimiter: str) -> dict[str, str]:
    parts = [part.strip() for part in (line or "").split(delimiter)]
    cfg: dict[str, str] = {}
    index = 0

    while index < len(parts) - 1:
        key = parts[index]
        if key.endswith(":"):
            normalized_key = key[:-1].strip()
            value = parts[index + 1].strip()
            if normalized_key:
                cfg[normalized_key] = value
            index += 2
        else:
            index += 1

    return cfg


def compact_config(cfg: dict[str, str], keys: list[str]) -> str:
    chunks: list[str] = []
    for key in keys:
        value = (cfg.get(key) or "").strip()
        if value:
            chunks.append(f"{key}={value}")
    return ";".join(chunks)


def build_perf_record(
    *,
    op_name: str,
    algorithm: Optional[str] = None,
    measurement_config: Optional[str] = None,
    data_length: Optional[int] = None,
    avg_ms: Optional[float] = None,
    min_ms: Optional[float] = None,
    max_ms: Optional[float] = None,
    total_iterations: Optional[int] = None,
    total_invocations: Optional[int] = None,
    error: Optional[str] = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "algorithm": algorithm or op_name,
        "op_name": op_name,
    }

    if measurement_config:
        record["measurement_config"] = measurement_config
    if data_length is not None:
        record["data_length"] = data_length
    if avg_ms is not None:
        record["avg_ms"] = avg_ms
    if min_ms is not None:
        record["min_ms"] = min_ms
    if max_ms is not None:
        record["max_ms"] = max_ms
    if total_iterations is not None:
        record["total_iterations"] = total_iterations
    if total_invocations is not None:
        record["total_invocations"] = total_invocations
    if error:
        record["error"] = error

    return record


def flush_block(
    result: dict[str, Any],
    section: Optional[str],
    lines: list[str],
    parse_fn: Callable[..., Optional[dict[str, Any]]],
    *parse_args: Any,
) -> list[str]:
    if section and lines:
        rec = parse_fn(lines, *parse_args)
        if rec:
            result.setdefault(section, []).append(rec)
    return []
