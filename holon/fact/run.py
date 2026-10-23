"""The FACT laws of a typed milestone, decided on the typed model (BUILD_PLAN I26; the contract is the docstring of
tests_m3/test_fact.py, "Deciding", "Replay", "Records" and "Classification").

  python -m holon run --milestone M [--sidecar PATH] [--fact-sidecar PATH] [--laws ID,ID] [--out DIR] [--gen-dir DIR]
  python -m holon replay --milestone M [--sidecar PATH] [--fact-sidecar PATH]

`run` decides every FACT law of laws/<M> (or those --laws names):
  1. the FACT section gen/<M>/fact/models/<model>.fact.bend over the typed model (holon.fact.section), and the law's
     statement gen/<M>/laws/<id>/LAWS.bend (holon.fact.proofs);
  2. refutation (holon.fact.search, the FACT sidecar's budget) on the combined module the evaluator runs; with the
     sidecar's binding, a witness counts only when its steps succeed on the deployment and, its external calls answered
     as the deployment answers them, the model still finds the law's function false at it; its counter-law
     gen/<M>/proofs/<id>/witness/PROOF.bend is accepted only when bend2 and BendTT check it;
  3. without an accepted counter-law, the product program's routes (holon.gen.mproofs.product: guard, injective for a
     kernel law; provenance for an attribution law), each a PROOF.bend checked by bend2 and BendTT, within the term
     budget (spec/M3/lib/term_size.json measure (1)), the law's inhabitant file counted with it; otherwise UNKNOWN
     with what was tried. A PROVED law's record carries the search for a checked reachable inhabitant of fhit_<x>
     (gen/<M>/<id>/nonvac/): without one it stays PROVED with non_vacuity unknown, as I30's records do, and G11V
     fails it;
  4. every REFUTED law's runs replayed on the real contract (the binding's step harness): replay/<M>/fact/report.json;
  5. the record results/<M>/<id>.json (v1 and v2, with the fact field), and results/<M>/fact/classification.json.
`replay` re-runs step 4 for the committed records.

Nothing here names a target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

from ..gen.mlaws import law_name
from ..machine_bend import bname
from ..rules import fact as RF
from ..sorts import evaluate3 as E3
from ..sorts import proofs3 as P3
from ..sorts import run3
from ..sorts import search3 as S3
from ..sorts import termsize as TS
from ..sorts.model3 import importable, model_name, write_model_file
from ..undo import search as US
from . import product as FPR
from . import proofs as FP
from . import search as FS
from . import section as S

ROOT = Path(__file__).resolve().parents[2]


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fact_laws(derivation: dict) -> list[str]:
    return sorted(lid for lid, e in derivation.items() if e.get("rule") == RF.RULE)


# ------------------------------------------------------------------------------------------------ the context
class FactCtx:
    """One document's FACT section: the module Bend checks, and the combined module the evaluator runs."""

    def __init__(self, ctx: "Ctx", doc_rel: str):
        rc = ctx.rc
        self.doc_rel = doc_rel
        self.root = rc.root
        self.ev, self.init, _mf, self.mm, self.docm = rc.model(doc_rel)
        self.model_file = rc.model_path(doc_rel)
        self.text = self.model_file.read_text(encoding="utf-8")
        self.doc = json.loads((rc.root / doc_rel).read_text(encoding="utf-8"))
        self.hashes = self.ev.hashes()
        self.an = RF.analyse(self.doc, RF.model_of(doc_rel), ctx.fsc.doc)
        self.elements = RF.elements(self.an)
        got = {e["law_id"]: e for e in self.elements}
        for lid in fact_laws(rc.derivation):
            de = rc.derivation[lid]
            if de["facts"] != doc_rel:
                continue
            if lid not in got or got[lid]["basis"] != de["basis"] or got[lid]["premises"] != de["premises"]:
                raise RuntimeError(f"{lid}: the document's analysis no longer gives the derived basis (derive again)")
        hyps = ctx.fsc.doc.get("hypotheses") or {}
        self.dir = ctx.gen / "fact" / "models"
        name = model_name(doc_rel) + ".fact"
        self.import_file = self.dir / importable(name)
        mt = S.module_text(self.mm, self.text, self.doc, self.hashes, self.elements, hyps,
                           os.path.relpath(rc.import_path(doc_rel), self.dir).replace(os.sep, "/"))
        self.path = write_model_file(self.dir, name, mt)          # <model>.fact.bend, a link to the importable file
        self.module_text = mt
        ct = S.combined_text(self.mm, self.text, self.doc, self.hashes, self.elements, hyps)
        cd = E3.cache_dir().parent / "fact3" / hashlib.sha256(ct.encode()).hexdigest()[:32]
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
        self.mine = set(E3.records(mt))

    def element(self, lid: str) -> dict:
        return next(e for e in self.elements if e["law_id"] == lid)

    def factory(self, empty: bool = False, native: bool = True) -> S3.Model:
        i = dict(self.init)
        if empty:
            i["preimages"] = []
        return S3.Model(self.cev, i, self.hints, self.root / self.doc_rel, native=native)

    def close(self):
        self.cev.close()


class Ctx:
    def __init__(self, milestone: str, root: Path, sidecar: str | None, fact_sidecar: str | None, gen: Path | None,
                 out: Path | None, log=print):
        self.rc = run3.Ctx(milestone, root, sidecar, gen, out, log)
        self.m = milestone
        self.root = Path(root)
        self.gen = self.rc.gen
        self.out = self.rc.out
        self.log = log
        self.fsc = RF.load_sidecar(milestone, self.root, fact_sidecar)
        self.deadline: float | None = None
        self.facts: dict = {}

    def fact(self, doc_rel: str) -> FactCtx:
        if doc_rel not in self.facts:
            self.facts[doc_rel] = FactCtx(self, doc_rel)
        return self.facts[doc_rel]

    def sorts_of(self, doc_rel: str) -> dict:
        a = json.loads((self.root / "gen" / self.m / "sorts" / "assignment.json").read_text())
        return a["models"][model_name(doc_rel)]["assignment"]

    def close(self):
        for t in self.facts.values():
            t.close()
        self.rc.close()


GEN_FACT = ["holon/fact/run.py", "holon/fact/search.py", "holon/fact/section.py", "holon/fact/proofs.py",
            "holon/fact/product.py", "holon/rules/fact.py", "holon/measures_fact.py"]


