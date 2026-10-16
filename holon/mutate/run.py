"""`python -m holon mutate run | gate | rate` (I61; the contract is the docstring of
tests_m2/test_mutation_adequacy_i61.py, "The pipeline", "Kill criterion", "Outputs"; the rules are the instrument's).

    python -m holon mutate run --milestone M2 [--only A001,...] [--control C1,...] [--baseline-only] [--work DIR]
                               [--jobs N] [--no-carry] [--dry-run] [--check]
    python -m holon mutate gate [--check]
    python -m holon mutate rate [--check]

A unit is the baseline (the null mutant: the unmutated pinned files), a catalog mutant or a planted control. Per unit:
  1. its source tree (holon.mutate.stage.source_tree) and a scratch HOLON tree at the pipeline commit naming it;
  2. the re-extraction with the M2 frontends, unchanged (stage.extract);
  3. the projection (holon.mutate.project) and the three law sets (M0 by holon.mutate.m0, M1x and M2 here), each
     law's own decided input hashed, carried when equal to the baseline's, matched by (rule, subform, basis span);
  4. per law: proof attempt of the baseline generator, model hits replayed on the unit's code and on the original
     code (holon.mutate.replay), recorded witness, Bend-checked counter-law, K2 (c) search;
  5. the detection channels (holon.mutate.channels), never a kill;
  6. the kill decision, outcome and survivor class (holon.mutate.decide).
Exit 0 ok; 1 --check found a difference; 2 refused, nothing written.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

from . import common as C
from . import decide as D
from . import lawsets as L
from . import stage as S
from .m0 import model_verdict  # noqa: F401  (the contract names holon.mutate.run.model_verdict)

BASELINE = "baseline"
INPUTS = C.GEN / "baseline_inputs.json"        # the baseline's own-input components, traces and channel references
I20_CORPUS = C.GEN / "i20_corpus.json"         # the baseline's I20 corpus and real observables (channels.i20_baseline)
STEP_RETRY = 2                                  # a step that fails for a reason other than the law is retried once


def log_default(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ================================================================================================ units
def units(inst: dict, only=None, controls=None, baseline=False) -> list[dict]:
    """The units to run, in order: the baseline, the named controls, the named catalog mutants (default: all)."""
    out = []
    if baseline:
        out.append({"id": BASELINE, "kind": "baseline", "mutant": None})
    ctl = {c["id"]: c for c in inst["harness_gate"]["controls"]}
    for cid in controls or []:
        if cid not in ctl:
            raise C.MutateError(f"no planted control {cid} (controls: {sorted(ctl)})")
        out.append({"id": cid, "kind": "control", "mutant": ctl[cid]})
    ms = {m["id"]: m for m in inst["mutants"]}
    for mid in only if only is not None else []:
        if mid not in ms:
            raise C.MutateError(f"no catalog mutant {mid}")
        out.append({"id": mid, "kind": "mutant", "mutant": ms[mid]})
    return out


def record_path(unit: dict) -> Path:
    if unit["kind"] == "baseline":
        return C.RESULTS / "baseline.json"
    if unit["kind"] == "control":
        return C.CONTROLS / f"{unit['id']}.json"
    return C.RESULTS / f"{unit['id']}.json"


# ================================================================================================ preconditions
def _git(root: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def committed_bytes(root: Path, commit: str, path: str) -> bytes | None:
    p = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{path}"], capture_output=True)
    return p.stdout if p.returncode == 0 else None


def check_target(root: Path, inst: dict) -> list[str]:
    """run refuses when the pinned checkout is dirty or not at target.commit, or an in-scope file differs."""
    bad = []
    co = C.checkout(root)
    p = _git(co, "rev-parse", "HEAD")
    if p.returncode != 0 or p.stdout.strip() != inst["target"]["commit"]:
        bad.append(f"the pinned checkout {co} is at {p.stdout.strip() or '?'}, not {inst['target']['commit']}")
    p = _git(co, "status", "--porcelain")
    if p.returncode != 0 or p.stdout.strip():
        bad.append(f"the pinned checkout {co} is dirty: {p.stdout.strip()[:300]}")
    nm = C.sol_deps(root)
    for f, v in inst["in_scope"]["files"].items():
        src = (co / f) if v["root"] == "checkout" else (nm / f)
        try:
            got = C.sha256_file(src)
        except OSError:
            got = None
        if got != v["sha256"]:
            bad.append(f"in-scope file {f} hashes to {got}, the instrument pins {v['sha256']}")
    return bad


def check_review(root: Path, inst_ref: dict) -> tuple[list[str], dict | None]:
    p = root / C.REVIEW
    if not p.is_file():
        return [f"{C.REVIEW}: missing"], None
    try:
        rv = json.loads(p.read_text())
    except ValueError as e:
        return [f"{C.REVIEW}: does not parse: {e}"], None
    bad = []
    if rv.get("instrument") != inst_ref:
        bad.append(f"{C.REVIEW}: names another instrument ({rv.get('instrument')})")
    lenses = rv.get("reviews") or {}
    for lens in ("fairness", "soundness"):
        x = lenses.get(lens)
        if not isinstance(x, dict):
            bad.append(f"{C.REVIEW}: the {lens} lens is missing")
        elif x.get("sign_off") is not True or x.get("blocking"):
            bad.append(f"{C.REVIEW}: the {lens} lens is not signed off")
    if rv.get("verdict") != "signed off":
        bad.append(f"{C.REVIEW}: verdict is {rv.get('verdict')!r}, not 'signed off'")
    return bad, rv


def check_adjudication(root: Path, inst: dict, inst_ref: dict) -> tuple[list[str], dict | None]:
    p = root / C.ADJUDICATION
    if not p.is_file():
        return [f"{C.ADJUDICATION}: missing"], None
    try:
        adj = json.loads(p.read_text())
    except ValueError as e:
        return [f"{C.ADJUDICATION}: does not parse: {e}"], None
    bad = []
    if adj.get("instrument") != inst_ref:
        bad.append(f"{C.ADJUDICATION}: names another instrument")
    if adj.get("mutants_sha256") != inst["mutants_sha256"]:
        bad.append(f"{C.ADJUDICATION}: names another catalog (mutants_sha256)")
    if adj.get("diff_sheet_sha256") != inst["diff_sheet"]["sha256"]:
        bad.append(f"{C.ADJUDICATION}: names another diff sheet")
    rv = root / C.REVIEW
    want = {"path": C.REVIEW.as_posix(), "sha256": C.sha256_file(rv) if rv.is_file() else None}
    if adj.get("review") != want:
        bad.append(f"{C.ADJUDICATION}: names another review ({adj.get('review')})")
    ids = [m["id"] for m in inst["mutants"]]
    v = adj.get("verdicts") or {}
    miss = sorted(set(ids) - set(v))
    extra = sorted(set(v) - set(ids))
    if miss:
        bad.append(f"{C.ADJUDICATION}: misses {len(miss)} ids ({', '.join(miss[:5])})")
    if extra:
        bad.append(f"{C.ADJUDICATION}: names unknown ids ({', '.join(extra[:5])})")
    return bad, adj


def check_gate(root: Path, inst_ref: dict, commit: str) -> list[str]:
    p = root / C.GATE
    if not p.is_file():
        return [f"{C.GATE}: missing"]
    try:
        g = json.loads(p.read_text())
    except ValueError as e:
        return [f"{C.GATE}: does not parse: {e}"]
    bad = []
    if g.get("instrument") != inst_ref:
        bad.append(f"{C.GATE}: names another instrument")
    if g.get("passed") is not True:
        bad.append(f"{C.GATE}: the gate has not passed")
    if g.get("pipeline_commit") != commit:
        bad.append(f"{C.GATE}: passed at {g.get('pipeline_commit')}, not at the run's pipeline commit {commit}")
    return bad


def check_baseline(root: Path, inst: dict, commit: str) -> tuple[list[str], dict | None]:
    p = root / C.RESULTS / "baseline.json"
    if not p.is_file():
        return [f"{C.RESULTS / 'baseline.json'}: missing"], None
    try:
        b = json.loads(p.read_text())
    except ValueError as e:
        return [f"{C.RESULTS / 'baseline.json'}: does not parse: {e}"], None
    bad = []
    if b.get("pipeline_commit") != commit:
        bad.append(f"baseline.json: pipeline commit {b.get('pipeline_commit')}, not {commit}")
    st = {k: e.get("mutant") for k, e in (b.get("laws") or {}).items()}
    for set_ in L.SETS:
        want = inst["baseline"][set_]
        got = {k: st.get(k) for k in want}
        if got != want:
            diff = sorted(k for k in want if got[k] != want[k])
            bad.append(f"baseline.json: the {set_} statuses do not reproduce the pins ({', '.join(diff[:5])})")
    docs = b.get("documents") or {}
    committed = sorted(f"{C.FACTS2.as_posix()}/{x.name}" for x in (root / C.FACTS2).glob("*.extracted.json"))
    if sorted(docs) != committed:
        bad.append("baseline.json: its documents are not the committed spec/M2/facts/*.extracted.json")
    for path in committed:
        d = docs.get(path) or {}
        want = C.normalized_sha256(json.loads((root / path).read_text()))
        if d.get("normalized_sha256") != want or d.get("changed") is not False:
            bad.append(f"baseline.json: {path} does not reproduce the committed document")
    pp = root / C.PROJECTED
    if not pp.is_file():
        bad.append(f"{C.PROJECTED}: missing")
    elif (b.get("projection") or {}).get("normalized_sha256") != C.normalized_sha256(json.loads(pp.read_text())):
        bad.append("baseline.json: its projection does not reproduce the committed projection")
    if b.get("extraction") != {"status": "ok", "errors": {}}:
        bad.append("baseline.json: its extraction did not complete")
    return bad, b


def check_i21(root: Path, commit: str) -> list[str]:
    """I21's exit at the run's pipeline commit: audit/rounds/M2/round2.json exists and audit/M2_findings.jsonl has no
    line of severity high and status open (preconditions.i21_exit)."""
    bad = []
    if committed_bytes(root, commit, "audit/rounds/M2/round2.json") is None:
        bad.append("I21's exit: audit/rounds/M2/round2.json is not in the pipeline commit's tree")
    raw = committed_bytes(root, commit, "audit/M2_findings.jsonl")
    if raw is None:
        bad.append("I21's exit: audit/M2_findings.jsonl is not in the pipeline commit's tree")
        return bad
    for n, line in enumerate(raw.decode().splitlines(), 1):
        if not line.strip():
            continue
        try:
            f = json.loads(line)
        except ValueError:
            bad.append(f"I21's exit: audit/M2_findings.jsonl line {n} does not parse")
            continue
        if f.get("severity") == "high" and f.get("status") == "open":
            bad.append(f"I21's exit: audit/M2_findings.jsonl line {n} is an open high-severity finding "
                       f"({f.get('id')})")
    return bad


def preconditions(root: Path, inst: dict, commit: str) -> tuple[list[str], dict]:
    """Every precondition of a catalog mutant's run (instrument preconditions.refusal); ([problems], {inputs})."""
    ref = C.instrument_ref(root)
    bad, got = [], {}
    b, got["review"] = check_review(root, ref)
    bad += b
    b, got["adjudication"] = check_adjudication(root, inst, ref)
    bad += b
    bad += check_gate(root, ref, commit)
    b, got["baseline"] = check_baseline(root, inst, commit)
    bad += b
    bad += check_i21(root, commit)
    return bad, got


