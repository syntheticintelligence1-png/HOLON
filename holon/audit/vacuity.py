"""Auditor A4 of audit round M2/2 (I21): vacuity and over-strength (whitepaper §9.5 A4, §12.3, L21). The contract is
the a4.json part of the docstring of tests_m2/test_audit_extraction.py; the instrument's fixed choices are the
degenerate_rule, representative_search and hypotheses of the frozen sidecar spec/M2/lib/audit_round2.json.

    python -m holon audit vacuity --milestone M2 --round 2 [--checkout PATH] [--out FILE] [--target COMMIT]
                                  [--work DIR] [--check]

What it does. As holon audit hostile: the target commit's tree is materialized in a scratch directory and every
repository input is read from there; the real code runs in scratch copies of the pinned checkout.

  laws        every results/M2/L_*.json and results/M2/extracted_m1/L_*.json. For a premised law (an assume premise
              or a Reach binder in its statement, laws/M2/<id>.json or laws/M1/<id>.json for an extracted_m1 record)
              that is PROVED, the record's inhabitant (non_vacuity.witness), else one the search finds, is replayed
              on the compiled model the record names (the record's artifacts.model, its sha256 checked against the
              record): replayed iff every action of every state binder's run succeeds from the initial state. The
              premises are evaluated there: for a SORT-site law, Reach (the replayed run) and at_site (the model's own
              hit_<x> ghost predicate); for any other law, every assume premise by holon/js/explore.mjs's evaluate
              mode on the compiled model. For a SORT-site law the site's subtraction is evaluated where the action
              evaluates it (the walk of holon.sorts.sites R8-R10, with every expression computed by a probe
              definition the model's own generator, holon.gen.machine, emits from the facts and appends to the
              compiled model), and site_operands are the operands of its first evaluation; the walk's evaluations
              must exist exactly when hit_<x> holds. A REFUTED premised law's counter-witness is evaluated the same
              way (source counter_witness) and never judged degenerate.
              degenerate: the sidecar's degenerate_rule (an empty run: initial_state; else a SORT-site law whose
              subtrahend is 0 at the inhabitant: zero_subtrahend). run_length counts the actions of the runs of the
              inhabitant's state binders (State or Reach) and of its Trace binders the statement runs from the
              initial state (run(p, s0)), summed; each of these runs is replayed. representative: for a degenerate inhabitant, the
              sidecar's representative_search (audit/rounds/M2/round2/harness/js/vacuity.mjs: breadth-first over
              runs of at most max_run_length successful actions of the facts' search policy, holon.gen.targetlib,
              from the initial state; at each state every policy action is tried as the inhabitant's action).
  hypotheses  every key of results/M2/hypotheses.json, as the round's hypothesis binding
              (audit/rounds/M2/round2/harness/hypotheses.json) says: a tested hypothesis runs the binding's harness
              items (audit/rounds/M2/round2/harness/go/holon_vacuity_test.go in the pinned checkout's Go workspace,
              solidity/HolonVacuity.t.sol in the round's Foundry project of the pinned contracts) on inputs this
              module generates, and is judged here by the binding's check; an untestable one carries the binding's
              reason. Implementations are the pinned checkout's code, its Go module graph, and the EVM; never holon/.
  canaries    A4's own sensitivity: a scratch copy of a premised PROVED law with a premise that contradicts one of
              its own, the record inhabitant of an equal-states law replaced by the initial state, and the binding's
              first equality hypothesis with its stated value altered. Never written to the repository.

Output: audit/rounds/M2/round2/a4.json (canonical JSON; no timestamps). --check rebuilds from the committed file's
target commit and compares byte for byte. A law or hypothesis finding is the id of the audit/M2_findings.jsonl line
of this round whose "a4_keys" holds "law|<record path>" or "hypothesis|<id>".
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .hostile import (FINDINGS, HARNESS, ROOT, ROUND, Ctx, GoWorkspace, HostileError, canonical,
                      chain_bytes, checkout_flags, default_checkout, git_checkout_head, hx, load, materialize,
                      resolve_commit, run, sol_project)

OUT = Path("audit") / "rounds" / "M2" / "round2" / "a4.json"
BINDING = HARNESS / "hypotheses.json"
RECORD = re.compile(r"results/M2/(extracted_m1/)?L_[^/]+\.json")
MAX_STATES = 400000          # the representative search's state cap (reported in its bound when reached)


class VacuityError(HostileError):
    pass


def log(msg: str) -> None:
    print(f"vacuity: {msg}", file=sys.stderr, flush=True)


def round_findings(root: Path = ROOT) -> dict[str, str]:
    """{a4 key: finding id} from this round's ledger lines ("a4_keys")."""
    p = Path(root) / FINDINGS
    out: dict[str, str] = {}
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        if line.strip():
            f = json.loads(line)
            if f.get("round") == ROUND:
                for k in f.get("a4_keys") or []:
                    out.setdefault(k, f["id"])
    return out


def premised(statement: dict) -> bool:
    return bool(statement.get("assume")) or any(b.get("type") == "Reach" for b in statement.get("binders", []))


def law_file(record: str) -> str:
    stem = Path(record).stem
    return f"laws/M1/{stem}.json" if "/extracted_m1/" in record else f"laws/M2/{stem}.json"


def records(tree: Path) -> list[str]:
    return sorted(p.relative_to(tree).as_posix() for p in (tree / "results" / "M2").rglob("L_*.json")
                  if RECORD.fullmatch(p.relative_to(tree).as_posix()))