def generator_sha256(root: Path) -> str:
    from ..records import _holon_imports
    seen, todo = set(), list(GEN_FACT) + list(run3.GEN3)
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


def hexw(v: int) -> str:
    return "0x%064x" % (int(v) & ((1 << 256) - 1))


def addr(v: int) -> str:
    return "0x%040x" % (int(v) & ((1 << 160) - 1))


def word_of(out) -> int:
    """An evaluator word (a 0x-string, or {"$w"})."""
    if isinstance(out, dict) and "$w" in out:
        out = out["$w"]
    return int(str(out), 16)


# ------------------------------------------------------------------------------------------------ the real side
def real_runs(real: run3.Real, traces: list, slots: list) -> list:
    """Each trace (step JSON) on the real contract from the binding's deployment: per trace, per step, (its
    observation, the raw calls it made (to, data, ok, ret), the words at the given slots after it)."""
    from ..replay_fragments import run_harness
    from ..undo.run import obs_of_exec
    real.setup()
    runs = run_harness(real.proj, real.tc, real.binding, [real.steps(ws) for ws in traces], list(slots), real.init,
                       tag="fact")
    out = []
    for tr in runs:
        execs = [e for e in tr.execs if e.id != "d"]
        out.append([(obs_of_exec(e),
                     [{"to": US.norm_to(c[0]), "data": str(c[1]).lower(), "ok": bool(c[2]), "ret": str(c[3]).lower()}
                      for c in e.calls],
                     list(e.dump or [])) for e in execs])
    return out


def with_calls(st: S3.Step, calls: list) -> S3.Step:
    env = json.loads(json.dumps(st.env))
    env.pop("_unanswered", None)
    env["calls"] = [dict(c) for c in calls]
    return S3.Step(st.action, json.loads(json.dumps(st.args)), env)


def calls_agree(steps_json: list, raws: list) -> bool:
    """Every external call each real step made is the witness's env call, in order (the calls the step's evaluation
    looked up; a call the witness answers that the real step did not make is not one)."""
    for s, calls in zip(steps_json, raws):
        env = [{"to": US.norm_to(c["to"]), "data": c["data"].lower(), "ok": bool(c["ok"]), "ret": c["ret"].lower()}
               for c in (s.get("env") or {}).get("calls") or []]
        made = {(c["to"], c["data"]) for c in calls}
        mine = [c for c in env if (c["to"], c["data"]) in made]
        if mine != calls:
            return False
    return True


# ------------------------------------------------------------------------------------------------ deciding a law
def run_states(model_f, prefix: list) -> list:
    """run_fact's decoded value (the state and the companions) after each step of an attribution witness's trace, from
    Reach's initial state; the by-parts proof writes them as literals (holon.fact.proofs.Shape)."""
    m = model_f(empty=True, native=False)
    o = US.Obs(m)
    r0 = {"$r": "FxR", "f": {"s": {"$call": "gh_s0", "args": []}, "g": {"$call": "fx_g0", "args": []}}}
    return [o.value("run_fact", [[m.act(st) for st in prefix[:k]], r0]) for k in range(1, len(prefix) + 1)]


def settle_closed(model_f, fn: str, args_of) -> tuple[dict, dict, object]:
    """The hash tables of a closed evaluation (an attribution law's function at its trace and step): the real hash
    of exactly the keys fn looks up, from empty tables, on a fresh model whose tables are passed as Bend lists."""
    for _ in range(8):
        m = model_f(empty=True, native=False)
        n0, r = None, None
        for _round in range(6):
            r = US.Obs(m).settle({"fn": fn, "args": lambda: list(args_of(m))}, None)
            n = (len(m.kh), len(m.sh))
            if n == n0:
                break
            n0 = n
        return dict(m.kh), dict(m.sh), r["out"]
    raise RuntimeError("the witness's hash tables did not settle")


