"""Rules over a bundle of linked members (BUILD_PLAN row I84 = I37b; whitepaper §5.1 PAR-domain at an interface, §5.5
FACT, §5.7 DISCH self-controlled enabledness, §3.8 En_G; the contract is the docstring of
tests_m3/test_bundle2_laws.py, rules C1-C2, N1, LD1-LD3, FC1-FC3, FP1-FP2, FM1 and D1-D2). Three sub-forms, each read
from the milestone's bundle-laws sidecar (spec/<M>/lib/bundle2_laws.json), the bundle declaration it names
(I80's links L2, public-input views E4 and cost sites E5) and the documents:

  link_domain      (PAR) one law per static link row of kind action: when the caller's action succeeds from a reachable
                   state (the callee as an oracle), the callee's resolution of the call's (version, index) arguments
                   (by the view of the action's input) is defined and non-zero, from any state the callee reaches from
                   the laws' deployment
  public_input     (FACT) one law per (view row whose action has the receiver's input member, consumer field): two
                   successful calls of the action from reachable states with equal public inputs hold equal values of
                   the field in the parent header input (Thm 6.8 (iii): ker(m) within ker(c))
  self_controlled  (DISCH) one law per state-indexed cost site (a loop whose count reads storage only) of an adopted
                   member's action: whenever the action succeeds from a reachable state, its calibrated cost
                   c0 + c1 * iters(s) is at most the gas ceiling G

The consumers of public_input are the derivation document's call edges whose callee is a decoder of the codec
document's header codec, each with its decoder's one read (offset, width); their receiver (the commit transaction's
parent header) is the sidecar's binding. The measure F(PI, field) is the field's class in the headers the commit
actions store (free: 8 * width bits; checked: log2 of the admitted values; computed: a bound). Nothing here names a
target: every action, family, member, field and constant comes from the sidecar, the declaration and the documents.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

RULE_OF = {"link_domain": "PAR", "public_input": "FACT", "self_controlled": "DISCH"}
SUBFORMS = ("link_domain", "public_input", "self_controlled")
TEMPLATE_VERSION = 1
SIDECAR_VERSION = "holon-bundle2-laws/0.1"
PREFIX = {"link_domain": "L_par_ldom_", "public_input": "L_fact_pi_", "self_controlled": "L_disch_self_"}
ROOT = Path(__file__).resolve().parents[2]
HASHES = ("keccak256", "sha256")


class Bundle2Error(ValueError):
    """A basis that cannot be derived (exit 3 of derive)."""


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sidecar_path(milestone: str, root: Path) -> Path:
    return Path(root) / "spec" / str(milestone) / "lib" / "bundle2_laws.json"


# ------------------------------------------------------------------------------------------------ terms
def is_op(t, op=None) -> bool:
    return isinstance(t, list) and bool(t) and isinstance(t[0], str) and (op is None or t[0] == op)


def subterms(t):
    yield t
    if isinstance(t, list):
        for x in t:
            yield from subterms(x)
    elif isinstance(t, dict):
        for x in t.values():
            yield from subterms(x)


def member_ref(t):
    if is_op(t, "member") and len(t) == 3 and is_op(t[1], "param") and isinstance(t[2], str):
        return (t[1][1], t[2])
    return None


def reads_value(t, ref) -> bool:
    """The member ref occurs outside every hash preimage (a hash binds it to the hash's other side, never to a value)."""
    if member_ref(t) == ref:
        return True
    if is_op(t) and t[0] in HASHES:
        return False
    if isinstance(t, list):
        return any(reads_value(x, ref) for x in t)
    if isinstance(t, dict):
        return any(reads_value(x, ref) for x in t.values())
    return False


_ATOMS = ("storage", "env", "param", "call", "blobhash", "word", "byte", "map", "immutable", "count", "iter")


def atoms(t) -> set:
    out = set()

    def go(x):
        r = member_ref(x)
        if r is not None:
            out.add(("member",) + r)
            return
        if is_op(x) and x[0] in _ATOMS:
            out.add((x[0], canon(x[1:])))
            return
        if isinstance(x, list):
            for y in x:
                go(y)
        elif isinstance(x, dict):
            for y in x.values():
                go(y)
    go(t)
    return out


_CMP = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
        "==": lambda a, b: a == b, "!=": lambda a, b: a != b}


