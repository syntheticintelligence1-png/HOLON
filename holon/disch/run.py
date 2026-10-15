"""holon run and holon replay for the DISCH laws (BUILD_PLAN I31; the contract is the docstring of
tests_m3/test_disch.py, "Deciding", "Records" and "Replay").

A DISCH law is decided over I30's typed model of its document (gen/<M>/sorts/models/<model>.bend) and its DISCH
section (gen/<M>/disch/models/<model>.disch.bend, holon.disch.section):

  forall laws    (blocking, revert, external_none) the proof generators first (holon.disch.proofs: frame,
                 chain_revert; checked by bend2, then BendTT); a law they do not prove is searched for a refutation
                 (holon.disch.search: I30's S1-S3 from R0, the sidecar's budget); a refutation is written as a
                 counter-law in A30's shape (every premise a closed lemma that computes one step: the hash tables,
                 each prefix state a literal, the law's step) and checked by both kernels; with a binding it must
                 also replay on the real contract (Q22)
  external       searched for a witness, written as the existential law's proof in the same shape, checked by both
                 kernels and replayed; an external law is never REFUTED
  inhabitants    a PROVED forall law's premises at a reachable state (gen/<M>/<id>/nonvac/, G11V)

The search evaluates B, c and the law's claim with Bend's own functions: the typed model and its DISCH section
compiled together (outside the repo, ~/.holon/cache/disch) and run by I30's evaluator with the real hash of every key
they look up. Every outcome is Bend's: a search result is only a candidate until its file checks.

Nothing here names a target, an action, a class or a law.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from ..gen.mlaws import law_name
from ..machine_bend import bname
from ..sorts import evaluate3 as E3
from ..sorts import run3 as R3
from ..sorts import search3 as S3
from ..sorts.proofs3 import Lit, PHEADER, _table_defs, _trace_defs, rel_import, tabs_binders
from ..analysis import closure as C
from . import proofs as P
from . import search as DS
from . import section as SEC

ROOT = Path(__file__).resolve().parents[2]
SUBFORMS = ("blocking", "revert", "external", "external_none")
# the last-step syntheses of one law: every state where B holds within the sidecar's budget is tried in S1+S2 and in
# S3 (each with I30's synthesis of every action of the law's set); None: no cap beyond the preregistered budget (a cap
# here would search fewer prefixes than the sidecar's budget names)
LAST_STEP_STATES = None
# the modules that decide a DISCH law, beside I30's (their source is in the records' generator_sha256)
GEN_DISCH = ["holon/disch/run.py", "holon/disch/search.py"]
dumps = R3.dumps
rel = R3.rel


def generator_sha256(root: Path) -> str:
    """I30's generator closure (holon.sorts.run3.GEN3) and the DISCH deciding modules with their holon imports."""
    from ..records import _holon_imports
    seen, todo = set(), list(R3.GEN3) + GEN_DISCH
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


def _tail(out: str, n: int = 2000) -> str:
    return (out or "")[-n:]


def check_file(p: Path) -> tuple[dict, str]:
    """(checker, verdict) of a Bend file: bend2, then BendTT (--verdict) when bend2 accepts it. A time box or BendTT's
    fuel running out is a budget exhaustion, recorded as such (checker["budget_exhausted"], with the seconds), never a
    rejection (Q22); a BendTT rejection of a file bend2 accepts is a cross-kernel disagreement (Q8: blocking), named in
    checker["disagreement"]. BendTT's output is kept (its tail)."""
    from .. import bend
    t = time.time()
    r = bend.check(p)
    checker = {"exit_code": r.code, "marker": "ALL PROOFS CHECK" if r.ok else "SOME PROOFS FAIL",
               "seconds": round(time.time() - t, 3)}
    if not r.ok:
        if r.code is None:
            checker["budget_exhausted"] = f"bend2 time box ({r.seconds} s)"
        m = re.search(r"(?m)^Location:\s*(\S+)", r.out or "")
        checker["failing"] = m.group(1) if m else None
        return checker, "not_run"
    v = bend.check_verdict(p)
    checker["bendtt"] = {"exit_code": v.code, "seconds": v.seconds, "output_tail": _tail(v.out)}
    if v.ok:
        return checker, "checked"
    if v.code is None:
        checker["budget_exhausted"] = f"BendTT time box ({v.seconds} s)"
        return checker, "budget_exhausted"
    if re.search(r"(?i)out of fuel", v.out or ""):
        checker["budget_exhausted"] = f"BendTT out of fuel ({v.seconds} s)"
        return checker, "budget_exhausted"
    checker["disagreement"] = "bend2 accepts the file and BendTT rejects it: a cross-kernel disagreement (Q8, Q22)"
    return checker, "failed"


def _why(checker: dict, verdict: str) -> str:
    if checker.get("budget_exhausted"):
        return f"budget exhausted: {checker['budget_exhausted']}"
    if checker["marker"] != "ALL PROOFS CHECK":
        return "bend2 rejected the proof"
    if checker.get("disagreement"):
        return "BendTT rejected the proof that bend2 accepts: " + checker["disagreement"]
    return f"BendTT {verdict}"


def W(t: int) -> dict:
    return {"$w": "0x%064x" % int(t)}


