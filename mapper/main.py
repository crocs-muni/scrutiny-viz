# scrutiny-viz/mapper/main.py
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional, Set

import registry
import mapper_utils

logger = logging.getLogger(__name__)

def process_files(
    file_paths: list[str],
    csv_type: str,
    delimiter: str = ";",
    excluded_properties: Optional[Set[str]] = None,
    output_dir: Optional[Path] = None,
    source_base: Optional[Path] = None,
) -> list[Path]:
    mapper = registry.get_mapper(csv_type)
    canon = registry.normalize_type(csv_type)

    outputs: list[Path] = []
    for file_path in file_paths:
        logger.info(f"Processing file: {file_path} (type={canon})")

        groups = mapper_utils.load_file(file_path)
        if groups is None:
            logger.warning(f"Skipping {file_path} due to read error.")
            continue

        final_result = mapper(groups, delimiter)

        if excluded_properties:
            final_result = mapper_utils.apply_exclusions(final_result, excluded_properties)

        if output_dir and source_base:
            rel_path = Path(file_path).resolve().relative_to(source_base)
            out_path = (output_dir / rel_path).with_suffix(".json")
            out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            out_path = Path(file_path).with_suffix(".json")

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(final_result, f, indent=4, ensure_ascii=False)
            logger.info(f"Result saved to {out_path}")
            outputs.append(out_path)
        except Exception as e:
            logger.exception(f"Failed to write output for {file_path}: {e}")

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
        logger.error(f"Source folder does not exist: {source_path}")
        return []
    if not source_path.is_dir():
        logger.error(f"Path is not a directory: {source_path}")
        return []

    output_path = Path(output_folder).resolve() if output_folder else (Path.cwd() / f"{source_path.name}_parsed")

    csv_files = list(source_path.rglob("*.csv"))
    if not csv_files:
        logger.warning(f"No CSV files found in {source_path}")
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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse CSV files and convert to scrutiny-viz JSON format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python main.py --type jcperf file.csv
  python main.py --type tpm --folder ./csvs --output ./out
Known types: {", ".join(registry.list_types())}
""",
    )

    parser.add_argument("file_paths", nargs="*", default=[], help="Path(s) to CSV file(s)")
    parser.add_argument("-f", "--folder", dest="folder_path", help="Folder containing CSV files (recursive)")
    parser.add_argument("-t", "--type", dest="csv_type", required=True, help="CSV type / mapper to use")
    parser.add_argument("-o", "--output", dest="output_path", help="Output folder path (folder mode)")
    parser.add_argument("-d", "--delimiter", default=";", help="Delimiter to use (default: ;)")
    parser.add_argument("-x", "--exclude-file", default=None, help="File with attribute names to exclude")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    excluded = mapper_utils.load_exclusions(args.exclude_file) if args.exclude_file else None

    if args.folder_path:
        process_folder(
            args.folder_path,
            csv_type=args.csv_type,
            output_folder=args.output_path,
            delimiter=args.delimiter,
            excluded_properties=excluded,
        )
        return 0

    if args.file_paths:
        process_files(
            args.file_paths,
            csv_type=args.csv_type,
            delimiter=args.delimiter,
            excluded_properties=excluded,
        )
        return 0

    raise SystemExit("Please provide either file paths or use --folder option.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
    raise SystemExit(main())