def _eval(t, ref, v: int):
    if isinstance(t, bool) or isinstance(t, int):
        return t
    if member_ref(t) == ref:
        return v
    if is_op(t):
        op, a = t[0], t[1:]
        if op in _CMP:
            return _CMP[op](_eval(a[0], ref, v), _eval(a[1], ref, v))
        if op == "!":
            return not _eval(a[0], ref, v)
        if op == "&&":
            return all(_eval(x, ref, v) for x in a)
        if op == "||":
            return any(_eval(x, ref, v) for x in a)
        if op == "+":
            return sum(_eval(x, ref, v) for x in a)
        if op == "-":
            return _eval(a[0], ref, v) - _eval(a[1], ref, v)
    raise ValueError("not evaluable")


def storage_only(t) -> bool:
    reads = False
    for x in subterms(t):
        if is_op(x, "storage"):
            reads = True
        elif is_op(x) and x[0] in ("param", "env", "count", "iter", "word", "byte", "member", "map", "call",
                                   "blobhash", "immutable", "carried", "exit"):
            return False
    return reads


# ------------------------------------------------------------------------------------------------ the analysis
class Inputs:
    """The sidecar, the declaration and the documents of one milestone's bundle laws."""

    def __init__(self, milestone: str, root: Path, read=None):
        self.m, self.root = milestone, Path(root)
        self.read = read or (lambda p: Path(p).read_bytes())
        p = sidecar_path(milestone, self.root)
        self.side = json.loads(self.read(p).decode("utf-8"))
        if self.side.get("bundle2_laws_version") != SIDECAR_VERSION:
            raise Bundle2Error(f"{p}: bundle2_laws_version is not {SIDECAR_VERSION}")
        inp = self.side["inputs"]
        self.decl = self.json(inp["declaration"])
        self.rollup_rel = inp["rollup_document"]
        self.rollup = self.json(self.rollup_rel)
        self.rollup_sha = sha256_bytes(self.read(self.root / self.rollup_rel))
        self.deriv = self.json(inp["derivation_document"])
        self.codec = self.json(inp["codec_document"])
        g = self.side["gas"]["ceiling"]
        self.ceiling = int(self.json(g["from"])[g["key"]])
        self.members = {m["name"]: m for m in self.decl.get("members") or []}

    def json(self, rel: str) -> dict:
        return json.loads(self.read(self.root / rel).decode("utf-8"))

    def contract(self, member: str) -> str:
        return self.members[member]["contract"]

    def document(self, member: str) -> dict:
        m = self.members[member]
        if m["document"]["path"] == self.rollup_rel:
            return self.rollup
        return self.json(m["document"]["path"])

    def model(self, member: str) -> str:
        return Path(self.members[member]["document"]["path"]).name.removesuffix(".json")


def actions(doc: dict) -> dict:
    return {a["name"]: a for a in doc["actions"]}


def has_member(action: dict, name: str) -> bool:
    for p in action.get("params") or []:
        if p.get("name") == name or name in [f.get("name") for f in p.get("fields") or []]:
            return True
    return False


def input_of(action: dict, name: str):
    """The input term of a parameter or struct member named name: ["param", p] or ["member", ["param", p], name]."""
    for p in action.get("params") or []:
        if p.get("name") == name:
            return ["param", name]
        if name in [f.get("name") for f in p.get("fields") or []]:
            return ["member", ["param", p["name"]], name]
    return None


def consumers(I: Inputs) -> list:
    """FC1-FC2: one entry per decoder of the header codec the derivation document's call edges reach, sorted."""
    codec = I.side["consumers"]["codec"]
    reads = {}
    for dec in I.codec["go"]["codecs"]["decoders"]:
        f = dec["function"]
        if f.startswith(codec + ".") and len(dec.get("reads") or []) == 1:
            reads[f] = dec["reads"][0]
    out = {}
    for e in I.deriv["go"]["calls"]["edges"]:
        f = e.get("callee")
        if f in reads:
            g = f[len(codec) + 1:]
            ent = out.setdefault(g, {"getter": g, "function": f, "offset": reads[f]["offset"],
                                     "width": reads[f]["width"], "via": reads[f]["via"], "edges": []})
            ent["edges"].append({"caller": e["caller"], "site": e["site"]})
    for ent in out.values():
        ent["edges"] = sorted(ent["edges"], key=lambda x: (x["caller"], x["site"]))
    return [out[g] for g in sorted(out)]


