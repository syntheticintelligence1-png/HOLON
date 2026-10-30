"""The calibrated cost of Bundle II's state-indexed cost site (BUILD_PLAN row I84 = I37b; whitepaper App. D: cost is
c0 + sum over loops of c_l * iters_l(s), compared against G; the contract is the docstring of
tests_m3/test_bundle2_laws.py, rules K1-K5 and D3).

  python tools/calibrate_gas.py [--check] [--jobs N] [--work DIR]

K1  The state-indexed cost sites are the declaration's cost-site rows (E5) whose count term reads storage only (no
    parameter, input, environment or abstract count); the harness measures exactly one, so the declaration must give
    exactly one.
K2  replay/M3/bundle2/calibrate/'s harness runs the laws sidecar's calibration strategy for every backlog k of the fit
    and evaluation sets, from a fresh deployment each, and logs the state the count term reads, the call's calldata, its
    frame's gas before refunds (forge's lastCallGas().gasTotalUsed, setUp and the test being separate transactions) and
    its refund. The calldata's selector must be the site action's (from the member's document).
K3  cost(k) = intrinsic(calldata) + frame gas (21000 + 4 per zero byte + 16 per nonzero byte, Cancun); iters(k) = the
    count term evaluated on the logged state.
K4  (c0, c1) = ordinary least squares of cost on iters over the fit backlogs only (exact rationals); error(k) =
    |c0 + c1 * iters(k) - cost(k)| / cost(k) over the evaluation backlogs; calibrated iff every error is at most the
    tolerance, else "uncalibrated".
K5  results/M3/bundle2/calibration.json (the laws sidecar's outputs.calibration); --check re-runs the harness and
    compares byte for byte.
D3  k_star(c0, c1, G): the least backlog k with c0 + c1 * k > G.

Everything specific to a target comes from the sidecars, the declaration and the documents.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

from . import ROOT, SIDECAR, BundleError, Ctx, Refused, Writer, render

LAWS_SIDECAR = "spec/M3/lib/bundle2_laws.json"
CAL_VERSION = "holon-bundle2-calibration/0.1"
CONTRACT, TEST = "HolonBundle2CalibrateTest", "test_challenge"
STATE, CAL = "HOLON-CAL-STATE", "HOLON-CAL"
CMP = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
       "==": lambda a, b: a == b, "!=": lambda a, b: a != b}


# ------------------------------------------------------------------------------------------------ terms
def is_op(t, op=None) -> bool:
    return isinstance(t, list) and bool(t) and isinstance(t[0], str) and (op is None or t[0] == op)


def subterms(t):
    yield t
    if isinstance(t, list):
        for x in t:
            yield from subterms(x)


def storage_only(t) -> bool:
    """K1: the term reads storage and nothing else that varies (no parameter, input, environment or abstract count)."""
    reads = False
    for x in subterms(t):
        if is_op(x, "storage"):
            reads = True
        elif is_op(x) and x[0] in ("param", "env", "count", "iter", "word", "byte", "member", "map", "call",
                                   "blobhash", "immutable", "carried", "exit"):
            return False
    return reads


def evaluate(t, storage: dict) -> int:
    """A storage-only count term over a state given as {family: value}."""
    if isinstance(t, bool):
        return int(t)
    if isinstance(t, int):
        return t
    if is_op(t, "storage"):
        if t[1] not in storage:
            raise Refused(f"the harness logged no value of {t[1]}")
        return int(storage[t[1]])
    if is_op(t):
        op, a = t[0], t[1:]
        if op == "?":
            return evaluate(a[1], storage) if evaluate(a[0], storage) else evaluate(a[2], storage)
        if op in CMP:
            return int(CMP[op](evaluate(a[0], storage), evaluate(a[1], storage)))
        if op == "+":
            return sum(evaluate(x, storage) for x in a)
        if op == "-":
            return evaluate(a[0], storage) - evaluate(a[1], storage)
        if op == "!":
            return int(not evaluate(a[0], storage))
        if op == "&&":
            return int(all(evaluate(x, storage) for x in a))
        if op == "||":
            return int(any(evaluate(x, storage) for x in a))
    raise Refused(f"a count term the calibration does not evaluate: {json.dumps(t)[:160]}")


def state_sites(decl: dict) -> list:
    return [r for r in decl.get("cost_sites") or [] if storage_only(r[5])]


def intrinsic(calldata: bytes) -> int:
    return 21000 + sum(4 if b == 0 else 16 for b in calldata)


# ------------------------------------------------------------------------------------------------ the fit
def fit(points: dict, ks: list) -> tuple:
    xs = [Fraction(points[k]["iters"]) for k in ks]
    ys = [Fraction(points[k]["cost"]) for k in ks]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        raise BundleError("the fit backlogs give one iteration count only")
    c1 = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - c1 * mx, c1


def errors(c0, c1, points: dict, ks: list) -> dict:
    return {k: abs(c0 + c1 * Fraction(points[k]["iters"]) - Fraction(points[k]["cost"])) / Fraction(points[k]["cost"])
            for k in ks}


def k_star(c0, c1, ceiling: int):
    """D3: the least backlog k >= 0 with c0 + c1 * k > ceiling (None when the cost never exceeds it)."""
    c0, c1 = Fraction(c0), Fraction(c1)
    if c0 > ceiling:
        return 0
    if c1 <= 0:
        return None
    return max(math.floor((Fraction(ceiling) - c0) / c1) + 1, 0)


def r6(x) -> float:
    return round(float(x), 6)


# ------------------------------------------------------------------------------------------------ inputs
class Laws:
    """The laws sidecar, I80's context and declaration, the site, its action's selector, G."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.side = json.loads((self.root / LAWS_SIDECAR).read_text(encoding="utf-8"))
        self.bctx = Ctx(self.root, self.side["inputs"].get("bundle_sidecar") or SIDECAR)
        self.decl = json.loads((self.root / self.side["inputs"]["declaration"]).read_text(encoding="utf-8"))
        g = self.side["gas"]["ceiling"]
        self.ceiling = int(json.loads((self.root / g["from"]).read_text(encoding="utf-8"))[g["key"]])
        self.cal = self.side["calibration"]

    def site(self) -> list:
        sites = state_sites(self.decl)
        if len(sites) != 1:
            raise Refused(f"the declaration gives {len(sites)} state-indexed cost sites; the harness measures one")
        return sites[0]

    def document(self, member: str) -> dict:
        m = next((x for x in self.decl.get("members") or [] if x["name"] == member), None)
        if m is None:
            raise Refused(f"the declaration has no member {member}")
        return json.loads((self.root / m["document"]["path"]).read_text(encoding="utf-8"))

    def selector(self, member: str, action: str) -> str:
        a = next((x for x in self.document(member)["actions"] if x["name"] == action), None)
        if a is None or not a.get("selector"):
            raise Refused(f"{member} has no action {action} with a selector")
        return a["selector"].lower()

    def out(self, key: str) -> Path:
        return self.root / self.side["outputs"][key]


