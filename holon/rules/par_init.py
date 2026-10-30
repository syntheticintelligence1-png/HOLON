"""Rule PAR's sub-form init_chain: initialization coherence over a contract's versioned documents (BUILD_PLAN I28;
whitepaper §5.1, §11.3 O9; the contract is the docstring of tests_m3/test_versions.py, rules PI1-PI4 and "Catalog and
derive").

  PI1 chains   a commitment family F (a mapping family with a final, whole, keyed, unconditional hash write in a state
               action, and an authenticating guard reach ["==", ["map", ["storage", F], k], H] or its mirror, H a hash
               term, in some action) has root sites, commitment sites in an action with no authenticating guard reach
               of F over input bytes, whose committed value hashes input bytes; and successor sites, commitment sites in
               an action with one (the action's first gives the parent bytes P), whose committed value hashes a memory
               region
  PI2 cells    an mstore at a literal offset o of the region whose value is ["<<", V, s], s a literal; its read from
               input bytes X is [">>", ["word", X, o], s]
  PI3 pairs    (o, o', s): in every successor site's region, after folding additions of the literal 0, the cell at o is
               ["<<", ["+", R, Y], s] (or ["+", Y, R]), R the parent's read of (o, s), and the cell at o' != o is
               ["<<", Y, s]; a cell chained with a literal step gives no pair
  PI4 basis    one element per (contract, F, root site action, pair) of any version's document; its law
               L_pinit_<contract>_<root action>_<F>_<o>_<o'>, rule PAR, subform init_chain, over the versioned document,
               whose claim is the init term {"init": "<model>:chain:<F>:<o>:<o'>", "on": a, "from": s, "env": e}: when a
               is a successful call of the root site's action at s with environment e, the cell (o, s) of the bytes the
               root site hashes equals their cell (o', s)

produce(ctx) is the catalog's producer (PRODUCERS["init_chain"]): it reads the milestone's versions sidecar
(spec/<M>/lib/versions.json; a milestone without one derives nothing), the versioned document it names and every
per-version document that document lists (each checked by its sha256), all through ctx.inputs. init_ref(id, law, root) is
the statement ref init:<id> (holon.gen.refs): the sha256 of the basis element and of the versioned document's
per-version documents, recomputed from the law's versioned document.

Nothing here names a target: every family, action, contract and cell comes from the documents, the model's name from the
sidecar.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

RULE = "PAR"
SUBFORM = "init_chain"
TEMPLATE = "holon.rules.par_init/init_chain"
TEMPLATE_VERSION = 1
SIDECAR = "versions.json"
HASHES = ("keccak256", "sha256")
NOT_STATE = ("view", "pure")
LAW_PREFIX = "L_pinit_"
FACTS = ("holon-facts/0.2", "holon-facts/0.3")   # the documents PI1-PI3 read; any other gives no chain


class InitChainError(ValueError):
    """A versioned document that cannot be read as the sidecar names it (derive exit 1)."""


def canon(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def is_op(t, op=None) -> bool:
    return isinstance(t, list) and bool(t) and isinstance(t[0], str) and (op is None or t[0] == op)


def conjuncts(e) -> list:
    if is_op(e, "&&"):
        out = []
        for x in e[1:]:
            out += conjuncts(x)
        return out
    return [e]


def fold0(t):
    """Additions of the literal 0 removed, bottom up."""
    if not isinstance(t, list):
        return t
    if t and isinstance(t[0], str):
        t = [t[0]] + [fold0(x) for x in t[1:]]
        if t[0] == "+" and len(t) == 3:
            if t[1] == 0:
                return t[2]
            if t[2] == 0:
                return t[1]
        return t
    return [fold0(x) for x in t]


def occurs(t, sub) -> bool:
    if t == sub:
        return True
    return isinstance(t, list) and any(occurs(x, sub) for x in t)


def hash_of(t) -> bool:
    return is_op(t) and t[0] in HASHES


def is_region(x) -> bool:
    return is_op(x, "slice")


def write_key(w: dict):
    path = w.get("path") or []
    if not path:
        return None, True
    if is_op(path[0], "map"):
        return path[0][1], len(path) == 1
    return None, False


def last_whole(a: dict, i: int) -> bool:
    """No later write of the action writes the same family whole at the same key."""
    w = a["writes"][i]
    k, _ = write_key(w)
    for w2 in a["writes"]:
        if w2 is w or w2.get("family") != w.get("family") or w2.get("seq", 0) <= w.get("seq", 0):
            continue
        k2, whole2 = write_key(w2)
        if whole2 and canon(k2) == canon(k):
            return False
    return True


def guard_reaches(a: dict) -> list:
    return [(gi, ri, r) for gi, g in enumerate(a.get("guards") or []) for ri, r in enumerate(g.get("reaches") or [])]


def register_eq(c, F: str) -> list:
    """[(key, H)] of a conjunct ["==", R, H] or ["==", H, R] with R = F's register at a key and H a hash term."""
    out = []
    if is_op(c, "==") and len(c) == 3:
        for R, H in ((c[1], c[2]), (c[2], c[1])):
            if is_op(R, "map") and len(R) == 3 and R[1] == ["storage", F] and hash_of(H):
                out.append((R[2], H))
    return out


