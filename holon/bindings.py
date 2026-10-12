"""Semantic bindings (whitepaper §8.9 references by hash, §9.4 stale propagation, L22).

A frozen statement's hash covers its IR and the facts hash, not the model definitions
it calls (generator names such as `perm` or `no_code`, the observers, the `b_*`
builtins). The bindings close that gap: each law is bound to the sha256 of the *kernel
form* of every definition its statement reaches.

The kernel form comes from the pinned checker itself: `bend model.bend -o model.bendtt`
writes the BendTT translation of every definition and datatype the model uses (Base
definitions included), alpha-normalized (locals become x0, x1, ...), with every global
reference resolved. So:
  * the dependency graph is the elaborator's, not a reading of HOLON's own text;
  * renaming a local or editing a comment changes no entry, so it binds the same;
  * any change of meaning in a reached definition changes its entry, so the binding
    fails and names exactly the laws whose cone contains it (results/<m>/deps.json).

Roots of a law: the `M.<name>` references of its emitted frozen statement (a constructor
maps to the datatype that declares it), closed over the BendTT graph. An `M.` reference
that resolves to nothing, a definition BendTT leaves out of scope, an empty cone, or a
model definition named like a BendTT local (x<digits>) is an error, never a silent gap.

A binding also pins what the emitter prints: the sha256 of the emitted statement and of the
emitted counter-law (comment lines removed). They include the law-local definitions the
cone cannot see (pin_h, the View types and projections), so an emitter change that adds,
drops or alters a premise, a quantifier or the erased fields fails G2 even when the IR and
the model are unchanged. (BUILD_PLAN I2 also listed generator_sha256 in each binding; it is
not bound: a refactor that emits identical text changes no meaning, and the records carry
it for G1.)

Files:
  gen/<m>/model/<model>.defs.json   kernel index: definition -> {sha256, refs}   (generated, G1)
  results/<m>/deps.json             model -> definition -> laws whose cone contains it (generated,
                                    G1); "dependents" is the same index by bare name, which merges
                                    same-named definitions of different models
  spec/bindings/<m>.json            law -> {statement_hash, model, statement_sha256, counter_sha256,
                                    cone: {def: sha256}}
  spec/bindings/changes.jsonl       append-only log of every write: creations and accepted changes
`python -m holon bind` writes a missing bindings file (logging the creation), and changes an
existing one only with --accept-change "<reason>". Gate G2 re-derives the bindings from the
committed models. All of this is self-certified until the statement lifecycle (I10) and the
human's freeze (Q1): spec/bindings is agent-writable, so deleting or hand-editing it cannot
be blocked before then.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

from . import bend, ir, records
from . import facts as F

ROOT = Path(__file__).resolve().parents[1]
BINDINGS_DIR = Path("spec") / "bindings"
CHANGES = BINDINGS_DIR / "changes.jsonl"

_ENTRY = re.compile(r"^(?:opaque )?(\S+) : ", re.M)
_QNAME = re.compile(r"(?<![\w.])([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)")
_TAG = re.compile(r"(?<![\w])\.([A-Za-z_][A-Za-z0-9_]*)")
_QUAL = re.compile(r"(?<![\w.])M\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)")
_LOCAL = re.compile(r"^x[0-9]+$")
_DTYPE_ENUM = re.compile(r"=\s*Σx[0-9]+ : <([A-Za-z0-9_, ]+)>")


class BindingError(Exception):
    pass


# ---------------------------------------------------------------- kernel form
def bendtt_text(model: Path, cfg: dict | None = None, shown: str | None = None) -> str:
    model = Path(model)
    shown = shown or model.name
    tmp = Path(tempfile.mkdtemp(prefix="holon-bendtt-"))
    try:
        src = tmp / model.name
        shutil.copy(model, src)
        r = bend.run([src.name, "-o", src.with_suffix(".bendtt").name], cwd=tmp, cfg=cfg)
        out = src.with_suffix(".bendtt")
        if r.code != 0 or not out.exists():
            raise BindingError(f"bend could not translate {shown} to BendTT: {r.out[:1500]}")
        if "out of scope" in r.out:
            raise BindingError(f"BendTT left definitions of {shown} out of scope (they would be unbound): "
                               f"{r.out[:800]}")
        return out.read_text()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@lru_cache(maxsize=None)
def _entries_cached(model_text: str, cfg_json: str, shown: str) -> tuple:
    tmp = Path(tempfile.mkdtemp(prefix="holon-bendtt-src-"))
    try:
        f = tmp / "model.bend"
        f.write_text(model_text)
        text = bendtt_text(f, json.loads(cfg_json) if cfg_json else None, shown)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    entries = parse_entries(text, shown)
    bad = sorted(n for n in entries if _LOCAL.match(n))
    if bad:
        raise BindingError(f"{shown}: definitions named like BendTT locals ({bad}) would rename every local of "
                           "the translation and change every binding")
    return tuple(sorted(entries.items()))


def kernel_entries(model: Path, cfg: dict | None = None) -> dict[str, str]:
    """BendTT entry name -> its full text (type and body), for a model file."""
    model = Path(model)
    try:
        shown = model.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        shown = model.name
    return dict(_entries_cached(model.read_text(), json.dumps(cfg, sort_keys=True) if cfg else "", shown))


def parse_entries(text: str, shown: str = "BendTT text") -> dict[str, str]:
    ms = list(_ENTRY.finditer(text))
    if text[:ms[0].start() if ms else len(text)].strip():
        raise BindingError(f"{shown}: unexpected text before the first BendTT entry")
    for line in text.splitlines():
        if line and not line[0].isspace() and not _ENTRY.match(line + " "):
            raise BindingError(f"{shown}: unrecognised BendTT line {line[:80]!r}")
    out = {}
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out[m.group(1)] = text[m.start():end].strip() + "\n"
    return out


def tag_owner(entries: dict[str, str]) -> dict[str, str]:
    """Constructor tag -> the datatype whose body (`= Σx : <tags> -> ...`) enumerates it."""
    own = {}
    for name, text in entries.items():
        for m in _DTYPE_ENUM.finditer(text):
            for tag in (t.strip() for t in m.group(1).split(",")):
                if tag:
                    own.setdefault(tag, name)
    return own


def kernel_graph(entries: dict[str, str]) -> dict[str, list[str]]:
    own = tag_owner(entries)
    g = {}
    for name, text in entries.items():
        body = text[len(name):]
        refs = {t for t in _QNAME.findall(body) if t in entries and t != name}
        refs |= {own[t] for t in _TAG.findall(body) if t in own and own[t] != name}
        g[name] = sorted(refs)
    return g


def defs_index(model: Path, cfg: dict | None = None) -> dict:
    entries = kernel_entries(model, cfg)
    g = kernel_graph(entries)
    return {"model": Path(model).stem, "kernel": "bendtt",
            "defs": {n: {"sha256": hashlib.sha256(t.encode()).hexdigest(), "refs": g[n]} for n, t in sorted(entries.items())}}


def _resolve_root(tok: str, entries: dict[str, str], own: dict[str, str]) -> str | None:
    """The longest dotted prefix that names a kernel entry, else a constructor's datatype."""
    parts = tok.split(".")
    for k in range(len(parts), 0, -1):
        name = ".".join(parts[:k])
        if name in entries:
            return name
    return own.get(parts[0])