def _images(a: dict) -> list:
    out = []
    for w in a.get("writes") or []:
        v = w.get("value")
        if is_op(v, "keccak256") and is_op(v[1], "slice") and is_op(v[1][1], "mem"):
            out.append(v[1][1])
    return out


def _store_at(image, offset: int):
    for x in subterms(image):
        if is_op(x) and x[0] in ("mstore", "mstore8") and len(x) == 3 and x[1] == offset:
            return x[0], x[2]
    return None


def _checks(a: dict) -> list:
    return [r["expr"] for sec in ("checks", "guards") for r in (a.get(sec) or [])
            if r.get("kind") != "abi" and "expr" in r]


def field_class(doc: dict, offset: int, width: int) -> dict:
    """FM1 over the header images the document's actions commit (as tests_m3/_i84.py::field_class states it)."""
    bits = 8 * width
    seen = []
    for name, a in sorted(actions(doc).items()):
        for img in _images(a):
            st = _store_at(img, offset)
            if st is None:
                continue
            op, val = st
            ref = None
            if op == "mstore8" and width == 1:
                ref = member_ref(val)
            elif op == "mstore" and is_op(val, "<<") and len(val) == 3 and val[2] == 256 - bits:
                ref = member_ref(val[1])
            elif op == "mstore" and bits == 256:
                ref = member_ref(val)
            if ref is None:
                seen.append({"action": name, "class": "computed"})
                continue
            reading = [e for e in _checks(a) if reads_value(e, ref)]
            if not reading:
                seen.append({"action": name, "class": "free", "member": list(ref)})
                continue
            if width > 2:
                seen.append({"action": name, "class": "checked_wide", "member": list(ref)})
                continue
            closed = [e for e in reading if atoms(e) == {("member",) + ref}]
            joint = [e for e in reading if atoms(e) != {("member",) + ref}]
            admitted = [v for v in range(1 << bits) if all(_eval(e, ref, v) for e in closed)]
            seen.append({"action": name, "class": "checked_joint" if joint else "checked", "member": list(ref),
                         "admitted": admitted})
    classes = sorted({s["class"] for s in seen})
    acts = sorted(s["action"] for s in seen)
    if not seen:
        return {"class": "absent", "kind": "bound", "lower": 1.0, "upper": float(bits), "actions": []}
    if classes == ["free"]:
        return {"class": "free", "kind": "value", "value": float(bits), "lower": float(bits), "upper": float(bits),
                "actions": acts}
    if classes == ["checked"] and len({tuple(s["admitted"]) for s in seen}) == 1:
        n = len(seen[0]["admitted"])
        v = round(math.log2(n), 6) if n else 0.0
        return {"class": "checked", "kind": "value", "value": v, "lower": v, "upper": v, "actions": acts,
                "admitted": seen[0]["admitted"]}
    if set(classes) <= {"checked", "checked_joint"}:
        n = max(len(s["admitted"]) for s in seen)
        return {"class": "checked_joint", "kind": "bound", "lower": 1.0, "upper": round(math.log2(n), 6),
                "actions": acts, "admitted": sorted({v for s in seen for v in s["admitted"]})}
    return {"class": "computed" if classes == ["computed"] else "mixed", "kind": "bound", "lower": 1.0,
            "upper": float(bits), "actions": acts}


def _lines(src: str) -> str:
    return src.rsplit(":", 1)[1].replace("-", "_")


