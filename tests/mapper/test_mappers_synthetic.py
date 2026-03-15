# scrutiny-viz/tests/mapper/test_mappers_synthetic.py
from __future__ import annotations

from mapper.mappers.jcperf import convert_to_map_jcperf, END_OF_BASIC_INFO as JC_PERF_END
from mapper.mappers.tpm import convert_to_map_tpm
from mapper.mappers.jcaid import convert_to_map_aid
from mapper.mappers.jcalg_support import convert_to_map_jcalgsupport


def test_jcperf_parser_synthetic_minimal():
    groups = [
        ["Some header;1", JC_PERF_END],
        [
            "MESSAGE DIGEST",
            "method name:;ALG_SHA MessageDigest_doFinal()",
            "operation stats (ms/op):;avg op:;1.0;min op:;0.9;max op:;1.1",
            "operation info:;data length;256;total iterations;1;total invocations;1",
            "MESSAGE DIGEST - END",
        ],
    ]
    out = convert_to_map_jcperf(groups, ";")
    assert isinstance(out, dict)
    assert out.get("_type") == "jcperf"
    assert "MESSAGE_DIGEST" in out
    assert len(out["MESSAGE_DIGEST"]) == 1
    rec = out["MESSAGE_DIGEST"][0]
    assert rec["algorithm"].startswith("ALG_SHA")
    assert "avg_ms" in rec


def test_tpm_parser_synthetic_minimal():
    groups = [
        ["TPM_VENDOR;ExampleVendor", "TPM_FIRMWARE;1.0"],
        ["TPM2_Sign"],
        [
            "Key:;RSA 2048;Scheme:;RSASSA",
            "operation stats (ms/op):;avg op:;10.0;min op:;9.5;max op:;10.5",
            "operation info:;total iterations;1;successful;1;failed;0;error;none",
        ],
    ]
    out = convert_to_map_tpm(groups, ";")
    assert isinstance(out, dict)
    assert out.get("_type") == "tpm-perf"
    assert "TPM_INFO" in out
    assert "TPM2_Sign" in out
    assert len(out["TPM2_Sign"]) == 1
    assert "avg_ms" in out["TPM2_Sign"][0]


def test_jcaid_parser_synthetic_minimal():
    groups = [
        ["***** Card info", "CARD;ExampleCard", "JavaCard;3.0.5"],
        ["***** KEY INFO", "VER;255 ID;1 TYPE;DES3 LEN;16", "Some note"],
        ["PACKAGE AID;", "a0000000620101;1;0;java/lang;3.0.5"],
        ["FULL PACKAGE AID;", "a0000000620101;yes;java/lang 1.0"],
    ]
    out = convert_to_map_aid(groups, ";")
    assert isinstance(out, dict)
    assert out.get("_type") == "javacard-aid"
    assert "Package AID" in out
    assert out["Package AID"][0]["package_key"].startswith("a0000000620101:")
    assert "Full package AID support" in out


def test_jcalgsupport_parser_synthetic_minimal():
    groups = [
        ["Card name;Example Card", "JavaCard support version;3.0.5"],
        ["Cipher", "Cipher;ALG_DES_CBC_NOPAD;yes"],
    ]
    out = convert_to_map_jcalgsupport(groups, ";")
    assert isinstance(out, dict)
    assert out.get("_type") == "javacard-alg-support"
    assert "Basic information" in out
    assert "Cipher" in out
    assert out["Cipher"][0]["algorithm_name"] == "ALG_DES_CBC_NOPAD"
