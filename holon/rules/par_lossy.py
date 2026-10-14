"""PAR-lossy and injective pushing over the frozen evidence set (whitepaper §10.3 step 6, Prop 6.11, Lemma 6.12, §12
L3; what they rest on: Def 4.4 and 4.5, Cor 6.16, §10.2, Thm 6.4's invertible-fragment hypothesis, L21; BUILD_PLAN
I25). The contract is the docstring of tests_m3/test_par_lossy.py: rules L0-L9.

  python -m holon lossy --milestone M [--root DIR] [--out DIR] [--review PATH] [--records DIR] [--codec PATH ...]
                        [--gen-dir DIR] [--check]

What it computes, per linked codec component (I24's holon.diagram.linked; its diagram and its evidence atoms):

  L1 the fragment (Def 4.4): an encoder is invertible at a version when its layout holds every byte of every field of
     its source record (the version field aside: the version premise fixes it), else lossy with the fields it drops; a
     decoder is lossy when it reads past offset 0 or accepts a longer string (a projection); a loader is unmodelled
     (its domain only is modelled); a HASH edge is invertible only under a CF premise (Cor 6.16): class "cf".
  L2 the evidenced lossy elements (the evidence set's atoms over the component, E1-E5; E6 counted under "weak"):
     round trips (E1 inverse), observed pairs (E1 common-decoder groups, observed through the family of decoders),
     constant and partial reads (E2 at a common version without an inverse atom) and anything else (E3-E5).
  L3 coverage, direct only: a round trip by its I24 round-trip law, an observed pair by a pushed law.
  L4 the push verdict of each cross-component law (Lemma 6.12 by position): the two layouts at the version, the
     pinned cells replaced by their constants; the family's decoders that reject the images' length under the
     version's tag are blind; the law is pushed iff the layouts have one length and every position no seeing decoder
     reads holds one constant on both sides. Otherwise the first failing position is the collision (Prop 6.11).
  L5 a collision certificate in Bend for each law that is not pushed: at the ones fill under the law's premises,
     every observation agrees and the images differ (cross), or, when the premises tie the collision, two inputs of
     one side whose images differ while every observation agrees (same_side).
  L6 HASH candidates: pairs of the component's functions whose selected sink hashes the same carrier.
  L7 the core laws core_inj_push, core_inj_pull and core_cf_succ (statements frozen in the milestone's
     spec/<M>/lib/par_lossy.json "core"), proved by per-class proof generators.
  L8 the per-component document <out>/<role>.json and the metric (holon metrics: evidenced_pair_coverage).
  L9 the evidence review: every replay disagreement of a refinement record that does not resolve to an endpoint of a
     covered element is one open entry, adjudicated by A4 in I45.

I24's PAR basis is recomputed in memory with holon-rules/1.1's PAR producers, exactly as holon derive computes it: no
law file and no record is read. Nothing here names a target; every name in an output comes from the component's
documents, its diagram, its atoms and I24's law ids. The checker's word is final: the Bend files written here are
accepted only when Bend checks them (the tests and the report run Bend; this module never decides a status).

Model imports (rule L5). A certificate imports the component model holon run wrote: gen/<M>/model/<role>.bend for a
milestone M<k> (always written relative to the committed location gen/<M>/par_lossy, so a --out elsewhere writes the
very documents the committed tree holds, which --check compares), <gen-dir>/model/<role>.bend relative to <out> for a
test milestone T<k>. The model must be what holon.gen.linked generates from the codec document now (else exit 2).

Exit 0 written; 1 (--check) a file differs from a fresh build, nothing written; 2 refused, nothing written (an input
missing, malformed or stale, named); 3 a construct the rules refuse, named, nothing written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

LOSSY_VERSION = "holon-lossy/0.1"
DOCUMENT = "par_lossy"
KINDS = ("round_trip", "observed", "constant_read", "partial_read", "other")
REASONS = ("no_law", "non_injective", "no_rule")
COLLISIONS = ("length", "constants_differ", "unobserved_field", "unknown_cell")
OUT_DIR = "par_lossy"
REVIEW_NAME = "evidence_review.jsonl"
SIDECAR_NAME = "par_lossy.json"
ROOT = Path(__file__).resolve().parents[2]


def relative_to(milestone: str) -> str:
    """Rule L8's sentence: completeness is relative to the frozen evidence set (Prop 6.11)."""
    return (f"the frozen evidence set gen/{milestone}/evidence.json: the lossy fragment has no topological basis "
            "(whitepaper Prop 6.11), so completeness is relative to the evidenced pairs; an unevidenced pair is not "
            "counted")


class Refused(ValueError):
    """An input missing, malformed or stale (exit 2, nothing written)."""


class Construct(ValueError):
    """A construct the rules refuse (exit 3, nothing written)."""


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def target_milestone(milestone: str) -> bool:
    return re.fullmatch(r"M\d+", milestone or "") is not None


