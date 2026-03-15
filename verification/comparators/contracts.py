# scrutiny-viz/verification/comparators/contracts.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, TypedDict


class CompareResult(TypedDict, total=False):
    section: str
    result: str
    counts: Dict[str, int]
    stats: Dict[str, int]
    labels: Dict[str, str]
    key_labels: Dict[str, str]
    diffs: List[Dict[str, Any]]
    matches: List[Dict[str, Any]]
    artifacts: Dict[str, Any]


@dataclass(frozen=True)
class ComparatorSpec:
    name: str
    aliases: Tuple[str, ...] = ()
    description: str = ""


class ComparatorPlugin(ABC):
    """
    Stable comparator plugin contract.

    Comparator implementations should be pure functions of their inputs and should not
    mutate global state. The return value must follow CompareResult so the reporting
    layer can stay generic.
    """

    spec: ComparatorSpec

    @abstractmethod
    def compare(
        self,
        *,
        section: str,
        key_field: str,
        show_field: Optional[str],
        metadata: Dict[str, Any],
        reference: List[Dict[str, Any]],
        tested: List[Dict[str, Any]],
    ) -> CompareResult:
        ...
