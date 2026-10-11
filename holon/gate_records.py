"""M2 record gates (docs/M2_SPEC.md S9, whitepaper section 9, audit round1 R2).

Wired into `python -m holon gate` for machine milestones (M1, M3_sorts); M0 is
unchanged. Four checks over the v1 result records on disk plus the new gates:

  G6   every REFUTED record has replay evidence whose witness sha256 matches the
       record's witness (holon.replay.replay_status enforces that binding), or
       the record is explicitly 'model-only pending replay'.
  G8   coverage report: each facts action and register and which laws touch it;
       written to results/<m>/coverage_report.json. Fails on drift (a law
       referencing an element that does not exist in its facts file), on a
       modelled action or register no law touches and no debt explains, on
       stale coverage debt, and on malformed spec/M2/coverage files.
  G9   records are complete and consistent: every law has a record, no stale
       records, statement_hash / facts_sha256 recomputed from the frozen law and
       facts files, summary.json agrees, records validate against the frozen v1
       schema, and their v2 conversions validate against
       spec/M2/schemas/result_v2.json.
  G11  premise inhabitance (audit R2): for every PROVED law with assumptions the
       gate exhibits a concrete model point where all premises are true, found
       by searching the compiled model, and requires the law's certificate to be
       non-vacuous (its LAWS.bend states the expected law). A vacuously proved
       law (premises unsatisfiable in the searched bound) fails. For REFUTED
       laws the recorded witness is re-verified: its premises must still hold
       on the compiled model. Inhabitance points are written to
       results/<m>/g11_inhabitance.json and reported in the detail string.

The old 'G11' law-presence/name check stays under the honest name 'G11_names';
'G11' now means inhabitance, matching audit R2.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from . import ir, refute
from . import facts as F
from . import records_v2
from .gen import laws as LG
from .model_eval import CompiledModel, value_in
from .mpipeline import CompiledMachine
from .pipeline import law_names
from .replay import load_report, replay_status, witness_sha256

# Milestones whose gate runs the record checks (M0 keeps the M0 contract).
RECORD_GATE_MILESTONES = ("M1", "M3_sorts")
MODEL_ONLY = "model-only pending replay"
LOG_CHANNEL = "log"  # the observation channel; not a modelled element


def _res(passed: bool, detail: str) -> dict:
    return {"passed": bool(passed), "detail": detail}


# =================================================================== G6
def g6_check(records: dict, report: dict | None) -> dict:
    """Every REFUTED record has bound replay evidence or the model-only label."""
    bad, replayed, pending = [], [], []
    for lid, rec in sorted(records.items()):
        if rec is None or rec.get("status") != "REFUTED":
            continue
        rs = replay_status(report, lid, rec.get("witness"))
        if rs["status"] in ("passed", "failed"):
            # status passed/failed is only returned when the report's
            # witness_sha256[lid] equals sha256 of this record's witness.
            replayed.append(f"{lid}:{rs['status']}")
            continue
        text = " ".join([rs.get("detail") or "", (rec.get("replay") or {}).get("detail") or "",
                         rec.get("triage_why") or ""])
        if MODEL_ONLY in text or (rec.get("replay") or {}).get("status") == "model_only_pending_replay":
            pending.append(lid)
        else:
            bad.append(f"{lid}: replay {rs['status']} ({rs.get('detail', '')[:80]}); "
                       f"no evidence bound to witness sha256 and no model-only label")
    ok = not bad
    if ok:
        n = len(replayed) + len(pending)
        detail = (f"{n} REFUTED records: {len(replayed)} replayed with matching witness sha256"
                  + (f" ({', '.join(replayed)})" if replayed else "")
                  + (f"; {len(pending)} model-only pending replay" if pending else ""))
    else:
        detail = "; ".join(bad)
    return _res(ok, detail)


# =================================================================== G8
def _atoms(e, out=None):
    """Bare atoms and call targets of a facts-DSL expression."""
    out = out if out is not None else set()
    if isinstance(e, str):
        out.add(e)
    elif isinstance(e, list):
        if e and e[0] == "call" and len(e) > 1:
            out.add(("call", e[1]))
            for x in e[2:]:
                _atoms(x, out)
        else:
            for x in e:
                _atoms(x, out)
    elif isinstance(e, dict):
        for v in e.values():
            _atoms(v, out)
    return out


def _machine_coverage(facts: dict, laws: list[dict]) -> tuple[dict, list]:
    """Coverage entry for a machine facts file plus a list of drift problems."""
    regs = {s[0] for s in facts["state"]} | set(facts.get("ghost_state", [])) | set(facts.get("shadow", {}))
    defs = facts.get("defs", {})
    problems = []

    def def_regs(name, seen=()):
        if name in seen or name not in defs:
            return set()
        d = defs[name]
        params = {p[0] for p in d.get("params", [])}
        at = _atoms(d.get("body"))
        out = {a for a in at if isinstance(a, str) and a in regs and a not in params}
        for c in at:
            if isinstance(c, tuple):
                out |= def_regs(c[1], seen + (name,))
        return out

    def expr_regs(e, locals_=()):
        at = _atoms(e)
        out = {a for a in at if isinstance(a, str) and a in regs and a not in locals_}
        for c in at:
            if isinstance(c, tuple):
                out |= def_regs(c[1])
        return out

    act_regs = {}
    for a in facts.get("actions", []):
        inp = {n for n, _ in a.get("inputs", [])}
        lets = {g["let"] for g in a.get("guards", []) if isinstance(g, dict) and "let" in g}
        locals_ = inp | lets
        rr = set((a.get("effects") or {}).keys())
        for g in a.get("guards", []):
            rr |= expr_regs(g, locals_)
        for v in (a.get("effects") or {}).values():
            rr |= expr_regs(v, locals_)
        act_regs[a["name"]] = sorted(rr)
    obs_regs = {name: sorted(expr_regs(o.get("body"), {p[0] for p in o.get("params", [])}))
                for name, o in facts.get("observers", {}).items()}
    mig_regs = {name: sorted(set((m.get("effects") or {}).keys()) |
                             set().union(*[expr_regs(v, {p[0] for p in m.get("inputs", [])})
                                           for v in (m.get("effects") or {}).values()] or [set()]))
                for name, m in facts.get("migrations", {}).items()}
    consumers = {c for c in facts.get("consumers", {})}

    def walk(t, acc):
        if isinstance(t, dict):
            if "act" in t:
                acc["acts"].add(t["act"])
            if "fn" in t:
                fn = t["fn"]
                if fn.startswith("is_") and fn[3:] in act_regs:
                    acc["acts"].add(fn[3:])
                else:
                    acc["fns"].add(fn)
            if "obsv" in t:
                acc["obsv"].add(t["obsv"])
            if "mig" in t:
                acc["mig"].add(t["mig"])
            if "proj" in t:
                acc["regs"] |= set(t["proj"])
            if "call" in t:
                acc["fns"].add(t["call"])
            for v in t.values():
                walk(v, acc)
        elif isinstance(t, list):
            for x in t:
                walk(x, acc)

    actions = {a: {"direct": [], "quantified": [], "registers": act_regs[a]} for a in act_regs}
    registers = {r: {"laws": [], "how": {}} for r in regs}
    for law in laws:
        lid = law["law_id"]
        st = law["statement"]
        acc = {"acts": set(), "fns": set(), "obsv": set(), "mig": set(), "regs": set()}
        walk({"assume": st.get("assume", []), "claim": st.get("claim")}, acc)
        for a in sorted(acc["acts"] - set(act_regs)):
            problems.append(f"{lid}: references unknown action {a}")
        for o in sorted(acc["obsv"] - set(obs_regs)):
            problems.append(f"{lid}: references unknown observer {o}")
        for mg in sorted(acc["mig"] - set(mig_regs)):
            problems.append(f"{lid}: references unknown migration {mg}")
        for fn in sorted(acc["fns"] - {"last_ok", "runs_ok", "no_code", "perm", "cost", "elapsed"} - consumers):
            problems.append(f"{lid}: references unknown model function {fn}")
        for r in sorted(acc["regs"] - regs):
            problems.append(f"{lid}: references unknown register {r}")
        how: dict[str, set] = {}
        rr = set(acc["regs"])
        for r in acc["regs"] & regs:
            how.setdefault(r, set()).add("proj")
        for o in acc["obsv"] & set(obs_regs):
            for r in obs_regs[o]:
                rr.add(r)
                how.setdefault(r, set()).add(f"obsv:{o}")
        for mg in acc["mig"] & set(mig_regs):
            for r in mig_regs[mg]:
                rr.add(r)
                how.setdefault(r, set()).add(f"mig:{mg}")
        for a in acc["acts"] & set(act_regs):
            actions[a]["direct"].append(lid)
            for r in act_regs[a]:
                rr.add(r)
                how.setdefault(r, set()).add(f"action:{a}")
        binders = st.get("binders", [])
        if any(b["type"] in ("Act", "Trace") for b in binders):
            for a in act_regs:
                actions[a]["quantified"].append(lid)
            for a, rs in act_regs.items():
                for r in rs:
                    rr.add(r)
                    how.setdefault(r, set()).add(f"quantified:action:{a}")
        for r in rr & regs:
            registers[r]["laws"].append(lid)
            registers[r]["how"][lid] = sorted(how.get(r, set()))
    for a in actions:
        actions[a]["direct"].sort()
        actions[a]["quantified"].sort()
    for r in registers:
        registers[r]["laws"].sort()
    uncovered = ([f"action {a}" for a, v in actions.items() if not v["direct"] and not v["quantified"]]
                 + [f"register {r}" for r, v in registers.items()
                    if not v["laws"] and r != LOG_CHANNEL])
    return {"kind": "machine", "actions": actions, "registers": registers,
            "uncovered": uncovered}, problems


def _codec_coverage(facts: dict, laws: list[dict]) -> tuple[dict, list]:
    """Coverage entry for an ir/0.1 codec facts file (elements = functions)."""
    fns = facts.get("functions", {})
    problems = []
    touched = {f: [] for f in fns}
    for law in laws:
        lid = law["law_id"]
        st = law["statement"]

        def walk(t):
            if isinstance(t, dict):
                if "call" in t:
                    yield t["call"]
                for v in t.values():
                    yield from walk(v)
            elif isinstance(t, list):
                for x in t:
                    yield from walk(x)
        called = set(walk(st.get("claim"))) | set(walk(st.get("assume", [])))
        for fn in sorted(called):
            if fn in touched:
                touched[fn].append(lid)
            else:
                problems.append(f"{lid}: references unknown codec function {fn}")
    uncovered = [f"function {f}" for f, v in touched.items() if not v]
    return {"kind": "codec", "functions": {f: {"laws": v} for f, v in touched.items()},
            "uncovered": uncovered}, problems


def _debt_files(root: Path) -> tuple[list, list]:
    """Validate spec/M2/coverage/*.json; return (entries, problems)."""
    out, problems = [], []
    cdir = root / "spec" / "M2" / "coverage"
    for p in sorted(cdir.glob("*.json")) if cdir.is_dir() else []:
        rel = p.relative_to(root).as_posix()
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError as e:
            problems.append(f"{rel}: not JSON ({e})")
            continue
        if not isinstance(d.get("frontend"), str) or not isinstance(d.get("target_commit"), str):
            problems.append(f"{rel}: needs string frontend and target_commit")
            continue
        items = d.get("items")
        if not isinstance(items, list) or any(not isinstance(i.get("element"), str)
                                             or not isinstance(i.get("kind"), str)
                                             or not isinstance(i.get("reason"), str) for i in items):
            problems.append(f"{rel}: items must be {{element,kind,reason}} strings")
            continue
        elements = [i["element"] for i in items]
        if elements != sorted(elements):
            problems.append(f"{rel}: items not sorted by element")
        out.append({"file": rel, "frontend": d["frontend"], "target_commit": d["target_commit"],
                    "items": items})
    return out, problems


def _debt_listed(el: str, debt_text: list) -> bool:
    return any(el == d or el in d.split() for d in debt_text)


def _stale_debt(modelled: set, debt_text: list) -> list:
    """Debt claiming to explain an element that IS modelled: the debt is stale."""
    return [f"stale coverage debt: {el!r} is modelled in the facts"
            for el in sorted(modelled) if _debt_listed(el, debt_text)]


def _coverage_holes(uncovered: list, debt_text: list) -> list:
    """Modelled actions/registers no law touches and no debt explains."""
    out = []
    for u in uncovered:
        if ": action " not in u and ": register " not in u:
            continue
        el = u.rsplit(" ", 1)[-1]
        if el == LOG_CHANNEL or _debt_listed(el, debt_text):
            continue
        out.append(f"coverage hole: {u} is touched by no law and not in debt")
    return out


def g8_check(gate) -> dict:
    """Coverage report: each facts action and register and the laws touching it."""
    root, m = gate.root, gate.m
    laws = ir.load_laws_any(m, root)
    report = {"milestone": m, "facts": {}, "coverage_debt": [], "uncovered": []}
    problems = []
    modelled = set()  # action/register names for stale-debt detection
    for fp in sorted({l["facts"] for l in laws}):
        facts = F.load(root / fp)
        fl = [l for l in laws if l["facts"] == fp]
        if "actions" in facts:
            cov, probs = _machine_coverage(facts, fl)
            modelled |= set(cov["actions"])
            modelled |= set(cov["registers"])
        else:
            cov, probs = _codec_coverage(facts, fl)
        problems += probs
        report["facts"][fp] = cov
        report["uncovered"] += [f"{fp}: {u}" for u in cov["uncovered"]]
        report["coverage_debt"] += [{"element": d, "source": fp}
                                    for d in sorted(facts.get("coverage", {}).get("debt", []))]
    debt, dprobs = _debt_files(root)
    problems += dprobs
    report["coverage_debt"] += [{"element": i["element"], "kind": i["kind"], "reason": i["reason"],
                                 "source": e["file"]} for e in debt for i in e["items"]]
    debt_text = [d["element"] for d in report["coverage_debt"]]
    problems += _stale_debt(modelled, debt_text)
    # a modelled action or register (not the log channel) no law touches and no
    # debt explains is a coverage hole the gate must flag; codec functions are
    # reported as context (they are the M0 surface, not M2 actions/registers)
    problems += _coverage_holes(report["uncovered"], debt_text)
    out = gate.results / "coverage_report.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    ok = not problems
    n_act = sum(len(c.get("actions", {})) for c in report["facts"].values())
    n_reg = sum(len(c.get("registers", {})) for c in report["facts"].values())
    detail = (f"coverage of {len(report['facts'])} facts files: {n_act} actions, {n_reg} registers; "
              f"{len(report['uncovered'])} uncovered elements (incl. the log channel); report at {out.relative_to(root)}"
              if ok else "; ".join(problems))
    return _res(ok, detail)


# =================================================================== G9
def g9_check(gate) -> dict:
    """Records complete and consistent with the frozen laws and facts."""
    root, m = gate.root, gate.m
    v1_schema = json.loads((root / "schemas" / "result_record.schema.json").read_text())
    v2_schema = records_v2.load_schema(root)
    laws = {l["law_id"]: l for l in ir.load_laws_any(m, root)}
    recs = gate.records()
    problems = []
    summ_p = gate.results / "summary.json"
    summary = json.loads(summ_p.read_text()) if summ_p.exists() else None
    if summary is None:
        problems.append("summary.json missing")
    # complete: one record per law, no stale records
    for f in sorted(gate.results.glob("L_*.json")) if gate.results.is_dir() else []:
        if f.stem not in laws:
            problems.append(f"stale record {f.name}: no such law")
    for lid, law in sorted(laws.items()):
        rec = recs.get(lid)
        if rec is None:
            problems.append(f"{lid}: no result record")
            continue
        if rec.get("law_id") != lid:
            problems.append(f"{lid}: record law_id is {rec.get('law_id')!r}")
        want = ir.statement_hash(law)
        if rec.get("statement_hash") != want:
            problems.append(f"{lid}: statement_hash {rec.get('statement_hash')} != recomputed {want[:20]}...")
        fsha = F.sha256_file(root / law["facts"])
        if rec.get("facts_sha256") != fsha:
            problems.append(f"{lid}: facts_sha256 does not match {law['facts']}")
        if summary is not None and summary.get(lid) != rec.get("status"):
            problems.append(f"{lid}: status {rec.get('status')} != summary {summary.get(lid)}")
        for p in records_v2.validate(rec, v1_schema):
            problems.append(f"{lid}: v1 invalid: {p}")
        if rec.get("status") in ("PROVED", "REFUTED"):
            for a in ("laws", "proof", "model"):
                ap = (rec.get("artifacts") or {}).get(a)
                if ap is None or not (root / ap).is_file():
                    problems.append(f"{lid}: artifacts.{a} missing on disk ({ap})")
    # every record also converts to a valid v2 record
    try:
        lv = records_v2._lean_version(root)
        for lid, rec in sorted(recs.items()):
            if rec is None:
                continue
            v2 = records_v2.convert(rec, laws[lid], m, root, lv)
            for p in records_v2.validate(v2, v2_schema):
                problems.append(f"{lid}: v2 invalid: {p}")
    except Exception as e:  # noqa: BLE001
        problems.append(f"v2 conversion failed: {e}")
    ok = not problems
    return _res(ok, f"{len(recs)} records complete and consistent (v1 validated, v2 converts)"
                if ok else "; ".join(problems))


# =================================================================== G11
def _evaluate_premises(cm: CompiledMachine, law: dict, w: dict):
    """premises list at a point, or None when the point is not a valid model value
    (the refutation search tolerates ill-typed heuristic candidates; an
    inhabitant must be a real model point, verified by evaluate())."""
    try:
        ev = cm.evaluate(law, w)
    except Exception:  # noqa: BLE001
        return None
    return ev["premises"]


def inhabit_machine(cm: CompiledMachine, law: dict) -> tuple[dict | None, str]:
    """A model point where every premise of `law` holds, from the compiled model.

    Runs the refutation search against a synthetic unsatisfiable claim
    (true == false): the engine returns the first fully-assigned point whose
    premises all hold — a premise inhabitant. The point is then re-verified
    against the *real* law with evaluate(), which recomputes the premises on
    the compiled model. The search's premise-directed State perturbations can
    be ill-typed (a list element of the wrong record shape): when the point
    does not evaluate, we repair by unifying same-type State binders and
    re-verify — a repair only counts if evaluate() says every premise holds.
    """
    synth = copy.deepcopy(law)
    synth["statement"]["claim"] = {"eq": [{"bool": True}, {"bool": False}]}
    s = cm.explore(synth)
    bound = s.get("bound", "")
    w = s.get("witness")
    if w is None:
        return None, bound
    tries = [w]
    states = [b["name"] for b in law["statement"]["binders"] if b["type"] == "State"]
    for a in states:
        for b in states:
            if a != b and a in w and b in w:
                tries.append({**w, b: w[a]})
    for cand in tries:
        prems = _evaluate_premises(cm, law, cand)
        if prems is not None and all(prems):
            return {"point": cand, "premises": prems}, bound
    return None, bound + " (found point failed the premise re-check)"


def _par_premises_hold(model: CompiledModel, facts: dict, law: dict, env: dict):
    """premises list at one codec assignment, on the compiled model; None if undefined."""
    types = LG.binder_types(law)
    assumes = law["statement"].get("assume", [])
    terms = [x for p in assumes for x in p["eq"]]
    try:
        job = {"terms": terms, "env": {v: value_in(types[v], env[v], facts) for v in types}}
        vals, = model.run_jobs([job])
    except Exception:  # noqa: BLE001
        return None
    return [vals[2 * i] == vals[2 * i + 1] for i in range(len(assumes))]


def inhabit_par(model: CompiledModel, facts: dict, law: dict) -> tuple[dict | None, str]:
    """Premise inhabitant for an ir/0.1 codec law, evaluated on the compiled model."""
    pins = LG.collect_pins(law, facts)
    bound = refute.describe_space(law, facts)
    for _, env in refute.candidates(law, facts, pins):
        prems = _par_premises_hold(model, facts, law, env)
        if prems is not None and all(prems):
            return {"point": env, "premises": prems}, bound
    return None, bound


def g11_inhabitance(gate) -> dict:
    """Premise inhabitance (audit R2): PROVED laws must not be vacuous."""
    root, m = gate.root, gate.m
    laws = ir.load_laws_any(m, root)
    recs = gate.records()
    machines, models = {}, {}
    points: dict[str, dict] = {}
    problems, skipped = [], {}
    for law in laws:
        lid = law["law_id"]
        rec = recs.get(lid)
        assume = law["statement"].get("assume") or []
        if rec is None:
            problems.append(f"{lid}: no result record")
            continue
        status = rec.get("status")
        if status == "UNKNOWN":
            skipped[lid] = "UNKNOWN"
            continue
        # inhabitance presupposes a real certificate: the law's LAWS.bend must
        # state the expected law (the G11_names check, per law).
        want = [LG.law_name(lid, counter=status == "REFUTED")]
        laws_p = rec["artifacts"].get("laws")
        laws_f = Path(laws_p) if laws_p else None
        if laws_f is not None and not laws_f.is_absolute():
            laws_f = root / laws_f
        got = law_names(laws_f.read_text()) if laws_f and laws_f.exists() else []
        if got != want:
            problems.append(f"{lid}: no non-vacuous certificate "
                            f"(LAWS.bend states {got or 'nothing'}, expected {want})")
            continue
        if not assume:
            skipped[lid] = "no premises"
            continue
        if law["ir_version"] == "holon-ir/0.2":
            fp = law["facts"]
            if fp not in machines:
                machines[fp] = CompiledMachine.build(root / fp, gate.cfg)
            cm = machines[fp]
            if status == "REFUTED":
                # the recorded witness is already the certificate's inhabitant;
                # re-verify its premises still hold on the compiled model.
                w = rec.get("witness")
                if w is None:
                    problems.append(f"{lid}: REFUTED record has no witness")
                    continue
                repaired = False
                prems = _evaluate_premises(cm, law, w)
                if prems is None:
                    states = [b["name"] for b in law["statement"]["binders"] if b["type"] == "State"]
                    for a in states:
                        for b in states:
                            if a != b and a in w and b in w:
                                cand = {**w, b: w[a]}
                                prems = _evaluate_premises(cm, law, cand)
                                if prems is not None:
                                    w, repaired = cand, True
                                    break
                        if prems is not None:
                            break
                if prems is not None and all(prems):
                    points[lid] = {"point": w, "premises": prems,
                                   "bound": "recorded witness re-verified"
                                            + (" (states unified)" if repaired else "")}
                else:
                    problems.append(f"{lid}: REFUTED witness does not satisfy its premises")
                continue
            try:
                found, bound = inhabit_machine(cm, law)
            except Exception as e:  # noqa: BLE001
                found, bound = None, f"search error: {e}"
        else:
            fp = law["facts"]
            if fp not in models:
                models[fp] = (CompiledModel.build(root / fp, cfg=gate.cfg), F.load(root / fp))
            model, facts = models[fp]
            if status == "REFUTED":
                w = rec.get("witness")
                if w is None:
                    problems.append(f"{lid}: REFUTED record has no witness")
                    continue
                prems = _par_premises_hold(model, facts, law, w)
                if prems is not None and all(prems):
                    points[lid] = {"point": w, "premises": prems,
                                   "bound": "recorded witness re-verified"}
                else:
                    problems.append(f"{lid}: REFUTED witness does not satisfy its premises")
                continue
            try:
                found, bound = inhabit_par(model, facts, law)
            except Exception as e:  # noqa: BLE001
                found, bound = None, f"search error: {e}"
        if found is None:
            problems.append(f"{lid}: vacuous certificate? no model point satisfies all "
                            f"{len(assume)} premises within bound ({bound[:160]})")
        else:
            found["bound"] = bound
            points[lid] = found
    out = gate.results / "g11_inhabitance.json"
    out.write_text(json.dumps({"milestone": m, "points": points, "skipped": skipped,
                               "problems": problems}, indent=2, sort_keys=True) + "\n")
    ok = not problems
    searched = len(points) + len(problems)
    detail = (f"inhabitance: {len(points)}/{searched} premise-bearing laws inhabited; "
              f"{len(skipped)} premise-free/skipped; points in {out.relative_to(root)}"
              if ok else "; ".join(problems))
    return _res(ok, detail)


# =================================================================== driver
def record_gates(gate) -> None:
    """Run the M2 record gates on a Gate instance that has already run g11()."""
    # The existing check verifies law presence and LAWS.bend names (audit R2:
    # that is 'law presence', not inhabitance). Keep it under an honest name.
    gate.checks["G11_names"] = gate.checks.pop("G11")
    for name, fn in (("G6", lambda: g6_check(gate.records(), load_report(gate.m, gate.root))),
                     ("G8", lambda: g8_check(gate)),
                     ("G9", lambda: g9_check(gate)),
                     ("G11", lambda: g11_inhabitance(gate))):
        try:
            gate.checks[name] = fn()
        except Exception as e:  # noqa: BLE001 - a check reports, it never crashes the gate
            gate.checks[name] = _res(False, f"error: {e}")


RECORD_ORDER = ["GENV", "G2", "G1", "G3", "G5", "G6", "G8", "G9", "G11_names", "G11", "G7", "G4"]
