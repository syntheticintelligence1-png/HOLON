"""IR 0.2 state-machine law and proof emitters."""
from __future__ import annotations

import itertools
import json

from .sm_gen import _tag_ids

MODEL_IMPORT = "../model/rollup_sm.bend"


def _action_domains(facts, action):
    n = int(facts["config"]["N"])
    out = []
    for name, domain in facts["actions"][action].get("params", {}).items():
        vals = list(range(1, n + 1)) if domain == "1..N" else list(domain)
        out.append((name, vals))
    return out


def _assignments(domains):
    if not domains:
        return [{}]
    keys = [k for k, _ in domains]
    vals = [v for _, v in domains]
    return [dict(zip(keys, xs)) for xs in itertools.product(*vals)]


def _param_values(facts, law):
    domains = []
    for binder in law["statement"].get("forall_params", []):
        d = binder["domain"]
        if d == "1..N":
            values = list(range(1, int(facts["config"]["N"]) + 1))
        elif isinstance(d, list):
            values = d
        else:
            raise ValueError(f"unsupported forall_params domain {d!r}")
        domains.append((binder["name"], values))
    if not domains:
        return [{}]
    keys = [k for k, _ in domains]
    return [dict(zip(keys, values)) for values in itertools.product(*(v for _, v in domains))]


def _combine(parts, op="and"):
    if not parts:
        return "True{}" if op == "and" else "False{}"
    if len(parts) == 1:
        return parts[0]
    fn = "Bool.and" if op == "and" else "Bool.or"
    acc = parts[-1]
    for part in reversed(parts[:-1]):
        acc = f"{fn}({part}, {acc})"
    return acc


def _state_name(name, states):
    if name not in states:
        raise ValueError(f"unknown state variable {name!r}")
    return states[name]


def _term(t, facts, states, values, actions, law_id):
    if not isinstance(t, dict):
        raise ValueError(f"unsupported term {t!r}")
    n = int(facts["config"]["N"])
    if "c" in t:
        return f"{int(t['c'])}n"
    if "var" in t:
        v = t["var"]
        if v in values:
            value = values[v]
            return f"{int(value)}n" if isinstance(value, int) else str(value)
        if v in actions:
            return actions[v]
        raise ValueError(f"unknown term variable {v!r}")
    if "st" in t:
        state, field = t["st"]
        return f"M.get_{field}({_state_name(state, states)})"
    if "arr" in t:
        state, field, idx = t["arr"]
        return f"M.nth(M.get_{field}({_state_name(state, states)}), {_term(idx, facts, states, values, actions, law_id)})"
    if "add" in t:
        a, b = t["add"]
        return f"Nat.add({_term(a, facts, states, values, actions, law_id)}, {_term(b, facts, states, values, actions, law_id)})"
    if "k" in t:
        return f"{int(facts['config'][t['k']])}n"
    if "tag" in t:
        return f"{_tag_ids(facts)[t['tag']]}n"
    if "ite" in t:
        p, a, b = t["ite"]
        return f"Bool.pick(Nat, {_prop(p, facts, states, values, actions, law_id)}, {_term(a, facts, states, values, actions, law_id)}, {_term(b, facts, states, values, actions, law_id)})"
    if "enabled" in t:
        spec = t["enabled"]
        state = _state_name(spec["from"], states)
        action = spec["act"]
        calls = []
        for assignment in _assignments(_action_domains(facts, action)):
            args = [f"{key}: {value}" for key, value in assignment.items()]
            call = f"M.act_{action}({state}" + "".join(f", {value}n" for value in assignment.values()) + ")"
            calls.append(f"is_ok({call})")
        return _combine(calls, "or")
    if "outcome_tag" in t:
        spec = t["outcome_tag"]
        state = _state_name(spec["from"], states)
        action = spec["act"]
        params = [_term(spec["params"][p], facts, states, values, actions, law_id)
                  for p in facts["actions"][action].get("params", {})]
        return f"out_tag(M.act_{action}({state}" + "".join(f", {x}" for x in params) + "))"
    if "reach_within" in t:
        return f"search_{law_id.lower()}({_state_name(t['reach_within']['from'], states)}, {int(t['reach_within']['J'])}n)"
    raise ValueError(f"unsupported term {t!r}")


