"""Refinement of an extracted transitions document against the real contract, step by step (I20; whitepaper §8.7,
§8.6, Def 4.7; the contract is the docstring of tests_m2/test_extracted_refinement.py, clauses 1, 2 and 7-9).

    python -m holon fragments [--binding replay/M2/fragments.json] [--facts DOC] [--out PATH] [--details PATH]
                              [--work DIR] [--morph PATH] [--jobs N] [--corpus N] [--sources m1,witness,boundary,target]
                              [--evaluator MODULE:FUNCTION | FILE.py:FUNCTION] [--disagreements PATH | --no-file]
                              [--no-locate] [--root DIR]

The real side. A binding (replay/M2/fragments.json; a toy's binding in its fixture) names the harness files, the
harness test contract (and its last-step contract), the target contract and how the scratch Foundry project is laid
out. The harness inherits the generic replay/M2/solidity/HolonStepBase.sol: it deploys the real target and its
dependencies for every trace, runs each step and records the status, the raw return or revert data, the block and
transaction environment, every storage write to the target (vm.startStateDiffRecording: the touched slots are exact),
every log the target emitted (vm.recordLogs), every external call the target made with its answer (re-run in order from
the state before the step, as the target), and vm.load of every slot of the document's storage layout (inherited
storage included) after the step. A fork step runs from a snapshot and is reverted: the boundary and guard-targeting
steps (holon.fragments_corpus) branch off the corpus traces. One harness run serves many traces (chunks of about
--max-steps steps); the corpus is built from a first, translation, run of the base traces and compared on a second run
with the fork steps inserted.

States. The target's storage is tracked exactly: the deployment's writes, then every kept step's writes. After every
step the tracked state must equal the harness's vm.load of every layout slot, else FragmentsError (the recording
missed a write). The model side of a step starts from the real state before it, so a disagreement is local to its
step ("fragments") and never an accumulation.

The model side: the A/B interface, holon.extracted_eval.step(model, state, action, args, env) with
model = holon.machine.load_extracted(doc) (or --evaluator):
  state  {"0x<slot>": "0x<word>"} of every non-zero slot before the step (32-byte lowercase hex; missing = 0)
  args   the calldata decoded with the target's compiled ABI (holon.evm_abi values: ints, bools, 0x-hex, dicts, lists)
  env    {"caller", "this", "msg.value", "msg.data.length", "block.timestamp", "block.number", "block.chainid",
          "block.basefee", "block.prevrandao", "block.coinbase", "block.gaslimit", "block.blobbasefee", "tx.origin",
          "tx.gasprice", "blobhash": ["0x<32 bytes>", ...],
          "calls": [{"to", "data", "fn": "<Interface>.<function>" | null, "args": {...} | null, "ok", "ret"}],
          "balance": {address: wei before the call (its value not yet transferred)}, "code": {target: runtime code}}
It answers {"status": "ok" | "revert" (| "unsupported", with "reason"), "revert": "0x.." | None, "writes":
{"0x<slot>": "0x<word>"}, "events": [{"topics": [...], "data"}], "guard": "<action>#<span>#<k>" | None}.

The comparison (clause 7), one step at a time:
  status    ok or revert (a model that answers neither, or raises, disagrees on status);
  revert    on two reverts, the revert data's key: the Error(string) reason, a custom error's selector, the Panic code,
            else the raw bytes (holon.replay_fragments.revert_key);
  storage   on two oks, every slot that a write of the step touches on either side: the model's post value (its
            write, else the value before the step) against the real post value (the tracked state, which vm.load of
            every layout slot confirms);
  events    on two oks, every log the target emitted (topics and data, in order) against the model's events.
A difference in any observable is a disagreement. New ones are appended to spec/M2/disagreements.json (or
--disagreements) as "unexplained" with no links, under an id that is a function of (action, input); a class comes from
an entry's links only (holon.refinement.classify), never from a label.

The record (--out, default results/M2/refinement/extracted.json; canonical JSON):
  {"traces", "steps", "disagreements": [{"id", "class", "links"}], "unexplained", "observables", "storage_slots",
   "by_action": {action: {"ok", "revert"}} (by the real status), "panics": [{"src", "code", "steps", ...}],
   "guard_coverage": {"reaches", "falsified", "unfalsified": [{"id", "reason"}]}, plus provenance}.
A reach (holon.fragments_doc) is falsified when some step ends on the model at that reach (its guard id) and the real
contract reverts with the same revert key. panics groups the steps where both sides Panic with the same code by the
model's reach span and code; with a last-step contract in the binding, the real Panic's source line of the first step
of each group is located in a debugger dump (holon.mreplay.locate_panic) and reported as "src" ("model_src" keeps the
model's span). Per-step digests and the corpus search log go to --details (default <work>/details.json).

Nothing here names a target: names come from the binding, the document and the compiled artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import evm_abi as abi
from . import ir
from .fragments_doc import DocError, DocView

ROOT = Path(__file__).resolve().parents[1]
RECORD = Path("results") / "M2" / "refinement" / "extracted.json"
BINDING = Path("replay") / "M2" / "fragments.json"
RECORD_KIND = "extracted"
OBSERVABLES = ("events", "revert", "status", "storage")
PANIC = "4e487b71"
ERROR_STRING = "08c379a0"
STEP_ABSTRACT, STEP_CALL = 1, 2
MAX_STEPS = 400
MAX_DUMP = 1 << 30          # a debugger dump larger than this is not read (locate_panics)
ZERO_ADDR = "0x" + "00" * 20
SOURCES = ("m1", "witness", "boundary", "target")


class FragmentsError(RuntimeError):
    pass


def sha256_json(obj) -> str:
    return hashlib.sha256(ir.canonical_json(obj)).hexdigest()


def word(v) -> int:
    """A storage word or slot given as an int or 0x-hex."""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        return int(v, 16) if v.lower().startswith("0x") else int(v)
    raise FragmentsError(f"not a word: {v!r}")


def hex32(v: int) -> str:
    return "0x%064x" % v


# ---------------------------------------------------------------- steps
@dataclass
class Step:
    """One harness step. kind "abstract": row is an abstract row (the binding's abstract facts); kind "call": a call
    (caller, value, timestamp (0 keeps the clock), blobs, to (None: the target), data). fork: run from a snapshot and
    reverted. meta: what built it (corpus source, the reach it targets, ...), carried into the details."""
    kind: str
    fork: bool = False
    row: list = field(default_factory=list)
    caller: str = ZERO_ADDR
    value: int = 0
    timestamp: int = 0
    blobs: list = field(default_factory=list)
    to: str | None = None
    data: str = "0x"
    meta: dict = field(default_factory=dict)

    def encode(self) -> str:
        if self.kind == "abstract":
            payload = abi.encode_args([{"type": "uint256[]"}], [[int(x) for x in self.row]])
            k = STEP_ABSTRACT
        elif self.kind == "call":
            payload = abi.encode_args(
                [{"type": "address"}, {"type": "uint256"}, {"type": "uint256"}, {"type": "bytes32[]"},
                 {"type": "address"}, {"type": "bytes"}],
                [self.caller, self.value, self.timestamp, list(self.blobs), self.to or ZERO_ADDR, self.data])
            k = STEP_CALL
        else:
            raise FragmentsError(f"unknown step kind {self.kind}")
        return "0x" + abi.encode_args([{"type": "uint8"}, {"type": "bool"}, {"type": "bytes"}],
                                      [k, self.fork, "0x" + payload.hex()]).hex()

    def key(self) -> tuple:
        return (self.kind, tuple(self.row), self.caller, self.value, self.timestamp, tuple(self.blobs), self.to,
                self.data)


@dataclass
class Exec:
    """What the harness recorded for one executed step."""
    tid: int
    id: str
    kind: str                     # call | env
    fork: bool
    ok: bool
    to: str | None
    caller: str | None
    value: int
    timestamp: int
    number: int
    blobs: list
    data: str
    ret: str
    env: dict = field(default_factory=dict)       # the V line's block and transaction members
    balances: tuple = (0, 0)                      # the target's and the caller's balance before the call
    writes: list = field(default_factory=list)    # (slot, value, reverted)
    logs: list = field(default_factory=list)      # (topics, data)
    calls: list = field(default_factory=list)     # (to, data, ok, ret)
    dump: list | None = None
    notes: list = field(default_factory=list)


@dataclass
class TraceRun:
    tid: int
    target: str
    harness: str
    execs: list                   # Exec in execution order; execs[0] is the deployment (id "d")
    steps: list                   # the Step list the trace ran (deployment excluded)
    code: str = "0x"              # the target's runtime code after the deployment
    impl_code: str | None = None  # an EIP-1967 proxy target's implementation code (where its immutables are)


# ---------------------------------------------------------------- binding and project
def load_binding(path: Path) -> dict:
    try:
        b = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        raise FragmentsError(f"binding {path}: {e}")
    for k in ("harness", "project", "target"):
        if k not in b:
            raise FragmentsError(f"binding {path}: no {k!r}")
    return b


TOY_FOUNDRY = """[profile.default]
src = 'src'
out = 'out'
libs = ['node_modules']
evm_version = 'cancun'
fs_permissions = [{ access = 'read-write', path = './' }]
extra_output = ['storageLayout']
"""
TOY_REMAP = "forge-std/=node_modules/forge-std/src/\nds-test/=node_modules/ds-test/src/\n"


def harness_project(binding: dict, work: Path, root: Path = ROOT, morph: Path | None = None,
                    tc: dict | None = None) -> Path:
    """A scratch Foundry project: the target's sources (kind "checkout": the Foundry tree project.foundry_dir of the
    pinned checkout, without project.drop; kind "sources": a fixture's src/), the pinned dependencies and the harness
    files under test/."""
    from .replay import _sol_deps
    proj = Path(work) / "solidity"
    proj.mkdir(parents=True, exist_ok=True)
    pk = binding["project"]
    if pk["kind"] == "checkout":
        if morph is None:
            raise FragmentsError("the binding needs the pinned checkout (--morph or config replay.morph)")
        fd = morph / pk["foundry_dir"]
        shutil.rmtree(proj / "contracts", ignore_errors=True)   # never compile a stale copy
        shutil.copytree(fd / "contracts", proj / "contracts")
        for d in pk.get("drop", []):
            shutil.rmtree(proj / "contracts" / d, ignore_errors=True)
        for f in ("foundry.toml", "remappings.txt"):
            shutil.copy(fd / f, proj / f)
    elif pk["kind"] == "sources":
        shutil.rmtree(proj / "src", ignore_errors=True)
        shutil.copytree(root / pk["dir"], proj / "src")
        (proj / "foundry.toml").write_text(TOY_FOUNDRY)
        (proj / "remappings.txt").write_text(TOY_REMAP)
    else:
        raise FragmentsError(f"unknown project kind {pk['kind']}")
    _sol_deps(proj, Path(tc["sol_deps"]) if tc else None)
    shutil.rmtree(proj / "test", ignore_errors=True)
    (proj / "test").mkdir()
    for f in binding["harness"]["files"]:
        shutil.copy(root / f, proj / "test" / Path(f).name)
    return proj


def unit_of(binding: dict, path: str) -> str:
    """A source path of the scratch project as the document's units name it (the binding's project.unit_prefix)."""
    return (binding["project"].get("unit_prefix") or "") + path


def foundry_out(proj: Path) -> Path:
    m = re.search(r"^\s*out\s*=\s*['\"]([^'\"]+)['\"]", (proj / "foundry.toml").read_text(), re.M)
    return proj / (m.group(1) if m else "out")


def _run(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 7200) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True,
                       timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def forge_build(proj: Path, tc: dict) -> None:
    code, out = _run(["nice", "-n", "10", tc["forge"], "build", "--offline", "--use", tc["solc"]], proj)
    if code != 0:
        raise FragmentsError(f"forge build failed (exit {code}): {out[-2000:]}")


def artifact(proj: Path, source: str, contract: str) -> dict:
    """The compiled artifact (abi, storageLayout, ...) of contract in source (a path in the project)."""
    p = foundry_out(proj) / Path(source).name / f"{contract}.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        raise FragmentsError(f"no compiled artifact {p.relative_to(proj)} (forge build first)")


def artifacts_named(proj: Path, contract: str) -> list[dict]:
    """Every compiled artifact of a contract or interface of that name, sorted by path."""
    out = []
    for p in sorted(foundry_out(proj).glob(f"*/{contract}.json")):
        try:
            out.append(json.loads(p.read_text()))
        except (OSError, ValueError):
            continue
    return out


# ---------------------------------------------------------------- the compiled storage layout
class Layout:
    """The target's storage layout as the compiler reports it (inherited storage included): every variable with its
    slot, byte offset and type id, and the types."""

    def __init__(self, storage_layout: dict):
        self.raw = storage_layout or {}
        self.types = self.raw.get("types") or {}
        self.entries = [{"label": v["label"], "slot": int(v["slot"]), "offset": int(v["offset"]), "type": v["type"]}
                        for v in self.raw.get("storage") or []]
        self.vars = {}
        for v in self.entries:
            self.vars.setdefault(v["label"], v)

    def type_of(self, t: str) -> dict:
        return self.types.get(t) or {}


# ---------------------------------------------------------------- running the harness
def harness_input(traces: list[list[Step]], slots: list[int], init: list[int]) -> dict:
    return {"lens": [len(t) for t in traces], "steps": [s.encode() for t in traces for s in t],
            "slots": [hex32(s) for s in slots], "init": [int(x) for x in init]}


def chunks(traces: list[list[Step]], max_steps: int) -> list[tuple[int, int]]:
    """[lo, hi) trace ranges of about max_steps steps each (a deployment counts as a step)."""
    out, lo, n = [], 0, 0
    for i, t in enumerate(traces):
        if n and n + len(t) + 1 > max_steps:
            out.append((lo, i))
            lo, n = i, 0
        n += len(t) + 1
    if lo < len(traces):
        out.append((lo, len(traces)))
    return out


def harness_command(binding: dict) -> str:
    h = binding["harness"]
    return (f"HOLON_STEPS_IN=<chunk>.json HOLON_STEPS_OUT=<chunk>.out HOLON_LO=0 HOLON_HI=<n> forge test "
            f"--match-contract '^{h['contract']}$' --match-test '^test_steps\\(\\)$' --offline --use <solc 0.8.24>  "
            f"# per chunk of about {MAX_STEPS} steps")


def run_harness(proj: Path, tc: dict, binding: dict, traces: list[list[Step]], slots: list[int], init: list[int],
                max_steps: int = MAX_STEPS, jobs: int = 1, tag: str = "run") -> list[TraceRun]:
    """Run every trace through the harness (in chunks of about max_steps steps, jobs forge processes at a time) and
    parse what it recorded."""
    h = binding["harness"]
    runs: list[TraceRun | None] = [None] * len(traces)
    parts = chunks(traces, max_steps)
    pending = []
    for k, (lo, hi) in enumerate(parts):
        fin = proj / f"holon_{tag}_{k}.json"
        fout = proj / f"holon_{tag}_{k}.out"
        fin.write_text(json.dumps(harness_input(traces[lo:hi], slots, init)))
        fout.unlink(missing_ok=True)
        cmd = ["nice", "-n", "10", tc["forge"], "test", "--match-contract", f"^{h['contract']}$", "--match-test",
               "^test_steps\\(\\)$", "--offline", "--use", tc["solc"]]
        env = {**os.environ, "HOLON_STEPS_IN": fin.name, "HOLON_STEPS_OUT": fout.name, "HOLON_LO": "0",
               "HOLON_HI": str(hi - lo)}
        pending.append((k, lo, hi, fin, fout, cmd, env))
    active: list = []

    def finish(item, proc):
        k, lo, hi, fin, fout, cmd, env = item
        out, _ = proc.communicate()
        text = fout.read_text() if fout.exists() else ""
        if proc.returncode != 0 or not text.rstrip().endswith(f"DONE 0 {hi - lo}"):
            raise FragmentsError(f"harness chunk {k} (traces {lo}..{hi}) failed (exit {proc.returncode}): "
                                 f"{(out or '')[-2500:]}")
        for tr in parse_output(text):
            tr.tid += lo
            for e in tr.execs:
                e.tid = tr.tid
            tr.steps = traces[tr.tid]
            runs[tr.tid] = tr
        fin.unlink(missing_ok=True)
        fout.unlink(missing_ok=True)

    for item in pending:
        while len(active) >= max(1, jobs):
            it, pr = active.pop(0)
            finish(it, pr)
        proc = subprocess.Popen(item[5], cwd=proj, env=item[6], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True)
        active.append((item, proc))
    for it, pr in active:
        finish(it, pr)
    missing = [i for i, r in enumerate(runs) if r is None]
    if missing:
        raise FragmentsError(f"the harness recorded no run for traces {missing[:10]}")
    for tr in runs:
        if len([e for e in tr.execs if e.id != "d"]) != len(tr.steps):
            raise FragmentsError(f"trace {tr.tid}: {len(tr.execs) - 1} records for {len(tr.steps)} steps")
    return runs


def _hexwords(s: str) -> list:
    return [] if s == "-" else s.split(",")


ENV_KEYS = ("block.chainid", "block.basefee", "block.prevrandao", "block.coinbase", "block.gaslimit",
            "block.blobbasefee", "tx.origin", "tx.gasprice")


def parse_output(text: str) -> list[TraceRun]:
    """The harness's lines (see replay/M2/solidity/HolonStepBase.sol) as TraceRuns, in trace order."""
    runs: dict[int, TraceRun] = {}
    cur: dict[tuple, Exec] = {}
    for line in text.splitlines():
        f = line.split(" ")
        tag = f[0]
        if tag == "T":
            tid = int(f[1])
            runs[tid] = TraceRun(tid, f[2].lower(), f[3].lower(), [], [])
        elif tag == "S":
            tid, sid = int(f[1]), f[2]
            e = Exec(tid, sid, f[3], f[4] == "1", f[5] == "1", None if f[6] == "-" else f[6].lower(),
                     None if f[7] == "-" else f[7].lower(), int(f[8]), int(f[9]), int(f[10]),
                     [b.lower() for b in _hexwords(f[11])], f[12].lower(), f[13].lower())
            runs[tid].execs.append(e)
            cur[(tid, sid)] = e
        elif tag == "K":
            runs[int(f[1])].code = f[2].lower()
        elif tag == "Q":
            runs[int(f[1])].impl_code = f[3].lower()
        elif tag == "V":
            vals = f[3:]
            env = {}
            for k, v in zip(ENV_KEYS, vals):
                env[k] = v.lower() if v.startswith("0x") else int(v)
            e = cur[(int(f[1]), f[2])]
            e.env = env
            if len(vals) >= len(ENV_KEYS) + 2:
                e.balances = (int(vals[len(ENV_KEYS)]), int(vals[len(ENV_KEYS) + 1]))
        elif tag == "W":
            cur[(int(f[1]), f[2])].writes.append((int(f[3], 16), int(f[4], 16), f[5] == "1"))
        elif tag == "L":
            cur[(int(f[1]), f[2])].logs.append(([t.lower() for t in _hexwords(f[3])], f[4].lower()))
        elif tag == "C":
            cur[(int(f[1]), f[2])].calls.append((f[3].lower(), f[4].lower(), f[5] == "1", f[6].lower()))
        elif tag == "D":
            cur[(int(f[1]), f[2])].dump = [0 if v == "0" else int(v, 16) for v in _hexwords(f[3])]
        elif tag == "X":
            cur[(int(f[1]), f[2])].notes.append(" ".join(f[3:]))
    return [runs[k] for k in sorted(runs)]