class Decider:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        side = json.loads((ctx.root / str(ctx.fsc.doc.get("term_size") or "spec/M3/lib/term_size.json")).read_text())
        self.measure = TS.Measure(side)
        self.budget = int(side["budget"])

    def paths(self, lid: str) -> dict:
        g = self.ctx.gen
        return {"laws": g / "laws" / lid / "LAWS.bend", "proofs": g / "proofs" / lid, "nonvac": g / lid / "nonvac"}

    def imports(self, d: Path, tc: FactCtx) -> tuple[str, str]:
        return (P3.rel_import(d, self.ctx.rc.import_path(tc.doc_rel)), P3.rel_import(d, tc.import_file))

    def write_law(self, law: dict, tc: FactCtx, counter: bool) -> Path:
        p = self.paths(law["law_id"])["laws"]
        p.parent.mkdir(parents=True, exist_ok=True)
        sh = self.ctx.rc.registry["statements"][law["law_id"]]
        mi, si = self.imports(p.parent, tc)
        p.write_text(FP.law_file(law, sh, mi, si, tc.hashes, counter=counter), encoding="utf-8")
        return p

    def steps_json(self, tc: FactCtx, steps: list) -> list:
        fns = run3.fn_names(tc.docm)
        return [run3.step_json(tc.docm, st, fns) for st in steps]

    def consumer_sel(self, tc: FactCtx, el: dict) -> str | None:
        if el["subform"] != "attribution":
            return None
        fn = el["basis"]["consumer"]["fn"]
        try:
            return str(tc.mm.m.call_signature(fn)["selector"]).lower()
        except Exception:  # noqa: BLE001: a consumer whose selector the model does not know makes no call here
            return None

    # ---------------------------------------------------------- the witness on the model and on the real side
    def traces(self, el: dict, w: dict) -> list:
        """The witness's runs (lists of steps): a kernel witness's two, an attribution witness's one."""
        if el["subform"] == "kernel":
            return [list(r["prefix"]) + [r["x"]] for r in w["runs"]]
        return [list(w["prefix"]) + [w["y"]] + list(w.get("t") or [])]

    def model_value(self, el: dict, tc: FactCtx, w: dict):
        """fact_<x> at the witness on the model (the steps' own call answers), or None when a prefix step fails."""
        m = tc.factory()
        o = US.Obs(m)
        x = RF.ghost_x(el["law_id"])
        if el["subform"] == "kernel":
            gs = []
            for r in w["runs"]:
                g = m.s0()
                for st in r["prefix"]:
                    code, g, _c = m.run_step(g, US.fresh_step(st), save=True)
                    if code != 0:
                        return None
                gs.append(g)
            (x1, x2) = (w["runs"][0]["x"], w["runs"][1]["x"])
            r = o.settle({"fn": f"fact_{x}", "args": lambda: [{"$ref": gs[0]}, m.act(x1), {"$ref": gs[1]},
                                                                m.act(x2)]}, None)
            return bool(r["out"])
        r = o.settle({"fn": f"fact_{x}", "args": lambda: [[m.act(s) for s in w["prefix"]], m.act(w["y"])]}, None)
        return bool(r["out"])

    def repair(self, real, tc: FactCtx, el: dict, w: dict) -> tuple[dict, list]:
        """The witness's steps with every external call answered as the deployment answers it (each run on the real
        contract; a shared prefix takes the first run's answers)."""
        trs = self.traces(el, w)
        res = real_runs(real, [self.steps_json(tc, t) for t in trs], [])
        raws = [[c for _o, c, _d in run] for run in res]
        out = json.loads(json.dumps({k: v for k, v in w.items() if k not in ("runs", "prefix", "y", "t")}))
        if el["subform"] == "kernel":
            out["runs"] = []
            for j, r in enumerate(w["runs"]):
                n = len(r["prefix"])
                out["runs"].append({"prefix": [with_calls(st, raws[j][i]) for i, st in enumerate(r["prefix"])],
                                    "x": with_calls(r["x"], raws[j][n])})
        else:
            n = len(w["prefix"])
            out["prefix"] = [with_calls(st, raws[0][i]) for i, st in enumerate(w["prefix"])]
            out["y"] = with_calls(w["y"], raws[0][n])
            out["t"] = [with_calls(st, raws[0][n + 1 + i]) for i, st in enumerate(w.get("t") or [])]
        return out, res

    def search(self, el: dict, tc: FactCtx, real) -> tuple[dict | None, str]:
        """The model's search; with a real side, a witness counts only when every step of its runs succeeds on the
        deployment and, its external calls answered as the deployment answers them, the model still finds fact_<x>
        false at it (and an attribution witness's continuation still ends in the consumer's call with the bonded
        principal); the accepted witness comes back repaired."""
        accept, kept = None, {}
        sel = self.consumer_sel(tc, el)
        if real is not None:
            def accept(w):
                try:
                    w2, res = self.repair(real, tc, el, w)
                except Exception as e:  # noqa: BLE001: a witness the real side cannot run is no witness
                    return f"the real side cannot run it: {type(e).__name__}: {str(e)[:200]}"
                for j, run in enumerate(res):
                    bad = [i for i, (o, _c, _d) in enumerate(run) if o["status"] != "ok"]
                    if bad:
                        return f"run {j + 1}: step {bad[0]} reverts on the deployment"
                if self.model_value(el, tc, w2) is not False:
                    return "with the deployment's call answers the model finds fact true"
                if el["subform"] == "attribution" and w2.get("t"):
                    last = res[0][-1][1]
                    if not any(c["data"].startswith(sel or "-") and len(c["data"]) >= 74
                               and int(c["data"][10:74], 16) == int(w2["bonded"]) for c in last):
                        return "the continuation's last step does not call the consumer with the bonded principal"
                kept["w"] = w2
                return None
        s = FS.FactSearch(tc.factory, tc.doc, self.ctx.sorts_of(tc.doc_rel), self.ctx.fsc.search, el,
                          log=self.ctx.log, accept=accept, deadline=self.ctx.deadline, consumer_sel=sel)
        if el["subform"] == "kernel":
            w, bound = s.kernel(el)
        else:
            x = RF.ghost_x(el["law_id"])
            w, bound = s.attribution(el, lambda g, k: s.o.word(f"fx_bond_{x}", [s.st_of(g), {"$w": hexw(k)}]),
                                     lambda g, y: self.key_at(s, el, g, y))
        return (kept.get("w", w) if w is not None else None), bound

    def key_at(self, s, el: dict, g: str, y: S3.Step) -> int:
        """The key the step y pins at, in its pre-context at g."""
        x = RF.ghost_x(el["law_id"])
        a = bname(y.action)
        act = s.m.act(y)
        x0 = {"$call": f"x0_{a}", "args": [s.st_of(g), act["f"]["ar"], act["f"]["en"]] + s.m.tables()}
        return s.o.word(f"fx_key_{x}", [x0])

    # ---------------------------------------------------------- the counter-law
    def emit_counter(self, el: dict, law: dict, tc: FactCtx, w: dict) -> tuple[Path, dict, str, dict, object]:
        x = RF.ghost_x(law["law_id"])
        if el["subform"] == "kernel":
            r1, r2 = w["runs"]
            if [st.key() for st in r1["prefix"]] != [st.key() for st in r2["prefix"]]:
                raise RuntimeError("a kernel witness with two different prefixes (K1 searches shared ones only)")
            kh, sh, val, states = US.settle_witness(tc.factory, r1["prefix"], f"fact_{x}",
                                                    lambda m, g: [m.act(r1["x"]), {"$ref": g}, m.act(r2["x"])])
            m = tc.factory(empty=True, native=False)
            acts = [m.act(st) for st in r1["prefix"]]
            prefixes = {"s1": (acts, states), "s2": (acts, states)}
            values = {"x1": m.act(r1["x"]), "x2": m.act(r2["x"])}
            note = f"the witness (kernel: a shared prefix of {len(acts)} steps), every premise by computation"
            rst = None
        else:
            kh, sh, val = settle_closed(tc.factory, f"fact_{x}",
                                        lambda m: [[m.act(st) for st in w["prefix"]], m.act(w["y"])])
            m = tc.factory(empty=True, native=False)
            prefixes = {}
            values = {"p": [m.act(st) for st in w["prefix"]], "y": m.act(w["y"])}
            note = f"the witness (attribution: a trace of {len(w['prefix'])} steps and y), every premise by computation"
            rst = run_states(tc.factory, w["prefix"])
        d = self.paths(law["law_id"])["proofs"] / "witness"
        d.mkdir(parents=True, exist_ok=True)
        mi, si = self.imports(d, tc)
        li = P3.rel_import(d, self.paths(law["law_id"])["laws"])
        p = d / "PROOF.bend"
        tabs = {"keccak256": kh, "sha256": sh}
        shape = FP.Shape(tc.module_text, el["subform"], el["basis"]["action"], rst)
        p.write_text(FP.counter_proof(law, mi, si, li, tc.hashes, prefixes, values, tabs, FP.Lit(tc.recs, set()), note,
                                      shape), encoding="utf-8")
        checker, verdict = run3.check_file(p)
        if not (checker["marker"] == "ALL PROOFS CHECK" and verdict == "checked"):
            # the one closed computation (the form before parts): a different text, kept when both kernels accept it
            p.write_text(FP.counter_proof(law, mi, si, li, tc.hashes, prefixes, values, tabs, FP.Lit(tc.recs, set()),
                                          note), encoding="utf-8")
            c2, v2 = run3.check_file(p)
            if c2["marker"] == "ALL PROOFS CHECK" and v2 == "checked":
                checker, verdict = c2, v2
            else:
                p.write_text(FP.counter_proof(law, mi, si, li, tc.hashes, prefixes, values, tabs,
                                              FP.Lit(tc.recs, set()), note, shape), encoding="utf-8")
        return p, checker, verdict, tabs, val

    def hashes_json(self, tc: FactCtx, tables: dict) -> dict:
        return {h: [["0x" + k[2:], hexw(v)] for k, v in sorted((tables.get(h) or {}).items())] for h in tc.hashes}

    def witness_json(self, el: dict, tc: FactCtx, w: dict, tables: dict) -> dict:
        if el["subform"] == "kernel":
            return {"runs": [{"prefix": self.steps_json(tc, r["prefix"]), "x": self.steps_json(tc, [r["x"]])[0]}
                             for r in w["runs"]], "hashes": self.hashes_json(tc, tables)}
        # k a JSON integer: the contract leaves its form open, and its replay check reads it with int()
        return {"prefix": self.steps_json(tc, w["prefix"]), "y": self.steps_json(tc, [w["y"]])[0],
                "t": self.steps_json(tc, w.get("t") or []), "k": int(w["k"]), "chooser": w["chooser"],
                "bonded": addr(w["bonded"]), "hashes": self.hashes_json(tc, tables)}

    def chooser(self, el: dict, tc: FactCtx, w: dict) -> str | None:
        """g_P[k] before y on the model (fx_who_<x>): the chooser's address, None when bottom."""
        x = RF.ghost_x(el["law_id"])
        m = tc.factory()
        v = US.Obs(m).value(f"fx_who_{x}", [[m.act(s) for s in w["prefix"]], m.act(w["y"])])
        f = v.get("f") or {}
        if f.get("b"):
            return None
        return addr(word_of(f.get("a")))

    # ---------------------------------------------------------- proofs
    def law_terms(self, law_file: Path, proofs: list[str]) -> int:
        return self.measure.terms(self.measure.law_blocks(law_file.read_text(encoding="utf-8"))) + \
            max([self.measure.terms(t) for t in proofs] or [0])

    def prove(self, el: dict, law: dict, tc: FactCtx, lp: Path, attempts: list) -> dict | None:
        """The product program's routes in order (kernel: guard, injective; attribution: provenance): the first whose
        PROOF.bend is within the term budget and checked by bend2 and BendTT. Returns {"route", "proof", "checker",
        "verdict", "text"} or None; every route tried is an attempt."""
        from ..gen import mproofs as MP
        lid = law["law_id"]
        d = self.paths(lid)["proofs"]
        mi, si = self.imports(d, tc)
        li = P3.rel_import(d, lp)
        routes = ("guard", "injective") if el["subform"] == "kernel" else ("provenance",)
        for route in routes:
            att = {"kind": "proof", "generator": "holon.gen.mproofs.product", "route": route}
            try:
                text = MP.product(route, tc.text, dict(law, subform=el["subform"]), el["basis"], tc.hashes, mi, si, li)
            except FPR.NoProof as e:
                attempts.append(dict(att, error=str(e)))
                continue
            lt = self.law_terms(lp, [text])
            att["term_size"] = {"law_terms": lt, "budget": self.budget}
            if lt > self.budget:
                attempts.append(dict(att, error=f"law_terms {lt} exceeds the budget {self.budget}: not checked"))
                continue
            d.mkdir(parents=True, exist_ok=True)
            p = d / "PROOF.bend"
            p.write_text(text, encoding="utf-8")
            checker, verdict = run3.check_file(p)
            att.update({"checker": checker, "verdict": verdict})
            attempts.append(att)
            if checker["marker"] == "ALL PROOFS CHECK" and verdict == "checked":
                return {"route": route, "proof": run3.rel(p, self.ctx.root), "checker": checker, "verdict": verdict,
                        "text": text}
            shutil.rmtree(d, ignore_errors=True)
        return None

    def inhabit(self, el: dict, law: dict, tc: FactCtx, real) -> tuple[dict, str | None]:
        """The non-vacuity record of a PROVED kernel law (G11V): a reachable state and a step of the action, both runs
        that step from that state, at which fhit_<x> holds; searched like a witness, its calls answered by the
        deployment when there is one, checked like a counter-law, in gen/<M>/<id>/nonvac/. (record, the proof text)."""
        ctx = self.ctx
        lid = law["law_id"]
        x = RF.ghost_x(lid)
        sh = ctx.rc.registry["statements"][lid]
        out = {"status": "unknown", "law": None, "witness": None, "reachable": None, "degenerate": None,
               "parent_statement_hash": sh, "bound": None}
        d = self.paths(lid)["nonvac"]
        shutil.rmtree(d, ignore_errors=True)
        if el["subform"] != "kernel":
            return {**out, "bound": "no inhabitant search for an attribution law"}, None
        accept = None
        kept = {}
        if real is not None:
            def accept(w):
                ww = {"runs": [{"prefix": w["prefix"], "x": w["x"]}, {"prefix": w["prefix"], "x": w["x"]}]}
                try:
                    w2, res = self.repair(real, tc, el, ww)
                except Exception as e:  # noqa: BLE001
                    return f"the real side cannot run it: {type(e).__name__}: {str(e)[:200]}"
                if any(o["status"] != "ok" for o, _c, _d in res[0]):
                    return "a step reverts on the deployment"
                kept["w"] = {"prefix": w2["runs"][0]["prefix"], "x": w2["runs"][0]["x"]}
                return None
        s = FS.FactSearch(tc.factory, tc.doc, ctx.sorts_of(tc.doc_rel), ctx.fsc.search, el, log=ctx.log,
                          accept=accept, deadline=ctx.deadline)
        w, bound = s.inhabit_kernel(el)
        if w is None:
            return {**out, "bound": f"no reachable state and step satisfy fhit_{x} within the search budget ({bound})"}, None
        w = kept.get("w", w)
        prefix, xs = w["prefix"], w["x"]
        kh, shs, val, states = US.settle_witness(tc.factory, prefix, f"fhit_{x}",
                                                 lambda m, g: [m.act(xs), {"$ref": g}, m.act(xs)])
        if val is not True:
            return {**out, "bound": f"fhit_{x} is false at the inhabitant with the deployment's call answers"}, None
        m = tc.factory(empty=True, native=False)
        acts = [m.act(st) for st in prefix]
        d.mkdir(parents=True, exist_ok=True)
        mi, si = self.imports(d, tc)
        lp = d / "LAWS.bend"
        lp.write_text(FP.inhabitant_law(law, sh, mi, si, tc.hashes), encoding="utf-8")
        p = d / "PROOF.bend"
        args = (law, mi, si, P3.rel_import(d, lp), tc.hashes, {"s1": (acts, states), "s2": (acts, states)},
                {"x1": m.act(xs), "x2": m.act(xs)}, {"keccak256": kh, "sha256": shs}, FP.Lit(tc.recs, set()))
        # by parts first (BendTT's fuel), then the one closed computation; the inhabitant's file is a discharging file
        # of the law, so a text over the terms the law's blocks leave in the budget is not checked
        limit = self.budget - self.measure.terms(self.measure.law_blocks(
            self.paths(lid)["laws"].read_text(encoding="utf-8")))
        cands = [FP.inhabitant_proof(*args, shape=FP.Shape(tc.module_text, el["subform"], el["basis"]["action"])),
                 FP.inhabitant_proof(*args)]
        text, tried = None, []
        for t in [c for i, c in enumerate(cands) if c not in cands[:i]]:
            n = self.measure.terms(t)
            if n > limit:
                tried.append(f"{n} terms, over the {limit} the law's budget leaves")
                continue
            p.write_text(t, encoding="utf-8")
            checker, verdict = run3.check_file(p)
            if checker["marker"] == "ALL PROOFS CHECK" and verdict == "checked":
                text = t
                break
            tried.append(f"{checker['marker']}, {verdict}")
        wj = {"prefix": self.steps_json(tc, prefix), "x": self.steps_json(tc, [xs])[0],
              "hashes": self.hashes_json(tc, {"keccak256": kh, "sha256": shs})}
        if text is None:
            shutil.rmtree(d, ignore_errors=True)
            return {**out, "witness": wj, "bound": f"the inhabitant does not check ({'; '.join(tried)})"}, None
        return {**out, "status": "inhabited", "law": run3.rel(lp, ctx.root), "witness": wj, "reachable": True,
                "bound": f"inhabitant: both runs a call of {xs.action} after {len(prefix)} prefix steps"}, text

    # ---------------------------------------------------------- the law
    def decide(self, lid: str, real) -> tuple[dict, dict | None]:
        ctx = self.ctx
        e = ctx.rc.derivation[lid]
        law = json.loads((ctx.rc.laws_dir / f"{lid}.json").read_text())
        tc = ctx.fact(e["facts"])
        el = tc.element(lid)
        lp = self.write_law(law, tc, counter=False)
        shutil.rmtree(self.paths(lid)["proofs"], ignore_errors=True)
        shutil.rmtree(self.paths(lid)["nonvac"].parent, ignore_errors=True)
        attempts = []
        t0 = time.time()
        w, bound = self.search(el, tc, real)
        attempts.append({"kind": "refute", "engine": "holon.fact.search", "budget": dict(ctx.fsc.search),
                         "bound": bound, "found": w is not None})
        ctx.log(f"{lid}: {'witness' if w else 'no witness'} ({bound}) in {round(time.time() - t0, 1)} s")
        status, prim, wj, nonvac, route, term_size, cont = "UNKNOWN", None, None, None, None, None, None
        if w is not None and el["subform"] == "attribution":
            w["chooser"] = self.chooser(el, tc, w)
        if w is not None:
            lp = self.write_law(law, tc, counter=True)
            p, checker, verdict, tables, val = self.emit_counter(el, law, tc, w)
            wj = self.witness_json(el, tc, w, tables)
            ok = checker["marker"] == "ALL PROOFS CHECK" and verdict == "checked"
            attempts.append({"kind": "counter", "checker": checker, "verdict": verdict,
                             "evaluator": "fact is false at the witness" if val is False else
                             "the evaluator finds fact true at the repaired witness (not a witness)"})
            if ok:
                status = "REFUTED"
                prim = {"proof": run3.rel(p, ctx.root), "checker": checker, "verdict": verdict}
                if el["subform"] == "attribution":
                    cont = {"steps": len(w.get("t") or []), "bound": w.get("t_bound")}
            else:
                ctx.log(f"{lid}: the counter-law is not accepted ({checker.get('marker')}, "
                        f"{checker.get('failing')}, {verdict}; {attempts[-1]['evaluator']})")
                shutil.rmtree(self.paths(lid)["proofs"], ignore_errors=True)
                lp = self.write_law(law, tc, counter=False)
        if status != "REFUTED":
            pr = self.prove(el, law, tc, lp, attempts)
            if pr is not None:
                status, route = "PROVED", pr["route"]
                prim = {k: pr[k] for k in ("proof", "checker", "verdict")}
                nonvac, ntext = self.inhabit(el, law, tc, real)
                lt = self.law_terms(lp, [pr["text"]] + ([ntext] if ntext else []))
                term_size = {"law_terms": lt, "budget": self.budget}
                if lt > self.budget:     # the inhabitant's file is a discharging file of the law too
                    attempts.append({"kind": "term_size", "law_terms": lt, "budget": self.budget,
                                     "error": "the law's files with its inhabitant exceed the term budget"})
                    shutil.rmtree(self.paths(lid)["proofs"], ignore_errors=True)
                    shutil.rmtree(self.paths(lid)["nonvac"].parent, ignore_errors=True)
                    status, route, prim, nonvac = "UNKNOWN", None, None, None
            else:
                over = [a["term_size"] for a in attempts if a.get("kind") == "proof" and a.get("term_size")
                        and a["term_size"]["law_terms"] > self.budget]
                term_size = over[0] if over else None
        rec = self.record(law, e, el, tc, status, wj if status == "REFUTED" else None, attempts, lp, prim,
                          bound if status == "UNKNOWN" else None, nonvac, route, term_size, cont)
        rep = None
        if status == "REFUTED" and real is not None:
            rep = replay_entry(self, el, tc, real, rec["witness"])
            rec["replay"] = {"status": rep["status"], "detail": f"calls_agree {rep['calls_agree']}"}
        elif status == "REFUTED":
            rec["replay"] = {"status": "not_applicable", "detail": "no binding: the milestone has no real side"}
        else:
            rec["replay"] = {"status": "not_applicable", "detail": f"{status}: no witness to replay"}
        return rec, rep

    def hypotheses(self, el: dict, status: str, witness: dict | None) -> list:
        """Rule H1: each sidecar hypothesis with the roles the law gives it."""
        calls = set()
        if witness:
            steps = []
            if "runs" in witness:
                for r in witness["runs"]:
                    steps += list(r["prefix"]) + [r["x"]]
            else:
                steps = list(witness["prefix"]) + [witness["y"]] + list(witness.get("t") or [])
            for s in steps:
                for c in (s.get("env") or {}).get("calls") or []:
                    calls.add(c.get("fn"))
        consumer = el["basis"]["consumer"] if el["subform"] == "kernel" else el["basis"]["consumer"]["fn"]
        out = []
        for hid, h in sorted((self.ctx.fsc.doc.get("hypotheses") or {}).items()):
            roles = []
            if f"hyp:{hid}" in el["premises"]:
                roles.append("premise")
            if status == "REFUTED" and calls & set(h.get("functions") or []):
                roles.append("witness")
            if consumer in (h.get("interpretation") or []):
                roles.append("interpretation")
            if roles:
                out.append({"id": hid, "roles": sorted(roles), "result": h.get("result"), "finding": h.get("finding")})
        return out

    def record(self, law: dict, e: dict, el: dict, tc: FactCtx, status: str, witness: dict | None, attempts: list,
               lp: Path, prim: dict | None, bound: str | None, nonvac: dict | None, route: str | None,
               term_size: dict | None, cont: dict | None) -> dict:
        from .. import records as R
        ctx = self.ctx
        lid = law["law_id"]
        sh = ctx.rc.registry["statements"][lid]
        st_text = lp.read_text(encoding="utf-8").replace("F.", "M.")
        cone = R.cone(st_text, tc.combined)
        hyps = self.hypotheses(el, status, witness)
        m = e.get("measure")
        fact = {"subform": el["subform"], "fact_id": el["fact_id"],
                "measure": None if m is None else {"bits": m["bits"], "max_fiber": m["max_fiber"]},
                "hypotheses": hyps,
                "unconditional": not any(h["result"] != "pass" and set(h["roles"]) & {"premise", "witness"}
                                         for h in hyps),
                "impact_conditional_on": sorted(h["id"] for h in hyps
                                                if h["result"] == "fail" and "interpretation" in h["roles"]),
                "term_size": term_size, "route": route if status == "PROVED" else None,
                "consumer_continuation": cont if (status == "REFUTED" and el["subform"] == "attribution") else None}
        rec = {"law_id": lid, "statement_hash": sh, "facts_sha256": law["facts_sha256"], "status": status,
               "scope": "unbounded", "premises": sorted(el["premises"]),
               "kernel": {"name": "bend", "version": run3.bend_version(),
                          "verdict": (prim or {}).get("verdict", "not_run")},
               "artifacts": {"laws": run3.rel(lp, ctx.root), "proof": (prim or {}).get("proof"),
                             "model": run3.rel(tc.path, ctx.root), "law_name": law_name(lid, status == "REFUTED"),
                             "typed_model": run3.rel(ctx.rc.model_path(tc.doc_rel), ctx.root)},
               "checker": (prim or {}).get("checker") or {"exit_code": None, "marker": "not_run"},
               "triage": "finding" if status == "REFUTED" else "none",
               "replay": {"status": "not_run", "detail": ""}, "attempts": attempts, "rule": RF.RULE,
               "subform": el["subform"], "fact": fact, "witness": witness, "bound": bound}
        if status == "REFUTED":
            rec["difference"] = {"lhs": False, "rhs": True}   # fact_<x> at the witness, against true
        try:
            b, match = R.resolve_bundle(rec["facts_sha256"], law["facts"], ctx.root, tc.combined, set(cone), ctx.m)
            assumptions = R.model_assumptions(b["facts_sha256"], set(cone), ctx.root, law["facts"])
        except R.LedgerError:
            match, assumptions = "none", []
        rec.update({"record_version": R.RECORD_VERSION, "prover": "generator", "model_sha256": sha256_file(tc.path),
                    "compiled_sha256": sha256_file(tc.cev.compiled()), "generator_sha256": generator_sha256(ctx.root),
                    "cone": cone, "ledger_match": match, "model_assumptions": assumptions,
                    "scope_v2": R.scope_v2(law, rec), "kernels": R.kernels(rec),
                    "independence_class": R.independence_class(rec), "refinement_refs": [],
                    "coverage": R.coverage_field(law, ctx.root) if ctx.m.startswith("M") else None,
                    "non_vacuity": nonvac or {"status": "counter_witness" if status == "REFUTED" else "unknown",
                                              "law": run3.rel(lp, ctx.root) if status == "REFUTED" else None,
                                              "witness": None, "reachable": None, "degenerate": None,
                                              "parent_statement_hash": sh,
                                              "bound": "the accepted counter-law inhabits the premises"
                                              if status == "REFUTED" else "no proof"},
                    "witness_provenance": {"solidity": "internal_harness"} if status == "REFUTED" else None,
                    "filter_bin": "finding" if status == "REFUTED" else None,
                    **R.evidence_fields(law, {"status": status}, ctx.root)})
        if ctx.m not in ("M0", "M1"):
            from ..gen import oracles as O
            rec["ledger_assumptions"] = sorted(rec["model_assumptions"])
            rec["model_assumptions"] = O.hypothesis_premises(law, None)
        rec["statement"] = law.get("notes", "")
        return rec


