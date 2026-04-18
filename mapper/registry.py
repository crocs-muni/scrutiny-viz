# scrutiny-viz/mapper/registry.py
from __future__ import annotations

import pkgutil
from importlib import import_module
from typing import Dict

from .mappers.contracts import MapperPlugin, MapperSpec


_ALIASES: Dict[str, str] = {}
_MAPPERS: Dict[str, MapperPlugin] = {}
_DISCOVERED = False
_DISCOVERED_PACKAGE: str | None = None


def _norm(value: str) -> str:
    return (value or "").strip().lower()


def _package_name() -> str:
    return f"{__package__}.mappers" if __package__ else "mapper.mappers"


def _register_plugin(plugin: MapperPlugin) -> None:
    spec = getattr(plugin, "spec", None)
    if spec is None:
        raise TypeError("Mapper plugin must expose a 'spec' attribute")
    if not getattr(spec, "name", ""):
        raise ValueError("Mapper plugin spec.name must be non-empty")

    canon = _norm(spec.name)
    _MAPPERS[canon] = plugin
    _ALIASES[canon] = canon

    for alias in getattr(spec, "aliases", ()):
        alias_key = _norm(alias)
        if alias_key:
            _ALIASES[alias_key] = canon


def discover_builtin_mappers(*, force: bool = False) -> None:
    global _DISCOVERED, _DISCOVERED_PACKAGE

    package_name = _package_name()

    if _DISCOVERED and _DISCOVERED_PACKAGE == package_name and not force:
        return

    _ALIASES.clear()
    _MAPPERS.clear()

    pkg = import_module(package_name)
    skip = {"contracts", "__pycache__"}

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


def normalize_type(name: str) -> str:
    discover_builtin_mappers()
    if not name:
        raise ValueError("mapper type must be a non-empty string")
    key = _norm(name)
    return _ALIASES.get(key, key)


def list_types() -> list[str]:
    discover_builtin_mappers()
    return sorted(_MAPPERS.keys())


def list_specs() -> list[MapperSpec]:
    discover_builtin_mappers()
    return [plugin.spec for _, plugin in sorted(_MAPPERS.items())]


def get_plugin(name: str) -> MapperPlugin:
    discover_builtin_mappers()
    canon = normalize_type(name)
    try:
        return _MAPPERS[canon]
    except KeyError as exc:
        raise KeyError(f"Unknown mapper type '{name}'. Known: {', '.join(list_types())}") from exc