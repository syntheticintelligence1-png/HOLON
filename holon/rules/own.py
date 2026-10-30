"""Rule OWN (BUILD_PLAN I35; whitepaper §5.8; the contract is rules W4, W5 and W8 of the docstring of
tests_m3/test_own.py): one law per (view, writer) pair whose writer writes the view's field in place (OWN-alias), and
one per lost write with an E2 read (OWN-lost-write), over the committed OWN carrier documents gen/<M>/own/*.json
(holon.own).

  alias       L_own_alias_<stem>_<V>_<W>: from any state the type's methods reach from its constructor's value,
              v := V(); one call of W; v's bytes are their snapshot at V's return
  lost_write  L_own_lost_<stem>_<m>_<F>: for every value x of the type and every call of m on x, x.F afterwards is
              the value m assigned to its receiver's F

<stem> is the type's "<pkg>_<T>". The claim is {"eq": [{"own": <own id>, "on": [binders]}, {"bool": true}]}, the own
id "<stem>:alias:<V>:<W>" or "<stem>:lost_write:<m>:<F>", hashed through the ref "own:<id>" (own_ref: the sha256 of
the canonical template, version, subform and basis, recomputed from the carrier document). A view a valid
volatile-view contract declares (holon.contracts, I64's K9: whitepaper §5.8's exception) gives no alias law.

Nothing here names a target: every type, method and field comes from the carrier documents.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

RULE = "OWN"
SUBFORMS = ("alias", "lost_write")
TEMPLATE_VERSION = 1
ROOT = Path(__file__).resolve().parents[2]


class OwnRuleError(ValueError):
    """Two basis elements with one law id: derive exit 3."""


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def volatile_views(root: Path, milestone: str, inputs=None) -> set[tuple[str, int]]:
    """(function id, result index) of every valid volatile-view contract of the milestone (I64, K9); each such contract
    file is listed in inputs (derive's input list) when given."""
    out = set()
    try:
        from .. import contracts as C
    except ImportError:
        return out
    cdir = Path(root) / "laws" / "CONTRACTS"
    for p in sorted(cdir.glob("*.json")) if cdir.is_dir() else []:
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(c, dict) or c.get("kind") != "volatile_view" or c.get("milestone") != milestone:
            continue
        try:
            if C.problems(c, Path(root)):
                continue
        except (AttributeError, TypeError, ValueError, KeyError, OSError):
            continue
        v = c.get("view") or {}
        if isinstance(v.get("function"), str) and isinstance(v.get("result"), int):
            out.add((v["function"], v["result"]))
            if inputs is not None:
                inputs.read(p)
    return out


def elements(doc: dict, volatile: set | None = None) -> list[dict]:
    """Every basis element of one carrier document: {"law_id", "subform", "own_id", "basis"}."""
    stem = doc["stem"]
    volatile = volatile or set()
    out = []
    view_fields: dict[str, set] = {}
    for v in doc["views"]:
        if (doc["methods"][v["method"]]["source"], v["result"]) in volatile:
            continue
        view_fields.setdefault(v["method"], set()).add(v["field"])
    write_fields: dict[str, set] = {}
    for w in doc["writers"]:
        write_fields.setdefault(w["method"], set()).add(w["field"])
    for V in sorted(view_fields):
        for W in sorted(write_fields):
            shared = sorted(view_fields[V] & write_fields[W])
            if not shared:
                continue
            basis = {"kind": "own_alias", "type": doc["type"], "stem": stem, "view": V, "writer": W,
                     "fields": shared, "modelled": doc["modelled"], "abstracted": doc["abstracted"],
                     "constructors": doc["constructors"]}
            out.append({"law_id": f"L_own_alias_{stem}_{V}_{W}", "subform": "alias",
                        "own_id": f"{stem}:alias:{V}:{W}", "basis": basis})
    for x in doc["lost_writes"]:
        if not x.get("law"):
            continue
        basis = {"kind": "own_lost_write", "type": doc["type"], "stem": stem, "method": x["method"],
                 "field": x["field"], "readers": x["readers"], "site": x["site"], "value": x["value"]}
        out.append({"law_id": f"L_own_lost_{stem}_{x['method']}_{x['field']}", "subform": "lost_write",
                    "own_id": f"{stem}:lost_write:{x['method']}:{x['field']}", "basis": basis})
    ids = [e["law_id"] for e in out]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise OwnRuleError(f"two basis elements map to one law id: {dup}")
    return sorted(out, key=lambda e: e["law_id"])


def own_spec(subform: str, basis: dict) -> dict:
    return {"template": f"holon.rules.own/{subform}", "template_version": TEMPLATE_VERSION, "subform": subform,
            "basis": basis}


def own_hash(subform: str, basis: dict) -> str:
    return sha256_bytes(canon(own_spec(subform, basis)).encode("utf-8"))


def own_ref(oid: str, law: dict, root=None) -> str:
    """The ref "own:<ID>" recomputed from the law's carrier document (absent when the document no longer gives it)."""
    root = Path(root or ROOT)
    try:
        doc = json.loads((root / str(law.get("facts"))).read_text(encoding="utf-8"))
        els = elements(doc)
    except (OSError, ValueError, KeyError, TypeError) as e:
        return sha256_bytes(canon({"absent": oid, "error": type(e).__name__}).encode("utf-8"))
    for e in els:
        if e["own_id"] == oid:
            return own_hash(e["subform"], e["basis"])
    return sha256_bytes(canon({"absent": oid}).encode("utf-8"))


def law_ir(e: dict, milestone: str, doc_rel: str, doc_sha: str, catalog_version: str) -> dict:
    """The holon-ir/0.3 law of a basis element (W4, W5, W8)."""
    b = e["basis"]
    if e["subform"] == "alias":
        head = [("p", "Trace"), ("w", f"Call_{b['stem']}")]
        notes = (f"OWN-alias (whitepaper §5.8): after any trace p of {b['type']}'s methods from its constructor's "
                 f"value, the view {b['view']} returns keeps its bytes across one call w of {b['writer']}, which "
                 f"writes {', '.join(b['fields'])} in place")
    else:
        head = [("x", f"Val_{b['stem']}"), ("c", f"Call_{b['stem']}")]
        notes = (f"OWN-lost-write (whitepaper §5.8): after a call c of {b['method']} on a value x of {b['type']}, "
                 f"x.{b['field']} is what {b['method']} assigned (read again by {', '.join(b['readers'])}: E2)")
    binders = [{"q": "forall", "name": n, "type": t} for n, t in head]
    return {"ir_version": "holon-ir/0.3", "law_id": e["law_id"], "milestone": milestone, "rule": RULE,
            "subform": e["subform"], "rule_catalog_version": catalog_version, "facts": doc_rel,
            "facts_sha256": doc_sha, "notes": f"{notes}; own {e['own_id']}",
            "statement": {"binders": binders, "assume": [],
                          "claim": {"eq": [{"own": e["own_id"], "on": [{"var": x["name"]} for x in binders]},
                                           {"bool": True}]},
                          "scope": {"kind": "unbounded"}}}


def entry_of(e: dict, doc_rel: str) -> dict:
    return {"law_id": e["law_id"], "rule": RULE, "subform": e["subform"], "facts": doc_rel, "basis": e["basis"]}


def documents(ctx) -> list[tuple[str, bytes, dict]]:
    """(repo-relative path, raw bytes, document) of every committed carrier document of the derivation's milestone."""
    from .. import own as OW
    root = Path(ctx.root)
    out = []
    for p in OW.committed(ctx.milestone, root):
        raw = ctx.inputs.read(p) if getattr(ctx, "inputs", None) is not None else p.read_bytes()
        out.append((p.resolve().relative_to(root.resolve()).as_posix(), raw, json.loads(raw.decode("utf-8"))))
    return out


class _Producer:
    def __init__(self, subform: str):
        self.subform = subform
        self.__name__ = f"holon.rules.own.{subform}"

    def produce(self, ctx) -> list:
        out = []
        vol = volatile_views(Path(ctx.root), ctx.milestone, getattr(ctx, "inputs", None))
        for rel, raw, doc in documents(ctx):
            sha = sha256_bytes(raw)
            for e in elements(doc, vol):
                if e["subform"] == self.subform:
                    out.append((law_ir(e, ctx.milestone, rel, sha, ctx.rule_catalog_version), entry_of(e, rel)))
        return out


ALIAS = _Producer("alias")
LOST_WRITE = _Producer("lost_write")
PRODUCERS = {"alias": ALIAS, "lost_write": LOST_WRITE}
