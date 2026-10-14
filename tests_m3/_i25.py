"""I25 instrument, fixed at the I25 prereg (BUILD_PLAN §0.1, "instruments are inputs").

The contract is the docstring of tests_m3/test_par_lossy.py: rules L0-L9 (PAR-lossy and injective pushing over the
linked codec components I24 built from the adopted extracted documents). This module writes those rules out a second
time, independently of holon/, so that the tests can decide what holon must write:

- fragment(comp, diag): rule L1, Def 4.4 by the layout algebra (§10.2) and Cor 6.16 for HASH edges;
- elements(comp, diag, ats, exp): rules L2-L4, the evidenced lossy elements of the frozen evidence set, each covered
  or not, and the push verdict (Lemma 6.12 by position) of every cross-component law I24 derived;
- blind_decoders(comp, family, lengths, v), push_verdict(comp, lid, law, family, v): rule L4 for one law (a family
  decoder that rejects the images' length under the version's tag observes nothing);
- collision_witness(comp, law), certificate(comp, lid, law, family, v, verdict): rule L5 (the ones fill under the
  law's premises; a cross certificate, or a same_side one when the premises tie the collision);
- hash_candidates(comp, diag, ats): rule L6;
- analyse(comp, milestone): the per-component document of rule L8 (gen/<M>/par_lossy/<role>.json, the keys the
  contract fixes);
- review(root, record_files, analyses): rule L9, the evidence-review entries of the refinement records;
- metric(analyses, entries): rule L8's evidenced_pair_coverage entry of results/M3/metrics.json;
- par_lossy_doc(root): the frozen sidecar spec/M3/lib/par_lossy.json (every value this contract predicts).

Inputs only: what tests_m3/_i24x.py reads (the adopted extracted documents, spec/M3/lib/derive_extracted.json and
link.json, the I14 lexicon), the committed frozen evidence set gen/M3/evidence.json (its atoms are compared with the
recomputed ones), the planted fixtures, and the refinement records results/M2/refinement/. It reads no law file and no
record: I24's basis and laws are recomputed by tests_m3/_i24x.py::expected, as holon must recompute them in memory
(rule L0). Nothing here imports holon/.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests_m3 import _i24 as P
from tests_m3 import _i24x as X
from tests_m3._m3 import ROOT, canonical_json, file_sha256, load_json

LOSSY_VERSION = "holon-lossy/0.1"
SIDECAR = Path("spec") / "M3" / "lib" / "par_lossy.json"
EVIDENCE = Path("gen") / "M3" / "evidence.json"
REF_DIR = Path("results") / "M2" / "refinement"
KINDS = ("round_trip", "observed", "constant_read", "partial_read", "other")
REASONS = ("no_law", "non_injective", "no_rule")
COLLISIONS = ("length", "constants_differ", "unobserved_field", "unknown_cell")
RELATIVE_TO = ("the frozen evidence set gen/M3/evidence.json: the lossy fragment has no topological basis "
               "(whitepaper Prop 6.11), so completeness is relative to the evidenced pairs; an unevidenced pair is "
               "not counted")
FIX_INJ = {"milestone": "T251", "adoption": "tests_m3/fixtures/par_lossy/derive_extracted.json",
           "link": "tests_m3/fixtures/par_lossy/link.json", "role": "hdr_len"}
FIX_NONINJ = {"milestone": "T252", "adoption": "tests_m3/fixtures/par_linked/derive_extracted.json",
              "link": "tests_m3/fixtures/par_linked/link.json", "role": "hdr_len"}

# rule L7: the core laws, statements fixed here (Bend 2 text, checked at the prereg as well-typed open laws)
CORE = [
    {"name": "core_inj_push",
     "doc": "Lemma 6.12, the pushing direction: h o f = h o g implies f = g wherever h is collision-free on "
            "{f(x), g(x)} (Cor 6.16: a CF premise over a two-element set at each point, never global injectivity).",
     "bend": "law core_inj_push:\n"
             "  for -X: Type\n"
             "  for -A: Type\n"
             "  for -B: Type\n"
             "  for -h: A -> B\n"
             "  for -f: X -> A\n"
             "  for -g: X -> A\n"
             "  for cf: @x:X -> {h(f(x)) == h(g(x)) : B} -> {f(x) == g(x) : A}\n"
             "  for e: @x:X -> {h(f(x)) == h(g(x)) : B}\n"
             "  @x:X -> {f(x) == g(x) : A}"},
    {"name": "core_inj_pull",
     "doc": "Lemma 6.12, the other direction (no premise: whiskering, Lemma 6.2): f = g implies h o f = h o g.",
     "bend": "law core_inj_pull:\n"
             "  for -X: Type\n"
             "  for -A: Type\n"
             "  for -B: Type\n"
             "  for -h: A -> B\n"
             "  for -f: X -> A\n"
             "  for -g: X -> A\n"
             "  for e: @x:X -> {f(x) == g(x) : A}\n"
             "  @x:X -> {h(f(x)) == h(g(x)) : B}"},
    {"name": "core_cf_succ",
     "doc": "Non-vacuity of core_inj_push's CF premise (whitepaper L21, G11): the successor on Nat is collision-free "
            "on every pair, so cf is inhabited (h = successor, any f and g).",
     "bend": "law core_cf_succ:\n"
             "  for x: Nat\n"
             "  for y: Nat\n"
             "  for e: {1n+x == 1n+y : Nat}\n"
             "  {x == y : Nat}"},
]
# rule L7's canary: core_inj_push without its CF premise is false (Prop 6.11) and must not check
CANARY = {"name": "canary_inj_push_without_cf",
          "bend": "law canary_inj_push_without_cf:\n"
                  "  for -X: Type\n"
                  "  for -A: Type\n"
                  "  for -B: Type\n"
                  "  for -h: A -> B\n"
                  "  for -f: X -> A\n"
                  "  for -g: X -> A\n"
                  "  for e: @x:X -> {h(f(x)) == h(g(x)) : B}\n"
                  "  @x:X -> {f(x) == g(x) : A}"}

# D7 (whitepaper §11.6): the pushing candidate whose instance belongs to I36; its sites at the pinned commit 3e44e79
D7 = {"id": "D7",
      "obligation": "The 32-bit truncation of the tree index is discharged by leaf injectivity under CF "
                    "(whitepaper §11.6)",
      "sites": ["contracts/contracts/libraries/common/Verify.sol:9 (uint256 index)",
                "contracts/contracts/libraries/common/Verify.sol:14-15 (only heights 0..31 of index select the path: "
                "the index is truncated to its low 32 bits)",
                "contracts/contracts/l1/L1CrossDomainMessenger.sol:138 (the leaf is keccak256 of the cross-domain "
                "calldata, which holds the full _nonce)",
                "contracts/contracts/l1/L1CrossDomainMessenger.sol:155 (verifyMerkleProof(leaf, proof, _nonce, root))"],
      "lossy_map": "index -> its low 32 bits (Verify.verifyMerkleProof)",
      "injective_map": "keccak256 over the encoded cross-domain calldata, collision-free on the pair compared (CF)",
      "push": "core_inj_push with h = keccak256 under CF(keccak256, {leaf inputs}): the truncated index plus the "
              "leaf determine the message",
      "in_extraction": False,
      "why_not_here": "outside today's extraction: no adopted M3 document (spec/M3/lib/derive_extracted.json: "
                      "morph_batch.go, morph_header, morph_rollup; the Solidity ones extract Rollup.sol only, "
                      "spec/M2/lib/extract_solidity.json and extract_rollup.json) contains Verify.sol or "
                      "L1CrossDomainMessenger.sol, so no component, edge or atom of the frozen evidence set reaches it",
      "instance": "I36 (BUILD_PLAN: 'D7 PROVED through injective pushing under CF (I25)')"}
D7_FILES = ("Verify.sol", "L1CrossDomainMessenger.sol", "verifyMerkleProof")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# ------------------------------------------------------------------ components and I24's basis, recomputed
def component(root: Path = ROOT, adoption: str | None = None, link: str | None = None, role: str | None = None):
    """(comp, diag, atoms) of one linked component (I24 rules X1-X7)."""
    comps = X.components(root) if adoption is None else X.components(root, adoption, link)
    if role is not None:
        comps = [c for c in comps if c["role"] == role]
    if len(comps) != 1:
        raise AssertionError(f"expected one component, got {[c['role'] for c in comps]}")
    comp = comps[0]
    diag = X.diagram(comp)
    return comp, diag, X.atoms(comp, diag)


# ------------------------------------------------------------------ L1 the fragment (Def 4.4)
def fragment(comp: dict, diag: dict) -> list[dict]:
    fs = comp["functions"]
    tag = comp["tag_index"]
    out = []
    for e in sorted(diag["edges"], key=lambda e: e["id"]):
        if e["kind"] == "HASH":
            out.append({"edge": e["id"], "version": None, "class": "cf"})
            continue
        f = fs[e["model_fn"]]
        if f["kind"] == "encoder":
            rec = comp["carriers"][f["from"]]
            names = [x["name"] for x in rec["fields"]]
            for v in (f["versions"] if f["versions"] is not None else [None]):
                lay = X.layout_at(f, v)
                dropped = []
                for fld in rec["fields"]:
                    if fld["name"] == "version" and "version" in names and v is not None:
                        continue   # P0 fixes version = v on R_v
                    if any(["field", fld["name"], k] not in lay for k in range(fld["width"])):
                        dropped.append(fld["name"])
                out.append({"edge": e["id"], "version": v, "class": "lossy" if dropped else "invertible",
                            "dropped": dropped})
        elif f["kind"] == "decoder":
            o, w = f["read"]["offset"], f["read"]["width"]
            longer = any(X.decoder_ok(f, o + w + 1, t, tag) for t in range(256))
            out.append({"edge": e["id"], "version": None, "class": "lossy" if (o > 0 or longer) else "invertible",
                        "reads": [o, w]})
        elif f["kind"] == "loader":
            out.append({"edge": e["id"], "version": None, "class": "unmodelled"})
        else:
            raise AssertionError(f"{e['id']}: no fragment rule for {f['kind']}")
    return out


# ------------------------------------------------------------------ L4 the push verdict (Lemma 6.12 by position)
def _pins(st: dict) -> dict:
    out = {}
    for a in st.get("assume", []):
        x, y = a["eq"]
        if "field" in x and "bytes" in y:
            out[(x["of"]["var"], x["field"])] = list(bytes.fromhex(y["bytes"][2:]))
    return out


def _norm(c: list, var: str, pins: dict) -> list:
    if c[0] == "field" and (var, c[1]) in pins:
        return ["const", pins[(var, c[1])][c[2]]]
    return c


def blind_decoders(comp: dict, family: list[str], lengths: list[int], v: int) -> list[str]:
    """L4: the family decoders that observe nothing on the pair's images at v: a decoder that rejects a byte string
    of an image's length whose tag byte is v (P0: the version premise fixes the tag) returns its error on every image,
    so its read range is not observed (it is constant on the images and cannot separate them)."""
    fs = comp["functions"]
    tag = comp["tag_index"]
    return sorted(d for d in family
                  if not all(X.decoder_ok(fs[d.split(".", 1)[1]], n, v, tag) for n in lengths))


def observed_positions(comp: dict, family: list[str], blind: list[str]) -> set[int]:
    fs = comp["functions"]
    reads: set[int] = set()
    for d in family:
        if d in blind:
            continue
        rd = fs[d.split(".", 1)[1]]["read"]
        reads |= set(range(rd["offset"], rd["offset"] + rd["width"]))
    return reads


def push_verdict(comp: dict, lid: str, law: dict, family: list[str], v: int) -> dict:
    fs = comp["functions"]
    st = law["statement"]
    l, r = st["claim"]["eq"]
    p, q = fs[l["call"]], fs[r["call"]]
    hp, hq = l["args"][0]["var"], r["args"][0]["var"]
    lp, lq = X.layout_at(p, v), X.layout_at(q, v)
    pins = _pins(st)
    if len(lp) != len(lq):
        return {"law": lid, "pushed": False, "collision": {"position": min(len(lp), len(lq)), "kind": "length",
                                                           "p": None, "q": None}}
    reads = observed_positions(comp, family, blind_decoders(comp, family, [len(lp)], v))
    for i in range(len(lp)):
        if i in reads:
            continue
        a, b = _norm(lp[i], hp, pins), _norm(lq[i], hq, pins)
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


def collision_witness(comp: dict, law: dict) -> dict:
    """L5: every field byte of each binder is 0x01, except the fields the law's premises pin (the version premise
    and the pins), which take the pinned bytes; correspondence premises hold because both sides are 0x01."""
    st = law["statement"]
    pins = _pins(st)
    out = {}
    for b in st["binders"]:
        rec = comp["carriers"][b["type"]]
        out[b["name"]] = {f["name"]: "0x" + bytes(pins.get((b["name"], f["name"]), [1] * f["width"])).hex()
                          for f in rec["fields"]}
    return out


def _cell_value(cell: list, binder: str, fill: dict):
    if cell[0] == "const":
        return cell[1]
    if cell[0] == "field":
        return bytes.fromhex(fill[binder][cell[1]][2:])[cell[2]]
    return None


def certificate(comp: dict, lid: str, law: dict, family: list[str], v: int, verdict: dict) -> dict | None:
    """L5: the collision certificate of a push law that is not pushed, or None when neither form applies.
    cross: the ones fill W under the law's premises, whose two images differ at the collision (or in length);
    same_side: when the premises tie the collision (the ones-fill images agree there), the first side (p, then q) whose
    collision cell is a field F of its binder, provided every position of F in that side's layout is unobserved: W
    and W2 = W with F's bytes all 0x02, two inputs of that side whose images differ and whose observations agree."""
    fs = comp["functions"]
    st = law["statement"]
    l, r = st["claim"]["eq"]
    sides = [(l["call"], l["args"][0]["var"], "p"), (r["call"], r["args"][0]["var"], "q")]
    fill = collision_witness(comp, law)
    c = verdict["collision"]
    base = {"law": lid, "family": family, "laws": sorted(f"obs_{d.split('.', 1)[1]}" for d in family) + ["differ"],
            "dir": f"collisions/{lid}"}
    if c["kind"] == "length":
        return dict(base, kind="cross", witness=fill, witness2=None)
    a = _cell_value(c["p"], sides[0][1], fill)
    b = _cell_value(c["q"], sides[1][1], fill)
    if a is not None and b is not None and a != b:
        return dict(base, kind="cross", witness=fill, witness2=None)
    lay0 = X.layout_at(fs[sides[0][0]], v)
    reads = observed_positions(comp, family, blind_decoders(comp, family, [len(lay0)], v))
    for (fn, binder, key) in sides:
        cell = c[key]
        if cell[0] != "field":
            continue
        lay = X.layout_at(fs[fn], v)
        at = [i for i, x in enumerate(lay) if x[0] == "field" and x[1] == cell[1]]
        if any(i in reads for i in at):
            continue
        rec = comp["carriers"][next(x["type"] for x in st["binders"] if x["name"] == binder)]
        width = next(f["width"] for f in rec["fields"] if f["name"] == cell[1])
        w2 = dict(fill[binder], **{cell[1]: "0x" + bytes([2] * width).hex()})
        return dict(base, kind="same_side", side=key, witness={binder: fill[binder]}, witness2={binder: w2})
    return None


