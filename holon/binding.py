"""`holon binding --milestone M [--root DIR] [--check]` (BUILD_PLAN I95): the deployment record of a typed milestone's
binding, derived from code.

For each typed document of the milestone's typed-sorts sidecar (spec/<M>/lib/sort_types.json, "documents") whose
sidecar names a binding spec ("binding"), it re-runs the binding's existing deployment (holon.sorts.deploy3: the
binding's harness deploys the real target with the binding's parameters, by forge, on the pinned checkout) and writes
gen/<M>/binding/<document stem>.json:

  {"binding_version", "document",
   "inputs": {"harness": {"contract", "last_contract", "files": {name: sha256}}, "project", "target", "init",
              "commit"},
   "deployment": {"target", "harness", "storage", "preimages", "immutables", "timestamp", "number", "chainid",
                  "calls"}}

The record names its inputs by content (each harness file by name and sha256), never by the binding spec's path. So a
binding spec at another path with the same content gives the same bytes. It is canonical JSON: indent 2, sorted keys,
a final newline.

  --check    re-derives every record in a fresh cache (no cached deployment is read) and exits 1 unless each equals
             the committed bytes.
  --spec-out PATH
             writes the binding spec's configuration-only form instead: the harness, project and target members as
             they are, the deployment parameters resolved to a literal list (holon.fragments_corpus.binding_init), and
             nothing else, so a pack can carry it without any record.

Exit 0: written, or reproduced. Exit 1: a record differs or is missing (--check). Exit 2: refused (no typed sidecar,
or no binding). The module is target-agnostic: the binding spec and the documents say what is deployed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "holon-binding/1"
DEPLOYMENT_KEYS = ("target", "harness", "storage", "preimages", "immutables", "timestamp", "number", "chainid", "calls")


class BindingError(Exception):
    pass


def dump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def stem(doc_rel: str) -> str:
    """gen/<M>/binding/<stem>.json: the document's file name without its last suffix."""
    return Path(doc_rel).name[: -len(".json")] if doc_rel.endswith(".json") else Path(doc_rel).name


def config(root: Path, binding_rel: str) -> dict:
    """The binding spec's configuration-only form: what the deployment reads, its parameters resolved."""
    from .fragments_corpus import binding_init
    from .replay_fragments import FragmentsError, load_binding
    try:
        b = load_binding(Path(root) / binding_rel)
    except FragmentsError as e:
        raise BindingError(str(e)) from None
    return {"binding_version": VERSION,
            "doc": "The configuration of a typed milestone's deployment (holon binding): the harness that deploys the "
                   "target, the project it builds in, the target, and the deployment's parameters as a literal list. "
                   "It holds no record: holon binding derives the deployment from it by forge.",
            "harness": b["harness"], "project": b["project"], "target": b["target"],
            "init": binding_init(b, Path(root))}


def record(root: Path, binding_rel: str, doc_rel: str) -> dict:
    from .sorts import deploy3
    cfg = config(root, binding_rel)
    doc = json.loads((Path(root) / doc_rel).read_text(encoding="utf-8"))
    files = {}
    for f in cfg["harness"]["files"]:
        p = Path(root) / f
        if not p.is_file():
            raise BindingError(f"the binding's harness file {f} is missing")
        files[Path(f).name] = _sha(p)
    dep = deploy3.deployment(Path(root), binding_rel, doc_rel)
    return {"binding_version": VERSION, "document": doc_rel,
            "inputs": {"harness": {"contract": cfg["harness"]["contract"],
                                   "last_contract": cfg["harness"].get("last_contract"), "files": files},
                       "project": cfg["project"], "target": cfg["target"], "init": cfg["init"],
                       "commit": (doc.get("target") or {}).get("commit")},
            "deployment": {k: dep.get(k) for k in DEPLOYMENT_KEYS}}


def records(root: Path, milestone: str) -> dict[str, str]:
    """{gen/<M>/binding/<stem>.json: bytes} for every typed document of the milestone."""
    from .sorts import typed_sidecar as TS
    try:
        sc = TS.load(milestone, Path(root))
    except (TS.SidecarError, OSError, ValueError) as e:
        raise BindingError(f"no typed-sorts sidecar for {milestone}: {e}") from None
    if not sc.binding:
        raise BindingError(f"the typed-sorts sidecar of {milestone} names no binding")
    out = {}
    for d in sc.documents:
        rel = TS.rel_of(d, Path(root))
        out[f"gen/{milestone}/binding/{stem(rel)}.json"] = dump(record(Path(root), sc.binding, rel))
    return out


def _fresh(root: Path, milestone: str) -> dict[str, str]:
    tmp = Path(tempfile.mkdtemp(prefix="holon-binding-"))
    old = os.environ.get("HOLON_CACHE")
    os.environ["HOLON_CACHE"] = str(tmp)
    try:
        return records(root, milestone)
    finally:
        if old is None:
            os.environ.pop("HOLON_CACHE", None)
        else:
            os.environ["HOLON_CACHE"] = old
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon binding")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--spec-out", help="write the binding spec's configuration-only form to this path instead")
    a = ap.parse_args(argv)
    root = Path(a.root)
    try:
        if a.spec_out:
            from .sorts import typed_sidecar as TS
            sc = TS.load(a.milestone, root)
            if not sc.binding:
                raise BindingError(f"the typed-sorts sidecar of {a.milestone} names no binding")
            out = root / a.spec_out
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(dump(config(root, sc.binding)), encoding="utf-8")
            print(f"holon binding: wrote {a.spec_out} from {sc.binding}")
            return 0
        recs = _fresh(root, a.milestone) if a.check else records(root, a.milestone)
    except BindingError as e:
        print(f"holon binding: refused: {e}", file=sys.stderr)
        return 2
    if a.check:
        bad = [p for p, b in sorted(recs.items())
               if not (root / p).is_file() or (root / p).read_text(encoding="utf-8") != b]
        for p in bad:
            print(f"holon binding: {p} differs from a fresh run" if (root / p).is_file() else f"holon binding: {p} missing")
        if not bad:
            print(f"holon binding: {len(recs)} record(s) reproduced from a fresh forge run")
        return 1 if bad else 0
    for p, b in sorted(recs.items()):
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_text(b, encoding="utf-8")
        print(f"holon binding: wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
