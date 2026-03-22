# scrutiny-viz/mapper/mappers/rsabias.py
from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Any

from .contracts import MapperPlugin, MapperSpec, MappingContext

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore

try:
    from .. import mapper_utils
except ImportError:
    import mapper_utils  # type: ignore


_RESULTS_RE = re.compile(r"^n_(\d+)_results\.json$", re.IGNORECASE)
_GROUP_HEADER_RE = re.compile(r"Group \[(\d+)\] is often missclassified as:", re.IGNORECASE)
_EDGE_RE = re.compile(r"group g\[(\d+)\] in ([0-9]+(?:\.[0-9]+)?)% cases", re.IGNORECASE)


class RSABiasMapper(MapperPlugin):
    spec = MapperSpec(
        name="rsabias",
        aliases=("rsa-bias", "rsabias-eval"),
        description="Map RSABias evaluation output directory into scrutiny-viz JSON.",
    )

    @property
    def accepts_directories(self) -> bool:
        return True

    def ingest(self, source_path: Path) -> dict[str, Any]:
        root = Path(source_path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"RSABias input path does not exist: {root}")
        if not root.is_dir():
            raise ValueError(f"RSABias mapper expects a directory, got: {root}")

        bucket_docs: dict[int, Any] = {}
        confusion_text: str | None = None
        confusion_matrix: Any | None = None

        for file_path in mapper_utils.list_files(root):
            m = _RESULTS_RE.match(file_path.name)
            if m:
                n_keys = int(m.group(1))
                doc = mapper_utils.read_json_file(file_path)
                if doc is not None:
                    bucket_docs[n_keys] = doc
                continue

            lower_name = file_path.name.lower()

            if lower_name == "confusion_matrix.txt":
                confusion_text = mapper_utils.read_text_file(file_path)
                continue

            if lower_name == "confusion_matrix.pkl":
                with open(file_path, "rb") as f:
                    confusion_matrix = pickle.load(f)
                continue

        return {
            "root": root,
            "bucket_docs": bucket_docs,
            "confusion_text": confusion_text,
            "confusion_matrix": confusion_matrix,
        }

    def map_groups(self, groups: list[list[str]], context: MappingContext) -> dict[str, Any]:
        raise TypeError("RSABias mapper does not support grouped text input; use a directory source.")

    def map_source(self, source: Any, context: MappingContext) -> dict[str, Any]:
        root: Path = source["root"]
        bucket_docs: dict[int, Any] = source["bucket_docs"]
        confusion_text: str | None = source.get("confusion_text")
        confusion_matrix = source.get("confusion_matrix")

        result: dict[str, Any] = {"_type": "rsabias"}

        result["META"] = [
            {"name": "source_dir", "value": root.name},
            {"name": "bucket_count", "value": str(len(bucket_docs))},
            {"name": "n_keys_available", "value": ",".join(str(k) for k in sorted(bucket_docs))},
            {"name": "has_confusion_summary", "value": "true" if confusion_text else "false"},
            {"name": "has_confusion_matrix", "value": "true" if confusion_matrix is not None else "false"},
        ]

        summary_rows: list[dict[str, Any]] = []

        for n_keys in sorted(bucket_docs):
            rows, summary = self._aggregate_accuracy(bucket_docs[n_keys])
            result[f"ACCURACY_N{n_keys}"] = rows

            summary_rows.append({"name": f"n{n_keys}_groups", "value": str(summary["groups"])})
            summary_rows.append({"name": f"n{n_keys}_correct", "value": str(summary["correct"])})
            summary_rows.append({"name": f"n{n_keys}_wrong", "value": str(summary["wrong"])})
            summary_rows.append({"name": f"n{n_keys}_total", "value": str(summary["total"])})
            summary_rows.append({"name": f"n{n_keys}_accuracy_pct", "value": f"{summary['accuracy_pct']:.4f}"})

        result["SUMMARY"] = summary_rows
        result["CONFUSION_TOP"] = self._parse_confusion_text(confusion_text) if confusion_text else []

        if confusion_matrix is not None:
            matrix_meta, matrix_cells = self._flatten_confusion_matrix(confusion_matrix)
            result["CONFUSION_MATRIX_META"] = matrix_meta
            result["CONFUSION_MATRIX_CELLS"] = matrix_cells

        return result

    def _aggregate_accuracy(self, doc: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        grouped: dict[str, dict[str, int]] = {}
        accuracies = doc.get("accuracies") or {}

        for _run_id, per_group in accuracies.items():
            if not isinstance(per_group, dict):
                continue
            for group_id, counts in per_group.items():
                if not isinstance(counts, dict):
                    continue
                acc = grouped.setdefault(str(group_id), {"correct": 0, "wrong": 0})
                acc["correct"] += int(counts.get("correct", 0) or 0)
                acc["wrong"] += int(counts.get("wrong", 0) or 0)

        rows: list[dict[str, Any]] = []
        total_correct = 0
        total_wrong = 0

        def _sort_key(group: str) -> tuple[int, str]:
            return (0, f"{int(group):09d}") if str(group).isdigit() else (1, str(group))

        for group_id in sorted(grouped.keys(), key=_sort_key):
            correct = grouped[group_id]["correct"]
            wrong = grouped[group_id]["wrong"]
            total = correct + wrong
            if total <= 0:
                continue

            accuracy_pct = (correct * 100.0 / total) if total else 0.0
            rows.append(
                {
                    "group": str(group_id),
                    "correct": correct,
                    "wrong": wrong,
                    "total": total,
                    "accuracy_pct": round(accuracy_pct, 4),
                }
            )
            total_correct += correct
            total_wrong += wrong

        grand_total = total_correct + total_wrong
        summary = {
            "groups": len(rows),
            "correct": total_correct,
            "wrong": total_wrong,
            "total": grand_total,
            "accuracy_pct": round((total_correct * 100.0 / grand_total), 4) if grand_total else 0.0,
        }
        return rows, summary

    def _parse_confusion_text(self, text: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        current_true: str | None = None

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            m_header = _GROUP_HEADER_RE.search(line)
            if m_header:
                current_true = m_header.group(1)
                continue

            m_edge = _EDGE_RE.search(line)
            if m_edge and current_true is not None:
                pred_group = m_edge.group(1)
                share_pct = float(m_edge.group(2))
                rows.append(
                    {
                        "edge_id": f"{current_true}->{pred_group}",
                        "true_group": str(current_true),
                        "pred_group": str(pred_group),
                        "share_pct": round(share_pct, 4),
                    }
                )

        return rows

    def _flatten_confusion_matrix(self, matrix: Any) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        if np is None:
            raise RuntimeError("numpy is required to process confusion_matrix.pkl")

        arr = np.asarray(matrix)
        if arr.ndim != 2:
            raise ValueError(f"Expected a 2D confusion matrix, got shape {arr.shape}")

        rows, cols = arr.shape
        out_rows: list[dict[str, Any]] = []
        finite_cells = 0
        nonzero_finite_cells = 0

        for row_idx in range(rows):
            for col_idx in range(cols):
                val = arr[row_idx, col_idx]
                if not np.isfinite(val):
                    continue

                finite_cells += 1
                fval = float(val)
                if abs(fval) > 1e-12:
                    nonzero_finite_cells += 1

                out_rows.append(
                    {
                        "cell_id": f"{row_idx}:{col_idx}",
                        "row_index": row_idx,
                        "col_index": col_idx,
                        "row_label": str(row_idx),
                        "col_label": str(col_idx),
                        "value": round(fval, 8),
                        "is_diagonal": row_idx == col_idx,
                    }
                )

        meta = [
            {"name": "rows", "value": str(rows)},
            {"name": "cols", "value": str(cols)},
            {"name": "finite_cells", "value": str(finite_cells)},
            {"name": "nonzero_finite_cells", "value": str(nonzero_finite_cells)},
            {"name": "labels_mode", "value": "matrix_index"},
        ]
        return meta, out_rows


PLUGIN = RSABiasMapper()
PLUGINS = [PLUGIN]