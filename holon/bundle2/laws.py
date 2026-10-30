"""Bundle II's laws: the analysis, the claims modules and the planted-ceiling construction (BUILD_PLAN row I84 = I37b;
the contract is the docstring of tests_m3/test_bundle2_laws.py, rules LD1-LD5, FC1-FC3, FP1-FP4, FM1-FM3, D1-D6 and
RC1-RC2).

  python -m holon bundle2 laws [--check] [--root DIR] [--work DIR]

writes the bundle-laws sidecar's outputs.analysis (gen/M3/bundle2/laws.json) and the claims modules under its
outputs.claims_dir:

  the analysis   the inputs (path -> sha256), the laws' deployment (one forge run of the law replay harness with no
                 step: each member's address, storage, code and immutables, the harness, the clock and the chain), the
                 consumers (FC1-FC2), and per law of the three sub-forms its basis (holon.rules.bundle2), the claim's
                 compiled document terms, and: link_domain the callee's resolution action and, once its record is
                 REFUTED, the witness's (version, index); public_input the measure (FM1); self_controlled the
                 calibration's coefficients (exact, refitted from the record's raw points), G, k*_model (D3) and the
                 kernel budget
  rollup.bend    the adopted member's typed model at the laws' deployment (holon.bundle2.laws_claims)
  claims.bend    the claims section (holon.bundle2.laws_claims), importing it as M and the callee's model as V

planted_ceiling(root, law_id, out) is D6: the self_controlled claim with the ceiling c0 + 2 * c1 - 1 (so k* = 2),
decided in out (outside the repository) by holon.bundle2.laws_decide's strategy search and counter-law.

Everything specific to a target comes from the sidecars, the declaration, the documents and the compiler's output.
Exit codes: 0 written (or --check reproduced), 1 --check differs, 2 refused, 3 a harness or model error.
"""
from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

from . import ROOT, BundleError, Refused, Writer, file_sha, render
from ..rules import bundle2 as RB

LAWS_SIDECAR = "spec/M3/lib/bundle2_laws.json"
ANALYSIS_VERSION = "holon-bundle2-laws-analysis/0.1"


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


class LawsCtx:
    """The bundle-laws sidecar, its inputs, the analysis of holon.rules.bundle2 and the output paths."""

    def __init__(self, root: Path, milestone: str = "M3"):
        self.root = Path(root)
        self.m = milestone
        try:
            self.I = RB.Inputs(milestone, self.root)
            self.laws = RB.analyse(self.I)
        except (OSError, ValueError, KeyError) as e:
            raise Refused(f"the bundle laws' inputs: {type(e).__name__}: {e}") from e
        self.side = self.I.side
        out = self.side["outputs"]
        self.analysis_path = self.root / out["analysis"]
        self.claims_dir = self.root / out["claims_dir"]
        self.cal_path = self.root / out["calibration"]
        self.replay_path = self.root / out["replay"]
        self.doc_rel = self.I.rollup_rel
        self.caller = next(n for n, m in self.I.members.items() if m["document"]["path"] == self.doc_rel)

    # ---------------------------------------------------------- inputs
    def inputs(self) -> dict:
        inp = self.side["inputs"]
        keys = sorted(k for k in inp if k not in ("declaration", "refute_sidecar"))
        out = {inp[k]: file_sha(self.root / inp[k]) for k in keys}
        out[RB.sidecar_path(self.m, self.root).relative_to(self.root).as_posix()] = file_sha(
            RB.sidecar_path(self.m, self.root))
        out[inp["declaration"]] = file_sha(self.root / inp["declaration"])
        if self.cal_path.is_file():
            out[self.cal_path.relative_to(self.root).as_posix()] = file_sha(self.cal_path)
        return dict(sorted(out.items()))

    def calibration(self) -> dict | None:
        return json.loads(self.cal_path.read_text(encoding="utf-8")) if self.cal_path.is_file() else None

    def callee_doc(self, member: str) -> dict:
        return self.I.document(member)

    def callee_model(self, member: str) -> Path:
        """The callee's committed model (I80's models.json entry)."""
        side = json.loads((self.root / self.side["inputs"]["bundle_sidecar"]).read_text(encoding="utf-8"))
        mp = self.root / side["outputs"]["models"] / "models.json"
        ms = json.loads(mp.read_text(encoding="utf-8"))
        e = (ms.get("models") or {}).get(member)
        if e is None:
            raise Refused(f"{mp.relative_to(self.root)} has no model of {member}")
        return self.root / e["path"]

    def committed_deployment(self) -> dict:
        if not self.analysis_path.is_file():
            raise Refused(f"{self.analysis_path.relative_to(self.root)} is missing (run holon bundle2 laws)")
        an = json.loads(self.analysis_path.read_text(encoding="utf-8"))
        return an["deployment"]


