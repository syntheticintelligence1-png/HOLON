"""`holon run` for the Go part of rule PAR (I93; contract rules G8-G11 of tests_m3/test_go_laws.py): decides each law of
holon.rules.gox from its DERIVATION entry's basis.

  go_round_trip   the law, proved by reflexivity (PROVED when the pinned bend accepts the proof).
  go_branch       the counter-law at G9's witness (bend accepts it) and the replay replay/<M>/gox/<law>.json agreeing,
                  its witness_sha256 the witness's: REFUTED; otherwise UNKNOWN.
  go_recompute    likewise, the counter-law by the length argument at G9's witness.

Files: gen/<M>/gox/<law>.bend (the module), gen/<M>/laws/<law>/LAWS.bend, gen/<M>/proofs/<law>/PROOF.bend; the record
results/<M>/<law>.json. A record made with the local (unpinned) checker is never committed (the landing makes them).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from . import model as G

ROOT = Path(__file__).resolve().parents[2]


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def witness_sha256(w) -> str:
    return hashlib.sha256(json.dumps(w, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def gox_entries(m: str, root: Path) -> dict:
    """{law id: DERIVATION entry} of the milestone's gox laws."""
    from ..rules.gox import SUBFORMS
    p = Path(root) / "laws" / m / "DERIVATION.json"
    if not p.is_file():
        return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    return {e["law_id"]: e for e in d.get("laws") or [] if e.get("rule") == "PAR" and e.get("subform") in SUBFORMS}


def generator_sha256(root: Path) -> str:
    h = hashlib.sha256()
    for rel in ("holon/gox/model.py", "holon/gox/lawrun.py", "holon/gox/basis.py", "holon/gox/ledger.py",
                "holon/rules/gox.py"):
        h.update(rel.encode() + b"\0" + (Path(root) / rel).read_bytes() + b"\0")
    return h.hexdigest()


