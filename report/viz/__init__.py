# scrutiny-viz/report/viz/__init__.py
from .registry import discover_builtin_viz, get_plugin, list_by_slot, list_types, normalize_name

__all__ = [
    "discover_builtin_viz",
    "get_plugin",
    "list_by_slot",
    "list_types",
    "normalize_name",
]