def clean_tree(root: Path) -> list[str]:
    """The run's code is the pipeline commit's: no uncommitted change outside the outcome paths."""
    p = _git(root, "status", "--porcelain", "--untracked-files=no", "--", "holon", "replay", "config", "spec",
             "laws", "facts", "bend", "gen/M0", "gen/M2/model")
    lines = [x for x in p.stdout.splitlines() if x.strip() and C.ADJUDICATION.as_posix() not in x]
    return [f"uncommitted change outside the outcome paths: {x}" for x in lines[:10]]


# ================================================================================================ the run context
class Ctx:
    """What every unit of one run shares: the HOLON root and pipeline commit, the instrument, the baseline record and
    inputs (None while the baseline itself runs), the original tree's replay harness, the adjudication."""

    def __init__(self, root: Path, work: Path, carry: bool = True, log=log_default):
        self.root = Path(root)
        self.inst = C.instrument(root)
        self.commit = C.pipeline_commit(root)
        self.work = Path(work).resolve()
        self.carry = carry
        self.log = log
        self.checkout = C.checkout(root)
        self.sol_deps = C.sol_deps(root)
        self.null_doc = json.loads((self.root / C.FACTS2 / "morph_header.extracted.json").read_text())
        self.base = None
        self.inputs = None
        self.equivalent = None
        self._orig = None
        self._orig_tree = None
        self._base_model = None
        self.laws0 = None

    def load_baseline(self) -> None:
        bp = self.root / C.RESULTS / "baseline.json"
        ip = self.root / INPUTS
        self.base = json.loads(bp.read_text()) if bp.is_file() else None
        self.inputs = json.loads(ip.read_text()) if ip.is_file() else None

    def original(self):
        """The replay harness of the unmutated tree (built once per run, reused by every unit)."""
        if self._orig is None:
            from .replay import Harness
            self._orig_tree = C.copy_tree(self.checkout, self.work / "_original" / "src")
            self._orig = Harness(self._orig_tree, self.sol_deps, work=self.work / "_original" / "harness")
            self._orig.__enter__()
        return self._orig

    def close(self) -> None:
        if self._orig is not None:
            self._orig.__exit__(None, None, None)
            self._orig = None


class Unit:
    """One unit's state while it runs."""

    def __init__(self, ctx: Ctx, u: dict):
        self.ctx = ctx
        self.id = u["id"]
        self.kind = u["kind"]
        self.m = u["mutant"]
        self.dir = ctx.work / self.id
        self.tree = self.nm = self.H = None
        self.harness = None
        self.errors = []
        self.proj = None
        self.proj_path = None
        self.secs = {}

    @property
    def is_base(self) -> bool:
        return self.kind == "baseline"

    def lang(self) -> str | None:
        if self.m is None:
            return None
        return "solidity" if self.m["file"].endswith(".sol") else "go"

    def error(self, step: str, laws: list, message: str) -> None:
        self.errors.append({"step": step, "laws": sorted(laws), "message": message[-1500:]})

    def mut_harness(self):
        """The replay harness of this unit's tree (the original's for the baseline)."""
        if self.is_base:
            return self.ctx.original()
        if self.harness is None:
            from .replay import Harness
            self.harness = Harness(self.tree, self.nm, work=self.dir / "harness")
            self.harness.__enter__()
        return self.harness

    def close(self) -> None:
        if self.harness is not None:
            self.harness.__exit__(None, None, None)
            self.harness = None


def _retry(fn, *a, **k):
    """Run a step; a failure (an exception) is retried once (kill_criterion.errors)."""
    last = None
    for _ in range(STEP_RETRY):
        try:
            return fn(*a, **k)
        except Exception as e:  # noqa: BLE001: the step's failure is recorded against the laws it decides
            last = e
    raise last


# ================================================================================================ one unit
def skeleton(ctx: Ctx, u: Unit) -> dict:
    m = u.m
    cat = u.kind == "mutant"
    return {"id": u.id, "stratum": m["stratum"] if cat else None, "operator": m["operator"] if cat else None,
            "pipeline_commit": ctx.commit, "documents": {}, "extraction": {"status": "ok", "errors": {}},
            "projection": {"normalized_sha256": None, "changed": None, "error": None},
            "recomputed": None, "laws": {}, "kill": None, "recomputed_only": [], "masked_obstructions": [],
            "proof_lost_unwitnessed": [], "replay_disagreements": [], "baseline_findings": [], "errors": [],
            "refinement": {"channels": []}, "extraction_defect_detected": None, "corpus_detected": None,
            "outcome": None, "class": None, "gap_stage": None, "rule_gap_kind": None,
            "structural": m["structural"]["class"] if cat else None}


def predicted_sets(ctx: Ctx, u: Unit) -> dict:
    """The frozen predicted sets (instrument predicted): a catalog mutant's own; a control's by the same rules on the
    pinned artifacts (operators.recompute over the committed tree); the baseline predicts nothing."""
    if u.kind == "mutant":
        return {k: set(v) for k, v in u.m["predicted"].items()}, set(u.m["actions"])
    if u.kind == "control":
        from .operators import recompute
        r = recompute(ctx.inst, u.m, u.tree, u.nm, ctx.root)
        return {k: set(v) for k, v in r["predicted"].items()}, set(r["actions"])
    return {"M0": set(), "M1x": set(), "M2": set()}, set()


def documents(ctx: Ctx, u: Unit, rec: dict, texts: dict, errs: dict) -> None:
    if u.is_base:
        ref = {f"{C.FACTS2.as_posix()}/{p.name}": C.normalized_sha256(json.loads(p.read_text()))
               for p in sorted((ctx.root / C.FACTS2).glob("*.extracted.json"))}
    else:
        ref = {p: d["normalized_sha256"] for p, d in ctx.base["documents"].items()}
    for rel in sorted(texts):
        n = C.normalized_sha256(json.loads(texts[rel]))
        rec["documents"][rel] = {"sha256": C.sha256_text(texts[rel]), "normalized_sha256": n,
                                 "changed": n != ref.get(rel)}
    rec["extraction"] = {"status": "error" if errs else "ok", "errors": dict(sorted(errs.items()))}


def projection(ctx: Ctx, u: Unit, rec: dict, errs: dict) -> None:
    """Step 3's projected header document (holon.mutate.project) of the unit's documents."""
    from .project import project_root
    read = {r["document"] for r in ctx.inst["roles"]["solidity"].values()} | \
           {r["document"] for r in ctx.inst["roles"]["go"].values()}
    failed = sorted(d for d in errs if d in read)
    if failed:
        rec["projection"] = {"normalized_sha256": None, "changed": None,
                             "error": "extraction failed: " + ", ".join(failed)}
        return
    try:
        proj = _retry(project_root, u.H)
    except Exception as e:  # noqa: BLE001
        rec["projection"] = {"normalized_sha256": None, "changed": None, "error": f"{type(e).__name__}: {e}"[:1500]}
        return
    u.proj = proj
    u.proj_path = u.dir / "m0" / "morph_header.json"
    u.proj_path.parent.mkdir(parents=True, exist_ok=True)
    u.proj_path.write_text(C.dump(proj))
    sha = C.normalized_sha256(proj)
    if u.is_base:
        ref = C.normalized_sha256(json.loads((ctx.root / C.PROJECTED).read_text()))
    else:
        ref = ctx.base["projection"]["normalized_sha256"]
    rec["projection"] = {"normalized_sha256": sha, "changed": sha != ref, "error": None}


# ------------------------------------------------------------------------------------------------ replays
def _env_key(env) -> str:
    return C.compact(env)


def original_claims(ctx: Ctx, law: dict, envs: list) -> list:
    """The law's claim on the original tree at each env (cached across units)."""
    cache = ctx.__dict__.setdefault("_ocache", {})
    lid = law["law_id"]
    need = [env for env in envs if (lid, _env_key(env)) not in cache]
    if need:
        res = _retry(ctx.original().claims, law, need)
        for env, r in zip(need, res):
            cache[(lid, _env_key(env))] = r
    return [cache[(lid, _env_key(env))] for env in envs]


def unit_claims(ctx: Ctx, u: Unit, law: dict, envs: list) -> list:
    if u.is_base:
        return original_claims(ctx, law, envs)
    return _retry(u.mut_harness().claims, law, envs) if envs else []


