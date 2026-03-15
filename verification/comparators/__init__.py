# scrutiny-viz/verification/comparators/__init__.py
from .contracts import CompareResult, ComparatorPlugin, ComparatorSpec
from .registry import (
    available_plugins,
    discover_builtin_comparators,
    get_plugin,
    list_types,
    normalize_name,
    register_plugin,
)

__all__ = [
    "CompareResult",
    "ComparatorPlugin",
    "ComparatorSpec",
    "available_plugins",
    "discover_builtin_comparators",
    "get_plugin",
    "list_types",
    "normalize_name",
    "register_plugin",
]
