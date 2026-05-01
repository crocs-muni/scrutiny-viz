# scrutiny-viz/scrutiny/batch/service.py
from __future__ import annotations

import csv
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from scrutiny import logging as slog
from scrutiny.errors import MapperError, ReportError, ScrutinyError, UserInputError
from scrutiny.paths import results_dir
from scrutiny.validation import require_dir, require_file, require_path_exists

from mapper import mapper_utils, registry as mapper_registry
from mapper.mappers.contracts import build_context
from report.service import run_report_html
from verification.service import run_verification


_slug_pat = re.compile(r"[^A-Za-z0-9._-]+")
log = slog.get_logger("BATCH")


def _slug(value: str) -> str:
    s = _slug_pat.sub("_", str(value or "").strip())
    return s.strip("._") or "item"


def _default_batch_id() -> str:
    return f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_json_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".json"


def _input_kind(path: Path) -> str:
    path = require_path_exists(path, label="Batch input path", component="BATCH")
    if path.is_dir():
        return "directory"
    if _is_json_file(path):
        return "json"
    return "rawfile"


def _resolve_mapper_type(shared_type: str | None, specific_type: str | None) -> str | None:
    return specific_type or shared_type


def _discover_profile_inputs(*, profiles: list[str], profiles_dir: str | None) -> list[Path]:
    if profiles:
        return [require_path_exists(profile, label="Profile input", component="BATCH") for profile in profiles]

    root = require_dir(profiles_dir or "", label="Profiles directory", component="BATCH")

    items: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if child.name.startswith("."):
            continue
        if child.is_file() or child.is_dir():
            items.append(child.resolve())
    return items


def _label_from_input(path: Path) -> str:
    return path.stem if path.is_file() else path.name


def _unique_output_stem(label: str, used: set[str]) -> str:
    base = _slug(label)
    if base not in used:
        used.add(base)
        return base

    index = 2
    while True:
        candidate = f"{base}_{index}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        index += 1


def _map_input_to_json(
    *,
    input_path: Path,
    role: str,
    mapper_type: str | None,
    mapped_dir: Path,
    delimiter: str,
    mapped_stem: str | None = None,
) -> tuple[Path, str]:
    kind = _input_kind(input_path)

    if kind == "json":
        return input_path, "json"

    if not mapper_type:
        if kind == "directory":
            raise UserInputError(
                f"{role} input '{input_path}' is a directory, so a mapper type is required. "
                f"Use --{role}-type or --type.",
                component="BATCH",
            )
        raise UserInputError(
            f"{role} input '{input_path}' is CSV/raw, so a mapper type is required. "
            f"Use --{role}-type or --type.",
            component="BATCH",
        )

    try:
        plugin = mapper_registry.get_plugin(mapper_type)
    except KeyError as exc:
        raise UserInputError(
            f"Unknown mapper type '{mapper_type}'. "
            "Use 'python scrutinize.py map --list-mappers' to inspect available plugins.",
            component="BATCH",
        ) from exc
    context = build_context(delimiter=delimiter)

    if kind == "directory":
        if not getattr(plugin, "accepts_directories", False):
            raise UserInputError(f"Mapper '{mapper_type}' does not support directory input: {input_path}", component="BATCH")
        payload = plugin.map_path(input_path, context)
    else:
        try:
            payload = plugin.map_path(input_path, context)
        except Exception:
            groups = mapper_utils.load_file(str(input_path))
            if groups is None:
                raise MapperError(f"Failed to load raw input file: {input_path}", component="BATCH")
            payload = plugin.map_groups(groups, context)

    mapped_label = mapped_stem or _label_from_input(input_path)
    out_name = f"{_slug(role)}_{_slug(mapped_label)}.json"
    out_path = mapped_dir / out_name
    _write_json(out_path, payload)
    return out_path, mapper_type


