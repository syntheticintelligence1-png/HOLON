"""The I30 laws of a typed milestone, decided on the typed model (I30; the contract is the docstring of
tests_m3/test_sort_types.py, "Proofs, refutation, non-vacuity", "Records" and "Replay").

  python -m holon run --milestone M [--sidecar PATH] [--laws ID,ID] [--out DIR] [--gen-dir DIR]
  python -m holon replay --milestone M [--sidecar PATH]

`run` decides every SORT law of laws/<M> whose subform is I30's (realize, as_member, reinterpret):
  1. its statement, gen/<M>/laws/<id>/LAWS.bend, importing the typed model gen/<M>/sorts/models/<model>.bend as M (the
     model `holon model` writes; a test milestone's goes to its --gen-dir);
  2. refutation once per entry point (holon.sorts.search3: S1-S3 on the compiled model, the sidecar's budget); every
     witness becomes a counter-law gen/<M>/proofs/<id>/entry_<e>/PROOF.bend, accepted only when Bend and BendTT check
     it; the primary witness (the first entry point, sorted, with one) is also gen/<M>/proofs/<id>/PROOF.bend, and the
     law file then states the counter-law;
  3. with no witness, a proof generator of the subform (realize: coercion_guard; as_member: tag_exact; reinterpret:
     the generic generators) and, for a PROVED law, a checked reachable inhabitant of chit_<x> (G11V,
     gen/<M>/<id>/nonvac/); a law they leave UNKNOWN takes its submission in <root>/proofs/inbox/<id>, if any,
     decided by the intake's checks (I41, holon.intake.decide_in_run: the run's files stand in for the regeneration;
     an accepted proof is copied to gen/<M>/proofs/<id>/PROOF.bend and the record names the agent as its prover; a
     refused one is an attempt); otherwise UNKNOWN with what was tried;
  4. with the sidecar's binding, every REFUTED entry is replayed on the real contract (the binding's step harness: its
     deployment, one call per step with the step's calldata, caller, msg.value, block.timestamp and blob hashes);
  5. the record results/<M>/<id>.json (v1 and v2).
`replay` re-runs step 4 for the committed records and writes replay/<M>/sorts/report.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

from .. import bend
from .. import extracted_eval as EV
from ..gen.mlaws import law_name
from ..machine_bend import bname
from . import evaluate3 as E3
from . import proofs3 as P3
from . import search3 as S3
from .model3 import generate, importable, init_of, model_name, write_model_file

ROOT = Path(__file__).resolve().parents[2]
SUBFORMS = ("as_member", "realize", "reinterpret")
GEN3 = ["holon/sorts/run3.py", "holon/sorts/model3.py", "holon/sorts/search3.py", "holon/sorts/proofs3.py",
        "holon/sorts/evaluate3.py", "holon/sorts/deploy3.py", "holon/rules/sort.py", "holon/js/eval3.mjs"]
PANIC = bytes.fromhex("4e487b71")
ERROR = bytes.fromhex("08c379a0")


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rel(p: Path, root: Path) -> str:
    """The repo path of p as it is named (a link keeps its own name: the typed model is <model>.bend, a link to the
    importable file)."""
    p = Path(p)
    try:
        return (p.parent.resolve() / p.name).relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def generator_sha256(root: Path) -> str:
    from ..records import _holon_imports
    seen, todo = set(), list(GEN3)
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


def revert_text(data: bytes) -> str:
    """An outcome's revert key, as the replay compares them: the Error(string) reason, panic:0x<code>, else 0x<sel>."""
    if len(data) >= 68 and data[:4] == ERROR:
        n = int.from_bytes(data[36:68], "big")
        return data[68:68 + n].decode("utf-8", "replace")
    if len(data) == 36 and data[:4] == PANIC:
        return "panic:0x%x" % int.from_bytes(data[4:], "big")
    return "0x" + data[:4].hex()


