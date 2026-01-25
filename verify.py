#!/usr/bin/env python3
import sys
import argparse
import json
import os
import subprocess

from scrutiny.schemaloader import SchemaLoader
from scrutiny.ingest import JsonParser
from scrutiny import logging as slog

from scrutiny.comparators.registry import get as get_comparator
import scrutiny.comparators.basic_comparator
import scrutiny.comparators.algperf_comparator
import scrutiny.comparators.cplc_comparator

from scrutiny.reporting.reporting import assemble_report


def _load_schema(path: str):
    slog.log_step("Loading schema:", path)
    loader = SchemaLoader(path)
    schema = loader.load()
    slog.log_ok(f"Schema loaded with {len(schema)} section(s).")
    return schema


def _load_json(parser: JsonParser, title: str, path: str):
    slog.log_step(f"Reading {title} JSON:", path)
    data = parser.parse(path)
    slog.log_ok(f"{title} loaded.")
    return data


def main():
    p = argparse.ArgumentParser(
        description="YAML-driven verification (modular comparators + reporting)."
    )
    p.add_argument("-s", "--schema",    required=True, help="Path to structure.yml")
    p.add_argument("-r", "--reference", required=True, help="Path to the reference JSON file")
    p.add_argument("-p", "--profile",   required=True, help="Path to the test/profile JSON file")
    p.add_argument("-o", "--output-file", default="verification.json", help="Output JSON path")

    p.add_argument("-v", "--verbose", action="count", default=0,
                   help="Increase log verbosity (-v, -vv)")
    p.add_argument("--emit-matches", action="store_true",
                   help="(kept for compatibility; comparators may use it)")
    p.add_argument("--print-diffs", type=int, default=3, metavar="N",
                   help="Print up to N diffs per section (default: 3, 0 to disable)")
    p.add_argument("--print-matches", type=int, default=0, metavar="N",
                   help="Print up to N matches per section (default: 0)")
    p.add_argument("-rep", "--report", action="store_true",
                   help="Create an HTML report (results/comparison.html) using report_html.py")

    args = p.parse_args()
    slog.setup_logging(args.verbose)

    schema = _load_schema(args.schema)
    parser = JsonParser(schema)

    data_ref = _load_json(parser, "reference", args.reference)
    data_tst = _load_json(parser, "profile", args.profile)

    all_results = {}
    section_rows = {}

    for section, cfg in schema.items():
        comp_cfg = cfg.get("component", {}) or {}
        comp_name = (comp_cfg.get("comparator") or "basic").lower()
        match_key = comp_cfg.get("match_key")
        if not match_key:
            slog.log_err(f"[{section}] missing component.match_key in schema")
            sys.exit(2)
        show_key = comp_cfg.get("show_key", match_key)

        Comparator = get_comparator(comp_name)
        if Comparator is None:
            slog.log_warn(f"[{section}] comparator '{comp_name}' not found; falling back to 'basic'")
            Comparator = get_comparator("basic")

        comparator = Comparator()
        ref_rows = data_ref.get(section, []) or []
        tst_rows = data_tst.get(section, []) or []

        section_rows[section] = {"reference": ref_rows, "tested": tst_rows}

        meta = {
            "include_matches": bool(comp_cfg.get("include_matches", False) or args.emit_matches),
            "threshold_ratio": comp_cfg.get("threshold_ratio"),
            "threshold_count": comp_cfg.get("threshold_count"),
            **(cfg.get("target") or {}),
        }

        slog.log_step("Comparing section:", f"[{section}] comparator={comp_name}")
        res = comparator.compare(
            section=section,
            key_field=match_key,
            show_field=show_key,
            metadata=meta,
            reference=ref_rows,
            tested=tst_rows,
        )

        counts = res.get("counts", {"compared": 0, "changed": 0})
        slog.log_info(f"    • {section}: diffs {counts.get('changed',0)}/{counts.get('compared',0)}")

        # Optional console preview
        diffs = res.get("diffs", []) or []
        to_print = min(args.print_diffs, len(diffs)) if args.print_diffs and diffs else 0
        for i in range(to_print):
            d = diffs[i]
            line = f"       - {d.get('key','')}.{d.get('field','')}: {d.get('ref','')} {d.get('op','!=')} {d.get('test','')}"
            slog.log_info(line)

        if args.print_matches and res.get("matches"):
            mprint = min(args.print_matches, len(res["matches"]))
            for i in range(mprint):
                m = res["matches"][i]
                line = f"       = {m.get('key','')}.{m.get('field','')}: {m.get('value','')}"
                slog.log_info(line)

        all_results[section] = res

    final_json = assemble_report(
        schema=schema,
        compare_results=all_results,
        reference_name="reference",
        profile_name="profile",
        section_rows=section_rows,
    )

    slog.log_step("Writing output JSON:", args.output_file)
    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(final_json, f, indent=2, ensure_ascii=False)

    if args.report:
        slog.log_ok("Generating HTML report")
        report_script = os.path.join(os.path.dirname(__file__), "report_html.py")
        if not os.path.exists(report_script):
            report_script = "report_html.py"

        try:
            subprocess.run(
                [sys.executable, report_script, "-v", args.output_file, "-o", "comparison.html"],
                check=True
            )
            slog.log_ok("HTML report written to results/comparison.html")
        except subprocess.CalledProcessError as e:
            slog.log_err(f"Failed to build HTML report: {e}")
        except Exception as e:
            slog.log_err(f"Error while generating HTML report: {e}")
    else:
        slog.log_info("Report generation skipped (use -rep/--report to enable).")

    slog.log_ok("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        from scrutiny import logging as slog
        slog.log_err(f"Error: {e}")
        sys.exit(1)
