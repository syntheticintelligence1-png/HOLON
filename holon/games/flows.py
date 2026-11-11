"""The value-flow document (key I56: definitions.value_flows, VM1-VM4, G-A1, G-A2) and V9's coverage.

The document is generated from the deployment's extracted documents only. One entry per value-moving action, each
listing its constructs as flows whose party, amount and condition terms are the documents' own terms, so that the run
(holon.games.run) evaluates payoffs from this document and nothing else:

  VM1  {construct, party ["caller"], asset eth, amount ["env", "msg.value"], direction "debit"}
  VM2  {construct, party <receiver term>, asset eth, amount <value term>, direction "credit", cond <cond term>}
  VM3  {construct, family, key <key term>, asset, direction "delta"}   the entry's post-state minus pre-state value
  VM4  {construct, fn, callee "<member>.<action>", params [{name, type}], effects [...]}   the callee's ledger writes
       ({kind "ledger", family, key, shape zero|plus|minus|other, amount, asset}) and transfers
       ({kind "transfer", receiver, amount, asset eth}), over the callee's parameters

V9 (the lead's condition 1) is measured in holon.games.cli against every value-moving action, by entry completeness.
"""
from __future__ import annotations

from .common import ETH, Target


def ledgers(t: Target) -> dict:
    """{(member, family): asset} (G-A1, G-A2)."""
    out: dict = {}
    for m in sorted(t.docs):
        for a in t.docs[m]["actions"]:
            for c in a["calls"]:
                v = c.get("value")
                if isinstance(v, list) and len(v) == 3 and v[0] == "map" and isinstance(v[1], list) \
                        and v[1][:1] == ["storage"]:
                    key = (m, v[1][1])
                    redeem = a.get("principal") is None and v[2] == ["caller"]
                    if redeem or key not in out:
                        out[key] = ETH if redeem else f"ledger:{m}.{v[1][1]}"
    return out


def _nonzero(v) -> bool:
    return v not in (0, None, "0")


def direct(t: Target, led: dict) -> dict:
    """{"<member>.<action>": [VM1..VM3]} of every non-view action."""
    out = {}
    for m in sorted(t.docs):
        for a in t.docs[m]["actions"]:
            if a.get("mutability") in ("view", "pure"):
                continue
            cons = []
            if a.get("payable"):
                cons.append("VM1")
            if any(_nonzero(c.get("value")) for c in a["calls"]):
                cons.append("VM2")
            if any((m, w["family"]) in led for w in a["writes"]):
                cons.append("VM3")
            out[f"{m}.{a['name']}"] = cons
    return out


def callee(t: Target, member: str, fn: str):
    """VM4's match: the unique other member with an action named fn's last part whose extraction inputs include
    <I>.sol, I being fn before its last '.'."""
    if "." not in str(fn):
        return None
    iface, name = str(fn).rsplit(".", 1)
    hits = []
    for m in sorted(t.docs):
        if m == member:
            continue
        units = {str(u.get("unit", "")).rsplit("/", 1)[-1] for u in t.docs[m].get("extraction", {}).get("inputs", [])}
        if f"{iface}.sol" in units:
            hits += [(m, a) for a in t.docs[m]["actions"] if a["name"] == name]
    return hits[0] if len(hits) == 1 else None


def _callee_effects(cm: str, ca: dict, led: dict) -> list[dict]:
    out = []
    for w in ca["writes"]:
        f = w["family"]
        if (cm, f) not in led:
            continue
        path = w.get("path") or []
        key = path[0][1] if len(path) == 1 and path[0][0] == "map" else None
        cur = ["map", ["storage", f], key] if key is not None else None
        v = w.get("value")
        if v == 0:
            shape, amount = "zero", None
        elif isinstance(v, list) and len(v) == 3 and v[0] in ("+", "-") and cur is not None and v[1] == cur:
            shape, amount = ("plus" if v[0] == "+" else "minus"), v[2]
        else:
            shape, amount = "other", v
        out.append({"kind": "ledger", "family": f, "key": key, "shape": shape, "amount": amount,
                    "asset": led[(cm, f)], "src": w.get("src")})
    for c in ca["calls"]:
        if _nonzero(c.get("value")):
            out.append({"kind": "transfer", "receiver": c.get("receiver"), "amount": c.get("value"), "asset": ETH,
                        "src": c.get("src")})
    return out


