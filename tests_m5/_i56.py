"""I56's instrument: the bounded-games definitions of key I56 written out a second time, independently of holon/games.

Fixed at I56's prereg and pinned by sha256 in tests_m5/test_m5_games.py (PINNED). It reads the deployment's extracted
documents and the target's game sidecar (spec/M5/lib/games_M3.json) and computes, without importing holon/games:

  classes(sc, docs)            the target's game classes (definitions G-C1..G-C3 of the key)
  claim_ledgers(docs)          the claim ledgers and their assets (G-A1, G-A2)
  value_moving(docs)           every value-moving action with the constructs that make it so (VM1..VM4), the set V9's
                               coverage is measured against
  schedule(record)             a REFUTED witness's call schedule by the witness-form table (G-W1..G-W5), or None with
                               the reason
  run_flows(...)               the flows of a schedule evaluated on the model's run (holon.extracted_eval, the M2/M3
                               evaluator, which is the model and not holon/games), per party and asset
  classify(comp)               the ordinal payoff of a holding vector (G-P1..G-P3)
  target_game(...)             the class verdicts of a finding's witness game (G-T1..G-T4)
  control_record_truth(doc)    a control's class verdicts and shortest nonneg strategy, by tests_m5/_i54.py's
                               enumeration of every schedule (I54's interpreter, reused unchanged)
  l6_v9(inputs, v9)            L6 by tests_m5/_i54.py's l6 with V9 applied first (the lead's condition 1)

Gaps (the key's E-G entries): the same session writes this file and holon/games (E-G1); payoffs are evaluated by the
extracted evaluator on the witness's run, not inside the Bend model (E-G2); a target's witness game is an
under-approximation of its strategy space, so only rational verdicts are sound on a target (E-G3).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests_m5 import _i54 as I

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = "spec/M5/lib/games_M3.json"
ETH = "eth"
UNTRUSTED_NAMES = ("anyone",)


def load(p) -> dict:
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def sidecar() -> dict:
    return load(SIDECAR)


def documents(sc: dict) -> dict:
    """{member: document} for every document the sidecar names."""
    return {d["member"]: load(d["path"]) for d in sc["documents"]}


def canon(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ classes (G-C1..G-C3)
def group_of(member: str, action: dict) -> str:
    """G-C1: an action's permission group: 'anyone' when its principal is null, else '<contract>.<modifier>'."""
    p = action.get("principal")
    return "anyone" if not p else f"{member}.{p['modifier']}"


def groups(docs: dict) -> dict:
    """{group id: {"predicate", "actions": [member.action]}} over every mutating and view action."""
    out: dict = {}
    for m in sorted(docs):
        for a in docs[m]["actions"]:
            g = group_of(m, a)
            e = out.setdefault(g, {"predicate": None if g == "anyone" else canon(a["principal"]["predicate"]),
                                   "actions": []})
            e["actions"].append(f"{m}.{a['name']}")
    for e in out.values():
        e["actions"].sort()
    return out


def classes(sc: dict, docs: dict) -> list[str]:
    """G-C2: the game classes are every group except the member-caller groups the sidecar lists."""
    return sorted(g for g in groups(docs) if g not in sc["member_caller"])


def class_of_action(member: str, action: dict, sc: dict) -> str | None:
    g = group_of(member, action)
    return None if g in sc["member_caller"] else g


# ------------------------------------------------------------------ claim ledgers (G-A1, G-A2)
def _is_map_of_caller(t, fam: str) -> bool:
    return t == ["map", ["storage", fam], ["caller"]]


def claim_ledgers(docs: dict) -> dict:
    """{(member, family): asset}. A family F is a claim ledger iff some call of an action of the same member transfers
    exactly ["map", ["storage", F], K] (G-A1). Its asset is eth when such an action has a null principal and K is the
    caller (its holder redeems it by its own call), else 'ledger:<member>.<F>' (G-A2)."""
    out = {}
    for m in sorted(docs):
        for a in docs[m]["actions"]:
            for c in a["calls"]:
                v = c.get("value")
                if isinstance(v, list) and len(v) == 3 and v[0] == "map" and isinstance(v[1], list) \
                        and v[1][:1] == ["storage"]:
                    fam = v[1][1]
                    redeem = a.get("principal") is None and v[2] == ["caller"]
                    key = (m, fam)
                    if redeem or key not in out:
                        out[key] = ETH if redeem else f"ledger:{m}.{fam}"
    return out


