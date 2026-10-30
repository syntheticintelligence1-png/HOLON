"""The SYM laws of a typed milestone, decided on the typed model (BUILD_PLAN I34; the contract is rules J6, J8 and J9
of the docstring of tests_m3/test_sym.py).

  python -m holon run --milestone M [--sidecar PATH] [--laws ID,ID] [--out DIR] [--gen-dir DIR]

`run` decides every SYM law of laws/<M> (or those --laws names), one document at a time:
  1. the sym section gen/<M>/sym/models/<model>.bend over the typed model (holon.gen.symsec), and the law's
     statement gen/<M>/laws/<id>/LAWS.bend importing both (holon.symd.proofs);
  2. refutation (holon.symd.search, the budget below) on the combined module the evaluator runs; with the sidecar's
     binding a witness counts only when it runs on the real contract as on the model: every prefix step succeeds, and
     x (tau, pi: from s and, after the target's slots are set to g s, as g x; omega: both orders; sentinel: once)
     succeeds or reverts there as the model says; its calls then answered as the deployment answers them, the claim
     must still be false. Its counter-law gen/<M>/proofs/<id>/witness/PROOF.bend is accepted only when bend2 and BendTT
     check it;
  3. without an accepted counter-law, the law's proof (holon.symd.proofs: the sentinel proof of a site that writes the
     clock); a law it does not decide stays UNKNOWN with what was tried (NO_PROOF);
  4. G11V: an inhabitant of the premises (sy_hit_<n>) searched like a witness, its proof gen/<id>/nonvac/PROOF.bend;
  5. the record results/<M>/<id>.json (v1 and v2, with the sym field); a REFUTED tau or pi law's filter_bin is
     split_pending (J8), never finding; then results/<M>/sym/<family>.json (A_eq, A_break, A_unknown per family and
     role), results/<M>/sym/races.json (J5) and audit/sym_adjudications/<family>_<role or "time">.json (route (ii)
     requests, answered in I45), and replay/<M>/sym/report.json.

Nothing here names a target.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from ..gen import symsec as SS
from ..gen.mlaws import law_name
from ..machine_bend import bname
from ..rules import sym as R
from ..sorts import evaluate3 as E3
from ..sorts import run3
from ..sorts import search3 as S3
from ..sorts.model3 import importable, model_name, write_model_file
from ..undo import proofs as UP
from ..undo.trace import act_constructors
from ..undo import search as US
from . import proofs as SP
from . import search as SY

ROOT = Path(__file__).resolve().parents[2]
GEN_SYM = ["holon/symd/run.py", "holon/symd/search.py", "holon/symd/proofs.py", "holon/gen/symsec.py",
           "holon/rules/sym.py", "holon/sym.py"]
BUDGET = {"prefix_depth": 2, "max_prefixes": 400, "max_candidates": 60000}
SPLIT = ("tau", "pi")


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def generator_sha256(root: Path) -> str:
    h = hashlib.sha256()
    for rel in sorted(GEN_SYM):
        p = root / rel
        h.update(rel.encode() + b"\0" + (p.read_bytes() if p.is_file() else b"") + b"\0")
    return h.hexdigest()


def sym_laws(derivation: dict) -> list[str]:
    return sorted(lid for lid, e in derivation.items() if e.get("rule") == R.RULE)


class SymCtx:
    """One document's sym section: the module Bend checks, and the combined module the evaluator runs."""

    def __init__(self, ctx: "Ctx", doc_rel: str):
        rc = ctx.rc
        self.doc_rel = doc_rel
        self.root = rc.root
        self.ev, self.init, _mf, self.mm, self.docm = rc.model(doc_rel)
        self.text = rc.model_path(doc_rel).read_text(encoding="utf-8")
        self.doc = json.loads((rc.root / doc_rel).read_text(encoding="utf-8"))
        self.hashes = self.ev.hashes()
        self.assignment = ctx.sorts_of(doc_rel)
        self.elements = R.elements(self.doc, self.assignment, doc_rel)
        got = {e["law_id"]: e for e in self.elements}
        for lid in sym_laws(rc.derivation):
            de = rc.derivation[lid]
            if de["facts"] != doc_rel:
                continue
            if lid not in got or got[lid]["basis"] != de["basis"]:
                raise RuntimeError(f"{lid}: the document's analysis no longer gives the derived basis (derive again)")
        self.fn = {e["law_id"]: n for n, e in enumerate(self.elements)}
        self.dir = ctx.gen / "sym" / "models"
        name = model_name(doc_rel)
        self.import_file = self.dir / importable(name)
        mt, self.notes = SS.module_text(self.mm, self.text, self.doc, self.hashes, self.elements, self.assignment,
                                        os.path.relpath(rc.import_path(doc_rel), self.dir).replace(os.sep, "/"))
        self.path = write_model_file(self.dir, name, mt)
        ct = SS.combined_text(self.mm, self.text, self.doc, self.hashes, self.elements, self.assignment)
        cd = E3.cache_dir().parent / "sym3" / hashlib.sha256(ct.encode()).hexdigest()[:32]
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
        self.actions = act_constructors(self.text)

    def factory(self, empty: bool = False, native: bool = True) -> S3.Model:
        i = dict(self.init)
        if empty:
            i["preimages"] = []
        return S3.Model(self.cev, i, self.hints, self.root / self.doc_rel, native=native)

    def close(self):
        self.cev.close()


