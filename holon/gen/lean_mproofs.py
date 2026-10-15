"""Lean proofs of machine laws (I43 rule L1): one generator per Bend proof class of the verdict re-checked.

  evaluate         an existential law at the record's witness, each conjunct by decide (a perturbed constant then
                   fails for a semantic reason: rule L9's canary keeps the proof)
  nat_split        a case split on the Nat binder: zero by decide; the successor by simp over the model's
                   definitions in the statement's cone (the closed prefix evaluates, the binder's comparisons become
                   linear facts), as Bend reduces 1n+p
  noninterference  a step lemma for the view (each decision reads only the fields its guards read, so both states
                   take the same decision; then each branch is rfl), then induction on the trace
  deadline         per permissionless action, the deadline observer kept: unchanged fields by the hypothesis, time
                   moving forward by omega, a cleared list entry by a list lemma proved once per file
  chain_revert     the require the deadline observer falsifies, located by its index in the decision chain (as Bend's
                   generator does), then a revert never succeeds
  counter_decide   a REFUTED law: the counter-law at the record's witness, each conjunct by decide, and the
                   refutation from it

The proofs name the model's declarations Model.<name>; helper theorems and definitions come before the law's
theorem, named hev_/hns_/hni_/hdl_/hcr_ (none is a frozen name). Imports no Bend-side module (rule L1). A form a
generator cannot prove raises Unsupported, never a silent fallback.
"""
from __future__ import annotations

from .lean_common import Theorem, Unsupported, ident
from .lean_machine import Ctx, cone, decl_names, model, paren, qualify
from .lean_mlaws import Render, strip, value

CLASSES = ("evaluate", "nat_split", "noninterference", "deadline", "chain_revert", "counter_decide")


def theorems(cls: str, law: dict, status: str, record: dict, ctx: Ctx,
             stmts: list[tuple[str, str]]) -> tuple[Theorem, ...]:
    """The theorems of a machine law file, after the marker: its frozen statements (stmts, from lean_mlaws) with
    their proofs by class cls, and any helper declarations before them. record: the law's record (its status,
    witness and attempts)."""
    if cls not in CLASSES:
        raise Unsupported(f"no machine proof class {cls}")
    if any(b["type"] == "Reach" or b["type"].startswith("Fn<") for b in law["statement"]["binders"]):
        raise Unsupported(f"{cls} over a statement with Reach or oracle binders (holon.gen.lean_sites)")
    want = "REFUTED" if cls == "counter_decide" else "PROVED"
    if status != want:
        raise Unsupported(f"class {cls} for a {status} law")
    return {"evaluate": _evaluate, "nat_split": _nat_split, "noninterference": _noninterference,
            "deadline": _deadline, "chain_revert": _chain_revert, "counter_decide": _counter}[cls](
        law, record, ctx, dict(stmts))


# ---------------------------------------------------------------------- shared pieces
class _Q:
    """The model's names, for writing terms after `end Model`."""

    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.decls = model(ctx, [], []).decls
        self.names = set(decl_names(self.decls)) | {"Reach"}

    def q(self, text: str) -> str:
        return qualify(text, self.names)

    def expr(self, e, env: dict) -> str:
        """A facts expression as a qualified Lean term (env as Ctx.expr's)."""
        return self.q(self.ctx.expr(e, env)[0])

    def unfold(self, roots: list[str]) -> list[str]:
        return ["Model." + n for n in cone(self.decls, roots)]


def _binders(law: dict, q: str) -> list[dict]:
    bs = law["statement"]["binders"]
    if any(b["q"] != q for b in bs):
        raise Unsupported(f"binders that are not all {q}")
    return bs


def _witness(law: dict, record: dict, ctx: Ctx) -> list[str]:
    """The record's witness, one Lean term per binder in binder order."""
    w = record.get("witness")
    bs = law["statement"]["binders"]
    if bs and not isinstance(w, dict):
        raise Unsupported("the record has no witness")
    out = []
    for b in bs:
        if b["name"] not in w:
            raise Unsupported(f"the witness has no value for {b['name']}")
        out.append(value(ctx, b["type"], w[b["name"]]))
    return out