# ---------------------------------------------------------------- states
def apply_writes(state: dict, writes: list) -> dict:
    out = dict(state)
    for slot, val, rev in writes:
        if rev:
            continue
        if val:
            out[slot] = val
        else:
            out.pop(slot, None)
    return out


def track(run: TraceRun, slots: list[int]) -> list[tuple[Exec, dict, dict]]:
    """(exec, state before, state after) for every executed step of the trace, the deployment first. A kept step's
    writes carry over; a fork's do not. Every state after must match the harness's vm.load dump."""
    state: dict = {}
    out = []
    for e in run.execs:
        before = state
        after = apply_writes(before, e.writes) if (e.ok or e.kind == "env") else dict(before)
        if e.dump is not None and slots:
            if len(e.dump) != len(slots):
                raise FragmentsError(f"trace {run.tid} step {e.id}: dump of {len(e.dump)} slots for {len(slots)}")
            bad = [hex(s) for s, v in zip(slots, e.dump) if after.get(s, 0) != v]
            if bad:
                raise FragmentsError(f"trace {run.tid} step {e.id}: the tracked storage differs from vm.load at "
                                     f"slots {bad[:5]} (a write the recording missed)")
        out.append((e, before, after))
        if not e.fork:
            state = after
    return out


# ---------------------------------------------------------------- the target
def _walk_terms(t, acc: list) -> None:
    if isinstance(t, list):
        acc.append(t)
        for x in t:
            _walk_terms(x, acc)
    elif isinstance(t, dict):
        for x in t.values():
            _walk_terms(x, acc)


