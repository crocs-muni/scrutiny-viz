# scrutiny-viz/mapper/jcaid_parser.py
from __future__ import annotations

from typing import Optional, Any, Dict

from mapper_utils import create_attribute, flatten_groups

BASIC_INFO = "Basic information"

SECTION_CARD_INFO = "***** Card info"
SECTION_CARD_DATA = "***** CARD DATA"
SECTION_KEY_INFO = "***** KEY INFO"
SECTION_PACKAGE_AID = "PACKAGE AID;"
SECTION_FULL_PACKAGE_AID = "FULL PACKAGE AID;"


def is_section_marker(line: str) -> Optional[str]:
    stripped = (line or "").strip()
    if stripped.startswith(SECTION_CARD_INFO):
        return "card_info"
    if stripped.startswith(SECTION_CARD_DATA):
        return "card_data"
    if stripped.startswith(SECTION_KEY_INFO):
        return "key_info"
    if stripped.startswith(SECTION_PACKAGE_AID):
        return "package_aid"
    if stripped.startswith(SECTION_FULL_PACKAGE_AID):
        return "full_package_aid"
    return None


def parse_basic_info(lines: list[str], delimiter: str) -> list[dict]:
    attributes: list[dict] = []

    for line in lines:
        s = (line or "").strip()
        if not s or s.startswith("*****") or s.startswith("http"):
            continue

        # stop at tables
        if s.startswith(SECTION_PACKAGE_AID) or s.startswith(SECTION_FULL_PACKAGE_AID):
            break

        parts = s.split(delimiter)
        if len(parts) >= 2:
            name = parts[0].strip()
            value = parts[1].strip()
            if name:
                attributes.append(create_attribute(name, value))
        elif len(parts) == 1 and parts[0].strip():
            attributes.append(create_attribute(parts[0].strip(), ""))

    return attributes


def parse_key_info(lines: list[str]) -> dict:
    keys: list[dict] = []
    notes: list[str] = []

    for line in lines:
        s = (line or "").strip()
        if not s:
            continue

        if s.startswith("VER;"):
            key_info: dict[str, str] = {}
            pairs = s.split(" ")
            for pair in pairs:
                if ";" in pair:
                    parts = pair.split(";")
                    if len(parts) == 2:
                        key_info[parts[0].strip()] = parts[1].strip()
            if key_info:
                keys.append(key_info)
        else:
            notes.append(s)

    result: dict[str, Any] = {"keys": keys}
    if notes:
        result["notes"] = notes
    return result


def parse_package_aid_table(lines: list[str], delimiter: str) -> list[dict]:
    packages: list[dict] = []
    header_found = False

    for line in lines:
        s = (line or "").strip()
        if not s:
            continue

        if s.startswith(SECTION_PACKAGE_AID):
            header_found = True
            continue

        if s.startswith(SECTION_FULL_PACKAGE_AID) or s.startswith("*****"):
            break

        if header_found:
            parts = [p.strip() for p in s.split(delimiter)]
            if len(parts) >= 5:
                major = parts[1]
                minor = parts[2]
                version = f"{major}.{minor}"

                entry = {
                    "package_aid": parts[0],
                    "version": version,
                    "package_name": parts[3],
                    # unique match key for comparator / report
                    "package_key": f"{parts[0]}:{version}",
                }
                packages.append(entry)

    return packages


def _normalize_aid(s: str) -> str:
    """Remove spaces/colons and keep only hex chars."""
    return "".join(c for c in (s or "") if c.lower() in "0123456789abcdef").lower()


def _looks_like_aid(s: str) -> bool:
    norm = _normalize_aid(s)
    return len(norm) >= 8


def parse_full_package_aid_table(lines: list[str], delimiter: str) -> list[dict]:
    """
    FULL PACKAGE AID format (3 columns):
      full_package_aid;yes/no;package_name_version
    """
    packages: list[dict] = []
    header_found = False

    for line in lines:
        s = (line or "").strip()
        if not s:
            continue

        if s.startswith(SECTION_FULL_PACKAGE_AID):
            header_found = True
            continue

        if header_found:
            parts = [p.strip() for p in s.split(delimiter)]
            if len(parts) >= 3:
                if parts[0].upper().startswith("JC CONVERTOR VERSION"):
                    continue
                if parts[0] and not _looks_like_aid(parts[0]):
                    continue

                packages.append(
                    {
                        "full_package_aid": _normalize_aid(parts[0]),
                        "supported": parts[1].strip().lower() == "yes",
                        "package_name_version": parts[2],
                    }
                )

    return packages


def convert_to_map_aid(groups: list[list[str]], delimiter: str) -> dict:
    result: Dict[str, Any] = {"_type": "javacard-aid"}

    all_lines = flatten_groups(groups)

    basic_lines: list[str] = []
    key_lines: list[str] = []
    package_lines: list[str] = []
    full_package_lines: list[str] = []

    current = "basic"
    for line in all_lines:
        s = (line or "").strip()
        if not s:
            continue

        marker = is_section_marker(s)
        if marker:
            current = marker
            continue

        if current in {"basic", "card_info", "card_data"}:
            basic_lines.append(line)
        elif current == "key_info":
            key_lines.append(line)
        elif current == "package_aid":
            package_lines.append(line)
        elif current == "full_package_aid":
            full_package_lines.append(line)

    if key_lines:
        result["_key_info"] = parse_key_info(key_lines)

    result[BASIC_INFO] = parse_basic_info(basic_lines, delimiter)

    if package_lines:
        result["Package AID"] = parse_package_aid_table([SECTION_PACKAGE_AID] + package_lines, delimiter)

    if full_package_lines:
        result["Full package AID support"] = parse_full_package_aid_table(
            [SECTION_FULL_PACKAGE_AID] + full_package_lines, delimiter
        )

    return result


convert_to_map_jcaid = convert_to_map_aid