def _props(law: dict) -> tuple[int, list[dict]]:
    """(number of premises, the claim's propositions)."""
    st = law["statement"]
    claim = st["claim"]
    return len(st.get("assume", [])), (list(claim["all"]) if set(claim) == {"all"} else [claim])


def _mentions(x, key: str) -> bool:
    if isinstance(x, dict):
        return key in x or any(_mentions(v, key) for v in x.values())
    if isinstance(x, list):
        return any(_mentions(v, key) for v in x)
    return False


# ---------------------------------------------------------------------- evaluate
def _evaluate(law: dict, record: dict, ctx: Ctx, stmts: dict) -> tuple[Theorem, ...]:
    lid = law["law_id"]
    bs = law["statement"]["binders"]
    if bs:
        _binders(law, "exists")
    nprem, props = _props(law)
    parts = [strip(w) for w in _witness(law, record, ctx)] + ["by decide"] * (nprem + len(props))
    proof = parts[0] if len(parts) == 1 else "⟨" + ", ".join(parts) + "⟩"
    return (Theorem(lid, stmts[lid], proof),)


# ---------------------------------------------------------------------- counter_decide (machine)
def _counter(law: dict, record: dict, ctx: Ctx, stmts: dict) -> tuple[Theorem, ...]:
    lid = law["law_id"]
    bs = _binders(law, "forall")
    nprem, props = _props(law)
    claim = law["statement"]["claim"]
    ws = [strip(w) for w in _witness(law, record, ctx)]
    parts = ws + ["by decide"] * (nprem + 1)
    counter = parts[0] if len(parts) == 1 else "⟨" + ", ".join(parts) + "⟩"
    xs = [f"hx{k}" for k in range(len(bs))]
    hs = [f"hp{k}" for k in range(nprem)]
    applied = "".join(["H"] + [f" {x}" for x in xs + hs])
    neq = set(claim) == {"neq"}
    if not xs and not hs:
        refuted = f"fun H => H {lid}_counter" if neq else f"fun H => {lid}_counter H"
    else:
        use = f"({applied}) hc" if neq else f"hc ({applied})"
        refuted = f"fun H => match {lid}_counter with\n  | ⟨{', '.join(xs + hs + ['hc'])}⟩ => {use}"
    return (Theorem(f"{lid}_counter", stmts[f"{lid}_counter"], counter),
            Theorem(f"{lid}_refuted", stmts[f"{lid}_refuted"], refuted))


# ---------------------------------------------------------------------- nat_split
def _nat_split(law: dict, record: dict, ctx: Ctx, stmts: dict) -> tuple[Theorem, ...]:
    lid = law["law_id"]
    bs = _binders(law, "forall")
    if [b["type"] for b in bs] != ["Nat"] or law["statement"].get("assume"):
        raise Unsupported("nat_split needs exactly one Nat binder and no premise")
    Q = _Q(ctx)
    roots = sorted({w[len("Model."):] for w in stmts[lid].replace("(", " ").replace(")", " ").split()
                    if w.startswith("Model.")})
    simps = ", ".join(["← Bool.not_eq_true", "Nat.blt_eq", "Nat.ble_eq", "Nat.beq_eq"] + Q.unfold(roots))
    proof = ("by\n  intro hn\n  cases hn with\n  | zero => decide\n  | succ hp =>\n"
             f"    simp (config := {{ decide := true }}) [{simps}]")
    return (Theorem(lid, stmts[lid], proof, option="set_option maxHeartbeats 8000000 in"),)


# ---------------------------------------------------------------------- noninterference
def _view_eq(t: dict) -> tuple[list[str], dict, dict] | None:
    """proj F (a) == proj F (b): (F, a, b)."""
    if set(t) != {"eq"}:
        return None
    a, b = t["eq"]
    if set(a) != {"proj", "of"} or set(b) != {"proj", "of"} or sorted(a["proj"]) != sorted(b["proj"]):
        return None
    return sorted(a["proj"]), a["of"], b["of"]


