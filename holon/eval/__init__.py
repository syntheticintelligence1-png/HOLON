"""Evaluation corpus, unsolved control obligations, and isomorphic renaming package."""
from __future__ import annotations

import json
from pathlib import Path

from holon.eval import rename
from holon.eval.controls import (
    compute_calibration,
    load_controls_manifest,
    materialize_controls,
    run_controls_evaluation,
)
from holon.eval.corpus import (
    load_corpus_manifest,
    materialize_corpus,
    verify_corpus,
    verify_git_provenance,
)

ROOT = Path(__file__).resolve().parents[2]


def build_evaluation_report(
    manifest_path: Path | str | None = None,
    controls_dir: Path | str | None = None,
    sidecar_path: Path | str | None = None,
    root: Path | str | None = None,
) -> dict:
    """Build deterministic evaluation report for §12 Limitations and §13 Evaluation."""
    base_root = Path(root or ROOT)
    s_path = Path(sidecar_path or (base_root / "spec" / "M4" / "lib" / "corpus_controls.json"))
    m_path = Path(manifest_path or (base_root / "spec" / "eval" / "corpus_manifest.json"))
    c_dir = Path(controls_dir or (base_root / "spec" / "eval" / "controls"))

    corpus_summary = verify_corpus(manifest_path=m_path, sidecar_path=s_path, root=base_root)
    controls_summary = run_controls_evaluation(
        controls_dir=c_dir, sidecar_path=s_path, root=base_root
    )

    limitations_table = [
        {
            "control_id": item["control_id"],
            "law_id": item["law_id"],
            "category": item["category"],
            "rule": item["rule"],
            "subform": item["subform"],
            "limitation_class": item["limitation_class"],
            "description": item["description"],
            "unassisted_status": item["unassisted_status"],
            "bound": item["bound"],
            "ground_truth_kind": item["ground_truth_kind"],
            "ground_truth_symbol": item["ground_truth_symbol"],
            "ground_truth_verified": item["ground_truth_verified"],
        }
        for item in controls_summary["controls"]
    ]

    return {
        "schema": "holon-eval-report/0.1",
        "iteration": "I48",
        "milestone": "M4",
        "corpus_summary": corpus_summary,
        "controls_summary": controls_summary,
        "calibration": controls_summary["calibration"],
        "limitations_table": limitations_table,
    }


def write_evaluation_report(
    out_path: Path | str | None = None,
    manifest_path: Path | str | None = None,
    controls_dir: Path | str | None = None,
    sidecar_path: Path | str | None = None,
    root: Path | str | None = None,
) -> dict:
    base_root = Path(root or ROOT)
    target_out = Path(out_path or (base_root / "results" / "eval" / "I48_corpus_controls.json"))
    report = build_evaluation_report(
        manifest_path=manifest_path,
        controls_dir=controls_dir,
        sidecar_path=sidecar_path,
        root=base_root,
    )
    target_out.parent.mkdir(parents=True, exist_ok=True)
    target_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


__all__ = [
    "build_evaluation_report",
    "compute_calibration",
    "load_corpus_manifest",
    "materialize_controls",
    "materialize_corpus",
    "rename",
    "run_controls_evaluation",
    "verify_corpus",
    "verify_git_provenance",
    "write_evaluation_report",
]