# ------------------------------------------------------------------------------------------------ the replay
def real_slot(tc: FactCtx, family: str, key: int, member: str | None = None) -> tuple[int, int, int]:
    """(slot, byte offset, byte size) of F's register at key (or its member) on the real contract: the compiler's
    keccak256 of the key and the family's slot, as the typed model's table maps them."""
    from ..keccak import keccak256
    sec = S.Section(tc.mm, tc.text, tc.doc, tc.hashes, tc.elements, {})
    slot, kt, vt, _n = sec.slots_of(family)
    base = int.from_bytes(keccak256(int(key).to_bytes(32, "big") + int(slot).to_bytes(32, "big")), "big")
    if member is None:
        return base, 0, 32
    mem = next(m for m in vt.get("members") or [] if m.get("label") == member)
    ty = tc.mm.m.type_of(mem["type"])
    return base + int(mem["slot"]), int(mem.get("offset") or 0), int(ty.get("numberOfBytes", 32))


def field(word: int, offset: int, size: int) -> int:
    return (int(word) >> (8 * offset)) & ((1 << (8 * size)) - 1)


def model_obs(tc: FactCtx, steps_json: list) -> tuple[list, list, object]:
    """A trace on the model from Reach's initial state: (observations, the state handles after each step, the model)."""
    m = tc.factory()
    o = US.Obs(m)
    obs, gs = o.run(m.s0(), [US.fresh_step(run3.step_of_json(s)) for s in steps_json])
    return [{k: x[k] for k in ("status", "ret", "logs", "calls")} for x in obs], gs, m