# ------------------------------------------------------------------------------------------------ the context
class Ctx:
    def __init__(self, milestone: str, root: Path, sidecar: str | None, gen: Path | None, out: Path | None,
                 log=print):
        from .typed_sidecar import load as load_sidecar
        self.m = milestone
        self.root = Path(root)
        self.sidecar_arg = sidecar
        self.sc = load_sidecar(milestone, self.root, sidecar)
        self.gen = Path(gen) if gen else self.root / "gen" / milestone
        self.out = Path(out) if out else self.root / "results" / milestone
        self.laws_dir = self.root / "laws" / milestone
        self.log = log
        dv = json.loads((self.laws_dir / "DERIVATION.json").read_text())
        self.derivation = {e["law_id"]: e for e in dv["laws"]}
        self.registry = json.loads((self.laws_dir / "REGISTRY.json").read_text())
        self.models: dict = {}
        self.resume = False                 # holon run --resume: searches checkpointed under ~/.holon/cache/run3
        self.ckpt_every = 300.0
        self.generated: dict = {}           # doc -> (init, machine, document, model path) this context generated
        self.shared: dict = {}              # the same, handed down by a parent context (holon run --jobs)

    def resume_dir(self, lid: str, doc_rel: str, e: dict) -> Path:
        """Where a law's searches keep their progress (holon run --resume): keyed by everything a search depends on
        (the law, its derivation entry and statement, the typed model, its initial state, the hints, the budget and
        the generator files), outside the repo."""
        hp = self.root / "results" / self.m / "sorts" / "refinement" / "hints.json"
        key = hashlib.sha256(json.dumps({
            "law": lid, "entry": e, "statement": self.registry["statements"].get(lid),
            "model": sha256_file(self.model_path(doc_rel)), "init": self.models[doc_rel][1],
            "hints": sha256_file(hp) if hp.is_file() else None, "budget": self.sc.search,
            "generator": generator_sha256(self.root)}, sort_keys=True, default=str).encode()).hexdigest()
        return Path.home() / ".holon" / "cache" / "run3" / f"{lid}-{key[:16]}"

    def model_path(self, doc_rel: str) -> Path:
        """The typed model as `holon model` names it (gen/<M>/sorts/models/<model>.bend, a link)."""
        return self.gen / "sorts" / "models" / f"{model_name(doc_rel)}.bend"

    def import_path(self, doc_rel: str) -> Path:
        """The file Bend imports (holon.sorts.model3.importable: <model>.bend links to it)."""
        return self.gen / "sorts" / "models" / importable(model_name(doc_rel))

    def model(self, doc_rel: str):
        """(Evaluator, init, search Model factory, hashes) of a document's typed model, writing the model when it is
        not the generated text."""
        if doc_rel in self.models:
            return self.models[doc_rel]
        if doc_rel in self.shared:          # a law context of --jobs: the parent's model, an evaluator of its own
            init, mm, doc, mp = self.shared[doc_rel]
        else:
            from ..machine import load_extracted
            init = init_of(self.m, self.root, self.sidecar_arg, doc_rel)
            text, mm = generate(self.m, self.root, doc_rel, typed=True, sidecar=self.sidecar_arg, init=init)
            mp = write_model_file(self.model_path(doc_rel).parent, model_name(doc_rel), text)
            ip = mp.parent / f"{model_name(doc_rel)}.init.json"
            if not ip.is_file() or ip.read_text(encoding="utf-8") != dumps(init):
                ip.write_text(dumps(init), encoding="utf-8")
            src = self.sc.source(doc_rel)
            doc = load_extracted(self.root / doc_rel, self.root, source=(self.root / src) if src else None)
            self.generated[doc_rel] = (init, mm, doc, mp)
        ev = E3.Evaluator.build(mp, doc)
        hp = self.root / "results" / self.m / "sorts" / "refinement" / "hints.json"
        hints = S3.Hints(json.loads(hp.read_text()) if hp.is_file() else None)

        def factory(empty: bool = False, native: bool = True):
            i = dict(init)
            if empty:
                i["preimages"] = []
            return S3.Model(ev, i, hints, self.root / doc_rel, native=native)
        self.models[doc_rel] = (ev, init, factory, mm, doc)
        return self.models[doc_rel]

    def close(self):
        for ev, *_ in self.models.values():
            ev.close()


# ------------------------------------------------------------------------------------------------ witnesses
def fn_names(doc_model) -> dict:
    out = {}
    for fn, hits in (doc_model.info.get("members") or {}).items():
        for h in hits:
            if h.get("selector"):
                out.setdefault(h["selector"].lower(), fn)
    return out


def calldata(doc_model, st: S3.Step) -> str:
    a = doc_model.actions[st.action]
    ps = doc_model.params(st.action) or []
    vals = [EV.norm(st.args.get(p["name"]), p) for p in ps]
    return (a.get("selector") or "0x") + EV.abi_encode(vals, ps).hex()


def step_json(doc_model, st: S3.Step, fns: dict) -> dict:
    env = st.env
    calls = []
    for c in env.get("calls") or []:
        calls.append({"fn": fns.get(c["data"][:10]), "to": c["to"], "data": c["data"], "ok": bool(c["ok"]),
                      "ret": c["ret"]})
    return {"action": st.action, "args": _plain(st.args), "calldata": calldata(doc_model, st),
            "env": {"caller": "0x%040x" % EV.to_int(env.get("caller", 0)), "msg.value": int(env.get("msg.value", 0)),
                    "block.timestamp": int(env.get("block.timestamp", 0)),
                    "blobhash": ["0x%064x" % EV.to_int(b) for b in env.get("blobhash") or []], "calls": calls}}


def _plain(v):
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex()
    return v


def step_of_json(s: dict) -> S3.Step:
    env = dict(s["env"])
    env["caller"] = EV.to_int(env["caller"])
    env["blobhash"] = [EV.to_int(b) for b in env.get("blobhash") or []]
    env["calls"] = [{"to": c["to"], "data": c["data"], "ok": c["ok"], "ret": c["ret"]} for c in env.get("calls") or []]
    return S3.Step(s["action"], s["args"], env)