def kernel_cone(statement_text: str, entries: dict[str, str]) -> list[str]:
    own = tag_owner(entries)
    g = kernel_graph(entries)
    roots = set()
    for tok in _QUAL.findall(re.sub(r"#[^\n]*", "", statement_text)):
        r = _resolve_root(tok, entries, own)
        if r is None:
            raise BindingError(f"M.{tok} in the statement resolves to no kernel entry: it would be unbound")
        roots.add(r)
    if not roots:
        raise BindingError("the statement names no model definition: an empty cone binds nothing")
    seen, todo = set(), sorted(roots)
    while todo:
        d = todo.pop()
        if d not in seen:
            seen.add(d)
            todo.extend(x for x in g[d] if x not in seen)
    return sorted(seen)


# ---------------------------------------------------------------- statements and models
def registry_facts(m: str, root: Path) -> str:
    return ir.load_registry(m, root).get("facts", "facts/morph_header.json")


def law_facts(law: dict, m: str, root: Path) -> str:
    return law.get("facts") or registry_facts(m, root)


def model_path(law: dict, m: str, root: Path) -> Path:
    from .model_eval import model_name
    return root / "gen" / m / "model" / f"{model_name(law_facts(law, m, root))}.bend"


def _emit(law: dict, m: str, root: Path, counter: bool) -> str | None:
    """The emitter's text for a law (statement or counter-law), as the pipelines emit it;
    None when the emitter cannot express that form."""
    from .model_eval import model_name
    from .mpipeline import layout
    fp = root / law_facts(law, m, root)
    imp = f"{layout(m, root, law['law_id'])[2]}model/{model_name(fp)}.bend"   # as the pipelines import it (I10)
    if law["ir_version"] == "holon-ir/0.1":
        from .gen import laws as LG
        try:
            return LG.emit(law, F.load(fp), imp, counter=counter, header_note=ir.statement_hash(law)).text
        except LG.Unsupported:
            return None
    from .gen import mlaws
    from .gen.machine import Machine
    from .gen.oracles import Oracles
    from .mpipeline import m2plus
    orc = Oracles.for_facts(fp) if m2plus(m) else None   # M2+ models take their oracles as parameters (I12)
    try:
        return mlaws.Emitter(Machine(F.load(fp), fp, oracles=orc)).emit(law, imp, counter=counter,
                                                                        note=ir.statement_hash(law)).text
    except mlaws.Unsupported:
        return None


def statement_text(law: dict, m: str, root: Path) -> str:
    """The emitted frozen statement (never a counter-law), or the IR's names when it is inexpressible."""
    t = _emit(law, m, root, counter=False)
    return t if t is not None else records.ir_roots_text(law)