# ---------------------------------------------------------------- compiled models and probes
class Probes:
    """Probe definitions: one Bend definition per expression the walk evaluates, emitted by the model's generator
    (holon.gen.machine.Machine.ex) over the expression's free variables, appended to the compiled model."""

    def __init__(self, m):
        from ..gen.machine import bname, bt
        self.m, self.bname, self.bt = m, bname, bt
        self.defs: list[str] = []
        self.memo: dict = {}

    def expr(self, e, env: dict) -> dict:
        fv = sorted(self.m.fv(e))
        missing = [v for v in fv if v not in env]
        if missing:
            raise VacuityError(f"probe of {json.dumps(e)}: {missing} are not bound where it is evaluated")
        key = (json.dumps(e, sort_keys=True), tuple((v, env[v]) for v in fv))
        if key not in self.memo:
            text, ty = self.m.ex(e, env)
            name = f"i21_e{len(self.defs)}"
            params = ", ".join(f"+{self.bname(v)}: {self.bt(env[v])}" for v in fv)
            self.defs.append(f"def {name}({params}) -> {self.bt(ty)}:\n  {text}\n")
            self.memo[key] = ({"fn": name, "args": [self.bname(v) for v in fv]}, ty)
        return self.memo[key][0]

    def type_of(self, e, env: dict) -> str:
        return self.m.ex(e, env)[1]

    def conds(self, conds, env: dict) -> list:
        return [{"e": self.expr(c, env), "pol": bool(p)} for c, p in conds]

    def text(self) -> str:
        return "\n# ---- I21 probes (holon/audit/vacuity.py): one definition per expression the A4 walk evaluates\n\n" \
            + "\n".join(self.defs)


def site_plan(P: Probes, facts: dict, entry: dict, real: set) -> dict:
    """The walk of one SORT-site law (mirrors holon.sorts.sites.Ghost: hits, positions, path conditions)."""
    from ..sorts import sites as S
    m = P.m
    b = entry["basis"]
    site = {"id": b["site_id"], "model": b["model"], "span": b["span"], "expr": b["expr"]}
    live = S.recompute_sites(site["model"], facts, m.lib.builtins)
    if site["id"] not in live:
        raise VacuityError(f"{entry['law_id']}: the facts hold no site {site['id']}")
    site["occurrences"] = live[site["id"]]["occurrences"]
    hs = S.hits_internal(facts, site, real)
    got = [{k: h[k] for k in ("action", "at", "kind", "via") if k in h} for h in hs]
    if got != entry["hits"]:
        raise VacuityError(f"{entry['law_id']}: the facts give the hits {got}, DERIVATION.json says {entry['hits']}")
    minus = site["expr"]
    defsite = S.is_def_site(site)
    reach = S.reaching(facts, site) if defsite else {}
    D = set(S.site_defs(site)) if defsite else set()
    plan: dict = {"hit": f"hit_{S.ghost_x(entry['law_id'])}", "actions": {}, "defs": {}}

    def node(env):
        return {"min": P.expr(minus[1], env), "sub": P.expr(minus[2], env)}
    for f in sorted(reach):
        d = facts["defs"][f]
        env = {p: t for p, t in d["params"]}
        env.update(m.tab_env(m.def_uses(f)))
        pos = []
        if f in D:
            for conds in S.node_positions(d["body"], minus):
                pos.append({"conds": P.conds(conds, env), "node": node(env)})
        for g, n, conds in S.call_positions(d["body"], reach):
            if g != f:
                pos.append({"conds": P.conds(conds, env), "call": {"def": g, "args": [P.expr(y, env) for y in n[2:]]}})
        plan["defs"][f] = {"params": [P.bname(p) for p, _ in d["params"]], "positions": pos}
    acts = {a["name"]: a for a in facts["actions"]}
    by_action: dict = {}
    for h in hs:
        by_action.setdefault(h["action"], []).append(h)
    for an, hl in sorted(by_action.items()):
        a = acts[an]
        env = {**{f: t for f, t in m.state}, **{i: t for i, t in a["inputs"]}, **m.tab_env(m.threaded)}

        def positions(hits, env=env, a=a):
            out = []
            for h in hits:
                if h["kind"] == "call":
                    e = S.entry_expr(a, h["at"])
                    for g, n, conds in S.call_positions(e, reach):
                        out.append({"conds": P.conds(conds, env),
                                    "call": {"def": g, "args": [P.expr(y, env) for y in n[2:]]}})
                else:
                    for w in h["occurrences"]:
                        e = S.entry_expr(a, w.split(".")[0] if w.startswith("guards[") else w)
                        for conds in S.node_positions(e, minus):
                            out.append({"conds": P.conds(conds, env), "node": node(env)})
            return out
        at_guard: dict = {}
        at_effects: list = []
        for h in hl:
            if h["at"].startswith("guards["):
                at_guard.setdefault(int(h["at"][7:-1]), []).append(h)
            else:
                at_effects.append(h)
        guards = a.get("guards", [])
        last = len(guards) if at_effects else max(at_guard)
        steps = []
        for i, g in enumerate(guards):
            if i in at_guard:
                steps.append({"k": "hit", "positions": positions(at_guard[i])})
            if i == last:
                break
            if "let" in g:
                steps.append({"k": "let", "name": P.bname(g["let"]), "e": P.expr(g["expr"], env)})
                env[g["let"]] = P.type_of(g["expr"], env)
            else:
                steps.append({"k": "req", "e": P.expr(g["require"], env)})
        if at_effects:
            steps.append({"k": "hit", "positions": positions(at_effects)})
        plan["actions"][an] = {"inputs": [P.bname(i) for i, _ in a["inputs"]], "steps": steps}
    return plan


def compile_module(text: str, name: str, work: Path, cfg: dict) -> Path:
    from .. import bend
    d = work / "models" / hashlib.sha256(text.encode()).hexdigest()[:16]
    d.mkdir(parents=True, exist_ok=True)
    src = d / f"{name}.bend"
    art = src.with_suffix(".mjs")
    if not art.exists():
        src.write_text(text)
        log(f"bend: compiling {src.name} ({len(text.splitlines())} lines)")
        r = bend.run([src.name, "-o", art.name], cwd=d, cfg=cfg)
        if r.code != 0 or not art.exists():
            raise VacuityError(f"bend failed to compile {src}: {r.out[:2000]}")
    return art