# ====================================================================== the components (rule L0)
class Component:
    """One linked codec component: its document, diagram, atoms and I24's PAR basis over it (recomputed in memory)."""

    def __init__(self, path: Path, rel: str, raw: bytes, diagram: dict, atoms: list, inputs: list, evidence_sha256):
        from . import CATALOGS, PAR_CATALOG_VERSION
        from . import par as P
        self.path, self.rel, self.raw = path, rel, raw
        self.sha = sha256_bytes(raw)
        self.doc = json.loads(raw.decode("utf-8"))
        self.diagram = diagram
        self.atoms = atoms
        self.inputs = inputs
        self.evidence_sha256 = evidence_sha256
        pd = P.ParDoc(rel=rel, facts=self.doc, diagram=diagram, atoms=atoms, oracle_binders=[], lib_builtins={})
        self.pd = pd
        try:
            acc = P.derive_document(pd, CATALOGS[PAR_CATALOG_VERSION]["PAR"])
        except P.ParError as e:
            raise Construct(f"{rel}: {e}") from e
        self.basis = acc.basis
        self.laws = {lid: x["statement"] for lid, x in acc.laws.items()}

    @property
    def role(self) -> str:
        return self.doc.get("role") or self.doc["component"]

    @property
    def model(self) -> str:
        return self.diagram["model"]

    @property
    def fns(self) -> dict:
        return self.doc["functions"]

    @property
    def tag(self) -> int:
        return self.doc["tag_index"]

    def edge(self, eid: str) -> dict:
        return next(e for e in self.diagram["edges"] if e["id"] == eid)

    def fixed_field(self, carrier: str, v) -> str | None:
        """The field of a record carrier that rule P0's version premise fixes at version v (I24's
        holon.rules.par.version_premise), or None."""
        from . import par as P
        try:
            vp = P.version_premise(self.pd, "h", carrier, v)
        except P.ParError as e:
            raise Construct(f"{self.rel}: {e}") from e
        return vp[0]["eq"][0]["field"] if vp else None

    def fn_of(self, eid: str) -> dict:
        return self.fns[self.edge(eid)["model_fn"]]


def _file_input(root: Path, rel: str) -> dict:
    return {"path": rel, "sha256": sha256_bytes((Path(root) / rel).read_bytes())}


def components(milestone: str, root: Path, codecs: list[str] | None = None) -> tuple[list[Component], dict]:
    """The linked codec components of a milestone and its evidence set. M<k> without --codec: the committed linked
    codec layer (gen/<M>/codec, gen/<M>/diagram, gen/<M>/evidence.json), each byte for byte what holon codecs, diagram
    and evidence write now (holon derive's check). Otherwise the --codec documents, their diagrams and the evidence set
    built in memory, as derive builds them."""
    from . import DeriveError, Inputs, _committed_par_inputs, _documents, _given_par_inputs
    from . import Refused as DRefused
    from ..diagram import linked as L
    root = Path(root).resolve()
    inputs = Inputs(root)
    try:
        if codecs:
            try:
                cpaths = _documents(milestone, root, codecs)
            except ValueError as e:
                raise Refused(str(e)) from e
            for p in cpaths:
                if not p.is_file():
                    raise Refused(f"--codec {inputs.rel(p)}: no such file")
            _, comps, ev, _ = _given_par_inputs(milestone, root, inputs, [], cpaths, None)
            committed = False
        else:
            if not target_milestone(milestone):
                raise Refused(f"{milestone}: a test milestone names its linked codec documents with --codec")
            comps, ev, _ = _committed_par_inputs(milestone, root, inputs)
            committed = True
    except DRefused as e:
        raise Refused(str(e)) from e
    except DeriveError as e:
        raise Construct(str(e)) from e
    except (OSError, ValueError, KeyError, TypeError) as e:
        if isinstance(e, (Refused, Construct)):
            raise
        raise Refused(f"an input cannot be read: {type(e).__name__}: {e}") from e
    out = []
    for p, dg in comps:
        raw = Path(p).read_bytes()
        if not L.is_linked(json.loads(raw.decode("utf-8"))):
            continue
        rel = inputs.rel(p)
        if committed:
            ins = sorted([_file_input(root, rel), _file_input(root, f"gen/{milestone}/diagram/{dg['model']}.json"),
                          _file_input(root, f"gen/{milestone}/evidence.json")], key=lambda i: i["path"])
        else:
            ins = [_file_input(root, rel)]
        out.append(Component(Path(p), rel, raw, dg, [a for a in ev["atoms"] if a["model"] == dg["model"]], ins,
                             ev.get("evidence_sha256")))
    if not out:
        raise Refused(f"{milestone}: no linked codec component")
    roles = [c.role for c in out]
    if len(set(roles)) != len(roles):
        raise Construct(f"two components share a role: {sorted(roles)}")
    return sorted(out, key=lambda c: c.role), ev


# ====================================================================== conditions and layouts
def layout_at(f: dict, v) -> list[list] | None:
    from ..diagram.linked import layout_at as _lay
    return _lay(f, v)


def decoder_ok(f: dict, length: int, tagv: int, tag: int) -> bool:
    """Whether some ok path of a decoder (or predicate) holds on a byte string of this length and tag byte (I24's
    decoder conditions, as rule X9 evaluates them)."""
    from ..diagram.linked import eval_go
    env = {("len",): length, ("index", tag): tagv}
    for cond in f["ok"]:
        vals = [eval_go(a, env, f["param"]) for a in cond]
        if None in vals:
            raise Construct(f"{f['source']}: an ok condition mentions more than the length and the tag byte")
        if all(vals):
            return True
    return False


# ====================================================================== L1 the fragment (Def 4.4)
def fragment(c: Component) -> list[dict]:
    out = []
    for e in sorted(c.diagram["edges"], key=lambda e: e["id"]):
        if e["kind"] == "HASH":
            out.append({"edge": e["id"], "version": None, "class": "cf"})
            continue
        if e["kind"] != "CODEC":
            raise Construct(f"{e['id']}: no fragment rule for an edge of kind {e['kind']}")
        f = c.fns[e["model_fn"]]
        if f["kind"] == "encoder":
            rec = c.doc["carriers"][f["from"]]
            for v in (f["versions"] if f["versions"] is not None else [None]):
                lay = layout_at(f, v)
                if lay is None:
                    raise Construct(f"{e['id']}: no layout at version {v}")
                fixed = c.fixed_field(f["from"], v)
                dropped = []
                for fld in rec["fields"]:
                    if fld["name"] == fixed:
                        continue   # P0: the version premise fixes the field on R_v
                    if any(["field", fld["name"], k] not in lay for k in range(fld["width"])):
                        dropped.append(fld["name"])
                out.append({"edge": e["id"], "version": v, "class": "lossy" if dropped else "invertible",
                            "dropped": dropped})
        elif f["kind"] == "decoder":
            o, w = f["read"]["offset"], f["read"]["width"]
            longer = any(decoder_ok(f, o + w + 1, t, c.tag) for t in range(256))
            out.append({"edge": e["id"], "version": None, "class": "lossy" if (o > 0 or longer) else "invertible",
                        "reads": [o, w]})
        elif f["kind"] == "loader":
            out.append({"edge": e["id"], "version": None, "class": "unmodelled"})
        else:
            raise Construct(f"{e['id']}: no fragment rule for a function of kind {f['kind']}")
    return out


