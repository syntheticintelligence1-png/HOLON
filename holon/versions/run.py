"""Rule PI6: `python -m holon run --milestone M --laws <id>,..` decides the PAR-init laws (rule PAR, sub-form
init_chain) it names, over the versioned model (holon.__main__ routes them here; every other law of the list goes on as
before).

The search (sidecar search.par_init): the path versions in path order, at each the traces by length up to max_trace from
vr0 whose last step is the root step at that version, every earlier step one of the candidates in this order: the
migration along the path's next edge by the proxy admin (upgradeToAndCall with the reinitializer it introduces and the
sidecar's upgrade_path arguments, else upgradeTo), then the deployment record's calls whose selector names an action of
the state's version, each by its recorded caller with its recorded calldata. The root step is the deployment record's
first call of the root site's action, by its recorded caller, with the bytes its root site hashes changed so that the
chained cell holds the increment cell's value plus one. A witness is a trace whose root step succeeds (its input then has
cell o != cell o'; holon.versions.machine evaluates the model). Its counter-law (LAWS.bend over the layer, PROOF.bend
importing it as Laws: holon.versions.proofs) is checked by Bend and, when the verdict is enabled, BendTT (AGENTS rule 6):
both accept, REFUTED; otherwise the law is UNKNOWN with what was tried. No generator proves an init_chain law.

Outputs: <results>/<id>.json (the M3 record fields, v1 and v2), gen/<M>/laws/<id>/LAWS.bend and gen/<M>/proofs/<id>/
PROOF.bend. No lean4 entry: no Lean emitter reads the versioned document.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from . import Ctx, Refused, VersionsError
from .machine import Machine, cd_bytes, num

GEN_VERSIONS = ["holon/versions/run.py", "holon/versions/machine.py", "holon/versions/model.py",
                "holon/versions/proofs.py", "holon/versions/bendlit.py", "holon/versions/paths.py",
                "holon/rules/par_init.py"]


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def generator_sha256(root: Path) -> str:
    """The digest of the PAR-init deciders' closure: this module, its holon imports and I30's runner closure."""
    from ..records import _holon_imports
    from ..sorts.run3 import GEN3
    seen, todo = set(), list(GEN_VERSIONS) + list(GEN3)
    while todo:
        r = todo.pop()
        if r in seen or not (root / r).is_file():
            continue
        seen.add(r)
        if r.endswith(".py"):
            todo.extend(sorted(_holon_imports(r, root) - seen))
    h = hashlib.sha256()
    for r in sorted(seen):
        h.update(r.encode() + b"\0" + (root / r).read_bytes() + b"\0")
    return h.hexdigest()


def _arg(argv: list, name: str):
    for i, x in enumerate(argv):
        if x == name and i + 1 < len(argv):
            return argv[i + 1]
        if x.startswith(name + "="):
            return x.split("=", 1)[1]
    return None


def init_entries(milestone: str, root: Path) -> dict:
    try:
        dv = json.loads((Path(root) / "laws" / milestone / "DERIVATION.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    from ..rules.par_init import RULE, SUBFORM
    return {e["law_id"]: e for e in dv.get("laws") or []
            if isinstance(e, dict) and e.get("rule") == RULE and e.get("subform") == SUBFORM}


def ids_of(argv: list, root: Path | None = None):
    """(the PAR-init law ids, the other ids) of a `run --laws` argv, or None when it names none."""
    from . import ROOT
    m, laws = _arg(argv, "--milestone"), _arg(argv, "--laws")
    if argv[:1] != ["run"] or not m or not laws:
        return None
    ids = [x.strip() for x in laws.split(",") if x.strip()]
    mine = init_entries(m, Path(_arg(argv, "--root") or root or ROOT))
    vids = [i for i in ids if i in mine]
    if not vids:
        return None
    return vids, [i for i in ids if i not in mine]


def strip_args(argv: list, names: tuple) -> list:
    out, skip = [], False
    for x in argv:
        if skip:
            skip = False
            continue
        if x in names:
            skip = True
            continue
        if any(x.startswith(n + "=") for n in names):
            continue
        out.append(x)
    return out


# ------------------------------------------------------------------------------------------------ the search
def root_input(m: Machine, vid: str, element: dict) -> tuple[dict, str] | None:
    """(the recorded call, the root step's calldata): the deployment record's first call of the root action, its bytes
    parameter (the root site's hashed bytes) with the chained cell set to the increment cell's value plus one."""
    from .bendlit import Lit
    action = element["root_action"]
    fn = m.function(vid, action)
    if fn is None:
        return None
    sel = fn["selector"].removeprefix("0x")
    rec = next((c for c in m.dep.get("calls") or [] if c["data"][2:10] == sel), None)
    if rec is None:
        return None
    hashed = m.root_bytes_param(vid, element)
    if hashed is None:
        return None
    data = bytearray(cd_bytes(rec["data"]))
    idx = [p.get("name") for p in fn["inputs"]].index(hashed)
    nodes = Lit("M").leaves(fn["inputs"], rec["data"])
    if nodes[idx][0] != "b":
        return None
    # the parameter's tail: its offset word in the head, then its length, then its bytes
    off = 4 + int.from_bytes(data[4 + 32 * idx:4 + 32 * (idx + 1)], "big")
    n = int.from_bytes(data[off:off + 32], "big")
    h = bytearray(data[off + 32:off + 32 + n])
    width = 32 - element["shift"] // 8
    o, o2 = element["cell"], element["incr"]
    pad = lambda b: bytes(b) + bytes(max(0, width - len(b)))     # noqa: E731
    incr = int.from_bytes(pad(h[o2:o2 + width]), "big")
    new = ((incr + 1) % (1 << (8 * width))).to_bytes(width, "big")
    if o + width > len(h):
        return None
    h[o:o + width] = new
    data[off + 32:off + 32 + n] = h
    return rec, "0x" + bytes(data).hex()


def candidates(m: Machine, state: dict) -> list:
    """The candidate steps at a state (before the root step), in search order."""
    from .paths import migration
    out = []
    v = state["version"]
    nxt = [b for (a, b) in sorted(m.edges) if a == v]
    if nxt:
        out.append(migration(m, v, nxt[0], m.ctx.side["upgrade_path"]["arguments"], state))
    if v in m.path:
        for c in m.dep.get("calls") or []:
            for name in m.actions(v):
                fn = m.function(v, name)
                if fn and fn["selector"] and c["data"][2:10] == fn["selector"].removeprefix("0x"):
                    out.append(m.call_step(v, name, num(c["caller"]), c["data"]))
    return out


def search(m: Machine, element: dict, budget: dict) -> tuple[list | None, list, dict]:
    """(the witness trace or None, the trace's outcomes, what was tried)."""
    max_trace = int(budget.get("max_trace", 4))
    tried = {"versions": [], "traces": 0, "root_steps": 0}
    for vid in m.path:
        if element["root_action"] not in m.actions(vid):
            continue
        ri = root_input(m, vid, element)
        if ri is None:
            continue
        rec, cd = ri
        root = m.call_step(vid, element["root_action"], num(rec["caller"]), cd)
        tried["versions"].append(vid)
        frontier = [([], m.initial())]
        for length in range(1, max_trace + 1):
            for prefix, state in frontier:
                if state["version"] != vid:
                    continue
                tried["traces"] += 1
                tried["root_steps"] += 1
                o = m.step(state, root)
                if o["status"] == "ok":
                    trace = prefix + [root]
                    outs, _kh, _sh = m.run(trace)
                    return [dict(st, ok=x["status"] == "ok") for st, x in zip(trace, outs)], outs, tried
            if length == max_trace:
                break
            nxt = []
            for prefix, state in frontier:
                for st in candidates(m, state):
                    o = m.step(state, st)
                    nxt.append((prefix + [dict(st, ok=o["status"] == "ok")], o["state"]))
            frontier = nxt
    return None, [], tried


# ------------------------------------------------------------------------------------------------ deciding
class Decider:
    def __init__(self, ctx: Ctx, results: Path, gen: Path):
        self.ctx = ctx
        self.root = ctx.root
        self.results = results
        self.gen = gen
        self.m = Machine(ctx)
        from .. import ir
        self.registry = ir.load_registry(ctx.milestone, self.root)
        self.entries = init_entries(ctx.milestone, self.root)

    def close(self):
        self.m.close()

    def rel(self, p: Path) -> str:
        p = Path(p)
        try:
            return (p.parent.resolve() / p.name).relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return p.as_posix()

    def model_path(self) -> Path:
        return self.root / self.ctx.out("model_dir") / f"{self.ctx.model}.bend"

    def import_path(self) -> Path:
        from .model import stem
        return self.root / self.ctx.out("model_dir") / f"{stem(self.ctx.model)}.bend"

    def check(self, proof: Path) -> dict:
        from .. import bend
        r = bend.check(proof)
        out = {"exit_code": r.code, "marker": r.marker, "seconds": r.seconds}
        verdict = "not_run"
        if r.ok and bend.verdict_enabled():
            v = bend.check_verdict(proof)
            verdict = "checked" if v.ok else "failed"
            out["verdict"] = {"exit_code": v.code, "marker": v.marker, "seconds": v.seconds}
        return {"checker": out, "ok": r.ok and verdict != "failed", "verdict": verdict,
                "detail": (r.out or "")[-1500:] if not r.ok else ""}

    def decide(self, lid: str) -> dict:
        from . import proofs as P
        from ..bend import escape_hatches
        t0 = time.monotonic()
        law = json.loads((self.root / "laws" / self.ctx.milestone / f"{lid}.json").read_text(encoding="utf-8"))
        e = self.entries.get(lid)
        if e is None:
            raise Refused(f"{lid} is not a PAR-init law of {self.ctx.milestone}")
        element = e["basis"]
        sh = self.registry["statements"][lid]
        claims = (self.m.init.get("layer") or {}).get("claims") or {}
        claim = P.claim_of(self.m.init, element)
        laws_dir = self.gen / "laws" / lid
        proof_dir = self.gen / "proofs" / lid
        laws_dir.mkdir(parents=True, exist_ok=True)
        lp = laws_dir / "LAWS.bend"
        attempts, witness, prim, status = [], None, None, "UNKNOWN"
        budget = (self.ctx.side.get("search") or {}).get("par_init") or {}
        if claim is None:
            attempts.append({"kind": "refute", "engine": "holon.versions.run", "found": False,
                             "reason": "the versioned model has no claim function for this basis element: "
                                       + "; ".join((claims.get(element["init_id"]) or {}).get("debt") or ["none"])})
        else:
            trace, outs, tried = search(self.m, element, budget)
            attempts.append({"kind": "refute", "engine": "holon.versions.run", "found": trace is not None,
                             "budget": {"max_trace": int(budget.get("max_trace", 4)), "order": budget.get("order")},
                             "bound": f"{tried['traces']} traces at versions {', '.join(tried['versions'])}"})
            if trace is not None:
                _outs, kh, _sh = self.m.run(trace)
                lp.write_text(P.law_file(law, self.ctx.milestone, self.root, sh, True, self.gen), encoding="utf-8")
                proof_dir.mkdir(parents=True, exist_ok=True)
                pp = proof_dir / "PROOF.bend"
                pp.write_text(P.counter_proof(law, self.m, P.rel_import(proof_dir, self.import_path()),
                                              P.rel_import(proof_dir, lp), claim, trace, outs, kh), encoding="utf-8")
                hits = escape_hatches(pp.read_text(encoding="utf-8"))
                chk = self.check(pp)
                attempts.append({"kind": "counter", "evaluator": "the claim is false at the witness",
                                 "checker": chk["checker"], "verdict": chk["verdict"] if chk["ok"] else "failed"})
                if chk["ok"] and not hits:
                    status = "REFUTED"
                    last = trace[-1]
                    witness = {"trace": trace, "root": {k: last[k] for k in ("version", "action", "caller",
                                                                              "calldata")}}
                    prim = {"proof": self.rel(pp), "checker": chk["checker"], "verdict": chk["verdict"]}
                else:
                    attempts[-1]["detail"] = chk["detail"] or f"escape hatches {hits}"
        if status != "REFUTED":
            lp.write_text(P.law_file(law, self.ctx.milestone, self.root, sh, False, self.gen), encoding="utf-8")
            pp = proof_dir / "PROOF.bend"
            if pp.exists():
                pp.unlink()
        rec = self.record(law, e, status, witness, attempts, lp, prim, sh)
        rec["seconds"] = round(time.monotonic() - t0, 3)
        return rec

    def record(self, law: dict, e: dict, status: str, witness: dict | None, attempts: list, lp: Path,
               prim: dict | None, sh: str) -> dict:
        from .. import records as R
        from . import replay as VR
        from .proofs import law_name
        lid = law["law_id"]
        model_text = self.import_path().read_text(encoding="utf-8")
        st_text = lp.read_text(encoding="utf-8")
        cone = R.cone(st_text, model_text)
        rec = {"law_id": lid, "statement_hash": sh, "facts_sha256": law["facts_sha256"], "status": status,
               "scope": "unbounded", "premises": [],
               "kernel": {"name": "bend", "version": bend_version(), "verdict": (prim or {}).get("verdict", "not_run")},
               "artifacts": {"laws": self.rel(lp), "proof": (prim or {}).get("proof"), "model": self.rel(self.model_path()),
                             "law_name": law_name(lid, status == "REFUTED")},
               "checker": (prim or {}).get("checker") or {"exit_code": None, "marker": "not_run"},
               "triage": "finding" if status == "REFUTED" else "none",
               "replay": (VR.replay_status(self.ctx, VR.load(self.ctx), lid, witness) if status == "REFUTED" else
                          {"status": "not_applicable", "detail": f"{status}: no witness to replay"}),
               "attempts": attempts, "rule": law["rule"], "subform": law["subform"], "witness": witness,
               "bound": None if status != "UNKNOWN" else "; ".join(a.get("bound") or a.get("reason") or ""
                                                                    for a in attempts if a["kind"] == "refute")}
        if status == "REFUTED":
            rec["difference"] = {"lhs": False, "rhs": True}
        try:
            b, match = R.resolve_bundle(rec["facts_sha256"], law["facts"], self.root, model_text, set(cone),
                                        self.ctx.milestone)
            assumptions = R.model_assumptions(b["facts_sha256"], set(cone), self.root, law["facts"])
        except R.LedgerError:
            match, assumptions = "none", []
        vid = (witness or {}).get("root", {}).get("version") or self.m.path[0]
        rec.update({"record_version": R.RECORD_VERSION, "prover": "generator",
                    "model_sha256": sha256_file(self.import_path()),
                    "compiled_sha256": sha256_file(self.m.evaluator(vid).compiled()),
                    "generator_sha256": generator_sha256(self.root), "cone": cone, "ledger_match": match,
                    "model_assumptions": assumptions, "scope_v2": R.scope_v2(law, rec), "kernels": R.kernels(rec),
                    "independence_class": R.independence_class(rec), "refinement_refs": [],
                    "coverage": None,
                    "non_vacuity": {"status": "counter_witness" if status == "REFUTED" else "unknown",
                                    "law": self.rel(lp) if status == "REFUTED" else None, "witness": None,
                                    "reachable": None, "degenerate": None, "parent_statement_hash": sh,
                                    "bound": "the accepted counter-law inhabits the premises" if status == "REFUTED"
                                    else "no proof"},
                    "witness_provenance": {"solidity": "internal_harness"} if status == "REFUTED" else None,
                    "filter_bin": "finding" if status == "REFUTED" else None,
                    **R.evidence_fields(law, {"status": status}, self.root)})
        rec["ledger_assumptions"] = sorted(rec["model_assumptions"])
        rec["model_assumptions"] = []
        rec["statement"] = law.get("notes", "")
        return rec


def bend_version() -> str:
    from ..sorts.run3 import bend_version as bv
    return bv()


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="holon run (PAR-init laws)")
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--laws", required=True)
    ap.add_argument("--root")
    ap.add_argument("--out", help="the results directory (default results/<M>)")
    ap.add_argument("--gen-dir", help="the generated files' directory (default gen/<M>)")
    a, _rest = ap.parse_known_args(argv)
    from . import ROOT
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        ctx = Ctx(root, f"spec/{a.milestone}/lib/versions.json")
        results = Path(a.out) if a.out else root / "results" / a.milestone
        gen = Path(a.gen_dir) if a.gen_dir else root / "gen" / a.milestone
        d = Decider(ctx, results, gen)
        try:
            rc = 0
            for lid in [x.strip() for x in a.laws.split(",") if x.strip()]:
                rec = d.decide(lid)
                results.mkdir(parents=True, exist_ok=True)
                (results / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
                print(f"{lid}: {rec['status']} ({rec['seconds']} s)")
        finally:
            d.close()
        return rc
    except Refused as e:
        print(f"holon run: refused: {e}", file=sys.stderr)
        return 2
    except VersionsError as e:
        print(f"holon run: error: {e}", file=sys.stderr)
        return 3
