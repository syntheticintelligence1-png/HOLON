"""A schedule run on the run member's extracted model, and its flows to a set of deviators (key I56: G-R1..G-R3,
G-P1..G-P3). The flows are evaluated from the value-flow document's entries, never from the documents directly.

The model is the run member's extracted model (holon.extracted_eval over the sidecar's run document, from its pinned
initial state): the evaluator M2 and M3 refine against the real code. A term the run cannot evaluate is an atom (an
unknown amount >= 0); an unresolved party is possibly a deviator.
"""
from __future__ import annotations

from .. import extracted_eval as X
from ..machine import load_extracted
from .common import Target


class Comp:
    """One component: a concrete integer and atom counts (credited/debited; ...p: positive by a premise)."""

    __slots__ = ("c", "up", "un", "upp", "unp")

    def __init__(self, c=0, up=0, un=0, upp=0, unp=0):
        self.c, self.up, self.un, self.upp, self.unp = c, up, un, upp, unp

    def add(self, o: "Comp") -> None:
        self.c += o.c
        self.up += o.up
        self.un += o.un
        self.upp += o.upp
        self.unp += o.unp

    def nat6(self) -> tuple:
        """(pos, neg, up, un, upp, unp): the Bend module's Cp."""
        return (max(self.c, 0), max(-self.c, 0), self.up, self.un, self.upp, self.unp)

    def ge(self) -> bool:
        return self.un == 0 and self.unp == 0 and self.c >= 0

    def le(self) -> bool:
        return self.up == 0 and self.upp == 0 and self.c <= 0

    def lt(self) -> bool:
        return self.le() and (self.c < 0 or self.unp > 0)

    def gt(self) -> bool:
        return self.ge() and (self.c > 0 or self.upp > 0)


def classify(comps: list[Comp]) -> str:
    """G-P2."""
    if all(x.ge() for x in comps):
        return "nonneg"
    if all(x.le() for x in comps) and any(x.lt() for x in comps):
        return "negative"
    if any(x.gt() for x in comps) and any(x.lt() for x in comps):
        return "incomparable"
    return "undetermined"


def as_int(v):
    if isinstance(v, bool):
        return int(v)
    return v if isinstance(v, int) else None


def addr(v: int) -> str:
    return "0x%040x" % (int(v) & ((1 << 160) - 1))


class Ledger:
    """Per-step holding changes of a deviator set D: [{asset: Comp}] in step order, and a log."""

    def __init__(self, deviators, bond: str | None = None):
        self.dev = {str(d).lower() for d in deviators}
        self.bond = bond
        self.steps: list[dict] = []
        self.log: list = []

    def open(self) -> None:
        self.steps.append({})

    def add(self, party, asset: str, amount, credit: bool, construct: str, family: str | None = None) -> None:
        if party is not None and party.lower() not in self.dev:
            return
        cur = self.steps[-1].setdefault(asset, Comp())
        if party is not None and amount is not None:
            if amount == 0:
                return
            cur.add(Comp(c=amount if credit else -amount))
        elif credit:
            cur.add(Comp(up=1))
        elif self.bond is not None and family == self.bond and party is not None:
            cur.add(Comp(unp=1))
        else:
            cur.add(Comp(un=1))
        self.log.append([len(self.steps) - 1, construct, party, asset, amount, "credit" if credit else "debit"])

    def assets(self) -> list[str]:
        return sorted({a for s in self.steps for a in s})

    def total(self) -> list[Comp]:
        out = {a: Comp() for a in self.assets()}
        for s in self.steps:
            for a, c in s.items():
                out[a].add(c)
        return [out[a] for a in sorted(out)]


