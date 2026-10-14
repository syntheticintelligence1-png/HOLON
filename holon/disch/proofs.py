"""The proof generators of the DISCH laws (BUILD_PLAN I31; the contract is the docstring of tests_m3/test_disch.py,
"Deciding"): one class per route, generic in the model.

  frame         an action of a closure that writes no slot B reads: every store of its program is at a literal slot
                other than B's slots, so the word at each of B's slots after it is the word before (core lemma
                st_frame), on every path of the program, and B (stated over those words, blkv_<tag>) is kept
  chain_revert  an action whose decision chain reaches a check B makes 0, or reverts earlier: on every path of its
                program before that check either an earlier check fails (the step reverts with that check's code) or
                the check is reached, where its condition and B are contradictory (a boolean lemma over their shared
                atoms, by cases); a reverting step's post-state is its pre-state
  transport     an action that writes a slot B reads with a value B's sign keeps: not built (no law of I31's documents
                reaches it with every other action of its closure proved; refused with that reason)
  time          B at t and t <= time(e) give B at time(e): immediate for a B that reads no clock; a B that reads the
                clock is refused (named)

The proofs mirror the typed model's statement chains (holon.disch.mirror): a lemma per statement of an action, over its
context record with the fields that change as variables, and a case lemma per condition the program branches on. Every
lemma holds for every state: no reachability is assumed (the Reach premise is not used). The core lemmas
(holon.disch.lemmas.LIBRARY) are emitted into each proof file and checked with it.

A law whose every action of its set has a route is written as gen/<M>/proofs/<id>/PROOF.bend; otherwise NoProof names
the first action without one and why. Nothing here names a target.
"""
from __future__ import annotations

import itertools
import re

from ..machine_bend import bname
from ..sorts.proofs3 import PHEADER
from .lemmas import LIBRARY
from .mirror import Branch, Final, Mirror, NoMirror, Next, as_call, split_top


class NoProof(ValueError):
    """The route does not apply (named)."""


_CONN = {"Bool.and": 2, "Bool.or": 2, "Bool.not": 1}


# ------------------------------------------------------------------------------------------------ boolean skeletons
def skeleton(code: str, atoms: list) -> str:
    """code as a term over v<i> (its atoms, collected in order): Bool.and/or/not and the literals kept."""
    code = code.strip()
    if code in ("True{}", "False{}"):
        return code
    c = as_call(code)
    if c and c[2] == "(" and c[0] in _CONN and len(c[1]) == _CONN[c[0]]:
        return f"{c[0]}(" + ", ".join(skeleton(x, atoms) for x in c[1]) + ")"
    if code not in atoms:
        atoms.append(code)
    return f"v{atoms.index(code)}"


def _bev(sk: str, val: dict) -> bool:
    sk = sk.strip()
    if sk == "True{}":
        return True
    if sk == "False{}":
        return False
    m = re.fullmatch(r"v(\d+)", sk)
    if m:
        return val[int(m.group(1))]
    c = as_call(sk)
    xs = [_bev(x, val) for x in c[1]]
    return {"Bool.and": lambda: xs[0] and xs[1], "Bool.or": lambda: xs[0] or xs[1], "Bool.not": lambda: not xs[0]}[c[0]]()


def contradicts(b_code: str, c_code: str) -> tuple | None:
    """(atoms, B's skeleton, c's skeleton) when B and c are never true together (by cases on their shared atoms),
    else None."""
    atoms: list = []
    sb = skeleton(b_code, atoms)
    sc = skeleton(c_code, atoms)
    if len(atoms) > 10:
        return None
    for vals in itertools.product([True, False], repeat=len(atoms)):
        val = dict(enumerate(vals))
        if _bev(sb, val) and _bev(sc, val):
            return None
    return atoms, sb, sc