def authenticates(a: dict, F: str) -> bool:
    return any(register_eq(c, F) for _gi, _ri, r in guard_reaches(a) for c in conjuncts(r.get("expr")))


def authenticated_inputs(a: dict, F: str) -> list:
    """[(where, key, X)] of the action's authenticating conjuncts of F whose hash term hashes input bytes X (no memory
    region), in reach then conjunct order."""
    out = []
    for gi, ri, r in guard_reaches(a):
        for c in conjuncts(r.get("expr")):
            for k, H in register_eq(c, F):
                if len(H) == 2 and not is_region(H[1]):
                    out.append((f"guards[{gi}].reaches[{ri}]", k, H[1]))
    return out


def families(d: dict) -> dict:
    return {f["name"]: f for f in (d.get("storage") or []) + (d.get("inherited_storage") or [])}


def commitment_sites(d: dict, F: str) -> list:
    out = []
    for a in d.get("actions") or []:
        if a.get("mutability") in NOT_STATE:
            continue
        for i, w in enumerate(a.get("writes") or []):
            k, whole = write_key(w)
            if (w.get("family") == F and w.get("cond") == 1 and whole and k is not None and hash_of(w.get("value"))
                    and last_whole(a, i)):
                out.append((a["name"], i))
    return sorted(out, key=lambda s: (s[0], f"writes[{s[1]}]"))


def region_cells(v) -> dict | None:
    if not (hash_of(v) and len(v) == 2 and is_region(v[1]) and is_op(v[1][1], "mem")):
        return None
    cells = {}
    for w in v[1][1][1:]:
        if is_op(w, "mstore") and len(w) == 3 and isinstance(w[1], int) and not isinstance(w[1], bool):
            cells[w[1]] = w[2]
    return cells


def shifted(v):
    if is_op(v, "<<") and len(v) == 3 and isinstance(v[2], int) and not isinstance(v[2], bool):
        return fold0(v[1]), v[2]
    return None


def site_pairs(cells: dict, parent) -> set:
    pairs = set()
    for o, val in cells.items():
        sv = shifted(val)
        if sv is None or not is_op(sv[0], "+") or len(sv[0]) != 3:
            continue
        V, sh = sv
        read = [">>", ["word", parent, o], sh]
        for x, y in ((V[1], V[2]), (V[2], V[1])):
            if x != read or isinstance(y, int):
                continue
            for o2, val2 in cells.items():
                sv2 = shifted(val2)
                if o2 != o and sv2 is not None and sv2[1] == sh and sv2[0] == y:
                    pairs.add((o, o2, sh))
    return pairs