def original_traces(ctx: Ctx, law: dict, traces: list) -> list:
    cache = ctx.__dict__.setdefault("_tcache", {})
    lid = law["law_id"]
    need = [t for t in traces if (lid, C.compact(t)) not in cache]
    if need:
        res = _retry(ctx.original().trace_claims, law, need)
        for t, r in zip(need, res):
            cache[(lid, C.compact(t))] = r
    return [cache[(lid, C.compact(t))] for t in traces]


def unit_traces(ctx: Ctx, u: Unit, law: dict, traces: list) -> list:
    if u.is_base:
        return original_traces(ctx, law, traces)
    return _retry(u.mut_harness().trace_claims, law, traces) if traces else []


def recorded_witness(replay: list | None, labels: list):
    """replay.hits: the first hit that replays on the mutant and not on the original, else the first hit."""
    for r in replay or []:
        if r["mutant"] is True and r["original"] is False:
            return r["label"]
    return labels[0] if labels else None


def fits_entry(ctx: Ctx, u: Unit, calls: list) -> bool:
    """equivalence.contradictions (entry-fit): a Go mutant's witness always fits; otherwise every enc_sol call the
    witness executes must satisfy enc_sol's unprojected revert conditions and the extracted Header's value types (a
    witness that executes only the loader fits)."""
    from .m0 import fits
    if u.lang() == "go":
        return True
    for c in calls or []:
        if c.get("role") == "enc_sol" and not (isinstance(c.get("arg"), dict) and fits(c["arg"], ctx.null_doc)):
            return False
    return True


# ------------------------------------------------------------------------------------------------ the M0 set
def base_entry(ctx: Ctx, lid: str) -> dict | None:
    return (ctx.base or {}).get("laws", {}).get(lid)


def _accepted_generator(rec: dict) -> str | None:
    acc = [a["generator"] for a in rec.get("attempts", [])
           if a.get("kind") == "proof" and a.get("marker") == D.MARK_OK]
    return acc[-1] if acc else None


def decide_m0(ctx: Ctx, u: Unit, rec: dict, pred: set) -> None:
    """The M0 set: decided by `holon run --milestone M0 --no-registry` on the unit's projection, or carried when the
    projection (and with it every M0 law's own decided input) equals the baseline's. A carried law's entry is the one
    a run would write (run --check reruns with --no-carry and compares every field but "decided"): its proof is the
    baseline's (the same generated model and generator), its counter-law is checked on the same model."""
    from . import m0 as M
    from ..gen import model as G
    inst = ctx.inst
    limit = inst["kill_criterion"]["replay_candidates"]
    laws0 = M.laws(ctx.root)
    entries = {}
    for lid in laws0:
        b = base_entry(ctx, lid)
        e = L.entry("M0", L.m0_family(lid), b["mutant"] if b else "absent")
        e["predicted"] = lid in pred
        entries[lid] = e
    rec["laws"].update(entries)
    pj = rec["projection"]
    if pj["error"] is not None:
        for e in entries.values():
            e["mutant"], e["error"] = "error", "projection: " + pj["error"]
        u.error("projection", list(entries), pj["error"])
        return
    proj_sha = pj["normalized_sha256"]
    carry = ctx.carry and not u.is_base and pj["changed"] is False
    m0dir = u.dir / "m0"
    facts_path, facts = u.proj_path, u.proj
    recs, cones = None, None
    if carry:
        model_src = m0dir / "gen" / "model" / f"{M.MODEL_NAME}.bend"
        model_src.parent.mkdir(parents=True, exist_ok=True)
        model_src.write_text(G.generate(facts, C.sha256_file(facts_path)))
    else:
        p = None
        for _ in range(STEP_RETRY):
            shutil.rmtree(m0dir / "results", ignore_errors=True)
            p = S.holon(u.H, ["run", "--milestone", "M0", "--facts", facts_path, "--no-registry", "--out",
                              m0dir / "results", "--gen-dir", m0dir / "gen"], timeout=5400)
            if p.returncode == 0:
                break
        if p.returncode != 0:
            msg = f"holon run --milestone M0 (exit {p.returncode}): {S._tail(p)}"
            for e in entries.values():
                e["mutant"], e["error"] = "error", msg[:500]
            u.error("M0", list(entries), msg)
            return
        recs = {lid: json.loads((m0dir / "results" / f"{lid}.json").read_text()) for lid in laws0}
        cones = L.cones(m0dir / "results" / "deps.json", m0dir / "gen" / "model" / f"{M.MODEL_NAME}.defs.json")
        u.m0_cones = cones
    try:
        model = _retry(M.compiled, facts_path, m0dir)
    except Exception as ex:  # noqa: BLE001
        msg = f"the projected model does not compile: {ex}"
        for e in entries.values():
            e["mutant"], e["error"] = "error", msg[:500]
        u.error("M0", list(entries), msg)
        return
    mverdict = None
    for lid, law in laws0.items():
        e = entries[lid]
        b = base_entry(ctx, lid)
        cands = M.candidates(law, facts)
        hs = M.hits(law, facts, model, cands, limit)
        labels = [lab for lab, _ in hs]
        env_of = dict(cands)
        e["hits"] = labels
        replay_calls = {}
        try:
            mres = unit_claims(ctx, u, law, [env for _, env in hs])
            ores = original_claims(ctx, law, [env for _, env in hs])
            e["replay"] = [{"label": lab, "mutant": mr["value"] is False, "original": orr["value"] is False}
                           for lab, mr, orr in zip(labels, mres, ores)]
            replay_calls = {lab: mr["calls"] for lab, mr in zip(labels, mres)}
        except Exception as ex:  # noqa: BLE001
            e["replay"] = None
            u.error("replay", [], f"{lid}: the replay of its hits failed: {ex}")
        witness = recorded_witness(e["replay"], labels)
        e["witness"] = witness
        if carry:
            e["own_input"] = {"sha256": b["own_input"]["sha256"], "changed": False}
            e["decided"] = "carried"
            pipe = b["mutant"]
        else:
            own = L.own_input_sha(law, {M.PROJECTION_KEY: proj_sha}, cones.get(lid, {}))
            e["own_input"] = {"sha256": own, "changed": (own != b["own_input"]["sha256"]) if b else False}
            e["decided"] = "run"
            pipe = recs[lid]["status"]
        status = "UNKNOWN"
        if pipe == "PROVED":
            status = "PROVED"
        elif witness is not None:
            try:
                e["counter_law"] = _retry(M.counter_law, law, facts, m0dir / "gen", env_of[witness])
                status = "REFUTED" if e["counter_law"]["marker"] == D.MARK_OK else "UNKNOWN"
            except Exception as ex:  # noqa: BLE001
                e["mutant"], e["error"] = "error", f"counter-law check failed: {ex}"[:500]
                u.error("counter_law", [lid], f"{lid}: {ex}")
                continue
        elif pipe == "REFUTED":
            e["mutant"], e["error"] = "error", "the run refuted the law but the model shows no hit"
            u.error("M0", [lid], f"{lid}: the run refuted the law but the model shows no hit")
            continue
        if carry and status != b["mutant"]:
            e["mutant"], e["error"] = "error", f"carried status {b['mutant']} but the model decides {status}"
            u.error("M0", [lid], f"{lid}: carried status {b['mutant']} but the model decides {status}")
            continue
        e["mutant"] = status
        if (b and b["mutant"] == "PROVED") or (u.is_base and status == "PROVED"):
            if carry:
                e["proof"] = dict(b["proof"])
            else:
                gen = (b.get("proof") or {}).get("generator") if b else _accepted_generator(recs[lid])
                pa = None
                for _ in range(STEP_RETRY):
                    pa = M.proof_attempt(law, facts, m0dir / "gen", gen)
                    if pa["exit_code"] is not None and pa["verdict"] is not None:
                        break
                if mverdict is None:
                    mverdict = M.model_verdict(m0dir / "gen" / "model" / f"{M.MODEL_NAME}.bend")
                e["proof"] = {"generator": gen, "exit_code": pa["exit_code"], "marker": pa["marker"],
                              "verdict": pa["verdict"], "model_verdict": mverdict}
                if status == "UNKNOWN" and b and b["mutant"] == "PROVED":
                    why = pa["why"]
                    if why is None and pa["verdict"] == D.MARK_OK:
                        why = "the baseline generator's proof checks but the run left the law UNKNOWN"
                    if why is None and mverdict != D.MARK_OK:
                        why = f"the generated model alone does not check ({mverdict})"
                    if why is not None:          # not_K2: a law-level error, never K2
                        e["mutant"], e["error"] = "error", why
                        u.error("proof_check", [lid], f"{lid}: {why}")
                        continue
                    if e["own_input"]["changed"] is True:
                        try:
                            falsifier(ctx, u, law, e, cands, facts, model, limit)
                        except Exception as ex:  # noqa: BLE001
                            e["mutant"], e["error"] = "error", f"the K2 (c) search failed: {ex}"[:500]
                            u.error("falsifier", [lid], f"{lid}: {ex}")
                            continue
        if e["witness"] is not None:
            e["witness_fits_entry"] = fits_entry(ctx, u, replay_calls.get(e["witness"]) or [])
        elif e["falsifier"] is not None:
            e["witness_fits_entry"] = fits_entry(ctx, u, e.get("_fcalls") or [])
        e.pop("_fcalls", None)


def base_model(ctx: Ctx):
    """The baseline model: the committed projection compiled for the refuter (holon.refute's own evaluation)."""
    if ctx._base_model is None:
        from . import m0 as M
        ctx._base_model = M.compiled(ctx.root / C.PROJECTED, ctx.work / "_baseline_model")
    return ctx._base_model


