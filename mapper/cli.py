# scrutiny-viz/mapper/cli.py
from __future__ import annotations

import argparse
from typing import Optional

from scrutiny import logging as slog

from . import mapper_utils, registry
from .service import process_files, process_folder


def add_mapper_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("file_paths", nargs="*", default=[], help="Path(s) to CSV file(s)")
    parser.add_argument("-f", "--folder", dest="folder_path", help="Folder containing CSV files (recursive)")
    parser.add_argument("-t", "--type", dest="csv_type", required=True, help="CSV type / mapper to use")
    parser.add_argument("-o", "--output", dest="output_path", help="Output folder path (folder mode)")
    parser.add_argument("-d", "--delimiter", default=";", help="Delimiter to use (default: ;)")
    parser.add_argument("-x", "--exclude-file", default=None, help="File with attribute names to exclude")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity (-v, -vv)")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse CSV files and convert to scrutiny-viz JSON format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python scrutinize.py map -t jcperf file.csv
  python scrutinize.py map -t tpm -f ./csvs -o ./out
Known types: {", ".join(registry.list_types())}
""",
    )
    add_mapper_args(parser)
    return parser


def run_from_namespace(args: argparse.Namespace) -> int:
    slog.setup_logging(getattr(args, "verbose", 0))

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


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run_from_namespace(args)


if __name__ == "__main__":
    raise SystemExit(main())