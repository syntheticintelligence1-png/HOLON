"""One Bend module per game (key I56: B1-B5), its LAWS.bend and its PROOF.bend.

A holding is a List<&2, Cp>, one component per asset; a Cp is (pos, neg, up, un, upp, unp): a concrete part and the
atom counts of G-P1. The module classifies holdings as G-P2 does, and computes every class's verdict:

  complete game (a control)  win_k / lose_k: fuelled depth-first search over every schedule of distinct actions of
                             class k inside the module (fuel = the number of actions + 1), so the universal claim needs
                             no list the generator supplies
  witness game (a target)    legal_k over the witness's steps and the classification of their flows: Rat or Unk

l_game_<g> states the verdict vector; l_strategy_<g>_<k> returns a rational class's strategy (B2). The econ modules
state N3's two claims over a run's flows and O35's for-all-k claim (proved by induction). Untrusted output: Bend's
check is the only verdict.
"""
from __future__ import annotations

import re

PRELUDE = '''import Base

type Cp is Data:
  Cp{pos: Nat, neg: Nat, up: Nat, un: Nat, upp: Nat, unp: Nat}

type Pay is Data:
  Nonneg{}
  Negative{}
  Incomparable{}
  Undetermined{}

type V is Data:
  Rat{}
  Irr{}
  IrrB{}
  Unk{}

def cadd(a: Cp, b: Cp) -> Cp:
  match a b:
    case Cp{p1, n1, u1, v1, w1, x1} Cp{p2, n2, u2, v2, w2, x2}:
      Cp{Nat.add(p1, p2), Nat.add(n1, n2), Nat.add(u1, u2), Nat.add(v1, v2), Nat.add(w1, w2), Nat.add(x1, x2)}

def hadd(xs: List<&2, Cp>, ys: List<&2, Cp>) -> List<&2, Cp>:
  match xs ys:
    case Nil{} _:
      ys
    case Con{x, xt} Nil{}:
      Con{x, xt}
    case Con{x, xt} Con{y, yt}:
      Con{cadd(x, y), hadd(xt, yt)}

def c_ge(c: Cp) -> Bool:
  match c:
    case Cp{+p, +n, u, +v, w, +x}:
      Bool.and(Nat.is_eq(Nat.add(v, x), 0n), Nat.is_le(n, p))

def c_le(c: Cp) -> Bool:
  match c:
    case Cp{+p, +n, +u, v, +w, x}:
      Bool.and(Nat.is_eq(Nat.add(u, w), 0n), Nat.is_le(p, n))

def c_lt(c: Cp) -> Bool:
  match c:
    case Cp{+p, +n, +u, v, +w, +x}:
      Bool.and(Bool.and(Nat.is_eq(Nat.add(u, w), 0n), Nat.is_le(p, n)), Bool.or(Nat.is_lt(p, n), Nat.is_gt(x, 0n)))

def c_gt(c: Cp) -> Bool:
  match c:
    case Cp{+p, +n, u, +v, +w, +x}:
      Bool.and(Bool.and(Nat.is_eq(Nat.add(v, x), 0n), Nat.is_le(n, p)), Bool.or(Nat.is_lt(n, p), Nat.is_gt(w, 0n)))

def all_ge(xs: List<&2, Cp>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{+x, t}:
      Bool.and(c_ge(x), all_ge(t))

def all_le(xs: List<&2, Cp>) -> Bool:
  match xs:
    case Nil{}:
      True{}
    case Con{+x, t}:
      Bool.and(c_le(x), all_le(t))

def any_lt(xs: List<&2, Cp>) -> Bool:
  match xs:
    case Nil{}:
      False{}
    case Con{+x, t}:
      Bool.or(c_lt(x), any_lt(t))

def any_gt(xs: List<&2, Cp>) -> Bool:
  match xs:
    case Nil{}:
      False{}
    case Con{+x, t}:
      Bool.or(c_gt(x), any_gt(t))

def pick(ge: Bool, le: Bool, lt: Bool, gt: Bool) -> Pay:
  match ge le lt gt:
    case True{} _ _ _:
      Nonneg{}
    case False{} True{} True{} _:
      Negative{}
    case False{} _ True{} True{}:
      Incomparable{}
    case _ _ _ _:
      Undetermined{}

def classify(+h: List<&2, Cp>) -> Pay:
  pick(all_ge(h), all_le(h), any_lt(h), any_gt(h))

def is_nonneg(p: Pay) -> Bool:
  match p:
    case Nonneg{}:
      True{}
    case _:
      False{}

def is_neg(p: Pay) -> Bool:
  match p:
    case Negative{}:
      True{}
    case _:
      False{}

def vpick(w: Bool, l: Bool) -> V:
  match w l:
    case True{} _:
      Rat{}
    case False{} True{}:
      Irr{}
    case False{} False{}:
      Unk{}

def vpick1(w: Bool) -> V:
  match w:
    case True{}:
      Rat{}
    case False{}:
      Unk{}
'''