def falsifier(ctx: Ctx, u: Unit, law: dict, e: dict, cands: list, facts: dict, model, limit: int) -> None:
    """K2 (c): among the first replay_candidates candidates (refuter order) a falsification (the claim false on the
    unit's code, not false on the original), else a partiality witness (replay.partiality); its model tie
    (replay.model_tied)."""
    from . import m0 as M
    first = cands[:limit]
    envs = [env for _, env in first]
    mres = unit_claims(ctx, u, law, envs)
    ores = original_claims(ctx, law, envs)
    found = None
    for i, (mr, orr) in enumerate(zip(mres, ores)):
        if mr["value"] is False and orr["value"] is not False:
            found = (i, "falsification", None, None)
            break
    if found is None:
        sol = ctx.inst["roles"]["solidity"]
        for i, (mr, orr) in enumerate(zip(mres, ores)):
            if not M.premises_hold(law, first[i][1]):
                continue
            if not orr["calls"] or any(c["result"]["kind"] != "value" for c in orr["calls"]):
                continue
            for c in mr["calls"]:
                res = c["result"]
                if c["role"] in sol and res["kind"] == "revert" and res.get("revert_line") in sol[c["role"]]["revert_lines"]:
                    same = [o for o in orr["calls"] if o["role"] == c["role"] and C.compact(o["arg"]) == C.compact(c["arg"])]
                    if same and all(o["result"]["kind"] != "revert" for o in same):
                        found = (i, "partiality", c["role"], res["revert_line"])
                        break
            if found is not None:
                break
    if found is None:
        return
    i, kind, role, line = found
    label, env = first[i]
    mv = M.model_values(law, facts, model, [env])[0]
    bf = json.loads((ctx.root / C.PROJECTED).read_text())
    bv = M.model_values(law, bf, base_model(ctx), [env])[0]
    tied = (mv is None or not M.claim_true(mv)) and (bv is not None and M.claim_true(bv))
    e["falsifier"] = {"label": label, "tried": i + 1, "kind": kind, "model_tied": bool(tied), "role": role,
                      "revert_line": line}
    e["_fcalls"] = mres[i]["calls"]


# ------------------------------------------------------------------------------------------------ the trace laws
_VIEW_SCRIPT = r"""
import json, sys
from pathlib import Path
from holon import differential as D, window as W
root = Path.cwd()
decls = [(p, d) for p, d in W.declarations(root) if p.relative_to(root).parts[1] == "M2"]
views = [view for _drel, _decl, _facts, _ab, _deltas, view in D._plan("M2", root, decls, False)]
if len(views) != 1:
    sys.exit("expected one window declaration of M2, found %d" % len(views))
Path(sys.argv[1]).write_text(views[0])
"""


def window_view(u: Unit) -> str:
    """The window view of the unit's rollup document (holon differential steps 1-2, in the scratch tree)."""
    out = u.dir / "m1x_view.json"
    env = C.env_tools()
    env["PYTHONPATH"] = str(u.H)
    last = None
    for _ in range(STEP_RETRY):
        p = subprocess.run([sys.executable, "-c", _VIEW_SCRIPT, str(out)], cwd=str(u.H), env=env, capture_output=True,
                           text=True, timeout=3600)
        if p.returncode == 0 and out.is_file():
            return out.read_text()
        last = (p.stdout + p.stderr)[-1500:]
    raise C.MutateError(f"the window view: {last}")


def _attempt_entry(rec: dict, generator: str) -> dict | None:
    xs = [a for a in rec.get("attempts", []) if a.get("kind") == "proof" and a.get("generator") == generator]
    return xs[-1] if xs else None


def _verdict(a: dict | None):
    """The first line of the checker's output of a recorded attempt: the accepted attempt's marker, else the first
    line of its recorded error when it is a marker."""
    if a is None or a.get("exit_code") is None:
        return None
    if a.get("marker") == D.MARK_OK and "error" not in a:
        return D.MARK_OK
    first = (a.get("error") or "").strip().splitlines()
    return first[0].strip() if first and first[0].strip() in (D.MARK_OK, D.MARK_FAIL) else None


def trace_counter_laws(run_rec: dict, labels: list) -> dict:
    """{witness label: {exit_code, marker}} of a trace law's run record: an M2 SORT-site law checks one counter-law per
    entry point (attempt "entry"), an M1x law one for its witness."""
    cls = [a for a in run_rec.get("attempts", []) if a.get("kind") == "counter-law"]
    out = {}
    for lab in labels:
        mine = [a for a in cls if a.get("entry") == lab] or [a for a in cls if "entry" not in a]
        if mine:
            out[lab] = {"exit_code": mine[-1].get("exit_code"), "marker": mine[-1].get("marker")}
    return out


def trace_replay(ctx: Ctx, u: Unit, e: dict, law: dict, traces: list) -> None:
    labels = [lab for lab, _ in traces]
    e["hits"] = labels
    try:
        mres = unit_traces(ctx, u, law, [t for _, t in traces])
        ores = original_traces(ctx, law, [t for _, t in traces])
        e["replay"] = [{"label": lab, "mutant": mr is False, "original": orr is False}
                       for lab, mr, orr in zip(labels, mres, ores)]
    except Exception as ex:  # noqa: BLE001
        e["replay"] = None
        u.error("replay", [], f"{law['law_id']}: the trace replay failed: {ex}")
    e["witness"] = recorded_witness(e["replay"], labels)
    if e["witness"] is not None:
        e["witness_fits_entry"] = True   # a trace runs through the public entry points: it fits by construction


def trace_entry(ctx: Ctx, u: Unit, e: dict, law: dict, traces: list, run_rec: dict | None, model_bend: Path | None,
                base_gen: str | None, carried_from: dict | None = None, counters: dict | None = None) -> None:
    """Hits, replay, witness, counter-law and proof of a trace law (M1x or M2) whose status is set: from the unit's run
    record, or (carried_from: the baseline's entry, counters: its counter-laws by witness label) as a run would give
    them on the same inputs."""
    trace_replay(ctx, u, e, law, traces)
    if carried_from is not None:
        if e["mutant"] == "REFUTED" and e["witness"] is not None:
            e["counter_law"] = (counters or {}).get(e["witness"])
        if carried_from.get("proof") is not None:
            e["proof"] = dict(carried_from["proof"])
        return
    if run_rec is not None and e["mutant"] == "REFUTED" and e["witness"] is not None:
        e["counter_law"] = trace_counter_laws(run_rec, [e["witness"]]).get(e["witness"])
    if run_rec is not None and base_gen and (e["baseline"] == "PROVED" or (u.is_base and e["mutant"] == "PROVED")):
        a = _attempt_entry(run_rec, base_gen)
        mv = model_verdict(model_bend) if model_bend is not None and Path(model_bend).is_file() else None
        e["proof"] = {"generator": base_gen, "exit_code": (a or {}).get("exit_code"),
                      "marker": (a or {}).get("marker", "not_run"), "verdict": _verdict(a), "model_verdict": mv}
        if e["mutant"] == "UNKNOWN" and e["baseline"] == "PROVED" and not u.is_base:
            pr = e["proof"]
            why = None
            if pr["exit_code"] is None:
                why = "the baseline generator did not complete on the unit"
            elif pr["verdict"] is None:
                why = "the checker gave no verdict line"
            elif pr["verdict"] == D.MARK_FAIL and mv != D.MARK_OK:
                why = f"the generated model alone does not check ({mv})"
            if why is not None:
                e["mutant"], e["error"] = "error", why
                u.error("proof_check", [law["law_id"]], f"{law['law_id']}: {why}")
            # K2 (c) for a trace law: holon.refute's candidate space is the M0 refuter's; a trace law has none here,
            # so no falsifier is searched (an M1x or M2 law cannot lose its proof at this pipeline: limitations)


def decide_m1x(ctx: Ctx, u: Unit, rec: dict, pred: set, errs: dict) -> None:
    inst = ctx.inst
    ids = sorted(inst["baseline"]["M1x"])
    laws1 = {lid: json.loads((ctx.root / "laws" / "M1" / f"{lid}.json").read_text()) for lid in ids}
    entries = {}
    for lid in ids:
        b = base_entry(ctx, lid)
        e = L.entry("M1x", "M1x:" + laws1[lid]["rule"], b["mutant"] if b else "absent")
        e["predicted"] = lid in pred
        entries[lid] = e
    rec["laws"].update(entries)
    rollup = f"{C.FACTS2.as_posix()}/morph_rollup.extracted.json"
    if rollup in errs:
        for e in entries.values():
            e["mutant"], e["error"] = "error", "extraction failed: " + rollup
        u.error("extraction", list(entries), errs[rollup])
        return
    try:
        view = window_view(u)
    except Exception as ex:  # noqa: BLE001
        for e in entries.values():
            e["mutant"], e["error"] = "error", str(ex)[:500]
        u.error("M1x", list(entries), str(ex))
        return
    view_sha = C.normalized_sha256(json.loads(view))
    bc = ((ctx.inputs or {}).get("cones") or {}).get("M1x") or {}
    carry = ctx.carry and not u.is_base and all(
        base_entry(ctx, lid) and L.own_input_sha(laws1[lid], {L.VIEW: view_sha}, bc.get(lid, {}))
        == base_entry(ctx, lid)["own_input"]["sha256"] for lid in ids)
    model_bend = u.H / "gen" / "M2" / "extracted" / "m1" / "model" / "m1_view.bend"
    if carry:
        tr = ((ctx.inputs or {}).get("traces") or {})
        cl = ((ctx.inputs or {}).get("counter_laws") or {})
        for lid in ids:
            b, e = base_entry(ctx, lid), entries[lid]
            e["mutant"], e["decided"] = b["mutant"], "carried"
            e["own_input"] = {"sha256": b["own_input"]["sha256"], "changed": False}
            trace_entry(ctx, u, e, laws1[lid], [tuple(x) for x in tr.get(lid, [])], None, None, None,
                        carried_from=b, counters=cl.get(lid))
        return
    p = None
    for _ in range(STEP_RETRY):
        p = S.holon(u.H, ["differential", "--milestone", "M2", "--root", u.H], timeout=7200)
        if p.returncode == 0:
            break
    if p.returncode != 0:
        msg = f"holon differential (exit {p.returncode}): {S._tail(p)}"
        for e in entries.values():
            e["mutant"], e["error"] = "error", msg[:500]
        u.error("M1x", list(entries), msg)
        return
    rdir = u.H / "results" / "M2" / "extracted_m1"
    cones = L.cones(rdir / "deps.json", u.H / "gen" / "M2" / "extracted" / "m1" / "model" / "m1_view.defs.json")
    u.m1x_cones = cones
    for lid in ids:
        e = entries[lid]
        b = base_entry(ctx, lid)
        r = json.loads((rdir / f"{lid}.json").read_text())
        own = L.own_input_sha(laws1[lid], {L.VIEW: view_sha}, cones.get(lid, {}))
        e["own_input"] = {"sha256": own, "changed": (own != b["own_input"]["sha256"]) if b else False}
        e["decided"] = "run"
        e["mutant"] = r["status"]
        gen = (b.get("proof") or {}).get("generator") if b else _accepted_generator(r)
        traces = L.m1_traces(laws1[lid], r) if r["status"] == "REFUTED" else []
        u.__dict__.setdefault("traces", {})[lid] = traces
        u.__dict__.setdefault("counter_laws", {})[lid] = trace_counter_laws(r, [lab for lab, _ in traces])
        trace_entry(ctx, u, e, laws1[lid], traces, r, model_bend, gen)


