"""holon bundle2 corpus | deploy | refine (rules C1-C6, M3 and L1-L8 of the contract): the corpus, the forge harness of
the real members, and the refinement of the linked machine and of the member models against it.

corpus   gen/M3/bundle2/corpus.json: the m1 traces (holon.fragments_corpus.m1_traces on the sidecar's binding, I20's
         abstract rows), the sidecar's seed traces (sorted by label) and its random traces (random.Random(seed): per
         trace the prefix rows, then per step an op drawn from the sorted ops and one draw per field from its pool).
deploy   one forge run of the deployment alone: replay/M3/bundle2/deployment.json (members, created accounts, the
         members' non-zero slots after the deployment).
refine   one forge run of the whole corpus; every call step is compared with the linked machine (holon.bundle2.link)
         from the real pre-state of every member, and every top-level step on a modelled member with its compiled
         model (holon.sorts.evaluate3); writes results/M3/bundle2/{refinement,refinement_models,steps,
         disagreements}.json. --check re-runs nothing: the records must name the committed corpus and steps.json must
         recount to refinement.json.

The scratch project is the pinned checkout's Foundry tree (I20's binding's project section), the pinned dependencies
and the harness files: the sidecar's harness files under replay/M3/bundle2/ and I20's M1 harness they inherit.
"""
from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import BundleError, Ctx, Refused, Writer, render

CORPUS_VERSION = "holon-bundle2-corpus/0.1"
DEPLOY_VERSION = "holon-bundle2-deployment/0.1"
REF_VERSION = "holon-bundle2-refinement/0.1"
REFM_VERSION = "holon-bundle2-refinement-models/0.1"
ROW = 13
ENV_OPS = (9, 10, 11)
HARNESS_FILES = ["replay/M1/solidity/HolonTraceReplay.t.sol", "replay/M3/bundle2/HolonBundle2Base.sol",
                 "replay/M3/bundle2/HolonBundle2Step.t.sol"]
HARNESS_CONTRACT = "HolonBundle2StepTest"
MAX_STEPS = 300
MASK = (1 << 256) - 1


# ------------------------------------------------------------------------------------------------ the corpus
def _binding(ctx: Ctx) -> dict:
    from ..replay_fragments import load_binding
    return load_binding(ctx.root / ctx.side["corpus"]["m1"]["binding"])


def random_rows(side: dict) -> list:
    rp = side["corpus"]["random"]
    rng = random.Random(rp["seed"])
    ops = sorted(int(k) for k in rp["ops"])
    out = []
    for _ in range(int(rp["traces"])):
        tr = [list(r) for r in rp["prefix"]]
        for _ in range(int(rp["steps"])):
            op = rng.choice(ops)
            row = [op]
            for f in rp["ops"][str(op)]:
                row.append(rng.choice(rp["pools"][f]))
            tr.append(row + [0] * (ROW - len(row)))
        out.append(tr)
    return out


def build_corpus(ctx: Ctx) -> dict:
    from ..fragments_corpus import abstract_facts, binding_init, m1_traces
    from ..mreplay import encode_step
    b = _binding(ctx)
    m1 = ctx.side["corpus"]["m1"]
    facts = abstract_facts(b, ctx.root)
    traces = []
    for i, tr in enumerate(m1_traces(b, ctx.root, int(m1["traces"]), int(m1["seed"]))):
        traces.append({"source": "m1", "label": f"m1/{i}", "rows": [encode_step(a, facts) for a in tr]})
    for label in sorted(ctx.side["corpus"]["seed"]):
        traces.append({"source": "seed", "label": label, "rows": [list(r) for r in ctx.side["corpus"]["seed"][label]]})
    for i, rows in enumerate(random_rows(ctx.side)):
        traces.append({"source": "random", "label": f"random/{i}", "rows": rows})
    for t in traces:
        for r in t["rows"]:
            if len(r) != ROW:
                raise BundleError(f"{t['label']}: a row of {len(r)} words")
    return {"corpus_version": CORPUS_VERSION, "sidecar": {"path": ctx.side_rel, "sha256": ctx.side_sha},
            "init": binding_init(b, ctx.root), "traces": traces}


def run_corpus(ctx: Ctx, check: bool, _args=None) -> int:
    w = Writer(check)
    w.put(ctx.path("corpus"), render(build_corpus(ctx)))
    return w.finish("corpus")


