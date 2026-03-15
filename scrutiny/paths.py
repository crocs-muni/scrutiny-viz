# scrutiny-viz/scrutiny/paths.py
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRUTINY_DIR = REPO_ROOT / "scrutiny"
SCHEMA_DIR = SCRUTINY_DIR / "schemas"
EXAMPLES_DIR = REPO_ROOT / "examples"
REPORT_ASSETS_DIR = SCRUTINY_DIR / "reporting" / "assets"
RESULTS_DIR_NAME = "results"


def repo_path(*parts: str) -> Path:
    return REPO_ROOT.joinpath(*parts)


def results_dir(base: str | Path | None = None) -> Path:
    root = Path(base) if base is not None else Path.cwd()
    return root / RESULTS_DIR_NAME