class Ctx:
    def __init__(self, milestone: str, root: Path, sidecar: str | None, gen: Path | None, out: Path | None,
                 log=print):
        self.rc = run3.Ctx(milestone, root, sidecar, gen, out, log)
        self.m = milestone
        self.root = Path(root)
        self.gen = self.rc.gen
        self.out = self.rc.out
        self.log = log
        self.deadline: float | None = None
        self.secs: dict = {}

    def sec(self, doc_rel: str) -> SymCtx:
        if doc_rel not in self.secs:
            self.secs[doc_rel] = SymCtx(self, doc_rel)
        return self.secs[doc_rel]

    def sorts_of(self, doc_rel: str) -> dict:
        a = json.loads((self.root / "gen" / self.m / "sorts" / "assignment.json").read_text())
        return a["models"][model_name(doc_rel)]["assignment"]

    def close(self):
        for s in self.secs.values():
            s.close()
        self.rc.close()


# ------------------------------------------------------------------------------------------------ the real side
def _w(n) -> dict:
    return {"$w": "0x%064x" % (int(n) & ((1 << 256) - 1))}


def g_step(st: S3.Step, w: dict, doc: dict) -> S3.Step:
    """g x as a step: τ_d moves the clock by d; π_(a,b) swaps the caller and the address-typed arguments."""
    env, args = json.loads(json.dumps(st.env)), json.loads(json.dumps(st.args))
    if w["subform"] == "tau":
        env["block.timestamp"] = int(env.get("block.timestamp") or 0) + int(w["d"])
        return S3.Step(st.action, args, env)
    a, b = int(w["a"]), int(w["b"])
    sw = lambda v: b if v == a else (a if v == b else v)  # noqa: E731
    env["caller"] = sw(SY._int(env.get("caller")))
    act = next((x for x in doc.get("actions") or [] if x["name"] == st.action), {})
    for p in act.get("params") or []:
        if p.get("type") == "address" and p["name"] in args:
            args[p["name"]] = sw(SY._int(args[p["name"]]))
    return S3.Step(st.action, args, env)


def pokes(m: S3.Model, g: str, w: dict) -> list:
    """The target's slots to set so that the deployment after the prefix holds g s: every real slot of s or g s whose
    word differs (a slot g s does not hold is set to zero)."""
    h = m.fresh()
    if w["subform"] == "tau":
        m.mreq({"fn": "sy_tau_g", "args": [{"$ref": g}, _w(w["d"])], "save": h, "quiet": True})
    else:
        m.mreq({"fn": "sy_pi_g", "args": [{"$ref": g}, _w(w["a"]), _w(w["b"])], "save": h, "quiet": True})
    s1, s2 = m.state(g), m.state(h)
    m.drop([h])
    return [(sl, s2.get(sl, 0)) for sl in sorted(set(s1) | set(s2)) if s1.get(sl, 0) != s2.get(sl, 0)]


def harness_steps(sc: SymCtx, sts: list, fork_from: int | None = None, poked: dict | None = None) -> list:
    from ..replay_fragments import Step
    fns = run3.fn_names(sc.docm)
    out = []
    for i, st in enumerate(sts):
        j = run3.step_json(sc.docm, st, fns)
        e = j["env"]
        out.append(Step(kind="call", caller=e["caller"], value=int(e.get("msg.value", 0)),
                        timestamp=int(e["block.timestamp"]), blobs=list(e.get("blobhash") or []), to=None,
                        data=j["calldata"], fork=fork_from is not None and i >= fork_from,
                        pokes=list((poked or {}).get(i, []))))
    return out