class Decider:
    def __init__(self, root: Path, m: str, results: Path, gen: Path):
        from .. import ir
        self.root, self.m, self.results, self.gen = Path(root), m, Path(results), Path(gen)
        self.entries = gox_entries(m, self.root)
        self.registry = ir.load_registry(m, self.root)
        self.laws = {lid: json.loads((self.root / "laws" / m / f"{lid}.json").read_text(encoding="utf-8"))
                     for lid in self.entries}

    def rel(self, p: Path) -> str:
        try:
            return Path(p).resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return str(p)

    def paths(self, lid: str) -> dict:
        return {"module": self.gen / "gox" / f"{lid}.bend", "laws": self.gen / "laws" / lid / "LAWS.bend",
                "proof": self.gen / "proofs" / lid / "PROOF.bend"}

    def write(self, lid: str, module: str, laws: str, proof: str | None) -> dict:
        p = self.paths(lid)
        for k, text in (("module", module), ("laws", laws), ("proof", proof)):
            if text is None:
                continue
            p[k].parent.mkdir(parents=True, exist_ok=True)
            p[k].write_text(text, encoding="utf-8")
        return p

    def replay_agrees(self, lid: str, w) -> tuple[bool, str]:
        rp = self.root / "replay" / self.m / "gox" / f"{lid}.json"
        if not rp.is_file():
            return False, f"no replay at {self.rel(rp)} (holon gox replay writes it)"
        r = json.loads(rp.read_text(encoding="utf-8"))
        if r.get("witness_sha256") != witness_sha256(w):
            return False, "the replay is of another witness"
        if r.get("verdict") != "agree":
            return False, f"the replay's verdict is {r.get('verdict')}: {r.get('detail')}"
        return True, r.get("detail") or "agree"

    def decide(self, lid: str) -> dict:
        from ..bundle.lawrun import check
        t0 = time.time()
        e, law = self.entries[lid], self.laws[lid]
        b = e["basis"]
        sh = self.registry["statements"][lid]
        mod_rel = f"../../gox/{lid}.bend"
        attempts, witness, status, prim, bound = [], None, "UNKNOWN", None, None
        try:
            if e["subform"] == "go_round_trip":
                module, laws, proof = G.round_trip_files(b, lid, sh, mod_rel)
                p = self.write(lid, module, laws, proof)
                chk = check(p["proof"])
                attempts.append({"kind": "proof", "class": "reflexivity", "ok": chk["ok"],
                                 "checker": chk["checker"]})
                if chk["ok"]:
                    status, prim = "PROVED", dict(chk, proof=self.rel(p["proof"]))
                else:
                    bound = "the reflexivity proof does not check"
            elif e["subform"] == "go_branch":
                w = G.branch_witness(b)
                if G.branch_eval(b, lid, w["values"]):
                    raise G.ModelDebt("G9's witness meets the law in the model")
                module, laws, proof = G.branch_files(b, lid, sh, mod_rel, True, w)
                p = self.write(lid, module, laws, proof)
                chk = check(p["proof"])
                witness = branch_record_witness(b, w)
                attempts.append({"kind": "counter_law", "witness": witness, "ok": chk["ok"], "checker": chk["checker"]})
                if chk["ok"]:
                    agree, why = self.replay_agrees(lid, witness)
                    attempts.append({"kind": "replay", "ok": agree, "detail": why})
                    if agree:
                        status, prim = "REFUTED", dict(chk, proof=self.rel(p["proof"]))
                    else:
                        bound = f"the counter-law checks, the replay does not confirm it: {why}"
                else:
                    bound = "the counter-law does not check"
            else:
                w = G.recompute_witness(b)
                module, laws, proof = G.recompute_files(b, lid, sh, mod_rel, w)
                p = self.write(lid, module, laws, proof)
                chk = check(p["proof"])
                witness = recompute_record_witness(b, w)
                attempts.append({"kind": "counter_law", "witness": witness, "ok": chk["ok"], "checker": chk["checker"]})
                if chk["ok"]:
                    agree, why = self.replay_agrees(lid, witness)
                    attempts.append({"kind": "replay", "ok": agree, "detail": why})
                    if agree:
                        status, prim = "REFUTED", dict(chk, proof=self.rel(p["proof"]))
                    else:
                        bound = f"the counter-law checks, the replay does not confirm it: {why}"
                else:
                    bound = "the counter-law does not check"
        except G.ModelDebt as ex:
            attempts.append({"kind": "model", "ok": False, "detail": str(ex)})
            bound = f"the model does not state this law: {ex}"
        rec = self.record(law, e, status, witness, attempts, prim, bound)
        rec["seconds"] = round(time.time() - t0, 3)
        return rec

    def record(self, law: dict, e: dict, status: str, witness, attempts: list, prim, bound) -> dict:
        from .. import records as R
        from ..bundle.lawrun import bend_version
        lid = law["law_id"]
        sh = self.registry["statements"][lid]
        p = self.paths(lid)
        mtext = p["module"].read_text(encoding="utf-8") if p["module"].exists() else ""
        ltext = p["laws"].read_text(encoding="utf-8") if p["laws"].exists() else ""
        roots = "\n".join(ln for ln in ltext.splitlines() if not ln.startswith("import "))   # M.-qualified roots
        cone = R.cone(roots, mtext) if mtext else []
        hz = (e["basis"].get("hypz_len") or {}) if e["subform"] == "go_branch" else {}
        premises = ([f"HypZ_len ({hz.get('from')}) at {hz.get('via')}: |g(X)| <= CB(|X|) for a successful call on a "
                     "non-empty X"] if hz else [])
        rec = {"law_id": lid, "statement_hash": sh, "facts_sha256": law["facts_sha256"], "status": status,
               "scope": "unbounded", "premises": premises,
               "kernel": {"name": "bend", "version": bend_version(), "verdict": (prim or {}).get("verdict", "not_run")},
               "artifacts": {"laws": self.rel(p["laws"]) if p["laws"].exists() else None,
                             "proof": (prim or {}).get("proof"),
                             "model": self.rel(p["module"]) if p["module"].exists() else None,
                             "law_name": G.law_name(lid, status == "REFUTED")},
               "checker": (prim or {}).get("checker") or {"exit_code": None, "marker": "not_run"},
               "triage": "finding" if status == "REFUTED" else "none",
               "replay": ({"status": "passed", "detail": "the real-code replay agrees "
                                                         f"(replay/{self.m}/gox/{lid}.json)"}
                          if status == "REFUTED" else {"status": "not_applicable",
                                                       "detail": f"{status}: no replayed witness"}),
               "attempts": attempts, "rule": law["rule"], "subform": law["subform"],
               "gox": {"gox_id": law["statement"]["claim"]["eq"][0]["gox"], "basis": e["basis"]},
               "bound": bound if status == "UNKNOWN" else None}
        if witness is not None:
            rec["witness"] = witness
            rec["witness_sha256"] = witness_sha256(witness)
        if status == "REFUTED":
            rec["difference"] = {"lhs": False, "rhs": True}
        try:
            _b, match = R.resolve_bundle(law["facts_sha256"], law["facts"], self.root, mtext, set(cone), self.m)
            assumptions = R.model_assumptions(_b["facts_sha256"], set(cone), self.root, law["facts"], self.m)
        except R.LedgerError:
            match, assumptions = "none", []
        msha = sha256_file(p["module"]) if p["module"].exists() else None
        rec.update({"record_version": R.RECORD_VERSION, "prover": "generator", "model_sha256": msha,
                    "compiled_sha256": msha, "generator_sha256": generator_sha256(self.root), "cone": cone,
                    "ledger_match": match, "model_assumptions": [], "ledger_assumptions": sorted(assumptions),
                    "scope_v2": R.scope_v2(law, rec), "kernels": R.kernels(rec),
                    "independence_class": R.independence_class(rec), "refinement_refs": [], "coverage": None,
                    "non_vacuity": {
                        "status": "counter_witness" if status == "REFUTED" else "unknown",
                        "law": self.rel(p["laws"]) if status == "REFUTED" else None, "witness": None,
                        "reachable": True if status == "REFUTED" else None, "degenerate": None,
                        "parent_statement_hash": sh,
                        "bound": ("the accepted counter-law inhabits the premises" if status == "REFUTED"
                                  else ("no premise: the law is unconditional" if status == "PROVED" and not premises
                                        else "no proof"))},
                    "witness_provenance": {"go": "internal_harness"} if status == "REFUTED" else None,
                    "filter_bin": "finding" if status == "REFUTED" else None,
                    **R.evidence_fields(law, {"status": status}, self.root)})
        rec["statement"] = law.get("notes", "")
        return rec


