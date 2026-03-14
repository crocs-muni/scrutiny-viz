# scrutiny-viz/mapper/tpm_parser.py
from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from .mapper_utils import (
        parse_name_value_attributes,
        parse_colon_pairs_line,
        parse_kv_pairs,
        compact_config,
        to_int,
        to_float,
    )
except ImportError:
    from mapper_utils import (
        parse_name_value_attributes,
        parse_colon_pairs_line,
        parse_kv_pairs,
        compact_config,
        to_int,
        to_float,
    )

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
    s = (line or "").strip()
    return s.startswith("TPM2_") and ";" not in s


def parse_group_as_record(group: list[str], delimiter: str, op: str) -> Optional[dict]:
    if not group:
        return None

    cfg = parse_colon_pairs_line(group[0], delimiter)
    stats: dict[str, str] = {}
    info: dict[str, str] = {}

    for line in group[1:]:
        s = (line or "").strip()
        if not s:
            continue
        parts = s.split(delimiter)
        head = (parts[0] or "").strip().lower()
        if head.startswith("operation stats"):
            stats.update(parse_kv_pairs(parts, start=1))
        elif head.startswith("operation info"):
            info.update(parse_kv_pairs(parts, start=1))

    keys = TPM_CONFIG_KEYS.get(op, list(cfg.keys()))
    measurement_config = compact_config(cfg, keys)

    dlen = to_int(cfg.get("Data length (bytes)")) or to_int(info.get("data length"))
    avg = to_float(stats.get("avg op")) or to_float(stats.get("avg"))
    mn = to_float(stats.get("min op")) or to_float(stats.get("min"))
    mx = to_float(stats.get("max op")) or to_float(stats.get("max"))

    rec: dict[str, Any] = {
        "algorithm": op + (f"|{measurement_config.replace(';', '|')}" if measurement_config else ""),
        "op_name": op,
    }
    if measurement_config:
        rec["measurement_config"] = measurement_config
    if dlen is not None:
        rec["data_length"] = dlen
    if avg is not None:
        rec["avg_ms"] = avg
    if mn is not None:
        rec["min_ms"] = mn
    if mx is not None:
        rec["max_ms"] = mx

    iters = to_int(info.get("total iterations"))
    inv = to_int(info.get("successful")) or to_int(info.get("total invocations"))
    if iters is not None:
        rec["total_iterations"] = iters
    if inv is not None:
        rec["total_invocations"] = inv

    err = (info.get("error") or "").strip()
    if err and err.lower() != "none":
        rec["error"] = err

    return rec


def convert_to_map_tpm(groups: list[list[str]], delimiter: str) -> dict:
    result: Dict[str, Any] = {"_type": "tpm-perf"}

    current_op: Optional[str] = None

    for i, group in enumerate(groups):
        if not group:
            continue

        first = (group[0] or "").strip()

        if i == 0:
            result[TPM_INFO] = parse_name_value_attributes(group, delimiter, allow_single_value=True)
            continue

        if is_tpm_op_header(first):
            current_op = first
            result.setdefault(current_op, [])
            continue

        if not current_op:
            continue

        rec = parse_group_as_record(group, delimiter, current_op)
        if rec:
            result[current_op].append(rec)

    return result