# ------------------------------------------------------------------ value-moving actions (VM1..VM4)
def selectors(docs: dict) -> dict:
    """{selector: [(member, action)]} over every action that has a selector."""
    out: dict = {}
    for m in sorted(docs):
        for a in docs[m]["actions"]:
            if a.get("selector"):
                out.setdefault(a["selector"].lower(), []).append((m, a["name"]))
    return out


def _direct(m: str, a: dict, led: dict) -> list[str]:
    cons = []
    if a.get("payable"):
        cons.append("VM1")
    if any(c.get("value") not in (0, None, "0") for c in a["calls"]):
        cons.append("VM2")
    if any((m, w["family"]) in led for w in a["writes"]):
        cons.append("VM3")
    return cons


def direct_moving(docs: dict) -> dict:
    """{"<member>.<action>": [VM1..VM3 constructs]} of every non-view action (empty list when none)."""
    led = claim_ledgers(docs)
    out = {}
    for m in sorted(docs):
        for a in docs[m]["actions"]:
            if a.get("mutability") in ("view", "pure"):
                continue
            out[f"{m}.{a['name']}"] = _direct(m, a, led)
    return out


def callee(docs: dict, member: str, fn: str):
    """VM4's match: (member, action) of the unique other member with an action named fn's last part whose extraction
    inputs include a unit <I>.sol, I being fn before its last '.'; None otherwise."""
    if "." not in str(fn):
        return None
    iface, name = str(fn).rsplit(".", 1)
    hits = []
    for m in sorted(docs):
        if m == member:
            continue
        units = {str(u.get("unit", "")).rsplit("/", 1)[-1] for u in docs[m].get("extraction", {}).get("inputs", [])}
        if f"{iface}.sol" not in units:
            continue
        hits += [(m, a) for a in docs[m]["actions"] if a["name"] == name]
    return hits[0] if len(hits) == 1 else None


def value_moving(docs: dict) -> dict:
    """{"<member>.<action>": [constructs]}: VM1 payable; VM2 a call whose value term is not the literal 0; VM3 a write
    to a claim ledger of its member; VM4 a non-view call that callee() matches to an action value-moving by VM1..VM3.
    View actions are never value-moving."""
    direct = direct_moving(docs)
    out = {}
    for m in sorted(docs):
        for a in docs[m]["actions"]:
            k = f"{m}.{a['name']}"
            if k not in direct:
                continue
            cons = list(direct[k])
            for c in a["calls"]:
                if c.get("mutability") in ("view", "pure"):
                    continue
                hit = callee(docs, m, c.get("fn", ""))
                if hit and direct.get(f"{hit[0]}.{hit[1]['name']}") and "VM4" not in cons:
                    cons.append("VM4")
            if cons:
                out[k] = sorted(cons)
    return dict(sorted(out.items()))


def v9_coverage(doc: dict, docs: dict) -> dict:
    """V9: every value-moving action has an entry in the value-flow document that lists each of its constructs.
    {"numerator", "denominator", "missing": [...], "holds"}."""
    vm = value_moving(docs)
    entries = {e["action"]: e for e in doc.get("entries", [])}
    missing = []
    for k, cons in vm.items():
        e = entries.get(k)
        got = sorted({f["construct"] for f in (e or {}).get("flows", [])}) if e else []
        if e is None or not e.get("complete") or not set(cons) <= set(got):
            missing.append(k)
    n = len(vm)
    return {"numerator": n - len(missing), "denominator": n, "missing": sorted(missing), "holds": not missing and n > 0}


