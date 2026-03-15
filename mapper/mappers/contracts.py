# scrutiny-viz/mapper/mappers/contracts.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, FrozenSet, Iterable, Optional

try:
    from .. import mapper_utils
except ImportError:  # pragma: no cover
    import mapper_utils


MapperFn = Callable[[list[list[str]], str], dict]


@dataclass(frozen=True)
class MapperSpec:
    name: str
    aliases: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class MappingContext:
    delimiter: str = ";"
    excluded_properties: FrozenSet[str] = field(default_factory=frozenset)


class MapperPlugin(ABC):
    """Base contract for all built-in mappers."""

    spec: MapperSpec

    def load_groups(self, file_path: str | Path) -> list[list[str]]:
        groups = mapper_utils.load_file(str(Path(file_path)))
        if groups is None:
            raise ValueError(f"Could not load input file: {file_path}")
        return groups

    def map_file(self, file_path: str | Path, context: MappingContext) -> dict:
        result = self.map_groups(self.load_groups(file_path), context)
        if context.excluded_properties:
            result = mapper_utils.apply_exclusions(result, set(context.excluded_properties))
        return result

    def legacy_map(self, groups: list[list[str]], delimiter: str) -> dict:
        return self.map_groups(groups, MappingContext(delimiter=delimiter))

    @abstractmethod
    def map_groups(self, groups: list[list[str]], context: MappingContext) -> dict:
        raise NotImplementedError


class FunctionMapperPlugin(MapperPlugin):
    """Adapter for tests or temporary legacy registrations."""

    def __init__(self, spec: MapperSpec, fn: MapperFn) -> None:
        self.spec = spec
        self._fn = fn

    def map_groups(self, groups: list[list[str]], context: MappingContext) -> dict:
        return self._fn(groups, context.delimiter)


def build_context(
    delimiter: str = ";",
    excluded_properties: Optional[Iterable[str]] = None,
) -> MappingContext:
    return MappingContext(
        delimiter=delimiter,
        excluded_properties=frozenset(excluded_properties or ()),
    )
