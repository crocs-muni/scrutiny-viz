# scrutiny-viz/mapper/mappers/contracts.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, FrozenSet, Optional


@dataclass(frozen=True)
class MapperSpec:
    name: str
    aliases: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class MappingContext:
    delimiter: str = ";"
    excluded_properties: FrozenSet[str] = field(default_factory=frozenset)


def build_context(
    delimiter: str = ";",
    excluded_properties: Optional[set[str] | FrozenSet[str]] = None,
) -> MappingContext:
    return MappingContext(
        delimiter=delimiter,
        excluded_properties=frozenset(excluded_properties or ()),
    )


class MapperPlugin(ABC):
    spec: MapperSpec

    @property
    def accepts_directories(self) -> bool:
        return False

    def ingest(self, source_path: Path) -> Any:
        """
        Default ingest for grouped-text mappers.
        RSABias-style mappers should override this.
        """
        try:
            from .. import mapper_utils
        except ImportError:
            import mapper_utils  # type: ignore

        groups = mapper_utils.load_file(str(source_path))
        if groups is None:
            raise FileNotFoundError(f"Failed to load grouped text input from: {source_path}")
        return groups

    def map_source(self, source: Any, context: MappingContext) -> dict[str, Any]:
        """
        Default source mapping for grouped-text mappers.
        Directory/JSON bundle mappers should override this.
        """
        if not isinstance(source, list):
            raise TypeError(
                f"Mapper '{self.spec.name}' expected grouped text input, got {type(source).__name__}"
            )
        return self.map_groups(source, context)

    @abstractmethod
    def map_groups(self, groups: list[list[str]], context: MappingContext) -> dict[str, Any]:
        raise NotImplementedError

    def map_path(self, source_path: Path, context: MappingContext) -> dict[str, Any]:
        return self.map_source(self.ingest(source_path), context)