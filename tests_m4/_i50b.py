"""I50b instrument: the contaminated rerun's rules, recomputed independently of holon/ (key I50b, spec/M4/predictions.json).

Written at the I50b prereg, after the sealed I49/I50 results were recorded and before any change to holon/ or any
rerun. Nothing here imports holon/ (a test that exercises a holon module imports it inside the test). What it computes,
the tests compare with what holon/ writes:

  protocol            spec/M4/lib/heldout_rerun.json, parsed
  expected_target     rule T1b: the rerun target's description from the sealed one
  expected_scope      the rerun's scope sidecar from the sealed one (sidecar_version 2, its own output)
  expected_sidecars   rules Q1b-Q4b: I50's Q1-Q4 with the rerun's document and the named changes
  comparison          rule C1: every metric of the sealed and the rerun target, read from their committed files
  sealed_files        the files under the sealed paths at a commit (git ls-tree), with their blob ids
  update_document     a synthetic holon-facts/0.3 document over one struct family, for rules U1-U3
  dead_code_detail    the detail pattern of rule D1
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "spec" / "M4" / "lib" / "heldout_rerun.json"
SEALED = "scroll"
RERUN = "scroll_i50b"
DOC = f"gen/targets/{RERUN}/facts/ScrollChain.extracted.json"
SEALED_DOC = f"gen/targets/{SEALED}/facts/ScrollChain.extracted.json"
FIXTURE = ROOT / "tests_m4" / "fixtures" / "i50b"
LABEL = "contaminated (post-seal change)"


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def protocol() -> dict:
    return load(PROTOCOL)


# ------------------------------------------------------------------ rule T1b and the scope sidecar
def _rewrite(x, old: str, new: str):
    if isinstance(x, dict):
        return {k: _rewrite(v, old, new) for k, v in x.items()}
    if isinstance(x, list):
        return [_rewrite(v, old, new) for v in x]
    if isinstance(x, str):
        return x.replace(old, new)
    return x


def drop_docs(x):
    """A description without its doc strings (keys named doc or ending in _doc), which T1b leaves free."""
    if isinstance(x, dict):
        return {k: drop_docs(v) for k, v in x.items() if not (k == "doc" or k.endswith("_doc"))}
    if isinstance(x, list):
        return [drop_docs(v) for v in x]
    return x


def expected_target(sealed: dict) -> dict:
    tr = protocol()["target"]
    old, new = tr["path_rewrite"]
    t = _rewrite(copy.deepcopy(sealed), old, new)
    t["name"] = tr["name"]
    t["names"] = list(tr["names"])
    co = t["checkout"]
    co.pop("sealed", None)
    co.pop("sealed_keys", None)
    co["rerun_of"] = SEALED
    co["contaminated"] = protocol()["contamination"]["label"]
    t["run"]["iteration"] = "I50b"
    t["run"]["sidecar_rules"] = "spec/M4/lib/heldout_rerun.json"
    return drop_docs(t)


def expected_scope(sealed_side: dict) -> dict:
    s = copy.deepcopy(sealed_side)
    s["sidecar_version"] = 2
    s["output"] = DOC
    return drop_docs(s)


# ------------------------------------------------------------------ rules Q1b-Q4b
def expected_sidecars(root: Path = ROOT) -> dict:
    def m3(n):
        return load(root / "spec" / "M3" / "lib" / f"{n}.json")
    ts = f"gen/targets/{RERUN}/lib/sort_types.json"
    st, un, di, fa = m3("sort_types"), m3("undo"), m3("disch"), m3("fact")
    return {
        "sort_types": {"sort_types_version": "holon-sort-types/0.2", "documents": [DOC], "seeds": st["seeds"],
                       "binding": None, "search": st["search"]},
        "undo": {"undo_version": "holon-undo/0.1", "sort_types": ts, "observation": un["observation"],
                 "premise": un["premise"], "search": un["search"]},
        "disch": {"disch_version": "holon-disch/0.1", "documents": [DOC], "binding": None, "model_sidecar": ts,
                  "hypotheses": {}, "search": di["search"]},
        "fact": {"fact_version": "holon-fact/0.1", "iteration": "I50b", "documents": [DOC], "sort_types": ts,
                 "binding": None, "hypotheses": {}, "search": fa["search"], "measure": fa["measure"],
                 "term_size": fa["term_size"]},
    }


# ------------------------------------------------------------------ rule C1
def _opt(p: Path):
    return load(p) if p.is_file() else None


def metrics(target: str, root: Path = ROOT) -> dict:
    """{metric: value} of one target by rule C1 (gate checks under gate.<c>, in report order)."""
    out = {}
    cov = _opt(root / "gen" / "targets" / target / "coverage.json")
    docs = (cov or {}).get("documents") or []
    out["coverage.statements"] = sum(d["statements"] for d in docs) if cov else None
    out["coverage.extracted"] = sum(d["extracted"] for d in docs) if cov else None
    out["coverage.unaccounted"] = sum(len(d["unaccounted"]) for d in docs) if cov else None
    out["coverage.debt_by_kind"] = dict(sorted(Counter(x["kind"] for d in docs for x in d["debt"]).items())) \
        if cov else None
    dias = sorted((root / "gen" / "diagrams" / target).glob("*.json"))
    dia = load(dias[0]) if len(dias) == 1 else None
    out["diagram.V"] = len(dia["carriers"]) if dia else None
    out["diagram.E"] = len(dia["edges"]) if dia else None
    gate = _opt(root / "results" / "targets" / target / "gate_report.json")
    out["gate"] = {c: v["passed"] for c, v in ((gate or {}).get("checks") or {}).items()}
    ref = _opt(root / "results" / "targets" / target / "derive_refusal.json")
    der = _opt(root / "gen" / "targets" / target / "laws" / "DERIVATION.json")
    out["derive.status"] = f"refused at {ref['step']}" if ref else ("derived" if der is not None else None)
    out["derive.laws"] = len(der["laws"]) if der is not None and not ref else None
    out["derive.by_rule_subform"] = dict(sorted(Counter(f"{x['rule']}/{x['subform']}" for x in der["laws"]).items())) \
        if der is not None and not ref else None
    rref = _opt(root / "results" / "targets" / target / "run_refusal.json")
    summ = _opt(root / "results" / "targets" / target / "records" / "summary.json")
    if rref:
        out["run.status"] = f"refused at {rref['step']}"
    elif summ:
        out["run.status"] = "decided"
    elif summ == {}:
        out["run.status"] = "no law"
    else:
        out["run.status"] = None
    out["run.by_status"] = dict(sorted(Counter(summ.values()).items())) if summ else None
    rep = _opt(root / "results" / "targets" / target / "replay.json")
    out["replay.entries"] = len(rep["laws"]) if rep is not None else None
    return out


def comparison_rows(root: Path = ROOT) -> list[dict]:
    s, r = metrics(SEALED, root), metrics(RERUN, root)
    rows = []
    for m in ("coverage.statements", "coverage.extracted", "coverage.unaccounted", "coverage.debt_by_kind",
              "diagram.V", "diagram.E"):
        rows.append({"metric": m, "sealed": s[m], "rerun": r[m], "contaminated": True})
    checks = list(s["gate"]) + [c for c in r["gate"] if c not in s["gate"]]
    for c in checks:
        rows.append({"metric": f"gate.{c}", "sealed": s["gate"].get(c), "rerun": r["gate"].get(c),
                     "contaminated": True})
    for m in ("derive.status", "derive.laws", "derive.by_rule_subform", "run.status", "run.by_status",
              "replay.entries"):
        rows.append({"metric": m, "sealed": s[m], "rerun": r[m], "contaminated": True})
    return rows


# ------------------------------------------------------------------ the sealed files
def sealed_files(commit: str, root: Path = ROOT) -> dict[str, str]:
    """{path: blob id} of every file under the protocol's sealed paths at a commit."""
    out = {}
    for p in protocol()["sealed"]["paths"]:
        txt = git("ls-tree", "-r", commit, "--", p, cwd=root)
        for ln in txt.splitlines():
            meta, path = ln.split("\t", 1)
            out[path] = meta.split()[2]
    return out


