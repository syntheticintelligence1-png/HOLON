"""The M1-laws differential on the extracted model (I20; whitepaper §8.7, §10.1; BUILD_PLAN I20 "an M1-laws
differential with --no-registry on the extracted facts"). The contract is clause 4 of the docstring of
tests_m2/test_extracted_refinement.py.

  python -m holon differential --milestone M2 [--root DIR] [--reuse-view]

--reuse-view (I43) skips the extraction of step 1, which needs the replay toolchain (solc and the target checkout:
holon.machine.load_extracted), and reuses the deltas of the committed gen/<M>/abstraction_diff.json: it recomputes the
view of step 2 from them and refuses (exit 2, writing nothing) unless the view is the committed
gen/<M>/extracted/m1_view.json byte for byte; steps 3 and 4 run as usual. G1 runs the full differential.

For every window declaration of the milestone (holon.window: an extracted transitions document and the hand
abstraction it views), this module

  1. derives the deltas between the two documents, each from one concrete difference (gen/<M>/abstraction_diff.json):
       guard_missing    an abstraction require of an action the document also has, with no check of that action whose
                        span overlaps the require's span (same unit, intersecting line ranges; the require's src is
                        "<unit>:<lo>[-<hi>]" followed by anything; a src of another form matches nothing; the
                        dispatcher's callvalue and calldatasize checks, located at the whole function, match none);
       guard_extra      a check of the document (holon.machine.ExtractedModel.reaches: guard reaches and implicit
                        checks) with no require of the same action whose span overlaps it;
       state_unmapped   an abstraction state or record field the window view cannot express from raw families
                        (holon.window.classify: unmapped, the environment, the record of observations);
       family_unmapped  a raw family (inherited storage included) that no window mapping reads;
       ghost            an abstraction ghost field (ghost_state, a record type's "ghost" fields);
       external         a field held by another contract (the window declaration's "external").
     Every delta names the abstraction names it touches: the action (guard deltas), or the field ("<Type>.<field>"
     for a record field) with every definition, observer, target-library builtin and action whose code reads or
     writes it.
  2. builds the window view of the abstraction (gen/<M>/extracted/m1_view.json): the abstraction with the requires of
     its guard_missing deltas removed (the extracted model does not check there). These are the deltas the view
     applies; no other delta changes the view (an extra check has no expression in the abstraction's terms; unmapped
     and external fields keep the abstraction's model of them; ghost fields never influence the rest by the
     abstraction's ghost discipline).
  3. re-runs every law of the abstraction's milestone over that document (holon.mpipeline.run_m1 with the view as
     --facts and --no-registry; records in results/<M>/extracted_m1/, the run's files in gen/<M>/extracted/m1/). A law
     whose statement reads a ghost field (a statement root, an observer or definition it names or a projection, reads
     one directly, through another definition, or through a target-library builtin whose body uses the field) is not
     run: the extracted model has no such field, so its status there is UNKNOWN, recorded with the reason.
  4. writes results/<M>/differential.json: {"laws": {law: {"m1", "extracted", "deltas"}}}. deltas is empty exactly
     when the two statuses agree; otherwise it lists every applied delta (guard_missing, and ghost for a law that is
     not run) that shares a name with the law's cone (holon.mpipeline.law_cone over the abstraction, as the M1 run
     recorded it in results/<M1>/<law>.json "cone"). Names are matched to kernel names by the machine generator's
     conventions (holon.gen.machine: d_<def>, b_<builtin>, exec_/decide_/step_/Dec_/dec_<action>_<i>,
     g_<Type>_<field>, with_<Type>_..., observers by name). A status difference no applied delta explains lists none,
     and is reported as such.

Deterministic (clause 10): sorted iteration, no timestamps; two runs write the same bytes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

from . import window as W

ROOT = Path(__file__).resolve().parents[1]
DIFF_VERSION = "holon-differential/0.1"
APPLIED = ("guard_missing", "ghost")
DISPATCHER = ("callvalue", "calldatasize")   # checks of the dispatcher, located at the function (holon.machine)


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------------ spans
def span(src) -> tuple[str, int, int] | None:
    """(unit, lo, hi) of a source span "<unit>:<lo>[-<hi>]" (anything may follow); None otherwise."""
    from .machine import source_span
    return source_span(src)


def overlap(a, b) -> bool:
    from .machine import spans_overlap
    return spans_overlap(a, b)


# ------------------------------------------------------------------------------------------------ the abstraction
def _walk(e):
    if isinstance(e, list):
        yield e
        for x in e:
            yield from _walk(x)
    elif isinstance(e, dict):
        for x in e.values():
            yield from _walk(x)


class Abstraction:
    """What the differential reads of a holon-facts/0.2 document: its names and what each piece of code reads and
    writes."""

    def __init__(self, facts: dict, lib_texts: dict | None = None):
        self.f = facts
        self.state = [s[0] for s in facts.get("state") or []]
        self.types = {t: [x[0] for x in spec.get("fields") or []] for t, spec in (facts.get("types") or {}).items()
                      if isinstance(spec, dict)}
        self.defs = dict(facts.get("defs") or {})
        self.observers = dict(facts.get("observers") or {})
        self.actions = {a["name"]: a for a in facts.get("actions") or []}
        self.lib = dict(lib_texts or {})             # builtin name -> its Bend text (b_<name>)
        self.gstate, self.grec = W.ghosts(facts)

    def rfield(self, name: str) -> list[str]:
        """The record types holding a field of that name."""
        return sorted(t for t, fs in self.types.items() if name in fs)

    def code(self):
        """(kind, name, expressions) of every piece of code: defs, observers, actions (guards and effects),
        migrations."""
        for n, d in sorted(self.defs.items()):
            yield "def", n, [d.get("body")]
        for n, o in sorted(self.observers.items()):
            yield "observer", n, [o.get("body")]
        for n, a in sorted(self.actions.items()):
            exprs = [g.get("require", g.get("expr")) for g in a.get("guards") or []]
            exprs += [v for _, v in sorted((a.get("effects") or {}).items())]
            yield "action", n, exprs
        for n, mg in sorted((self.f.get("migrations") or {}).items()):
            yield "migration", n, [v for _, v in sorted((mg.get("effects") or {}).items())]

    def reads(self, exprs, local=()) -> dict:
        """{"state": fields, "fields": record fields read (["get", x, f]), "calls": defs/observers/builtins called,
        "writes": record fields written (mk / with keys)}."""
        out = {"state": set(), "fields": set(), "calls": set(), "writes": set()}
        st = set(self.state)
        for e in exprs:
            if isinstance(e, str) and e in st and e not in local:
                out["state"].add(e)
            for n in _walk(e):
                if not n or not isinstance(n[0], str):
                    for x in n:
                        if isinstance(x, str) and x in st and x not in local:
                            out["state"].add(x)
                    continue
                op = n[0]
                if op == "get" and len(n) == 3 and isinstance(n[2], str):
                    out["fields"].add(n[2])
                elif op == "call" and len(n) > 1 and isinstance(n[1], str):
                    out["calls"].add(n[1])
                elif op == "mk" and len(n) == 3 and isinstance(n[2], dict):
                    out["writes"] |= set(n[2])
                elif op == "with" and len(n) == 4 and isinstance(n[3], dict):
                    out["writes"] |= set(n[3])
                for x in n[1:]:
                    if isinstance(x, str) and x in st and x not in local:
                        out["state"].add(x)
        return out

    def builtin_uses(self, name: str, field: str) -> bool:
        """Whether a target-library builtin's body uses a record field: the field's variable occurs outside the
        record patterns and reconstructions of its Bend text."""
        text = self.lib.get(name)
        if not text:
            return False
        body = re.sub(r"\bH\w+\{[^{}]*\}", " ", text)
        return re.search(rf"\b{re.escape(field)}\b", body) is not None

    def ghost_readers(self) -> set:
        """Every def, observer and builtin whose value depends on a ghost field (module docstring)."""
        gfields = {f for fs in self.grec.values() for f in fs}
        bad = {n for n, d in self.defs.items() if d.get("ghost")}
        bad |= {b for b in self.lib if any(self.builtin_uses(b, f) for f in gfields)}
        changed = True
        while changed:
            changed = False
            for kind, n, exprs in self.code():
                if kind not in ("def", "observer") or n in bad:
                    continue
                params = [p[0] for p in (self.defs.get(n) or {}).get("params") or []] if kind == "def" else []
                r = self.reads(exprs, set(params))
                if (r["state"] & self.gstate) or (r["fields"] & gfields) or (r["calls"] & bad):
                    bad.add(n)
                    changed = True
        return bad

    def touching(self, field: str | None = None, record_field: str | None = None) -> list[str]:
        """The defs, observers, builtins and actions whose code reads or writes a state field or a record field."""
        out = set()
        for kind, n, exprs in self.code():
            params = [p[0] for p in (self.defs.get(n) or {}).get("params") or []] if kind == "def" else []
            r = self.reads(exprs, set(params))
            if field and (field in r["state"] or (kind == "action" and field in (self.actions[n].get("effects") or {}))):
                out.add(n)
            if record_field and (record_field in r["fields"] or record_field in r["writes"]):
                out.add(n)
        if record_field:
            out |= {b for b in self.lib if self.builtin_uses(b, record_field)}
        return sorted(out)

    def kernel_names(self, name: str) -> set:
        """The kernel (Bend) names of an abstraction name (module docstring)."""
        out = {name}
        if name in self.defs:
            out.add(f"d_{name}")
        if name in self.lib:
            out.add(f"b_{name}")
        if name in self.actions:
            out |= {f"exec_{name}", f"decide_{name}", f"step_{name}", f"Dec_{name}"}
        if "." in name:
            t, f = name.split(".", 1)
            out |= {f"g_{t}_{f}"}
        return out

    def shares(self, names, cone) -> bool:
        cone = set(cone or [])
        for n in names:
            if self.kernel_names(n) & cone:
                return True
            if n in self.actions and any(c.startswith(f"dec_{n}_") for c in cone):
                return True
            if "." in n:
                t, f = n.split(".", 1)
                if any(c.startswith(f"with_{t}_") and f in c[len(f"with_{t}_"):].split("_") for c in cone):
                    return True
        return False


def lib_texts(facts_path: Path, root: Path) -> dict:
    """builtin name -> the Bend text of its definition, from the abstraction's target libraries."""
    from .gen.targetlib import lib_files
    texts = {}
    blocks = []
    for p in lib_files(facts_path, root):
        d = json.loads(p.read_text(encoding="utf-8"))
        for b in d.get("record_blocks") or []:
            if isinstance(b, dict) and isinstance(b.get("bend"), str):
                blocks.append(b["bend"])
        pre = d.get("prelude")
        blocks += pre if isinstance(pre, list) else [pre] if isinstance(pre, str) else []
        for name in d.get("builtins") or {}:
            texts.setdefault(name, "")
    text = "\n".join(x for x in blocks if isinstance(x, str))
    for name in texts:
        m = re.search(rf"(?ms)^def b_{re.escape(name)}\(.*?(?=^def |\Z)", text)
        texts[name] = m.group(0) if m else ""
    return texts