def _prop(p, facts, states, values, actions, law_id):
    if not isinstance(p, dict):
        raise ValueError(f"unsupported prop {p!r}")
    for op, fn in (("eq", "Nat.is_eq"), ("ne", "Nat.is_ne"), ("lt", "Nat.is_lt"),
                   ("le", "Nat.is_le"), ("gt", "Nat.is_gt"), ("ge", "Nat.is_ge")):
        if op in p:
            a, b = p[op]
            return f"{fn}({_term(a, facts, states, values, actions, law_id)}, {_term(b, facts, states, values, actions, law_id)})"
    if "and" in p:
        return _combine([_prop(x, facts, states, values, actions, law_id) for x in p["and"]])
    if "or" in p:
        return _combine([_prop(x, facts, states, values, actions, law_id) for x in p["or"]], "or")
    if "not" in p:
        return f"Bool.not({_prop(p['not'], facts, states, values, actions, law_id)})"
    if "iff" in p:
        a, b = p["iff"]
        return f"M.bool_eq({_prop(a, facts, states, values, actions, law_id)}, {_prop(b, facts, states, values, actions, law_id)})"
    if "implies" in p:
        a, b = p["implies"]
        return f"Bool.or(Bool.not({_prop(a, facts, states, values, actions, law_id)}), {_prop(b, facts, states, values, actions, law_id)})"
    if "state_eq" in p:
        a, b = p["state_eq"]
        return f"M.state_eq({_state_name(a, states)}, {_state_name(b, states)})"
    if "arr_eq" in p:
        a, b, field = p["arr_eq"]
        return f"M.nat_list_eq(M.get_{field}({_state_name(a, states)}), M.get_{field}({_state_name(b, states)}))"
    if "enabled" in p or "reach_within" in p:
        return _term(p, facts, states, values, actions, law_id)
    if "forall_idx" in p:
        name = p["forall_idx"]
        body = p["body"]
        local = dict(values)
        return _combine([_prop(body, facts, states, dict(local, **{name: i}), actions, law_id)
                         for i in range(int(facts["config"]["N"]) + 1)])
    raise ValueError(f"unsupported prop {p!r}")


def _step_defs(steps, law, facts, values, actions, initial_states, k):
    """Emit a chain of Outcome-dispatch defs, one per step, inner-first.

    Returns (lines, entry_expr). The final instance value is the
    assume->claim proposition evaluated in the last bound state scope."""
    lid = law["law_id"].lower()
    stmt = law["statement"]
    lines = []

    def final_expr(states):
        assumptions = [_prop(p, facts, states, values, actions, law["law_id"])
                       for p in stmt.get("assume", [])]
        claim = _prop(stmt["claim"], facts, states, values, actions, law["law_id"])
        if assumptions:
            return f"Bool.or(Bool.not({_combine(assumptions)}), {claim})"
        return claim

    states = dict(initial_states)
    if not steps:
        return lines, final_expr(states)

    # entry expr for step j: i_<lid>_<k>_<j>(call_j, <vars>)
    def sig_args(state_vars):
        return "".join(f", +{v}: M.State" for v in state_vars)

    def call_args(state_vars):
        return "".join(f", {v}" for v in state_vars)

    # vars_at[j] = state variables visible before step j (initial + binds[<j])
    vars_at = []
    cur = dict(states)
    for step in steps:
        vars_at.append(list(cur.values()))
        cur[step["bind"]] = step["bind"]
    full_states = cur

    for j in range(len(steps) - 1, -1, -1):
        step = steps[j]
        if j == len(steps) - 1:
            body = final_expr(full_states)
        else:
            nxt = steps[j + 1]
            nact_key = nxt["act"][1:] if str(nxt["act"]).startswith("$") else nxt["act"]
            naction = actions.get(nact_key, nact_key)
            if naction not in facts["actions"]:
                raise ValueError(f"unknown action {naction!r}")
            scope = dict(states)
            for b in steps[:j + 1]:
                scope[b["bind"]] = b["bind"]
            nparams = [_term(nxt.get("params", {})[p], facts, scope, values, actions, law["law_id"])
                       for p in facts["actions"][naction].get("params", {})]
            nsrc = scope[nxt["from"]]
            ncall = f"M.act_{naction}({nsrc}" + "".join(f", {v}" for v in nparams) + ")"
            body = f"i_{lid}_{k}_{j + 1}({ncall}{call_args(vars_at[j + 1])})"
        fn = f"i_{lid}_{k}_{j}"
        lines.append(f"def {fn}(o: M.Outcome{sig_args(vars_at[j])}) -> Bool:")
        lines.append("  match o:")
        lines.append(f"    case M.Ok{{+{step['bind']}}}:")
        lines.append(f"      {body}")
        lines.append("    case M.Revert{tag}:")
        lines.append("      True{}")
        lines.append("    case M.Bound{}:")
        lines.append("      True{}")
        lines.append("")

    step0 = steps[0]
    a0_key = step0["act"][1:] if str(step0["act"]).startswith("$") else step0["act"]
    a0 = actions.get(a0_key, a0_key)
    p0 = [_term(step0.get("params", {})[p], facts, states, values, actions, law["law_id"])
          for p in facts["actions"][a0].get("params", {})]
    src0 = states[step0["from"]]
    entry = f"i_{lid}_{k}_0(M.act_{a0}({src0}" + "".join(f", {v}" for v in p0) + f"){call_args(list(states.values()))})"
    return lines, entry