# ------------------------------------------------------------------ L2-L3 the elements
def elements(comp: dict, diag: dict, ats: list[dict], exp: dict) -> tuple[list, list, dict]:
    """(elements, excluded, weak) of one component."""
    fs = comp["functions"]
    edges = {e["id"]: e for e in diag["edges"]}
    rt = {b["key"]["atom"]: b for b in exp["basis"] if b["subform"] == "round_trip"}
    cc = {(b["key"]["p"], b["key"]["q"], b["version"]): b for b in exp["basis"]
          if b["subform"] == "cross_component_codec"}
    weak = [b for b in exp["basis"] if b["subform"] == "weak"]
    els, excluded, inv = [], [], set()
    for a in sorted((a for a in ats if a["level"] == "E1" and a["via"]["kind"] == "inverse"), key=lambda a: a["id"]):
        b = rt[a["id"]]
        laws = sorted(set(b["laws"]) | set(b["duplicates"].values()))
        v = a["via"]["version"]
        inv.add((a["p"], a["q"], v))
        els.append({"kind": "round_trip", "p": a["p"], "q": a["q"], "version": v, "atoms": [a["id"]],
                    "laws": laws, "covered": bool(laws), "reason": None if laws else "no_law"})
    groups: dict[tuple, list] = {}
    for a in ats:
        if a["level"] == "E1" and a["via"]["kind"] == "common_decoder":
            groups.setdefault((a["p"], a["q"], a["via"]["version"]), []).append(a)
    for (pid, qid, v), g in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        fam = sorted({a["via"]["decoder"] for a in g})
        b = cc[(pid, qid, v)]
        lids = sorted(set(b["laws"]) | set(b["duplicates"].values()))
        pushes = [push_verdict(comp, lid, exp["laws"][lid], fam, v) for lid in lids]
        covered = any(x["pushed"] for x in pushes)
        lens = sorted({len(X.layout_at(fs[pid.split(".", 1)[1]], v)), len(X.layout_at(fs[qid.split(".", 1)[1]], v))})
        els.append({"kind": "observed", "p": pid, "q": qid, "version": v, "atoms": sorted(a["id"] for a in g),
                    "family": fam, "blind": blind_decoders(comp, fam, lens, v), "pushes": pushes,
                    "laws": [x["law"] for x in pushes if x["pushed"]],
                    "covered": covered, "reason": None if covered else "non_injective"})
    for a in sorted((a for a in ats if a["level"] == "E2"), key=lambda a: a["id"]):
        e, d = edges[a["p"]], edges[a["q"]]
        cv = P.common_versions([e, d])
        if cv == []:
            excluded.append({"atom": a["id"], "p": a["p"], "q": a["q"], "reason": "no_common_version"})
            continue
        for v in (cv if cv is not None else [None]):
            if (a["p"], a["q"], v) in inv:
                continue
            lay = X.layout_at(fs[e["model_fn"]], v)
            rd = fs[d["model_fn"]]["read"]
            cells = [lay[i] if i < len(lay) else ["unknown"] for i in range(rd["offset"], rd["offset"] + rd["width"])]
            kind = "constant_read" if all(c[0] == "const" for c in cells) else "partial_read"
            el = {"kind": kind, "p": a["p"], "q": a["q"], "version": v, "atoms": [a["id"]], "laws": [],
                  "covered": False, "reason": "no_rule"}
            if kind == "constant_read":
                el["bytes"] = "0x" + bytes(c[1] for c in cells).hex()
            els.append(el)
    for a in sorted((a for a in ats if a["level"] in ("E3", "E4", "E5")), key=lambda a: a["id"]):
        els.append({"kind": "other", "p": a["p"], "q": a["q"], "version": a["via"].get("version"),
                    "atoms": [a["id"]], "laws": [], "covered": False, "reason": "no_rule"})
    order = {k: i for i, k in enumerate(KINDS)}
    els.sort(key=lambda x: (order[x["kind"]], x["p"], x["q"], -1 if x["version"] is None else x["version"]))
    e6 = [a for a in ats if a["level"] == "E6"]
    with_law = sorted({b["key"]["atom"] for b in weak if b["laws"] or b["duplicates"]})
    return els, excluded, {"atoms": len(e6), "with_law": len(with_law)}