# ------------------------------------------------------------------------------------------------ deltas
def compute_deltas(model, decl: dict, facts: dict, ab: Abstraction) -> list[dict]:
    """The mechanical deltas between the extracted document and the abstraction (module docstring)."""
    out = []
    ids: dict = {}

    def add(kind: str, key: str, names, src, **extra):
        i = f"{kind}:{key}"
        k = ids.get(i, 0)
        ids[i] = k + 1
        out.append(dict({"id": i if k == 0 else f"{i}#{k}", "kind": kind, "names": sorted(set(names)), "src": src},
                        **extra))

    for an in sorted(ab.actions):
        if an not in model.actions:
            continue
        a = ab.actions[an]
        checks = model.reaches(an)
        # the dispatcher's checks (callvalue, calldatasize) sit at the function's own span: they stand for no require
        # of the function's body, so they match none
        cspans = [(c, span(c.src) if c.kind not in DISPATCHER else None) for c in checks]
        reqs = [(i, g) for i, g in enumerate(a.get("guards") or []) if "require" in g]
        for i, g in reqs:
            sp = span(g.get("src"))
            if not any(overlap(sp, cs) for _, cs in cspans):
                r = ab.reads([g["require"]])
                names = [an] + sorted(r["state"]) + sorted(r["calls"]) + [f"{t}.{f}" for f in sorted(r["fields"])
                                                                         for t in ab.rfield(f)]
                add("guard_missing", f"{an}:{g.get('src') or f'guards[{i}]'}", names, g.get("src"),
                    action=an, guard=i, reason=g.get("reason"))
        for c, cs in cspans:
            if not any(overlap(cs, span(g.get("src"))) for _, g in reqs):
                add("guard_extra", c.id, [an], c.src, action=an, check_kind=c.kind)
    cls = W.classify(model, decl, facts)
    for x in cls["fields"]:
        if x["kind"] == "mapped":
            continue
        if x.get("record"):
            name = f"{x['record']}.{x['field']}"
            names = [name] + ab.touching(record_field=x["field"])
        else:
            name = x["field"]
            names = [name] + ab.touching(field=x["field"])
        add(x["kind"], name, names, None, reason=x["reason"])
    for fam in cls["families"]["unmapped"]:
        f = model.families[fam]
        add("family_unmapped", fam, [fam], None, reason=f"slot {f.slot} offset {f.offset}" +
            ("" if f.declared else f" (inherited from {f.contract})"))
    return sorted(out, key=lambda d: d["id"])


