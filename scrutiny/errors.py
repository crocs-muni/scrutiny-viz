# scrutiny-viz/scrutiny/errors.py
from __future__ import annotations


class ScrutinyError(Exception):
    """Base class for expected, user-facing scrutiny-viz errors."""

    exit_code = 1
    component = "APP"

    def __init__(self, message: str, *, component: str | None = None, exit_code: int | None = None):
        super().__init__(message)
        self.message = str(message)
        if component is not None:
            self.component = str(component).upper()
        if exit_code is not None:
            self.exit_code = int(exit_code)

    def __str__(self) -> str:
        return self.message


class UserInputError(ScrutinyError):
    """Invalid CLI argument, missing input path, or unusable user-provided path."""

    exit_code = 2
    component = "APP"


class ConfigError(ScrutinyError):
    """Invalid configuration that prevents a safe workflow run."""

    exit_code = 2
    component = "CONFIG"


class SchemaError(ConfigError):
    """Invalid schema file or schema content."""

    component = "SCHEMA"


class IngestError(ScrutinyError):
    """Invalid input JSON shape or section content during ingest."""

    exit_code = 2
    component = "INGEST"


class MapperError(ScrutinyError):
    """Mapper workflow failure."""

    exit_code = 1
    component = "MAPPER"


class VerificationError(ScrutinyError):
    """Verification workflow failure."""

    exit_code = 1
    component = "VERIFY"


class ReportError(ScrutinyError):
    """Report rendering failure."""

    exit_code = 1
    component = "REPORT"


class BatchError(ScrutinyError):
    """Batch verification workflow failure."""

    exit_code = 1
    component = "BATCH"