VCODE = {"rational": "Rat{}", "irrational": "Irr{}", "irrational_bounded": "IrrB{}", "UNKNOWN": "Unk{}"}


def bend_name(s: str) -> str:
    n = re.sub(r"[^a-z0-9_]+", "_", s.lower()).strip("_")
    return n if n[:1].isalpha() else "g_" + n


NAT_MAX = 65535   # Bend's Nat is unary underneath: a larger concrete amount is refused, and its game is UNKNOWN


class Range(ValueError):
    pass


def nat(n: int) -> str:
    if n < 0:
        raise ValueError(f"a negative Nat literal {n}")
    if n > NAT_MAX:
        raise Range(f"a concrete amount {n} exceeds the module's Nat range ({NAT_MAX})")
    return f"{n}n"


def cp(t: tuple) -> str:
    return "Cp{" + ", ".join(nat(x) for x in t) + "}"


def cps(ts: list[tuple]) -> str:
    return "[" + ", ".join(cp(t) for t in ts) + "]" if ts else "Nil{}"


def zero_h(n: int) -> str:
    return cps([(0, 0, 0, 0, 0, 0)] * n)


# ------------------------------------------------------------------ a complete game (a control document)
def complete_module(doc: dict) -> tuple[str, dict]:
    """(game.bend text, info): info["actors"] in sorted order with their Bend index."""
    vars_ = sorted(doc["vars"])
    acts = doc["actions"]
    assets = list(doc["assets"])
    actors = sorted(a["id"] for a in doc["actors"])
    vi = {v: f"v{i}" for i, v in enumerate(vars_)}
    out = [PRELUDE]
    out.append("type St is Data:\n  St{" + ", ".join(f"{vi[v]}: Nat" for v in vars_) + "}\n")
    out.append("type Act is Data:\n" + "".join(f"  A{i}{{}}\n" for i in range(len(acts))))
    pat_all = "St{" + ", ".join(f"+{vi[v]}" for v in vars_) + "}"

    def cond(c):
        op, var, k = c
        fn = {"ge": "Nat.is_ge", "eq": "Nat.is_eq", "lt": "Nat.is_lt"}[op]
        return f"{fn}({vi[var]}, {nat(k)})"

    def conj(cs):
        e = "True{}"
        for c in cs:
            e = f"Bool.and({e}, {cond(c)})"
        return e
    lines = ["def guard(a: Act, s: St) -> Bool:", "  match a s:"]
    for i, a in enumerate(acts):
        lines += [f"    case A{i}{{}} {pat_all}:", f"      {conj(a['guard'])}"]
    out.append("\n".join(lines) + "\n")
    lines = ["def eff(a: Act, s: St) -> St:", "  match a s:"]
    for i, a in enumerate(acts):
        new = {v: vi[v] for v in vars_}
        for op, var, k in a["effect"]:
            new[var] = f"Nat.add({new[var]}, {nat(k)})" if op == "add" else nat(k)
            if op not in ("add", "set"):
                raise ValueError(op)
        lines += [f"    case A{i}{{}} {pat_all}:", "      St{" + ", ".join(new[v] for v in vars_) + "}"]
    out.append("\n".join(lines) + "\n")
    out.append("def bad(s: St) -> Bool:\n  match s:\n    case " + pat_all + ":\n      " + conj(doc["bad"]) + "\n")
    lines = ["def act_eq(a: Act, b: Act) -> Bool:", "  match a b:"]
    for i in range(len(acts)):
        lines += [f"    case A{i}{{}} A{i}{{}}:", "      True{}"]
    lines += ["    case _ _:", "      False{}"]
    out.append("\n".join(lines) + "\n")
    out.append('''def mem(+a: Act, xs: List<&2, Act>) -> Bool:
  match xs:
    case Nil{}:
      False{}
    case Con{h, t}:
      Bool.or(act_eq(a, h), mem(a, t))
''')
    out.append("def all_acts() -> List<&2, Act>:\n  [" + ", ".join(f"A{i}{{}}" for i in range(len(acts))) + "]\n")
    out.append("def s0() -> St:\n  St{" + ", ".join(nat(doc["vars"][v]) for v in vars_) + "}\n")
    out.append(f"def h0() -> List<&2, Cp>:\n  {zero_h(len(assets))}\n")
    fuel = nat(len(acts) + 1)
    for k, x in enumerate(actors):
        lines = [f"def by_{k}(a: Act) -> Bool:", "  match a:"]
        for i, a in enumerate(acts):
            lines += [f"    case A{i}{{}}:", f"      {'True{}' if x in a['by'] else 'False{}'}"]
        out.append("\n".join(lines) + "\n")
        lines = [f"def fl_{k}(a: Act, h: List<&2, Cp>) -> List<&2, Cp>:", "  match a:"]
        for i, a in enumerate(acts):
            d = [0] * len(assets)
            for who, m in a["flows"].items():
                if (x if who == "caller" else who) == x:
                    for s, q in m.items():
                        d[assets.index(s)] += q
            lines += [f"    case A{i}{{}}:", f"      hadd(h, {cps([(max(q, 0), max(-q, 0), 0, 0, 0, 0) for q in d])})"]
        out.append("\n".join(lines) + "\n")
        out.append(f'''# every legal schedule of distinct actions of class {k} that triggers ends negative (or none triggers)
def lose_{k}(fuel: Nat, xs: List<&2, Act>, +s: St, +h: List<&2, Cp>, +used: List<&2, Act>, +trig: Bool) -> Bool:
  match fuel:
    case 0n:
      True{{}}
    case 1n+(+p):
      match xs:
        case Nil{{}}:
          True{{}}
        case Con{{+a, t}}:
          +s2 = eff(a, s)
          +h2 = fl_{k}(a, h)
          +t2 = Bool.or(trig, bad(s2))
          +ok = Bool.and(Bool.and(by_{k}(a), guard(a, s)), Bool.not(mem(a, used)))
          +here = Bool.or(Bool.not(t2), is_neg(classify(h2)))
          Bool.and(Bool.or(Bool.not(ok), Bool.and(here, lose_{k}(p, all_acts(), s2, h2, Con{{a, used}}, t2))), lose_{k}(1n+p, t, s, h, used, trig))

# some legal schedule of distinct actions of class {k} triggers and ends nonneg
def win_{k}(fuel: Nat, xs: List<&2, Act>, +s: St, +h: List<&2, Cp>, +used: List<&2, Act>, +trig: Bool) -> Bool:
  match fuel:
    case 0n:
      False{{}}
    case 1n+(+p):
      match xs:
        case Nil{{}}:
          False{{}}
        case Con{{+a, t}}:
          +s2 = eff(a, s)
          +h2 = fl_{k}(a, h)
          +t2 = Bool.or(trig, bad(s2))
          +ok = Bool.and(Bool.and(by_{k}(a), guard(a, s)), Bool.not(mem(a, used)))
          +here = Bool.and(t2, is_nonneg(classify(h2)))
          Bool.or(Bool.and(ok, Bool.or(here, win_{k}(p, all_acts(), s2, h2, Con{{a, used}}, t2))), win_{k}(1n+p, t, s, h, used, trig))

# a strategy of class {k} (a list of its actions): legal, distinct, triggers, nonneg at its end
def wins_{k}(xs: List<&2, Act>, +s: St, +h: List<&2, Cp>, +used: List<&2, Act>, +trig: Bool, +n: Nat) -> Bool:
  match xs:
    case Nil{{}}:
      Bool.and(Bool.and(trig, Nat.is_gt(n, 0n)), is_nonneg(classify(h)))
    case Con{{+a, t}}:
      +s2 = eff(a, s)
      Bool.and(Bool.and(Bool.and(by_{k}(a), guard(a, s)), Bool.not(mem(a, used))), wins_{k}(t, s2, fl_{k}(a, h), Con{{a, used}}, Bool.or(trig, bad(s2)), Nat.add(n, 1n)))

def verdict_{k}() -> V:
  vpick(win_{k}({fuel}, all_acts(), s0(), h0(), Nil{{}}, False{{}}), lose_{k}({fuel}, all_acts(), s0(), h0(), Nil{{}}, False{{}}))
''')
    out.append("def verdicts() -> List<&2, V>:\n  [" + ", ".join(f"verdict_{k}()" for k in range(len(actors))) + "]\n")
    return "\n".join(out), {"actors": actors, "act_index": {a["id"]: i for i, a in enumerate(acts)}}