def _noninterference(law: dict, record: dict, ctx: Ctx, stmts: dict) -> tuple[Theorem, ...]:
    lid = law["law_id"]
    st = law["statement"]
    bs = _binders(law, "forall")
    if [b["type"] for b in bs] != ["Trace", "State", "State"] or len(st.get("assume", [])) != 1:
        raise Unsupported("noninterference needs binders (Trace, State, State) and one premise")
    tr, s1, s2 = (b["name"] for b in bs)
    pre, post = _view_eq(st["assume"][0]), _view_eq(st["claim"])
    if not pre or not post or pre[0] != post[0] or pre[1] != {"var": s1} or pre[2] != {"var": s2} or \
            post[1] != {"run": {"var": tr}, "from": {"var": s1}} or post[2] != {"run": {"var": tr}, "from": {"var": s2}}:
        raise Unsupported("noninterference needs proj(s1) == proj(s2) => proj(run(tr, s1)) == proj(run(tr, s2))")
    fields = pre[0]
    v = "__".join(ident("", f) for f in fields)
    kept = [n for n, _ in ctx.state if n not in fields]
    n = len(ctx.state)
    xs, ys = " ".join(f"hx{k}" for k in range(n)), " ".join(f"hy{k}" for k in range(n))
    acts = [ident("", a) for a in ctx.actions]
    unf = ", ".join(["Model.step"] + [f"Model.stp_{a}" for a in acts] + [f"Model.exe_{a}" for a in acts])
    rfls = ", ".join("rfl" for _ in kept)
    step = (f"theorem hni_{lid} (a : Model.Act) (s1 s2 : Model.St) (h : Model.view_{v} s1 = Model.view_{v} s2) : "
            f"Model.view_{v} (Model.step a s1) = Model.view_{v} (Model.step a s2) := by\n"
            f"  obtain ⟨{', '.join(xs.split())}⟩ := s1\n  obtain ⟨{', '.join(ys.split())}⟩ := s2\n"
            f"  simp only [Model.view_{v}, Model.V_{v}.mk.injEq] at h\n"
            + (f"  obtain ⟨{rfls}⟩ := h\n" if len(kept) > 1 else "  subst h\n")
            + f"  cases a <;> simp only [{unf}] <;> split <;> rfl")
    proof = ("by\n  intro htr\n  induction htr with\n  | nil => intro hs1 hs2 h; exact h\n"
             f"  | cons ha htr ih => intro hs1 hs2 h; exact ih _ _ (hni_{lid} ha hs1 hs2 h)")
    return (Theorem(lid, stmts[lid], proof, before=(step,)),)


# ---------------------------------------------------------------------- deadline and chain_revert
def _kappa(ctx: Ctx, name: str) -> dict | None:
    """The deadline observer: b && (x + get(nth(xs, i), f)) < t over state fields, nth a twin list accessor with a default element
    (kind nth_default); the pieces, or None."""
    o = ctx.observers.get(name)
    if not o:
        return None
    e = o["body"]
    try:
        op, b, lt = e
        assert op == "&&" and isinstance(b, str) and lt[0] == "<" and len(lt) == 3
        _, plus, t = lt
        assert plus[0] == "+" and isinstance(t, str) and len(plus) == 3
        _, x, get = plus
        assert isinstance(x, str) and get[0] == "get" and len(get) == 3
        _, call, fld = get
        assert call[0] == "call" and len(call) == 4 and isinstance(call[2], str) and isinstance(call[3], str)
        kind, dflt = ctx.builtin_kind(call[1])
        assert kind == "nth_default" and dflt
        for f in (b, x, t, call[2], call[3]):
            assert f in ctx.stypes
        return {"b": b, "x": x, "xs": call[2], "i": call[3], "f": fld, "t": t, "nth": call[1], "default": dflt,
                "deadline": plus}
    except (AssertionError, ValueError, TypeError, IndexError, KeyError):
        return None