def call_names(doc: dict) -> list[str]:
    """Every "<Interface>.<function>" an external call of the document names: call terms, COMMIT edges and the
    planned calls section (A19-02)."""
    acc: list = []
    _walk_terms(doc.get("actions"), acc)
    names = {t[1] for t in acc if len(t) >= 2 and t[0] in ("call", "callok") and isinstance(t[1], str)}
    for a in doc.get("actions") or []:
        names |= {e["fn"] for e in a.get("edges") or [] if isinstance(e.get("fn"), str) and "." in e["fn"]}
        names |= {c["fn"] for c in a.get("calls") or [] if isinstance(c, dict) and isinstance(c.get("fn"), str)}
    return sorted(n for n in names if "." in n and not n.startswith("address."))


def interface_selectors(proj: Path, doc: dict) -> dict[str, tuple[str, dict]]:
    """selector -> ("<I>.<f>", ABI entry) for the external-call names of the document, from the compiled ABIs of
    their interfaces (the first name in sorted order wins a shared selector)."""
    out = {}
    for name in call_names(doc):
        iface, fn = name.split(".", 1)
        for art in artifacts_named(proj, iface):
            for f in art.get("abi") or []:
                if f.get("type") == "function" and f.get("name") == fn:
                    out.setdefault(abi.selector(f["name"], f["inputs"]), (name, f))
    return out