# ------------------------------------------------------------------ L6 HASH candidates
def hash_candidates(comp: dict, diag: dict, ats: list[dict]) -> list[dict]:
    fs = comp["functions"]
    out = []
    for h in sorted((e for e in diag["edges"] if e["kind"] == "HASH"), key=lambda e: e["id"]):
        names = sorted(n for n, f in fs.items() if (f.get("sink") or {}).get("op") == h["tgt"] and f["to"] == h["src"])
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                pair = [f"CODEC.{a}", f"CODEC.{b}"]
                ev = sorted(x["id"] for x in ats if {x["p"], x["q"]} == set(pair))
                out.append({"hash": h["id"], "pair": pair, "sinks": [fs[a]["sink"]["stack"][0], fs[b]["sink"]["stack"][0]],
                            "evidenced": bool(ev), "atoms": ev})
    return out


# ------------------------------------------------------------------ L8 the per-component document
def coverage(els: list[dict]) -> dict:
    n = len(els)
    c = sum(1 for x in els if x["covered"])
    return {"elements": n, "covered": c, "rate": (c / n) if n else None,
            "by_kind": {k: {"elements": sum(1 for x in els if x["kind"] == k),
                            "covered": sum(1 for x in els if x["kind"] == k and x["covered"])} for k in KINDS},
            "uncovered": [{"kind": x["kind"], "p": x["p"], "q": x["q"], "version": x["version"], "reason": x["reason"]}
                          for x in els if not x["covered"]]}


