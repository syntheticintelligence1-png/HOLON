"""CLI entry point for HOLON evaluation corpus and control obligations (`python3 -m holon.eval`)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from holon.eval import (
    ROOT,
    build_evaluation_report,
    materialize_controls,
    materialize_corpus,
    verify_git_provenance,
    write_evaluation_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize and verify I48 evaluation corpus and controls.")
    parser.add_argument(
        "command",
        nargs="?",
        default="build",
        choices=("build", "verify", "check"),
        help="Subcommand: 'build' (default) materializes and writes report; 'verify'/'check' verifies existing artifacts.",
    )
    parser.add_argument("--root", default=str(ROOT), help="Repository root.")
    parser.add_argument("--cache-dir", default="/tmp/holon-corpus-cache", help="Git bare repository cache directory.")
    parser.add_argument("--skip-materialize", action="store_true", help="Skip re-materializing spec/eval artifacts.")
    parser.add_argument("--check", action="store_true", help="Verify existing artifacts and report determinism without overwriting.")
    args = parser.parse_args(argv)

    base_root = Path(args.root)
    cache_dir = Path(args.cache_dir)
    check_only = args.check or args.command in ("verify", "check")

    if check_only:
        verify_git_provenance(cache_dir=cache_dir, root=base_root)
        report = build_evaluation_report(root=base_root)
        expected_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        report_path = base_root / "results" / "eval" / "I48_corpus_controls.json"
        if not report_path.is_file():
            raise FileNotFoundError(f"missing evaluation report: {report_path}")
        actual_text = report_path.read_text(encoding="utf-8")
        if actual_text != expected_text:
            raise ValueError(f"evaluation report mismatch in {report_path}")
        return 0

    if not args.skip_materialize:
        materialize_corpus(cache_dir=cache_dir, root=base_root)
        materialize_controls(root=base_root)

    verify_git_provenance(cache_dir=cache_dir, root=base_root)
    write_evaluation_report(root=base_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