def _param_branches(law, facts, s_expr="s"):
    stmt = law["statement"]
    lines = []
    branches = []
    for k, combo in enumerate(_param_values(facts, law)):
        action_values = {}
        for b in stmt.get("forall_params", []):
            value = combo[b["name"]]
            if isinstance(value, str) and value in facts["actions"]:
                action_values[b["name"]] = value
        states = {stmt.get("forall_reach", "s"): s_expr, "s": s_expr}
        dl, entry = _step_defs(stmt.get("steps", []), law, facts, combo, action_values, states, k)
        lines.extend(dl)
        branches.append(entry)
    return lines, branches


def _role_search(law, facts):
    spec = law["statement"].get("claim", {}).get("reach_within")
    if not spec:
        return []
    lid = law["law_id"].lower()
    goal = _prop(spec["goal"], facts, {spec["goal_state"]: "s", "s": "s"}, {}, {}, law["law_id"])
    lines = [f"def goal_{lid}(+s: M.State) -> Bool:", f"  {goal}", ""]
    calls = []
    roles = set(spec["roles"])
    for action in sorted(facts["actions"]):
        if facts["actions"][action].get("role") not in roles:
            continue
        for assignment in _assignments(_action_domains(facts, action)):
            call = f"M.act_{action}(s" + "".join(f", {v}n" for v in assignment.values()) + ")"
            calls.append(call)
    expr = "Nil{}"
    for call in reversed(calls):
        expr = f"M.keep({call}, {expr})"
    lines.extend([f"def role_succs_{lid}(+s: M.State) -> List<&2, M.State>:",
                  f"  {expr}", "",
                  f"def exp_{lid}(+xs: List<&2, M.State>) -> List<&2, M.State>:",
                  "  match xs:",
                  "    case Nil{}:",
                  "      Nil{}",
                  "    case Con{+h, +t}:",
                  f"      List.append(&2, M.State, role_succs_{lid}(h), exp_{lid}(t))", "",
                  f"def any_goal_{lid}(+xs: List<&2, M.State>) -> Bool:",
                  "  match xs:",
                  "    case Nil{}:",
                  "      False{}",
                  "    case Con{+h, +t}:",
                  f"      Bool.or(goal_{lid}(h), any_goal_{lid}(t))", "",
                  f"def reachw_{lid}(+p: Nat, +frontier: List<&2, M.State>) -> Bool:",
                  "  match p:",
                  "    case 0n:",
                  f"      any_goal_{lid}(frontier)",
                  "    case 1n+q:",
                  f"      Bool.or(any_goal_{lid}(frontier), reachw_{lid}(q, exp_{lid}(frontier)))", "",
                  f"def search_{lid}(+s: M.State, depth: Nat) -> Bool:",
                  f"  reachw_{lid}(depth, [s])", ""])
    return lines


def _trace_defs(facts, law):
    actions = sorted(facts["actions"])
    ids = {a: i for i, a in enumerate(actions)}
    lid = law["law_id"].lower()
    lines = ["type TraceStep is Data:", "  TraceStep{action: Nat, p0: Nat, p1: Nat}", "",
             "def apply_step(+s: M.State, step: TraceStep) -> M.Outcome:",
             "  match step:", "    case TraceStep{action, p0, p1}:", "      match action:"]
    for action in actions:
        params = list(facts["actions"][action].get("params", {}))
        args = ["p0", "p1"][:len(params)]
        call = f"M.act_{action}(s" + "".join(f", {x}" for x in args) + ")"
        lines.extend([f"        case {ids[action]}n:", f"          {call}"])
    lines.extend([f"        case {len(actions)}n+p:", "          M.Bound{}", "",
                  f"def run_trace_{lid}(trace: List<&2, TraceStep>, o: M.Outcome) -> M.Outcome:",
                  "  match trace:",
                  "    case Nil{}:",
                  "      o",
                  "    case Con{+step, +rest}:",
                  "      match o:",
                  "        case M.Ok{+s}:",
                  f"          run_trace_{lid}(rest, apply_step(s, step))",
                  "        case M.Revert{tag}:",
                  "          M.Revert{tag}",
                  "        case M.Bound{}:",
                  "          M.Bound{}", "",
                  f"def rf_{lid}(o: M.Outcome) -> Bool:",
                  "  match o:",
                  "    case M.Ok{+s}:",
                  f"      Bool.not(check_{lid}(s))",
                  "    case M.Revert{tag}:",
                  "      False{}",
                  "    case M.Bound{}:",
                  "      False{}", "",
                  f"def refutes_{lid}(trace: List<&2, TraceStep>) -> Bool:",
                  f"  rf_{lid}(run_trace_{lid}(trace, M.Ok{{M.init_state()}}))", ""])
    return lines, ids


