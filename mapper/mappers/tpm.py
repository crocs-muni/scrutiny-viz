# scrutiny-viz/mapper/mappers/tpm.py
from __future__ import annotations

from typing import Any, Optional

try:
    from ..mapper_utils import (
        build_perf_record,
        compact_config,
        parse_colon_pairs_line,
        parse_kv_pairs,
        parse_name_value_attributes,
        to_float,
        to_int,
    )
except ImportError:  # pragma: no cover
    from mapper_utils import (
        build_perf_record,
        compact_config,
        parse_colon_pairs_line,
        parse_kv_pairs,
        parse_name_value_attributes,
        to_float,
        to_int,
    )

from .contracts import MapperPlugin, MapperSpec, MappingContext

TPM_INFO = "TPM_INFO"

TPM_CONFIG_KEYS: dict[str, list[str]] = {
    "TPM2_Create": ["Key parameters"],
    "TPM2_Sign": ["Key", "Scheme", "Key parameters"],
    "TPM2_VerifySignature": ["Key", "Scheme", "Key parameters"],
    "TPM2_RSA_Encrypt": ["Key", "Scheme"],
    "TPM2_RSA_Decrypt": ["Key", "Scheme"],
    "TPM2_EncryptDecrypt": ["Algorithm", "Key length", "Mode", "Dir", "Data length (bytes)"],
    "TPM2_Hash": ["Hash algorithm", "Data length (bytes)"],
    "TPM2_HMAC": ["Hash", "Data length (bytes)"],
    "TPM2_GetRandom": ["Data length (bytes)"],
}


def is_tpm_op_header(line: str) -> bool:
    stripped = (line or "").strip()
    return stripped.startswith("TPM2_") and ";" not in stripped


def parse_group_as_record(group: list[str], delimiter: str, op: str) -> Optional[dict[str, Any]]:
    if not group:
        return None

    cfg = parse_colon_pairs_line(group[0], delimiter)
    stats: dict[str, str] = {}
    info: dict[str, str] = {}

    for line in group[1:]:
        stripped = (line or "").strip()
        if not stripped:
            continue

        parts = stripped.split(delimiter)
        head = (parts[0] or "").strip().lower()
        if head.startswith("operation stats"):
            stats.update(parse_kv_pairs(parts, start=1))
        elif head.startswith("operation info"):
            info.update(parse_kv_pairs(parts, start=1))

    keys = TPM_CONFIG_KEYS.get(op, list(cfg.keys()))
    measurement_config = compact_config(cfg, keys)

    data_length = to_int(cfg.get("Data length (bytes)")) or to_int(info.get("data length"))
    avg_ms = to_float(stats.get("avg op")) or to_float(stats.get("avg"))
    min_ms = to_float(stats.get("min op")) or to_float(stats.get("min"))
    max_ms = to_float(stats.get("max op")) or to_float(stats.get("max"))
    total_iterations = to_int(info.get("total iterations"))
    total_invocations = to_int(info.get("successful")) or to_int(info.get("total invocations"))

    error = (info.get("error") or "").strip()
    if error.lower() == "none":
        error = ""

    algorithm = op + (f"|{measurement_config.replace(';', '|')}" if measurement_config else "")

    return build_perf_record(
        op_name=op,
        algorithm=algorithm,
        measurement_config=measurement_config,
        data_length=data_length,
        avg_ms=avg_ms,
        min_ms=min_ms,
        max_ms=max_ms,
        total_iterations=total_iterations,
        total_invocations=total_invocations,
        error=error or None,
    )


class TpmMapper(MapperPlugin):
    spec = MapperSpec(
        name="tpm",
        aliases=("tpm-perf", "tpm-performance"),
        description="TPM performance CSV mapper",
    )

    def map_groups(self, groups: list[list[str]], context: MappingContext) -> dict[str, Any]:
        result: dict[str, Any] = {"_type": "tpm-perf"}
        current_op: Optional[str] = None

        for index, group in enumerate(groups):
            if not group:
                continue

            first = (group[0] or "").strip()

            if index == 0:
                result[TPM_INFO] = parse_name_value_attributes(
                    group,
                    context.delimiter,
                    allow_single_value=True,
                )
                continue

            if is_tpm_op_header(first):
                current_op = first
                result.setdefault(current_op, [])
                continue

            if not current_op:
                continue

            rec = parse_group_as_record(group, context.delimiter, current_op)
            if rec:
                result[current_op].append(rec)

        return result


PLUGIN = TpmMapper()
PLUGINS = [PLUGIN]
