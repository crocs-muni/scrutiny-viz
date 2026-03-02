# scrutiny-viz/mapper/registry.py
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Callable, Dict, Iterable

from jcperf_parser import convert_to_map_jcperf
from tpm_parser import convert_to_map_tpm
from jcaid_parser import convert_to_map_aid
from jcalg_support import convert_to_map_jcalgsupport

Mapper = Callable[[list[list[str]], str], dict]


@dataclass(frozen=True)
class MapperSpec:
    name: str
    fn: Mapper
    aliases: tuple[str, ...] = ()


_ALIASES: Dict[str, str] = {}
_MAPPERS: Dict[str, Mapper] = {}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def register_mapper(name: str, fn: Mapper, aliases: Iterable[str] = ()) -> None:
    if not name:
        raise ValueError("Mapper name must be non-empty")
    if not callable(fn):
        raise TypeError(f"Mapper '{name}' must be callable")

    try:
        sig = inspect.signature(fn)
        if len(sig.parameters) < 2:
            raise TypeError(f"Mapper '{name}' must accept (groups, delimiter)")
    except (ValueError, TypeError):
        pass

    canon = _norm(name)
    _MAPPERS[canon] = fn
    _ALIASES[canon] = canon

    for a in aliases:
        _ALIASES[_norm(a)] = canon


def normalize_type(name: str) -> str:
    if not name:
        raise ValueError("csv type must be a non-empty string")
    key = _norm(name)
    return _ALIASES.get(key, key)


def list_types() -> list[str]:
    return sorted(_MAPPERS.keys())


def get_mapper(name: str) -> Mapper:
    canon = normalize_type(name)
    try:
        return _MAPPERS[canon]
    except KeyError as e:
        raise KeyError(f"Unknown csv type '{name}'. Known: {', '.join(list_types())}") from e


# ---- built-in registrations ----

register_mapper(
    "tpm",
    convert_to_map_tpm,
    aliases=("tpm-perf", "tpm-performance"),
)

register_mapper(
    "jcperf",
    convert_to_map_jcperf,
    aliases=("perf", "performance", "javacard-performance", "javacard-perf"),
)

register_mapper(
    "jcaid",
    convert_to_map_aid,
    aliases=("aid", "javacard-aid"),
)

register_mapper(
    "jcalgsupport",
    convert_to_map_jcalgsupport,
    aliases=("jcalg", "javacard-alg-support", "jcsupport"),
)