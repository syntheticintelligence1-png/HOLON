"""I86's instrument (= I36b: Bundle I's laws over the current deployment, over I69's extraction). The contract is the
docstring of tests_m3/test_bundle_laws.py; this module writes its rules a second time, independently of holon/ (it
imports nothing from holon/), over the committed inputs:

  basis(root, rev=None)      the construction facts the prereg fixes (spec/M3/lib/bundle_laws_basis.json): the members,
                             the principal classes (rule DC1), the payer sites (PY1-PY3), the conservation sites
                             (the payable actions) with their classes (CS1-CS4), the keyed blocked conditions of the
                             sidecar's obligations with their writers and class statuses (K1-K6), the push candidates
                             (PP1-PP3), the queue-linked BMC targets (Q1) and every law id (N1). With rev, I69's outputs
                             (the declaration and the member documents, which the prereg's base does not hold yet) are
                             read from that git revision of this repository; everything else from the working tree.
  expected_status(basis)     the predicted status of every law id (the key's predictions, as data)
  enc_relay(args)            rule PP6's reference encoding: abi.encodeWithSignature over the leaf's arguments, in
                             Python, from the ABI's head/tail rule (no keccak: the selector is computed by tests with
                             tests_m2/_keccak.py, an independent implementation)

Nothing here runs holon, forge or Bend.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDE_REL = "spec/M3/lib/bundle_laws.json"
BASIS_REL = "spec/M3/lib/bundle_laws_basis.json"
BASIS_VERSION = "holon-bundle-laws-basis/0.1"
DECL_REL = "gen/M3/bundle/bundle.json"
LOSSY_REL = "spec/M3/lib/par_lossy.json"
PRINCIPAL_TYPES = ("address",)
INIT_MODIFIERS = ("initializer", "reinitializer")
QUEUE_TIME_FN = "IL1MessageQueue.getFirstUnfinalizedMessageEnqueueTime"


# ------------------------------------------------------------------------------------------------ reading
class Reader:
    """Reads a repo-relative file from the working tree, or (for I69's outputs, `rev_paths`) from a git revision of
    this repository; records the sha256 of every file read."""

    def __init__(self, root: Path, rev: str | None = None, rev_prefixes: tuple = ("gen/M3/bundle/",)):
        self.root, self.rev, self.rev_prefixes = Path(root), rev, rev_prefixes
        self.read: dict[str, str] = {}

    def bytes(self, rel: str) -> bytes:
        if self.rev and rel.startswith(self.rev_prefixes):
            p = subprocess.run(["git", "-C", str(self.root), "show", f"{self.rev}:{rel}"], capture_output=True,
                               env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
            if p.returncode != 0:
                raise FileNotFoundError(f"{self.rev}:{rel}: {p.stderr.decode(errors='replace').strip()}")
            b = p.stdout
        else:
            b = (self.root / rel).read_bytes()
        self.read[rel] = hashlib.sha256(b).hexdigest()
        return b

    def json(self, rel: str):
        return json.loads(self.bytes(rel).decode("utf-8"))


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def x8(o) -> str:
    return hashlib.sha256(canon(o).encode("utf-8")).hexdigest()[:8]


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True) + "\n"


# ------------------------------------------------------------------------------------------------ terms
def head(t):
    return t[0] if isinstance(t, list) and t and isinstance(t[0], str) else None


def subterms(t):
    yield t
    if isinstance(t, list):
        for x in (t[1:] if head(t) is not None else t):
            yield from subterms(x)


def reads(t, pred) -> bool:
    return any(pred(x) for x in subterms(t))


def is_msg_value(t) -> bool:
    return t == ["env", "msg.value"]


def line_of(src: str) -> str:
    """The first line of a span "path:lo[-hi]"."""
    return str(src).rpartition(":")[2].split("-")[0]


def slug(src: str) -> str:
    """DISCH's slug of a span (holon.analysis.closure.slug's rule, written again): the file name's stem lower-cased,
    every run outside [a-z0-9] replaced by "_", then "_" and the line ("a-b" gives "a_b")."""
    file_part, _, line = str(src).rpartition(":")
    stem = file_part.split("/")[-1].split(".", 1)[0].lower()
    return "_".join([re.sub("[^a-z0-9]+", "_", stem), line.replace("-", "_")])


def simplify(t):
    """K2's normal form: a member read of a struct value updated at another member reads the value before the update
    (["member", ["update", X, m2, v], m] -> ["member", X, m] when m != m2); applied bottom-up."""
    if not isinstance(t, list):
        return t
    if head(t) is None:
        return [simplify(x) for x in t]
    t = [t[0]] + [simplify(x) for x in t[1:]]
    while head(t) == "member" and head(t[1]) == "update" and len(t[1]) == 4 and t[1][2] != t[2]:
        t = ["member", t[1][1], t[2]]
    return t


def negate(t):
    return t[1] if head(t) == "!" else ["!", t]


# ------------------------------------------------------------------------------------------------ members
def members(rd: Reader) -> list[dict]:
    """The declaration's members (I69's rule L2 file), each with its document (read) and its relative path."""
    decl = rd.json(DECL_REL)
    out = []
    for m in decl["members"]:
        rel = m["document"]["path"]
        doc = rd.json(rel)
        out.append({"name": m["name"], "contract": m["contract"], "document": rel, "doc": doc,
                    "adopted": m.get("sidecar") is None})
    return out


def actions(doc: dict) -> dict:
    return {a["name"]: a for a in doc.get("actions") or []}


def storage(doc: dict) -> dict:
    out = {}
    for s in (doc.get("storage") or []) + (doc.get("inherited_storage") or []):
        if isinstance(s, dict) and s.get("name"):
            out.setdefault(s["name"], s)
    return out


def class_of(action: dict) -> str | None:
    """DC1: an action's principal class: its principal record's modifier, "anyone" without one; None for an
    initializer (modifier initializer or reinitializer), which DC2 excludes from every class."""
    if any(m in INIT_MODIFIERS for m in action.get("modifiers") or []):
        return None
    p = action.get("principal")
    return p.get("modifier") if isinstance(p, dict) and p.get("modifier") else "anyone"


def classes(doc: dict) -> dict:
    """{class: sorted non-view action names} over the document's state-changing actions (DC1, DC2)."""
    out: dict = {}
    for a in doc.get("actions") or []:
        if a.get("mutability") in ("view", "pure"):
            continue
        c = class_of(a)
        if c is not None:
            out.setdefault(c, []).append(a["name"])
    return {c: sorted(v) for c, v in sorted(out.items())}


