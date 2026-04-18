# scrutiny-viz/scrutiny/batch/cli.py
from __future__ import annotations

import argparse
from typing import Optional

from scrutiny import logging as slog

from .service import run_batch_verification


def add_batch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-s", "--schema", required=True, help="Path to schema YAML")
    parser.add_argument("-r", "--reference", required=True, help="Reference input (JSON, raw file, or mapper-supported directory)")
    parser.add_argument("-t", "--type", dest="shared_type", help="Shared mapper type for both reference and profiles when raw inputs need mapping")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity (-v, -vv)")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--profiles-dir", help="Directory containing profile inputs")
    group.add_argument("--profiles", nargs="+", help="Explicit list of profile inputs")

    parser.add_argument("--reference-type", help="Mapper type for the reference input when raw mapping is needed")
    parser.add_argument("--profile-type", help="Mapper type for profile inputs when raw mapping is needed")
    parser.add_argument("--batch-id", help="Optional batch identifier; default is timestamp-based")
    parser.add_argument("--delimiter", default=";", help="Delimiter for CSV-like file mappers (default: ';')")
    parser.add_argument(
        "--report-mode",
        choices=("nonmatch", "all", "none"),
        default="nonmatch",
        help="Which profiles should get HTML reports: nonmatch (default = any non-MATCH), all, or none",
    )
    parser.add_argument("--keep-mapped", action="store_true", help="Keep mapped intermediate JSON files under results/<batch_id>/mapped")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch verification: compare one reference against many profiles.")
    add_batch_args(parser)
    return parser


def run_from_namespace(args: argparse.Namespace) -> int:
    slog.setup_logging(args.verbose)
    log = slog.get_logger("BATCH")

    result = run_batch_verification(
        schema_path=args.schema,
        reference_input=args.reference,
        profiles=args.profiles or [],
        profiles_dir=args.profiles_dir,
        shared_type=args.shared_type,
        reference_type=args.reference_type,
        profile_type=args.profile_type,
        batch_id=args.batch_id,
        delimiter=args.delimiter,
        report_mode=args.report_mode,
        keep_mapped=args.keep_mapped,
    )

    exit_code = int(result.get("exit_code", 0 if result.get("ok", False) else 1))

    if result.get("summary_json_path"):
        status = "batch-verify completed with errors." if result.get("profile_errors", 0) else "batch-verify completed."
        log.info(
            f"{status} "
            f"Summary written to: {result['summary_json_path']}. "
            f"Profiles processed: {result['profiles_processed']}. "
            f"Non-MATCH profiles: {result.get('nonmatch_profiles', 0)}. "
            f"Reports generated: {result['reports_generated']}."
        )
        log.info(f"Verification outputs: {result['verify_dir']}")
        log.info(f"Report outputs: {result['report_dir']}")

    return exit_code


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run_from_namespace(args)


if __name__ == "__main__":
    raise SystemExit(main())
