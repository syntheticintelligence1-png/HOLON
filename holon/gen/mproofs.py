"""Proof generators for state-machine laws (holon-ir/0.2), one per obligation class.

Untrusted like every generator: a proof counts only if Bend accepts it. Generators dispatch
on the statement's shape and on the machine's structure (reads, effects), never on law ids.

  evaluate        closed claims (no forall binders): `{==}` per conjunct; an exists law is
                  given its witness (from the refuter) and each conjunct is checked by evaluation.
  nat_split       forall binders of type Nat only: case split 0n / 1n+p, then `{==}`.
  noninterference forall tr s1 s2. proj(s1) == proj(s2) -> proj(run(tr, s1)) == proj(run(tr, s2)).
                  Per action: generalise over the decision of decide_<a> (which takes only the
                  fields it reads), so exec_<a> reduces branch by branch; then rewrite with the
                  hypothesis and induct over the trace (whitepaper Thm 6.9(i), §10.6).
  deadline        DISCH blocking for a guard kappa = b && (w + start(nth(chs, i))) < t:
                  preserved by every permissionless action whose effects leave kappa's fields
                  alone, only advance t, or only clear entries of chs (Thm 6.10).
  chain_revert    a guard kappa forces an action to revert: mirror the decide chain of the
                  action down to the require whose condition kappa falsifies.
  counter         refutations: the witness for every binder, `{==}` for every premise, and the
                  claim's two sides separated through the model's equality function.
  act_split       (holon-ir/0.3) one forall binder of type Act, no premises: match the action
                  constructor, then `{==}` per conjunct in every case.
  hyp             (holon-ir/0.3) the claim is one of the premises as rendered (for example a
                  conjunct of a collision-freedom premise, in decidable form): return that hypothesis.
  param_premise   (I12) every binder is a forall oracle parameter (a table): each conjunct of the claim
                  is closed by computation ({==}) or is a premise once both are computed (the model runs
                  on the tables until only lookups ap_p(p, x) remain); its candidates are {==}, h0, h1, ..
                  and Bend picks (holon.mpipeline.param_search). Not in GENERATORS: it yields candidates.
  product         (I26) the product program of a FACT law over the typed M3 model, by one route ("guard",
                  "injective", "provenance"): holon.fact.product. Not in GENERATORS: holon.fact.run calls it.

Witnesses over oracle parameters (I12) are resolved tables (holon.gen.mlaws.resolve_param); a witness dict
may carry "$defs" (name -> Bend def of a sidecar instance), which the proof file defines before using them.
"""
from __future__ import annotations

import re

from .machine import Machine, bname, bt, fresh
from .mlaws import ALIAS, EmittedM, Unsupported, binder_parts, q, reach_name, value_literal, witness_tabs

CORE = '''\
# ---- core lemmas (Nat / Bool / lists), proved here by induction; no axioms
def efq(-P: Type, x: Empty) -> P:
  match x:

def core_false_ne_true(e: {False{} == True{} : Bool}) -> Empty:
  (%Equal.sym(Bool, False{}, True{}, e) : M.is_true(_)
  Unit{})

def core_lt_add(x: Nat, t: Nat, +dt: Nat, e: {Nat.is_lt(x, t) == True{} : Bool}) -> {Nat.is_lt(x, Nat.add(t, dt)) == True{} : Bool}:
  match x t:
    case 0n 0n:
      efq({Nat.is_lt(0n, Nat.add(0n, dt)) == True{} : Bool}, core_false_ne_true(e))
    case 0n 1n+tp:
      {==}
    case 1n+xp 0n:
      efq({Nat.is_lt(1n+xp, Nat.add(0n, dt)) == True{} : Bool}, core_false_ne_true(e))
    case 1n+xp 1n+tp:
      core_lt_add(xp, tp, dt, e)

def core_le_zero(x: Nat) -> {Nat.is_le(0n, x) == True{} : Bool}:
  match x:
    case 0n:
      {==}
    case 1n+p:
      {==}

def core_le_refl(x: Nat) -> {Nat.is_le(x, x) == True{} : Bool}:
  match x:
    case 0n:
      {==}
    case 1n+p:
      core_le_refl(p)

def core_lt_of_le_lt(a: Nat, b: Nat, c: Nat, e1: {Nat.is_le(a, b) == True{} : Bool}, e2: {Nat.is_lt(b, c) == True{} : Bool}) -> {Nat.is_lt(a, c) == True{} : Bool}:
  match a b c:
    case 0n 0n 0n:
      efq({Nat.is_lt(0n, 0n) == True{} : Bool}, core_false_ne_true(e2))
    case 0n 1n+bp 0n:
      efq({Nat.is_lt(0n, 0n) == True{} : Bool}, core_false_ne_true(e2))
    case 0n _ 1n+cp:
      {==}
    case 1n+ap 0n _:
      efq({Nat.is_lt(1n+ap, c) == True{} : Bool}, core_false_ne_true(e1))
    case 1n+ap 1n+bp 0n:
      efq({Nat.is_lt(1n+ap, 0n) == True{} : Bool}, core_false_ne_true(e2))
    case 1n+ap 1n+bp 1n+cp:
      core_lt_of_le_lt(ap, bp, cp, e1, e2)

def core_le_add_l(w: Nat, a: Nat, b: Nat, e: {Nat.is_le(a, b) == True{} : Bool}) -> {Nat.is_le(Nat.add(w, a), Nat.add(w, b)) == True{} : Bool}:
  match w:
    case 0n:
      e
    case 1n+wp:
      core_le_add_l(wp, a, b, e)

def core_lt_not_le(x: Nat, t: Nat, e: {Nat.is_lt(x, t) == True{} : Bool}) -> {Nat.is_le(t, x) == False{} : Bool}:
  match x t:
    case 0n 0n:
      efq({Nat.is_le(0n, 0n) == False{} : Bool}, core_false_ne_true(e))
    case 0n 1n+tp:
      {==}
    case 1n+xp 0n:
      efq({Nat.is_le(0n, 1n+xp) == False{} : Bool}, core_false_ne_true(e))
    case 1n+xp 1n+tp:
      core_lt_not_le(xp, tp, e)

# a guard b && x < t falsifies the require !b || t <= x
def core_kappa_site(b: Bool, x: Nat, t: Nat, e: {Bool.and(b, Nat.is_lt(x, t)) == True{} : Bool}) -> {Bool.or(Bool.not(b), Nat.is_le(t, x)) == False{} : Bool}:
  match b:
    case True{}:
      core_lt_not_le(x, t, e)
    case False{}:
      efq({Bool.or(Bool.not(False{}), Nat.is_le(t, x)) == False{} : Bool}, core_false_ne_true(e))

def core_and_lt_add(b: Bool, x: Nat, t: Nat, +dt: Nat, e: {Bool.and(b, Nat.is_lt(x, t)) == True{} : Bool}) -> {Bool.and(b, Nat.is_lt(x, Nat.add(t, dt))) == True{} : Bool}:
  match b:
    case True{}:
      core_lt_add(x, t, dt, e)
    case False{}:
      efq({Bool.and(False{}, Nat.is_lt(x, Nat.add(t, dt))) == True{} : Bool}, core_false_ne_true(e))
'''


# The core library (holon.gen.core, I8) for M2+ milestones: None (M0, M1: their proofs paste CORE),
# "import" (import <gen>/core/PROOF.bend and call lemmas through the core LAWS alias C) or "paste"
# (the same lemmas pasted into each file: the cost baseline). Set by holon.mpipeline per run.
CORE_MODE: str | None = None
CORE_PASTE = ""


def core_import_lines(model_import: str) -> list[str]:
    if CORE_MODE == "import":
        base = model_import.rsplit("/model/", 1)[0]
        return [f"import {base}/core/PROOF.bend as CP", f"import {base}/core/LAWS.bend as C"]
    return []


def core_ref(name: str) -> str:
    """A core lemma as a generated proof calls it: M0 and M1 (CORE_MODE None) paste CORE, which defines it; M2+
    call the core library (holon.gen.core) through its LAWS alias C, or by its pasted name (`--core paste`)."""
    return f"C.{name}" if CORE_MODE == "import" else name


def efq_ref() -> str:
    """Ex falso: CORE's `efq` (M0, M1), else the core library's helper core_efq (in its PROOF, alias CP)."""
    return "efq" if CORE_MODE is None else ("CP.core_efq" if CORE_MODE == "import" else "core_efq")


def core_block() -> list[str]:
    """The pasted CORE of M0 and M1 proofs; M2+ proofs import (or paste) the generated core library instead."""
    return [CORE] if CORE_MODE is None else []


def _imports(model_import: str) -> list[str]:
    out = ["# GENERATED by holon.gen.mproofs; untrusted, accepted only if Bend checks it.", "import Base",
           f"import {model_import} as {ALIAS}"] + core_import_lines(model_import) + ["import ./LAWS.bend as Laws", ""]
    if CORE_MODE == "paste":
        out += CORE_PASTE.splitlines() + [""]
    return out