def analyse(comp: dict, diag: dict, ats: list[dict], milestone: str = "M3") -> dict:
    exp = X.expected(comp, diag, ats, milestone)
    els, excluded, weak = elements(comp, diag, ats, exp)
    collisions, uncertified = [], []
    for el in els:
        if el["kind"] != "observed":
            continue
        for x in el["pushes"]:
            if not x["pushed"]:
                law = exp["laws"][x["law"]]
                cert = certificate(comp, x["law"], law, el["family"], el["version"], x)
                if cert is None:
                    uncertified.append(x["law"])
                else:
                    collisions.append(cert)
    return {"lossy_version": LOSSY_VERSION, "document": "par_lossy", "milestone": milestone,
            "model": comp["component"], "facts": X.facts_path(comp["component"], milestone),
            "fragment": fragment(comp, diag), "elements": els, "excluded": excluded, "weak": weak,
            "hash_candidates": hash_candidates(comp, diag, ats), "collisions": sorted(collisions, key=lambda c: c["law"]),
            "uncertified": sorted(uncertified), "coverage": coverage(els)}


# ------------------------------------------------------------------ L9 the evidence review
def record_files(root: Path = ROOT, ref_dir: Path = REF_DIR) -> list[Path]:
    root = Path(root)
    return sorted((root / ref_dir).glob("*.json")) + sorted((root / ref_dir / "historical").glob("*.json"))


