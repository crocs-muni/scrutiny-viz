# scrutiny-viz/mapper/service.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Set

from . import mapper_utils, registry

logger = logging.getLogger(__name__)


def process_file(
    file_path: str | Path,
    csv_type: str,
    delimiter: str = ";",
    excluded_properties: Optional[Set[str]] = None,
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    mapper = registry.get_mapper(csv_type)
    canon = registry.normalize_type(csv_type)

    src_path = Path(file_path).resolve()
    logger.info("Processing file: %s (type=%s)", src_path, canon)

    groups = mapper_utils.load_file(str(src_path))
    if groups is None:
        logger.warning("Skipping %s due to read error.", src_path)
        return None

    final_result = mapper(groups, delimiter)

    if excluded_properties:
        final_result = mapper_utils.apply_exclusions(final_result, excluded_properties)

    out_path = output_path.resolve() if output_path else src_path.with_suffix(".json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        logger.warning("Overwriting existing output file: %s", out_path)

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(final_result, f, indent=4, ensure_ascii=False)
        logger.info("Result saved to %s", out_path)
        return out_path
    except Exception as e:
        logger.exception("Failed to write output for %s: %s", src_path, e)
        return None


def process_files(
    file_paths: list[str],
    csv_type: str,
    delimiter: str = ";",
    excluded_properties: Optional[Set[str]] = None,
    output_dir: Optional[Path] = None,
    source_base: Optional[Path] = None,
) -> list[Path]:
    outputs: list[Path] = []

    for file_path in file_paths:
        src_path = Path(file_path).resolve()

        out_path: Optional[Path] = None
        if output_dir:
            if source_base:
                try:
                    rel_path = src_path.relative_to(source_base.resolve())
                except ValueError:
                    rel_path = Path(src_path.name)
            else:
                rel_path = Path(src_path.name)
            out_path = (output_dir.resolve() / rel_path).with_suffix(".json")

        written = process_file(
            file_path=src_path,
            csv_type=csv_type,
            delimiter=delimiter,
            excluded_properties=excluded_properties,
            output_path=out_path,
        )
        if written is not None:
            outputs.append(written)

    return outputs


def process_folder(
    folder_path: str,
    csv_type: str,
    output_folder: Optional[str] = None,
    delimiter: str = ";",
    excluded_properties: Optional[Set[str]] = None,
) -> list[Path]:
    source_path = Path(folder_path).resolve()

    if not source_path.exists():
        logger.error("Source folder does not exist: %s", source_path)
        return []
    if not source_path.is_dir():
        logger.error("Path is not a directory: %s", source_path)
        return []

    output_path = (
        Path(output_folder).resolve()
        if output_folder
        else (Path.cwd() / f"{source_path.name}_parsed")
    )

    csv_files = list(source_path.rglob("*.csv"))
    if not csv_files:
        logger.warning("No CSV files found in %s", source_path)
        return []

    output_path.mkdir(parents=True, exist_ok=True)

    return process_files(
        [str(p) for p in csv_files],
        csv_type=csv_type,
        delimiter=delimiter,
        excluded_properties=excluded_properties,
        output_dir=output_path,
        source_base=source_path,
    )


def map_single_file(
    file_path: str | Path,
    csv_type: str,
    delimiter: str = ";",
    exclude_file: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    excluded = mapper_utils.load_exclusions(exclude_file) if exclude_file else None
    return process_file(
        file_path=file_path,
        csv_type=csv_type,
        delimiter=delimiter,
        excluded_properties=excluded,
        output_path=output_path,
    )