@dataclass
class Target:
    """What the comparison needs about the target: the document view, the compiled ABI's functions, the external-call
    selectors and the compiled layout."""
    doc: dict
    view: DocView
    fns: dict              # selector -> ABI entry
    calls: dict            # selector -> (name, ABI entry)
    layout: Layout
    errors: dict = field(default_factory=dict)    # selector -> custom error name (compiled ABI)
    immutables: dict = field(default_factory=dict)    # name -> (byte offset, length) in the runtime code

    @classmethod
    def build(cls, proj: Path, binding: dict, doc: dict) -> "Target":
        t = binding["target"]
        art = artifact(proj, t["source"], t["contract"])
        lay = art.get("storageLayout") or {}
        try:
            view = DocView.build(doc, lay)
        except DocError as e:
            raise FragmentsError(f"the document and the compiled target disagree: {e}")
        fns = abi.functions(art.get("abi") or [])
        missing = sorted(s for s in view.by_selector if s not in fns)
        if missing:
            raise FragmentsError(f"document actions with no function of that selector in the compiled ABI: "
                                 f"{[view.by_selector[s] for s in missing]}")
        errors = {abi.selector(e["name"], e["inputs"]): e["name"] for e in art.get("abi") or []
                  if e.get("type") == "error"}
        return cls(doc, view, fns, interface_selectors(proj, doc), Layout(lay), errors, immutables_of(proj, art))

    def action_of(self, data: str) -> str | None:
        if data in ("", "0x"):
            return "receive" if "receive" in self.view.actions else None
        return self.view.action_of(data[:10])


def immutables_of(proj: Path, art: dict) -> dict:
    """{name: (byte offset, length)} of the target's immutables in its runtime code: the compiled artifact's
    deployedBytecode.immutableReferences, named by the declarations of the artifacts' ASTs (the target's first)."""
    refs = ((art.get("deployedBytecode") or {}).get("immutableReferences") or {})
    if not refs:
        return {}
    want = {int(k) for k in refs}
    names: dict = {}

    def scan(node):
        stack = [node]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if x.get("nodeType") == "VariableDeclaration" and x.get("id") in want:
                    names.setdefault(x["id"], x.get("name"))
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
    scan(art.get("ast"))
    if want - set(names):
        for p in sorted(foundry_out(proj).glob("*/*.json")):
            try:
                scan(json.loads(p.read_text()).get("ast"))
            except (OSError, ValueError):
                continue
            if not want - set(names):
                break
    out = {}
    for k, v in sorted(refs.items(), key=lambda kv: int(kv[0])):
        if int(k) in names and v:
            out[names[int(k)]] = (int(v[0]["start"]), int(v[0]["length"]))
    return dict(sorted(out.items()))


def model_call(tgt: Target, e: Exec, before: dict, target_addr: str, code: str | None = None,
               impl_code: str | None = None) -> tuple[str, dict, dict, dict] | None:
    """(action, state, args, env) of a step that calls the target with a document action's selector, else None.
    Raises abi.AbiError when the calldata does not decode (the corpus never builds such a step)."""
    if e.kind != "call" or e.to != target_addr:
        return None
    action = tgt.action_of(e.data)
    if action is None:
        return None
    fn = tgt.fns.get(e.data[:10])
    args = {}
    if fn:
        try:
            args = abi.decode_args(fn["inputs"], bytes.fromhex(e.data[10:]))
        except abi.AbiError:   # dirty calldata (an ABI range check's target): the raw words, for the model to reject
            args = abi.decode_args(fn["inputs"], bytes.fromhex(e.data[10:]), strict=False)
    calls = []
    for to, data, ok, ret in e.calls:
        name, fe = tgt.calls.get(data[:10], (None, None))
        cargs = None
        if fe is not None:
            try:
                cargs = abi.decode_args(fe["inputs"], bytes.fromhex(data[10:]))
            except abi.AbiError:
                cargs = None
        calls.append({"to": to, "data": data, "fn": name, "args": cargs, "ok": ok, "ret": ret})
    env = {"caller": e.caller, "this": target_addr, "msg.value": e.value, "msg.data.length": (len(e.data) - 2) // 2,
           "block.timestamp": e.timestamp, "block.number": e.number, **e.env, "blobhash": list(e.blobs),
           "calls": calls, "balance": {target_addr: e.balances[0]}}
    if e.caller and e.caller != target_addr:
        env["balance"][e.caller] = e.balances[1]
    if code is not None:
        env["code"] = {target_addr: code}
    if tgt.immutables:
        src = impl_code or code or "0x"
        imm = {}
        for name, (start, n) in tgt.immutables.items():
            w = src[2 + 2 * start: 2 + 2 * (start + n)]
            if len(w) == 2 * n:
                imm[name] = "0x" + w
        env["immutable"] = imm
    state = {hex32(k): hex32(v) for k, v in sorted(before.items())}
    return action, state, args, env