# ------------------------------------------------------------------------------------------------ the judge
class Judge:
    """The DISCH section's functions on a model compiled with it (names prefixed D_): blocked(st, t), the law's claim
    and its premise, with the hash keys they look up learned (real hashes) and the external calls of a step answered as
    the search answers them."""

    def call(self, m, fn: str, args, st=None):
        for _ in range(40):
            r = m.mreq({"fn": fn, "args": args() + m.tables()})
            new = m.learn(r)
            changed = m.answer_calls(st, r.get("calls") or []) if st is not None else False
            if new or changed:
                continue
            return r["out"]
        raise RuntimeError(f"{fn}: the hash keys did not settle")

    def blocked(self, m, tag: str, g: str, t: int) -> bool:
        return self.call(m, f"D_blk_{tag}", lambda: [{"$call": "gh_get_st", "args": [{"$ref": g}]}, W(t)]) is True

    def claim(self, m, law: dict, g: str, st, t: int):
        x = SEC.law_key(law["law_id"])
        return self.call(m, f"D_disch_{x}", lambda: [m.act(st), {"$ref": g}, W(t), m.act(st)["f"]["en"]], st)

    def decides(self, m, law: dict, g: str, st, t: int) -> bool:
        """The step refutes a forall law (its claim false) or witnesses an external law (its claim true)."""
        v = self.claim(m, law, g, st, t)
        return v is True if law["subform"] == "external" else v is False

    def premise(self, m, law: dict, g: str, st, t: int) -> bool:
        x = SEC.law_key(law["law_id"])
        return self.call(m, f"D_prem_{x}", lambda: [m.act(st), {"$ref": g}, W(t), m.act(st)["f"]["en"]], st) is True


def combined_text(model_text: str, section_text: str) -> str:
    """The typed model and its DISCH section as one program (the section's definitions prefixed D_, the model's
    qualifier dropped): what the search evaluates. The section file itself imports the model; this text is never
    checked, only run."""
    body = "\n".join(ln for ln in section_text.split("\n") if not ln.startswith("import "))
    names = sorted(set(re.findall(r"(?m)^def (\w+)\(", body)), key=len, reverse=True)
    for n in names:
        body = re.sub(rf"(?<![\w.]){re.escape(n)}(?=\()", "D_" + n, body)
    body = re.sub(r"(?<![\w.])M\.", "", body)
    return model_text.rstrip("\n") + "\n\n" + body + "\n"


# ------------------------------------------------------------------------------------------------ one document
class Doc:
    """One document's typed model, DISCH section, proof context, judge model and shared exploration."""

    def __init__(self, run: "Run", doc_rel: str, an: dict):
        ctx = run.ctx
        self.run = run
        self.doc_rel = doc_rel
        self.an = an
        self.ev, self.init, self.model_f, self.mm, self.doc = ctx.model(doc_rel)
        self.mp = ctx.model_path(doc_rel)
        self.ip = ctx.import_path(doc_rel)
        self.text = self.ip.read_text(encoding="utf-8")
        self.hashes = self.ev.hashes()
        self.sec = SEC.Section(an, self.mm, self.text, self.hashes)
        self.sdir = ctx.gen / "disch" / "models"
        self.stext = self.sec.text(rel_import(self.sdir, self.ip))
        self.spath = SEC.write_section(self.sdir, an["model"], self.stext)
        self.simp = self.sdir / SEC.section_file(an["model"])
        self.g = P.Gen(self.text, self.sec, an)
        self.tb = tabs_binders(self.hashes)
        self.lit = Lit(self.ev.recs)
        ctext = combined_text(self.text, self.stext)
        d = Path.home() / ".holon" / "cache" / "disch" / hashlib.sha256(ctext.encode()).hexdigest()[:32]
        d.mkdir(parents=True, exist_ok=True)
        cp = d / "model.bend"
        if not cp.is_file() or cp.read_text(encoding="utf-8") != ctext:
            cp.write_text(ctext, encoding="utf-8")
        self.cev = E3.Evaluator.build(cp, self.doc)
        hp = ctx.root / "results" / ctx.m / "sorts" / "refinement" / "hints.json"
        self.hints = S3.Hints(json.loads(hp.read_text()) if hp.is_file() else None)
        self.doc_json = json.loads((ctx.root / doc_rel).read_text())
        ap = ctx.gen / "sorts" / "assignment.json"
        self.sorts = json.loads(ap.read_text())["models"][an["model"]]["assignment"] if ap.is_file() else {}
        self.judge = Judge()
        self.judge.clock = self.sec.has_time
        self._ex = None

    def factory(self, empty: bool = False, native: bool = True):
        i = dict(self.init)
        if empty:
            i["preimages"] = []
        mdl = S3.Model(self.cev, i, self.hints, self.run.ctx.root / self.doc_rel, native=native)
        # every model of this document shares one evaluator process: each names its stored states with its own
        # prefix, so that a witness's settling never overwrites a state the shared exploration holds
        pfx = mdl.tid

        def fresh(m=mdl, p=pfx) -> str:
            m.n += 1
            return f"{p}g{m.n}"
        mdl.fresh = fresh
        return mdl

    @property
    def ex(self) -> DS.Explorer:
        if self._ex is None:
            self._ex = DS.Explorer(self.factory(), self.doc_json, self.sorts, self.run.sc.search, self.an,
                                   log=self.run.log)
        return self._ex

    def close(self):
        self.cev.close()


def law_entries(an: dict, law: dict) -> list[str]:
    """The actions a law's last step is drawn from, the ones most likely to decide it first: blocking, the closure's
    unsafe writers first; revert, the excluded actions; external and external_none, the class's writers first."""
    sf = law["subform"]
    if sf == "revert":
        return sorted(law["excluded"])
    first: list = []
    if sf == "blocking":
        b = next(x for x in an["basis"] if x["tag"] == law["tag"])
        first = sorted((b["classes"].get(law["class"]) or {}).get("unsafe") or {})
    else:
        first = sorted(law.get("writers") or [])
    return first + [a for a in sorted(law["closure"]) if a not in first]


# ------------------------------------------------------------------------------------------------ Bend files
LHEADER = P.LHEADER


