# scrutiny-viz/tests/mapper/conftest.py
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent           # C:\scrutiny-viz\tests\mapper
REPO_ROOT = THIS_DIR.parents[1]                     # C:\scrutiny-viz
MAPPER_DIR = REPO_ROOT / "mapper"                   # C:\scrutiny-viz\mapper

for p in (str(MAPPER_DIR), str(REPO_ROOT), str(THIS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)