def real_outcome(e: Exec, before: dict, after: dict) -> dict:
    """The real side of a step, in the A/B interface's shape (writes: the post value of every slot the step wrote)."""
    touched = sorted({s for s, _v, rev in e.writes if not rev}) if e.ok else []
    return {"status": "ok" if e.ok else "revert", "revert": None if e.ok else e.ret,
            "writes": {hex32(s): hex32(after.get(s, 0)) for s in touched},
            "events": [{"topics": list(t), "data": d} for t, d in e.logs] if e.ok else [], "guard": None}


def _norm_model(out) -> dict:
    """The model's answer in canonical form (ints and 0x-hex accepted for words). A status other than ok and revert is
    kept (it disagrees on status)."""
    if not isinstance(out, dict) or not isinstance(out.get("status"), str):
        raise ValueError(f"the evaluator answered {str(out)[:200]}")
    rv = out.get("revert")
    writes = {hex32(word(k)): hex32(word(v)) for k, v in (out.get("writes") or {}).items()}
    events = [{"topics": ["0x%064x" % word(t) for t in (ev.get("topics") or [])],
               "data": (ev.get("data") or "0x").lower()} for ev in (out.get("events") or [])]
    res = {"status": out["status"], "revert": rv.lower() if isinstance(rv, str) else rv, "writes": writes,
           "events": events, "guard": out.get("guard")}
    if out["status"] not in ("ok", "revert"):
        res["reason"] = str(out.get("reason") or "")[:300]
    return res


def revert_key(data: str | None) -> list:
    """What clause 7 compares of revert data: ["error", reason] for Error(string), ["panic", code] for
    Panic(uint256), ["custom", selector] for any other 4-byte-selector payload, ["raw", hex] otherwise."""
    d = (data or "0x").lower()
    b = bytes.fromhex(d[2:]) if len(d) % 2 == 0 else b""
    if len(b) == 36 and b[:4].hex() == PANIC:
        return ["panic", int.from_bytes(b[4:], "big")]
    if b[:4].hex() == ERROR_STRING:
        try:
            return ["error", abi.decode_args([{"type": "string", "name": "r"}], b[4:])["r"]]
        except abi.AbiError:
            return ["raw", d]
    if len(b) >= 4:
        return ["custom", "0x" + b[:4].hex()]
    return ["raw", d]


def compare(model: dict, real: dict, before: dict, after: dict) -> tuple[list[str], int]:
    """(the observables that differ, the number of storage slots compared)."""
    if model["status"] != real["status"]:
        return ["status"], 0
    if model["status"] == "revert":
        return (["revert"] if revert_key(model["revert"]) != revert_key(real["revert"]) else []), 0
    diff = []
    slots = sorted(set(model["writes"]) | set(real["writes"]))
    mism = 0
    for s in slots:
        k = int(s, 16)
        if model["writes"].get(s, hex32(before.get(k, 0))) != hex32(after.get(k, 0)):
            mism += 1
    if mism:
        diff.append("storage")
    if model["events"] != real["events"]:
        diff.append("events")
    return diff, len(slots)


def panic_code(ret: str | None) -> int | None:
    k = revert_key(ret)
    return k[1] if k[0] == "panic" else None


# ---------------------------------------------------------------- the evaluator
def load_evaluator(spec: str | None, root: Path = ROOT):
    """(load, step): holon.machine.load_extracted and holon.extracted_eval.step by default; "module:function" or
    "path/to/file.py:function" names another step (its module's load_extracted, if any, loads the model)."""
    if spec:
        mod, _, fn = spec.rpartition(":") if spec.count(":") else (spec, "", "step")
        if mod.endswith(".py"):
            p = Path(mod)
            p = p if p.is_absolute() else Path(root) / p
            sp = importlib.util.spec_from_file_location(f"holon_evaluator_{p.stem}", p)
            if sp is None or sp.loader is None:
                raise FragmentsError(f"cannot load the evaluator {p}")
            m = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(m)
        else:
            m = importlib.import_module(mod)
        step = getattr(m, fn or "step")
        load = getattr(m, "load_extracted", None) or (lambda p: json.loads(Path(p).read_text()))
        return load, step
    try:
        ev = importlib.import_module("holon.extracted_eval")
        mach = importlib.import_module("holon.machine")
    except ImportError as e:
        raise FragmentsError(f"the extracted model's evaluator is not installed ({e}); pass --evaluator")
    return (lambda path, source=None: mach.load_extracted(path, root, source=source)), ev.step


def check_reach_ids(model, view: DocView) -> str | None:
    """None when the evaluator's model gives the reach ids this module counts (or exposes none), else what differs."""
    fn = getattr(model, "all_reaches", None)
    if not callable(fn):
        return None
    try:
        theirs = sorted(getattr(r, "id", None) or r["id"] for r in fn())
    except Exception as e:  # noqa: BLE001: a model without usable reaches is reported, not trusted
        return f"the model's all_reaches() failed: {type(e).__name__}: {e}"
    ours = sorted(r.id for r in view.all_reaches())
    if theirs == ours:
        return None
    a, b = set(theirs) - set(ours), set(ours) - set(theirs)
    return f"the model counts {len(theirs)} reaches, the document view {len(ours)}: only the model {sorted(a)[:5]}, " \
           f"only the view {sorted(b)[:5]}"


# ---------------------------------------------------------------- the comparison over runs
@dataclass
class Compared:
    tid: int
    id: str
    action: str
    model: dict
    real: dict
    diff: list
    slots: int
    input_sha: str
    meta: dict
    prefix: list           # the kept steps before it that can change state (the last-step replay of a Panic)
    step: Step | None = None


def disagreement_id(action: str, inp: dict) -> str:
    return f"D-x-{action}-{sha256_json([action, inp])[:16]}"


