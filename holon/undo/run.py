"""The UNDO laws of a typed milestone, decided on the typed model (BUILD_PLAN I27; the contract is the docstring of
tests_m3/test_undo.py, "Deciding", "Replay" and "Records").

  python -m holon run --milestone M [--sidecar PATH] [--undo-sidecar PATH] [--laws ID,ID] [--out DIR] [--gen-dir DIR]
  python -m holon replay --milestone M [--sidecar PATH] [--undo-sidecar PATH]

`run` decides every UNDO law of laws/<M> (or those --laws names):
  1. the trace section gen/<M>/undo/models/<model>.bend over the typed model (holon.undo.trace), and the law's
     statement gen/<M>/laws/<id>/LAWS.bend importing both (holon.undo.proofs);
  2. refutation (holon.undo.search, the UNDO sidecar's budget) on the combined module the evaluator runs; with the
     sidecar's binding, the witness's external calls are then answered as the deployment answers them (both runs, the
     one with the pair and the one without it, replayed on the real contract) and its hash tables settled; its
     counter-law gen/<M>/proofs/<id>/witness/PROOF.bend is accepted only when bend2 and BendTT check it (the law file
     then states the counter-law);
  3. without an accepted counter-law, the law's proof generator (a pair without residue: the restore proof; a residue
     or a pair with residues: index-relative noninterference; none for a cancel law, I71); a law it does not decide stays
     UNKNOWN with what was tried (holon.undo.proofs states what each generator needs);
  4. every REFUTED law's two runs replayed on the real contract (the binding's step harness): replay/<M>/undo/
     report.json when the records are the milestone's own;
  5. the record results/<M>/<id>.json (v1 and v2, with the undo field and the nz premises), and
     results/<M>/undo/classification.json (holon.rules.undo.classification).
`replay` re-runs step 4 for the committed records.

Nothing here names a target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from .. import bend
from ..gen.mlaws import law_name
from ..machine_bend import bname
from ..rules import undo as U
from ..sorts import evaluate3 as E3
from ..sorts import run3
from ..sorts import search3 as S3
from ..sorts.model3 import importable, model_name, write_model_file
from . import proofs as UP
from . import search as US
from . import trace as T

ROOT = Path(__file__).resolve().parents[2]
GEN_UNDO = ["holon/undo/run.py", "holon/undo/search.py", "holon/undo/trace.py", "holon/undo/proofs.py",
            "holon/rules/undo.py", "holon/analysis/deadness.py"]


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def generator_sha256(root: Path) -> str:
    from ..records import _holon_imports
    seen, todo = set(), list(GEN_UNDO) + list(run3.GEN3)
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


def undo_laws(derivation: dict) -> list[str]:
    return sorted(lid for lid, e in derivation.items() if e.get("rule") == U.RULE)


# ------------------------------------------------------------------------------------------------ the context
class TraceCtx:
    """One document's trace section: the module Bend checks, and the combined module the evaluator runs."""

    def __init__(self, ctx: "Ctx", doc_rel: str):
        rc = ctx.rc
        self.doc_rel = doc_rel
        self.root = rc.root
        self.ev, self.init, _mf, self.mm, self.docm = rc.model(doc_rel)
        self.model_file = rc.model_path(doc_rel)
        self.text = self.model_file.read_text(encoding="utf-8")
        self.doc = json.loads((rc.root / doc_rel).read_text(encoding="utf-8"))
        self.hashes = self.ev.hashes()
        self.elements = U.elements(U.analyse(self.doc, U.model_of(doc_rel)))
        got = {e["law_id"]: e for e in self.elements}
        for lid in undo_laws(ctx.rc.derivation):
            de = ctx.rc.derivation[lid]
            if de["facts"] != doc_rel:
                continue
            if lid not in got or got[lid]["basis"] != de["basis"]:
                raise RuntimeError(f"{lid}: the document's analysis no longer gives the derived basis (derive again)")
        self.dir = ctx.gen / "undo" / "models"
        name = model_name(doc_rel)
        self.import_file = self.dir / importable(name)
        mt = T.module_text(self.mm, self.text, self.doc, self.hashes, self.elements,
                           os.path.relpath(rc.import_path(doc_rel), self.dir).replace(os.sep, "/"))
        self.path = write_model_file(self.dir, name, mt)          # <model>.bend, a link to the importable file
        self.module_text = mt
        ct = T.combined_text(self.mm, self.text, self.doc, self.hashes, self.elements)
        cd = E3.cache_dir().parent / "undo3" / hashlib.sha256(ct.encode()).hexdigest()[:32]
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

    def factory(self, empty: bool = False, native: bool = True) -> S3.Model:
        i = dict(self.init)
        if empty:
            i["preimages"] = []
        return S3.Model(self.cev, i, self.hints, self.root / self.doc_rel, native=native)

    def close(self):
        self.cev.close()