# ------------------------------------------------------------------------------------------------ the real side
class Real:
    """The binding's step harness on the real contract (holon.replay_fragments): one project per run."""

    def __init__(self, ctx: Ctx, doc: dict):
        self.ctx = ctx
        self.doc = doc
        self.proj = None
        self.tc = None
        self.work = None

    def setup(self):
        if self.proj is not None:
            return
        from ..fragments_corpus import binding_init
        from ..replay import check_checkout, morph_path, toolchain
        from ..replay_fragments import forge_build, harness_project, load_binding
        self.binding = load_binding(self.ctx.root / self.ctx.sc.binding)
        checkout = None
        if self.binding["project"]["kind"] == "checkout":
            checkout = morph_path(argparse.Namespace(), self.ctx.root)
            check_checkout(checkout, (self.doc.get("target") or {}).get("commit"))
        self.tc = toolchain(argparse.Namespace(forge=None, solc=None, write_pins=False), self.ctx.root)
        self.work = Path(tempfile.mkdtemp(prefix="holon-m3-replay-"))
        self.proj = harness_project(self.binding, self.work, self.ctx.root, checkout, self.tc)
        forge_build(self.proj, self.tc)
        self.init = binding_init(self.binding, self.ctx.root)

    def steps(self, ws: list[dict]):
        from ..replay_fragments import Step
        return [Step(kind="call", caller=s["env"]["caller"], value=int(s["env"].get("msg.value", 0)),
                     timestamp=int(s["env"]["block.timestamp"]), blobs=list(s["env"].get("blobhash") or []),
                     to=None, data=s["calldata"]) for s in ws]

    def run(self, ws: list[dict]) -> dict:
        from ..replay_fragments import run_harness, unit_of
        self.setup()
        runs = run_harness(self.proj, self.tc, self.binding, [self.steps(ws)], [], self.init, tag="m3")
        tr = runs[0]
        execs = [e for e in tr.execs if e.id != "d"]
        outcomes, calls = [], []
        for e in execs:
            outcomes.append("ok" if e.ok else "rev " + revert_text(bytes.fromhex(e.ret[2:])))
            calls.append([{"to": c[0], "data": c[1], "ok": c[2], "ret": c[3]} for c in e.calls])
        panic = None
        if outcomes and outcomes[-1].startswith("rev panic:"):
            panic = self.locate(ws)
            if panic:
                panic = dict(panic, site=f"{unit_of(self.binding, panic['path'])}:{panic['line']}")
        return {"outcomes": outcomes, "calls": calls, "panic": panic}

    def locate(self, ws: list[dict]) -> dict | None:
        from ..mreplay import locate_panic
        from ..replay_fragments import _run, harness_input
        last = self.binding["harness"].get("last_contract")
        if not last:
            return None
        fin, fout, dump = self.proj / "holon_m3_last.json", self.proj / "holon_m3_last.out", self.proj / "m3_dump.json"
        fin.write_text(json.dumps(harness_input([self.steps(ws)], [], self.init)))
        code, out = _run(["nice", "-n", "10", self.tc["forge"], "test", "--match-contract", f"^{last}$",
                          "--match-test", r"^test_last\(\)$", "--offline", "--use", self.tc["solc"], "--debug",
                          "--dump", dump.name], self.proj, {"HOLON_STEPS_IN": fin.name, "HOLON_STEPS_OUT": fout.name})
        try:
            if code != 0 or not dump.exists():
                return None
            return locate_panic(json.loads(dump.read_text()))
        finally:
            for f in (fin, fout, dump):
                f.unlink(missing_ok=True)

    def close(self):
        if self.work is not None:
            shutil.rmtree(self.work, ignore_errors=True)


def model_outcomes(model: S3.Model, steps: list[S3.Step]) -> tuple[list[str], str | None]:
    """Each step's outcome on the model (as the replay keys them) and the last step's failing check id."""
    out = []
    g = model.s0()
    ids = None
    for i, st in enumerate(steps):
        env = model.full_env(st)
        r, _kh, _sh = model.ev.run_fix(st.action, model.state(g), st.args, env, model.kh, model.sh)
        f = r.out["f"]
        c = int(f["c"])
        if c == 0:
            out.append("ok")
        else:
            rv = bytes.fromhex(((f["rv"] or {}).get("$b", "0x") if isinstance(f["rv"], dict) else "0x")[2:])
            out.append("rev " + revert_text(rv))
        if i == len(steps) - 1:
            cks = model.ev.checks.get(st.action) or []
            ids = cks[c - 1] if 0 < c <= len(cks) else None
        _c, g, _calls = model.run_step(g, st, save=True)
    return out, ids


def site_of_span(span: str) -> str:
    return span


def in_span(site: str | None, span: str) -> bool:
    from ..mreplay import in_span as _in
    return bool(site) and _in(span, site)


# ------------------------------------------------------------------------------------------------ deciding a law
def check_file(p: Path) -> tuple[dict, str]:
    """(checker, verdict) of a Bend file: bend2, then BendTT (--verdict) when bend2 accepts it."""
    t = time.time()
    r = bend.check(p)
    checker = {"exit_code": r.code, "marker": "ALL PROOFS CHECK" if r.ok else "SOME PROOFS FAIL",
               "seconds": round(time.time() - t, 3)}
    if not r.ok:
        return checker, "not_run"
    v = bend.check_verdict(p)
    return checker, ("checked" if v.ok else "failed")


