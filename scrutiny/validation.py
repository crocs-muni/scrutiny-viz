# scrutiny-viz/scrutiny/validation.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scrutiny.errors import UserInputError


def _label(label: str | None) -> str:
    return str(label or "Path")


def as_resolved_path(path: str | Path, *, label: str | None = None, component: str = "APP") -> Path:
    if path is None or str(path).strip() == "":
        raise UserInputError(f"{_label(label)} was not provided.", component=component)
    return Path(path).expanduser().resolve()


def require_path_exists(path: str | Path, *, label: str = "Path", component: str = "APP") -> Path:
    p = as_resolved_path(path, label=label, component=component)
    if not p.exists():
        raise UserInputError(f"{label} does not exist: {p}", component=component)
    return p


def require_file(path: str | Path, *, label: str = "File", component: str = "APP") -> Path:
    p = require_path_exists(path, label=label, component=component)
    if not p.is_file():
        raise UserInputError(f"{label} must be a file, got: {p}", component=component)
    return p


def require_dir(path: str | Path, *, label: str = "Directory", component: str = "APP") -> Path:
    p = require_path_exists(path, label=label, component=component)
    if not p.is_dir():
        raise UserInputError(f"{label} must be a directory, got: {p}", component=component)
    return p


def ensure_output_parent(path: str | Path, *, label: str = "Output file", component: str = "APP") -> Path:
    p = as_resolved_path(path, label=label, component=component)
    parent = p.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise UserInputError(f"Cannot create parent directory for {label}: {parent} ({exc})", component=component) from exc
    if not parent.exists() or not parent.is_dir():
        raise UserInputError(f"Parent path for {label} is not a directory: {parent}", component=component)
    return p


def read_json_file(path: str | Path, *, label: str = "JSON file", component: str = "APP") -> Any:
    p = require_file(path, label=label, component=component)
    try:
        with p.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise UserInputError(f"{label} is not valid JSON: {p} ({exc})", component=component) from exc
    except OSError as exc:
        raise UserInputError(f"Failed to read {label}: {p} ({exc})", component=component) from exc