def replay_entry(dec: Decider, el: dict, tc: FactCtx, real, wj: dict) -> dict:
    """holon's replay of one REFUTED FACT witness: its runs on the model (from Reach's initial state, the steps as the
    witness states them) and on the real contract (the binding's deployment), step by step."""
    x = RF.ghost_x(el["law_id"])
    b = el["basis"]
    if el["subform"] == "kernel":
        runs, cms, keys = [], [], []
        for r in wj["runs"]:
            trace = list(r["prefix"]) + [r["x"]]
            obs, gs, m = model_obs(tc, trace)
            g0 = gs[-2] if len(gs) > 1 else m.s0()
            act = m.act(US.fresh_step(run3.step_of_json(r["x"])))
            x0 = {"$call": f"x0_{bname(r['x']['action'])}", "args": [{"$call": "gh_get_st", "args": [{"$ref": g0}]},
                                                                     act["f"]["ar"], act["f"]["en"]] + m.tables()}
            k = US.Obs(m).word(f"fx_key_{x}", [x0])
            keys.append(k)
            cms.append(US.Obs(m).word(f"fx_cmw_{x}", [{"$call": "gh_get_st", "args": [{"$ref": gs[-1]}]},
                                                       {"$w": hexw(k)}]))
            runs.append({"trace": trace, "model": obs})
        slots = sorted({real_slot(tc, b["commitment"], k)[0] for k in keys})
        res = real_runs(real, [r["trace"] for r in runs], slots)
        real_cm = []
        for r, rr, k in zip(runs, res, keys):
            r["real"] = [o for o, _c, _d in rr]
            dump = rr[-1][2]
            real_cm.append(dump[slots.index(real_slot(tc, b["commitment"], k)[0])] if dump else None)
        agree = all(calls_agree(r["trace"], [c for _o, c, _d in rr]) for r, rr in zip(runs, res))
        consumers = [[str(h).lower() for h in r["x"]["env"].get("blobhash") or []] for r in wj["runs"]]
        ok = (all(r["model"] == r["real"] for r in runs) and agree
              and all(r["real"][-1]["status"] == "ok" for r in runs)
              and real_cm[0] is not None and real_cm[0] == real_cm[1] and real_cm == cms
              and consumers[0] != consumers[1])
        return {"runs": runs, "commitment": {"model": [hexw(c) for c in cms],
                                             "real": [hexw(c) if c is not None else None for c in real_cm]},
                "consumers": consumers, "calls_agree": agree, "status": "passed" if ok else "failed"}
    trace = list(wj["prefix"]) + [wj["y"]] + list(wj.get("t") or [])
    obs, gs, m = model_obs(tc, trace)
    n = len(wj["prefix"])
    k = int(str(wj["k"]), 16) if str(wj["k"]).startswith("0x") else int(wj["k"])
    bonded_model = US.Obs(m).word(f"fx_bond_{x}", [{"$call": "gh_get_st", "args": [{"$ref": gs[n]}]}, {"$w": hexw(k)}])
    c = b["consumer"]
    slot, off, size = real_slot(tc, c["family"], k, c["member"])
    res = real_runs(real, [trace], [slot])[0]
    real_obs = [o for o, _c, _d in res]
    bonded_real = field(res[n][2][0], off, size) if res[n][2] else None
    agree = calls_agree(trace, [cc for _o, cc, _d in res])
    cc = None
    sel = dec.consumer_sel(tc, el)
    if wj.get("t"):
        for call in res[-1][1]:
            if sel and call["data"].startswith(sel) and len(call["data"]) >= 74:
                cc = {"step": len(trace) - 1, "fn": c["fn"], "argument": addr(int(call["data"][10:74], 16))}
                break
    chooser = wj.get("chooser")
    ok = (obs == real_obs and agree and bonded_real is not None and bonded_real == bonded_model
          and (chooser is None or bonded_real != int(str(chooser), 16))
          and (not wj.get("t") or (cc is not None and int(cc["argument"], 16) == bonded_real)))
    return {"trace": trace, "model": obs, "real": real_obs, "y_at": n, "chooser": chooser,
            "bonded": {"model": addr(bonded_model), "real": addr(bonded_real) if bonded_real is not None else None},
            "consumer_call": cc, "calls_agree": agree, "status": "passed" if ok else "failed"}