# ====================================================================== L4 the push verdict (Lemma 6.12 by position)
def _slot(t) -> tuple | None:
    if (isinstance(t, dict) and set(t) == {"field", "of"} and isinstance(t["of"], dict) and set(t["of"]) == {"var"}):
        return (t["of"]["var"], t["field"])
    return None


def pins(st: dict) -> dict:
    """{(binder, field): bytes} of the premises that pin a field to constant bytes (the version premise and the pins);
    correspondence premises (field = field) fix no value."""
    out = {}
    for a in st.get("assume", []):
        eq = a.get("eq") if isinstance(a, dict) else None
        if not (isinstance(eq, list) and len(eq) == 2):
            continue
        for x, y in ((eq[0], eq[1]), (eq[1], eq[0])):
            s = _slot(x)
            if s is not None and isinstance(y, dict) and set(y) == {"bytes"}:
                out[s] = list(bytes.fromhex(y["bytes"][2:]))
                break
    return out


def _norm(cell: list, var: str, pn: dict) -> list:
    if cell[0] == "field" and (var, cell[1]) in pn:
        return ["const", pn[(var, cell[1])][cell[2]]]
    return cell


def _sides(st: dict) -> list[tuple[str, str]]:
    """[(function, binder)] of a law's two claim sides: p(h) and q(k)."""
    out = []
    for t in st["claim"]["eq"]:
        if not (isinstance(t, dict) and set(t) == {"call", "args"} and len(t["args"]) == 1 and set(t["args"][0]) == {"var"}):
            raise Construct(f"a push law's claim side is no call of a binder: {t}")
        out.append((t["call"], t["args"][0]["var"]))
    return out


def blind_decoders(c: Component, family: list[str], lengths: list[int], v: int) -> list[str]:
    """The family decoders that observe nothing on the images at v: one that rejects a byte string of an image's
    length whose tag byte is v (the version premise fixes the tag) returns its error on every image."""
    return sorted(d for d in family if not all(decoder_ok(c.fn_of(d), n, v, c.tag) for n in lengths))


def observed_positions(c: Component, family: list[str], blind: list[str]) -> set[int]:
    reads: set[int] = set()
    for d in family:
        if d in blind:
            continue
        rd = c.fn_of(d)["read"]
        reads |= set(range(rd["offset"], rd["offset"] + rd["width"]))
    return reads


def push_verdict(c: Component, lid: str, st: dict, family: list[str], v: int) -> dict:
    (pf, hp), (qf, hq) = _sides(st)
    lp, lq = layout_at(c.fns[pf], v), layout_at(c.fns[qf], v)
    if lp is None or lq is None:
        raise Construct(f"{lid}: a side has no layout at version {v}")
    pn = pins(st)
    if len(lp) != len(lq):
        return {"law": lid, "pushed": False,
                "collision": {"position": min(len(lp), len(lq)), "kind": "length", "p": None, "q": None}}
    reads = observed_positions(c, family, blind_decoders(c, family, [len(lp)], v))
    for i in range(len(lp)):
        if i in reads:
            continue
        a, b = _norm(lp[i], hp, pn), _norm(lq[i], hq, pn)
        if a[0] == "const" and b[0] == "const":
            if a[1] == b[1]:
                continue
            kind = "constants_differ"
        elif "unknown" in (a[0], b[0]):
            kind = "unknown_cell"
        else:
            kind = "unobserved_field"
        return {"law": lid, "pushed": False, "collision": {"position": i, "kind": kind, "p": a, "q": b}}
    return {"law": lid, "pushed": True, "collision": None}


# ====================================================================== L5 collision certificates
def ones_fill(c: Component, st: dict) -> dict:
    """W: every field byte of each binder 0x01, the fields a premise pins taking the pinned bytes."""
    pn = pins(st)
    out = {}
    for b in st["binders"]:
        rec = c.doc["carriers"].get(b["type"])
        if not rec or rec.get("kind") != "record":
            raise Construct(f"binder {b['name']}: {b['type']} is no record carrier")
        out[b["name"]] = {f["name"]: "0x" + bytes(pn.get((b["name"], f["name"]), [1] * f["width"])).hex()
                          for f in rec["fields"]}
    return out


def _cell_value(cell: list, binder: str, fill: dict):
    if cell[0] == "const":
        return cell[1]
    if cell[0] == "field":
        return bytes.fromhex(fill[binder][cell[1]][2:])[cell[2]]
    return None


def certificate(c: Component, lid: str, st: dict, family: list[str], v: int, verdict: dict) -> dict | None:
    """Rule L5 for one law that is not pushed: a cross certificate, a same_side one, or None."""
    sides = [(f, b, k) for (f, b), k in zip(_sides(st), ("p", "q"))]
    fill = ones_fill(c, st)
    col = verdict["collision"]
    base = {"law": lid, "family": family,
            "laws": sorted(f"obs_{c.edge(d)['model_fn']}" for d in family) + ["differ"],
            "dir": f"collisions/{lid}"}
    if col["kind"] == "length":
        return dict(base, kind="cross", witness=fill, witness2=None)
    a = _cell_value(col["p"], sides[0][1], fill)
    b = _cell_value(col["q"], sides[1][1], fill)
    if a is not None and b is not None and a != b:
        return dict(base, kind="cross", witness=fill, witness2=None)
    lay0 = layout_at(c.fns[sides[0][0]], v)
    reads = observed_positions(c, family, blind_decoders(c, family, [len(lay0)], v))
    binders = {x["name"]: x["type"] for x in st["binders"]}
    for (fn, binder, key) in sides:
        cell = col[key]
        if cell[0] != "field":
            continue
        lay = layout_at(c.fns[fn], v)
        at = [i for i, x in enumerate(lay) if x[0] == "field" and x[1] == cell[1]]
        if any(i in reads for i in at):
            continue
        width = next(f["width"] for f in c.doc["carriers"][binders[binder]]["fields"] if f["name"] == cell[1])
        w2 = dict(fill[binder], **{cell[1]: "0x" + bytes([2] * width).hex()})
        return dict(base, kind="same_side", side=key, witness={binder: fill[binder]}, witness2={binder: w2})
    return None