def trace_literal(trace, facts, prefix=""):
    ids = {a: i for i, a in enumerate(sorted(facts["actions"]))}
    if not trace:
        return "Nil{}"
    rows = []
    for item in trace:
        action = item["action"]
        params = item.get("params", {})
        vals = list(facts["actions"][action].get("params", {}))
        p0 = int(params.get(vals[0], 0)) if vals else 0
        p1 = int(params.get(vals[1], 0)) if len(vals) > 1 else 0
        rows.append(f"{prefix}TraceStep{{{ids[action]}n, {p0}n, {p1}n}}")
    out = "Nil{}"
    for row in reversed(rows):
        out = f"Con{{{row}, {out}}}"
    return out


def emit_laws(law: dict, facts: dict, counter_trace=None) -> str:
    lid = law["law_id"].lower()
    stmt = law["statement"]
    is_sm = stmt.get("kind") == "sm"
    if not is_sm:
        raise ValueError(f"{law['law_id']} is not a state-machine law")
    lines = ["import Base", f"import {MODEL_IMPORT} as M", ""]
    lines.extend(["def is_ok(o: M.Outcome) -> Bool:", "  match o:", "    case M.Ok{state}:", "      True{}",
                  "    case M.Revert{tag}:", "      False{}", "    case M.Bound{}:", "      False{}", "",
                  "def out_tag(o: M.Outcome) -> Nat:", "  match o:",
                  f"    case M.Ok{{state}}:", f"      {len(_tag_ids(facts))}n",
                  "    case M.Revert{tag}:", "      tag", "    case M.Bound{}:", f"      {len(_tag_ids(facts)) + 1}n", ""])
    lines.extend(_role_search(law, facts))
    if counter_trace is None:
        branch_lines, branches = _param_branches(law, facts)
        lines.extend(branch_lines)
        lines.extend([f"def check_{lid}_assignment(+s: M.State, index: Nat) -> Bool:", "  match index:"])
        for i, branch in enumerate(branches):
            lines.extend([f"    case {i}n:", f"      {branch}"])
        lines.extend([f"    case {len(branches)}n+p:", "      False{}", ""])
        lines.extend([f"def check_{lid}(+s: M.State) -> Bool:"])
        lines.append("  " + _combine([f"check_{lid}_assignment(s, {i}n)" for i in range(len(branches))]))
        lines.append("")
        lines.extend([f"def all_states_{lid}(states: List<&2, M.State>) -> Bool:",
                      "  match states:", "    case Nil{}:", "      True{}", "    case Con{state, rest}:",
                      f"      Bool.and(check_{lid}(state), all_states_{lid}(rest))", ""])
        k = int(stmt["bound"]["K"])
        lines.extend([f"law {lid}:", f"  {{all_states_{lid}(M.reach_k({k}n)) == True{{}} : Bool}}", ""])
    else:
        trace_lines, _ = _trace_defs(facts, law)
        branch_lines, branches = _param_branches(law, facts)
        lines.extend(branch_lines)
        lines.extend([f"def check_{lid}_assignment(+s: M.State, index: Nat) -> Bool:", "  match index:"])
        for i, branch in enumerate(branches):
            lines.extend([f"    case {i}n:", f"      {branch}"])
        lines.extend([f"    case {len(branches)}n+p:", "      False{}", ""])
        lines.extend([f"def check_{lid}(+s: M.State) -> Bool:",
                      "  " + _combine([f"check_{lid}_assignment(s, {i}n)" for i in range(len(branches))]), ""])
        lines.extend(trace_lines)
        literal = trace_literal(counter_trace, facts)
        lines.extend([f"law cl_{lid}:", "  exs trace: List<&2, TraceStep>",
                      f"  {{refutes_{lid}(trace) != False{{}} : Bool}}", ""])
    return "\n".join(lines)


def emit_proof(law: dict, facts: dict, counter_trace=None) -> str:
    lid = law["law_id"].lower()
    lines = ["import Base", f"import {MODEL_IMPORT} as M", "import ./LAWS.bend as Laws", ""]
    if counter_trace is None:
        lines.extend([f"def Laws.{lid}():", "  {==}", ""])
    else:
        literal = trace_literal(counter_trace, facts, prefix="Laws.")
        lines.extend([f"def Laws.cl_{lid}():",
                      f"  ({literal}, e => (%e : M.is_true(M.bool_eq(_, Laws.refutes_{lid}({literal})))",
                      "  Unit{}))", ""])
    return "\n".join(lines)


def parameter_assignments(law, facts):
    return _param_values(facts, law)