def real_outcomes(real, sc: SymCtx, traces: list) -> list:
    """[(outcome per step, calls per step)] of each harness trace on the deployment."""
    from ..replay_fragments import run_harness
    real.setup()
    runs = run_harness(real.proj, real.tc, real.binding, traces, [], real.init, tag="sym")
    out = []
    for tr in runs:
        execs = [e for e in tr.execs if e.id != "d"]
        out.append((["ok" if e.ok else "rev " + run3.revert_text(bytes.fromhex(e.ret[2:])) for e in execs],
                    [[{"to": c[0], "data": c[1], "ok": c[2], "ret": c[3]} for c in e.calls] for e in execs]))
    return out


# ------------------------------------------------------------------------------------------------ the decider
class Decider:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx

    def paths(self, lid: str) -> dict:
        g = self.ctx.gen
        return {"laws": g / "laws" / lid / "LAWS.bend", "proofs": g / "proofs" / lid, "nonvac": g / lid / "nonvac"}

    def imports(self, d: Path, sc: SymCtx) -> tuple[str, str]:
        return (os.path.relpath(self.ctx.rc.import_path(sc.doc_rel), d).replace(os.sep, "/"),
                os.path.relpath(sc.import_file, d).replace(os.sep, "/"))

    def write_law(self, law: dict, sc: SymCtx, counter: bool) -> Path:
        p = self.paths(law["law_id"])["laws"]
        p.parent.mkdir(parents=True, exist_ok=True)
        sh = self.ctx.rc.registry["statements"][law["law_id"]]
        mi, si = self.imports(p.parent, sc)
        p.write_text(SP.law_file(law, sc.fn[law["law_id"]], sh, mi, si, sc.hashes, counter=counter), encoding="utf-8")
        return p

    def steps_json(self, sc: SymCtx, steps: list) -> list:
        fns = run3.fn_names(sc.docm)
        return [run3.step_json(sc.docm, st, fns) for st in steps]

    def values(self, el: dict, w: dict, m) -> dict:
        sub = el["subform"]
        v = {"x": m.act(w["x"])}
        if sub == "tau":
            v["d"] = int(w["d"])
        elif sub == "pi":
            v["a"], v["b"] = int(w["a"]), int(w["b"])
        elif sub == "omega":
            v["y"] = m.act(w["y"])
        return v

    def args_of(self, el: dict, w: dict):
        def f(m, g):
            v = self.values(el, w, m)
            return [v[n] if not isinstance(v[n], int) else _w(v[n]) for n, _t in R.BINDERS[el["subform"]][1:]]
        return f

    def model_value(self, sc: SymCtx, el: dict, w: dict):
        m = sc.factory()
        g = m.s0()
        for st in w.get("prefix") or []:
            code, g, _c = m.run_step(g, US.fresh_step(st), save=True)
            if code != 0:
                return None
        n = sc.fn[el["law_id"]]
        r = US.Obs(m).settle({"fn": f"sy_ok_{n}", "args": lambda: [{"$ref": g}] + list(self.args_of(el, w)(m, g))},
                             w["x"])
        return bool(r["out"])

    def real_check(self, real, sc: SymCtx, el: dict, w: dict):
        """None when the witness runs on the deployment as on the model (see the module docstring), else the reason;
        and the replay entry."""
        sub = w["subform"]
        pre = list(w.get("prefix") or [])
        m = sc.factory()
        g = m.s0()
        for st in pre:
            code, g, _c = m.run_step(g, US.fresh_step(st), save=True)
            if code != 0:
                return "a prefix step does not succeed on the model from Reach's initial state", None
        o = US.Obs(m)
        n0 = len(pre)
        if sub in SPLIT:
            gx = g_step(w["x"], w, sc.doc)
            pk = pokes(m, g, w)
            trace = harness_steps(sc, pre + [w["x"], gx], fork_from=n0, poked={n0 + 1: pk})
            model = [w["codes"][0] == 0, w["codes"][1] == 0]
        elif sub == "omega":
            trace = harness_steps(sc, pre + [w["x"], w["y"]], fork_from=None)
            trace2 = harness_steps(sc, pre + [w["y"], w["x"]], fork_from=None)
            model = [True, True]
        else:
            trace = harness_steps(sc, pre + [w["x"]])
            model = [True]
        traces = [trace] + ([trace2] if sub == "omega" else [])
        try:
            res = real_outcomes(real, sc, traces)
        except Exception as e:  # noqa: BLE001: a witness the real side cannot run is no witness
            return f"the real side cannot run it: {type(e).__name__}: {str(e)[:200]}", None
        outs = res[0][0]
        if any(x != "ok" for x in outs[:n0]):
            return f"a prefix step does not succeed on the deployment ({outs[:n0]})", None
        if sub == "omega":
            got = [res[0][0][n0:] == ["ok", "ok"], res[1][0][n0:] == ["ok", "ok"]]
        else:
            got = [x == "ok" for x in outs[n0:]]
        rep = {"law": el["law_id"], "subform": sub, "model": model, "real": got,
               "outcomes": [r[0][n0:] for r in res], "pokes": len(pk) if sub in SPLIT else 0}
        if got != model:
            if got[0] != model[0]:     # x itself (from s, as the model runs it) does not run on the deployment as on the model
                return (f"x:{w['x'].action}: the deployment's outcomes {got} are not the model's {model} "
                        f"({[r[0][n0:] for r in res]})"), rep
            return f"the deployment's outcomes {got} are not the model's {model} ({[r[0][n0:] for r in res]})", rep
        if self.model_value(sc, el, w) is not False:
            return "with the deployment's call answers the model finds the claim true", rep
        rep["status"] = "passed"
        return None, rep

    def search(self, sc: SymCtx, el: dict, real=None):
        kept = {}
        accept = None
        if real is not None:
            def accept(w):
                why, rep = self.real_check(real, sc, el, w)
                if why is None:
                    kept["rep"] = rep
                return why
        s = SY.SymSearch(sc.factory, sc.doc, self.ctx.sorts_of(sc.doc_rel), BUDGET, sc.fn, log=self.ctx.log,
                         accept=accept, deadline=self.ctx.deadline)
        w, bound = s.decide(el)
        return w, bound, kept.get("rep"), s.races

    def settle_runs(self, sc: SymCtx, el: dict, w: dict, kh: dict, sh: dict) -> dict:
        """The decoded result (UOS) of each run sy_ok_<n> makes at the witness, on a model holding exactly the settled
        tables; a run that looks up a key outside them refuses (the tables would not be the proof's)."""
        m = sc.factory(empty=True, native=False)
        m.kh.update(kh)
        m.sh.update(sh)
        g = m.s0()
        for st in w["prefix"]:
            code, g, _c = m.run_step(g, US.fresh_step(st), save=True)
            if code != 0:
                raise RuntimeError(f"the witness's prefix step {st.action} does not succeed (code {code})")
        before = (len(m.kh), len(m.sh))

        def run(act, gs, save=None):
            r = m.mreq(dict({"fn": "ux_ostep", "args": [act, gs] + m.tables()}, **({"save": save} if save else {})))
            m.learn(r)
            if (len(m.kh), len(m.sh)) != before:
                raise RuntimeError("a run of the claim looks up a hash key the settled tables do not hold")
            return r["out"]
        sub = el["subform"]
        x = m.act(w["x"])
        if sub in ("tau", "pi"):
            if sub == "tau":
                gen = [_w(w["d"])]
                fx, fg, fu = "sy_tau_x", "sy_tau_g", "sy_tau_uos"
            else:
                gen = [_w(w["a"]), _w(w["b"])]
                fx, fg, fu = "sy_pi_x", "sy_pi_g", f"sy_pi_uos_{bname(el['basis']['action'])}"
            h1 = m.fresh()
            out = {"u1": run(x, {"$ref": g}, h1),
                   "px": m.mreq({"fn": fx, "args": [x] + gen})["out"],
                   "ps": m.mreq({"fn": fg, "args": [{"$ref": g}] + gen})["out"],
                   "u2": run({"$call": fx, "args": [x] + gen}, {"$call": fg, "args": [{"$ref": g}] + gen}),
                   "pu1": m.mreq({"fn": fu, "args": [{"$ref": h1}] + gen})["out"]}
            m.drop([h1])
            return out
        y = m.act(w["y"])
        hx, hy = m.fresh(), m.fresh()
        out = {"ux": run(x, {"$ref": g}, hx), "uy": run(y, {"$ref": g}, hy)}
        out["uxy"] = run(y, {"$call": "sy_post", "args": [{"$ref": hx}]})
        out["uyx"] = run(x, {"$call": "sy_post", "args": [{"$ref": hy}]})
        m.drop([hx, hy])
        return out

    def emit_counter(self, el: dict, law: dict, sc: SymCtx, w: dict):
        n = sc.fn[law["law_id"]]
        kh, sh, val, states = US.settle_witness(sc.factory, w["prefix"], f"sy_ok_{n}", self.args_of(el, w))
        runs = self.settle_runs(sc, el, w, kh, sh) if el["subform"] != "sentinel" else None
        m = sc.factory(empty=True, native=False)
        d = self.paths(law["law_id"])["proofs"] / "witness"
        d.mkdir(parents=True, exist_ok=True)
        mi, si = self.imports(d, sc)
        li = os.path.relpath(self.paths(law["law_id"])["laws"], d).replace(os.sep, "/")
        p = d / "PROOF.bend"
        note = f"the witness ({el['subform']}: prefix {len(w['prefix'])} steps), every premise by computation"
        lit = SP.SymLit(sc.recs, sc.mine, SP.constructors(sc.text))
        if runs is None:
            text = SP.counter_proof(law, n, mi, si, li, sc.hashes, [m.act(s) for s in w["prefix"]], states,
                                    self.values(el, w, m), {"keccak256": kh, "sha256": sh}, lit, note)
        else:
            text = SP.counter_proof_split(law, n, el["subform"], mi, si, li, sc.hashes, [m.act(s) for s in w["prefix"]],
                                          states, self.values(el, w, m), {"keccak256": kh, "sha256": sh}, lit, runs,
                                          el["basis"], note + ", one conversion per run")
        p.write_text(text, encoding="utf-8")
        checker, verdict = run3.check_file(p)
        return p, checker, verdict, {"keccak256": kh, "sha256": sh}, val

    def witness_json(self, el: dict, sc: SymCtx, w: dict, tables: dict) -> dict:
        out = {"prefix": self.steps_json(sc, w["prefix"]), "x": self.steps_json(sc, [w["x"]])[0],
               "hashes": {h: [["0x" + k[2:], "0x%064x" % v] for k, v in sorted((tables.get(h) or {}).items())]
                          for h in ("keccak256", "sha256")}}
        sub = el["subform"]
        if sub == "tau":
            out["d"] = int(w["d"])
        elif sub == "pi":
            out["a"], out["b"] = "0x%040x" % int(w["a"]), "0x%040x" % int(w["b"])
        elif sub == "omega":
            out["y"] = self.steps_json(sc, [w["y"]])[0]
        return out

    def prove(self, el: dict, law: dict, sc: SymCtx) -> tuple[dict, dict | None]:
        """The law's proof attempt: (the attempt record, the accepted proof or None)."""
        sub = el["subform"]
        if sub != "sentinel":
            return {"kind": "proof", "generator": f"holon.symd.proofs.{sub}", "marker": None,
                    "error": SP.NO_PROOF[sub]}, None
        b = el["basis"]
        term = next((v for a, src, v in R.S.write_values(sc.doc, b["register"])
                     if a == b["action"] and src == b["src"] and v != b["constant"]), None)
        d = self.paths(law["law_id"])["proofs"]
        d.mkdir(parents=True, exist_ok=True)
        mi, si = self.imports(d, sc)
        li = os.path.relpath(self.paths(law["law_id"])["laws"], d).replace(os.sep, "/")
        try:
            text = SP.sentinel_proof(law, sc.fn[law["law_id"]], term, b["action"], sc.actions, mi, si, li, sc.hashes)
        except SP.NoProof as e:
            return {"kind": "proof", "generator": "holon.symd.proofs.sentinel", "marker": None, "error": str(e)}, None
        p = d / "PROOF.bend"
        p.write_text(text, encoding="utf-8")
        checker, verdict = run3.check_file(p)
        att = {"kind": "proof", "generator": "holon.symd.proofs.sentinel", "class": "clock_site",
               "checker": checker, "verdict": verdict}
        if checker["marker"] == "ALL PROOFS CHECK" and verdict == "checked":
            return att, {"proof": run3.rel(p, self.ctx.root), "checker": checker, "verdict": verdict}
        return att, None

    def inhabit(self, el: dict, law: dict, sc: SymCtx) -> dict:
        lid = law["law_id"]
        sh = self.ctx.rc.registry["statements"][lid]
        base = {"status": "unknown", "law": None, "witness": None, "reachable": None, "degenerate": None,
                "parent_statement_hash": sh, "bound": None}
        nd = self.paths(lid)["nonvac"]
        shutil.rmtree(nd, ignore_errors=True)
        s = SY.SymSearch(sc.factory, sc.doc, self.ctx.sorts_of(sc.doc_rel), BUDGET, sc.fn, log=self.ctx.log,
                         deadline=self.ctx.deadline)
        w, bound = s.inhabitant(el)
        if w is None:
            return {**base, "bound": f"no inhabitant: {bound}"}
        n = sc.fn[lid]
        kh, shh, _val, states = US.settle_witness(sc.factory, w["prefix"], f"sy_hit_{n}", self.args_of(el, w))
        m = sc.factory(empty=True, native=False)
        nd.mkdir(parents=True, exist_ok=True)
        mi, si = self.imports(nd, sc)
        lp = nd / "LAWS.bend"
        lp.write_text(SP.inhabitant_law(law, n, sh, mi, si, sc.hashes), encoding="utf-8")
        p = nd / "PROOF.bend"
        p.write_text(SP.inhabitant_proof(law, n, mi, si, "./LAWS.bend", sc.hashes, [m.act(x) for x in w["prefix"]],
                                         states, self.values(el, w, m), {"keccak256": kh, "sha256": shh},
                                         UP.Lit(sc.recs, sc.mine)), encoding="utf-8")
        checker, verdict = run3.check_file(p)
        ok = checker["marker"] == "ALL PROOFS CHECK" and verdict == "checked"
        return {**base, "status": "inhabited" if ok else "unknown", "law": run3.rel(lp, self.ctx.root),
                "witness": self.witness_json(el, sc, w, {"keccak256": kh, "sha256": shh}) if ok else None,
                "reachable": ok, "degenerate": False if ok else None,
                "bound": bound if ok else f"the inhabitant's proof did not check: {checker['marker']}, {verdict}"}

    def decide(self, lid: str, real) -> tuple[dict, dict | None, list]:
        ctx = self.ctx
        e = ctx.rc.derivation[lid]
        law = json.loads((ctx.rc.laws_dir / f"{lid}.json").read_text())
        sc = ctx.sec(e["facts"])
        el = next(x for x in sc.elements if x["law_id"] == lid)
        lp = self.write_law(law, sc, counter=False)
        shutil.rmtree(self.paths(lid)["proofs"], ignore_errors=True)
        attempts = []
        t0 = time.time()
        status, prim, wj, diag = "UNKNOWN", None, None, None
        w, bound, rep, races = None, None, None, []
        if el["subform"] == "sentinel":
            # a checked proof leaves no counterexample to find: the proof first, the search only without one
            att, pr = self.prove(el, law, sc)
            attempts.append(att)
            if pr is not None:
                status, prim = "PROVED", pr
        if status != "PROVED":
            w, bound, rep, races = self.search(sc, el, real)
            attempts.append({"kind": "refute", "engine": "holon.symd.search", "budget": dict(BUDGET), "bound": bound,
                             "found": w is not None})
            ctx.log(f"{lid}: {'witness' if w else 'no witness'} ({bound}) in {round(time.time() - t0, 1)} s")
        if w is not None:
            lp = self.write_law(law, sc, counter=True)
            p, checker, verdict, tables, val = self.emit_counter(el, law, sc, w)
            wj = self.witness_json(el, sc, w, tables)
            ok = checker["marker"] == "ALL PROOFS CHECK" and verdict == "checked"
            attempts.append({"kind": "counter", "checker": checker, "verdict": verdict,
                             "evaluator": "the claim is false at the witness" if val is False else
                             "the evaluator finds the claim true at the settled witness (not a witness)"})
            if ok:
                status = "REFUTED"
                prim = {"proof": run3.rel(p, ctx.root), "checker": checker, "verdict": verdict}
            else:
                diag = attempts[-1]["evaluator"]
                shutil.rmtree(self.paths(lid)["proofs"], ignore_errors=True)
                lp = self.write_law(law, sc, counter=False)
        if status == "UNKNOWN" and el["subform"] != "sentinel":
            att, pr = self.prove(el, law, sc)
            attempts.append(att)
            if pr is not None:
                status, prim = "PROVED", pr
        nv = None
        if status != "REFUTED":
            nv = self.inhabit(el, law, sc)
        rec = self.record(law, e, el, sc, status, wj if status == "REFUTED" else None, attempts, lp, prim,
                          bound if status == "UNKNOWN" else None, diag, nv)
        if status == "REFUTED":
            rec["replay"] = ({"status": rep.get("status", "failed"), "detail": f"model {rep['model']}, real {rep['real']}"}
                             if rep else {"status": "not_applicable", "detail": "no binding: no real side"})
        else:
            rec["replay"] = {"status": "not_applicable", "detail": f"{status}: no witness to replay"}
        return rec, rep, [dict(r, x=self.steps_json(sc, [r["x"]])[0], y=self.steps_json(sc, [r["y"]])[0],
                               prefix=self.steps_json(sc, r["prefix"])) for r in races]

    def record(self, law: dict, e: dict, el: dict, sc: SymCtx, status: str, witness: dict | None, attempts: list,
               lp: Path, prim: dict | None, bound: str | None, diag: str | None, nv: dict | None) -> dict:
        from .. import records as RC
        ctx = self.ctx
        lid = law["law_id"]
        sh = ctx.rc.registry["statements"][lid]
        st_text = lp.read_text(encoding="utf-8").replace("U.", "M.")
        cone = RC.cone(st_text, sc.combined)
        sub = el["subform"]
        bin_ = None
        if status == "REFUTED":
            bin_ = "split_pending" if sub in SPLIT else "finding"
        premises = []
        if sub == "sentinel" and ["env", "block.timestamp"] in list(R.S._walk(
                next((v for a, src, v in R.S.write_values(sc.doc, el["basis"]["register"])
                      if a == el["basis"]["action"] and src == el["basis"]["src"]), None))):
            premises.append("env:block.timestamp >= 1 (a law premise: on chain no block has timestamp 0)")
        if sub == "tau":
            premises.append("fits64: every Time word of s and x plus d is below 2^64")
        rec = {"law_id": lid, "statement_hash": sh, "facts_sha256": law["facts_sha256"], "status": status,
               "scope": "unbounded", "premises": premises,
               "kernel": {"name": "bend", "version": run3.bend_version(),
                          "verdict": (prim or {}).get("verdict", "not_run")},
               "artifacts": {"laws": run3.rel(lp, ctx.root), "proof": (prim or {}).get("proof"),
                             "model": run3.rel(sc.path, ctx.root), "law_name": law_name(lid, status == "REFUTED"),
                             "typed_model": run3.rel(ctx.rc.model_path(sc.doc_rel), ctx.root)},
               "checker": (prim or {}).get("checker") or {"exit_code": None, "marker": "not_run"},
               "triage": "finding" if status == "REFUTED" else "none",
               "replay": {"status": "not_run", "detail": ""}, "attempts": attempts, "rule": R.RULE,
               "subform": sub, "sym": {"subform": sub, "sym_id": el["sym_id"], "basis": el["basis"],
                                       "section": SS.SECTION_VERSION, "notes": list(sc.notes)},
               "witness": witness, "bound": bound}
        if status == "REFUTED":
            rec["difference"] = {"lhs": False, "rhs": True}
        if diag:
            rec["diagnosis"] = diag
        try:
            b, match = RC.resolve_bundle(rec["facts_sha256"], law["facts"], ctx.root, sc.combined, set(cone), ctx.m)
            assumptions = RC.model_assumptions(b["facts_sha256"], set(cone), ctx.root, law["facts"], ctx.m)
        except RC.LedgerError:
            match, assumptions = "none", []
        if status == "REFUTED":
            nvf = {"status": "counter_witness", "law": run3.rel(lp, ctx.root), "witness": None, "reachable": None,
                   "degenerate": None, "parent_statement_hash": sh,
                   "bound": "the accepted counter-law inhabits the premises"}
        else:
            nvf = nv
        rec.update({"record_version": RC.RECORD_VERSION, "prover": "generator", "model_sha256": sha256_file(sc.path),
                    "compiled_sha256": sha256_file(sc.cev.compiled()), "generator_sha256": generator_sha256(ctx.root),
                    "cone": cone, "ledger_match": match, "model_assumptions": assumptions,
                    "scope_v2": RC.scope_v2(law, rec), "kernels": RC.kernels(rec),
                    "independence_class": RC.independence_class(rec), "refinement_refs": [],
                    "coverage": RC.coverage_field(law, ctx.root) if ctx.m.startswith("M") else None,
                    "non_vacuity": nvf,
                    "witness_provenance": {"solidity": "internal_harness"} if status == "REFUTED" else None,
                    "filter_bin": bin_, **RC.evidence_fields(law, {"status": status}, ctx.root)})
        if ctx.m not in ("M0", "M1"):
            from ..gen import oracles as O
            rec["ledger_assumptions"] = sorted(rec["model_assumptions"])
            rec["model_assumptions"] = O.hypothesis_premises(law, None)
        rec["statement"] = law.get("notes", "")
        return rec


