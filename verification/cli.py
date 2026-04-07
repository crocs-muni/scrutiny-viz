# scrutiny-viz/verification/cli.py
from __future__ import annotations

import argparse
from typing import Optional

from scrutiny import logging as slog

from .service import run_verification


def add_verify_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-s", "--schema", required=True, help="Path to structure.yml")
    parser.add_argument("-r", "--reference", required=True, help="Path to the reference JSON file")
    parser.add_argument("-p", "--profile", required=True, help="Path to the test/profile JSON file")
    parser.add_argument("-o", "--output-file", default="verification.json", help="Output JSON path")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity (-v, -vv)")
    parser.add_argument("--emit-matches", action="store_true", help="(kept for compatibility; comparators may use it)")
    parser.add_argument("--print-diffs", type=int, default=3, metavar="N", help="Print up to N diffs per section (default: 3, 0 to disable)")
    parser.add_argument("--print-matches", type=int, default=0, metavar="N", help="Print up to N matches per section (default: 0)")
    parser.add_argument("--report", action="store_true", help="Create an HTML report after verification")

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="YAML-driven verification (modular comparators + reporting)."
    )
    add_verify_args(parser)
    return parser


def run_from_namespace(args: argparse.Namespace) -> int:
    slog.setup_logging(args.verbose)
    result = run_verification(
        schema_path=args.schema,
        reference_path=args.reference,
        profile_path=args.profile,
        output_file=args.output_file,
        emit_matches=args.emit_matches,
        print_diffs=args.print_diffs,
        print_matches=args.print_matches,
        report=args.report,
    )

    if not result.get("ok", False):
        return int(result.get("exit_code", 1))

    msg = (
        f"verify completed successfully. Output written to: {result['output_json_path']}. "
        f"Overall result: {result['overall']}."
    )
    if result.get("report_html_path"):
        msg += f" Report written to: {result['report_html_path']}."
    print(msg)

    if result.get("report_zip_path"):
        print(f"Report zip written to: {result['report_zip_path']}")

    return 0


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