def view_facts(facts: dict, deltas: list[dict], doc_rel: str, doc_sha: str, decl_rel: str | None) -> dict:
    """The window view of the abstraction: its requires of the guard_missing deltas removed (module docstring)."""
    out = copy.deepcopy(facts)
    drop: dict = {}
    for d in deltas:
        if d["kind"] == "guard_missing":
            drop.setdefault(d["action"], set()).add(d["guard"])
    for a in out.get("actions") or []:
        gone = drop.get(a["name"], set())
        a["guards"] = [g for i, g in enumerate(a.get("guards") or []) if i not in gone]
    out["extraction"] = {"method": f"generated by holon.differential: the window view of {doc_rel} over the hand "
                                   "abstraction, its unmatched requires removed",
                         "facts": doc_rel, "facts_sha256": doc_sha, "declaration": decl_rel,
                         "removed": {a: sorted(v) for a, v in sorted(drop.items())}}
    return out


def statement_roots(law: dict) -> dict:
    """{"names": observers / defs / fns a statement names, "proj": state fields it projects}."""
    names, proj = set(), set()
    stack = [law.get("statement")]
    while stack:
        t = stack.pop()
        if isinstance(t, dict):
            for k in ("obsv", "fn", "call"):
                if isinstance(t.get(k), str):
                    names.add(t[k])
            if isinstance(t.get("proj"), list):
                proj |= {x for x in t["proj"] if isinstance(x, str)}
            stack.extend(t.values())
        elif isinstance(t, list):
            stack.extend(t)
    return {"names": sorted(names), "proj": sorted(proj)}


