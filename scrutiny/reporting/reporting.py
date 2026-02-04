# scrutiny-viz/scrutiny/reporting/reporting.py
from __future__ import annotations
from typing import Dict, Any, List
from scrutiny.interfaces import ContrastState

# --------------------------- enums & ordering ---------------------------

_STATE_TO_STR = {
    ContrastState.MATCH: "MATCH",
    ContrastState.WARN: "WARN",
    ContrastState.SUSPICIOUS: "SUSPICIOUS",
}
_ORDER = {"MATCH": 0, "WARN": 1, "SUSPICIOUS": 2}


def _state_to_str(x) -> str:
    if isinstance(x, ContrastState):
        return _STATE_TO_STR[x]
    if isinstance(x, str):
        up = x.upper()
        if up in _ORDER:
            return up
    return "WARN"


def _max_state(a: str, b: str) -> str:
    return a if _ORDER.get(a, 1) >= _ORDER.get(b, 1) else b


# --------------------------- severity policy ---------------------------

def compute_severity(meta: dict, changed: int, compared: int) -> str:
    """Return MATCH/WARN/SUSPICIOUS based on thresholds."""
    if compared == 0 or changed == 0:
        return "MATCH"

    thr_ratio = meta.get("threshold_ratio", None)
    thr_count = meta.get("threshold_count", None)

    if isinstance(thr_ratio, (int, float, str)):
        try:
            thr_ratio = float(thr_ratio)
        except Exception:
            thr_ratio = None
    if isinstance(thr_count, (int, float, str)):
        try:
            thr_count = int(thr_count)
        except Exception:
            thr_count = None

    if isinstance(thr_ratio, float) and 0 <= thr_ratio <= 1 and compared > 0:
        ratio = changed / float(compared)
        return "SUSPICIOUS" if ratio >= float(thr_ratio) else "WARN"

    if isinstance(thr_count, int) and thr_count > 0:
        return "SUSPICIOUS" if changed >= thr_count else "WARN"

    return "WARN"


# --------------------------- stats & thresholds ---------------------------

