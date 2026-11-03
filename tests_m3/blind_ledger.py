"""The assumption ledger of BUILD_PLAN I46's run 2: spec/ledger/assumptions.json as the blind session is given it
beside the scope set (spec/M3/amendments/I46.jsonl, lines 3 and 4), with its free text blanked.

    python tests_m3/blind_ledger.py [--root DIR] [--commit C] [--protocol FILE] --out DIR

holon run reads the ledger (holon.records.load_ledger), and the pack leaves it out. Records are computed from its
structure only: each bundle's facts, facts_sha256 and model, each entry's id, introduced_by and requires, and each
no_assumption group's defs. Its free text is prose for people, and it carries leak-class matches and result-like
phrases. So:
  source   the blob spec/ledger/assumptions.json of commit C;
  blank    every member named "doc", "text" or "why" whose value is a string, at any depth, gets the value MARKER.
           The key stays. Every other member is kept as it is, and a doc, text or why that is not a string is an error;
  check    the scope protocol's strip rules (blind_scope.strip, with the leak classes of tools/blind_pack.py's
           protocol at C) strip nothing from the output, and the output less its blanked members equals the source less
           the same members. The script exits 1 when either check fails;
  output   DIR/files/spec/ledger/assumptions.json: the blanked document (JSON, indent 2, the source's member order, a
           final newline);
           DIR/blanked.json: {path: [blanked key paths]}, in document order.
A key path joins object keys and list indices with "/". Every byte comes from git objects of C, and nothing records a
time or a machine path, so one commit gives the same bytes. It imports nothing from holon/. It is an I46 instrument
(amendment 4), beside blind_scope.py, and is never packed.
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
LEDGER = "spec/ledger/assumptions.json"
FREE_TEXT = ("doc", "text", "why")
MARKER = "(withheld from the blind tree: free text; no record field is computed from it)"


class LedgerError(Exception):
    pass


def blank(x, at: str = "") -> tuple[object, list[str]]:
    """(x with every free-text string member set to MARKER, the blanked key paths in document order)."""
    if isinstance(x, dict):
        out, paths = {}, []
        for k, v in x.items():
            path = f"{at}/{k}" if at else str(k)
            if k in FREE_TEXT:
                if not isinstance(v, str):
                    raise LedgerError(f"{path} is free text by name but holds a {type(v).__name__}")
                out[k] = MARKER
                paths.append(path)
            else:
                out[k], sub = blank(v, path)
                paths += sub
        return out, paths
    if isinstance(x, list):
        out, paths = [], []
        for i, v in enumerate(x):
            o, sub = blank(v, f"{at}/{i}" if at else str(i))
            out.append(o)
            paths += sub
        return out, paths
    return x, []


def drop(x, paths: set[str], at: str = ""):
    """x less the members at paths."""
    if isinstance(x, dict):
        return {k: drop(v, paths, f"{at}/{k}" if at else str(k)) for k, v in x.items()
                if (f"{at}/{k}" if at else str(k)) not in paths}
    if isinstance(x, list):
        return [drop(v, paths, f"{at}/{i}" if at else str(i)) for i, v in enumerate(x)]
    return x


def ledger(root: Path, commit: str, protocol: dict) -> tuple[bytes, list[str], str]:
    """(the output bytes, the blanked key paths, the source sha256)."""
    src = blind_pack.show(root, commit, LEDGER)
    doc = json.loads(src.decode("utf-8"))
    if not isinstance(doc, dict):
        raise LedgerError(f"{LEDGER} at {commit[:8]} is not a JSON object")
    out, paths = blank(doc)
    sc = protocol["scope"]
    _, removed = blind_scope.strip(out, re.compile(sc["strip_key_pattern"]), re.compile(sc["strip_hash_pattern"]),
                                   blind_scope.leak_patterns(root, commit))
    if removed:
        raise LedgerError(f"the strip rules would still strip {[r['key'] for r in removed]}")
    if drop(out, set(paths)) != drop(doc, set(paths)):
        raise LedgerError("a member other than the blanked ones changed")
    return (json.dumps(out, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), paths, blind_scope.sha256(src)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="blind_ledger.py", description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="the repository (default: this checkout)")
    ap.add_argument("--commit", default="HEAD", help="the packed commit (default HEAD)")
    ap.add_argument("--protocol", type=Path, help=f"the protocol (default: {PROTOCOL} of the working tree)")
    ap.add_argument("--out", type=Path, required=True, help="the output directory (created; must be empty)")
    a = ap.parse_args(argv)
    try:
        commit = blind_pack.git(a.root, "rev-parse", "--verify", f"{a.commit}^{{commit}}").decode().strip()
        protocol = json.loads((a.protocol or (a.root / PROTOCOL)).read_bytes())
        out, paths, src_sha = ledger(a.root, commit, protocol)
    except LedgerError as e:
        print(f"blind_ledger: {e}", file=sys.stderr)
        return 1
    except (blind_pack.PackError, OSError, KeyError, ValueError) as e:
        print(f"blind_ledger: {e}", file=sys.stderr)
        return 2
    if a.out.exists() and any(a.out.iterdir()):
        print(f"blind_ledger: {a.out} is not empty", file=sys.stderr)
        return 2
    (a.out / "files" / LEDGER).parent.mkdir(parents=True, exist_ok=True)
    (a.out / "files" / LEDGER).write_bytes(out)
    (a.out / "blanked.json").write_text(blind_scope.dump({LEDGER: paths}), encoding="utf-8")
    print(f"blind_ledger: {LEDGER} given with {len(paths)} free-text members blanked, {len(out)} bytes, sha256 "
          f"{blind_scope.sha256(out)} (source {src_sha[:12]}); the strip rules strip nothing; commit {commit[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