# ------------------------------------------------------------------------------------------------ the claims' terms
def call_record(action: dict, fn: str) -> dict:
    hits = [c for c in action.get("calls") or [] if c.get("fn") == fn]
    if len(hits) != 1:
        raise Refused(f"{action['name']} has {len(hits)} call records of {fn}, not one")
    return hits[0]


def resolver(callee_doc: dict, target: str) -> str:
    """The callee's action whose returns term is the receiver of the target action's committed external call."""
    acts = {a["name"]: a for a in callee_doc["actions"]}
    t = acts.get(target)
    if t is None:
        raise Refused(f"the callee has no action {target}")
    recv = [c["receiver"] for c in t.get("calls") or [] if c.get("commit") and c.get("receiver") is not None]
    hits = sorted(n for n, a in acts.items() if n != target and a.get("returns") is not None and a["returns"] in recv)
    if len(hits) != 1:
        raise Refused(f"{len(hits)} actions of the callee resolve the receiver of {target}'s call, not one")
    return hits[0]


def view_hash_index(I, entry: dict) -> int:
    b = entry["basis"]
    for r in I.decl.get("public_input") or []:
        if (r["member"], r["action"], r["src"]) == (b["member"], b["action"], b["src"]):
            idx = [i for i, x in enumerate(r["args"]) if isinstance(x, dict) and x.get("hash")]
            if len(idx) == 1:
                return idx[0]
    raise Refused(f"{b['action']}: no public-input view with one hash argument")


def terms(ctx: LawsCtx, lid: str, e: dict) -> dict:
    """The compiled document terms of a law's claim (from the action's call record and the basis)."""
    acts = RB.actions(ctx.I.rollup)
    b = e["basis"]
    a = acts[b["action"]]
    if e["subform"] == "link_domain":
        c = call_record(a, b["fn"])
        return {"version": c["args"][0], "index": c["args"][1], "cond": c.get("cond", 1)}
    if e["subform"] == "public_input":
        c = call_record(a, _view_fn(ctx, e))
        recv = b["input"]
        con = b["consumer"]
        off, w = int(con["offset"]), int(con["width"])
        return {"pi": c["args"][view_hash_index(ctx.I, e)], "field": [">>", ["word", recv, off], 256 - 8 * w],
                "has": [">=", ["len", recv], off + w]}
    return {}


def _view_fn(ctx: LawsCtx, e: dict) -> str:
    b = e["basis"]
    for r in ctx.I.decl.get("public_input") or []:
        if (r["member"], r["action"], r["src"]) == (b["member"], b["action"], b["src"]):
            return r["fn"]
    raise Refused(f"{b['action']}: no public-input view")


def cost_coefficients(cal: dict | None) -> tuple | None:
    """(c0, c1) as exact rationals refitted from the calibration record's raw points, or None."""
    if not cal:
        return None
    from .laws_calibrate import exact
    return exact(cal)


def kstar(c0, c1, ceiling: int):
    from .laws_calibrate import k_star
    return k_star(c0, c1, ceiling)


