# scrutiny/comparators/registry.py
from __future__ import annotations
from typing import Dict, Type
from .interface import Comparator

_REGISTRY: Dict[str, Type[Comparator]] = {}

def register(name: str, cls: Type[Comparator]) -> None:
    key = (name or "").strip().lower()
    if not key:
        raise ValueError("Comparator name must be non-empty")
    _REGISTRY[key] = cls

def get(name: str) -> Type[Comparator] | None:
    return _REGISTRY.get((name or "").strip().lower())

def available() -> Dict[str, Type[Comparator]]:
    return dict(_REGISTRY)
