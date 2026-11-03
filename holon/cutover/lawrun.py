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
    vname = next((m["name"] for m in ctx.bundle().members() if m.get("adopted")), "the versioned member")
    path = list(vdoc.get("path") or [])
    upto = path[:path.index(a) + 1] if a in path else [a]
    if not (root / linked).is_file():
        out.append(f"the linked layer {linked} is not built: the registry modules' type conversions (each registry "
                   f"model's words, store, hash table, call answers and environment, to and from the versioned "
                   f"layer's), for {ra} at {a} and {rb} at {b}")
        out.append(f"a reachability witness of the versioned layer through {upto[0]}..{upto[-1]} whose registry word "
                   f"names {ra} at its initial state's address and whose committer is a staker of {ra}'s state: the "
                   f"cutover harness deploys {vname} at {a} directly, which is not a state of the versioned "
                   f"layer's reachability (it starts at the deployed path's entry), so the search over the corpus "
                   f"states (the sidecar's search) cannot run as stated")
    if not (root / claims).is_file():
        out.append(f"the claims module {claims} (each site's answer: the registry model's step on the site's call, "
                   f"its arguments read from {vname}'s storage at the key k)")
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
        self._search, self._found = None, None

    def close(self) -> None:
        if self._search is not None:
            self._search.close()

    def linked_ready(self) -> bool:
        from .s0 import SIDECAR
        sp = self.root / SIDECAR.format(m=self.ctx.milestone)
        if not sp.is_file():
            return False
        side = json.loads(sp.read_text(encoding="utf-8"))
        return all((self.root / side["outputs"][k]).is_file() for k in ("linked", "claims", "registry_s0"))

    def refute(self, law: dict, t0: float, observed: str) -> dict | None:
        """I94 (D2-D3): the witness the search finds on the compiled claims module, its LAWS.bend and PROOF.bend, and
        their check; the REFUTED record, or None when the search finds none or the checker refuses (the caller records
        UNKNOWN with what was tried)."""
        from .. import bend
        from ..bend import escape_hatches
        from . import search as SR
        if self._search is None:
            self._search = SR.Search(self.ctx, log=lambda *a: None)
            self._found = self._search.run(keep=True)
        lid = law["law_id"]
        w = (self._found.get("found") or {}).get(law["rule"])
        self._tried = self._found.get("tried") or []
        if w is None:
            return None
        sh = self.registry["statements"][lid]
        ld = self.gen / "laws" / lid
        pd = self.gen / "proofs" / lid
        ld.mkdir(parents=True, exist_ok=True)
        pd.mkdir(parents=True, exist_ok=True)
        lp, pp = ld / "LAWS.bend", pd / "PROOF.bend"
        lp.write_text(laws_text(self.ctx, law, sh, ld, True), encoding="utf-8")
        pp.write_text(proof_text(self.ctx, law, w, self._search, self._search.m, pd), encoding="utf-8")
        hits = escape_hatches(lp.read_text(encoding="utf-8") + pp.read_text(encoding="utf-8"))
        r = bend.check(pp)
        chk = {"exit_code": r.code, "marker": "ALL PROOFS CHECK" if r.ok else "SOME PROOFS FAIL", "seconds": r.seconds}
        verdict = "not_run"
        if r.ok and bend.verdict_enabled():
            v = bend.check_verdict(pp)
            verdict = "checked" if v.ok else "failed"
        self._last = {"checker": chk, "verdict": verdict, "out": (r.out or "")[-1500:], "hits": hits}
        if not r.ok or hits or verdict == "failed":
            return None
        rep = self.replay_status(lid, w)
        rec = self.record(law, [{"kind": "refute", "engine": "holon.cutover.search", "found": True,
                                 "candidates": self._tried},
                                {"kind": "counter", "evaluator": "the claim is false at the witness",
                                 "checker": chk, "verdict": verdict}], None, observed)
        p_claims = self.root / self._search.side["outputs"]["claims"]
        from .claims import claim_name
        from .. import records as R
        text = p_claims.read_text(encoding="utf-8")
        cone = R.cone(f"M.{claim_name(law)}", text)
        a, b = self._search.a, self._search.b
        rec.update({"status": "REFUTED", "checker": chk,
                    "kernel": dict(rec["kernel"], verdict=verdict),
                    "artifacts": {"laws": self.rel(lp), "proof": self.rel(pp), "model": self.rel(p_claims),
                                  "law_name": "cl_" + lid.lower()},
                    "triage": "finding", "replay": rep, "bound": None,
                    "witness": {"trace": [s_["label"] + ("@" + s_["version"] if s_.get("version") else "")
                                          for s_ in w["trace"]],
                                "committer": w["committer"], "k": w["k"], "u": w["mig"]["calldata"],
                                "edge": f"{a}->{b}", "left": w["left"], "right": w["right"],
                                "link_equations": w.get("link_equations", 0)},
                    "compiled_sha256": w["compiled_sha256"], "model_sha256": sha256_file(p_claims),
                    "cone": cone or rec["cone"], "difference": {"lhs": False, "rhs": True},
                    "non_vacuity": dict(rec["non_vacuity"], status="counter_witness", law=self.rel(lp),
                                        bound="the accepted counter-law inhabits the premises"),
                    "witness_provenance": {"solidity": "internal_harness"}, "filter_bin": "finding"})
        from .. import records as R2
        rec["scope_v2"] = R2.scope_v2(law, rec)
        rec["kernels"] = R2.kernels(rec)
        rec["independence_class"] = R2.independence_class(rec)
        rec.update(R2.evidence_fields(law, {"status": "REFUTED"}, self.root))
        rec["seconds"] = round(time.monotonic() - t0, 3)
        return rec

    def replay_status(self, lid: str, w: dict) -> dict:
        from .s0 import sidecar
        p = self.root / sidecar(self.ctx)["outputs"]["replay"]
        if not p.is_file():
            return {"status": "not_run", "detail": "the replay report is missing (holon cutover replay)"}
        runs = {x["id"]: x for x in json.loads(p.read_text(encoding="utf-8")).get("runs") or []}
        ok = all((runs.get(f"{lid}:{s}") or {}).get("passed") for s in ("left", "right"))
        return {"status": "passed" if ok else "failed",
                "detail": f"{lid}:left and {lid}:right in {sidecar(self.ctx)['outputs']['replay']}"}

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
        if self.linked_ready():
            rec = self.refute(law, t0, observation(self.ctx, e))
            if rec is not None:
                return rec
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
        try:
            for lid in [x.strip() for x in a.laws.split(",") if x.strip()]:
                rec = d.decide(lid)
                results.mkdir(parents=True, exist_ok=True)
                (results / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
                print(f"{lid}: {rec['status']} ({rec['seconds']} s)")
                if rec["status"] != "REFUTED" and getattr(d, "_last", None):
                    print(f"{lid}: the counter-law: {d._last['checker']['marker']}: {d._last['out'][-600:]}")
        finally:
            d.close()
        return 0
    except Refused as e:
        print(f"holon run: refused: {e}", file=sys.stderr)
        return 2
    except (KeyError, FileNotFoundError) as e:
        print(f"holon run: error: {e}", file=sys.stderr)
        return 3


# ------------------------------------------------------------------------------------------------ I94: the Bend files
def _imports(ctx, d: Path) -> list:
    """The modules a slash law's files import, relative to directory d: the link spec's members, the linked layer
    (L) and the claims module (C)."""
    from .linked import rel_import
    from .s0 import sidecar
    side = sidecar(ctx)
    link = side["link"]
    out = ["import Base", f"import {rel_import(d, ctx.root / link['caller']['module'])} as {link['caller']['alias']}"]
    for c in link["callees"]:
        out.append(f"import {rel_import(d, ctx.root / c['module'])} as {c['alias']}")
    out.append(f"import {rel_import(d, ctx.root / side['outputs']['linked'])} as L")
    out.append(f"import {rel_import(d, ctx.root / side['outputs']['claims'])} as C")
    return out


def laws_text(ctx, law: dict, sh: str, d: Path, counter: bool) -> str:
    """A slash law's LAWS.bend (rule D1): the statement (for, ==) or its counter-law (exs, !=) over the table kh, the
    caller's state and reachability, each callee's state (the linked reachability LReach), k, u and each callee's
    environment."""
    from .claims import claim_name
    from .s0 import sidecar
    link = sidecar(ctx)["link"]
    P = link["caller"]["alias"]
    st = {"versioned": "VSt", "plain": "HSt"}
    q = "exs" if counter else "for"
    a, b = law["statement"]["claim"]["eq"][0]["slash"].split(":")[2:4]
    xs = [c["alias"] for c in link["callees"]]
    lines = ["# GENERATED by holon.cutover.lawrun from the frozen law IR; do not edit.",
             f"# law_id: {law['law_id']}   statement_hash: {sh}", *_imports(ctx, d), "",
             f"law {('cl_' if counter else '') + law['law_id'].lower()}:",
             f"  {q} kh: List<&2, {P}.HKB>", f"  {q} s: {P}.{st[link['caller']['kind']]}"]
    lines += [f"  {q} s_{x}: {x}.{st[c['kind']]}" for x, c in zip(xs, link["callees"])]
    lines += [f"  {q} r: L.LReach<kh, s, {', '.join('s_' + x for x in xs)}>", f"  {q} k: {P}.W",
              f"  {q} u: {P}.UC_{a}_{b}"]
    lines += [f"  {q} e_{x}: {x}.HEnv" for x in xs]
    call = f"C.{claim_name(law)}(s, {', '.join('s_' + x for x in xs)}, k, u, {', '.join('e_' + x for x in xs)}, kh)"
    lines += [f"  {{{call} {'!=' if counter else '=='} True{{}} : Bool}}", ""]
    return "\n".join(lines)


def law_file(law: dict, m: str, root, sh: str, counter: bool) -> str | None:
    """The bound emission (holon.bindings): the law's LAWS.bend text as the decider writes it under gen/<m>/laws/<id>/,
    or None while the linked layer or the claims module is missing."""
    from . import context
    from .s0 import SIDECAR
    root = Path(root)
    sp = root / SIDECAR.format(m=m)
    if not sp.is_file():
        return None
    side = json.loads(sp.read_text(encoding="utf-8"))
    if not ((root / side["outputs"]["linked"]).is_file() and (root / side["outputs"]["claims"]).is_file()):
        return None
    ctx = context(root, m)
    return laws_text(ctx, law, sh, root / "gen" / m / "laws" / law["law_id"], counter)


def proof_text(ctx, law: dict, w: dict, search, m, d: Path) -> str:
    """A witness's counter-law PROOF.bend (rule D3): the trace's states, steps and step equations, the callees'
    initial-state proofs, the link equations of the word-argument answers, and the claim false by computation."""
    from ..versions.bendlit import Lit
    from .claims import claim_name
    link = search.link
    xs = [c["alias"] for c in link["callees"]]
    n = len(w["trace"])
    defs = [x for x in search.literals(m, w) if not any(x.startswith(f"def s_{a}()") for a in xs)]
    for c in link["callees"]:
        x = c["alias"]
        defs.append(f"def s_{x}() -> {x}.HSt:\n  {x}.s0()\n")
        defs.append(f"def r_{x}_w() -> {x}.Reach<L.lHKB_to_{x}(t_kh()), s_{x}()>:\n  {x}.R0{{{{==}}}}\n")
        defs.append(f"def rv_{x}(o: {x}.HOut) -> List<&2, U32>:\n  match o:\n    case {x}.HOut{{c, rv, po, lg, tw}}:\n"
                    "      rv\n")
    P = link["caller"]["alias"]
    defs.append(f"def lr_w() -> L.LReach<t_kh(), s_{n}(), {', '.join(f's_{x}()' for x in xs)}>:\n"
                f"  L.LR{{reach_w(), {', '.join(f'r_{x}_w()' for x in xs)}}}\n")
    stated = 0
    for i, a in enumerate(w.get("answered") or []):
        x = a["callee"]
        callee = next(c for c in search_callees(search) if c["alias"] == x)
        doc = callee["doc"]
        ps = doc.params(a["action"]) or []
        if any(p.get("type") not in ("uint256", "address", "bool", "bytes32") and not str(p.get("type", "")).startswith(("uint", "int")) for p in ps):
            continue
        lit = Lit(x)
        vals = [lit.word(int(a["args"].get(p["name"]) or 0) if not isinstance(a["args"].get(p["name"]), bool)
                         else int(a["args"].get(p["name"]))) for p in ps]
        ar = f"{x}.AR_{a['action']}{{{', '.join(vals)}}}"
        env = search.henv(x, a["env"])
        ret = Lit.blist(bytes.fromhex(a["ret"][2:]))
        defs.append(f"def lk_{i}() -> {{{ret} == rv_{x}({x}.run_{a['action']}(s_{x}(), {ar}, {env}, "
                    f"L.lHKB_to_{x}(t_kh()))) : List<&2, U32>}}:\n  {{==}}\n")
        stated += 1
    w["link_equations"] = stated
    es = [f"e_{x}()" for x in xs]
    call = f"C.{claim_name(law)}(s_{n}(), {', '.join(f's_{x}()' for x in xs)}, k_w(), u_w(), {', '.join(es)}, t_kh())"
    defs.append(f"def cz() -> {{{call} == False{{}} : Bool}}:\n  {{==}}\n")
    defs.append("def is_true(b: Bool) -> Type:\n  match b:\n    case True{}:\n      Unit\n    case False{}:\n      Empty\n")
    defs.append("def true_ne_false(p: {True{} == False{} : Bool}) -> Empty:\n  (%p : is_true(_)\n  Unit{})\n")
    wit = ["t_kh()", f"s_{n}()"] + [f"s_{x}()" for x in xs] + ["lr_w()", "k_w()", "u_w()"] + es
    body = "e => true_ne_false((%e : {_ == False{} : Bool}\n  cz()))"
    for x in reversed(wit):
        body = f"({x}, {body})"
    defs.append(f"def Laws.cl_{law['law_id'].lower()}():\n  {body}\n")
    from .linked import rel_import
    head = ["# GENERATED by holon.cutover.lawrun; untrusted, accepted only if Bend checks it.", *_imports(ctx, d),
            f"import {rel_import(d, ctx.root / 'gen' / ctx.milestone / 'laws' / law['law_id'] / 'LAWS.bend')} as Laws"]
    return "\n".join(head) + "\n\n" + "\n".join(defs)


def search_callees(search) -> list:
    """The callees' compiled-model handles the search used (their documents), by alias."""
    return getattr(search, "_callee_docs", [])