def nonvac_law_text(lid: str, statement_hash: str, model_import: str, section_import: str, tabs: list) -> str:
    x = SEC.law_key(lid)
    idx = "".join(f"{n}, " for n in tabs)
    lines = [LHEADER, f"# non-vacuity of {lid} (statement_hash {statement_hash}): its premise prem_{x} is inhabited by "
             "a reachable state, a time, a step and an environment", "import Base", f"import {model_import} as M",
             f"import {section_import} as D", "", f"law nv_{lid.lower()}:"]
    for n in tabs:
        lines.append(f"  exs {n}: List<&2, M.HKB>")
    lines += ["  exs s: M.GSt", f"  exs r_s: M.Reach<{idx}s>", "  exs t: M.W", "  exs a: M.HAct", "  exs e: M.HEnv",
              f"  {{D.prem_{x}(a, s, t, e{''.join(', ' + n for n in tabs)}) == True{{}} : Bool}}"]
    return "\n".join(lines) + "\n"


def trace_proof(lid: str, d: Doc, model_import: str, section_import: str, laws_import: str, acts: list, tables: dict,
                states: list, t: int, kind: str, note: str) -> str:
    """The proof of a witness (A30's shape): the hash tables, each prefix action and literal state, one lemma per
    prefix step, the Reach chain, t and the last step's environment as literals, and one closed lemma that computes
    the law's claim at the last step. kind: "counter" (the claim is false: the counter-law of a forall law), "exists"
    (true: an external law) or "nonvac" (the premise is true: an inhabitant)."""
    x = SEC.law_key(lid)
    tb = d.tb
    lit = d.lit
    targs = "".join(f", t_{n}()" for n, _h in tb)
    lines = [PHEADER, "import Base", f"import {model_import} as M", f"import {section_import} as D",
             f"import {laws_import} as Laws", "", f"# {note}"]
    lines += _table_defs(tb, tables, lit)
    body, chain, state = _trace_defs(tb, acts, states, lit)
    lines += body
    n = len(acts) - 1
    last = f"w_a{n}()"
    lines.append(f"def w_t() -> M.W:\n  {lit.word('0x%064x' % int(t))}")
    lines.append("")
    lines.append(f"def w_e() -> M.HEnv:\n  {lit.text(acts[-1]['f']['en'])}")
    lines.append("")
    fn = "prem" if kind == "nonvac" else "disch"
    want = "False{}" if kind == "counter" else "True{}"
    lines.append(f"def cz() -> {{D.{fn}_{x}({last}, {state}, w_t(), w_e(){targs}) == {want} : Bool}}:\n  {{==}}")
    lines.append("")
    if kind == "counter":
        lines.append("def true_ne_false(p: {True{} == False{} : Bool}) -> Empty:\n  (%p : M.is_true(_)\n  Unit{})")
        lines.append("")
        proof = "e => true_ne_false((%e : {_ == False{} : Bool}\n  cz()))"
        name = law_name(lid, True)
    elif kind == "exists":
        proof = "cz()"
        name = law_name(lid)
    else:
        proof = "cz()"
        name = f"nv_{lid.lower()}"
    tup = f"({state}, ({chain}, (w_t(), ({last}, (w_e(), {proof})))))"
    for nm, _h in reversed(tb):
        tup = f"(t_{nm}(), {tup})"
    lines.append(f"def Laws.{name}():\n  {tup}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------ the run
class Run:
    def __init__(self, milestone: str, root: Path, sidecar: str | None, disch: str | None, gen: Path | None,
                 out: Path | None, log=print):
        self.ctx = R3.Ctx(milestone, root, sidecar, gen, out, log=log)
        self.log = log
        self.sc, self.ans = C.load(milestone, root, disch)
        self.disch_arg = disch
        self.docs: dict = {}
        self.real = None
        self.s12: dict = {}             # law id -> its S1+S2 candidate (or None): S3's witnesses
        self.validations: dict = {}     # law id -> candidates checked against the deployment's answers

    def doc_of(self, e: dict) -> Doc:
        doc_rel = e["facts"]
        if doc_rel not in self.docs:
            an = next(a for a in self.ans.values() if a["_doc"] == doc_rel)
            self.docs[doc_rel] = Doc(self, doc_rel, an)
        return self.docs[doc_rel]

    def ids(self, laws: str | None) -> list[str]:
        ids = sorted(l for l, e in self.ctx.derivation.items() if e.get("rule") == "DISCH" and e.get("subform") in SUBFORMS)
        if laws:
            want = {x.strip() for x in laws.split(",") if x.strip()}
            ids = [l for l in ids if l in want]
        return ids

    def law_of(self, d: Doc, lid: str) -> dict:
        return next(l for l in d.an["laws"] if l["law_id"] == lid)

    def paths(self, lid: str) -> dict:
        g = self.ctx.gen
        return {"laws": g / "laws" / lid / "LAWS.bend", "proofs": g / "proofs" / lid, "nonvac": g / lid / "nonvac"}

    def binding(self) -> str | None:
        return self.sc.binding

    def get_real(self, d: Doc):
        if not self.binding():
            return None
        if self.real is None:
            self.real = R3.Real(self.ctx, d.doc_json)
        return self.real

    # ------------------------------------------------------------------ files
    def write_laws(self, d: Doc, lid: str, kind: str) -> Path:
        lp = self.paths(lid)["laws"]
        lp.parent.mkdir(parents=True, exist_ok=True)
        sh = self.ctx.registry["statements"][lid]
        name = law_name(lid, kind == "counter")
        lp.write_text(P.laws_text(lid, sh, rel_import(lp.parent, d.ip), rel_import(lp.parent, d.simp),
                                  [n for n, _h in d.tb], name, kind), encoding="utf-8")
        return lp

    def prove(self, d: Doc, law: dict, lp: Path) -> dict:
        lid = law["law_id"]
        pdir = self.paths(lid)["proofs"]
        shutil.rmtree(pdir, ignore_errors=True)
        att = {"kind": "proof", "generator": "holon.disch.proofs", "marker": None}
        try:
            text, routes = P.law_proof(d.g, law, rel_import(pdir, d.ip), rel_import(pdir, d.simp),
                                       rel_import(pdir, lp), law_name(lid))
        except (P.NoProof, Exception) as ex:  # noqa: BLE001: a route that does not apply is named, never fatal
            att["error"] = f"does not apply: {ex}"[:2000]
            return att
        pdir.mkdir(parents=True, exist_ok=True)
        p = pdir / "PROOF.bend"
        p.write_text(text, encoding="utf-8")
        checker, verdict = check_file(p)
        att.update({"routes": routes, "marker": checker["marker"], "verdict": verdict, "checker": checker,
                    "proof": rel(p, self.ctx.root)})
        if checker["marker"] != "ALL PROOFS CHECK" or verdict != "checked":
            att["error"] = _why(checker, verdict)
            shutil.rmtree(pdir, ignore_errors=True)
            att.pop("proof", None)
        return att

    def settle(self, d: Doc, law: dict, steps: list, t: int, fn: str):
        """The witness's hash tables (S3.settle's fixpoint over the trace, then the keys the claim looks up at the
        last step), the decoded prefix states, the actions and the claim's value there."""
        kh, sh, _codes = S3.settle(d.factory, steps, [])
        x = SEC.law_key(law["law_id"])
        val = None
        # an inhabitant (never replayed) keeps the hints' answers its evaluation looks up, which its literal states and
        # its actions compute with: one copy of the steps carries them through every round, the states and the acts
        # (the caller's steps, which the exploration may still hold, are never written)
        own = [S3.Step(st.action, st.args, json.loads(json.dumps(st.env))) for st in steps] if fn == "prem" else None
        for _ in range(8):
            m = d.factory(empty=True, native=False)
            m.kh, m.sh = dict(kh), dict(sh)
            m.kh_sent = m.sh_sent = -1
            g = m.s0()
            # copies: an evaluation answers a call the witness does not hold from the hints, and the witness keeps
            # exactly its own answers (the deployment's, with a binding), which the counter-law states
            cs = own if own is not None else [S3.Step(st.action, st.args, json.loads(json.dumps(st.env)))
                                              for st in steps]
            for st in cs[:-1]:
                _c, g, _calls = m.run_step(g, st, save=True)
            m._run_step(g, cs[-1], False)
            last = own[-1] if own is not None else steps[-1]
            val = d.judge.call(m, f"D_{fn}_{x}", lambda: [m.act(last), {"$ref": g}, W(t), m.act(last)["f"]["en"]])
            if (len(m.kh), len(m.sh)) == (len(kh), len(sh)):
                break
            kh, sh = dict(m.kh), dict(m.sh)
        src = own if own is not None else steps
        states = S3.trace_states(d.factory, src, kh, sh)
        m = d.factory(empty=True)
        acts = [m.act(st) for st in src]
        return {"keccak256": kh, "sha256": sh}, states, acts, val

    def emit(self, d: Doc, law: dict, steps: list, t: int, kind: str, where: Path, laws_path: Path, note: str):
        tables, states, acts, val = self.settle(d, law, steps, t, "prem" if kind == "nonvac" else "disch")
        where.mkdir(parents=True, exist_ok=True)
        p = where / "PROOF.bend"
        p.write_text(trace_proof(law["law_id"], d, rel_import(where, d.ip), rel_import(where, d.simp),
                                 rel_import(where, laws_path), acts, tables, states, t, kind, note), encoding="utf-8")
        checker, verdict = check_file(p)
        return p, checker, verdict, tables, val

    def witness_json(self, d: Doc, steps: list, t: int, tables: dict) -> dict:
        fns = R3.fn_names(d.doc)
        return {"steps": [R3.step_json(d.doc, st, fns) for st in steps], "t": int(t),
                "hashes": {h: [["0x" + k[2:], "0x%064x" % v] for k, v in sorted((tables.get(h) or {}).items())]
                           for h in d.hashes}}

    def repair(self, d: Doc, steps: list) -> list:
        """The witness's external-call answers as the deployment's dependencies give them (holon.sorts.run3)."""
        real = self.get_real(d)
        if real is None:
            return steps
        fns = R3.fn_names(d.doc)
        ws = [R3.step_json(d.doc, st, fns) for st in steps]
        res = real.run(ws)
        out = []
        for st, calls in zip(steps, res["calls"]):
            env = dict(st.env)
            env["calls"] = [{"to": c["to"], "data": c["data"], "ok": c["ok"], "ret": c["ret"]} for c in calls]
            env.pop("_unanswered", None)
            out.append(S3.Step(st.action, st.args, env))
        return out

    # ------------------------------------------------------------------ deciding
    def valid(self, d: Doc, law: dict, trace: list, st, t: int) -> bool:
        """A candidate's last step with the deployment's answers to its external calls (the real run's, as the witness
        will state them): every step still succeeds on the model and the step still decides the law. A candidate
        found with the hints' answers that the deployment answers otherwise is not taken."""
        self.validations[law["law_id"]] = self.validations.get(law["law_id"], 0) + 1
        steps = self.repair(d, list(trace) + [st])
        m = d.factory()
        g = m.s0()
        for s in steps[:-1]:
            code, g, _c = m.run_step(g, S3.Step(s.action, s.args, json.loads(json.dumps(s.env))), save=True)
            if code != 0:
                return False
        last = S3.Step(steps[-1].action, steps[-1].args, json.loads(json.dumps(steps[-1].env)))
        code, _g2, _c = m.run_step(g, last, save=False)
        if code != 0:
            return False
        ok = d.judge.decides(m, law, g, last, t)
        if not ok:
            self.log(f"  {law['law_id']}: a candidate ({st.action}) does not decide the law with the deployment's "
                     "external answers")
        return ok

    def search(self, d: Doc, law: dict, s3_states: list, s3: bool = True):
        ls = DS.LawSearch(d.ex, d.an, law, law_entries(d.an, law), d.judge, log=self.log)
        if self.binding():
            ls.validate = lambda trace, st, t: self.valid(d, law, trace, st, t)
        r = ls.refute(False, LAST_STEP_STATES)
        if r is None and s3 and s3_states:
            ls.extra = list(s3_states)
            ls.capped = False
            r = ls.refute(True, LAST_STEP_STATES)
        return r, ls

    def decide_all(self, ids: list[str]) -> dict:
        """{law_id: (record, replay entry or None)}."""
        out: dict = {}
        pending: dict = {}
        found: dict = {}
        for lid in ids:
            e = self.ctx.derivation[lid]
            d = self.doc_of(e)
            law = self.law_of(d, lid)
            t0 = time.time()
            attempts: list = []
            lp = self.write_laws(d, lid, "exists" if law["subform"] == "external" else "forall")
            if law["subform"] != "external":
                att = self.prove(d, law, lp)
                attempts.append(att)
                if att.get("marker") == "ALL PROOFS CHECK" and att.get("verdict") == "checked":
                    self.log(f"{lid}: PROVED ({', '.join(sorted(set(att['routes'].values())))}) in "
                             f"{round(time.time() - t0, 1)} s")
                    out[lid] = ("PROVED", {"attempts": attempts, "proof": att})
                    continue
            r, ls = self.search(d, law, [])
            self.log(f"{lid}: search {'found a candidate' if r else 'found nothing'} in {round(time.time() - t0, 1)} s")
            attempts.append({"kind": "search", "stage": "S1+S2", "found": r is not None, "bound": ls.bound()})
            if r is not None:
                found[lid] = r
                out[lid] = ("CANDIDATE", {"attempts": attempts, "steps": r[0], "t": r[1], "stage": "S1+S2",
                                          "bound": ls.bound()})
            else:
                pending[lid] = {"attempts": attempts, "bound": ls.bound()}
        # S3: the states along the S1+S2 witnesses of every other external and external_none law of the same document
        # (law id order), searched for here when this run did not decide them, so that a law's outcome does not depend
        # on which laws a run names
        for lid in sorted(pending):
            e = self.ctx.derivation[lid]
            d = self.doc_of(e)
            law = self.law_of(d, lid)
            wits = []
            for other in sorted(d.an["laws"], key=lambda x: x["law_id"]):
                k = other["law_id"]
                if k == lid or other["subform"] not in ("external", "external_none"):
                    continue
                if k not in self.s12:
                    if k in found:
                        self.s12[k] = found[k]
                    else:
                        r0, _ls0 = self.search(d, other, [], s3=False)
                        self.s12[k] = r0
                if self.s12[k] is not None:
                    wits.append(self.s12[k])
            states = self.witness_states(d, wits)
            if not states:
                out[lid] = ("UNKNOWN", pending[lid])
                continue
            t0 = time.time()
            r, ls = self.search(d, law, states)
            self.log(f"{lid}: S3 {'found a candidate' if r else 'found nothing'} in {round(time.time() - t0, 1)} s")
            att = pending[lid]["attempts"] + [{"kind": "search", "stage": "S3", "found": r is not None,
                                               "bound": ls.bound()}]
            if r is not None:
                out[lid] = ("CANDIDATE", {"attempts": att, "steps": r[0], "t": r[1], "stage": "S3",
                                          "bound": ls.bound()})
            else:
                out[lid] = ("UNKNOWN", {"attempts": att, "bound": ls.bound()})
        return out

    def witness_states(self, d: Doc, wits: list) -> list:
        """(trace, g) of every prefix of the given witnesses, and their full traces, rebuilt on the shared
        exploration's model (distinct by fingerprint and clock, in order)."""
        m = d.ex.m
        seen = set()
        out = []
        for steps, _t in wits:
            g = m.s0()
            for k, st in enumerate(steps):
                code, g2, _c = m.run_step(g, st, save=True)
                if code != 0:
                    break
                g = g2
                key = (m.fingerprint(g), int(st.env.get("block.timestamp") or 0))
                if key in seen:
                    continue
                seen.add(key)
                out.append((list(steps[:k + 1]), g))
        return out

    def finish(self, lid: str, outcome: tuple) -> tuple[dict, dict | None]:
        """Checks a candidate (counter-law or witness proof, both kernels, the replay), searches the inhabitant of a
        PROVED forall law and writes the record."""
        kind, info = outcome
        e = self.ctx.derivation[lid]
        d = self.doc_of(e)
        law = self.law_of(d, lid)
        sf = law["subform"]
        paths = self.paths(lid)
        lp = paths["laws"]
        status, prim, witness, rep, nonvac = "UNKNOWN", None, None, None, None
        attempts = list(info["attempts"])
        bound = info.get("bound")
        if kind == "PROVED":
            status = "PROVED"
            prim = {"proof": info["proof"]["proof"], "checker": info["proof"]["checker"], "verdict": "checked"}
            nonvac = self.inhabit(d, law)
        elif kind == "CANDIDATE":
            steps, t = self.repair(d, info["steps"]), info["t"]
            ck = "exists" if sf == "external" else "counter"
            lp = self.write_laws(d, lid, ck)
            pdir = paths["proofs"]
            shutil.rmtree(pdir, ignore_errors=True)
            p, checker, verdict, tables, val = self.emit(
                d, law, steps, t, ck, pdir, lp, f"the witness ({info['stage']}): every premise by computation")
            witness = self.witness_json(d, steps, t, tables)
            ok = checker["marker"] == "ALL PROOFS CHECK" and verdict == "checked"
            attempts.append({"kind": "witness", "stage": info["stage"], "marker": checker["marker"],
                             "verdict": verdict, "claim_at_witness": val, "checker": checker})
            if ok and self.binding():
                rep = self.replay_one(d, law, witness)
                attempts[-1]["replay"] = rep["status"]
                ok = rep["status"] == "passed"
            if not ok:
                # the candidate and what the checkers and the replay said of it, kept for the record (never evidence)
                attempts[-1]["candidate"] = witness
                if rep is not None:
                    attempts[-1]["replay_entry"] = {k: v for k, v in rep.items() if k != "trace"}
            if ok:
                status = "REFUTED" if sf != "external" else "PROVED"
                prim = {"proof": rel(p, self.ctx.root), "checker": checker, "verdict": verdict}
                if sf == "external":
                    nonvac = {"status": "inhabited", "law": rel(lp, self.ctx.root), "witness": witness,
                              "reachable": True, "degenerate": None,
                              "parent_statement_hash": self.ctx.registry["statements"][lid],
                              "bound": "the checked witness inhabits the premises"}
            else:
                # the candidate is not kept: the law stays UNKNOWN, its statement file the forall (or existential) law
                shutil.rmtree(pdir, ignore_errors=True)
                lp = self.write_laws(d, lid, "exists" if sf == "external" else "forall")
                why = (f"a candidate witness did not check ({checker['marker']}, BendTT {verdict}; bend2 fails at {checker.get('failing')}; {_why(checker, verdict)})"
                       if checker["marker"] != "ALL PROOFS CHECK" or verdict != "checked" else
                       "a candidate witness checked but did not replay on the real contract")
                bound = f"{info['bound']}; {why}"
                witness = None
                rep = None
        rec = self.record(d, law, e, status, prim, witness, bound if status == "UNKNOWN" else None, nonvac, attempts,
                          lp, rep)
        return rec, rep

    def inhabit(self, d: Doc, law: dict) -> dict:
        lid = law["law_id"]
        sh = self.ctx.registry["statements"][lid]
        base = {"status": "unknown", "law": None, "witness": None, "reachable": None, "degenerate": None,
                "parent_statement_hash": sh, "bound": None}
        nd = self.paths(lid)["nonvac"]
        shutil.rmtree(nd, ignore_errors=True)
        ls = DS.LawSearch(d.ex, d.an, law, law_entries(d.an, law), d.judge, log=self.log)
        r = ls.inhabit(LAST_STEP_STATES)
        if r is None:
            return {**base, "bound": f"no reachable state where the premises hold: {ls.bound()}"}
        steps, t = r
        nd.mkdir(parents=True, exist_ok=True)
        lpn = nd / "LAWS.bend"
        lpn.write_text(nonvac_law_text(lid, sh, rel_import(nd, d.ip), rel_import(nd, d.simp), [n for n, _h in d.tb]),
                       encoding="utf-8")
        p, checker, verdict, tables, _val = self.emit(d, law, steps, t, "nonvac", nd, lpn,
                                                      "the inhabitant: every premise by computation")
        w = self.witness_json(d, steps, t, tables)
        if checker["marker"] != "ALL PROOFS CHECK" or verdict != "checked":
            shutil.rmtree(nd, ignore_errors=True)
            return {**base, "witness": w, "bound": f"the inhabitant does not check ({checker['marker']}, {verdict}; bend2 fails at {checker.get('failing')}; {_why(checker, verdict)})"}
        return {**base, "status": "inhabited", "law": rel(lpn, self.ctx.root), "witness": w, "reachable": True,
                "degenerate": False,
                "bound": f"a reachable state of {len(steps) - 1} steps where B holds at t, and {steps[-1].action}"}

    # ------------------------------------------------------------------ records
    def record(self, d: Doc, law: dict, e: dict, status: str, prim, witness, bound, nonvac, attempts, lp: Path,
               rep) -> dict:
        from .. import records as R
        ctx = self.ctx
        lid = law["law_id"]
        law_ir = json.loads((ctx.laws_dir / f"{lid}.json").read_text())
        sh = ctx.registry["statements"][lid]
        mp = d.mp
        cone = R.cone(lp.read_text(encoding="utf-8"), mp.read_text(encoding="utf-8"))
        if rep is not None:
            replay = {"status": rep["status"], "detail": " / ".join(rep["real"])}
        elif witness is not None:
            replay = {"status": "not_applicable", "detail": "no binding: the milestone has no real side"}
        else:
            replay = {"status": "not_applicable", "detail": f"{status}: no witness to replay"}
        rec = {"law_id": lid, "statement_hash": sh, "facts_sha256": law_ir["facts_sha256"], "status": status,
               "scope": "unbounded", "premises": [],
               "kernel": {"name": "bend", "version": R3.bend_version(), "verdict": (prim or {}).get("verdict", "not_run")},
               "artifacts": {"laws": rel(lp, ctx.root), "proof": (prim or {}).get("proof"), "model": rel(mp, ctx.root),
                             "disch": rel(d.spath, ctx.root),
                             "law_name": law_name(lid, status == "REFUTED")},
               "checker": (prim or {}).get("checker") or {"exit_code": None, "marker": "not_run"},
               "triage": "finding" if status == "REFUTED" else "none", "replay": replay, "attempts": attempts,
               "rule": "DISCH", "subform": e["subform"],
               "disch": {k: v for k, v in e.items() if k != "statement_hash"}, "bound": bound}
        if witness is not None:
            rec["witness"] = witness
        if status == "REFUTED":
            rec["difference"] = {"lhs": False, "rhs": True}
        try:
            b, match = R.resolve_bundle(rec["facts_sha256"], law_ir["facts"], ctx.root, mp.read_text(encoding="utf-8"),
                                        set(cone), ctx.m)
            assumptions = R.model_assumptions(b["facts_sha256"], set(cone), ctx.root, law_ir["facts"])
        except R.LedgerError:
            match, assumptions = "none", []
        rec.update({"record_version": R.RECORD_VERSION, "prover": "generator", "model_sha256": R3.sha256_file(mp),
                    "compiled_sha256": R3.sha256_file(d.ev.compiled()), "generator_sha256": generator_sha256(ctx.root),
                    "cone": cone, "ledger_match": match, "model_assumptions": assumptions,
                    "scope_v2": R.scope_v2(law_ir, rec), "kernels": R.kernels(rec),
                    "independence_class": R.independence_class(rec), "refinement_refs": [],
                    "coverage": R.coverage_field(law_ir, ctx.root) if ctx.m.startswith("M") else None,
                    "non_vacuity": nonvac or {"status": "counter_witness" if status == "REFUTED" else "unknown",
                                              "law": rel(lp, ctx.root) if status == "REFUTED" else None,
                                              "witness": None, "reachable": None, "degenerate": None,
                                              "parent_statement_hash": sh,
                                              "bound": "the accepted counter-law inhabits the premises"
                                              if status == "REFUTED" else "no proof"},
                    "witness_provenance": {"solidity": "internal_harness"} if status == "REFUTED" else None,
                    "filter_bin": "finding" if status == "REFUTED" else None,
                    **R.evidence_fields(law_ir, {"status": status}, ctx.root)})
        rec["statement"] = law_ir.get("notes", "")
        return rec

    # ------------------------------------------------------------------ replay
    def replay_one(self, d: Doc, law: dict, witness: dict) -> dict:
        """One witness on the model and on the real contract (the binding's step harness), with B and c evaluated on
        the real storage (holon.extracted_eval over the words the harness dumps after each step)."""
        from .. import extracted_eval as EV
        from ..replay_fragments import run_harness
        real = self.get_real(d)
        real.setup()
        steps_json = witness["steps"]
        steps = [R3.step_of_json(s) for s in steps_json]
        t = int(witness["t"])
        b = next(x for x in d.an["basis"] if x["tag"] == law["tag"])
        scope = b["check"].split("#")[0]
        m = d.model_f()
        model_out, _check = R3.model_outcomes(m, steps)
        # the slots B and c read (on the model's states before and after the last step): the slots to dump
        mm = d.model_f()
        g = mm.s0()
        states = [mm.state(g)]
        for st in steps:
            _c, g, _calls = mm.run_step(g, st, save=True)
            states.append(mm.state(g))
        now = int(steps[-1].env.get("block.timestamp") or 0)

        def reads(state, term, ts):
            class Rec(dict):
                seen: set = set()

                def get(self, k, default=None):
                    self.seen.add(k)
                    return super().get(k, default)
            r = Rec(state)
            r.seen = set()
            try:
                e = EV.Eval(d.doc, {}, scope, {}, {"block.timestamp": ts})
                e.state = r
                e.truth(term)
            except Exception:  # noqa: BLE001
                pass
            return r.seen
        slots = sorted(reads(states[-2], b["blocked"], t) | reads(states[-1], b["blocked"], now)
                       | reads(states[-1], b["check_expr"], now))
        runs = run_harness(real.proj, real.tc, real.binding, [real.steps(steps_json)], slots, real.init, tag="disch")
        tr = runs[0]
        execs = [x for x in tr.execs if x.id != "d"]
        dep = next((x for x in tr.execs if x.id == "d"), None)
        outcomes, calls, dumps_ = [], [], []
        for x in execs:
            outcomes.append("ok" if x.ok else "rev " + R3.revert_text(bytes.fromhex(x.ret[2:])))
            calls.append([{"to": c[0], "data": c[1], "ok": c[2], "ret": c[3]} for c in x.calls])
            dumps_.append(dict(zip(slots, x.dump or [])))
        calls_agree = all([{k: c[k] for k in ("to", "data", "ok", "ret")} for c in calls[i]] ==
                          [{"to": c["to"].lower(), "data": c["data"].lower(), "ok": bool(c["ok"]), "ret": c["ret"].lower()}
                           for c in s["env"].get("calls") or []] for i, s in enumerate(steps_json))

        def truth(words, term, ts):
            try:
                return EV.Eval(d.doc, words, scope, {}, {"block.timestamp": ts}).truth(term)
            except Exception:  # noqa: BLE001
                return None
        before = dumps_[-2] if len(dumps_) > 1 else (dict(zip(slots, dep.dump or [])) if dep is not None else {})
        blocked_before = truth(before, b["blocked"], t) is True
        if law["subform"] == "blocking":
            discharged = truth(dumps_[-1], b["blocked"], now) is False
        else:
            discharged = truth(dumps_[-1], b["check_expr"], now) is True
        ok = (model_out == outcomes and all(o == "ok" for o in outcomes) and calls_agree and blocked_before
              and discharged)
        return {"trace": steps_json, "t": t, "model": model_out, "real": outcomes, "calls_agree": calls_agree,
                "blocked_before": blocked_before, "discharged_after": discharged,
                "status": "passed" if ok else "failed"}

    def report(self, entries: dict) -> dict:
        from ..replay_fragments import load_binding
        bp = self.binding()
        bind = load_binding(self.ctx.root / bp)
        return {"document": "disch_replay", "binding": {"path": bp, "sha256": R3.sha256_file(self.ctx.root / bp)},
                "harness": [{"path": h, "sha256": R3.sha256_file(self.ctx.root / h)}
                            for h in sorted(bind["harness"]["files"])],
                "laws": {k: entries[k] for k in sorted(entries)}}

    def close(self):
        for d in self.docs.values():
            d.close()
        if self.real is not None:
            self.real.close()
        self.ctx.close()


# ------------------------------------------------------------------------------------------------ the CLI
def run_disch(a) -> int:
    root = Path(getattr(a, "root", None) or ROOT).resolve()
    gen = Path(a.gen_dir).resolve() if a.gen_dir else None
    out = Path(a.out).resolve() if a.out else None
    r = Run(a.milestone, root, a.sidecar, a.disch, gen, out)
    try:
        ids = r.ids(a.laws)
        if not ids:
            return 0
        r.ctx.out.mkdir(parents=True, exist_ok=True)
        outcomes = r.decide_all(ids)
        entries = {}
        for lid in ids:
            rec, rep = r.finish(lid, outcomes[lid])
            r.log(f"{lid}: {rec['status']}")
            (r.ctx.out / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
            if rep is not None:
                entries[lid] = rep
        if r.binding() and r.ctx.out.resolve() == (root / "results" / r.ctx.m).resolve():
            write_report(r, entries, partial=bool(a.laws))
        return 0
    finally:
        r.close()


def write_report(r: Run, entries: dict, partial: bool) -> Path:
    """replay/<M>/disch/report.json: the given entries (a partial run keeps the other laws' entries)."""
    rp = r.ctx.root / "replay" / r.ctx.m / "disch" / "report.json"
    old = {}
    if partial and rp.is_file():
        old = json.loads(rp.read_text()).get("laws") or {}
    keep = {k: v for k, v in old.items() if k not in entries and (r.ctx.out / f"{k}.json").is_file()}
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(dumps(r.report({**keep, **entries})), encoding="utf-8")
    return rp


def replay_disch(a) -> int:
    """holon replay --milestone M: every REFUTED DISCH record's and every PROVED external law's witness, again, into
    replay/<M>/disch/report.json."""
    root = Path(getattr(a, "root", None) or ROOT).resolve()
    r = Run(a.milestone, root, a.sidecar, getattr(a, "disch", None), None, None)
    try:
        if not r.binding():
            return 0
        entries = {}
        for lid in r.ids(None):
            p = r.ctx.out / f"{lid}.json"
            if not p.is_file():
                continue
            rec = json.loads(p.read_text())
            if not rec.get("witness") or rec.get("status") not in ("REFUTED", "PROVED"):
                continue
            e = r.ctx.derivation[lid]
            d = r.doc_of(e)
            entries[lid] = r.replay_one(d, r.law_of(d, lid), rec["witness"])
        rp = write_report(r, entries, partial=False)
        bad = sorted(k for k, v in entries.items() if v["status"] != "passed")
        print(f"holon replay (DISCH): {len(entries)} witnesses, {len(bad)} failed -> {rel(rp, root)}")
        return 0 if not bad else 1
    finally:
        r.close()



def disch_ids_of(argv: list, root: Path = ROOT) -> tuple[list[str], list[str]] | None:
    """(the DISCH ids, the other ids) a `holon run --laws ..` names; None without --laws."""
    m = laws = None
    for i, x in enumerate(argv):
        if x == "--milestone" and i + 1 < len(argv):
            m = argv[i + 1]
        elif x.startswith("--milestone="):
            m = x.split("=", 1)[1]
        elif x == "--laws" and i + 1 < len(argv):
            laws = argv[i + 1]
        elif x.startswith("--laws="):
            laws = x.split("=", 1)[1]
    if laws is None or m is None:
        return None
    try:
        dv = json.loads((Path(root) / "laws" / m / "DERIVATION.json").read_text())
    except (OSError, ValueError):
        dv = {}
    rules = {e.get("law_id"): e.get("rule") for e in dv.get("laws") or [] if isinstance(e, dict)}
    ids = [x.strip() for x in laws.split(",") if x.strip()]
    return [x for x in ids if rules.get(x) == "DISCH"], [x for x in ids if rules.get(x) != "DISCH"]


def strip_args(rest: list, names: tuple) -> list:
    out, skip = [], False
    for x in rest:
        if skip:
            skip = False
            continue
        if x in names:
            skip = True
            continue
        if any(x.startswith(n + "=") for n in names):
            continue
        out.append(x)
    return out


def main(argv: list) -> int:
    """holon run | replay of a typed milestone with DISCH laws (holon/__main__.py sends --laws naming only DISCH laws,
    or a run or replay of the whole milestone, here): I30's and I27's laws first (holon.undo.run, as before), then the
    DISCH laws."""
    cmd, rest = argv[0], argv[1:]
    ap = argparse.ArgumentParser(prog=f"holon {cmd}", add_help=False)
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--sidecar")
    ap.add_argument("--disch")
    ap.add_argument("--laws")
    ap.add_argument("--out")
    ap.add_argument("--gen-dir")
    a, _unknown = ap.parse_known_args(rest)
    base = strip_args(rest, ("--disch",))
    from ..undo import run as undo_run   # I30's laws (holon.sorts.run3) and I27's UNDO laws, as before the DISCH laws
    if cmd == "run":
        rc = 0
        if not a.laws:
            dv = json.loads((ROOT / "laws" / a.milestone / "DERIVATION.json").read_text())
            if any(isinstance(e, dict) and e.get("rule") in ("SORT", "UNDO") for e in dv.get("laws") or []):
                rc = undo_run.main([cmd] + base)
        return max(rc, run_disch(a))
    rc = undo_run.main([cmd] + base)
    return max(rc, replay_disch(a))
