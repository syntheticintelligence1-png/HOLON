"""`python -m holon.frontends.go` — the S3 go-ssa extraction driver.

    extract   run gossa over the pinned morph packages and write
              spec/M2/extracted/go_codecs.json,
              spec/M2/extracted/go_batchdata.json,
              spec/M2/coverage/go.json
    dump      write the raw gossa-dump JSON for inspection

The extractor never reads hand-written facts (docs/M2_SPEC.md §2);
comparison happens only in tests_m2/s3_go_ssa via differ.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from . import codecs, model, own, tool

PACKAGES = ["morph-l2/common/batch", "morph-l2/node/types"]

REPO_ROOT = Path(__file__).resolve().parents[3]
EXTRACTED = REPO_ROOT / "spec" / "M2" / "extracted"
COVERAGE = REPO_ROOT / "spec" / "M2" / "coverage"


def morph_dir() -> Path:
    d = os.environ.get("HOLON_MORPH_DIR", str(Path.home() / ".holon" / "morph"))
    p = Path(d)
    if not p.exists():
        raise SystemExit(
            f"morph checkout not found at {p}; set HOLON_MORPH_DIR")
    return p


def target_commit(morph: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(morph), "rev-parse", "HEAD"],
        capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else "unknown"


def load_dump(morph: Path) -> model.Dump:
    raw = tool.run_dump(morph, PACKAGES)
    return model.Dump(raw)


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=False) + "\n")


def _debt_items(codecs_cov, own_cov):
    items = []
    for it in codecs_cov.get("debt", []):
        items.append({"element": it["element"], "kind": it["kind"],
                      "reason": it["reason"]})
    for d in own_cov.get("debt", []):
        if isinstance(d, dict):
            if "element" in d:
                items.append({"element": d["element"],
                              "kind": d["kind"], "reason": d["reason"]})
                continue
            site = d.get("site") or {}
            el = f"{site.get('file')}:{site.get('line')} {d.get('field') or ''}".rstrip()
            items.append({"element": el or "unknown",
                          "kind": "unmodelled", "reason": d["reason"]})
        else:
            items.append({"element": str(d), "kind": "unmodelled",
                          "reason": str(d)})
    items.sort(key=lambda i: i["element"])
    return items


def extract(morph: Path = None) -> dict:
    morph = morph or morph_dir()
    commit = target_commit(morph)
    dump = load_dump(morph)
    cc = codecs.extract_codecs(dump)
    mm = own.extract_machine(dump, type_names=("BatchData",))
    cc["target"] = {"repo": "morph-l2/morph", "commit": commit,
                    "packages": PACKAGES}
    mm["target"] = {"repo": "morph-l2/morph", "commit": commit,
                    "packages": PACKAGES}
    _write(EXTRACTED / "go_codecs.json", cc)
    _write(EXTRACTED / "go_batchdata.json", mm)
    coverage = {
        "frontend": "go",
        "target_commit": commit,
        "items": _debt_items(cc["coverage"], mm["coverage"]),
    }
    _write(COVERAGE / "go.json", coverage)
    return {"codecs": cc, "machine": mm, "coverage": coverage}


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "extract"
    if cmd == "extract":
        out = extract()
        n_enc = len(out["codecs"]["encoders"])
        n_pred = len(out["codecs"]["predicates"])
        n_get = len(out["codecs"]["decoders"]["getters"])
        n_act = sum(len(m["actions"]) for m in out["machine"]["machines"])
        n_debt = len(out["coverage"]["items"])
        print(f"go_codecs.json: {n_enc} encoders, {n_pred} predicates, "
              f"{n_get} getters, "
              f"{len(out['codecs']['partiality'])} partiality sites")
        print(f"go_batchdata.json: {len(out['machine']['machines'])} "
              f"machine(s), {n_act} actions")
        print(f"go.json coverage: {n_debt} debt items")
        return 0
    if cmd == "dump":
        morph = morph_dir()
        raw = tool.run_dump(morph, PACKAGES)
        where = argv[2] if len(argv) > 2 else "-"
        text = json.dumps(raw, indent=1)
        if where == "-":
            sys.stdout.write(text)
        else:
            Path(where).write_text(text)
            print(f"wrote {where}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