def complete_laws(gid: str, verdicts: list[str], strategies: dict) -> tuple[str, str, dict]:
    """(LAWS.bend, PROOF.bend, laws.json) for a complete game: the verdict law and one strategy law per rational class
    (strategies: {k: [action index]})."""
    g = bend_name(gid)
    vec = "[" + ", ".join("G." + VCODE[v] for v in verdicts) + "]"
    laws = [f"law l_game_{g}:\n  {{G.verdicts() == {vec} : List<&2, G.V>}}\n"]
    proofs = [f"def Laws.l_game_{g}():\n  {{==}}\n"]
    names = {f"l_game_{g}": {"kind": "game", "claim": f"{{G.verdicts() == {vec} : List<&2, G.V>}}"}}
    for k in sorted(strategies):
        n = f"l_strategy_{g}_{k}"
        claim = f"{{G.wins_{k}(xs, G.s0(), G.h0(), Nil{{}}, False{{}}, 0n) == True{{}} : Bool}}"
        laws.append(f"law {n}:\n  exs xs: List<&2, G.Act>\n  {claim}\n")
        lst = "[" + ", ".join(f"G.A{i}{{}}" for i in strategies[k]) + "]"
        proofs.append(f"def Laws.{n}():\n  ({lst}, {{==}})\n")
        names[n] = {"kind": "strategy", "claim": claim}
    return _files(laws, proofs, names)