def entry(t: Target, m: str, a: dict, led: dict, dmv: dict) -> dict | None:
    flows = []
    if a.get("payable"):
        flows.append({"construct": "VM1", "party": ["caller"], "asset": ETH, "amount": ["env", "msg.value"],
                      "direction": "debit", "src": a.get("src")})
    for c in a["calls"]:
        if _nonzero(c.get("value")):
            flows.append({"construct": "VM2", "party": c.get("receiver"), "asset": ETH, "amount": c.get("value"),
                          "direction": "credit", "cond": c.get("cond"), "src": c.get("src")})
    seen = set()
    for w in a["writes"]:
        f = w["family"]
        if (m, f) not in led:
            continue
        path = w.get("path") or []
        key = path[0][1] if len(path) == 1 and path[0][0] == "map" else None
        k = (f, None if key is None else str(key))
        if k in seen:
            continue
        seen.add(k)
        flows.append({"construct": "VM3", "family": f, "key": key, "asset": led[(m, f)], "direction": "delta",
                      "src": w.get("src")})
    for c in a["calls"]:
        if c.get("mutability") in ("view", "pure"):
            continue
        hit = callee(t, m, c.get("fn", ""))
        if hit is None or not dmv.get(f"{hit[0]}.{hit[1]['name']}"):
            continue
        cm, ca = hit
        flows.append({"construct": "VM4", "fn": c.get("fn"), "callee": f"{cm}.{ca['name']}",
                      "params": [{"name": p["name"], "type": p.get("type")} for p in (ca.get("params") or [])],
                      "effects": _callee_effects(cm, ca, led), "src": c.get("src")})
    if not flows:
        return None
    cons = sorted({f["construct"] for f in flows})
    want = set(dmv.get(f"{m}.{a['name']}", []))
    complete = want <= set(cons) and all(_flow_complete(f) for f in flows)
    return {"action": f"{m}.{a['name']}", "class": t.klass(m, a), "constructs": cons, "complete": complete,
            "flows": flows}


def _flow_complete(f: dict) -> bool:
    """Every flow names its asset and the terms the run reads (a term the run cannot evaluate becomes an atom)."""
    if f["construct"] in ("VM1", "VM2"):
        return f.get("party") is not None and f.get("amount") is not None and bool(f.get("asset"))
    if f["construct"] == "VM3":
        return bool(f.get("family")) and bool(f.get("asset"))
    return bool(f.get("callee")) and all(e.get("asset") for e in f.get("effects", []))


def document(t: Target) -> dict:
    led = ledgers(t)
    dmv = direct(t, led)
    entries = []
    for m in sorted(t.docs):
        for a in sorted(t.docs[m]["actions"], key=lambda x: x["name"]):
            if a.get("mutability") in ("view", "pure"):
                continue
            e = entry(t, m, a, led, dmv)
            if e:
                entries.append(e)
    return {"flows_version": "holon-value-flows/0.1",
            "documents": {d["member"]: d["sha256"] for d in t.sc["documents"]},
            "ledgers": [{"member": m, "family": f, "asset": led[(m, f)]} for (m, f) in sorted(led)],
            "entries": sorted(entries, key=lambda e: e["action"])}


def coverage(doc: dict, value_moving: dict) -> dict:
    """V9 against a set of value-moving actions {action: [constructs]}."""
    entries = {e["action"]: e for e in doc["entries"]}
    missing = []
    for k, cons in sorted(value_moving.items()):
        e = entries.get(k)
        got = {f["construct"] for f in e["flows"]} if e else set()
        if e is None or not e.get("complete") or not set(cons) <= got:
            missing.append(k)
    n = len(value_moving)
    return {"numerator": n - len(missing), "denominator": n, "missing": missing, "holds": not missing and n > 0}


def value_moving(doc: dict) -> dict:
    """The document's own value-moving set (its entries' constructs)."""
    return {e["action"]: e["constructs"] for e in doc["entries"]}


def detected(t: Target) -> dict:
    """The value-moving actions by the key's rules (VM1-VM3 directly, VM4 through callee), independently of entry():
    the set V9's coverage is measured against."""
    led = ledgers(t)
    dmv = direct(t, led)
    out = {}
    for m in sorted(t.docs):
        for a in t.docs[m]["actions"]:
            k = f"{m}.{a['name']}"
            if k not in dmv:
                continue
            cons = list(dmv[k])
            for c in a["calls"]:
                if c.get("mutability") in ("view", "pure"):
                    continue
                hit = callee(t, m, c.get("fn", ""))
                if hit and dmv.get(f"{hit[0]}.{hit[1]['name']}") and "VM4" not in cons:
                    cons.append("VM4")
            if cons:
                out[k] = sorted(cons)
    return dict(sorted(out.items()))