# ------------------------------------------------------------------------------------------------ measuring
def parse(lines: list) -> tuple:
    """(state {family: value}, measurement) of one run's kept lines."""
    state, cal = None, None
    for ln in lines:
        parts = ln.split()
        if parts[0] == STATE:
            state = {"k": int(parts[1])}
            for kv in parts[2:]:
                name, v = kv.split("=", 1)
                state[name] = int(v)
        elif parts[0] == CAL:
            cal = {"k": int(parts[1]), "ok": parts[2] == "1", "frame_gas": int(parts[3]), "refund": int(parts[4]),
                   "tx_gas": int(parts[5]), "frame_limit": int(parts[6]), "calldata": parts[7].lower()}
    if state is None or cal is None:
        raise BundleError(f"the calibration harness logged no state or measurement: {lines[-6:]}")
    return state, cal


def measure(forge, ks: list, jobs: int, tx_gas: int = 0) -> dict:
    """{k: (state, measurement)} of the harness at every backlog of ks (with a transaction gas limit when tx_gas)."""
    extra = (lambda k: {"HOLON_K": k, "HOLON_TX_GAS": tx_gas}) if tx_gas else (lambda k: {"HOLON_K": k})
    outs = forge.run_many(jobs, [(CONTRACT, TEST, extra(k)) for k in ks], (STATE, CAL))
    return {k: parse(o) for k, o in zip(ks, outs)}


