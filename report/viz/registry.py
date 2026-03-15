# scrutiny-viz/report/viz/registry.py
from __future__ import annotations

import pkgutil
from importlib import import_module
from typing import Dict, List

from .contracts import VizPlugin

_VIZ: Dict[str, VizPlugin] = {}
_ALIASES: Dict[str, str] = {}
_DISCOVERED = False
_DISCOVERED_PACKAGE: str | None = None


def _package_name() -> str:
    return "report.viz"


def _canon(name: str) -> str:
    return str(name or "").strip().lower().replace("-", "").replace("_", "")


def _register_plugin(plugin: VizPlugin) -> None:
    spec = plugin.spec
    canon = _canon(spec.name)
    if not canon:
        raise ValueError("Viz plugin name must not be empty")
    if canon in _VIZ:
        raise ValueError(f"Duplicate viz plugin name: {spec.name}")

    _VIZ[canon] = plugin
    _ALIASES[canon] = canon

    for alias in getattr(spec, "aliases", ()):
        alias_canon = _canon(alias)
        if not alias_canon:
            continue
        prev = _ALIASES.get(alias_canon)
        if prev is not None and prev != canon:
            raise ValueError(f"Alias '{alias}' already mapped to '{prev}'")
        _ALIASES[alias_canon] = canon


def discover_builtin_viz(*, force: bool = False) -> None:
    global _DISCOVERED, _DISCOVERED_PACKAGE

    package_name = _package_name()
    if _DISCOVERED and _DISCOVERED_PACKAGE == package_name and not force:
        return

    _VIZ.clear()
    _ALIASES.clear()

    pkg = import_module(package_name)
    skip = {"contracts", "registry"}

    for module_info in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        short_name = module_info.name.rsplit(".", 1)[-1]
        if short_name.startswith("_") or short_name in skip:
            continue

        module = import_module(module_info.name)
        plugins = getattr(module, "PLUGINS", None)
        if plugins:
            for plugin in plugins:
                _register_plugin(plugin)

    _DISCOVERED = True
    _DISCOVERED_PACKAGE = package_name


def normalize_name(name: str) -> str:
    discover_builtin_viz()
    key = _canon(name)
    return _ALIASES.get(key, key)


def list_types() -> List[str]:
    discover_builtin_viz()
    return sorted(_VIZ.keys())


def list_by_slot(slot: str) -> List[str]:
    discover_builtin_viz()
    slot_norm = str(slot or "").strip().lower()
    return sorted(name for name, plugin in _VIZ.items() if plugin.spec.slot == slot_norm)


def get_plugin(name: str) -> VizPlugin:
    discover_builtin_viz()
    canon = normalize_name(name)
    try:
        return _VIZ[canon]
    except KeyError as exc:
        raise KeyError(f"Unknown viz plugin '{name}'. Known: {', '.join(list_types())}") from exc