def nb_lemma(name: str, atoms: list, sb: str, sc: str) -> str:
    """def name(v0.., hB: {B == True}, hc: {c == True}) -> Empty, by cases on the atoms."""
    vs = [f"v{i}" for i in range(len(atoms))]
    head = (f"def {name}(" + "".join(f"{v}: Bool, " for v in vs) + f"hB: {{{sb} == True{{}} : Bool}}, "
            f"hc: {{{sc} == True{{}} : Bool}}) -> Empty:\n")
    if not vs:
        return head + "  false_ne_true(hB)\n"
    lines = [head, f"  match {' '.join(vs)}:\n"]
    for vals in itertools.product([True, False], repeat=len(vs)):
        val = dict(enumerate(vals))
        pat = " ".join("True{}" if x else "False{}" for x in vals)
        which = "hB" if not _bev(sb, val) else "hc"
        lines.append(f"    case {pat}:\n      false_ne_true({which})\n")
    return "".join(lines)


# ------------------------------------------------------------------------------------------------ words
def literal_word(t: str) -> int | None:
    """The value of a literal word term (M.W{l0, .., l7}, M.w0(), M.w_add of literals), else None."""
    t = t.strip()
    if t in ("M.w0()",):
        return 0
    c = as_call(t)
    if not c:
        return None
    if c[0] == "M.W" and c[2] == "{" and len(c[1]) == 8 and all(re.fullmatch(r"\d+", x) for x in c[1]):
        return sum(int(x) << (32 * i) for i, x in enumerate(c[1]))
    if c[0] == "M.w_add" and len(c[1]) == 2:
        a, b = literal_word(c[1][0]), literal_word(c[1][1])
        if a is not None and b is not None:
            return (a + b) % (1 << 256)
    return None


def stores(term: str, base: str) -> list | None:
    """[(key, value)..] when term is sstore(..sstore(base, k1, v1).., kn, vn) (innermost first), else None."""
    out = []
    t = term.strip()
    while t != base:
        c = as_call(t)
        if not c or c[0] != "M.sstore" or len(c[1]) != 3:
            return None
        out.append((c[1][1], c[1][2]))
        t = c[1][0].strip()
    return list(reversed(out))


# ------------------------------------------------------------------------------------------------ the generator
class Gen:
    """The proof context of one model: its text, its DISCH section (holon.disch.section.Section, compiled), the
    analysis and the hash tables."""

    def __init__(self, model_text: str, sec, an: dict):
        self.text = model_text
        self.sec = sec
        self.an = an
        self.names = sec.names
        self.tabs = sec.tabs
        self.tparams = "".join(f", +{n}: List<&2, M.HKB>" for n in self.tabs)
        self.targs = "".join(f", {n}" for n in self.tabs)
        m = re.search(r"(?m)^type GSt is Data:\n  GSt\{(.*)\}$", model_text)
        if not m:
            raise NoProof("the typed model has no augmented state GSt")
        self.gst = [p.split(":")[0].strip() for p in split_top(m.group(1))]
        self.gst_types = [p.split(":", 1)[1].strip() for p in split_top(m.group(1))]
        if self.gst[0] != "st":
            raise NoProof("GSt's first field is not the store")
        self.mirrors: dict = {}

    def mirror(self, ab: str) -> Mirror:
        if ab not in self.mirrors:
            self.mirrors[ab] = Mirror(self.text, ab, self.names)
        return self.mirrors[ab]

    def mtype(self, ty: str) -> str:
        """A model type as a proof file names it (M.-qualified)."""
        return re.sub(r"(?<![\w.])([A-Z]\w*)", lambda m: "M." + m.group(1) if m.group(1) in self.names else m.group(1),
                      ty)

    def record_types(self, ab: str) -> list:
        m = re.search(rf"(?m)^type X_{ab} is Data:\n  X_{ab}\{{(.*)\}}$", self.text)
        return [self.mtype(p.split(":", 1)[1].strip()) for p in split_top(m.group(1))]

    def g_term(self) -> str:
        return "M.GSt{" + ", ".join(["st"] + [f"g_{f}" for f in self.gst[1:]]) + "}"

    def g_params(self) -> str:
        return "".join(f", +g_{f}: {self.mtype(t)}" for f, t in zip(self.gst[1:], self.gst_types[1:]))

    def g_args(self) -> str:
        return "".join(f", g_{f}" for f in self.gst[1:])


FIXED = ("st", "ar", "en", "kh", "sh")


