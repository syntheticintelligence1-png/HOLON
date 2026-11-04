"""Cross-language links (whitepaper §10.1 Linking, §7.7 step 5; BUILD_PLAN I19; contract: the docstring of
tests_m2/test_coverage.py).

    python -m holon link --milestone M2 [--root DIR] [--out PATH] [--check]

writes <root>/gen/<M>/link.json (canonical JSON: indent 2, sorted keys, newline):

  {"links": [{"role", "solidity": <value>, "go": <value>, "equal": bool}]}   sorted by role

The roles and, per language, the fact that plays each one are the frozen sidecar spec/<M>/lib/link.json; this module
names no role and no target identifier. Values are read from the extracted documents only (never from the source, a
hand-written fact document or a law), by the key a role's source carries:

  "edge"      (Solidity layout document, holon-facts/0.3 of I17) the accepted (first byte, length) pairs of the loader
              edge's ok paths: for every first-byte value 0..255 an ok path's condition admits, the lengths it admits,
              written as an integer when exactly one length is admitted, [">=", k] when every length from k up is, and
              ["in", k, ...] (the admitted lengths among the probes) otherwise. The conditions are I17 DSL expressions
              over ["byte", input, 0] and ["len", input]; they are evaluated exactly on probe lengths around every
              constant they hold (k - 1, k, k + 1, 0 and a length above all of them), which decides comparisons of the
              length with constants. A sorted list of [first byte, length] pairs.
  "function"  (Go document of I18) the accepted (tag, length) pairs of the tagged predicate go.codecs.predicates whose
              function's last name segment is the source's function: [[value, length], ...] sorted.
  "constant"  (Solidity transitions document) constants[<name>] (a 0x-hex string).
  "global"    (Go document) the value the document records for the package variable named by the source: the entry of
              go.globals (holon.frontends.go.extract, I19 follow-up A19-13) whose "global" is exactly that qualified
              name, else the only entry whose name ends in "." + the source's name (two or more: refused). Its cells
              written as a 0x-hex string when every cell is a constant; null when the variable has no entry or its
              bytes are not all known (the recorded value term is then reported on stderr).

Roles are validated before any document is read (I19 follow-up A19-19): each names both languages, and each
language's source is an object with a "document" path and exactly one reader key among edge, function, constant and
global; a malformed role is refused (exit 2) and nothing is written.

equal is true iff both values are present and equal. A value that is missing, and a link that is not equal, are
reported on stderr; the link stays in the report as an explicit unlinked assumption (§7.7 step 5). --check writes
nothing and exits 0 iff the report equals --out (default the committed one). Exit 0 written, 1 (--check) differs,
2 refused (no link sidecar, a malformed role, a document missing, a source the reader cannot read).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANGS = ("solidity", "go")


class LinkError(Exception):
    """A role source that cannot be read (exit 2)."""


def sidecar_path(m: str, root=ROOT) -> Path:
    return Path(root) / "spec" / m / "lib" / "link.json"


def report_path(m: str, root=ROOT) -> Path:
    return Path(root) / "gen" / m / "link.json"


def _load(root: Path, rel: str) -> dict:
    p = Path(root) / rel
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise LinkError(f"cannot read {rel}: {e}") from e


# ------------------------------------------------------------------------------------------------ the DSL (I17 J5)
def _eval(e, byte0: int, length: int, name: str):
    if isinstance(e, bool):
        return int(e)
    if isinstance(e, int):
        return e
    if not isinstance(e, list) or not e:
        raise LinkError(f"not a DSL expression: {e!r:.120}")
    op = e[0]
    if op == "len" and len(e) == 2 and e[1] == name:
        return length
    if op == "byte" and len(e) == 3 and e[1] == name:
        if e[2] != 0:
            raise LinkError(f"a loader condition reads byte {e[2]} of {name}: no (first byte, length) pair")
        return byte0
    args = [_eval(x, byte0, length, name) for x in e[1:]]
    if op == "!":
        return int(not args[0])
    if op == "&&":
        return int(all(args))
    if op == "||":
        return int(any(args))
    binary = {"==": lambda a, b: int(a == b), "!=": lambda a, b: int(a != b), "<": lambda a, b: int(a < b),
              "<=": lambda a, b: int(a <= b), ">": lambda a, b: int(a > b), ">=": lambda a, b: int(a >= b),
              "+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b,
              "/": lambda a, b: a // b if b else 0, "%": lambda a, b: a % b if b else 0}
    if op in binary and len(args) == 2:
        return binary[op](*args)
    raise LinkError(f"an operator the linker does not evaluate: {op!r}")


def _constants(e, out: set) -> None:
    if isinstance(e, bool):
        return
    if isinstance(e, int):
        out.add(e)
    elif isinstance(e, list):
        for x in e[1:]:
            _constants(x, out)


def _length_compared_with_constants(e, name: str, parent=None) -> None:
    """Every ["len", name] is an operand of a comparison with an integer: probing around the constants is then exact."""
    if isinstance(e, list) and e:
        if e[0] == "len" and len(e) == 2 and e[1] == name:
            ok = isinstance(parent, list) and parent[0] in ("==", "!=", "<", "<=", ">", ">=") and len(parent) == 3 \
                and any(isinstance(x, int) and not isinstance(x, bool) for x in parent[1:])
            if not ok:
                raise LinkError(f"a loader condition uses the length of {name} other than in a comparison with a "
                                f"constant: {parent!r:.120}")
            return
        for x in e[1:]:
            _length_compared_with_constants(x, name, e)


def _input_name(paths: list) -> str | None:
    found = set()

    def walk(e):
        if isinstance(e, list) and e:
            if e[0] in ("len", "byte") and len(e) >= 2 and isinstance(e[1], str):
                found.add(e[1])
            for x in e[1:]:
                walk(x)
    for p in paths:
        for c in p.get("cond", []):
            walk(c)
    if len(found) > 1:
        raise LinkError(f"the loader's conditions name several inputs: {sorted(found)}")
    return next(iter(found), None)


def loader_pairs(doc: dict, edge: str) -> list:
    """The accepted (first byte, length) pairs of a Solidity loader edge's ok paths (module docstring)."""
    fn = (doc.get("functions") or {}).get(edge)
    if fn is None:
        raise LinkError(f"the Solidity document has no edge {edge!r}")
    oks = [p for p in fn.get("paths", []) if p.get("outcome") == "ok"]
    name = _input_name(oks) or ""
    pairs = []
    for p in oks:
        conds = p.get("cond", [])
        for c in conds:
            _length_compared_with_constants(c, name)
        ks: set = set()
        for c in conds:
            _constants(c, ks)
        probes = sorted({0} | {k + d for k in ks for d in (-1, 0, 1) if k + d >= 0})
        top = probes[-1] + 2
        probes.append(top)
        for b in range(256):
            ok = [L for L in probes if all(_eval(c, b, L, name) for c in conds)]
            if not ok:
                continue
            i = len(probes)
            while i > 0 and probes[i - 1] in ok:
                i -= 1
            if i < len(probes) and ok == probes[i:]:
                form = [">=", probes[i]]           # every probe from probes[i] up, the gaps between them too
            elif len(ok) == 1 and ok[0] in ks:
                form = ok[0]                       # exactly the constant (k - 1 and k + 1 are probes, rejected)
            else:
                form = ["in"] + ok
            pairs.append([b, form])
    out, seen = [], set()
    for pr in sorted(pairs, key=lambda x: (x[0], json.dumps(x[1]))):
        key = json.dumps(pr)
        if key not in seen:
            seen.add(key)
            out.append(pr)
    return out