def _files(laws: list[str], proofs: list[str], names: dict) -> tuple[str, str, dict]:
    head = "# GENERATED by holon.games.bendgen; do not edit.\nimport Base\nimport ./game.bend as G\n\n"
    lt = head + "\n".join(laws)
    pt = ("# GENERATED by holon.games.bendgen; untrusted, accepted only if Bend checks it.\nimport Base\n"
          "import ./game.bend as G\nimport ./LAWS.bend as Laws\n\n" + "\n".join(proofs))
    return lt, pt, names


# ------------------------------------------------------------------ a witness game (a target finding)
def witness_module(groups: list[str | None], classes: list[str], deltas: list[list[tuple]], n_assets: int) -> str:
    """deltas: per step, one Cp tuple per asset (the flows to the schedule's callers)."""
    gl = sorted({g for g in groups if g is not None} | set(classes))
    gi = {g: i for i, g in enumerate(gl)}
    out = [PRELUDE]
    out.append("type Grp is Data:\n" + "".join(f"  Gr{i}{{}}\n" for i in range(len(gl))) + "  GrNone{}\n")
    out.append("type Step is Data:\n  Step{g: Grp, d: List<&2, Cp>}\n")
    lines = ["def grp_eq(a: Grp, b: Grp) -> Bool:", "  match a b:"]
    for i in range(len(gl)):
        lines += [f"    case Gr{i}{{}} Gr{i}{{}}:", "      True{}"]
    lines += ["    case GrNone{} GrNone{}:", "      True{}", "    case _ _:", "      False{}"]
    out.append("\n".join(lines) + "\n")
    out.append('''def cp_eq(a: Cp, b: Cp) -> Bool:
  match a b:
    case Cp{p1, n1, u1, v1, w1, x1} Cp{p2, n2, u2, v2, w2, x2}:
      Bool.and(Bool.and(Bool.and(Nat.is_eq(p1, p2), Nat.is_eq(n1, n2)), Bool.and(Nat.is_eq(u1, u2), Nat.is_eq(v1, v2))), Bool.and(Nat.is_eq(w1, w2), Nat.is_eq(x1, x2)))

def cps_eq(xs: List<&2, Cp>, ys: List<&2, Cp>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Con{x, xt} Con{y, yt}:
      Bool.and(cp_eq(x, y), cps_eq(xt, yt))
    case _ _:
      False{}

def step_eq(a: Step, b: Step) -> Bool:
  match a b:
    case Step{g1, d1} Step{g2, d2}:
      Bool.and(grp_eq(g1, g2), cps_eq(d1, d2))

def steps_eq(xs: List<&2, Step>, ys: List<&2, Step>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Con{x, xt} Con{y, yt}:
      Bool.and(step_eq(x, y), steps_eq(xt, yt))
    case _ _:
      False{}

def pay(xs: List<&2, Step>, h: List<&2, Cp>) -> List<&2, Cp>:
  match xs:
    case Nil{}:
      h
    case Con{x, t}:
      match x:
        case Step{g, d}:
          pay(t, hadd(h, d))
''')
    st = ", ".join("Step{" + (f"Gr{gi[g]}{{}}" if g is not None else "GrNone{}") + ", " + cps(d) + "}"
                   for g, d in zip(groups, deltas))
    out.append(f"def witness() -> List<&2, Step>:\n  [{st}]\n")
    out.append(f"def h0() -> List<&2, Cp>:\n  {zero_h(n_assets)}\n")
    anyone = gi.get("anyone")
    for k, x in enumerate(classes):
        lines = [f"def may_{k}(g: Grp) -> Bool:", "  match g:"]
        for gname, i in sorted(gi.items(), key=lambda kv: kv[1]):
            lines += [f"    case Gr{i}{{}}:", f"      {'True{}' if gname in (x, 'anyone') else 'False{}'}"]
        lines += ["    case GrNone{}:", "      False{}"]
        out.append("\n".join(lines) + "\n")
        out.append(f'''def legal_{k}(xs: List<&2, Step>) -> Bool:
  match xs:
    case Nil{{}}:
      True{{}}
    case Con{{x, t}}:
      match x:
        case Step{{g, d}}:
          Bool.and(may_{k}(g), legal_{k}(t))

def wins_{k}(+xs: List<&2, Step>) -> Bool:
  Bool.and(steps_eq(xs, witness()), Bool.and(legal_{k}(xs), is_nonneg(classify(pay(xs, h0())))))

def verdict_{k}() -> V:
  vpick1(wins_{k}(witness()))
''')
    del anyone
    out.append("def verdicts() -> List<&2, V>:\n  [" + ", ".join(f"verdict_{k}()" for k in range(len(classes))) + "]\n")
    return "\n".join(out)