def disagreements_of(rec: dict) -> list[tuple[str, str | None]]:
    """(disagreement id, edge) pairs of one refinement record: a per-edge record's disagreement_ids at its
    diagram_edge; a step record's (kind "extracted") disagreements, each at TRANS.<its action> when it names one."""
    if isinstance(rec.get("disagreement_ids"), list):
        return [(d, rec.get("diagram_edge")) for d in rec["disagreement_ids"]]
    if rec.get("kind") == "extracted" and isinstance(rec.get("disagreements"), list):
        return [(d["id"], f"TRANS.{d['action']}" if d.get("action") else None) for d in rec["disagreements"]]
    return []


def review(root: Path, files: list[Path], analyses: dict[str, tuple[dict, dict]], evidence_sha256: str) -> list[dict]:
    """analyses: {model: (analysis, diagram)}. One entry per disagreement whose (facts, edge) resolves to no endpoint
    (p, q or a family decoder) of a covered element of a component, sorted by id."""
    root = Path(root)
    edges, covered = {}, set()
    for model, (an, diag) in analyses.items():
        for e in diag["edges"]:
            if e.get("component"):
                edges[(e["component"], e["id"])] = e["id"]
        comp_of = {e["id"]: e.get("component") for e in diag["edges"]}
        for el in an["elements"]:
            if el["covered"]:
                for eid in [el["p"], el["q"]] + el.get("family", []):
                    covered.add((comp_of.get(eid), eid))
    out = []
    for f in files:
        rel = Path(f).resolve().relative_to(root.resolve()).as_posix()
        rec = load_json(f)
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
    """spec/<M>/evidence_review.jsonl: one json.dumps(entry, sort_keys=True) line per entry; empty when none."""
    return "".join(json.dumps(e, sort_keys=True) + "\n" for e in entries)


