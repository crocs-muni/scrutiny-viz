# scrutiny-viz/report/cli.py
from __future__ import annotations

import argparse
from typing import Optional

from scrutiny import logging as slog
from report.viz import registry as viz_registry
from .service import run_report_html


def _format_aliases(aliases: tuple[str, ...]) -> str:
    return ", ".join(aliases) if aliases else "-"


def _print_viz_catalog() -> None:
    specs = viz_registry.list_specs()
    print("Available viz plugins:")
    for spec in specs:
        print(f"- {spec.name}")
        print(f"  slot: {spec.slot}")
        print(f"  aliases: {_format_aliases(spec.aliases)}")
        print(f"  description: {spec.description or '-'}")


def add_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-p", "--verification-profile", metavar="file", help="Input verification JSON produced by verify.py")
    parser.add_argument("--list-viz", action="store_true", help="List discovered viz plugins and exit")
    parser.add_argument("-o", "--output-file", metavar="outfile", default="comparison.html", help="Name of output HTML")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity (-v, -vv)")
    parser.add_argument("--exclude-style-and-scripts", action="store_true", help="Inline CSS/JS instead of linking to /data/")
    parser.add_argument("--no-zip", action="store_true", help="Disables creation of a zip")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render an HTML report from verification JSON.")
    add_report_args(parser)
    return parser


def run_from_namespace(args: argparse.Namespace) -> int:
    slog.setup_logging(args.verbose)
    log = slog.get_logger("REPORT")

    if args.list_viz:
        _print_viz_catalog()
        return 0

    if not args.verification_profile:
        raise SystemExit(
            "Missing required argument: --verification-profile. "
            "Provide it to render a report, or use --list-viz to inspect available plugins."
        )

    result = run_report_html(
        verification_profile=args.verification_profile,
        output_file=args.output_file,
        exclude_style_and_scripts=args.exclude_style_and_scripts,
        no_zip=args.no_zip,
    )

    if not result.get("ok", False):
        return int(result.get("exit_code", 1))

    message = f"report completed successfully. HTML written to: {result['html_path']}"
    if result.get("zip_path"):
        message += f". Zip written to: {result['zip_path']}"
    log.info(message)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run_from_namespace(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        slog.get_logger("REPORT").err(f"Error: {exc}")
        raise SystemExit(1)
