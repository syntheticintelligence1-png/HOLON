"""The term-size sidecar of BUILD_PLAN I46's run 2: spec/M3/lib/term_size.json as the blind session is given it beside
the scope set (spec/M3/amendments/I46.jsonl, line 7), cut to the members holon run reads.

    python tests_m3/blind_term_size.py [--root DIR] [--commit C] [--protocol FILE] --out DIR

FACT's decider (holon.fact.run.Decider) reads I30's term-size sidecar for its budget and for its measure
(holon.sorts.termsize.Measure: tokenizer, literal_list and placeholder). The pack leaves the sidecar out, and the
target code does not fix it. Its other members are prose, the measure's context, and measurements of the lead's own
laws. So:
  source   the blob spec/M3/lib/term_size.json of commit C;
  keep     the top-level members KEEP, in the source's order, with the source's values. Every other member is dropped,
           and a KEEP member that the source lacks is an error;
  check    the scope protocol's strip rules (blind_scope.strip, with the leak classes of tools/blind_pack.py's
           protocol at C) strip nothing from the output. The script exits 1 otherwise;
  output   DIR/files/spec/M3/lib/term_size.json: the kept document (JSON, indent 2, the source's member order, a final
           newline);
           DIR/dropped.json: {path: [dropped key paths]}, in document order.
Every byte comes from git objects of C, and nothing records a time or a machine path, so one commit gives the same
bytes. It imports nothing from holon/. It is an I46 instrument (amendment 7), beside blind_scope.py and
blind_ledger.py, and is never packed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blind_scope  # noqa: E402  (the scope set's strip rules and leak classes; imports nothing from holon/)

blind_pack = blind_scope.blind_pack
DEFAULT_ROOT = blind_scope.DEFAULT_ROOT
PROTOCOL = blind_scope.PROTOCOL
SIDECAR = "spec/M3/lib/term_size.json"
KEEP = ("term_size_version", "budget", "tokenizer", "literal_list", "placeholder")


class SidecarError(Exception):
    pass


def cut(root: Path, commit: str, protocol: dict) -> tuple[bytes, list[str], str]:
    """(the output bytes, the dropped key paths, the source sha256)."""
    src = blind_pack.show(root, commit, SIDECAR)
    doc = json.loads(src.decode("utf-8"))
    if not isinstance(doc, dict):
        raise SidecarError(f"{SIDECAR} at {commit[:8]} is not a JSON object")
    missing = [k for k in KEEP if k not in doc]
    if missing:
        raise SidecarError(f"{SIDECAR} at {commit[:8]} lacks {missing}")
    out = {k: v for k, v in doc.items() if k in KEEP}
    dropped = [k for k in doc if k not in KEEP]
    sc = protocol["scope"]
    _, removed = blind_scope.strip(out, re.compile(sc["strip_key_pattern"]), re.compile(sc["strip_hash_pattern"]),
                                   blind_scope.leak_patterns(root, commit))
    if removed:
        raise SidecarError(f"the strip rules would still strip {[r['key'] for r in removed]}")
    return (json.dumps(out, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), dropped, blind_scope.sha256(src)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="blind_term_size.py", description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="the repository (default: this checkout)")
    ap.add_argument("--commit", default="HEAD", help="the packed commit (default HEAD)")
    ap.add_argument("--protocol", type=Path, help=f"the protocol (default: {PROTOCOL} of the working tree)")
    ap.add_argument("--out", type=Path, required=True, help="the output directory (created; must be empty)")
    a = ap.parse_args(argv)
    try:
        commit = blind_pack.git(a.root, "rev-parse", "--verify", f"{a.commit}^{{commit}}").decode().strip()
        protocol = json.loads((a.protocol or (a.root / PROTOCOL)).read_bytes())
        out, dropped, src_sha = cut(a.root, commit, protocol)
    except SidecarError as e:
        print(f"blind_term_size: {e}", file=sys.stderr)
        return 1
    except (blind_pack.PackError, OSError, KeyError, ValueError) as e:
        print(f"blind_term_size: {e}", file=sys.stderr)
        return 2
    if a.out.exists() and any(a.out.iterdir()):
        print(f"blind_term_size: {a.out} is not empty", file=sys.stderr)
        return 2
    (a.out / "files" / SIDECAR).parent.mkdir(parents=True, exist_ok=True)
    (a.out / "files" / SIDECAR).write_bytes(out)
    (a.out / "dropped.json").write_text(blind_scope.dump({SIDECAR: dropped}), encoding="utf-8")
    print(f"blind_term_size: {SIDECAR} given with {len(KEEP)} members kept and {len(dropped)} dropped, {len(out)} bytes, "
          f"sha256 {blind_scope.sha256(out)} (source {src_sha[:12]}); the strip rules strip nothing; commit {commit[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
