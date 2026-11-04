"""`holon binding --milestone M [--root DIR] [--check] [--spec-out]` (BUILD_PLAN I95): the deployment record of a typed
milestone's binding, derived from code.

For each typed document of the milestone's typed-sorts sidecar (spec/<M>/lib/sort_types.json, "documents") whose
sidecar names a binding spec ("binding"), it re-runs the binding's existing deployment (holon.sorts.deploy3: the
binding's harness deploys the real target with the binding's parameters, by forge, on the pinned checkout) and writes
gen/<M>/binding/<document stem>.json:

  {"binding_version", "document",
   "inputs": {"harness": {"contract", "last_contract", "files": {name: sha256}}, "project", "target", "init",
              "commit"},
   "deployment": {"target", "harness", "storage", "preimages", "immutables", "timestamp", "number", "chainid",
                  "calls"}}

The record names its inputs by content (each harness file by name and sha256; the parameters resolved), never by the
binding spec's path. So a binding spec at another path with the same content gives the same bytes. It is canonical
JSON: indent 2, sorted keys, a final newline.

The configuration-only spec, spec/<M>/lib/binding.json (--spec-out writes it, from the typed sidecar's binding):
the harness, project and target members as they are, and the parameters. When the source binding reads its
parameters from a facts document ({"facts", "keys"}), the spec reads them from a copy of that document's initial
members that the keys name, spec/<M>/lib/binding_facts.json:
  {"facts_copy_version", "doc", "copy_of", "copy_of_sha256", "initial": {name: value}}.
That copy is facts, not a record. Every run refuses (exit 2) when a facts copy's values for the keys differ from its
source's, wherever the source is present. In a pack the source may be absent, and then the copy is the declared input.

  --check    re-derives every record in a fresh cache (no cached deployment is read), and the configuration-only
             spec and its facts copy from the source binding (when the typed sidecar names another binding). It
             exits 1 unless each equals the committed bytes.
  --spec-out writes the configuration-only spec and its facts copy instead.

Exit 0: written, or reproduced. Exit 1: a record or a spec file differs or is missing (--check). Exit 2: refused (no
typed sidecar, no binding, or a facts copy that differs from its source). The module is target-agnostic: the binding
spec and the documents say what is deployed.
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


def spec_rel(milestone: str) -> str:
    return f"spec/{milestone}/lib/binding.json"


def facts_rel(milestone: str) -> str:
    return f"spec/{milestone}/lib/binding_facts.json"


def _load(root: Path, binding_rel: str) -> dict:
    from .replay_fragments import FragmentsError, load_binding
    try:
        return load_binding(Path(root) / binding_rel)
    except FragmentsError as e:
        raise BindingError(str(e)) from None


def _init(root: Path, init) -> list[int]:
    from .fragments_corpus import binding_init
    try:
        return binding_init({"init": init}, Path(root))
    except (OSError, ValueError, KeyError, IndexError, TypeError) as e:
        raise BindingError(f"the deployment parameters {init!r}: {e}") from None


def copy_check(root: Path, init) -> None:
    """A facts copy ({"copy_of": the source facts}) must give its source's values for the keys; refuse otherwise.
    Without the source (a pack), the copy is the declared input and nothing is compared."""
    if not isinstance(init, dict):
        return
    p = Path(root) / init["facts"]
    try:
        src = json.loads(p.read_text(encoding="utf-8")).get("copy_of")
    except (OSError, ValueError) as e:
        raise BindingError(f"the deployment parameters' facts {init['facts']}: {e}") from None
    if not src or not (Path(root) / src).is_file():
        return
    got, want = _init(root, init), _init(root, {**init, "facts": src})
    if got != want:
        raise BindingError(f"the facts copy {init['facts']} gives the parameters {got}, its source {src} gives {want}")


def config(root: Path, binding_rel: str, milestone: str | None = None) -> tuple[dict, dict | None]:
    """(the configuration-only spec, its facts copy or None). With a milestone, a source binding whose parameters
    read a facts document reads them, in the spec, from the copy at facts_rel(milestone); without one (or with a
    literal list), the spec holds the parameters as a literal list."""
    b = _load(root, binding_rel)
    init, copy = b.get("init", []), None
    if isinstance(init, dict) and milestone:
        src, keys = init["facts"], list(init["keys"])
        sdoc = json.loads((Path(root) / src).read_text(encoding="utf-8"))
        names = sorted({k.split(".")[0] for k in keys})
        missing = [n for n in names if n not in (sdoc.get("initial") or {})]
        if missing:
            raise BindingError(f"the facts {src} have no initial members {missing}")
        copy = {"facts_copy_version": VERSION,
                "doc": "A copy of the initial members that the binding's parameter keys name, from the facts document "
                       "copy_of (whose sha256 is copy_of_sha256): facts, not a record. holon binding refuses when the "
                       "copy's values differ from its source's, wherever the source is present.",
                "copy_of": src, "copy_of_sha256": _sha(Path(root) / src),
                "initial": {n: sdoc["initial"][n] for n in names}}
        init_out = {"facts": facts_rel(milestone), "keys": keys}
    else:
        init_out = _init(root, init)
    spec = {"binding_version": VERSION,
            "doc": "The configuration of a typed milestone's deployment (holon binding): the harness that deploys the "
                   "target, the project it builds in, the target, and the deployment's parameters. It holds no record: "
                   "holon binding derives the deployment from it by forge.",
            "harness": b["harness"], "project": b["project"], "target": b["target"], "init": init_out}
    return spec, copy


def record(root: Path, binding_rel: str, doc_rel: str) -> dict:
    from .sorts import deploy3
    b = _load(root, binding_rel)
    copy_check(root, b.get("init"))
    init = _init(root, b.get("init", []))
    doc = json.loads((Path(root) / doc_rel).read_text(encoding="utf-8"))
    files = {}
    for f in b["harness"]["files"]:
        p = Path(root) / f
        if not p.is_file():
            raise BindingError(f"the binding's harness file {f} is missing")
        files[Path(f).name] = _sha(p)
    dep = deploy3.deployment(Path(root), binding_rel, doc_rel)
    return {"binding_version": VERSION, "document": doc_rel,
            "inputs": {"harness": {"contract": b["harness"]["contract"],
                                   "last_contract": b["harness"].get("last_contract"), "files": files},
                       "project": b["project"], "target": b["target"], "init": init,
                       "commit": (doc.get("target") or {}).get("commit")},
            "deployment": {k: dep.get(k) for k in DEPLOYMENT_KEYS}}


def _sidecar(root: Path, milestone: str):
    from .sorts import typed_sidecar as TS
    try:
        sc = TS.load(milestone, Path(root))
    except (TS.SidecarError, OSError, ValueError) as e:
        raise BindingError(f"no typed-sorts sidecar for {milestone}: {e}") from None
    if not sc.binding:
        raise BindingError(f"the typed-sorts sidecar of {milestone} names no binding")
    return sc


def records(root: Path, milestone: str) -> dict[str, str]:
    """{gen/<M>/binding/<stem>.json: bytes} for every typed document of the milestone."""
    from .sorts import typed_sidecar as TS
    sc = _sidecar(root, milestone)
    return {f"gen/{milestone}/binding/{stem(TS.rel_of(d, Path(root)))}.json":
            dump(record(Path(root), sc.binding, TS.rel_of(d, Path(root)))) for d in sc.documents}


def spec_files(root: Path, milestone: str) -> dict[str, str]:
    """{spec_rel: bytes, facts_rel: bytes} from the typed sidecar's binding (the facts copy only when there is one)."""
    sc = _sidecar(root, milestone)
    spec, copy = config(Path(root), sc.binding, milestone)
    out = {spec_rel(milestone): dump(spec)}
    if copy is not None:
        out[facts_rel(milestone)] = dump(copy)
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
    ap.add_argument("--spec-out", action="store_true",
                    help="write the configuration-only spec and its facts copy (spec/<M>/lib/binding*.json) instead")
    a = ap.parse_args(argv)
    root, m = Path(a.root), a.milestone
    try:
        if a.spec_out:
            for p, b in sorted(spec_files(root, m).items()):
                (root / p).parent.mkdir(parents=True, exist_ok=True)
                (root / p).write_text(b, encoding="utf-8")
                print(f"holon binding: wrote {p}")
            return 0
        if (root / spec_rel(m)).is_file():
            copy_check(root, json.loads((root / spec_rel(m)).read_text(encoding="utf-8")).get("init"))
        out = _fresh(root, m) if a.check else records(root, m)
        if a.check and _sidecar(root, m).binding != spec_rel(m) and (root / spec_rel(m)).is_file():
            out.update(spec_files(root, m))
    except BindingError as e:
        print(f"holon binding: refused: {e}", file=sys.stderr)
        return 2
    if a.check:
        bad = [p for p, b in sorted(out.items())
               if not (root / p).is_file() or (root / p).read_text(encoding="utf-8") != b]
        for p in bad:
            print(f"holon binding: {p} differs from a fresh derivation" if (root / p).is_file()
                  else f"holon binding: {p} missing")
        if not bad:
            print(f"holon binding: {len(out)} file(s) reproduced (the records from a fresh forge run)")
        return 1 if bad else 0
    for p, b in sorted(out.items()):
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_text(b, encoding="utf-8")
        print(f"holon binding: wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
