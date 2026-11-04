"""holon run on a typed milestone's contract laws (BUILD_PLAN I33; tests_m3/test_o12_m3.py rules B5, B7 and B10).

A contract law here is an intended_weak law (holon.contracts K3) over a holon-facts/0.3 document (holon.sorts.contract3
.applies): nothing names its id (K4). It is decided on the structural typed model of its document:

  1. LAWS.bend (holon.sorts.contract3, B2) at gen/<M>/laws/<id>/;
  2. the proof class residue_bound (holon.sorts.residue, B6): its PROOF.bend at gen/<M>/proofs/<id>/, PROVED when bend2
     accepts it and BendTT's verdict is checked;
  3. the typed refuter (B5): holon.sorts.search3's reachable prefixes for the Reach state (holon.undo.search's prefix
     enumeration), the Act binders' calls of the actions their is[A] premises name, succeeding where their ok premises
     say (x from s, y after x), and each Word binder over a small pool of key words (the corpus's: 0..3 and the
     numeric arguments of the trace's steps, each +-1); the claim's conjuncts evaluated on the compiled model (the
     word- and Bool-valued statement helpers, holon.sorts.contract3.section_text; N and the comparisons exactly over
     the words). With a real side, a model witness counts only when its steps succeed on the deployment with the
     deployment's call answers and the model, those answers taken, still finds the conjunct false. The witness is the
     typed records' shape ({"prefix", the Act binders' steps, the Word binders' words, "hashes", "conjunct"}); its
     counter-law (the conjunct's, every premise and the conjunct by computation) at gen/<M>/proofs/<id>/witness/;
  4. the replay of a REFUTED witness on the real contract (the binding's step harness): its steps run there, and the
     words the conjunct reads are read at their real slots (holon.sorts.skeys.real_slot of the structural keys) before
     x and after the last step: passed when every step succeeds, the real words are the model's and the conjunct is
     false on them;
  5. non-vacuity (B7) of a PROVED law: the first candidate whose premises hold (a reachable prefix and the binders),
     its inhabitant law nv_<id> and proof at gen/<M>/<id>/nonvac/ (never under proofs/: G3), checked by bend; an
     attempt of kind "inhabitant" and the record's non_vacuity block;
  6. the record (G9's v1 and v2 shape, over the structural typed model: its ledger's model assumptions).

A law with no proof and no witness is UNKNOWN, its record naming the bound searched. The run's last step applies the
contracts (holon.contracts.after_run, K5), as on every milestone.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from ..machine_bend import bname
from . import contract3 as C3
from . import evaluate3 as E3
from . import proofs3 as P3
from . import run3
from . import search3 as S3

ROOT = Path(__file__).resolve().parents[2]
SKIP = "HOLON_CONTRACT3_SKIP"
GENERATOR = "holon.sorts.contract3"
BUDGET = {"prefix_depth": 3, "max_prefixes": 3000, "max_candidates": 20000, "continuation_depth": 0}
KEY_POOL = (0, 1, 2, 3)
GEN_FILES = ["holon/sorts/contract3.py", "holon/sorts/contract3_run.py", "holon/sorts/residue.py"]


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def rel(p: Path, root: Path) -> str:
    return os.path.relpath(Path(p).resolve(), Path(root).resolve()).replace(os.sep, "/")


# ---------------------------------------------------------------------------------------------------- dispatch
def _arg(argv: list, name: str):
    for i, x in enumerate(argv):
        if x == name and i + 1 < len(argv):
            return argv[i + 1]
        if x.startswith(name + "="):
            return x.split("=", 1)[1]
    return None


def contract_ids(milestone: str, root: Path = ROOT) -> list[str]:
    """The milestone's contract laws this runner decides (holon.sorts.contract3.applies), by law id."""
    d = Path(root) / "laws" / str(milestone)
    out = []
    for p in sorted(d.glob("L_contract_*.json")) if d.is_dir() else []:
        try:
            law = json.loads(p.read_text(encoding="utf-8"))
            facts = json.loads((Path(root) / law["facts"]).read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            continue
        if C3.applies(law, facts):
            out.append(law["law_id"])
    return out


def ids_of(argv: list) -> tuple[list[str], list[str] | None] | None:
    """(this runner's ids, the other ids of --laws, or None for the rest of a whole-milestone run), or None when the
    run names none of this runner's laws (or the milestone has none)."""
    if os.environ.get(SKIP):
        return None
    mine = contract_ids(_arg(argv, "--milestone") or "M0")
    if not mine:
        return None
    laws = _arg(argv, "--laws")
    if laws is None:
        return mine, None
    ids = [x.strip() for x in laws.split(",") if x.strip()]
    cids = [x for x in ids if x in mine]
    if not cids:
        return None
    return cids, [x for x in ids if x not in mine]


def with_laws(argv: list, ids: list[str]) -> list:
    out, skip = [], False
    for x in argv:
        if skip:
            skip = False
            continue
        if x == "--laws":
            skip = True
            continue
        if x.startswith("--laws="):
            continue
        out.append(x)
    return out + ["--laws", ",".join(ids)]


@contextlib.contextmanager
def skipping():
    """A whole-milestone run of the other runners, this one's laws left out (they run after)."""
    old = os.environ.get(SKIP)
    os.environ[SKIP] = "1"
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(SKIP, None)
        else:
            os.environ[SKIP] = old


# ---------------------------------------------------------------------------------------------------- the model
class Doc:
    """One law over its document's typed model: the law file's tables, and the evaluator over the model with the law's
    statement helpers appended (one combined module per law)."""

    def __init__(self, rc: run3.Ctx, law: dict):
        self.rc, self.law = rc, law
        self.doc_rel = law["facts"]
        self.ev, self.init, _mf, self.mm, self.docm = rc.model(self.doc_rel)
        self.model_file = rc.model_path(self.doc_rel)
        self.import_file = rc.import_path(self.doc_rel)
        self.text = self.model_file.read_text(encoding="utf-8")
        self.facts = json.loads((rc.root / self.doc_rel).read_text(encoding="utf-8"))
        self.hashes = self.ev.hashes()
        self.tb = P3.tabs_binders(self.hashes)
        self.tables = [n for n, _h in self.tb]
        sec, self.tm = C3.section_text(law, self.facts, self.tables)
        ct = self.text + "\n" + sec + "\n" + _touch_def(self.tm)
        cd = E3.cache_dir().parent / "contract3" / hashlib.sha256(ct.encode()).hexdigest()[:32]
        cd.mkdir(parents=True, exist_ok=True)
        cp = cd / "combined.bend"
        if not cp.is_file() or cp.read_text(encoding="utf-8") != ct:
            tmp = cd / f"combined.{os.getpid()}.part"
            tmp.write_text(ct, encoding="utf-8")
            os.replace(tmp, cp)
        self.combined = ct
        self.cev = E3.Evaluator.build(cp, self.docm)
        hp = rc.root / "results" / rc.m / "sorts" / "refinement" / "hints.json"
        self.hints = S3.Hints(json.loads(hp.read_text()) if hp.is_file() else None)
        self.recs = E3.records(ct)

    def factory(self, empty: bool = False, native: bool = True) -> S3.Model:
        i = dict(self.init)
        if empty:
            i["preimages"] = []
        return S3.Model(self.cev, i, self.hints, self.rc.root / self.doc_rel, native=native)

    def close(self):
        self.cev.close()


def _touch_def(tm: C3.Terms) -> str:
    """c3_touch: every word-valued helper of the law (the sread and env instances) in one list, so that evaluating it
    runs both steps and every read (the hash keys and call answers a witness needs), and no Nat."""
    words = [n for n, ty, _t in tm.helpers.values() if ty == "W"]
    body = "[" + ", ".join(f"{n}({tm.args()})" for n in words) + "]" if words else "Nil{}"
    return f"def c3_touch({tm.sig()}) -> List<&2, W>:\n  {body}\n"


# ---------------------------------------------------------------------------------------------------- the shape
class Shape:
    """The binders of a typed contract law as the refuter searches them: the Reach state s; the Act binders in the
    order the premises step them (ok(X1, s), ok(X2, step(X1, s)), ..), each with the action of its is[A] premise; the
    Word binders."""

    def __init__(self, law: dict):
        st = law["statement"]
        bs = [(b["name"], str(b.get("type", ""))) for b in st.get("binders") or []]
        self.binders = bs
        self.s = next(n for n, t in bs if t == "Reach")
        self.words = [n for n, t in bs if t == "Word"]
        acts = [n for n, t in bs if t == "Act"]
        isa, oks = {}, {}
        for p in st.get("assume") or []:
            a = (p.get("eq") or [None])[0]
            k = C3.term_kind(a)
            if k == "is" and isinstance(a.get("act"), dict):
                isa[a["act"].get("var")] = a["is"]
            elif k == "ok" and isinstance(a.get("ok"), dict):
                oks[a["ok"].get("var")] = _depth(a.get("from"), self.s)
        if set(isa) != set(acts) or set(oks) != set(acts):
            raise C3.Unsupported("each Act binder needs an is[A] premise and an ok premise (the refuter's shape)")
        self.order = sorted(acts, key=lambda n: oks[n])
        if [oks[n] for n in self.order] != list(range(len(self.order))):
            raise C3.Unsupported("the ok premises step the Act binders one after another from s")
        self.action = isa


def _depth(t, s) -> int:
    if isinstance(t, dict) and t.get("var") == s:
        return 0
    if isinstance(t, dict) and set(t) == {"step", "from"}:
        return 1 + _depth(t["from"], s)
    raise C3.Unsupported("an ok premise from a state that is not s stepped by the binders")


# ---------------------------------------------------------------------------------------------------- evaluation
class Eval:
    """The law's terms at concrete binders: the B1 leaves by the compiled helpers, N, + and the comparisons exactly."""

    def __init__(self, d: Doc, m: S3.Model, shape: Shape):
        from ..undo import search as US
        self.d, self.m, self.shape = d, m, shape
        self.o = US.Obs(m)
        self.names = {k: v[0] for k, v in d.tm.helpers.items()}

    def args(self, env: dict):
        out = []
        for n, ty in self.shape.binders:
            v = env[n]
            if ty == "Reach":
                out.append({"$ref": v})
            elif ty == "Act":
                out.append(self.m.act(v))
            else:
                out.append({"$w": "0x%064x" % (int(v) & C3.MASK)})
        return out

    def leaf(self, t, env):
        key = json.dumps(t, sort_keys=True, separators=(",", ":"))
        r = self.o.settle({"fn": self.names[key], "args": lambda: self.args(env)}, None)
        out = r["out"]
        return int(out, 16) if isinstance(out, str) else bool(out)

    def value(self, t, env):
        k = C3.term_kind(t)
        if k in ("sread", "env", "ok", "is"):
            return self.leaf(t, env)
        if k == "wnat":
            return int(self.value(t["wnat"], env))
        if k == "cmp":
            a, b = (self.value(x, env) for x in t["args"])
            return {"<=": a <= b, "<": a < b, "==": a == b}[t["cmp"]]
        if isinstance(t, dict) and set(t) == {"plus"}:
            return self.value(t["plus"][0], env) + self.value(t["plus"][1], env)
        if isinstance(t, dict) and set(t) == {"nat"}:
            return int(t["nat"])
        if isinstance(t, dict) and set(t) == {"bool"}:
            return bool(t["bool"])
        if isinstance(t, dict) and "var" in t:
            return env[t["var"]]
        raise C3.Unsupported(f"no value for {json.dumps(t)[:120]}")

    def prop(self, p, env) -> bool:
        a, b = p["eq"]
        return self.value(a, env) == self.value(b, env)


# ---------------------------------------------------------------------------------------------------- the search
def _search_class():
    from ..undo import search as US

    class ContractSearch(US.UndoSearch):
        """holon.undo.search's prefix enumeration and successful-call candidates, over a contract law's binders."""

        def run(self, d: Doc, law: dict, shape: Shape, mode: str):
            self.d, self.law, self.shape, self.mode = d, law, shape, mode
            self.ev = Eval(d, self.m, shape)
            self.first = None
            st = law["statement"]
            self.prem = list(st.get("assume") or [])
            self.claims = C3.claims_of(law)
            return self.over_prefixes(shape.action[shape.order[0]], self.at)

        def pool(self, trace: list, steps: list) -> list[int]:
            ks = list(KEY_POOL)
            for st in list(trace) + list(steps):
                for v in _numbers(st.args):
                    ks.append(v)
            return self.key_pool(sorted(set(k & C3.MASK for k in ks)))[:24]

        def at(self, trace: list, g: str):
            return self.chain(trace, g, g, [], 0)

        def chain(self, trace: list, g0: str, g: str, steps: list, i: int):
            sh = self.shape
            if i == len(sh.order):
                return self.words(trace, g0, steps)
            a = sh.action[sh.order[i]]
            for st, g1 in self.x_candidates(g, trace + steps, a):
                w = self.chain(trace, g0, g1, steps + [st], i + 1)
                if w is not None:
                    return w
            return None

        def words(self, trace, g0, steps):
            sh = self.shape
            base = {sh.s: g0}
            base.update(dict(zip(sh.order, steps)))
            pools = [self.pool(trace, steps) for _w in sh.words]
            for combo in _product(pools):
                self.tick()
                env = dict(base, **dict(zip(sh.words, combo)))
                try:
                    if not all(self.ev.prop(p, env) for p in self.prem):
                        continue
                    if self.first is None:
                        self.first = {"prefix": list(trace), "steps": list(steps), "words": dict(zip(sh.words, combo))}
                    if self.mode == "inhabit":
                        return self.first
                    bad = [j for j, c in enumerate(self.claims) if not self.ev.prop(c, env)]
                except Exception as e:  # noqa: BLE001: a candidate the evaluator cannot settle is no candidate
                    self.log(f"  candidate skipped: {type(e).__name__}: {str(e)[:160]}")
                    continue
                if bad:
                    w = {"prefix": list(trace), "steps": list(steps), "words": dict(zip(sh.words, combo)),
                         "conjunct": bad[0]}
                    if self.accepted(w):
                        return w
            return None

        def accepted(self, w: dict) -> bool:
            why = None if self.accept is None else self.accept(w)
            if why is None:
                return True
            self.refused += 1
            self.log(f"  the witness is refused by the real-side check: {why} ({self.refused} refused)")
            return False

    return ContractSearch


def _numbers(v) -> list[int]:
    out = []
    if isinstance(v, bool):
        return out
    if isinstance(v, int):
        return [v]
    if isinstance(v, str) and v.startswith("0x") and len(v) <= 66:
        try:
            return [int(v, 16)]
        except ValueError:
            return out
    if isinstance(v, dict):
        for x in v.values():
            out += _numbers(x)
    if isinstance(v, list):
        for x in v:
            out += _numbers(x)
    return out


def _product(pools):
    if not pools:
        yield ()
        return
    for v in pools[0]:
        for rest in _product(pools[1:]):
            yield (v,) + rest


# ---------------------------------------------------------------------------------------------------- proof files
def _props(law: dict, facts: dict, tables: list[str]):
    """The premises' and conjuncts' (lhs, rhs, type) texts as the law file states them, and the helpers' argument
    list there."""
    tm, _lines, prem, cl = C3._statement(law, facts, tables, "law", None)
    return prem, cl, tm.args()


def _in_proof(text: str, law_args: str, lit_args: str) -> str:
    """A statement text of the law file as a proof file states it: the helpers qualified by Laws, the binders by
    the witness's literals."""
    import re
    return re.sub(r"(?<![\w.])(ct_[0-9a-f]{12}|c3_[A-Za-z0-9_]+)\(", r"Laws.\1(", text.replace(f"({law_args})",
                                                                                         f"({lit_args})"))


def witness_proof(law: dict, facts: dict, tables: list[str], tb: list, model_import: str, laws_import: str,
                  prefix: list, states: list, values: dict, tabs: dict, lit, kind: str, conjunct: int | None,
                  note: str) -> str:
    """The proof of the counter-law (kind "counter": every premise and the conjunct's falsity by computation) or of
    the inhabitant law ("nonvac": every premise by computation), at one witness: the prefix and the state after each
    of its steps, the binders' values, the hash tables."""
    from ..undo.proofs import _prefix_defs
    lid = law["law_id"]
    targs = [f"t_{n}()" for n, _h in tb]
    lines = [P3.PHEADER, "import Base", f"import {model_import} as M", f"import {laws_import} as Laws", "",
             f"# {GENERATOR} ({kind}): {note}"]
    lines += P3._table_defs(tb, tabs, lit)
    body, chain, state = _prefix_defs(tb, prefix, states, lit)
    lines += body
    names = {}
    for n, ty in law_binders(law):
        if ty == "Reach":
            names[n] = state
            continue
        v = values[n]
        text = lit.text(v) if ty == "Act" else lit.word("0x%064x" % (int(v) & C3.MASK))
        bty = "M.HAct" if ty == "Act" else "M.W"
        lines += [f"def b_{bname(n)}() -> {bty}:\n  {text}", ""]
        names[n] = f"b_{bname(n)}()"
    prem, cl, law_args = _props(law, facts, tables)
    lit_args = ", ".join([names[n] for n, _t in law_binders(law)] + targs)
    hs = []
    for i, (a, b, ty) in enumerate(prem):
        a, b = _in_proof(a, law_args, lit_args), _in_proof(b, law_args, lit_args)
        ty = ty.replace("M.", "M.")
        lines += [f"def h_{i}() -> {{{a} == {b} : {ty}}}:\n  {{==}}", ""]
        hs.append(f"h_{i}()")
    if kind == "counter":
        a, b, ty = cl[conjunct]
        a, b = _in_proof(a, law_args, lit_args), _in_proof(b, law_args, lit_args)
        lines += ["def true_ne_false(p: {True{} == False{} : Bool}) -> Empty:\n  (%p : M.is_true(_)\n  Unit{})", ""]
        if ty == "Bool" and b == "True{}":
            lines += [f"def cz() -> {{{a} == False{{}} : Bool}}:\n  {{==}}", ""]
            tail = "e => true_ne_false((%e : {_ == False{} : Bool}\n  cz()))"
        else:
            eq = "Nat.is_eq" if ty == "Nat" else ("M.w_eq" if ty == "M.W" else None)
            if eq is None:
                raise C3.Unsupported(f"a counter-law on a {ty} equality")
            lines += [f"def cz() -> {{{eq}({a}, {b}) == False{{}} : Bool}}:\n  {{==}}", "",
                      f"def cr() -> {{{eq}({b}, {b}) == True{{}} : Bool}}:\n  {{==}}", ""]
            tail = (f"e => true_ne_false(Equal.trans(Bool, True{{}}, {eq}({b}, {b}), False{{}}, Equal.sym(Bool, "
                    f"{eq}({b}, {b}), True{{}}, cr()), (%e : {{{eq}(_, {b}) == False{{}} : Bool}}\n  cz())))")
        items = hs
    else:
        tail = hs[-1]
        items = hs[:-1]
    tup = tail
    for x in reversed(items):
        tup = f"({x}, {tup})"
    for n, ty in reversed(law_binders(law)):
        if ty == "Reach":
            tup = f"({state}, ({chain}, {tup}))"
        else:
            tup = f"({names[n]}, {tup})"
    for t in reversed(targs):
        tup = f"({t}, {tup})"
    lines.append(f"def Laws.{C3.law_name(lid, kind)}():\n  {tup}")
    return "\n".join(lines) + "\n"


def law_binders(law: dict) -> list[tuple[str, str]]:
    return [(b["name"], str(b.get("type", ""))) for b in law["statement"].get("binders") or []]


# ---------------------------------------------------------------------------------------------------- deciding
class Run:
    def __init__(self, milestone: str, root: Path, sidecar: str | None, gen: Path | None, out: Path | None,
                 log=print, deadline: float | None = None):
        self.rc = run3.Ctx(milestone, root, sidecar, gen, out, log)
        self.m, self.root, self.gen, self.out, self.log = milestone, Path(root), self.rc.gen, self.rc.out, log
        self.deadline = deadline
        self.real = None

    def close(self):
        if self.real is not None:
            self.real.close()
        self.rc.close()

    def paths(self, lid: str) -> dict:
        g = self.gen
        return {"laws": g / "laws" / lid / "LAWS.bend", "proofs": g / "proofs" / lid, "nonvac": g / lid / "nonvac"}

    def model_import(self, d: Doc, at: Path) -> str:
        return rel(d.import_file, at)

    def statement_hash(self, lid: str) -> str:
        reg = json.loads((self.root / "laws" / self.m / "REGISTRY.json").read_text())
        sh = (reg.get("statements") or {}).get(lid)
        if sh is None:
            raise C3.Unsupported(f"{lid}: laws/{self.m}/REGISTRY.json lists no statement hash (holon derive first)")
        return sh

    def write_law(self, d: Doc, law: dict, sh: str, kind: str = "law", conjunct=None) -> Path:
        p = self.paths(law["law_id"])["laws"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(C3.law_file(law, d.facts, sh, self.model_import(d, p.parent), d.tables, kind, conjunct),
                     encoding="utf-8")
        return p

    def real_side(self, d: Doc):
        if not self.rc.sc.binding:
            return None
        if self.real is None:
            self.real = run3.Real(self.rc, d.facts)
        return self.real

    # ---------------------------------------------------------- the search
    def search(self, d: Doc, law: dict, shape: Shape, mode: str, real=None):
        from ..undo import search as US
        accept, kept = None, {}
        if real is not None and mode == "refute":
            def accept(w):
                try:
                    w2 = self.repair(d, real, w)
                except Exception as e:  # noqa: BLE001: a witness the real side cannot run is no witness
                    return f"the real side cannot run it: {type(e).__name__}: {str(e)[:200]}"
                if w2 is None:
                    return "a step that succeeds on the model does not succeed on the deployment"
                if self.claim_value(d, law, shape, w2, w["conjunct"]) is not False:
                    return "with the deployment's call answers the model finds the conjunct true"
                kept["w"] = dict(w2, conjunct=w["conjunct"])
                return None
        sorts = json.loads((self.root / "gen" / self.m / "sorts" / "assignment.json").read_text())
        sorts = sorts["models"][run3.model_name(d.doc_rel)]["assignment"]
        s = _search_class()(d.factory, d.facts, sorts, BUDGET, log=self.log, accept=accept, deadline=self.deadline)
        w, bound = s.run(d, law, shape, mode)
        if mode == "refute" and w is not None:
            w = kept.get("w", w)
        return w, bound, s.first

    def steps_json(self, d: Doc, steps: list) -> list:
        fns = run3.fn_names(d.docm)
        return [run3.step_json(d.docm, st, fns) for st in steps]

    def repair(self, d: Doc, real, w: dict):
        """The witness's steps with every external call answered as the deployment answers it (its run there), or
        None when a step does not succeed there."""
        from ..undo import run as UR
        steps = list(w["prefix"]) + list(w["steps"])
        (obs, calls), = UR.real_runs(real, [self.steps_json(d, steps)])
        if any(o["status"] != "ok" for o in obs):
            return None

        def env_of(st, cs):
            env = json.loads(json.dumps(st.env))
            env.pop("_unanswered", None)
            env["calls"] = list(cs)
            return S3.Step(st.action, json.loads(json.dumps(st.args)), env)
        out = [env_of(st, calls[i]) for i, st in enumerate(steps)]
        n = len(w["prefix"])
        return dict(w, prefix=out[:n], steps=out[n:])

    def claim_value(self, d: Doc, law: dict, shape: Shape, w: dict, j: int):
        """The conjunct j at the witness on a fresh model (its prefix run from s0 with the steps' own answers), or None
        when a step does not succeed."""
        from ..undo import search as US
        m = d.factory()
        g = m.s0()
        for st in w["prefix"]:
            code, g, _c = m.run_step(g, US.fresh_step(st), save=True)
            if code != 0:
                return None
        env = {shape.s: g}
        env.update(dict(zip(shape.order, [US.fresh_step(x) for x in w["steps"]])))
        env.update(w["words"])
        return Eval(d, m, shape).prop(C3.claims_of(law)[j], env)

    def args_of(self, law: dict, shape: Shape, w: dict):
        acts = dict(zip(shape.order, w["steps"]))

        def f(m, g):
            out = []
            for n, ty in law_binders(law)[1:]:
                out.append(m.act(acts[n]) if ty == "Act" else {"$w": "0x%064x" % (int(w["words"][n]) & C3.MASK)})
            return out
        return f

    def emit_witness(self, d: Doc, law: dict, sh: str, shape: Shape, w: dict, kind: str) -> tuple[Path, dict, str, dict]:
        from ..undo import search as US
        if law_binders(law)[0][1] != "Reach":
            raise C3.Unsupported("the Reach binder comes first (the witness's state)")
        kh, shtab, _val, states = US.settle_witness(d.factory, w["prefix"], "c3_touch", self.args_of(law, shape, w))
        m = d.factory(empty=True, native=False)
        acts = dict(zip(shape.order, w["steps"]))
        values = {n: (m.act(acts[n]) if ty == "Act" else int(w["words"][n])) for n, ty in law_binders(law)[1:]}
        lid = law["law_id"]
        dd = self.paths(lid)["proofs"] / "witness" if kind == "counter" else self.paths(lid)["nonvac"]
        dd.mkdir(parents=True, exist_ok=True)
        if kind == "counter":
            lp = self.write_law(d, law, sh, "counter", w["conjunct"])
        else:
            lp = dd / "LAWS.bend"
            lp.write_text(C3.law_file(law, d.facts, sh, self.model_import(d, dd), d.tables, "nonvac"),
                          encoding="utf-8")
        p = dd / "PROOF.bend"
        note = (f"the witness (prefix {len(w['prefix'])} steps, then {', '.join(st.action for st in w['steps'])})"
                + (f", conjunct {w['conjunct']} false by computation" if kind == "counter" else
                   ", every premise by computation"))
        p.write_text(witness_proof(law, d.facts, d.tables, d.tb, self.model_import(d, dd), rel(lp, dd),
                                   [m.act(st) for st in w["prefix"]], states, values,
                                   {"keccak256": kh, "sha256": shtab}, P3.Lit(d.recs), kind,
                                   w.get("conjunct"), note), encoding="utf-8")
        checker, verdict = run3.check_file(p)
        return p, checker, verdict, {"keccak256": kh, "sha256": shtab}

    def witness_json(self, d: Doc, law: dict, shape: Shape, w: dict, tabs: dict) -> dict:
        out = {"prefix": self.steps_json(d, w["prefix"]),
               "hashes": {h: [["0x" + k[2:], "0x%064x" % v] for k, v in sorted((tabs.get(h) or {}).items())]
                          for h in ("keccak256", "sha256")}}
        for n, st in zip(shape.order, w["steps"]):
            out[n] = self.steps_json(d, [st])[0]
        for n in shape.words:
            out[n] = "0x%064x" % (int(w["words"][n]) & C3.MASK)
        if "conjunct" in w:
            out["conjunct"] = w["conjunct"]
        return out

    # ---------------------------------------------------------- the replay
    def replay(self, d: Doc, law: dict, shape: Shape, wj: dict, real) -> dict:
        """The witness on the real contract: its steps there, and the words its conjunct reads at their real slots."""
        from ..replay_fragments import run_harness
        from ..undo import search as US
        from . import skeys
        steps = list(wj["prefix"]) + [wj[n] for n in shape.order]
        n0 = len(wj["prefix"])
        j = int(wj["conjunct"])
        claim = C3.claims_of(law)[j]
        # the model's words (and the keys of every read) at the witness
        m = d.factory()
        g = m.s0()
        for s in wj["prefix"]:
            _c, g, _x = m.run_step(g, US.fresh_step(run3.step_of_json(s)), save=True)
        env = {shape.s: g}
        env.update({n: US.fresh_step(run3.step_of_json(wj[n])) for n in shape.order})
        env.update({n: int(wj[n], 16) for n in shape.words})
        ev = Eval(d, m, shape)
        reads = []
        _reads_of(claim, reads)
        slots, plan = [], []
        for t in reads:
            fam = C3.family(d.facts, t["sread"])
            mem = C3.member(fam, t.get("member"))
            mslot = int(mem.get("slot", 0)) if mem else 0
            path, v = [], fam
            for kt in t.get("keys") or []:
                kw = ev.value(kt, env)
                nb, masked = C3.key_bytes(v.get("key"))
                if masked:
                    kw &= (1 << (8 * nb)) - 1
                path.append(["m", kw & C3.MASK, 0])
                v = v.get("inner") if isinstance(v.get("inner"), dict) else v
            if path:
                path[-1][2] = mslot
                slot = skeys.real_slot(int(fam["slot"]), 0, [tuple(x) for x in path])
            else:
                slot = skeys.real_slot(int(fam["slot"]), mslot, ())
            holder = mem if mem is not None else fam
            width = int(holder.get("width", 256) or 256)
            off = int(holder.get("offset", 0) or 0) if (mem is not None or not path) else 0
            at = _depth(t["from"], shape.s)
            slots.append(slot)
            plan.append((t, slot, at, off, width))
        slots = sorted(set(slots))
        real.setup()
        runs = run_harness(real.proj, real.tc, real.binding, [real.steps(steps)], slots, real.init, tag="contract3")
        tr = runs[0]
        execs = [x for x in tr.execs if x.id != "d"]
        dep = next((x for x in tr.execs if x.id == "d"), None)
        outcomes = ["ok" if x.ok else "rev " + run3.revert_text(bytes.fromhex(x.ret[2:])) for x in execs]
        dumps_ = [dict(zip(slots, [int(str(v), 16) if isinstance(v, str) else int(v) for v in (x.dump or [])]))
                  for x in execs]
        dep_dump = dict(zip(slots, [int(str(v), 16) if isinstance(v, str) else int(v) for v in ((dep.dump if dep else None)
                                                                                                or [])]))

        def state_at(k):   # the real words after the prefix and k steps of the binders
            i = n0 + k - 1
            return dep_dump if i < 0 else dumps_[i]
        real_words, model_words = {}, {}
        for t, slot, at, off, width in plan:
            key = json.dumps(t, sort_keys=True, separators=(",", ":"))
            wv = (state_at(at).get(slot, 0) >> (8 * off)) & ((1 << width) - 1)
            real_words[key] = wv
            model_words[key] = ev.leaf(t, env)

        class RealEval(Eval):
            def leaf(self, t, env2):
                key = json.dumps(t, sort_keys=True, separators=(",", ":"))
                if C3.term_kind(t) == "sread":
                    return real_words[key]
                return Eval.leaf(self, t, env2)
        rv = RealEval(d, m, shape)
        try:
            real_truth = rv.prop(claim, env)
        except Exception:  # noqa: BLE001
            real_truth = None
        agree = all(real_words[k] == model_words[k] for k in real_words)
        ok = all(o == "ok" for o in outcomes) and agree and real_truth is False
        return {"trace": steps, "real": outcomes, "slots": ["0x%064x" % s for s in slots],
                "words_agree": agree, "conjunct": j, "conjunct_on_real": real_truth,
                "status": "passed" if ok else "failed"}

    # ---------------------------------------------------------- one law
    def decide(self, lid: str) -> dict:
        from . import residue
        law = json.loads((self.rc.laws_dir / f"{lid}.json").read_text())
        sh = self.statement_hash(lid)
        d = Doc(self.rc, law)
        try:
            return self._decide(d, law, sh, residue)
        finally:
            d.close()

    def _decide(self, d: Doc, law: dict, sh: str, residue) -> dict:
        lid = law["law_id"]
        shutil.rmtree(self.paths(lid)["proofs"], ignore_errors=True)
        shutil.rmtree(self.paths(lid)["nonvac"].parent, ignore_errors=True)
        lp = self.write_law(d, law, sh)
        attempts, status, prim, wj, rep, bound, nonvac, diag = [], "UNKNOWN", None, None, None, None, None, None
        shape = Shape(law)
        # the proof class (B6)
        t0 = time.time()
        try:
            text, note = residue.prove(law, d.facts, d.text, d.tables, self.model_import(d, self.paths(lid)["proofs"]),
                                       rel(lp, self.paths(lid)["proofs"]))
        except residue.NoProof as e:
            attempts.append({"kind": "proof", "generator": residue.CLASS, "marker": None, "error": str(e)[:2000]})
            text = None
        if text is not None:
            pp = self.paths(lid)["proofs"] / "PROOF.bend"
            pp.parent.mkdir(parents=True, exist_ok=True)
            pp.write_text(text, encoding="utf-8")
            checker, verdict = run3.check_file(pp)
            att = {"kind": "proof", "generator": residue.CLASS, "marker": checker["marker"], "checker": checker,
                   "verdict": verdict, "note": note, "seconds": round(time.time() - t0, 1)}
            if checker["marker"] == "ALL PROOFS CHECK" and verdict == "checked":
                status = "PROVED"
                prim = {"proof": rel(pp, self.root), "checker": checker, "verdict": verdict}
            else:
                att["error"] = f"bend2 {checker['marker']}, BendTT {verdict}" + (
                    f" (failing at {checker.get('failing')})" if checker.get("failing") else "")
                shutil.rmtree(self.paths(lid)["proofs"], ignore_errors=True)
            attempts.append(att)
        real = self.real_side(d)
        if status == "PROVED":
            # non-vacuity (B7): the first candidate whose premises hold
            w, sbound, _first = self.search(d, law, shape, "inhabit")
            attempts.append({"kind": "refute", "engine": "holon.sorts.contract3_run (inhabitant)", "budget": BUDGET,
                             "bound": sbound, "found": w is not None})
            nonvac = self.inhabit(d, law, sh, shape, w, attempts)
        else:
            t1 = time.time()
            w, bound, _first = self.search(d, law, shape, "refute", real)
            attempts.append({"kind": "refute", "engine": "holon.sorts.contract3_run", "budget": BUDGET,
                             "bound": bound, "found": w is not None, "seconds": round(time.time() - t1, 1)})
            self.log(f"{lid}: {'witness' if w else 'no witness'} ({bound})")
            if w is not None:
                p, checker, verdict, tabs = self.emit_witness(d, law, sh, shape, w, "counter")
                lp = self.paths(lid)["laws"]
                wj = self.witness_json(d, law, shape, w, tabs)
                att = {"kind": "counter", "checker": checker, "verdict": verdict, "conjunct": w["conjunct"]}
                attempts.append(att)
                if checker["marker"] == "ALL PROOFS CHECK":
                    status = "REFUTED"
                    prim = {"proof": rel(p, self.root), "checker": checker, "verdict": verdict}
                    bound = None
                else:
                    diag = (f"the counter-law at the model's witness does not check (bend2 {checker['marker']}"
                            + (f", failing at {checker.get('failing')}" if checker.get("failing") else "") + ")")
                    shutil.rmtree(self.paths(lid)["proofs"], ignore_errors=True)
                    lp = self.write_law(d, law, sh)
                    bound = f"{bound}; a model witness was found but {diag}"
        if status == "REFUTED":
            rep = self.replay(d, law, shape, wj, real) if real is not None else None
        rec = self.record(d, law, sh, status, prim, wj if status == "REFUTED" else None, bound, nonvac, attempts,
                          self.paths(lid)["laws"], rep, diag)
        return rec

    def inhabit(self, d: Doc, law: dict, sh: str, shape: Shape, w, attempts: list):
        lid = law["law_id"]
        if w is None:
            attempts.append({"kind": "inhabitant", "exit_code": None, "error": "the search found no candidate whose "
                                                                              "premises hold"})
            return None
        p, checker, verdict, tabs = self.emit_witness(d, law, sh, shape, w, "nonvac")
        att = {"kind": "inhabitant", "law": rel(p.parent / "LAWS.bend", self.root), "proof": rel(p, self.root),
               "exit_code": checker["exit_code"], "marker": checker["marker"], "verdict": verdict}
        if checker["marker"] != "ALL PROOFS CHECK":
            att["error"] = f"bend2 {checker['marker']}"
        attempts.append(att)
        if checker["marker"] != "ALL PROOFS CHECK":
            return None
        return {"status": "inhabited", "law": rel(p.parent / "LAWS.bend", self.root),
                "witness": self.witness_json(d, law, shape, w, tabs), "reachable": True, "degenerate": False,
                "parent_statement_hash": sh,
                "bound": f"a reachable state of {len(w['prefix'])} steps from s0 and its binders satisfy every "
                         "premise (checked by bend)"}

    # ---------------------------------------------------------- the record
    def record(self, d: Doc, law: dict, sh: str, status: str, prim, witness, bound, nonvac, attempts, lp: Path, rep,
               diag) -> dict:
        from .. import records as R
        lid = law["law_id"]
        cone = R.cone(lp.read_text(encoding="utf-8"), d.text)
        if rep is not None:
            replay = {"status": rep["status"], "detail": f"real outcomes {rep['real']}; words agree "
                                                         f"{rep['words_agree']}; conjunct {rep['conjunct']} on the "
                                                         f"real words {rep['conjunct_on_real']}"}
        elif witness is not None:
            replay = {"status": "not_applicable", "detail": "no binding: the milestone has no real side"}
        else:
            replay = {"status": "not_applicable", "detail": f"{status}: no witness to replay"}
        rec = {"law_id": lid, "statement_hash": sh, "facts_sha256": law["facts_sha256"], "status": status,
               "scope": "unbounded", "premises": [],
               "kernel": {"name": "bend", "version": run3.bend_version(),
                          "verdict": (prim or {}).get("verdict", "not_run")},
               "artifacts": {"laws": rel(lp, self.root), "proof": (prim or {}).get("proof"),
                             "model": rel(d.model_file, self.root),
                             "law_name": C3.law_name(lid, "counter" if status == "REFUTED" else "law")},
               "checker": (prim or {}).get("checker") or {"exit_code": None, "marker": "not_run"},
               "triage": "finding" if status == "REFUTED" else "none", "replay": replay, "attempts": attempts,
               "rule": law["rule"], "subform": law.get("subform"), "bound": bound}
        if witness is not None:
            rec["witness"] = witness
            rec["difference"] = {"lhs": False, "rhs": True}
        if diag:
            rec["diagnosis"] = diag
        if rep is not None:
            rec["replay_entry"] = rep
        try:
            b, match = R.resolve_bundle(rec["facts_sha256"], law["facts"], self.root, d.text, set(cone), self.m)
            assumptions = R.model_assumptions(b["facts_sha256"], set(cone), self.root, law["facts"], self.m)
        except R.LedgerError:
            match, assumptions = "none", []
        rec.update({"record_version": R.RECORD_VERSION, "prover": "generator",
                    "model_sha256": run3.sha256_file(d.model_file), "compiled_sha256": run3.sha256_file(
                        d.ev.compiled()), "generator_sha256": generator_sha256(self.root),
                    "cone": cone, "ledger_match": match, "model_assumptions": assumptions,
                    "scope_v2": R.scope_v2(law, rec), "kernels": R.kernels(rec),
                    "independence_class": R.independence_class(rec), "refinement_refs": [],
                    "coverage": R.coverage_field(law, self.root) if self.m.startswith("M") else None,
                    "non_vacuity": nonvac or {"status": "counter_witness" if status == "REFUTED" else "unknown",
                                              "law": rel(lp, self.root) if status == "REFUTED" else None,
                                              "witness": None, "reachable": None, "degenerate": None,
                                              "parent_statement_hash": sh,
                                              "bound": "the accepted counter-law inhabits the premises"
                                              if status == "REFUTED" else "no inhabitant was checked"},
                    "witness_provenance": {"solidity": "internal_harness"} if status == "REFUTED" else None,
                    "filter_bin": "finding" if status == "REFUTED" else None,
                    **R.evidence_fields(law, {"status": status}, self.root)})
        rec["statement"] = law.get("notes", "")
        return rec


def _reads_of(t, out: list) -> None:
    if C3.term_kind(t) == "sread":
        if t not in out:
            out.append(t)
        for k in t.get("keys") or []:
            _reads_of(k, out)
        return
    if isinstance(t, dict):
        for v in t.values():
            _reads_of(v, out)
    elif isinstance(t, list):
        for v in t:
            _reads_of(v, out)


def generator_sha256(root: Path) -> str:
    from ..records import _holon_imports
    seen, todo = set(), list(GEN_FILES) + list(run3.GEN3)
    while todo:
        r = todo.pop()
        if r in seen or not (root / r).is_file():
            continue
        seen.add(r)
        if r.endswith(".py"):
            todo.extend(sorted(_holon_imports(r, root) - seen))
    h = hashlib.sha256()
    for r in sorted(seen):
        h.update(r.encode() + b"\0" + (root / r).read_bytes() + b"\0")
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------------- main
def main(argv: list) -> int:
    """holon run --milestone M --laws ID,.. (this runner's laws): decide each, write its record."""
    ap = argparse.ArgumentParser(prog="holon run (typed contract laws)")
    ap.add_argument("cmd")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--sidecar")
    ap.add_argument("--laws")
    ap.add_argument("--out")
    ap.add_argument("--gen-dir")
    ap.add_argument("--deadline", type=float)
    a, _unknown = ap.parse_known_args(argv)
    mine = contract_ids(a.milestone, ROOT)
    want = [x.strip() for x in (a.laws or "").split(",") if x.strip()] or mine
    ids = [x for x in want if x in mine]
    run = Run(a.milestone, ROOT, a.sidecar, Path(a.gen_dir).resolve() if a.gen_dir else None,
              Path(a.out).resolve() if a.out else None, deadline=a.deadline)
    rc = 0
    try:
        run.out.mkdir(parents=True, exist_ok=True)
        for lid in ids:
            try:
                rec = run.decide(lid)
            except C3.Unsupported as e:
                print(f"{lid}: not decided: {e}")
                rc = 1
                continue
            (run.out / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
            print(f"{lid}: {rec['status']}")
    finally:
        run.close()
    return rc