class ActionProof:
    """The lemmas of one route for one action (a revert route's goal: its code is not 0; a frame route's: B after the
    step), within one law's proof file."""

    def __init__(self, g: Gen, tag: str, action: str, route: str, prefix: str):
        self.g = g
        self.tag = tag
        self.action = action
        self.ab = bname(action)
        self.route = route
        self.p = prefix                     # lemma name prefix (unique in the file)
        self.mi = g.mirror(self.ab)
        self.fields = self.mi.field_names
        self.types = g.record_types(self.ab)
        self.fixed = {"st": "st", "ar": "ar", "en": "e"} | {n: n for n in g.tabs}
        self.var_fields = [f for f in self.fields if f not in self.fixed]
        self.defs: list = []
        self.done: dict = {}
        self.nbs: dict = {}
        self.nb_count = 0
        self.br_count = 0
        blk = g.sec.blk[tag]
        self.b_code = blk["code"]
        self.keys = blk["keys"]
        if blk["time"]:
            raise NoProof("B reads the clock: time monotonicity over the typed model's words is not built")
        if route == "frame" and blk["v"] is None:
            raise NoProof("B reads a slot that is not a literal (a mapping or array slot): no frame by slots")

    # ------------------------------------------------------------------ text pieces
    def fixed_params(self) -> str:
        out = f"+st: M.HSt, +ar: M.AR_{self.ab}, +e: M.HEnv{self.g.tparams}, +t: M.W"
        if self.route == "frame":
            out += self.g.g_params()
        return out

    def fixed_args(self) -> str:
        out = f"st, ar, e{self.g.targs}, t"
        if self.route == "frame":
            out += self.g.g_args()
        return out

    def hyp_params(self) -> str:
        out = f", +hb: {{D.blk_{self.tag}(st, t{self.g.targs}) == True{{}} : Bool}}"
        if self.route == "frame":
            for j, k in enumerate(self.keys):
                out += f", +inv{j}: {{M.sload(v_ov, {k}) == M.sload(st, {k}) : M.W}}"
        return out

    def var_params(self) -> str:
        return "".join(f", +v_{f}: {self.types[self.fields.index(f)]}" for f in self.var_fields)

    def record(self, values: dict) -> str:
        return f"M.X_{self.ab}{{" + ", ".join(values[f] for f in self.fields) + "}"

    def var_record(self) -> str:
        return self.record({f: (self.fixed[f] if f in self.fixed else f"v_{f}") for f in self.fields})

    def goal(self, x: str) -> str:
        if self.route == "revert":
            return f"{{M.u_nz(M.gx_{self.ab}_cd({x})) == True{{}} : Bool}}"
        return (f"{{D.blk_{self.tag}(M.gh_get_st(M.gh_go_{self.ab}({x}, {self.g.g_term()})), D.d_time(e)"
                f"{self.g.targs}) == True{{}} : Bool}}")

    # ------------------------------------------------------------------ statements
    def stmt(self, i: int) -> str:
        """The lemma of statement i (generated once); returns its name."""
        name = f"{self.p}_s{i}"
        if i in self.done:
            return name
        self.done[i] = name
        node = self.mi.step(i, [self.fixed[f] if f in self.fixed else f"v_{f}" for f in self.fields])
        body = self.emit(node, {f: f"v_{f}" for f in self.var_fields}, invs=[f"inv{j}" for j in range(len(self.keys))])
        self.defs.append(f"def {name}({self.fixed_params()}{self.var_params()}{self.hyp_params()}) -> "
                         f"{self.goal(f'M.s_{self.ab}_{i}({self.var_record()})')}:\n  {body}\n")
        return name

    def call(self, name: str, vals: dict, invs: list) -> str:
        args = self.fixed_args() + "".join(f", {vals[f]}" for f in self.var_fields) + ", hb"
        if self.route == "frame":
            args += "".join(f", {x}" for x in invs)
        return f"{name}({args})"

    def check_fixed(self, fields: list) -> dict:
        vals = dict(zip(self.fields, fields))
        for f, want in self.fixed.items():
            if f in vals and vals[f].strip() != want:
                raise NoProof(f"{self.action}: the program changes its context's {f}")
        return {f: vals[f] for f in self.var_fields}

    def emit(self, node, cur: dict, invs: list) -> str:
        """The proof term of the goal at node (cur: the current variables of the varying fields)."""
        if isinstance(node, Next):
            vals = self.check_fixed(node.fields)
            new_invs = self.frame_invs(cur["ov"], vals["ov"], invs) if self.route == "frame" else invs
            return self.call(self.stmt(node.j), vals, new_invs)
        if isinstance(node, Final):
            vals = self.check_fixed(node.fields)
            cd = vals["cd"].strip()
            if re.fullmatch(r"\d+", cd) and int(cd) != 0:
                return "{==}" if self.route == "revert" else "hb"
            if self.route == "revert":
                raise NoProof(f"{self.action}: a path of its program ends without reverting before the check B "
                              "makes 0")
            new_invs = self.frame_invs(cur["ov"], vals["ov"], invs)
            return self.end(vals, new_invs)
        if isinstance(node, Branch):
            return self.branch(node, cur, invs)
        raise NoProof(f"{self.action}: an evaluation result the mirror cannot state ({type(node).__name__})")

    def branch(self, br: Branch, cur: dict, invs: list) -> str:
        self.br_count += 1
        name = f"{self.p}_b{self.br_count}"
        fn = br.fn
        args = ", ".join(br.args)
        then_term = None
        if self.route == "revert" or self.route == "frame":
            target = self.contradiction(br)
            if target is not None:
                nb, atoms = target
                goal_t = self.goal(f"{fn}(True{{}}, {args})")
                then_term = f"efq({goal_t}, {nb}({''.join(a + ', ' for a in atoms)}hb, ec))"
        if then_term is None:
            then_term = self.emit(br.then, cur, invs)
        else_term = self.emit(br.other, cur, invs)
        inv_params = ""
        if self.route == "frame":
            inv_params = "".join(f", +{x}: {{M.sload({cur['ov']}, {k}) == M.sload(st, {k}) : M.W}}"
                                 for x, k in zip(invs, self.keys))
        vp = "".join(f", +v_{f}: {self.types[self.fields.index(f)]}" for f in self.var_fields)
        self.defs.append(
            f"def {name}(c: Bool, {self.fixed_params()}{vp}, +hb: {{D.blk_{self.tag}(st, t{self.g.targs}) == True{{}} : "
            f"Bool}}{inv_params}, ec: {{{br.cond} == c : Bool}}) -> {self.goal(f'{fn}(c, {args})')}:\n"
            f"  match c:\n    case True{{}}:\n      {then_term}\n    case False{{}}:\n      {else_term}\n")
        call_args = self.fixed_args() + "".join(f", {cur[f]}" for f in self.var_fields) + ", hb"
        if self.route == "frame":
            call_args += "".join(f", {x}" for x in invs)
        return f"{name}({br.cond}, {call_args}, {{==}})"

    def contradiction(self, br: Branch):
        """(the boolean lemma, its atoms) when the branch is a check whose condition B makes 0 (the chain_revert
        target), else None."""
        if not br.fn.startswith(f"M.k_{self.ab}_"):
            return None
        r = contradicts(self.b_code, br.cond)
        if r is None:
            return None
        atoms, sb, sc = r
        key = (sb, sc, len(atoms))
        if key not in self.nbs:
            self.nb_count += 1
            nm = f"{self.p}_nb{self.nb_count}"
            self.nbs[key] = nm
            self.defs.append(nb_lemma(nm, atoms, sb, sc))
        return self.nbs[key], atoms

    # ------------------------------------------------------------------ frame
    def frame_invs(self, old_ov: str, new_ov: str, invs: list) -> list:
        """The invariants of the new overlay: each of B's slots holds the pre-state's word."""
        if self.route != "frame" or new_ov.strip() == old_ov.strip():
            return invs
        ss = stores(new_ov, old_ov.strip())
        if ss is None:
            raise NoProof(f"{self.action}: its overlay changes other than by stores")
        out = list(invs)
        for j, K in enumerate(self.keys):
            kv = literal_word(K)
            o = old_ov.strip()
            proof = out[j]
            for kw, v in ss:
                w = literal_word(kw)
                if w is None:
                    raise NoProof(f"{self.action}: it stores at a slot that is not a literal ({kw[:80]}): a mapping "
                                  "or array slot goes through the law's keccak256 parameter, which the statement leaves "
                                  "unconstrained, so no frame separates it from B's slots")
                if w == kv:
                    raise NoProof(f"{self.action}: it stores at a slot B reads ({K}): the transport route, which is "
                                  "not built")
                o2 = f"M.sstore({o}, {kw}, {v})"
                proof = (f"Equal.trans(M.W, M.sload({o2}, {K}), M.sload({o}, {K}), M.sload(st, {K}), "
                         f"st_frame({o}, {kw}, {v}, {K}, {{==}}, {{==}}), {proof})")
                o = o2
            out[j] = proof
        return out

    def end(self, vals: dict, invs: list) -> str:
        """The end of a path that does not revert by a literal code: by cases on the code, the post-state is the
        pre-state (a revert) or the overlay, where B holds by the invariants."""
        self.br_count += 1
        name = f"{self.p}_e{self.br_count}"
        rec = self.record({f: (self.fixed[f] if f in self.fixed else vals[f]) for f in self.fields})
        rec_v = self.record({f: (self.fixed[f] if f in self.fixed else f"v_{f}") for f in self.fields})
        vp = "".join(f", +v_{f}: {self.types[self.fields.index(f)]}" for f in self.var_fields)
        ip = "".join(f", +inv{j}: {{M.sload(v_ov, {k}) == M.sload(st, {k}) : M.W}}" for j, k in enumerate(self.keys))
        n = len(self.keys)
        body = "hb"
        for j in range(n - 1, -1, -1):
            args = [f"M.sload(st, {self.keys[i]})" for i in range(j)] + ["_"] + \
                   [f"M.sload(v_ov, {self.keys[i]})" for i in range(j + 1, n)]
            motive = f"{{D.blkv_{self.tag}({', '.join(args)}, D.d_time(e){self.g.targs}) == True{{}} : Bool}}"
            body = (f"(%Equal.sym(M.W, M.sload(v_ov, {self.keys[j]}), M.sload(st, {self.keys[j]}), inv{j}) "
                    f": {motive}\n      {body})")
        goal = (f"{{D.blk_{self.tag}(M.gh_get_st(M.gh_ok_{self.ab}(c, {rec_v}, {self.g.g_term()})), D.d_time(e)"
                f"{self.g.targs}) == True{{}} : Bool}}")
        self.defs.append(f"def {name}(c: Bool, {self.fixed_params()}{vp}, +hb: {{D.blk_{self.tag}(st, t{self.g.targs}) "
                         f"== True{{}} : Bool}}{ip}) -> {goal}:\n  match c:\n    case True{{}}:\n      hb\n"
                         f"    case False{{}}:\n      {body}\n")
        args = self.fixed_args() + "".join(f", {vals[f]}" for f in self.var_fields) + ", hb" + \
            "".join(f", {x}" for x in invs)
        _ = rec
        return f"{name}(M.u_nz({vals['cd']}), {args})"

    # ------------------------------------------------------------------ the action's term
    def term(self) -> str:
        """The proof of the route's goal for the whole program, from x0 (variables st, ar, e, t, tables, G's fields,
        hb in scope)."""
        x0 = self.mi.x0_fields("st", "ar", "e", list(self.g.tabs))
        vals = self.check_fixed(x0)
        first = self.stmt(self.mi.first)
        invs = []
        if self.route == "frame":
            invs = ["{==}" for _k in self.keys]       # the overlay starts as the pre-state
        return self.call(first, vals, invs)


