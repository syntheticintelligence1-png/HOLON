"""`holon run` for state-machine milestones (holon-ir/0.2 and 0.3, M1 onward).

Same contract as M0 (holon.pipeline): every frozen law ends PROVED, REFUTED or UNKNOWN,
with a result record; Bend's verdict is final; witnesses come from the compiled model.

For each law, in law_id order:
  1. exists laws: the strategy search proposes a witness; the `evaluate` generator checks it;
  2. forall laws: try the proof generators (holon.gen.mproofs) in order;
  3. otherwise search the compiled model for a witness (holon/js/explore.mjs) and emit a
     counter-law; REFUTED iff Bend accepts it;
  4. otherwise UNKNOWN, with what was tried.

holon-ir/0.3 (I7): a law whose premises the IR rejects (holon.ir.check_premises, e.g. global
injectivity) is not run; the counter-law of a conjunction names the conjunct that fails at the
witness (evaluated on the compiled model), recorded as failing_conjunct; an existential law is
never REFUTED: when no witness is found it stays UNKNOWN with bounded_negative {H, space} and its
generated negation (holon.gen.mlaws.negation_ir) is decided by the same proof generators.

Hashes and oracles as parameters (I12; M2+ milestones): the model of a facts file with an oracle sidecar
(holon.gen.oracles) takes its hashes and oracles as parameters (oracle tables). A law whose hyp premises do
not resolve against the sidecar is not run. Its statement hash covers the hypotheses it names
(holon.gen.refs.law_hash(.., oracles=)); a law over the parameters alone is tried by param_premise
(mproofs) after the other classes; the refuter's candidates for a parameter are the sidecar's concrete
instances, then the empty table, and a counter-law supplies the table its witness denotes at the points
the statement queries, carrying the law's hypothesis premises as `exs hN` lines; model_assumptions is
exactly the set of hypothesis premises (§8.5); and the run writes <out>/splits.json (holon-splits/0.1:
hypothesis splits are law pairs, found from statements).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from . import bend, bindings, inhabit, ir, records
from . import facts as F
from .gen import mlaws, mproofs
from .gen import oracles as O
from .gen import refs as R
from .gen import targetlib
from .gen.machine import Machine
from .replay import replay_status, load_report

ROOT = Path(__file__).resolve().parents[1]
EXPLORE = Path(__file__).resolve().parent / "js" / "explore.mjs"
MACHINE_JS = Path(__file__).resolve().parent / "js" / "machine.mjs"
HOUDINI = Path(__file__).resolve().parent / "js" / "houdini.mjs"


def model_name(facts_path: Path) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_]", "_", Path(facts_path).stem) or "model"


class CompiledMachine:
    def __init__(self, source: Path, artifact: Path, facts: dict, machine: Machine, facts_path: Path | None = None,
                 cfg: dict | None = None):
        self.source, self.artifact, self.facts, self.m = source, artifact, facts, machine
        self.facts_path = Path(facts_path) if facts_path else None
        self.oracles = machine.orc
        self.cfg = cfg
        self._inst = None

    def hints(self) -> str | None:
        """The facts' untrusted search-hints module (holon.gen.targetlib), or None for the generic policy."""
        h = targetlib.hints_for(self.facts_path)
        return str(h) if h else None

    @classmethod
    def build(cls, facts_path: Path, cfg: dict | None = None, reach: bool = False,
              anchor: Path | None = None, oracles=None) -> "CompiledMachine":
        """reach: emit the Reach predicate (M2+ milestones, I8). anchor: the facts file whose target
        libraries and search hints apply (holon.gen.targetlib), when facts_path stands in for it (a
        `--facts` override such as a mutated copy); by default facts_path itself. oracles: the facts'
        oracle sidecar (M2+ milestones, I12)."""
        facts = F.load(facts_path)
        sha = F.sha256_file(facts_path)
        m = Machine(facts, anchor or facts_path, oracles=oracles)
        text = m.generate(sha, reach)
        tag = ("-reach" if reach else "") + (f"-orc{hashlib.sha256(text.encode()).hexdigest()[:8]}" if oracles else "")
        src = bend.build_dir(ROOT) / "eval" / (sha[:16] + tag) / f"{model_name(facts_path)}.bend"
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
        return cls(src, art, facts, m, Path(anchor or facts_path), cfg)

    # ------------------------------------------------------------ oracle parameters (I12)
    def instance_module(self) -> tuple[Path | None, list[dict], list[str]]:
        """(compiled module, [{id, param, fn}], notes): the model plus one inst_<entry> def per sidecar instance,
        compiled for the refuter (untrusted search: an instance that does not compile is not tried)."""
        if self._inst is not None:
            return self._inst
        orc = self.m.orc
        items = [(e, O.inst_name(e["id"])) for e in (orc.entries if orc else [])
                 if e in orc.instances(e["parameter"]["name"])]
        model_text = self.source.read_text()

        def compiled(sel):
            text = model_text + "\n" + "\n".join(mlaws.instance_def(self.m, e, n, qualified=False) for e, n in sel)
            h = hashlib.sha256(text.encode()).hexdigest()
            src = self.source.parent / f"{self.source.stem}.inst-{h[:12]}.bend"
            art = src.with_suffix(".mjs")
            if not art.exists():
                src.write_text(text)
                r = bend.run([src.name, "-o", art.name], cwd=src.parent, cfg=self.cfg)
                if r.code != 0 or not art.exists():
                    return None
            return art
        notes: list[str] = []
        art = compiled(items) if items else None
        if items and art is None:
            good = [x for x in items if compiled([x]) is not None]
            notes = [f"the instance of {e['id']} does not compile with the model: not tried" for e, n in items if (e, n) not in good]
            items = good
            art = compiled(items) if items else None
        self._inst = (art, [{"id": e["id"], "param": e["parameter"]["name"], "fn": n} for e, n in items], notes)
        return self._inst

    def oracle_req(self) -> dict | None:
        """What the refuter needs to know of the oracle parameters (holon/js/explore.mjs)."""
        if not self.m.oparams:
            return None
        art, insts, _ = self.instance_module()
        return {"params": {p: {"type": f"Fn<{a},{b}>", "dom": a, "cod": b} for p, (a, b) in self.m.oparams.items()},
                "threaded": list(self.m.threaded), "fnTabs": self.m.fn_tabs, "instances": insts,
                "instModule": str(art) if art else None}

    def _req(self, law: dict, **kw) -> str:
        """An explore.mjs request; hyp premises go as their predicates (the refuter evaluates premises)."""
        if O.hyp_names(law):
            law = O.expand_hyps(law, self.m.orc)
        r = {"module": str(self.artifact), "facts": self.facts, "hints": self.hints(), "law": law, **kw}
        orc = self.oracle_req()
        if orc is not None:
            r["oracles"] = orc
        return json.dumps(r)

    def evaluate(self, law: dict, assignment: dict) -> dict:
        """Premises and claims of a law at one assignment, on the compiled model."""
        p = subprocess.run(["node", str(EXPLORE)], input=self._req(law, evaluate=assignment),
                           capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            raise RuntimeError(f"evaluate failed: {p.stderr[-2000:]}")
        return json.loads(p.stdout)

    def explore(self, law: dict, budget: dict | None = None) -> dict:
        p = subprocess.run(["node", str(EXPLORE)], input=self._req(law, budget=budget or {}),
                           capture_output=True, text=True, timeout=3600)
        if p.returncode != 0:
            raise RuntimeError(f"explore failed: {p.stderr[-2000:]}")
        return json.loads(p.stdout)

    def houdini(self, budget: dict | None = None) -> dict:
        """Strengthening proposals (holon/js/houdini.mjs; untrusted)."""
        p = subprocess.run(["node", str(HOUDINI)], input=json.dumps({"module": str(self.artifact), "facts": self.facts,
                                                                      "hints": self.hints(), "budget": budget or {}}),
                           capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            raise RuntimeError(f"houdini failed: {p.stderr[-2000:]}")
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


def witness_difference(cm: CompiledMachine, law: dict, witness: dict, conjunct: int | None = None) -> dict | None:
    """The claim's two sides at the witness (of conjunct `conjunct` of a conjunction), evaluated on the
    compiled model (decoded JSON)."""
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
    if any(n in cm.m.oparams and t.startswith("Fn<") for n, t in ty_env.items()):   # oracle parameters (I12)
        try:
            sides = (cm.evaluate(law, witness).get("sides") or [])
        except RuntimeError:
            return None
        i = conjunct or 0
        return {"lhs": sides[i][0], "rhs": sides[i][1]} if i < len(sides) and sides[i] else None
    c = st["claim"]
    if "all" in c:
        if conjunct is None:
            return None
        c = c["all"][conjunct]
    if set(c) != {"eq"}:
        return None
    try:
        lhs, rhs = cm.calls([to_js(c["eq"][0], ty_env), to_js(c["eq"][1], ty_env)])
    except (ValueError, KeyError, RuntimeError):
        return None
    return {"lhs": lhs, "rhs": rhs}


def _value_js(m: Machine, ty: str, v):
    if ty == "Reach":
        ty = "State"
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


def m2plus(milestone: str) -> bool:
    """Milestones after M1 (M2.., and the test milestones T*) use the core library and Reach (I8)."""
    return milestone not in ("M0", "M1")


# ---------------------------------------------------------------- I10: prover separation (whitepaper L14)
LEGACY_LAYOUT = ("M0", "M1")   # their gen/ trees are pinned byte for byte (tests_m2/test_target_agnostic.py)


def layout(milestone: str, gen: Path, lid: str) -> tuple[Path, Path, str]:
    """(laws dir, proofs dir, path from either dir up to gen/) of a law's LAWS.bend and PROOF.bend.

    M0 and M1 keep their layout: both files in gen/<law>/. Every other milestone separates the statement
    from its prover: gen/laws/<law>/LAWS.bend and gen/proofs/<law>/PROOF.bend, the proof importing the law
    by relative path (separated_proof), so G3 rejects any `law` declared under proofs/
    (holon.gate.laws_in_proofs). A law's inhabitant (gen/<law>/nonvac/) and the negation of an existential
    law (gen/<law>/neg/) are generated statements with their proofs, regenerated by G11V and G1; they stay in
    gen/<law>/ for every milestone."""
    if milestone in LEGACY_LAYOUT:
        return gen / lid, gen / lid, "../"
    return gen / "laws" / lid, gen / "proofs" / lid, "../../"


def separated_proof(text: str, laws_dir: Path, proofs_dir: Path) -> str:
    """A generated PROOF.bend that imports its LAWS.bend from the laws side (unchanged when both share a dir)."""
    if laws_dir == proofs_dir:
        return text
    rel = Path(os.path.relpath(laws_dir / "LAWS.bend", proofs_dir)).as_posix()
    return text.replace("import ./LAWS.bend as Laws", f"import {rel} as Laws", 1)


def write_pair(laws_dir: Path, proofs_dir: Path, laws_text: str, proof_text: str) -> Path:
    """Write a law and its proof where layout() puts them; returns the PROOF.bend path."""
    for x in (laws_dir, proofs_dir):
        x.mkdir(parents=True, exist_ok=True)
    (laws_dir / "LAWS.bend").write_text(laws_text)
    (proofs_dir / "PROOF.bend").write_text(separated_proof(proof_text, laws_dir, proofs_dir))
    return proofs_dir / "PROOF.bend"


def run_m1(milestone: str, facts_path: str | None, out: str | None, gen_dir: str | None, no_registry: bool, log=print,
           core: str = "import") -> dict:
    cfg = bend.config(ROOT)
    laws = ir.load_laws_any(milestone, ROOT)
    reg = ir.load_registry(milestone, ROOT)
    primary = reg["facts"]
    override = Path(facts_path) if facts_path else None
    out_dir = Path(out or ROOT / "results" / milestone)
    gen = Path(gen_dir or ROOT / "gen" / milestone)

    def fpath_of(law: dict) -> Path:
        return override if (override and law["facts"] == primary) else ROOT / law["facts"]
    if no_registry:
        laws = [ir.rebind_facts(l, F.sha256_file(fpath_of(l))) for l in laws]
    else:
        check_registry_multi(laws, reg, milestone)
    kver = bend.version(cfg)
    if kver != cfg["bend"]["pinned_version"]:
        raise RuntimeError(f"bend {kver} is not the pinned {cfg['bend']['pinned_version']}")
    verdict = bend.verdict_enabled(cfg)
    triage = {}
    tp = ROOT / "config" / "triage.json"
    if tp.exists():
        triage = json.loads(tp.read_text()).get(milestone, {})
    report = None if no_registry else load_report(milestone, ROOT)

    if gen.exists():
        shutil.rmtree(gen)
    (gen / "model").mkdir(parents=True)
    machines: dict = {}
    oracles_of: dict = {}   # law id -> the oracle sidecar of its facts (M2+, I12), for splits.json
    from .gen import core as C
    mproofs.CORE_MODE, mproofs.CORE_PASTE = None, ""
    if m2plus(milestone):
        mproofs.CORE_MODE = core
        if core == "import":
            C.emit(gen, cfg=cfg)
        else:
            mproofs.CORE_PASTE = C.paste_text(gen, cfg)
            shutil.rmtree(gen / "core", ignore_errors=True)

    def machine_for(law: dict):
        fp = fpath_of(law)
        if fp not in machines:
            # a --facts override stands in for the registry's facts: it takes their target libraries and
            # search hints (I6 put them next to the facts; a mutated copy elsewhere would otherwise lose them)
            anchor = ROOT / primary if (override and fp == override) else None
            orc = O.Oracles.for_facts(anchor or fp) if m2plus(milestone) else None   # M0, M1 never read one (I12)
            cm_ = CompiledMachine.build(fp, cfg, reach=m2plus(milestone), anchor=anchor, oracles=orc)
            src = gen / "model" / f"{model_name(fp)}.bend"
            src.write_text(cm_.source.read_text())
            (gen / "model" / f"{model_name(fp)}.defs.json").write_text(bindings.dump(bindings.defs_index(src, cfg)))
            machines[fp] = (cm_, src, f"../model/{model_name(fp)}.bend", F.sha256_file(fp))
        return machines[fp]
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {}
    kbound = {"milestone": milestone, "laws": {}}
    for law in laws:
        lid = law["law_id"]
        cm, model_src, imp0, facts_sha = machine_for(law)
        d = gen / lid
        ld, pd, up = layout(milestone, gen, lid)   # I10: d for M0 and M1
        imp = f"{up}model/{model_src.name}"         # the model, from ld and pd (imp0 from d)
        attempts: list = []
        oracles_of[lid] = cm.oracles
        shash = R.law_hash(law, cm.facts, oracles=cm.oracles)
        rec = {"law_id": lid, "statement_hash": shash, "facts_sha256": facts_sha,
               "rule": law["rule"], "subform": law.get("subform"), "maps_to": law.get("maps_to"),
               "statement": ir.render_statement(law), "premises": ir.premises(law),
               "kernel": {"name": "bend", "version": kver, "verdict": "not_run"},
               "artifacts": {"laws": None, "proof": None, "model": relpath(model_src), "law_name": None},
               "checker": {"exit_code": None, "marker": "not_run"}, "witness": None, "difference": None,
               "triage": "none", "replay": {"status": "not_run", "detail": "certificates are not replayed; refinement replay corpus in replay/M1"}}
        status, em, r = "UNKNOWN", None, None
        bound = None
        stmt_text = records.ir_roots_text(law)
        try:
            ir.check_premises(law)
            if m2plus(milestone):
                O.check_law(law, cm.oracles)
            E = mlaws.Emitter(cm.m)
            em = E.emit(law, imp, note=shash)
            stmt_text = em.text
            exists = any(b["q"] == "exists" for b in law["statement"]["binders"])
            witness = None
            witness_raw = None
            if exists:
                s = cm.explore(law)
                attempts.append({"kind": "strategy-search", "tried": s["tried"], "hit": s["witness"] is not None})
                witness = witness_raw = s["witness"]
                bound = s["bound"]
                if witness is not None:   # oracle parameters (I12): the tables the witness denotes, as in counter-laws
                    witness = mlaws.resolve_witness(cm.m, em.binders, witness,
                                                    {p_: [k for k, _ in es] for p_, es in (s.get("tables") or {}).items()})
            for gname, g in mproofs.GENERATORS:
                text = g(em, cm.m, imp, witness) if gname == "evaluate" else g(em, cm.m, imp)
                if text is None:
                    continue
                rr = bend.check(write_pair(ld, pd, em.text, text), cfg)
                ok = rr.ok and _law_names(em.text) == [em.name] and not bend.escape_hatches(text + em.text)
                attempts.append({"kind": "proof", "generator": gname, "exit_code": rr.code, "marker": rr.marker,
                                 "seconds": rr.seconds, **({} if ok else {"error": _first(rr.out)})})
                if ok:
                    status, r = "PROVED", rr
                    if exists:
                        rec["witness"] = witness_raw
                    break
            if status != "PROVED" and not exists:
                got = param_search(em, cm, imp, ld, pd, cfg, attempts)
                if got is not None:
                    status, r = "PROVED", got
            if status != "PROVED" and not exists and any(b["type"] == "Reach" for b in law["statement"]["binders"]):
                got = reach_search(em, cm, imp, ld, pd, cfg, attempts)
                if got is not None:
                    status, r = "PROVED", got
            if status != "PROVED" and exists:
                # never REFUTED: a bounded negative search, and the generated negation decided instead
                rec["bounded_negative"] = {"H": bound, "space": attempts[0]["tried"] if attempts else 0}
                rec["negation"] = decide_negation(law, cm, imp0, d / "neg", cfg)
                attempts.append({"kind": "negation", "law_id": rec["negation"]["law_id"], "status": rec["negation"]["status"]})
            if status != "PROVED" and not exists:
                s = cm.explore(law)
                bound = s["bound"]
                attempts.append({"kind": "refute", "engine": "compiled-model trace search", "bound": s["bound"],
                                 "tried": s["tried"], "hit": s["witness"] is not None})
                if s["witness"] is not None:
                    w = s["witness"]
                    conj = failing_conjunct(cm, law, w)
                    em2 = mlaws.Emitter(cm.m).emit(law, imp, counter=True, note=shash, conjunct=conj)
                    # oracle parameters (I12): the tables the witness denotes, at the points the statement queries
                    wr = mlaws.resolve_witness(cm.m, em2.binders, w, {p_: [k for k, _ in es]
                                                                     for p_, es in (s.get("tables") or {}).items()})
                    tabs = mlaws.witness_tabs(cm.m, em2.binders, wr)
                    env = {n: mlaws.value_literal(cm.m, t, wr[n], tabs) for _, n, t in em2.binders}
                    E2 = mlaws.Emitter(cm.m)
                    lhs, _, ty = E2.claims(law["statement"], env, {n: ("State" if t == "Reach" else t)
                                                                   for _, n, t in em2.binders})[conj or 0]
                    text = mproofs.counter(em2, cm.m, imp, wr, lhs, ty)
                    for x in {d, ld, pd}:
                        shutil.rmtree(x, ignore_errors=True)
                    rr = bend.check(write_pair(ld, pd, em2.text, text), cfg)
                    ok = rr.ok and _law_names(em2.text) == [em2.name] and not bend.escape_hatches(text + em2.text)
                    attempts.append({"kind": "counter-law", "generator": "counter", "exit_code": rr.code, "marker": rr.marker,
                                     "seconds": rr.seconds, **({} if ok else {"error": _first(rr.out)})})
                    if ok:
                        status, r, em = "REFUTED", rr, em2
                        rec["witness"] = w
                        if conj is not None:
                            rec["failing_conjunct"] = conj
                        rec["difference"] = witness_difference(cm, law, w, conj)
                        t = triage.get(lid, {})
                        rec["triage"] = t.get("triage", "finding")
                        if t.get("why"):
                            rec["triage_why"] = t["why"]
                        rec["replay"] = replay_status(report, lid, w)
        except mlaws.Unsupported as e:
            attempts.append({"kind": "emit", "error": f"unsupported statement form: {e}"})
        except ir.IRError as e:
            attempts.append({"kind": "ir", "error": f"rejected by the IR rules (G3): {e}"})
            bound = "not searched: the IR rejects the statement"
        except O.OracleError as e:
            attempts.append({"kind": "ir", "error": f"rejected by the oracle sidecar rules: {e}"})
            bound = "not searched: the statement's oracle premises do not resolve against the sidecar"
        if status == "UNKNOWN":
            if "negation" in rec:   # keep the decided negation's files, drop everything else
                for x in (ld / "LAWS.bend", pd / "PROOF.bend"):
                    x.unlink(missing_ok=True)
            else:
                shutil.rmtree(d, ignore_errors=True)
            for x in {ld, pd} - {d}:   # the separated dirs (I10) hold nothing else
                shutil.rmtree(x, ignore_errors=True)
            rec["scope"] = "bounded"
            rec["bound"] = bound or "not searched"
        else:
            rec["scope"] = "unbounded"
            rec["artifacts"].update({"laws": relpath(ld / "LAWS.bend"), "proof": relpath(pd / "PROOF.bend"), "law_name": em.name})
            rec["checker"] = {"exit_code": r.code, "marker": r.marker, "seconds": r.seconds}
            if verdict:
                v = bend.check_verdict(pd / "PROOF.bend", cfg)
                rec["kernel"]["verdict"] = "checked" if v.ok else "failed"
                attempts.append({"kind": "verdict", "kernel": "BendTT (Lean-proven)", "exit_code": v.code,
                                 "marker": v.marker, "seconds": v.seconds})
        rec["status"] = status
        rec["attempts"] = attempts
        kbound["laws"][lid] = {"model": model_src.stem, "cone": law_cone(law, cm.facts, stmt_text, model_src, cfg)}
        rec.update(records.v2_fields(law, rec, stmt_text, model_src, law["facts"], cm.artifact, ROOT))
        if m2plus(milestone):   # §8.5: exactly the hypothesis premises, nothing else (I12)
            rec["model_assumptions"] = O.hypothesis_premises(law, cm.oracles)
        rec["non_vacuity"] = inhabit.inhabit(law, milestone, ROOT, d, cfg, cm=cm, rec=rec)
        (out_dir / f"{lid}.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
        summary[lid] = status
        log(f"{lid:22s} {status:8s} {rec['kernel']['verdict']:8s} {rec['triage']}")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out_dir / "deps.json").write_text(bindings.dump(bindings.dependents(kbound)))
    if m2plus(milestone):   # hypothesis splits are law pairs (I12)
        (out_dir / "splits.json").write_text(json.dumps(O.splits(laws, summary, oracles_of, milestone),
                                                        indent=2, sort_keys=True) + "\n")
    return summary


def param_search(em, cm: CompiledMachine, imp: str, ld: Path, pd: Path, cfg: dict, attempts: list):
    """mproofs.param_premise (I12): its candidates in order, Bend picks. Returns the accepted check, or None."""
    texts = mproofs.param_premise(em, cm.m, imp)
    for i, text in enumerate(texts or []):
        rr = bend.check(write_pair(ld, pd, em.text, text), cfg)
        ok = rr.ok and _law_names(em.text) == [em.name] and not bend.escape_hatches(text + em.text)
        attempts.append({"kind": "proof", "generator": "param_premise", "candidate": i, "exit_code": rr.code,
                         "marker": rr.marker, "seconds": rr.seconds, **({} if ok else {"error": _first(rr.out)})})
        if ok:
            return rr
    return None


def reach_search(em, cm: CompiledMachine, imp: str, ld: Path, pd: Path, cfg: dict, attempts: list, max_tries: int = 120):
    """mproofs.ReachProof: first without strengthening, then with houdini's proposals; in each, Bend picks
    the case terms (the slot on the line it rejects advances). Returns the accepted check, or None."""
    import re
    houdini = None
    for mode in ("plain", "strengthened"):
        strength = []
        if mode == "strengthened":
            houdini = houdini or cm.houdini()
            strength = [(c["field"], c["type"], c["value"]) for c in houdini["candidates"]]
            if not strength:
                break
        try:
            rp = mproofs.ReachProof(em, cm.m, imp, strength)
        except mlaws.Unsupported as e:
            attempts.append({"kind": "proof", "generator": "reach_invariant", "error": f"unsupported: {e}"})
            return None
        choice: dict = {}
        tries, rr, ok = 0, None, False
        for tries in range(1, max_tries + 1):
            text, slot_at = rp.render(choice)   # separated_proof keeps the line count, so slot lines hold
            rr = bend.check(write_pair(ld, pd, em.text, text), cfg)
            ok = rr.ok and _law_names(em.text) == [em.name] and not bend.escape_hatches(text + em.text)
            if ok or rr.ok:
                break
            mm = re.search(r"^\s*(\d+)>\|", rr.out, re.M)
            slot = slot_at.get(int(mm.group(1))) if mm else None
            if slot is None:
                break
            choice[slot] = choice.get(slot, 0) + 1
            if choice[slot] >= len(rp.candidates(slot[2])):
                break
        att = {"kind": "proof", "generator": "reach_invariant", "mode": mode, "tries": tries,
               "strengthening": [f"{f} == {json.dumps(v)}" for f, _, v in strength],
               "exit_code": rr.code if rr else None, "marker": rr.marker if rr else None, "seconds": rr.seconds if rr else None}
        if houdini and mode == "strengthened":
            att["houdini"] = {"states": houdini["states"], "bound": houdini["bound"]}
        if not ok:
            att["error"] = _first(rr.out) if rr else "not checked"
        attempts.append(att)
        if ok:
            return rr
    return None


def law_cone(law: dict, facts: dict, stmt_text: str, model_src: Path, cfg: dict) -> list[str]:
    """The kernel cone of a statement. A holon-ir/0.3 statement that names no model definition at all
    (only Fn binders and IR builtins, e.g. a collision-freedom law) has an empty cone; any other
    statement with an empty cone is an emitter bug (bindings.BindingError)."""
    from .gen.mlaws import BUILTINS
    if law.get("ir_version") == "holon-ir/0.3" and set(R.refs(law, facts)) <= set(BUILTINS):
        return []
    return bindings.kernel_cone(stmt_text, bindings.kernel_entries(model_src, cfg))


def failing_conjunct(cm: CompiledMachine, law: dict, w: dict) -> int | None:
    """The first conjunct of a conjunction that is false at the witness, on the compiled model."""
    if "all" not in law["statement"]["claim"]:
        return None
    ev = cm.evaluate(law, w)
    return next((i for i, ok in enumerate(ev["claims"]) if not ok), None)


def decide_negation(law: dict, cm: CompiledMachine, imp: str, d: Path, cfg: dict) -> dict:
    """Generate the negation of an existential law (for all binders, not claim) and try the proof
    generators on it. imp is relative to the law's directory, so the negation's import goes up one."""
    E = mlaws.Emitter(cm.m)
    out = {"law_id": law["law_id"] + "_neg", "statement_hash": None, "status": "UNKNOWN", "laws": None, "proof": None,
           "generator": None, "statement": None, "attempts": []}
    try:
        neg = E.negation_ir(law)
        out["statement_hash"] = R.law_hash(neg, cm.facts)
        out["statement"] = ir.render_statement(neg)
        nimp = "../" + imp
        em = mlaws.Emitter(cm.m).emit(neg, nimp, note=f"negation of {law['law_id']} ({out['statement_hash']})")
    except mlaws.Unsupported as e:
        out["attempts"].append({"kind": "emit", "error": f"unsupported: {e}"})
        return out
    for gname, g in mproofs.GENERATORS:
        if gname == "evaluate":
            continue
        text = g(em, cm.m, nimp)
        if text is None:
            continue
        d.mkdir(parents=True, exist_ok=True)
        (d / "LAWS.bend").write_text(em.text)
        (d / "PROOF.bend").write_text(text)
        rr = bend.check(d / "PROOF.bend", cfg)
        ok = rr.ok and _law_names(em.text) == [em.name] and not bend.escape_hatches(text + em.text)
        out["attempts"].append({"kind": "proof", "generator": gname, "exit_code": rr.code, "marker": rr.marker,
                                **({} if ok else {"error": _first(rr.out)})})
        if ok:
            if bend.verdict_enabled(cfg):
                v = bend.check_verdict(d / "PROOF.bend", cfg)
                out["attempts"].append({"kind": "verdict", "exit_code": v.code, "marker": v.marker})
                if not v.ok:
                    continue
            out.update({"status": "PROVED", "generator": gname, "laws": relpath(d / "LAWS.bend"),
                        "proof": relpath(d / "PROOF.bend")})
            return out
    shutil.rmtree(d, ignore_errors=True)
    return out


def check_registry_multi(laws: list[dict], reg: dict, milestone: str | None = None) -> None:
    from .pipeline import RegistryMismatch
    problems = []
    files = reg.get("facts_files") or {reg["facts"]: reg["facts_sha256"]}
    for path, sha in files.items():
        if F.sha256_file(ROOT / path) != sha:
            problems.append(f"facts {path} hash differs from the registry")
    if sorted(reg["statements"]) != sorted(l["law_id"] for l in laws):
        problems.append("registry and laws/ list different law ids")
    for law in laws:
        if files.get(law["facts"]) != law["facts_sha256"]:
            problems.append(f"{law['law_id']}: facts_sha256 differs from its facts file")
        orc = O.Oracles.for_facts(ROOT / law["facts"]) if milestone and m2plus(milestone) else None
        if reg["statements"].get(law["law_id"]) != R.law_hash(law, F.load(ROOT / law["facts"]), oracles=orc):
            problems.append(f"{law['law_id']}: statement hash differs from the registry")
    if problems:
        raise RegistryMismatch("; ".join(problems))


def _law_names(text: str) -> list[str]:
    from .pipeline import law_names
    return law_names(text)