class Decider:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx

    def paths(self, lid: str) -> dict:
        g = self.ctx.gen
        return {"laws": g / "laws" / lid / "LAWS.bend", "proofs": g / "proofs" / lid, "nonvac": g / lid / "nonvac"}

    def write_law(self, law_ir: dict, doc_rel: str, counter: bool, hashes: list) -> Path:
        p = self.paths(law_ir["law_id"])["laws"]
        p.parent.mkdir(parents=True, exist_ok=True)
        sh = self.ctx.registry["statements"][law_ir["law_id"]]
        p.write_text(P3.law_file(law_ir, sh, P3.rel_import(p.parent, self.ctx.import_path(doc_rel)), hashes, counter),
                     encoding="utf-8")
        return p

    def emit_counter(self, law: dict, doc_rel: str, steps: list, model_f, ev, hashes: list, where: Path,
                     note: str) -> tuple[Path, dict, str, dict]:
        x = law["law_id"][len("L_sort_"):]
        kh, sh, vals = S3.settle(model_f, steps, [f"coerce_{x}"])
        m = model_f(empty=True)
        acts = [m.act(st) for st in steps]
        states = S3.trace_states(model_f, steps, kh, sh)
        lp = self.paths(law["law_id"])["laws"]
        where.mkdir(parents=True, exist_ok=True)
        p = where / "PROOF.bend"
        p.write_text(P3.counter_proof(law, P3.rel_import(where, self.ctx.import_path(doc_rel)),
                                      P3.rel_import(where, lp), hashes, acts, {"keccak256": kh, "sha256": sh},
                                      P3.Lit(ev.recs), note, states), encoding="utf-8")
        checker, verdict = check_file(p)
        return p, checker, verdict, {"keccak256": kh, "sha256": sh}

    def decide(self, lid: str, real: Real | None, found: dict) -> dict:
        ctx = self.ctx
        e = ctx.derivation[lid]
        law_ir = json.loads((ctx.laws_dir / f"{lid}.json").read_text())
        doc_rel = e["facts"]
        ev, init, model_f, mm, doc = ctx.model(doc_rel)
        hashes = ev.hashes()
        lp = self.write_law(law_ir, doc_rel, False, hashes)
        law = dict(e)
        sorts = json.loads((ctx.root / "gen" / ctx.m / "sorts" / "assignment.json").read_text())["models"][
            model_name(doc_rel)]["assignment"]
        doc_json = json.loads((ctx.root / doc_rel).read_text())
        attempts, witnesses = [], {}
        fns = fn_names(doc)
        resume = ctx.resume_dir(lid, doc_rel, e) if ctx.resume else None
        for entry in sorted(e["entry_points"]):
            t0 = time.time()
            # each entry point is searched from the initial state with the initial hash tables (its own model), so
            # its outcome does not depend on what an earlier entry point's search learned
            ref = S3.Refuter(model_f(), doc_json, sorts, ctx.sc.search, log=ctx.log)
            done = resume / f"{entry}.done.json" if resume is not None else None
            if done is not None and done.is_file():
                dj = json.loads(done.read_text(encoding="utf-8"))
                steps = None if dj["steps"] is None else [S3.Step(*x) for x in dj["steps"]]
                stage, bound = dj["stage"], dj["bound"]
                ctx.log(f"{lid} {entry}: the search's outcome from {done}")
            else:
                if resume is not None:
                    ref.ckpt = S3.Checkpoint(resume, ctx.ckpt_every)
                steps, stage, bound = ref.refute(law, entry, {k: v for k, v in found.items()})
                if resume is not None:
                    resume.mkdir(parents=True, exist_ok=True)
                    tmp = done.with_suffix(".tmp")
                    tmp.write_text(json.dumps({"steps": None if steps is None else
                                               [[st.action, st.args, st.env] for st in steps],
                                               "stage": stage, "bound": bound}), encoding="utf-8")
                    os.replace(tmp, done)
                    ref.ckpt.clear(entry)
            ctx.log(f"{lid} {entry}: {'witness (' + stage + ')' if steps else 'no witness'} in "
                    f"{round(time.time() - t0, 1)} s")
            attempts.append({"kind": "refute", "entry": entry, "stage": stage, "bound": bound,
                             "found": steps is not None})
            if steps is None:
                witnesses[entry] = {"status": "UNKNOWN", "witness": None, "laws": None, "proof": None,
                                    "checker": None, "verdict": "not_run", "stage": None, "bound": bound,
                                    "replay": {"status": "not_run", "detail": "no witness", "panic_site": None}}
                continue
            found[entry] = steps
            witnesses[entry] = {"steps": steps, "stage": stage, "bound": bound}
        status = "UNKNOWN"
        refuted = sorted(k for k, v in witnesses.items() if "steps" in v)
        primary = None
        if refuted:
            lp = self.write_law(law_ir, doc_rel, True, hashes)
            pdir = self.paths(lid)["proofs"]
            shutil.rmtree(pdir, ignore_errors=True)
            for entry in refuted:
                w = witnesses[entry]
                steps = w["steps"]
                if real is not None:
                    steps = self.repair(real, steps, doc, fns, model_f)
                p, checker, verdict, tables = self.emit_counter(
                    law, doc_rel, steps, model_f, ev, hashes, pdir / f"entry_{entry}",
                    f"the witness of entry point {entry} ({w['stage']}), every premise by computation")
                wj = {"steps": [step_json(doc, st, fns) for st in steps],
                      "hashes": {h: [["0x" + k[2:], "0x%064x" % v] for k, v in sorted(tables[h].items())]
                                 for h in hashes}}
                ok = checker["marker"] == "ALL PROOFS CHECK" and verdict == "checked"
                # a counter-law that a kernel rejects is not kept: the entry stays UNKNOWN with its witness and the
                # checkers' answers (bend2's marker, BendTT's verdict)
                witnesses[entry] = {"status": "REFUTED" if ok else "UNKNOWN", "witness": wj,
                                    "laws": rel(lp, ctx.root) if ok else None, "proof": rel(p, ctx.root) if ok else None,
                                    "checker": checker,
                                    "verdict": verdict, "stage": w["stage"] if w["stage"] in ("S2", "S3") else None,
                                    "search_stage": w["stage"], "bound": w["bound"],
                                    "replay": {"status": "not_run", "detail": "", "panic_site": None},
                                    "_steps": steps}
                if ok and primary is None:
                    primary = entry
                if not ok:
                    shutil.rmtree(pdir / f"entry_{entry}", ignore_errors=True)
            if primary is not None:
                status = "REFUTED"
                w = witnesses[primary]
                p, checker, verdict, _t = self.emit_counter(
                    law, doc_rel, w["_steps"], model_f, ev, hashes, pdir,
                    f"the primary witness (entry point {primary}), every premise by computation")
                primary_art = {"proof": rel(p, ctx.root), "checker": checker, "verdict": verdict}
        nonvac = None
        if status != "REFUTED":
            if refuted:
                lp = self.write_law(law_ir, doc_rel, False, hashes)
            att = self.prove(law, doc_rel, mm, hashes, lp)
            attempts.append(att)
            if att.get("marker") == "ALL PROOFS CHECK" and att.get("verdict") == "checked":
                status = "PROVED"
                primary_art = {"proof": att["proof"], "checker": att["checker"], "verdict": "checked"}
                ref = S3.Refuter(model_f(), doc_json, sorts, ctx.sc.search, log=ctx.log)
                nonvac = self.inhabit(law, doc_rel, ref, model_f, ev, hashes, fns)
        prover = "generator"
        if status == "UNKNOWN":
            # I41 (holon.intake): a law the generators and the refuter left UNKNOWN takes the inbox's submission, if
            # any, decided by the intake's checks with this run's files as the regeneration
            agent = self.intake(lid, doc_rel, lp)
            if agent is not None:
                d, proof = agent
                from .. import intake as IN
                attempts.append(IN.attempt(d))
                if d["verdict"] == "accepted":
                    pdir = self.paths(lid)["proofs"]
                    shutil.rmtree(pdir, ignore_errors=True)
                    pdir.mkdir(parents=True, exist_ok=True)
                    (pdir / "PROOF.bend").write_bytes(proof)          # the inbox file, byte for byte
                    r = d["_bend2"]
                    status, prover = "PROVED", d["prover"]
                    primary_art = {"proof": rel(pdir / "PROOF.bend", ctx.root),
                                   "checker": {"exit_code": r.code, "marker": r.marker, "seconds": r.seconds},
                                   "verdict": d["kernels"]["bendtt"]}
                    ref = S3.Refuter(model_f(), doc_json, sorts, ctx.sc.search, log=ctx.log)
                    nonvac = self.inhabit(law, doc_rel, ref, model_f, ev, hashes, fns)
        for k, w in witnesses.items():
            w.pop("_steps", None)
        rec = self.record(law_ir, e, status, witnesses, attempts, lp, doc_rel, primary,
                          primary_art if status in ("REFUTED", "PROVED") else None, nonvac, prover)
        return rec

    def intake(self, lid: str, doc_rel: str, lp: Path):
        """holon.intake.decide_in_run for a law this run left UNKNOWN: (decision, proof bytes), or None without a
        submission in <root>/proofs/inbox/<lid>. The kernels see this run's files at their gen/<M>/ layout paths: the
        typed model the law imports, the milestone's core library when there is one, and the law's statement."""
        from .. import intake as IN
        ctx = self.ctx
        if not os.path.lexists(ctx.root / IN.INBOX / lid):
            return None
        gen, base = ctx.gen.resolve(), Path("gen") / ctx.m

        def lay(p: Path) -> str:
            p = Path(p)
            return (base / (p.parent.resolve() / p.name).relative_to(gen)).as_posix()
        model = ctx.import_path(doc_rel)
        files = {lay(model): model.read_bytes(), lay(lp): lp.read_bytes()}
        for n in ("LAWS.bend", "PROOF.bend"):
            if (gen / "core" / n).is_file():
                files[lay(gen / "core" / n)] = (gen / "core" / n).read_bytes()
        return IN.decide_in_run(ctx.m, lid, ctx.registry["statements"][lid], files, lay(lp),
                                lay(self.paths(lid)["proofs"] / "PROOF.bend"), None, bend.config(ctx.root), ctx.root)

    def prove(self, law: dict, doc_rel: str, mm, hashes: list, lp: Path) -> dict:
        """The proof generator of the law's subform (realize: coercion_guard; as_member: tag_exact; reinterpret:
        reach_invariant), checked by bend2 then BendTT; a rejected or inapplicable attempt leaves no proof file."""
        ctx = self.ctx
        lid = law["law_id"]
        gen_name = {"realize": "coercion_guard", "as_member": "tag_exact", "reinterpret": "reach_invariant"}[law["subform"]]
        pdir = self.paths(lid)["proofs"]
        shutil.rmtree(pdir, ignore_errors=True)
        att = {"kind": "proof", "generator": gen_name, "marker": None}
        if gen_name != "coercion_guard":
            att["error"] = ("does not apply: no " + gen_name + " generator over the M3 model (its mapping slots go "
                            "through the law's hash parameter, which the statement leaves unconstrained)")
            return att
        model_text = ctx.model_path(doc_rel).read_text(encoding="utf-8")
        try:
            text = P3.coercion_guard(law, mm, model_text, P3.rel_import(pdir, ctx.import_path(doc_rel)),
                                     P3.rel_import(pdir, lp), hashes)
        except P3.NoProof as ex:
            att["error"] = f"does not apply: {ex}"
            return att
        pdir.mkdir(parents=True, exist_ok=True)
        p = pdir / "PROOF.bend"
        p.write_text(text, encoding="utf-8")
        checker, verdict = check_file(p)
        att.update({"marker": checker["marker"], "verdict": verdict, "checker": checker, "proof": rel(p, ctx.root)})
        if checker["marker"] != "ALL PROOFS CHECK" or verdict != "checked":
            r = bend.check(p) if checker["marker"] != "ALL PROOFS CHECK" else None
            att["error"] = ("bend2 rejected the proof: " + (r.out or "")[:400]) if r is not None else \
                "BendTT rejected the proof"
            shutil.rmtree(pdir, ignore_errors=True)
            att.pop("proof", None)
        return att

    def inhabit(self, law: dict, doc_rel: str, ref, model_f, ev, hashes: list, fns: dict) -> dict:
        """The non-vacuity record of a PROVED law (G11V): a reachable trace whose last step reaches a hit (chit_<x>),
        searched like a witness (S1, S2) and proved like a counter-law, in gen/<M>/<id>/nonvac/."""
        ctx = self.ctx
        lid = law["law_id"]
        x = lid[len("L_sort_"):]
        sh = ctx.registry["statements"][lid]
        out = {"status": "unknown", "law": None, "witness": None, "reachable": None, "degenerate": None,
               "parent_statement_hash": sh, "bound": None}
        d = self.paths(lid)["nonvac"]
        shutil.rmtree(d, ignore_errors=True)
        steps = ref.inhabit(law)
        if steps is None:
            return {**out, "bound": "no reachable state and step reach a hit within the search budget"}
        kh, shs, _vals = S3.settle(model_f, steps, [f"chit_{x}"])
        m = model_f(empty=True)
        acts = [m.act(st) for st in steps]
        states = S3.trace_states(model_f, steps, kh, shs)
        d.mkdir(parents=True, exist_ok=True)
        lp = d / "LAWS.bend"
        lp.write_text(P3.inhabitant_law(law, sh, P3.rel_import(d, ctx.import_path(doc_rel)), hashes), encoding="utf-8")
        p = d / "PROOF.bend"
        p.write_text(P3.inhabitant_proof(law, P3.rel_import(d, ctx.import_path(doc_rel)), P3.rel_import(d, lp), hashes,
                                         acts, {"keccak256": kh, "sha256": shs}, P3.Lit(ev.recs), states),
                     encoding="utf-8")
        checker, verdict = check_file(p)
        doc = ctx.models[doc_rel][4]
        w = {"steps": [step_json(doc, st, fns) for st in steps],
             "hashes": {h: [["0x" + k[2:], "0x%064x" % v] for k, v in sorted(({"keccak256": kh, "sha256": shs}[h]
                                                                               or {}).items())] for h in hashes}}
        if checker["marker"] != "ALL PROOFS CHECK" or verdict != "checked":
            shutil.rmtree(d, ignore_errors=True)
            return {**out, "witness": w, "bound": f"the inhabitant does not check ({checker['marker']}, {verdict})"}
        return {**out, "status": "inhabited", "law": rel(lp, ctx.root), "witness": w, "reachable": True,
                "bound": f"at-site inhabitant through {steps[-1].action}: {len(steps) - 1} prefix steps"}

    def repair(self, real: Real, steps: list, doc, fns: dict, model_f) -> list:
        """The witness's external-call answers as the deployment's dependencies give them: the real run's calls, in
        order (the model was searched with the hints' answers; the counter-law is checked with these)."""
        ws = [step_json(doc, st, fns) for st in steps]
        res = real.run(ws)
        out = []
        for st, calls in zip(steps, res["calls"]):
            env = dict(st.env)
            env["calls"] = [{"to": c["to"], "data": c["data"], "ok": c["ok"], "ret": c["ret"]} for c in calls]
            out.append(S3.Step(st.action, st.args, env))
        return out

    def record(self, law_ir: dict, e: dict, status: str, witnesses: dict, attempts: list, lp: Path, doc_rel: str,
               primary: str | None, prim: dict | None, nonvac, prover: str = "generator") -> dict:
        from .. import records as R
        ctx = self.ctx
        lid = law_ir["law_id"]
        mp = ctx.model_path(doc_rel)
        sh = ctx.registry["statements"][lid]
        ev = ctx.models[doc_rel][0]
        x = lid[len("L_sort_"):]
        st_text = lp.read_text(encoding="utf-8")
        cone = R.cone(st_text, mp.read_text(encoding="utf-8"))
        rec = {"law_id": lid, "statement_hash": sh, "facts_sha256": law_ir["facts_sha256"], "status": status,
               "scope": "unbounded", "premises": [],
               "kernel": {"name": "bend", "version": bend_version(), "verdict": (prim or {}).get("verdict", "not_run")},
               "artifacts": {"laws": rel(lp, ctx.root), "proof": (prim or {}).get("proof"), "model": rel(mp, ctx.root),
                             "law_name": law_name(lid, status == "REFUTED")},
               "checker": (prim or {}).get("checker") or {"exit_code": None, "marker": "not_run"},
               "triage": "finding" if status == "REFUTED" else "none",
               "replay": {"status": "not_run", "detail": ""},
               "attempts": attempts, "rule": "SORT", "subform": e["subform"], "site": law_ir["statement"]["claim"]["eq"][0]["coerce"],
               "coercion": e["coercion"], "witnesses": witnesses if status != "PROVED" else {},
               "bound": None if status != "UNKNOWN" else "; ".join(sorted({w.get("bound") or "" for w in witnesses.values()}))}
        if primary:
            rec["witness"] = witnesses[primary]["witness"]
            rec["difference"] = {"lhs": False, "rhs": True}   # coerce_<x> at the witness, against true
        base_facts = law_ir["facts"]
        try:
            b, match = R.resolve_bundle(rec["facts_sha256"], base_facts, ctx.root, mp.read_text(encoding="utf-8"),
                                        set(cone), ctx.m)
            assumptions = R.model_assumptions(b["facts_sha256"], set(cone), ctx.root, base_facts)
        except R.LedgerError:
            match, assumptions = "none", []
        compiled = ev.compiled()
        # I41: every record names its prover: "generator", or the agent whose inbox proof the intake accepted
        rec.update({"record_version": R.RECORD_VERSION, "prover": prover, "model_sha256": sha256_file(mp),
                    "compiled_sha256": sha256_file(compiled), "generator_sha256": generator_sha256(ctx.root),
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


def bend_version() -> str:
    try:
        return str(bend.config().get("bend", {}).get("version") or "2.0.36")
    except Exception:  # noqa: BLE001
        return "2.0.36"


# ------------------------------------------------------------------------------------------------ the replay
def replay_entry(model_f, real: Real, steps_json: list, law_e: dict, entry: str) -> dict:
    """holon's replay of one REFUTED entry: the trace on the model and on the real contract, step by step."""
    steps = [step_of_json(s) for s in steps_json]
    m = model_f()
    model_out, check = model_outcomes(m, steps)
    res = real.run(steps_json)
    calls_agree = all([{k: c[k] for k in ("to", "data", "ok", "ret")} for c in res["calls"][i]] ==
                      [{"to": c["to"].lower(), "data": c["data"].lower(), "ok": bool(c["ok"]), "ret": c["ret"].lower()}
                       for c in s["env"].get("calls") or []] for i, s in enumerate(steps_json))
    sub = law_e["subform"]
    panic_site = (res["panic"] or {}).get("site")
    ok = model_out == res["outcomes"] and calls_agree
    if sub == "realize":
        hit = [h["at"] for h in law_e["hits"] if h["action"] == entry]
        ok = ok and res["outcomes"][-1].startswith("rev panic:0x11") and all(o == "ok" for o in res["outcomes"][:-1]) \
            and check in hit and bool(panic_site) and in_span(panic_site, law_e["basis"]["span"])
        obs = True
    else:
        ok = ok and all(o == "ok" for o in res["outcomes"])
        obs = False
    out = {"trace": steps_json, "model": model_out, "real": res["outcomes"], "calls_agree": calls_agree,
           "status": "passed" if ok else "failed", "panic_site": panic_site if sub == "realize" else None,
           "obstruction_observed": obs if ok else (not obs)}
    if sub == "realize":
        out["model_check"] = check
    return out


# ------------------------------------------------------------------------------------------------ the CLI
def _decide_law(ctx: Ctx, lid: str, real) -> tuple[dict, dict | None]:
    """(the record, its replay report entry or None) of one law; the law's own refuter, model and replay."""
    e = ctx.derivation[lid]
    own = None
    if ctx.sc.binding and real is None:
        real = own = Real(ctx, json.loads((ctx.root / e["facts"]).read_text()))
    try:
        return _decide_with(ctx, lid, e, real)
    finally:
        if own is not None:
            own.close()


def _decide_with(ctx: Ctx, lid: str, e: dict, real) -> tuple[dict, dict | None]:
    rec = Decider(ctx).decide(lid, real, {})
    entry_rep = None
    if rec["status"] == "REFUTED" and real is not None:
        model_f = ctx.models[e["facts"]][2]
        entries = {}
        for entry, w in sorted(rec["witnesses"].items()):
            if w.get("status") != "REFUTED":
                continue
            x = replay_entry(model_f, real, w["witness"]["steps"], e, entry)
            entries[entry] = x
            w["replay"] = {"status": x["status"], "detail": " / ".join(x["real"]), "panic_site": x.get("panic_site")}
        entry_rep = {"entries": entries}
        st = "passed" if entries and all(x["status"] == "passed" for x in entries.values()) else "failed"
        rec["replay"] = {"status": st, "detail": "; ".join(f"{k}: {' / '.join(v['real'])}"
                                                          for k, v in sorted(entries.items()))}
    elif rec["status"] == "REFUTED":
        rec["replay"] = {"status": "not_applicable", "detail": "no binding: the milestone has no real side"}
        for w in rec["witnesses"].values():
            if w.get("status") == "REFUTED":
                w["replay"] = {"status": "not_applicable", "detail": "no binding", "panic_site": None}
    else:
        rec["replay"] = {"status": "not_applicable", "detail": f"{rec['status']}: no witness to replay"}
    return rec, entry_rep


def run_main(a) -> int:
    """Every I30 law of the milestone (or --laws), each decided on its own (its refuter, model and witnesses are its
    own, so --jobs N decides N laws at a time with the same records), then the records and the replay report written
    in law order."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    root = ROOT
    gen = Path(a.gen_dir).resolve() if a.gen_dir else None
    out = Path(a.out).resolve() if a.out else None
    ctx = Ctx(a.milestone, root, a.sidecar, gen, out)
    ctx.resume = bool(getattr(a, "resume", False))
    ctx.ckpt_every = float(getattr(a, "checkpoint_seconds", 300) or 300)
    ids = sorted(l for l, e in ctx.derivation.items() if e.get("rule") == "SORT" and e.get("subform") in SUBFORMS)
    if a.laws:
        want = {x.strip() for x in a.laws.split(",") if x.strip()}
        ids = [l for l in ids if l in want]
    ctx.out.mkdir(parents=True, exist_ok=True)
    report = {"document": "sorts_replay", "milestone": ctx.m, "binding": ctx.sc.binding, "laws": {}}
    jobs = max(1, int(getattr(a, "jobs", 1) or 1))
    lock = threading.Lock()
    results: dict = {}
    contexts: list = []
    try:
        for lid in ids:                     # the models are written once, before any law runs
            ctx.model(ctx.derivation[lid]["facts"])

        def one(lid: str):
            if jobs == 1:
                c = ctx
            else:
                c = Ctx(a.milestone, root, a.sidecar, gen, out,
                        log=lambda m, lid=lid: print(f"[{lid}] {m}", flush=True))
                c.shared = dict(ctx.generated)
                c.resume, c.ckpt_every = ctx.resume, ctx.ckpt_every
                with lock:
                    contexts.append(c)
            try:
                rec, rep = _decide_law(c, lid, None)
            except BaseException as ex:
                import traceback
                print(f"[{lid}] failed: {type(ex).__name__}: {ex}\n{traceback.format_exc()}", flush=True)
                raise
            finally:
                if c is not ctx:
                    c.close()
            c.log(f"{lid}: {rec['status']}")
            (ctx.out / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")     # kept if a later law fails
            return lid, rec, rep
        if jobs == 1:
            reals: dict = {}
            for lid in ids:
                e = ctx.derivation[lid]
                if ctx.sc.binding and "r" not in reals:
                    reals["r"] = Real(ctx, json.loads((ctx.root / e["facts"]).read_text()))
                rec, rep = _decide_law(ctx, lid, reals.get("r"))
                ctx.log(f"{lid}: {rec['status']}")
                (ctx.out / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
                results[lid] = (rec, rep)
            for r in reals.values():
                r.close()
        else:
            with ThreadPoolExecutor(max_workers=jobs) as ex:
                for lid, rec, rep in ex.map(one, ids):
                    results[lid] = (rec, rep)
        for lid in ids:
            rec, rep = results[lid]
            (ctx.out / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
            if rep is not None:
                report["laws"][lid] = rep
        if report["laws"]:
            rp = ctx.root / "replay" / ctx.m / "sorts" / "report.json"
            if ctx.out.resolve() == (ctx.root / "results" / ctx.m).resolve():
                rp.parent.mkdir(parents=True, exist_ok=True)
                rp.write_text(dumps(report), encoding="utf-8")
    finally:
        ctx.close()
    return 0


def replay_main(a) -> int:
    """holon replay --milestone M: every REFUTED I30 record's entries, again, into replay/<M>/sorts/report.json."""
    root = ROOT
    ctx = Ctx(a.milestone, root, getattr(a, "sidecar", None), None, None)
    report = {"document": "sorts_replay", "milestone": ctx.m, "binding": ctx.sc.binding, "laws": {}}
    real = None
    try:
        for lid in sorted(ctx.derivation):
            e = ctx.derivation[lid]
            if e.get("rule") != "SORT" or e.get("subform") not in SUBFORMS:
                continue
            p = ctx.out / f"{lid}.json"
            if not p.is_file():
                continue
            r = json.loads(p.read_text())
            if r.get("status") != "REFUTED" or not ctx.sc.binding:
                continue
            if real is None:
                real = Real(ctx, json.loads((ctx.root / e["facts"]).read_text()))
            ctx.model(e["facts"])
            model_f = ctx.models[e["facts"]][2]
            entries = {}
            for entry, w in sorted((r.get("witnesses") or {}).items()):
                if w.get("status") == "REFUTED":
                    entries[entry] = replay_entry(model_f, real, w["witness"]["steps"], e, entry)
            report["laws"][lid] = {"entries": entries}
        rp = ctx.root / "replay" / ctx.m / "sorts" / "report.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(dumps(report), encoding="utf-8")
        bad = [(l, k) for l, x in report["laws"].items() for k, v in x["entries"].items() if v["status"] != "passed"]
        print(f"holon replay: {sum(len(x['entries']) for x in report['laws'].values())} entries, {len(bad)} failed "
              f"-> {rel(rp, ctx.root)}")
        return 0 if not bad else 1
    finally:
        ctx.close()
        if real is not None:
            real.close()


def main(argv: list) -> int:
    cmd, rest = argv[0], argv[1:]
    ap = argparse.ArgumentParser(prog=f"holon {cmd}")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--sidecar")
    ap.add_argument("--laws")
    ap.add_argument("--out")
    ap.add_argument("--gen-dir")
    ap.add_argument("--facts")
    ap.add_argument("--no-registry", action="store_true")
    ap.add_argument("--core", default="import")
    ap.add_argument("--morph")
    ap.add_argument("--forge")
    ap.add_argument("--solc")
    ap.add_argument("--work")
    ap.add_argument("--write-pins", action="store_true")
    ap.add_argument("--corpus", type=int, default=300)
    ap.add_argument("--jobs", type=int, default=1, help="laws decided at a time (the records do not depend on it)")
    ap.add_argument("--resume", action="store_true",
                    help="checkpoint each search under ~/.holon/cache/run3 and resume an interrupted one (the records "
                         "are the uninterrupted run's)")
    ap.add_argument("--checkpoint-seconds", type=float, default=300.0,
                    help="with --resume: seconds between checkpoints (the records do not depend on it)")
    a = ap.parse_args(rest)
    if cmd == "replay":
        return replay_main(a)
    return run_main(a)