class Ctx:
    def __init__(self, milestone: str, root: Path, sidecar: str | None, undo_sidecar: str | None, gen: Path | None,
                 out: Path | None, log=print):
        self.rc = run3.Ctx(milestone, root, sidecar, gen, out, log)
        self.m = milestone
        self.root = Path(root)
        self.gen = self.rc.gen
        self.out = self.rc.out
        self.log = log
        self.usc = U.load_sidecar(milestone, self.root, undo_sidecar)
        self.deadline: float | None = None   # holon run --deadline: a wall-clock time box on each search
        self.traces: dict = {}

    def trace(self, doc_rel: str) -> TraceCtx:
        if doc_rel not in self.traces:
            self.traces[doc_rel] = TraceCtx(self, doc_rel)
        return self.traces[doc_rel]

    def sorts_of(self, doc_rel: str) -> dict:
        a = json.loads((self.root / "gen" / self.m / "sorts" / "assignment.json").read_text())
        return a["models"][model_name(doc_rel)]["assignment"]

    def close(self):
        for t in self.traces.values():
            t.close()
        self.rc.close()


# ------------------------------------------------------------------------------------------------ the real side
def obs_of_exec(e) -> dict:
    ok = bool(e.ok)
    return {"status": "ok" if ok else "revert", "ret": str(e.ret).lower(),
            "logs": [{"topics": [str(t).lower() for t in tps], "data": str(d).lower()} for tps, d in e.logs] if ok else [],
            "calls": [{"to": US.norm_to(c[0]), "data": str(c[1]).lower()} for c in e.calls] if ok else []}


def real_runs(real: run3.Real, traces: list) -> list:
    """Each trace (step JSON) on the real contract from the binding's deployment: [(observations, raw calls per step)]
    per trace (the raw calls (to, data, ok, ret) of every step, reverted ones included)."""
    from ..replay_fragments import run_harness
    real.setup()
    runs = run_harness(real.proj, real.tc, real.binding, [real.steps(ws) for ws in traces], [], real.init, tag="undo")
    out = []
    for tr in runs:
        execs = [e for e in tr.execs if e.id != "d"]
        out.append(([obs_of_exec(e) for e in execs],
                    [[{"to": US.norm_to(c[0]), "data": str(c[1]).lower(), "ok": bool(c[2]), "ret": str(c[3]).lower()}
                      for c in e.calls] for e in execs]))
    return out


def with_without(w: dict, subform: str = "pair") -> tuple[list, list]:
    """(the run with x, the run without it) of a witness: prefix + [x, y] + t, and prefix + t (a pair, a residue) or
    prefix + [y] + t (a cancel law, I71: y alone)."""
    pre, t = list(w.get("prefix") or []), list(w.get("t") or [])
    return pre + [w["x"], w["y"]] + t, pre + ([w["y"]] if subform == U.CANCEL_SUBFORM else []) + t


def t_without(pre: int, subform: str) -> int:
    """The index of t's first step in the run without x."""
    return pre + (1 if subform == U.CANCEL_SUBFORM else 0)