def witness_laws(gid: str, verdicts: list[str], rational: list[int]) -> tuple[str, str, dict]:
    g = bend_name(gid)
    vec = "[" + ", ".join("G." + VCODE[v] for v in verdicts) + "]"
    laws = [f"law l_game_{g}:\n  {{G.verdicts() == {vec} : List<&2, G.V>}}\n"]
    proofs = [f"def Laws.l_game_{g}():\n  {{==}}\n"]
    names = {f"l_game_{g}": {"kind": "game", "claim": f"{{G.verdicts() == {vec} : List<&2, G.V>}}"}}
    for k in rational:
        n = f"l_strategy_{g}_{k}"
        claim = f"{{G.wins_{k}(xs) == True{{}} : Bool}}"
        laws.append(f"law {n}:\n  exs xs: List<&2, G.Step>\n  {claim}\n")
        proofs.append(f"def Laws.{n}():\n  (G.witness(), {{==}})\n")
        names[n] = {"kind": "strategy", "claim": claim}
    return _files(laws, proofs, names)


# ------------------------------------------------------------------ econ modules
def run_module(runs: dict[str, list[list[tuple]]], n_assets: dict[str, int]) -> str:
    """One def per named run: its per-step deltas (one Cp per asset), folded by sum_<name>."""
    out = [PRELUDE]
    out.append('''def hsum(xs: List<&2, List<&2, Cp>>, h: List<&2, Cp>) -> List<&2, Cp>:
  match xs:
    case Nil{}:
      h
    case Con{x, t}:
      hsum(t, hadd(h, x))
''')
    for name in sorted(runs):
        rows = runs[name]
        body = "[" + ", ".join(cps(r) for r in rows) + "]" if rows else "Nil{}"
        out.append(f"def run_{name}() -> List<&2, List<&2, Cp>>:\n  {body}\n")
        out.append(f"def pay_{name}() -> Pay:\n  classify(hsum(run_{name}(), {zero_h(n_assets[name])}))\n")
    return "\n".join(out)