LHEADER = "# GENERATED by holon.disch.proofs from the frozen law IR; do not edit."


def laws_text(law_id: str, statement_hash: str, model_import: str, section_import: str, tabs: list, law_name: str,
              kind: str) -> str:
    """gen/<M>/laws/<id>/LAWS.bend: the law (kind "forall": every binder universal, the claim disch_<x> == True;
    "exists": an existential law, every binder a witness; "counter": the counter-law of a forall law, every binder a
    witness and the claim disch_<x> != True). Bend's binder order puts the hash tables first (Reach depends on them);
    the IR's order is s, t, a, e, then the tables."""
    x = law_id[len("L_disch_"):]
    q, plus, rel = {"forall": ("for", "+", "=="), "exists": ("exs", "", "=="), "counter": ("exs", "", "!=")}[kind]
    lines = [LHEADER, f"# law_id: {law_id}   statement_hash: {statement_hash}", "import Base",
             f"import {model_import} as M", f"import {section_import} as D", "", f"law {law_name}:"]
    for n in tabs:
        lines.append(f"  {q} {plus}{n}: List<&2, M.HKB>")
    idx = "".join(f"{n}, " for n in tabs)
    lines += [f"  {q} {plus}s: M.GSt", f"  {q} r_s: M.Reach<{idx}s>", f"  {q} {plus}t: M.W", f"  {q} {plus}a: M.HAct",
              f"  {q} {plus}e: M.HEnv", f"  {{D.disch_{x}(a, s, t, e{''.join(', ' + n for n in tabs)}) {rel} True{{}} : Bool}}"]
    return "\n".join(lines) + "\n"