def chains(d: dict) -> dict:
    """PI1-PI3 over one fact document (holon-facts/0.2 or 0.3; any other document has no family): {"contract", "families": [{"family", "root_sites": [{"action", "at"}],
    "successor_sites": [{"action", "at", "auth", "parent"}], "pairs": [{"cell", "incr", "shift"}]}]}."""
    if not isinstance(d, dict) or d.get("facts_version") not in FACTS:   # e.g. a PAR component with no facts version
        return {"contract": d.get("contract") if isinstance(d, dict) else None, "families": []}
    by = {a["name"]: a for a in d.get("actions") or []}
    fams = []
    fs = families(d)
    for F in sorted(fs):
        if fs[F].get("kind") != "mapping":
            continue
        sites = commitment_sites(d, F)
        if not sites or not any(authenticates(a, F) for a in d.get("actions") or []):
            continue
        roots, succs, per_site = [], [], []
        for name, i in sites:
            a = by[name]
            v = a["writes"][i].get("value")
            auth = authenticated_inputs(a, F)
            if not auth:
                if len(v) == 2 and not is_region(v[1]):
                    roots.append({"action": name, "at": f"writes[{i}]"})
                continue
            cells = region_cells(v)
            if cells is None:
                continue
            where, _k, parent = auth[0]
            succs.append({"action": name, "at": f"writes[{i}]", "auth": where, "parent": parent})
            per_site.append(site_pairs(cells, parent))
        if not roots or not succs:
            continue
        common = set.intersection(*per_site) if per_site else set()
        fams.append({"family": F, "root_sites": sorted(roots, key=lambda r: (r["action"], r["at"])),
                     "successor_sites": sorted(succs, key=lambda r: (r["action"], r["at"])),
                     "pairs": [{"cell": o, "incr": o2, "shift": sh} for o, o2, sh in sorted(common)]})
    return {"contract": d.get("contract"), "families": fams}


def vkey(v: str):
    return (int(v[1:]) if v[1:].isdigit() else 10 ** 9, v)


def law_id(contract: str, root_action: str, family: str, cell: int, incr: int) -> str:
    return f"{LAW_PREFIX}{contract}_{root_action}_{family}_{cell}_{incr}"


def init_id(model: str, family: str, cell: int, incr: int) -> str:
    return f"{model}:chain:{family}:{cell}:{incr}"


def basis(per: dict, model: str) -> list:
    """PI4: one element per (contract, family, root action, pair) found in any version's chains, sorted by law id."""
    found = {}
    for v, ch in sorted(per.items()):
        for f in ch["families"]:
            for r in f["root_sites"]:
                for pr in f["pairs"]:
                    k = (ch["contract"], f["family"], r["action"], pr["cell"], pr["incr"], pr["shift"])
                    found.setdefault(k, []).append(v)
    out = []
    for (contract, F, ra, o, o2, sh), vs in found.items():
        out.append({"family": F, "root_action": ra, "cell": o, "incr": o2, "shift": sh,
                    "versions": sorted(vs, key=vkey), "law_id": law_id(contract, ra, F, o, o2),
                    "init_id": init_id(model, F, o, o2)})
    return sorted(out, key=lambda b: b["law_id"])


def hash_binders(docs: list) -> list:
    from .sort import hash_functions
    used = set()
    for d in docs:
        used |= set(hash_functions(d))
    return [h for h in HASHES if h in used] or ["keccak256"]


# ------------------------------------------------------------------------------------------------ reading the documents
def sidecar_path(milestone: str, root: Path) -> Path:
    return Path(root) / "spec" / milestone / "lib" / SIDECAR


