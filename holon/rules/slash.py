"""NAT's and SORT's slash sub-forms: a migration's slash sites (BUILD_PLAN I70 = I36c; whitepaper §5.3 NAT, §7.5 SORT,
§11.3 O13 and O20; the contract is the docstring of tests_m3/test_cutover_slash.py, rules S1-S5).

  S1 per MIG edge a->b of the versioned document: its retyped in-flight entries T and its reinterpreted entries R (each
     the entry at b and its reads at a)
  S2 a slash site of an action at version v: a call (i) whose receiver is a registry word of R at v (the entry at b, a
     read at a), (ii) one of whose arguments reads a member of an entry of T, (iii) whose result is credited to a
     mapping cell (a write of a mapping family whose value reads that family and holds the call's result term)
  S3 one site pair per (edge a->b, action op of b with an action of a of the same selector) with a site at a and one at
     b; per pair one law of each sub-form: NAT slash L_nat_slash_<contract>_<a>_<b>_<op> and SORT slash
     L_sort_slash_<contract>_<a>_<b>_<op>, facts the versioned document
  S4 the claim {"eq": [{"slash": "<model>:slash_<rule>:<a>:<b>:<op>", "on": [s, k, u, ea, eb]}, {"bool": true}]} over a
     linked state s with its reachability, a batch index k, the edge's migration choice u and the two registries'
     environments; its statement ref slash:<ID> is the sha256 of the canonical {template "holon.rules.slash/slash",
     template_version 1, subform, rule, edge, op, sites} recomputed from the documents (slash_ref)

A milestone derives these only when it has the cutover sidecar (spec/<M>/lib/cutover_slash.json, inputs.versioned):
derive's slash part runs the producers (their part marker keeps the typed part and the NAT part from running them).
Nothing here names a target: every edge, family, member, call and action comes from the documents.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

RULES = ("NAT", "SORT")
SUBFORM = "slash"
TEMPLATE = "holon.rules.slash/slash"
TEMPLATE_VERSION = 1
SIDECAR = "spec/{}/lib/cutover_slash.json"


class SlashError(ValueError):
    """A document that cannot be read as the sidecar names it (derive exit 1)."""


def canon(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _label(entry: str) -> str:
    return entry.split(".", 1)[1] if "." in entry else entry


def _contains(term, sub) -> bool:
    if term == sub:
        return True
    if isinstance(term, list):
        return any(_contains(t, sub) for t in term)
    if isinstance(term, dict):
        return any(_contains(t, sub) for t in term.values())
    return False


def _member_reads(term, family: str) -> list:
    out = []
    if isinstance(term, list):
        if (len(term) == 3 and term[0] == "member" and isinstance(term[1], list) and len(term[1]) == 3
                and term[1][0] == "map" and term[1][1] == ["storage", family]):
            out.append(term[2])
        for t in term:
            out.extend(_member_reads(t, family))
    return out


# ------------------------------------------------------------------------------------------------ S1-S3
def edge_types(vdoc: dict) -> dict:
    """S1."""
    out: dict = {}
    for t in vdoc.get("in_flight_types") or []:
        e = out.setdefault(t["edge"], {"retyped": [], "reinterpreted": []})
        if t["kind"] == "retyped":
            e["retyped"].append(_label(t["entry"]))
        elif t["kind"] == "reinterpreted":
            e["reinterpreted"].append({"entry": _label(t["entry"]), "reads": sorted(_label(r) for r in t["reads"])})
    for e in out.values():
        e["retyped"].sort()
        e["reinterpreted"].sort(key=lambda r: r["entry"])
    return out


def _credits(action: dict, call: dict) -> list:
    res = ["call", call["fn"], *call["args"]]
    out = []
    for w in action.get("writes") or []:
        path = w.get("path") or []
        if not path or not isinstance(path[0], list) or path[0][0] != "map":
            continue
        if _contains(w.get("value"), res) and _contains(w.get("value"), ["storage", w["family"]]):
            out.append({"family": w["family"], "seq": w.get("seq"), "src": w.get("src")})
    return out


def sites(action: dict, words: list, retyped: list) -> list:
    """S2."""
    out = []
    for c in action.get("calls") or []:
        rec = c.get("receiver")
        if not (isinstance(rec, list) and len(rec) == 2 and rec[0] == "storage" and rec[1] in words):
            continue
        reads = sorted({f"{f}.{m}" for f in retyped for a in c.get("args") or [] for m in _member_reads(a, f)})
        if not reads:
            continue
        cr = _credits(action, c)
        if cr:
            out.append({"fn": c["fn"], "receiver": rec[1], "reads": reads, "seq": c.get("seq"), "src": c.get("src"),
                        "credits": cr})
    return out


def pairs_of(vdoc: dict, docs: dict) -> list:
    """S3: the site pairs, each with its two law ids."""
    contract = vdoc["contract"]["name"]
    types = edge_types(vdoc)
    out = []
    for edge in sorted(types):
        a, b = edge.split("->")
        t = types[edge]
        if not t["retyped"] or not t["reinterpreted"]:
            continue
        words_b = sorted({r["entry"] for r in t["reinterpreted"]})
        words_a = sorted({x for r in t["reinterpreted"] for x in r["reads"]})
        acts_a = {x["name"]: x for x in docs[a]["actions"]}
        for op in sorted(x["name"] for x in docs[b]["actions"]):
            act_b = next(x for x in docs[b]["actions"] if x["name"] == op)
            act_a = acts_a.get(op)
            if act_a is None or act_a.get("selector") != act_b.get("selector"):
                continue
            sa, sb = sites(act_a, words_a, t["retyped"]), sites(act_b, words_b, t["retyped"])
            if sa and sb:
                tag = f"{contract}_{a}_{b}_{op}"
                out.append({"edge": edge, "op": op, "selector": act_b.get("selector"), "a": sa, "b": sb,
                            "laws": {"NAT": f"L_nat_slash_{tag}", "SORT": f"L_sort_slash_{tag}"}})
    return out


def slash_id(model: str, rule: str, edge: str, op: str) -> str:
    a, b = edge.split("->")
    return f"{model}:slash_{rule.lower()}:{a}:{b}:{op}"


# ------------------------------------------------------------------------------------------------ the inputs
def has_sidecar(milestone: str, root: Path) -> bool:
    return (Path(root) / SIDECAR.format(milestone)).is_file()


def read_inputs(milestone: str, root: Path, read=None) -> tuple:
    """(versioned document's path, its sha256, the document, {version: document}, the model name), every file through
    read (a derive input list's reader) when given."""
    root = Path(root)

    def rd(rel: str) -> bytes:
        p = root / rel
        return read(p) if read is not None else p.read_bytes()
    side = json.loads(rd(SIDECAR.format(milestone)).decode("utf-8"))
    vrel = side["inputs"]["versioned"]
    vdata = rd(vrel)
    vdoc = json.loads(vdata.decode("utf-8"))
    docs = {}
    for v, d in sorted(vdoc["documents"].items()):
        data = rd(d["path"])
        if hashlib.sha256(data).hexdigest() != d["sha256"]:
            raise SlashError(f"{d['path']} is not the document {vrel} records")
        docs[v] = json.loads(data.decode("utf-8"))
    model = Path(vrel).name[:-len(".json")] if vrel.endswith(".json") else Path(vrel).name
    return vrel, hashlib.sha256(vdata).hexdigest(), vdoc, docs, model


def spec_of(pair: dict, rule: str) -> dict:
    return {"template": TEMPLATE, "template_version": TEMPLATE_VERSION, "subform": SUBFORM, "rule": rule,
            "edge": pair["edge"], "op": pair["op"], "sites": {"a": pair["a"], "b": pair["b"]}}


def slash_ref(sid: str, law: dict, root=None) -> str:
    """The ref slash:<ID>: the sha256 (hex) of the canonical spec of the site pair whose id is ID, recomputed from the
    law's versioned document and its per-version documents."""
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    try:
        _rel, _sha, vdoc, docs, model = read_inputs(str(law.get("milestone")), root)
        for p in pairs_of(vdoc, docs):
            for rule in RULES:
                if slash_id(model, rule, p["edge"], p["op"]) == sid:
                    return hashlib.sha256(canon(spec_of(p, rule)).encode("utf-8")).hexdigest()
    except (OSError, ValueError, KeyError, TypeError) as e:
        return hashlib.sha256(canon({"absent": sid, "error": type(e).__name__}).encode("utf-8")).hexdigest()
    return hashlib.sha256(canon({"absent": sid}).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------ the producers
def law_of(pair: dict, rule: str, milestone: str, cv: str, rel: str, sha: str, model: str) -> dict:
    a, b = pair["edge"].split("->")
    sid = slash_id(model, rule, pair["edge"], pair["op"])
    sa = "; ".join(f"{s['fn']} on {s['receiver']} reading {', '.join(s['reads'])}" for s in pair["a"])
    sb = "; ".join(f"{s['fn']} on {s['receiver']} reading {', '.join(s['reads'])}" for s in pair["b"])
    if rule == "NAT":
        what = (f"slash naturality (whitepaper §5.3 (b), observed at the slash site): from a linked state s at {a} in "
                f"which the batch k is in flight, the answer of {pair['op']}'s slash site at {b} ({sb}) after the "
                f"migration u equals the answer of its slash site at {a} ({sa}) at s")
    else:
        what = (f"slash value (whitepaper §7.5, O20's economic half): from a linked state s at {a} in which the batch k "
                f"is in flight, if {pair['op']}'s slash site at {a} ({sa}) returns a nonzero word at s, its slash site "
                f"at {b} ({sb}) returns a nonzero word after the migration u")
    notes = (f"{what}; the registries' own calls answer ok (ea, eb); slash {sid}")
    binders = [{"q": "forall", "name": "s", "type": "Reach"}, {"q": "forall", "name": "k", "type": "Word"},
               {"q": "forall", "name": "u", "type": "Act"}, {"q": "forall", "name": "ea", "type": "Env"},
               {"q": "forall", "name": "eb", "type": "Env"}, {"q": "forall", "name": "keccak256",
                                                              "type": "Fn<Bytes,Word>"}]
    on = [{"var": "s"}, {"var": "k"}, {"var": "u"}, {"var": "ea"}, {"var": "eb"}]
    return {"ir_version": "holon-ir/0.3", "law_id": pair["laws"][rule], "milestone": milestone, "rule": rule,
            "subform": SUBFORM, "rule_catalog_version": cv, "facts": rel, "facts_sha256": sha, "notes": notes,
            "statement": {"binders": binders, "assume": [],
                          "claim": {"eq": [{"slash": sid, "on": on}, {"bool": True}]},
                          "scope": {"kind": "unbounded"}}}


class _Producer:
    """A catalog producer object for one rule's slash sub-form; derive's slash part runs it (part marker)."""

    part = "slash"

    def __init__(self, rule: str):
        self.rule = rule

    def produce(self, ctx) -> list:
        root = Path(ctx.root)
        if not has_sidecar(ctx.milestone, root):
            return []
        try:
            rel, sha, vdoc, docs, model = read_inputs(ctx.milestone, root, read=lambda p: ctx.inputs.read(Path(p)))
        except (OSError, KeyError) as e:
            raise SlashError(f"the versioned document of {ctx.milestone} cannot be read: {type(e).__name__}: {e}") \
                from e
        out = []
        for p in pairs_of(vdoc, docs):
            law = law_of(p, self.rule, ctx.milestone, ctx.rule_catalog_version, rel, sha, model)
            out.append((law, {"law_id": law["law_id"], "rule": self.rule, "subform": SUBFORM, "facts": rel,
                              "basis": {k: p[k] for k in ("edge", "op", "selector", "a", "b")}}))
        return out

    def __repr__(self) -> str:
        return f"<holon.rules.slash producer {self.rule}/{SUBFORM}>"


PRODUCERS = {r: _Producer(r) for r in RULES}