# ------------------------------------------------------------------------------------------------ deciding a law
class Decider:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx

    def paths(self, lid: str) -> dict:
        g = self.ctx.gen
        return {"laws": g / "laws" / lid / "LAWS.bend", "proofs": g / "proofs" / lid, "nonvac": g / lid / "nonvac"}

    def imports(self, d: Path, tc: TraceCtx) -> tuple[str, str]:
        return (os.path.relpath(self.ctx.rc.import_path(tc.doc_rel), d).replace(os.sep, "/"),
                os.path.relpath(tc.import_file, d).replace(os.sep, "/"))

    def write_law(self, law: dict, tc: TraceCtx, counter: bool) -> Path:
        p = self.paths(law["law_id"])["laws"]
        p.parent.mkdir(parents=True, exist_ok=True)
        sh = self.ctx.rc.registry["statements"][law["law_id"]]
        mi, ti = self.imports(p.parent, tc)
        p.write_text(UP.law_file(law, sh, mi, ti, tc.hashes, counter=counter), encoding="utf-8")
        return p

    def steps_json(self, tc: TraceCtx, steps: list) -> list:
        fns = run3.fn_names(tc.docm)
        return [run3.step_json(tc.docm, st, fns) for st in steps]

    # ---------------------------------------------------------- search
    def search(self, el: dict, tc: TraceCtx, real=None) -> tuple[dict | None, str]:
        """The model's search; with a real side, a witness counts only when its pair steps succeed on the deployment
        and, its external calls answered as the deployment answers them (repair), the model still finds the law's
        function false at it (else the search goes on; holon.undo.search.UndoSearch says when it stops). The accepted
        witness comes back repaired."""
        accept, kept = None, {}
        if real is not None:
            def accept(w):
                try:
                    w2, res = self.repair(real, tc, w, el["subform"])
                except Exception as e:  # noqa: BLE001: a witness the real side cannot run is no witness
                    return f"the real side cannot run it: {type(e).__name__}: {str(e)[:200]}"
                pre = len(w.get("prefix") or [])
                for i, st in ((pre, w["x"]), (pre + 1, w["y"])):
                    if res[0][0][i]["status"] != "ok":
                        return f"pair:{st.action}"
                if el["subform"] == U.CANCEL_SUBFORM and res[1][0][pre]["status"] != "ok":   # y alone (I71)
                    return f"pair:{w['y'].action}"
                if self.model_value(el, tc, w2) is not False:
                    return "with the deployment's call answers the model finds undo true"
                kept["w"] = w2
                return None
        s = US.UndoSearch(tc.factory, tc.doc, self.ctx.sorts_of(tc.doc_rel), self.ctx.usc.search, log=self.ctx.log,
                          accept=accept, deadline=self.ctx.deadline)
        w, bound = self._search(s, el, tc)
        return (kept.get("w", w) if w is not None else None), bound

    def model_value(self, el: dict, tc: TraceCtx, w: dict):
        """undo_<x> at the witness on the model (its prefix run from Reach's initial state with the steps' own
        answers), or None when a prefix step does not succeed."""
        m = tc.factory()
        g = m.s0()
        for st in w.get("prefix") or []:
            code, g, _c = m.run_step(g, US.fresh_step(st), save=True)
            if code != 0:
                return None
        x = U.ghost_x(el["law_id"])
        r = US.Obs(m).settle({"fn": f"undo_{x}", "args": lambda: [{"$ref": g}] + list(self.args_of(el, w)(m, g))}, None)
        return bool(r["out"])

    def _search(self, s, el: dict, tc: TraceCtx) -> tuple[dict | None, str]:
        if el["subform"] == "pair":
            return s.pair(el)
        if el["subform"] == U.CANCEL_SUBFORM:
            return s.cancel(el)
        pls = {e["basis"]["a"]: e for e in tc.elements
               if e["subform"] == "pair" and e["basis"]["undo"] == el["basis"]["undo"]}
        return s.residue(el, pls)

    def repair(self, real, tc: TraceCtx, w: dict, subform: str = "pair") -> tuple[dict, list]:
        """The witness's steps with every external call answered as the deployment answers it: both runs on the real
        contract, each step's environment the calls its runs made, in order (a step of t runs in both; so does a cancel
        law's y)."""
        wr, wo = with_without(w, subform)
        res = real_runs(real, [self.steps_json(tc, wr), self.steps_json(tc, wo)])
        (_ow, cw), (_oo, co) = res
        pre = len(w.get("prefix") or [])
        tw = t_without(pre, subform)

        def env_of(st, *lists):
            calls = []
            for cs in lists:
                for c in cs:
                    if c not in calls:
                        calls.append(c)
            env = json.loads(json.dumps(st.env))
            env.pop("_unanswered", None)
            env["calls"] = calls
            return S3.Step(st.action, json.loads(json.dumps(st.args)), env)
        out = dict(w)
        out["prefix"] = [env_of(st, cw[i]) for i, st in enumerate(w.get("prefix") or [])]
        out["x"] = env_of(w["x"], cw[pre])
        out["y"] = env_of(w["y"], cw[pre + 1], *([co[pre]] if subform == U.CANCEL_SUBFORM else []))
        out["t"] = [env_of(st, cw[pre + 2 + i], co[tw + i]) for i, st in enumerate(w["t"])]
        return out, res

    def args_of(self, el: dict, w: dict):
        if el["subform"] in ("pair", U.CANCEL_SUBFORM):
            return lambda m, g: [m.act(w["x"]), m.act(w["y"]), [m.act(s) for s in w["t"]]]
        return lambda m, g: [{"$w": "0x%064x" % int(w["k"])}, w["v"], [m.act(s) for s in w["t"]]]

    def emit_counter(self, el: dict, law: dict, tc: TraceCtx, w: dict) -> tuple[Path, dict, str, dict, object]:
        x = U.ghost_x(law["law_id"])
        kh, sh, val, states = US.settle_witness(tc.factory, w["prefix"], f"undo_{x}", self.args_of(el, w))
        m = tc.factory(empty=True, native=False)
        if el["subform"] in ("pair", U.CANCEL_SUBFORM):
            values = {"x": m.act(w["x"]), "y": m.act(w["y"]), "t": [m.act(s) for s in w["t"]]}
        else:
            values = {"k": int(w["k"]), "v": w["v"], "t": [m.act(s) for s in w["t"]]}
        d = self.paths(law["law_id"])["proofs"] / "witness"
        d.mkdir(parents=True, exist_ok=True)
        mi, ti = self.imports(d, tc)
        li = os.path.relpath(self.paths(law["law_id"])["laws"], d).replace(os.sep, "/")
        p = d / "PROOF.bend"
        p.write_text(UP.counter_proof(law, mi, ti, li, tc.hashes, [m.act(s) for s in w["prefix"]], states, values,
                                      {"keccak256": kh, "sha256": sh}, UP.Lit(tc.recs, tc.mine),
                                      f"the witness ({el['subform']}: prefix {len(w['prefix'])} steps, t {len(w['t'])} "
                                      "steps), every premise by computation"), encoding="utf-8")
        checker, verdict = run3.check_file(p)
        return p, checker, verdict, {"keccak256": kh, "sha256": sh}, val

    def witness_json(self, el: dict, tc: TraceCtx, w: dict, tables: dict) -> dict:
        out = {"prefix": self.steps_json(tc, w["prefix"]), "x": self.steps_json(tc, [w["x"]])[0],
               "y": self.steps_json(tc, [w["y"]])[0], "t": self.steps_json(tc, w["t"]),
               "hashes": {h: [["0x" + k[2:], "0x%064x" % v] for k, v in sorted((tables.get(h) or {}).items())]
                          for h in ("keccak256", "sha256")}}
        if el["subform"] == "residue":
            out["k"] = "0x%064x" % int(w["k"])
            out["v"] = [s for _f, s in sorted(((w["v"].get("f") or {}).items()), key=lambda kv: int(kv[0][1:]))]
            out["v"] = [x["$w"] if isinstance(x, dict) else x for x in out["v"]]
        return out

    # ---------------------------------------------------------- proofs
    def prove(self, el: dict) -> dict:
        """The law's proof generator (a pair without residue: the restore proof; a residue or a pair with residues:
        index-relative noninterference; a cancel law: none), as an attempt record. None is generated over the typed M3
        model: see holon.undo.proofs.NO_PROOF for what each needs."""
        if el["subform"] == U.CANCEL_SUBFORM:
            gen = U.CANCEL_SUBFORM
        else:
            gen = "restore" if (el["subform"] == "pair" and not el["basis"]["residues"]) else "noninterference"
        return {"kind": "proof", "generator": gen, "marker": None, "error": UP.NO_PROOF[gen]}

    # ---------------------------------------------------------- the law
    def decide(self, lid: str, real) -> tuple[dict, dict | None]:
        ctx = self.ctx
        e = ctx.rc.derivation[lid]
        law = json.loads((ctx.rc.laws_dir / f"{lid}.json").read_text())
        tc = ctx.trace(e["facts"])
        el = next(x for x in tc.elements if x["law_id"] == lid)
        lp = self.write_law(law, tc, counter=False)
        shutil.rmtree(self.paths(lid)["proofs"], ignore_errors=True)
        shutil.rmtree(self.paths(lid)["nonvac"].parent, ignore_errors=True)
        attempts = []
        t0 = time.time()
        w, bound = self.search(el, tc, real)
        attempts.append({"kind": "refute", "engine": "holon.undo.search", "budget": dict(ctx.usc.search),
                         "bound": bound, "found": w is not None})
        ctx.log(f"{lid}: {'witness' if w else 'no witness'} ({bound}) in {round(time.time() - t0, 1)} s")
        status, prim, wj, rep, diag = "UNKNOWN", None, None, None, None
        if w is not None:
            lp = self.write_law(law, tc, counter=True)
            p, checker, verdict, tables, val = self.emit_counter(el, law, tc, w)
            wj = self.witness_json(el, tc, w, tables)
            ok = checker["marker"] == "ALL PROOFS CHECK" and verdict == "checked"
            attempts.append({"kind": "counter", "checker": checker, "verdict": verdict,
                             "evaluator": "undo is false at the witness" if val is False else
                             "the evaluator finds undo true at the repaired witness (not a witness)"})
            if ok:
                status = "REFUTED"
                prim = {"proof": run3.rel(p, ctx.root), "checker": checker, "verdict": verdict}
            else:
                diag = attempts[-1]["evaluator"]
                shutil.rmtree(self.paths(lid)["proofs"], ignore_errors=True)
                lp = self.write_law(law, tc, counter=False)
        if status != "REFUTED":
            attempts.append(self.prove(el))
        rec = self.record(law, e, el, tc, status, wj if status == "REFUTED" else None, attempts, lp, prim,
                          bound if status == "UNKNOWN" else None, diag, witness_kept=wj)
        if status == "REFUTED" and real is not None:
            rep = replay_entry(self, tc, real, rec["witness"], el["subform"])
            rec["replay"] = {"status": rep["status"], "detail": f"diverges at t[{rep.get('diverges_at')}]; calls_agree "
                                                                 f"{rep['calls_agree']}"}
        elif status == "REFUTED":
            rec["replay"] = {"status": "not_applicable", "detail": "no binding: the milestone has no real side"}
        else:
            rec["replay"] = {"status": "not_applicable", "detail": f"{status}: no witness to replay"}
        return rec, rep

    def record(self, law: dict, e: dict, el: dict, tc: TraceCtx, status: str, witness: dict | None, attempts: list,
               lp: Path, prim: dict | None, bound: str | None, diag: str | None, witness_kept=None) -> dict:
        from .. import records as R
        ctx = self.ctx
        lid = law["law_id"]
        sh = ctx.rc.registry["statements"][lid]
        hb = [b["name"] for b in law["statement"]["binders"] if str(b.get("type", "")).startswith("Fn<")]
        st_text = lp.read_text(encoding="utf-8").replace("U.", "M.")
        cone = R.cone(st_text, tc.combined)
        static = dict(e.get("static") or {})
        kernel = U.kernel_class({"status": status})
        rec = {"law_id": lid, "statement_hash": sh, "facts_sha256": law["facts_sha256"], "status": status,
               "scope": "unbounded", "premises": [f"nz:{h}" for h in hb],
               "kernel": {"name": "bend", "version": run3.bend_version(),
                          "verdict": (prim or {}).get("verdict", "not_run")},
               "artifacts": {"laws": run3.rel(lp, ctx.root), "proof": (prim or {}).get("proof"),
                             "model": run3.rel(tc.path, ctx.root), "law_name": law_name(lid, status == "REFUTED"),
                             "typed_model": run3.rel(ctx.rc.model_path(tc.doc_rel), ctx.root)},
               "checker": (prim or {}).get("checker") or {"exit_code": None, "marker": "not_run"},
               "triage": "finding" if status == "REFUTED" else "none",
               "replay": {"status": "not_run", "detail": ""}, "attempts": attempts, "rule": U.RULE,
               "subform": el["subform"],
               "undo": {"subform": el["subform"], "undo_id": el["undo_id"], "static": static, "kernel": kernel,
                        "agree": static.get("class") == kernel},
               "witness": witness, "bound": bound}
        if status == "REFUTED":
            rec["difference"] = {"lhs": False, "rhs": True}   # undo_<x> at the witness, against true
        if diag:
            rec["diagnosis"] = diag
        if status != "REFUTED" and witness_kept is not None:
            rec["candidate"] = witness_kept
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
                    "non_vacuity": {"status": "counter_witness" if status == "REFUTED" else "unknown",
                                    "law": run3.rel(lp, ctx.root) if status == "REFUTED" else None,
                                    "witness": None, "reachable": None, "degenerate": None,
                                    "parent_statement_hash": sh,
                                    "bound": "the accepted counter-law inhabits the premises" if status == "REFUTED"
                                    else "no proof"},
                    "witness_provenance": {"solidity": "internal_harness"} if status == "REFUTED" else None,
                    "filter_bin": "finding" if status == "REFUTED" else None,
                    **R.evidence_fields(law, {"status": status}, ctx.root)})
        if ctx.m not in ("M0", "M1"):
            # an M2+ record (holon.mpipeline, F-M2-12): model_assumptions are the law's hypothesis premises (§8.5) and
            # the ledger entries meeting the cone stay in ledger_assumptions; the extracted model replaces no ledger
            # stand-in by an oracle parameter, so they are all of them (holon.gen.oracles.ledger_problems)
            from ..gen import oracles as O
            rec["ledger_assumptions"] = sorted(rec["model_assumptions"])
            rec["model_assumptions"] = O.hypothesis_premises(law, None)
        rec["statement"] = law.get("notes", "")
        return rec


