# scrutiny/comparators/interface.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypedDict


class CompareResult(TypedDict, total=False):
    section: str
    result: str
    counts: Dict[str, int]
    labels: Dict[str, str]
    diffs: List[Dict[str, Any]]
    matches: List[Dict[str, Any]]
    artifacts: Dict[str, Any]  # comparator-specific extras (e.g. chart_rows)


class Comparator(ABC):
    """
    Stable comparator interface.
    Implementations should be pure functions of inputs (no global state).
    """

    @abstractmethod
    def compare(
        self,
        *,
        section: str,
        key_field: str,
        show_field: Optional[str],
        metadata: Dict[str, Any],
        reference: List[Dict[str, Any]],
        tested: List[Dict[str, Any]]
    ) -> CompareResult:
        """
        Return a normalized CompareResult (see TypedDict).
        Implementations MAY propose a `result` but the reporter will finalize severity.
        """
        ...
