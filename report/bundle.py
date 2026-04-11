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


_name_pat = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(value: str, *, fallback: str = "item") -> str:
    s = _name_pat.sub("_", str(value or "").strip())
    return s.strip("._") or fallback


def _is_tracecompare_table_section(section: Dict[str, Any]) -> bool:
    rep = section.get("report") or {}
    raw_types = rep.get("types") or []

    for item in raw_types:
        if isinstance(item, dict):
            tp = str(item.get("type") or "").strip().lower()
            variant = str(item.get("variant") or "").strip().lower()
            if tp == "table" and variant == "tracescompare":
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

    # Windows drive letter form: /C:/path -> C:/path
    if path.startswith("/") and len(path) >= 3 and path[2] == ":":
        path = path[1:]

    # UNC path: file://server/share/path
    if netloc:
        if path:
            path = f"//{netloc}{path}"
        else:
            path = f"//{netloc}"

    if not path:
        return None

    return Path(path)


def _asset_ref_to_local_path(raw_ref: str, *, base_dir: Path) -> Optional[Path]:
    raw_ref = str(raw_ref or "").strip()
    if not raw_ref:
        return None

    if raw_ref.lower().startswith("file://"):
        p = _file_uri_to_path(raw_ref)
        if p is not None and p.exists():
            return p.resolve()
        return None

    parsed = urlparse(raw_ref)
    if parsed.scheme and parsed.scheme.lower() != "file":
        return None

    p = Path(raw_ref)
    if not p.is_absolute():
        p = (base_dir / p).resolve()

    if p.exists():
        return p.resolve()

    return None


def _ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    i = 2
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


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

    preferred = Path(image_name).name if str(image_name or "").strip() else src.name
    preferred_stem = _safe_name(Path(preferred).stem, fallback=src.stem or "image")
    preferred_suffix = Path(preferred).suffix or src.suffix or ".png"

    dst = _ensure_unique_path(dst_dir / f"{preferred_stem}{preferred_suffix}")
    shutil.copy2(src, dst)
    return dst


def prepare_report_bundle(
    report: Dict[str, Any],
    *,
    source_report_path: str | Path,
    html_output_path: str | Path,
) -> Dict[str, Any]:
    """
    Prepare a portable report bundle for tracecompare sections only.

    - copies local trace PNGs into a report-local assets folder
    - rewrites image_path values in a copied report object to relative paths
    - writes a bundled JSON copy next to the HTML output
    """
    source_report = Path(source_report_path).resolve()
    html_output = Path(html_output_path).resolve()
    html_dir = html_output.parent
    source_report_dir = source_report.parent

    report_copy: Dict[str, Any] = copy.deepcopy(report)
    assets_root = html_dir / f"{html_output.stem}_assets"

    any_tracecompare = False
    copied_assets = 0
    missing_assets = 0
    rewritten_paths = 0

    sections = report_copy.get("sections") or {}
    for section_name, section in sections.items():
        if not isinstance(section, dict):
            continue
        if not _is_tracecompare_table_section(section):
            continue

        any_tracecompare = True

        artifacts = section.get("artifacts") or {}
        operations = artifacts.get("operations") or []
        for operation in operations:
            if not isinstance(operation, dict):
                continue

            operation_code = str(operation.get("operation_code") or "")
            pipeline_results = operation.get("comparison_results") or []
            for pipeline in pipeline_results:
                if not isinstance(pipeline, dict):
                    continue

                pipeline_code = str(pipeline.get("pipeline_code") or "")
                comparisons = pipeline.get("comparison_results") or []
                for comparison in comparisons:
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
                    except Exception as e:
                        slog.log_warn(f"[BUNDLE] Failed to copy trace image '{src}': {e}")
                        missing_assets += 1
                        continue

                    rel_path = dst.relative_to(html_dir).as_posix()
                    if str(comparison.get("image_path") or "") != rel_path:
                        comparison["image_path"] = rel_path
                        rewritten_paths += 1
                    copied_assets += 1

    if not any_tracecompare:
        return {
            "report": report,
            "bundled_json_path": None,
            "assets_dir": None,
            "copied_assets": 0,
            "missing_assets": 0,
            "rewritten_paths": 0,
            "tracecompare_detected": False,
        }

    if not assets_root.exists():
        assets_root.mkdir(parents=True, exist_ok=True)

    bundled_json_path = html_dir / f"{html_output.stem}.bundled.json"
    bundled_json_path.write_text(
        json.dumps(report_copy, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # If nothing was copied, do not pretend there is a usable assets folder
    assets_dir: Optional[Path] = assets_root if copied_assets > 0 else None

    # Best-effort cleanup of empty root dir
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