def decide_m2(ctx: Ctx, u: Unit, rec: dict, pred: set, actions: set, errs: dict, where,
              widths: str | None = None) -> None:
    """laws/M2 as `holon derive` re-derives it over the unit's documents, decided by `holon run --milestone M2
    --no-registry` (carrying, matching: instrument law_sets.M2)."""
    base_der = L.derivation(ctx.root)
    p = None
    for _ in range(STEP_RETRY):
        p = S.holon(u.H, ["derive", "--milestone", "M2", "--root", u.H], timeout=3600)
        if p.returncode == 0:
            break
    if p.returncode != 0:
        msg = f"holon derive (exit {p.returncode}): {S._tail(p)}"
        for lid in sorted(base_der):
            b = base_entry(ctx, lid)
            e = L.entry("M2", f"M2:{base_der[lid]['rule']}/{base_der[lid]['subform']}", b["mutant"] if b else "absent")
            e["entry_points"] = sorted(base_der[lid]["entry_points"])
            e["predicted"] = lid in pred
            e["mutant"], e["error"] = "error", msg[:500]
            rec["laws"][lid] = e
        u.error("M2", sorted(base_der), msg)
        return
    mut_der = L.derivation(u.H)
    pairs, new, missing = L.match(base_der, mut_der) if not u.is_base else ({k: k for k in mut_der}, [], [])
    bc = ((ctx.inputs or {}).get("cones") or {}).get("M2") or {}
    plan = []          # (record key, mutant law id, law file, entry)
    for key, mid in list(pairs.items()) + [(mid, mid) for mid in new]:
        d = mut_der[mid]
        b = base_entry(ctx, key) if key in base_der else None
        e = L.entry("M2", f"M2:{d['rule']}/{d['subform']}", (b["mutant"] if b else "absent") if key in base_der
                    else "absent")
        e["matched_from"] = mid if mid != key else None
        e["entry_points"] = sorted(d["entry_points"])
        e["basis_span"] = (d.get("basis") or {}).get("span")
        e["site_in_mutated_function"] = L.span_inside(e["basis_span"], where)
        if key in base_der and not u.is_base:
            e["predicted"] = key in pred
        elif key in base_der:
            e["predicted"] = False
        else:
            e["predicted"] = bool(set(e["entry_points"]) & actions)
        law = json.loads((u.H / "laws" / "M2" / f"{mid}.json").read_text())
        plan.append((key, mid, law, e))
        rec["laws"][key] = e
    for key in missing:
        b = base_entry(ctx, key)
        e = L.entry("M2", f"M2:{base_der[key]['rule']}/{base_der[key]['subform']}", b["mutant"] if b else "absent")
        e["entry_points"] = sorted(base_der[key]["entry_points"])
        e["basis_span"] = (base_der[key].get("basis") or {}).get("span")
        e["site_in_mutated_function"] = L.span_inside(e["basis_span"], where)
        e["predicted"] = key in pred and not u.is_base
        rec["laws"][key] = e            # mutant "absent": the unit's derivation has no such law
    facts_sha = {}

    def fsha(rel: str) -> str | None:
        if rel not in facts_sha:
            fp = u.H / rel
            facts_sha[rel] = C.normalized_sha256(json.loads(fp.read_text())) if fp.is_file() else None
        return facts_sha[rel]

    bad_docs = {d for d in errs}
    run_ids, carried = [], []
    for key, mid, law, e in plan:
        if law.get("facts") in bad_docs or fsha(law["facts"]) is None:
            e["mutant"], e["error"] = "error", f"extraction failed: {law.get('facts')}"
            u.error("extraction", [key], f"{key}: its facts document {law.get('facts')} did not extract")
            continue
        if widths is not None and mut_der[mid].get("subform") == "width":
            # a SORT-width law reads the width values of the unit's own i20_step run when its rollup document
            # changed (the contract's pipeline step 3); that run did not complete
            e["mutant"], e["error"] = "error", widths[:500]
            u.error("i20_step", [key], f"{key}: {widths}")
            continue
        b = base_entry(ctx, key) if e["baseline"] != "absent" else None
        cand = L.own_input_sha(law, {law["facts"]: fsha(law["facts"])}, bc.get(key, {}))
        if ctx.carry and not u.is_base and b is not None and cand == b["own_input"]["sha256"]:
            carried.append((key, mid, law, e))
        else:
            run_ids.append(mid)
    tr = ((ctx.inputs or {}).get("traces") or {})
    cl = ((ctx.inputs or {}).get("counter_laws") or {})
    for key, mid, law, e in carried:
        b = base_entry(ctx, key)
        e["mutant"], e["decided"] = b["mutant"], "carried"
        e["own_input"] = {"sha256": b["own_input"]["sha256"], "changed": False}
        trace_entry(ctx, u, e, law, [tuple(x) for x in tr.get(key, [])], None, None, None,
                    carried_from=b, counters=cl.get(key))
    if not run_ids:
        return
    rollup = f"{C.FACTS2.as_posix()}/morph_rollup.extracted.json"
    if rec["documents"].get(rollup, {}).get("changed") or u.is_base:
        p = None
        for _ in range(STEP_RETRY):
            p = S.holon(u.H, ["model", "--facts", rollup, "--out", "gen/M2/extracted"], timeout=3600)
            if p.returncode == 0:
                break
        if p.returncode != 0:
            msg = f"holon model (exit {p.returncode}): {S._tail(p)}"
            for key, mid, law, e in plan:
                if mid in run_ids:
                    e["mutant"], e["error"] = "error", msg[:500]
            u.error("M2", [k for k, mid, _, _ in plan if mid in run_ids], msg)
            return
    p = None
    for _ in range(STEP_RETRY):
        p = S.holon(u.H, ["run", "--milestone", "M2", "--no-registry", "--laws", ",".join(sorted(run_ids))],
                    timeout=7200)
        if p.returncode == 0:
            break
    if p.returncode != 0:
        msg = f"holon run --milestone M2 (exit {p.returncode}): {S._tail(p)}"
        for key, mid, law, e in plan:
            if mid in run_ids:
                e["mutant"], e["error"] = "error", msg[:500]
        u.error("M2", [k for k, mid, _, _ in plan if mid in run_ids], msg)
        return
    rdir = u.H / "results" / "M2"
    cones = {}
    if (rdir / "deps.json").is_file() and (u.H / "gen" / "M2" / "model" / "morph_rollup.defs.json").is_file():
        cones = L.cones(rdir / "deps.json", u.H / "gen" / "M2" / "model" / "morph_rollup.defs.json")
    u.m2_cones = cones
    model_bend = u.H / "gen" / "M2" / "model" / "morph_rollup.bend"
    for key, mid, law, e in plan:
        if mid not in run_ids or e["mutant"] == "error":
            continue
        r = json.loads((rdir / f"{mid}.json").read_text())
        b = base_entry(ctx, key) if e["baseline"] != "absent" else None
        own = L.own_input_sha(law, {law["facts"]: fsha(law["facts"])}, cones.get(mid, {}))
        e["own_input"] = {"sha256": own, "changed": (own != b["own_input"]["sha256"]) if b else
                          (False if u.is_base else True)}
        e["decided"] = "run"
        e["mutant"] = r["status"]
        gen = (b.get("proof") or {}).get("generator") if b else _accepted_generator(r)
        traces = L.m2_traces(r) if r["status"] == "REFUTED" else []
        u.__dict__.setdefault("traces", {})[key] = traces
        u.__dict__.setdefault("counter_laws", {})[key] = trace_counter_laws(r, [lab for lab, _ in traces])
        trace_entry(ctx, u, e, law, traces, r, model_bend, gen)


# ------------------------------------------------------------------------------------------------ the channels
def channel_wants(u: Unit) -> list[str]:
    """instrument channels: i20_step for the baseline and every stratum-A Solidity mutant; i16_edge for the baseline,
    every stratum-A Go mutant and every stratum-A Solidity mutant with edges; stratum B and the controls have none."""
    if u.is_base:
        return ["i16_edge", "i20_step"]
    if u.kind != "mutant" or u.m["stratum"] != "A":
        return []
    sol = u.lang() == "solidity"
    return sorted((["i20_step"] if sol else []) + (["i16_edge"] if (not sol or u.m["edges"]) else []))


def incomplete(harness: str, why: str) -> dict:
    return {"harness": harness, "steps": 0, "new_disagreements": [], "corpus_differences": None,
            "error": why[-1500:]}