class Versioned:
    """The milestone's versions sidecar, its versioned document and the per-version documents it lists."""

    def __init__(self, milestone: str, root: Path, read=None):
        root = Path(root)
        self.root = root
        read = read or (lambda p: Path(p).read_bytes())
        sp = sidecar_path(milestone, root)
        self.side = json.loads(read(sp).decode("utf-8"))
        self.model = self.side["model"]
        self.rel = self.side["outputs"]["versions"]
        data = read(root / self.rel)
        self.sha = hashlib.sha256(data).hexdigest()
        self.doc = json.loads(data.decode("utf-8"))
        self.docs = {}
        self.shas = {}
        for v, x in sorted((self.doc.get("documents") or {}).items(), key=lambda kv: vkey(kv[0])):
            b = read(root / x["path"])
            sha = hashlib.sha256(b).hexdigest()
            if sha != x["sha256"]:
                raise InitChainError(f"{x['path']} is not the document {self.rel} records")
            self.docs[v] = json.loads(b.decode("utf-8"))
            self.shas[v] = sha

    def basis(self) -> list:
        return basis({v: chains(d) for v, d in self.docs.items()}, self.model)


def init_spec(element: dict, shas: dict) -> dict:
    return {"template": TEMPLATE, "template_version": TEMPLATE_VERSION, "basis": element,
            "documents": dict(sorted(shas.items(), key=lambda kv: vkey(kv[0])))}


def init_ref(iid: str, law: dict, root=None) -> str:
    """The ref init:<ID>: the sha256 (hex) of the canonical {template, template_version, basis, documents} of the basis
    element ID, recomputed from the law's versioned document and the per-version documents it lists."""
    from pathlib import Path as _P
    root = _P(root) if root is not None else _P(__file__).resolve().parents[2]
    try:
        vd = Versioned(str(law.get("milestone")), root)
        for b in vd.basis():
            if b["init_id"] == iid:
                return hashlib.sha256(canon(init_spec(b, vd.shas)).encode("utf-8")).hexdigest()
    except (OSError, ValueError, KeyError, TypeError) as e:
        return hashlib.sha256(canon({"absent": iid, "error": type(e).__name__}).encode("utf-8")).hexdigest()
    return hashlib.sha256(canon({"absent": iid}).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------ the producer
def law_of(b: dict, milestone: str, cv: str, rel: str, sha: str, hashes: list) -> dict:
    binders = [{"q": "forall", "name": "s", "type": "Reach"}, {"q": "forall", "name": "a", "type": "Act"},
               {"q": "forall", "name": "e", "type": "Env"}]
    binders += [{"q": "forall", "name": h, "type": "Fn<Bytes,Word>"} for h in hashes]
    notes = (f"initialization coherence (whitepaper §5.1): when a is a successful call of {b['root_action']} (the root "
             f"site of the chain {b['family']}) at the reachable state s with environment e, the header it commits has "
             f"cell {b['cell']} (shift {b['shift']}) equal to its cell {b['incr']}: the running sum the successor sites "
             f"carry starts at the first header's own increment; init {b['init_id']}")
    return {"ir_version": "holon-ir/0.3", "law_id": b["law_id"], "milestone": milestone, "rule": RULE,
            "subform": SUBFORM, "rule_catalog_version": cv, "facts": rel, "facts_sha256": sha, "notes": notes,
            "statement": {"binders": binders, "assume": [],
                          "claim": {"eq": [{"init": b["init_id"], "on": {"var": "a"}, "from": {"var": "s"},
                                            "env": {"var": "e"}}, {"bool": True}]},
                          "scope": {"kind": "unbounded"}}}


def produce(ctx) -> list:
    """[(law, DERIVATION entry)] of the milestone's versioned document (none without a versions sidecar)."""
    root = Path(ctx.root)
    if not sidecar_path(ctx.milestone, root).is_file():
        return []
    try:
        vd = Versioned(ctx.milestone, root, read=lambda p: ctx.inputs.read(Path(p)))
    except (OSError, KeyError) as e:
        raise InitChainError(f"the versioned document of {ctx.milestone} cannot be read: {type(e).__name__}: {e}") from e
    hashes = hash_binders(list(vd.docs.values()))
    out = []
    for b in vd.basis():
        law = law_of(b, ctx.milestone, ctx.rule_catalog_version, vd.rel, vd.sha, hashes)
        out.append((law, {"law_id": b["law_id"], "rule": RULE, "subform": SUBFORM, "facts": vd.rel, "basis": b}))
    return out


PRODUCERS = {SUBFORM: produce}
