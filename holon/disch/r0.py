"""DISCH's R0 derived from the binding (BUILD_PLAN I96a; the contract is the docstring of tests_m3/test_r0_i96a.py,
"R"): ``python -m holon disch-r0 --milestone <M> [--sidecar PATH] [--model-sidecar PATH] [--root PATH] [--check]``.

The step reads the DISCH sidecar's documents and, for each, the deployment record gen/<M>/binding/<stem>.json that
``holon binding`` writes: the storage the deployment leaves and the keccak256 preimages it computed. It writes the
sidecar's "r0" and "model_sidecar", and nothing else. Paths are the layout's: the document's storage and
inherited_storage declarations, with __gap skipped (holon.analysis.closure.Layout).

  values        A scalar path holds its deployed word, at its offset and width. A mapping family holds 0 plus the
                deployed words of its written keys; for a struct family, each member path does, at the member's slot,
                offset and width. A non-zero word whose declared type is an address (address, address payable, or a
                contract or interface type) is "T". A path whose deployed words are all 0 is unlisted, which
                closure.py reads as {0}. Lists are sorted, ints first.
  keys          {family: {key: null, or for a struct family its members made non-zero, in declaration order}}, for
                each key whose entry holds a non-zero word. Keys are found through the record's 64-byte preimages
                (key . slot). Integer and bool keys are decimal; address keys are 0x plus 40 lowercase hex digits;
                other keys are 0x plus 64 lowercase hex digits.
  proxy_slots   The written non-zero slots that no layout path holds, as 0x plus 64 lowercase hex digits, sorted.
  derived_from  [{"document", "path", "sha256"}] of the deployment records, by document. "doc" states the rule.

model_sidecar names the milestone's typing sidecar (holon.sorts.typed_sidecar.default_path, or --model-sidecar)
explicitly. closure.py is unchanged and has no default for it. "expected" is never written. The sidecar is written as
JSON with indent 2, sorted keys and ASCII escapes, plus a newline. --check exits 0 when the sidecar's bytes are what a
run would write, and 1 otherwise. The step refuses (exit 2) when the sidecar, a deployment record or the typing
sidecar is missing; when the documents' derivations disagree; or when a written slot lies in a region the rule does
not read (an array family, a nested mapping, or a mapping keyed by a dynamic type).

Nothing here names a target. Types, slots and keys come from the document and the record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .. import binding as BD
from ..analysis import closure as C
from ..keccak import keccak256
from ..sorts import typed_sidecar as TS

VERSION = "holon-disch-r0/1"
ROOT = Path(__file__).resolve().parents[2]
RULE = ("The deployment's abstraction R0, derived by `python -m holon disch-r0` (" + VERSION + ") from the deployment "
        "records named in derived_from, through each document's layout. values: a scalar path holds its deployed word "
        "(at its offset and width); a mapping family holds 0 plus the deployed words of its written keys (for a struct "
        "family, each member path does); a non-zero word whose declared type is an address is \"T\"; a path whose "
        "deployed words are all 0 is unlisted, which is {0}. keys: the keys whose entry holds a non-zero word (for a "
        "struct family, the members made non-zero), from the record's 64-byte keccak256 preimages. proxy_slots: the "
        "written non-zero slots that no layout path holds. Configuration derived from code, never authored.")
DYNAMIC = ("string", "bytes")


class R0Error(ValueError):
    pass


def dump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def is_address(t) -> bool:
    t = str(t or "").strip()
    return t in ("address", "address payable") or t.startswith(("contract ", "interface ", "t_contract("))


def _bits(word: int, offset: int, width: int) -> int:
    return (word >> (8 * int(offset or 0))) & ((1 << int(width or 256)) - 1)


def _int_type(t) -> bool:
    t = str(t or "").strip()
    return t == "bool" or t.startswith(("uint", "int", "enum "))


def key_text(key: bytes, key_type) -> str:
    """A mapping key as r0 lists it: decimal for an integer or bool key (two's complement for intN), 0x plus 40 hex
    digits for an address key, 0x plus 64 hex digits otherwise."""
    n = int.from_bytes(key, "big")
    t = str(key_type or "").strip()
    if is_address(t):
        return "0x" + format(n & ((1 << 160) - 1), "040x")
    if t.startswith("int") and n >> 255:
        return str(n - (1 << 256))
    if _int_type(t):
        return str(n)
    return "0x" + format(n, "064x")


def _sorted(xs) -> list:
    return sorted(xs, key=lambda x: (isinstance(x, str), x))


def derive(doc: dict, record: dict) -> dict:
    """{"values", "keys", "proxy_slots"} of one document from its deployment record (R0Error on a region the rule does
    not read)."""
    dep = record["deployment"]
    storage = {int(s, 16): int(w, 16) for s, w in (dep.get("storage") or {}).items()}
    storage = {s: w for s, w in storage.items() if w}
    decls = [d for d in list(doc.get("storage") or []) + list(doc.get("inherited_storage") or [])
             if d.get("name") != "__gap"]
    paths = C.Layout(doc).paths
    held: set = set()
    words: dict = {}        # path -> {non-zero word, or "T"}
    keys: dict = {}

    def put(path: str, word: int, typ) -> bool:
        if path not in paths:
            raise R0Error(f"the layout has no path {path}")
        if not word:
            return False
        words.setdefault(path, set()).add("T" if is_address(typ) else word)
        return True

    fams: dict = {}
    for d in decls:
        kind = d.get("kind")
        if kind == "scalar":
            held.add(int(d["slot"]))
            put(d["name"], _bits(storage.get(int(d["slot"]), 0), d.get("offset", 0), d.get("width") or 256),
                d.get("value"))
        elif kind == "mapping":
            fams[int(d["slot"])] = d
        elif kind == "array":
            n = int(d.get("length") or 0)
            per = max(1, 256 // int(d.get("width") or 256))
            if any(int(d["slot"]) <= s < int(d["slot"]) + max(1, (n + per - 1) // per) for s in storage):
                raise R0Error(f"a written slot lies in the array family {d['name']}")
        else:
            raise R0Error(f"{d.get('name')}: a declaration kind the rule does not read ({kind})")
    pre = [bytes.fromhex(p[2:] if p.startswith("0x") else p) for p in dep.get("preimages") or []]
    hashes = sorted({int.from_bytes(keccak256(b), "big") for b in pre})
    for b in pre:
        d = fams.get(int.from_bytes(b[-32:], "big")) if len(b) >= 32 else None
        if d is None:
            continue
        if len(b) != 64 or str(d.get("key") or "").strip() in DYNAMIC:
            continue        # not (key . slot) of a 32-byte key: a written entry of it is refused below (near a hash)
        if str(d.get("value") or "").strip().startswith("mapping"):
            continue                                    # a nested mapping: its entries are refused below
        base, k = int.from_bytes(keccak256(b), "big"), key_text(b[:32], d.get("key"))
        if d.get("fields"):
            made = []
            for f in d["fields"]:
                s = base + int(f["slot"])
                held.add(s)
                if put(d["name"] + "." + f["name"], _bits(storage.get(s, 0), f.get("offset", 0), f.get("width") or 256),
                       f.get("type")):
                    made.append(f["name"])
            if made:
                keys.setdefault(d["name"], {})[k] = made
        else:
            held.add(base)
            if put(d["name"], _bits(storage.get(base, 0), d.get("offset", 0), d.get("width") or 256), d.get("value")):
                keys.setdefault(d["name"], {})[k] = None
    loose = sorted(s for s in storage if s not in held)
    near = [s for s in loose if any(0 <= s - h < 256 for h in hashes)]
    if near:
        raise R0Error(f"{len(near)} written slot(s) lie in a mapping entry the rule does not read (a nested mapping, or "
                      f"a mapping inside a struct)")
    family = {d["name"] + "." + f["name"] for d in fams.values() for f in d.get("fields") or []}
    family |= {d["name"] for d in fams.values() if not d.get("fields")}
    values = {p: _sorted(({0} | ws) if p in family else ws) for p, ws in sorted(words.items())}
    return {"values": values, "keys": {f: dict(sorted(ks.items())) for f, ks in sorted(keys.items())},
            "proxy_slots": ["0x" + format(s, "064x") for s in loose]}


def _record_rel(milestone: str, doc_rel: str) -> str:
    return f"gen/{milestone}/binding/{BD.stem(doc_rel)}.json"


def build(milestone: str, root: Path, sidecar: str | None, model_sidecar: str | None) -> tuple[Path, str]:
    """(the sidecar's path, the bytes a run writes)."""
    root = Path(root).resolve()
    try:
        sc = C.Sidecar(milestone, root, sidecar)
    except C.Refused as e:
        raise R0Error(str(e)) from None
    if model_sidecar:
        mp = Path(model_sidecar)
        mp = mp if mp.is_absolute() else root / mp
    else:
        mp = TS.default_path(milestone, root)
    if not mp.is_file():
        raise R0Error(f"the typing sidecar {mp} does not exist")
    model_rel = TS.rel_of(mp, root)
    derived, provenance = None, []
    for d in sc.documents:
        rec_rel = _record_rel(milestone, d)
        rp = root / rec_rel
        if not rp.is_file():
            raise R0Error(f"{rec_rel} is missing: run `python -m holon binding --milestone {milestone}` first")
        doc, _h = sc.read_json(d)
        one = derive(doc, json.loads(rp.read_text(encoding="utf-8")))
        if derived is not None and one != derived:
            raise R0Error(f"the documents' derivations disagree ({d})")
        derived = one
        provenance.append({"document": d, "path": rec_rel, "sha256": _sha(rp)})
    out = dict(sc.doc)
    out["r0"] = {"doc": RULE, **derived, "derived_from": sorted(provenance, key=lambda x: x["document"])}
    out["model_sidecar"] = model_rel
    return sc.path, dump(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon disch-r0")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--sidecar", help="the DISCH sidecar (default spec/<M>/lib/disch.json)")
    ap.add_argument("--model-sidecar", help="the typing sidecar it names (default spec/<M>/lib/sort_types.json)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    try:
        path, text = build(a.milestone, Path(a.root), a.sidecar, a.model_sidecar)
    except (R0Error, OSError, ValueError, KeyError) as e:
        print(f"holon disch-r0: refused: {e}", file=sys.stderr)
        return 2
    rel = path.relative_to(Path(a.root).resolve()).as_posix() if path.is_relative_to(Path(a.root).resolve()) else path
    if a.check:
        if path.read_text(encoding="utf-8") == text:
            print(f"holon disch-r0: {rel} reproduced (r0 and model_sidecar from the deployment records)")
            return 0
        old, new = json.loads(path.read_text(encoding="utf-8")), json.loads(text)
        bad = [k for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k)] or ["formatting"]
        print(f"holon disch-r0: {rel} differs from a fresh derivation: {', '.join(bad)}")
        return 1
    path.write_text(text, encoding="utf-8")
    print(f"holon disch-r0: wrote {rel} (r0 and model_sidecar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