def _aggregate_verify_counts(report_json: dict[str, Any]) -> dict[str, int]:
    sections = report_json.get("sections", {}) or {}
    totals = {"compared": 0, "changed": 0, "matched": 0, "only_ref": 0, "only_test": 0}

    for section in sections.values():
        stats = section.get("stats") or section.get("counts") or {}
        totals["compared"] += int(stats.get("compared", 0) or 0)
        totals["changed"] += int(stats.get("changed", 0) or 0)
        totals["matched"] += int(stats.get("matched", 0) or 0)
        totals["only_ref"] += int(stats.get("only_ref", 0) or 0)
        totals["only_test"] += int(stats.get("only_test", 0) or 0)

    return totals


def _should_generate_report(overall: str, report_mode: str) -> bool:
    mode = str(report_mode or "nonmatch").strip().lower()
    verdict = str(overall or "WARN").strip().upper()

    if mode == "none":
        return False
    if mode == "all":
        return True
    return verdict != "MATCH"


def _relative_str(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def _generate_report_into_batch(
    *,
    verify_json_path: Path,
    report_dir: Path,
    output_stem: str,
) -> Path:
    temp_name = f"batch_tmp_{output_stem}_{datetime.now().strftime('%H%M%S%f')}.html"
    report_result = run_report_html(
        verification_profile=str(verify_json_path),
        output_file=temp_name,
        exclude_style_and_scripts=False,
        no_zip=True,
    )
    if not report_result.get("ok", False):
        raise ReportError(
            f"Failed to build HTML report for {verify_json_path}: "
            f"{report_result.get('error', 'unknown error')}",
            component="BATCH",
        )

    source = Path(report_result["html_path"]).resolve()
    if not source.exists():
        raise ReportError(f"Expected generated report not found: {source}", component="BATCH")

    destination = report_dir / f"{output_stem}.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return destination


def run_batch_verification(
    *,
    schema_path: str,
    reference_input: str,
    profiles: list[str] | None = None,
    profiles_dir: str | None = None,
    shared_type: str | None = None,
    reference_type: str | None = None,
    profile_type: str | None = None,
    batch_id: str | None = None,
    delimiter: str = ";",
    report_mode: str = "nonmatch",
    keep_mapped: bool = False,
) -> dict[str, Any]:
    try:
        schema_resolved = require_file(schema_path, label="Schema file", component="BATCH")
        profile_inputs = _discover_profile_inputs(profiles=profiles or [], profiles_dir=profiles_dir)
    except ScrutinyError as exc:
        return {"ok": False, "exit_code": int(getattr(exc, "exit_code", 1)), "error": str(exc)}

    if not profile_inputs:
        log.err("No profile inputs found.")
        return {"ok": False, "exit_code": 1, "error": "No profile inputs found."}

    schema_path = str(schema_resolved)

    batch_name = _slug(batch_id or _default_batch_id())
    batch_root = results_dir() / batch_name
    verify_dir = batch_root / "verify"
    report_dir = batch_root / "report"
    mapped_dir = batch_root / "mapped"

    batch_root.mkdir(parents=True, exist_ok=True)
    verify_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    reference_input_path = Path(reference_input).resolve()
    reference_mapper_type = _resolve_mapper_type(shared_type, reference_type)
    profile_mapper_type = _resolve_mapper_type(shared_type, profile_type)

    log.step("Batch reference", str(reference_input_path))
    try:
        reference_json_path, _ = _map_input_to_json(
            input_path=reference_input_path,
            role="reference",
            mapper_type=reference_mapper_type,
            mapped_dir=mapped_dir,
            delimiter=delimiter,
        )
    except Exception as exc:
        log.err(f"Failed to prepare reference input: {exc}")
        return {"ok": False, "exit_code": 1, "error": f"Failed to prepare reference input: {exc}"}

    summary_rows: list[dict[str, Any]] = []
    used_stems: set[str] = set()

    for profile_input in profile_inputs:
        label = _label_from_input(profile_input)
        out_stem = _unique_output_stem(label, used_stems)

        log.step("Batch profile", str(profile_input))
        verify_json_path = verify_dir / f"{out_stem}.verify.json"
        html_report_path: Path | None = None
        normalized_profile_path: Path | None = None
        overall = "ERROR"
        counts = {"compared": 0, "changed": 0, "matched": 0, "only_ref": 0, "only_test": 0}
        error_message = ""

        try:
            normalized_profile_path, _ = _map_input_to_json(
                input_path=profile_input,
                role="profile",
                mapper_type=profile_mapper_type,
                mapped_dir=mapped_dir,
                delimiter=delimiter,
                mapped_stem=out_stem,
            )

            verify_result = run_verification(
                schema_path=schema_path,
                reference_path=str(reference_json_path),
                profile_path=str(normalized_profile_path),
                output_file=str(verify_json_path),
                emit_matches=False,
                print_diffs=0,
                print_matches=0,
                report=False,
            )
            if not verify_result.get("ok", False):
                raise RuntimeError(
                    verify_result.get(
                        "error",
                        f"Verification failed with exit code {verify_result.get('exit_code', 1)}",
                    )
                )

            verify_json = _read_json(verify_json_path)
            overall = str(verify_json.get("overall", "WARN")).upper()
            counts = _aggregate_verify_counts(verify_json)

            if _should_generate_report(overall, report_mode):
                html_report_path = _generate_report_into_batch(
                    verify_json_path=verify_json_path,
                    report_dir=report_dir,
                    output_stem=out_stem,
                )

        except Exception as exc:
            error_message = str(exc)
            log.err(f"[{label}] {exc}")

        summary_rows.append(
            {
                "profile_name": label,
                "input_path": str(profile_input),
                "normalized_input_path": _relative_str(normalized_profile_path, batch_root),
                "verify_json_path": _relative_str(
                    verify_json_path if verify_json_path.exists() else None,
                    batch_root,
                ),
                "html_report_path": _relative_str(html_report_path, batch_root),
                "overall": overall,
                "compared": counts["compared"],
                "changed": counts["changed"],
                "matched": counts["matched"],
                "only_ref": counts["only_ref"],
                "only_test": counts["only_test"],
                "error": error_message,
            }
        )

    if not keep_mapped and mapped_dir.exists():
        shutil.rmtree(mapped_dir, ignore_errors=True)

    inputs_payload = {
        "batch_id": batch_name,
        "schema_path": str(schema_resolved),
        "reference_input": str(reference_input_path),
        "reference_json_path": _relative_str(reference_json_path, batch_root),
        "reference_type": reference_mapper_type or "",
        "profile_type": profile_mapper_type or "",
        "shared_type": shared_type or "",
        "report_mode": report_mode,
        "delimiter": delimiter,
        "profiles": [str(path) for path in profile_inputs],
    }
    _write_json(batch_root / "inputs.json", inputs_payload)
    _write_json(batch_root / "summary.json", {"batch_id": batch_name, "rows": summary_rows})

    csv_fields = [
        "profile_name",
        "input_path",
        "normalized_input_path",
        "verify_json_path",
        "html_report_path",
        "overall",
        "compared",
        "changed",
        "matched",
        "only_ref",
        "only_test",
        "error",
    ]
    with (batch_root / "summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    reports_generated = sum(1 for row in summary_rows if row.get("html_report_path"))
    profile_errors = sum(1 for row in summary_rows if row.get("error"))
    match_profiles = sum(1 for row in summary_rows if row.get("overall") == "MATCH")
    nonmatch_profiles = sum(1 for row in summary_rows if row.get("overall") != "MATCH")

    return {
        "ok": profile_errors == 0,
        "exit_code": 0 if profile_errors == 0 else 1,
        "batch_root": str(batch_root.resolve()),
        "summary_json_path": str((batch_root / "summary.json").resolve()),
        "summary_csv_path": str((batch_root / "summary.csv").resolve()),
        "verify_dir": str(verify_dir.resolve()),
        "report_dir": str(report_dir.resolve()),
        "profiles_processed": len(summary_rows),
        "reports_generated": reports_generated,
        "profile_errors": profile_errors,
        "match_profiles": match_profiles,
        "nonmatch_profiles": nonmatch_profiles,
    }