# ====================================================================== L2-L4 the elements
def _order_key(x: dict) -> tuple:
    return (KINDS.index(x["kind"]), x["p"], x["q"], -1 if x["version"] is None else x["version"])


def elements(c: Component) -> tuple[list, list, dict]:
    """(elements, excluded, weak) of one component (rules L2-L4)."""
    from .par import common_versions
    edges = {e["id"]: e for e in c.diagram["edges"]}
    rt = {b["key"]["atom"]: b for b in c.basis if b["subform"] == "round_trip" and "atom" in b["key"]}
    cc = {(b["key"]["p"], b["key"]["q"], b["version"]): b for b in c.basis
          if b["subform"] == "cross_component_codec" and "p" in b["key"]}
    weak = [b for b in c.basis if b["subform"] == "weak"]
    els, excluded, inv = [], [], set()
    for a in sorted((a for a in c.atoms if a["level"] == "E1" and a["via"]["kind"] == "inverse"), key=lambda a: a["id"]):
        b = rt.get(a["id"])
        laws = sorted(set(b["laws"]) | set(b["duplicates"].values())) if b is not None else []
        v = a["via"]["version"]
        inv.add((a["p"], a["q"], v))
        els.append({"kind": "round_trip", "p": a["p"], "q": a["q"], "version": v, "atoms": [a["id"]],
                    "laws": laws, "covered": bool(laws), "reason": None if laws else "no_law"})
    groups: dict[tuple, list] = {}
    for a in c.atoms:
        if a["level"] == "E1" and a["via"]["kind"] == "common_decoder":
            groups.setdefault((a["p"], a["q"], a["via"]["version"]), []).append(a)
    for (pid, qid, v), g in sorted(groups.items(), key=lambda kv: kv[0]):
        fam = sorted({a["via"]["decoder"] for a in g})
        b = cc.get((pid, qid, v))
        lids = sorted(set(b["laws"]) | set(b["duplicates"].values())) if b is not None else []
        pushes = [push_verdict(c, lid, c.laws[lid], fam, v) for lid in lids]
        covered = any(x["pushed"] for x in pushes)
        lens = sorted({len(layout_at(c.fn_of(pid), v)), len(layout_at(c.fn_of(qid), v))})
        els.append({"kind": "observed", "p": pid, "q": qid, "version": v, "atoms": sorted(a["id"] for a in g),
                    "family": fam, "blind": blind_decoders(c, fam, lens, v), "pushes": pushes,
                    "laws": [x["law"] for x in pushes if x["pushed"]],
                    "covered": covered, "reason": None if covered else "non_injective"})
    for a in sorted((a for a in c.atoms if a["level"] == "E2"), key=lambda a: a["id"]):
        e, d = edges[a["p"]], edges[a["q"]]
        cv = common_versions([e, d])
        if cv == []:
            excluded.append({"atom": a["id"], "p": a["p"], "q": a["q"], "reason": "no_common_version"})
            continue
        for v in (cv if cv is not None else [None]):
            if (a["p"], a["q"], v) in inv:
                continue
            lay = layout_at(c.fns[e["model_fn"]], v)
            if lay is None:
                raise Construct(f"{a['id']}: {e['id']} has no layout at version {v}")
            rd = c.fns[d["model_fn"]]["read"]
            cells = [lay[i] if i < len(lay) else ["unknown"] for i in range(rd["offset"], rd["offset"] + rd["width"])]
            kind = "constant_read" if all(x[0] == "const" for x in cells) else "partial_read"
            el = {"kind": kind, "p": a["p"], "q": a["q"], "version": v, "atoms": [a["id"]], "laws": [],
                  "covered": False, "reason": "no_rule"}
            if kind == "constant_read":
                el["bytes"] = "0x" + bytes(x[1] for x in cells).hex()
            els.append(el)
    for a in sorted((a for a in c.atoms if a["level"] in ("E3", "E4", "E5")), key=lambda a: a["id"]):
        els.append({"kind": "other", "p": a["p"], "q": a["q"], "version": (a.get("via") or {}).get("version"),
                    "atoms": [a["id"]], "laws": [], "covered": False, "reason": "no_rule"})
    els.sort(key=_order_key)
    e6 = [a for a in c.atoms if a["level"] == "E6"]
    with_law = sorted({b["key"]["atom"] for b in weak if b["laws"] or b["duplicates"]})
    return els, excluded, {"atoms": len(e6), "with_law": len(with_law)}


# ====================================================================== L6 HASH candidates
def hash_candidates(c: Component) -> list[dict]:
    out = []
    for h in sorted((e for e in c.diagram["edges"] if e["kind"] == "HASH"), key=lambda e: e["id"]):
        names = sorted(n for n, f in c.fns.items() if (f.get("sink") or {}).get("op") == h["tgt"] and f["to"] == h["src"])
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                pair = sorted([f"CODEC.{a}", f"CODEC.{b}"])
                ev = sorted(x["id"] for x in c.atoms if {x["p"], x["q"]} == set(pair))
                first = {n: c.fns[n]["sink"]["stack"][0] for n in (a, b)}
                out.append({"hash": h["id"], "pair": pair, "sinks": [first[p.split(".", 1)[1]] for p in pair],
                            "evidenced": bool(ev), "atoms": ev})
    return sorted(out, key=lambda x: (x["hash"], x["pair"]))