def compare_runs(runs: list[TraceRun], tgt: Target, slots: list[int], model, step_fn,
                 observers=()) -> tuple[list[Compared], list[dict]]:
    """Every compared step, and the disagreement entries to file (one per distinct (action, input)). Each observer
    is called with (Compared, state, args, env) of every compared step (the width evaluation, width_values)."""
    out, dis, seen = [], [], set()
    for tr in runs:
        steps_by_id = {str(i): s for i, s in enumerate(tr.steps)}
        kept: list = []
        for e, before, after in track(tr, slots):
            if e.id == "d":
                continue
            st = steps_by_id.get(e.id)
            mc = model_call(tgt, e, before, tr.target, tr.code, tr.impl_code)
            if mc is not None:
                action, state, args, env = mc
                real = real_outcome(e, before, after)
                inp = {"action": action, "args": args, "env": env, "state": state}
                try:
                    m = _norm_model(step_fn(model, state, action, args, env))
                except Exception as ex:  # noqa: BLE001: the evaluator's failure is a disagreement, never a skip
                    m = {"status": "error", "revert": None, "writes": {}, "events": [], "guard": None,
                         "reason": f"{type(ex).__name__}: {str(ex)[:300]}"}
                diff, n = compare(m, real, before, after)
                meta = dict(st.meta) if st else {}
                c = Compared(tr.tid, e.id, action, m, real, diff, n, sha256_json(inp), meta, list(kept), st)
                out.append(c)
                for ob in observers:
                    ob(c, state, args, env)
                if diff:
                    did = disagreement_id(action, inp)
                    if did not in seen:
                        seen.add(did)
                        entry = {"id": did, "edge": action, "milestone": "M2", "observables": diff,
                                 "input": {"trace": tr.tid, "step": e.id, "corpus": meta.get("source"),
                                           "state_sha256": sha256_json(state), "action": action, "args": args,
                                           "env": env},
                                 "model": m, "real": real}
                        if "events" in diff:   # logs whose event the document does not record (A19-09 topic0)
                            known = tgt.view.topics0()
                            entry["unrecorded_topics0"] = sorted({ev["topics"][0] for ev in real["events"]
                                                                  if ev["topics"] and ev["topics"][0] not in known})
                        dis.append(entry)
            if st is not None and not e.fork and (e.ok or e.kind == "env" or st.timestamp):
                kept.append(st)   # a kept step that reverted changed nothing but, maybe, the clock
    return out, dis


def _both_at(c: Compared, rid: str) -> bool:
    return (c.model.get("guard") == rid and c.model["status"] == "revert" and c.real["status"] == "revert"
            and revert_key(c.model["revert"]) == revert_key(c.real["revert"]))


def guard_coverage(view: DocView, compared: list[Compared], reason_of=None) -> dict:
    """reaches, falsified (some step ends there on the model and the real contract reverts with the same revert key)
    and every other reach with a reason (reason_of(reach, steps targeting it) or a generic one)."""
    hit: dict = {}
    targeted: dict = {}
    for c in compared:
        g = c.model.get("guard")
        if g and _both_at(c, g):
            hit[g] = hit.get(g, 0) + 1
        for t in [c.meta.get("targets")] + [m.get("targets") for m in c.meta.get("also") or []]:
            if t:
                targeted.setdefault(t, []).append(c)
    unf = []
    rs = view.all_reaches()
    for r in rs:
        if r.id in hit:
            continue
        why = reason_of(r, targeted.get(r.id, [])) if reason_of else None
        unf.append({"id": r.id, "reason": why or "no corpus step ended at this reach on the model with the real "
                                                  "contract reverting with the same revert key"})
    return {"reaches": len(rs), "falsified": len(rs) - len(unf), "unfalsified": unf}


def outcome_text(c: Compared) -> str:
    """The two sides of a step in a few words (reasons and logs)."""
    def side(x):
        if x["status"] == "revert":
            return "revert " + json.dumps(revert_key(x["revert"]))
        if x["status"] == "ok":
            return "ok"
        return f"{x['status']} ({x.get('reason', '')[:80]})"
    g = c.model.get("guard")
    return f"trace {c.tid} step {c.id}: model {side(c.model)}{' at ' + g if g else ''}, real {side(c.real)}"


def panic_groups(compared: list[Compared]) -> dict:
    """{(model span or None, code): [Compared]} of the steps where both sides Panic with the same code."""
    groups: dict = {}
    for c in compared:
        rc, mc = panic_code(c.real.get("revert")), panic_code(c.model.get("revert"))
        if rc is None or rc != mc:
            continue
        g = c.model.get("guard")
        src = g.split("#")[1] if isinstance(g, str) and g.count("#") >= 2 else None
        groups.setdefault((src, rc), []).append(c)
    return groups


def panics(groups: dict, located: dict | None = None) -> list[dict]:
    """The record's panics: one entry per (model span, code), src the located real site when there is one."""
    from .mreplay import in_span
    out = []
    for (src, code), cs in sorted(groups.items(), key=lambda kv: (kv[0][0] or "", kv[0][1])):
        site = (located or {}).get((src, code))
        e = {"src": site or src or "unknown", "code": "0x%02x" % code, "steps": len(cs), "model_src": src,
             "real_site": site}
        if site and src:
            e["site_agrees"] = in_span(src, site)
        out.append(e)
    return out


def by_action(compared: list[Compared]) -> dict:
    out: dict = {}
    for c in compared:
        a = out.setdefault(c.action, {"ok": 0, "revert": 0})
        a["ok" if c.real["status"] == "ok" else "revert"] += 1
    return dict(sorted(out.items()))


def build_record(runs: list[TraceRun], compared: list[Compared], entries: list[dict], view: DocView, root: Path,
                 reason_of=None, located: dict | None = None, extra: dict | None = None) -> dict:
    """results/M2/refinement/extracted.json (clauses 1 and 7): classes come from the entries' links only."""
    from .refinement import classify
    ds = []
    for e in sorted(entries, key=lambda x: x["id"]):
        ds.append({"id": e["id"], "class": classify(e, root), "links": e.get("links") or {}})
    rec = {"kind": RECORD_KIND, "traces": len(runs), "steps": len(compared), "disagreements": ds,
           "unexplained": sum(1 for d in ds if d["class"] == "unexplained"),
           "observables": list(OBSERVABLES), "storage_slots": sum(c.slots for c in compared),
           "by_action": by_action(compared), "panics": panics(panic_groups(compared), located),
           "guard_coverage": guard_coverage(view, compared, reason_of)}
    rec.update(extra or {})
    return rec


def file_disagreements(path: Path, new: list[dict]) -> list[dict]:
    """Append the new disagreements to the disagreements file (spec/M2/disagreements.json by default) as
    "unexplained" with no links, as holon.refinement.append_disagreements does, and return the entries of this run's
    ids as the file holds them (an existing entry keeps its links: its class is what they establish)."""
    path = Path(path)
    try:
        doc = json.loads(path.read_text()) if path.exists() else None
    except ValueError:
        raise FragmentsError(f"{path} is not JSON")
    if not isinstance(doc, dict) or not isinstance(doc.get("disagreements"), list):
        doc = {"disagreements": []}
    have = {e.get("id") for e in doc["disagreements"] if isinstance(e, dict)}
    added = 0
    for d in new:
        if d["id"] not in have:
            doc["disagreements"].append({**d, "class": "unexplained", "links": {}})
            have.add(d["id"])
            added += 1
    if added:
        write_json(path, doc)
    want = {d["id"] for d in new}
    return [e for e in doc["disagreements"] if isinstance(e, dict) and e.get("id") in want]


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


