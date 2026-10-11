"""`holon run` for state-machine milestones (holon-ir/0.2, M1 onward).

Same contract as M0 (holon.pipeline): every frozen law ends PROVED, REFUTED or UNKNOWN,
with a result record; Bend's verdict is final; witnesses come from the compiled model.

For each law, in law_id order:
  1. exists laws: the strategy search proposes a witness; the `evaluate` generator checks it;
  2. forall laws: try the proof generators (holon.gen.mproofs) in order;
  3. otherwise search the compiled model for a witness (holon/js/explore.mjs) and emit a
     counter-law; REFUTED iff Bend accepts it;
  4. otherwise UNKNOWN, with what was tried.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from . import bend, ir
from . import facts as F
from .gen import mlaws, mproofs
from .gen.machine import Machine
from .replay import replay_status, load_report

ROOT = Path(__file__).resolve().parents[1]
EXPLORE = Path(__file__).resolve().parent / "js" / "explore.mjs"
MACHINE_JS = Path(__file__).resolve().parent / "js" / "machine.mjs"


def model_name(facts_path: Path) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_]", "_", Path(facts_path).stem) or "model"


class CompiledMachine:
    def __init__(self, source: Path, artifact: Path, facts: dict, machine: Machine):
        self.source, self.artifact, self.facts, self.m = source, artifact, facts, machine

    @classmethod
    def build(cls, facts_path: Path, cfg: dict | None = None) -> "CompiledMachine":
        facts = F.load(facts_path)
        sha = F.sha256_file(facts_path)
        m = Machine(facts)
        text = m.generate(sha)
        src = ROOT / "build" / "eval" / sha[:16] / f"{model_name(facts_path)}.bend"
        src.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists() or src.read_text() != text:
            src.write_text(text)
        art = src.with_suffix(".mjs")
        stamp = src.with_suffix(".src.sha256")
        h = hashlib.sha256(text.encode()).hexdigest()
        if not (art.exists() and stamp.exists() and stamp.read_text() == h):
            r = bend.run([src.name, "-o", art.name], cwd=src.parent, cfg=cfg)
            if r.code != 0 or not art.exists():
                raise RuntimeError(f"bend failed to compile {src}: {r.out[:2000]}")
            stamp.write_text(h)
        return cls(src, art, facts, m)

    def evaluate(self, law: dict, assignment: dict) -> dict:
        """Premises and claims of a law at one assignment, on the compiled model."""
        p = subprocess.run(["node", str(EXPLORE)], input=json.dumps({"module": str(self.artifact), "facts": self.facts,
                                                                     "law": law, "evaluate": assignment}),
                           capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            raise RuntimeError(f"evaluate failed: {p.stderr[-2000:]}")
        return json.loads(p.stdout)

    def explore(self, law: dict, budget: dict | None = None) -> dict:
        p = subprocess.run(["node", str(EXPLORE)], input=json.dumps({"module": str(self.artifact), "facts": self.facts,
                                                                     "law": law, "budget": budget or {}}),
                           capture_output=True, text=True, timeout=3600)
        if p.returncode != 0:
            raise RuntimeError(f"explore failed: {p.stderr[-2000:]}")
        return json.loads(p.stdout)

    def calls(self, calls: list) -> list:
        p = subprocess.run(["node", str(MACHINE_JS)], input=json.dumps({"module": str(self.artifact), "calls": calls}),
                           capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            raise RuntimeError(p.stderr[-2000:])
        return json.loads(p.stdout)["results"]


def relpath(p: Path) -> str:
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(p)


def _first(out: str, n: int = 14) -> str:
    return "\n".join(out.strip().splitlines()[:n])


def witness_difference(cm: CompiledMachine, law: dict, witness: dict) -> dict | None:
    """The claim's two sides at the witness, evaluated on the compiled model (decoded JSON)."""
    def to_js(t, ty_env):
        # IR term -> machine.mjs expression, with witness values substituted
        if "var" in t:
            n = t["var"]
            return _value_js(cm.m, ty_env[n], witness[n])
        if "nat" in t:
            return {"val": t["nat"]}
        if "bool" in t:
            return {"val": t["bool"]}
        if "nats" in t:
            return {"val": t["nats"]}
        if "s0" in t:
            return {"fn": "s0", "args": []}
        if "run" in t:
            return {"fn": "run", "args": [to_js(t["run"], ty_env), to_js(t["from"], ty_env)]}
        if "step" in t:
            return {"fn": "step", "args": [to_js(t["step"], ty_env), to_js(t["from"], ty_env)]}
        if "obs" in t:
            return {"fn": "obs", "args": [to_js(t["obs"], ty_env), to_js(t["from"], ty_env)]}
        if "trace" in t:
            return {"val": [_act_obj(cm.m, a, ty_env, witness) for a in t["trace"]]}
        if "cat" in t:
            a, b = to_js(t["cat"][0], ty_env), to_js(t["cat"][1], ty_env)
            if "val" not in a or "val" not in b:
                raise ValueError("cat of non-literal traces")
            return {"val": a["val"] + b["val"]}
        if "act" in t:
            return {"val": _act_obj(cm.m, t, ty_env, witness)}
        if "plus" in t:
            x, y = to_js(t["plus"][0], ty_env), to_js(t["plus"][1], ty_env)
            if "val" not in x or "val" not in y:
                raise ValueError("plus of computed terms")
            return {"val": x["val"] + y["val"]}
        if "obsv" in t:
            return {"fn": t["obsv"], "args": [to_js(t["of"], ty_env)]}
        if "mig" in t:
            return {"fn": "mig_" + t["mig"], "args": [to_js(t["of"], ty_env)] + [to_js(a, ty_env) for a in t.get("args", [])]}
        if "fn" in t:
            return {"fn": t["fn"], "args": [to_js(a, ty_env) for a in t["args"]]}
        raise ValueError(t)
    st = law["statement"]
    ty_env = {b["name"]: b["type"] for b in st["binders"]}
    c = st["claim"]
    if "all" in c:
        return None
    try:
        lhs, rhs = cm.calls([to_js(c["eq"][0], ty_env), to_js(c["eq"][1], ty_env)])
    except (ValueError, KeyError, RuntimeError):
        return None
    return {"lhs": lhs, "rhs": rhs}


