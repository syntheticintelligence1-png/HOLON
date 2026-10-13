"""Statement refs for holon-ir/0.3 (whitepaper §8.9, §9.4; BUILD_PLAN I7; audit F-M2-03).

A 0.3 statement hash covers the statement and `refs`: every model construct the statement depends on, each by
the content hash of the construct that defines it, never the whole facts bundle. An extraction change outside
a law's refs leaves its hash unchanged; a change inside them restales it.

refs is the transitive closure of what the statement names, over the facts def graph and the target library:

  obsv:NAME          facts.observers[NAME] (doc removed), then every def, library builtin, DSL builtin and facts
                     param its body calls or names, transitively; and the state signature `sig`
  mig:NAME           facts.migrations[NAME] (doc, src removed), then its effects' closure; and `sig`
  A_NAME             the action NAME as the model steps it: inputs, guards (with their revert reasons) and effects,
                     src and doc removed, then their closure. Only the actions a statement can reach are refs: the
                     ones it names as literals ({act}, {trace: [{act}..]}), or every action when a step, run, obs or
                     runs_ok term takes a trace or action that is not a literal (a binder). Editing an action the
                     statement cannot reach, or any action's src span, changes no hash.
  acts               the action signature (each action's name and inputs): what an Act or Trace binder ranges over,
                     what an {act} literal, an is_NAME test or a consumer matches on
  sig                the state signature: state fields and types, record types and fields, shadow fields
  s0                 facts.initial (doc removed), with `sig`
  def:NAME           facts.defs[NAME] (doc removed), and its closure
  lib:NAME           the target-library entry of builtin NAME (holon.gen.targetlib), and libsupport:<library>, that
                     library's prelude, record blocks and shadow values (the Bend text the entry's template calls)
  param:NAME         the value of facts param NAME
  oparam:P           the signature of oracle parameter P (I12), when the model's definitions apply it
  disch.cost         facts.disch.cost (for cost); disch.delay: facts.disch.delay (for elapsed)
  principals         each action's principal label (for perm, which the generator derives from them)
  consumer:NAME      facts.consumers[NAME] (doc removed), with `acts`
  hyp:H              the oracle sidecar entry whose hypothesis is H, restricted to {parameter, hypothesis} (I12;
                     holon.gen.oracles.Oracles.hyp_ref). Without a sidecar, the hash of null.
  eq_nat, ..         an IR builtin (holon.gen.mlaws.BUILTINS) under the rule catalog version
  tmpl:NAME, dsl:NAME  a generator-synthesized helper (step, run, obs, runs_ok, last_ok, no_code, perm, cost,
                     elapsed, is_act, consumer, observer, migration, s0, reach) or a DSL builtin the generator
                     renders itself (len, take, ..): {template_id, template_version}, never its text (TEMPLATES).
                     The bindings (G2, holon.bindings) bind the kernel form of every definition a statement reaches,
                     so a template change that keeps its version still fails G2 by name.
  fn:NAME            a name the facts, the library and the generator do not define: hashed as absent, so defining
                     it changes the hash
  site:ID            a SORT-site term {"site": ID, "on": A, "from": S} (I15): the site's spec as holon.sorts.sites
                     computes it from the facts and the SORT-site sidecar of the law's milestone (template id and
                     version, the basis element and the hit points), so G2 needs no derive output; the term also
                     takes the step closure of A, as a step term does

The oracle sidecar of a law, when the caller passes none (oracles=None), is the one its model takes in its
milestone (holon.gen.oracles.Oracles.for_milestone over <root>/<law facts>; audit M2/1 F-M2-11), so
law_hash(law, facts) is the hash `holon run` and G2 compute; M0 and M1 never take one.

Every hash is "sha256:" + sha256 of the canonical JSON of the construct. `doc`, `src` and `*_doc` keys are
removed everywhere: they are text for humans and replay, and re-extraction that shifts a line number must not
restale a law.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import ir

ROOT = Path(__file__).resolve().parents[2]

# Generator-synthesized helpers: template id -> version. Bump a version when the generator changes what the
# template means; adding a template (e.g. I15's at_site and site_hit) adds an entry here.
TEMPLATES = {
    "step": ("holon.gen.machine.gen_dispatch:step", 1), "run": ("holon.gen.machine.gen_dispatch:run", 1),
    "obs": ("holon.gen.machine.gen_dispatch:obs", 1), "runs_ok": ("holon.gen.machine.gen_dispatch:runs_ok", 1),
    "last_ok": ("holon.gen.machine.gen_dispatch:last_ok", 1), "no_code": ("holon.gen.machine.gen_dispatch:no_code", 1),
    "perm": ("holon.gen.machine.gen_dispatch:perm", 1), "cost": ("holon.gen.machine.gen_dispatch:cost", 1),
    "elapsed": ("holon.gen.machine.gen_dispatch:elapsed", 1), "is_act": ("holon.gen.machine.gen_dispatch:is_act", 1),
    "consumer": ("holon.gen.machine.gen_dispatch:consumer", 1),
    "observer": ("holon.gen.machine.gen_observers:observer", 1),
    "migration": ("holon.gen.machine.gen_observers:migration", 1), "s0": ("holon.gen.machine.gen_initial:s0", 1),
    "reach": ("holon.gen.machine.gen_reach:Reach", 1), "action": ("holon.gen.machine.gen_action", 1),
    "proj": ("holon.gen.mlaws.Emitter.view_defs:proj", 1),
}
# DSL functions holon.gen.machine.Machine.builtin renders itself (after facts defs, oracle parameters and the
# target library, in that order, exactly as the generator resolves a call)
DSL_FIRST = ("len", "take", "drop", "tail", "concat", "snoc", "eq_nats")
DSL_FIXED = ("nth", "set_nat", "mem", "remove", "zeros_like")
DSL_TEMPLATE_VERSION = 1
_TRACE_FNS = {"runs_ok", "last_ok", "no_code", "perm", "cost", "elapsed"}


def _h(obj) -> str:
    return "sha256:" + hashlib.sha256(ir.canonical_json(obj)).hexdigest()


def strip_meta(x):
    """x without doc, src and *_doc keys, at any depth."""
    if isinstance(x, dict):
        return {k: strip_meta(v) for k, v in x.items() if not (k in ("doc", "src") or k.endswith("_doc"))}
    if isinstance(x, list):
        return [strip_meta(v) for v in x]
    return x


def template_ref(name: str) -> dict:
    tid, ver = TEMPLATES[name]
    return {"template_id": tid, "template_version": ver}


def lib_docs_for(law: dict, root: Path | str | None = None) -> list[dict]:
    """The target-library documents of the law's facts file (holon.gen.targetlib.lib_files), as the model
    generator reads them; [] when the law names no facts file."""
    from .targetlib import lib_files
    root = Path(root or ROOT)
    rel = law.get("facts")
    if not isinstance(rel, str) or not rel:
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in lib_files(root / rel, root)]


class _Closure:
    def __init__(self, law: dict, facts: dict, orc, lib_docs: list[dict], root: Path | str | None = None):
        self.law, self.f, self.orc, self.out = law, facts or {}, orc, {}
        self.root = Path(root or ROOT)
        self.lib_docs = list(lib_docs or [])
        self.defs = self.f.get("defs", {}) or {}
        self.params = self.f.get("params", {}) or {}
        self.acts = {a["name"]: a for a in self.f.get("actions", []) or []}
        self.oparams = dict(getattr(orc, "params", {}) or {}) if orc is not None else {}
        self.lib: dict[str, tuple[str, dict]] = {}
        self.support: dict[str, dict] = {}
        self.shadow_libs: dict[str, list[str]] = {}
        for d in lib_docs or []:
            name = d.get("name", "?")
            self.support[name] = {"prelude": d.get("prelude", []), "record_blocks": d.get("record_blocks", []),
                                  "shadow_values": d.get("shadow_values", {})}
            for k, b in (d.get("builtins") or {}).items():
                self.lib.setdefault(k, (name, b))
            for k in d.get("shadow_values") or {}:
                self.shadow_libs.setdefault(k, []).append(name)
        self.shadow_fields = set((self.f.get("shadow") or {}).values())

    # ------------------------------------------------------------ entries
    def put(self, key: str, obj) -> bool:
        if key in self.out:
            return False
        self.out[key] = _h(obj)
        return True

    def tmpl(self, name: str) -> None:
        self.out.setdefault("tmpl:" + name, template_ref(name))

    def sig(self) -> None:
        self.put("sig", {"state": [[x[0], x[1]] for x in self.f.get("state", [])],
                         "types": strip_meta(self.f.get("types", {})), "shadow": self.f.get("shadow", {})})

    def acts_sig(self) -> None:
        self.put("acts", [[a["name"], a.get("inputs", [])] for a in self.f.get("actions", []) or []])

    def action(self, name: str) -> None:
        a = self.acts.get(name)
        if not self.put("A_" + name, None if a is None else strip_meta({k: v for k, v in a.items() if k != "principal"})):
            return
        self.tmpl("action")
        if a is None:
            return
        if isinstance(a.get("effects"), list):   # an extracted transitions document (I20): the action as stated is the ref
            return
        self.sig()
        for g in a.get("guards", []):
            self.expr(g.get("require", g.get("expr")))
        for e in (a.get("effects") or {}).values():
            self.expr(e)

    def reach(self, t) -> None:
        """The actions a step/run/obs/runs_ok argument can reach: its literals, or every action."""
        lits = self.literal_actions(t)
        self.acts_sig()
        self.tmpl("step")
        for n in (sorted(self.acts) if lits is None else sorted(lits)):
            self.action(n)

    def literal_actions(self, t) -> set | None:
        if not isinstance(t, dict):
            return None
        if "act" in t and isinstance(t.get("act"), str):
            return {t["act"]}
        if "trace" in t and isinstance(t["trace"], list):
            out: set = set()
            for x in t["trace"]:
                s = self.literal_actions(x)
                if s is None:
                    return None
                out |= s
            return out
        if "cat" in t and isinstance(t["cat"], list):
            out = set()
            for x in t["cat"]:
                s = self.literal_actions(x)
                if s is None:
                    return None
                out |= s
            return out
        return None

    # ------------------------------------------------------------ facts expressions (holon-facts DSL)
    def expr(self, e) -> None:
        if isinstance(e, str):
            if e in self.params:
                self.put("param:" + e, self.params[e])
            return
        if not isinstance(e, list) or not e:
            return
        op, *a = e
        if op == "call" and a:
            name, *args = a
            for x in args:
                self.expr(x)
            self.call(name)
        elif op == "get" and a:
            self.expr(a[0])
        elif op == "mk" and len(a) == 2 and isinstance(a[1], dict):
            for x in a[1].values():
                self.expr(x)
        elif op == "with" and len(a) == 3:
            self.expr(a[1])
            for x in (a[2] or {}).values():
                self.expr(x)
        elif op == "list":
            for x in a[1:]:
                self.expr(x)
        else:
            for x in a:
                self.expr(x)

    def call(self, name: str) -> None:
        """A call, resolved in the generator's order (holon.gen.machine.Machine.ex, .builtin)."""
        if not isinstance(name, str):
            return
        if name in self.defs:
            if self.put("def:" + name, strip_meta(self.defs[name])):
                self.expr(self.defs[name].get("body"))
        elif name in self.oparams:
            self.put("oparam:" + name, list(self.oparams[name]))
        elif name in DSL_FIRST:
            self.out.setdefault("dsl:" + name, {"template_id": f"holon.gen.machine.builtin:{name}",
                                                "template_version": DSL_TEMPLATE_VERSION})
        elif name in self.lib:
            lname, entry = self.lib[name]
            self.put("lib:" + name, entry)
            self.put("libsupport:" + lname, self.support.get(lname))
        elif name in DSL_FIXED or (name.startswith("es_") and name[3:] in self.shadow_fields):
            self.out.setdefault("dsl:" + name, {"template_id": f"holon.gen.machine.builtin:{name}",
                                                "template_version": DSL_TEMPLATE_VERSION})
            if name.startswith("es_"):
                self.sig()
                for lname in self.shadow_libs.get(name[3:], []):
                    self.put("libsupport:" + lname, self.support.get(lname))
        else:
            self.put("fn:" + name, None)

    # ------------------------------------------------------------ IR statement terms
    def binder(self, ty: str) -> None:
        if ty == "State":
            self.sig()
        elif ty in ("Act", "Trace"):
            self.acts_sig()
        elif ty == "Reach":
            self.tmpl("reach")
            self.s0()
            self.reach({"var": "_"})   # reachable by any action
        elif ty in self.f.get("types", {}):
            self.sig()

    def s0(self) -> None:
        self.tmpl("s0")
        self.sig()
        self.put("s0", strip_meta(self.f.get("initial")))   # literal values, no calls

    def term(self, t) -> None:
        if isinstance(t, list):
            for x in t:
                self.term(x)
            return
        if not isinstance(t, dict):
            return
        if isinstance(t.get("hyp"), dict) and isinstance(t["hyp"].get("name"), str):
            n = t["hyp"]["name"]
            self.out["hyp:" + n] = self.orc.hyp_ref(n) if self.orc is not None else _h(None)
            return
        if isinstance(t.get("obsv"), str):
            n = t["obsv"]
            o = (self.f.get("observers") or {}).get(n)
            self.tmpl("observer")
            self.sig()
            if self.put("obsv:" + n, None if o is None else strip_meta(o)) and o is not None:
                self.expr(o.get("body"))
            self.term(t.get("of"))
            return
        if isinstance(t.get("mig"), str):
            n = t["mig"]
            mg = (self.f.get("migrations") or {}).get(n)
            self.tmpl("migration")
            self.sig()
            if self.put("mig:" + n, None if mg is None else strip_meta(mg)) and mg is not None:
                for e in (mg.get("effects") or {}).values():
                    self.expr(e)
            self.term(t.get("of"))
            self.term(t.get("args", []))
            return
        for k in ("run", "step", "obs"):
            if k in t:
                self.tmpl(k)
                self.sig()
                self.reach(t[k])
                self.term(t[k])
                self.term(t.get("from"))
                return
        if "s0" in t:
            self.s0()
            return
        if isinstance(t.get("act"), str):
            self.acts_sig()
            self.term(list((t.get("args") or {}).values()))
            return
        if "proj" in t:
            self.tmpl("proj")
            self.sig()
            self.term(t.get("of"))
            return
        if isinstance(t.get("fn"), str) and "args" in t:
            self.fn(t["fn"], t["args"])
            self.term(t["args"])
            return
        if isinstance(t.get("site"), str) and "on" in t and "from" in t:   # a SORT-site term (I15)
            self.site(t["site"])
            self.tmpl("step")
            self.sig()
            self.reach(t["on"])
            self.term(t["on"])
            self.term(t["from"])
            return
        if isinstance(t.get("width_site"), str) and "on" in t and "from" in t:   # a SORT-width term (I20)
            self.width(t["width_site"])
            self.term(t["on"])
            self.term(t["from"])
            return
        for v in t.values():
            self.term(v)

    def width(self, sid: str) -> None:
        """width:<ID>: the width site's spec (holon.sorts.width.width_ref: the store, its field and widths, its entry
        points), and the entry points' actions as the extracted document states them (A_<name>)."""
        if "width:" + sid in self.out:
            return
        from ..sorts.width import width_ref
        spec = width_ref(sid, self.law, self.root)
        self.out["width:" + sid] = _h(spec)
        acts = {a.get("name"): a for a in self.f.get("actions") or [] if isinstance(a, dict)}
        for n in spec.get("entry_points") or []:
            self.put("A_" + n, strip_meta(acts.get(n)) if n in acts else None)

    def site(self, sid: str) -> None:
        """site:<ID>: the site's spec (holon.sorts.sites.site_ref), from the facts, their library and the sidecar."""
        if "site:" + sid in self.out:
            return
        from ..sorts.sites import site_ref
        from .targetlib import Library, LibError
        try:
            builtins = Library(self.lib_docs, self.f.get("params", {})).builtins
        except LibError as e:
            self.out["site:" + sid] = _h({"error": f"library: {e}"})
            return
        self.out["site:" + sid] = _h(site_ref(sid, self.law, self.f, builtins, self.root))

    def fn(self, n: str, args: list) -> None:
        from .mlaws import BUILTINS
        if n in BUILTINS:
            self.out[n] = _h({"builtin": n, "bend": BUILTINS[n][0],
                              "rule_catalog_version": self.law.get("rule_catalog_version")})
        elif n == "runs_ok":
            self.tmpl("runs_ok")
            self.sig()
            self.reach(args[0] if args else None)
        elif n == "last_ok":
            self.tmpl("last_ok")
            self.sig()
        elif n == "no_code":
            self.tmpl("no_code")
        elif n == "perm":
            self.tmpl("perm")
            self.acts_sig()
            self.put("principals", {a["name"]: a.get("principal") for a in self.f.get("actions", []) or []})
        elif n == "cost":
            self.tmpl("cost")
            self.acts_sig()
            self.put("disch.cost", (self.f.get("disch") or {}).get("cost", {}))
        elif n == "elapsed":
            self.tmpl("elapsed")
            self.acts_sig()
            self.put("disch.delay", (self.f.get("disch") or {}).get("delay", {}))
        elif n.startswith("is_") and n[3:] in self.acts:
            self.tmpl("is_act")
            self.acts_sig()
        elif n in (self.f.get("consumers") or {}):
            self.tmpl("consumer")
            self.acts_sig()
            self.put("consumer:" + n, strip_meta(self.f["consumers"][n]))
        else:
            self.put("fn:" + n, None)   # a name nothing defines: hashed as absent, so defining it changes the hash