def predicate_pairs(doc: dict, function: str) -> list:
    """The accepted (tag, length) pairs of the Go tagged predicate named by its function's last segment."""
    preds = (((doc.get("go") or {}).get("codecs") or {}).get("predicates")) or []
    hits = [p for p in preds if str(p.get("function", "")).rsplit(".", 1)[-1] == function]
    if len(hits) != 1:
        raise LinkError(f"the Go document has {len(hits)} tagged predicates named {function!r}")
    return sorted([a["value"], a["length"]] for a in hits[0].get("accepts", []))


NOTES: list = []


def global_value(doc: dict, name: str):
    """The 0x-hex bytes the Go document records for the package variable `name` (module docstring), or None."""
    entries = [g for g in ((doc.get("go") or {}).get("globals") or []) if isinstance(g, dict)]
    hits = [g for g in entries if g.get("global") == name]
    if not hits:
        hits = [g for g in entries if str(g.get("global", "")).endswith("." + name)]
    if len(hits) > 1:
        raise LinkError(f"the Go document has {len(hits)} package variables named {name!r}: "
                        f"{sorted(g['global'] for g in hits)}")
    if not hits:
        return None
    cells = hits[0].get("cells")
    if isinstance(cells, list) and cells and all(isinstance(c, list) and len(c) == 2 and c[0] == "const"
                                                 and isinstance(c[1], int) and 0 <= c[1] < 256 for c in cells):
        return "0x" + bytes(c[1] for c in cells).hex()
    NOTES.append(f"{hits[0]['global']}: its bytes are not all known; the document records "
                 f"{json.dumps(hits[0].get('value'))[:300]}")
    return None