# ------------------------------------------------------------------------------------------------ the replay
def replay_entry(dec: Decider, tc: TraceCtx, real, wj: dict, subform: str = "pair") -> dict:
    """holon's replay of one REFUTED witness: both runs on the model (from Reach's initial state, the steps as the
    witness states them) and on the real contract (the binding's deployment), step by step. A cancel law's entry (I71)
    also carries t_at_without, where t starts in the run without x."""
    steps = {k: ([run3.step_of_json(s) for s in wj[k]] if isinstance(wj[k], list) else run3.step_of_json(wj[k]))
             for k in ("prefix", "x", "y", "t")}
    w = {"prefix": steps["prefix"], "x": steps["x"], "y": steps["y"], "t": steps["t"]}
    wr, wo = with_without(w, subform)
    m = tc.factory()
    o = US.Obs(m)
    model = []
    for run in (wr, wo):
        obs, _gs = o.run(m.s0(), [US.fresh_step(s) for s in run])
        model.append([{k: x[k] for k in ("status", "ret", "logs", "calls")} for x in obs])
    jw, jo = with_without(wj, subform)
    res = real_runs(real, [jw, jo])
    (rw, cw), (ro, co) = res
    pre = len(wj.get("prefix") or [])
    t_at, tw = pre + 2, t_without(pre, subform)

    def first_diff(a, b):
        for i in range(len(wj["t"])):
            if a[t_at + i] != b[tw + i]:
                return i
        return None
    dm, dr = first_diff(model[0], model[1]), first_diff(rw, ro)

    def agree(run_json, raw):
        for s, calls in zip(run_json, raw):
            env = s.get("env", {}).get("calls") or []
            want = [{"to": US.norm_to(c["to"]), "data": c["data"].lower(), "ok": bool(c["ok"]), "ret": c["ret"].lower()}
                    for c in env]
            made = {(c["to"], c["data"]) for c in calls}
            mine = [c for c in want if (c["to"], c["data"]) in made]
            if mine != calls:
                return False
        return True
    calls_agree = agree(jw, cw) and agree(jo, co)
    ok = model[0] == rw and model[1] == ro and calls_agree and dm is not None and dm == dr
    out = {"with": {"trace": jw, "model": model[0], "real": rw}, "without": {"trace": jo, "model": model[1], "real": ro},
           "t_at": t_at, "diverges_at": dr if dr is not None else dm, "calls_agree": calls_agree,
           "status": "passed" if ok else "failed"}
    if subform == U.CANCEL_SUBFORM:
        out["t_at_without"] = tw
    return out