def ghost_reason(law: dict, ab: Abstraction, readers: set) -> str | None:
    r = statement_roots(law)
    hit = sorted(set(r["names"]) & readers) + sorted(set(r["proj"]) & ab.gstate)
    if not hit:
        return None
    return (f"the statement reads ghost state through {', '.join(hit)}: the extracted model has no ghost field, so "
            "the law is not run on it")


# ------------------------------------------------------------------------------------------------ the run
class ReuseRefused(Exception):
    """--reuse-view cannot stand for the extraction: the committed deltas or view are missing, or the view the
    committed deltas give today is not the committed one, byte for byte."""


def _document_sha256(doc_rel: str, root: Path) -> str:
    """sha256 of the extracted document's bytes, located as holon.machine.load_extracted locates it (repo-relative or
    absolute), which is what the extracted model's sha256 is."""
    p = Path(doc_rel)
    if not p.is_absolute():
        p = (root / p) if (root / p).exists() else Path.cwd() / p
    return sha256_file(p)


def _committed_deltas(milestone: str, root: Path) -> list[dict]:
    p = root / "gen" / milestone / "abstraction_diff.json"
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ReuseRefused(f"no committed gen/{milestone}/abstraction_diff.json to reuse ({type(e).__name__}: {e})")
    if doc.get("differential_version") != DIFF_VERSION or not isinstance(doc.get("deltas"), list):
        raise ReuseRefused(f"gen/{milestone}/abstraction_diff.json is not a {DIFF_VERSION} document")
    return doc["deltas"]