READERS = ("edge", "function", "constant", "global")


def check_roles(side: dict) -> None:
    """Every role names both languages, each with a document and exactly one reader key (LinkError otherwise)."""
    roles = side.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise LinkError("the link sidecar has no roles")
    bad = []
    for role in sorted(roles):
        r = roles[role]
        if not isinstance(r, dict):
            bad.append(f"{role}: not an object")
            continue
        for lang in LANGS:
            src = r.get(lang)
            if not isinstance(src, dict):
                bad.append(f"{role}: no {lang} source")
                continue
            if not isinstance(src.get("document"), str) or not src["document"]:
                bad.append(f"{role}.{lang}: no document")
            keys = [k for k in READERS if k in src]
            if len(keys) != 1 or not isinstance(src[keys[0]], str) or not src[keys[0]]:
                bad.append(f"{role}.{lang}: needs exactly one of {', '.join(READERS)} (has {keys})")
    if bad:
        raise LinkError("malformed link sidecar: " + "; ".join(bad))


def read_value(src: dict, root: Path):
    doc = _load(root, src["document"])
    if "edge" in src:
        return loader_pairs(doc, src["edge"])
    if "function" in src:
        return predicate_pairs(doc, src["function"])
    if "constant" in src:
        consts = doc.get("constants") or {}
        if src["constant"] not in consts:
            raise LinkError(f"{src['document']} has no constant {src['constant']!r}")
        return consts[src["constant"]]
    if "global" in src:
        return global_value(doc, src["global"])
    raise LinkError(f"a role source names no fact the linker reads: {sorted(src)}")


def compute(m: str, root=ROOT) -> dict:
    root = Path(root)
    p = sidecar_path(m, root)
    if not p.is_file():
        raise LinkError(f"no link sidecar {p.relative_to(root) if p.is_relative_to(root) else p}")
    side = _load(root, p.relative_to(root).as_posix()) if p.is_relative_to(root) else json.loads(p.read_text())
    check_roles(side)
    links = []
    for role in sorted(side.get("roles") or {}):
        r = side["roles"][role]
        vals = {lang: read_value(r[lang], root) for lang in LANGS}
        links.append({"role": role, "solidity": vals["solidity"], "go": vals["go"],
                      "equal": vals["solidity"] is not None and vals["go"] is not None
                      and vals["solidity"] == vals["go"]})
    return {"links": links}


def render(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon link", description="cross-language links between extracted documents")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--root")
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    out = Path(a.out) if a.out else report_path(a.milestone, root)
    try:
        doc = compute(a.milestone, root)
    except LinkError as e:
        print(f"holon link: refused: {e}", file=sys.stderr)
        return 2
    data = render(doc)
    for note in NOTES:
        print(f"holon link: {note}", file=sys.stderr)
    for ln in doc["links"]:
        missing = [lang for lang in LANGS if ln[lang] is None]
        if missing:
            print(f"holon link: {ln['role']}: no {' and no '.join(missing)} value in the extracted documents",
                  file=sys.stderr)
        elif not ln["equal"]:
            print(f"holon link: {ln['role']}: the languages differ: solidity {json.dumps(ln['solidity'])}, "
                  f"go {json.dumps(ln['go'])}", file=sys.stderr)
    if a.check:
        same = out.is_file() and out.read_bytes() == data
        print(f"holon link: {out} {'is up to date' if same else 'differs from a fresh run'}")
        return 0 if same else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, out)
    print(f"holon link: wrote {out}")
    return 0