def run_i20(ctx: Ctx, u: Unit, rec: dict, errs: dict) -> dict:
    from . import channels as CH
    rollup = f"{C.FACTS2.as_posix()}/morph_rollup.extracted.json"
    if rollup in errs:
        return incomplete("i20_step", "extraction failed: " + rollup)
    try:
        if u.is_base:
            out = ctx.work / "i20_corpus.json"      # outside the unit's scratch tree, which is removed after it
            res = _retry(CH.i20_baseline, u.H, u.tree, u.dir / "i20", out)
            u.i20_corpus = out
            return res
        return _retry(CH.i20_mutant, u.H, u.tree, u.dir / "i20", ctx.root / I20_CORPUS)
    except Exception as ex:  # noqa: BLE001
        return incomplete("i20_step", f"{type(ex).__name__}: {ex}")


def run_i16(ctx: Ctx, u: Unit, rec: dict) -> dict:
    from . import channels as CH
    if u.proj_path is None:
        return incomplete("i16_edge", "no projected document: " + str(rec["projection"]["error"]))
    try:
        base_ids = None if u.is_base else ((ctx.inputs or {}).get("i16_ids") or [])
        res, ids = _retry(CH.i16_edge, u.H, u.tree, u.dir / "i16", u.proj_path, base_ids)
        u.i16_ids = ids
        return res
    except Exception as ex:  # noqa: BLE001
        return incomplete("i16_edge", f"{type(ex).__name__}: {ex}")


def flags(u: Unit, rec: dict) -> None:
    """channels.flags: extraction_defect_detected and corpus_detected."""
    runs = rec["refinement"]["channels"]
    if rec["replay_disagreements"] or any(r["new_disagreements"] for r in runs):
        rec["extraction_defect_detected"] = True
    elif any(r["error"] for r in runs):
        rec["extraction_defect_detected"] = None
    else:
        rec["extraction_defect_detected"] = False
    rec["corpus_detected"] = None
    if u.kind == "mutant" and u.m["stratum"] == "A" and u.lang() == "solidity":
        i20 = [r for r in runs if r["harness"] == "i20_step"]
        if i20 and i20[0]["error"] is None:
            rec["corpus_detected"] = bool(i20[0]["corpus_differences"])


# ------------------------------------------------------------------------------------------------ the unit
def run_unit(ctx: Ctx, ud: dict, keep: bool = False) -> tuple[dict, Unit]:
    """One unit through the pipeline (module docstring); its record and its state (the baseline's inputs)."""
    u = Unit(ctx, ud)
    shutil.rmtree(u.dir, ignore_errors=True)
    u.dir.mkdir(parents=True)
    rec = skeleton(ctx, u)
    t0 = time.monotonic()
    try:
        u.tree, u.nm = S.source_tree(ud, u.dir, ctx.checkout, ctx.sol_deps)
        u.H = S.holon_tree(ctx.root, ctx.commit, u.dir / "holon", u.tree, u.nm)
        texts, errs, secs = S.extract(u.H, u.tree, u.dir / "docs")
        u.secs.update(secs)
        documents(ctx, u, rec, texts, errs)
        for d, msg in sorted(errs.items()):
            u.error("extraction", [], f"{d}: {msg}")
        pred, actions = predicted_sets(ctx, u)
        where = None
        if u.m is not None and u.lang() == "solidity":
            from .operators import mutated_function_lines
            where = mutated_function_lines(ctx.inst, u.m, u.tree, u.nm)
        projection(ctx, u, rec, errs)
        decide_m0(ctx, u, rec, pred["M0"])
        decide_m1x(ctx, u, rec, pred["M1x"], errs)
        wants = channel_wants(u)
        runs = []
        widths = None
        if "i20_step" in wants:
            r20 = run_i20(ctx, u, rec, errs)
            runs.append(r20)
            rollup = f"{C.FACTS2.as_posix()}/morph_rollup.extracted.json"
            if r20["error"] is not None and (u.is_base or rec["documents"].get(rollup, {}).get("changed")):
                widths = "the unit's i20_step run did not complete: " + r20["error"]
        elif u.lang() == "solidity" and not u.is_base:
            rollup = f"{C.FACTS2.as_posix()}/morph_rollup.extracted.json"
            if rec["documents"].get(rollup, {}).get("changed"):
                widths = "the rollup document changed and the unit has no i20_step run (no width values of its own)"
        decide_m2(ctx, u, rec, pred["M2"], actions, errs, where, widths)
        if "i16_edge" in wants:
            runs.append(run_i16(ctx, u, rec))
        rec["refinement"]["channels"] = sorted(runs, key=lambda r: r["harness"])
        if not u.is_base:
            from .operators import recompute
            try:
                rec["recomputed"] = recompute(ctx.inst, u.m, u.tree, u.nm, u.H)
            except Exception as ex:  # noqa: BLE001
                rec["recomputed"] = {"edges": [], "actions": [], "predicted": {"M0": [], "M1x": [], "M2": []}}
                u.error("recompute", [], f"the recomputed edges, actions and predicted sets: {ex}")
    except Exception as ex:  # noqa: BLE001: a unit-level failure marks every law its paths decide
        tb = traceback.format_exc()
        ctx.log(f"{u.id}: unit failure: {tb[-3000:]}")
        why = f"{type(ex).__name__}: {ex}"[:500]
        for law, b in sorted(((ctx.base or {}).get("laws") or {}).items()):
            if law not in rec["laws"]:
                e = L.entry(b["set"], b["family"], b["mutant"])
                e["entry_points"] = b["entry_points"]
                e["predicted"] = u.kind == "mutant" and law in set().union(*map(set, u.m["predicted"].values()))
                rec["laws"][law] = e
        undecided = [law for law, e in rec["laws"].items() if e["mutant"] == "absent" and e["decided"] is None]
        for law in undecided:
            rec["laws"][law]["mutant"], rec["laws"][law]["error"] = "error", why
        u.error("unit", undecided, why)
    finally:
        u.close()
    rec["errors"] = sorted(u.errors, key=lambda x: (x["step"], x["laws"], x["message"]))
    rec["laws"] = {k: rec["laws"][k] for k in sorted(rec["laws"])}
    if u.is_base:      # the baseline is its own reference: its statuses fill every record's "baseline"
        for e in rec["laws"].values():
            e["baseline"] = e["mutant"]
    eq = None
    if u.kind == "mutant":
        v = (ctx.equivalent or {}).get(u.id)
        eq = bool(v) if v is not None else False
    D.finish(rec, eq)
    flags(u, rec)
    ctx.log(f"{u.id}: {rec['outcome']} ({', '.join(f'{x['law']} {x['how']}' for x in rec['kill']['by']) or '-'}) "
            f"in {time.monotonic() - t0:.0f} s; steps {u.secs}")
    if not keep:
        shutil.rmtree(u.dir, ignore_errors=True)
    return rec, u


def baseline_inputs(u: Unit, rec: dict) -> dict:
    """What later units read from the baseline beside its record (gen/M2/mutation_i61/baseline_inputs.json)."""
    return {"document": "I61 baseline inputs", "pipeline_commit": rec["pipeline_commit"],
            "cones": {"M1x": getattr(u, "m1x_cones", {}), "M2": getattr(u, "m2_cones", {})},
            "traces": {k: [[lab, t] for lab, t in v] for k, v in sorted(getattr(u, "traces", {}).items()) if v},
            "counter_laws": {k: v for k, v in sorted(getattr(u, "counter_laws", {}).items()) if v},
            "i16_ids": sorted(getattr(u, "i16_ids", []) or [])}


# ================================================================================================ run
def _ids(text: str | None) -> list | None:
    if text is None:
        return None
    return [x.strip() for x in text.split(",") if x.strip()]


def write_record(root: Path, unit: dict, rec: dict) -> Path:
    p = root / record_path(unit)
    C.write_text(p, C.dump(rec))
    return p


def strip_decided(rec: dict) -> dict:
    r = json.loads(json.dumps(rec))
    for e in (r.get("laws") or {}).values():
        e.pop("decided", None)
    return r


def cmd_run(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="holon mutate run")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--only")
    ap.add_argument("--control")
    ap.add_argument("--baseline-only", action="store_true")
    ap.add_argument("--work")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--no-carry", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep each unit's scratch tree (debugging)")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    if a.milestone != "M2":
        print(f"holon mutate run: refused: milestone {a.milestone} (I61 runs on M2)", file=sys.stderr)
        return 2
    root = C.ROOT
    inst = C.instrument(root)
    try:
        commit = C.pipeline_commit(root)
    except C.MutateError as e:
        print(f"holon mutate run: refused: {e}", file=sys.stderr)
        return 2
    only, controls = _ids(a.only), _ids(a.control) or []
    if a.check:
        return run_check(root, inst, only or [], a)
    catalog = only if only is not None else ([] if (controls or a.baseline_only) else [m["id"] for m in inst["mutants"]])
    try:
        todo = units(inst, catalog, controls, baseline=a.baseline_only)
    except C.MutateError as e:
        print(f"holon mutate run: refused: {e}", file=sys.stderr)
        return 2
    problems = check_target(root, inst) + clean_tree(root)
    got = {}
    if catalog:
        bad, got = preconditions(root, inst, commit)
        problems += bad
    elif controls and not (root / C.RESULTS / "baseline.json").is_file():
        problems.append(f"{C.RESULTS / 'baseline.json'}: missing (a control is decided against the baseline)")
    if problems:
        for x in problems:
            print(f"holon mutate run: refused: {x}", file=sys.stderr)
        return 2
    if a.dry_run:
        print(f"holon mutate run: dry run: every input checks ({len(todo)} units at {commit})")
        return 0
    if a.jobs > 1 and len(catalog) > 1:
        return run_jobs(root, catalog, a)
    work = Path(a.work).resolve() if a.work else C.scratch_dir("holon-mutate-")
    ctx = Ctx(root, work, carry=not a.no_carry)
    try:
        if a.baseline_only:
            ctx.log(f"baseline at {commit}")
            rec, u = run_unit(ctx, todo[0], keep=a.keep)
            write_record(root, todo[0], rec)
            C.write_text(root / INPUTS, C.dump(baseline_inputs(u, rec)))
            corpus = work / "i20_corpus.json"
            if corpus.is_file():
                C.write_text(root / I20_CORPUS, corpus.read_text())
            todo = todo[1:]
        ctx.load_baseline()
        if todo and (ctx.base is None or ctx.inputs is None):
            print("holon mutate run: refused: no baseline record and inputs (run --baseline-only first)",
                  file=sys.stderr)
            return 2
        if catalog:
            adj = got.get("adjudication") or json.loads((root / C.ADJUDICATION).read_text())
            ctx.equivalent = {i: v["equivalent"] for i, v in adj["verdicts"].items()}
        for ud in todo:
            rec, _ = run_unit(ctx, ud, keep=a.keep)
            write_record(root, ud, rec)
    finally:
        ctx.close()
        if not a.work and not a.keep:
            shutil.rmtree(work, ignore_errors=True)
    return 0


