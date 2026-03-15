# scrutiny-viz/scrutinize.py
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from scrutiny import logging as slog

from mapper.cli import add_mapper_args, run_from_namespace as run_mapper_from_namespace
from mapper.service import map_single_file

from verification.cli import add_verify_args, run_from_namespace as run_verify_from_namespace
from verification.service import run_verification

from report.cli import add_report_args, run_from_namespace as run_report_from_namespace
from report.service import run_report_html


def add_full_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-s", "--schema", required=True, help="Path to structure.yml")
    parser.add_argument("-r", "--reference", required=True, help="Reference input (.json or .csv)")
    parser.add_argument("-p", "--profile", required=True, help="Profile/test input (.json or .csv)")
    parser.add_argument("-t", "--type", dest="shared_type", default=None, help="Shared mapper type for CSV inputs (used for both reference and profile unless overridden)")
    parser.add_argument("--reference-type", dest="reference_type", default=None, help="Mapper type for reference CSV input")
    parser.add_argument("--profile-type", dest="profile_type", default=None, help="Mapper type for profile CSV input")
    parser.add_argument("-m", "--mapped-dir", dest="mapped_dir", default=None, help="Directory for mapped intermediate JSON files")
    parser.add_argument("-d", "--delimiter", default=";", help="Delimiter to use for CSV mapping (default: ;)")
    parser.add_argument("-x", "--exclude-file", default=None, help="File with attribute names to exclude during mapping")
    parser.add_argument("-vo", "--verify-output", dest="verify_output", default="verification.json", help="Output JSON path for verification result")
    parser.add_argument("--emit-matches", action="store_true", help="Pass through to verification")
    parser.add_argument("--print-diffs", type=int, default=3, metavar="N", help="Print up to N diffs per section (default: 3, 0 to disable)")
    parser.add_argument("--print-matches", type=int, default=0, metavar="N", help="Print up to N matches per section (default: 0)")
    parser.add_argument("-ro", "--report-output", dest="report_output", default="comparison.html", help="Output HTML filename/path for final report")
    parser.add_argument("-e", "--exclude-style-and-scripts", action="store_true", help="Link CSS/JS instead of inlining them into the HTML")
    parser.add_argument("-nz", "--no-zip", action="store_true", help="Disable zip creation for the report output")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity (-v, -vv)")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Single entry point for scrutiny-viz workflows.")
    sub = parser.add_subparsers(dest="command", required=True)

    map_parser = sub.add_parser("map", help="Run CSV -> JSON mapping")
    add_mapper_args(map_parser)

    verify_parser = sub.add_parser("verify", help="Run JSON verification")
    add_verify_args(verify_parser)

    report_parser = sub.add_parser("report", help="Render HTML report from verification JSON")
    add_report_args(report_parser)

    full_parser = sub.add_parser("full", help="Map CSV inputs if needed, run verification, then render HTML report")
    add_full_args(full_parser)

    return parser


def _resolve_mapper_type(*, explicit_type: Optional[str], shared_type: Optional[str], path: Path, role: str) -> Optional[str]:
    if explicit_type:
        return explicit_type
    if shared_type:
        return shared_type
    if path.suffix.lower() == ".csv":
        raise SystemExit(f"{role} input '{path}' is CSV, so a mapper type is required. Use --{role}-type or --type.")
    return None


def _mapped_output_path(*, input_path: Path, mapped_dir: Optional[str], role: str) -> Optional[Path]:
    if not mapped_dir:
        return None
    out_dir = Path(mapped_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{input_path.stem}_{role}.json"


def _ensure_json_input(*, input_path: str, role: str, mapper_type: Optional[str], mapped_dir: Optional[str], delimiter: str, exclude_file: Optional[str]) -> Path:
    src = Path(input_path).resolve()
    suffix = src.suffix.lower()

    if suffix == ".json":
        return src

    if suffix != ".csv":
        raise SystemExit(f"{role} input must be .json or .csv, got '{src.suffix}' for '{src}'.")

    if not mapper_type:
        raise SystemExit(f"{role} input '{src}' is CSV but no mapper type was provided. Use --{role}-type or --type.")

    out_path = _mapped_output_path(input_path=src, mapped_dir=mapped_dir, role=role)

    slog.log_step(f"Mapping {role} CSV", str(src))
    written = map_single_file(file_path=src, csv_type=mapper_type, delimiter=delimiter, exclude_file=exclude_file, output_path=out_path)
    if written is None:
        raise SystemExit(f"Failed to map {role} CSV: {src}")

    slog.log_ok(f"{role.capitalize()} mapped to {written}")
    return Path(written).resolve()


def run_full_from_namespace(args: argparse.Namespace) -> int:
    slog.setup_logging(getattr(args, "verbose", 0))

    ref_input = Path(args.reference).resolve()
    prof_input = Path(args.profile).resolve()

    ref_type = _resolve_mapper_type(explicit_type=args.reference_type, shared_type=args.shared_type, path=ref_input, role="reference")
    prof_type = _resolve_mapper_type(explicit_type=args.profile_type, shared_type=args.shared_type, path=prof_input, role="profile")

    reference_json = _ensure_json_input(input_path=str(ref_input), role="reference", mapper_type=ref_type, mapped_dir=args.mapped_dir, delimiter=args.delimiter, exclude_file=args.exclude_file)
    profile_json = _ensure_json_input(input_path=str(prof_input), role="profile", mapper_type=prof_type, mapped_dir=args.mapped_dir, delimiter=args.delimiter, exclude_file=args.exclude_file)

    slog.log_step("Running verification", args.schema)
    rc = run_verification(schema_path=args.schema, reference_path=str(reference_json), profile_path=str(profile_json), output_file=args.verify_output, emit_matches=args.emit_matches, print_diffs=args.print_diffs, print_matches=args.print_matches, report=False)
    if rc != 0:
        return int(rc)

    verification_json = Path(args.verify_output).resolve()

    slog.log_step("Rendering final report", str(verification_json))
    rc = run_report_html(verification_profile=str(verification_json), output_file=args.report_output, exclude_style_and_scripts=args.exclude_style_and_scripts, no_zip=args.no_zip)
    if rc != 0:
        return int(rc)

    slog.log_ok(f"Full pipeline finished. Verification: {verification_json}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "map":
        return int(run_mapper_from_namespace(args))

    if args.command == "verify":
        return int(run_verify_from_namespace(args))

    if args.command == "report":
        return int(run_report_from_namespace(args))

    if args.command == "full":
        return int(run_full_from_namespace(args))

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
