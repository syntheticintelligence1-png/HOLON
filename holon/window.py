"""The window view of an extracted model: the hand abstraction's state fields expressed over raw storage families
(I20; whitepaper §8.7, §10.1; BUILD_PLAN I20 "plus a window view where declared"). The contract is clause 1 of the
docstring of tests_m2/test_extracted_refinement.py: the raw-family model is authoritative; when the window view
disagrees with the hand abstraction on a corpus state, both are reported in window_check.json.

A window declaration is a sidecar spec/<M>/lib/window_*.json naming the transitions document it views ("facts") and the
holon-facts/0.2 hand abstraction ("abstraction"):

  {"window_version": "holon-window/0.1", "doc", "facts": "<transitions document>", "abstraction": "<0.2 facts>",
   "corpus": "<corpus states file>" | null,
   "fields": {"<abstraction state field>": <mapping>}}

  mapping   {"term": T}                     a term of the extracted language over raw storage (holon.extracted_eval),
            {"list": {"from": T, "to": T, "item": I}}      the items at k = from..to (inclusive),
            {"residue": {"after": T, "item": I, "bound": n}} the items at k = after+1, .. while some item field is
                                            non-zero (at most n),
            {"external": "<contract or interface>", "reason"}   state another contract holds (reached by call),
            {"env": "<global>", "reason"}   the environment (block.timestamp, ..),
            {"observations": "<reason>"}    the abstraction's record of step outcomes, not storage,
            {"unmapped": "<reason>"}        a field the raw families do not determine;
  item I    a term over ["var", "k"], or {"record": {"<record field>": <mapping of a term over ["var", "k"]>}};
  any mapping may carry "decode": {"sub": n} | {"table": {"<raw value as 0x-hex>": value}}, applied to the raw value
            before it is compared (the abstraction's token encodings).

Ghost fields (the abstraction's ghost_state, and the "ghost" fields of its record types) have no raw family by
definition; a declaration must not map them. Nothing here names a target: names come from the declaration and the
documents.

  declaration_for(model, root)          the declaration that names model's document, or None
  classify(model, decl, abstraction)    every abstraction state field and record field with its kind (mapped,
                                        state_unmapped, external, ghost) and every raw family no mapping reads
                                        (family_unmapped): the input of holon.differential's deltas
  view(model, decl, raw)                the abstraction fields the declaration maps, evaluated on raw storage
  check(model, decl, root)              window_check.json: {"states", "disagreements", ...} over the corpus states
  corpus_states(...)                    the corpus-states document from (abstract trace, raw states) pairs
"""
from __future__ import annotations

import json
from pathlib import Path

from . import extracted_eval as X

ROOT = Path(__file__).resolve().parents[1]
WINDOW_VERSION = "holon-window/0.1"
CORPUS_VERSION = "holon-corpus-states/0.1"
MAX_ITEMS = 4096
KINDS = ("term", "list", "residue", "external", "env", "observations", "unmapped")


class WindowError(ValueError):
    pass


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


