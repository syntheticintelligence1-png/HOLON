"""Static deadness of an undo residue (BUILD_PLAN I27; whitepaper §10.6: "a key-sensitive backward analysis, with index
variables kept symbolic"; the contract is the docstring of tests_m3/test_undo.py, rules D1-D3).

A residue basis (undo action, family F, cursors C, zero families Z) leaves F's register at a key k above every cursor
(C < k) in a slot whose existence markers ā cleared (G[k] == 0 for every G in Z). The residue is dead when no record of
any action of the document (views included) can read F at such a key; a record that can is a live reader.

Every read of F is located in a record; the records and the fields scanned, in scan order:

  guards[i].reaches[j]  expr, args
  checks[i]             expr
  panics[i]             expr, args
  calls[i]              expr, args, receiver, value, cond
  writes[i]             value, cond, path
  events[i]             args, cond, topics
  mstores[i]            value, cond, offset
  loops[i]              head, cond, bound, count
  returns               the action's returns term (after every record)

A read is ["map", ["storage", F], key] (or ["map", ["carried", span, ["storage", F]], key] inside a loop record): its
key is the third element; a bare ["storage", F] is a read without a key. In a holon-facts/0.3 document every such read
is of F's value before the transaction (assumption A-env; the extractor resolves a read after a write to the value).

FalseAt(x, rho), for a read at key rho, holds when x cannot be true at rho = k under the residue's context:
  cursor form  x is ["==", rho, S], ["==", S, rho], ["<=", rho, S], ["<", rho, S], [">=", S, rho] or [">", S, rho]
               with S = ["storage", C] for a cursor C (rho <= C < k);
  zero form    x is ["!=", Zr, 0], ["!=", 0, Zr], ["!", ["==", Zr, 0]] or ["!", ["==", 0, Zr]] with
               Zr = ["map", ["storage", G], rho] or ["member", ["map", ["storage", G], rho], m] for a zero family G
               (G[k] == 0).
rho is compared syntactically. The dominating conjuncts of a record: the top-level conjuncts of every guard reach of
its action with a smaller seq, of the record's own cond, and of the head and cond of its loop.

  D1  the read's key is ["storage", C] for a cursor C, or a dominating conjunct is FalseAt in a cursor form
  D2  else, a dominating conjunct is FalseAt in a zero form (dominated by a cleared marker)
  D3  else, an ancestor ["&&", ..] of the read has another operand one of whose top-level conjuncts is FalseAt (masked)

A read without a key (F a scalar) is never excluded. A record holding a read that no rule excludes is a live reader
{"action", "at"}; a record all of whose reads are excluded is listed under "excluded" {"action", "at", "rules"}. The
residue is dead iff it has no live reader. Soundness is not claimed (gap G6): the context is assumed to persist until
the residue is overwritten; the kernel decides, and a disagreement is reported.

Nothing here names a target: every family, action and term comes from the document.
"""
from __future__ import annotations

import json

INF = float("inf")
SCAN = (("checks", ("expr",)), ("panics", ("expr", "args")),
        ("calls", ("expr", "args", "receiver", "value", "cond")),
        ("writes", ("value", "cond", "path")), ("events", ("args", "cond", "topics")),
        ("mstores", ("value", "cond", "offset")), ("loops", ("head", "cond", "bound", "count")))
CURSOR_OPS = ("==", "<=", "<", ">=", ">")


# ------------------------------------------------------------------------------------------------ terms
def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def is_op(t, op: str | None = None) -> bool:
    return isinstance(t, list) and bool(t) and isinstance(t[0], str) and (op is None or t[0] == op)


def is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def conjuncts(e) -> list:
    """["&&", x, y, ..] splits recursively into the conjuncts of its operands; any other term is one conjunct."""
    if is_op(e, "&&"):
        out = []
        for x in e[1:]:
            out += conjuncts(x)
        return out
    return [e]


def storage(family: str) -> list:
    return ["storage", family]


def is_storage_of(t, family: str) -> bool:
    return is_op(t, "storage") and len(t) == 2 and t[1] == family


def reads_family(t, family: str) -> bool:
    """Does the term name ["storage", family] anywhere?"""
    if isinstance(t, list):
        if is_storage_of(t, family):
            return True
        return any(reads_family(x, family) for x in t)
    if isinstance(t, dict):
        return any(reads_family(v, family) for v in t.values())
    return False


def occurrences(t, family: str, anc: list | None = None, out: list | None = None) -> list:
    """Every read of `family` in t: (key or None, the read's ancestors ending with the read term itself)."""
    anc = [] if anc is None else anc
    out = [] if out is None else out
    if isinstance(t, dict):
        for v in t.values():
            occurrences(v, family, anc, out)
        return out
    if not isinstance(t, list):
        return out
    if is_op(t, "map") and len(t) == 3:
        b = t[1]
        if is_storage_of(b, family) or (is_op(b, "carried") and len(b) == 3 and is_storage_of(b[2], family)):
            out.append((t[2], anc + [t]))
            occurrences(t[2], family, anc + [t], out)
            return out
    if is_storage_of(t, family):
        out.append((None, anc + [t]))
        return out
    for x in (t[1:] if is_op(t) else t):
        occurrences(x, family, anc + [t], out)
    return out


