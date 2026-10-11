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
maps to the datatype that declares it), closed over the BendTT graph.

Files:
  gen/<m>/model/<model>.defs.json   kernel index: definition -> {sha256, refs}   (generated, G1)
  results/<m>/deps.json             definition -> laws whose cone contains it   (generated, G1)
  spec/bindings/<m>.json            law -> {statement_hash, model, cone: {def: sha256}}
  spec/bindings/changes.jsonl       append-only log of accepted binding changes
`python -m holon bind` writes a missing bindings file, and changes an existing one only
with --accept-change "<reason>" (self-certified until the statement lifecycle, I10, and
the human's freeze, Q1). Gate G2 re-derives the bindings from the committed models.
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

_ENTRY = re.compile(r"^(\S+) : ", re.M)
_QNAME = re.compile(r"(?<![\w.])([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)")
_TAG = re.compile(r"(?<![\w])\.([A-Za-z_][A-Za-z0-9_]*)")
_ENUM = re.compile(r"<([A-Za-z0-9_, ]+)>")
_QUAL = re.compile(r"(?<![\w.])M\.([A-Za-z_][A-Za-z0-9_]*)")


class BindingError(Exception):
    pass


# ---------------------------------------------------------------- kernel form
def bendtt_text(model: Path, cfg: dict | None = None) -> str:
    model = Path(model)
    tmp = Path(tempfile.mkdtemp(prefix="holon-bendtt-"))
    try:
        src = tmp / model.name
        shutil.copy(model, src)
        r = bend.run([src.name, "-o", src.with_suffix(".bendtt").name], cwd=tmp, cfg=cfg)
        out = src.with_suffix(".bendtt")
        if r.code != 0 or not out.exists():
            raise BindingError(f"bend could not translate {model} to BendTT: {r.out[:1500]}")
        return out.read_text()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@lru_cache(maxsize=None)
def _entries_cached(model_text: str, cfg_json: str) -> tuple:
    tmp = Path(tempfile.mkdtemp(prefix="holon-bendtt-src-"))
    try:
        f = tmp / "model.bend"
        f.write_text(model_text)
        text = bendtt_text(f, json.loads(cfg_json) if cfg_json else None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return tuple(sorted(parse_entries(text).items()))


def kernel_entries(model: Path, cfg: dict | None = None) -> dict[str, str]:
    """BendTT entry name -> its full text (type and body), for a model file."""
    return dict(_entries_cached(Path(model).read_text(), json.dumps(cfg, sort_keys=True) if cfg else ""))


def parse_entries(text: str) -> dict[str, str]:
    ms = list(_ENTRY.finditer(text))
    out = {}
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out[m.group(1)] = text[m.start():end].strip() + "\n"
    return out


def tag_owner(entries: dict[str, str]) -> dict[str, str]:
    """Constructor tag -> the datatype whose enumeration declares it."""
    own = {}
    for name, text in entries.items():
        head = text.split("=", 1)[0]
        if not re.search(r":\s*\*\(", head):
            continue
        for m in _ENUM.finditer(text):
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


def kernel_cone(statement_text: str, entries: dict[str, str]) -> list[str]:
    own = tag_owner(entries)
    g = kernel_graph(entries)
    roots = set()
    for tok in _QUAL.findall(re.sub(r"#[^\n]*", "", statement_text)):
        if tok in entries:
            roots.add(tok)
        elif tok in own:
            roots.add(own[tok])
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


def statement_text(law: dict, m: str, root: Path) -> str:
    """The emitted frozen statement (never a counter-law), as the pipelines emit it."""
    fp = root / law_facts(law, m, root)
    if law["ir_version"] == "holon-ir/0.1":
        from .gen import laws as LG
        try:
            return LG.emit(law, F.load(fp), "../model/m.bend").text
        except LG.Unsupported:
            return records.ir_roots_text(law)
    from .gen import mlaws
    from .gen.machine import Machine
    try:
        return mlaws.Emitter(Machine(F.load(fp))).emit(law, "../model/m.bend").text
    except mlaws.Unsupported:
        return records.ir_roots_text(law)


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
                              "cone": {d: hashlib.sha256(entries[d].encode()).hexdigest() for d in c}}
    return {"milestone": m, "kernel": "bendtt", "laws": out}


def dependents(bound: dict) -> dict:
    deps: dict[str, list[str]] = {}
    for lid, x in sorted(bound["laws"].items()):
        for d in x["cone"]:
            deps.setdefault(d, []).append(lid)
    return {"milestone": bound["milestone"], "dependents": {d: sorted(ls) for d, ls in sorted(deps.items())}}


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
        if x["statement_hash"] != y["statement_hash"]:
            laws.add(lid)
            msgs.append(f"{lid}: statement hash differs from its binding")
        ch = sorted(d for d in set(x["cone"]) | set(y["cone"]) if x["cone"].get(d) != y["cone"].get(d))
        if ch:
            laws.add(lid)
            defs.update(ch)
            msgs.append(f"{lid}: meaning changed in {', '.join(ch[:8])}{' ...' if len(ch) > 8 else ''}")
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
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(dump(new))
        print(f"wrote {p.relative_to(root)}: {len(new['laws'])} laws bound")
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
    log = root / CHANGES
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as fh:
        fh.write(json.dumps({"milestone": m, "laws": laws, "defs": defs, "reason": reason}, sort_keys=True) + "\n")
    p.write_text(dump(new))
    print(f"rebound {len(laws)} laws in {p.relative_to(root)}; logged in {CHANGES}")
    return 0
