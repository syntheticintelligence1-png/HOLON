"""The detection channels of a run (I61 contract, "The pipeline" step 5; instrument channels: doc, i20_step, i16_edge,
flags). They never decide a kill: a record lists its runs in refinement.channels, and two flags read them (flags).

Each run function returns one run entry of the record's refinement.channels:

    {"harness": "i20_step" | "i16_edge", "steps": n, "new_disagreements": [id, ...] (sorted),
     "corpus_differences": [step id, ...] (sorted) | null, "error": null | str}

A harness that exits without a result leaves its run incomplete: a panic, a build failure, FragmentsError, RefineError,
a timeout, a refused toolchain pin or any other exception of the step. An incomplete run has steps 0,
new_disagreements [], corpus_differences null and error a deterministic one-line account (error_text: the exception,
the tool's summary line and its first diagnostic line, with scratch paths replaced by placeholders and durations
removed), so that a rerun writes the same record.

Inputs. htree is the unit's scratch HOLON tree (holon.mutate.stage.holon_tree): every binding, harness file, document,
record and configuration a run reads comes from it, and nothing is read from or written to the repository the run
starts from (but this package's code). tree is the unit's source tree laid out as the checkout, never a git checkout:
the I16 and I20 CLIs refuse it (holon.replay.check_checkout), so the channels call their library functions, following
holon.replay_fragments.run and holon.refinement.refine without their checkout checks and without writing their
records or spec/M2/disagreements.json. work is a scratch directory; a run keeps its Foundry and Go workspaces under
work/<harness>/. The toolchain is holon.replay.toolchain on htree: the pins of htree's configuration (a mutated
sol_deps copy has its own tree hash there).

i20_step: I20's step harness (holon fragments, with I20's binding replay/M2/fragments.json)
  i20_baseline  the base traces (every source, the M1 corpus size), the translation run, the boundary and targeting
                forks and the suffix traces, the second run, then the comparison with the extracted model of the
                binding's document in htree (the evaluator holon fragments uses, the model compiled from tree) with
                the WidthValues observer. Writes the corpus file (below) and the width values.
  i20_mutant    the corpus file's traces, rebuilt exactly, on the mutant contract against the mutant's own extracted
                document, with no corpus search. new_disagreements: the run's ids the corpus file does not hold;
                corpus_differences: the step ids whose real observables differ from the corpus file's (a step id on
                one side only is a difference).
  The width values are holon fragments' width_values.json beside its record (results/M2/refinement/extracted/),
  which the SORT-width laws read. A completed run whose document has width sites writes them in htree through
  WidthValues.document; after any other run htree holds no width values file, so that no later step reads another
  run's values as its own.

The corpus file (canonical JSON, common.dump; no paths, no timings):
  {"traces": [[step, ...], ...]   every Step of every trace as run, forks and suffixes included, in order: its
                                  dataclass fields, pokes as [slot, word] pairs (step_json, step_of),
   "observables": {"<trace index>:<exec id>": {"status", "revert": revert key | null,
                   "writes": {slot: post value}, "logs": [{"topics", "data"}]}}   the real side of every compared step,
   "disagreement_ids": [id, ...]}  the run's disagreement ids, sorted

i16_edge: I16's per-edge refinement (holon.refinement.refine). Every refined edge of the M0 registry facts' diagram,
each bound by I16's binding (replay/M2/implementations.json); I16's per-edge corpus (holon.corpus.corpus on the
registry facts in htree); the model side evaluated on the given header document with the engine refine picks
(model_engine, build_engine); the real side through I16's harnesses on tree, fed as refine feeds them (the binding and
the registry facts); disagreement ids as holon.refinement.edge_record computes them. steps: compared items over all
edges. A Go harness has no recover: a panicking Go mutant fails the run (an incomplete run).

Process environment. A run sets, for its duration, HOLON_BUILD_DIR to htree/build (the libraries compile and cache
models under the build dir of their own root unless it is set; this keeps every cache in the scratch tree, where the
pipeline's own steps in htree keep theirs), BEND_NO_TELEMETRY=1, GOTOOLCHAIN=local, GOFLAGS=-mod=readonly and
(modules from the cache or the go.sum-verified proxy), and restores them after. The environment is process-wide, so runs in one process are serialized by a
lock: run units in parallel in separate processes.

Timings and the raw message of an error never enter an entry or the corpus file: a caller that passes detail={} gets
them there (seconds per phase, counts, per-edge counts, error_raw).

Nothing here names the target: names come from the bindings, the documents and the compiled artifacts.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import os
import re
import threading
import time
from pathlib import Path

from . import common as C

I20 = "i20_step"
I16 = "i16_edge"
WIDTH_VALUES = "width_values.json"
ERROR_CHARS = 400
_LOCK = threading.Lock()
_ENV = {"BEND_NO_TELEMETRY": "1", "GOTOOLCHAIN": "local", "GOFLAGS": "-mod=readonly"}
# the first line of a tool's output that says what failed, by kind, in this order of preference: a Go panic, a
# compiler error, a failed forge test, a failed Go test, a Go package that did not load or build, a forge error
_DIAGNOSTICS = tuple(re.compile(p, re.M) for p in (r"^\s*(panic: [^\n]*)$", r"^\s*(Error \(\d+\)[^\n]*)$",
                                                     r"^\s*(\[FAIL[^\n]*)$", r"^\s*(--- FAIL: [^\n]*)$",
                                                     r"^\s*(FAIL\s+\S+\s+\[(?:setup|build) failed\])\s*$",
                                                     r"^\s*(Error: [^\n]*)$"))
# a Go loader or compiler error line ("<file>.go:<line>:<col>: <message>"): quoted only when every such line of the
# output gives the same message (their order is not fixed)
_GO_POSITION = re.compile(r"^\s*\S+\.go:\d+:\d+: ([^\n]*)$", re.M)
_DURATION = re.compile(r"\b\d+(?:\.\d+)?(?:ns|us|µs|ms|s)\b")


# ---------------------------------------------------------------- entries and flags
def entry(harness: str, steps: int, new_disagreements: list, corpus_differences, error) -> dict:
    return {"harness": harness, "steps": steps, "new_disagreements": sorted(new_disagreements),
            "corpus_differences": None if corpus_differences is None else sorted(corpus_differences), "error": error}


def incomplete(harness: str, error: str) -> dict:
    return entry(harness, 0, [], None, error)


def harnesses(mutant: dict | None) -> list[str]:
    """The runs a record lists (instrument channels), sorted: the baseline (mutant None) runs both; a stratum-A
    Solidity mutant runs i20_step, and i16_edge when its edges are non-empty; a stratum-A Go mutant runs i16_edge;
    stratum B (and any unit of no stratum) runs none."""
    if mutant is None:
        return sorted([I16, I20])
    if mutant.get("stratum") != "A":
        return []
    sol = str(mutant.get("file") or "").endswith(".sol")
    return sorted(([I20] if sol else []) + ([I16] if (not sol or mutant.get("edges")) else []))


def flags(runs: list[dict], replay_disagreements: list) -> tuple:
    """(extraction_defect_detected, corpus_detected) of a record (instrument channels.flags): the first is True when
    some law is a replay disagreement or some run reports a new disagreement, None when neither and some run is
    incomplete, False otherwise; the second reads the record's i20_step run (only the baseline and stratum-A
    Solidity mutants have one): whether its corpus_differences is non-empty when it completed, None when it is
    incomplete or absent."""
    if replay_disagreements or any(r["new_disagreements"] for r in runs):
        defect = True
    elif any(r["error"] for r in runs):
        defect = None
    else:
        defect = False
    i20 = [r for r in runs if r["harness"] == I20]
    corpus = bool(i20[0]["corpus_differences"]) if i20 and i20[0]["error"] is None else None
    return defect, corpus


def error_text(e: BaseException, places: dict) -> str:
    """A deterministic one-line account of an exception that ended a run: "<type>: <summary>", where the summary is
    the message's first line, cut before the tool output it quotes ("(exit n): <output>") when there is one, followed
    by " | <the output's first diagnostic line>" (a panic, a compiler error, a failed test, a Go package that did not
    load or build) and by " | <message>" when every Go position line of the output ("<file>.go:l:c: <message>")
    gives the same message; every place (name -> path) is replaced by "<name>" and durations by "<t>"."""
    msg = e.code if isinstance(e, SystemExit) and not isinstance(e.code, int) else e
    text = f"{type(e).__name__}: {msg}"
    forms = {}
    for name, p in places.items():
        if p is None:
            continue
        for f in {str(p), str(Path(p).resolve()), os.path.realpath(str(p))}:
            if len(f) > 1:
                forms[f] = name
    for f in sorted(forms, key=lambda x: (-len(x), x)):
        text = text.replace(f, f"<{forms[f]}>")
    lines = text.splitlines() or [""]
    head, tail = lines[0], "\n".join(lines[1:])
    cut = head.find("): ")
    if cut >= 0 and "\n" in text:
        head, tail = head[:cut + 1], head[cut + 3:] + "\n" + tail
    diag = next((" ".join(m.group(1).split()) for m in (p.search(tail) for p in _DIAGNOSTICS) if m), None)
    out = head if not diag or diag in head else f"{head} | {diag}"
    same = set(_GO_POSITION.findall(tail))
    if len(same) == 1:
        out += f" | {same.pop().strip()}"
    return _DURATION.sub("<t>", out)[:ERROR_CHARS]


# ---------------------------------------------------------------- the process environment of a run
@contextlib.contextmanager
def _environment(htree: Path):
    want = {"HOLON_BUILD_DIR": str(Path(htree) / "build"), **_ENV}
    with _LOCK:
        old = {k: os.environ.get(k) for k in want}
        os.environ.update(want)
        try:
            yield
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def _places(htree: Path, tree: Path, work: Path, **more) -> dict:
    """The paths an error message may quote, by placeholder name: the scratch trees, this package's checkout and the
    sol_deps htree's configuration names (a mutant's scratch copy, or the pinned one)."""
    out = {"holon": htree, "tree": tree, "work": work, "code": C.ROOT, **more}
    with contextlib.suppress(Exception):
        sd = (C.config(htree).get("replay") or {}).get("sol_deps")
        if sd:
            out["sol_deps"] = Path(sd)
    return out


def _fail(harness: str, e: BaseException, places: dict, detail: dict) -> dict:
    detail["error_raw"] = f"{type(e).__name__}: {e.code if isinstance(e, SystemExit) else e}"
    return incomplete(harness, error_text(e, places))


class _Clock:
    def __init__(self, sec: dict):
        self.sec, self.t = sec, time.monotonic()

    def lap(self, name: str) -> None:
        now = time.monotonic()
        self.sec[name] = round(self.sec.get(name, 0) + now - self.t, 1)
        self.t = now


# ---------------------------------------------------------------- the corpus file
def step_json(step) -> dict:
    """A harness Step as JSON: its dataclass fields, pokes as [slot, word] pairs."""
    d = {f.name: getattr(step, f.name) for f in dataclasses.fields(step)}
    d["pokes"] = [[int(s), int(w)] for s, w in step.pokes]
    return d


def step_of(d: dict):
    """The harness Step a step_json value stands for, exactly (pokes as (slot, word) tuples, as the corpus search
    builds them)."""
    from ..replay_fragments import Step
    names = sorted(f.name for f in dataclasses.fields(Step))
    if not isinstance(d, dict) or sorted(d) != names:
        raise ValueError(f"a corpus step has the fields {sorted(d) if isinstance(d, dict) else type(d).__name__}, "
                         f"a Step has {names}")
    d = dict(d, pokes=[tuple(p) for p in d["pokes"]])
    return Step(**d)


def observables(compared: list) -> dict:
    """{"<trace index>:<exec id>": the real observables of the step} of every compared step: status, revert key
    (holon.replay_fragments.revert_key; null on ok), the touched storage slots with their post values, the logs."""
    from ..replay_fragments import revert_key
    out = {}
    for c in compared:
        r = c.real
        out[f"{c.tid}:{c.id}"] = {"status": r["status"],
                                  "revert": revert_key(r["revert"]) if r["status"] == "revert" else None,
                                  "writes": dict(sorted(r["writes"].items())),
                                  "logs": [{"topics": list(ev["topics"]), "data": ev["data"]} for ev in r["events"]]}
    return out


def corpus_document(traces: list, compared: list, new: list) -> dict:
    return {"traces": [[step_json(s) for s in t] for t in traces], "observables": observables(compared),
            "disagreement_ids": sorted({d["id"] for d in new})}


def load_corpus(path: Path) -> tuple[list, dict, list]:
    """(traces as Steps, observables, disagreement ids) of a corpus file."""
    doc = json.loads(Path(path).read_text())
    if not isinstance(doc, dict) or sorted(doc) != ["disagreement_ids", "observables", "traces"]:
        raise ValueError("the corpus file holds no traces, observables and disagreement_ids")
    return [[step_of(d) for d in t] for t in doc["traces"]], doc["observables"], list(doc["disagreement_ids"])


def corpus_differences(base: dict, obs: dict) -> list[str]:
    """The step ids whose real observables differ between two observables maps; an id on one side only differs."""
    return sorted(k for k in set(base) | set(obs)
                  if k not in base or k not in obs or C.compact(base[k]) != C.compact(obs[k]))


def width_path(htree: Path) -> Path:
    """Where holon fragments writes the width values: beside its record, results/M2/refinement/extracted/."""
    from ..replay_fragments import RECORD
    return Path(htree) / RECORD.with_suffix("") / WIDTH_VALUES


def _write_width(htree: Path, doc: dict | None) -> None:
    from ..replay_fragments import write_json
    p = width_path(htree)
    if doc is None:
        p.unlink(missing_ok=True)
    else:
        write_json(p, doc)


# ---------------------------------------------------------------- i20_step
@dataclasses.dataclass
class _I20Run:
    traces: list
    compared: list
    new: list
    width: dict | None


def _i20(htree: Path, tree: Path, work: Path, traces: list | None, jobs: int, clock: _Clock) -> _I20Run:
    """One I20 step-harness run as holon.replay_fragments.run does it (no checkout check, no record, no disagreements
    file, no panic location): with traces None the corpus is searched (base traces, translation run, forks and
    suffixes, second run); else the given traces run once."""
    from .. import fragments_corpus as FC
    from .. import replay_fragments as RF
    from ..replay import toolchain
    binding = RF.load_binding(htree / RF.BINDING)
    if not binding.get("facts"):
        raise RF.FragmentsError("the binding names no transitions document (\"facts\")")
    doc_path = htree / binding["facts"]
    doc = json.loads(doc_path.read_bytes())
    tc = toolchain(argparse.Namespace(forge=None, solc=None, write_pins=False), htree)
    clock.lap("toolchain")
    proj = RF.harness_project(binding, work, htree, tree, tc)
    RF.forge_build(proj, tc)
    tgt = RF.Target.build(proj, binding, doc)
    view = tgt.view
    slots = view.dump_slots()
    init = FC.binding_init(binding, htree)
    clock.lap("build")
    load, step_fn = RF.load_evaluator(None, htree)
    model = load(str(doc_path), str(tree))
    mismatch = RF.check_reach_ids(model, view)
    if mismatch:
        raise RF.FragmentsError(f"reach ids differ between the evaluator and holon.fragments_doc: {mismatch}")
    clock.lap("model")
    if traces is None:
        sources = list(RF.SOURCES)
        base, _counts = FC.base_traces(binding, htree, FC.M1_SIZE, sources, {f["name"]: f for f in tgt.fns.values()})
        if not base:
            raise RF.FragmentsError("the corpus is empty (no abstract facts, witnesses or seed traces in the binding)")
        clock.lap("base_traces")
        runs = RF.run_harness(proj, tc, binding, base, slots, init, RF.MAX_STEPS, jobs, tag="translation")
        clock.lap("translation_run")
        search = FC.Search(view, tgt, runs, slots)
        forks_b, forks_t, suffix = {}, {}, []
        if "boundary" in sources:
            forks_b = search.boundary(view.widths())
        if "target" in sources:
            forks_t, log = search.target()
            suffix = search.suffixes(log, base)
        traces = FC.insert_forks(base, forks_b, forks_t) + suffix
        clock.lap("search")
        if any(forks_b.values()) or any(forks_t.values()) or suffix:
            runs = RF.run_harness(proj, tc, binding, traces, slots, init, RF.MAX_STEPS, jobs, tag="full")
            clock.lap("second_run")
    else:
        runs = RF.run_harness(proj, tc, binding, traces, slots, init, RF.MAX_STEPS, jobs, tag="full")
        clock.lap("run")
    wv = RF.WidthValues(model, htree)
    compared, new = RF.compare_runs(runs, tgt, slots, model, step_fn, [wv.observe] if wv.sites else [])
    width = None
    if wv.sites:
        width = wv.document(RF._rel(doc_path, htree), RF.sha256_json([c.input_sha for c in compared]))
    clock.lap("compare")
    return _I20Run(traces, compared, new, width)


def i20_baseline(htree: Path, tree: Path, work: Path, corpus_out: Path, *, jobs: int = 1,
                 detail: dict | None = None) -> dict:
    """I20's step harness on the baseline (the null mutant), exactly as holon fragments runs it (module docstring).
    Writes corpus_out (the corpus file) and htree's width values. The entry: steps the compared steps,
    new_disagreements [] and corpus_differences []."""
    htree, tree, work, corpus_out = (Path(p).resolve() for p in (htree, tree, work, corpus_out))
    detail = {} if detail is None else detail
    clock = _Clock(detail.setdefault("seconds", {}))
    t0 = time.monotonic()
    try:
        with _environment(htree):
            r = _i20(htree, tree, work / I20, None, jobs, clock)
            text = C.dump(corpus_document(r.traces, r.compared, r.new))
            again = json.loads(text)["traces"]
            if [[step_of(d) for d in t] for t in again] != r.traces:
                raise ValueError("the corpus file does not rebuild the run's Steps exactly")
            C.write_text(corpus_out, text)
            _write_width(htree, r.width)
            clock.lap("write")
    except (Exception, SystemExit) as e:
        with contextlib.suppress(Exception):
            corpus_out.unlink(missing_ok=True)
        with contextlib.suppress(Exception):
            _write_width(htree, None)
        return _fail(I20, e, _places(htree, tree, work, corpus=corpus_out), detail)
    finally:
        detail["seconds"]["total"] = round(time.monotonic() - t0, 1)
    detail.update(traces=len(r.traces), trace_steps=sum(len(t) for t in r.traces), steps=len(r.compared),
                  disagreements=len({d["id"] for d in r.new}), corpus_bytes=len(text.encode()),
                  width_sites=len((r.width or {}).get("sites") or {}))
    return entry(I20, len(r.compared), [], [], None)


def i20_mutant(htree: Path, tree: Path, work: Path, corpus_in: Path, *, jobs: int = 1,
               detail: dict | None = None) -> dict:
    """I20's step harness on the mutant contract (tree) with exactly the corpus file's traces and no corpus search,
    compared step by step with the mutant's own extracted document (module docstring). Writes htree's width values."""
    htree, tree, work, corpus_in = (Path(p).resolve() for p in (htree, tree, work, corpus_in))
    detail = {} if detail is None else detail
    clock = _Clock(detail.setdefault("seconds", {}))
    t0 = time.monotonic()
    try:
        with _environment(htree):
            traces, base_obs, base_ids = load_corpus(corpus_in)
            clock.lap("corpus")
            r = _i20(htree, tree, work / I20, traces, jobs, clock)
            _write_width(htree, r.width)
            clock.lap("write")
    except (Exception, SystemExit) as e:
        with contextlib.suppress(Exception):
            _write_width(htree, None)
        return _fail(I20, e, _places(htree, tree, work, corpus=corpus_in), detail)
    finally:
        detail["seconds"]["total"] = round(time.monotonic() - t0, 1)
    ids = {d["id"] for d in r.new}
    diffs = corpus_differences(base_obs, observables(r.compared))
    detail.update(traces=len(traces), steps=len(r.compared), disagreements=len(ids),
                  width_sites=len((r.width or {}).get("sites") or {}))
    return entry(I20, len(r.compared), sorted(ids - set(base_ids)), diffs, None)


# ---------------------------------------------------------------- i16_edge
def _i16(htree: Path, tree: Path, work: Path, facts_path: Path, clock: _Clock) -> dict:
    """{edge: {"compared", "disagreements", "ids"}} of I16's per-edge refinement as holon.refinement.refine does it
    (no checkout check, no native record write, no record, no disagreements file)."""
    from .. import corpus as CO
    from .. import facts as F
    from .. import ir
    from .. import refinement as R
    from ..replay import toolchain
    reg = ir.load_registry("M0", htree)
    reg_rel = reg["facts"]
    reg_path = htree / reg_rel
    reg_facts = F.load(reg_path)
    edges = R.refined_edges(reg_rel, htree)
    names = [e for e, _k, _d in edges]
    bind = R.binding(htree)
    missing = sorted(set(names) - set(bind.get("edges", {})))
    if missing:
        raise R.RefineError(f"{R.BINDING.as_posix()} binds no implementation for {missing}")
    engine = R.model_engine(htree)
    tc = toolchain(argparse.Namespace(forge=None, solc=None, write_pins=False), htree)
    clock.lap("toolchain")
    facts = F.load(facts_path)
    model = R.build_engine(engine, facts_path)
    clock.lap("model")
    corpora = {e: CO.corpus(e, reg_path, "M0", htree) for e in names}
    inputs = {e: [it["input"] for it in corpora[e]] for e in names}
    clock.lap("corpus")
    outputs = {e: R.evaluate(model, facts, e, inputs[e]) for e in names}
    clock.lap("model_side")
    real = R.real_outputs(htree, reg_facts, bind, names, inputs, tree, work, tc)
    clock.lap("real_side")
    out = {}
    for e, kind, diagram_edge in edges:
        # edge_record gives the compared count and the disagreement ids; the record is never written, so the fields
        # that only describe it (model hash, native status, domain counts, fixes, checkout commit) stay empty
        rec, dis = R.edge_record(e, kind, diagram_edge, reg_rel, reg["facts_sha256"], "", engine, "", bind,
                                 corpora[e], outputs[e], real[e], None, [], "", tc)
        out[e] = {"compared": rec["compared"], "disagreements": rec["disagreements"], "ids": [d["id"] for d in dis]}
    return out


def i16_edge(htree: Path, tree: Path, work: Path, facts_path: Path, baseline_ids: list | None, *,
             detail: dict | None = None) -> tuple[dict, list]:
    """I16's per-edge refinement of the header document facts_path (absolute, or relative to htree) against the code of
    tree on I16's per-edge corpus (module docstring). Returns (entry, ids): ids the run's disagreement ids, sorted;
    new_disagreements the ids baseline_ids does not hold ([] when baseline_ids is None: the baseline itself);
    corpus_differences null. An incomplete run returns ids []."""
    htree, tree, work = (Path(p).resolve() for p in (htree, tree, work))
    fp = Path(facts_path)
    fp = (fp if fp.is_absolute() else htree / fp).resolve()
    detail = {} if detail is None else detail
    clock = _Clock(detail.setdefault("seconds", {}))
    t0 = time.monotonic()
    try:
        with _environment(htree):
            per = _i16(htree, tree, work / I16, fp, clock)
    except (Exception, SystemExit) as e:
        return _fail(I16, e, _places(htree, tree, work, facts=fp), detail), []
    finally:
        detail["seconds"]["total"] = round(time.monotonic() - t0, 1)
    ids = sorted({i for v in per.values() for i in v["ids"]})
    detail["edges"] = {e: {"compared": v["compared"], "disagreements": v["disagreements"]} for e, v in sorted(per.items())}
    new = [] if baseline_ids is None else sorted(set(ids) - set(baseline_ids))
    return entry(I16, sum(v["compared"] for v in per.values()), new, None, None), ids
