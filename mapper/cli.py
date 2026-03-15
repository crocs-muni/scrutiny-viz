# scrutiny-viz/mapper/cli.py
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from scrutiny import logging as slog

from . import mapper_utils, registry
from .service import map_single_file, process_files, process_folder


def add_mapper_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("file_paths", nargs="*", default=[], help="Path(s) to CSV file(s)")
    parser.add_argument("-f", "--folder", dest="folder_path", help="Folder containing CSV files (recursive)")
    parser.add_argument("-t", "--type", dest="csv_type", required=True, help="CSV type / mapper to use")
    parser.add_argument("-o", "--output", dest="output_path", help="Output path for single-file mode, or output folder for folder/multi-file mode")
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
  python scrutinize.py map -t jcalg file.csv -o out.json
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
        outputs = process_folder(
            args.folder_path,
            csv_type=args.csv_type,
            output_folder=args.output_path,
            delimiter=args.delimiter,
            excluded_properties=excluded,
        )
        for p in outputs:
            print(p)
        return 0 if outputs else 1

    if args.file_paths:
        # single file: allow exact output file path
        if len(args.file_paths) == 1:
            written = map_single_file(
                file_path=args.file_paths[0],
                csv_type=args.csv_type,
                delimiter=args.delimiter,
                exclude_file=args.exclude_file,
                output_path=Path(args.output_path).resolve() if args.output_path else None,
            )
            if written is not None:
                print(written)
                return 0
            return 1

        # multiple explicit files: treat -o as output directory
        outputs = process_files(
            args.file_paths,
            csv_type=args.csv_type,
            delimiter=args.delimiter,
            excluded_properties=excluded,
            output_dir=Path(args.output_path).resolve() if args.output_path else None,
            source_base=Path.cwd() if args.output_path else None,
        )
        for p in outputs:
            print(p)
        return 0 if outputs else 1

    raise SystemExit("Please provide either file paths or use --folder option.")


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run_from_namespace(args)


if __name__ == "__main__":
    raise SystemExit(main())