# ------------------------------------------------------------------ rules U1-U3: a synthetic document
def _u(base, member, v):
    return ["update", base, ["member", base, member], v]


S = ["storage", "S"]
U_A = _u(S, "a", ["param", "p"])                         # S with a := p
U_AB = _u(U_A, "b", ["param", "q"])                      # then b := q
U_DEEP = ["update", S, ["index", S, 0], ["param", "q"]]  # an element write: not a one-level member


def update_document() -> dict:
    """One struct family S {a, b, c} and one action whose records exercise U1-U3:
       writes[0]  S := (S with a := p, b := q)                      (U3: p flows into S.a, q into S.b, S.c nothing)
       guards[0]  (S with a := p).a == r                            (U2: a compare of act.p and act.r)
       guards[1]  (r ? (S with a := p) : S).a == q                  (U2 through '?': p and S.a flow into one value)
       guards[2]  (S with [0] := q).a == r                          (U2: a deeper update leaves the read fresh)"""
    fields = [{"name": "a", "type": "uint64"}, {"name": "b", "type": "uint64"}, {"name": "c", "type": "uint8"}]
    return {
        "facts_version": "holon-facts/0.3", "extraction": {"kind": "transitions"},
        "storage": [{"name": "S", "kind": "scalar", "value": "struct T", "fields": fields}],
        "inherited_storage": [],
        "actions": [{
            "name": "act",
            "params": [{"name": "p", "type": "uint64"}, {"name": "q", "type": "uint64"}, {"name": "r", "type": "uint64"}],
            "writes": [{"seq": 4, "src": "t.sol:9", "family": "S", "path": [], "value": U_AB, "cond": 1}],
            "guards": [
                {"src": "t.sol:1", "reaches": [{"seq": 1, "expr": ["==", ["member", U_A, "a"], ["param", "r"]]}]},
                {"src": "t.sol:2", "reaches": [{"seq": 2, "expr": [
                    "==", ["member", ["?", ["param", "r"], U_A, S], "a"], ["param", "q"]]}]},
                {"src": "t.sol:3", "reaches": [{"seq": 3, "expr": ["==", ["member", U_DEEP, "a"], ["param", "r"]]}]},
            ],
        }],
    }


DEAD_DETAIL = re.compile(r"^the condition of the if statement at (\S+) is the constant ([01]) at each of its "
                         r"([1-9][0-9]*) reach\(es\) by the walk, so this branch is never executed$")