# ------------------------------------------------------------------------------------------------ PY: payer
def principal_terms(t, action: dict, doc: dict) -> bool:
    """PY1's principal argument: the caller, tx.origin, or a parameter, storage family or immutable of address type."""
    if t == ["caller"] or t == ["env", "tx.origin"]:
        return True
    if head(t) == "param":
        p = next((p for p in action.get("params") or [] if p.get("name") == t[1]), None)
        return bool(p) and p.get("type") in PRINCIPAL_TYPES
    if head(t) == "storage":
        s = storage(doc).get(t[1])
        return bool(s) and s.get("kind") == "scalar" and s.get("value") in PRINCIPAL_TYPES
    if head(t) == "immutable":
        return any(i.get("name") == t[1] and i.get("type") in PRINCIPAL_TYPES
                   for i in doc.get("immutables") or [] if isinstance(i, dict))
    return False


def price_bound(expr):
    """PY1: the bound R of a price check [">=", msg.value, R] or ["<=", R, msg.value], else None."""
    if head(expr) == ">=" and is_msg_value(expr[1]):
        return expr[2]
    if head(expr) == "<=" and is_msg_value(expr[2]):
        return expr[1]
    return None


def payer_sites(mem: list[dict]) -> list[dict]:
    """PY1-PY3: one site per (payable action, price check, price call with a principal argument)."""
    out = []
    for m in mem:
        doc = m["doc"]
        for a in doc.get("actions") or []:
            if not a.get("payable"):
                continue
            for g in a.get("guards") or []:
                r = price_bound(g.get("expr"))
                if r is None:
                    continue
                for t in subterms(r):
                    if head(t) != "call":
                        continue
                    keys = [x for x in t[2:] if principal_terms(x, a, doc)]
                    if not keys:
                        continue
                    lid = f"L_sort_payer_{m['contract']}_{a['name']}_{line_of(g['src'])}"
                    out.append({"law_id": lid, "member": m["name"], "contract": m["contract"], "action": a["name"],
                                "check_src": g["src"], "price_call": t[1], "keys": keys, "payer": ["caller"],
                                "keyed_on_payer": all(k == ["caller"] for k in keys)})
    return sorted(out, key=lambda s: s["law_id"])


# ------------------------------------------------------------------------------------------------ CS: conservation
def value_calls(a: dict) -> list[dict]:
    return [c for c in a.get("calls") or [] if c.get("value") not in (0, None)]