def _plan(milestone: str, root: Path, decls: list, reuse_view: bool) -> list[tuple]:
    """Per window declaration: (its repo-relative path, the declaration, the abstraction, its Abstraction, the deltas,
    the view's text). With reuse_view the deltas are the committed abstraction_diff.json's (no extraction, so no replay
    toolchain), and the view they give must be the committed m1_view.json byte for byte (ReuseRefused otherwise);
    nothing is written here."""
    from . import machine
    committed = _committed_deltas(milestone, root) if reuse_view else None
    plans = []
    for p, decl in decls:
        W.validate(decl, p)
        drel = p.relative_to(root).as_posix()
        fpath = root / decl["abstraction"]
        facts = W.load_abstraction(decl, root)
        ab = Abstraction(facts, lib_texts(fpath, root))
        if reuse_view:
            deltas = [{k: v for k, v in d.items() if k != "declaration"} for d in committed
                      if isinstance(d, dict) and d.get("declaration") == drel]
            doc_sha = _document_sha256(decl["facts"], root)
        else:
            model = machine.load_extracted(decl["facts"], root)
            deltas = compute_deltas(model, decl, facts, ab)
            doc_sha = model.sha256
        view = dumps(view_facts(facts, deltas, decl["facts"], doc_sha, drel))
        if reuse_view:
            vp = root / "gen" / milestone / "extracted" / "m1_view.json"
            if not vp.is_file() or vp.read_bytes() != view.encode("utf-8"):
                raise ReuseRefused(f"the view the committed deltas of {drel} give today is not the committed "
                                   f"gen/{milestone}/extracted/m1_view.json (an input of the view changed since it "
                                   "was extracted): run holon differential without --reuse-view, with the replay "
                                   "toolchain")
        plans.append((drel, decl, facts, ab, deltas, view))
    return plans