# ---------------------------------------------------------------- locating a real Panic (clause 9)
def locate_panics(proj: Path, tc: dict, binding: dict, groups: dict, init: list[int], slots: list[int]) -> dict:
    """{(model span, code): "<unit>:<line>"}: the real Panic's source line of the first step of each group, from a
    debugger dump of the binding's last-step contract (the kept steps that succeeded before it, then the step alone;
    holon.mreplay.locate_panic). A group whose step cannot be located is left out."""
    from .mreplay import locate_panic
    last = binding["harness"].get("last_contract")
    if not last:
        return {}
    out = {}
    for k, (key, cs) in enumerate(sorted(groups.items(), key=lambda kv: (kv[0][0] or "", kv[0][1]))):
        c = cs[0]
        if c.step is None:
            continue
        trace = list(c.prefix) + [Step(**{**c.step.__dict__, "fork": False})]
        fin = proj / f"holon_last_{k}.json"
        fout = proj / f"holon_last_{k}.out"
        dump = proj / f"holon_last_{k}.dump.json"
        fin.write_text(json.dumps(harness_input([trace], slots, init)))
        env = {"HOLON_STEPS_IN": fin.name, "HOLON_STEPS_OUT": fout.name}
        base = ["nice", "-n", "10", tc["forge"], "test", "--match-contract", f"^{last}$", "--match-test", "^test_last\\(\\)$",
                "--offline", "--use", tc["solc"]]
        code, outp = _run(base + ["--debug", "--dump", dump.name], proj, env)
        try:
            if code != 0 or not dump.exists() or dump.stat().st_size > MAX_DUMP:
                continue
            p = locate_panic(json.loads(dump.read_text()))
            if p and p["code"] == key[1]:
                out[key] = f"{unit_of(binding, p['path'])}:{p['line']}"
        finally:
            for f in (fin, fout, dump):
                f.unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------- the CLI
def _evaluator_label(spec: str | None) -> str:
    return spec or "holon.extracted_eval:step (model: holon.machine.load_extracted)"


def run(args) -> int:
    from . import fragments_corpus as FC
    from .replay import PIN_KEYS, check_checkout, morph_path, toolchain
    root = Path(args.root).resolve() if args.root else ROOT
    bpath = Path(args.binding)
    bpath = bpath if bpath.is_absolute() else root / bpath
    binding = load_binding(bpath)
    if not (args.facts or binding.get("facts")):
        raise FragmentsError("no transitions document: pass --facts or name one in the binding (\"facts\")")
    doc_path = Path(args.facts or binding.get("facts") or "")
    doc_path = doc_path if doc_path.is_absolute() else root / doc_path
    doc_bytes = doc_path.read_bytes()
    doc = json.loads(doc_bytes)
    sources = [s.strip() for s in (args.sources or ",".join(SOURCES)).split(",") if s.strip()]
    bad = sorted(set(sources) - set(SOURCES))
    if bad:
        raise FragmentsError(f"unknown corpus sources {bad} (known: {list(SOURCES)})")
    morph = None
    morph_sha = None
    if binding["project"]["kind"] == "checkout":
        morph = morph_path(args, root)
        morph_sha = check_checkout(morph, (doc.get("target") or {}).get("commit"))
    tc = toolchain(argparse.Namespace(forge=None, solc=None, write_pins=False, morph=str(morph) if morph else None), root)
    work = Path(args.work).resolve() if args.work else root / "build" / "fragments"
    work.mkdir(parents=True, exist_ok=True)
    proj = harness_project(binding, work, root, morph, tc)
    forge_build(proj, tc)
    tgt = Target.build(proj, binding, doc)
    view = tgt.view
    slots = view.dump_slots()
    init = FC.binding_init(binding, root)
    load, step_fn = load_evaluator(args.evaluator, root)
    src = binding.get("source")     # the extraction's source tree (a fixture's), else the configured checkout
    model = load(str(doc_path), str(root / src)) if (src and not args.evaluator) else load(str(doc_path))
    mismatch = check_reach_ids(model, view)
    if mismatch:
        raise FragmentsError(f"reach ids differ between the evaluator and holon.fragments_doc: {mismatch}")
    # corpus: base traces, a translation run, then the boundary and targeting forks
    base, counts = FC.base_traces(binding, root, args.corpus, sources, {f["name"]: f for f in tgt.fns.values()})
    if not base:
        raise FragmentsError("the corpus is empty (no abstract facts, witnesses or seed traces in the binding)")
    print(f"fragments: {len(base)} base traces ({', '.join(f'{k} {v}' for k, v in counts.items())}), "
          f"{sum(len(t) for t in base)} steps; {len(slots)} layout slots; {len(view.all_reaches())} reaches")
    runs = run_harness(proj, tc, binding, base, slots, init, args.max_steps, args.jobs, tag="translation")
    search = FC.Search(view, tgt, runs, slots)
    forks_b, forks_t, log, suffix = {}, {}, {}, []
    if "boundary" in sources:
        forks_b = search.boundary(view.widths())
    if "target" in sources:
        forks_t, log = search.target()
        suffix = search.suffixes(log, base)
    traces = FC.insert_forks(base, forks_b, forks_t) + suffix
    nb = sum(len(v) for v in forks_b.values())
    nt = sum(len(v) for v in forks_t.values())
    if nb or nt or suffix:
        print(f"fragments: {nb} boundary and {nt} targeting fork steps, {len(suffix)} suffix traces; second run")
        runs = run_harness(proj, tc, binding, traces, slots, init, args.max_steps, args.jobs, tag="full")
    wv = WidthValues(model, root) if not args.evaluator else None
    compared, new = compare_runs(runs, tgt, slots, model, step_fn, [wv.observe] if wv and wv.sites else [])
    groups = panic_groups(compared)
    located = {} if args.no_locate else locate_panics(proj, tc, binding, groups, init, slots)
    if args.no_file:
        entries = [{**d, "class": "unexplained", "links": {}} for d in new]
    else:
        dpath = Path(args.disagreements) if args.disagreements else root / "spec" / "M2" / "disagreements.json"
        entries = file_disagreements(dpath, new)
    reason_of = FC.reason_function(search, log, outcome_text)
    extra = {"facts": _rel(doc_path, root), "facts_sha256": hashlib.sha256(doc_bytes).hexdigest(),
             "binding": _rel(bpath, root), "evaluator": _evaluator_label(args.evaluator),
             "corpus": {**counts, "boundary": nb, "target": nt, "suffix": len(suffix), "m1_seed": FC.M1_SEED,
                        "inputs_sha256": sha256_json([c.input_sha for c in compared])},
             "storage_layout": {"slots": len(slots), "document": sum(1 for e in view.layout if e.source == "storage"),
                                "inherited": sum(1 for e in view.layout if e.source == "inherited_storage")},
             "command": harness_command(binding),
             "harness_notes": harness_notes(runs),
             "toolchain": {k: tc[k] for k in PIN_KEYS}}
    if morph_sha:
        extra["morph_commit"] = morph_sha
    rec = build_record(runs, compared, entries, view, root, reason_of, located, extra)
    out = Path(args.out) if args.out else root / RECORD
    out = out if out.is_absolute() else root / out
    write_json(out, rec)
    side = out.with_suffix("")      # results/M2/refinement/extracted/: what the run measures beside the comparison
    if wv and wv.sites:
        write_json(side / "width_values.json", wv.document(_rel(doc_path, root), rec["corpus"]["inputs_sha256"]))
    details = Path(args.details) if args.details else work / "details.json"
    write_json(details, run_details(runs, compared, log, view))
    print(f"fragments: {rec['traces']} traces, {rec['steps']} steps compared, {rec['storage_slots']} slot comparisons, "
          f"{len(rec['disagreements'])} disagreements ({rec['unexplained']} unexplained); reaches "
          f"{rec['guard_coverage']['reaches']}, falsified {rec['guard_coverage']['falsified']}; wrote {out}")
    for p in rec["panics"]:
        print(f"  panic {p['code']} at {p['src']} on {p['steps']} steps (model {p['model_src']})")
    return 0 if rec["unexplained"] == 0 else 1