# ---------------------------------------------------------------- evaluate / nat_split / counter
def evaluate(em: EmittedM, m: Machine, model_import: str, witness: dict | None = None) -> str | None:
    if any(qq == "forall" for qq, _, _ in em.binders) or em.assume:
        return None
    ex = [(n, t) for qq, n, t in em.binders if qq == "exists"]
    if ex and witness is None:
        return None
    tabs = witness_tabs(m, em.binders, witness) if witness else ""
    parts = [x for n, t in ex for x in binder_parts(m, t, witness[n], tabs)] + ["{==}"] * len(em.claims)
    tup = parts[-1]
    for p in reversed(parts[:-1]):
        tup = f"({p}, {tup})"
    lines = ["# class evaluate: witnesses (if any), then every conjunct by computation", f"def Laws.{em.name}():", f"  {tup}"]
    return "\n".join(_imports(model_import) + _witness_defs(witness) + lines) + "\n"


def _witness_defs(witness: dict | None) -> list[str]:
    """The defs a resolved witness needs (the sidecar instances it applies, I12), each once, by name."""
    defs = (witness or {}).get("$defs") or {}
    return [line for name in sorted(defs) for line in defs[name].rstrip("\n").split("\n") + [""]]


def nat_split(em: EmittedM, m: Machine, model_import: str, depth: int = 1) -> str | None:
    fa = [(n, t) for qq, n, t in em.binders if qq == "forall"]
    if not fa or any(t != "Nat" for _, t in fa) or em.assume or len(fa) != 1:
        return None
    v = bname(fa[0][0])
    lines = [f"# class nat_split: case split {v} into 0n / 1n+p, then computation",
             f"def Laws.{em.name}({v}):", f"  match {v}:", "    case 0n:", "      {==}", "    case 1n+p:", "      {==}"]
    return "\n".join(_imports(model_import) + lines) + "\n"


def _eq_defs(m: Machine, view: str, erased: list) -> tuple[list[str], str]:
    """Structural equality over a View (untrusted helper: a wrong one only makes Bend reject)."""
    out = []

    def eqf(t: str) -> str:
        if t == "Nat":
            return "Nat.is_eq"
        if t == "Bool":
            return f"{ALIAS}.eq_bool"
        if t == "Obs":
            return f"{ALIAS}.eq_obs"
        if t.startswith("List<"):
            et = t[5:-1]
            name = f"peq_list_{et.replace('<', '_').replace('>', '')}"
            if not any(l.startswith(f"def {name}(") for l in out):
                inner = eqf(et)
                bt_ = q(bt(t))
                out.extend([f"def {name}(xs: {bt_}, ys: {bt_}) -> Bool:", "  match xs ys:", "    case Nil{} Nil{}:", "      True{}",
                            "    case Nil{} Con{h, t}:", "      False{}", "    case Con{h, t} Nil{}:", "      False{}",
                            "    case Con{x, xt} Con{y, yt}:", f"      Bool.and({inner}(x, y), {name}(xt, yt))", ""])
            return name
        fields = m.types[t]
        name = f"peq_{t}"
        if not any(l.startswith(f"def {name}(") for l in out):
            subs = [eqf(ft) for _, ft in fields]
            conj = "True{}"
            for (fn, _), e in reversed(list(zip(fields, subs))):
                conj = f"Bool.and({e}(a_{fn}, b_{fn}), {conj})"
            pa = ", ".join(f"a_{fn}" for fn, _ in fields)
            pb = ", ".join(f"b_{fn}" for fn, _ in fields)
            out.extend([f"def {name}(a: {ALIAS}.H{t}, b: {ALIAS}.H{t}) -> Bool:", "  match a b:",
                        f"    case {ALIAS}.H{t}{{{pa}}} {ALIAS}.H{t}{{{pb}}}:", f"      {conj}", ""])
        return name
    kept = [(n, t) for n, t in m.state if n not in erased]
    subs = [eqf(t) for _, t in kept]
    conj = "True{}"
    for (n, _), e in reversed(list(zip(kept, subs))):
        conj = f"Bool.and({e}(a_{n}, b_{n}), {conj})"
    pa = ", ".join(f"a_{n}" for n, _ in kept)
    pb = ", ".join(f"b_{n}" for n, _ in kept)
    out.extend([f"def peq_view(a: Laws.{view}, b: Laws.{view}) -> Bool:", "  match a b:",
                f"    case Laws.{view}{{{pa}}} Laws.{view}{{{pb}}}:", f"      {conj}", ""])
    return out, "peq_view"


def counter(em: EmittedM, m: Machine, model_import: str, witness: dict, lhs_at: str, ty: str) -> str:
    """lhs_at: the claim's left side re-emitted at the witness (Bend text)."""
    eqfn = {"Obs": f"{ALIAS}.eq_obs_list", "Bool": f"{ALIAS}.eq_bool", "Nat": "Nat.is_eq",
            "List<Nat>": f"{ALIAS}.eq_list_nat"}.get(ty)
    import re as _re
    lhs_at = _re.sub(r"(?<![\w.])proj_V_", "Laws.proj_V_", lhs_at)  # statement helpers live in LAWS.bend
    lhs_at = _re.sub(r"(?<![\w.])(ex_[0-9a-f]{12})\(", r"Laws.\1(", lhs_at)   # as do expr helpers (I24)
    lhs_at = _re.sub(r"(?<![\w.])(gh1?_[0-9a-f]{12})\(", r"Laws.\1(", lhs_at)   # and ghost helpers (I65 rule O1)
    helpers: list[str] = []
    if eqfn is None and ty in em.views:
        helpers, eqfn = _eq_defs(m, ty, em.views[ty])
    if eqfn is None:
        raise Unsupported(f"no equality function for {ty}")
    tabs = witness_tabs(m, em.binders, witness)
    parts = [x for _, n, t in em.binders for x in binder_parts(m, t, witness[n], tabs)] + ["{==}"] * len(em.assume)
    refute = f"e => (%e : {ALIAS}.is_true({eqfn}(_, {lhs_at}))\n  Unit{{}})"
    tup = refute
    for p in reversed(parts):
        tup = f"({p}, {tup})"
    lines = helpers + _witness_defs(witness) + [
        "# class counter: concrete witness, premises by computation, sides separated by an equality function",
        f"def Laws.{em.name}():", f"  {tup}"]
    return "\n".join(_imports(model_import) + lines) + "\n"


