# scrutiny-viz/scrutinize.py
from __future__ import annotations

import argparse
from typing import Optional

from mapper.cli import add_mapper_args, run_from_namespace as run_mapper_from_namespace
from verification.cli import add_verify_args, run_from_namespace as run_verify_from_namespace
from report.cli import add_report_args, run_from_namespace as run_report_from_namespace


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Single entry point for scrutiny-viz workflows."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    map_parser = sub.add_parser("map", help="Run CSV -> JSON mapping")
    add_mapper_args(map_parser)

    verify_parser = sub.add_parser("verify", help="Run JSON verification")
    add_verify_args(verify_parser)

    report_parser = sub.add_parser("report", help="Render HTML report from verification JSON")
    add_report_args(report_parser)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "map":
        return int(run_mapper_from_namespace(args))

    if args.command == "verify":
        return int(run_verify_from_namespace(args))

    if args.command == "report":
        return int(run_report_from_namespace(args))

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())