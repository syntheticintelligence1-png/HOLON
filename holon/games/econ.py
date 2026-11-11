"""The DISCH-econ readings (key I56: definitions.econ_laws).

  n3(rec, runner)        O25/N3 over a FACT attribution witness {prefix, y, t, bonded, chooser}: the bonded address's
                         payoff over the full schedule (premise P-bond: the bond family's debited atoms are positive)
                         and over the prefix alone (it refuses), and each caller of t but the bonded one as the deviator
                         over the full schedule
  backlog_writers(t)     O35: the actions of the self-controlled law's member that write a register with a positive
                         coefficient in the count term of the law's loop, callable by an untrusted class
"""
from __future__ import annotations

from .common import Target, canon
from .run import Ledger, Runner, classify
from .target import schedule


def status(holds: bool, undetermined: bool) -> str:
    return "PROVED" if holds else ("UNKNOWN" if undetermined else "REFUTED")


def n3(rec: dict, runner: Runner, bond: str) -> dict:
    w = rec.get("witness") or {}
    steps, form = schedule(rec)
    if steps is None or form != "G-W2":
        return {"status": "UNKNOWN", "reason": "not an attribution witness (G-W2)"}
    if not w.get("t"):
        return {"status": "UNKNOWN", "reason": "the witness has no continuation t: no adversary schedule to read"}
    b = str(w["bonded"]).lower()
    full = Ledger({b}, bond)
    st_full = runner.run(steps, [full])
    ref = Ledger({b}, bond)
    st_ref = runner.run(list(w["prefix"]), [ref])
    if any(x != "ok" for x in st_full + st_ref) or len(st_full) != len(steps):
        return {"status": "UNKNOWN", "reason": f"the schedule does not run on the model: {st_full}"}
    adv = sorted({str(s["env"]["caller"]).lower() for s in w["t"]} - {b})
    advl = {}
    for x in adv:
        lg = Ledger({x})
        runner.run(steps, [lg])
        advl[x] = lg
    return {"status": "computed", "bonded": b, "full": full, "refuse": ref, "adversaries": advl,
            "recommit": classify(full.total()), "refuse_pay": classify(ref.total()),
            "adversary_pay": {x: classify(lg.total()) for x, lg in advl.items()}}


def _positive_storage(t, sign: int, out: set) -> None:
    if not isinstance(t, list) or not t:
        return
    if t[0] == "storage" and len(t) == 2:
        if sign > 0:
            out.add(t[1])
        return
    if t[0] == "-" and len(t) == 3:
        _positive_storage(t[1], sign, out)
        _positive_storage(t[2], -sign, out)
    elif t[0] == "+":
        for x in t[1:]:
            _positive_storage(x, sign, out)
    elif t[0] == "?" and len(t) == 4:
        _positive_storage(t[2], sign, out)


def backlog_writers(t: Target) -> list[str]:
    o = t.sc["o35"]
    a = t.action(o["member"], o["action"])
    loop = next(lp for lp in a["loops"] if str(lp.get("src", "")).endswith(o["loop"]) or o["loop"] in canon(lp)[:400])
    pos: set = set()
    _positive_storage(loop["count"], 1, pos)
    out = []
    for x in t.docs[o["member"]]["actions"]:
        g = t.klass(o["member"], x)
        if g is None or t.trusted.get(g, True):
            continue
        if any(w["family"] in pos for w in x["writes"]):
            out.append(x["name"])
    return sorted(out)
