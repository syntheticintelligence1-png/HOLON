"""Stepping real transactions through the extracted model, unchanged (I23; the contract is the docstring of
tests_m2/test_historical_exit.py, "historical trans").

The model is I20's: holon.machine.load_extracted of the instrument's transitions document, evaluated by
holon.extracted_eval with its own semantics. This module only observes a step; it changes no evaluation:

  SlotState    the pre-state of a step, a dict whose reads are recorded. A slot without a value is never read as 0
               (holon.extracted_eval's default for a missing slot): the read raises Unsupported, so the step is
               "unsupported" (I20's rule), and the slot is listed in `missing` for the acquisition to fetch.
  Traced       holon.extracted_eval.Eval, observed: before Eval.run evaluates a record, `visit` notes what the step
               evaluates (below); Eval.run then runs that record exactly as it would. `answer` notes every external
               call the step asks env for.
  traced_step  holon.extracted_eval.step with a Traced evaluator (the same result shape and status rules).

What a step evaluated (its "sites"): the distinct source lines ("<path>:<line>", every line of a record's span) of
  - every check (guard reach, implicit check, panic record, external-call check) that the program reached and whose
    context holds. A check's context is the extractor's ["||", ["!", K], c] form (holon.frontends.solidity.
    transitions: "["||", ["!", K], c] under the context K"); an external call's is its record's "cond" (K). A check of
    another form is evaluated whenever reached. A record in an untaken branch (K false) is not evaluated;
  - every storage write the program reached whose cond holds;
  - every width-site store (holon.sorts.width.transitions_stores: a memory store that narrows a wider value) that
    the program reached and whose cond holds, with the value it stores and the field's width.
Reached means: in program order before the step stopped (a revert or an unsupported term stops it), loop bodies once
per iteration.

The step's external calls ("calls"): every external-call check evaluated (in order) as {fn, to, args}: the callee is
its record's receiver term, the arguments its argument terms, evaluated by the step. A call term the step evaluates
outside such a check (holon.extracted_eval answers it from env) is added once per distinct (fn, to, args).

Environment (env) of a real transaction: caller and tx.origin = the transaction's sender; this = the instrument's
proxy; msg.value and msg.data.length from the transaction; blobhash = its blob versioned hashes; block.number,
block.timestamp, block.basefee, block.gaslimit, block.coinbase and block.prevrandao from the block header; calls = the
answers given (call items). Nothing else is given: a term that needs another value is unsupported, never guessed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import extracted_eval as X
from ..machine import Check, MStore, Write, source_span

ROOT = Path(__file__).resolve().parents[2]
INSTRUMENT = "historical_exit.json"


class StepperError(RuntimeError):
    pass


def instrument(milestone: str = "M2", root: Path = ROOT) -> dict:
    p = Path(root) / "spec" / milestone / "lib" / INSTRUMENT
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError) as e:
        raise StepperError(f"the instrument {p} is missing or unreadable: {e}") from None


def hex_addr(v) -> str:
    return "0x" + ("%064x" % X.to_int(v))[-40:]


def slot_key(address: str, slot: int) -> str:
    return f"{address.lower()}:0x{slot:064x}"


def call_key(to: str, data: str, frm: str) -> str:
    """The supplement's key of a call: callee, sha256 of the calldata bytes, sender."""
    return f"{to.lower()}:{hashlib.sha256(bytes.fromhex(data[2:])).hexdigest()}:{frm.lower()}"


def span_lines(src) -> list[str]:
    """Every source line of a span "<path>:<lo>[-<hi>]" as "<path>:<line>" ([] for a span that is no source span)."""
    sp = source_span(src)
    if sp is None:
        return []
    unit, lo, hi = sp
    return [f"{unit}:{n}" for n in range(lo, hi + 1)]


def context(c: Check):
    """The context K under which a check is evaluated (module docstring); 1 when it has none."""
    if c.section == "calls" and isinstance(c.entry, dict) and "cond" in c.entry:
        return c.entry["cond"]
    e = c.expr
    if isinstance(e, list) and len(e) == 3 and e[0] == "||" and isinstance(e[1], list) and len(e[1]) == 2 \
            and e[1][0] == "!":
        return e[1][1]
    return 1


def _callok(t):
    """The ["callok", fn, receiver, args..] term of an external-call check's expression."""
    if isinstance(t, list) and t and t[0] == "callok":
        return t
    if isinstance(t, list) and t and t[0] == "||":
        for x in t[1:]:
            r = _callok(x)
            if r is not None:
                return r
    return None


