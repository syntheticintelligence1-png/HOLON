"""Principal and amount sorts over a bundle's transitions documents (whitepaper §7.5: "a waiver must be keyed by the
principal that bears the cost"; "every inflow is accounted for"; BUILD_PLAN I36's holon/sorts/conservation.py). The
contract is the docstring of tests_m3/test_bundle_laws.py, rules PY1-PY3 and CS1-CS2.

  payer_sites(members)         PY1-PY3: for each payable action, each price check (a guard [">=", msg.value, R] or
                               ["<=", R, msg.value]) and each price call ["call", fn, args..] of R with a principal
                               argument (the caller, tx.origin, or an address-typed parameter, scalar storage family or
                               immutable): one site, its keys the principal arguments, keyed_on_payer when every key is
                               the caller term
  conservation_sites(members)  CS1-CS2: one site per payable action (receive included); its class unaccounted (msg.value
                               reaches the value of no write and no value call), ledger (it reaches a write of a mapping
                               family), outflow (it reaches a value call) or ledger+outflow; dependencies "I68" for a
                               mapping credit and "outflow" for a forwarded inflow

members is a list of {"name", "contract", "document" (relative path), "doc" (the document)}. Nothing here names a target:
every action, family, parameter and term comes from the documents.
"""
from __future__ import annotations

ADDRESS = "address"
MSG_VALUE = ["env", "msg.value"]


def _head(t):
    return t[0] if isinstance(t, list) and t and isinstance(t[0], str) else None


def _terms(t):
    yield t
    if isinstance(t, list):
        for x in (t[1:] if _head(t) is not None else t):
            yield from _terms(x)


def _reads(t, pred) -> bool:
    return any(pred(x) for x in _terms(t))


def _line(src: str) -> str:
    return str(src).rpartition(":")[2].split("-")[0]


def storage_families(doc: dict) -> dict:
    out: dict = {}
    for s in list(doc.get("storage") or []) + list(doc.get("inherited_storage") or []):
        if isinstance(s, dict) and s.get("name") and s["name"] not in out:
            out[s["name"]] = s
    return out


def principal(term, action: dict, doc: dict) -> bool:
    """PY1: is a call argument a principal (the caller, tx.origin, or an address-typed parameter, scalar storage
    family or immutable)?"""
    if term in (["caller"], ["env", "tx.origin"]):
        return True
    h = _head(term)
    if h == "param":
        return any(p.get("name") == term[1] and p.get("type") == ADDRESS for p in action.get("params") or [])
    if h == "storage":
        s = storage_families(doc).get(term[1]) or {}
        return s.get("kind") == "scalar" and s.get("value") == ADDRESS
    if h == "immutable":
        return any(isinstance(i, dict) and i.get("name") == term[1] and i.get("type") == ADDRESS
                   for i in doc.get("immutables") or [])
    return False


def price_bound(expr):
    """PY1: R of a price check [">=", msg.value, R] or ["<=", R, msg.value]; None otherwise."""
    if _head(expr) == ">=" and expr[1] == MSG_VALUE:
        return expr[2]
    if _head(expr) == "<=" and expr[2] == MSG_VALUE:
        return expr[1]
    return None


def payer_sites(members: list) -> list:
    out = []
    for m in members:
        doc = m["doc"]
        for a in doc.get("actions") or []:
            if not a.get("payable"):
                continue
            for g in a.get("guards") or []:
                r = price_bound(g.get("expr"))
                if r is None:
                    continue
                for t in _terms(r):
                    if _head(t) != "call":
                        continue
                    keys = [x for x in t[2:] if principal(x, a, doc)]
                    if not keys:
                        continue
                    out.append({"law_id": f"L_sort_payer_{m['contract']}_{a['name']}_{_line(g['src'])}",
                                "member": m["name"], "contract": m["contract"], "action": a["name"],
                                "check_src": g["src"], "price_call": t[1], "keys": keys, "payer": ["caller"],
                                "keyed_on_payer": all(k == ["caller"] for k in keys)})
    return sorted(out, key=lambda s: s["law_id"])


def conservation_sites(members: list) -> list:
    out = []
    for m in members:
        doc = m["doc"]
        fams = storage_families(doc)
        for a in doc.get("actions") or []:
            if not a.get("payable"):
                continue
            credited = sorted({w["family"] for w in a.get("writes") or []
                               if _reads(w.get("value"), lambda z: z == MSG_VALUE)})
            mapping = [f for f in credited if (fams.get(f) or {}).get("kind") == "mapping"]
            forwarded = sorted({c["src"] for c in a.get("calls") or [] if c.get("value") not in (0, None)
                                and _reads(c.get("value"), lambda z: z == MSG_VALUE)})
            deps = (["I68"] if mapping else []) + (["outflow"] if forwarded else [])
            if not (credited or forwarded):
                cls = "unaccounted"
            elif mapping and forwarded:
                cls = "ledger+outflow"
            elif mapping:
                cls = "ledger"
            elif forwarded:
                cls = "outflow"
            else:
                cls = "scalar"
            out.append({"law_id": f"L_sort_cons_{m['contract']}_{a['name']}", "member": m["name"],
                        "contract": m["contract"], "action": a["name"], "credited": credited,
                        "mapping_ledgers": mapping, "forwarded": forwarded, "class": cls, "dependencies": deps})
    return sorted(out, key=lambda s: s["law_id"])