# ------------------------------------------------------------------------------------------------ the claims modules
class Claims:
    """The typed model at the laws' deployment and the claims section, generated (and, for a search, evaluated)."""

    def __init__(self, ctx: LawsCtx, dep: dict, ceiling: int | None = None, out_dir: Path | None = None,
                 lids: list | None = None):
        from ..sorts.model3 import generate, model_name
        from ..sorts.typed_sidecar import load as load_typed
        from . import laws_claims as LC
        self.ctx, self.dep = ctx, dep
        self.dir = Path(out_dir) if out_dir else ctx.claims_dir
        root = ctx.root
        mem = self.member(ctx.caller)
        self.init = {"binding": None, "target": mem["address"], "harness": dep["harness"], "storage": mem["storage"],
                     "preimages": [], "immutables": dict(mem.get("immutables") or {}), "timestamp": dep["timestamp"],
                     "number": dep["number"], "chainid": dep["chainid"], "calls": [],
                     "code": {k: v for k, v in ((mem["address"], mem["code"]),
                                                (mem.get("implementation"), mem.get("implementation_code")))
                              if k and isinstance(v, str) and len(v) > 2}}
        origin = f"the laws' deployment ({RB.sidecar_path(ctx.m, root).relative_to(root).as_posix()})"
        self.text, self.mm = generate(ctx.m, root, ctx.doc_rel, typed=True,
                                      init={"storage": mem["storage"], "binding": origin})
        self.model_name = model_name(ctx.doc_rel)
        sc = load_typed(ctx.m, root, None)
        from ..sorts.model3 import load_doc_model
        self.docm = load_doc_model(root, ctx.doc_rel, sc.source(ctx.doc_rel))
        self.doc = ctx.I.rollup
        from ..rules.sort import hash_functions
        self.hashes = hash_functions(self.doc) or ["keccak256"]
        cal = ctx.calibration()
        co = cost_coefficients(cal)
        G = int(ceiling if ceiling is not None else ctx.I.ceiling)
        self.ceiling = G
        self.coeffs = co
        self.laws = {}
        for lid, e in ctx.laws.items():
            if lids is not None and lid not in lids:
                continue
            if e["subform"] == "self_controlled" and co is None:
                continue          # no calibration: no cost claim (D4: uncalibrated)
            self.laws[lid] = dict(e, terms=terms(ctx, lid, e))
        self.cost = {lid: LC.scaled(co[0], co[1], G) for lid, e in self.laws.items()
                     if e["subform"] == "self_controlled"}
        self.router = None
        ld = [e for e in self.laws.values() if e["subform"] == "link_domain"]
        if ld:
            callees = sorted({e["basis"]["callee"] for e in ld})
            targets = sorted({e["basis"]["target"] for e in ld})
            if len(callees) != 1 or len(targets) != 1:
                raise Refused("the link_domain laws name more than one callee or target")
            cm = self.member(callees[0])
            res = resolver(ctx.callee_doc(callees[0]), targets[0])
            nargs = len(next(a for a in ctx.callee_doc(callees[0])["actions"] if a["name"] == res).get("params") or [])
            self.router = {"member": callees[0], "storage": cm["storage"], "resolver": res,
                           "env": {"caller": 0, "length": 4 + 32 * nargs}}
            self.callee_model = ctx.callee_model(callees[0])
        self.model_path = self.dir / "rollup.bend"
        self.claims_path = self.dir / "claims.bend"
        mi = "./rollup.bend"
        vi = None
        if self.router is not None:
            from ..sorts.proofs3 import rel_import
            vi = rel_import(self.dir, self.callee_model)
        self.module = LC.module_text(self.mm, self.text, self.doc, self.hashes, self.laws, self.router, self.cost, mi,
                                     vi)
        self.combined = LC.combined_text(self.mm, self.text, self.doc, self.hashes, self.laws, self.cost)

    def member(self, name: str) -> dict:
        for m in self.dep["members"]:
            if m["name"] == name:
                return m
        raise Refused(f"the laws' deployment has no member {name}")

    def files(self) -> dict:
        return {self.model_path: self.text.encode("utf-8"), self.claims_path: self.module.encode("utf-8")}

    def write(self) -> None:
        for p, d in self.files().items():
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.is_file() or p.read_bytes() != d:
                p.write_bytes(d)