def arg_value(v):
    """A call argument as the step's record shows it: a word as an int, bytes as 0x-hex."""
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex()
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    return X.canonical(v) if not isinstance(v, str) else v


class SlotState(dict):
    """A step's pre-state (slot int -> word int) whose reads are recorded; a missing slot is unsupported."""

    def __init__(self, values: dict, reads: set, missing: set):
        dict.__init__(self, values)
        self.reads, self.missing = reads, missing

    def get(self, k, default=None):  # noqa: ARG002 - the evaluator's default 0 is never used
        self.reads.add(k)
        if dict.__contains__(self, k):
            return dict.__getitem__(self, k)
        self.missing.add(k)
        raise X.Unsupported(f"storage slot 0x{k:064x} has no value: the supplement holds none (never read as 0)")


class Plan:
    """What a step observes of an action's program: the width-site store spans (field width per span) and, per
    called function, the receiver terms of its call records."""

    def __init__(self, model, doc_rel: str):
        from ..sorts import width as W
        self.width_spans: dict = {}
        for s in W.transitions_stores(doc_rel, model.doc):
            if isinstance(s.get("span"), str):
                self.width_spans.setdefault(s["span"], s["width"])
        self.receivers: dict = {}
        for a in model.doc.get("actions") or []:
            for r in a.get("calls") or []:
                if isinstance(r, dict) and isinstance(r.get("fn"), str):
                    self.receivers.setdefault((a["name"], r["fn"]), [])
                    if r.get("receiver") not in self.receivers[(a["name"], r["fn"])]:
                        self.receivers[(a["name"], r["fn"])].append(r.get("receiver"))


class Traced(X.Eval):
    """holon.extracted_eval.Eval, observed (module docstring). Every evaluation is Eval's own."""

    def __init__(self, model, state: SlotState, action: str, args: dict, env: dict, plan: Plan):
        super().__init__(model, {}, action, args, env)
        self.state = state
        self.plan = plan
        self.sites: set = set()
        self.calls_made: list = []
        self.asked: list = []          # (fn, receiver int | None, [arg values]) of every answer env was asked for
        self.width_values: list = []   # (span, value int | None, width bits)

    def visit(self, s) -> None:
        if isinstance(s, Check):
            k = context(s)
            if k != 1 and not self.truth(k):
                return
            self.sites.update(span_lines(s.span))
            if s.kind == "call":
                t = _callok(s.expr)
                if t is not None:
                    to = self.iv(t[2]) if t[2] is not None else None
                    args = [arg_value(self.value(self.ev(x))) for x in t[3:]]
                    self.calls_made.append({"fn": t[1], "to": hex_addr(to) if to is not None else None, "args": args})
        elif isinstance(s, Write):
            if self.truth(s.cond):
                self.sites.update(span_lines(s.src))
        elif isinstance(s, MStore):
            w = self.plan.width_spans.get(s.src)
            if w is None:
                return
            # Eval.run never evaluates a memory store: observing one must change neither the step nor the slots it
            # reads (the observation's reads go to scratch sets)
            saved = (self.state.reads, self.state.missing)
            self.state.reads, self.state.missing = set(), set()
            try:
                try:
                    if not self.truth(s.cond):
                        return
                except (X.Unsupported, X.CallReverted, ArithmeticError):
                    return
                self.sites.update(span_lines(s.src))
                v = s.value
                if isinstance(v, list) and len(v) == 3 and v[0] == "<<":
                    v = v[1]
                try:
                    val = self.iv(v)
                except (X.Unsupported, X.CallReverted, ArithmeticError):
                    val = None
                self.width_values.append((s.src, val, w))
            finally:
                self.state.reads, self.state.missing = saved

    def run(self, steps) -> None:
        for s in steps:
            if isinstance(s, (Check, Write, MStore)):
                self.visit(s)
            X.Eval.run(self, [s])

    def answer(self, fn, receiver, args):
        try:
            mine = [self.value(a) for a in args]
        except X.Unsupported:
            mine = None
        if mine is not None:
            self.asked.append((fn, receiver, mine))
        return super().answer(fn, receiver, args)