# ---------------------------------------------------------------- non-interference
def noninterference(em: EmittedM, m: Machine, model_import: str) -> str | None:
    fa = [(n, t) for qq, n, t in em.binders if qq == "forall"]
    if [t for _, t in fa] != ["Trace", "State", "State"] or len(em.assume) != 1 or len(em.claims) != 1 or len(em.views) != 1:
        return None
    (vname, erased), = em.views.items()
    tr, s1, s2 = (bname(n) for n, _ in fa)
    a0, b0, _ = em.assume[0]
    a1, b1, _ = em.claims[0]
    if (a0, b0) != (f"proj_{vname}({s1})", f"proj_{vname}({s2})") or \
            (a1, b1) != (f"proj_{vname}({ALIAS}.run({tr}, {s1}))", f"proj_{vname}({ALIAS}.run({tr}, {s2}))"):
        return None
    V = f"Laws.{vname}"
    P = f"Laws.proj_{vname}"
    names = [bname(n) for n, _ in m.state]
    kept = [bname(n) for n, _ in m.state if n not in erased]
    er = [bname(n) for n in erased]

    def fields(suffix: str) -> list[str]:
        return [f"{x}{suffix}" if x in er else x for x in names]

    out = ["# class noninterference: generalise each action's decision, rewrite with the hypothesis, induct on the trace", ""]
    # rebuild a state from a view and the erased fields
    out += [f"def ni_rebuild(v: {V}, {', '.join(f'{x}: {q(bt(m.stypes[x.rstrip(chr(95))] if x.rstrip(chr(95)) in m.stypes else m.stypes[x]))}' for x in er)}) -> {ALIAS}.HSt:",
            "  match v:", f"    case {V}{{{', '.join(kept)}}}:", f"      {ALIAS}.HSt{{{', '.join(names)}}}", ""]
    # per action: exec lemma generalised over the decision
    for a in m.actions:
        an = a["name"]
        ins = [bname(n) for n, _ in a["inputs"]]
        params = [f"+{x}: {q(bt(m.stypes[n]))}" for x, (n, _) in zip(names, m.state) if x not in er]
        params += [f"{x}1: {q(bt(m.stypes[n]))}" for x, n in zip(er, erased)] + [f"{x}2: {q(bt(m.stypes[n]))}" for x, n in zip(er, erased)]
        params += [f"+{bname(n)}: {q(bt(t))}" for n, t in a["inputs"]]
        args1 = ", ".join(fields("1") + ins)
        args2 = ", ".join(fields("2") + ins)
        dec = f"{ALIAS}.Dec_{an}"
        out += [f"def ni_exec_{an}(d: {dec}, {', '.join(params)}) -> {{{P}({ALIAS}.exec_{an}(d, {args1})) == {P}({ALIAS}.exec_{an}(d, {args2})) : {V}}}:",
                "  match d:", f"    case {ALIAS}.D_{an}_Rev{{code}}:", "      {==}", f"    case {ALIAS}.D_{an}_Ok{{" +
                ", ".join("_" for _ in _carried(m, a)) + "}:", "      {==}", ""]
    # step lemma over a shared view
    sparams = [f"+{x}: {q(bt(m.stypes[n]))}" for x, (n, _) in zip(names, m.state) if x not in er]
    sparams += [f"{x}1: {q(bt(m.stypes[n]))}" for x, n in zip(er, erased)] + [f"{x}2: {q(bt(m.stypes[n]))}" for x, n in zip(er, erased)]
    st1 = f"{ALIAS}.HSt{{{', '.join(fields('1'))}}}"
    st2 = f"{ALIAS}.HSt{{{', '.join(fields('2'))}}}"
    out += [f"def ni_step({', '.join(sparams)}, a: {ALIAS}.HAct) -> {{{P}({ALIAS}.step(a, {st1})) == {P}({ALIAS}.step(a, {st2})) : {V}}}:",
            "  match a:"]
    for a in m.actions:
        an = a["name"]
        ins = [bname(n) for n, _ in a["inputs"]]
        reads = [bname(r) for r in m.reads[an]]
        if any(r in er for r in reads):
            # decide reads an erased field: the lemma is false in general; emit the attempt so Bend reports it
            dargs1 = ", ".join([f"{r}1" if r in er else r for r in reads] + ins)
        else:
            dargs1 = ", ".join(reads + ins)
        out += [f"    case {ALIAS}.A_{an}{{{', '.join('+' + i for i in ins)}}}:",
                f"      ni_exec_{an}({ALIAS}.decide_{an}({dargs1}), {', '.join(kept + [f'{x}1' for x in er] + [f'{x}2' for x in er] + ins)})"]
    out.append("")
    # generalised step lemma: any two states with equal views
    pat1 = ", ".join(fields("1") if False else [f"{x}_a" for x in names])
    pat2 = ", ".join([f"{x}_b" for x in names])
    st_a = f"{ALIAS}.HSt{{{pat1}}}"
    rebuild_b = f"ni_rebuild(_, {', '.join(f'{x}_b' for x in er)})"
    lemma_args = ", ".join([f"{x}_a" for x in kept] + [f"{x}_a" for x in er] + [f"{x}_b" for x in er] + ["a"])
    out += [f"def ni_step_gen(s1: {ALIAS}.HSt, s2: {ALIAS}.HSt, e: {{{P}(s1) == {P}(s2) : {V}}}, +a: {ALIAS}.HAct) -> "
            f"{{{P}({ALIAS}.step(a, s1)) == {P}({ALIAS}.step(a, s2)) : {V}}}:",
            "  match s1 s2:", f"    case {st_a} {ALIAS}.HSt{{{pat2}}}:",
            f"      %e : {{{P}({ALIAS}.step(a, {st_a})) == {P}({ALIAS}.step(a, {rebuild_b})) : {V}}}",
            f"      ni_step({lemma_args})", ""]
    out += [f"def Laws.{em.name}({tr}, {s1}, {s2}, h0):", f"  match {tr}:", "    case Nil{}:", "      h0",
            "    case Con{+a, rest}:", f"      Laws.{em.name}(rest, {ALIAS}.step(a, {s1}), {ALIAS}.step(a, {s2}), ni_step_gen({s1}, {s2}, h0, a))"]
    return "\n".join(_imports(model_import) + out) + "\n"


def _carried(m: Machine, a: dict) -> list[str]:
    lets = [g["let"] for g in a["guards"] if "let" in g]
    eff = set().union(*(m.fv(e) for e in a["effects"].values())) if a["effects"] else set()
    return [l for l in lets if l in eff]


GENERATORS = [("evaluate", evaluate), ("nat_split", nat_split), ("noninterference", noninterference)]


# ---------------------------------------------------------------- DISCH: deadline guards
def _kappa_shape(m: Machine, name: str):
    """kappa = b && (x + get(nth(chs, i), f)) < t over state fields, where nth is a target-library list
    accessor with a default element (kind nth_default); returns the pieces or None."""
    o = m.f.get("observers", {}).get(name)
    if not o:
        return None
    e = o["body"]
    try:
        op, b, lt = e
        assert op == "&&" and isinstance(b, str) and lt[0] == "<"
        _, plus, t = lt
        assert plus[0] == "+" and isinstance(t, str)
        _, x, get = plus
        assert isinstance(x, str) and get[0] == "get"
        _, call, fld = get
        assert call[0] == "call" and m.lib.kind(call[1]) == "nth_default" and isinstance(call[2], str) \
            and isinstance(call[3], str)
        return {"b": b, "x": x, "xs": call[2], "i": call[3], "f": fld, "t": t, "expr": e,
                "start": get, "deadline": plus, "nth": call[1]}
    except (AssertionError, ValueError, TypeError, IndexError):
        return None


def _parse_guarded(em: EmittedM):
    fa = [(n, t) for qq, n, t in em.binders if qq == "forall"]
    if [t for _, t in fa] != ["State", "Act"] or len(em.assume) != 2 or len(em.claims) != 1:
        return None
    s, a = (bname(n) for n, _ in fa)
    (k_l, k_r, _), (p_l, p_r, _) = em.assume
    import re as _re
    mk = _re.fullmatch(rf"{ALIAS}\.(\w+)\({s}\)", k_l)
    mp = _re.fullmatch(rf"{ALIAS}\.(\w+)\({a}\)", p_l)
    if not (mk and mp and k_r == "True{}" and p_r == "True{}"):
        return None
    c_l, c_r, _ = em.claims[0]
    return s, a, mk.group(1), mp.group(1), c_l, c_r


def _state_pat(m: Machine) -> str:
    return f"{ALIAS}.HSt{{{', '.join(bname(n) for n, _ in m.state)}}}"


def _goal_for(m: Machine, act: dict, lhs_fn, rhs: str) -> str:
    ins = ", ".join(bname(n) for n, _ in act["inputs"])
    return f"{{{lhs_fn(f'{ALIAS}.A_{act['name']}{{{ins}}}')} == {rhs} : Bool}}"


def _ok_pat(m: Machine, act: dict) -> tuple[str, list]:
    car = _carried(m, act)
    return f"{ALIAS}.D_{act['name']}_Ok{{{', '.join('+' + bname(c) for c in car)}}}", car


