# scrutiny-viz/scrutiny/plugin_core.py
from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
import pkgutil
from typing import Dict, Generic, Iterable, Iterator, Optional, Protocol, TypeVar


@dataclass(frozen=True)
class PluginSpec:
    name: str
    kind: str
    aliases: tuple[str, ...] = ()
    description: str = ""
    version: str = "1"
    metadata: dict[str, object] = field(default_factory=dict)


class SupportsSpec(Protocol):
    spec: PluginSpec


PluginT = TypeVar("PluginT", bound=SupportsSpec)


class PluginRegistry(Generic[PluginT]):
    def __init__(self, *, kind: str) -> None:
        self.kind = kind
        self._plugins: Dict[str, PluginT] = {}
        self._aliases: Dict[str, str] = {}

    @staticmethod
    def _norm(value: str) -> str:
        return (value or "").strip().lower()

    def clear(self) -> None:
        self._plugins.clear()
        self._aliases.clear()

    def register(self, plugin: PluginT) -> None:
        spec = plugin.spec
        if spec.kind != self.kind:
            raise ValueError(f"Cannot register kind '{spec.kind}' in '{self.kind}' registry")

        canonical = self._norm(spec.name)
        if not canonical:
            raise ValueError(f"{self.kind.title()} plugin name must be non-empty")
        if canonical in self._plugins:
            raise ValueError(f"Duplicate {self.kind} plugin '{canonical}'")

        self._plugins[canonical] = plugin
        self._aliases[canonical] = canonical

        for alias in spec.aliases:
            norm_alias = self._norm(alias)
            if not norm_alias:
                continue
            if norm_alias in self._aliases and self._aliases[norm_alias] != canonical:
                raise ValueError(
                    f"Alias '{alias}' already points to '{self._aliases[norm_alias]}' and cannot also point to '{canonical}'"
                )
            self._aliases[norm_alias] = canonical

    def normalize_name(self, name: str) -> str:
        key = self._norm(name)
        if not key:
            raise ValueError(f"{self.kind} name must be non-empty")
        return self._aliases.get(key, key)

    def get(self, name: str) -> PluginT:
        canonical = self.normalize_name(name)
        try:
            return self._plugins[canonical]
        except KeyError as exc:
            known = ", ".join(self.names())
            raise KeyError(f"Unknown {self.kind} '{name}'. Known: {known}") from exc

    def names(self) -> list[str]:
        return sorted(self._plugins.keys())

    def specs(self) -> list[PluginSpec]:
        return [self._plugins[name].spec for name in self.names()]

    def values(self) -> Iterator[PluginT]:
        for name in self.names():
            yield self._plugins[name]


def discover_package_plugins(package_name: str) -> list[SupportsSpec]:
    package = import_module(package_name)
    discovered: list[SupportsSpec] = []

    for _, module_name, _ in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        module = import_module(module_name)
        module_plugins = getattr(module, "PLUGINS", None)
        if module_plugins is None:
            continue
        if not isinstance(module_plugins, Iterable):
            raise TypeError(f"{module_name}.PLUGINS must be iterable")
        for plugin in module_plugins:
            spec = getattr(plugin, "spec", None)
            if spec is None:
                raise TypeError(f"Plugin exported by {module_name} does not expose .spec")
            discovered.append(plugin)

    return discovered
