"""D2 / Hyp-Z0-kzg: the zero-blob versioned hash, checked by code against Morph's constants.

Whitepaper §11.6, D2: Morph's `ZERO_VERSIONED_HASH` (Rollup.sol) and `EmptyVersionedHash`
(common/blob/payload.go) are claimed to equal the KZG versioned hash of the all-zero blob.
This module computes that hash from its definition and compares it with the constants as
they appear in a Morph checkout, at the facts' target commit.

This hypothesis is named Hyp-Z0-kzg. It is NOT HypZ: §8.5 reserves HypZ for the compression
hypothesis (Dec(Enc x ++ 0^k) = x), which this module does not touch.

The comparison reads the target's source text, never the frozen test oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FACTS = ROOT / "spec" / "M1" / "facts" / "morph_rollup.json"
DEFAULT_OUT = ROOT / "results" / "M2" / "hypotheses.json"
DEFAULT_MORPH = "/root/work/morph"
KEY = "Hyp-Z0-kzg"

SOL_PATH = "contracts/contracts/l1/rollup/Rollup.sol"
GO_PATH = "common/blob/payload.go"

_HEX64 = r"(0x[0-9a-fA-F]{64})(?![0-9a-fA-F])"
SOL_RE = re.compile(r"\bZERO_VERSIONED_HASH\s*=\s*" + _HEX64)
GO_RE = re.compile(r'\bEmptyVersionedHash\s*=\s*common\.HexToHash\(\s*"' + _HEX64 + r'"\s*\)')


class _FactsTarget:
    """Sentinel default for `check(commit=...)`: use the facts' target commit."""

    def __repr__(self) -> str:
        return "<facts target>"


FACTS_TARGET = _FactsTarget()


def compute() -> str:
    """The KZG versioned hash of the all-zero blob (D2 / Hyp-Z0-kzg, whitepaper §11.6).

    EIP-4844: versioned_hash = 0x01 ‖ sha256(commitment)[1:]. The KZG commitment of the
    all-zero polynomial is the point at infinity of G1, whose 48-byte compressed encoding is
    0xc0 followed by 47 zero bytes. So the result is 0x01 ‖ sha256(0xc0 ‖ 0^47)[1:].

    This is distinct from HypZ, the compression hypothesis of §8.5.
    """
    return "0x01" + hashlib.sha256(bytes([0xC0]) + bytes(47)).hexdigest()[2:]


def facts_target_commit() -> str:
    """The full target commit recorded in spec/M1/facts/morph_rollup.json."""
    commit = json.loads(FACTS.read_text(encoding="utf-8"))["target"]["commit"]
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError(f"{FACTS}: target.commit is not a full 40-hex commit: {commit!r}")
    return commit


def _find(morph: Path, rel: str, pattern: re.Pattern) -> dict:
    """First line of `rel` whose code (before any `//` comment) declares the constant."""
    found = {"path": rel, "line": None, "value": None}
    try:
        text = (morph / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return found
    for n, line in enumerate(text.splitlines(), start=1):
        m = pattern.search(line.split("//", 1)[0])
        if m:
            found["line"] = n
            found["value"] = m.group(1).lower()
            return found
    return found


def _checkout_head(morph: Path) -> str | None:
    """`git -C morph rev-parse HEAD`, or None if git fails."""
    try:
        r = subprocess.run(["git", "-C", str(morph), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def check(morph: Path, commit: str | None | _FactsTarget = FACTS_TARGET) -> dict:
    """Compare compute() with ZERO_VERSIONED_HASH (Rollup.sol) and EmptyVersionedHash (payload.go).

    `commit` defaults to the facts' target commit. Unless `commit` is explicitly None, the morph
    directory must be a git checkout whose HEAD is `commit` and whose two source files carry no
    uncommitted change; otherwise the status is "mismatch", with the actual HEAD (None when the
    directory is not a checkout) as "checkout_commit", and "dirty" when the files are modified.
    Only commit=None (a fixture, not a claim about the target) skips that. A constant that is not
    found has value None and makes the status "mismatch".
    """
    morph = Path(morph)
    if isinstance(commit, _FactsTarget):
        commit = facts_target_commit()
    want = compute()
    sol = _find(morph, SOL_PATH, SOL_RE)
    go = _find(morph, GO_PATH, GO_RE)
    ok = sol["value"] == want and go["value"] == want
    rec = {"computed": want, "solidity": sol, "go": go, "morph_commit": commit}
    if commit is not None:
        head = _checkout_head(morph) if (morph / ".git").exists() else None
        if head != commit:
            rec["checkout_commit"] = head
            ok = False
        else:
            import subprocess
            p = subprocess.run(["git", "-C", str(morph), "status", "--porcelain", "--", SOL_PATH, GO_PATH],
                               capture_output=True, text=True, env={**__import__("os").environ, "GIT_OPTIONAL_LOCKS": "0"})
            if p.returncode != 0 or p.stdout.strip():
                rec["dirty"] = p.stdout.strip() or p.stderr.strip()[:200]
                ok = False
    rec["status"] = "checked" if ok else "mismatch"
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon oracle zero-blob",
                                 description="Check D2 (Hyp-Z0-kzg): Morph's zero-blob versioned hash constants.")
    ap.add_argument("--morph", type=Path, default=Path(os.environ.get("HOLON_MORPH") or DEFAULT_MORPH),
                    help="Morph checkout (default: $HOLON_MORPH or %s)" % DEFAULT_MORPH)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="hypotheses JSON to update (default: results/M2/hypotheses.json)")
    args = ap.parse_args(argv)

    obj: dict = {}
    if args.out.exists():
        obj = json.loads(args.out.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            print(f"{args.out}: not a JSON object; refusing to overwrite", file=sys.stderr)
            return 2
    rec = check(args.morph)
    obj[KEY] = rec
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{KEY}: {rec['status']} (computed {rec['computed']}; "
          f"solidity {rec['solidity']['value']} at {SOL_PATH}:{rec['solidity']['line']}; "
          f"go {rec['go']['value']} at {GO_PATH}:{rec['go']['line']}; "
          f"morph_commit {rec['morph_commit']}"
          + (f"; checkout_commit {rec['checkout_commit']}" if "checkout_commit" in rec else "") + ")")
    return 0 if rec["status"] == "checked" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
