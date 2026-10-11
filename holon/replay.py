"""Fold replay/M0/report.json into the result records deterministically (P5).

replay.status per law: "failed" if any side failed; else "passed" if any side
passed; else "not_applicable" if every side is not_applicable/not_run with at
least one not_applicable; else "not_run". Laws absent from the report keep
{"status": "not_run"}.
"""
from __future__ import annotations

import json
from pathlib import Path

from .facts import DEFAULT_FACTS, ROOT, load_facts


def _side_status(entry: dict) -> str:
    s = entry.get("status")
    if s not in ("passed", "failed", "not_applicable", "not_run"):
        raise ValueError(f"unknown replay side status {s!r}")
    return s


def aggregate(sides: dict) -> str:
    statuses = [_side_status(e) for _, e in sorted(sides.items())]
    if "failed" in statuses:
        return "failed"
    if "passed" in statuses:
        return "passed"
    if "not_applicable" in statuses:
        return "not_applicable"
    return "not_run"


def apply_replay(out_dir: Path, report_path: Path, root: Path, milestone: str) -> dict:
    """Rewrite `replay` in out_dir/<law>.json from the report; returns {law: status}."""
    report = json.loads(Path(report_path).read_text())
    facts = load_facts(root / DEFAULT_FACTS)
    want_commit = facts["target"]["commit"]
    if not str(report.get("morph_commit", "")).startswith(want_commit):
        raise SystemExit(
            f"replay report morph_commit {report.get('morph_commit')!r} does not start "
            f"with the facts target commit {want_commit!r}")
    try:
        rel_report = str(Path(report_path).resolve().relative_to(root.resolve()))
    except ValueError:
        rel_report = str(report_path)
    updated = {}
    for lid in sorted(report.get("laws", {})):
        rec_path = out_dir / f"{lid}.json"
        if not rec_path.is_file():
            raise SystemExit(f"replay report names {lid}, but {rec_path} does not exist")
        sides = report["laws"][lid]
        status = aggregate(sides)
        detail = ", ".join(f"{side}: {_side_status(sides[side])}" for side in sorted(sides))
        rec = json.loads(rec_path.read_text())
        rec["replay"] = {"status": status, "detail": f"{detail} ({rel_report})"}
        rec_path.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
        updated[lid] = status
    return updated


def main(args) -> int:
    root = Path.cwd() if (Path.cwd() / "laws").is_dir() else ROOT
    milestone = args.milestone
    out_dir = Path(args.out) if getattr(args, "out", None) else root / "results" / milestone
    report_path = Path(args.report) if args.report else root / "replay" / milestone / "report.json"
    if not report_path.is_file():
        raise SystemExit(f"replay report not found: {report_path}")
    updated = apply_replay(out_dir, report_path, root, milestone)
    for lid, s in sorted(updated.items()):
        print(f"{lid}: replay={s}")
    return 0