# ------------------------------------------------------------------------------------------------ records
def reaches(action: dict) -> list:
    """(guard index, reach index, reach) of every guard reach of the action, in document order."""
    return [(gi, ri, r) for gi, g in enumerate(action.get("guards") or []) for ri, r in enumerate(g.get("reaches") or [])]


def loop_of(action: dict, rec: dict | None) -> dict | None:
    """The loop record a record sits in (its "loop" names the loop record's seq), or None."""
    if rec is None or rec.get("loop") is None:
        return None
    for lp in action.get("loops") or []:
        if lp.get("seq") == rec["loop"]:
            return lp
    raise ValueError(f"{action.get('name')}: no loop record with seq {rec['loop']}")


def records_of(action: dict) -> list:
    """(at, seq, scanned terms, record or None) of every record of the action, in scan order."""
    out = []
    for gi, ri, r in reaches(action):
        out.append((f"guards[{gi}].reaches[{ri}]", r.get("seq"), [r.get("expr"), r.get("args")], None))
    for sec, fields in SCAN:
        for i, rec in enumerate(action.get(sec) or []):
            out.append((f"{sec}[{i}]", rec.get("seq"), [rec.get(f) for f in fields], rec))
    if action.get("returns") is not None:
        out.append(("returns", INF, [action["returns"]], None))
    return out


def dominating(action: dict, seq, rec: dict | None) -> list:
    """The dominating conjuncts of a record at `seq`: every guard reach before it, its own cond, its loop's head and
    cond."""
    cs = []
    for _, _, r in reaches(action):
        if r.get("seq") is not None and seq is not None and r["seq"] < seq:
            cs += conjuncts(r.get("expr"))
    if rec is not None:
        if rec.get("cond") is not None:
            cs += conjuncts(rec["cond"])
        lp = loop_of(action, rec)
        if lp is not None:
            cs += conjuncts(lp.get("head")) + conjuncts(lp.get("cond"))
    return cs


# ------------------------------------------------------------------------------------------------ FalseAt
def false_at(x, rho, cursors: list, zero: list) -> bool:
    """FalseAt(x, rho) in a cursor form (cursors) or a zero form (zero)."""
    if rho is None or not is_op(x):
        return False
    r = canon(rho)
    if len(x) == 3 and x[0] in CURSOR_OPS:
        a, b = canon(x[1]), canon(x[2])
        for c in cursors:
            s = canon(storage(c))
            if x[0] == "==" and sorted([a, b]) == sorted([r, s]):
                return True
            if x[0] in ("<=", "<") and a == r and b == s:
                return True
            if x[0] in (">=", ">") and a == s and b == r:
                return True
    for g in zero:
        zr = canon(["map", storage(g), rho])

        def zread(y, zr=zr) -> bool:
            return canon(y) == zr or (is_op(y, "member") and len(y) == 3 and canon(y[1]) == zr)
        if is_op(x, "!=") and len(x) == 3 and ((zread(x[1]) and x[2] == 0) or (zread(x[2]) and x[1] == 0)):
            return True
        if is_op(x, "!") and len(x) == 2 and is_op(x[1], "==") and len(x[1]) == 3 and (
                (zread(x[1][1]) and x[1][2] == 0) or (zread(x[1][2]) and x[1][1] == 0)):
            return True
    return False


def rule_of(rho, anc: list, dom: list, cursors: list, zero: list) -> str | None:
    """The rule (D1, D2, D3) that excludes one read, or None."""
    if rho is None:
        return None
    if any(canon(rho) == canon(storage(c)) for c in cursors):
        return "D1"
    if any(false_at(x, rho, cursors, []) for x in dom):
        return "D1"
    if any(false_at(x, rho, [], zero) for x in dom):
        return "D2"
    for i, node in enumerate(anc):
        if is_op(node, "&&"):
            child = anc[i + 1] if i + 1 < len(anc) else None
            for op in node[1:]:
                if op is child:
                    continue
                if any(false_at(x, rho, cursors, zero) for x in conjuncts(op)):
                    return "D3"
    return None


def readers(doc: dict, family: str, cursors: list, zero: list) -> tuple[list, list]:
    """D1-D3 over every action of the document: (live readers, excluded readers), in scan order."""
    live, excluded = [], []
    for b in doc.get("actions") or []:
        for at, seq, terms, rec in records_of(b):
            occ = []
            for t in terms:
                occurrences(t, family, [], occ)
            if not occ:
                continue
            dom = dominating(b, seq, rec)
            rules = [rule_of(rho, anc, dom, cursors, zero) for rho, anc in occ]
            if all(rules):
                excluded.append({"action": b["name"], "at": at, "rules": sorted(set(rules))})
            else:
                live.append({"action": b["name"], "at": at})
    return live, excluded


def classify(doc: dict, family: str, cursors: list, zero: list) -> dict:
    """{"class": "dead" | "live", "live_readers", "excluded"} of one residue basis."""
    live, excluded = readers(doc, family, cursors, zero)
    return {"class": "live" if live else "dead", "live_readers": live, "excluded": excluded}
