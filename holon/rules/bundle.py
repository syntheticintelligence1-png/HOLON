"""The laws of a bundle of linked contracts (I86 = I36b; the contract is the docstring of tests_m3/test_bundle_laws.py,
rules DC1-DC2, PY1-PY4, CS1-CS5, K1-K8, PP1-PP6, N1 and ST1): the producers of SORT payer and conservation, DISCH
keyed_blocking, keyed_external and keyed_external_none, and PAR push, registered under holon-rules/1.11
(holon.rules.CATALOGS) and run by derive's bundle part (holon.rules._bundle_part), never by its typed or PAR part.

basis(root, milestone) reads the milestone's bundle-laws sidecar (spec/<M>/lib/bundle_laws.json; none: no law), the
bundle declaration it names (gen/<M>/bundle/bundle.json: its members and their documents), every member document, and
the deferred pushing candidates of spec/<M>/lib/par_lossy.json; it returns the sites of the six sub-forms with their law
ids. A law's claim names its site by the bundle id "<member>:<subform>:<site>" and is hashed through the ref
"bundle:<id>" (bundle_ref: the site recomputed from the same inputs).

Nothing here names a target: every member, action, family, parameter, span and term comes from the sidecar, the
declaration and the documents.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..sorts import conservation as CV

RULE_SUBFORMS = {"payer": "SORT", "conservation": "SORT", "keyed_blocking": "DISCH", "keyed_external": "DISCH",
                 "keyed_external_none": "DISCH", "push": "PAR"}
PREFIX = {"payer": "L_sort_payer_", "conservation": "L_sort_cons_", "keyed_blocking": "L_disch_kblk_",
          "keyed_external": "L_disch_kext_", "keyed_external_none": "L_disch_knoext_", "push": "L_par_push_"}
SIDECAR = "bundle_laws.json"
TEMPLATE_VERSION = 1
INIT_MODIFIERS = ("initializer", "reinitializer")
STATIC_WORDS = ("address", "uint256", "bytes32")
NOTES = {
    "payer": "§7.5 payer: in every reachable state where the action succeeds, every principal argument of its price "
             "call is the payer, the step's caller",
    "conservation": "§7.5 conservation (the inflow half): in every reachable state where the payable action succeeds, "
                    "its msg.value is accounted for by its class's claim",
    "keyed_blocking": "Thm 6.10 at a key: while the blocked condition holds at k, every successful step of the class "
                      "keeps it",
    "keyed_external": "external dependence at a key: a reachable state where the blocked condition holds at k and a "
                      "successful step of the class after which it does not",
    "keyed_external_none": "the forall-negation of keyed_external (an existential law is never REFUTED)",
    "push": "Lemma 6.12 pushing under CF (Cor 6.16): equal leaves and keccak256 collision-free on the two preimages give "
            "equal index fields of the preimages",
}


class BundleLawError(ValueError):
    """A basis element that cannot be derived (named): derive exit 3."""


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def x8(o) -> str:
    return hashlib.sha256(canon(o).encode("utf-8")).hexdigest()[:8]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


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


def slug(span: str) -> str:
    """The DISCH slug of a span (holon.analysis.closure.slug's rule)."""
    file_part, _, line = str(span).rpartition(":")
    stem = file_part.split("/")[-1].split(".", 1)[0].lower()
    return "_".join([re.sub("[^a-z0-9]+", "_", stem), line.replace("-", "_")])


# ------------------------------------------------------------------------------------------------ inputs
class Inputs:
    """The files the basis reads, with their sha256 (DERIVATION lists them)."""

    def __init__(self, root: Path, reader=None):
        self.root = Path(root)
        self.reader = reader
        self.files: dict = {}

    def read(self, rel: str) -> bytes:
        b = (self.root / rel).read_bytes()
        self.files[rel] = sha256_bytes(b)
        if self.reader is not None:
            self.reader.read(self.root / rel)
        return b

    def json(self, rel: str):
        return json.loads(self.read(rel).decode("utf-8"))


def sidecar_rel(milestone: str) -> str:
    return f"spec/{milestone}/lib/{SIDECAR}"


def has_sidecar(root: Path, milestone: str) -> bool:
    return (Path(root) / sidecar_rel(milestone)).is_file()


def members(inp: Inputs, side: dict) -> list:
    decl = inp.json(_declaration(side))
    out = []
    for m in decl["members"]:
        rel = m["document"]["path"]
        doc = inp.json(rel)
        out.append({"name": m["name"], "contract": m["contract"], "document": rel, "doc": doc,
                    "adopted": m.get("sidecar") is None, "sha256": inp.files[rel]})
    return out


def _declaration(side: dict) -> str:
    """The bundle declaration: beside the corpus the sidecar's witnesses name (I69's outputs share a directory)."""
    return str(Path(side["witnesses"]["corpus"]).parent / "bundle.json")


# ------------------------------------------------------------------------------------------------ DC: classes
def class_of(action: dict) -> str | None:
    """DC1-DC2: the principal class of an action (its principal modifier, else anyone; None for an initializer)."""
    if any(m in INIT_MODIFIERS for m in action.get("modifiers") or []):
        return None
    p = action.get("principal")
    return p.get("modifier") if isinstance(p, dict) and p.get("modifier") else "anyone"


def classes(doc: dict) -> dict:
    out: dict = {}
    for a in doc.get("actions") or []:
        if a.get("mutability") in ("view", "pure"):
            continue
        c = class_of(a)
        if c is not None:
            out.setdefault(c, []).append(a["name"])
    return {c: sorted(v) for c, v in sorted(out.items())}


# ------------------------------------------------------------------------------------------------ K: keyed
def normal(t):
    """K2: a member read of a struct value updated at another member reads the value before the update."""
    if not isinstance(t, list):
        return t
    if _head(t) is None:
        return [normal(x) for x in t]
    t = [t[0]] + [normal(x) for x in t[1:]]
    while _head(t) == "member" and _head(t[1]) == "update" and len(t[1]) == 4 and t[1][2] != t[2]:
        t = ["member", t[1][1], t[2]]
    return t


def _subst(t, old, new):
    if t == old:
        return new
    if isinstance(t, list):
        return [_subst(x, old, new) for x in t]
    return t


def keyed_site(members_: list, ob: dict) -> dict:
    m = next((x for x in members_ if x["name"] == ob["member"]), None)
    if m is None:
        raise BundleLawError(f"keyed obligation {ob['obligation']}: no member {ob['member']}")
    doc = m["doc"]
    an, span, k = ob["check"].split("#")
    act = next((a for a in doc.get("actions") or [] if a["name"] == an), None)
    if act is None:
        raise BundleLawError(f"{ob['check']}: no action {an}")
    gs = [g for g in act.get("guards") or [] if g.get("src") == span]
    if int(k) >= len(gs):
        raise BundleLawError(f"{ob['check']}: no such guard")
    conj = normal(gs[int(k)]["expr"])
    params = {p["name"] for p in act.get("params") or []}
    keys = []
    for x in _terms(conj):
        if _head(x) == "map" and _reads(x[2], lambda z: (_head(z) == "param" and z[1] in params) or z == ["caller"]):
            if x[2] not in keys:
                keys.append(x[2])
    if len(keys) != 1:
        raise BundleLawError(f"{ob['check']}: {len(keys)} input-keyed mapping reads (K1 needs exactly one)")
    neg = conj[1] if _head(conj) == "!" else ["!", conj]
    blocked = normal(_subst(neg, keys[0], ["var", "k"]))
    fams = sorted({x[1] for x in _terms(blocked) if _head(x) == "storage"})
    cls = classes(doc)
    writers: dict = {}
    for b in doc.get("actions") or []:
        if b["name"] == act["name"] or class_of(b) is None:
            continue
        if any(w["family"] in fams for w in b.get("writes") or []):
            writers.setdefault(class_of(b), []).append(b["name"])
    status = {c: ("discharges" if writers.get(c) else "blocked") for c in cls}
    tag = f"{slug(span)}_{x8(blocked)}"
    laws = {"keyed_blocking": [f"L_disch_kblk_{tag}_{c}" for c in cls if status[c] == "blocked"],
            "keyed_external": [f"L_disch_kext_{tag}_{c}" for c in cls if status[c] == "discharges"],
            "keyed_external_none": [f"L_disch_knoext_{tag}_{c}" for c in cls if status[c] == "discharges"]}
    return {"obligation": ob["obligation"], "member": m["name"], "contract": m["contract"], "action": act["name"],
            "check": ob["check"], "conjunct": conj, "key": keys[0], "blocked": blocked, "families": fams,
            "classes": cls, "writers": {c: sorted(v) for c, v in sorted(writers.items())}, "status": status,
            "tag": tag, "laws": laws}


# ------------------------------------------------------------------------------------------------ PP: push
def push_sites(members_: list) -> list:
    out = []
    for m in members_:
        for a in m["doc"].get("actions") or []:
            ptypes = {p["name"]: p["type"] for p in a.get("params") or []}
            for lp in a.get("loops") or []:
                span = next((c["value"][1] for c in lp.get("carried") or [] if _head(c.get("value")) == "carried"),
                            None)
                for c in lp.get("carried") or []:
                    e = c.get("entry")
                    if _head(e) != "keccak256" or _head(e[1]) != "abi.encodeWithSignature":
                        continue
                    nxt = next((n["value"] for n in lp.get("next") or [] if n.get("name") == c["name"]), None)
                    idx = None
                    for x in _terms(nxt):
                        if _head(x) == "&" and x[2] == 1 and _head(x[1]) == ">>" and _head(x[1][1]) == "param" \
                                and x[1][2] == ["iter", span]:
                            idx = x[1][1]
                    if idx is None:
                        continue
                    args = e[1][2:]
                    pos = args.index(idx)
                    static = all(ptypes.get(x[1]) in STATIC_WORDS for x in args[:pos] if _head(x) == "param")
                    check = next((g["src"] for g in a.get("guards") or []
                                  if any(_head(x) == "exit" and x[1] == span for x in _terms(g.get("expr")))), None)
                    if check is None:
                        raise BundleLawError(f"{a['name']}: no guard reads the exit of the loop {span}")
                    out.append({"law_id": f"L_par_push_{m['contract']}_{a['name']}_{_line(check)}",
                                "member": m["name"], "contract": m["contract"], "action": a["name"], "loop": span,
                                "bound": lp.get("bound"), "leaf": e, "index": idx, "index_position": pos,
                                "index_offset": 4 + 32 * pos if static else None, "merkle_check": check,
                                "signature": bytes.fromhex(e[1][1][1]).decode("ascii"),
                                "arguments": [[x[1], ptypes.get(x[1])] for x in args]})
    return sorted(out, key=lambda s: s["law_id"])


# ------------------------------------------------------------------------------------------------ the basis
def basis(root: Path, milestone: str, reader=None) -> dict | None:
    """The six sub-forms' sites and law ids over the milestone's bundle (None without a bundle-laws sidecar)."""
    root = Path(root)
    if not has_sidecar(root, milestone):
        return None
    inp = Inputs(root, reader)
    side = inp.json(sidecar_rel(milestone))
    mem = members(inp, side)
    lossy = inp.json(f"spec/{milestone}/lib/par_lossy.json")
    deferred = {d["id"]: d for d in lossy.get("deferred") or []}
    for d in side["push"]["deferred"]:
        if d not in deferred:
            raise BundleLawError(f"push candidate {d} is not deferred in spec/{milestone}/lib/par_lossy.json")
    pay = CV.payer_sites(mem)
    cons = CV.conservation_sites(mem)
    keyed = [keyed_site(mem, ob) for ob in side["keyed"]["obligations"]]
    push = push_sites(mem)
    ids = {"payer": [s["law_id"] for s in pay], "conservation": [s["law_id"] for s in cons],
           "keyed_blocking": sorted(x for k in keyed for x in k["laws"]["keyed_blocking"]),
           "keyed_external": sorted(x for k in keyed for x in k["laws"]["keyed_external"]),
           "keyed_external_none": sorted(x for k in keyed for x in k["laws"]["keyed_external_none"]),
           "push": [s["law_id"] for s in push]}
    return {"sidecar": side, "members": mem, "payer": pay, "conservation": cons, "keyed": keyed, "push": push,
            "law_ids": ids, "inputs": inp.files}


def sites(b: dict) -> dict:
    """{law_id: (subform, member name, site entry, class or None)} over the basis."""
    out = {}
    for s in b["payer"]:
        out[s["law_id"]] = ("payer", s["member"], s, None)
    for s in b["conservation"]:
        out[s["law_id"]] = ("conservation", s["member"], s, None)
    for k in b["keyed"]:
        for sub in ("keyed_blocking", "keyed_external", "keyed_external_none"):
            for lid in k["laws"][sub]:
                out[lid] = (sub, k["member"], k, _class_of_id(lid, k))
    for s in b["push"]:
        out[s["law_id"]] = ("push", s["member"], s, None)
    return out


def _class_of_id(lid: str, k: dict) -> str:
    for c in k["classes"]:
        if lid.endswith("_" + c):
            return c
    raise BundleLawError(f"{lid}: no class")


def bundle_id(sub: str, member: str, site: dict, cls: str | None) -> str:
    if sub == "payer":
        return f"{member}:payer:{site['action']}:{_line(site['check_src'])}"
    if sub == "conservation":
        return f"{member}:conservation:{site['action']}"
    if sub == "push":
        return f"{member}:push:{site['action']}:{_line(site['merkle_check'])}"
    return f"{member}:{sub}:{site['tag']}:{cls}"


def site_entry(sub: str, site: dict) -> dict:
    """The part of a site its law's meaning rests on (the ref's content; no derived law id lists)."""
    if sub in ("keyed_blocking", "keyed_external", "keyed_external_none"):
        return {k: site[k] for k in ("obligation", "action", "check", "conjunct", "key", "blocked", "families",
                                     "classes", "writers", "status", "tag")}
    return dict(site)


# ------------------------------------------------------------------------------------------------ law IR (ST1)
def _binders(sub: str, q: str) -> list:
    if sub == "push":
        return [{"q": "forall", "name": "keccak256", "type": "Fn<Bytes,Word>"},
                {"q": "forall", "name": "x1", "type": "Args"}, {"q": "forall", "name": "x2", "type": "Args"}]
    if sub.startswith("keyed"):
        return [{"q": q, "name": "s", "type": "Reach"}, {"q": q, "name": "k", "type": "Word"},
                {"q": q, "name": "a", "type": "Act"}, {"q": q, "name": "keccak256", "type": "Fn<Bytes,Word>"}]
    return [{"q": "forall", "name": "s", "type": "Reach"}, {"q": "forall", "name": "x", "type": "Args"},
            {"q": "forall", "name": "e", "type": "Env"}, {"q": "forall", "name": "keccak256", "type": "Fn<Bytes,Word>"}]


def law_ir(lid: str, sub: str, member: dict, site: dict, cls: str | None, milestone: str, cv: str) -> dict:
    bid = bundle_id(sub, member["name"], site, cls)
    q = "exists" if sub == "keyed_external" else "forall"
    if sub == "push":
        # PP4: collision-freedom of the hash on the two preimages (a finite set, L13) and equal leaves
        claim_term = {"bundle": bid, "on": [{"var": "x1"}, {"var": "x2"}]}
        enc = [{"bundle": bid, "premise": "enc", "on": [{"var": x}]} for x in ("x1", "x2")]
        leaf = [{"bundle": bid, "premise": "leaf", "on": [{"var": x}]} for x in ("x1", "x2")]
        assume = [{"cf": {"fn": "keccak256", "set": enc}}, {"eq": leaf}]
    elif sub.startswith("keyed"):
        claim_term = {"bundle": bid, "on": {"var": "a"}, "from": {"var": "s"}, "at": {"var": "k"}}
        assume = []
    else:
        claim_term = {"bundle": bid, "on": {"var": "x"}, "from": {"var": "s"}, "env": {"var": "e"}}
        assume = [{"eq": [{"bundle": bid, "premise": "ok", "on": {"var": "x"}, "from": {"var": "s"},
                           "env": {"var": "e"}}, {"bool": True}]}]
    return {"ir_version": "holon-ir/0.3", "law_id": lid, "milestone": milestone, "rule": RULE_SUBFORMS[sub],
            "subform": sub, "rule_catalog_version": cv, "facts": member["document"],
            "facts_sha256": member["sha256"], "notes": f"{NOTES[sub]}; {bid}",
            "statement": {"binders": _binders(sub, q), "assume": assume,
                          "claim": {"eq": [claim_term, {"bool": True}]}, "scope": {"kind": "unbounded"}}}


# ------------------------------------------------------------------------------------------------ producers
class _Producer:
    """One sub-form's producer. derive's bundle part calls it (holon.rules._bundle_part); the typed part skips it."""
    bundle = True

    def __init__(self, subform: str):
        self.subform = subform
        self.__name__ = f"holon.rules.bundle.{subform}"

    def produce(self, ctx) -> list:
        cache = getattr(ctx, "_bundle_basis", None)
        if cache is None:
            cache = ctx._bundle_basis = basis(ctx.root, ctx.milestone, getattr(ctx, "inputs", None))
        if cache is None:
            return []
        by_name = {m["name"]: m for m in cache["members"]}
        out = []
        for lid, (sub, mname, site, cls) in sorted(sites(cache).items()):
            if sub != self.subform:
                continue
            m = by_name[mname]
            ir = law_ir(lid, sub, m, site, cls, ctx.milestone, ctx.rule_catalog_version)
            entry = {"law_id": lid, "rule": RULE_SUBFORMS[sub], "subform": sub, "facts": m["document"],
                     "basis": site_entry(sub, site), "member": mname}
            if cls is not None:
                entry["class"] = cls
            out.append((ir, entry))
        return out

    __call__ = produce


PRODUCERS = {sub: _Producer(sub) for sub in RULE_SUBFORMS}


def bundle_ref(bid: str, law: dict, root) -> str:
    """bundle:<ID>: sha256 (hex) of the canonical {template, template_version, subform, member, site}, the site
    recomputed from the law's milestone's sidecar, declaration and documents."""
    b = basis(Path(root), law["milestone"])
    if b is None:
        raise BundleLawError(f"bundle:{bid}: no bundle-laws sidecar for {law['milestone']}")
    for lid, (sub, mname, site, cls) in sites(b).items():
        if bundle_id(sub, mname, site, cls) == bid:
            doc = {"template": f"holon.rules.bundle/{sub}", "template_version": TEMPLATE_VERSION, "subform": sub,
                   "member": mname, "site": site_entry(sub, site)}
            return hashlib.sha256(canon(doc).encode("utf-8")).hexdigest()
    raise BundleLawError(f"bundle:{bid}: no such site")
