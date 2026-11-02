"""Rule S6: the slash laws' decider (the contract: tests_m3/test_cutover_slash.py, S4-S6).

  python -m holon run --milestone M3 --laws <slash ids>     (routed here by holon.__main__, before rule NAT's runner)

A slash law (rules NAT and SORT, sub-form "slash": holon.rules.slash) is stated over the linked layer (the sidecar's
outputs.linked: the versioned layer and both registries' models, under the wiring premise) and its claims module
(outputs.claims). It is REFUTED only by a counter-law Bend accepts at a witness the search finds on that layer's
compiled code (.mjs), replayed on the real code; no generator proves one. When the layer, the claims module or the
search's inputs are missing, the law is UNKNOWN, and its record says why, construct by construct: what the linked layer
lacks (from the sidecar's link and outputs), the registry model's own debt (its models.json) and the steps the decision
needs that did not run. The record's notes add the real code's observation at the law's site pair (the cutover refine's
rows, outputs.steps): an observation of the harness, never a checker's verdict.

Records are holon-record/0.2 (holon.records), written to results/<M>/<id>.json. Nothing here names a target: every
contract, member, version, action and path comes from the sidecar, the laws, the documents and the outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

GEN_SLASH = ("holon/cutover/lawrun.py", "holon/cutover/model.py", "holon/rules/slash.py")


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def generator_sha256(root: Path) -> str:
    """The digest of the slash decider's closure: these modules and their holon imports."""
    from ..records import _holon_imports
    seen, todo = set(), list(GEN_SLASH)
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