def calibrate(L: Laws, forge, jobs: int) -> dict:
    site = L.site()
    member, action, span, _seq, _is_cost, count = site
    sel = L.selector(member, action)
    fit_ks, eval_ks = [int(k) for k in L.cal["fit_backlogs"]], [int(k) for k in L.cal["eval_backlogs"]]
    if set(fit_ks) & set(eval_ks):
        raise Refused("the fit and evaluation backlogs overlap")
    ks = sorted(set(fit_ks) | set(eval_ks))
    raw = measure(forge, ks, jobs)
    points = {}
    for k in ks:
        state, m = raw[k]
        if m["k"] != k or state["k"] != k:
            raise BundleError(f"backlog {k}: the harness ran another backlog")
        if not m["ok"]:
            raise BundleError(f"backlog {k}: the measured call reverted with no gas limit")
        cd = bytes.fromhex(m["calldata"][2:])
        if "0x" + cd[:4].hex() != sel:
            raise BundleError(f"backlog {k}: the harness called selector 0x{cd[:4].hex()}, not {action}'s {sel}")
        it = evaluate(count, {n: v for n, v in state.items() if n != "k"})
        points[k] = {"iters": it, "calldata": m["calldata"], "frame_gas": m["frame_gas"], "refund": m["refund"],
                     "cost": intrinsic(cd) + m["frame_gas"]}
    c0, c1 = fit(points, fit_ks)
    errs = errors(c0, c1, points, eval_ks)
    worst = max(errs.values())
    status = "calibrated" if worst <= Fraction(str(L.cal["tolerance"])) else "uncalibrated"
    return {"calibration_version": CAL_VERSION, "site": [member, action, span], "count": count,
            "gas_ceiling": L.ceiling, "points": {str(k): points[k] for k in ks}, "fit_backlogs": fit_ks,
            "eval_backlogs": eval_ks, "c0": r6(c0), "c1": r6(c1), "errors": {str(k): r6(e) for k, e in errs.items()},
            "max_error": r6(worst), "status": status, "toolchain": forge.toolchain(),
            "harness": {"contract": CONTRACT, "test": TEST, "deployment_versions": forge.versions,
                        "init": forge.init}}


def exact(cal: dict) -> tuple:
    """(c0, c1) as exact rationals, refitted from a record's raw points."""
    pts = {int(k): v for k, v in cal["points"].items()}
    return fit(pts, [int(k) for k in cal["fit_backlogs"]])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tools/calibrate_gas.py", description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--root")
    ap.add_argument("--work", help="scratch directory for the forge project (default: a temporary directory)")
    ap.add_argument("--jobs", type=int, default=2)
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        L = Laws(root)
        from .laws_forge import Forge
        forge = Forge(L.bctx, L.side, Path(a.work) if a.work else None)
        cal = calibrate(L, forge, a.jobs)
        w = Writer(a.check)
        w.put(L.out("calibration"), render(cal))
        print(f"calibrate_gas: {len(cal['points'])} backlogs; c0 {cal['c0']}, c1 {cal['c1']}; max error "
              f"{cal['max_error']} ({cal['status']})")
        return w.finish("calibrate")
    except Refused as e:
        print(f"calibrate_gas: refused: {e}", file=sys.stderr)
        return 2
    except BundleError as e:
        print(f"calibrate_gas: error: {e}", file=sys.stderr)
        return 3