def deadline(em: EmittedM, m: Machine, model_import: str) -> str | None:
    if CORE_MODE is not None:   # M2+: any conjunction of linear Nat comparisons, through the core library
        return deadline_linear(em, m, model_import)
    p = _parse_guarded(em)
    if not p:
        return None
    s, a, kname, pname, c_l, c_r = p
    if pname != "perm" or c_l != f"{ALIAS}.{kname}({ALIAS}.step({a}, {s}))" or c_r != "True{}":
        return None
    k = _kappa_shape(m, kname)
    if not k:
        return None
    rec, fld = m.lib.builtins[k["nth"]]["type"], k["f"]
    if m.stypes.get(k["xs"]) != f"List<{rec}>":
        return None
    kfields = {k["b"], k["x"], k["xs"], k["i"], k["t"]}
    dflt = m.lib.default_of(k["nth"])
    E = f"{ALIAS}.{m.lib.render(dflt, [])[0]}"
    get = lambda xs, j: f"{ALIAS}.g_{rec}_{fld}({ALIAS}.nth_d({ALIAS}.H{rec}, {xs}, {j}, {E}))"
    setE = lambda xs, i: f"{ALIAS}.set_d({ALIAS}.H{rec}, {xs}, {i}, {E}, {E})"
    out = ["# class deadline: kappa = b && w + start(chs[i]) < t is preserved by every permissionless action", ""]
    # list lemma: clearing an entry never raises the start time read at any index
    out += [f"def dl_nth_set_le(cs: List<&2, {ALIAS}.H{rec}>, i: Nat, j: Nat) -> {{Nat.is_le({get(setE('cs', 'i'), 'j')}, {get('cs', 'j')}) == True{{}} : Bool}}:",
            "  match cs i j:", "    case Nil{} 0n 0n:", "      {==}", "    case Nil{} 0n 1n+jq:", "      {==}",
            "    case Nil{} 1n+ip 0n:", "      {==}", "    case Nil{} 1n+ip 1n+jq:", "      dl_nth_set_le(Nil{}, ip, jq)",
            "    case Con{+h, t} 0n 0n:", f"      core_le_zero({ALIAS}.g_{rec}_{fld}(h))",
            "    case Con{h, +t} 0n 1n+jq:", f"      core_le_refl({get('t', 'jq')})",
            "    case Con{+h, t} 1n+ip 0n:", f"      core_le_refl({ALIAS}.g_{rec}_{fld}(h))",
            "    case Con{h, t} 1n+ip 1n+jq:", "      dl_nth_set_le(t, ip, jq)", ""]
    out += [f"def dl_and_lt_clear(b: Bool, +w: Nat, +cs: List<&2, {ALIAS}.H{rec}>, +i: Nat, +j: Nat, t: Nat, "
            f"e: {{Bool.and(b, Nat.is_lt(Nat.add(w, {get('cs', 'j')}), t)) == True{{}} : Bool}}) -> "
            f"{{Bool.and(b, Nat.is_lt(Nat.add(w, {get(setE('cs', 'i'), 'j')}), t)) == True{{}} : Bool}}:",
            "  match b:", "    case True{}:",
            f"      core_lt_of_le_lt(Nat.add(w, {get(setE('cs', 'i'), 'j')}), Nat.add(w, {get('cs', 'j')}), t, "
            f"core_le_add_l(w, {get(setE('cs', 'i'), 'j')}, {get('cs', 'j')}, dl_nth_set_le(cs, i, j)), e)",
            "    case False{}:",
            f"      efq({{Bool.and(False{{}}, Nat.is_lt(Nat.add(w, {get(setE('cs', 'i'), 'j')}), t)) == True{{}} : Bool}}, core_false_ne_true(e))", ""]
    spat = _state_pat(m)
    fargs = ", ".join(bname(n) for n, _ in m.state)
    kterm = lambda st: f"{ALIAS}.{kname}({st})"
    perm_names = {x["name"] for x in m.actions if x.get("principal", "").startswith(("anyone", "environment"))}
    cases = []
    for act in m.actions:
        an = act["name"]
        ins = [bname(n) for n, _ in act["inputs"]]
        insp = ", ".join("+" + i for i in ins)
        goal = _goal_for(m, act, lambda A: kterm(f"{ALIAS}.step({A}, {spat})"), "True{}")
        if an not in perm_names:
            cases.append((an, insp, f"efq({goal}, core_false_ne_true(h1))"))
            continue
        touched = {f: e for f, e in act["effects"].items() if f in kfields}
        okpat, car = _ok_pat(m, act)
        envx = {**m.stypes, **dict(act["inputs"]), **{c: None for c in car}}
        if not touched:
            okbody = "h0"
        elif set(touched) == {k["t"]} and touched[k["t"]][0] == "+" and touched[k["t"]][1] == k["t"]:
            dt, _ = m.ex(touched[k["t"]][2], {**m.stypes, **dict(act["inputs"])})
            okbody = (f"core_and_lt_add({bname(k['b'])}, Nat.add({bname(k['x'])}, {get(bname(k['xs']), bname(k['i']))}), "
                      f"{bname(k['t'])}, {dt}, h0)")
        elif set(touched) == {k["xs"]} and touched[k["xs"]][0] == "call" \
                and m.lib.kind(touched[k["xs"]][1]) == "set_default" and m.lib.default_of(touched[k["xs"]][1]) == dflt \
                and touched[k["xs"]][2] == k["xs"] and touched[k["xs"]][4] == ["call", dflt]:
            lets_t = {g["let"]: None for g in act["guards"] if "let" in g}
            env = {**m.stypes, **dict(act["inputs"])}
            ix, _ = m.ex(touched[k["xs"]][3], env)
            okbody = (f"dl_and_lt_clear({bname(k['b'])}, {bname(k['x'])}, {bname(k['xs'])}, {ix}, {bname(k['i'])}, "
                      f"{bname(k['t'])}, h0)")
            del lets_t
        else:
            return None
        iparams = ", ".join(f"+{bname(n)}: {q(bt(t))}" for n, t in act["inputs"])
        fparams = ", ".join(f"+{bname(n)}: {q(bt(t))}" for n, t in m.state)
        ex = f"{ALIAS}.exec_{an}(d, {fargs}{', ' + ', '.join(ins) if ins else ''})"
        out += [f"def dl_exec_{an}(d: {ALIAS}.Dec_{an}, {fparams}{', ' + iparams if iparams else ''}, "
                f"h0: {{{kterm(spat)} == True{{}} : Bool}}) -> {{{kterm(ex)} == True{{}} : Bool}}:",
                "  match d:", f"    case {ALIAS}.D_{an}_Rev{{code}}:", "      h0", f"    case {okpat}:", f"      {okbody}", ""]
        reads = ", ".join(bname(r) for r in m.reads[an])
        dec = f"{ALIAS}.decide_{an}({', '.join(x for x in [reads] + ins if x)})"
        cases.append((an, insp, f"dl_exec_{an}({dec}, {fargs}{', ' + ', '.join(ins) if ins else ''}, h0)"))
    out += [f"def Laws.{em.name}({s}, {a}, h0, h1):", f"  match {s}:", f"    case {ALIAS}.HSt{{{', '.join('+' + bname(n) for n, _ in m.state)}}}:",
            f"      match {a}:"]
    for an, insp, body in cases:
        out += [f"        case {ALIAS}.A_{an}{{{insp}}}:", f"          {body}"]
    return "\n".join(_imports(model_import) + [CORE] + out) + "\n"


# ---------------------------------------------------------------- DISCH: deadline over linear Nat conjunctions (M2+)
def _subst_vars(e, sub: dict):
    """A facts expression with the variables in `sub` replaced (function, field and type names untouched)."""
    if isinstance(e, str):
        return sub.get(e, e)
    if not isinstance(e, list) or not e:
        return e
    if e[0] == "call":
        return ["call", e[1]] + [_subst_vars(x, sub) for x in e[2:]]
    if e[0] == "get":
        return ["get", _subst_vars(e[1], sub), e[2]]
    if e[0] == "mk":
        return ["mk", e[1], {k: _subst_vars(v, sub) for k, v in e[2].items()}]
    if e[0] == "with":
        return ["with", e[1], _subst_vars(e[2], sub), {k: _subst_vars(v, sub) for k, v in e[3].items()}]
    if e[0] == "list":
        return ["list", e[1]] + [_subst_vars(x, sub) for x in e[2:]]
    return [e[0]] + [_subst_vars(x, sub) for x in e[1:]]


def _let_types(m: Machine, act: dict) -> dict:
    env, out = {**m.stypes, **dict(act["inputs"])}, {}
    for g in act["guards"]:
        if "let" in g:
            out[g["let"]] = m.ex(g["expr"], {**env, **out})[1]
    return out