def analyse(I: Inputs) -> dict:
    """{law_id: {"subform", "bundle_id", "basis", "measure"?}} for the three sub-forms (N1)."""
    out = {}
    model = I.model(next(n for n, m in I.members.items() if m["document"]["path"] == I.rollup_rel))
    dep = (I.side.get("deployment") or {}).get("router") or {}
    # link_domain: one per static link row of kind action
    views = {(r["member"], r["action"], r["src"]): r for r in I.decl.get("public_input") or []}
    for r in I.decl.get("links") or []:
        member, action, src, fn, callee, kind, target = r
        if kind != "action":
            continue
        view = views.get((member, action, src))
        if view is None:
            raise Bundle2Error(f"the link {member}.{action} at {src} has no public-input view (E4)")
        lid = f"{PREFIX['link_domain']}{I.contract(member)}_{action}_{I.contract(callee)}_{target}"
        bid = f"{model}:link_domain:{action}:{callee}:{target}"
        out[lid] = {"subform": "link_domain", "bundle_id": bid, "action": action,
                    "basis": {"member": member, "action": action, "src": src, "fn": fn, "callee": callee,
                              "target": target, "args": view["args"][:2],
                              "deployment": {"versions": dep.get("versions"), "verifier": dep.get("verifier")}}}
    # public_input: per view row whose action has the receiver's input member, per consumer field
    recv = I.side["consumers"]["receiver"]
    cons = consumers(I)
    acts = actions(I.rollup)
    for row in I.decl.get("public_input") or []:
        a = acts.get(row["action"])
        if a is None or not has_member(a, recv["solidity_member"]):
            continue
        pi = [x for x in row["args"] if isinstance(x, dict) and x.get("hash")]
        if len(pi) != 1:
            raise Bundle2Error(f"{row['action']}: the view has {len(pi)} hash arguments, not one")
        for c in cons:
            lid = f"{PREFIX['public_input']}{I.contract(row['member'])}_{row['action']}_{c['getter']}"
            bid = f"{model}:public_input:{row['action']}:{c['getter']}"
            out[lid] = {"subform": "public_input", "bundle_id": bid, "action": row["action"],
                        "basis": {"member": row["member"], "action": row["action"], "src": row["src"],
                                  "pi": pi[0], "input": input_of(a, recv["solidity_member"]),
                                  "consumer": {k: c[k] for k in ("getter", "function", "offset", "width", "via",
                                                                 "edges")}},
                        "measure": field_class(I.rollup, c["offset"], c["width"])}
    # self_controlled: per state-indexed cost site of the adopted member
    for r in I.decl.get("cost_sites") or []:
        member, action, span, seq, _is_cost, count = r
        if not storage_only(count) or I.members[member]["document"]["path"] != I.rollup_rel:
            continue
        lid = f"{PREFIX['self_controlled']}{I.contract(member)}_{action}_{_lines(span)}"
        bid = f"{model}:self_controlled:{action}:{_lines(span)}"
        out[lid] = {"subform": "self_controlled", "bundle_id": bid, "action": action,
                    "basis": {"member": member, "action": action, "span": span, "seq": seq, "count": count,
                              "gas_ceiling": I.ceiling, "writers": writers_of(I.rollup, count)}}
    return dict(sorted(out.items()))


def writers_of(doc: dict, count) -> list:
    """D2's classification: [family, action, principal] for every action whose writes touch a storage family the
    count reads (the document's write records and principals), sorted."""
    fams = sorted({x[1] for x in subterms(count) if is_op(x, "storage")})
    out = set()
    for a in doc["actions"]:
        for w in a.get("writes") or []:
            if w.get("family") in fams:
                p = a.get("principal")
                out.add((w["family"], a["name"], canon(p) if not isinstance(p, str) else p))
    return [list(x) for x in sorted(out)]


# ------------------------------------------------------------------------------------------------ laws
BINDERS = {"link_domain": [("s", "Reach"), ("x", "Act"), ("vt", "Trace")],
           "public_input": [("s1", "Reach"), ("x1", "Act"), ("s2", "Reach"), ("x2", "Act")],
           "self_controlled": [("s", "Reach"), ("x", "Act")]}


def notes(x: dict) -> str:
    b = x["basis"]
    if x["subform"] == "link_domain":
        return (f"if a call x of {b['action']} succeeds from a reachable state s and makes its call {b['fn']} at "
                f"{b['src']} (answered as an oracle), then {b['callee']}'s resolution of the call's (version, index) "
                f"by the view of x's input is defined and non-zero in every state the trace vt reaches from "
                f"{b['callee']}'s deployment (domain coherence at the interface, §5.1)")
    if x["subform"] == "public_input":
        c = b["consumer"]
        return (f"if calls x1 and x2 of {b['action']} both succeed from reachable states and pass equal public inputs "
                f"to {b['src']}, the parent headers they take hold equal {c['getter']} (bytes {c['offset']}.."
                f"{c['offset'] + c['width']}, read by the derivation: Thm 6.8 (iii), ker(m) within ker(c))")
    return (f"if a call x of {b['action']} succeeds from a reachable state s, its calibrated cost c0 + c1 * iters(s) "
            f"(the loop {b['span']}) is at most G = {b['gas_ceiling']} (En_G, §3.8; self-controlled enabledness, §5.7)")


