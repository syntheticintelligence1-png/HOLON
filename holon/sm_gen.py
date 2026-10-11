"""Mechanical generator for the M1 rollup state-machine facts."""
from __future__ import annotations

import json


def _unwrap(x):
    if isinstance(x, dict) and "code" in x and "ite" in x:
        return x["ite"]
    return x


def _tag_ids(facts):
    tags = set()
    def walk(x):
        if isinstance(x, dict):
            if "tag" in x and ("req" in x or "subc" in x):
                tags.add(x["tag"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(facts["actions"])
    return {tag: i for i, tag in enumerate(sorted(tags))}


def _state_fields(facts):
    st = facts["state"]
    return [(x, "scalar") for x in st["scalars"]] + [(x, "array") for x in st["arrays_N"] + st["arrays_Q"]]


def bend_model(facts: dict) -> str:
    """Emit the state, every action, and a bounded reachability engine."""
    fields = _state_fields(facts)
    names = [x for x, _ in fields]
    kinds = dict(fields)
    config = facts["config"]
    n = int(config["N"])
    q = int(config["Q"])
    tags = _tag_ids(facts)
    out = ["import Base", "", "type State is Data:"]
    out.append("  State{" + ", ".join(f"{x}: {'Nat' if kinds[x] == 'scalar' else 'List<&2, Nat>'}" for x in names) + "}")
    out.extend(["", "type Outcome is Data:", "  Ok{state: State}", "  Revert{tag: Nat}", "  Bound{}", ""])
    out.append("# Revert tag IDs: " + json.dumps(tags, sort_keys=True, ensure_ascii=False))
    out.extend(["", "def nth(+xs: List<&2, Nat>, i: Nat) -> Nat:", "  match xs i:", "    case Nil{} _:", "      0n", "    case Con{+h, +t} 0n:", "      h", "    case Con{+h, +t} 1n+p:", "      nth(t, p)", "", "def put_nth(+xs: List<&2, Nat>, i: Nat, +x: Nat) -> List<&2, Nat>:", "  match xs i:", "    case Nil{} _:", "      Nil{}", "    case Con{h, +t} 0n:", "      Con{x, t}", "    case Con{h, +t} 1n+p:", "      Con{h, put_nth(t, p, x)}", ""])

    # Accessors and immutable record updates.
    for name in names:
        ty = "Nat" if kinds[name] == "scalar" else "List<&2, Nat>"
        out.append(f"def get_{name}(+s: State) -> {ty}:")
        out.append("  match s:")
        out.append("    case State{" + ", ".join(names) + f"}}: {name}")
        out.append("")
        if kinds[name] == "scalar":
            out.append(f"def set_{name}(s: State, x: Nat) -> State:")
            out.append("  match s:")
            out.append("    case State{" + ", ".join(names) + "}:")
            out.append("      State{" + ", ".join('x' if f == name else f for f in names) + "}")
        else:
            out.append(f"def set_{name}(s: State, x: List<&2, Nat>) -> State:")
            out.append("  match s:")
            out.append("    case State{" + ", ".join(names) + "}:")
            out.append("      State{" + ", ".join('x' if f == name else f for f in names) + "}")
        out.append("")

    out.extend(["def bool_eq(a: Bool, b: Bool) -> Bool:", "  match a b:", "    case True{} True{}:", "      True{}", "    case True{} False{}:", "      False{}", "    case False{} True{}:", "      False{}", "    case False{} False{}:", "      True{}", "", "def is_true(b: Bool) -> Type:", "  match b:", "    case True{}:", "      Unit", "    case False{}:", "      Empty", ""])
    out.extend(["def nat_list_eq(xs: List<&2, Nat>, ys: List<&2, Nat>) -> Bool:", "  match xs ys:", "    case Nil{} Nil{}:", "      True{}", "    case Nil{} Con{h, t}:", "      False{}", "    case Con{h, t} Nil{}:", "      False{}", "    case Con{x, xt} Con{y, yt}:", "      Bool.and(Nat.is_eq(x, y), nat_list_eq(xt, yt))", ""])
    out.append("def state_eq(+a: State, +b: State) -> Bool:")
    clauses = []
    for name in names:
        eq = f"Nat.is_eq(get_{name}(a), get_{name}(b))" if kinds[name] == "scalar" else f"nat_list_eq(get_{name}(a), get_{name}(b))"
        clauses.append(eq)
    expr = clauses[-1]
    for part in reversed(clauses[:-1]):
        expr = f"Bool.and({part}, {expr})"
    out.extend([f"  {expr}", ""])

    # Expression compiler: checked subtraction guards are propagated to each statement.
    def term(t, env):
        t = _unwrap(t)
        if isinstance(t, list) and len(t) == 3:
            t = {"ite": t}
        if not isinstance(t, dict):
            raise ValueError(f"unsupported term {t!r}")
        if "c" in t: return f"{int(t['c'])}n", "True{}", None
        if "s" in t: return f"get_{t['s']}(s)", "True{}", None
        if "a" in t:
            idx, safe, tag = term(t["i"], env)
            return f"nth(get_{t['a']}(s), {idx})", safe, tag
        if "p" in t: return t["p"], "True{}", None
        if "k" in t: return f"{int(config[t['k']])}n", "True{}", None
        if "var" in t:
            v = t["var"]
            return v, "True{}", None
        if "add" in t:
            a, sa, ta = term(t["add"][0], env); b, sb, tb = term(t["add"][1], env)
            return f"Nat.add({a}, {b})", f"Bool.and({sa}, {sb})", ta or tb
        if "subc" in t:
            a, sa, ta = term(t["subc"][0], env); b, sb, tb = term(t["subc"][1], env)
            tag = t.get("tag", "panic: arithmetic underflow")
            safe = f"Bool.and({sa}, Bool.and({sb}, Nat.is_ge({a}, {b})) )"
            return f"Nat.sub({a}, {b})", safe, ta or tb or tag
        if "ite" in t:
            p, sp, tp = prop(t["ite"][0], env)
            a, sa, ta = term(t["ite"][1], env); b, sb, tb = term(t["ite"][2], env)
            safe = f"Bool.and({sp}, Bool.pick(Bool, {p}, {sa}, {sb}))"
            return f"Bool.pick(Nat, {p}, {a}, {b})", safe, tp or ta or tb
        raise ValueError(f"unsupported term {t!r}")

    def prop(p, env):
        p = _unwrap(p)
        if not isinstance(p, dict): raise ValueError(f"unsupported prop {p!r}")
        if "var" in p:
            return p["var"], "True{}", None
        if "not" in p:
            a, sa, ta = prop(p["not"], env)
            return f"Bool.not({a})", sa, ta
        for op, fn in (("eq", "Nat.is_eq"), ("ne", "Nat.is_ne"), ("lt", "Nat.is_lt"), ("le", "Nat.is_le"), ("gt", "Nat.is_gt"), ("ge", "Nat.is_ge")):
            if op in p:
                a, sa, ta = term(p[op][0], env); b, sb, tb = term(p[op][1], env)
                return f"{fn}({a}, {b})", f"Bool.and({sa}, {sb})", ta or tb
        for op, fn in (("and", "Bool.and"), ("or", "Bool.or")):
            if op in p:
                a, sa, ta = prop(p[op][0], env); b, sb, tb = prop(p[op][1], env)
                return f"{fn}({a}, {b})", f"Bool.and({sa}, {sb})", ta or tb
        raise ValueError(f"unsupported prop {p!r}")

    class ActionEmitter:
        def __init__(self, action, body, params):
            self.action, self.body, self.params = action, body, params
            self.defs = []
            self.num = 0
        def fresh(self, prefix="step"):
            self.num += 1
            return f"_{self.action}_{prefix}_{self.num}"
        def sig(self, fn, env):
            return f"def {fn}(+s: State" + "".join(f", +{v}: {'Bool' if ty == 'Bool' else 'Nat'}" for v, ty in env.items()) + ") -> Outcome:"
        def call(self, fn, env, s="s"):
            return f"{fn}({s}" + "".join(f", {v}" for v in env) + ")"
        def _final_env(self, env, stmts):
            out = dict(env)
            for stmt in stmts:
                if "let" in stmt:
                    raw = _unwrap(stmt["be"])
                    is_prop = isinstance(raw, dict) and any(
                        k in raw for k in ("eq", "ne", "lt", "le", "gt", "ge",
                                           "and", "or", "not", "iff", "implies"))
                    out[stmt["let"]] = "Bool" if is_prop else "Nat"
            return out

        def seq(self, stmts, env, nenv, nextfn):
            """Compile a statement sequence. env = vars visible at entry;
            nenv = vars the continuation nextfn expects at the end."""
            env_at = [dict(env)]
            cur_env = dict(env)
            for stmt in stmts:
                cur_env = self._final_env(cur_env, [stmt])
                env_at.append(cur_env)
            env_at[-1] = dict(nenv)
            current = nextfn
            for i in range(len(stmts) - 1, -1, -1):
                current = self.statement(stmts[i], env_at[i], env_at[i + 1], current)
            return current
        def helper(self, env, lines, prefix="step"):
            fn = self.fresh(prefix)
            self.defs.append(self.sig(fn, env) + "\n" + "\n".join("  " + line if line else "" for line in lines) + "\n")
            return fn

        def _mb(self, env, cond, tlines, elines):
            """Condition dispatch: match can only inspect a parameter, so the
            computed condition is passed to a dedicated helper (BEND_PRIMER)."""
            fn = self.fresh("cond")
            body = (self.sig(fn, env).replace(f"def {fn}(+s: State",
                                              f"def {fn}(c: Bool, +s: State")
                    + "\n"
                    + "\n".join("  " + l for l in
                                [f"match c:", "  case True{}:", *("    " + x for x in tlines),
                                 "  case False{}:", *("    " + x for x in elines)])
                    + "\n")
            self.defs.append(body)
            return [f"{fn}({cond}, s" + "".join(f", {v}" for v in env) + ")"]

        def _mo(self, env, call_expr, ok_state, ok_lines, extra_params=""):
            """Outcome dispatch: run call_expr, match on Ok/Revert/Bound."""
            fn = self.fresh("out")
            body = (self.sig(fn, env).replace(f"def {fn}(+s: State",
                                              f"def {fn}(o: Outcome, +s: State")
                    + extra_params + "\n"
                    + "\n".join("  " + l for l in
                                [f"match o:", f"  case Ok{{{ok_state}}}:", *("    " + x for x in ok_lines),
                                 "  case Revert{tag}:", "    Revert{tag}",
                                 "  case Bound{}:", "    Bound{}"])
                    + "\n")
            self.defs.append(body)
            return [f"{fn}({call_expr}, s" + "".join(f", {v}" for v in env) + ")"]
        def statement(self, stmt, env, nenv, nextfn):
            if "req" in stmt:
                p, safe, tag = prop(stmt["req"], env)
                fail_tag = tag or stmt["tag"]
                rev = f"Revert{{{tags[fail_tag]}n}}"
                return self.helper(env, self._mb(env, safe, self._mb(env, p, [self.call(nextfn, nenv)], [rev]), [rev]), "req")
            if "let" in stmt:
                name = stmt["let"]
                raw = stmt["be"]
                is_prop = any(k in _unwrap(raw) for k in ("eq", "ne", "lt", "le", "gt", "ge", "and", "or", "not", "iff", "implies"))
                v, safe, tag = prop(raw, env) if is_prop else term(raw, env)
                nen = dict(env); nen[name] = "Bool" if is_prop else "Nat"
                args = ["s", *env.keys(), v]
                call = f"{nextfn}(" + ", ".join(args) + ")"
                return self.helper(env, self._mb(env, safe, [call], [f"Revert{{{tags[tag or 'panic: arithmetic underflow']}n}}"]), "let")
            if "set" in stmt:
                target = stmt["set"]
                idx_expr = None; safe_parts=[]; tag=None
                if "a" in target:
                    idx_expr, si, ti = term(target["i"], env); safe_parts.append(si); tag = ti
                value, sv, tv = term(stmt["to"], env); safe_parts.append(sv); tag = tag or tv
                safe = "True{}"
                for p0 in safe_parts: safe = f"Bool.and({safe}, {p0})"
                if "s" in target:
                    upd = f"set_{target['s']}(s, {value})"
                    body = self._mb(env, safe, [self.call(nextfn, nenv, upd)], [f"Revert{{{tags[tag or 'panic: arithmetic underflow']}n}}"])
                else:
                    nm = target["a"]
                    ln = n + 1 if nm in facts["state"]["arrays_N"] else q
                    body = self._mb(env, safe,
                                    self._mb(env, f"Nat.is_lt({idx_expr}, {ln}n)",
                                             [self.call(nextfn, nenv, f'set_{nm}(s, put_nth(get_{nm}(s), {idx_expr}, {value}))')],
                                             ["Bound{}"]),
                                    [f"Revert{{{tags[tag or 'panic: arithmetic underflow']}n}}"])
                return self.helper(env, body, "set")
            if "if" in stmt:
                p, safe, tag = prop(stmt["if"], env)
                a = self.seq(stmt.get("then", []), env, nenv, nextfn)
                b = self.seq(stmt.get("else", []), env, nenv, nextfn)
                return self.helper(env, self._mb(env, safe,
                                            self._mb(env, p, [self.call(a, env)], [self.call(b, env)]),
                                            [f"Revert{{{tags[tag or 'panic: arithmetic underflow']}n}}"]), "if")
            if any(k in stmt for k in ("bound", "bound_q", "bound_t")):
                key = next(k for k in ("bound", "bound_q", "bound_t") if k in stmt)
                x, safe, tag = term(stmt[key], env)
                cond = f"Nat.is_gt({x}, {n}n)" if key == "bound" else (f"Nat.is_ge({x}, {q}n)" if key == "bound_q" else f"Nat.is_gt({x}, {int(config['T'])}n)")
                return self.helper(env, self._mb(env, safe,
                                            self._mb(env, cond, ["Bound{}"], [self.call(nextfn, nenv)]),
                                            [f"Revert{{{tags[tag or 'panic: arithmetic underflow']}n}}"]), "bound")
            if "for" in stmt:
                loopvar = stmt["for"]
                start, ss, ts = term(stmt["from"], env)
                end, se, te = term(stmt["to_incl"], env)
                loop_env = dict(env); loop_env[loopvar] = "Nat"
                body_final = self.helper(self._final_env(loop_env, stmt["body"]), ["Ok{s}"], "loop_body_done")
                body_entry = self.seq(stmt["body"], loop_env, self._final_env(loop_env, stmt["body"]), body_final)
                # bg = body transform guarded by the range check and `while`.
                # Outside the range (or while false once reached) it is Ok{s},
                # so the fuel loop can run to its bound harmlessly.
                guard_env = dict(loop_env); guard_env["end"] = "Nat"
                while_expr = stmt.get("while")
                if while_expr is not None:
                    wp, ws, wt = prop(while_expr, loop_env)
                    inner = self._mb(guard_env, ws,
                                     self._mb(guard_env, wp, [self.call(body_entry, loop_env)], ["Ok{s}"]),
                                     [f"Revert{{{tags[wt or 'panic: arithmetic underflow']}n}}"])
                else:
                    inner = [self.call(body_entry, loop_env)]
                bg = self.helper(guard_env,
                                 self._mb(guard_env, f"Nat.is_gt({loopvar}, end)",
                                          ["Ok{s}"], inner),
                                 "body_guard")
                # loopfn: matches its own Outcome parameter; recurses on fuel only.
                loopfn = self.fresh("loop")
                loop_params = "".join(f", +{v}: {'Bool' if t == 'Bool' else 'Nat'}" for v, t in env.items())
                loop_args = "".join(f", {v}" for v in env)
                loop_sig = (f"def {loopfn}(fuel: Nat, o: Outcome, +s: State{loop_params}, "
                            f"+{loopvar}: Nat, +end: Nat) -> Outcome:")
                bg_call = f"{bg}(s2{loop_args}, Nat.add({loopvar}, 1n), end)"
                loop_body = [
                    "match fuel:",
                    "  case 0n:",
                    "    match o:",
                    "    case Ok{+s2}:",
                    "      " + self.call(nextfn, nenv, "s2"),
                    "    case Revert{tag}:",
                    "      Revert{tag}",
                    "    case Bound{}:",
                    "      Bound{}",
                    "  case 1n+p:",
                    "    match o:",
                    "    case Ok{+s2}:",
                    f"      {loopfn}(p, {bg_call}, s2{loop_args}, Nat.add({loopvar}, 1n), end)",
                    "    case Revert{tag}:",
                    "      Revert{tag}",
                    "    case Bound{}:",
                    "      Bound{}"]
                self.defs.append(loop_sig + "\n" + "\n".join("  " + l for l in loop_body) + "\n")
                hi = f"Nat.min({end}, {n}n)"
                entry_call = (f"{loopfn}(Nat.add({hi}, 1n), {bg}(s, " + ", ".join([*env.keys(), start, hi]) + f"), s{loop_args}, "
                              f"{start}, {hi})")
                startfn = self.helper(env, self._mb(env, ss,
                                                  self._mb(env, se, [entry_call],
                                                           [f"Revert{{{tags[te or 'panic: arithmetic underflow']}n}}"]),
                                                  [f"Revert{{{tags[ts or 'panic: arithmetic underflow']}n}}"]), "for")
                return startfn
            raise ValueError(f"unsupported statement {stmt!r}")

    # action definitions; helper definition ordering is callee before caller.
    for action in sorted(facts["actions"]):
        spec = facts["actions"][action]
        params = spec.get("params", {})
        env = {p: "Nat" for p in params}
        em = ActionEmitter(action, spec.get("body", []), params)
        final_env = em._final_env(env, spec.get("body", []))
        done = em.helper(final_env, ["Ok{s}"], "done")
        entry = em.seq(spec.get("body", []), env, final_env, done)
        param_sig = "".join(f", {p}: Nat" for p in params)
        out.extend(x.rstrip("\n") for x in em.defs)
        out.append("")
        out.append(f"def act_{action}(+s: State{param_sig}) -> Outcome:")
        out.append("  " + em.call(entry, env))
        out.append("")

    # Initial state, arrays use configured model bounds.
    init = facts.get("init", {})
    arr_init = init.get("arrays", {})
    values = {}
    for name, kind in fields:
        if kind == "scalar": values[name] = f"{int(init.get(name, 0))}n"
        else:
            length = n + 1 if name in facts["state"]["arrays_N"] else q
            entries = arr_init.get(name, {})
            vals = [f"{int(entries.get(str(i), 0))}n" for i in range(length)]
            values[name] = "[" + ", ".join(vals) + "]"
    out.append("def init_state() -> State:")
    out.append("  State{" + ", ".join(values[name] for name in names) + "}")
    out.append("")

    # Reachability support: statically instantiate every finite action argument assignment.
    action_calls = []
    for action in sorted(facts["actions"]):
        params = facts["actions"][action].get("params", {})
        domains = []
        for p, d in params.items():
            vals = list(range(1, n + 1)) if d == "1..N" else list(d)
            domains.append((p, vals))
        combos = [({}, 0)]
        for p, vals in domains:
            combos = [(dict(a, **{p: v}), 0) for a, _ in combos for v in vals]
        for assign, _ in combos:
            call = f"act_{action}(s" + "".join(f", {assign[p]}n" for p in params) + ")"
            action_calls.append(call)
    out.extend(["def keep(o: Outcome, acc: List<&2, State>) -> List<&2, State>:",
                "  match o:",
                "    case Ok{+state}:",
                "      Con{state, acc}",
                "    case Revert{tag}:",
                "      acc",
                "    case Bound{}:",
                "      acc",
                ""])
    out.append("def succs(+s: State) -> List<&2, State>:")
    if action_calls:
        expr = "Nil{}"
        for call in reversed(action_calls):
            expr = f"keep({call}, {expr})"
        out.append("  " + expr)
    else:
        out.append("  Nil{}")
    out.extend(["", "def contains_state(xs: List<&2, State>, +s: State) -> Bool:", "  match xs:", "    case Nil{}:", "      False{}", "    case Con{h, t}:", "      Bool.or(state_eq(h, s), contains_state(t, s))", "", "def add_fresh(+xs: List<&2, State>, +seen: List<&2, State>) -> List<&2, State>:", "  match xs:", "    case Nil{}:", "      Nil{}", "    case Con{+h, +t}:", "      List.append(&2, State,", "        Bool.pick(List<&2, State>, contains_state(seen, h), Nil{}, [h]),", "        add_fresh(t, Bool.pick(List<&2, State>, contains_state(seen, h), seen, Con{h, seen})))", "", "def expand_all(xs: List<&2, State>) -> List<&2, State>:", "  match xs:", "    case Nil{}:", "      Nil{}", "    case Con{h, t}:", "      List.append(&2, State, succs(h), expand_all(t))", "", "def reach_n(k: Nat, frontier: List<&2, State>, +seen: List<&2, State>) -> List<&2, State>:", "  match k:", "    case 0n:", "      seen", "    case 1n+p:", "      +fresh = add_fresh(expand_all(frontier), seen)", "      reach_n(p, fresh, List.append(&2, State, seen, fresh))", "", f"def reach_k(k: Nat) -> List<&2, State>:", "  reach_n(k, [init_state()], [init_state()])", ""])
    source = "\n".join(out) + "\n"
    missing = [f"act_{action}" for action in facts["actions"]
               if f"def act_{action}(" not in source]
    if missing:
        raise AssertionError(f"facts actions without generated functions: {missing}")
    return source


def action_functions(facts: dict) -> set[str]:
    return {f"act_{name}" for name in facts["actions"]}
