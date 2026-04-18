# scrutiny-viz/mapper/mappers/jcaid.py
from __future__ import annotations

from typing import Any, Optional

try:
    from ..mapper_utils import flatten_groups, parse_name_value_attributes_filtered
except ImportError:  # pragma: no cover
    from mapper_utils import flatten_groups, parse_name_value_attributes_filtered

from .contracts import MapperPlugin, MapperSpec, MappingContext

META_KEY = "_META"

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
    return parse_name_value_attributes_filtered(
        lines,
        delimiter,
        allow_single_value=True,
        skip_prefixes=("*****", "http"),
        stop_prefixes=(SECTION_PACKAGE_AID, SECTION_FULL_PACKAGE_AID),
    )


def parse_key_info(lines: list[str]) -> dict[str, Any]:
    keys: list[dict[str, str]] = []
    notes: list[str] = []

    for line in lines:
        stripped = (line or "").strip()
        if not stripped:
            continue

        if stripped.startswith("VER;"):
            key_info: dict[str, str] = {}
            for pair in stripped.split(" "):
                if ";" not in pair:
                    continue

                parts = pair.split(";")
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if key:
                        key_info[key] = value

            if key_info:
                keys.append(key_info)
            continue

        notes.append(stripped)

    result: dict[str, Any] = {"keys": keys}
    if notes:
        result["notes"] = notes
    return result


def parse_package_aid_table(lines: list[str], delimiter: str) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    in_table = False

    for line in lines:
        stripped = (line or "").strip()
        if not stripped:
            continue

        if stripped.startswith(SECTION_PACKAGE_AID):
            in_table = True
            continue

        if stripped.startswith(SECTION_FULL_PACKAGE_AID) or stripped.startswith("*****"):
            break

        if not in_table:
            continue

        parts = [part.strip() for part in stripped.split(delimiter)]
        if len(parts) < 5:
            continue

        version = f"{parts[1]}.{parts[2]}"
        packages.append(
            {
                "package_aid": parts[0],
                "version": version,
                "package_name": parts[3],
                "package_key": f"{parts[0]}:{version}",
            }
        )

    return packages


def _normalize_aid(value: str) -> str:
    return "".join(char for char in (value or "") if char.lower() in "0123456789abcdef").lower()


def _looks_like_aid(value: str) -> bool:
    return len(_normalize_aid(value)) >= 8


def parse_full_package_aid_table(lines: list[str], delimiter: str) -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    in_table = False

    for line in lines:
        stripped = (line or "").strip()
        if not stripped:
            continue

        if stripped.startswith(SECTION_FULL_PACKAGE_AID):
            in_table = True
            continue

        if not in_table:
            continue

        parts = [part.strip() for part in stripped.split(delimiter)]
        if len(parts) < 3:
            continue

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


class JcAidMapper(MapperPlugin):
    spec = MapperSpec(
        name="jcaid",
        aliases=("aid", "javacard-aid"),
        description="JavaCard AID scan CSV mapper",
    )

    def map_groups(self, groups: list[list[str]], context: MappingContext) -> dict[str, Any]:
        result: dict[str, Any] = {"_type": "javacard-aid"}
        all_lines = flatten_groups(groups)

        basic_lines: list[str] = []
        key_lines: list[str] = []
        package_lines: list[str] = []
        full_package_lines: list[str] = []

        current_section = "basic"
        for line in all_lines:
            stripped = (line or "").strip()
            if not stripped:
                continue

            marker = is_section_marker(stripped)
            if marker:
                current_section = marker
                continue

            if current_section in {"basic", "card_info", "card_data"}:
                basic_lines.append(line)
            elif current_section == "key_info":
                key_lines.append(line)
            elif current_section == "package_aid":
                package_lines.append(line)
            elif current_section == "full_package_aid":
                full_package_lines.append(line)

        meta = parse_basic_info(basic_lines, context.delimiter)
        if meta:
            result[META_KEY] = meta

        if key_lines:
            result["_key_info"] = parse_key_info(key_lines)
        if package_lines:
            result["Package AID"] = parse_package_aid_table(
                [SECTION_PACKAGE_AID] + package_lines,
                context.delimiter,
            )
        if full_package_lines:
            result["Full package AID support"] = parse_full_package_aid_table(
                [SECTION_FULL_PACKAGE_AID] + full_package_lines,
                context.delimiter,
            )

        return result


PLUGIN = JcAidMapper()
PLUGINS = [PLUGIN]