def conservation_sites(mem: list[dict]) -> list[dict]:
    """CS1-CS4: one site per payable action of a member (receive included): the inflow half of whitepaper §7.5
    ("every inflow is accounted for"). Its class: ledger when msg.value reaches the value of a write of a mapping
    family (the inflow is credited to a mapping cell), outflow when it reaches the value of a value call (it is
    forwarded), both when both, unaccounted when neither."""
    out = []
    for m in mem:
        doc = m["doc"]
        st = storage(doc)
        for a in doc.get("actions") or []:
            if not a.get("payable"):
                continue
            credited = sorted({w["family"] for w in a.get("writes") or []
                               if reads(w.get("value"), is_msg_value)})
            mapping = [f for f in credited if (st.get(f) or {}).get("kind") == "mapping"]
            forwarded = sorted({c["src"] for c in value_calls(a) if reads(c.get("value"), is_msg_value)})
            reasons = (["I68"] if mapping else []) + (["outflow"] if forwarded else [])
            cls = "unaccounted" if not (credited or forwarded) else (
                "ledger" if mapping and not forwarded else ("outflow" if forwarded and not mapping else
                                                            ("ledger+outflow" if mapping else "scalar")))
            out.append({"law_id": f"L_sort_cons_{m['contract']}_{a['name']}", "member": m["name"],
                        "contract": m["contract"], "action": a["name"], "credited": credited,
                        "mapping_ledgers": mapping, "forwarded": forwarded, "class": cls, "dependencies": reasons})
    return sorted(out, key=lambda s: s["law_id"])


# ------------------------------------------------------------------------------------------------ K: keyed DISCH
def keyed_conjunct(doc: dict, check: str):
    """K1: the guard of the sidecar's check id "<action>#<span>#<k>": the k-th guard of the action with that span."""
    an, span, k = check.split("#")
    a = actions(doc)[an]
    gs = [g for g in a.get("guards") or [] if g.get("src") == span]
    return a, gs[int(k)]


def key_terms(t, params: set) -> list:
    """The keys of the mapping reads of a term whose key reads an input (a parameter or the caller)."""
    out = []
    for x in subterms(t):
        if head(x) == "map" and reads(x[2], lambda z: (head(z) == "param" and z[1] in params) or z == ["caller"]):
            if x[2] not in out:
                out.append(x[2])
    return out


def abstract_key(t, key, var=("var", "k")):
    if t == key:
        return list(var)
    if isinstance(t, list):
        return [abstract_key(x, key, var) for x in t]
    return t


def families_read(t) -> list:
    out = set()
    for x in subterms(t):
        if head(x) == "storage":
            out.add(x[1])
    return sorted(out)


def keyed_obligation(mem: list[dict], ob: dict) -> dict:
    """K1-K6 for one sidecar obligation: the conjunct, its blocked condition B(k) over the key variable k, the
    families B reads, their writers by class (initializers excluded, DC2; the guarded action excluded, K4: it writes
    only when its guard holds, i.e. when B does not), the class statuses (blocked: no writer of a family of B in the
    class; discharges: some) and the law ids."""
    m = next(x for x in mem if x["name"] == ob["member"])
    doc = m["doc"]
    a, g = keyed_conjunct(doc, ob["check"])
    params = {p["name"] for p in a.get("params") or []}
    conj = simplify(g["expr"])
    keys = key_terms(conj, params)
    if len(keys) != 1:
        raise ValueError(f"{ob['check']}: {len(keys)} input-keyed mapping reads (K1 needs exactly one)")
    blocked = simplify(abstract_key(negate(conj), keys[0]))
    fams = families_read(blocked)
    cls = classes(doc)
    writers: dict = {}
    for b in doc.get("actions") or []:
        if b["name"] == a["name"] or class_of(b) is None:
            continue
        if any(w["family"] in fams for w in b.get("writes") or []):
            writers.setdefault(class_of(b), []).append(b["name"])
    status = {c: ("discharges" if writers.get(c) else "blocked") for c in cls}
    tag = f"{slug(g['src'])}_{x8(blocked)}"
    laws = {"keyed_blocking": [f"L_disch_kblk_{tag}_{c}" for c in cls if status[c] == "blocked"],
            "keyed_external": [f"L_disch_kext_{tag}_{c}" for c in cls if status[c] == "discharges"],
            "keyed_external_none": [f"L_disch_knoext_{tag}_{c}" for c in cls if status[c] == "discharges"]}
    return {"obligation": ob["obligation"], "member": m["name"], "contract": m["contract"], "action": a["name"],
            "check": ob["check"], "conjunct": conj, "key": keys[0], "blocked": blocked, "families": fams,
            "classes": cls, "writers": {c: sorted(v) for c, v in sorted(writers.items())}, "status": status,
            "tag": tag, "laws": laws}