def _tally_stats(diffs: List[Dict[str, Any]], matches: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Infer stats from diffs/matches:
      - presence diffs (field == "__presence__") increment only_ref/only_test
      - all other diffs increment changed
      - matches length → matched
      - compared = changed + matched + only_ref + only_test
    """
    only_ref = 0
    only_test = 0
    changed = 0

    for d in diffs or []:
        fld = d.get("field")
        if fld == "__presence__":
            r = d.get("ref")
            t = d.get("test")
            if isinstance(r, bool) and isinstance(t, bool):
                if r and not t:
                    only_ref += 1
                elif t and not r:
                    only_test += 1
                else:
                    changed += 1
            else:
                changed += 1
        else:
            changed += 1

    matched = len(matches or [])
    compared = changed + matched + only_ref + only_test
    return {
        "compared": compared,
        "changed": changed,
        "matched": matched,
        "only_ref": only_ref,
        "only_test": only_test,
    }


def _merge_severity_meta(schema: Dict[str, Any], section_name: str, section_res: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge severity thresholds with precedence:
      1) schema.compare[section].severity
      2) schema.sections[section].severity
      3) section_res.report.severity
      4) section_res.severity
    """
    out: Dict[str, Any] = {}

    if isinstance(schema, dict):
        sec = schema.get(section_name, {}) or {}
        if isinstance(sec, dict):
            comp = sec.get("component", {}) or {}
            if isinstance(comp, dict):
                if comp.get("threshold_ratio") is not None:
                    out["threshold_ratio"] = comp.get("threshold_ratio")
                if comp.get("threshold_count") is not None:
                    out["threshold_count"] = comp.get("threshold_count")

    rep = section_res.get("report", {})
    if isinstance(rep, dict):
        sev = rep.get("severity", {})
        if isinstance(sev, dict):
            out.update(sev)

    sev2 = section_res.get("severity", {})
    if isinstance(sev2, dict):
        out.update(sev2)

    return out


# --------------------------- radar helpers (bool/int/float) ---------------------------

def _parse_boolish(v) -> float | None:
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return 1.0 if float(v) != 0.0 else 0.0
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("yes", "true", "1"):
            return 1.0
        if s in ("no", "false", "0"):
            return 0.0
    return None


def _parse_number(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except Exception:
            return None
    return None


def _collect_numeric_pairs_from_chart(chart_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in chart_rows or []:
        key = str(r.get("key", ""))
        ref_raw = _parse_number(r.get("ref_avg"))
        tst_raw = _parse_number(r.get("test_avg"))
        if ref_raw is None and tst_raw is None:
            continue
        out.append({"key": key, "ref_raw": ref_raw, "test_raw": tst_raw, "kind": "numeric"})
    return out


def _collect_pairs_from_rows(diffs: List[Dict[str, Any]], matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fallback extraction (when no chart_rows):
      - Prefer explicit ref/test in diffs
      - For matches, use value for both ref/test (they match)
      - Parse as bool first; else numeric; else drop
    """
    buf: Dict[str, Dict[str, Any]] = {}
    for d in diffs or []:
        key = str(d.get("key", ""))
        buf.setdefault(key, {})
        buf[key]["ref_raw"] = buf[key].get("ref_raw", d.get("ref"))
        buf[key]["test_raw"] = buf[key].get("test_raw", d.get("test"))
    for m in matches or []:
        key = str(m.get("key", ""))
        v = m.get("value")
        buf.setdefault(key, {})
        buf[key].setdefault("ref_raw", v)
        buf[key].setdefault("test_raw", v)

    out: List[Dict[str, Any]] = []
    for key, payload in buf.items():
        ref_raw = payload.get("ref_raw")
        tst_raw = payload.get("test_raw")

        rb = _parse_boolish(ref_raw)
        tb = _parse_boolish(tst_raw)
        if rb is not None or tb is not None:
            out.append({
                "key": key,
                "ref_raw": rb if rb is not None else 0.0,
                "test_raw": tb if tb is not None else 0.0,
                "kind": "bool",
            })
            continue

        rn = _parse_number(ref_raw)
        tn = _parse_number(tst_raw)
        if rn is None and tn is None:
            continue
        out.append({
            "key": key,
            "ref_raw": rn if rn is not None else 0.0,
            "test_raw": tn if tn is not None else 0.0,
            "kind": "numeric",
        })
    return out


def _normalize_pairs(pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Produce ref_score/test_score in [0,1], preserve raw values and kind.
      - bool: already 0/1
      - numeric: divide by max of all raw (across ref+test)
    """
    if not pairs:
        return []

    maxv = 0.0
    for p in pairs:
        if p.get("kind") == "numeric":
            for k in ("ref_raw", "test_raw"):
                v = p.get(k)
                if isinstance(v, (int, float)) and float(v) > maxv:
                    maxv = float(v)
    if maxv <= 0:
        maxv = 1.0

    out: List[Dict[str, Any]] = []
    for p in pairs:
        kind = p.get("kind", "numeric")
        rr = float(p.get("ref_raw") or 0.0)
        tr = float(p.get("test_raw") or 0.0)
        if kind == "bool":
            ref_score = 1.0 if rr >= 0.5 else 0.0
            test_score = 1.0 if tr >= 0.5 else 0.0
        else:
            ref_score = rr / maxv
            test_score = tr / maxv
        out.append({
            "key": str(p.get("key", "")),
            "ref_score": ref_score,
            "test_score": test_score,
            "ref_raw": rr,
            "test_raw": tr,
            "kind": kind,
        })
    return out


# --------------------------- report config helpers ---------------------------

def _normalize_types_from_schema(explicit_types: Any) -> List[Dict[str, Any]]:
    """SchemaLoader should already normalize this, but keep it defensive."""
    if explicit_types is None:
        return []
    out: List[Dict[str, Any]] = []
    if isinstance(explicit_types, list):
        for t in explicit_types:
            if isinstance(t, str):
                s = t.strip().lower()
                if s:
                    out.append({"type": s, "variant": None})
            elif isinstance(t, dict):
                tp = str(t.get("type") or "").strip().lower()
                if not tp:
                    continue
                v = t.get("variant")
                v = str(v).strip().lower() if v is not None and str(v).strip() else None
                out.append({"type": tp, "variant": v})
    elif isinstance(explicit_types, str):
        for x in explicit_types.split(","):
            s = x.strip().lower()
            if s:
                out.append({"type": s, "variant": None})
    return out


def _pick_global_theme(schema: Dict[str, Any]) -> str:
    """Find first non-null report.theme in schema, else 'light'."""
    if not isinstance(schema, dict):
        return "light"
    for _name, sec in schema.items():
        if not isinstance(sec, dict):
            continue
        rep = sec.get("report") or {}
        if isinstance(rep, dict):
            t = rep.get("theme")
            if isinstance(t, str) and t.strip():
                tt = t.strip().lower()
                if tt in {"light", "dark"}:
                    return tt
    return "light"


# --------------------------- main entrypoint ---------------------------

def assemble_report(
    *,
    schema: Dict[str, Any],
    compare_results: Dict[str, Dict[str, Any]],
    reference_name: str,
    profile_name: str,
    section_rows: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build the normalized report JSON used by the HTML layer."""

    sections_out: Dict[str, Any] = {}
    overall = "MATCH"

    overall_counts = {"MATCH": 0, "WARN": 0, "SUSPICIOUS": 0}
    by_section: Dict[str, Dict[str, int]] = {}

    theme = _pick_global_theme(schema)

    for name, res in (compare_results or {}).items():
        diffs = res.get("diffs", []) or []
        matches = res.get("matches", []) or []

        # Promote artifacts.chart_rows -> chart_rows
        artifacts = res.get("artifacts", {}) or {}
        chart_rows = res.get("chart_rows")
        if chart_rows is None:
            chart_rows = artifacts.get("chart_rows", []) or []
        if not isinstance(chart_rows, list):
            chart_rows = []

        # Stats
        provided_stats = res.get("stats")
        if isinstance(provided_stats, dict):
            stats = {
                "compared": int(provided_stats.get("compared", 0) or 0),
                "changed": int(provided_stats.get("changed", 0) or 0),
                "matched": int(provided_stats.get("matched", 0) or 0),
                "only_ref": int(provided_stats.get("only_ref", 0) or 0),
                "only_test": int(provided_stats.get("only_test", 0) or 0),
            }
            if stats["compared"] == 0 and (diffs or matches):
                stats = _tally_stats(diffs, matches)
        else:
            stats = _tally_stats(diffs, matches)

        # Severity
        sev_meta = _merge_severity_meta(schema, name, res)
        result = compute_severity(sev_meta, stats["changed"], stats["compared"])

        overall_counts[result] = overall_counts.get(result, 0) + 1
        by_section[name] = {
            "MATCH": 1 if result == "MATCH" else 0,
            "WARN": 1 if result == "WARN" else 0,
            "SUSPICIOUS": 1 if result == "SUSPICIOUS" else 0,
            "TOTAL": 1,
        }

        pairs = _collect_numeric_pairs_from_chart(chart_rows)
        if not pairs:
            pairs = _collect_pairs_from_rows(diffs, matches)
        radar_rows = _normalize_pairs(pairs)

        # -------------------- Report config (STRICTLY from schema) --------------------
        schema_sec = (schema.get(name, {}) or {}) if isinstance(schema, dict) else {}
        schema_rep = dict(schema_sec.get("report", {}) or {})

        # Allow comparator to override *non-type* report fields if needed
        res_rep = dict(res.get("report") or {})
        rep_cfg = {**schema_rep, **res_rep}

        explicit_types = schema_rep.get("types", None)
        rep_cfg["types"] = _normalize_types_from_schema(explicit_types)

        if "doc_text" in schema_rep and schema_rep.get("doc_text"):
            rep_cfg["doc_text"] = schema_rep.get("doc_text")

        if rep_cfg.get("theme") is None:
            rep_cfg["theme"] = theme

        src_rows = None
        if isinstance(section_rows, dict):
            src_rows = section_rows.get(name)

        sections_out[name] = {
            "result": result,
            "stats": stats,
            "stats_display": dict(stats),
            "key_labels": res.get("key_labels") or res.get("labels") or {},
            "diffs": diffs,
            "matches": matches,
            "chart_rows": chart_rows,
            "radar_rows": radar_rows,
            "report": rep_cfg,
            **({"source_rows": src_rows} if src_rows is not None else {}),
        }

        overall = _max_state(overall, result)

    total_sections = sum(overall_counts.values())
    dashboard = {
        "overall_state_counts": {
            "MATCH": overall_counts.get("MATCH", 0),
            "WARN": overall_counts.get("WARN", 0),
            "SUSPICIOUS": overall_counts.get("SUSPICIOUS", 0),
            "TOTAL": total_sections,
        },
        "by_section": by_section,
    }

    return {
        "reference_name": reference_name,
        "profile_name": profile_name,
        "theme": theme,
        "overall": overall,
        "sections": sections_out,
        "dashboard": dashboard,
        "meta": {
            "generated_by": "assemble_report",
            "schema_title": schema.get("title") if isinstance(schema, dict) else None,
        },
    }
