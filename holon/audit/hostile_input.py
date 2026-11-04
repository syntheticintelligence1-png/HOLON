"""Auditor A2 of an audit round, M3 on: the auditor's hostile inputs at the entry points the facts name, run on the
compiled model and on the real code by HOLON's existing harnesses, and compared (whitepaper §9.5 A2, §8.7;
spec/<M>/lib/audit_loop.json auditor_types.A2).

    python -m holon audit hostile-input --milestone M --round n --spec FILE [--target COMMIT] [--checkout DIR]
                                        [--out PATH] [--work DIR] [--check]

The auditor chooses the inputs; this command chooses none. It runs them and judges the result.

The spec (holon-audit-a2-spec/0.1, JSON):
  {"spec_version": "holon-audit-a2-spec/0.1", "milestone": "M3", "cases": [
    {"id": "c1", "entry": {"kind": "action", "document": "<facts document>", "action": "<action of it>"},
     "call": {"args": {"<param>": <value>, ...} | "calldata": "0x..", "caller": "0x<20 bytes>", "value": 0,
              "timestamp": 0, "blobs": ["0x<32 bytes>", ...]},
     "pre": {"calls": [<call, with its "action">, ...], "storage": {"0x<slot>": "0x<word>"}}},
    {"id": "g1", "entry": {"kind": "go", "document": "<Go-op document>", "function": "<op of it>"},
     "input": {"set": [[<byte index>, <byte>], ...]}}]}
  An action case runs from the deployment: the pre calls in order (kept, each reported with the real status), then
  the case's call with the target's storage first set to pre.storage (vm.store). args are encoded with the target's
  compiled ABI (holon.evm_abi values); calldata is sent as given (a hostile encoding). timestamp 0 keeps the clock;
  caller defaults to the zero address. A go case runs one op of a Go-op document on one carrier value: the bytes of
  input.set, every other byte 0.

Per action case:
  model  the document's compiled model gen/<M>/sorts/models/<document stem>.bend, through holon.sorts.evaluate3 (the
         A/B interface of holon.replay_fragments), on the real pre-state of the step;
  real   the step harness of the binding under replay/ whose "facts" is the document (holon.replay_fragments: forge
         and solc against the pinned checkout, every storage write recorded);
  compared as holon.replay_fragments.compare does: status, the revert data's key, and on two oks every storage slot
  either side writes and the emitted logs.
Per go case:
  model  the Go-op document's compiled model (holon.gen.goloop.CompiledModel): the op's outcome class (ORet, OErr,
         OPanic) on the cells the op reads (Shape.cell_map) of the carrier value;
  real   holon.goreplay.run_cases: the op called on that carrier value under recover(), from a generated Go test in a
         scratch copy of the pinned checkout; its outcome class (a nil error, an error, a panic).
Verdicts: "agree", "disagree" (the observables that differ), "unsupported" (with the reason: no binding, no compiled
model, an action the document does not name, a call that reaches no document action, the model's own "unsupported").

Output: audit/rounds/<M>/round<n>/a2.json (holon-audit-a2/0.1; json.dumps(indent=1, sort_keys=True) + newline; no
timestamps, no scratch paths), whose "attack" is the round file's attack entry (run true); the measured seconds go to
a2.timings.json beside it. --check reruns and compares a2.json byte for byte. Nothing here names a law or a target:
names come from the spec, the documents, the bindings and the configuration. The test oracle is never read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

from .mutation import ROOT, MutationError, archive, git_out, rel_path, resolve_commit, sha256_bytes, sha256_file

SPEC_VERSION = "holon-audit-a2-spec/0.1"
A2_VERSION = "holon-audit-a2/0.1"
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
HEX = re.compile(r"^0x([0-9a-fA-F]{2})*$")
ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")
WORD = re.compile(r"^0x[0-9a-fA-F]{1,64}$")
CALL_KEYS = {"args", "calldata", "caller", "value", "timestamp", "blobs"}
GO_CLASS = {"ok": "ORet", "err": "OErr", "panic": "OPanic"}


class HostileInputError(RuntimeError):
    """Refused: nothing is written."""


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ================================================================================================ the spec
def _call_problems(c, w: str, with_action: bool) -> list[str]:
    if not isinstance(c, dict):
        return [f"{w}: not an object"]
    bad = []
    keys = CALL_KEYS | ({"action"} if with_action else set())
    if set(c) - keys:
        bad.append(f"{w}: unknown fields {sorted(set(c) - keys)}")
    if with_action and not isinstance(c.get("action"), str):
        bad.append(f"{w}: action must name an action of the document")
    if ("args" in c) == ("calldata" in c):
        bad.append(f"{w}: give exactly one of args and calldata")
    if "args" in c and not isinstance(c["args"], dict):
        bad.append(f"{w}: args must be an object of parameter values")
    if "calldata" in c and not (isinstance(c["calldata"], str) and HEX.match(c["calldata"])):
        bad.append(f"{w}: calldata must be 0x-hex")
    if "caller" in c and not (isinstance(c["caller"], str) and ADDR.match(c["caller"])):
        bad.append(f"{w}: caller must be a 20-byte 0x address")
    for k in ("value", "timestamp"):
        if k in c and not (isinstance(c[k], int) and not isinstance(c[k], bool) and 0 <= c[k] < 2 ** 256):
            bad.append(f"{w}: {k} must be a uint256")
    if "blobs" in c and not (isinstance(c["blobs"], list) and all(isinstance(b, str) and HEX.match(b)
                                                                  and len(b) == 66 for b in c["blobs"])):
        bad.append(f"{w}: blobs must be 32-byte 0x words")
    return bad


def spec_problems(spec, milestone: str) -> list[str]:
    if not isinstance(spec, dict):
        return ["not a JSON object"]
    bad = []
    if set(spec) - {"spec_version", "milestone", "cases", "note"}:
        bad.append(f"unknown fields {sorted(set(spec) - {'spec_version', 'milestone', 'cases', 'note'})}")
    if spec.get("spec_version") != SPEC_VERSION:
        bad.append(f"spec_version must be {SPEC_VERSION!r}")
    if spec.get("milestone", milestone) != milestone:
        bad.append(f"milestone {spec.get('milestone')!r} is not {milestone!r}")
    cs = spec.get("cases")
    if not isinstance(cs, list) or not cs:
        return bad + ["cases must be a non-empty list"]
    seen = set()
    for i, c in enumerate(cs):
        w = f"cases[{i}]"
        if not isinstance(c, dict):
            bad.append(f"{w}: not an object")
            continue
        if not isinstance(c.get("id"), str) or not ID.match(c["id"]):
            bad.append(f"{w}: id must match {ID.pattern}")
        elif c["id"] in seen:
            bad.append(f"{w}: id {c['id']} repeats")
        else:
            seen.add(c["id"])
        e = c.get("entry")
        kind = e.get("kind") if isinstance(e, dict) else None
        if kind == "action":
            if set(e) != {"kind", "document", "action"} or not all(isinstance(e[k], str) for k in ("document",
                                                                                                    "action")):
                bad.append(f"{w}: an action entry is {{kind, document, action}}")
            if set(c) - {"id", "entry", "call", "pre", "note"}:
                bad.append(f"{w}: unknown fields {sorted(set(c) - {'id', 'entry', 'call', 'pre', 'note'})}")
            bad += _call_problems(c.get("call"), f"{w}.call", False)
            pre = c.get("pre", {})
            if not isinstance(pre, dict) or set(pre) - {"calls", "storage"}:
                bad.append(f"{w}.pre: takes calls and storage only")
            else:
                for j, pc in enumerate(pre.get("calls") or []):
                    bad += _call_problems(pc, f"{w}.pre.calls[{j}]", True)
                st = pre.get("storage", {})
                if not (isinstance(st, dict) and all(isinstance(k, str) and WORD.match(k) and isinstance(v, str)
                                                     and WORD.match(v) for k, v in st.items())):
                    bad.append(f"{w}.pre.storage: {{0x<slot>: 0x<word>}}")
        elif kind == "go":
            if set(e) != {"kind", "document", "function"} or not all(isinstance(e[k], str) for k in ("document",
                                                                                                      "function")):
                bad.append(f"{w}: a go entry is {{kind, document, function}}")
            if set(c) - {"id", "entry", "input", "note"}:
                bad.append(f"{w}: unknown fields {sorted(set(c) - {'id', 'entry', 'input', 'note'})}")
            inp = c.get("input")
            if not (isinstance(inp, dict) and set(inp) == {"set"} and isinstance(inp["set"], list)
                    and all(isinstance(p, list) and len(p) == 2 and all(isinstance(x, int) and not isinstance(x, bool)
                                                                       for x in p) and p[0] >= 0 and 0 <= p[1] <= 255
                            for p in inp["set"])
                    and len({p[0] for p in inp["set"]}) == len(inp["set"])):
                bad.append(f"{w}.input: {{set: [[byte index >= 0, byte 0..255], ...]}} with distinct indices")
        else:
            bad.append(f"{w}: entry.kind must be action or go")
    return bad


def load_spec(path: Path, milestone: str) -> dict:
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise HostileInputError(f"the spec {path} does not parse: {e}") from None
    bad = spec_problems(spec, milestone)
    if bad:
        raise HostileInputError("the spec is malformed:\n  " + "\n  ".join(bad))
    return spec


# ================================================================================================ helpers
def unsupported(c: dict, why: str) -> dict:
    return {"id": c["id"], "entry": c["entry"], "verdict": "unsupported", "why": why}


def bindings(tree: Path) -> dict[str, str]:
    """{document: binding path} of every step-harness binding under replay/ (holon.replay_fragments.load_binding's
    shape: facts, harness, target, project)."""
    out: dict[str, str] = {}
    for p in sorted((tree / "replay").rglob("*.json")):
        if p.stat().st_size > 200_000:
            continue
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(b, dict) and {"facts", "harness", "target", "project"} <= set(b) and isinstance(b["facts"], str):
            out.setdefault(b["facts"], p.relative_to(tree).as_posix())
    return out


def model_of(tree: Path, milestone: str, doc_rel: str) -> str | None:
    stem = Path(doc_rel).name[: -len(".json")] if doc_rel.endswith(".json") else Path(doc_rel).name
    rel = f"gen/{milestone}/sorts/models/{stem}.bend"
    return rel if (tree / rel).is_file() else None


def word_int(s: str) -> int:
    return int(s, 16)


class Ctx:
    def __init__(self, milestone: str, rnd: int, spec_path: Path, spec: dict, commit: str, work: Path,
                 checkout_arg: str | None):
        self.milestone, self.rnd, self.spec, self.spec_path, self.commit, self.work = (milestone, rnd, spec, spec_path,
                                                                                       commit, work)
        self.checkout_arg = checkout_arg
        self.timings: dict = {}
        t0 = time.monotonic()
        self.tree = archive(ROOT, commit, work / "target", (f"gen/{milestone}/refute", "spec/heldout"))
        self.timings["stage_s"] = round(time.monotonic() - t0, 1)
        self.cfg = json.loads((self.tree / "config" / "holon.json").read_text(encoding="utf-8"))
        self.places = {"work": work, "root": ROOT, "home": Path.home()}

    def scrub(self, text: str, n: int = 400) -> str:
        from ..mutate.common import scrub
        return scrub(str(text or ""), self.places)[-n:].strip()

    def checkout_for(self, doc: dict) -> Path:
        t = doc.get("target") or {}
        co = self.checkout_arg or ((self.cfg.get("extract") or {}).get("sources") or {}).get(t.get("repo"))
        if not co:
            raise HostileInputError(f"no checkout of {t.get('repo')}: config extract.sources names none; pass "
                                    "--checkout")
        co = Path(co).resolve()
        head = git_out(co, "rev-parse", "HEAD").stdout.decode().strip()
        if head != t.get("commit"):
            raise HostileInputError(f"the checkout {co} is at {head or '?'}, the document at {t.get('commit')}")
        dirty = git_out(co, "status", "--porcelain", "--untracked-files=no").stdout.decode().strip()
        if dirty:
            raise HostileInputError(f"the checkout {co} has local changes: {dirty[:300]}")
        self.places["checkout"] = co
        return co


# ================================================================================================ action cases
def run_actions(ctx: Ctx, doc_rel: str, cases: list[dict]) -> list[dict]:
    from .. import evm_abi as abi
    from .. import fragments_corpus as FC
    from .. import replay_fragments as RF
    from ..replay import toolchain
    tree = ctx.tree
    if not (tree / doc_rel).is_file():
        return [unsupported(c, f"{doc_rel} is not a document of the target tree") for c in cases]
    bmap = bindings(tree)
    if doc_rel not in bmap:
        return [unsupported(c, f"no step-harness binding under replay/ names {doc_rel} as its facts") for c in cases]
    mrel = model_of(tree, ctx.milestone, doc_rel)
    if mrel is None:
        return [unsupported(c, f"{doc_rel} has no compiled model gen/{ctx.milestone}/sorts/models/<stem>.bend")
                for c in cases]
    binding = RF.load_binding(tree / bmap[doc_rel])
    doc = json.loads((tree / doc_rel).read_text(encoding="utf-8"))
    checkout = ctx.checkout_for(doc) if binding["project"]["kind"] == "checkout" else None
    import argparse
    tc = toolchain(argparse.Namespace(forge=None, solc=None, write_pins=False), tree)
    t0 = time.monotonic()
    proj = RF.harness_project(binding, ctx.work / "sol" / hashlib.sha256(doc_rel.encode()).hexdigest()[:12], tree,
                              checkout, tc)
    RF.forge_build(proj, tc)
    tgt = RF.Target.build(proj, binding, doc)
    ctx.timings[f"build:{doc_rel}"] = round(time.monotonic() - t0, 1)
    slots = tgt.view.dump_slots()
    init = FC.binding_init(binding, tree)
    t0 = time.monotonic()
    load, step_fn = RF.load_evaluator(str(tree / mrel), tree)
    model = load(str(tree / doc_rel))
    ctx.timings[f"model:{doc_rel}"] = round(time.monotonic() - t0, 1)
    sel_of = {a: s for s, a in tgt.view.by_selector.items()}

    def step_for(call: dict, action: str | None) -> tuple[object | None, str | None]:
        if "calldata" in call:
            data = call["calldata"].lower()
        else:
            if action not in tgt.view.actions:
                return None, f"{action!r} is not an action of {doc_rel}"
            sel = sel_of.get(action)
            fn = tgt.fns.get(sel) if sel else None
            if fn is None:
                return None, f"the compiled ABI has no function for the action {action!r} (a receive or fallback)"
            missing = sorted({i["name"] for i in fn["inputs"]} - set(call["args"]))
            if missing:
                return None, f"args lack {missing}"
            try:
                data = sel + abi.encode_args(fn["inputs"], call["args"]).hex()
            except Exception as e:  # noqa: BLE001: a value the encoder refuses is the spec's error, reported
                return None, f"args do not encode: {type(e).__name__}: {str(e)[:200]}"
        return RF.Step("call", caller=(call.get("caller") or RF.ZERO_ADDR).lower(), value=call.get("value", 0),
                       timestamp=call.get("timestamp", 0), blobs=[b.lower() for b in call.get("blobs") or []],
                       data=data, meta={"source": "a2"}), None

    out: dict[str, dict] = {}
    traces, owners = [], []
    for c in cases:
        if c["entry"]["action"] not in tgt.view.actions:
            out[c["id"]] = unsupported(c, f"{c['entry']['action']!r} is not an action of {doc_rel}")
            continue
        steps, why = [], None
        for pc in (c.get("pre") or {}).get("calls") or []:
            st, why = step_for(pc, pc["action"])
            if why:
                break
            steps.append(st)
        if why is None:
            st, why = step_for(c["call"], c["entry"]["action"])
        if why:
            out[c["id"]] = unsupported(c, why)
            continue
        st.pokes = [(word_int(k), word_int(v)) for k, v in sorted((c.get("pre") or {}).get("storage", {}).items(),
                                                                  key=lambda kv: word_int(kv[0]))]
        steps.append(st)
        traces.append(steps)
        owners.append(c)
    if traces:
        t0 = time.monotonic()
        runs = RF.run_harness(proj, tc, binding, traces, slots, init, RF.MAX_STEPS, 1, tag="a2")
        ctx.timings[f"harness:{doc_rel}"] = round(time.monotonic() - t0, 1)
        for tr, c in zip(runs, owners):
            out[c["id"]] = compare_trace(ctx, RF, tgt, slots, tr, c, model, step_fn)
    return [out[c["id"]] for c in cases]


def compare_trace(ctx: Ctx, RF, tgt, slots, tr, c: dict, model, step_fn) -> dict:
    tracked = [x for x in RF.track(tr, slots) if x[0].id != "d"]
    pre = [{"action": tgt.action_of(e.data), "real": "ok" if e.ok else "revert"} for e, _b, _a in tracked[:-1]]
    e, before, after = tracked[-1]
    rec = {"id": c["id"], "entry": c["entry"], "pre": pre}
    mc = RF.model_call(tgt, e, before, tr.target, tr.code, tr.impl_code)
    real = RF.real_outcome(e, before, after)
    rec["real"] = {"status": real["status"], "revert_key": RF.revert_key(real["revert"]) if real["status"] == "revert"
                   else None, "writes": real["writes"], "events": len(real["events"])}
    if mc is None:
        rec.update(verdict="unsupported", why="the call reaches no action of the document (its selector is not one)")
        return rec
    action, state, args, env = mc
    try:
        m = RF._norm_model(step_fn(model, state, action, args, env))
    except Exception as ex:  # noqa: BLE001: the evaluator's failure is reported, never skipped
        m = {"status": "error", "revert": None, "writes": {}, "events": [], "guard": None,
             "reason": ctx.scrub(f"{type(ex).__name__}: {ex}", 300)}
    rec["model"] = {"status": m["status"], "revert_key": RF.revert_key(m["revert"]) if m["status"] == "revert" else None,
                    "writes": m["writes"], "events": len(m["events"]), "guard": m.get("guard")}
    if m["status"] not in ("ok", "revert"):
        rec["model"]["reason"] = m.get("reason")
        if m["status"] == "unsupported":
            rec.update(verdict="unsupported", why=f"the model: {m.get('reason')}")
            return rec
    diff, n = RF.compare(m, real, before, after)
    rec["slots_compared"] = n
    rec["verdict"] = "disagree" if diff else "agree"
    if diff:
        rec["differ"] = diff
    return rec


# ================================================================================================ go cases
def run_go(ctx: Ctx, doc_rel: str, cases: list[dict]) -> list[dict]:
    from .. import bend, goreplay
    from ..gen import goloop as GG
    tree = ctx.tree
    p = tree / doc_rel
    if not p.is_file():
        return [unsupported(c, f"{doc_rel} is not a document of the target tree") for c in cases]
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not (isinstance(doc.get("ops"), dict) and isinstance(doc.get("carrier"), dict) and doc.get("document")):
        return [unsupported(c, f"{doc_rel} is not a Go-op document (ops, carrier, document)") for c in cases]
    go_doc = json.loads((tree / doc["document"]).read_text(encoding="utf-8"))
    ctx.checkout_for(go_doc)
    t0 = time.monotonic()
    cm = GG.CompiledModel.build(doc, sha256_bytes(p.read_bytes()), doc["component"], bend.config(tree))
    ctx.timings[f"model:{doc_rel}"] = round(time.monotonic() - t0, 1)
    out: dict[str, dict] = {}
    ops, runs, plan = {}, [], {}
    for c in cases:
        o = c["entry"]["function"]
        if o not in doc["ops"]:
            out[c["id"]] = unsupported(c, f"{o!r} is not an op of {doc_rel} (ops: {sorted(doc['ops'])})")
            continue
        shape = cm.shapes.get(o)
        if shape is None or isinstance(shape, GG.Unsupported):
            out[c["id"]] = unsupported(c, f"the compiled model has no shape for {o}: {shape}")
            continue
        if goreplay._go_ident(doc["ops"][o]["source"]) is None:
            out[c["id"]] = unsupported(c, f"{o}'s function {doc['ops'][o]['source']} cannot be called from a "
                                          "generated test (a method, or not exported)")
            continue
        stride, base, n = shape.cell_map()
        byte = {i: v for i, v in c["input"]["set"]}
        cells = [byte.get(stride * k + base, 0) for k in range(n)]
        try:
            m = cm.outcomes([o], cells)[o]
        except Exception as ex:  # noqa: BLE001: reported, never skipped
            out[c["id"]] = unsupported(c, ctx.scrub(f"the compiled model failed: {type(ex).__name__}: {ex}", 300))
            continue
        unread = sorted(i for i in byte if (i - base) % stride or not 0 <= (i - base) // stride < n)
        plan[c["id"]] = {"model": m, "cells": n, "unread_bytes": len(unread)}
        ops[o] = (doc["ops"][o]["source"], len(doc["ops"][o]["results"]))
        runs.append({"key": c["id"], "op": o, "set": sorted(c["input"]["set"])})
    if runs:
        t0 = time.monotonic()
        try:
            got, command = goreplay.run_cases(tree, go_doc, doc["carrier"]["type"], ops, runs)
        except goreplay.Refused as e:
            got, command = None, ctx.scrub(str(e), 400)
        ctx.timings[f"go:{doc_rel}"] = round(time.monotonic() - t0, 1)
        for c in cases:
            if c["id"] not in plan:
                continue
            pl = plan[c["id"]]
            rec = {"id": c["id"], "entry": c["entry"], "model": {"class": pl["model"], "cells_read": pl["cells"]},
                   "bytes_the_model_does_not_read": pl["unread_bytes"]}
            if got is None:
                rec.update(verdict="unsupported", why=f"the generated Go test did not run: {command}")
            else:
                r = got.get(c["id"], "")
                cls = GO_CLASS.get(r.split(":", 1)[0])
                rec["real"] = {"class": cls, "detail": ctx.scrub(r, 200)}
                rec["verdict"] = "agree" if cls == pl["model"] else "disagree"
                if cls != pl["model"]:
                    rec["differ"] = ["outcome class"]
            out[c["id"]] = rec
    return [out[c["id"]] for c in cases]


# ================================================================================================ the record
def build(milestone: str, rnd: int, spec_path: Path, commit: str, work: Path, checkout: str | None) -> tuple[dict, dict]:
    spec = load_spec(spec_path, milestone)
    ctx = Ctx(milestone, rnd, spec_path, spec, commit, work, checkout)
    by: dict[tuple, list] = {}
    for c in spec["cases"]:
        by.setdefault((c["entry"]["kind"], c["entry"]["document"]), []).append(c)
    res: dict[str, dict] = {}
    for (kind, doc), cs in sorted(by.items()):
        log(f"hostile-input: {len(cs)} {kind} case(s) on {doc}")
        try:
            got = run_actions(ctx, doc, cs) if kind == "action" else run_go(ctx, doc, cs)
        except HostileInputError:
            raise
        except Exception as ex:  # noqa: BLE001: a harness that fails is reported per case, with its error
            got = [unsupported(c, ctx.scrub(f"the harness failed: {type(ex).__name__}: {ex}", 500)) for c in cs]
        for r in got:
            res[r["id"]] = r
    cases = [res[c["id"]] for c in spec["cases"]]
    summary = {v: sorted(r["id"] for r in cases if r["verdict"] == v) for v in ("agree", "disagree", "unsupported")}
    spec_rel = rel_path(spec_path)
    rd = f"audit/rounds/{milestone}/round{rnd}"
    tried = (f"`python -m holon audit hostile-input --milestone {milestone} --round {rnd} --spec {spec_rel}`: "
             f"{len(cases)} hostile input(s) of the auditor's choosing; {len(summary['agree'])} agree, "
             f"{len(summary['disagree'])} disagree, {len(summary['unsupported'])} unsupported (reasons in the "
             f"record).")
    if summary["disagree"]:
        tried += (" Each disagreement is the auditor's to judge (the model or the code is wrong); file the real "
                  "defects as findings and list their ids.")
    rec = {"a2_version": A2_VERSION, "milestone": milestone, "round": rnd, "target_commit": commit,
           "spec": {"path": spec_rel, "sha256": sha256_file(spec_path), "body": spec},
           "cases": cases, "summary": summary,
           "attack": {"id": "A2", "category": "model_vs_code", "auditor_type": "A2", "run": True, "tried": tried,
                      "result": "finding" if summary["disagree"] else "no_finding", "findings": [],
                      "evidence": [f"{rd}/a2.json"] + ([spec_rel] if spec_rel.startswith(rd + "/") else [])}}
    return rec, ctx.timings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon audit hostile-input", description=__doc__.split("\n\n")[0])
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--spec", required=True, help="the auditor's input spec (holon-audit-a2-spec/0.1)")
    ap.add_argument("--target", help="the audited commit of this repository (default HEAD)")
    ap.add_argument("--checkout", help="the target's checkout (default: config extract.sources of its repository)")
    ap.add_argument("--out", help="default audit/rounds/<M>/round<n>/a2.json")
    ap.add_argument("--work", help="scratch directory, kept (default: a fresh temporary directory, removed after)")
    ap.add_argument("--check", action="store_true", help="rerun and compare with the committed a2.json byte for byte")
    a = ap.parse_args(argv)
    if a.round < 1:
        print("hostile-input: rounds are numbered from 1", file=sys.stderr)
        return 2
    out = Path(a.out) if a.out else ROOT / "audit" / "rounds" / a.milestone / f"round{a.round}" / "a2.json"
    out = out if out.is_absolute() else ROOT / out
    target = a.target
    if a.check:
        if not out.is_file():
            print(f"hostile-input --check: {out} does not exist", file=sys.stderr)
            return 2
        target = json.loads(out.read_text(encoding="utf-8"))["target_commit"]
    work = Path(a.work).resolve() if a.work else Path(tempfile.mkdtemp(prefix="holon-a2-"))
    try:
        commit = resolve_commit(target or "HEAD")
        rec, timings = build(a.milestone, a.round, Path(a.spec).resolve(), commit, work, a.checkout)
    except (HostileInputError, MutationError) as e:
        print(f"hostile-input: refused: {e}", file=sys.stderr)
        return 2
    finally:
        if not a.work:
            shutil.rmtree(work, ignore_errors=True)
    text = dumps(rec)
    if a.check:
        same = out.read_text(encoding="utf-8") == text
        print(f"hostile-input --check: {'identical' if same else 'DIFFERS from'} {rel_path(out)}")
        return 0 if same else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    (out.parent / (out.stem + ".timings.json")).write_text(dumps(timings), encoding="utf-8")
    print(f"hostile-input: wrote {rel_path(out)}: " + ", ".join(f"{len(v)} {k}" for k, v in rec["summary"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