# ------------------------------------------------------------------------------------------------ the project
def _toolchain(ctx: Ctx) -> dict:
    import argparse
    from ..replay import toolchain
    try:
        return toolchain(argparse.Namespace(forge=None, solc=None, write_pins=False), ctx.root)
    except SystemExit as e:
        raise Refused(str(e))


def project(ctx: Ctx, work: Path, tc: dict) -> Path:
    from ..replay import check_checkout
    from ..replay_fragments import FragmentsError, forge_build, harness_project
    b = _binding(ctx)
    checkout = Path(ctx.source()).resolve()
    try:
        check_checkout(checkout, ctx.side["target"]["head"])
    except SystemExit as e:
        raise Refused(str(e))
    binding = {"project": b["project"], "harness": {"files": HARNESS_FILES}}
    try:
        proj = harness_project(binding, work, ctx.root, checkout, tc)
        forge_build(proj, tc)
    except FragmentsError as e:
        raise BundleError(str(e))
    return proj


def artifact_of(proj: Path, unit: str, contract: str) -> dict:
    from ..replay_fragments import artifact
    return artifact(proj, unit.split("/", 1)[1] if unit.startswith("contracts/contracts/") else unit, contract)


def member_layouts(ctx: Ctx, proj: Path) -> list:
    """[(member index, member, compiled artifact)] in the sidecar's member order."""
    out = []
    for i, m in enumerate(ctx.members()):
        out.append((i, m, artifact_of(proj, m["source"], m["contract"])))
    return out