def law_ir(lid: str, x: dict, milestone: str, doc_rel: str, doc_sha: str, catalog_version: str, hashes: list) -> dict:
    binders = [{"q": "forall", "name": n, "type": t} for n, t in BINDERS[x["subform"]]]
    binders += [{"q": "forall", "name": h, "type": "Fn<Bytes,Word>"} for h in hashes]
    return {"ir_version": "holon-ir/0.3", "law_id": lid, "milestone": milestone, "rule": RULE_OF[x["subform"]],
            "subform": x["subform"], "rule_catalog_version": catalog_version, "facts": doc_rel,
            "facts_sha256": doc_sha, "notes": f"{notes(x)}; bundle {x['bundle_id']}",
            "statement": {"binders": binders, "assume": [],
                          "claim": {"eq": [{"bundle": x["bundle_id"], "on": [{"var": y["name"]} for y in binders]},
                                           {"bool": True}]},
                          "scope": {"kind": "unbounded"}}}


def entry_of(lid: str, x: dict, doc_rel: str) -> dict:
    e = {"law_id": lid, "rule": RULE_OF[x["subform"]], "subform": x["subform"], "facts": doc_rel,
         "bundle_id": x["bundle_id"], "basis": x["basis"]}
    if "measure" in x:
        e["measure"] = x["measure"]
    return e


def bundle_hash(subform: str, basis: dict) -> str:
    return sha256_bytes(canon({"template": f"holon.rules.bundle2/{subform}", "template_version": TEMPLATE_VERSION,
                               "basis": basis}).encode("utf-8"))


def bundle_ref(bid: str, law: dict, root=None) -> str:
    """The ref "bundle:<ID>" recomputed from the milestone's bundle-laws sidecar, its declaration and documents."""
    try:
        an = analyse(Inputs(str(law.get("milestone")), Path(root or ROOT)))
    except (OSError, ValueError, KeyError, TypeError, Bundle2Error) as e:
        return sha256_bytes(canon({"absent": bid, "error": type(e).__name__}).encode("utf-8"))
    for x in an.values():
        if x["bundle_id"] == bid:
            return bundle_hash(x["subform"], x["basis"])
    return sha256_bytes(canon({"absent": bid}).encode("utf-8"))


def hash_binders(doc: dict) -> list:
    seen = set()
    for x in subterms(doc.get("actions")):
        if is_op(x) and x[0] in HASHES:
            seen.add(x[0])
    return [h for h in HASHES if h in seen]


# ------------------------------------------------------------------------------------------------ producers
def _elements(ctx) -> dict:
    if getattr(ctx, "_bundle2_elements", None) is not None:
        return ctx._bundle2_elements
    root = Path(ctx.root)
    if not sidecar_path(ctx.milestone, root).is_file():
        ctx._bundle2_elements = {}
        return {}
    inputs = getattr(ctx, "disch_inputs", None) or getattr(ctx, "inputs", None)
    read = inputs.read if inputs is not None else None
    try:
        I = Inputs(ctx.milestone, root, read)
        an = analyse(I)
    except (OSError, ValueError, KeyError) as e:
        raise Bundle2Error(f"the bundle laws of {ctx.milestone}: {type(e).__name__}: {e}") from e
    ctx._bundle2_elements = {"inputs": I, "laws": an, "hashes": hash_binders(I.rollup)}
    return ctx._bundle2_elements


class _Producer:
    def __init__(self, subform: str):
        self.subform = subform
        self.__name__ = f"holon.rules.bundle2.{subform}"

    def produce(self, ctx) -> list:
        el = _elements(ctx)
        if not el:
            return []
        I = el["inputs"]
        out = []
        for lid, x in el["laws"].items():
            if x["subform"] != self.subform:
                continue
            law = law_ir(lid, x, ctx.milestone, I.rollup_rel, I.rollup_sha, ctx.rule_catalog_version, el["hashes"])
            out.append((law, entry_of(lid, x, I.rollup_rel)))
        return out


LINK_DOMAIN = _Producer("link_domain")
PUBLIC_INPUT = _Producer("public_input")
SELF_CONTROLLED = _Producer("self_controlled")
PRODUCERS = {"link_domain": LINK_DOMAIN, "public_input": PUBLIC_INPUT, "self_controlled": SELF_CONTROLLED}