class _Transport:
    """A proof that an action preserves kappa == True (deadline_linear), atom by atom. Texts are Bend over the
    pattern-bound old fields, the action's inputs and its carried lets (dl_exec_<a>); `new` texts read each
    touched field as its effect expression."""

    def __init__(self, m: Machine, act: dict, kfields: set, touched: dict, taken: set):
        from .mlaws import qualify_model
        self.m, self.act, self.kfields, self.touched = m, act, kfields, touched
        lets = _let_types(m, act)
        self.env = {**m.stypes, **dict(act["inputs"]), **{c: lets[c] for c in _carried(m, act)}}
        self.qual = lambda t: qualify_model(m, t)   # noqa: E731
        self.taken, self.n = set(taken), 0
        self.helpers: dict = {}   # name -> lines
        self.uses_and = False

    def fields(self, e) -> set:
        return self.m.fv(e) & self.kfields if not isinstance(e, (bool, int)) else set()

    def old(self, e) -> str:
        return self.qual(self.m.ex(e, self.env)[0])

    def new(self, e) -> str:
        return self.old(_subst_vars(e, self.touched))

    def var(self) -> str:
        self.n += 1
        v = fresh(f"hk{self.n}", self.taken)
        self.taken.add(v)
        return v

    def proof(self, e, h: str) -> str | None:
        """A proof of {new(e) == True} from h : {old(e) == True}, or None when the class cannot show it."""
        if not (self.fields(e) & set(self.touched)):
            return h
        if isinstance(e, list) and e[0] == "&&" and len(e) >= 3:
            left, right = e[1], (e[2] if len(e) == 3 else ["&&", *e[2:]])
            x, y = self.var(), self.var()
            pl, pr = self.proof(left, x), self.proof(right, y)
            if pl is None or pr is None:
                return None
            self.uses_and = True
            return (f"dl_and({self.old(left)}, {self.old(right)}, {self.new(left)}, {self.new(right)}, {h}, "
                    f"({x} => {pl}), ({y} => {pr}))")
        if isinstance(e, list) and e[0] in ("<", "<="):
            return self.compare(e[0], e[1], e[2], h)
        return None   # a touched Bool field or another atom form

    def compare(self, op: str, S, T, h: str) -> str | None:
        """S < T or S <= T: T advanced by its own increment (T := T + d), and/or S lowered summand-wise."""
        cur = h
        if self.fields(T) & set(self.touched):
            eff = self.touched.get(T) if isinstance(T, str) else None
            if not (isinstance(eff, list) and eff[0] == "+" and eff[1] == T
                    and not (self.fields(eff[2]) & set(self.touched))):
                return None
            d = self.old(eff[2])
            if op == "<":
                cur = f"{core_ref('core_lt_add')}({self.old(S)}, {self.old(T)}, {d}, {cur})"
            else:
                cur = (f"{core_ref('core_le_trans')}({self.old(S)}, {self.old(T)}, {self.new(T)}, {cur}, "
                       f"{core_ref('core_le_add_self')}({self.old(T)}, {d}))")
        if self.fields(S) & set(self.touched):
            mono = self.le(S)
            if mono is None:
                return None
            lemma = "core_lt_of_le_lt" if op == "<" else "core_le_trans"
            cur = f"{core_ref(lemma)}({self.new(S)}, {self.old(S)}, {self.new(T)}, {mono}, {cur})"
        return cur

    def le(self, S) -> str | None:
        """A proof of {Nat.is_le(new(S), old(S)) == True}: S a sum tree whose touched summands only go down."""
        if not (self.fields(S) & set(self.touched)):
            return f"{core_ref('core_le_refl')}({self.old(S)})"
        if isinstance(S, list) and S[0] == "+":
            pl, pr = self.le(S[1]), self.le(S[2])
            if pl is None or pr is None:
                return None
            return f"{core_ref('core_le_add_mono')}({self.new(S[1])}, {self.old(S[1])}, {self.new(S[2])}, {self.old(S[2])}, {pl}, {pr})"
        return self.cleared(S)

    def cleared(self, S) -> str | None:
        """A summand get(nth(xs, i), f) read from a list the action clears at some index: set to the accessor's own
        default (a target-library set_default of the nth_default's default), which never raises the summand."""
        m, lib = self.m, self.m.lib
        if not (isinstance(S, list) and S[0] == "get" and isinstance(S[1], list) and S[1][0] == "call" and len(S[1]) == 4):
            return None
        nth, xs, i, fld = S[1][1], S[1][2], S[1][3], S[2]
        if lib.kind(nth) != "nth_default" or not isinstance(xs, str) or xs not in self.touched \
                or self.fields(i) & set(self.touched):
            return None
        eff, dflt = self.touched[xs], lib.default_of(nth)
        if not (isinstance(eff, list) and eff[0] == "call" and lib.kind(eff[1]) == "set_default" and len(eff) == 5
                and lib.default_of(eff[1]) == dflt and eff[2] == xs and eff[4] == ["call", dflt]):
            return None   # (the cleared index is an effect: it reads the old fields)
        rec = lib.builtins[nth]["type"]
        if m.stypes.get(xs) != f"List<{rec}>" or dict(m.types.get(rec, [])).get(fld) != "Nat":
            return None
        name = f"dl_nth_set_le_{rec}_{fld}"
        if name not in self.helpers:
            E = f"{ALIAS}.{lib.render(dflt, [])[0]}"
            get = lambda cs, j: f"{ALIAS}.g_{rec}_{fld}({ALIAS}.nth_d({ALIAS}.H{rec}, {cs}, {j}, {E}))"   # noqa: E731
            setE = lambda cs, j: f"{ALIAS}.set_d({ALIAS}.H{rec}, {cs}, {j}, {E}, {E})"   # noqa: E731
            self.helpers[name] = [
                f"# clearing entry i of a {rec} list never raises the {fld} read at any index j",
                f"def {name}(cs: List<&2, {ALIAS}.H{rec}>, i: Nat, j: Nat) -> "
                f"{{Nat.is_le({get(setE('cs', 'i'), 'j')}, {get('cs', 'j')}) == True{{}} : Bool}}:",
                "  match cs i j:", "    case Nil{} 0n 0n:", "      {==}", "    case Nil{} 0n 1n+jq:", "      {==}",
                "    case Nil{} 1n+ip 0n:", "      {==}", "    case Nil{} 1n+ip 1n+jq:", f"      {name}(Nil{{}}, ip, jq)",
                "    case Con{+h, t} 0n 0n:", f"      {core_ref('core_le_zero')}({ALIAS}.g_{rec}_{fld}(h))",
                "    case Con{h, +t} 0n 1n+jq:", f"      {core_ref('core_le_refl')}({get('t', 'jq')})",
                "    case Con{+h, t} 1n+ip 0n:", f"      {core_ref('core_le_refl')}({ALIAS}.g_{rec}_{fld}(h))",
                "    case Con{h, t} 1n+ip 1n+jq:", f"      {name}(t, ip, jq)", ""]
        return f"{name}({self.old(xs)}, {self.old(eff[3])}, {self.old(i)})"


def _and_helper() -> list[str]:
    goal = "{Bool.and(a2, b2) == True{} : Bool}"
    efq = f"{efq_ref()}({goal}, {core_ref('core_false_ne_true')}(h))"
    return ["# a conjunction stays true when each conjunct's truth carries over (core_and_intro)",
            "def dl_and(a: Bool, b: Bool, a2: Bool, b2: Bool, h: {Bool.and(a, b) == True{} : Bool}, "
            "fa: {a == True{} : Bool} -> {a2 == True{} : Bool}, fb: {b == True{} : Bool} -> {b2 == True{} : Bool}) -> "
            f"{goal}:",
            "  match a b:", "    case True{} True{}:", f"      {core_ref('core_and_intro')}(a2, b2, fa({{==}}), fb({{==}}))",
            "    case True{} False{}:", f"      {efq}", "    case False{} _:", f"      {efq}", ""]


def deadline_linear(em: EmittedM, m: Machine, model_import: str) -> str | None:
    """DISCH blocking (Thm 6.10) for M2+ (audit M2/1 F-M2-15): kappa is any conjunction (any nesting of &&) of
    atoms; an atom no action touches is carried as is, a comparison S < T or S <= T of linear Nat sums (any sum
    tree, any summand order) survives an action that only advances T by its own increment (T := T + d) and only
    lowers summands of S (a list entry cleared to the accessor's default). Each atom's step is a core lemma
    (holon.gen.core, through C: core_lt_add, core_le_trans with core_le_add_self, core_lt_of_le_lt with
    core_le_add_mono and core_le_refl); conjunctions by the generated dl_and (core_and_intro). Preserved by every
    permissionless action (Machine.permissionless: the permission guards in an M2+ model); any other action is
    excluded by the perm premise. None when an atom is touched in another way."""
    p = _parse_guarded(em)
    if not p:
        return None
    s, a, kname, pname, c_l, c_r = p
    if pname != "perm" or c_l != f"{ALIAS}.{kname}({ALIAS}.step({a}, {s}))" or c_r != "True{}":
        return None
    o = m.f.get("observers", {}).get(kname)
    if not o or o.get("type") != "Bool" or m.threaded:
        return None
    body = o["body"]
    kfields = m.fv(body) & set(m.stypes)
    perm_names = set(m.permissionless())
    taken = {bname(n) for n, _ in m.state} | {bname(n) for x in m.actions for n, _ in x["inputs"]} \
        | {bname(g["let"]) for x in m.actions for g in x["guards"] if "let" in g} | {"h0", "h1", "d", "code", s, a}
    spat = _state_pat(m)
    fargs = ", ".join(bname(n) for n, _ in m.state)
    kterm = lambda st: f"{ALIAS}.{kname}({st})"   # noqa: E731
    helpers: dict = {}
    uses_and = False
    out, cases = [], []
    for act in m.actions:
        an = act["name"]
        ins = [bname(n) for n, _ in act["inputs"]]
        insp = ", ".join("+" + i for i in ins)
        if an not in perm_names:
            goal = _goal_for(m, act, lambda A: kterm(f"{ALIAS}.step({A}, {spat})"), "True{}")
            cases.append((an, insp, f"{efq_ref()}({goal}, {core_ref('core_false_ne_true')}(h1))"))
            continue
        touched = {f: e for f, e in act["effects"].items() if f in kfields}
        if touched:
            tr = _Transport(m, act, kfields, touched, taken)
            okbody = tr.proof(body, "h0")
            if okbody is None:
                return None
            helpers.update(tr.helpers)
            uses_and = uses_and or tr.uses_and
        else:
            okbody = "h0"
        okpat, _ = _ok_pat(m, act)
        iparams = ", ".join(f"+{bname(n)}: {q(bt(t))}" for n, t in act["inputs"])
        fparams = ", ".join(f"+{bname(n)}: {q(bt(t))}" for n, t in m.state)
        ex = f"{ALIAS}.exec_{an}(d, {fargs}{', ' + ', '.join(ins) if ins else ''})"
        out += [f"def dl_exec_{an}(d: {ALIAS}.Dec_{an}, {fparams}{', ' + iparams if iparams else ''}, "
                f"h0: {{{kterm(spat)} == True{{}} : Bool}}) -> {{{kterm(ex)} == True{{}} : Bool}}:",
                "  match d:", f"    case {ALIAS}.D_{an}_Rev{{code}}:", "      h0", f"    case {okpat}:", f"      {okbody}", ""]
        reads = ", ".join(bname(r) for r in m.reads[an])
        dec = f"{ALIAS}.decide_{an}({', '.join(x for x in [reads] + ins if x)})"
        cases.append((an, insp, f"dl_exec_{an}({dec}, {fargs}{', ' + ', '.join(ins) if ins else ''}, h0)"))
    head = ["# class deadline (linear): kappa, a conjunction of linear Nat comparisons, is preserved by every "
            "permissionless action, atom by atom through the core library", ""]
    head += [line for name in sorted(helpers) for line in helpers[name]] + (_and_helper() if uses_and else [])
    out += [f"def Laws.{em.name}({s}, {a}, h0, h1):", f"  match {s}:", f"    case {ALIAS}.HSt{{{', '.join('+' + bname(n) for n, _ in m.state)}}}:",
            f"      match {a}:"]
    for an, insp, b in cases:
        out += [f"        case {ALIAS}.A_{an}{{{insp}}}:", f"          {b}"]
    return "\n".join(_imports(model_import) + core_block() + head + out) + "\n"


