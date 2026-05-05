# scrutiny-viz/mapper/service.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Set

from scrutiny import logging as slog
from scrutiny.errors import MapperError, ScrutinyError, UserInputError
from scrutiny.validation import ensure_output_parent, require_dir, require_path_exists

from . import mapper_utils, registry
from .mappers.contracts import build_context

log = slog.get_logger("MAPPER")


def _get_mapper_plugin(mapper_type: str):
    try:
        return registry.get_plugin(mapper_type)
    except KeyError as exc:
        raise UserInputError(
            f"Unknown mapper type '{mapper_type}'. "
            "Use 'python scrutinize.py map --list-mappers' to inspect available plugins.",
            component="MAPPER",
        ) from exc


def _default_output_path(src_path: Path) -> Path:
    if src_path.is_file():
        return src_path.with_suffix(".json")
    return src_path.parent / f"{src_path.name}.json"


def _directory_mode_output_path(source_path: Path, output_hint: Optional[str]) -> Path:
    if not output_hint:
        return _default_output_path(source_path)

    output_path = Path(output_hint).resolve()
    if output_path.exists() and output_path.is_dir():
        return output_path / f"{source_path.name}.json"

    if not output_path.suffix:
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path / f"{source_path.name}.json"

    return output_path


def _write_json_output(out_path: Path, result: dict) -> Optional[Path]:
    try:
        out_path = ensure_output_parent(out_path, label="Mapper output file", component="MAPPER")
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=4, ensure_ascii=False)
        log.info(f"Result saved to {out_path}")
        return out_path
    except ScrutinyError:
        raise
    except Exception as exc:
        raise MapperError(f"Failed to write output to {out_path}: {exc}") from exc


def process_source(
    source_path: str | Path,
    mapper_type: str,
    delimiter: str = ";",
    excluded_properties: Optional[Set[str]] = None,
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    plugin = _get_mapper_plugin(mapper_type)
    canonical_type = registry.normalize_type(mapper_type)

    src_path = require_path_exists(source_path, label="Mapper source path", component="MAPPER")
    log.info(f"Processing source: {src_path} (type={canonical_type})")

    context = build_context(delimiter=delimiter, excluded_properties=excluded_properties)

    try:
        final_result = plugin.map_path(src_path, context)
    except ScrutinyError:
        raise
    except Exception as exc:
        raise MapperError(f"Failed to map source {src_path}: {exc}") from exc

    if excluded_properties:
        final_result = mapper_utils.apply_exclusions(final_result, excluded_properties)

    final_output_path = output_path.resolve() if output_path else _default_output_path(src_path)
    return _write_json_output(final_output_path, final_result)


def process_files(
    file_paths: list[str],
    mapper_type: str,
    delimiter: str = ";",
    excluded_properties: Optional[Set[str]] = None,
    output_dir: Optional[Path] = None,
    source_base: Optional[Path] = None,
) -> list[Path]:
    outputs: list[Path] = []

    resolved_source_base = source_base.resolve() if source_base else None

    for file_path in file_paths:
        src_path = Path(file_path).resolve()

        out_path: Optional[Path] = None
        if output_dir:
            if resolved_source_base:
                try:
                    rel_path = src_path.relative_to(resolved_source_base)
                except ValueError:
                    rel_path = Path(src_path.name)
            else:
                rel_path = Path(src_path.name)

            out_path = (output_dir.resolve() / rel_path).with_suffix(".json")

        written = process_source(
            source_path=src_path,
            mapper_type=mapper_type,
            delimiter=delimiter,
            excluded_properties=excluded_properties,
            output_path=out_path,
        )
        if written is not None:
            outputs.append(written)

    return outputs


def process_folder(
    folder_path: str,
    mapper_type: str,
    output_folder: Optional[str] = None,
    delimiter: str = ";",
    excluded_properties: Optional[Set[str]] = None,
) -> list[Path]:
    source_path = require_dir(folder_path, label="Source folder", component="MAPPER")
    plugin = _get_mapper_plugin(mapper_type)

    if plugin.accepts_directories:
        out_path = _directory_mode_output_path(source_path, output_folder)
        written = process_source(
            source_path=source_path,
            mapper_type=mapper_type,
            delimiter=delimiter,
            excluded_properties=excluded_properties,
            output_path=out_path,
        )
        return [written] if written is not None else []

    output_path = Path(output_folder).resolve() if output_folder else (Path.cwd() / f"{source_path.name}_parsed")

    csv_files = list(source_path.rglob("*.csv"))
    if not csv_files:
        raise UserInputError(f"No CSV files found in source folder: {source_path}", component="MAPPER")

    output_path.mkdir(parents=True, exist_ok=True)

    return process_files(
        [str(path) for path in csv_files],
        mapper_type=mapper_type,
        delimiter=delimiter,
        excluded_properties=excluded_properties,
        output_dir=output_path,
        source_base=source_path,
    )


def map_single_source(
    source_path: str | Path,
    mapper_type: str,
    delimiter: str = ";",
    exclude_file: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    excluded = mapper_utils.load_exclusions(exclude_file) if exclude_file else None
    return process_source(
        source_path=source_path,
        mapper_type=mapper_type,
        delimiter=delimiter,
        excluded_properties=excluded,
        output_path=output_path,
    )


def map_single_file(
    file_path: str | Path,
    mapper_type: str,
    delimiter: str = ";",
    exclude_file: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    return map_single_source(
        source_path=file_path,
        mapper_type=mapper_type,
        delimiter=delimiter,
        exclude_file=exclude_file,
        output_path=output_path,
    )