def run_jobs(root: Path, catalog: list, a) -> int:
    """--jobs N: the catalog split into N contiguous chunks, each run by its own `holon mutate run --only` process."""
    n = max(1, min(a.jobs, len(catalog)))
    chunks = [catalog[k::n] for k in range(n)]
    base = Path(a.work).resolve() if a.work else C.scratch_dir("holon-mutate-jobs-")
    procs = []
    for k, ch in enumerate(chunks):
        cmd = [sys.executable, "-m", "holon", "mutate", "run", "--milestone", "M2", "--only", ",".join(ch),
               "--work", str(base / f"job{k}")] + (["--no-carry"] if a.no_carry else [])
        procs.append(subprocess.Popen(cmd, cwd=str(root), env=C.env_tools()))
    codes = [p.wait() for p in procs]
    if not a.work:
        shutil.rmtree(base, ignore_errors=True)
    return 0 if all(c == 0 for c in codes) else max(codes)


def run_check(root: Path, inst: dict, ids: list, a) -> int:
    """run --check: materialize the tree of the records' pipeline commit (a detached worktree), rerun there the
    baseline and the listed units with --no-carry, and compare with the committed records byte for byte except each
    law's "decided" field. Exit 0 iff equal."""
    bp = root / C.RESULTS / "baseline.json"
    if not bp.is_file():
        print("holon mutate run --check: refused: no committed baseline record", file=sys.stderr)
        return 2
    commit = json.loads(bp.read_text())["pipeline_commit"]
    scratch = C.scratch_dir("holon-mutate-check-", Path(a.work).resolve() if a.work else None)
    tree = scratch / "tree"
    p = _git(root, "worktree", "add", "--detach", str(tree), commit)
    if p.returncode != 0:
        print(f"holon mutate run --check: refused: git worktree add {commit}: {p.stderr.strip()}", file=sys.stderr)
        return 2
    diffs = []
    try:
        for rel in (C.REVIEW, C.ADJUDICATION, C.GATE):
            if (root / rel).is_file() and not (tree / rel).is_file():
                (tree / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / rel, tree / rel)
        env = C.env_tools()
        env["PYTHONPATH"] = str(tree)
        steps = [["--baseline-only"]] + ([["--only", ",".join(i for i in ids if not i.startswith("C"))]]
                                         if any(not i.startswith("C") for i in ids) else []) \
            + ([["--control", ",".join(i for i in ids if i.startswith("C"))]] if any(i.startswith("C") for i in ids)
               else [])
        for k, extra in enumerate(steps):
            q = subprocess.run([sys.executable, "-m", "holon", "mutate", "run", "--milestone", "M2", "--no-carry",
                                "--work", str(scratch / f"w{k}"), *extra], cwd=str(tree), env=env,
                               capture_output=True, text=True)
            if q.returncode != 0:
                print(f"holon mutate run --check: the rerun {' '.join(extra)} failed (exit {q.returncode}): "
                      f"{(q.stdout + q.stderr)[-2000:]}", file=sys.stderr)
                return 1
        units_ = [{"id": BASELINE, "kind": "baseline"}] + \
                 [{"id": i, "kind": "control" if i.startswith("C") else "mutant"} for i in ids]
        for ud in units_:
            rel = record_path(ud)
            old, new = root / rel, tree / rel
            if not old.is_file():
                diffs.append(f"{rel}: not committed")
                continue
            if C.dump(strip_decided(json.loads(old.read_text()))) != C.dump(strip_decided(json.loads(new.read_text()))):
                a_ = strip_decided(json.loads(old.read_text()))
                b_ = strip_decided(json.loads(new.read_text()))
                laws = sorted(k for k in set(a_.get("laws", {})) | set(b_.get("laws", {}))
                              if a_.get("laws", {}).get(k) != b_.get("laws", {}).get(k))
                keys = sorted(k for k in set(a_) | set(b_) if k != "laws" and a_.get(k) != b_.get(k))
                diffs.append(f"{rel}: differs (laws {laws}, fields {keys})")
    finally:
        _git(root, "worktree", "remove", "--force", str(tree))
        if not a.work:
            shutil.rmtree(scratch, ignore_errors=True)
    for d in diffs:
        print(f"holon mutate run --check: {d}", file=sys.stderr)
    if not diffs:
        print(f"holon mutate run --check: the baseline and {len(ids)} units reproduce at {commit}")
    return 1 if diffs else 0


# ================================================================================================ the harness gate
def gate_i16(ctx: Ctx) -> dict:
    """harness_gate.checks.i16: `holon mutate replay --i16` reproduces I16's real outputs on every edge."""
    p = subprocess.run([sys.executable, "-m", "holon", "mutate", "replay", "--i16"], cwd=str(ctx.root),
                       env=C.env_tools(), capture_output=True, text=True, timeout=7200)
    if p.returncode != 0:
        return {"passed": False, "detail": f"holon mutate replay --i16 exit {p.returncode}: {(p.stdout + p.stderr)[-800:]}"}
    try:
        got = json.loads(p.stdout)
    except ValueError:
        return {"passed": False, "detail": "holon mutate replay --i16 printed no JSON: " + p.stdout[-300:]}
    bad, parts = [], []
    for edge in sorted(json.loads((ctx.root / "replay" / "M2" / "implementations.json").read_text())["edges"]):
        rec = json.loads((ctx.root / "results" / "M2" / "refinement" / f"{edge}.json").read_text())
        want = (rec["compared"], rec["outputs_sha256"]["real"])
        have = ((got.get(edge) or {}).get("compared"), (got.get(edge) or {}).get("outputs_sha256"))
        parts.append(f"{edge} {have[0]}/{want[0]}")
        if have != want:
            bad.append(f"{edge}: {have} != I16's {want}")
    return {"passed": not bad, "detail": ("reproduces I16's real outputs: " + ", ".join(parts)) if not bad
            else "; ".join(bad)}


def gate_model(ctx: Ctx) -> dict:
    """harness_gate.checks.model: on the original code, every role call of every laws/M0 statement at every candidate
    of its candidate space whose value in the baseline model (the committed projection) is defined has a harness value
    equal to it; undefined model values are counted, not compared."""
    from . import m0 as M
    from .. import facts as F
    from ..model_eval import ModelError, value_in, value_out
    facts = json.loads((ctx.root / C.PROJECTED).read_text())
    model = base_model(ctx)
    n = {"calls": 0, "compared": 0, "equal": 0, "undefined": 0}
    bad = []
    for lid, law in M.laws(ctx.root).items():
        cands = M.candidates(law, facts)
        res = original_claims(ctx, law, [env for _, env in cands])
        calls = [(lab, c) for (lab, _), r in zip(cands, res) for c in r["calls"]]
        by_role: dict = {}
        for lab, c in calls:
            by_role.setdefault(c["role"], []).append((lab, c))
        for role, xs in sorted(by_role.items()):
            if role not in facts["functions"]:
                continue
            arg_t, res_t = F.fn_types(facts, role)
            jobs = [{"terms": [{"call": role, "args": [{"var": "x"}]}], "env": {"x": value_in(arg_t, c["arg"], facts)}}
                    for _, c in xs]
            outs = model.run_jobs(jobs)
            for (lab, c), (v,) in zip(xs, outs):
                n["calls"] += 1
                try:
                    mv = value_out(res_t, v)
                except (ValueError, ModelError):
                    n["undefined"] += 1
                    continue
                n["compared"] += 1
                r = c["result"]
                if r["kind"] == "value" and C.compact(r["value"]) == C.compact(mv):
                    n["equal"] += 1
                else:
                    bad.append(f"{lid} {lab} {role}: harness {r['kind']} {str(r.get('value'))[:80]} != model "
                               f"{str(mv)[:80]}")
    detail = (f"{n['calls']} role calls over every candidate of the 8 statements: {n['compared']} compared, "
              f"{n['equal']} equal, {n['undefined']} undefined in the model")
    if bad:
        detail += f"; {len(bad)} differ: " + "; ".join(bad[:8])
    return {"passed": not bad and n["compared"] > 0, "detail": detail}