# ---------------------------------------------------------------- DISCH: a guard forces a revert
def _inline(m: Machine, e, lets: dict, keep: set):
    """Substitute let names (not in keep) by their expressions, recursively."""
    if isinstance(e, str):
        if e in lets and e not in keep:
            return _inline(m, lets[e], lets, keep)
        return e
    if isinstance(e, list):
        if e and e[0] in ("mk", "with"):
            return e
        if e and e[0] == "call":
            return ["call", e[1]] + [_inline(m, x, lets, keep) for x in e[2:]]
        if e and e[0] == "get":
            return ["get", _inline(m, e[1], lets, keep), e[2]]
        return [e[0]] + [_inline(m, x, lets, keep) for x in e[1:]]
    return e


def chain_revert(em: EmittedM, m: Machine, model_import: str) -> str | None:
    p = _parse_guarded(em)
    if not p:
        return None
    s, a, kname, pname, c_l, c_r = p
    if not pname.startswith("is_") or c_l != f"{ALIAS}.last_ok({ALIAS}.step({a}, {s}))" or c_r != "False{}":
        return None
    k = _kappa_shape(m, kname)
    act = next((x for x in m.actions if f"is_{x['name']}" == pname), None)
    if not k or act is None:
        return None
    an = act["name"]
    lets = {g["let"]: g["expr"] for g in act["guards"] if "let" in g}
    target = ["||", ["!", k["b"]], ["<=", k["t"], k["deadline"]]]
    site = None
    for i, g in enumerate(act["guards"]):
        if "require" in g and _inline(m, g["require"], lets, set()) == target:
            site = i
            break
    if site is None:
        return None
    info = m.chains[an]
    helpers = info["helpers"]
    path, rec = [], info["top"]
    while rec is not None:
        path.append((rec["call"], rec))
        if helpers[rec["call"]]["guard_index"] == site:
            break
        rec = helpers[rec["call"]]["next"]
    if helpers[path[-1][0]]["guard_index"] != site:
        return None
    req = act["guards"][site]["require"]
    dec = f"{ALIAS}.Dec_{an}"
    out = ["# class chain_revert: kappa falsifies one require of the decide chain, so the action reverts", "",
           f"def cr_rev(d: {dec}) -> Bool:", "  match d:", f"    case {ALIAS}.D_{an}_Rev{{c}}:", "      True{}",
           f"    case {ALIAS}.D_{an}_Ok{{{', '.join('_' for _ in _carried(m, act))}}}:", "      False{}", ""]
    lemmas = []
    for idx, (hname, _) in enumerate(path):
        h = helpers[hname]
        pvars = [v for v, _ in h["params"]]
        cond_txt, _ = m.ex(_inline(m, req, lets, set(pvars)), dict(h["params"]))
        params = ", ".join(f"+{bname(v)}: {q(bt(t))}" for v, t in h["params"])
        args = ", ".join(bname(v) for v in pvars)
        if idx == len(path) - 1:
            lemmas.append([f"def cr_{idx}({params}{', ' if params else ''}hk: {{{q(cond_txt)} == False{{}} : Bool}}) -> "
                           f"{{cr_rev({ALIAS}.{hname}({q(cond_txt)}{', ' + args if args else ''})) == True{{}} : Bool}}:",
                           f"  %Equal.sym(Bool, {q(cond_txt)}, False{{}}, hk) : {{cr_rev({ALIAS}.{hname}(_{', ' + args if args else ''})) == True{{}} : Bool}}",
                           "  {==}", ""])
        else:
            nxt = h["next"]
            call_args = ", ".join(nxt["args"])
            last = idx + 1 == len(path) - 1
            call = (f"cr_{idx + 1}({call_args}{', ' if call_args else ''}hk)" if last
                    else f"cr_{idx + 1}({q(nxt['cond'])}{', ' + call_args if call_args else ''}, hk)")
            body = ["    case True{}:"] + [f"      {q(l)}" for l in nxt["let_lines"]] + [f"      {call}"]
            lemmas.append([f"def cr_{idx}(c: Bool{', ' + params if params else ''}, hk: {{{q(cond_txt)} == False{{}} : Bool}}) -> "
                           f"{{cr_rev({ALIAS}.{hname}(c{', ' + args if args else ''})) == True{{}} : Bool}}:",
                           "  match c:", "    case False{}:", "      {==}"] + body + [""])
    for l in reversed(lemmas):
        out += l
    # final: a reverting decision means the action did not succeed
    ins = [bname(n) for n, _ in act["inputs"]]
    fparams = ", ".join(f"+{bname(n)}: {q(bt(t))}" for n, t in m.state)
    iparams = ", ".join(f"+{bname(n)}: {q(bt(t))}" for n, t in act["inputs"])
    fargs = ", ".join(bname(n) for n, _ in m.state)
    okpat = f"{ALIAS}.D_{an}_Ok{{{', '.join(bname(c) for c in _carried(m, act))}}}"
    ex = lambda d: f"{ALIAS}.exec_{an}({d}, {fargs}{', ' + ', '.join(ins) if ins else ''})"
    out += [f"def cr_final(d: {dec}, {fparams}{', ' + iparams if iparams else ''}, r: {{cr_rev(d) == True{{}} : Bool}}) -> "
            f"{{{ALIAS}.last_ok({ex('d')}) == False{{}} : Bool}}:",
            "  match d:", f"    case {ALIAS}.D_{an}_Rev{{c}}:", "      {==}", f"    case {okpat}:",
            f"      {efq_ref()}({{{ALIAS}.last_ok({ex(okpat)}) == False{{}} : Bool}}, {core_ref('core_false_ne_true')}(r))", ""]
    spat = _state_pat(m)
    top = info["top"]
    kb, kx, kt = bname(k["b"]), None, bname(k["t"])
    kx, _ = m.ex(k["deadline"], dict(m.stypes))
    first_call = (f"cr_0({', '.join(top['args'])}{', ' if top['args'] else ''}HK)" if len(path) == 1
                  else f"cr_0({q(top['cond'])}{', ' + ', '.join(top['args']) if top['args'] else ''}, HK)")
    first_call = first_call.replace("HK", f"{core_ref('core_kappa_site')}({kb}, {q(kx)}, {kt}, h0)")
    reads = ", ".join(bname(r) for r in m.reads[an])
    dec_call = f"{ALIAS}.decide_{an}({', '.join(x for x in [reads] + ins if x)})"
    out += [f"def Laws.{em.name}({s}, {a}, h0, h1):", f"  match {s}:", f"    case {ALIAS}.HSt{{{', '.join('+' + bname(n) for n, _ in m.state)}}}:",
            f"      match {a}:"]
    for b in m.actions:
        bins = [bname(n) for n, _ in b["inputs"]]
        out.append(f"        case {ALIAS}.A_{b['name']}{{{', '.join('+' + i for i in bins)}}}:")
        if b is act:
            out += [f"          {q(l)}" for l in top["let_lines"]]
            out.append(f"          cr_final({dec_call}, {fargs}{', ' + ', '.join(ins) if ins else ''}, {first_call})")
        else:
            goal = _goal_for(m, b, lambda A: f"{ALIAS}.last_ok({ALIAS}.step({A}, {spat}))", "False{}")
            out.append(f"          {efq_ref()}({goal}, {core_ref('core_false_ne_true')}(h1))")
    return "\n".join(_imports(model_import) + core_block() + out) + "\n"


# ---------------------------------------------------------------- holon-ir/0.3: act_split, hyp
def _tuple(parts: list[str]) -> str:
    tup = parts[-1]
    for p in reversed(parts[:-1]):
        tup = f"({p}, {tup})"
    return tup


def act_split(em: EmittedM, m: Machine, model_import: str) -> str | None:
    fa = [(n, t) for qq, n, t in em.binders if qq == "forall"]
    if len(fa) != 1 or fa[0][1] != "Act" or em.assume or len(fa) != len(em.binders):
        return None
    v = bname(fa[0][0])
    body = _tuple(["{==}"] * len(em.claims))
    lines = [f"# class act_split: case split {v} by action constructor, then computation per conjunct",
             f"def Laws.{em.name}({v}):", f"  match {v}:"]
    for a in m.actions:
        ins = [bname(n) for n, _ in a["inputs"]]
        lines += [f"    case {ALIAS}.A_{a['name']}{{{', '.join('+' + i for i in ins)}}}:", f"      {body}"]
    return "\n".join(_imports(model_import) + lines) + "\n"