# ====================================================================== L8 the document
def coverage(els: list[dict]) -> dict:
    n = len(els)
    k = sum(1 for x in els if x["covered"])
    return {"elements": n, "covered": k, "rate": (k / n) if n else None,
            "by_kind": {kd: {"elements": sum(1 for x in els if x["kind"] == kd),
                             "covered": sum(1 for x in els if x["kind"] == kd and x["covered"])} for kd in KINDS},
            "uncovered": [{"kind": x["kind"], "p": x["p"], "q": x["q"], "version": x["version"], "reason": x["reason"]}
                          for x in els if not x["covered"]]}


def analyse(c: Component, milestone: str) -> dict:
    els, excluded, weak = elements(c)
    certs, uncertified = [], []
    for el in els:
        if el["kind"] != "observed":
            continue
        for x in el["pushes"]:
            if x["pushed"]:
                continue
            cert = certificate(c, x["law"], c.laws[x["law"]], el["family"], el["version"], x)
            if cert is None:
                uncertified.append(x["law"])
            else:
                certs.append(cert)
    return {"lossy_version": LOSSY_VERSION, "document": DOCUMENT, "milestone": milestone, "model": c.model,
            "facts": c.rel, "inputs": c.inputs, "fragment": fragment(c), "elements": els, "excluded": excluded,
            "weak": weak, "hash_candidates": hash_candidates(c), "collisions": sorted(certs, key=lambda x: x["law"]),
            "uncertified": sorted(uncertified), "coverage": coverage(els)}


# ====================================================================== L5 in Bend
def _model_text_check(c: Component, model: Path, root: Path) -> None:
    from ..gen import linked as GL
    try:
        want = GL.generate(c.doc, c.sha)
    except GL.Unsupported as e:
        raise Construct(f"{c.rel}: the component model cannot be generated: {e}") from e
    shown = _show(model, root)
    if not model.is_file():
        raise Refused(f"{shown} is missing: the component model is written by `holon run` (I24 rule X9)")
    if model.read_text(encoding="utf-8") != want:
        raise Refused(f"{shown} is stale: it is not what holon.gen.linked generates from {c.rel} now (run `holon run`)")


def _show(p: Path, root: Path) -> str:
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(p)


def _lit(c: Component, binder_type: str, value: dict) -> str:
    from ..gen import linked as GL
    return GL.literal(c.doc, binder_type, value)


def certificate_files(c: Component, cert: dict, st: dict, model_import: str) -> tuple[str, str]:
    """(LAWS.bend, PROOF.bend) of one collision certificate: obs_<d> by evaluation, differ by the counter-law motive
    (BEND_PRIMER 5.4: the model's equality is untrusted; if the images were equal no proof of differ could check)."""
    from ..gen import linked as GL
    types = {b["name"]: b["type"] for b in st["binders"]}
    (pf, hp), (qf, hq) = _sides(st)
    if cert["kind"] == "cross":
        lhs = f"{GL.ALIAS}.{pf}({_lit(c, types[hp], cert['witness'][hp])})"
        rhs = f"{GL.ALIAS}.{qf}({_lit(c, types[hq], cert['witness'][hq])})"
        what = (f"kind cross: at the ones fill under the law's premises, the images of {pf} and {qf} differ while every "
                "decoder of the family observes the same")
    else:
        fn, b = (pf, hp) if cert["side"] == "p" else (qf, hq)
        lhs = f"{GL.ALIAS}.{fn}({_lit(c, types[b], cert['witness'][b])})"
        rhs = f"{GL.ALIAS}.{fn}({_lit(c, types[b], cert['witness2'][b])})"
        what = (f"kind same_side (side {cert['side']}): two inputs of {fn} whose images differ while every decoder of the "
                "family observes the same")
    head = [f"# GENERATED by holon.rules.par_lossy (rule L5, Prop 6.11 at a point): the collision certificate of "
            f"{cert['law']}; do not edit.", f"# {what}.", "import Base", f"import {model_import} as {GL.ALIAS}", ""]
    laws, proofs = list(head), ["# GENERATED by holon.rules.par_lossy: obs_* by evaluation, differ by the counter-law "
                                "motive; accepted only if Bend checks it.", "import Base",
                                f"import {model_import} as {GL.ALIAS}", "import ./LAWS.bend as Laws", ""]
    for d in cert["family"]:
        dn = c.edge(d)["model_fn"]
        laws += [f"law obs_{dn}:", f"  {{{GL.ALIAS}.{dn}({lhs}) == {GL.ALIAS}.{dn}({rhs}) : {GL.MAYBE_BYTES}}}", ""]
        proofs += [f"def Laws.obs_{dn}():", "  {==}", ""]
    laws += ["law differ:", f"  {{{lhs} != {rhs} : {GL.BYTES}}}"]
    proofs += ["def Laws.differ():", f"  e => (%e : {GL.ALIAS}.is_true({GL.ALIAS}.eq_bytes(_, {lhs}))", "  Unit{})"]
    return "\n".join(laws) + "\n", "\n".join(proofs) + "\n"


# ====================================================================== L7 the core laws and their proof generators
LAW_HEAD = re.compile(r"^law\s+(\w+)\s*:\s*$")
BINDER = re.compile(r"^\s+for\s+([+-]?)(\w+)\s*:\s*(.+?)\s*$")


def core_sidecar(milestone: str, root: Path) -> Path:
    """spec/<M>/lib/par_lossy.json of the milestone, or of the latest earlier milestone that has one (a test milestone:
    the latest milestone's)."""
    root = Path(root)
    found = []
    for p in sorted(root.glob(f"spec/M*/lib/{SIDECAR_NAME}")):
        m = re.fullmatch(r"M(\d+)", p.parent.parent.name)
        if m:
            found.append((int(m.group(1)), p))
    k = re.fullmatch(r"M(\d+)", milestone or "")
    if k:
        found = [x for x in found if x[0] <= int(k.group(1))]
    if not found:
        raise Refused(f"no spec/M*/lib/{SIDECAR_NAME} holds the core statements for {milestone}")
    return max(found)[1]


