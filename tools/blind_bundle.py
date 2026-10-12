"""Build the M3 blind-rerun bundle (docs/M3_SPEC.md decision 3).

Copies the tracked tree at HEAD (no .git) minus everything that states
findings, laws, predictions or results, and strips the whitepaper of
Appendix A and §11.3-§11.8. Writes BLIND_MANIFEST.json (sha256 per file).

    python3 tools/blind_bundle.py OUT_DIR
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDE_PREFIXES = (
    "audit/", "results/", "laws/", "predictions/", "replay/", "facts/",
    "spec/M1/", "spec/M2/", "spec/M0/",
    "spec/M3/", "tests/", "tests_m1/", "tests_m2/", "tests_m3/",
    "bend/probes/", "README.md", "gen/", "prompts/",
    "config/triage.json", "FROZEN.sha256",
)
# Identifiers that name a finding or law. Files that keep one after the
# exclusions (factory code and the residual whitepaper) are listed in the
# manifest as known leaks, so the comparison can discount them.
LEAK_RE = re.compile(
    rb"L_(?:undo|sort|tag|fact|sym|nat|disch|own|par|dom)_[A-Za-z0-9_]+"
    rb"|\bF(?:[1-9]|1[0-4])\b|\bO(?:[1-9]|[12][0-9]|3[0-7])\b")
DOCS_KEPT = {"docs/BEND_PRIMER.md", "docs/BEND_NOTES.md"}
WHITEPAPER = "whitepaper.md"

# (start heading regex, end heading regex): drop [start, end)
STRIP = (
    (r"^### 11\.3 ", r"^## 12 "),
    (r"^## Appendix A\.", r"^## Appendix B\."),
)


def kept(path: str) -> bool:
    if path.startswith("docs/"):
        return path in DOCS_KEPT
    return not path.startswith(EXCLUDE_PREFIXES)


def strip_whitepaper(text: str) -> str:
    lines = text.splitlines(keepends=True)
    for start, end in STRIP:
        s = next(i for i, l in enumerate(lines) if re.match(start, l))
        e = next(i for i, l in enumerate(lines) if i > s and re.match(end, l))
        lines = lines[:s] + lines[e:]
    return "".join(lines)


def main(out: Path) -> int:
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty")
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files"], check=True,
                           capture_output=True, text=True).stdout.split()
    manifest, leaks = {}, {}
    for f in sorted(files):
        if not kept(f):
            continue
        data = (ROOT / f).read_bytes()
        if f == WHITEPAPER:
            data = strip_whitepaper(data.decode()).encode()
        dst = out / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        manifest[f] = hashlib.sha256(data).hexdigest()
        hits = sorted({m.decode() for m in LEAK_RE.findall(data)})
        if hits:
            leaks[f] = hits
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()
    (out / "BLIND_MANIFEST.json").write_text(json.dumps(
        {"source_commit": head, "files": manifest, "known_leaks": leaks}, indent=1, sort_keys=True) + "\n")
    print(f"{len(manifest)} files -> {out}; {len(leaks)} with known leaks")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
