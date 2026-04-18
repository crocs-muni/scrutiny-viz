# scrutiny-viz/verification/comparators/registry.py
from __future__ import annotations

from importlib import import_module
import pkgutil
from typing import Dict

from .contracts import ComparatorPlugin, ComparatorSpec


_COMPARATORS: Dict[str, ComparatorPlugin] = {}
_ALIASES: Dict[str, str] = {}
_DISCOVERED = False
_DISCOVERED_PACKAGE: str | None = None


def _package_name() -> str:
    return "verification.comparators"


def _normalize_key(name: str) -> str:
    key = (name or "").strip().lower()
    if not key:
        raise ValueError("Comparator name must be non-empty")
    return key


def _register_plugin(plugin: ComparatorPlugin) -> None:
    spec = getattr(plugin, "spec", None)
    if spec is None:
        raise TypeError(f"Comparator plugin {plugin!r} is missing a 'spec' attribute")

    name = _normalize_key(spec.name)
    _COMPARATORS[name] = plugin
    _ALIASES[name] = name

    for alias in getattr(spec, "aliases", ()) or ():
        alias_key = _normalize_key(alias)
        _ALIASES[alias_key] = name


def register_plugin(plugin: ComparatorPlugin) -> None:
    _register_plugin(plugin)


def discover_builtin_comparators(*, force: bool = False) -> None:
    global _DISCOVERED, _DISCOVERED_PACKAGE

    package_name = _package_name()
    if _DISCOVERED and _DISCOVERED_PACKAGE == package_name and not force:
        return

    _COMPARATORS.clear()
    _ALIASES.clear()

    pkg = import_module(package_name)
    skip = {"contracts", "registry", "__init__"}

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
    discover_builtin_comparators()
    key = _normalize_key(name)
    return _ALIASES.get(key, key)


def get_plugin(name: str) -> ComparatorPlugin:
    discover_builtin_comparators()
    canon = normalize_name(name)
    try:
        return _COMPARATORS[canon]
    except KeyError as exc:
        known = ", ".join(list_types())
        raise KeyError(f"Unknown comparator '{name}'. Known: {known}") from exc


def list_types() -> list[str]:
    discover_builtin_comparators()
    return sorted(_COMPARATORS)


def list_specs() -> list[ComparatorSpec]:
    discover_builtin_comparators()
    return [plugin.spec for _, plugin in sorted(_COMPARATORS.items())]


def available_plugins() -> Dict[str, ComparatorPlugin]:
    discover_builtin_comparators()
    return dict(_COMPARATORS)