# ------------------------------------------------------------------------------------------------ the analysis
def analysis(ctx: LawsCtx, dep: dict, cl: Claims) -> dict:
    from ..rules.bundle2 import consumers
    out = {"analysis_version": ANALYSIS_VERSION, "milestone": ctx.m, "inputs": ctx.inputs(), "deployment": dep,
           "consumers": consumers(ctx.I), "claims": {"model": cl.model_path.relative_to(ctx.root).as_posix(),
                                                     "section": cl.claims_path.relative_to(ctx.root).as_posix()},
           "link_domain": {}, "public_input": {}, "self_controlled": {}}
    cal = ctx.calibration()
    for lid, e in ctx.laws.items():
        ent = {"bundle_id": e["bundle_id"], "action": e["action"], "basis": e["basis"]}
        if e["subform"] == "link_domain":
            ent["terms"] = terms(ctx, lid, e)
            ent["resolver"] = (cl.router or {}).get("resolver")
            ent["witness"] = link_witness(ctx, lid)
        elif e["subform"] == "public_input":
            ent["terms"] = terms(ctx, lid, e)
            ent["measure"] = e["measure"]
        else:
            ent["gas_ceiling"] = ctx.I.ceiling
            ent["kernel_budget_steps"] = int(ctx.side["o35"]["kernel_budget_steps"])
            ent["calibration"] = None if cal is None else {"status": cal["status"], "c0": cal["c0"], "c1": cal["c1"],
                                                           "max_error": cal["max_error"]}
            co = cost_coefficients(cal)
            if co is None:
                ent["k_star_model"] = None
                ent["coefficients"] = None
            else:
                ent["coefficients"] = {"c0": str(co[0]), "c1": str(co[1])}
                ent["k_star_model"] = kstar(co[0], co[1], ctx.I.ceiling)
        out[e["subform"]][lid] = ent
    return out


def link_witness(ctx: LawsCtx, lid: str) -> dict | None:
    """The (version, index) of a REFUTED link_domain law's witness, from its record (the router call's arguments by the
    view, as the record's witness states them)."""
    p = ctx.root / "results" / ctx.m / f"{lid}.json"
    if not p.is_file():
        return None
    rec = json.loads(p.read_text(encoding="utf-8"))
    w = (rec.get("bundle") or {}).get("link") if rec.get("status") == "REFUTED" else None
    if not w:
        return None
    return {"version": int(w["version"]), "index": int(w["index"])}


def capture(ctx: LawsCtx, work: Path | None) -> dict:
    from .laws_calibrate import Laws
    from .laws_forge import Forge
    L = Laws(ctx.root)
    return Forge(L.bctx, L.side, work).deployment()


def run_laws(root: Path, check: bool, work: Path | None = None) -> int:
    try:
        ctx = LawsCtx(root)
        dep = capture(ctx, work)
        cl = Claims(ctx, dep)
        an = analysis(ctx, dep, cl)
        w = Writer(check)
        w.put(ctx.analysis_path, render(an))
        for p, d in cl.files().items():
            w.put(p, d)
        n = {k: len(an[k]) for k in ("link_domain", "public_input", "self_controlled")}
        print(f"holon bundle2 laws: {n}; k*_model "
              f"{[v.get('k_star_model') for v in an['self_controlled'].values()]}")
        return w.finish("laws")
    except Refused as e:
        print(f"holon bundle2 laws: refused: {e}", file=sys.stderr)
        return 2
    except BundleError as e:
        print(f"holon bundle2 laws: error: {e}", file=sys.stderr)
        return 3


# ------------------------------------------------------------------------------------------------ D6
def planted_ceiling(root: Path, lid: str, out: Path) -> dict:
    """D6: the self_controlled law decided with the ceiling c0 + 2 * c1 - 1 in out (outside the repository): the
    strategy search at k*_model = 2 and its counter-law, checked by the pinned Bend. Returns {"status", "backlog",
    "ceiling", "checker", "witness"}."""
    from . import laws_decide as LD
    root, out = Path(root), Path(out)
    ctx = LawsCtx(root)
    e = ctx.laws.get(lid)
    if e is None or e["subform"] != "self_controlled":
        raise Refused(f"{lid} is not a self_controlled law of the analysis")
    co = cost_coefficients(ctx.calibration())
    if co is None:
        raise Refused("no calibration record")
    c0, c1 = co
    planted = c0 + 2 * c1 - 1
    if planted.denominator != 1:
        planted = Fraction(int(planted))       # a ceiling is a gas amount: the floor keeps k* = 2 for c1 >= 1
    G = int(planted)
    dep = ctx.committed_deployment()
    cl = Claims(ctx, dep, ceiling=G, out_dir=out / "claims", lids=[lid])
    cl.write()
    return LD.decide_self_controlled(ctx, cl, lid, out, planted=True)


def main_laws(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon bundle2 laws", description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--root")
    ap.add_argument("--work")
    a = ap.parse_args(argv)
    return run_laws(Path(a.root).resolve() if a.root else ROOT, a.check, Path(a.work) if a.work else None)