# ------------------------------------------------------------------------------------------------ the CLI
def run_main(a, ids: list[str] | None = None) -> int:
    root = ROOT
    gen = Path(a.gen_dir).resolve() if a.gen_dir else None
    out = Path(a.out).resolve() if a.out else None
    ctx = Ctx(a.milestone, root, a.sidecar, a.undo_sidecar, gen, out)
    ctx.deadline = getattr(a, "deadline", None)
    lids = undo_laws(ctx.rc.derivation)
    if ids is not None:
        lids = [x for x in lids if x in set(ids)]
    ctx.out.mkdir(parents=True, exist_ok=True)
    own = ctx.out.resolve() == (ctx.root / "results" / ctx.m).resolve()
    rp = ctx.root / "replay" / ctx.m / "undo" / "report.json"
    report = json.loads(rp.read_text()) if (own and rp.is_file()) else {"document": "undo_replay", "milestone": ctx.m,
                                                                         "binding": ctx.rc.sc.binding, "laws": {}}
    real = None
    try:
        for lid in lids:
            if ctx.rc.sc.binding and real is None:
                real = run3.Real(ctx.rc, json.loads((ctx.root / ctx.rc.derivation[lid]["facts"]).read_text()))
            rec, rep = Decider(ctx).decide(lid, real)
            ctx.log(f"{lid}: {rec['status']}")
            (ctx.out / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
            report["laws"].pop(lid, None)
            if rep is not None:
                report["laws"][lid] = rep
        if own:   # merged into the report as it is now: runs of other laws may have written it meanwhile
            cur = json.loads(rp.read_text()) if rp.is_file() else dict(report, laws={})
            for lid in lids:
                cur["laws"].pop(lid, None)
                if lid in report["laws"]:
                    cur["laws"][lid] = report["laws"][lid]
            report = dict(cur, laws=dict(sorted(cur["laws"].items())))
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(dumps(report), encoding="utf-8")
            c = U.classification(ctx.m, ctx.root)
            cp = ctx.root / "results" / ctx.m / "undo" / "classification.json"
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(dumps(c), encoding="utf-8")
    finally:
        if real is not None:
            real.close()
        ctx.close()
    return 0


def replay_main(a) -> int:
    """holon replay --milestone M: every REFUTED UNDO record's two runs again, into replay/<M>/undo/report.json."""
    root = ROOT
    ctx = Ctx(a.milestone, root, a.sidecar, a.undo_sidecar, None, None)
    report = {"document": "undo_replay", "milestone": ctx.m, "binding": ctx.rc.sc.binding, "laws": {}}
    real = None
    try:
        for lid in undo_laws(ctx.rc.derivation):
            p = ctx.out / f"{lid}.json"
            if not p.is_file():
                continue
            r = json.loads(p.read_text())
            if r.get("status") != "REFUTED" or not ctx.rc.sc.binding:
                continue
            if real is None:
                real = run3.Real(ctx.rc, json.loads((ctx.root / ctx.rc.derivation[lid]["facts"]).read_text()))
            tc = ctx.trace(ctx.rc.derivation[lid]["facts"])
            report["laws"][lid] = replay_entry(Decider(ctx), tc, real, r["witness"],
                                               ctx.rc.derivation[lid].get("subform") or "pair")
        rp = ctx.root / "replay" / ctx.m / "undo" / "report.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(dumps(report), encoding="utf-8")
        bad = [k for k, v in report["laws"].items() if v["status"] != "passed"]
        print(f"holon replay (UNDO): {len(report['laws'])} laws, {len(bad)} failed -> {run3.rel(rp, ctx.root)}")
        return 0 if not bad else 1
    finally:
        if real is not None:
            real.close()
        ctx.close()


def split_argv(argv: list, opt: str = "--undo-sidecar") -> tuple[list, str | None]:
    """argv without opt (run3's parser takes neither --undo-sidecar nor --deadline), and its value."""
    out, val, skip = [], None, False
    for i, x in enumerate(argv):
        if skip:
            skip = False
            continue
        if x == opt:
            val = argv[i + 1] if i + 1 < len(argv) else None
            skip = True
            continue
        if x.startswith(opt + "="):
            val = x.split("=", 1)[1]
            continue
        out.append(x)
    return out, val


def parse_deadline(v: str | None) -> float | None:
    """--deadline: an ISO 8601 UTC time (2026-01-01T12:00:00Z) or epoch seconds; None without one."""
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        from datetime import datetime
        return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()


def main(argv: list) -> int:
    """holon run | replay on a typed milestone: the I30 laws by holon.sorts.run3, the UNDO laws here (an UNDO law needs
    the milestone's UNDO sidecar: spec/<M>/lib/undo.json, or --undo-sidecar for a test milestone)."""
    cmd = argv[0]
    rest, usc = split_argv(argv[1:])
    rest, dl = split_argv(rest, "--deadline")
    ap = argparse.ArgumentParser(prog=f"holon {cmd}")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--sidecar")
    ap.add_argument("--laws")
    ap.add_argument("--out")
    ap.add_argument("--gen-dir")
    a, _unknown = ap.parse_known_args(rest)
    a.undo_sidecar = usc
    a.deadline = parse_deadline(dl)
    root = ROOT
    try:
        dv = json.loads((root / "laws" / a.milestone / "DERIVATION.json").read_text())
        derivation = {x["law_id"]: x for x in dv.get("laws") or []}
    except (OSError, ValueError):
        derivation = {}
    mine = undo_laws(derivation)
    want = [x.strip() for x in (a.laws or "").split(",") if x.strip()] or None
    undo_ids = [x for x in mine if want is None or x in want]
    others = None if want is None else [x for x in want if x not in mine]
    rc = 0
    if cmd == "replay":
        rc = run3.main([cmd] + rest)
        if mine and U.has_sidecar(a.milestone, root, usc):
            rc = max(rc, replay_main(a))
        return rc
    if want is None or others:
        r_argv = list(rest)
        if others is not None:
            r_argv = _with_laws(rest, others)
        rc = run3.main([cmd] + r_argv)
    if undo_ids and U.has_sidecar(a.milestone, root, usc):
        rc = max(rc, run_main(a, undo_ids))
    return rc


def _with_laws(argv: list, ids: list) -> list:
    out, skip = [], False
    for i, x in enumerate(argv):
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