# ------------------------------------------------------------------------------------------------ splits and requests
def families_doc(m: str, root: Path) -> dict:
    """results/<M>/sym/<family>.json contents per family: A_eq, A_break (witness, the site or principal localized),
    A_unknown, per role (pi) or "time" (tau)."""
    out: dict = {}
    for p in sorted((root / "results" / m).glob("L_sym_*.json")):
        r = json.loads(p.read_text())
        sub = r.get("subform")
        if sub not in SPLIT:
            continue
        b = (r.get("sym") or {}).get("basis") or {}
        group = b.get("role") if sub == "pi" else "time"
        row = out.setdefault(sub, {}).setdefault(group, {"A_eq": [], "A_break": [], "A_unknown": []})
        a = b.get("action")
        if r["status"] == "PROVED":
            row["A_eq"].append(a)
        elif r["status"] == "REFUTED":
            row["A_break"].append({"action": a, "law": r["law_id"], "witness": r.get("witness"),
                                   "localizes": (f"principal {b.get('role')}" if sub == "pi" else "a Time comparison")})
        else:
            row["A_unknown"].append(a)
    return out


def write_splits(m: str, root: Path, races: list) -> None:
    d = root / "results" / m / "sym"
    d.mkdir(parents=True, exist_ok=True)
    fams = families_doc(m, root)
    for fam in ("tau", "pi"):
        doc = {"document": "sym_split", "milestone": m, "family": fam, "groups": fams.get(fam, {})}
        (d / f"{fam}.json").write_text(dumps(doc), encoding="utf-8")
        for group, row in sorted(fams.get(fam, {}).items()):
            if row["A_break"] and (row["A_eq"] or row["A_unknown"]):
                ad = root / "audit" / "sym_adjudications"
                ad.mkdir(parents=True, exist_ok=True)
                req = {"split": f"{fam}_{group}", "eq": sorted(row["A_eq"]),
                       "break": sorted(x["action"] for x in row["A_break"]),
                       "hypotheses": ["minority deviates", "majority deviates"], "answer": None}
                (ad / f"{fam}_{group}.json").write_text(dumps(req), encoding="utf-8")
    rp = d / "races.json"
    cur = json.loads(rp.read_text()) if rp.is_file() else {"document": "sym_races", "milestone": m, "races": []}
    keep = {r["law"]: r for r in cur.get("races") or []}
    for r in races:
        keep[r["law"]] = {k: v for k, v in r.items()}
    rp.write_text(dumps(dict(cur, races=[keep[k] for k in sorted(keep)])), encoding="utf-8")