def traced_step(model, state: SlotState, action: str, args: dict, env: dict, plan: Plan) -> tuple[dict, Traced | None]:
    """holon.extracted_eval.step with a Traced evaluator: (the step's result, the evaluator)."""
    if action not in model.actions:
        return X._result("unsupported", reason=f"no action {action} in the document"), None
    prog = model.program(action)
    e = Traced(model, state, action, args or {}, env or {}, plan)
    try:
        e.run(prog.steps)
    except X.Reverted as x:
        out = X._result("revert", X.hexb(x.data), guard=x.check.id)
        if x.prefix:
            out["revert_prefix"] = True
        return out, e
    except X.CallReverted as x:
        return X._result("revert", X.hexb(x.data), guard=None, reason=f"external call {x.fn} reverted (bubbled)"), e
    except X.Unsupported as x:
        return X._result("unsupported", reason=f"{action}: {x}"), e
    except (ArithmeticError, RecursionError) as x:
        return X._result("unsupported", reason=f"{action}: {type(x).__name__}: {x}"), e
    wd = {X.h32(k): X.h32(e.overlay[k]) for k in sorted(e.touched)}
    return X._result("ok", None, wd, e.events, None), e


def calldata(model, fn: str, args: list) -> str | None:
    """The calldata of an external call fn(args) by the compiler's signature of fn (None when it has no unique one)."""
    sig = model.call_signature(fn)
    if not sig or not sig.get("selector") or sig.get("inputs") is None or len(sig["inputs"]) != len(args):
        return None
    try:
        vals = [X.norm(a, p) if not isinstance(a, int) else a & X.MASK for a, p in zip(args, sig["inputs"])]
        return sig["selector"] + X.abi_encode(vals, sig["inputs"]).hex()
    except (X.Unsupported, ValueError, TypeError):
        return None


def asked_calls(model, plan: Plan, e: Traced) -> list[dict]:
    """{fn, to, data} of every call the step asked env to answer (the receiver of a call term without one: the unique
    receiver term of the action's call records of that function, evaluated by the step); calls whose callee or
    calldata cannot be determined are left out."""
    out, seen = [], set()
    for fn, receiver, args in e.asked:
        to = receiver
        if to is None:
            terms = plan.receivers.get((e.action, fn)) or []
            if len(terms) != 1 or terms[0] is None:
                continue
            saved = (e.state.reads, e.state.missing)     # an observation: its reads are not the step's
            e.state.reads, e.state.missing = set(), set()
            try:
                to = e.iv(terms[0])
            except (X.Unsupported, X.CallReverted, ArithmeticError):
                continue
            finally:
                e.state.reads, e.state.missing = saved
        data = calldata(model, fn, args)
        if data is None:
            continue
        k = (fn, to, data)
        if k not in seen:
            seen.add(k)
            out.append({"fn": fn, "to": hex_addr(to), "data": data})
    return out


def header_env(h: dict) -> dict:
    """block.* of a stored block header (holon.historical.supplement HEADER_FIELDS)."""
    out = {}
    for key, field in (("block.number", "number"), ("block.timestamp", "timestamp"), ("block.basefee", "baseFeePerGas"),
                       ("block.gaslimit", "gasLimit"), ("block.coinbase", "miner"), ("block.prevrandao", "mixHash")):
        v = h.get(field)
        if v is not None:
            out[key] = v
    return out


def tx_env(tx: dict, proxy: str, header: dict | None, calls: list[dict]) -> dict:
    data = tx.get("input") or "0x"
    env = {"caller": tx["from"].lower(), "tx.origin": tx["from"].lower(), "this": proxy.lower(),
           "msg.value": tx.get("value") or "0x0", "msg.data.length": (len(data) - 2) // 2,
           "blobhash": [x.lower() for x in tx.get("blobVersionedHashes") or []], "calls": calls}
    if header is not None:
        env.update(header_env(header))
    return env


def decode_args(model, action: str, data: str) -> dict:
    """The action's arguments decoded strictly with the compiler's ABI of the action (holon.evm_abi)."""
    from .. import evm_abi
    params = model.params(action)
    if params is None:
        raise StepperError(f"{action}: the model has no ABI for it")
    return evm_abi.decode_args(params, bytes.fromhex(data[10:]))


def action_of(model, data: str) -> str | None:
    """The document action whose selector the calldata starts with (the compiler's ABI)."""
    sel = data[:10].lower()
    for name, a in model.actions.items():
        if (a.get("selector") or "").lower() == sel:
            return name
    return None