def _guarded(law: dict, ctx: Ctx) -> tuple[str, str, str, str, dict] | None:
    """∀ s a, ob(s) == true -> P(a) == true -> claim: (s, a, the observer, P's fn name, claim)."""
    st = law["statement"]
    bs = st["binders"]
    if [(b["q"], b["type"]) for b in bs] != [("forall", "State"), ("forall", "Act")] or len(st.get("assume", [])) != 2:
        return None
    s, a = bs[0]["name"], bs[1]["name"]
    k, p = st["assume"]
    try:
        assert set(k) == {"eq"} and k["eq"][1] == {"bool": True} and set(k["eq"][0]) == {"obsv", "of"}
        assert k["eq"][0]["of"] == {"var": s}
        assert set(p) == {"eq"} and p["eq"][1] == {"bool": True} and set(p["eq"][0]) == {"fn", "args"}
        assert p["eq"][0]["args"] == [{"var": a}]
    except (AssertionError, KeyError, TypeError, IndexError):
        return None
    return s, a, k["eq"][0]["obsv"], p["eq"][0]["fn"], st["claim"]


def _cases(ctx: Ctx, bodies: dict[str, str]) -> str:
    """cases on the action binder, one alternative per constructor, its inputs named i_<input>."""
    out = []
    for a, act in ctx.actions.items():
        ins = " ".join(ident("i_", n) for n, _ in act["inputs"])
        out.append(f"  | {ident('a_', a)}{' ' + ins if ins else ''} =>\n" + bodies[a])
    return "\n".join(out)