def slash_entries(milestone: str, root: Path) -> dict:
    """law id -> its DERIVATION.json entry, for the laws of the slash sub-form."""
    from ..rules import slash as S
    try:
        dv = json.loads((Path(root) / "laws" / milestone / "DERIVATION.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {e["law_id"]: e for e in dv.get("laws") or []
            if isinstance(e, dict) and e.get("subform") == S.SUBFORM and e.get("rule") in S.RULES}


# ------------------------------------------------------------------------------------------------ what is missing
def _action_of(fn: str) -> str:
    """The callee's action of a call's function name "<Contract>.<function>[_<selector>]"."""
    name = fn.rsplit(".", 1)[-1]
    head, _, tail = name.rpartition("_")
    return head if head and len(tail) == 8 and all(c in "0123456789abcdef" for c in tail) else name


def debt_of(ctx, law: dict, entry: dict) -> list:
    """The constructs the decision lacks, in order, each a sentence."""
    out = []
    side, root = ctx.side, ctx.root
    a, b = entry["basis"]["edge"].split("->")
    ra, rb = side["link"]["a"]["registry"], side["link"]["b"]["registry"]
    linked, claims = side["outputs"]["linked"], f"{side['outputs']['claims']}/slash.bend"
    vdoc = ctx.versioned()
    path = list(vdoc.get("path") or [])
    upto = path[:path.index(a) + 1] if a in path else [a]
    if not (root / linked).is_file():
        out.append(f"the linked layer {linked} is not built: the registry modules' type conversions (each registry "
                   f"model's words, store, hash table, call answers and environment, to and from the versioned "
                   f"layer's), for {ra} at {a} and {rb} at {b}")
        out.append(f"a reachability witness of the versioned layer through {upto[0]}..{upto[-1]} whose registry word "
                   f"names {ra} at its initial state's address and whose committer is a staker of {ra}'s state: the "
                   f"cutover harness deploys the Rollup at {a} directly, which is not a state of the versioned "
                   f"layer's reachability (it starts at the deployed path's entry), so the search over the corpus "
                   f"states (the sidecar's search) cannot run as stated")
    if not (root / claims).is_file():
        out.append(f"the claims module {claims} (each site's answer: the registry model's step on the site's call, "
                   f"its arguments read from the Rollup's storage at the key k)")
    out.append("the witness search over the compiled linked layer (.mjs): not run")
    out.append(f"the counter-law gen/{ctx.milestone}/proofs/{law['law_id']}/PROOF.bend: none")
    out.append(f"the replay of a witness on the real code (RP1, {side['outputs']['replay']}): not run")
    mp = root / side["outputs"]["models"] / "models.json"
    if mp.is_file():
        reg = (json.loads(mp.read_text(encoding="utf-8")).get(ra) or {})
        for d in reg.get("debt") or []:
            out.append(f"{ra}'s model debt: {d['error']}")
    else:
        out.append(f"{ra}'s model ({side['outputs']['models']}/{ra}.bend) is not built")
    return out


def observation(ctx, entry: dict) -> str:
    """The real code's run of the pair's op at both versions in the cutover refine's rows (outputs.steps): each
    registry call the versioned member makes there and each value a registry sends it back."""
    rel = ctx.side["outputs"]["steps"]
    p = ctx.root / rel
    if not p.is_file():
        return f"no observation ({rel} is missing)"
    steps = json.loads(p.read_text(encoding="utf-8"))
    vname = steps.get("versioned_member")
    a, b = entry["basis"]["edge"].split("->")
    op = entry["basis"]["op"]
    regs = {ctx.side["link"]["a"]["registry"], ctx.side["link"]["b"]["registry"]}
    sels = {}
    for side in ("a", "b"):
        for s_ in entry["basis"][side]:
            sels[s_["fn"]] = _action_of(s_["fn"])
    rows = []
    for r in steps.get("steps") or []:
        if r.get("status") != "ok" or r.get("version") not in (a, b):
            continue
        if not str(r.get("label", "")).startswith(f"{vname}@{r['version']}.{op} "):
            continue
        calls = [f"{f[1]}->{f[2]} {f[3]} {'ok' if f[5] else 'reverted'}" for f in r["frames"]
                 if f[1] == vname and f[2] in regs]
        back = [f"{f[4]} wei from {f[1]}" for f in r["frames"] if f[1] in regs and f[2] == vname and int(f[4]) > 0]
        rows.append(f"{r['trace']} step {r['index']} ({r['label']}, version {r['version']}): calls "
                    f"{', '.join(calls) or 'none'}; value back to {vname}: {', '.join(back) or 'none'}")
    if not rows:
        return f"no run of {op} at {a} or {b} in {rel}"
    return (f"observed on the real code by `holon cutover refine` (the harness under {ctx.side['outputs']['harness']}, "
            f"rows in {rel}; an observation, not a checker's verdict; the sites' registry action: "
            f"{', '.join(sorted(set(sels.values())))}; every run of {op} at {a} or {b} the corpus holds): "
            + "; ".join(rows))


# ------------------------------------------------------------------------------------------------ the decider
class Decider:
    def __init__(self, ctx, results: Path, gen: Path):
        from .. import ir
        self.ctx, self.root, self.results, self.gen = ctx, ctx.root, results, gen
        self.registry = ir.load_registry(ctx.milestone, self.root)
        self.entries = slash_entries(ctx.milestone, self.root)

    def rel(self, p: Path) -> str:
        return Path(p).resolve().relative_to(self.root).as_posix()

    def model(self) -> tuple:
        """(the registry model's path, its text, the compiled module's sha256): the one model of the claim built so
        far (M1)."""
        from ..sorts.evaluate3 import Evaluator
        ra = self.ctx.side["link"]["a"]["registry"]
        p = self.root / self.ctx.side["outputs"]["models"] / f"{ra}.bend"
        if not p.is_file():
            raise FileNotFoundError(f"{self.rel(p)} is missing (holon cutover model writes it)")
        text = p.read_text(encoding="utf-8")
        mjs = Evaluator(model_path=p, doc=None, text=text).compiled()
        return p, text, sha256_file(mjs)

    def decide(self, lid: str) -> dict:
        t0 = time.monotonic()
        e = self.entries.get(lid)
        if e is None:
            raise KeyError(f"{lid} is not a slash law of {self.ctx.milestone}")
        law = json.loads((self.root / "laws" / self.ctx.milestone / f"{lid}.json").read_text(encoding="utf-8"))
        debt = debt_of(self.ctx, law, e)
        bound = "not decided: " + "; ".join(f"({i + 1}) {d}" for i, d in enumerate(debt))
        attempts = [{"kind": "refute", "engine": "holon.cutover.lawrun", "found": False,
                     "bound": "the witness search needs the linked layer and its claims module (S6)",
                     "reason": "; ".join(debt[:3])},
                    {"kind": "proof", "found": False, "reason": "no generator proves a slash law (S6)"}]
        rec = self.record(law, attempts, bound, observation(self.ctx, e))
        rec["seconds"] = round(time.monotonic() - t0, 3)
        return rec

    def record(self, law: dict, attempts: list, bound: str, notes: str) -> dict:
        from .. import records as R
        from ..sorts.run3 import bend_version
        lid = law["law_id"]
        sh = self.registry["statements"][lid]
        mp, text, compiled = self.model()
        e = self.entries[lid]
        acts = sorted({_action_of(s_["fn"]) for s_ in e["basis"]["a"]})
        cone = R.cone(" ".join(f"M.run_{a}" for a in acts), text)
        rec = {"law_id": lid, "statement_hash": sh, "facts_sha256": law["facts_sha256"], "status": "UNKNOWN",
               "scope": "unbounded", "premises": [],
               "kernel": {"name": "bend", "version": bend_version(), "verdict": "not_run"},
               "artifacts": {"laws": None, "proof": None, "model": self.rel(mp), "law_name": lid.lower()},
               "checker": {"exit_code": None, "marker": "not_run"}, "triage": "none",
               "replay": {"status": "not_applicable", "detail": "UNKNOWN: no witness to replay"},
               "attempts": attempts, "rule": law["rule"], "subform": law["subform"], "witness": None, "bound": bound}
        try:
            b, match = R.resolve_bundle(rec["facts_sha256"], law["facts"], self.root, text, set(cone),
                                        self.ctx.milestone)
            assumptions = R.model_assumptions(b["facts_sha256"], set(cone), self.root, law["facts"])
        except R.LedgerError:
            match, assumptions = "none", []
        rec.update({"record_version": R.RECORD_VERSION, "prover": "generator", "model_sha256": sha256_file(mp),
                    "compiled_sha256": compiled, "generator_sha256": generator_sha256(self.root), "cone": cone,
                    "ledger_match": match, "model_assumptions": assumptions, "scope_v2": R.scope_v2(law, rec),
                    "kernels": R.kernels(rec), "independence_class": R.independence_class(rec),
                    "refinement_refs": [], "coverage": None,
                    "non_vacuity": {"status": "unknown", "law": None, "witness": None, "reachable": None,
                                    "degenerate": None, "parent_statement_hash": sh, "bound": "no proof"},
                    "witness_provenance": None, "filter_bin": None,
                    **R.evidence_fields(law, {"status": "UNKNOWN"}, self.root)})
        rec["ledger_assumptions"] = sorted(rec["model_assumptions"])
        rec["model_assumptions"] = []
        rec["statement"] = law.get("notes", "")
        rec["notes"] = notes
        return rec


# ------------------------------------------------------------------------------------------------ routing
def _arg(argv: list, name: str):
    for i, x in enumerate(argv):
        if x == name and i + 1 < len(argv):
            return argv[i + 1]
        if x.startswith(name + "="):
            return x.split("=", 1)[1]
    return None


def ids_of(argv: list, root: Path | None = None):
    """(the slash law ids, the other ids) of a `run --laws` argv, or None when it names none."""
    from . import ROOT
    m, laws = _arg(argv, "--milestone"), _arg(argv, "--laws")
    if argv[:1] != ["run"] or not m or not laws:
        return None
    ids = [x.strip() for x in laws.split(",") if x.strip()]
    mine = slash_entries(m, Path(_arg(argv, "--root") or root or ROOT))
    sids = [i for i in ids if i in mine]
    if not sids:
        return None
    return sids, [i for i in ids if i not in mine]


def strip_args(argv: list, names: tuple) -> list:
    from ..versions.run import strip_args as sa
    return sa(argv, names)


def run_main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="holon run (slash laws)")
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--laws", required=True)
    ap.add_argument("--root")
    ap.add_argument("--out", help="the results directory (default results/<M>)")
    ap.add_argument("--gen-dir", help="the generated files' directory (default gen/<M>)")
    a, _rest = ap.parse_known_args(argv)
    from . import ROOT, Refused, context
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        ctx = context(root, a.milestone)
        results = Path(a.out) if a.out else root / "results" / a.milestone
        gen = Path(a.gen_dir) if a.gen_dir else root / "gen" / a.milestone
        d = Decider(ctx, results, gen)
        for lid in [x.strip() for x in a.laws.split(",") if x.strip()]:
            rec = d.decide(lid)
            results.mkdir(parents=True, exist_ok=True)
            (results / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
            print(f"{lid}: {rec['status']} ({rec['seconds']} s)")
        return 0
    except Refused as e:
        print(f"holon run: refused: {e}", file=sys.stderr)
        return 2
    except (KeyError, FileNotFoundError) as e:
        print(f"holon run: error: {e}", file=sys.stderr)
        return 3