# ------------------------------------------------------------------------------------------------ PP: push
def push_candidates(mem: list[dict]) -> list[dict]:
    """PP1-PP3: a loop record whose carried name enters as a keccak256 hash E (the leaf) and whose next value selects
    by the bit ["&", [">>", ["param", P], ["iter", span]], 1] of an input P (the index): a Merkle fold reading only
    bits 0..bound-1 of P. The pushed law's leaf preimage is E, the index P, its field offset in E (4 + 32 times P's
    position among E's encoded arguments, for abi.encodeWithSignature over static heads before it)."""
    out = []
    for m in mem:
        for a in m["doc"].get("actions") or []:
            for lp in a.get("loops") or []:
                span = None
                for c in lp.get("carried") or []:
                    if head(c.get("value")) == "carried":
                        span = c["value"][1]
                for c in lp.get("carried") or []:
                    e = c.get("entry")
                    if head(e) != "keccak256" or head(e[1]) != "abi.encodeWithSignature":
                        continue
                    nxt = next((n["value"] for n in lp.get("next") or [] if n.get("name") == c["name"]), None)
                    idx = None
                    for x in subterms(nxt):
                        if head(x) == "&" and x[2] == 1 and head(x[1]) == ">>" and head(x[1][1]) == "param" \
                                and x[1][2] == ["iter", span]:
                            idx = x[1][1]
                    if idx is None:
                        continue
                    args = e[1][2:]
                    pos = args.index(idx)
                    ptypes = {p["name"]: p["type"] for p in a.get("params") or []}
                    static_before = all(ptypes.get(x[1]) in ("address", "uint256", "bytes32")
                                        for x in args[:pos] if head(x) == "param")
                    out.append({"law_id": f"L_par_push_{m['contract']}_{a['name']}_{line_of(merkle_check(a, span))}",
                                "merkle_check": merkle_check(a, span),
                                "member": m["name"], "contract": m["contract"], "action": a["name"], "loop": span,
                                "bound": lp.get("bound"), "leaf": e, "index": idx, "index_position": pos,
                                "index_offset": 4 + 32 * pos if static_before else None,
                                "signature": bytes.fromhex(e[1][1][1]).decode("ascii"),
                                "arguments": [[x[1], ptypes.get(x[1])] for x in args]})
    return sorted(out, key=lambda s: s["law_id"])


def merkle_check(a: dict, loop_span: str) -> str:
    """PP5's line: the span of the action's first guard whose expression reads the fold's exit (["exit", loop span,
    name]): the Merkle check that consumes the truncated index."""
    for g in a.get("guards") or []:
        if any(head(x) == "exit" and x[1] == loop_span for x in subterms(g.get("expr"))):
            return g["src"]
    raise ValueError(f"{a['name']}: no guard reads the exit of the loop {loop_span}")


# ------------------------------------------------------------------------------------------------ Q: BMC targets
def q28_targets(mem: list[dict]) -> dict:
    """Q1: every check of the adopted member's actions whose expression calls or callok's the queue's
    getFirstUnfinalizedMessageEnqueueTime (DISCH D1's check ids, written again: guard reaches, panics, checks and calls
    whose expr is not 1, in seq order, k counting earlier checks on the same span), with its kind: callok (the call's
    success), fits (the sum's overflow), guard (a guard reach) or checks (an implicit check)."""
    rol = next(m for m in mem if m["adopted"])
    out = []
    for a in rol["doc"].get("actions") or []:
        found = []
        for g in a.get("guards") or []:
            for r in g.get("reaches") or []:
                found.append((r["seq"], g.get("src"), r.get("expr"), "guards"))
        for p in a.get("panics") or []:
            found.append((p["seq"], p.get("src"), p.get("expr"), "panics"))
        for c in a.get("checks") or []:
            found.append((c["seq"], c.get("src"), c.get("expr"), "checks"))
        for c in a.get("calls") or []:
            if "expr" in c and c["expr"] != 1:
                found.append((c["seq"], c.get("src"), c["expr"], "calls"))
        found.sort(key=lambda r: r[0])
        used: dict = {}
        for seq, span, expr, sec in found:
            k = used.get(span, 0)
            used[span] = k + 1
            cid = f"{a['name']}#{span}#{k}"
            if reads(expr, lambda z: head(z) in ("call", "callok") and len(z) > 1 and z[1] == QUEUE_TIME_FN):
                kind = "callok" if head(expr) == "callok" else (
                    "fits" if head(expr) == "fits" else ("guard" if sec == "guards" else sec))
                out.append({"id": cid, "kind": kind})
    return {"targets": sorted(out, key=lambda r: r["id"]),
            "callok": sorted(r["id"] for r in out if r["kind"] == "callok"),
            "delay_guards": sorted(r["id"] for r in out if r["kind"] == "guard")}