class Model:
    """One compiled model a record names: the committed model text (its sha256 checked against the records), with
    the probes of the site laws of its facts appended."""

    def __init__(self, ctx: Ctx, rel: str, recs: dict[str, dict], laws: dict[str, dict]):
        from ..sorts import sites as S
        self.ctx, self.rel = ctx, rel
        self.text = (ctx.tree / rel).read_text()
        sha = hashlib.sha256(self.text.encode()).hexdigest()
        for p, r in recs.items():
            if r.get("model_sha256") != sha:
                raise VacuityError(f"{p}: model_sha256 {r.get('model_sha256')} is not that of {rel} ({sha})")
        self.site_laws = {p: laws[p] for p in recs if S.LAW_PREFIX in Path(p).stem and laws[p].get("subform") == "site"}
        facts_rels = sorted({laws[p]["facts"] for p in recs})
        self.facts_rel = None
        self.m = None
        self.plans: dict = {}
        if self.site_laws:
            if len(facts_rels) != 1:
                raise VacuityError(f"{rel}: the records name several facts {facts_rels}")
            self.facts_rel = facts_rels[0]
            m, facts, base = S.run_machine("M2", ctx.tree / self.facts_rel, ctx.tree)
            if not self.text.startswith(base.rstrip("\n") + "\n\n" + S.GHOST_MARKER + "\n"):
                raise VacuityError(f"{rel} is not the generator's model of {self.facts_rel} with its ghost section")
            self.m, self.facts = m, facts
            der = load(ctx.tree, "laws/M2/DERIVATION.json")
            entries = {e["law_id"]: e for e in der["laws"]}
            _, _, real = S.load_sidecar("M2", ctx.tree)
            P = Probes(m)
            for p, law in sorted(self.site_laws.items()):
                self.plans[law["law_id"]] = site_plan(P, facts, entries[law["law_id"]], real)
            for n in [f for f, _ in m.state] + [i for a in facts["actions"] for i, _ in a["inputs"]]:
                if P.bname(n) != n:
                    raise VacuityError(f"{n}: a name the harness cannot carry (a Bend keyword)")
            self.text = self.text + P.text()
        self.art = compile_module(self.text, Path(rel).stem, ctx.work, load_cfg(ctx))

    def harness_facts(self, facts: dict) -> dict:
        return {"actions": [{"name": a["name"], "inputs": a["inputs"]} for a in facts["actions"]],
                "params": facts.get("params", {}), **({"search": facts["search"]} if "search" in facts else {}),
                **({"policy": facts["policy"]} if "policy" in facts else {})}


def load_cfg(ctx: Ctx) -> dict:
    from .. import bend
    return bend.config(ctx.tree)


