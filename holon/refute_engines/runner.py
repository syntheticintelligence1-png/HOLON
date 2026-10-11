"""Drive the S10 refutation engines over a milestone's laws and emit checked records.

Per law, in law_id order:

  qf_ufbv      encode the claim's negation with `codec` and ask z3. SAT yields a
               concrete witness, which is then checked the normal way — replayed
               through the compiled Bend model (refute.evaluate) and, only when it
               still differs, re-encoded as a counter-law that `bend` (and
               `--verdict` when enabled) must accept. UNSAT is recorded as
               evidence only: PROVED still requires the kernel.
  grammar_fuzz seeded grammar/sort-boundary candidates evaluated on the compiled
               model; a hit goes through the same counter-law path.

Anything the engines cannot express is coverage debt — the law is listed, with
the reason, in spec/M2/coverage/refuter.json. Timeouts give UNKNOWN. No
approximations, and a solver answer alone is never a REFUTED.

    python -m holon.refute_engines run [--milestones M0 M1] [--out DIR] [--gen-dir DIR]
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import z3

from .. import bend, ir, pipeline, refute
from .. import facts as F
from ..gen import laws as LG
from ..gen import model as G
from ..model_eval import CompiledModel, model_name
from . import codec, fuzz

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MILESTONES = ("M0", "M1")
OUT_DIR = ROOT / "spec" / "M2" / "refuter"
GEN_DIR = OUT_DIR / "gen"
COVERAGE = ROOT / "spec" / "M2" / "coverage" / "refuter.json"


def _facts_path(law: dict) -> Path:
    return ROOT / (law.get("facts") or "facts/morph_header.json")


def _expected(law: dict) -> str | None:
    p = ROOT / "results" / law.get("milestone", "") / f"{law['law_id']}.json"
    return json.loads(p.read_text())["status"] if p.exists() else None


def _statement(law: dict) -> str:
    try:
        return ir.render_statement(law)
    except KeyError:                    # ir/0.2 statements have binders, not forall
        return f"{law['law_id']} ({law.get('maps_to', 'machine law')})"


def _checked_counter(law: dict, facts: dict, d: Path, model_import: str, cfg: dict,
                     witness: dict, attempts: list, engine: str) -> tuple:
    """replay-independent acceptance: emit the counter-law, bend check, --verdict."""
    em, r = pipeline.check_counter(law, facts, d, model_import, cfg, witness, attempts)
    if r is None:
        return None
    verdict = "not_run"
    if bend.verdict_enabled(cfg):
        v = bend.check_verdict(d / "PROOF.bend", cfg)
        verdict = "checked" if v.ok else "failed"
        attempts.append({"kind": "verdict", "kernel": "BendTT (Lean-proven)", "engine": engine,
                         "exit_code": v.code, "marker": v.marker, "seconds": v.seconds})
    return {"law_name": em.name, "laws": pipeline.relpath(d / "LAWS.bend"),
            "proof": pipeline.relpath(d / "PROOF.bend"), "exit_code": r.code,
            "marker": r.marker, "verdict": verdict}


def run_law(law: dict, facts: dict, facts_path: Path, model: CompiledModel, model_import: str,
            cfg: dict, out_dir: Path, gen: Path, log=print) -> dict:
    lid = law["law_id"]
    attempts: list = []
    engines = {}
    status, witness, difference = "UNKNOWN", None, None
    debt = []

    # ------------------------------------------------ engine 1: QF_UFBV (z3)
    qf = {"solver": codec.solver_info()}
    try:
        q = codec.encode(law, facts)
    except LG.Unsupported as e:
        qf.update({"answer": "unsupported", "reason": str(e)})
        debt.append({"element": f"{law.get('milestone', '?')}:{lid}", "kind": "law",
                     "reason": f"qf_ufbv: {e}"})
    else:
        t0 = time.monotonic()
        ans = q.solver.check()
        qf["seconds"] = round(time.monotonic() - t0, 3)
        qf["len_bound"] = q.cap
        if ans == z3.unsat:
            # evidence only — never a proof (M2_SPEC S10)
            qf.update({"answer": "unsat", "note": "UNSAT is evidence, not a proof"})
        elif ans == z3.unknown:
            qf.update({"answer": "unknown", "reason": q.solver.reason_unknown()})
        else:
            w = codec.extract(q.solver.model(), q, facts)
            qf["answer"] = "sat"
            qf["model_witness"] = w
            # checked the normal way: replayed through the compiled Bend model
            ev = refute.evaluate(law, facts, model, w)
            if ev is None:
                qf["replay"] = "undefined"
                qf["note"] = "solver witness leaves a subterm undefined: not a witness"
            elif ev[0] == ev[1]:
                qf["replay"] = "agree"
                qf["note"] = "solver model disagrees with the compiled model: not a witness"
            else:
                qf["replay"] = "differ"
                d = gen / lid / ENGINE_DIRS["qf_ufbv"]
                c = _checked_counter(law, facts, d, model_import, cfg, w, attempts, "qf_ufbv")
                qf["counter_law"] = c
                if c is not None:
                    status, witness, difference = "REFUTED", w, {"lhs": ev[0], "rhs": ev[1]}
    engines["qf_ufbv"] = qf

    # ------------------------------------------------ engine 2: grammar/sort fuzzing
    fz = {"seed": fuzz.SEED}
    try:
        s = fuzz.search(law, facts, model)
    except LG.Unsupported as e:
        fz.update({"answer": "unsupported", "reason": str(e)})
        debt.append({"element": f"{law.get('milestone', '?')}:{lid}", "kind": "law",
                     "reason": f"grammar_fuzz: {e}"})
    else:
        fz.update({"bound": s.bound, "tried": s.tried, "undefined": s.undefined,
                   "hit": s.witness is not None, "notes": s.notes})
        if s.witness is not None:
            d = gen / lid / ENGINE_DIRS["grammar_fuzz"]
            c = _checked_counter(law, facts, d, model_import, cfg, s.witness, attempts, "grammar_fuzz")
            fz["counter_law"] = c
            if c is not None and status != "REFUTED":
                status, witness, difference = "REFUTED", s.witness, s.difference
    engines["grammar_fuzz"] = fz

    if status != "REFUTED":
        if engines["qf_ufbv"].get("answer") == "unsat" and \
                engines["grammar_fuzz"].get("hit") is False:
            status = "UNSAT_EVIDENCE"
        elif debt:
            status = "COVERAGE_DEBT"
        else:
            status = "NO_WITNESS"

    exp = _expected(law)
    rec = {"law_id": lid, "milestone": law.get("milestone", "M0"),
           "statement_hash": ir.statement_hash(law), "facts_sha256": F.sha256_file(facts_path),
           "statement": ir.render_statement(law), "expected_status": exp,
           "agreement": agreement(status, exp), "status": status,
           "engines": engines, "witness": witness, "difference": difference,
           "attempts": attempts}
    (out_dir / f"{lid}.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    log(f"{lid:24s} {status:15s} qf_ufbv={qf.get('answer')} fuzz={fz.get('hit')}")
    return {"record": rec, "debt": debt}


def agreement(status: str, expected: str | None) -> str:
    if expected == "REFUTED":
        return "refound" if status == "REFUTED" else "missed"
    if expected == "PROVED":
        return "held" if status != "REFUTED" else "false_rebuttal"
    return "unpredicted"


ENGINE_DIRS = {"qf_ufbv": "qf_ufbv", "grammar_fuzz": "grammar_fuzz"}


def run(milestones=DEFAULT_MILESTONES, out: Path | None = None, gen_dir: Path | None = None,
        log=print) -> dict:
    cfg = bend.config(ROOT)
    kver = bend.version(cfg)
    if kver != cfg["bend"]["pinned_version"]:
        raise RuntimeError(f"bend {kver} is not the pinned {cfg['bend']['pinned_version']}")
    out_dir = Path(out or OUT_DIR)
    gen_root = Path(gen_dir or GEN_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    debt, summary = [], {}
    models: dict[Path, tuple] = {}
    for milestone in milestones:
        gen = gen_root / milestone
        for law in ir.load_laws_any(milestone, ROOT):
            lid = law["law_id"]
            if law["ir_version"] != "holon-ir/0.1":
                rec = {"law_id": lid, "milestone": milestone,
                       "statement": _statement(law),
                       "expected_status": _expected(law),
                       "status": "COVERAGE_DEBT",
                       "engines": {"qf_ufbv": {"solver": codec.solver_info(), "answer": "unsupported",
                                             "reason": "holon-ir/0.2 machine law: Trace/Act/Nat binders "
                                                       "and coinductive claims are outside the codec "
                                                       "QF_UFBV fragment"},
                                   "grammar_fuzz": {"seed": fuzz.SEED, "answer": "unsupported",
                                                    "reason": "holon-ir/0.2 machine law: no Header/Bytes "
                                                              "binder grammar applies"}},
                       "agreement": agreement("COVERAGE_DEBT", _expected(law)),
                       "witness": None, "difference": None, "attempts": []}
                (out_dir / f"{lid}.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
                debt.append({"element": f"{milestone}:{lid}", "kind": "law",
                             "reason": "holon-ir/0.2 machine law: Trace/Act/Nat binders and "
                                       "coinductive claims are outside the codec QF_UFBV fragment"})
                summary[lid] = rec["status"]
                log(f"{lid:24s} COVERAGE_DEBT    ir/0.2")
                continue
            facts_path = _facts_path(law)
            if facts_path not in models:
                facts = F.load(facts_path)
                sha = F.sha256_file(facts_path)
                name = model_name(facts_path)
                mdir = gen_root / milestone / "model"
                mdir.mkdir(parents=True, exist_ok=True)
                (mdir / f"{name}.bend").write_text(G.generate(facts, sha))
                models[facts_path] = (facts, CompiledModel.build(facts_path, cfg=cfg), name)
            facts, model, name = models[facts_path]
            model_import = f"../../model/{name}.bend"  # artifacts live at <M>/<lid>/<engine>/
            r = run_law(law, facts, facts_path, model, model_import, cfg, out_dir,
                        gen_root / milestone, log)
            summary[lid] = r["record"]["status"]
            debt.extend(r["debt"])

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    cov = {"frontend": "refuter", "target_commit": _target_commit(), "items": sorted(
        debt, key=lambda i: i["element"])}
    COVERAGE.parent.mkdir(parents=True, exist_ok=True)
    COVERAGE.write_text(json.dumps(cov, indent=1, sort_keys=False) + "\n")
    log(f"coverage debt: {len(debt)} item(s) -> {pipeline.relpath(COVERAGE)}")
    return summary


def _target_commit() -> str:
    for p in [ROOT / "facts" / "morph_header.json"]:
        return F.load(p).get("target", {}).get("commit", "")
    return ""


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m holon.refute_engines")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run", help="run the S10 engines over a milestone's laws")
    p.add_argument("--milestones", nargs="+", default=list(DEFAULT_MILESTONES))
    p.add_argument("--out", default=None)
    p.add_argument("--gen-dir", default=None)
    p2 = sub.add_parser("canary", help="run the fake-SAT mutation canaries")
    p2.add_argument("--milestone", default="M0")
    args = ap.parse_args(argv)
    if args.cmd == "run":
        run(tuple(args.milestones), args.out and Path(args.out),
            args.gen_dir and Path(args.gen_dir))
        return 0
    if args.cmd == "canary":
        from . import canary
        out = canary.run(milestone=args.milestone)
        print(json.dumps({"uncaught": out["uncaught"], "ok": out["ok"]}, indent=2, sort_keys=True))
        return 0 if out["ok"] else 1
    return 0