# ------------------------------------------------------------------------------------------------ the basis
def basis(root: Path = ROOT, rev: str | None = None) -> dict:
    rd = Reader(Path(root), rev)
    side = rd.json(SIDE_REL)
    mem = members(rd)
    lossy = rd.json(LOSSY_REL)
    pay = payer_sites(mem)
    cons = conservation_sites(mem)
    keyed = [keyed_obligation(mem, ob) for ob in side["keyed"]["obligations"]]
    push = push_candidates(mem)
    deferred = [d for d in lossy.get("deferred") or [] if d.get("id") in side["push"]["deferred"]]
    q = q28_targets(mem)
    ids = {"payer": [s["law_id"] for s in pay], "conservation": [s["law_id"] for s in cons],
           "keyed_blocking": sorted(x for k in keyed for x in k["laws"]["keyed_blocking"]),
           "keyed_external": sorted(x for k in keyed for x in k["laws"]["keyed_external"]),
           "keyed_external_none": sorted(x for k in keyed for x in k["laws"]["keyed_external_none"]),
           "push": [s["law_id"] for s in push]}
    return {"basis_version": BASIS_VERSION, "rev": rev,
            "members": [{"name": m["name"], "contract": m["contract"], "document": m["document"],
                         "adopted": m["adopted"], "classes": classes(m["doc"])} for m in mem],
            "payer": pay, "conservation": cons, "keyed": keyed, "push": push,
            "push_deferred": [{"id": d["id"], "sites": d["sites"], "lossy_map": d["lossy_map"]} for d in deferred],
            "q28": q, "law_ids": ids, "law_count": sum(len(v) for v in ids.values()),
            "inputs": [{"path": p, "sha256": h} for p, h in sorted(rd.read.items())]}


def expected_status(b: dict, side: dict) -> dict:
    """The key's predicted status per law id (the predictions, as data; decided by the build's records):
    payer PROVED when keyed on the payer else REFUTED (PY3); conservation REFUTED when unaccounted, else UNKNOWN
    naming its dependencies (I68 for a mapping credit, the model's missing value-outflow record for a forwarded
    inflow); keyed_blocking UNKNOWN (I68);
    keyed_external PROVED and keyed_external_none REFUTED (a discharging class's witness); push PROVED."""
    out = {}
    for s in b["payer"]:
        out[s["law_id"]] = "PROVED" if s["keyed_on_payer"] else "REFUTED"
    for s in b["conservation"]:
        out[s["law_id"]] = "REFUTED" if s["class"] == "unaccounted" else "UNKNOWN"
    for x in b["law_ids"]["keyed_blocking"]:
        out[x] = "UNKNOWN"
    for x in b["law_ids"]["keyed_external"]:
        out[x] = "PROVED"
    for x in b["law_ids"]["keyed_external_none"]:
        out[x] = "REFUTED"
    for x in b["law_ids"]["push"]:
        out[x] = "PROVED"
    return dict(sorted(out.items()))


# ------------------------------------------------------------------------------------------------ PP6
def _word(v: int) -> bytes:
    return int(v).to_bytes(32, "big")


def enc_relay(selector: bytes, types: list, values: list) -> bytes:
    """abi.encodeWithSignature's bytes for static words (address, uint256, bytes32) and dynamic bytes: the selector,
    the heads (a dynamic argument's head is the offset of its tail), then the tails (length word, data padded to 32)."""
    heads, tails = [], b""
    n = len(types)
    for t, v in zip(types, values):
        if t == "bytes":
            heads.append(_word(32 * n + len(tails)))
            data = bytes(v)
            tails += _word(len(data)) + data + b"\x00" * ((32 - len(data) % 32) % 32)
        else:
            heads.append(_word(v))
    return selector + b"".join(heads) + tails


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests_m3._i86")
    ap.add_argument("--write", action="store_true", help=f"write {BASIS_REL}")
    ap.add_argument("--rev", help="read I69's outputs (gen/M3/bundle/) from this git revision")
    a = ap.parse_args(argv)
    b = basis(ROOT, a.rev)
    text = dumps(b)
    if a.write:
        (ROOT / BASIS_REL).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
