from __future__ import annotations

from tests.mapper.helpers import iter_bucket_csvs, run_mapper


def _payload():
    csvs = iter_bucket_csvs("jcAlgSupport")
    assert csvs, "No jcAlgSupport CSV fixtures found"
    return run_mapper(csvs[0], mapper_type="jcalgsupport")


def _algo_sections(payload: dict) -> list[str]:
    return [
        k for k in payload.keys()
        if k not in {"JCSystem", "CPLC"} and not str(k).startswith("_")
    ]


def test_jcalgsupport_mapper_emits_meta_and_algo_sections():
    payload = _payload()

    assert isinstance(payload, dict)
    assert "_META" in payload
    assert isinstance(payload["_META"], list)
    assert payload["_META"], "Expected non-empty _META"

    sections = _algo_sections(payload)
    assert sections, "Expected algorithm support sections"


def test_jcalgsupport_mapper_meta_rows_have_name_and_value():
    payload = _payload()

    rows = payload.get("_META", [])
    assert rows, "Expected _META rows"

    for row in rows:
        assert "name" in row, f"_META row missing name: {row}"
        assert "value" in row, f"_META row missing value: {row}"


def test_jcalgsupport_mapper_rows_have_algorithm_name_and_support_flag():
    payload = _payload()
    found = 0

    for section in _algo_sections(payload):
        rows = payload.get(section, [])
        for row in rows:
            if "algorithm_name" in row:
                assert "is_supported" in row, f"{section}: missing is_supported"
                found += 1

    assert found > 0, "Expected at least one algorithm support row"


def test_jcalgsupport_mapper_support_values_are_boolish_when_present():
    payload = _payload()
    checked = 0
    allowed = {"true", "false", "yes", "no", "supported", "unsupported", "1", "0"}

    for section in _algo_sections(payload):
        rows = payload.get(section, [])
        for row in rows:
            if "is_supported" in row:
                value = row["is_supported"]
                assert isinstance(value, bool) or str(value).strip().lower() in allowed, (
                    f"{section}: is_supported should be bool or bool-like, got {value!r}"
                )
                checked += 1

    assert checked > 0, "Expected at least one support value"

def test_jcalgsupport_mapper_reads_older_jcalgtest_format():
    from mapper.mapper_utils import prepare_lines
    from mapper.mappers.contracts import build_context
    from mapper.mappers.jcalg_support import PLUGIN

    text = """JavaCard support version;2.2.1;

javacardx.crypto.Cipher;
ALG_DES_CBC_NOPAD;yes;
ALG_DES_CBC_PKCS5;no;

javacard.security.KeyBuilder;
TYPE_DES_TRANSIENT_RESET;yes;

TYPE_DSA_PRIVATE LENGTH_DSA_512;no;

javacard\\.security\\.KeyAgreement
ALG_EC_SVDP_DH;no;
"""
    payload = PLUGIN.map_groups(prepare_lines(text.splitlines()), build_context())

    assert [r["algorithm_name"] for r in payload["javacardx.crypto.Cipher"]] == ["ALG_DES_CBC_NOPAD", "ALG_DES_CBC_PKCS5"]
    assert [r["algorithm_name"] for r in payload["javacard.security.KeyBuilder"]] == [
        "TYPE_DES_TRANSIENT_RESET",
        "TYPE_DSA_PRIVATE LENGTH_DSA_512",
    ]
    assert payload["javacard.security.KeyAgreement"] == [{"algorithm_name": "ALG_EC_SVDP_DH", "is_supported": "no"}]
    assert not {"javacardx", "javacard", "TYPE_DSA_PRIVATE LENGTH_DSA_512"} & set(payload)