def hyp(em: EmittedM, m: Machine, model_import: str) -> str | None:
    if len(em.claims) != 1 or any(qq != "forall" for qq, _, _ in em.binders):
        return None
    c = em.claims[0]
    hit = next((i for i, a in enumerate(em.assume) if a == c), None)
    if hit is None:
        return None
    params = [bname(n) for _, n, _ in em.binders] + [f"h{i}" for i in range(len(em.assume))]
    lines = ["# class hyp: the claim is premise h%d as rendered" % hit, f"def Laws.{em.name}({', '.join(params)}):", f"  h{hit}"]
    return "\n".join(_imports(model_import) + lines) + "\n"


_EXPR_DEF = re.compile(r"^def ex_[0-9a-f]{12}\(", re.M)


def expr_open(em: EmittedM, m: Machine, model_import: str) -> str | None:
    """I24, a universal law over expr terms (holon.gen.mlaws.Emitter.expr_term): open every Act binder by its
    constructors and every State or Reach binder's state record, then {==} for every conjunct in every case (the
    statement helpers compute once the action and the state are constructors)."""
    if not _EXPR_DEF.search(em.text) or any(qq != "forall" for qq, _, _ in em.binders):
        return None
    if not any(t in ("Act", "State", "Reach") for _, _, t in em.binders):
        return None
    params = law_params(em) + [f"h{i}" for i in range(len(em.assume))]
    lines = ["# class expr_open: open the actions and the states, then computation per conjunct",
             f"def Laws.{em.name}({', '.join(params)}):"]
    k = 0

    def fresh_vars(n: int) -> list[str]:
        nonlocal k
        out = [f"+x{k + i}" for i in range(n)]
        k += n
        return out
    body = _tuple(["{==}"] * len(em.claims))

    def open_from(i: int, ind: int) -> list[str]:
        if i == len(em.binders):
            return [" " * ind + body]
        _, n, t = em.binders[i]
        v = bname(n)
        if t == "Act":
            out = [" " * ind + f"match {v}:"]
            for a in m.actions:
                out.append(" " * (ind + 2) + f"case {ALIAS}.A_{a['name']}{{{', '.join(fresh_vars(len(a['inputs'])))}}}:")
                out += open_from(i + 1, ind + 4)
            return out
        if t in ("State", "Reach"):
            return ([" " * ind + f"match {v}:",
                     " " * (ind + 2) + f"case {ALIAS}.HSt{{{', '.join(fresh_vars(len(m.state)))}}}:"]
                    + open_from(i + 1, ind + 4))
        return open_from(i + 1, ind)
    lines += open_from(0, 2)
    return "\n".join(_imports(model_import) + lines) + "\n"


GENERATORS = [("evaluate", evaluate), ("nat_split", nat_split), ("noninterference", noninterference),
              ("deadline", deadline), ("chain_revert", chain_revert), ("act_split", act_split), ("hyp", hyp),
              ("expr_open", expr_open)]

# I65 (= I33b, tests_m3/test_o12.py rule O2): linear bounds over the runs of a trace, appended after every earlier class
from .trace_bound import trace_bound   # noqa: E402
GENERATORS.append(("trace_bound", trace_bound))


# ---------------------------------------------------------------- I15: coercion_guard
def law_params(em: EmittedM) -> list[str]:
    """The parameters of Laws.<law>: one per binder in emitted order, a Reach binder's evidence after its state."""
    out = []
    for _, n, t in em.binders:
        out.append(bname(n))
        if t == "Reach":
            out.append(reach_name(n))
    return out


def coercion_guard(em: EmittedM, m: Machine, model_import: str, model_text: str) -> tuple[str | None, str]:
    """(PROOF.bend text, note) of a SORT-site law, `site_<x>(a, s[, tables]) == True` for every a and s, by mirroring
    the ghost chain of model_text (the instrumented model the law imports; holon.gen.coercion); (None, why) when the
    class does not apply. Not in GENERATORS: it reads the model text (holon.mpipeline calls it after them)."""
    from . import coercion
    if len(em.claims) != 1 or em.assume or any(qq != "forall" for qq, _, _ in em.binders):
        return None, "not a universal law with one claim and no premises"
    lhs, rhs, ty = em.claims[0]
    if rhs != "True{}" or ty != "Bool" or not lhs.startswith(f"{ALIAS}.site_"):
        return None, "the claim is not a SORT-site term"
    if CORE_MODE is None:
        return None, "coercion_guard calls the core library (M2+ milestones)"
    try:
        text, used, notes = coercion.proof(model_text, lhs, em.name, law_params(em), _imports(model_import), core_ref)
    except coercion.NoProof as e:
        return None, str(e)
    return text, f"core lemmas {', '.join(used)}; " + "; ".join(notes)


# ---------------------------------------------------------------- I12: param_premise
PARAM_PREMISE_MAX = 64


def param_premise(em: EmittedM, m: Machine, model_import: str) -> list[str] | None:
    """Candidate proofs of a law whose binders are all forall oracle parameters (tables): the claim's conjuncts
    each closed by {==} or by a premise h_i, which Bend accepts when the two agree once the model has run on the
    tables (only lookups ap_p(p, x) remain). Candidates in order: {==} first, then h0, h1, ..; at most
    PARAM_PREMISE_MAX. None when the class does not apply."""
    import itertools
    from .mlaws import fn_sig
    if not m.oparams or not em.binders or any(qq != "forall" or n not in m.oparams or not fn_sig(t)
                                             for qq, n, t in em.binders):
        return None
    cands = ["{==}"] + [f"h{i}" for i in range(len(em.assume))]
    params = [bname(n) for _, n, _ in em.binders] + [f"h{i}" for i in range(len(em.assume))]
    out = []
    for combo in itertools.islice(itertools.product(cands, repeat=len(em.claims)), PARAM_PREMISE_MAX):
        lines = ["# class param_premise: each conjunct by computation or by a premise, once the model has run on the "
                 "oracle tables", f"def Laws.{em.name}({', '.join(params)}):", f"  {_tuple(list(combo))}"]
        out.append("\n".join(_imports(model_import) + lines) + "\n")
    return out


