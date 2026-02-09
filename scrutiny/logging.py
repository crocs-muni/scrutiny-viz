# scrutiny-viz/scrutiny/logging.py
from __future__ import annotations
import logging as _logging
import os
import sys

_ANSI = {
    "reset": "\x1b[0m",
    "bold": "\x1b[1m",
    "dim": "\x1b[2m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "red": "\x1b[31m",
    "cyan": "\x1b[36m",
    "gray": "\x1b[90m",
}

_COLOR_ENABLED: bool = False
_LOGGER = _logging.getLogger("scrutiny.verify")

def _supports_color() -> bool:
    return sys.stdout.isatty() and (os.environ.get("TERM") not in (None, "dumb"))

def c(text: str, color: str) -> str:
    if not _COLOR_ENABLED:
        return text
    return f"{_ANSI.get(color, '')}{text}{_ANSI['reset']}"

def setup_logging(verbosity: int = 0, log_file: str | None = None) -> None:
    """Configure console logging. Verbosity: 0→WARNING, 1→INFO, 2+→DEBUG."""
    global _COLOR_ENABLED
    _COLOR_ENABLED = _supports_color()

    level = _logging.WARNING
    if verbosity >= 2:
        level = _logging.DEBUG
    elif verbosity == 1:
        level = _logging.INFO

    _LOGGER.handlers.clear()
    _LOGGER.setLevel(level)

    fmt = _logging.Formatter("%(message)s")

    sh = _logging.StreamHandler(stream=sys.stdout)
    sh.setLevel(level)
    sh.setFormatter(fmt)
    _LOGGER.addHandler(sh)

    if log_file:
        fh = _logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        _LOGGER.addHandler(fh)

def log_info(msg: str) -> None:
    _LOGGER.info(msg)

def log_debug(msg: str) -> None:
    _LOGGER.debug(msg)

def log_warn(msg: str) -> None:
    _LOGGER.warning(f"{c('⚠', 'yellow')} {msg}")

def log_err(msg: str) -> None:
    _LOGGER.error(f"{c('✖', 'red')} {msg}")

def log_ok(msg: str) -> None:
    _LOGGER.info(f"{c('✓', 'green')} {msg}")

def log_step(label: str, value: str = "") -> None:
    arrow = c("→", "cyan")
    gray  = c(value, "gray") if value else ""
    _LOGGER.info(f"{arrow} {label}{(' ' + gray) if gray else ''}")