# ------------------------------------------------------------------------------------------------ the command
def run_main(a, ids: list[str] | None = None) -> int:
    root = ROOT
    gen = Path(a.gen_dir).resolve() if getattr(a, "gen_dir", None) else None
    out = Path(a.out).resolve() if getattr(a, "out", None) else None
    ctx = Ctx(a.milestone, root, getattr(a, "sidecar", None), gen, out)
    ctx.deadline = getattr(a, "deadline", None)
    lids = sym_laws(ctx.rc.derivation)
    if ids is not None:
        lids = [x for x in lids if x in set(ids)]
    if not lids:
        ctx.close()
        return 0
    ctx.out.mkdir(parents=True, exist_ok=True)
    own = ctx.out.resolve() == (ctx.root / "results" / ctx.m).resolve()
    rp = ctx.root / "replay" / ctx.m / "sym" / "report.json"
    report = {"document": "sym_replay", "milestone": ctx.m, "binding": ctx.rc.sc.binding, "laws": {}}
    real = None
    races: list = []
    try:
        for lid in lids:
            if ctx.rc.sc.binding and real is None:
                real = run3.Real(ctx.rc, json.loads((ctx.root / ctx.rc.derivation[lid]["facts"]).read_text()))
            rec, rep, rs = Decider(ctx).decide(lid, real)
            races += rs
            ctx.log(f"{lid}: {rec['status']}")
            (ctx.out / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
            if rep is not None and rec["status"] == "REFUTED":
                report["laws"][lid] = rep
        if own:
            cur = json.loads(rp.read_text()) if rp.is_file() else dict(report, laws={})
            for lid in lids:
                cur["laws"].pop(lid, None)
                if lid in report["laws"]:
                    cur["laws"][lid] = report["laws"][lid]
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(dumps(dict(cur, laws=dict(sorted(cur["laws"].items())))), encoding="utf-8")
            write_splits(ctx.m, ctx.root, races)
    finally:
        if real is not None:
            real.close()
        ctx.close()
    return 0