def _deadline(law: dict, record: dict, ctx: Ctx, stmts: dict) -> tuple[Theorem, ...]:
    lid = law["law_id"]
    g = _guarded(law, ctx)
    if not g:
        raise Unsupported("deadline needs ∀ s a, ob(s) == true -> perm(a) == true -> ob(step(a, s)) == true")
    s, a, kname, pname, claim = g
    if pname != "perm" or claim != {"eq": [{"obsv": kname, "of": {"step": {"var": a}, "from": {"var": s}}},
                                           {"bool": True}]}:
        raise Unsupported("deadline's claim is not ob(step(a, s)) == true under perm(a)")
    k = _kappa(ctx, kname)
    if not k:
        raise Unsupported(f"observer {kname} is not b && x + get(nth(xs, i), f) < t")
    Q = _Q(ctx)
    rec = ctx.stypes[k["xs"]][len("List<"):-1] if ctx.stypes[k["xs"]].startswith("List<") else None
    if rec not in ctx.records:
        raise Unsupported(f"deadline: {k['xs']} is not a list of records")
    kfields = {k["b"], k["x"], k["xs"], k["i"], k["t"]}
    ob = "Model." + ident("ob_", kname)
    # the list lemma: clearing an entry never raises the field read at any index
    lenv = {"hcs": ("hcs", f"List<{rec}>"), "hi": ("hi", "Nat"), "hj": ("hj", "Nat")}
    dflt = ["call", k["default"]]
    sets = [n for n, b in ctx.builtins.items() if b.get("kind") == "set_default" and b.get("default") == k["default"]]
    after = lambda xs: Q.expr(["get", ["call", k["nth"], xs, "hj"], k["f"]], lenv)  # noqa: E731
    lemma_names = {}
    for sname in sets:
        try:
            set_term = ["call", sname, "hcs", "hi", dflt]
            lhs, rhs = after(set_term), after("hcs")
        except Unsupported:
            continue
        lemma_names[sname] = f"hdl_{ident('', sname)}_{lid}"
        helpers = [w for w in sorted(set((lhs + " " + rhs).replace("(", " ").replace(")", " ").split()))
                   if w.startswith("Model.") and "." not in w[len("Model."):]]
        unf = ", ".join(helpers)
        lemma = (f"theorem {lemma_names[sname]} (hcs : List Model.{ident('T_', rec)}) (hi hj : Nat) : "
                 f"{strip(lhs)} ≤ {strip(rhs)} := by\n"
                 "  induction hcs generalizing hi hj with\n"
                 "  | nil =>\n    induction hi generalizing hj with\n"
                 f"    | zero => cases hj <;> simp [{unf}]\n"
                 "    | succ hi ih => cases hj with\n"
                 f"      | zero => simp [{unf}]\n"
                 f"      | succ hj => simp only [{unf}]; exact ih hj\n"
                 "  | cons hh ht ih =>\n    cases hi with\n"
                 f"    | zero => cases hj <;> simp [{unf}]\n"
                 "    | succ hi => cases hj with\n"
                 f"      | zero => simp [{unf}]\n"
                 f"      | succ hj => simp only [{unf}]; exact ih hi hj")
        lemma_names[sname] = (lemma_names[sname], lemma)
    perm = set(ctx.perm_actions())
    senv = {n: (f"hs.{ident('f_', n)}", t) for n, t in ctx.state}
    kunf = f"{ob}, Bool.and_eq_true, Nat.blt_eq"
    bodies, before = {}, []
    for an, act in ctx.actions.items():
        if an not in perm:
            bodies[an] = "    simp [Model.fn_perm] at hp"
            continue
        info = ctx.action(an)
        A = ident("", an)
        head = f"    simp only [Model.step, Model.stp_{A}, Model.exe_{A}]\n    split\n    · exact hk\n"
        touched = {f: e for f, e in act["effects"].items() if f in kfields}
        env = dict(senv)
        env.update({n: (ident("i_", n), t) for n, t in info["inputs"]})
        if not touched:
            bodies[an] = head + "    · exact hk"
        elif set(touched) == {k["t"]} and isinstance(touched[k["t"]], list) and touched[k["t"]][0] == "+" and \
                touched[k["t"]][1] == k["t"] and not ctx.free(touched[k["t"]][2], set()) & set(info["carried"]):
            bodies[an] = head + f"    · simp only [{kunf}] at hk ⊢\n      exact ⟨hk.1, by omega⟩"
        elif set(touched) == {k["xs"]} and isinstance(touched[k["xs"]], list) and touched[k["xs"]][0] == "call" and \
                touched[k["xs"]][1] in lemma_names and touched[k["xs"]][2] == k["xs"] and \
                touched[k["xs"]][4] == dflt and not ctx.free(touched[k["xs"]][3], set()) & set(info["carried"]):
            lname, lemma = lemma_names[touched[k["xs"]][1]]
            if lemma not in before:
                before.append(lemma)
            ix = Q.expr(touched[k["xs"]][3], env)
            bodies[an] = head + (f"    · have hle := {lname} hs.{ident('f_', k['xs'])} {paren(ix)} "
                                 f"hs.{ident('f_', k['i'])}\n      simp only [{kunf}] at hk ⊢\n"
                                 "      exact ⟨hk.1, by omega⟩")
        else:
            raise Unsupported(f"deadline: action {an} changes {sorted(touched)} in a way the class does not cover")
    proof = "by\n  intro hs ha hk hp\n  cases ha with\n" + _cases(ctx, bodies)
    return (Theorem(lid, stmts[lid], proof, before=tuple(before)),)


def _inline(e, lets: dict):
    """Substitute let names by their expressions, recursively."""
    if isinstance(e, str):
        return _inline(lets[e], lets) if e in lets else e
    if isinstance(e, list) and e:
        if e[0] == "call":
            return ["call", e[1]] + [_inline(x, lets) for x in e[2:]]
        if e[0] == "get":
            return ["get", _inline(e[1], lets), e[2]]
        if e[0] in ("mk", "with", "list"):
            return e
        return [e[0]] + [_inline(x, lets) for x in e[1:]]
    return e


