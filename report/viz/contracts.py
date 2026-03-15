# scrutiny-viz/report/viz/contracts.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class VizSpec:
    name: str
    slot: str
    aliases: Tuple[str, ...] = ()
    description: str = ""


class VizPlugin(ABC):
    spec: VizSpec

    def supports_variant(self, variant: Optional[str]) -> bool:
        return True

    @abstractmethod
    def render(self, **kwargs: Any) -> Any:
        raise NotImplementedError