# ------------------------------------------------------------------ L8 the metric
def metric(analyses: list[dict], entries: list[dict], evidence_sha256: str | None) -> dict:
    """evidenced_pair_coverage of results/<M>/metrics.json; evidence_sha256 is the evidence set's at build time (the
    sidecar records None: the set's sorts_sha256, and so its evidence_sha256, may change with I30 while the component
    atoms do not)."""
    els = [x for an in analyses for x in an["elements"]]
    cov = coverage(els)
    return {"evidence": {"path": EVIDENCE.as_posix(), "evidence_sha256": evidence_sha256},
            "relative_to": RELATIVE_TO,
            "elements": cov["elements"], "covered": cov["covered"], "rate": cov["rate"], "by_kind": cov["by_kind"],
            "uncovered": len(cov["uncovered"]),
            "excluded": {"no_common_version": sum(len(an["excluded"]) for an in analyses)},
            "weak": {"atoms": sum(an["weak"]["atoms"] for an in analyses),
                     "with_law": sum(an["weak"]["with_law"] for an in analyses)},
            "hash_candidates": sum(len(an["hash_candidates"]) for an in analyses),
            "uncovered_disagreements": len(entries),
            "models": sorted(an["model"] for an in analyses)}


# ------------------------------------------------------------------ the frozen sidecar
def _inputs(root: Path, paths: list[str]) -> list[dict]:
    return [{"path": p, "sha256": file_sha256(Path(root) / p)} for p in sorted(set(paths))]