NOT_OF = ("def not_of(c: Bool, f: {c == True{} : Bool} -> Empty) -> {Bool.not(c) == True{} : Bool}:\n  match c:\n"
          "    case True{}:\n      efq({Bool.not(True{}) == True{} : Bool}, f({==}))\n    case False{}:\n      {==}\n")


def law_proof(g: Gen, law: dict, model_import: str, section_import: str, laws_import: str,
              law_name: str) -> tuple[str, dict]:
    """The proof file of a forall DISCH law (blocking, revert, external_none) and the route of each action of its
    set ({action: route}); NoProof names the first action without a route."""
    sf = law["subform"]
    tag = law["tag"]
    x = law["law_id"][len("L_disch_"):]
    if sf == "external":
        raise NoProof("an existential law is proved by its witness")
    members = law["excluded"] if sf == "revert" else law["closure"]
    cls = law.get("class")
    pred_actions = set()
    if cls is not None and g.an["classes"][cls]["predicate"] is not None:
        pred_actions = set(g.an["classes"][cls]["actions"])
    G = g.g_term()
    defs: list = []
    routes: dict = {}
    wrappers: dict = {}
    for i, act in enumerate(sorted(members)):
        ab = bname(act)
        p = f"r{i}"
        term, route, extra = None, None, []
        errors = []
        order = ("revert",) if sf == "revert" else ("revert", "frame")
        for rt in order:
            try:
                ap = ActionProof(g, tag, act, rt, f"{p}{rt[0]}")
                t0 = ap.term()
            except (NoProof, NoMirror) as e:
                errors.append(f"{'chain_revert' if rt == 'revert' else rt}: {e}")
                continue
            extra = ap.defs
            route = "chain_revert" if rt == "revert" else rt
            term = t0
            break
        if term is None:
            raise NoProof(f"{act}: no route ({'; '.join(errors)})")
        routes[act] = route
        defs += extra
        T = "D.d_time(e)"
        if sf == "revert":
            concl = term
        elif sf == "blocking":
            if route == "chain_revert":
                defs.append(go_rev_lemma(g, ab, f"{p}_go"))
                xr = f"M.xr_{ab}(st, ar, e{g.targs})"
                post = (f"(%Equal.sym(M.GSt, M.gh_go_{ab}({xr}, {G}), {G}, {p}_go({xr}, {G}, {term})) : "
                        f"{{D.blk_{tag}(M.gh_get_st(_), {T}{g.targs}) == True{{}} : Bool}}\n  hb)")
            else:
                post = term
            concl = (f"and_intro(D.blk_{tag}(st, {T}{g.targs}), D.blk_{tag}(M.gh_get_st(M.gh_step(D.d_env(M.A_{ab}"
                     f"{{ar, en}}, e), {G}{g.targs})), {T}{g.targs}), hb, {post})")
        else:   # external_none: a reverting step leaves the state, where c does not hold under B
            if route != "chain_revert":
                raise NoProof(f"{act}: external_none needs the step to revert (a frame of c is not built)")
            r = contradicts(g.sec.blk[tag]["code"], g.sec.chk[tag])
            if r is None or g.sec.blk[tag]["time"]:
                raise NoProof(f"{act}: B and c are not contradictory by cases on their atoms")
            atoms, sb, sc = r
            defs.append(nb_lemma(f"{p}_nbc", atoms, sb, sc))
            if "not_of" not in "".join(defs):
                defs.append(NOT_OF)
            defs.append(go_rev_lemma(g, ab, f"{p}_go"))
            xr = f"M.xr_{ab}(st, ar, e{g.targs})"
            notc = f"not_of(D.chk_{tag}(st, {T}{g.targs}), ec => {p}_nbc({''.join(a + ', ' for a in atoms)}hb, ec))"
            concl = (f"(%Equal.sym(M.GSt, M.gh_go_{ab}({xr}, {G}), {G}, {p}_go({xr}, {G}, {term})) : "
                     f"{{Bool.not(D.chk_{tag}(M.gh_get_st(_), {T}{g.targs})) == True{{}} : Bool}}\n  {notc})")
        member = "True{}" if sf == "revert" or act not in pred_actions else g.sec.perm_code(act)
        rest = f"Bool.and(D.blk_{tag}(st, t{g.targs}), M.w_le(t, {T}))"
        hsrc = "h" if member == "True{}" else f"and_r({member}, {rest}, h)"
        hb = f"and_l(D.blk_{tag}(st, t{g.targs}), M.w_le(t, {T}), {hsrc})"
        aterm = f"M.A_{ab}{{ar, en}}"
        wn = f"{p}_w"
        defs.append(f"def {wn}(+st: M.HSt{g.g_params()}, +ar: M.AR_{ab}, +en: M.HEnv, +t: M.W, +e: M.HEnv"
                    f"{g.tparams}, +h: {{D.prem_{x}({aterm}, {G}, t, e{g.targs}) == True{{}} : Bool}}) -> "
                    f"{{D.concl_{x}({aterm}, {G}, e{g.targs}) == True{{}} : Bool}}:\n  +hb = {hb}\n  {concl}\n")
        wrappers[ab] = wn
    cases = []
    for ab in g.sec.acts:
        if ab in wrappers:
            aterm = f"M.A_{ab}{{ar, en}}"
            cases.append(f"        case M.A_{ab}{{+ar, +en}}:\n          imp_g(D.prem_{x}({aterm}, {G}, t, e{g.targs}), "
                         f"D.concl_{x}({aterm}, {G}, e{g.targs}), h => {wrappers[ab]}(st{g.g_args()}, ar, en, t, e"
                         f"{g.targs}, h))\n")
        else:
            cases.append(f"        case M.A_{ab}{{_, _}}:\n          {{==}}\n")
    gpat = "M.GSt{" + ", ".join(["+st"] + [f"+g_{f}" for f in g.gst[1:]]) + "}"
    params = ", ".join(g.tabs + ["s", "r_s", "t", "a", "e"])
    head = [PHEADER, "import Base", f"import {model_import} as M", f"import {section_import} as D",
            f"import {laws_import} as Laws", "",
            f"# routes: {', '.join(f'{k}: {v}' for k, v in sorted(routes.items()))}", LIBRARY]
    main = (f"def Laws.{law_name}({params}):\n  match s:\n    case {gpat}:\n      match a:\n" + "".join(cases))
    return "\n".join(head + defs + [main]), routes


def go_rev_lemma(g: Gen, ab: str, name: str) -> str:
    """{gh_go_<a>(x, g) == g} when x's code is not 0 (a reverting step leaves the augmented state)."""
    mi = g.mirror(ab)
    pv = [f"x_{f}" for f in mi.field_names]
    rec = f"M.X_{ab}{{{', '.join(pv)}}}"
    pat = f"M.X_{ab}{{{', '.join('+' + v for v in pv)}}}"
    return (f"def {name}(x: M.X_{ab}, +gg: M.GSt, r: {{M.u_nz(M.gx_{ab}_cd(x)) == True{{}} : Bool}}) -> "
            f"{{M.gh_go_{ab}(x, gg) == gg : M.GSt}}:\n  match x:\n    case {pat}:\n"
            f"      (%Equal.sym(Bool, M.u_nz(x_cd), True{{}}, r) : {{M.gh_ok_{ab}(_, {rec}, gg) == gg : M.GSt}}\n"
            f"      {{==}})\n")