def gate_null(ctx: Ctx) -> dict:
    """harness_gate.checks.null: on the original code no PROVED M0 law's claim is false at any candidate of its
    candidate space, and every REFUTED M0 law's recorded witness (results/M0) makes its claim false."""
    from . import m0 as M
    facts = json.loads((ctx.root / C.PROJECTED).read_text())
    bad, parts = [], []
    for lid, law in M.laws(ctx.root).items():
        st = ctx.inst["baseline"]["M0"][lid]
        if st == "PROVED":
            cands = M.candidates(law, facts)
            res = original_claims(ctx, law, [env for _, env in cands])
            false = [lab for (lab, _), r in zip(cands, res) if r["value"] is False]
            none = sum(1 for r in res if r["value"] is None)
            parts.append(f"{lid} PROVED: {len(cands)} candidates, {len(false)} false, {none} no execution")
            if false:
                bad.append(f"{lid}: false at {false[:5]}")
        elif st == "REFUTED":
            w = json.loads((ctx.root / "results" / "M0" / f"{lid}.json").read_text())["witness"]
            r = original_claims(ctx, law, [w])[0]
            parts.append(f"{lid} REFUTED: its witness gives {r['value']}")
            if r["value"] is not False:
                bad.append(f"{lid}: its recorded witness gives {r['value']}, not false")
    return {"passed": not bad, "detail": "; ".join(bad) if bad else "; ".join(parts)}


def gate_controls(ctx: Ctx, keep: bool = False) -> dict:
    """harness_gate.checks.controls: each planted control through the per-mutant pipeline, killed through every law
    its 'expected' names by the 'how' it names; records results/M2/mutation_i61/controls/<id>.json."""
    bad, parts = [], []
    for c in ctx.inst["harness_gate"]["controls"]:
        ud = {"id": c["id"], "kind": "control", "mutant": c}
        rec, _ = run_unit(ctx, ud, keep=keep)
        write_record(ctx.root, ud, rec)
        how = {x["law"]: x["how"] for x in rec["kill"]["by"]}
        exp = c["expected"]
        miss = [law for law in exp["laws"] if how.get(law) != exp["how"]]
        if "falsifier" in exp:
            miss += [law for law in exp["laws"] if law not in miss and
                     ((rec["laws"].get(law) or {}).get("falsifier") or {}).get("kind") != exp["falsifier"]]
        ok = rec["outcome"] == exp["outcome"] and not miss
        parts.append(f"{c['id']} {rec['outcome']} by {sorted(how.items())}")
        if not ok:
            bad.append(f"{c['id']}: outcome {rec['outcome']}, expected {exp['outcome']} by {exp['how']} through "
                       f"{exp['laws']}; missing {miss}; errors {[e['message'][:120] for e in rec['errors']][:3]}")
    return {"passed": not bad, "detail": "; ".join(bad) if bad else "; ".join(parts)}


def cmd_gate(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="holon mutate gate")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fix", help="the fix of holon/mutate this attempt follows (required after a failed attempt)")
    ap.add_argument("--work")
    ap.add_argument("--keep", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    root = C.ROOT
    inst = C.instrument(root)
    commit = C.pipeline_commit(root)
    if a.check:
        return gate_check(root, a)
    problems = check_target(root, inst) + clean_tree(root)
    bad, _ = check_baseline(root, inst, commit)
    problems += bad
    if not (root / INPUTS).is_file():
        problems.append(f"{INPUTS}: missing (run --baseline-only first)")
    gp = root / C.GATE
    g = None
    if gp.is_file():
        g = json.loads(gp.read_text())
        if g.get("instrument") != C.instrument_ref(root):
            problems.append(f"{C.GATE}: names another instrument")
        elif g.get("passed") is True:
            problems.append(f"{C.GATE}: the gate has passed; attempts stop at the first that passes")
        elif not (a.fix or "").strip():
            problems.append(f"{C.GATE}: a re-run after a failed attempt names its fix (--fix)")
    if problems:
        for x in problems:
            print(f"holon mutate gate: refused: {x}", file=sys.stderr)
        return 2
    work = Path(a.work).resolve() if a.work else C.scratch_dir("holon-mutate-gate-")
    ctx = Ctx(root, work)
    ctx.load_baseline()
    try:
        checks = {}
        for name, fn in (("i16", gate_i16), ("model", gate_model), ("null", gate_null)):
            try:
                checks[name] = fn(ctx)
            except Exception as ex:  # noqa: BLE001
                checks[name] = {"passed": False, "detail": f"{type(ex).__name__}: {ex}"[:1500]}
            ctx.log(f"gate {name}: {checks[name]['passed']}: {checks[name]['detail'][:300]}")
        try:
            checks["controls"] = gate_controls(ctx, keep=a.keep)
        except Exception as ex:  # noqa: BLE001
            checks["controls"] = {"passed": False, "detail": f"{type(ex).__name__}: {ex}"[:1500]}
        ctx.log(f"gate controls: {checks['controls']['passed']}: {checks['controls']['detail'][:300]}")
    finally:
        ctx.close()
        if not a.work and not a.keep:
            shutil.rmtree(work, ignore_errors=True)
    attempt = {"pipeline_commit": commit, "checks": checks, "passed": all(c["passed"] for c in checks.values()),
               "fix": (a.fix.strip() if (g is not None and a.fix) else None)}
    g = g or {"instrument": C.instrument_ref(root), "attempts": []}
    g["attempts"].append(attempt)
    g["pipeline_commit"] = commit
    g["passed"] = attempt["passed"]
    C.write_text(gp, C.dump(g))
    print(f"holon mutate gate: attempt {len(g['attempts'])} at {commit}: "
          f"{'passed' if attempt['passed'] else 'FAILED'}")
    return 0 if attempt["passed"] else 1


def gate_check(root: Path, a) -> int:
    """gate --check: rerun the last attempt's checks at its pipeline commit (a detached worktree with the committed
    baseline record and inputs) and compare the checks and the controls' records with the committed ones."""
    gp = root / C.GATE
    if not gp.is_file():
        print(f"holon mutate gate --check: refused: {C.GATE} missing", file=sys.stderr)
        return 2
    g = json.loads(gp.read_text())
    commit = g["pipeline_commit"]
    scratch = C.scratch_dir("holon-mutate-gate-check-", Path(a.work).resolve() if a.work else None)
    tree = scratch / "tree"
    p = _git(root, "worktree", "add", "--detach", str(tree), commit)
    if p.returncode != 0:
        print(f"holon mutate gate --check: refused: git worktree add {commit}: {p.stderr.strip()}", file=sys.stderr)
        return 2
    diffs = []
    try:
        for rel in (C.RESULTS / "baseline.json", INPUTS, I20_CORPUS):
            if (root / rel).is_file():
                (tree / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / rel, tree / rel)
        env = C.env_tools()
        env["PYTHONPATH"] = str(tree)
        q = subprocess.run([sys.executable, "-m", "holon", "mutate", "gate", "--work", str(scratch / "w")],
                           cwd=str(tree), env=env, capture_output=True, text=True)
        if q.returncode not in (0, 1):
            print(f"holon mutate gate --check: the rerun failed (exit {q.returncode}): {(q.stdout + q.stderr)[-2000:]}",
                  file=sys.stderr)
            return 1
        new = json.loads((tree / C.GATE).read_text())
        if new["attempts"][-1]["checks"] != g["attempts"][-1]["checks"]:
            diffs.append("the checks differ: " + str(sorted(k for k in g["attempts"][-1]["checks"]
                                                            if new["attempts"][-1]["checks"].get(k)
                                                            != g["attempts"][-1]["checks"][k])))
        for c in C.instrument(root)["harness_gate"]["controls"]:
            rel = C.CONTROLS / f"{c['id']}.json"
            if (root / rel).read_text() != (tree / rel).read_text():
                diffs.append(f"{rel} differs")
    finally:
        _git(root, "worktree", "remove", "--force", str(tree))
        if not a.work:
            shutil.rmtree(scratch, ignore_errors=True)
    for d in diffs:
        print(f"holon mutate gate --check: {d}", file=sys.stderr)
    return 1 if diffs else 0


# ================================================================================================ rate
def cmd_rate(argv: list) -> int:
    from . import rate as RT
    ap = argparse.ArgumentParser(prog="holon mutate rate")
    ap.add_argument("--check", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    root = C.ROOT
    inst = C.instrument(root)
    recs, miss = {}, []
    for m in inst["mutants"]:
        p = root / C.RESULTS / f"{m['id']}.json"
        if p.is_file():
            recs[m["id"]] = json.loads(p.read_text())
        else:
            miss.append(m["id"])
    if miss:
        print(f"holon mutate rate: refused: {len(miss)} records missing ({', '.join(miss[:5])})", file=sys.stderr)
        return 2
    commits = sorted({r["pipeline_commit"] for r in recs.values()})
    base = json.loads((root / C.RESULTS / "baseline.json").read_text())
    if commits != [base["pipeline_commit"]]:
        print(f"holon mutate rate: refused: the records name pipeline commits {commits}, the baseline "
              f"{base['pipeline_commit']}", file=sys.stderr)
        return 2
    adj = json.loads((root / C.ADJUDICATION).read_text())
    refs = {"instrument": C.instrument_ref(root),
            "review": {"path": C.REVIEW.as_posix(), "sha256": C.sha256_file(root / C.REVIEW)},
            "adjudication": {"path": C.ADJUDICATION.as_posix(), "sha256": C.sha256_file(root / C.ADJUDICATION)},
            "gate": {"path": C.GATE.as_posix(), "sha256": C.sha256_file(root / C.GATE)}}
    text = C.dump(RT.summary(inst, recs, adj, refs, commits[0]))
    p = root / C.SUMMARY
    if a.check:
        same = p.is_file() and p.read_text() == text
        print(f"holon mutate rate --check: {'reproduces' if same else 'DIFFERS from'} {C.SUMMARY}")
        return 0 if same else 1
    C.write_text(p, text)
    print(f"holon mutate rate: wrote {C.SUMMARY}")
    return 0


def main(cmd: str, argv: list) -> int:
    try:
        if cmd == "run":
            return cmd_run(argv)
        if cmd == "gate":
            return cmd_gate(argv)
        if cmd == "rate":
            return cmd_rate(argv)
    except C.MutateError as e:
        print(f"holon mutate {cmd}: refused: {e}", file=sys.stderr)
        return 2
    print(f"holon mutate: unknown command {cmd}", file=sys.stderr)
    return 2
