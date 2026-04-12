# scrutiny-viz/report/cli.py
from __future__ import annotations

import argparse
from typing import Optional

from scrutiny import logging as slog
from .service import run_report_html


def add_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-p", "--verification-profile", metavar="file", required=True, help="Input verification JSON produced by verify.py",)
    parser.add_argument("-o", "--output-file", metavar="outfile", default="comparison.html", help="Name of output HTML")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity (-v, -vv)")
    parser.add_argument("--exclude-style-and-scripts", action="store_true", help="Inline CSS/JS instead of linking to /data/",)
    parser.add_argument("--no-zip", action="store_true", help="Disables creation of a zip")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render an HTML report from verification JSON.")
    add_report_args(parser)
    return parser


def run_from_namespace(args: argparse.Namespace) -> int:
    slog.setup_logging(args.verbose)
    log = slog.get_logger("REPORT")
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