def run_js(script: Path, req: dict, timeout: int = 7200) -> dict:
    p = subprocess.run(["node", str(script)], input=json.dumps(req), capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise VacuityError(f"{script.name} failed: {p.stderr[-3000:]}")
    return json.loads(p.stdout)


def policy_module(tree: Path, facts_rel: str) -> str:
    from ..gen import targetlib
    h = targetlib.hints_for(tree / facts_rel)
    return str(h) if h else str(ROOT / "holon" / "js" / "policy_gen.mjs")


def explore_eval(art: Path, facts: dict, law: dict, assignment: dict) -> dict:
    return run_js(ROOT / "holon" / "js" / "explore.mjs",
                  {"module": str(art), "facts": facts, "hints": None, "law": law, "evaluate": assignment}, 600)


def explore_search(art: Path, facts: dict, law: dict) -> dict:
    from .. import inhabit
    s = inhabit.search_law(law)
    r = run_js(ROOT / "holon" / "js" / "explore.mjs", {"module": str(art), "facts": facts, "hints": None, "law": s,
                                                       "budget": {"noPerturb": True}})
    return r


# ---------------------------------------------------------------- one law
def state_binders(stmt: dict) -> list[str]:
    return [b["name"] for b in stmt["binders"] if b["type"] in ("State", "Reach")]


def prefix_traces(stmt: dict) -> list[str]:
    """Trace binders the statement runs from the initial state (run(p, s0)): their value is a state's run too."""
    out: list = []

    def walk(t):
        if isinstance(t, dict):
            r, f = t.get("run"), t.get("from")
            if isinstance(r, dict) and set(r) == {"var"} and isinstance(f, dict) and set(f) == {"s0"}:
                if r["var"] not in out:
                    out.append(r["var"])
            for x in t.values():
                walk(x)
        elif isinstance(t, list):
            for x in t:
                walk(x)
    walk([stmt.get("assume", []), stmt.get("claim")])
    return [b["name"] for b in stmt["binders"] if b["type"] == "Trace" and b["name"] in out]


def runs_of(stmt: dict, w: dict) -> list[list]:
    """The runs from the initial state of an assignment: every state binder's, then every prefix trace's."""
    out = []
    for n in state_binders(stmt):
        v = w.get(n)
        if isinstance(v, dict) and isinstance(v.get("run"), list):
            out.append(v["run"])
        elif v is not None:
            raise VacuityError(f"state binder {n} is not a run from the initial state: {json.dumps(v)[:200]}")
    for n in prefix_traces(stmt):
        if isinstance(w.get(n), list):
            out.append(w[n])
    return out


def degenerate_of(run_length: int, ops) -> tuple[bool, str | None]:
    """The sidecar's degenerate_rule: an empty run (initial_state wins), else a zero subtrahend (zero_subtrahend)."""
    if run_length == 0:
        return True, "initial_state"
    if ops is not None and int(ops["subtrahend"]) == 0:
        return True, "zero_subtrahend"
    return False, None


def tables_of(m, w: dict) -> dict:
    """{table variable: table} of a witness's oracle parameters ({"table": [[k, v]..]}; an instance is not a table
    here: the empty one stands for it, as the site laws' ghost predicates are evaluated with)."""
    out = {}
    for p in (m.oparams if m is not None else {}):
        v = w.get(p)
        out[m.tvar[p]] = [list(x) for x in (v or {}).get("table", [])] if isinstance(v, dict) else []
    return out


def act_binder(stmt: dict) -> str | None:
    acts = [b["name"] for b in stmt["binders"] if b["type"] == "Act"]
    return acts[0] if len(acts) == 1 else None


class Lab:
    """The runs of one compiled model: replay and walk jobs on vacuity.mjs, premise evaluation on explore.mjs."""

    def __init__(self, ctx: Ctx, M: Model, facts: dict, policy: str):
        self.ctx, self.M, self.facts, self.policy = ctx, M, facts, policy
        self.script = ctx.harness("js/vacuity.mjs")

    def request(self, jobs: list, search: dict | None = None) -> dict:
        m = self.M.m
        req = {"module": str(self.M.art), "facts": self.M.harness_facts(self.facts), "policy": self.policy,
               "state": [f for f, _ in m.state] if m is not None else [f for f, *_ in self.facts["state"]],
               "tables": {m.tvar[p]: p for p in m.threaded} if m is not None else {},
               "plans": self.M.plans, "jobs": jobs, "search": search}
        return run_js(self.script, req)


def evaluate_inhabitant(lab: Lab, path: str, law: dict, w: dict, source: str) -> dict:
    """{source, run_length, replayed, premises_hold, site_operands[, evaluations]} of one inhabitant."""
    stmt = law["statement"]
    runs = runs_of(stmt, w)
    rl = sum(len(r) for r in runs)
    m = lab.M.m
    site = law.get("subform") == "site" and law["law_id"] in lab.M.plans
    a = act_binder(stmt)
    job = {"id": path, "law": law["law_id"] if site else None, "runs": runs,
           "act": w.get(a) if (site and a) else None, "tabs": tables_of(m, w)}
    r = lab.request([job])["jobs"][path]
    out = {"source": source, "run_length": rl, "replayed": bool(r["replayed"]), "premises_hold": False,
           "site_operands": None}
    if r["failed_at"] is not None:
        out["failed_at"] = r["failed_at"]
    if site:
        ev = r["evaluations"] or []
        if bool(ev) != bool(r["hit"]):
            raise VacuityError(f"{path}: the walk found {len(ev)} evaluations where hit is {r['hit']}")
        out["premises_hold"] = bool(r["replayed"] and r["hit"])
        if ev:
            out["site_operands"] = {"minuend": int(ev[0][0]), "subtrahend": int(ev[0][1])}
            out["evaluations"] = len(ev)
    else:
        e = explore_eval(lab.M.art, lab.facts, law, w)
        out["premises_hold"] = bool(r["replayed"] and all(e["premises"]))
        out["premises"] = [bool(x) for x in e["premises"]]
    return out


def representatives(lab: Lab, laws: list[str]) -> tuple[dict, str]:
    side = lab.ctx.side["representative_search"]
    r = lab.request([], {"laws": laws, "max_run_length": side["max_run_length"], "max_states": MAX_STATES,
                         "any": False})
    return r["search"], r["bound"]


def judge_law(lab: Lab | None, path: str, rec: dict, law: dict, findings: dict) -> dict:
    stmt = law["statement"]
    v = {"status": rec["status"], "premised": premised(stmt), "inhabitant": None, "satisfiable": None,
         "degenerate": None, "degenerate_reason": None, "representative": None, "finding": None,
         "model": rec.get("artifacts", {}).get("model")}
    nv = rec.get("non_vacuity") or {}
    if not v["premised"] or rec["status"] not in ("PROVED", "REFUTED") or lab is None:
        v["finding"] = findings.get(f"law|{path}")
        return v
    if rec["status"] == "REFUTED":
        w = rec.get("witness")
        if w:
            v["inhabitant"] = evaluate_inhabitant(lab, path, law, w, "counter_witness")
        v["finding"] = findings.get(f"law|{path}")
        return v
    w = nv.get("witness")
    source = "record"
    if not w:
        source = "search"
        w = search_inhabitant(lab, law)
    if w:
        v["inhabitant"] = evaluate_inhabitant(lab, path, law, w, source)
        inh = v["inhabitant"]
        v["satisfiable"] = bool(inh["replayed"] and inh["premises_hold"])
        if v["satisfiable"]:
            deg, why = degenerate_of(inh["run_length"], inh["site_operands"])
            v["degenerate"], v["degenerate_reason"] = deg, why
    if v["satisfiable"] is not True:
        # the record's (or the search's) inhabitant does not inhabit the premises: search for one before judging
        w2 = search_inhabitant(lab, law)
        if w2:
            inh2 = evaluate_inhabitant(lab, path, law, w2, "search")
            if inh2["replayed"] and inh2["premises_hold"]:
                v["inhabitant"], v["satisfiable"] = inh2, True
                deg, why = degenerate_of(inh2["run_length"], inh2["site_operands"])
                v["degenerate"], v["degenerate_reason"] = deg, why
        if v["satisfiable"] is not True:
            v["satisfiable"] = False
            v["unsatisfiable_bound"] = "no inhabitant: the record's does not satisfy the premises and the search found none"
    v["finding"] = findings.get(f"law|{path}")
    return v


def search_inhabitant(lab: Lab, law: dict) -> dict | None:
    """An inhabitant the search finds: a SORT-site law's by the breadth-first walk (any state, the initial one
    included); any other law's by holon/js/explore.mjs on the law with its claim replaced (holon.inhabit.search_law)."""
    if law.get("subform") == "site" and law["law_id"] in lab.M.plans:
        side = lab.ctx.side["representative_search"]
        r = lab.request([], {"laws": [law["law_id"]], "max_run_length": side["max_run_length"],
                             "max_states": MAX_STATES, "any": True})["search"][law["law_id"]]
        if r is None:
            return None
        stmt = law["statement"]
        w = {state_binders(stmt)[0]: {"run": r["run"]}, act_binder(stmt): r["act"]}
        for b in stmt["binders"]:
            if b["name"] not in w and lab.M.m is not None and b["name"] in lab.M.m.oparams:
                w[b["name"]] = {"table": []}
        return w
    r = explore_search(lab.M.art, lab.facts, law)
    return r.get("witness")


# ---------------------------------------------------------------- the laws part
def laws_part(ctx: Ctx, findings: dict) -> tuple[dict, dict]:
    tree = ctx.tree
    paths = records(tree)
    recs = {p: load(tree, p) for p in paths}
    laws = {p: load(tree, law_file(p)) for p in paths}
    by_model: dict[str, list] = {}
    for p in paths:
        st = laws[p]["statement"]
        if premised(st) and recs[p]["status"] in ("PROVED", "REFUTED"):
            by_model.setdefault(recs[p]["artifacts"]["model"], []).append(p)
    labs: dict = {}
    for rel, ps in sorted(by_model.items()):
        M = Model(ctx, rel, {p: recs[p] for p in ps}, {p: laws[p] for p in ps})
        facts_rel = M.facts_rel
        if facts_rel is None:   # a model compiled from another facts file than the laws': the records' own facts
            fr = sorted({recs[p].get("facts") or f"gen/M2/extracted/{Path(rel).stem}.json" for p in ps})
            facts_rel = fr[0]
            sha = hashlib.sha256((tree / facts_rel).read_bytes()).hexdigest()
            for p in ps:
                if recs[p].get("facts_sha256") != sha:
                    raise VacuityError(f"{p}: facts_sha256 is not that of {facts_rel}")
        facts = load(tree, facts_rel)
        lab = Lab(ctx, M, facts, policy_module(tree, facts_rel))
        for p in ps:
            labs[p] = lab
    out = {}
    for p in paths:
        log(p)
        out[p] = judge_law(labs.get(p), p, recs[p], laws[p], findings)
    # representatives of the degenerate inhabitants, one search per model
    by_lab: dict = {}
    for p, v in out.items():
        if v["degenerate"]:
            by_lab.setdefault(id(labs[p]), (labs[p], []))[1].append(p)
    for _, (lab, ps) in sorted(by_lab.items(), key=lambda kv: kv[1][1]):
        site = [p for p in ps if laws[p].get("subform") == "site" and laws[p]["law_id"] in lab.M.plans]
        found, bound = representatives(lab, [laws[p]["law_id"] for p in site]) if site else ({}, None)
        for p in ps:
            r = found.get(laws[p]["law_id"])
            v = out[p]
            if r is not None:
                stmt = laws[p]["statement"]
                w = {state_binders(stmt)[0]: {"run": r["run"]}, act_binder(stmt): r["act"]}
                inh = evaluate_inhabitant(lab, p, laws[p], w, "search")
                v["representative"] = {k: inh[k] for k in ("run_length", "replayed", "premises_hold", "site_operands")}
                v["representative"]["inhabitant"] = w
            v["representative_bound"] = bound if p in site else \
                "no representative search for a law without a SORT site (the sidecar's search walks site hits)"
    return out, {"laws": laws, "recs": recs, "labs": labs}


# ---------------------------------------------------------------- hypotheses
def binding(ctx: Ctx) -> dict:
    return json.loads((ROOT / BINDING).read_text())


def domain_sample(ty: str) -> list:
    """The fixed sample of a domain (the same as I12's oracle check, holon.oracle_check: the values, not the
    implementation)."""
    if ty == "List<Nat>":
        vals = range(16)
        return [[]] + [[a] for a in vals] + [[a, b] for a in vals for b in vals]
    if ty == "Nat":
        return list(range(256))
    raise VacuityError(f"no sample for the domain {ty}")


class Runner:
    """The harness items: Go (the round's header package, in the pinned checkout's workspace) and Solidity (the
    round's Foundry project), each run once per item and input list (memoized)."""

    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.memo: dict = {}
        self._go = None

    def go(self, inp: dict) -> list:
        key = ("go", json.dumps(inp, sort_keys=True))
        if key not in self.memo:
            pkg = sorted(self.ctx.side["surfaces"]["go_header"]["packages"])[0]
            if self._go is None:
                self._go = GoWorkspace(self.ctx.checkout, self.ctx.work, [pkg])
            self.memo[key] = self._go.test(pkg, self.ctx.harness("go/holon_vacuity_test.go"), "TestHolonVacuity",
                                           inp, "vacuity")
        return self.memo[key]

    def sol(self, item: str, cases: list[bytes]) -> list[str]:
        key = ("sol", item, hashlib.sha256(b"".join(len(c).to_bytes(4, "big") + c for c in cases)).hexdigest())
        if key in self.memo:
            return self.memo[key]
        if any(not c for c in cases):
            raise VacuityError("an empty case cannot be passed to the Solidity harness (\"0x\" ends the input)")
        proj = sol_project(self.ctx, "sol_vacuity")
        fin, fout = proj / "holon_vacuity_in.txt", proj / "holon_vacuity_out.txt"
        fin.write_text("\n".join(["0x" + c.hex() for c in cases] + ["0x"]) + "\n")
        fout.unlink(missing_ok=True)
        code, out = run(["nice", "-n", "10", self.ctx.tc["forge"], "test", "--match-contract", "^HolonVacuityTest$",
                         "--match-test", "^test_vacuity\\(\\)$", "--offline", "--use", self.ctx.tc["solc"]], proj,
                        {"HOLON_VACUITY_ITEM": item, "HOLON_HOSTILE_IN": fin.name, "HOLON_HOSTILE_OUT": fout.name})
        lines = fout.read_text().splitlines() if fout.exists() else []
        if code != 0 or not lines or lines[-1] != f"done {len(cases)}":
            raise VacuityError(f"Solidity harness item {item} failed (exit {code}, {len(lines)} lines): {out[-3000:]}")
        fin.unlink(missing_ok=True)
        fout.unlink(missing_ok=True)
        self.memo[key] = lines[:-1]
        return self.memo[key]


def _abi(types: list[str], values: list) -> bytes:
    from .. import evm_abi as A
    return A.encode_args([{"type": t} for t in types], values)


def check_cf(R: Runner, h: dict, oracle: dict) -> dict:
    ty = oracle["parameter"]["type"]
    dom = re.fullmatch(r"Fn<(.+),(.+)>", ty).group(1)
    xs = domain_sample(dom)
    words = [[hx(int(v).to_bytes(32, "big")) for v in (x if isinstance(x, list) else [x])] for x in xs]
    cases = [_abi(["bytes32[]"], [w]) for w in words]
    lines = R.sol(h["run"]["item"], cases)
    images = [ln.split(" ")[1] for ln in lines]
    seen: dict = {}
    for x, d in zip(xs, images):
        if d in seen:
            return {"result": "fail", "sample": len(xs), "counterexample": {"x": seen[d], "y": x, "image": d}}
        seen[d] = x
    return {"result": "pass", "sample": len(xs), "counterexample": None}


def check_cf_agree(R: Runner, h: dict, ctx: Ctx) -> dict:
    spec = h["inputs"]
    hdrs = []
    for v, n in sorted(spec["lengths"].items(), key=lambda kv: int(kv[0])):
        for k in range(spec["per_version"]):
            hdrs.append(bytes([int(v)]) + chain_bytes(ctx.seed, f"{h['id']}:{v}:{k}", n - 1))
    sol = R.sol(h["runs"]["solidity"], hdrs)
    gol = [ln for ln in R.go({h["runs"]["go"]: [hx(x) for x in hdrs]}) if ln[0] == "H"]
    if len(sol) != len(hdrs) or len(gol) != len(hdrs):
        raise VacuityError(f"{h['id']}: the harnesses answered {len(sol)} and {len(gol)} of {len(hdrs)} headers")
    seen: dict = {}
    for i, (x, s, g) in enumerate(zip(hdrs, sol, gol)):
        _, ok, sh = s.split(" ")
        gh = g[2].lower()
        if ok != "1" or gh.startswith("error"):
            return {"result": "fail", "sample": len(hdrs), "counterexample": {
                "header": hx(x), "solidity": "ok" if ok == "1" else f"revert {sh}", "go": gh,
                "why": "an in-domain header one side's loader rejects"}}
        if sh.lower() != gh:
            return {"result": "fail", "sample": len(hdrs), "counterexample": {
                "header": hx(x), "solidity": sh, "go": gh, "why": "the two sides' batch hashes differ"}}
        if gh in seen:
            return {"result": "fail", "sample": len(hdrs), "counterexample": {
                "x": hx(hdrs[seen[gh]]), "y": hx(x), "image": gh, "why": "two headers share a batch hash"}}
        seen[gh] = i
    return {"result": "pass", "sample": len(hdrs), "counterexample": None}


def source_value(ctx: Ctx, src: dict) -> str:
    """The 32-byte hex literal of a named constant's declaration in a source file of the pinned checkout."""
    text = (ctx.checkout / src["path"]).read_text()
    for n, line in enumerate(text.splitlines(), 1):
        if re.search(rf"\b{re.escape(src['name'])}\b", line):
            m = re.search(r"0x[0-9a-fA-F]{64}", line)
            if m:
                return m.group(0).lower()
    raise VacuityError(f"{src['path']}: no 32-byte literal declares {src['name']}")


def check_equal(R: Runner, h: dict, ctx: Ctx, alter: bool = False) -> dict:
    vals = []
    for ln in R.go({h["runs"]["go"]: True}):
        if ln[0] == "K":
            vals += [("computed", ln[1].lower()), ("go constant", ln[2].lower())]
    for src in h.get("sources", []):
        v = source_value(ctx, src)
        vals.append((f"{src['path']} {src['name']}", v))
    if alter:   # the canary: the stated value altered in its last nibble
        k, v = vals[-1]
        vals[-1] = (k, v[:-1] + ("0" if v[-1] != "0" else "1"))
    first = vals[0][1]
    bad = [(k, v) for k, v in vals if v != first]
    if bad:
        return {"result": "fail", "sample": len(vals), "counterexample": {"values": dict(vals)}}
    return {"result": "pass", "sample": len(vals), "counterexample": None, "value": first}


def check_queue_append(R: Runner, h: dict) -> dict:
    spec = h["inputs"]
    cases = []
    for to in spec["targets"]:
        for value in spec["values"]:
            for msg in spec["messages"]:
                for gas in spec["gas_limits"]:
                    cases.append((to, value, msg, gas))
    lines = R.sol(h["runs"]["solidity"], [_abi(["address", "uint256", "bytes", "uint256"], list(c)) for c in cases])
    n_ok, bad = 0, []
    for c, ln in zip(cases, lines):
        _, ok, before, after, nlogs, idx = ln.split(" ")
        before, after, nlogs = int(before), int(after), int(nlogs)
        if ok == "1":
            n_ok += 1
            good = after == before + 1 and nlogs == 1 and idx == str(before)
        else:
            good = after == before and nlogs == 0
        if not good:
            bad.append({"message": {"to": c[0], "value": c[1], "data": c[2], "gas_limit": c[3]},
                        "succeeded": ok == "1", "next_index": [before, after], "queued": nlogs, "queue_indices": idx})
    return {"result": "fail" if bad else "pass", "sample": len(cases), "violations": len(bad),
            "counterexample": bad[0] if bad else None, "succeeded": n_ok}


def check_registry(R: Runner, h: dict) -> dict:
    """isActive holds exactly for staked (stake > 0), unslashed principals, and the deposit keeps its initial value:
    every observation after every step of every operation sequence (breadth-first, length 1..max)."""
    spec = h["inputs"]
    seqs: list = [[]]
    allseq = []
    for _ in range(spec["max_length"]):
        seqs = [s + [o] for s in seqs for o in range(spec["ops"])]
        allseq += seqs
    lines = R.sol(h["runs"]["solidity"], [_abi(["uint8[]"], [s]) for s in allseq])
    first: dict = {}
    for ln in lines:
        i, k, op, ok, reg, stake, wd, slashed, active, dep, mins = ln.split(" ")
        seq = allseq[int(i)][:int(k) + 1]
        staked = int(stake) > 0 and slashed == "0"
        if (active == "1") != staked and "active" not in first:
            first["active"] = {"operations": [spec["names"][x] for x in seq], "isActive": active == "1",
                               "stake": stake, "registered": reg == "1", "withdrawing": wd == "1",
                               "slashed": slashed == "1", "minimumStake": mins}
        if dep != spec["initial_deposit"] and "deposit" not in first:
            first["deposit"] = {"operations": [spec["names"][x] for x in seq], "challengeDeposit": dep,
                                "initial": spec["initial_deposit"]}
    n = len(lines)
    if first:
        return {"result": "fail", "sample": n, "counterexample": first}
    return {"result": "pass", "sample": n, "counterexample": None}


def check_roundtrip(R: Runner, h: dict) -> dict:
    lines = [ln for ln in R.go({h["runs"]["go"]: True}) if ln[0] == "T"]
    produced = [ln for ln in lines if not str(ln[4]).startswith("encode:")]
    bad = [{"transaction": ln[2], "detail": ln[4]} for ln in produced if not ln[3]]
    return {"result": "fail" if bad else "pass", "sample": len(produced), "violations": len(bad),
            "counterexample": bad[0] if bad else None,
            "not_encoded": sorted({ln[2] + ": " + ln[4] for ln in lines if str(ln[4]).startswith("encode:")})}


def check_padded_decode(R: Runner, h: dict, ctx: Ctx) -> dict:
    spec = h["inputs"]
    cases = []
    for n in spec["lengths"]:
        for kind in spec["contents"]:
            if kind == "chain":
                x = chain_bytes(ctx.seed, f"{h['id']}:{n}", n)
            elif kind == "zeros":
                x = bytes(n)
            else:
                x = (bytes(range(256)) * (n // 256 + 1))[:n]
            for pad in spec["pads"]:
                cases.append((x, pad, kind))
    inp = [{"x": hx(x), "pad": pad} for x, pad, _ in cases]
    lines = [ln for ln in R.go({h["runs"]["go"]: inp}) if ln[0] == "Z"]
    sample, bad, not_encoded = 0, [], 0
    for (x, pad, kind), ln in zip(cases, lines):
        res = ln[3]
        if res.startswith("enc_error"):
            not_encoded += 1   # x outside the encoder's domain: no Enc x to decode
            continue
        sample += 1
        if res != f"ok:{hashlib.sha256(x).hexdigest()}:{len(x)}":
            bad.append({"x_length": len(x), "x_kind": kind, "encoded_length": ln[2], "pad": pad, "decoded": res})
    return {"result": "fail" if bad else "pass", "sample": sample, "counterexample": bad[0] if bad else None,
            "violations": len(bad), "not_encoded": not_encoded,
            "violating_x_lengths": sorted({b["x_length"] for b in bad})}


def hypotheses_part(ctx: Ctx, findings: dict, R: Runner) -> dict:
    keys = sorted(load(ctx.tree, "results/M2/hypotheses.json"))
    B = binding(ctx)["hypotheses"]
    oracles = {e["hypothesis"]["id"]: e for e in load(ctx.tree, "spec/M2/lib/oracles.json")["oracles"]}
    out = {}
    for k in keys:
        h = dict(B.get(k) or {"verdict": "untestable", "reason": "the round's hypothesis binding has no entry"})
        h["id"] = k
        v = {"verdict": h["verdict"], "result": None, "implementation": h.get("implementation"),
             "test": h.get("test") or "", "sample": None, "counterexample": None, "reason": h.get("reason"),
             "finding": findings.get(f"hypothesis|{k}")}
        if h["verdict"] == "tested":
            log(f"hypothesis {k} ({h['check']})")
            r = run_check(R, h, oracles.get(k), ctx)
            v.update({"result": r.pop("result"), "sample": r.pop("sample"), "counterexample": r.pop("counterexample")})
            if r:
                v["observed"] = r
            v["reason"] = None
        else:
            v["implementation"] = None
            v["test"] = h.get("test") or "not run: " + (h.get("reason") or "")
        out[k] = v
    return out


def run_check(R: Runner, h: dict, oracle: dict | None, ctx: Ctx, alter: bool = False) -> dict:
    c = h["check"]
    if c == "cf":
        return check_cf(R, h, oracle)
    if c == "cf_agree":
        return check_cf_agree(R, h, ctx)
    if c == "equal":
        return check_equal(R, h, ctx, alter)
    if c == "queue_append":
        return check_queue_append(R, h)
    if c == "registry":
        return check_registry(R, h)
    if c == "roundtrip":
        return check_roundtrip(R, h)
    if c == "padded_decode":
        return check_padded_decode(R, h, ctx)
    raise VacuityError(f"{h['id']}: unknown check {c}")


# ---------------------------------------------------------------- canaries (attack A9)
def canaries(ctx: Ctx, lawsv: dict, aux: dict, R: Runner) -> list[dict]:
    out = []
    laws, recs, labs = aux["laws"], aux["recs"], aux["labs"]
    # 1. an unsatisfiable premise: the first premised PROVED non-site law with an assume premise "X == true" gets
    #    "X == false" too; its record inhabitant is replayed and the search runs
    cand = [p for p in sorted(lawsv) if lawsv[p]["status"] == "PROVED" and lawsv[p]["premised"]
            and laws[p]["statement"].get("assume") and laws[p].get("subform") != "site"]
    done = False
    for p in cand:
        law = copy.deepcopy(laws[p])
        prem = law["statement"]["assume"]
        flip = next((x for x in prem if isinstance(x.get("eq"), list) and x["eq"][1] == {"bool": True}), None)
        if flip is None:
            continue
        prem.append({"eq": [flip["eq"][0], {"bool": False}]})
        v = judge_law(labs[p], p, recs[p], law, {})
        out.append({"kind": "unsatisfiable_premise", "what": f"{p} with the premise {json.dumps(flip['eq'][0])} == "
                    "false added to its own == true", "detected": v["satisfiable"] is False,
                    "satisfiable": v["satisfiable"]})
        done = True
        break
    if not done:
        out.append({"kind": "unsatisfiable_premise", "what": "no premised PROVED law with a boolean premise",
                    "detected": False})
    # 2. a degenerate inhabitant: the first premised PROVED law with two state binders, both at the initial state
    cand = [p for p in sorted(lawsv) if lawsv[p]["status"] == "PROVED" and lawsv[p]["premised"]
            and len(state_binders(laws[p]["statement"])) >= 2]
    if cand:
        p = cand[0]
        w = copy.deepcopy(recs[p]["non_vacuity"]["witness"])
        for n in state_binders(laws[p]["statement"]):
            w[n] = {"run": []}
        for b in laws[p]["statement"]["binders"]:
            if b["type"] == "Trace":
                w[b["name"]] = []
        inh = evaluate_inhabitant(labs[p], p, laws[p], w, "record")
        deg, why = degenerate_of(inh["run_length"], inh["site_operands"])
        out.append({"kind": "degenerate_inhabitant", "what": f"{p}'s inhabitant with every state at the initial "
                    f"state (premises hold: {inh['premises_hold']})", "detected": bool(deg and inh["premises_hold"]),
                    "degenerate_reason": why})
    else:
        out.append({"kind": "degenerate_inhabitant", "what": "no law with two state binders", "detected": False})
    # 3. a false hypothesis: the binding's first equality hypothesis with its stated value altered
    B = binding(ctx)["hypotheses"]
    eq = sorted(k for k, h in B.items() if h.get("verdict") == "tested" and h.get("check") == "equal")
    if eq:
        h = dict(B[eq[0]], id=eq[0])
        r = run_check(R, h, None, ctx, alter=True)
        out.append({"kind": "false_hypothesis", "what": f"{eq[0]} with its stated value altered in the last nibble",
                    "detected": r["result"] == "fail"})
    else:
        out.append({"kind": "false_hypothesis", "what": "no equality hypothesis in the binding", "detected": False})
    return out


# ---------------------------------------------------------------- the round's A4 record
def build(ctx: Ctx) -> dict:
    findings = round_findings(ROOT)
    lawsv, aux = laws_part(ctx, findings)
    R = Runner(ctx)
    hyps = hypotheses_part(ctx, findings, R)
    cans = canaries(ctx, lawsv, aux, R)
    from ..replay import PIN_KEYS
    return {"round": ctx.side["round"], "milestone": ctx.side["milestone"], "target_commit": ctx.commit,
            "degenerate_rule": ctx.side["degenerate_rule"], "laws": lawsv, "hypotheses": hyps, "canaries": cans,
            "toolchain": {k: ctx.tc[k] for k in (*PIN_KEYS, "go_version")},
            "checkout_commit": git_checkout_head(ctx.checkout)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon audit vacuity", description=__doc__.split("\n\n")[0])
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--round", type=int, default=2)
    ap.add_argument(*checkout_flags(), dest="checkout", help="the pinned source checkout (default: config replay)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--target", help="the audited commit (default: the target_commit of the committed output)")
    ap.add_argument("--work", help="scratch directory (default: a fresh temporary directory)")
    ap.add_argument("--check", action="store_true", help="rebuild from the committed file's target commit and "
                                                         "compare byte for byte")
    a = ap.parse_args(argv)
    if (a.milestone, a.round) != ("M2", 2):
        print("vacuity: only audit round M2/2 has an instrument (spec/M2/lib/audit_round2.json)", file=sys.stderr)
        return 2
    out = Path(a.out)
    out = out if out.is_absolute() else ROOT / out
    target = a.target
    if a.check or not target:
        if not out.exists():
            print(f"vacuity: {out} does not exist: pass --target", file=sys.stderr)
            return 2
        target = json.loads(out.read_text())["target_commit"]
    work = Path(a.work).resolve() if a.work else Path(tempfile.mkdtemp(prefix="holon-i21-vacuity-"))
    os.environ["HOLON_BUILD_DIR"] = str(work / "build")
    try:
        commit = resolve_commit(target)
        tree = materialize(commit, work / "tree")
        ctx = Ctx(tree, work, Path(a.checkout).resolve() if a.checkout else default_checkout(), None, commit)
        a4 = build(ctx)
    except HostileError as e:
        print(f"vacuity: {e}", file=sys.stderr)
        return 2
    text = canonical(a4)
    if a.check:
        same = out.read_text() == text
        print(f"vacuity --check: {'identical' if same else 'DIFFERS from'} {out.relative_to(ROOT)} "
              f"(target {commit[:12]})")
        if not same:
            (work / "a4.rebuilt.json").write_text(text)
            print(f"vacuity --check: the rebuilt record is {work / 'a4.rebuilt.json'}")
        else:
            shutil.rmtree(work, ignore_errors=True)
        return 0 if same else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"vacuity: wrote {out} (target {commit[:12]}; {len(a4['laws'])} laws, {len(a4['hypotheses'])} hypotheses)")
    if not a.work:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
