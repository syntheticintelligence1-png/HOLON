"""python -m holon eval controls [--root DIR] [--check] (I48 rules K0-K2): the unsolved controls.

Rule K0: the only input is the frozen plan spec/M4/lib/controls_plan.json. Rule K1: the plan's families and sizes
expand, in plan order, to one control each, with its truth (the family's), its witness (a false control's shortest
violating trace), within_budget (the plan's budget rule) and the outcome the factory is expected to reach:

  depth d     false; witness inc() d times then fire(); within the budget iff d + 1 <= prefixDepth
  value v     false; witness fire(v);                    within the budget iff v is a Nat input the generic policy tries
  relational  true;  no witness; never within the budget (its strengthening b == c_i is relational)
  constant    true;  no witness; always within the budget (its strengthening is field constants)

expected: a true control is PROVED within the budget, a false one REFUTED; beyond it, UNKNOWN.

Rule K2: each control gets a holon-facts/0.2 machine (generic policy, no search key) and one holon-ir/0.3 law over
its reachable states, both written as dumps(doc); spec/eval/controls/ledger.json is a sidecar holon-ledger/0.1 with
one exact bundle per control, classifying every definition of the model holon.gen.machine generates from the facts
(the classification is derived from the facts and then checked against the generated model: a definition the rules
below do not classify exactly once is an error, never silently filed); spec/eval/controls.json lists the controls with
the plan's budgets.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import common
from .common import Refused, dumps, sha256_bytes

PLAN = Path("spec") / "M4" / "lib" / "controls_plan.json"
OUT = Path("spec") / "eval" / "controls"
MANIFEST = Path("spec") / "eval" / "controls.json"
LEDGER = OUT / "ledger.json"
CONTROLS_VERSION = "holon-eval-controls/0.1"
EXTRACTION_DATE = "2026-10-15"   # the I48 build's fixed date (no timestamp is ever read from the clock)
BUDGET_KEYS = ("maxPrefixes", "natMax", "prefixDepth", "run", "run_rule", "source", "strengthening", "suffixDepth")


# ---------------------------------------------------------------------------------------------- rule K1
def _expected(truth: bool, within: bool) -> str:
    if not within:
        return "UNKNOWN"
    return "PROVED" if truth else "REFUTED"


def _family_rule(family: str, size: int, budgets: dict) -> tuple[list | None, bool]:
    """(witness, within_budget) of one control by the plan's budget rule."""
    if family == "depth":
        return [{"op": "inc"} for _ in range(size)] + [{"op": "fire"}], size + 1 <= budgets["prefixDepth"]
    if family == "value":
        return [{"op": "fire", "d": size}], size in budgets["nat_input_domain"]
    if family == "relational":
        return None, False
    if family == "constant":
        return None, True
    raise Refused(f"controls plan: unknown family {family!r}")


def control_list(plan: dict) -> list[dict]:
    out = []
    for fam in plan["families"]:
        name = fam["family"]
        for size in fam["sizes"]:
            witness, within = _family_rule(name, size, plan["budgets"])
            cid = f"{name}_{size}"
            out.append({
                "id": cid, "family": name, "size": size, "truth": fam["truth"],
                "facts": (OUT / f"{cid}.facts.json").as_posix(), "law": (OUT / f"{cid}.law.json").as_posix(),
                "law_id": f"L_i48_{name}_{size}", "witness": witness, "within_budget": within,
                "expected": _expected(fam["truth"], within),
            })
    return out


# ---------------------------------------------------------------------------------------------- rule K2: documents
def _action(name: str, inputs: list | None = None, guards: list | None = None, effects: dict | None = None) -> dict:
    return {"name": name, "src": f"control: {name}({', '.join(i[0] for i in inputs or [])})",
            "principal": "anyone", "inputs": [list(i) for i in inputs or []],
            "guards": [{"require": g, "reason": 1} for g in guards or []], "effects": dict(effects or {})}


def _observer(body, doc: str) -> dict:
    return {"params": [["s", "State"]], "type": "Bool", "body": body, "doc": doc}


FLAG_DOC = "planted false invariant: the flag stays down"


