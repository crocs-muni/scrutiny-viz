# scrutiny-viz/tests/conftest.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

for p in (ROOT, TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