def _value_js(m: Machine, ty: str, v):
    if ty in ("Nat", "Bool"):
        return {"val": v}
    if ty == "Act":
        return {"val": _act_val(m, v)}
    if ty == "Trace":
        return {"val": [_act_val(m, a) for a in v]}
    if ty == "State":
        if "state" in v:
            return {"val": v["state"]}
        return {"fn": "run", "args": [{"val": [_act_val(m, a) for a in v["run"]]}, {"fn": "s0", "args": []}]}
    raise ValueError(ty)


def _act_val(m: Machine, a: dict) -> dict:
    spec = next(x for x in m.actions if x["name"] == a["op"])
    return {"$": f"A_{a['op']}", **{n: a[n] for n, _ in spec["inputs"]}}


def _act_obj(m, t, ty_env, witness):
    if "var" in t:
        return _act_val(m, witness[t["var"]])
    if "act" in t:
        spec = next(x for x in m.actions if x["name"] == t["act"])
        out = {"$": f"A_{t['act']}"}
        for n, _ in spec["inputs"]:
            x = t["args"][n]
            out[n] = x.get("nat", x.get("bool", x.get("nats", witness.get(x.get("var")))))
        return out
    raise ValueError(t)


def run_m1(milestone: str, facts_path: str | None, out: str | None, gen_dir: str | None, no_registry: bool, log=print) -> dict:
    cfg = bend.config(ROOT)
    laws = ir.load_laws_any(milestone, ROOT)
    reg = ir.load_registry(milestone, ROOT)
    facts_path = Path(facts_path or ROOT / reg["facts"])
    out_dir = Path(out or ROOT / "results" / milestone)
    gen = Path(gen_dir or ROOT / "gen" / milestone)
    facts_sha = F.sha256_file(facts_path)
    if no_registry:
        laws = [ir.rebind_facts(l, facts_sha) for l in laws]
    else:
        from .pipeline import check_registry
        check_registry(laws, milestone, facts_sha)
    kver = bend.version(cfg)
    if kver != cfg["bend"]["pinned_version"]:
        raise RuntimeError(f"bend {kver} is not the pinned {cfg['bend']['pinned_version']}")
    verdict = bend.verdict_enabled(cfg)
    triage = {}
    tp = ROOT / "config" / "triage.json"
    if tp.exists():
        triage = json.loads(tp.read_text()).get(milestone, {})
    report = None if no_registry else load_report(milestone, ROOT)

    cm = CompiledMachine.build(facts_path, cfg)
    name = model_name(facts_path)
    if gen.exists():
        shutil.rmtree(gen)
    model_src = gen / "model" / f"{name}.bend"
    model_src.parent.mkdir(parents=True)
    model_src.write_text(cm.source.read_text())
    imp = f"../model/{name}.bend"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {}
    for law in laws:
        lid = law["law_id"]
        d = gen / lid
        attempts: list = []
        rec = {"law_id": lid, "statement_hash": ir.statement_hash(law), "facts_sha256": facts_sha,
               "rule": law["rule"], "subform": law.get("subform"), "maps_to": law.get("maps_to"),
               "premises": [json.dumps(p["eq"], sort_keys=True) for p in law["statement"].get("assume", [])]
               + ["CF(keccak256, headers): header equality stands for committedBatches equality (facts abstraction)"],
               "kernel": {"name": "bend", "version": kver, "verdict": "not_run"},
               "artifacts": {"laws": None, "proof": None, "model": relpath(model_src), "law_name": None},
               "checker": {"exit_code": None, "marker": "not_run"}, "witness": None, "difference": None,
               "triage": "none", "replay": {"status": "not_run", "detail": "certificates are not replayed; refinement replay corpus in replay/M1"}}
        status, em, r = "UNKNOWN", None, None
        bound = None
        try:
            E = mlaws.Emitter(cm.m)
            em = E.emit(law, imp, note=ir.statement_hash(law))
            exists = any(b["q"] == "exists" for b in law["statement"]["binders"])
            witness = None
            if exists:
                s = cm.explore(law)
                attempts.append({"kind": "strategy-search", "tried": s["tried"], "hit": s["witness"] is not None})
                witness = s["witness"]
                bound = s["bound"]
            for gname, g in mproofs.GENERATORS:
                text = g(em, cm.m, imp, witness) if gname == "evaluate" else g(em, cm.m, imp)
                if text is None:
                    continue
                d.mkdir(parents=True, exist_ok=True)
                (d / "LAWS.bend").write_text(em.text)
                (d / "PROOF.bend").write_text(text)
                rr = bend.check(d / "PROOF.bend", cfg)
                ok = rr.ok and _law_names(em.text) == [em.name] and not bend.escape_hatches(text + em.text)
                attempts.append({"kind": "proof", "generator": gname, "exit_code": rr.code, "marker": rr.marker,
                                 "seconds": rr.seconds, **({} if ok else {"error": _first(rr.out)})})
                if ok:
                    status, r = "PROVED", rr
                    if exists:
                        rec["witness"] = witness
                    break
            if status != "PROVED" and not exists:
                s = cm.explore(law)
                bound = s["bound"]
                attempts.append({"kind": "refute", "engine": "compiled-model trace search", "bound": s["bound"],
                                 "tried": s["tried"], "hit": s["witness"] is not None})
                if s["witness"] is not None:
                    w = s["witness"]
                    em2 = mlaws.Emitter(cm.m).emit(law, imp, counter=True, note=ir.statement_hash(law))
                    env = {n: mlaws.value_literal(cm.m, t, w[n]) for _, n, t in em2.binders}
                    lhs, _, ty = mlaws.Emitter(cm.m).prop(law["statement"]["claim"], env, {n: t for _, n, t in em2.binders})
                    text = mproofs.counter(em2, cm.m, imp, w, lhs, ty)
                    shutil.rmtree(d, ignore_errors=True)
                    d.mkdir(parents=True)
                    (d / "LAWS.bend").write_text(em2.text)
                    (d / "PROOF.bend").write_text(text)
                    rr = bend.check(d / "PROOF.bend", cfg)
                    ok = rr.ok and _law_names(em2.text) == [em2.name] and not bend.escape_hatches(text + em2.text)
                    attempts.append({"kind": "counter-law", "generator": "counter", "exit_code": rr.code, "marker": rr.marker,
                                     "seconds": rr.seconds, **({} if ok else {"error": _first(rr.out)})})
                    if ok:
                        status, r, em = "REFUTED", rr, em2
                        rec["witness"] = w
                        rec["difference"] = witness_difference(cm, law, w)
                        t = triage.get(lid, {})
                        rec["triage"] = t.get("triage", "finding")
                        if t.get("why"):
                            rec["triage_why"] = t["why"]
                        rec["replay"] = replay_status(report, lid, w)
        except mlaws.Unsupported as e:
            attempts.append({"kind": "emit", "error": f"unsupported statement form: {e}"})
        if status == "UNKNOWN":
            shutil.rmtree(d, ignore_errors=True)
            rec["scope"] = "bounded"
            rec["bound"] = bound or "not searched"
        else:
            rec["scope"] = "unbounded"
            rec["artifacts"].update({"laws": relpath(d / "LAWS.bend"), "proof": relpath(d / "PROOF.bend"), "law_name": em.name})
            rec["checker"] = {"exit_code": r.code, "marker": r.marker, "seconds": r.seconds}
            if verdict:
                v = bend.check_verdict(d / "PROOF.bend", cfg)
                rec["kernel"]["verdict"] = "checked" if v.ok else "failed"
                attempts.append({"kind": "verdict", "kernel": "BendTT (Lean-proven)", "exit_code": v.code,
                                 "marker": v.marker, "seconds": v.seconds})
        rec["status"] = status
        rec["attempts"] = attempts
        (out_dir / f"{lid}.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
        summary[lid] = status
        log(f"{lid:22s} {status:8s} {rec['kernel']['verdict']:8s} {rec['triage']}")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def _law_names(text: str) -> list[str]:
    from .pipeline import law_names
    return law_names(text)