def _machine(family: str, n: int) -> tuple[list, dict, list, dict]:
    """(state, initial registers, actions, observers) of the family's machine at size n (the plan's "machine")."""
    log = ["log", "List<Obs>", "observations"]
    if family == "depth":
        state = [["c", "Nat", "counter"], ["flag", "Bool", "raised once c >= SIZE"], log]
        regs = {"c": 0, "flag": False}
        acts = [_action("inc", effects={"c": ["+", "c", 1]}),
                _action("fire", guards=[[">=", "c", n]], effects={"flag": True})]
        return state, regs, acts, {"flag_down": _observer(["!", "flag"], FLAG_DOC)}
    if family == "value":
        state = [["flag", "Bool", "raised by fire(SIZE)"], log]
        acts = [_action("fire", inputs=[["d", "Nat"]], guards=[["==", "d", n]], effects={"flag": True})]
        return state, {"flag": False}, acts, {"flag_down": _observer(["!", "flag"], FLAG_DOC)}
    if family == "relational":
        cs = [f"c_{i}" for i in range(1, n + 1)]
        state = [["a", "Nat", "copied from some c_i"], ["b", "Nat", "bumped up to 3"]]
        state += [[c, "Nat", "bumped with b"] for c in cs] + [log]
        regs = {"a": 0, "b": 0, **{c: 0 for c in cs}}
        bump = {"b": ["+", "b", 1], **{c: ["+", c, 1] for c in cs}}
        acts = [_action("bump", guards=[["<", "b", 3]], effects=bump)]
        acts += [_action(f"copy_{i}", effects={"a": c}) for i, c in enumerate(cs, 1)]
        obs = {"a_le_b": _observer(["<=", "a", "b"],
                                   "planted true invariant; its strengthening is relational (b == c_i)")}
        return state, regs, acts, obs
    if family == "constant":
        ys = [f"y_{i}" for i in range(1, n + 1)]
        state = [["x", "Nat", "copied from y_1"]]
        state += [[y, "Nat", "shifted from the next y, the last one cleared"] for y in ys] + [log]
        regs = {"x": 0, **{y: 0 for y in ys}}
        acts = [_action("copy", effects={"x": "y_1"})]
        acts += [_action(f"shift_{i}", effects={ys[i - 1]: ys[i]}) for i in range(1, n)]
        acts += [_action("clear", effects={ys[-1]: 0})]
        obs = {"x_zero": _observer(["==", "x", 0], "planted true invariant; its strengthening is field constants")}
        return state, regs, acts, obs
    raise Refused(f"controls plan: unknown family {family!r}")


def documents(control: dict, plan: dict) -> tuple[dict, dict]:
    """The facts and law documents of one control (rule K2)."""
    family, n, cid = control["family"], control["size"], control["id"]
    fam = next(f for f in plan["families"] if f["family"] == family)
    state, regs, acts, obs = _machine(family, n)
    facts = {
        "facts_version": "holon-facts/0.2",
        "target": {"repo": "holon/eval-controls", "commit": "0" * 40, "scope": f"I48 control {cid}: {fam['machine']}"},
        "extraction": {"method": "generated from spec/M4/lib/controls_plan.json (I48 rule K2)", "date": EXTRACTION_DATE},
        "abstractions": [f"A planted obligation of the {family} family, size {n}, for UNKNOWN calibration (L15); "
                         "not a real target."],
        "params": {}, "types": {}, "state": state, "ghost_state": [],
        "initial": {"doc": "every register zero, flags down", **regs, "log": []},
        "principals": {}, "reasons": {"1": "the guard does not hold"}, "defs": {},
        "actions": acts, "observers": obs, "policy": "generic",
        "coverage": {"modelled": [a["name"] for a in acts], "debt": []},
    }
    if len(obs) != 1:
        raise Refused(f"{cid}: a control has exactly one observer")
    observer = next(iter(obs))
    truth = "true" if control["truth"] else "false"
    law = {
        "ir_version": "holon-ir/0.3", "law_id": control["law_id"], "milestone": plan["milestone"], "rule": "SORT",
        "rule_catalog_version": "holon-rules/1.0", "facts": control["facts"],
        "facts_sha256": sha256_bytes(dumps(facts).encode("utf-8")),
        "notes": f"I48 control {cid} ({truth}; expected {control['expected']}). {fam['law']}",
        "statement": {"binders": [{"q": "forall", "name": "s", "type": "Reach"}], "assume": [],
                      "claim": {"eq": [{"obsv": observer, "of": {"var": "s"}}, {"bool": True}]},
                      "scope": {"kind": "unbounded"}},
    }
    return facts, law


# ---------------------------------------------------------------------------------------------- rule K2: the ledger
PRELUDE = ["ite", "nth_d", "set_d", "tail0", "last_d", "b_enc", "b_mem", "b_nth", "b_pair", "b_remove", "b_set_nat",
           "b_zeros_like", "eq_bool", "eq_list_nat", "is_true"]
VOCABULARY = ["clear_log", "log_of", "obs", "ok_head", "last_ok", "all_ok", "runs_ok", "no_code", "eq_obs",
              "eq_obs_list", "cost", "elapsed"]


