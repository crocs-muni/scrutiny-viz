# scrutiny-viz/mapper/jcperf_parser.py
from __future__ import annotations

from typing import Any, Dict, Optional
from mapper_utils import to_int, to_float, parse_kv_pairs, flush_block

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
    s = (line or "").strip()
    if s.endswith(" - variable data - BEGIN"):
        s = s[: -len(" - variable data - BEGIN")]
    return s.strip()


def is_section_begin(line: str) -> bool:
    name = section_name(line)
    return name in SECTION_MARKERS or name in KEY_SECTIONS


def section_key(line: str) -> str:
    name = section_name(line)
    if name in KEY_SECTIONS:
        return name
    return name.replace(" ", "_")


def is_section_end(line: str) -> bool:
    return " - END" in (line or "")


def is_method(line: str) -> bool:
    return (line or "").startswith("method name:")


def parse_method_block(lines: list[str], delimiter: str) -> Optional[dict]:
    method_name: Optional[str] = None
    method_dlen: Optional[int] = None
    measurement_config: Optional[str] = None

    stats: dict[str, float] = {}
    info: dict[str, int] = {}
    no_such = False

    for raw in lines:
        s = (raw or "").strip()
        if not s:
            continue

        if s.startswith("method name:"):
            parts = s.split(delimiter)
            if len(parts) > 1:
                method_name = parts[1].strip()
            if len(parts) > 2 and parts[2].strip().isdigit():
                method_dlen = int(parts[2].strip())
            continue

        if s.startswith("measurement config:"):
            parts = [p.strip() for p in s.split(delimiter)[1:] if p.strip()]
            measurement_config = delimiter.join(parts)
            continue

        if s == "NO_SUCH_ALGORITHM":
            no_such = True
            continue

        if s.startswith("operation stats"):
            parts = s.split(delimiter)
            kv = parse_kv_pairs(parts, start=1)
            avg = to_float(kv.get("avg op"))
            mn = to_float(kv.get("min op"))
            mx = to_float(kv.get("max op"))
            if avg is not None:
                stats["avg_ms"] = avg
            if mn is not None:
                stats["min_ms"] = mn
            if mx is not None:
                stats["max_ms"] = mx
            continue

        if s.startswith("operation info:"):
            parts = s.split(delimiter)
            kv = parse_kv_pairs(parts, start=1)
            dlen = to_int(kv.get("data length"))
            iters = to_int(kv.get("total iterations"))
            inv = to_int(kv.get("total invocations"))
            if dlen is not None:
                info["data_length"] = dlen
            if iters is not None:
                info["total_iterations"] = iters
            if inv is not None:
                info["total_invocations"] = inv
            continue

    if not method_name:
        return None

    rec: dict[str, Any] = {"algorithm": method_name, "op_name": method_name}
    if measurement_config:
        rec["measurement_config"] = measurement_config

    if no_such:
        rec["error"] = "NO_SUCH_ALGORITHM"
        return rec

    rec.update(stats)

    if "data_length" in info:
        rec["data_length"] = info["data_length"]
    elif method_dlen is not None:
        rec["data_length"] = method_dlen

    if "total_iterations" in info:
        rec["total_iterations"] = info["total_iterations"]
    if "total_invocations" in info:
        rec["total_invocations"] = info["total_invocations"]

    return rec


def convert_to_map_jcperf(groups: list[list[str]], delimiter: str) -> dict:
    result: Dict[str, Any] = {"_type": "jcperf"}

    start = 0
    for i, group in enumerate(groups):
        if any(END_OF_BASIC_INFO in (ln or "") for ln in group):
            start = i + 1
            break

    current_section: Optional[str] = None
    current_lines: list[str] = []

    for i in range(start, len(groups)):
        for line in groups[i]:
            s = (line or "").strip()
            if not s:
                continue

            if is_section_begin(s):
                current_lines = flush_block(result, current_section, current_lines, parse_method_block, delimiter)
                current_section = section_key(s)
                result.setdefault(current_section, [])
                continue

            if is_section_end(s):
                current_lines = flush_block(result, current_section, current_lines, parse_method_block, delimiter)
                continue

            if is_method(s):
                current_lines = flush_block(result, current_section, current_lines, parse_method_block, delimiter)
                current_lines = [s]
                continue

            if current_section:
                current_lines.append(s)

    current_lines = flush_block(result, current_section, current_lines, parse_method_block, delimiter)
    return result