# ------------------------------------------------------------------------------------------------ the CLI
def write_report(ctx: Ctx, entries: dict, merge: bool) -> Path:
    """replay/<M>/fact/report.json: the given entries, merged into the report as it is now when merge (a run of some
    laws keeps the others' entries)."""
    rp = ctx.root / "replay" / ctx.m / "fact" / "report.json"
    rep = {"document": "fact_replay", "milestone": ctx.m, "binding": ctx.rc.sc.binding, "laws": {}}
    if merge and rp.is_file():
        rep["laws"] = dict(json.loads(rp.read_text()).get("laws") or {})
    for lid, x in entries.items():
        if x is None:
            rep["laws"].pop(lid, None)
        else:
            rep["laws"][lid] = x
    rep["laws"] = dict(sorted(rep["laws"].items()))
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(dumps(rep), encoding="utf-8")
    return rp


def run_main(a, ids: list[str] | None = None) -> int:
    root = ROOT
    gen = Path(a.gen_dir).resolve() if a.gen_dir else None
    out = Path(a.out).resolve() if a.out else None
    ctx = Ctx(a.milestone, root, a.sidecar, a.fact_sidecar, gen, out)
    ctx.deadline = getattr(a, "deadline", None)
    lids = fact_laws(ctx.rc.derivation)
    if ids is not None:
        lids = [x for x in lids if x in set(ids)]
    ctx.out.mkdir(parents=True, exist_ok=True)
    own = ctx.out.resolve() == (ctx.root / "results" / ctx.m).resolve()
    real, entries = None, {}
    try:
        for lid in lids:
            if ctx.rc.sc.binding and real is None:
                real = run3.Real(ctx.rc, json.loads((ctx.root / ctx.rc.derivation[lid]["facts"]).read_text()))
            rec, rep = Decider(ctx).decide(lid, real)
            ctx.log(f"{lid}: {rec['status']}")
            (ctx.out / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
            entries[lid] = rep
        if own:
            write_report(ctx, entries, merge=True)
            c = RF.classification(ctx.m, ctx.root)
            cp = ctx.root / "results" / ctx.m / "fact" / "classification.json"
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(dumps(c), encoding="utf-8")
    finally:
        if real is not None:
            real.close()
        ctx.close()
    return 0


def replay_main(a) -> int:
    """holon replay --milestone M: every REFUTED FACT record's runs again, into replay/<M>/fact/report.json."""
    root = ROOT
    ctx = Ctx(a.milestone, root, a.sidecar, a.fact_sidecar, None, None)
    entries, real = {}, None
    try:
        for lid in fact_laws(ctx.rc.derivation):
            p = ctx.out / f"{lid}.json"
            if not p.is_file():
                continue
            r = json.loads(p.read_text())
            if r.get("status") != "REFUTED" or not ctx.rc.sc.binding:
                continue
            e = ctx.rc.derivation[lid]
            if real is None:
                real = run3.Real(ctx.rc, json.loads((ctx.root / e["facts"]).read_text()))
            tc = ctx.fact(e["facts"])
            entries[lid] = replay_entry(Decider(ctx), tc.element(lid), tc, real, r["witness"])
        rp = write_report(ctx, entries, merge=False)
        bad = sorted(k for k, v in entries.items() if v["status"] != "passed")
        print(f"holon replay (FACT): {len(entries)} laws, {len(bad)} failed -> {run3.rel(rp, ctx.root)}")
        return 0 if not bad else 1
    finally:
        if real is not None:
            real.close()
        ctx.close()


def _arg(argv: list, name: str) -> str | None:
    for i, x in enumerate(argv):
        if x == name and i + 1 < len(argv):
            return argv[i + 1]
        if x.startswith(name + "="):
            return x.split("=", 1)[1]
    return None


def has_fact_laws(argv: list, root: Path = ROOT) -> bool:
    """Does the milestone derive FACT laws (a FACT entry in laws/<M>/DERIVATION.json)?"""
    try:
        dv = json.loads((Path(root) / "laws" / str(_arg(argv, "--milestone")) / "DERIVATION.json").read_text())
    except (OSError, ValueError):
        return False
    return any(isinstance(e, dict) and e.get("rule") == RF.RULE for e in dv.get("laws") or [])


def fact_ids_of(argv: list, root: Path = ROOT) -> tuple[list[str], list[str]] | None:
    """(the FACT ids, the other ids) a `holon run --laws ..` names; None without --laws."""
    m, laws = _arg(argv, "--milestone"), _arg(argv, "--laws")
    if laws is None or m is None:
        return None
    try:
        dv = json.loads((Path(root) / "laws" / m / "DERIVATION.json").read_text())
    except (OSError, ValueError):
        dv = {}
    rules = {e.get("law_id"): e.get("rule") for e in dv.get("laws") or [] if isinstance(e, dict)}
    ids = [x.strip() for x in laws.split(",") if x.strip()]
    return [x for x in ids if rules.get(x) == RF.RULE], [x for x in ids if rules.get(x) != RF.RULE]


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
    """holon run | replay of a typed milestone's FACT laws (holon/__main__.py sends --laws naming FACT laws here, and
    a run or replay of the whole milestone after its other laws)."""
    cmd, rest = argv[0], argv[1:]
    ap = argparse.ArgumentParser(prog=f"holon {cmd}", add_help=False)
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--sidecar")
    ap.add_argument("--fact-sidecar")
    ap.add_argument("--laws")
    ap.add_argument("--out")
    ap.add_argument("--gen-dir")
    ap.add_argument("--deadline", help="a wall-clock time box on each FACT search (ISO 8601 UTC or epoch seconds): a "
                                       "law the search has not decided by then is recorded with the time box")
    a, _unknown = ap.parse_known_args(rest)
    from ..undo.run import parse_deadline
    a.deadline = parse_deadline(a.deadline)
    if not RF.has_sidecar(a.milestone, ROOT, a.fact_sidecar):
        print(f"holon {cmd} (FACT): no FACT sidecar for {a.milestone}: the FACT laws are not decided", file=sys.stderr)
        return 2
    if cmd == "replay":
        return replay_main(a)
    ids = [x.strip() for x in (a.laws or "").split(",") if x.strip()] or None
    return run_main(a, ids)