def dump_slots(art: dict) -> list:
    """Every slot a statically sized variable of the compiled layout occupies, and the length word of every dynamic
    array, bytes and string (holon.fragments_doc's rule over the compiler's layout)."""
    lay = art.get("storageLayout") or {}
    types = lay.get("types") or {}
    out = set()
    for v in lay.get("storage") or []:
        t = types.get(v["type"]) or {}
        enc = t.get("encoding")
        slot, off = int(v["slot"]), int(v["offset"])
        if enc == "mapping":
            continue
        if enc in ("bytes", "dynamic_array"):
            out.add(slot)
            continue
        n = int(t.get("numberOfBytes", 32))
        out.update(range(slot, slot + max(1, (n + off + 31) // 32)))
    return sorted(out)


# ------------------------------------------------------------------------------------------------ runs
@dataclass
class B2Exec:
    tid: int
    id: str
    kind: str
    ok: bool
    to: str | None
    caller: str | None
    value: int
    timestamp: int
    number: int
    blobs: list
    data: str
    ret: str
    env: dict = field(default_factory=dict)
    balances: dict = field(default_factory=dict)
    pokes: list = field(default_factory=list)     # (member, slot, word)
    writes: list = field(default_factory=list)    # (member, slot, value, reverted)
    logs: list = field(default_factory=list)      # (emitter, topics, data)
    frames: list = field(default_factory=list)    # (depth, caller, callee, selector, value, reverted)
    calls: list = field(default_factory=list)     # (from, to, data, value, ok, ret)
    dump: list | None = None
    notes: list = field(default_factory=list)


@dataclass
class B2Run:
    tid: int
    harness: str = ""
    members: list = field(default_factory=list)
    created: list = field(default_factory=list)
    code: dict = field(default_factory=dict)
    impl: dict = field(default_factory=dict)      # member -> (implementation, code)
    execs: list = field(default_factory=list)


ENV_KEYS = ("block.chainid", "block.basefee", "block.prevrandao", "block.coinbase", "block.gaslimit",
            "block.blobbasefee", "tx.origin", "tx.gasprice")


def _w(s: str) -> int:
    return 0 if s == "0" else int(s, 16)


def parse_output(text: str) -> list:
    runs: dict = {}
    cur: dict = {}
    pokes: dict = {}
    for line in text.splitlines():
        f = line.split(" ")
        tag = f[0]
        if tag == "T":
            runs[int(f[1])] = B2Run(int(f[1]), f[2].lower())
        elif tag == "M":
            runs[int(f[1])].members.append(f[3].lower())
        elif tag == "A":
            runs[int(f[1])].created.append(f[2].lower())
        elif tag == "K":
            runs[int(f[1])].code[f[2].lower()] = f[3].lower()
        elif tag == "Q":
            runs[int(f[1])].impl[f[2].lower()] = (f[3].lower(), f[4].lower())
        elif tag == "S":
            tid, sid = int(f[1]), f[2]
            e = B2Exec(tid, sid, f[3], f[4] == "1", None if f[5] == "-" else f[5].lower(),
                       None if f[6] == "-" else f[6].lower(), int(f[7]), int(f[8]), int(f[9]),
                       [] if f[10] == "-" else [b.lower() for b in f[10].split(",")], f[11].lower(), f[12].lower())
            e.pokes = pokes.pop((tid, sid), [])
            runs[tid].execs.append(e)
            cur[(tid, sid)] = e
        elif tag == "V":
            e = cur[(int(f[1]), f[2])]
            vals = f[3:]
            e.env = {k: (v.lower() if v.startswith("0x") else int(v)) for k, v in zip(ENV_KEYS, vals)}
            for kv in vals[len(ENV_KEYS)].split(","):
                a, _, b = kv.partition(":")
                e.balances[a.lower()] = int(b)
        elif tag == "P":
            pokes.setdefault((int(f[1]), f[2]), []).append((f[3].lower(), _w(f[4]), _w(f[5])))
        elif tag == "W":
            cur[(int(f[1]), f[2])].writes.append((f[3].lower(), int(f[4], 16), int(f[5], 16), f[6] == "1"))
        elif tag == "L":
            cur[(int(f[1]), f[2])].logs.append((f[3].lower(), [] if f[4] == "-" else [t.lower() for t in f[4].split(",")],
                                               f[5].lower()))
        elif tag == "F":
            cur[(int(f[1]), f[2])].frames.append((int(f[3]), f[4].lower(), f[5].lower(),
                                                 None if f[6] == "-" else f[6].lower(), int(f[7]), f[8] == "1"))
        elif tag == "C":
            cur[(int(f[1]), f[2])].calls.append((f[3].lower(), f[4].lower(), f[5].lower(), int(f[6]), f[7] == "1",
                                                f[8].lower()))
        elif tag == "D":
            cur[(int(f[1]), f[2])].dump = [] if f[3] == "-" else [_w(v) for v in f[3].split(",")]
        elif tag == "X":
            cur[(int(f[1]), f[2])].notes.append(" ".join(f[3:]))
    return [runs[k] for k in sorted(runs)]


def _encode(row: list) -> str:
    from .. import evm_abi as abi
    payload = abi.encode_args([{"type": "uint256[]"}], [[int(x) for x in row]])
    return "0x" + abi.encode_args([{"type": "uint8"}, {"type": "bool"}, {"type": "bytes"}],
                                  [1, False, "0x" + payload.hex()]).hex()


def run_traces(proj: Path, tc: dict, traces: list, slot_members: list, slots: list, init: list, jobs: int,
               max_steps: int = MAX_STEPS) -> list:
    """Every trace (a list of rows) through the harness, in chunks of about max_steps steps, jobs forge processes at a
    time; the parsed runs in trace order."""
    parts, lo, n = [], 0, 0
    for i, t in enumerate(traces):
        if n and n + len(t) + 1 > max_steps:
            parts.append((lo, i))
            lo, n = i, 0
        n += len(t) + 1
    if lo < len(traces):
        parts.append((lo, len(traces)))
    runs: list = [None] * len(traces)
    pending = []
    for k, (a, b) in enumerate(parts):
        fin, fout = proj / f"holon_b2_{k}.json", proj / f"holon_b2_{k}.out"
        fin.write_text(json.dumps({"lens": [len(t) for t in traces[a:b]],
                                   "steps": [_encode(r) for t in traces[a:b] for r in t],
                                   "slot_members": [int(x) for x in slot_members],
                                   "slots": ["0x%064x" % s for s in slots], "init": [int(x) for x in init]}))
        fout.unlink(missing_ok=True)
        cmd = ["nice", "-n", "10", tc["forge"], "test", "--match-contract", f"^{HARNESS_CONTRACT}$", "--match-test",
               "^test_steps\\(\\)$", "--offline", "--use", tc["solc"]]
        env = {**os.environ, "HOLON_STEPS_IN": fin.name, "HOLON_STEPS_OUT": fout.name, "HOLON_LO": "0",
               "HOLON_HI": str(b - a)}
        pending.append((k, a, b, fin, fout, cmd, env))
    active: list = []

    def finish(item, proc):
        k, a, b, fin, fout, _cmd, _env = item
        out, _ = proc.communicate()
        text = fout.read_text() if fout.exists() else ""
        if proc.returncode != 0 or not text.rstrip().endswith(f"DONE 0 {b - a}"):
            raise BundleError(f"harness chunk {k} (traces {a}..{b}) failed (exit {proc.returncode}): {(out or '')[-2500:]}")
        for r in parse_output(text):
            r.tid += a
            for e in r.execs:
                e.tid = r.tid
            runs[r.tid] = r
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
    for i, r in enumerate(runs):
        if r is None:
            raise BundleError(f"the harness recorded no run for trace {i}")
        if len([e for e in r.execs if e.id != "d"]) != len(traces[i]):
            raise BundleError(f"trace {i}: {len(r.execs) - 1} records for {len(traces[i])} steps")
    return runs


def track(run: B2Run, slot_members: list, slots: list) -> list:
    """(exec, state before, state after) per executed step, the deployment first; states are {member: {slot: word}}.
    A step's pokes are in its state before; its writes that were not reverted are in its state after (none when the
    call reverted). Every state after must equal the harness's vm.load dump (rule C4)."""
    state = {m: {} for m in run.members}
    out = []
    for e in run.execs:
        before = {m: dict(s) for m, s in state.items()}
        for m, sl, w in e.pokes:
            if w:
                before[m][sl] = w
            else:
                before[m].pop(sl, None)
        after = {m: dict(s) for m, s in before.items()}
        if e.ok or e.kind == "env":
            for m, sl, val, rev in e.writes:
                if rev:
                    continue
                if val:
                    after[m][sl] = val
                else:
                    after[m].pop(sl, None)
        if e.dump is not None:
            if len(e.dump) != len(slots):
                raise BundleError(f"trace {run.tid} step {e.id}: a dump of {len(e.dump)} slots for {len(slots)}")
            bad = [(i, hex(s)) for i, s, v in zip(slot_members, slots, e.dump) if after[run.members[i]].get(s, 0) != v]
            if bad:
                raise BundleError(f"trace {run.tid} step {e.id}: the tracked storage differs from vm.load at "
                                  f"{bad[:5]} (a write the recording missed)")
        out.append((e, before, after))
        state = after
    return out


def _work(ctx: Ctx, args) -> Path:
    if args is not None and getattr(args, "work", None):
        p = Path(args.work).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    return Path(tempfile.mkdtemp(prefix="holon-bundle2-"))


def _slots(ctx: Ctx, proj: Path) -> tuple[list, list]:
    sm, sl = [], []
    for i, _m, art in member_layouts(ctx, proj):
        for s in dump_slots(art):
            sm.append(i)
            sl.append(s)
    return sm, sl


def deployment_record(ctx: Ctx, run: B2Run, tracked: list) -> dict:
    _e, _b, after = tracked[0]
    names = [m["name"] for m in ctx.members()]
    if len(run.members) != len(names):
        raise BundleError(f"the harness deployed {len(run.members)} members for {len(names)}")
    members = {}
    for name, addr in zip(names, run.members):
        im = run.impl.get(addr)
        members[name] = {"address": addr, "implementation": im[0] if im else None,
                         "storage": {"0x%064x" % k: "0x%064x" % v for k, v in sorted(after[addr].items()) if v}}
    return {"deployment_version": DEPLOY_VERSION, "sidecar": {"path": ctx.side_rel, "sha256": ctx.side_sha},
            "harness": run.harness, "members": members, "created": sorted(set(run.created)),
            "init": None}


def run_deploy(ctx: Ctx, check: bool, args=None) -> int:
    corpus = _load(ctx.path("corpus"))
    tc = _toolchain(ctx)
    work = _work(ctx, args)
    try:
        proj = project(ctx, work, tc)
        sm, sl = _slots(ctx, proj)
        runs = run_traces(proj, tc, [[]], sm, sl, corpus["init"], 1)
        rec = deployment_record(ctx, runs[0], track(runs[0], sm, sl))
        rec["init"] = corpus["init"]
    finally:
        if args is None or not getattr(args, "work", None):
            shutil.rmtree(work, ignore_errors=True)
    w = Writer(check)
    w.put(ctx.path("deployment"), render(rec))
    return w.finish("deploy")


def _load(p: Path) -> dict:
    if not p.is_file():
        raise Refused(f"{p} is missing")
    return json.loads(p.read_text(encoding="utf-8"))


def run_refine(ctx: Ctx, check: bool, args=None) -> int:
    from .refine import refine, refine_check
    if check:
        return refine_check(ctx)
    return refine(ctx, args)