# ------------------------------------------------------------------ schedules (G-W1..G-W5)
def _step(x) -> bool:
    return isinstance(x, dict) and isinstance(x.get("action"), str) and isinstance(x.get("env"), dict) \
        and isinstance(x.get("args"), dict)


def schedule(rec: dict):
    """(steps, form) or (None, reason) by the witness-form table:
      G-W1 {"steps": [...]}                         the steps
      G-W2 {"prefix", "y", "t", "bonded", "chooser"} prefix + [y] + t     (FACT attribution)
      G-W3 {"prefix", "x", "y", "t"} without bonded  prefix + [x, y] + t  (UNDO)
      G-W4 {"prefix", "x"} without "y"               prefix + [x]         (PAR link_domain, SYM tau)
      G-W5 anything else, or any element that is not an explicit step (a corpus reference, a migration move): none."""
    w = rec.get("witness")
    if not isinstance(w, dict):
        return None, "the witness is not a call schedule"
    if "steps" in w and isinstance(w["steps"], list):
        seq, form = list(w["steps"]), "G-W1"
    elif {"prefix", "y", "t", "bonded", "chooser"} <= set(w):
        seq, form = _list(w["prefix"]) + [w["y"]] + _list(w["t"]), "G-W2"
    elif {"prefix", "x", "y", "t"} <= set(w) and "bonded" not in w:
        seq, form = _list(w["prefix"]) + [w["x"], w["y"]] + _list(w["t"]), "G-W3"
    elif {"prefix", "x"} <= set(w) and "y" not in w:
        seq, form = _list(w["prefix"]) + [w["x"]], "G-W4"
    else:
        return None, "the witness is not a call schedule (G-W5)"
    if seq is None or any(s is None for s in seq) or not seq:
        return None, "the witness's schedule refers to steps it does not hold (G-W5)"
    if not all(_step(s) for s in seq):
        return None, "a step of the witness is not an explicit call (a reference into a corpus trace, or a migration move) (G-W5)"
    return seq, form


def _list(x):
    return list(x) if isinstance(x, list) else None


# ------------------------------------------------------------------ the model's run (G-R1..G-R3)
def env_of(step: dict, target: str | None) -> dict:
    """G-R1: the step's env, with msg.data.length from its calldata and this from the initial state's target when the
    witness does not give them."""
    env = dict(step["env"])
    if "msg.data.length" not in env:
        cd = step.get("calldata")
        if isinstance(cd, str) and cd.startswith("0x"):
            env["msg.data.length"] = (len(cd) - 2) // 2
    if "this" not in env and target:
        env["this"] = target
    return env


def init_state(init: dict) -> dict:
    return {int(k, 16): int(v, 16) for k, v in init["storage"].items()}


def _addr(v) -> str:
    return "0x%040x" % (int(v) & ((1 << 160) - 1))


class Comp:
    """A holding change of one party in one asset: a concrete integer part, and counts of atoms (unknown amounts, each
    >= 0): up/un credited/debited, upp/unp credited/debited and positive by a premise. Atoms never cancel (G-P1)."""

    def __init__(self):
        self.c, self.up, self.un, self.upp, self.unp = 0, 0, 0, 0, 0

    def add(self, other: "Comp") -> None:
        self.c += other.c
        self.up += other.up
        self.un += other.un
        self.upp += other.upp
        self.unp += other.unp

    def tup(self):
        return (max(self.c, 0), max(-self.c, 0), self.up, self.un, self.upp, self.unp)


def comp_of(c=0, up=0, un=0, upp=0, unp=0) -> Comp:
    x = Comp()
    x.c, x.up, x.un, x.upp, x.unp = c, up, un, upp, unp
    return x


def classify(comps: list[Comp]) -> str:
    """G-P2: nonneg iff every component is certainly >= 0; negative iff every component is certainly <= 0 and one is
    certainly < 0; incomparable iff one is certainly > 0 and another certainly < 0; otherwise undetermined."""
    def ge(x):
        return x.un == 0 and x.unp == 0 and x.c >= 0

    def le(x):
        return x.up == 0 and x.upp == 0 and x.c <= 0

    def lt(x):
        return le(x) and (x.c < 0 or x.unp > 0)

    def gt(x):
        return ge(x) and (x.c > 0 or x.upp > 0)
    if all(ge(x) for x in comps):
        return "nonneg"
    if all(le(x) for x in comps) and any(lt(x) for x in comps):
        return "negative"
    if any(gt(x) for x in comps) and any(lt(x) for x in comps):
        return "incomparable"
    return "undetermined"


