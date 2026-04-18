# scrutiny-viz/report/bundle.py
from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse

from scrutiny import logging as slog

_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(value: str, *, fallback: str = "item") -> str:
    sanitized = _NAME_PATTERN.sub("_", str(value or "").strip())
    return sanitized.strip("._") or fallback


def _is_tracecompare_table_section(section: Dict[str, Any]) -> bool:
    report_cfg = section.get("report") or {}
    raw_types = report_cfg.get("types") or []

    for item in raw_types:
        if not isinstance(item, dict):
            continue
        type_name = str(item.get("type") or "").strip().lower()
        variant = str(item.get("variant") or "").strip().lower()
        if type_name == "table" and variant == "tracescompare":
            return True
    return False


def _file_uri_to_path(uri: str) -> Optional[Path]:
    try:
        parsed = urlparse(uri)
    except Exception:
        return None

    if parsed.scheme.lower() != "file":
        return None

    netloc = unquote(parsed.netloc or "")
    path = unquote(parsed.path or "")

    if path.startswith("/") and len(path) >= 3 and path[2] == ":":
        path = path[1:]

    if netloc:
        path = f"//{netloc}{path}" if path else f"//{netloc}"

    return Path(path) if path else None


def _asset_ref_to_local_path(raw_ref: str, *, base_dir: Path) -> Optional[Path]:
    raw_ref = str(raw_ref or "").strip()
    if not raw_ref:
        return None

    if raw_ref.lower().startswith("file://"):
        file_path = _file_uri_to_path(raw_ref)
        return file_path.resolve() if file_path is not None and file_path.exists() else None

    parsed = urlparse(raw_ref)
    if parsed.scheme and parsed.scheme.lower() != "file":
        return None

    path = Path(raw_ref)
    if not path.is_absolute():
        path = (base_dir / path).resolve()

    return path.resolve() if path.exists() else None


def _ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _copy_asset(
    *,
    src: Path,
    assets_root: Path,
    section_name: str,
    operation_code: str,
    pipeline_code: str,
    image_name: str,
) -> Path:
    rel_dir = (
        Path("trace_images")
        / _safe_name(section_name, fallback="section")
        / _safe_name(operation_code, fallback="operation")
        / _safe_name(pipeline_code, fallback="pipeline")
    )
    dst_dir = assets_root / rel_dir
    dst_dir.mkdir(parents=True, exist_ok=True)

    preferred_name = Path(image_name).name if str(image_name or "").strip() else src.name
    preferred_stem = _safe_name(Path(preferred_name).stem, fallback=src.stem or "image")
    preferred_suffix = Path(preferred_name).suffix or src.suffix or ".png"

    dst = _ensure_unique_path(dst_dir / f"{preferred_stem}{preferred_suffix}")
    shutil.copy2(src, dst)
    return dst


def prepare_report_bundle(
    report: Dict[str, Any],
    *,
    source_report_path: str | Path,
    html_output_path: str | Path,
) -> Dict[str, Any]:
    source_report = Path(source_report_path).resolve()
    html_output = Path(html_output_path).resolve()
    html_dir = html_output.parent
    source_report_dir = source_report.parent

    report_copy: Dict[str, Any] = copy.deepcopy(report)
    assets_root = html_dir / f"{html_output.stem}_assets"

    tracecompare_detected = False
    copied_assets = 0
    missing_assets = 0
    rewritten_paths = 0

    for section_name, section in (report_copy.get("sections") or {}).items():
        if not isinstance(section, dict) or not _is_tracecompare_table_section(section):
            continue

        tracecompare_detected = True
        operations = (section.get("artifacts") or {}).get("operations") or []
        for operation in operations:
            if not isinstance(operation, dict):
                continue
            operation_code = str(operation.get("operation_code") or "")

            for pipeline in operation.get("comparison_results") or []:
                if not isinstance(pipeline, dict):
                    continue
                pipeline_code = str(pipeline.get("pipeline_code") or "")

                for comparison in pipeline.get("comparison_results") or []:
                    if not isinstance(comparison, dict):
                        continue

                    raw_ref = str(comparison.get("image_path") or "").strip()
                    image_name = str(comparison.get("image_name") or "").strip()
                    src = _asset_ref_to_local_path(raw_ref, base_dir=source_report_dir)
                    if src is None:
                        missing_assets += 1
                        continue

                    try:
                        dst = _copy_asset(
                            src=src,
                            assets_root=assets_root,
                            section_name=section_name,
                            operation_code=operation_code,
                            pipeline_code=pipeline_code,
                            image_name=image_name,
                        )
                    except Exception as exc:
                        slog.log_warn(f"[BUNDLE] Failed to copy trace image '{src}': {exc}")
                        missing_assets += 1
                        continue

                    rel_path = dst.relative_to(html_dir).as_posix()
                    if str(comparison.get("image_path") or "") != rel_path:
                        comparison["image_path"] = rel_path
                        rewritten_paths += 1
                    copied_assets += 1

    if not tracecompare_detected:
        return {
            "report": report,
            "bundled_json_path": None,
            "assets_dir": None,
            "copied_assets": 0,
            "missing_assets": 0,
            "rewritten_paths": 0,
            "tracecompare_detected": False,
        }

    assets_root.mkdir(parents=True, exist_ok=True)
    bundled_json_path = html_dir / f"{html_output.stem}.bundled.json"
    bundled_json_path.write_text(json.dumps(report_copy, indent=2, ensure_ascii=False), encoding="utf-8")

    assets_dir: Optional[Path] = assets_root if copied_assets > 0 else None
    if assets_dir is None:
        try:
            if assets_root.exists() and not any(assets_root.rglob("*")):
                assets_root.rmdir()
        except Exception:
            pass

    return {
        "report": report_copy,
        "bundled_json_path": bundled_json_path,
        "assets_dir": assets_dir,
        "copied_assets": copied_assets,
        "missing_assets": missing_assets,
        "rewritten_paths": rewritten_paths,
        "tracecompare_detected": True,
    }