def branch_record_witness(b: dict, w: dict) -> dict:
    """The go_branch witness in the target's words: each Go int parameter by name, |X|, and the model's |g(X)|."""
    tr = G.branch_tr(b)
    out = {"kind": "go_branch", "function": b["function"], "payload_length": w["x_length"],
           "payload_operand": w["last"], "enc_length_model": w["values"].get("e"), "values": w["values"]}
    for v, (k, t) in tr.vars.items():
        if k == "nat" and isinstance(t, list) and t[:1] == ["param"]:
            out[t[1]] = w["values"][v]
    return out


def recompute_record_witness(b: dict, w: dict) -> dict:
    return {"kind": "go_recompute", "function": b["function"], "appends": w["appends"],
            "lists": {k: [int(x) for x in v] for k, v in w["lists"].items()}, "nats": w["nats"],
            "go_preimage_length": w["go_preimage_length"], "rest": w["rest"]}


def law_text(lid: str, m: str, root: Path) -> str | None:
    """The LAWS.bend text decide writes for lid (bindings: the law file), or None."""
    p = Path(root) / "gen" / m / "laws" / lid / "LAWS.bend"
    return p.read_text(encoding="utf-8") if p.is_file() else None


# ------------------------------------------------------------------------------------------------ routing
def _arg(argv: list, name: str):
    for i, x in enumerate(argv):
        if x == name and i + 1 < len(argv):
            return argv[i + 1]
        if x.startswith(name + "="):
            return x.split("=", 1)[1]
    return None


def ids_of(argv: list, root: Path | None = None):
    """(the gox law ids, the other ids) of a `run --laws` argv, or None when it names none."""
    m, laws = _arg(argv, "--milestone"), _arg(argv, "--laws")
    if argv[:1] != ["run"] or not m or not laws:
        return None
    base = Path(_arg(argv, "--root") or root or ROOT)
    ids = [x.strip() for x in laws.split(",") if x.strip()]
    mine = gox_entries(m, base)
    gids = [i for i in ids if i in mine]
    if not gids:
        return None
    return gids, [i for i in ids if i not in mine]


def strip_args(argv: list, names: tuple) -> list:
    from ..versions.run import strip_args as sa
    return sa(argv, names)


def run_main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="holon run (gox laws)")
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--laws", required=True)
    ap.add_argument("--root")
    ap.add_argument("--out")
    ap.add_argument("--gen-dir")
    a, _rest = ap.parse_known_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    results = Path(a.out) if a.out else root / "results" / a.milestone
    gen = Path(a.gen_dir) if a.gen_dir else root / "gen" / a.milestone
    d = Decider(root, a.milestone, results, gen)
    for lid in [x.strip() for x in a.laws.split(",") if x.strip()]:
        if lid not in d.entries:
            print(f"holon run: {lid} is not a gox law of {a.milestone}", file=sys.stderr)
            return 3
        rec = d.decide(lid)
        results.mkdir(parents=True, exist_ok=True)
        (results / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
        print(f"{lid}: {rec['status']} ({rec['seconds']} s)")
    return 0