# ------------------------------------------------------------------------------------------------ declarations
def declarations(root=None) -> list[tuple[Path, dict]]:
    root = Path(root or ROOT)
    out = []
    for p in sorted(root.glob("spec/*/lib/window_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            raise WindowError(f"{p}: not JSON: {e}") from e
        if isinstance(d, dict) and d.get("window_version") == WINDOW_VERSION:
            out.append((p, d))
    return out


def declaration_for(model, root=None) -> dict | None:
    """The declaration whose "facts" is the model's document (repo-relative), or None. Two are an error."""
    rel = model.path.as_posix() if getattr(model, "path", None) else None
    hits = [(p, d) for p, d in declarations(root) if d.get("facts") == rel]
    if len(hits) > 1:
        raise WindowError(f"{len(hits)} window declarations name {rel}: {[str(p) for p, _ in hits]}")
    if not hits:
        return None
    p, d = hits[0]
    validate(d, p)
    return dict(d, _path=p.relative_to(Path(root or ROOT)).as_posix())


def validate(d: dict, where="declaration") -> None:
    bad = []
    for k in ("facts", "abstraction", "fields"):
        if k not in d:
            bad.append(f"no {k!r}")
    for name, mp in sorted((d.get("fields") or {}).items()):
        if not isinstance(mp, dict) or len([k for k in KINDS if k in mp]) != 1:
            bad.append(f"field {name}: a mapping has exactly one of {', '.join(KINDS)}")
    if bad:
        raise WindowError(f"{where}: " + "; ".join(bad))


def load_abstraction(decl: dict, root=None) -> dict:
    p = Path(root or ROOT) / decl["abstraction"]
    facts = json.loads(p.read_text(encoding="utf-8"))
    if facts.get("facts_version") != "holon-facts/0.2":
        raise WindowError(f"{decl['abstraction']}: the abstraction is not a holon-facts/0.2 document")
    return facts


def ghosts(facts: dict) -> tuple[set, dict]:
    """(ghost state fields, record type -> ghost fields) of a holon-facts/0.2 document."""
    state = set(facts.get("ghost_state") or [])
    recs = {t: set(spec.get("ghost") or []) for t, spec in (facts.get("types") or {}).items() if isinstance(spec, dict)}
    return state, {t: g for t, g in recs.items() if g}


def _record_of(facts: dict, field: str) -> str | None:
    """The record type of a List<Record> state field."""
    for f in facts.get("state") or []:
        if f[0] == field:
            ty = f[1]
            if ty.startswith("List<") and ty[5:-1] in (facts.get("types") or {}):
                return ty[5:-1]
            if ty in (facts.get("types") or {}):
                return ty
    return None


# ------------------------------------------------------------------------------------------------ classification
def _storage_in(t, acc: set) -> None:
    if isinstance(t, list):
        if len(t) == 2 and t[0] == "storage" and isinstance(t[1], str):
            acc.add(t[1])
        for x in t:
            _storage_in(x, acc)
    elif isinstance(t, dict):
        for x in t.values():
            _storage_in(x, acc)


def _kind(mp: dict) -> str:
    return next(k for k in KINDS if k in mp)


def classify(model, decl: dict, facts: dict) -> dict:
    """{"fields": [{"field", "record"?, "kind": mapped|state_unmapped|external|ghost, "reason"}],
        "families": {"read": [..], "unmapped": [..]}} (module docstring)."""
    gstate, grec = ghosts(facts)
    fields = decl.get("fields") or {}
    out = []
    for f in facts.get("state") or []:
        name = f[0]
        mp = fields.get(name)
        rec = _record_of(facts, name)
        if name in gstate:
            if mp is not None:
                raise WindowError(f"field {name} is a ghost field of the abstraction: a declaration must not map it")
            out.append({"field": name, "kind": "ghost", "reason": "a ghost field of the abstraction (no raw family)"})
            continue
        if mp is None:
            out.append({"field": name, "kind": "state_unmapped", "reason": "the declaration does not map it"})
            continue
        k = _kind(mp)
        if k == "external":
            out.append({"field": name, "kind": "external",
                        "reason": f"held by {mp['external']}" + (f": {mp['reason']}" if mp.get("reason") else "")})
        elif k in ("env", "observations", "unmapped"):
            why = {"env": f"the environment ({mp.get('env')})", "observations": "the record of step outcomes",
                   "unmapped": "not determined by the raw families"}[k]
            out.append({"field": name, "kind": "state_unmapped",
                        "reason": why + (f": {mp.get('reason') or mp.get(k)}" if k != "env" or mp.get("reason") else "")})
        else:
            out.append({"field": name, "kind": "mapped", "reason": k})
        # record fields of a list field
        if rec is not None:
            item = (mp.get("list") or mp.get("residue") or {}).get("item") if k in ("list", "residue") else None
            sub = (item or {}).get("record") if isinstance(item, dict) else None
            for rf, _rt in (facts.get("types") or {}).get(rec, {}).get("fields") or []:
                if rf in grec.get(rec, set()):
                    if sub and rf in sub:
                        raise WindowError(f"{rec}.{rf} is a ghost field: a declaration must not map it")
                    out.append({"field": rf, "record": rec, "kind": "ghost",
                                "reason": f"a ghost field of {rec} (no raw family)"})
                    continue
                if k in ("external", "env", "observations", "unmapped"):
                    continue    # the whole field is classified above
                smp = (sub or {}).get(rf)
                if smp is None:
                    out.append({"field": rf, "record": rec, "kind": "state_unmapped",
                                "reason": f"the declaration does not map {rec}.{rf} under {name}"})
                    continue
                sk = _kind(smp)
                if sk == "external":
                    out.append({"field": rf, "record": rec, "kind": "external", "reason": f"held by {smp['external']}"})
                elif sk != "term":
                    out.append({"field": rf, "record": rec, "kind": "state_unmapped",
                                "reason": smp.get(sk) if isinstance(smp.get(sk), str) else sk})
                else:
                    out.append({"field": rf, "record": rec, "kind": "mapped", "reason": "term"})
    read: set = set()
    _storage_in(fields, read)
    fams = sorted(model.families)
    uniq, seen = [], set()
    for x in out:
        key = (x.get("record"), x["field"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(x)
    return {"fields": uniq, "families": {"read": sorted(read & set(fams)),
                                         "unknown": sorted(read - set(fams)),
                                         "unmapped": sorted(set(fams) - read)}}


# ------------------------------------------------------------------------------------------------ the view
class _View(X.Eval):
    def __init__(self, model, raw: dict):
        super().__init__(model, raw, next(iter(sorted(model.actions))), {}, {})
        self.subst_heads.add("var")


def _decode(v, mp: dict):
    d = mp.get("decode")
    if not d or not isinstance(v, int):
        return v
    if "sub" in d:
        return v - int(d["sub"]) if v else 0     # zero stays zero: an absent key of a mapping
    if "div" in d:
        return v // int(d["div"])
    if "table" in d:
        return d["table"].get("0x%x" % v, d["table"].get(str(v), {"undecoded": "0x%x" % v}))
    return v


def _item(e: _View, item, k: int):
    key = X.canonical(["var", "k"])
    e.subst[key] = k
    try:
        if isinstance(item, dict) and "record" in item:
            out = {}
            for rf, smp in sorted(item["record"].items()):
                if "term" in smp:
                    out[rf] = _decode(_word(e, smp["term"]), smp)
            return out
        return _decode(_word(e, item), {})
    finally:
        e.subst.pop(key, None)


def _word(e: _View, t):
    v = e.value(e.ev(t))
    return e.as_int(v) if not isinstance(v, dict) else v


def view(model, decl: dict, raw: dict) -> dict:
    """{field: value | {"unsupported": reason}} for every field the declaration maps from raw storage."""
    e = _View(model, raw)
    out = {}
    for name, mp in sorted((decl.get("fields") or {}).items()):
        k = _kind(mp)
        try:
            if k == "term":
                out[name] = _decode(_word(e, mp["term"]), mp)
            elif k == "list":
                spec = mp["list"]
                lo, hi = e.iv(spec["from"]), e.iv(spec["to"])
                if hi + 1 - lo > MAX_ITEMS:
                    raise X.Unsupported(f"{hi + 1 - lo} items (more than {MAX_ITEMS})")
                out[name] = [_item(e, spec["item"], kk) for kk in range(lo, hi + 1)]
            elif k == "residue":
                spec = mp["residue"]
                after = e.iv(spec["after"])
                items = []
                for kk in range(after + 1, after + 1 + int(spec.get("bound", 64))):
                    it = _item(e, spec["item"], kk)
                    if not _nonzero(it):
                        break
                    items.append(it)
                out[name] = items
        except X.Unsupported as x:
            out[name] = {"unsupported": str(x)}
    return out


def _nonzero(v) -> bool:
    if isinstance(v, dict):
        return any(_nonzero(x) for x in v.values())
    if isinstance(v, list):
        return any(_nonzero(x) for x in v)
    return bool(v)


def _norm_abs(v):
    """An abstraction value as machine.mjs decodes it, comparable with the view: booleans as 0/1, records without
    their constructor tag."""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, list):
        return [_norm_abs(x) for x in v]
    if isinstance(v, dict):
        return {k: _norm_abs(x) for k, x in v.items() if k != "$"}
    return v


def apply_decode(vw: dict, decode: dict) -> dict:
    """The corpus producer's token encodings ({"<field>" | "<field>.<record field>": decode}) applied to a view."""
    if not decode:
        return vw
    out = {}
    for name, v in vw.items():
        if isinstance(v, list):
            out[name] = [{rf: _decode(x, {"decode": decode.get(f"{name}.{rf}")}) for rf, x in it.items()}
                         if isinstance(it, dict) else _decode(it, {"decode": decode.get(name)}) for it in v]
        else:
            out[name] = _decode(v, {"decode": decode.get(name)}) if not isinstance(v, dict) else v
    return out


def _trim(xs: list) -> list:
    """A list of mapping values without trailing zero items (a mapping reads 0 at every absent key)."""
    xs = list(xs)
    while xs and not _nonzero(xs[-1]):
        xs.pop()
    return xs


def compare(vw: dict, abstract: dict, decl: dict | None = None) -> list[dict]:
    """The differences between a view and the abstraction's state, over what the view maps."""
    out = []
    for name in sorted(vw):
        got, want = vw[name], _norm_abs(abstract.get(name))
        if isinstance(got, dict) and "unsupported" in got:
            out.append({"field": name, "window": got, "abstraction": want})
            continue
        if isinstance(got, list):
            if not isinstance(want, list):
                out.append({"field": name, "window": got, "abstraction": want})
                continue
            mp = ((decl or {}).get("fields") or {}).get(name) or {}
            keys = set().union(*[set(g) for g in got if isinstance(g, dict)]) if got else set()
            if keys:
                want = [{k: v for k, v in w.items() if k in keys} if isinstance(w, dict) else w for w in want]
            if "residue" in mp or (mp.get("list") or {}).get("trim"):
                got, want = _trim(got), _trim(want)
            if len(got) != len(want):
                out.append({"field": name, "window": {"length": len(got)}, "abstraction": {"length": len(want)}})
            for i, (g, w) in enumerate(zip(got, want)):
                if isinstance(g, dict):
                    for rf in sorted(g):
                        if g[rf] != (w or {}).get(rf):
                            out.append({"field": f"{name}[{i}].{rf}", "window": g[rf],
                                        "abstraction": (w or {}).get(rf)})
                elif g != w:
                    out.append({"field": f"{name}[{i}]", "window": g, "abstraction": w})
            continue
        if got != want:
            out.append({"field": name, "window": got, "abstraction": want})
    return out


def check(model, decl: dict, root=None) -> dict:
    """window_check.json (module docstring): every corpus state of the declaration's corpus file, its view against the
    abstraction's state. Without a corpus file, states is 0 and "corpus" says why."""
    root = Path(root or ROOT)
    facts = load_abstraction(decl, root)
    cls = classify(model, decl, facts)
    out = {"document": "window_check", "window_version": WINDOW_VERSION, "declaration": decl.get("_path"),
           "facts": decl["facts"], "abstraction": decl["abstraction"], "classification": cls,
           "states": 0, "compared": 0, "disagreements": []}
    cp = decl.get("corpus")
    if not cp or not (root / cp).is_file():
        out["corpus"] = {"path": cp, "note": "no corpus states file: nothing compared"}
        return out
    data = (root / cp).read_bytes()
    corpus = json.loads(data.decode("utf-8"))
    if corpus.get("corpus_version") != CORPUS_VERSION or corpus.get("facts") != decl["facts"]:
        raise WindowError(f"{cp}: not a {CORPUS_VERSION} corpus of {decl['facts']}")
    import hashlib
    out["corpus"] = {"path": cp, "sha256": hashlib.sha256(data).hexdigest()}
    n = 0
    dec = corpus.get("decode") or {}
    for st in corpus.get("states") or []:
        vw = apply_decode(view(model, decl, st.get("raw") or {}), dec)
        n += len(vw)
        for d in compare(vw, st.get("abstract") or {}, decl):
            out["disagreements"].append(dict(d, state=st.get("id")))
    out["states"] = len(corpus.get("states") or [])
    out["compared"] = n
    return out


def corpus_states(facts_rel: str, items: list[dict], decode: dict | None = None) -> dict:
    """The corpus-states document of (id, raw storage, abstraction state) items, sorted by id: the input of check.
    decode: the producer's token encodings ({"<field>" | "<field>.<record field>": {"sub": n} | {"table": {..}}})."""
    rows = [{"id": str(it["id"]), "raw": {X.h32(X.to_int(k)): X.h32(X.to_int(v)) for k, v in
                                          sorted((it.get("raw") or {}).items(), key=lambda kv: X.to_int(kv[0]))
                                          if X.to_int(v)},
             "abstract": it.get("abstract") or {}} for it in items]
    return {"corpus_version": CORPUS_VERSION, "facts": facts_rel, "decode": dict(sorted((decode or {}).items())),
            "states": sorted(rows, key=lambda r: r["id"])}


def abstract_states(cm, traces: list[list[dict]]) -> list[list]:
    """The abstraction's state after every step of each trace (holon.mreplay's trace rows: {"op", inputs..}), on its
    compiled model (holon.mpipeline.CompiledMachine, through machine.mjs). Pseudo-steps (migrations) are applied and
    give their state too."""
    from .mpipeline import _act_val
    calls, shape = [], []
    for tr in traces:
        expr = {"fn": "s0", "args": []}
        n = 0
        for a in tr:
            if a["op"].startswith("@"):
                for name, mg in cm.facts.get("migrations", {}).items():
                    expr = {"fn": "mig_" + name, "args": [expr] + [{"val": a[nm]} for nm, _ in mg.get("inputs", [])]}
            else:
                expr = {"fn": "step", "args": [{"val": _act_val(cm.m, a)}, expr]}
            calls.append(expr)
            n += 1
        shape.append(n)
    res = cm.calls(calls, instances=True) if calls else []
    out, i = [], 0
    for n in shape:
        out.append(res[i:i + n])
        i += n
    return out
