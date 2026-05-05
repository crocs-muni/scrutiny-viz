# scrutiny-viz/mapper/cli.py
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from scrutiny import logging as slog
from scrutiny.errors import ScrutinyError, UserInputError

from . import mapper_utils, registry
from .service import process_files, process_folder, map_single_source


def _format_aliases(aliases: tuple[str, ...]) -> str:
    return ", ".join(aliases) if aliases else "-"


def _print_mapper_catalog() -> None:
    specs = registry.list_specs()
    print("Available mapper plugins:")
    for spec in specs:
        print(f"- {spec.name}")
        print(f"  aliases: {_format_aliases(spec.aliases)}")
        print(f"  description: {spec.description or '-'}")


def _get_mapper_plugin_for_cli(mapper_type: str):
    try:
        return registry.get_plugin(mapper_type)
    except KeyError as exc:
        raise UserInputError(
            f"Unknown mapper type '{mapper_type}'. "
            "Use 'python scrutinize.py map --list-mappers' to inspect available plugins.",
            component="MAPPER",
        ) from exc


def add_mapper_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-t", "--type", dest="mapper_type", help="Mapper type to use")
    parser.add_argument("-o", "--output", dest="output_path", help="Output file path for one source, or output directory for multi-file folder mode")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity (-v, -vv)")
    parser.add_argument("file_paths", nargs="*", default=[], help="Path(s) to source file(s)")
    parser.add_argument("--folder", dest="folder_path", help="Folder containing input files, or a source directory for directory-based mappers")
    parser.add_argument("--delimiter", default=";", help="Delimiter to use for grouped-text mappers (default: ;)")
    parser.add_argument("--exclude-file", default=None, help="File with attribute names to exclude")
    parser.add_argument("--list-mappers", action="store_true", help="List discovered mapper plugins and exit")


def build_arg_parser() -> argparse.ArgumentParser:
    known_types = ", ".join(registry.list_types())
    parser = argparse.ArgumentParser(
        description="Parse supported input sources and convert them to scrutiny-viz JSON format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "\n"
            "Examples:\n"
            "  python scrutinize.py map --list-mappers\n"
            "  python scrutinize.py map -t jcperf file.csv\n"
            "  python scrutinize.py map -t tpm --folder ./csvs -o ./out\n"
            "  python scrutinize.py map -t rsabias --folder ./out_eval -o ./results/rsabias_old.json\n"
            f"Known types: {known_types}\n"
        ),
    )
    add_mapper_args(parser)
    return parser


def print_mapper_success(outputs: list[Path], output_hint: str | None) -> None:
    log = slog.get_logger("MAPPER")
    if len(outputs) == 1:
        log.info(f"Mapper completed successfully. Output written to: {outputs[0]}")
        return

    if output_hint:
        base_path = Path(output_hint).resolve()
        log.info(f"Mapper completed successfully. {len(outputs)} outputs written under: {base_path}")
    else:
        log.info(f"Mapper completed successfully. {len(outputs)} outputs written.")


def run_from_namespace(args: argparse.Namespace) -> int:
    slog.setup_logging(getattr(args, "verbose", 0))
    log = slog.get_logger("MAPPER")

    if args.list_mappers:
        _print_mapper_catalog()
        return 0

    if not args.mapper_type:
        raise UserInputError(
            "Please provide --type to select a mapper, or use --list-mappers to inspect available plugins.",
            component="MAPPER",
        )

    excluded = mapper_utils.load_exclusions(args.exclude_file) if args.exclude_file else None
    plugin = _get_mapper_plugin_for_cli(args.mapper_type)

    if args.folder_path:
        outputs = process_folder(
            args.folder_path,
            mapper_type=args.mapper_type,
            output_folder=args.output_path,
            delimiter=args.delimiter,
            excluded_properties=excluded,
        )
        if not outputs:
            return 1
        print_mapper_success(outputs, args.output_path)
        return 0

    if args.file_paths:
        if len(args.file_paths) == 1:
            src = Path(args.file_paths[0]).resolve()

            if src.is_dir() and not plugin.accepts_directories:
                raise UserInputError(
                    f"Mapper '{args.mapper_type}' does not accept directory input: {src}",
                    component="MAPPER",
                )

            written = map_single_source(
                source_path=src,
                mapper_type=args.mapper_type,
                delimiter=args.delimiter,
                exclude_file=args.exclude_file,
                output_path=Path(args.output_path).resolve() if args.output_path else None,
            )
            if written:
                log.info(f"Mapper completed successfully. Output written to: {written}")
                return 0
            return 1

        outputs = process_files(
            args.file_paths,
            mapper_type=args.mapper_type,
            delimiter=args.delimiter,
            excluded_properties=excluded,
            output_dir=Path(args.output_path).resolve() if args.output_path else None,
            source_base=Path.cwd() if args.output_path else None,
        )
        if not outputs:
            return 1
        print_mapper_success(outputs, args.output_path)
        return 0

    raise UserInputError("Please provide either file paths or use --folder option.", component="MAPPER")


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run_from_namespace(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScrutinyError as exc:
        slog.get_logger(getattr(exc, "component", "MAPPER")).err(str(exc))
        raise SystemExit(int(getattr(exc, "exit_code", 1)))