def run(milestone: str = "M2", root=None, log=print, out=None, reuse_view: bool = False) -> int:
    """The differential of the tree under root; its outputs go under out (default: root itself): gen/<M>/extracted/
    (m1_view.json, m1/), gen/<M>/abstraction_diff.json, results/<M>/extracted_m1/ and results/<M>/differential.json
    (G1 regenerates them into a scratch directory, holon.gate.regenerate_m2_outputs).

    reuse_view (I43; --reuse-view): skip the extraction (holon.machine.load_extracted, which needs the replay
    toolchain) and reuse the deltas of the committed gen/<M>/abstraction_diff.json; recompute the view from them and
    refuse (ReuseRefused, before writing anything) unless it is the committed gen/<M>/extracted/m1_view.json byte for
    byte; then run the rest as usual (the M1 laws on the view, the not-run stubs, summary.json with every law,
    differential.json and abstraction_diff.json)."""
    from . import ir
    from .mpipeline import run_m1
    root = Path(root or ROOT)
    out = Path(out or root)
    decls = [(p, d) for p, d in W.declarations(root) if p.relative_to(root).parts[1] == milestone]
    if not decls:
        log(f"holon differential: no window declaration under spec/{milestone}/lib/")
        return 1
    diffs, laws_out = [], {}
    for drel, decl, facts, ab, deltas, view in _plan(milestone, root, decls, reuse_view):
        diffs += [dict(d, declaration=drel) for d in deltas]
        m1 = _milestone_of(decl["abstraction"])
        laws = [law for law in ir.load_laws_any(m1, root) if law.get("facts") == decl["abstraction"]]
        summary = json.loads((root / "results" / m1 / "summary.json").read_text())
        gen = out / "gen" / milestone / "extracted"
        gen.mkdir(parents=True, exist_ok=True)
        vf = gen / "m1_view.json"
        vf.write_text(view, encoding="utf-8")
        readers = ab.ghost_readers()
        ghost_ids = [d["id"] for d in deltas if d["kind"] == "ghost"]
        skip = {law["law_id"]: ghost_reason(law, ab, readers) for law in laws}
        runnable = sorted(lid for lid, why in skip.items() if why is None)
        out_dir = out / "results" / milestone / "extracted_m1"
        statuses: dict = {}
        if runnable:
            # the records read the Lean report of the view's Lean directory (holon.lean: key "<M>/extracted_m1", this
            # module's results/<M>/extracted_m1 layout), under root, never under out
            res = run_m1(m1, str(vf), str(out_dir), str(gen / "m1"), True, log=log, only=runnable,
                         lean_key=f"{milestone}/extracted_m1")
            statuses.update({lid: res.get(lid, "UNKNOWN") for lid in runnable})
        for lid, why in sorted(skip.items()):
            if why is None:
                continue
            statuses[lid] = "UNKNOWN"
            rec = {"law_id": lid, "status": "UNKNOWN", "record": "not_run",
                   "facts": f"gen/{milestone}/extracted/{vf.name}",
                   "attempts": [{"kind": "not_run", "reason": why}],
                   "deltas": [i for i in ghost_ids if ab.shares(_names(deltas, i), _cone(root, m1, lid))]}
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
        (out_dir / "summary.json").write_text(dumps({lid: statuses[lid] for lid in sorted(statuses)}), encoding="utf-8")
        for law in laws:
            lid = law["law_id"]
            m1s, xs = summary.get(lid), statuses.get(lid, "UNKNOWN")
            ds = []
            if m1s != xs:
                cone = _cone(root, m1, lid)
                kinds = ("ghost",) if skip.get(lid) else ("guard_missing",)
                ds = [d["id"] for d in deltas if d["kind"] in kinds and ab.shares(d["names"], cone)]
            laws_out[lid] = {"m1": m1s, "extracted": xs, "deltas": sorted(ds)}
            if skip.get(lid):
                laws_out[lid]["not_run"] = skip[lid]
    gm = out / "gen" / milestone
    gm.mkdir(parents=True, exist_ok=True)
    (gm / "abstraction_diff.json").write_text(dumps({"document": "abstraction_diff", "differential_version": DIFF_VERSION,
                                                     "deltas": diffs}), encoding="utf-8")
    rm = out / "results" / milestone
    rm.mkdir(parents=True, exist_ok=True)
    (rm / "differential.json").write_text(dumps({"document": "differential", "differential_version": DIFF_VERSION,
                                                 "laws": laws_out}), encoding="utf-8")
    n = sum(1 for x in laws_out.values() if x["m1"] != x["extracted"])
    unexplained = sorted(l for l, x in laws_out.items() if x["m1"] != x["extracted"] and not x["deltas"])
    log(f"holon differential: {len(diffs)} deltas, {len(laws_out)} laws, {n} status differences"
        + (f", unexplained: {unexplained}" if unexplained else ""))
    return 0


def _names(deltas: list[dict], i: str) -> list[str]:
    return next(d["names"] for d in deltas if d["id"] == i)


def _milestone_of(rel: str) -> str:
    parts = Path(rel).parts
    if len(parts) >= 2 and parts[0] == "spec" and re.fullmatch(r"M\d+", parts[1]):
        return parts[1]
    if parts and parts[0] == "facts":
        return "M0"
    raise W.WindowError(f"{rel}: cannot tell the abstraction's milestone")


def _cone(root: Path, m1: str, lid: str) -> list[str]:
    """The law's cone as the abstraction's run recorded it (holon.mpipeline.law_cone over the abstraction)."""
    p = root / "results" / m1 / f"{lid}.json"
    if p.is_file():
        rec = json.loads(p.read_text())
        if isinstance(rec.get("cone"), list):
            return rec["cone"]
    from . import bend, records
    from . import ir
    from .mpipeline import law_cone
    law = next(x for x in ir.load_laws_any(m1, root) if x["law_id"] == lid)
    facts = json.loads((root / law["facts"]).read_text())
    model = root / "gen" / m1 / "model" / f"{Path(law['facts']).stem}.bend"
    return law_cone(law, facts, records.ir_roots_text(law), model, bend.config(root))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon differential")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--root")
    ap.add_argument("--reuse-view", action="store_true",
                    help="reuse the committed deltas instead of extracting (no replay toolchain); refused (exit 2) "
                         "unless they give the committed view byte for byte")
    a = ap.parse_args(argv)
    try:
        return run(a.milestone, a.root, reuse_view=a.reuse_view)
    except ReuseRefused as e:
        print(f"holon differential: refused: {e}", file=sys.stderr)
        return 2
    except (W.WindowError, ValueError) as e:
        print(f"holon differential: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