def core_statements(milestone: str, root: Path) -> tuple[list[dict], Path]:
    p = core_sidecar(milestone, root)
    try:
        laws = json.loads(p.read_text(encoding="utf-8"))["core"]["laws"]
        assert isinstance(laws, list) and all(isinstance(x["name"], str) and isinstance(x["bend"], str) for x in laws)
    except (OSError, ValueError, KeyError, TypeError, AssertionError) as e:
        raise Refused(f"{_show(p, root)}: no core statements ({type(e).__name__})") from e
    return laws, p


def parse_law(text: str) -> dict:
    """A law block: its name, binders [(mode, name, type)] and claim (the last line)."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    m = LAW_HEAD.match(lines[0]) if lines else None
    if not m:
        raise Construct(f"no law block: {text[:60]!r}")
    binders = []
    for ln in lines[1:-1]:
        b = BINDER.match(ln)
        if not b:
            raise Construct(f"law {m.group(1)}: cannot read the binder line {ln.strip()!r}")
        binders.append((b.group(1), b.group(2), b.group(3)))
    return {"name": m.group(1), "binders": binders, "claim": lines[-1].strip()}


PI = re.compile(r"^@(\w+)\s*:\s*(\w+)\s*->\s*(.+)$")


def _split_top(t: str, sep: str) -> list[str]:
    """t split at sep where no bracket is open."""
    out, depth, cur, i = [], 0, "", 0
    while i < len(t):
        ch = t[i]
        if ch in "({[<":
            depth += 1
        elif ch in ")}]>" and not (ch == ">" and t[i - 1:i] == "-"):
            depth -= 1
        if depth == 0 and t.startswith(sep, i):
            out.append(cur)
            cur = ""
            i += len(sep)
            continue
        cur += ch
        i += 1
    out.append(cur)
    return [x.strip() for x in out]


def _eq(t: str) -> tuple[str, str, str] | None:
    """(a, b, T) of an equation {a == b : T}."""
    t = t.strip()
    if not (t.startswith("{") and t.endswith("}")):
        return None
    inner = t[1:-1]
    parts = _split_top(inner, " : ")
    if len(parts) != 2:
        return None
    sides = _split_top(parts[0], " == ")
    if len(sides) != 2:
        return None
    return sides[0], sides[1], parts[1]


def _pi(t: str) -> tuple[str, str, list[str]] | None:
    """(x, X, [premise, .., conclusion]) of a dependent function @x:X -> P1 -> .. -> C."""
    m = PI.match(t.strip())
    if not m:
        return None
    return m.group(1), m.group(2), _split_top(m.group(3), " -> ")


def _call_parts(t: str) -> tuple[str, str] | None:
    """(head, argument) of a one-argument call h(a)."""
    m = re.fullmatch(r"([\w.]+)\((.*)\)", t.strip())
    if not m or len(_split_top(m.group(2), ",")) != 1:
        return None
    return m.group(1), m.group(2)


def proof_pointwise_premise(law: dict) -> tuple[list[str], list[str]] | None:
    """Class pointwise_premise (Lemma 6.12, the pushing direction under CF): the claim @x:X -> C, a binder
    cf: @x:X -> H -> C and a binder e: @x:X -> H; the proof applies cf at x to e at x."""
    claim = _pi(law["claim"])
    if claim is None or len(claim[2]) != 1:
        return None
    x, X, (concl,) = claim
    pis = [(n, p) for _, n, t in law["binders"] for p in [_pi(t)] if p is not None and p[0] == x and p[1] == X]
    for cf, (_, _, cps) in pis:
        if len(cps) != 2 or cps[1] != concl:
            continue
        for e, (_, _, eps) in pis:
            if e != cf and eps == [cps[0]]:
                return [], [f"{x} => {cf}({x}, {e}({x}))"]
    return None


def proof_whisker(law: dict) -> tuple[list[str], list[str]] | None:
    """Class whisker (Lemma 6.12's other direction, Lemma 6.2): the claim @x:X -> {h(a) == h(b) : B} and a binder
    e: @x:X -> {a == b : A}; rewrite with e at x under h, then reflexivity."""
    claim = _pi(law["claim"])
    if claim is None or len(claim[2]) != 1:
        return None
    x, X, (concl,) = claim
    ce = _eq(concl)
    if ce is None:
        return None
    l, r = _call_parts(ce[0]), _call_parts(ce[1])
    if l is None or r is None or l[0] != r[0]:
        return None
    for _, n, t in law["binders"]:
        p = _pi(t)
        if p is None or p[0] != x or p[1] != X or len(p[2]) != 1:
            continue
        he = _eq(p[2][0])
        if he is not None and (he[0], he[1]) == (l[1], r[1]):
            return [], [f"{x} => (%{n}({x}) : {{{ce[0]} == {r[0]}(_) : {ce[2]}}}", "{==})"]
    return None


def proof_succ_injective(law: dict) -> tuple[list[str], list[str]] | None:
    """Class succ_injective (an inhabitant of a CF premise, L21): the claim {x == y : Nat} and a hypothesis
    e: {1n+x == 1n+y : Nat}; rewrite with e through the predecessor, then reflexivity."""
    ce = _eq(law["claim"])
    if ce is None or ce[2] != "Nat":
        return None
    for _, n, t in law["binders"]:
        he = _eq(t)
        if he is not None and he[2] == "Nat" and (he[0], he[1]) == (f"1n+{ce[0]}", f"1n+{ce[1]}"):
            helper = ["# the predecessor: the motive that undoes a successor", "def core_pred(n: Nat) -> Nat:",
                      "  match n:", "    case 0n:", "      0n", "    case 1n+p:", "      p", ""]
            return helper, [f"%{n} : {{{ce[0]} == core_pred(_) : Nat}}", "{==}"]
    return None


PROOF_CLASSES = (("pointwise_premise", proof_pointwise_premise), ("whisker", proof_whisker),
                 ("succ_injective", proof_succ_injective))


def core_files(statements: list[dict]) -> tuple[str, str]:
    """(LAWS.bend, PROOF.bend) of rule L7: the frozen statements in order, each proved by the first proof class whose
    shape it has (never hand-written; Bend decides)."""
    laws = ["# GENERATED by holon.rules.par_lossy (rule L7): the core laws of injective pushing, statements frozen in "
            "the milestone's", "# par_lossy sidecar. Import core/PROOF.bend, never this file alone.", "import Base", ""]
    laws.append("\n\n".join(x["bend"].rstrip("\n") for x in statements))
    helpers, defs = [], []
    for x in statements:
        law = parse_law(x["bend"])
        if law["name"] != x["name"]:
            raise Construct(f"core statement {x['name']} declares the law {law['name']}")
        for cname, gen in PROOF_CLASSES:
            got = gen(law)
            if got is None:
                continue
            hs, body = got
            for h in hs:
                if h not in helpers or not h.strip():
                    helpers.append(h)
            params = ", ".join(n for _, n, _ in law["binders"])
            defs += [f"# class {cname}", f"def Laws.{law['name']}({params}):"] + [f"  {ln}" for ln in body] + [""]
            break
        else:
            raise Construct(f"core law {law['name']}: no proof class has its shape")
    proof = ["# GENERATED by holon.rules.par_lossy (rule L7): per-class proofs of the core laws; accepted only if Bend "
             "checks it.", "import Base", "import ./LAWS.bend as Laws", ""] + helpers + defs
    return "\n".join(laws).rstrip("\n") + "\n", "\n".join(proof).rstrip("\n") + "\n"


# ====================================================================== L9 the evidence review
def record_files(root: Path, records: Path | None) -> list[Path]:
    from ..refinement import REF_DIR
    d = Path(root) / REF_DIR if records is None else Path(records)
    return sorted(d.glob("*.json")) + sorted((d / "historical").glob("*.json"))


def disagreements_of(rec: dict) -> list[tuple[str, str | None]]:
    """(disagreement id, edge) pairs of a refinement record: a per-edge record's disagreement_ids at its diagram_edge;
    a step record's (kind extracted) disagreements, at TRANS.<action> when the entry names an action."""
    if isinstance(rec.get("disagreement_ids"), list):
        return [(d, rec.get("diagram_edge")) for d in rec["disagreement_ids"]]
    if rec.get("kind") == "extracted" and isinstance(rec.get("disagreements"), list):
        return [(d["id"], f"TRANS.{d['action']}" if d.get("action") else None) for d in rec["disagreements"]]
    return []


def review(root: Path, files: list[Path], analyses: list[tuple[dict, dict]], evidence_sha256) -> list[dict]:
    """analyses: [(analysis, diagram)]. One open entry per disagreement whose (facts, edge) is no endpoint (p, q or a
    family decoder) of a covered element of a component, sorted by id."""
    root = Path(root).resolve()
    edges, covered = {}, set()
    for an, dg in analyses:
        comp_of = {e["id"]: e.get("component") for e in dg["edges"]}
        for e in dg["edges"]:
            if e.get("component"):
                edges[(e["component"], e["id"])] = e["id"]
        for el in an["elements"]:
            if el["covered"]:
                for eid in [el["p"], el["q"]] + el.get("family", []):
                    covered.add((comp_of.get(eid), eid))
    out = []
    for f in files:
        rel = Path(f).resolve().relative_to(root).as_posix()
        try:
            rec = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise Refused(f"{rel}: not a readable refinement record ({type(e).__name__})") from e
        if not isinstance(rec, dict):
            raise Refused(f"{rel}: not a refinement record")
        for did, edge in disagreements_of(rec):
            key = (rec.get("facts"), edge)
            m3 = edges.get(key)
            if m3 is not None and key in covered:
                continue
            out.append({"id": f"review:{rel}#{did}", "record": rel, "disagreement": did, "facts": rec.get("facts"),
                        "edge": edge, "m3_edge": m3, "reason": "unresolved_edge" if m3 is None else "no_covered_element",
                        "status": "open", "adjudicator": "A4", "adjudication": "I45",
                        "evidence_sha256": evidence_sha256})
    return sorted(out, key=lambda e: e["id"])


def review_text(entries: list[dict]) -> str:
    return "".join(json.dumps(e, sort_keys=True) + "\n" for e in entries)


# ====================================================================== L8 the metric (holon metrics)
def metric(milestone: str, root: Path) -> dict | None:
    """evidenced_pair_coverage of results/<M>/metrics.json, from gen/<M>/par_lossy/*.json and
    spec/<M>/evidence_review.jsonl; None when the milestone has no par_lossy document."""
    root = Path(root)
    docs = []
    for p in sorted((root / "gen" / milestone / OUT_DIR).glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and d.get("document") == DOCUMENT:
            docs.append(d)
    if not docs:
        return None
    els = [x for d in docs for x in d["elements"]]
    cov = coverage(els)
    ev = root / "gen" / milestone / "evidence.json"
    rv = root / "spec" / milestone / REVIEW_NAME
    return {"evidence": {"path": f"gen/{milestone}/evidence.json",
                         "evidence_sha256": json.loads(ev.read_text(encoding="utf-8")).get("evidence_sha256")
                         if ev.is_file() else None},
            "relative_to": relative_to(milestone),
            "elements": cov["elements"], "covered": cov["covered"], "rate": cov["rate"], "by_kind": cov["by_kind"],
            "uncovered": len(cov["uncovered"]),
            "excluded": {"no_common_version": sum(len(d["excluded"]) for d in docs)},
            "weak": {"atoms": sum(d["weak"]["atoms"] for d in docs), "with_law": sum(d["weak"]["with_law"] for d in docs)},
            "hash_candidates": sum(len(d["hash_candidates"]) for d in docs),
            "uncovered_disagreements": len(rv.read_text(encoding="utf-8").splitlines()) if rv.is_file() else None,
            "models": sorted(d["model"] for d in docs)}


# ====================================================================== the build
def build(milestone: str, root: Path, out: Path, codecs: list[str] | None = None, gen_dir: Path | None = None,
          records: Path | None = None) -> tuple[dict[str, str], str]:
    """Every file rule L0-L9 writes, as ({path under out: text}, review text). Nothing is written here."""
    root = Path(root).resolve()
    tm = target_milestone(milestone)
    if gen_dir is not None and tm and not codecs:
        raise Refused(f"{milestone}: the component model of a milestone is gen/{milestone}/model (no --gen-dir)")
    comps, ev = components(milestone, root, codecs)
    gd = Path(gen_dir).resolve() if gen_dir is not None else root / "gen" / milestone
    canon_out = (root / "gen" / milestone / OUT_DIR) if (tm and not codecs) else Path(out).resolve()
    files: dict[str, str] = {}
    analyses = []
    for c in comps:
        model = gd / "model" / f"{c.role}.bend"
        an = analyse(c, milestone)
        if an["collisions"]:
            _model_text_check(c, model, root)
        for cert in an["collisions"]:
            imp = Path(os.path.relpath(model, canon_out / cert["dir"])).as_posix()
            lt, pt = certificate_files(c, cert, c.laws[cert["law"]], imp)
            files[f"{cert['dir']}/LAWS.bend"] = lt
            files[f"{cert['dir']}/PROOF.bend"] = pt
        files[f"{c.role}.json"] = dumps(an)
        analyses.append((an, c.diagram))
    statements, _ = core_statements(milestone, root)
    lt, pt = core_files(statements)
    files["core/LAWS.bend"] = lt
    files["core/PROOF.bend"] = pt
    if records is None:
        rec_files = record_files(root, None) if tm else []
    else:
        rp = Path(records).resolve()
        try:
            rp.relative_to(root)
        except ValueError:
            raise Refused(f"--records {records}: not inside the root {root}") from None
        if not rp.is_dir():
            raise Refused(f"--records {records}: no such directory")
        rec_files = record_files(root, rp)
    esha = ev.get("evidence_sha256")
    entries = review(root, rec_files, analyses, esha)
    return files, review_text(entries)


def _tree(d: Path) -> dict[str, str]:
    d = Path(d)
    if not d.is_dir():
        return {}
    return {p.relative_to(d).as_posix(): p.read_text(encoding="utf-8") for p in sorted(d.rglob("*")) if p.is_file()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon lossy")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", help="repository root holding the inputs (default: this checkout)")
    ap.add_argument("--out", help="output directory (default <root>/gen/<M>/par_lossy)")
    ap.add_argument("--review", help="the evidence review (default <root>/spec/<M>/evidence_review.jsonl for M<k>, "
                                     "<out>/evidence_review.jsonl for a test milestone)")
    ap.add_argument("--records", help="the refinement records directory (default results/M2/refinement for M<k>; a "
                                      "test milestone reads records only when given)")
    ap.add_argument("--codec", action="append", help="a linked codec document (test milestones, as derive)")
    ap.add_argument("--gen-dir", help="where holon run wrote the component model (test milestones; default gen/<M>)")
    ap.add_argument("--check", action="store_true", help="compare a fresh build with the files, writing nothing")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    m = a.milestone
    out = Path(a.out).resolve() if a.out else root / "gen" / m / OUT_DIR
    if a.review:
        rv = Path(a.review).resolve()
    elif target_milestone(m):
        rv = root / "spec" / m / REVIEW_NAME
    else:
        rv = out / REVIEW_NAME
    try:
        files, rtext = build(m, root, out, a.codec, Path(a.gen_dir) if a.gen_dir else None,
                             Path(a.records) if a.records else None)
    except Refused as e:
        print(f"holon lossy: refused: {e}", file=sys.stderr)
        return 2
    except Construct as e:
        print(f"holon lossy: refused construct: {e}", file=sys.stderr)
        return 3
    inside = None
    try:
        inside = rv.relative_to(out).as_posix()
    except ValueError:
        pass
    want = dict(files)
    if inside is not None:
        want[inside] = rtext
    if a.check:
        bad = []
        have = _tree(out)
        for k in sorted(set(have) | set(want)):
            if have.get(k) != want.get(k):
                bad.append(k)
        if inside is None and (not rv.is_file() or rv.read_text(encoding="utf-8") != rtext):
            bad.append(_show(rv, root))
        if bad:
            print(f"holon lossy: {len(bad)} file(s) differ from a fresh build: {bad[:10]}", file=sys.stderr)
            return 1
        print(f"holon lossy: {_show(out, root)} and {_show(rv, root)} reproduce ({len(want)} files)")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    for p in sorted(out.rglob("*"), reverse=True):
        rel = p.relative_to(out).as_posix()
        if p.is_file() and rel not in want:
            p.unlink()
        elif p.is_dir() and not any(k.startswith(rel + "/") for k in want):
            try:
                p.rmdir()
            except OSError:
                pass
    for rel, text in sorted(want.items()):
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    if inside is None:
        rv.parent.mkdir(parents=True, exist_ok=True)
        rv.write_text(rtext, encoding="utf-8")
    docs = [json.loads(files[k]) for k in sorted(files) if k.endswith(".json") and "/" not in k]
    for d in docs:
        cov = d["coverage"]
        print(f"{d['model']}: {cov['covered']} of {cov['elements']} evidenced elements covered; "
              f"{len(d['collisions'])} collision certificates; {len(d['hash_candidates'])} HASH candidates")
    print(f"wrote {_show(out, root)} ({len(want)} files) and the review {_show(rv, root)} "
          f"({len(rtext.splitlines())} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