def bundle(control: dict, facts: dict, facts_sha: str) -> dict:
    """The exact ledger bundle of one control's facts: one abstraction entry (the facts' only abstraction, carried by
    the state record) and the no-assumption groups of the generated definitions, named from the facts."""
    acts = facts["actions"]
    names = [a["name"] for a in acts]
    guards = [f"dec_{a['name']}_{i}" for a in acts for i in range(len(a["guards"]))]
    principals = sorted({a["principal"] for a in acts})
    return {
        "facts": control["facts"], "facts_sha256": facts_sha, "model": control["id"],
        "entries": [{"id": f"abs-{control['id'].replace('_', '-')}-control", "kind": "abstraction",
                     "source": f"{control['facts']}#/abstractions/0", "text": facts["abstractions"][0],
                     "introduced_by": ["HSt"]}],
        "no_assumption": [
            {"defs": list(PRELUDE), "why": "list, Nat and Bool utilities of the generator prelude; no modelling choice"},
            {"defs": ["HSt", "HObs", "HAct", "s0"] + [f"Dec_{a}" for a in names],
             "why": "record plumbing and the initial state, generated from the control's state, initial and actions"},
            {"defs": [f"{k}_{a}" for a in names for k in ("decide", "exec", "step")] + guards
             + ["step", "run", "Reach", "perm"] + [f"perm_{p}" for p in principals],
             "why": "action chains and guard decisions generated from the control's actions, and the reachability "
                    "predicate generated from s0 and step"},
            {"defs": list(VOCABULARY) + [f"is_{a}" for a in names] + sorted(facts["observers"]),
             "why": "statement vocabulary generated from the control's observer and the action log"},
        ],
    }


def check_bundle(b: dict, model_text: str) -> list[str]:
    """Definitions of the generated model that the bundle does not classify exactly once (by an entry, or by exactly
    one no-assumption group), and listed names that the model does not define."""
    from holon.records import model_defs
    defs = set(model_defs(model_text))
    bad = []
    for d in sorted(defs):
        by_entry = any(d in e["introduced_by"] for e in b["entries"])
        groups = sum(d in g["defs"] for g in b["no_assumption"])
        if groups > 1 or (groups == 0 and not by_entry):
            bad.append(f"{b['model']}: {d} is classified {groups} times")
    listed = {d for g in b["no_assumption"] for d in g["defs"]} | {d for e in b["entries"] for d in e["introduced_by"]}
    bad += [f"{b['model']}: {d} is not a definition of the model" for d in sorted(listed - defs)]
    return bad


def ledger(rows: list[tuple[dict, dict, str]], root: Path) -> dict:
    from holon.gen.machine import generate
    bundles, bad = [], []
    for control, facts, sha in rows:
        b = bundle(control, facts, sha)
        bad += check_bundle(b, generate(facts, sha, root / control["facts"], reach=True))
        bundles.append(b)
    if bad:
        raise RuntimeError("controls ledger: " + "; ".join(bad))
    return {"ledger_version": "holon-ledger/0.1",
            "doc": "Sidecar ledger of the I48 controls (rule K2): one exact bundle per control's facts, read by "
                   "holon.records next to the facts; generated by python -m holon eval controls.",
            "bundles": bundles}


# ---------------------------------------------------------------------------------------------- the command
def build(root: Path, plan: dict) -> dict[Path, str]:
    """Every file the command writes, relative path -> text."""
    controls = control_list(plan)
    files, rows = {}, []
    for c in controls:
        facts, law = documents(c, plan)
        text = dumps(facts)
        files[Path(c["facts"])] = text
        files[Path(c["law"])] = dumps(law)
        rows.append((c, facts, sha256_bytes(text.encode("utf-8"))))
    files[LEDGER] = dumps(ledger(rows, root))
    budgets = {k: plan["budgets"][k] for k in BUDGET_KEYS}
    manifest = {"controls_version": CONTROLS_VERSION, "milestone": plan["milestone"], "budgets": budgets,
                "ledger": LEDGER.as_posix(), "controls": controls}
    from holon.schema import errors
    errs = errors(manifest, common.load_json(common.LIB / "controls.schema.json"))
    if errs:
        raise RuntimeError("controls.json does not validate: " + "; ".join(errs[:10]))
    files[MANIFEST] = dumps(manifest)
    return files


def cli_controls(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon eval controls")
    ap.add_argument("--root", type=Path, default=common.ROOT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    if not (common.ROOT / PLAN).exists():
        raise Refused(f"{PLAN} is missing")
    plan = common.load_json(common.ROOT / PLAN)
    files = build(root, plan)
    differ = [p for p, text in sorted(files.items()) if common.write_or_check(root / p, text, a.check)]
    known = set(files)
    stray = sorted(p.relative_to(root) for p in (root / OUT).glob("*") if p.relative_to(root) not in known) \
        if (root / OUT).exists() else []
    for p in differ:
        print(f"{'differs' if a.check else 'wrote'}: {p.as_posix()}", file=sys.stderr if a.check else sys.stdout)
    for p in stray:
        print(f"not a control file: {p.as_posix()}", file=sys.stderr)
    if a.check:
        return 1 if differ or stray else 0
    return 1 if stray else 0
