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
_LOGGER = _logging.getLogger("scrutiny")


class _ComponentAdapter(_logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("component", self.extra["component"])
        return msg, kwargs


class ComponentLogger:
    def __init__(self, component: str):
        self.component = str(component or "APP").upper()
        self._adapter = _ComponentAdapter(_LOGGER, {"component": self.component})

    def info(self, msg: str) -> None:
        self._adapter.info(msg)

    def debug(self, msg: str) -> None:
        self._adapter.debug(msg)

    def warn(self, msg: str) -> None:
        self._adapter.warning(msg)

    def err(self, msg: str) -> None:
        self._adapter.error(msg)

    def ok(self, msg: str) -> None:
        self._adapter.info(msg)

    def step(self, label: str, value: str = "") -> None:
        gray = c(value, "gray") if value else ""
        self._adapter.info(f"{label}{(' ' + gray) if gray else ''}")


def get_logger(component: str) -> ComponentLogger:
    return ComponentLogger(component)


def _supports_color() -> bool:
    return sys.stdout.isatty() and (os.environ.get("TERM") not in (None, "dumb"))


def c(text: str, color: str) -> str:
    if not _COLOR_ENABLED:
        return text
    return f"{_ANSI.get(color, '')}{text}{_ANSI['reset']}"


class _ComponentFormatter(_logging.Formatter):
    def format(self, record):
        if not hasattr(record, "component"):
            record.component = "APP"
        record.levelname = record.levelname.upper()
        return super().format(record)


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
    _LOGGER.propagate = False

    fmt = _ComponentFormatter("[%(component)s][%(levelname)s] %(message)s")

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
    get_logger("APP").info(msg)


def log_debug(msg: str) -> None:
    get_logger("APP").debug(msg)


def log_warn(msg: str) -> None:
    get_logger("APP").warn(msg)


def log_err(msg: str) -> None:
    get_logger("APP").err(msg)


def log_ok(msg: str) -> None:
    get_logger("APP").ok(msg)


def log_step(label: str, value: str = "") -> None:
    get_logger("APP").step(label, value)