def _chain_revert(law: dict, record: dict, ctx: Ctx, stmts: dict) -> tuple[Theorem, ...]:
    lid = law["law_id"]
    g = _guarded(law, ctx)
    if not g:
        raise Unsupported("chain_revert needs ∀ s a, ob(s) == true -> is_X(a) == true -> claim")
    s, a, kname, pname, claim = g
    if claim != {"eq": [{"fn": "last_ok", "args": [{"step": {"var": a}, "from": {"var": s}}]}, {"bool": False}]}:
        raise Unsupported("chain_revert's claim is not last_ok(step(a, s)) == false")
    an = next((x for x in ctx.actions if f"is_{x}" == pname), None)
    k = _kappa(ctx, kname)
    if an is None or not k:
        raise Unsupported(f"chain_revert: {pname} names no action or {kname} has no deadline shape")
    act = ctx.actions[an]
    lets = {gd["let"]: gd["expr"] for gd in act["guards"] if "let" in gd}
    target = ["||", ["!", k["b"]], ["<=", k["t"], k["deadline"]]]
    site = next((i for i, gd in enumerate(act["guards"]) if "require" in gd and _inline(gd["require"], lets) == target),
                None)
    if site is None:
        raise Unsupported(f"chain_revert: no require of {an} is falsified by {kname}")
    Q = _Q(ctx)
    info = ctx.action(an)
    A = ident("", an)
    dc = f"Model.Dc_{A}"
    senv = {n: (f"hs.{ident('f_', n)}", t) for n, t in ctx.state}
    hb = f"hs.{ident('f_', k['b'])}"
    hj = strip(Q.expr(["<=", k["t"], k["deadline"]], senv))
    car = " ".join("_" for _ in info["carried"])
    is_rev = (f"def hcr_rev_{lid} : {dc} → Bool\n  | {dc}.rev _ => true\n  | {dc}.ok{' ' + car if car else ''} => false")
    cond = (f"theorem hcr_cond_{lid} (hc : Bool) (hx hy : {dc}) : hcr_rev_{lid} (bif hc then hx else hy) = "
            f"(bif hc then hcr_rev_{lid} hx else hcr_rev_{lid} hy) := by\n  cases hc <;> rfl")
    rr = f"theorem hcr_rr_{lid} (hc : Nat) : hcr_rev_{lid} ({dc}.rev hc) = true := rfl"
    gins = " ".join(f"({ident('i_', n)} : {Q.q(ctx.ty(t))})" for n, t in info["g_inputs"])
    dargs = " ".join([f"hs.{ident('f_', n)}" for n in info["reads"]] + [ident("i_", n) for n, _ in info["g_inputs"]])
    dcall = f"Model.dec_{A} {dargs}"
    dec = (f"theorem hcr_dec_{lid} (hs : Model.St){' ' + gins if gins else ''} (hk : Model.{ident('ob_', kname)} hs = "
           f"true) : hcr_rev_{lid} ({dcall}) = true := by\n"
           f"  simp only [Model.{ident('ob_', kname)}, Bool.and_eq_true, Nat.blt_eq] at hk\n"
           "  obtain ⟨hb, hlt⟩ := hk\n"
           f"  have hj : {hj} = false := by\n    rw [← Bool.not_eq_true, Nat.ble_eq]; omega\n"
           f"  simp only [Model.dec_{A}, hb, hj, Bool.not_true, Bool.false_or, Bool.not_false, Bool.cond_true, "
           f"hcr_cond_{lid}, hcr_rr_{lid}, Bool.cond_self]")
    eins = " ".join(f"({ident('i_', n)} : {Q.q(ctx.ty(t))})" for n, t in info["e_inputs"])
    eargs = "".join(f" {ident('i_', n)}" for n, _ in info["e_inputs"])
    exe = (f"theorem hcr_exe_{lid} (hd : {dc}) (hs : Model.St){' ' + eins if eins else ''} (h : hcr_rev_{lid} hd = "
           f"true) : Model.fn_last_ok (Model.exe_{A} hd hs{eargs}) = false := by\n"
           f"  cases hd with\n  | rev hc => rfl\n  | ok => simp [hcr_rev_{lid}] at h")
    bodies = {}
    for b in ctx.actions:
        if b == an:
            gargs = "".join(f" {ident('i_', n)}" for n, _ in info["g_inputs"])
            bodies[b] = f"    exact hcr_exe_{lid} _ hs{eargs} (hcr_dec_{lid} hs{gargs} hk)"
        else:
            bodies[b] = f"    simp [Model.fn_is_{A}] at hp"
    proof = "by\n  intro hs ha hk hp\n  cases ha with\n" + _cases(ctx, bodies)
    del site
    return (Theorem(lid, stmts[lid], proof, before=(is_rev, cond, rr, dec, exe)),)