def _model(sc: dict):
    """The run member's extracted model and its initial state (G-R2)."""
    from holon import extracted_eval as X  # the model's evaluator (M2/M3), not holon/games
    from holon.machine import load_extracted
    run = sc["run"]
    return X, load_extracted(run["document"]), load(run["init"])


def _ev(X, e, t):
    try:
        return e.ev(t)
    except Exception:  # an Unsupported term, a local the step's scope does not hold, an arithmetic failure
        return None


def _as_int(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    return None


def _decode(data: str, params: list[dict]):
    """The ABI arguments of a call's data by the callee's parameter types (static words only); None if any is not."""
    raw = bytes.fromhex(data[2:])[4:]
    out = {}
    for i, p in enumerate(params):
        ty = str(p.get("type", ""))
        if not (ty.startswith("uint") or ty.startswith("int") or ty == "address" or ty == "bool"
                or ty.startswith("bytes") and ty[5:].isdigit()):
            return None
        w = raw[32 * i:32 * i + 32]
        if len(w) < 32:
            return None
        out[p["name"]] = int.from_bytes(w, "big")
    return out


class Flows:
    """The flows of one run to a set of deviator addresses, per asset (G-R3)."""

    def __init__(self, deviators: set, bond: str | None):
        self.dev = {d.lower() for d in deviators}
        self.bond = bond
        self.by: dict = {}
        self.log: list = []

    def comp(self, asset: str) -> Comp:
        return self.by.setdefault(asset, Comp())

    def add(self, party, asset: str, amount, credit: bool, construct: str, atom_family: str | None = None):
        """party: an address string, or None (unresolved: possibly a deviator). amount: an int, or None (an atom)."""
        mine = party is None or party.lower() in self.dev
        if not mine:
            return
        sure = party is not None and amount is not None
        if sure:
            if amount == 0:
                return
            self.comp(asset).add(comp_of(c=amount if credit else -amount))
        else:
            pos = (not credit) and self.bond is not None and atom_family == self.bond and party is not None
            if credit:
                self.comp(asset).add(comp_of(up=1))
            else:
                self.comp(asset).add(comp_of(unp=1) if pos else comp_of(un=1))
        self.log.append([construct, party, asset, amount, "credit" if credit else "debit"])

    def comps(self) -> list[Comp]:
        return [self.by[a] for a in sorted(self.by)]


def run_flows(steps: list, sc: dict, docs: dict, deviators: set, bond: str | None = None):
    """(statuses, Flows): every step run on the run member's model from its initial state; the flows to the deviators:
    VM1 the caller pays msg.value; VM2 a call's receiver is credited its value (receiver, value and condition evaluated
    at the pre-state); VM3 a claim ledger entry written by the step moves by its post-state value minus its pre-state
    value (key evaluated at the pre-state); VM4 a call answered in the step's env of another member's value-moving
    action (by name) moves the callee's ledger entries and transfers by the callee's write shapes, its parameters
    decoded from the call's data, every amount over the callee's storage an atom."""
    X, m, init = _model(sc)
    member = sc["run"]["member"]
    doc = docs[member]
    acts = {a["name"]: a for a in doc["actions"]}
    led = claim_ledgers(docs)
    vm = value_moving(docs)
    direct = direct_moving(docs)
    st = init_state(init)
    fl = Flows(deviators, bond)
    statuses = []
    for s in steps:
        a = acts.get(s["action"])
        if a is None:
            statuses.append("not_in_document")
            return statuses, None
        env = env_of(s, init.get("target"))
        out = X.step(m, dict(st), s["action"], s["args"], env)
        statuses.append(out["status"])
        if out["status"] != "ok":
            return statuses, None
        post = dict(st)
        for k, v in out["writes"].items():
            post[int(k, 16)] = int(v, 16)
        e0 = X.Eval(m, st, s["action"], s["args"], env)
        e1 = X.Eval(m, post, s["action"], s["args"], env)
        caller = str(env.get("caller", "")).lower() or None
        if a.get("payable"):
            fl.add(caller, ETH, _as_int(env.get("msg.value", 0)) or 0, False, "VM1")
        for c in a["calls"]:
            if c.get("value") in (0, None, "0"):
                continue
            cond = 1 if c.get("cond") == 1 else _ev(X, e0, c.get("cond"))
            if cond is not None and not cond:
                continue
            rv, vv = _ev(X, e0, c.get("receiver")), _as_int(_ev(X, e0, c.get("value")))
            party = _addr(rv) if _as_int(rv) is not None else None
            fl.add(party, ETH, vv if cond is not None else None, True, "VM2")
        seen = set()
        for w in a["writes"]:
            f = w["family"]
            if (member, f) not in led or len(w.get("path") or []) != 1 or w["path"][0][0] != "map":
                continue
            kt = w["path"][0][1]
            key = _as_int(_ev(X, e0, kt))
            if key is None:
                fl.add(None, led[(member, f)], None, True, "VM3")
                fl.add(None, led[(member, f)], None, False, "VM3")
                continue
            if (f, key) in seen:
                continue
            seen.add((f, key))
            term = ["map", ["storage", f], kt]
            old, new = _as_int(_ev(X, e0, term)), _as_int(_ev(X, e1, term))
            party = _addr(key)
            if old is None or new is None:
                fl.add(party, led[(member, f)], None, True, "VM3")
                fl.add(party, led[(member, f)], None, False, "VM3")
            elif new != old:
                fl.add(party, led[(member, f)], abs(new - old), new > old, "VM3")
        for ans in env.get("calls") or []:
            if not ans.get("ok"):
                continue
            hit = callee(docs, member, ans.get("fn", ""))
            if hit is None or not direct.get(f"{hit[0]}.{hit[1]['name']}"):
                continue
            cm, ca = hit
            args = _decode(ans.get("data", "0x"), ca.get("params") or [])
            _callee(fl, cm, ca, args, env, led)
        st = post
    return statuses, fl


def _callee_term(t, args, env):
    if t == ["caller"]:
        return _as_int(int(str(env.get("this")), 16)) if env.get("this") else None
    if isinstance(t, list) and len(t) == 2 and t[0] == "param" and args is not None:
        return args.get(t[1])
    if isinstance(t, int):
        return t
    return None


def _callee(fl: Flows, cm: str, ca: dict, args, env, led) -> None:
    for w in ca["writes"]:
        f = w["family"]
        if (cm, f) not in led or len(w.get("path") or []) != 1 or w["path"][0][0] != "map":
            continue
        k = _callee_term(w["path"][0][1], args, env)
        party = _addr(k) if k is not None else None
        asset, fam = led[(cm, f)], f"{cm}.{f}"
        v, cur = w.get("value"), ["map", ["storage", f], w["path"][0][1]]
        if v == 0:
            fl.add(party, asset, None, False, "VM4", fam)
        elif isinstance(v, list) and len(v) == 3 and v[0] in ("+", "-") and v[1] == cur:
            amt = _as_int(_callee_term(v[2], args, env))
            fl.add(party, asset, amt, v[0] == "+", "VM4", fam)
        else:
            fl.add(party, asset, None, True, "VM4", fam)
            fl.add(party, asset, None, False, "VM4", fam)
    for c in ca["calls"]:
        if c.get("value") in (0, None, "0"):
            continue
        r = _callee_term(c.get("receiver"), args, env)
        party = _addr(r) if r is not None else None
        fl.add(party, ETH, _as_int(_callee_term(c.get("value"), args, env)), True, "VM4")


# ------------------------------------------------------------------ target games (G-T1..G-T4)
def target_game(rec: dict, sc: dict, docs: dict):
    """(game, None) or (None, reason): the class verdicts of a finding's witness game."""
    steps, form = schedule(rec)
    if steps is None:
        return None, form
    member = sc["run"]["member"]
    acts = {a["name"]: a for a in docs[member]["actions"]}
    if any(s["action"] not in acts for s in steps):
        return None, f"a step is not an action of the run member {member} (G-T1)"
    statuses, fl0 = run_flows(steps, sc, docs, set())
    if fl0 is None:
        return None, f"the schedule does not run on the model from its initial state: {statuses} (G-T1)"
    groups_ = [class_of_action(member, acts[s["action"]], sc) for s in steps]
    deviators = {str(s["env"].get("caller", "")).lower() for s in steps}
    _, fl = run_flows(steps, sc, docs, deviators)
    pay = classify(fl.comps())
    trusted = {c["id"]: c["trusted"] for c in sc["classes"]}
    cls = {}
    for x in classes(sc, docs):
        legal = all(g is not None and g in (x, "anyone") for g in groups_)
        if legal and pay == "nonneg":
            cls[x] = {"class": x, "trusted": trusted[x], "verdict": "rational", "payoff": "nonneg",
                      "strategy_length": len(steps)}
        else:
            cls[x] = {"class": x, "trusted": trusted[x], "verdict": "UNKNOWN",
                      "payoff": (pay if pay != "undetermined" else None) if legal else None, "strategy_length": None}
    verdict = I._finding_verdict(list(cls.values()))
    return {"form": form, "steps": len(steps), "classes": cls, "verdict": verdict, "payoff": pay,
            "legal": sorted(x for x in cls if all(g is not None and g in (x, "anyone") for g in groups_)),
            "flows": fl.log}, None


# ------------------------------------------------------------------ controls
def control_record_truth(doc: dict) -> dict:
    """{class: (verdict, shortest nonneg length or None, payoff label or None)} by enumerating every schedule of
    distinct actions (I54's semantics; the horizon of a control record is its number of actions)."""
    import itertools
    acts = doc["actions"]
    truth = I.game_truth(doc)["classes"]
    out = {}
    for a in doc["actors"]:
        x = a["id"]
        mine = [c for c in acts if x in c["by"]]
        best, pays = None, set()
        for r in range(1, len(mine) + 1):
            for seq in itertools.permutations(mine, r):
                vs = dict(doc["vars"])
                hold = {s: 0 for s in doc["assets"]}
                ok, trig = True, False
                for c in seq:
                    if not I._holds(c["guard"], vs):
                        ok = False
                        break
                    for op, var, k in c["effect"]:
                        vs[var] = vs[var] + k if op == "add" else k
                    for who, d in c["flows"].items():
                        if (x if who == "caller" else who) == x:
                            for s_, q in d.items():
                                hold[s_] += q
                    trig = trig or I._holds(doc["bad"], vs)
                if ok and trig:
                    p = I._sign([hold[s_] for s_ in doc["assets"]])
                    pays.add(p)
                    if p == "nonneg" and (best is None or r < best):
                        best = r
        v = truth[x]
        payoff = "nonneg" if v == "rational" else ("negative" if pays == {"negative"} else
                                                   ("incomparable" if "incomparable" in pays else None))
        out[x] = (v, best, payoff)
    return out


# ------------------------------------------------------------------ L6 with V9 (the lead's condition 1)
PENDING_CORPUS = "pending the corpus-truth key (the lead's condition 5): no corpus item is scored"


def l6_v9(inputs: dict, v9: dict) -> dict:
    """I54's l6 (tests_m5/_i54.py) after V9: when V9 does not hold, every target record is invalid with rule V9 (its
    finding UNKNOWN) and the decided threshold is not_judged; the overall verdict is recomputed from the thresholds."""
    inp = dict(inputs)
    demoted = []
    if not v9["holds"]:
        demoted = sorted({r["finding"] for r in inputs["records"] if r["kind"] == "target"})
        inp["records"] = [r for r in inputs["records"] if r["kind"] != "target"]
    out = I.l6(inp)
    for f in demoted:
        out["invalid"].setdefault(f, []).append("V9")
    out["invalid"] = {k: out["invalid"][k] for k in sorted(out["invalid"])}
    if not v9["holds"]:
        out["thresholds"]["decided"] = "not_judged"
    if inputs.get("corpus_truth") is None:
        out["corpus"] = {"label": "not_measured", "reason": PENDING_CORPUS}
    out["overall"] = I.overall(out["thresholds"])
    out["v9"] = {k: v9[k] for k in ("numerator", "denominator", "holds")}
    return out


# ------------------------------------------------------------------ econ laws (N3, O35)
def n3(rec: dict, sc: dict, docs: dict) -> dict:
    """The economic reading of O25/N3 over a FACT attribution witness (G-W2): the bonded address B's payoff over the full
    schedule with the bond family's debited atoms positive (premise P-bond), B's payoff over the prefix alone (B
    refuses), and each caller of the continuation t as the deviator over the full schedule."""
    w = rec["witness"]
    steps, form = schedule(rec)
    if steps is None or form != "G-W2":
        return {"status": "UNKNOWN", "reason": "not an attribution witness"}
    if not w.get("t"):
        return {"status": "UNKNOWN", "reason": "the witness has no continuation t: no adversary schedule to read"}
    b = str(w["bonded"]).lower()
    _, full = run_flows(steps, sc, docs, {b}, sc["n3"]["bond_family"])
    _, ref = run_flows(list(w["prefix"]), sc, docs, {b}, sc["n3"]["bond_family"])
    adv = sorted({str(s["env"]["caller"]).lower() for s in w["t"]} - {b})
    advp = {}
    for x in adv:
        _, fx = run_flows(steps, sc, docs, {x})
        advp[x] = classify(fx.comps())
    return {"status": "computed", "bonded": b, "recommit": classify(full.comps()), "refuse": classify(ref.comps()),
            "adversaries": advp}


def n3_status(holds: bool, undetermined: bool) -> str:
    """N3's status from the run's classifications: PROVED when the claim holds; UNKNOWN when it does not and a
    classification it reads is undetermined; REFUTED otherwise (the run certainly contradicts it)."""
    return "PROVED" if holds else ("UNKNOWN" if undetermined else "REFUTED")


def backlog_writers(sc: dict, docs: dict) -> list[str]:
    """The O35 backlog writers: the actions of the self-controlled law's member that write a storage register with a
    positive coefficient in the count term of the law's loop, callable by an untrusted class."""
    o = sc["o35"]
    doc = docs[o["member"]]
    a = next(x for x in doc["actions"] if x["name"] == o["action"])
    loop = next(lp for lp in a["loops"] if str(lp.get("src", "")).endswith(o["loop"]) or o["loop"] in canon(lp)[:400])
    pos: set = set()

    def walk(t, sign):
        if isinstance(t, list) and t:
            if t[0] == "storage" and len(t) == 2:
                if sign > 0:
                    pos.add(t[1])
                return
            if t[0] == "-" and len(t) == 3:
                walk(t[1], sign)
                walk(t[2], -sign)
                return
            if t[0] == "+":
                for x in t[1:]:
                    walk(x, sign)
                return
            if t[0] == "?" and len(t) == 4:
                walk(t[2], sign)
                return
    walk(loop["count"], 1)
    trusted = {c["id"]: c["trusted"] for c in sc["classes"]}
    out = []
    for x in doc["actions"]:
        g = class_of_action(o["member"], x, sc)
        if g is None or trusted.get(g, True):
            continue
        if any(w["family"] in pos for w in x["writes"]):
            out.append(x["name"])
    return sorted(out)


def o35_static(sc: dict, docs: dict) -> dict:
    """{writer: constructs}: a writer whose only construct is VM1 moves no value at msg.value 0."""
    vm = value_moving(docs)
    m = sc["o35"]["member"]
    return {b: vm.get(f"{m}.{b}", []) for b in backlog_writers(sc, docs)}