def frozen_atoms_agree(root: Path = ROOT) -> bool:
    """Whether the committed evidence set's atoms of the Morph component are exactly rule X7's (I24): the evidence set
    is frozen, and every element of rule L2 is computed from those atoms."""
    comp, diag, ats = component(root)
    ev = load_json(Path(root) / EVIDENCE)
    committed = sorted((a for a in ev["atoms"] if a["model"] == comp["component"]), key=lambda a: a["id"])
    return canonical_json(committed) == canonical_json(sorted(ats, key=lambda a: a["id"]))


def review_now(root: Path = ROOT) -> tuple[list[dict], list[str], int]:
    """Rule L9 over the refinement records committed now: (entries, record paths, disagreements listed)."""
    root = Path(root)
    comp, diag, ats = component(root)
    an = analyse(comp, diag, ats, "M3")
    files = record_files(root)
    ev = load_json(root / EVIDENCE)
    entries = review(root, files, {comp["component"]: (an, diag)}, ev["evidence_sha256"])
    rels = [Path(f).resolve().relative_to(root.resolve()).as_posix() for f in files]
    return entries, rels, sum(len(disagreements_of(load_json(f))) for f in files)


def par_lossy_doc(root: Path = ROOT) -> dict:
    """The content of spec/M3/lib/par_lossy.json: every value the contract predicts that depends only on the inputs
    listed (adoption, link roles, lexicon, the adopted documents, the fixtures). The evidence set and the refinement
    records are not inputs: the component's atoms are recomputed by rule X7 (test_the_frozen_evidence_set_is_rule_x7s
    checks the committed set holds exactly them), and the review is recomputed over the records at build time
    ("review_at_prereg" records what it gave at the prereg)."""
    root = Path(root)
    comp, diag, ats = component(root)
    an = analyse(comp, diag, ats, "M3")
    fixtures = {}
    for fx in (FIX_INJ, FIX_NONINJ):
        c2, d2, a2 = component(root, fx["adoption"], fx["link"], fx["role"])
        fixtures[fx["milestone"]] = {"adoption": fx["adoption"], "link": fx["link"], "role": fx["role"],
                                     "analysis": analyse(c2, d2, a2, fx["milestone"])}
    docs = list(load_json(root / X.ADOPTION)["documents"])
    inputs = _inputs(root, [X.ADOPTION.as_posix(), X.LINK.as_posix(), "spec/M2/lib/evidence_lexical.json", *docs,
                            FIX_INJ["adoption"], FIX_INJ["link"], FIX_NONINJ["adoption"], FIX_NONINJ["link"],
                            "tests_m3/fixtures/par_lossy/codec.go.extracted.json",
                            "tests_m3/fixtures/par_linked/codec.go.extracted.json",
                            "tests_m3/fixtures/par_linked/sol.extracted.json"])
    d7_hits = sorted(d for d in docs if any(k in (root / d).read_text() for k in D7_FILES))
    entries, rels, n = review_now(root)
    return {"par_lossy_version": LOSSY_VERSION,
            "doc": ("I25 prereg sidecar (frozen): every value the I25 contract (tests_m3/test_par_lossy.py, rules L0-L9) "
                    "predicts, computed at the prereg by tests_m3/_i25.py::par_lossy_doc from the inputs listed with "
                    "their sha256 and nothing else. morph: the component header_length (I24 rules X1-X7 over the "
                    "adopted extracted documents), I24's PAR basis over it recomputed by tests_m3/_i24x.py::expected, "
                    "and rules L1-L6 and L8 over that. fixtures: the same for the planted variant T251 "
                    "(tests_m3/fixtures/par_lossy/: its version-1 pair becomes injective) and I24's linked fixture as "
                    "T252 (non-injective at versions 1 and 2). core: the "
                    "statements of rule L7, checked at the prereg as well-typed open laws (bend reports exactly 3 "
                    "TODOs and no other error; no proof was attempted). metric: rule L8's evidenced_pair_coverage, "
                    "evidence_sha256 left null (it is the evidence set's at build time). review_at_prereg: rule L9 "
                    "over the 15 refinement records of results/M2/refinement/ as committed at the prereg (not an "
                    "input; recomputed at build time). deferred: D7, outside today's extraction (instance I36). "
                    "Recompute: python -c 'import json; from tests_m3 import _i25; "
                    "print(json.dumps(_i25.par_lossy_doc(), indent=2, sort_keys=True))'."),
            "inputs": inputs,
            "core": {"laws": CORE, "canary": CANARY},
            "morph": {"model": comp["component"], "analysis": an},
            "fixtures": fixtures,
            "metric": metric([an], entries, None),
            "review_at_prereg": {"records": rels, "disagreements": n, "entries": entries},
            "deferred": [dict(D7, adopted_documents_mentioning_it=d7_hits)]}