class WidthValues:
    """The width sites' corpus evaluation (holon.sorts.width; the "width_corpus" of the adoption sidecar): for every
    width site of the milestone's adopted documents whose document is the refined one, every compared step of an entry
    point evaluates the site's stores on the extracted model (holon.sorts.width.store_values, holon.extracted_eval);
    the document records how many steps reach the store, the largest value stored, and the first values wider than the
    field (witness candidates)."""

    def __init__(self, model, root: Path):
        from .sorts import width
        self.width = width
        self.model = model
        rel = model.path.as_posix() if getattr(model, "path", None) else None
        ms = str(Path(rel).parts[1]) if rel and len(Path(rel).parts) > 2 else "M2"
        self.sites = [s for s in width.basis_elements(ms, root) if s["document"] == rel]
        self.acc = {width.site_id(s["span"], s["record"], s["field"]): {"steps": 0, "reaching": 0, "max": 0,
                                                                         "over": []} for s in self.sites}

    def observe(self, c, state, args, env) -> None:
        for s in self.sites:
            if c.action not in (s.get("entry_points") or []):
                continue
            a = self.acc[self.width.site_id(s["span"], s["record"], s["field"])]
            a["steps"] += 1
            vals = self.width.store_values(self.model, {"state": state, "action": c.action, "args": args, "env": env}, s)
            if vals:
                a["reaching"] += 1
                a["max"] = max(a["max"], max(vals))
                bad = [v for v in vals if v >> s["width"]]
                if bad and len(a["over"]) < 8:
                    a["over"].append({"trace": c.tid, "step": c.id, "value": hex(bad[0])})

    def document(self, facts_rel: str, inputs_sha: str) -> dict:
        sites = {}
        for s in self.sites:
            sid = self.width.site_id(s["span"], s["record"], s["field"])
            a = self.acc[sid]
            sites[sid] = {"span": s["span"], "field": s["field"], "width": s["width"],
                          "entry_points": s.get("entry_points") or [], "steps": a["steps"], "reaching": a["reaching"],
                          "max": hex(a["max"]), "over": a["over"]}
        return {"document": "width_values", "facts": facts_rel, "inputs_sha256": inputs_sha,
                "evaluator": "holon.extracted_eval (holon.sorts.width.store_values)", "sites": sites}


def harness_notes(runs: list[TraceRun]) -> dict:
    """{note: number of steps} of the concrete harness's notes (X lines; e.g. a rebuilt header whose hash differs from
    the stored one), so that a translation the harness could not do faithfully is visible in the record."""
    out: dict = {}
    for tr in runs:
        for e in tr.execs:
            for n in e.notes:
                out[n] = out.get(n, 0) + 1
    return dict(sorted(out.items()))


def _rel(p: Path, root: Path) -> str:
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.name


def run_details(runs: list[TraceRun], compared: list[Compared], log: dict, view: DocView) -> dict:
    """Per-step digests, the corpus search log and the reaches: kept for review, never compared by the tests."""
    return {"reaches": [r.as_dict() for r in view.all_reaches()], "search": log,
            "compared": [{"trace": c.tid, "step": c.id, "action": c.action, "input_sha256": c.input_sha,
                          "model": {k: c.model.get(k) for k in ("status", "guard", "reason") if k in c.model},
                          "real": {"status": c.real["status"], "revert": revert_key(c.real["revert"])
                                   if c.real["status"] == "revert" else None},
                          "diff": c.diff, "meta": c.meta} for c in compared],
            "runs_sha256": sha256_json([[(e.id, e.kind, e.ok, e.data, e.ret, e.writes, e.logs, e.calls)
                                         for e in tr.execs] for tr in runs])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon fragments", description=__doc__.split("\n\n")[0])
    ap.add_argument("--facts", help="the transitions document (default: the binding's \"facts\")")
    ap.add_argument("--binding", default=str(BINDING))
    ap.add_argument("--out")
    ap.add_argument("--details")
    ap.add_argument("--work")
    ap.add_argument("--morph")
    ap.add_argument("--root")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--max-steps", type=int, default=MAX_STEPS)
    ap.add_argument("--corpus", type=int, default=300, help="M1 refinement traces (the M1 corpus rule's size)")
    ap.add_argument("--sources", help=f"comma-separated corpus sources (default: {','.join(SOURCES)})")
    ap.add_argument("--evaluator", help="MODULE:FUNCTION or FILE.py:FUNCTION in place of holon.extracted_eval.step")
    ap.add_argument("--disagreements", help="the disagreements file (default: spec/M2/disagreements.json)")
    ap.add_argument("--no-file", action="store_true", help="do not append disagreements (they stay unexplained)")
    ap.add_argument("--no-locate", action="store_true", help="do not locate the real Panic sites (debugger dumps)")
    args = ap.parse_args(argv)
    try:
        return run(args)
    except (FragmentsError, abi.AbiError) as e:
        print(f"fragments: {e}", file=sys.stderr)
        return 2