class Runner:
    """Runs schedules of the run member from its initial state and evaluates the value-flow document's entries."""

    def __init__(self, t: Target, flows_doc: dict):
        self.t = t
        run = t.sc["run"]
        self.member = run["member"]
        self.model = load_extracted(run["document"]) if (t.root / run["document"]).is_file() else None
        self.init = __import__("json").loads((t.root / run["init"]).read_text(encoding="utf-8"))
        self.entries = {e["action"]: e for e in flows_doc["entries"]}
        self.acts = {a["name"]: a for a in t.docs[self.member]["actions"]}

    def env_of(self, step: dict) -> dict:
        """G-R1."""
        env = dict(step["env"])
        if "msg.data.length" not in env:
            cd = step.get("calldata")
            if isinstance(cd, str) and cd.startswith("0x"):
                env["msg.data.length"] = (len(cd) - 2) // 2
        if "this" not in env and self.init.get("target"):
            env["this"] = self.init["target"]
        return env

    def state0(self) -> dict:
        return {int(k, 16): int(v, 16) for k, v in self.init["storage"].items()}

    @staticmethod
    def _ev(e, t):
        try:
            return e.ev(t)
        except Exception:  # Unsupported, a local the action's scope lacks, arithmetic: the term becomes an atom
            return None

    def run(self, steps: list, ledgers: list[Ledger]) -> list[str]:
        """Statuses of the steps (stops at the first that is not ok); fills each ledger with the step's flows."""
        st = self.state0()
        statuses = []
        for s in steps:
            if s["action"] not in self.acts:
                statuses.append("not_in_document")
                return statuses
            env = self.env_of(s)
            out = X.step(self.model, dict(st), s["action"], s["args"], env)
            statuses.append(out["status"])
            if out["status"] != "ok":
                return statuses
            post = dict(st)
            for k, v in out["writes"].items():
                post[int(k, 16)] = int(v, 16)
            for lg in ledgers:
                lg.open()
            e = self.entries.get(f"{self.member}.{s['action']}")
            if e is not None:
                e0 = X.Eval(self.model, st, s["action"], s["args"], env)
                e1 = X.Eval(self.model, post, s["action"], s["args"], env)
                for lg in ledgers:
                    self._flows(e, e0, e1, env, lg)
            st = post
        return statuses

    def _flows(self, e: dict, e0, e1, env: dict, lg: Ledger) -> None:
        caller = str(env.get("caller", "")).lower() or None
        done = set()
        for f in e["flows"]:
            k = f["construct"]
            if k == "VM1":
                lg.add(caller, f["asset"], as_int(env.get("msg.value", 0)) or 0, False, k)
            elif k == "VM2":
                cond = 1 if f.get("cond") == 1 else self._ev(e0, f.get("cond"))
                if cond is not None and not cond:
                    continue
                rv, vv = as_int(self._ev(e0, f["party"])), as_int(self._ev(e0, f["amount"]))
                lg.add(addr(rv) if rv is not None else None, f["asset"], vv if cond is not None else None, True, k)
            elif k == "VM3":
                if f.get("key") is None:   # a write that is not one map entry: not a holder's claim (G-R3)
                    continue
                key = as_int(self._ev(e0, f["key"]))
                if key is None:
                    lg.add(None, f["asset"], None, True, k)
                    lg.add(None, f["asset"], None, False, k)
                    continue
                if (f["family"], key) in done:
                    continue
                done.add((f["family"], key))
                term = ["map", ["storage", f["family"]], f["key"]]
                old, new = as_int(self._ev(e0, term)), as_int(self._ev(e1, term))
                party = addr(key)
                if old is None or new is None:
                    lg.add(party, f["asset"], None, True, k)
                    lg.add(party, f["asset"], None, False, k)
                elif new != old:
                    lg.add(party, f["asset"], abs(new - old), new > old, k)
            elif k == "VM4":
                self._callee(f, env, lg)

    def _callee(self, f: dict, env: dict, lg: Ledger) -> None:
        cm, name = f["callee"].split(".", 1)
        for ans in env.get("calls") or []:
            if not ans.get("ok") or str(ans.get("fn", "")) != f["fn"]:
                continue
            args = decode(ans.get("data", "0x"), f["params"])
            for x in f["effects"]:
                if x["kind"] == "ledger":
                    if x.get("key") is None:
                        continue
                    k = self._term(x.get("key"), args, env)
                    party = addr(k) if k is not None else None
                    fam = f"{cm}.{x['family']}"
                    if x["shape"] == "zero":
                        lg.add(party, x["asset"], None, False, "VM4", fam)
                    elif x["shape"] in ("plus", "minus"):
                        amt = as_int(self._term(x["amount"], args, env))
                        lg.add(party, x["asset"], amt, x["shape"] == "plus", "VM4", fam)
                    else:
                        lg.add(party, x["asset"], None, True, "VM4", fam)
                        lg.add(party, x["asset"], None, False, "VM4", fam)
                else:
                    r = self._term(x.get("receiver"), args, env)
                    lg.add(addr(r) if r is not None else None, x["asset"],
                           as_int(self._term(x.get("amount"), args, env)), True, "VM4")

    @staticmethod
    def _term(t, args, env):
        if t == ["caller"]:
            return int(str(env["this"]), 16) if env.get("this") else None
        if isinstance(t, list) and len(t) == 2 and t[0] == "param" and args is not None:
            return args.get(t[1])
        if isinstance(t, int) and not isinstance(t, bool):
            return t
        return None


def decode(data: str, params: list[dict]):
    """A call's static ABI arguments by the callee's parameter types; None if one is not a static word."""
    try:
        raw = bytes.fromhex(str(data)[2:])[4:]
    except ValueError:
        return None
    out = {}
    for i, p in enumerate(params):
        ty = str(p.get("type") or "")
        if not (ty.startswith(("uint", "int")) or ty in ("address", "bool") or (ty.startswith("bytes") and ty[5:].isdigit())):
            return None
        w = raw[32 * i:32 * i + 32]
        if len(w) < 32:
            return None
        out[p["name"]] = int.from_bytes(w, "big")
    return out

