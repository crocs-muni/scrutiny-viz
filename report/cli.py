# scrutiny-viz/report/cli.py
from __future__ import annotations

import argparse
from typing import Optional

from scrutiny import logging as slog
from .service import run_report_html


def add_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-p", "--verification-profile",
        help="Input verification JSON produced by verify.py",
        action="store", metavar="file", required=True
    )
    parser.add_argument(
        "-o", "--output-file",
        help="Name of output HTML",
        action="store", metavar="outfile",
        required=False, default="comparison.html"
    )
    parser.add_argument(
        "-e", "--exclude-style-and-scripts",
        help="Inline CSS/JS instead of linking to /data/",
        action="store_true"
    )
    parser.add_argument(
        "-nz", "--no-zip",
        help="Disables creation of a zip",
        action="store_true"
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0,
        help="Increase log verbosity (-v, -vv)"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render an HTML report from verification JSON."
    )
    add_report_args(parser)
    return parser


def run_from_namespace(args: argparse.Namespace) -> int:
    slog.setup_logging(args.verbose)
    return run_report_html(
        verification_profile=args.verification_profile,
        output_file=args.output_file,
        exclude_style_and_scripts=args.exclude_style_and_scripts,
        no_zip=args.no_zip,
    )


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run_from_namespace(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        from scrutiny import logging as slog
        slog.log_err(f"Error: {e}")
        raise SystemExit(1)