def n3_module(runs: dict, n_assets: dict, adversaries: list[str]) -> str:
    t = run_module(runs, n_assets)
    conj = "True{}"
    for a in adversaries:
        conj = f"Bool.and({conj}, is_nonneg(pay_{a}()))"
    if not adversaries:
        conj = "False{}"
    t += ("\ndef n3_recommit() -> Bool:\n  Bool.and(is_neg(pay_full()), is_nonneg(pay_refuse()))\n"
          f"\ndef n3_continuation() -> Bool:\n  {conj}\n")
    return t


def bool_law(name: str, fn: str, holds: bool) -> tuple[str, str, dict]:
    """A law that a Bool def of the module is True (PROVED), or its counter-law that it is False (REFUTED)."""
    n = name if holds else "cl_" + name
    claim = f"{{G.{fn}() == {'True' if holds else 'False'}{{}} : Bool}}"
    return _files([f"law {n}:\n  {claim}\n"], [f"def Laws.{n}():\n  {{==}}\n"], {n: {"kind": "econ", "claim": claim}})


def o35_module(n_assets: int) -> str:
    """The writer's step at msg.value mv pays mv in each asset its entry's VM1 flow moves (one component per asset);
    pay(k, mv) is the sum of k steps."""
    comps = ", ".join("Cp{0n, mv, 0n, 0n, 0n, 0n}" for _ in range(n_assets))
    step = f"[{comps}]" if n_assets else "Nil{}"
    out = [PRELUDE]
    out.append(f"def step(+mv: Nat) -> List<&2, Cp>:\n  {step}\n")
    out.append(f"def zero() -> List<&2, Cp>:\n  {zero_h(n_assets)}\n")
    out.append('''def pay(k: Nat, +mv: Nat) -> List<&2, Cp>:
  match k:
    case 0n:
      zero()
    case 1n+p:
      hadd(step(mv), pay(p, mv))
''')
    return "\n".join(out)


def o35_laws(name: str) -> tuple[str, str, dict]:
    claim = "{G.zero() == G.pay(k, 0n) : List<&2, G.Cp>}"
    law = f"law {name}:\n  for k: Nat\n  {claim}\n"
    proof = (f"def Laws.{name}(k):\n  match k:\n    case 0n:\n      {{==}}\n    case 1n+p:\n"
             f"      %Laws.{name}(p) : {{G.zero() == G.hadd(G.step(0n), _) : List<&2, G.Cp>}}\n      {{==}}\n")
    return _files([law], [proof], {name: {"kind": "econ", "claim": claim}})
