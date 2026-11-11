"""I47 instrument: the generator closures that committed records hash, probed in one tree.

Run as `python tests_m4/_i47_probe.py TREE` (a checkout or an exported tree of the repo). It imports holon from TREE,
calls every top-level `generator_sha256` that a module under TREE/holon defines (found by AST, never by a list kept
here), with the arguments its signature takes:
  (ir_version, root)  holon.records: once per key of holon.records.GENERATORS
  (root, extra)       holon.profile: extra = []
  (root)              every other module
  ()                  holon.gen.eqsearch
and records, for each call, its digest and the files under TREE it read while computing it (Path.read_bytes and
Path.read_text are logged; every closure digest in the repo reads its files through them). It prints one JSON
object: {"digests": {"<module>:<arg>": hex}, "files": sorted repo-relative paths read}.

The digests are what a committed record's generator_sha256 holds; the files are the record-pinned set: a byte change to
any of them moves at least one digest. Nothing is written.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import json
import sys
from pathlib import Path


def main(tree: Path) -> dict:
    tree = tree.resolve()
    sys.path.insert(0, str(tree))
    read: set[str] = set()
    orig_b, orig_t = Path.read_bytes, Path.read_text

    def log(p: Path) -> None:
        try:
            rel = Path(p).resolve().relative_to(tree).as_posix()
        except ValueError:
            return
        read.add(rel)

    def rb(self):
        log(self)
        return orig_b(self)

    def rt(self, *a, **k):
        log(self)
        return orig_t(self, *a, **k)

    mods = []
    for f in sorted((tree / "holon").rglob("*.py")):
        try:
            t = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        if any(isinstance(n, ast.FunctionDef) and n.name == "generator_sha256" for n in t.body):
            rel = f.relative_to(tree).with_suffix("")
            mods.append(".".join(rel.parts[:-1] if rel.name == "__init__" else rel.parts))
    digests: dict[str, str] = {}
    Path.read_bytes, Path.read_text = rb, rt
    try:
        for name in mods:
            m = importlib.import_module(name)
            fn = m.generator_sha256
            params = list(inspect.signature(fn).parameters)
            if name == "holon.records":
                for v in sorted(m.GENERATORS):
                    digests[f"{name}:{v}"] = fn(v, tree)
            elif len(params) == 0:
                digests[name] = fn()
            elif len(params) == 1:
                digests[name] = fn(tree)
            else:
                digests[name] = fn(tree, [])
    finally:
        Path.read_bytes, Path.read_text = orig_b, orig_t
    return {"digests": dict(sorted(digests.items())), "files": sorted(read)}


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1])), indent=1, sort_keys=True))
