# scrutiny-viz/tests/test_reporting.py
from scrutiny.reporting.reporting import compute_severity, _tally_stats, _normalize_pairs

# compute_severity: returns MATCH when there are zero changes (regardless of thresholds).
def test_compute_severity_match_when_no_changes():
    assert compute_severity({"threshold_ratio": 0.1}, changed=0, compared=10) == "MATCH"
    assert compute_severity({"threshold_count": 3}, changed=0, compared=10) == "MATCH"
    assert compute_severity({}, changed=0, compared=10) == "MATCH"


# compute_severity: ratio threshold yields WARN below threshold and SUSPICIOUS at/above it.
def test_compute_severity_ratio_threshold_warn_vs_suspicious():
    meta = {"threshold_ratio": 0.2}
    assert compute_severity(meta, changed=1, compared=10) == "WARN"        # 0.1 < 0.2
    assert compute_severity(meta, changed=2, compared=10) == "SUSPICIOUS"  # 0.2 >= 0.2
    assert compute_severity(meta, changed=3, compared=10) == "SUSPICIOUS"  # 0.3 >= 0.2


# compute_severity: if ratio is valid, it takes precedence and threshold_count is ignored.
def test_compute_severity_ratio_precedence_over_count():
    meta = {"threshold_ratio": 0.5, "threshold_count": 1}
    assert compute_severity(meta, changed=1, compared=10) == "WARN"        # ratio 0.1 < 0.5
    assert compute_severity(meta, changed=6, compared=10) == "SUSPICIOUS"  # ratio 0.6 >= 0.5


# compute_severity: uses threshold_count only when threshold_ratio is missing or invalid.
def test_compute_severity_count_only_when_ratio_missing_or_invalid():
    meta = {"threshold_count": 5}
    assert compute_severity(meta, changed=1, compared=10) == "WARN"
    assert compute_severity(meta, changed=4, compared=10) == "WARN"
    assert compute_severity(meta, changed=5, compared=10) == "SUSPICIOUS"

    meta2 = {"threshold_ratio": "not-a-number", "threshold_count": 2}
    assert compute_severity(meta2, changed=1, compared=10) == "WARN"
    assert compute_severity(meta2, changed=2, compared=10) == "SUSPICIOUS"


# compute_severity: threshold_count <= 0 is treated as disabled (so any change => WARN when no valid ratio).
def test_compute_severity_threshold_count_zero_disabled():
    meta = {"threshold_count": 0}
    assert compute_severity(meta, changed=1, compared=10) == "WARN"


# _tally_stats: counts presence diffs into only_ref/only_test and other diffs into changed; compared is the sum.
def test_tally_stats_presence_diffs_and_changed():
    diffs = [
        {"key": "a", "field": "__presence__", "ref": True,  "test": False},  # only_ref
        {"key": "b", "field": "__presence__", "ref": False, "test": True},   # only_test
        {"key": "c", "field": "avg_ms", "ref": 1, "test": 2},                # changed
    ]
    matches = [{"key": "m1"}, {"key": "m2"}]
    stats = _tally_stats(diffs, matches)

    assert stats["only_ref"] == 1
    assert stats["only_test"] == 1
    assert stats["changed"] == 1
    assert stats["matched"] == 2
    assert stats["compared"] == 1 + 2 + 1 + 1  # changed + matched + only_ref + only_test


# _normalize_pairs: numeric values are scaled to [0,1] by dividing by the max raw value across ref+test.
def test_normalize_pairs_numeric_scales_to_max():
    pairs = [
        {"key": "x", "ref_raw": 10.0, "test_raw": 20.0, "kind": "numeric"},
        {"key": "y", "ref_raw": 5.0,  "test_raw": 0.0,  "kind": "numeric"},
    ]
    out = _normalize_pairs(pairs)

    by_key = {p["key"]: p for p in out}
    assert abs(by_key["x"]["ref_score"] - 0.5) < 1e-9
    assert abs(by_key["x"]["test_score"] - 1.0) < 1e-9
    assert abs(by_key["y"]["ref_score"] - 0.25) < 1e-9
    assert abs(by_key["y"]["test_score"] - 0.0) < 1e-9