def refs(law: dict, facts: dict, oracles=None, lib=None, root: Path | str | None = None) -> dict:
    """{ref: content hash or template} for everything the statement depends on (see the module docstring).
    `oracles` is the parsed sidecar (holon.gen.oracles.Oracles or its JSON document) that hyp premises and oracle
    parameters refer to; `lib` the target-library documents (default: those of the law's facts file under root,
    holon.gen.targetlib.lib_files)."""
    orc = _oracles(oracles) if oracles is not None else milestone_oracles(law, root)
    docs = lib if lib is not None else lib_docs_for(law, root)
    c = _Closure(law, facts or {}, orc, docs, root)
    st = law["statement"]
    for b in st.get("binders", []):
        c.binder(str(b.get("type", "")))
    c.term(st.get("assume", []))
    c.term(st.get("claim", {}))
    return dict(sorted(c.out.items()))


def milestone_oracles(law: dict, root: Path | str | None = None):
    """The oracle sidecar the model of a 0.3 law's facts takes in the law's milestone (Oracles.for_milestone), or
    None (M0, M1, a law without facts, or no sidecar)."""
    m, rel = law.get("milestone"), law.get("facts")
    if law.get("ir_version") != "holon-ir/0.3" or not isinstance(m, str) or m in ("M0", "M1") or not isinstance(rel, str):
        return None
    from .oracles import Oracles
    root = Path(root or ROOT)
    return Oracles.for_milestone(m, root / rel, root)


def _oracles(oracles):
    if oracles is None or hasattr(oracles, "hyp_ref"):
        return oracles
    from .oracles import Oracles
    return Oracles(oracles)


def law_hash(law: dict, facts: dict | None, oracles=None, lib=None, root: Path | str | None = None) -> str:
    """The law's statement hash: 0.1/0.2 over the hashed keys; 0.3 with its refs into `facts`, the target library
    `lib` (default: the law's facts' libraries under root) and, for hyp premises and oracle parameters, the oracle
    sidecar `oracles` (I12; default: the one its milestone's model takes, milestone_oracles)."""
    if law.get("ir_version") == "holon-ir/0.3":
        return ir.statement_hash(law, refs=refs(law, facts or {}, oracles, lib, root))
    return ir.statement_hash(law)