def text_sha256(text: str | None) -> str | None:
    if text is None:
        return None
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    return hashlib.sha256(body.encode()).hexdigest()


def model_definitions(m: str, rec: dict, root: Path = ROOT) -> set[str]:
    """Names defined in the model file itself (def and type), as opposed to Base."""
    p = Path(rec["artifacts"]["model"])
    p = p if p.is_absolute() else Path(root) / p
    return set(records.model_defs(p.read_text()))


# ---------------------------------------------------------------- derive, compare, write
def derive(m: str, root: Path | str = ROOT, cfg: dict | None = None) -> dict:
    root = Path(root)
    cfg = cfg or bend.config(root)
    out = {}
    for law in ir.load_laws_any(m, root):
        mp = model_path(law, m, root)
        entries = kernel_entries(mp, cfg)
        c = kernel_cone(statement_text(law, m, root), entries)
        out[law["law_id"]] = {"statement_hash": ir.statement_hash(law), "model": mp.relative_to(root).as_posix(),
                              "statement_sha256": text_sha256(_emit(law, m, root, counter=False)),
                              "counter_sha256": text_sha256(_emit(law, m, root, counter=True)),
                              "cone": {d: hashlib.sha256(entries[d].encode()).hexdigest() for d in c}}
    return {"milestone": m, "kernel": "bendtt", "laws": out}


def dependents(bound: dict) -> dict:
    """bound: {"milestone", "laws": {law: {"model": name, "cone": [defs]}}}."""
    flat: dict[str, set] = {}
    by_model: dict[str, dict[str, set]] = {}
    for lid, x in sorted(bound["laws"].items()):
        for d in x["cone"]:
            flat.setdefault(d, set()).add(lid)
            by_model.setdefault(x["model"], {}).setdefault(d, set()).add(lid)
    return {"milestone": bound["milestone"],
            "dependents": {d: sorted(ls) for d, ls in sorted(flat.items())},
            "dependents_by_model": {mdl: {d: sorted(ls) for d, ls in sorted(ds.items())}
                                    for mdl, ds in sorted(by_model.items())}}


def diff(old: dict, new: dict) -> tuple[list[str], list[str], list[str]]:
    """(changed laws, changed definitions, problems as text)."""
    laws, defs, msgs = set(), set(), []
    a, b = old.get("laws", {}), new.get("laws", {})
    for lid in sorted(set(a) | set(b)):
        if lid not in a or lid not in b:
            laws.add(lid)
            msgs.append(f"{lid}: {'not bound' if lid not in a else 'bound but no longer a law'}")
            continue
        x, y = a[lid], b[lid]
        for key, what in (("statement_hash", "statement hash"), ("statement_sha256", "emitted statement"),
                          ("counter_sha256", "emitted counter-law"), ("model", "model file")):
            if x.get(key) != y.get(key):
                laws.add(lid)
                msgs.append(f"{lid}: {what} differs from its binding")
        changed = sorted(d for d in set(x["cone"]) & set(y["cone"]) if x["cone"][d] != y["cone"][d])
        gone = sorted(set(x["cone"]) - set(y["cone"]))
        new = sorted(set(y["cone"]) - set(x["cone"]))
        for ds, what in ((changed, "meaning changed in"), (gone, "no longer reaches"), (new, "now also reaches")):
            if ds:
                laws.add(lid)
                defs.update(ds)
                msgs.append(f"{lid}: {what} {', '.join(ds[:8])}{' ...' if len(ds) > 8 else ''}")
    return sorted(laws), sorted(defs), msgs


def path(m: str, root: Path) -> Path:
    return Path(root) / BINDINGS_DIR / f"{m}.json"


def dump(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True) + "\n"


def main_bind(args) -> int:
    root = Path(getattr(args, "root", None) or ROOT).resolve()
    m = args.milestone
    new = derive(m, root)
    p = path(m, root)
    log = root / CHANGES
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(dump(new))
        with log.open("a") as fh:
            fh.write(json.dumps({"milestone": m, "created": True, "laws": sorted(new["laws"]),
                                 "reason": getattr(args, "accept_change", None) or "initial binding"},
                                sort_keys=True) + "\n")
        print(f"wrote {p.relative_to(root)}: {len(new['laws'])} laws bound (logged in {CHANGES})")
        return 0
    old = json.loads(p.read_text())
    laws, defs, msgs = diff(old, new)
    if not laws:
        print(f"{p.relative_to(root)}: bindings unchanged")
        return 0
    for line in msgs:
        print(line)
    reason = getattr(args, "accept_change", None)
    if not reason:
        print(f"refusing to rebind {len(laws)} laws: give --accept-change \"<reason>\" (logged in {CHANGES})",
              file=sys.stderr)
        return 1
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as fh:
        fh.write(json.dumps({"milestone": m, "laws": laws, "defs": defs, "reason": reason}, sort_keys=True) + "\n")
    p.write_text(dump(new))
    print(f"rebound {len(laws)} laws in {p.relative_to(root)}; logged in {CHANGES}")
    return 0
