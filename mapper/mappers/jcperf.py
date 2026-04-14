# scrutiny-viz/mapper/mappers/jcperf.py
from __future__ import annotations

from typing import Any, Optional

try:
    from ..mapper_utils import (
        build_perf_record,
        flush_block,
        parse_kv_pairs,
        parse_name_value_attributes_filtered,
        to_float,
        to_int,
    )
except ImportError:  # pragma: no cover
    from mapper_utils import (
        build_perf_record,
        flush_block,
        parse_kv_pairs,
        parse_name_value_attributes_filtered,
        to_float,
        to_int,
    )

from .contracts import MapperPlugin, MapperSpec, MappingContext

META_KEY = "_META"
END_OF_BASIC_INFO = "JCSystem.getVersion()"

SECTION_MARKERS = [
    "MESSAGE DIGEST",
    "RANDOM GENERATOR",
    "CIPHER",
    "SIGNATURE",
    "CHECKSUM",
    "UTIL",
    "SWALGS",
    "KEY PAIR",
    "KEYAGREEMENT",
]

KEY_SECTIONS = [
    "AESKey",
    "DESKey",
    "KoreanSEEDKey",
    "DSAPrivateKey",
    "DSAPublicKey",
    "ECF2MPublicKey",
    "ECF2MPrivateKey",
    "ECFPPublicKey",
    "ECFPPrivateKey",
    "HMACKey",
    "RSAPrivateCRTKey",
    "RSAPrivateKey",
    "RSAPublicKey",
]


def section_name(line: str) -> str:
    stripped = (line or "").strip()
    if stripped.endswith(" - variable data - BEGIN"):
        stripped = stripped[: -len(" - variable data - BEGIN")]
    return stripped.strip()


def is_section_begin(line: str) -> bool:
    return section_name(line) in SECTION_MARKERS or section_name(line) in KEY_SECTIONS


def section_key(line: str) -> str:
    name = section_name(line)
    return name if name in KEY_SECTIONS else name.replace(" ", "_")


def is_section_end(line: str) -> bool:
    return " - END" in (line or "")


def is_method(line: str) -> bool:
    return (line or "").startswith("method name:")


def _parse_method_line(line: str, delimiter: str) -> tuple[Optional[str], Optional[int]]:
    parts = line.split(delimiter)
    method_name = parts[1].strip() if len(parts) > 1 else None
    method_dlen = int(parts[2].strip()) if len(parts) > 2 and parts[2].strip().isdigit() else None
    return method_name, method_dlen


def parse_method_block(lines: list[str], delimiter: str) -> Optional[dict[str, Any]]:
    method_name: Optional[str] = None
    method_dlen: Optional[int] = None
    measurement_config: Optional[str] = None

    stats: dict[str, float] = {}
    info: dict[str, int] = {}
    no_such_algorithm = False

    for raw in lines:
        stripped = (raw or "").strip()
        if not stripped:
            continue

        if stripped.startswith("method name:"):
            method_name, method_dlen = _parse_method_line(stripped, delimiter)
            continue

        if stripped.startswith("measurement config:"):
            parts = [part.strip() for part in stripped.split(delimiter)[1:] if part.strip()]
            measurement_config = delimiter.join(parts)
            continue

        if stripped == "NO_SUCH_ALGORITHM":
            no_such_algorithm = True
            continue

        if stripped.startswith("operation stats"):
            kv = parse_kv_pairs(stripped.split(delimiter), start=1)
            avg = to_float(kv.get("avg op"))
            min_value = to_float(kv.get("min op"))
            max_value = to_float(kv.get("max op"))
            if avg is not None:
                stats["avg_ms"] = avg
            if min_value is not None:
                stats["min_ms"] = min_value
            if max_value is not None:
                stats["max_ms"] = max_value
            continue

        if stripped.startswith("operation info:"):
            kv = parse_kv_pairs(stripped.split(delimiter), start=1)
            data_length = to_int(kv.get("data length"))
            total_iterations = to_int(kv.get("total iterations"))
            total_invocations = to_int(kv.get("total invocations"))
            if data_length is not None:
                info["data_length"] = data_length
            if total_iterations is not None:
                info["total_iterations"] = total_iterations
            if total_invocations is not None:
                info["total_invocations"] = total_invocations

    if not method_name:
        return None

    if no_such_algorithm:
        return build_perf_record(
            op_name=method_name,
            algorithm=method_name,
            measurement_config=measurement_config,
            error="NO_SUCH_ALGORITHM",
        )

    return build_perf_record(
        op_name=method_name,
        algorithm=method_name,
        measurement_config=measurement_config,
        data_length=info.get("data_length", method_dlen),
        avg_ms=stats.get("avg_ms"),
        min_ms=stats.get("min_ms"),
        max_ms=stats.get("max_ms"),
        total_iterations=info.get("total_iterations"),
        total_invocations=info.get("total_invocations"),
    )


class JcPerfMapper(MapperPlugin):
    spec = MapperSpec(
        name="jcperf",
        aliases=("perf", "performance", "javacard-performance", "javacard-perf"),
        description="JavaCard performance CSV mapper",
    )

    def map_groups(self, groups: list[list[str]], context: MappingContext) -> dict[str, Any]:
        result: dict[str, Any] = {"_type": "jcperf"}

        start_index = 0
        meta_lines: list[str] = []
        found_boundary = False

        for index, group in enumerate(groups):
            for line in group:
                stripped = (line or "").strip()
                if not stripped:
                    continue
                if END_OF_BASIC_INFO in stripped:
                    start_index = index + 1
                    found_boundary = True
                    break
                meta_lines.append(stripped)
            if found_boundary:
                break

        if meta_lines:
            meta = parse_name_value_attributes_filtered(
                meta_lines,
                context.delimiter,
                allow_single_value=True,
            )
            if meta:
                result[META_KEY] = meta

        current_section: Optional[str] = None
        current_lines: list[str] = []

        for group in groups[start_index:]:
            for line in group:
                stripped = (line or "").strip()
                if not stripped:
                    continue

                if is_section_begin(stripped):
                    current_lines = flush_block(
                        result,
                        current_section,
                        current_lines,
                        parse_method_block,
                        context.delimiter,
                    )
                    current_section = section_key(stripped)
                    result.setdefault(current_section, [])
                    continue

                if is_section_end(stripped):
                    current_lines = flush_block(
                        result,
                        current_section,
                        current_lines,
                        parse_method_block,
                        context.delimiter,
                    )
                    continue

                if is_method(stripped):
                    current_lines = flush_block(
                        result,
                        current_section,
                        current_lines,
                        parse_method_block,
                        context.delimiter,
                    )
                    current_lines = [stripped]
                    continue

                if current_section:
                    current_lines.append(stripped)

        flush_block(result, current_section, current_lines, parse_method_block, context.delimiter)
        return result


PLUGIN = JcPerfMapper()
PLUGINS = [PLUGIN]