# ---------------------------------------------------------------- holon-ir/0.3: reach_invariant (I8)
class ReachProof:
    """A Reach induction proof with open choice slots (whitepaper §8.3 R, §10.3).

    The invariant is the law's claim conjuncts, plus strengthening facts `field == constant` proposed by
    holon/js/houdini.mjs (untrusted; they live only here, in the proof file, never in LAWS.bend). The
    proof inducts on Reach: s0 by computation; a step by one lemma per action, generalised over the
    action's decision, after rewriting every strengthened field to its constant. Each component of
    each decision branch is a slot whose candidates are `{==}` and the hypotheses; Bend decides, and
    holon.mpipeline.reach_search advances the slot it rejects (render() maps lines to slots)."""

    def __init__(self, em: EmittedM, m: Machine, model_import: str, strengthening: list):
        from .mlaws import Emitter
        rb = [(qq, n, t) for qq, n, t in em.binders if t == "Reach"]
        if len(rb) != 1 or len(em.binders) != 1 or rb[0][0] != "forall" or em.assume:
            raise Unsupported("reach_invariant needs exactly one forall Reach binder and no premises")
        if m.threaded:
            raise Unsupported("reach_invariant over a model that threads oracle tables is not generated yet (I12)")
        self.em, self.m, self.imp = em, m, model_import
        self.v = bname(rb[0][1])
        self.rv = reach_name(rb[0][1])
        E = Emitter(m)
        self.targets = [f"{{{a} == {b} : {E.bend_ty(t)}}}" for a, b, t in em.claims]
        self.strength = list(strengthening)    # [(field, type, value)]
        fields = [bname(n) for n, _ in m.state]
        taken = set(fields) | {bname(n) for a in m.actions for n, _ in a["inputs"]}
        self.N = {k: fresh(k, taken) for k in ("ih", "s1", "a", "dd", "cc", "p", "r1", "e")}
        self.P = em.name + "_ri"
        self.ncomp = len(self.targets) + len(self.strength)

    # component j as a type of state expression `st`
    def comp_def(self, j: int) -> list[str]:
        v = self.v
        if j < len(self.targets):
            body = self.targets[j]
        else:
            f, ty, _ = self.strength[j - len(self.targets)]
            body = f"{{{self.P}_g_{f}({v}) == {self.const(ty, self.strength[j - len(self.targets)][2])} : {q(bt(ty))}}}"
        return [f"def {self.P}_c{j}({v}: {ALIAS}.HSt) -> Type:", f"  {body}", ""]

    def const(self, ty: str, val) -> str:
        return self.m.literal(ty, val)

    def inv_type(self, st: str) -> str:
        parts = [f"{self.P}_c{j}({st})" for j in range(self.ncomp)]
        out = parts[-1]
        for p in reversed(parts[:-1]):
            out = f"{p} & ({out})" if "&" in out else f"{p} & {out}"
        return out

    def slots(self) -> list:
        """[(action, branch, component)] in render order, then the base case's components."""
        out = []
        for a in self.m.actions:
            for br in ("Rev", "Ok"):
                for j in range(self.ncomp):
                    out.append((a["name"], br, j))
        return out

    def candidates(self, j: int) -> list[str]:
        hs = [f"h{j}"] if j < len(self.targets) else []
        return hs + ["{==}"] + [f"h{i}" for i in range(len(self.targets)) if i != j]

    def render(self, choice: dict) -> tuple[str, dict]:
        m, v, N, P = self.m, self.v, self.N, self.P
        fields = [bname(n) for n, _ in m.state]
        stypes = {bname(n): t for n, t in m.state}
        rewritten = {bname(f): self.const(ty, val) for f, ty, val in self.strength}
        lines = ["# class reach_invariant: induction on Reach (s0, then one lemma per action generalised over its decision)"]
        if self.strength:
            lines.append("# strengthening (proposed by holon/js/houdini.mjs, untrusted; it lives only in this proof file): "
                         + ", ".join(f"{f} == {val}" for f, _, val in self.strength))
        else:
            lines.append("# strengthening: none (the claim is inductive on its own)")
        lines.append("")
        for f, ty, _ in self.strength:
            pat = ", ".join("+" + x for x in fields)
            lines += [f"def {P}_g_{f}({v}: {ALIAS}.HSt) -> {q(bt(ty))}:", f"  match {v}:", f"    case {ALIAS}.HSt{{{pat}}}:", f"      {bname(f)}", ""]
        for j in range(self.ncomp):
            lines += self.comp_def(j)
        lines += [f"def {P}_I({v}: {ALIAS}.HSt) -> Type:", f"  {self.inv_type(v)}", ""]
        if self.strength:
            lines += [f"def {P}_app(-A: Type, -B: Type, f: A -> B, x: A) -> B:", "  f(x)", ""]
        slot_at: dict = {}
        sub_state = f"{ALIAS}.HSt{{{', '.join(rewritten.get(x, x) for x in fields)}}}"
        nt = len(self.targets)
        # per action: the exec lemma over the decision
        for a in m.actions:
            an = a["name"]
            ins = [bname(n) for n, _ in a["inputs"]]
            params = [f"+{x}: {q(bt(stypes[x]))}" for x in fields if x not in rewritten]
            params += [f"+{bname(n)}: {q(bt(t))}" for n, t in a["inputs"]]
            params += [f"h{j}: {P}_c{j}({sub_state})" for j in range(nt)]
            eargs = ", ".join([rewritten.get(x, x) for x in fields] + ins)
            lines += [f"def {P}_exec_{an}({N['dd']}: {ALIAS}.Dec_{an}, {', '.join(params)}) -> {P}_I({ALIAS}.exec_{an}({N['dd']}, {eargs})):",
                      f"  match {N['dd']}:"]
            for br in ("Rev", "Ok"):
                pat = f"{{{N['cc']}}}" if br == "Rev" else "{" + ", ".join("_" for _ in _carried(m, a)) + "}"
                lines.append(f"    case {ALIAS}.D_{an}_{br}{pat}:")
                comps = [self.candidates(j)[choice.get((an, br, j), 0)] for j in range(self.ncomp)]
                for j, c in enumerate(comps):   # right-nested pairs, one component per line
                    head = "      " + ("(" if j < self.ncomp - 1 else "")
                    tail = "," if j < self.ncomp - 1 else ")" * (self.ncomp - 1)
                    slot_at[len(lines) + 1] = (an, br, j)
                    lines.append(f"{head}{c}{tail}")
            lines.append("")
        # the step lemma
        lines += [f"def {P}_step(+{N['a']}: {ALIAS}.HAct, {N['s1']}: {ALIAS}.HSt, {N['ih']}: {P}_I({N['s1']})) -> {P}_I({ALIAS}.step({N['a']}, {N['s1']})):",
                  f"  match {N['a']} {N['s1']}:"]
        for a in m.actions:
            an = a["name"]
            ins = [bname(n) for n, _ in a["inputs"]]
            act = f"{ALIAS}.A_{an}{{{', '.join(ins)}}}"
            lines.append(f"    case {ALIAS}.A_{an}{{{', '.join('+' + i for i in ins)}}} {ALIAS}.HSt{{{', '.join('+' + x for x in fields)}}}:")
            hs = [f"h{j}" for j in range(self.ncomp)]
            if self.ncomp == 1:
                lines.append(f"      h0 = {N['ih']}")
            else:
                cur = N["ih"]
                for j in range(self.ncomp - 1):
                    nxt = f"hr{j}" if j < self.ncomp - 2 else hs[-1]
                    lines.append(f"      ({hs[j]}, {nxt}) = {cur}")
                    cur = nxt
            reads = [rewritten.get(bname(r), bname(r)) for r in m.reads[an]]
            dargs = ", ".join(reads + ins)
            call = f"{P}_exec_{an}({ALIAS}.decide_{an}({dargs}), {', '.join([x for x in fields if x not in rewritten] + ins)}"
            if not self.strength:
                lines.append(f"      {call}, {', '.join(f'h{j}' for j in range(nt))})")
                continue
            # equations are Type (never Data), so each is used once: the goal and the target hypotheses are
            # rewritten together, through a function-typed motive, and the result applied to the hypotheses
            def motive(st: str) -> str:
                return " -> ".join([f"{P}_c{j}({ALIAS}.HSt{{{st}}})" for j in range(nt)]
                                   + [f"{P}_I({ALIAS}.step({act}, {ALIAS}.HSt{{{st}}}))"])
            done: dict = {}
            fn = ""
            heads = []
            for k, (f, ty, val) in enumerate(self.strength):
                fb = bname(f)
                st = ", ".join("_" if x == fb else done.get(x, x) for x in fields)
                heads.append(f"(%Equal.sym({q(bt(ty))}, {fb}, {rewritten[fb]}, h{nt + k}) : ({motive(st)}); ")
                done[fb] = rewritten[fb]
            js = [f"j{j}" for j in range(nt)]
            fn = "".join(heads) + " => ".join(js) + f" => {call}, {', '.join(js)})" + ")" * len(heads)
            orig = ", ".join(fields)
            for j in range(nt):   # apply to h0, h1, .. one at a time
                rest = " -> ".join([f"{P}_c{i}({ALIAS}.HSt{{{orig}}})" for i in range(j + 1, nt)]
                                   + [f"{P}_I({ALIAS}.step({act}, {ALIAS}.HSt{{{orig}}}))"])
                fn = f"{P}_app({P}_c{j}({ALIAS}.HSt{{{orig}}}), {rest}, {fn}, h{j})"
            lines.append(f"      {fn}")
        lines.append("")
        # induction on Reach
        base = _tuple(["{==}"] * self.ncomp)
        lines += [f"def {P}_reach(-{v}: {ALIAS}.HSt, {self.rv}: {ALIAS}.Reach<{v}>) -> {P}_I({v}):",
                  f"  match {self.rv}:", f"    case {ALIAS}.R0{{{N['e']}}}:",
                  f"      (%Equal.sym({ALIAS}.HSt, {v}, {ALIAS}.s0(), {N['e']}) : {P}_I(_)",
                  f"      {base})",
                  f"    case {ALIAS}.RStep{{+{N['a']}, +{N['p']}, {N['r1']}, {N['e']}}}:",
                  f"      (%Equal.sym({ALIAS}.HSt, {v}, {ALIAS}.step({N['a']}, {N['p']}), {N['e']}) : {P}_I(_)",
                  f"      {P}_step({N['a']}, {N['p']}, {P}_reach({N['p']}, {N['r1']})))", ""]
        # the law: the claim's conjuncts out of the invariant
        if self.ncomp == 1:
            lines += [f"def Laws.{self.em.name}({v}, {self.rv}):", f"  {P}_reach({v}, {self.rv})"]
        else:   # a match cannot scrutinize a computed value: project in a def of its own
            tparts = [f"{P}_c{j}({v})" for j in range(nt)]
            tty = tparts[-1]
            for x in reversed(tparts[:-1]):
                tty = f"{x} & ({tty})" if "&" in tty else f"{x} & {tty}"
            hs = [f"t{j}" for j in range(self.ncomp)]
            lines.append(f"def {P}_out(-{v}: {ALIAS}.HSt, i: {P}_I({v})) -> {tty}:")
            cur = "i"
            for j in range(self.ncomp - 1):
                nxt = f"tr{j}" if j < self.ncomp - 2 else hs[-1]
                lines.append(f"  ({hs[j]}, {nxt}) = {cur}")
                cur = nxt
            lines += [f"  {_tuple(hs[:nt])}", "", f"def Laws.{self.em.name}({v}, {self.rv}):",
                      f"  {P}_out({v}, {P}_reach({v}, {self.rv}))"]
        text = "\n".join(_imports(self.imp) + lines) + "\n"
        off = len(_imports(self.imp))
        return text, {k + off: s for k, s in slot_at.items()}


def product(route: str, *args, **kw) -> str:
    """The product program's proof of a FACT law by one route (I26; holon.fact.product.product: the proof text, or
    holon.fact.product.NoProof naming why the route does not apply). Imported by name when called: no M1 or M2
    generator calls it, so holon.fact stays out of their generator closure (holon.records.generator_files)."""
    import importlib
    return importlib.import_module("holon.fact.product").product(route, *args, **kw)
