"""The proof generators of the DISCH laws (BUILD_PLAN I31; the contract is the docstring of tests_m3/test_disch.py,
"Deciding"): one class per route, generic in the model.

  frame         an action of a closure that writes no slot B reads: every store of its program is at a literal slot
                other than B's slots, so the word at each of B's slots after it is the word before (core lemma
                st_frame), on every path of the program, and B (stated over those words, blkv_<tag>) is kept
  transport     an action that stores a literal word at a slot B reads (the safe writes of D9 with a constant post):
                the word at that slot after it is the literal (st_same), and B of the stored words follows from B
                in the pre-state by cases on B's atoms, Bend evaluating the closed ones; a store of a word that is not
                a literal at a slot B reads (a bit-field update of a packed slot) is refused, named (bit-field lemmas
                are not built)
  chain_revert  an action whose decision chain reaches a check B makes 0, or reverts earlier: on every path of its
                program before that check either an earlier check fails (the step reverts with that check's code) or
                the check is reached, where its condition and B are contradictory: a boolean lemma over their atoms,
                by cases, under the word-order implications between comparisons of one term with literals (x < 2
                gives x < 3: holon.disch.order's w_lt_le, w_le_lt, the literals' order computed); a reverting step's
                post-state is its pre-state
  time          B at t and t <= time(e) give B at time(e) (TimeMono): each clock atom of B rises or falls with the
                clock (x < t, x <= t, t < x, t <= x, and a signed difference A - t that does or does not realize),
                proved from the word-order lemmas; tl_<tag> combines them by cases on B's atoms; every other route
                then states B at time(e). A clock atom of another form is refused (named)

external_none uses the blocking routes for one step (B in the post-state, or a revert that keeps the state) and the
contradiction of B and c. The proofs mirror the typed model's statement chains (holon.disch.mirror): a lemma per
statement of an action (per state of B's slot invariants), over its context record with the fields that change as
variables, and a case lemma per condition the program branches on. Every lemma holds for every state: no reachability
is assumed (the Reach premise is not used). The core lemmas (holon.disch.lemmas.LIBRARY) and the word-order lemmas
(holon.disch.order) are emitted into each proof file and checked with it.

A law whose every action of its set has a route is written as gen/<M>/proofs/<id>/PROOF.bend; otherwise NoProof names
the first action without one and why. Nothing here names a target.
"""
from __future__ import annotations

import itertools
import re

from ..machine_bend import bname
from ..sorts.proofs3 import PHEADER
from . import order as ORDER
from .lemmas import library
from .mirror import LOOP_PARTS, Branch, Final, Loop, Mirror, NoMirror, Next, Record, _match_close, as_call, split_top


class NoProof(ValueError):
    """The route does not apply (named)."""


class NeedSplit(NoProof):
    """(I68) A store's key meets one of B's keys in the words (x, y) and no fact in scope decides w_eq(x, y): a route
    that may split the path there (holon.sorts.tag_exact) catches it."""

    def __init__(self, x: str, y: str):
        super().__init__(f"a store meets B's key where {x[:80]} and {y[:80]} may be equal")
        self.x, self.y = x, y


_CONN = {"Bool.and": 2, "Bool.or": 2, "Bool.not": 1}


# ------------------------------------------------------------------------------------------------ boolean skeletons
def skeleton(code: str, atoms: list, keep=None) -> str:
    """code as a term over v<i> (its atoms, collected in order): Bool.and/or/not and the literals kept (and every
    atom keep(atom) holds for, left as it is)."""
    code = code.strip()
    if code in ("True{}", "False{}"):
        return code
    c = as_call(code)
    if c and c[2] == "(" and c[0] in _CONN and len(c[1]) == _CONN[c[0]]:
        return f"{c[0]}(" + ", ".join(skeleton(x, atoms, keep) for x in c[1]) + ")"
    if keep is not None and keep(code):
        return code
    if code not in atoms:
        atoms.append(code)
    return f"v{atoms.index(code)}"


def _closed(atom: str) -> bool:
    """An atom over literals only (no state, time, table, environment or argument variable)."""
    return re.search(r"(?<![\w.])(st|t|kh|sh|e|ar|en|v_\w+)(?![\w{])", atom) is None


def _bev_open(sk: str, val: dict):
    """_bev with closed atoms left in the skeleton: True / False when decided without them, else None."""
    try:
        return _bev(sk, val)
    except Exception:  # noqa: BLE001: a closed atom: undecided here (Bend evaluates it)
        return None


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


def _lt_parts(atom: str):
    """(x, k, side) for M.w_lt(x, K) (side "lo": x < K) or M.w_lt(K, x) (side "hi": K < x) with K a literal word."""
    c = as_call(atom)
    if not c or c[0] != "M.w_lt" or c[2] != "(" or len(c[1]) != 2:
        return None
    a, b = c[1][0].strip(), c[1][1].strip()
    ka, kb = literal_word(a), literal_word(b)
    if kb is not None and ka is None:
        return a, b, kb, "lo"
    if ka is not None and kb is None:
        return b, a, ka, "hi"
    return None


def implications(atoms: list) -> list:
    """[(i, j, proof)]: atom i implies atom j by the word order (holon.disch.order), for two comparisons of one term
    with literals: x < K1 gives x < K2 when K1 <= K2 (w_lt_le), K1 < x gives K2 < x when K2 <= K1 (w_le_lt). The
    proof is a function of h: {atom i == True}; the literals' own order is computed ({==})."""
    parts = [_lt_parts(a) for a in atoms]
    out = []
    for i, pi in enumerate(parts):
        for j, pj in enumerate(parts):
            if i == j or pi is None or pj is None or pi[0] != pj[0] or pi[3] != pj[3]:
                continue
            x, k1, v1, side = pi
            _x, k2, v2, _s = pj
            if side == "lo" and v1 <= v2:
                out.append((i, j, f"h => w_lt_le({x}, {k1}, {k2}, h, {{==}})"))
            elif side == "hi" and v2 <= v1:
                out.append((i, j, f"h => w_le_lt({k2}, {k1}, {x}, {{==}}, h)"))
    return out


def contradicts(b_code: str, c_code: str) -> tuple | None:
    """(atoms, B's skeleton, c's skeleton, implications) when B and c are never true together (by cases on their
    atoms, under the word-order implications between them), else None."""
    atoms: list = []
    sb = skeleton(b_code, atoms)
    sc = skeleton(c_code, atoms)
    if len(atoms) > 10:
        return None
    imps = implications(atoms)
    for vals in itertools.product([True, False], repeat=len(atoms)):
        val = dict(enumerate(vals))
        if any(val[i] and not val[j] for i, j, _p in imps):
            continue
        if _bev(sb, val) and _bev(sc, val):
            return None
    return atoms, sb, sc, imps


def nb_lemma(name: str, atoms: list, sb: str, sc: str, imps: list | None = None) -> str:
    """def name(v0.., hB: {B == True}, hc: {c == True}, m0..: {v_i == True} -> {v_j == True}) -> Empty, by cases on
    the atoms (a case an implication excludes is closed by it)."""
    imps = imps or []
    vs = [f"v{i}" for i in range(len(atoms))]
    ms = "".join(f", m{k}: {{v{i} == True{{}} : Bool}} -> {{v{j} == True{{}} : Bool}}" for k, (i, j, _p) in enumerate(imps))
    head = (f"def {name}(" + "".join(f"{v}: Bool, " for v in vs) + f"hB: {{{sb} == True{{}} : Bool}}, "
            f"hc: {{{sc} == True{{}} : Bool}}{ms}) -> Empty:\n")
    if not vs:
        return head + "  false_ne_true(hB)\n"
    lines = [head, f"  match {' '.join(vs)}:\n"]
    for vals in itertools.product([True, False], repeat=len(vs)):
        val = dict(enumerate(vals))
        pat = " ".join("True{}" if x else "False{}" for x in vals)
        bad = next((k for k, (i, j, _p) in enumerate(imps) if val[i] and not val[j]), None)
        if bad is not None:
            body = f"false_ne_true(m{bad}({{==}}))"
        else:
            body = f"false_ne_true({'hB' if not _bev(sb, val) else 'hc'})"
        lines.append(f"    case {pat}:\n      {body}\n")
    return "".join(lines)


def imp_args(imps: list) -> str:
    return "".join(f", {p}" for _i, _j, p in imps)


def at_time(code: str, T: str) -> str:
    """A section term over the time variable t at the time T (the variable replaced)."""
    return re.sub(r"(?<![\w.])t(?![\w{])", T, code)


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


_M256 = (1 << 256) - 1


def closed_word(t: str) -> int | None:
    """The value of a closed word term (literals, w0, w_and, w_or, w_not, w_add, w_shl_<n>, w_shr_<n>), else None."""
    v = literal_word(t)
    if v is not None:
        return v
    c = as_call(t.strip())
    if not c or c[2] != "(":
        return None
    xs = [closed_word(x) for x in c[1]]
    if any(x is None for x in xs):
        return None
    op = c[0]
    if op == "M.w_and" and len(xs) == 2:
        return xs[0] & xs[1]
    if op == "M.w_or" and len(xs) == 2:
        return xs[0] | xs[1]
    if op == "M.w_not" and len(xs) == 1:
        return ~xs[0] & _M256
    m = re.fullmatch(r"M\.w_sh([lr])_(\d+)", op)
    if m and len(xs) == 1:
        n = int(m.group(2))
        return (xs[0] << n) & _M256 if m.group(1) == "l" else xs[0] >> n
    return None


def word_text(v: int) -> str:
    return "M.W{" + ", ".join(str((v >> (32 * i)) & 0xFFFFFFFF) for i in range(8)) + "}"


def masked(v: str, inner: str):
    """(m, x) when v is a masked write w_or(w_and(inner, m), x) of the word inner with closed m and x, else None."""
    c = as_call(v.strip())
    if not c or c[0] != "M.w_or" or len(c[1]) != 2:
        return None
    a = as_call(c[1][0].strip())
    if not a or a[0] != "M.w_and" or len(a[1]) != 2 or a[1][0].strip() != inner.strip():
        return None
    m, x = a[1][1].strip(), c[1][1].strip()
    return (m, x) if closed_word(m) is not None and closed_word(x) is not None else None


def bf_value(t: str, k: str):
    """(value, proof of {w_and(t, k) == value}) when t is a chain of masked writes whose last write of k's bits wrote
    a closed word (w_bf_read there, w_bf_keep through the writes of other bits), else None (I68's bit-field lemmas)."""
    kv = closed_word(k)
    c = as_call(t.strip())
    if kv is None or not c or c[0] != "M.w_or" or len(c[1]) != 2:
        return None
    a = as_call(c[1][0].strip())
    if not a or a[0] != "M.w_and" or len(a[1]) != 2:
        return None
    x, m, v = a[1][0].strip(), a[1][1].strip(), c[1][1].strip()
    mv, vv = closed_word(m), closed_word(v)
    if mv is None or vv is None:
        return None
    if mv & kv == 0:
        return vv & kv, f"w_bf_read({x}, {m}, {v}, {k}, {{==}})"
    if mv & kv == kv and vv & kv == 0:
        r = bf_value(x, k)
        if r is not None:
            return r[0], (f"Equal.trans(M.W, M.w_and({t.strip()}, {k}), M.w_and({x}, {k}), {word_text(r[0])}, "
                          f"w_bf_keep({x}, {m}, {v}, {k}, {{==}}, {{==}}), {r[1]})")
    return None


def sk_parts(t: str):
    """(b, o, [(k, o2)..]) of a structural key term M.SK{b, o, p} whose path is a list literal (Nil{} or [M.SP_m{k,
    o2}, ..]), else None (I68)."""
    c = as_call(t.strip())
    if not c or c[0] != "M.SK" or c[2] != "{" or len(c[1]) != 3:
        return None
    b, o, p = (x.strip() for x in c[1])
    if p == "Nil{}":
        return b, o, []
    if not (p.startswith("[") and p.endswith("]")):
        return None
    steps = []
    for x in (split_top(p[1:-1]) if p[1:-1].strip() else []):
        cs = as_call(x)
        if not cs or cs[0] != "M.SP_m" or cs[2] != "{" or len(cs[1]) != 2:
            return None
        steps.append((cs[1][0].strip(), cs[1][1].strip()))
    return b, o, steps


def key_cmp(kw: str, k: str, structural: bool) -> tuple:
    """How Bend decides a store key kw against a read key k: ("same", None) when the key equality evaluates to True,
    ("differ", None) when it evaluates to False (st_frame's two hypotheses are then {==}), ("stuck", (x, y)) when the
    evaluation stops at the comparison of the words x (of kw) and y (of k). A raw key is a word (w_eq); a structural
    key is compared as sk_eq evaluates (the base, the offset, then each step's offset and key word, a step missing on
    one side deciding False)."""
    if not structural:
        a, b = literal_word(kw), literal_word(k)
        if a is None or b is None:
            return "stuck", (kw.strip(), k.strip())
        return ("same" if a == b else "differ"), None
    pa, pb = sk_parts(kw), sk_parts(k)
    if pa is None or pb is None:
        return "stuck", (kw.strip(), k.strip())
    pairs = [(pa[0], pb[0]), (pa[1], pb[1])]
    for i in range(max(len(pa[2]), len(pb[2]))):
        if i >= len(pa[2]) or i >= len(pb[2]):   # one path ends first: sps_eq is False there
            r = _cmp_pairs(pairs)
            return ("differ", None) if r[0] == "same" else r
        pairs += [(pa[2][i][1], pb[2][i][1]), (pa[2][i][0], pb[2][i][0])]
    return _cmp_pairs(pairs)


def _cmp_pairs(pairs: list) -> tuple:
    """The first comparison of word pairs that does not evaluate to True decides: False ("differ"), or stuck."""
    for x, y in pairs:
        a, b = literal_word(x), literal_word(y)
        if a is None or b is None:
            return "stuck", (x, y)
        if a != b:
            return "differ", None
    return "same", None


def _sps_text(steps: list) -> str:
    return ("[" + ", ".join(f"M.SP_m{{{k}, {o}}}" for k, o in steps) + "]") if steps else "Nil{}"


def sk_ne_proof(kw: str, k: str, hyp: str) -> str | None:
    """A proof of {sk_eq(kw, k) == False} from hyp : {w_eq(x, y) == False}, (x, y) the first comparison of their words
    that does not evaluate (key_cmp's stuck pair, x of kw); every comparison before it is {==} (holon.disch.lemmas'
    sk_ne_*, I68's key split). None when either is not a structural key with a list path."""
    pa, pb = sk_parts(kw), sk_parts(k)
    if pa is None or pb is None:
        return None
    (ab, ao, ap), (bb, bo, bp) = pa, pb
    args = f"{ab}, {ao}, {_sps_text(ap)}, {bb}, {bo}, {_sps_text(bp)}"
    if literal_word(ab) is None or literal_word(bb) is None:
        return f"sk_ne_b({args}, {hyp})"
    if literal_word(ao) is None or literal_word(bo) is None:
        return f"sk_ne_o({args}, {{==}}, {hyp})"

    def sps(xa: list, xb: list):
        if not xa or not xb:
            return None
        (k1, o1), (k2, o2) = xa[0], xb[0]
        x, y, xs, ys = f"M.SP_m{{{k1}, {o1}}}", f"M.SP_m{{{k2}, {o2}}}", _sps_text(xa[1:]), _sps_text(xb[1:])
        if literal_word(o1) is None or literal_word(o2) is None:
            return f"sps_ne_h({x}, {xs}, {y}, {ys}, sp_ne_o({k1}, {o1}, {k2}, {o2}, {hyp}))"
        if literal_word(k1) is None or literal_word(k2) is None:
            return f"sps_ne_h({x}, {xs}, {y}, {ys}, sp_ne_k({k1}, {o1}, {k2}, {o2}, {{==}}, {hyp}))"
        rest = sps(xa[1:], xb[1:])
        return f"sps_ne_t({x}, {xs}, {y}, {ys}, {{==}}, {rest})" if rest else None
    rest = sps(ap, bp)
    return f"sk_ne_p({args}, {{==}}, {{==}}, {rest})" if rest else None


def sk_eq_proof(kw: str, k: str, hyp: str) -> str | None:
    """A proof of {sk_eq(kw, k) == True} from hyp : {w_eq(x, y) == True}, (x, y) key_cmp's stuck pair (x of kw), every
    other comparison evaluating to True (and_intro over sk_eq's conjunctions); None otherwise."""
    pa, pb = sk_parts(kw), sk_parts(k)
    if pa is None or pb is None or len(pa[2]) != len(pb[2]):
        return None
    pairs = [(pa[0], pb[0]), (pa[1], pb[1])] + [q for (k1, o1), (k2, o2) in zip(pa[2], pb[2]) for q in ((o1, o2), (k1, k2))]
    used = False
    pfs = []
    for x, y in pairs:
        a, b = literal_word(x), literal_word(y)
        if a is not None and b is not None and a == b:
            pfs.append("{==}")
        elif not used and (a is None or b is None):
            pfs.append(hyp)
            used = True
        else:
            return None
    # sk_eq: and(w_eq(b), and(w_eq(o), sps)); sps: and(sp_eq, sps_rest) per step, Nil: True; sp_eq: and(w_eq(o), w_eq(k))
    def sps(i: int) -> tuple[str, str]:
        if i == len(pa[2]):
            return "M.sps_eq(Nil{}, Nil{})", "{==}"
        (k1, o1), (k2, o2) = pa[2][i], pb[2][i]
        sp = f"M.sp_eq(M.SP_m{{{k1}, {o1}}}, M.SP_m{{{k2}, {o2}}})"
        spp = f"and_intro(M.w_eq({o1}, {o2}), M.w_eq({k1}, {k2}), {pfs[2 + 2 * i]}, {pfs[3 + 2 * i]})"
        rest, rp = sps(i + 1)
        xs, ys = _sps_text(pa[2][i + 1:]), _sps_text(pb[2][i + 1:])
        return (f"M.sps_eq({_sps_text(pa[2][i:])}, {_sps_text(pb[2][i:])})",
                f"and_intro({sp}, M.sps_eq({xs}, {ys}), {spp}, {rp})")
    st, sp_pf = sps(0)
    return (f"and_intro(M.w_eq({pa[0]}, {pb[0]}), Bool.and(M.w_eq({pa[1]}, {pb[1]}), {st}), {pfs[0]}, "
            f"and_intro(M.w_eq({pa[1]}, {pb[1]}), {st}, {pfs[1]}, {sp_pf}))")


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
        self.sk = "\ntype SK is Data:\n" in model_text      # a structural store (I68): keys are SK terms
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
        self._common(g, action, route, prefix)
        self.tag = tag
        blk = g.sec.blk[tag]
        # a B that reads the clock is used at the step's time (the time monotonicity lemma tl_<tag> gives it there
        # from the premise's t <= time(e)): T is the time B is stated at in every hypothesis
        self.time = bool(blk["time"])
        self.T = "D.d_time(e)" if self.time else "t"
        self.b_code = at_time(blk["code"], self.T) if self.time else blk["code"]
        self.keys = blk["keys"]
        if route == "frame" and blk["v"] is None:
            raise NoProof("B reads a slot whose key reads the state (a key that is not closed): no frame by slots"
                          if g.sk else "B reads a slot that is not a literal (a mapping or array slot): no frame by slots")

    def _common(self, g: Gen, action: str, route: str, prefix: str) -> None:
        self.g = g
        self.action = action
        self.ab = bname(action)
        self.route = route
        self.tracks = route in ("frame", "loop")   # the route carries invariants of B's slots on the overlay
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
        self.loops: dict = {}               # loop L -> its LoopProof (I68, the loop frames L1)
        self.splits = False                 # a stuck store raises NeedSplit (I68: holon.sorts.tag_exact's step lemmas)
        self.loop_extra: list = []          # [(name, type)]: variables B's keys mention besides st (I68, tag_exact's k)

    # ------------------------------------------------------------------ text pieces
    def hb_param(self) -> str:
        return f", +hb: {{D.blk_{self.tag}(st, {self.T}{self.g.targs}) == True{{}} : Bool}}"

    def hb_arg(self) -> str:
        return ", hb"
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

    def same(self, j: int) -> str:
        return f"M.sload(st, {self.keys[j]})"

    def hyp_params(self, state: tuple = ()) -> str:
        """hb, and for a frame or transport route each of B's slots' invariant on the overlay: the pre-state's word
        (frame) or the literal word a store put there (transport)."""
        out = self.hb_param()
        if self.tracks:
            for j, k in enumerate(self.keys):
                out += f", +inv{j}: {{M.sload(v_ov, {k}) == {state[j]} : M.W}}"
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
    def stmt(self, i: int, state: tuple = (), conds: tuple = ()) -> str:
        """The lemma of statement i under the invariants' state and the passed checks carried to it (generated once
        per state and carried checks); returns its name."""
        key = (i, state, conds)
        if key in self.done:
            return self.done[key]
        k = len([1 for (j, _s, _c) in self.done if j == i])
        name = f"{self.p}_s{i}" + (f"_{k}" if k else "")
        self.done[key] = name
        node = self.mi.step(i, [self.fixed[f] if f in self.fixed else f"v_{f}" for f in self.fields])
        body = self.emit(node, {f: f"v_{f}" for f in self.var_fields},
                         invs=[(f"inv{j}", state[j]) for j in range(len(self.keys))] if self.tracks else [],
                         carried=tuple((f"hc{q}", c) for q, c in enumerate(conds)))
        self.defs.append(f"def {name}({self.fixed_params()}{self.var_params()}{self.hyp_params(state)}"
                         f"{self.carried_params(conds)}) -> "
                         f"{self.goal(f'M.s_{self.ab}_{i}({self.var_record()})')}:\n  {body}\n")
        return name

    @staticmethod
    def carried_params(conds) -> str:
        return "".join(f", +hc{q}: {{{c} == True{{}} : Bool}}" for q, c in enumerate(conds))

    def call(self, name: str, vals: dict, invs: list, carried: tuple = ()) -> str:
        args = self.fixed_args() + "".join(f", {vals[f]}" for f in self.var_fields) + self.hb_arg()
        if self.tracks:
            args += "".join(f", {x}" for x, _r in invs)
        args += "".join(f", {x}" for x, _c in carried)
        return f"{name}({args})"

    def check_fixed(self, fields: list) -> dict:
        vals = dict(zip(self.fields, fields))
        for f, want in self.fixed.items():
            if f in vals and vals[f].strip() != want:
                raise NoProof(f"{self.action}: the program changes its context's {f}")
        return {f: vals[f] for f in self.var_fields}

    def emit(self, node, cur: dict, invs: list, nonzero: str | None = None, carried: tuple = ()) -> str:
        """The proof term of the goal at node (cur: the current variables of the varying fields; nonzero: a code term
        the enclosing branch's equation ec says is not 0, u_nz(code) == True; carried: the passed checks' equations
        in scope, [(proof, condition)], the convoy)."""
        if isinstance(node, Next):
            if node.ctx is not None:
                raise NoProof(f"{self.action}: a loop body's statement outside its loop")
            vals = self.check_fixed(node.fields)
            new_invs = self.frame_invs(cur["ov"], vals["ov"], invs, carried) if self.tracks else invs
            return self.call(self.stmt(node.j, tuple(r for _x, r in new_invs), tuple(c for _x, c in carried)), vals,
                             new_invs, carried)
        if isinstance(node, Loop):
            return self.loop(node, cur, invs, carried)
        if isinstance(node, Final):
            vals = self.check_fixed(node.fields)
            cd = vals["cd"].strip()
            if re.fullmatch(r"\d+", cd) and int(cd) != 0:
                return "{==}" if self.route == "revert" else "hb"
            if self.route == "revert" and nonzero == cd:   # a code the enclosing branch knows is not 0
                return "ec"
            if self.route == "revert":
                raise NoProof(f"{self.action}: a path of its program ends without reverting before the check B "
                              "makes 0")
            new_invs = self.frame_invs(cur["ov"], vals["ov"], invs, carried)
            return self.end(vals, new_invs)
        if isinstance(node, Branch):
            return self.branch(node, cur, invs, carried)
        raise NoProof(f"{self.action}: an evaluation result the mirror cannot state ({type(node).__name__})")

    def branch(self, br: Branch, cur: dict, invs: list, carried: tuple = ()) -> str:
        self.br_count += 1
        name = f"{self.p}_b{self.br_count}"
        fn = br.fn
        args = ", ".join(br.args)
        then_term = None
        if self.route == "revert" or self.route == "frame":
            target = self.contradiction(br)
            if target is not None:
                nb, atoms, imps = target
                goal_t = self.goal(f"{fn}(True{{}}, {args})")
                then_term = f"efq({goal_t}, {nb}({''.join(a + ', ' for a in atoms)}hb, ec{imp_args(imps)}))"
        inner = tuple((f"hc{q}", c) for q, (_x, c) in enumerate(carried))
        if then_term is None:
            mz = re.fullmatch(r"M\.u_nz\((.*)\)", br.cond.strip())
            passed = inner + (("ec", br.cond.strip()),) if self.convoy(br, inner) else inner
            then_term = self.emit(br.then, cur, invs, nonzero=mz.group(1).strip() if mz else None, carried=passed)
        else_term = self.emit(br.other, cur, invs, carried=inner)
        inv_params = ""
        if self.tracks:
            inv_params = "".join(f", +{x}: {{M.sload({cur['ov']}, {k}) == {r} : M.W}}"
                                 for (x, r), k in zip(invs, self.keys))
        vp = "".join(f", +v_{f}: {self.types[self.fields.index(f)]}" for f in self.var_fields)
        lp, la = self.local_params(invs)
        self.defs.append(
            f"def {name}(c: Bool, {self.fixed_params()}{vp}{lp}{self.hb_param()}{inv_params}"
            f"{self.carried_params([c for _x, c in carried])}, ec: {{{br.cond} == c : Bool}}) "
            f"-> {self.goal(f'{fn}(c, {args})')}:\n"
            f"  match c:\n    case True{{}}:\n      {then_term}\n    case False{{}}:\n      {else_term}\n")
        call_args = self.fixed_args() + "".join(f", {cur[f]}" for f in self.var_fields) + la + self.hb_arg()
        if self.tracks:
            call_args += "".join(f", {x}" for x, _r in invs)
        call_args += "".join(f", {x}" for x, _c in carried)
        return f"{name}({br.cond}, {call_args}, {{==}})"

    def local_params(self, invs: list) -> tuple[str, str]:
        """(params, args) of the lemma-local words the invariants' right sides name (I68: tag_exact's transported
        words); the DISCH routes have none."""
        return "", ""

    def convoy(self, br: Branch, carried: tuple) -> bool:
        """(I68, the convoy) Is a passed check's equation carried down the chain? On the frame route over a structural
        store: a check of the action whose condition reads one of B's mapping families (a read at the base of a B key
        with a path) and no varying field of the context, so that a later store in that family, split on its key
        word, may find its equal case contradicting B by the check (key_split); at most six at a time."""
        if self.route != "frame" or not self.g.sk or not br.fn.startswith(f"M.k_{self.ab}_") or len(carried) >= 6:
            return False
        if re.search(r"(?<![\w.])v_\w+", br.cond):
            return False
        bases = {sk_parts(k)[0] for k in self.keys if sk_parts(k) and sk_parts(k)[2]}
        return any(f"M.sload(st, M.SK{{{b}," in br.cond for b in bases)

    @staticmethod
    def split_fact(at: tuple, carried: tuple):
        """("eq", {w_eq(x, y) == True}) or ("ne", {w_eq(x, y) == False}) when a carried fact decides the words (x, y) =
        at (a split's or a passed check's), else None."""
        x, y = at
        for pc, cond in carried:
            c = cond.strip()
            if c == f"M.w_eq({x}, {y})":
                return "eq", pc
            if c == f"Bool.not(M.w_eq({x}, {y}))":
                return "ne", f"not_t(M.w_eq({x}, {y}), {pc})"
        return None

    def nb_for(self, atoms: list, sb: str, sc: str, imps: list) -> str:
        """The boolean lemma of a contradiction (one per skeletons and implications)."""
        key = (sb, sc, len(atoms), tuple((i, j) for i, j, _p in imps))
        if key not in self.nbs:
            self.nb_count += 1
            nm = f"{self.p}_nb{self.nb_count}"
            self.nbs[key] = nm
            self.defs.append(nb_lemma(nm, atoms, sb, sc, imps))
        return self.nbs[key]

    def key_split(self, o: str, kw: str, v: str, k: str, at: tuple, carried: tuple) -> str | None:
        """(I68, the key split) {sload(sstore(o, kw, v), k) == sload(o, k)} for a store at kw that B's key k differs from
        only in the words (x, y) = at, by cases on w_eq(x, y): when they are equal, a passed check carried here (the
        convoy) contradicts B with x read as y; otherwise the keys differ (sk_ne_*) and st_frame applies. None when no
        carried check closes the equal case."""
        x, y = at
        for pc, cond in carried:
            if x not in cond:
                continue
            c2 = cond.replace(x, y)
            r = contradicts(self.b_code, c2.replace("M.ge_e_block_timestamp(e)", self.T) if self.time else c2)
            ne1, ne2 = sk_ne_proof(kw, k, "ec"), sk_ne_proof(k, kw, f"w_ne_sym({x}, {y}, ec)")
            if r is None or ne1 is None or ne2 is None:
                continue
            atoms, sb, sc, imps = r
            nb = self.nb_for(atoms, sb, sc, imps)
            self.br_count += 1
            name = f"{self.p}_ks{self.br_count}"
            vp, args = self.var_params(), self.fixed_args() + "".join(f", v_{f}" for f in self.var_fields)
            self.defs.append(f"def {name}r({self.fixed_params()}{vp}, ec: {{M.w_eq({x}, {y}) == True{{}} : Bool}}, "
                             f"hc: {{{cond} == True{{}} : Bool}}) -> {{{c2} == True{{}} : Bool}}:\n"
                             f"  (%w_refl({x}, {y}, ec) : {{{cond.replace(x, '_')} == True{{}} : Bool}}\n  hc)\n")
            goal = f"{{M.sload(M.sstore({o}, {kw}, {v}), {k}) == M.sload({o}, {k}) : M.W}}"
            true_t = f"efq({goal}, {nb}({''.join(a + ', ' for a in atoms)}hb, {name}r({args}, ec, hc){imp_args(imps)}))"
            self.defs.append(f"def {name}(c: Bool, {self.fixed_params()}{vp}{self.hb_param()}, +hc: {{{cond} == True{{}} "
                             f": Bool}}, +ec: {{M.w_eq({x}, {y}) == c : Bool}}) -> {goal}:\n  match c:\n"
                             f"    case True{{}}:\n      {true_t}\n    case False{{}}:\n"
                             f"      st_frame({o}, {kw}, {v}, {k}, {ne1}, {ne2})\n")
            return f"{name}(M.w_eq({x}, {y}), {args}{self.hb_arg()}, {pc}, {{==}})"
        return None

    def contradiction(self, br: Branch):
        """(the boolean lemma, its atoms) when the branch is a check whose condition B makes 0 (the chain_revert
        target), else None."""
        if not br.fn.startswith(f"M.k_{self.ab}_"):
            return None
        # B is stated at the step's time D.d_time(e), which is the check's block.timestamp by definition: one atom
        cond = br.cond.replace("M.ge_e_block_timestamp(e)", self.T) if self.time else br.cond
        r = contradicts(self.b_code, cond)
        if r is None:
            return None
        atoms, sb, sc, imps = r
        key = (sb, sc, len(atoms), tuple((i, j) for i, j, _p in imps))
        if key not in self.nbs:
            self.nb_count += 1
            nm = f"{self.p}_nb{self.nb_count}"
            self.nbs[key] = nm
            self.defs.append(nb_lemma(nm, atoms, sb, sc, imps))
        return self.nbs[key], atoms, imps

    # ------------------------------------------------------------------ frame
    def frame_invs(self, old_ov: str, new_ov: str, invs: list, carried: tuple = ()) -> list:
        """The invariants of the new overlay, [(proof, word)]: each of B's slots holds the pre-state's word (frame:
        stores at other literal slots, st_frame) or the literal word a store put there (transport: st_same, a store of
        a literal word at a slot B reads; the end of the path then shows B of the stored words)."""
        if not self.tracks or new_ov.strip() == old_ov.strip():
            return invs
        ss = stores(new_ov, old_ov.strip())
        if ss is None:
            raise NoProof(f"{self.action}: its overlay changes other than by stores")
        out = list(invs)
        for j, K in enumerate(self.keys):
            o = old_ov.strip()
            proof, rhs = out[j]
            for kw, v in ss:
                rel, at = key_cmp(kw, K, self.g.sk)
                if rel == "stuck" and not self.g.sk:
                    raise NoProof(f"{self.action}: it stores at a slot that is not a literal ({kw[:80]}): a mapping "
                                  "or array slot goes through the law's keccak256 parameter, which the statement leaves "
                                  "unconstrained, so no frame separates it from B's slots")
                fr = f"st_frame({o}, {kw}, {v}, {K}, {{==}}, {{==}})"
                fact = self.split_fact(at, carried) if rel == "stuck" and self.splits else None
                if fact is not None and fact[0] == "eq":   # (I68, tag_exact) a split's fact: the store is at B's key
                    keq = sk_eq_proof(kw, K, fact[1])
                    if keq is None:
                        raise NoProof(f"{self.action}: the store at {kw.strip()[:120]} meets B's key {K[:120]} in more "
                                      "than the split words")
                    o2 = f"M.sstore({o}, {kw}, {v})"
                    proof, rhs = f"st_same_k({o}, {kw}, {v}, {K}, {keq})", v.strip()
                    o = o2
                    continue
                if fact is not None:                        # (I68, tag_exact) a split's fact: the keys differ
                    ne1, ne2 = sk_ne_proof(kw, K, fact[1]), sk_ne_proof(K, kw, f"w_ne_sym({at[0]}, {at[1]}, {fact[1]})")
                    fr = f"st_frame({o}, {kw}, {v}, {K}, {ne1}, {ne2})" if ne1 and ne2 else None
                elif rel == "stuck":
                    if self.splits:
                        raise NeedSplit(*at)
                    fr = self.key_split(o, kw, v, K, at, carried) if self.route == "frame" else None
                if fr is None and self.route == "loop":
                    raise NoProof(f"{self.action}: its loop {self.L} stores at {kw.strip()[:160]}, which B's key {K} "
                                  f"differs from only in words that are not literals ({at[0][:80]} against "
                                  f"{at[1][:80]}): no loop frame by evaluation")
                if fr is None:
                    raise NoProof(f"{self.action}: keeping B through its store at {kw.strip()[:160]} needs a monotone "
                                  f"transport (not built): the store is at B's key {K[:160]} when {at[0][:80]} == "
                                  f"{at[1][:80]}, and no passed check excludes that")
                o2 = f"M.sstore({o}, {kw}, {v})"
                if rel == "same" and self.route == "loop":
                    raise NoProof(f"{self.action}: its loop {self.L} stores at B's key {K}: no loop frame")
                bf = masked(v, f"M.sload({o}, {K})") if rel == "same" and self.g.sk else None
                if rel == "same" and bf is not None:
                    # (I68) a masked write of B's packed slot: the word there is the write over the word it held
                    m, x = bf
                    v2 = f"M.w_or(M.w_and({rhs}, {m}), {x})"
                    proof = (f"Equal.trans(M.W, M.sload({o2}, {K}), {v.strip()}, {v2}, st_same({o}, {kw}, {v}), "
                             f"Equal.cong(M.W, M.W, z => M.w_or(M.w_and(z, {m}), {x}), M.sload({o}, {K}), {rhs}, {proof}))")
                    rhs = v2
                elif rel == "same":
                    if literal_word(v) is None:
                        raise NoProof(f"{self.action}: it stores a word that is not a literal at a slot B reads ({K}: "
                                      f"{v.strip()[:80]}): transport states B of literal stored words and of masked "
                                      "writes of a packed slot only")
                    proof, rhs = f"st_same({o}, {kw}, {v})", v.strip()
                else:
                    proof = f"Equal.trans(M.W, M.sload({o2}, {K}), M.sload({o}, {K}), {rhs}, {fr}, {proof})"
                o = o2
            out[j] = (proof, rhs)
        return out

    def end(self, vals: dict, invs: list) -> str:
        """The end of a path that does not revert by a literal code: by cases on the code, the post-state is the
        pre-state (a revert) or the overlay, where B holds by the invariants (frame), or of the stored literal words
        (transport: B of them, by cases on B's other atoms, from B in the pre-state)."""
        self.br_count += 1
        name = f"{self.p}_e{self.br_count}"
        state = tuple(r for _x, r in invs)
        rec_v = self.record({f: (self.fixed[f] if f in self.fixed else f"v_{f}") for f in self.fields})
        vp = "".join(f", +v_{f}: {self.types[self.fields.index(f)]}" for f in self.var_fields)
        ip = "".join(f", +inv{j}: {{M.sload(v_ov, {k}) == {state[j]} : M.W}}" for j, k in enumerate(self.keys))
        n = len(self.keys)
        body = "hb" if all(state[j] == self.same(j) for j in range(n)) else self.transported(state)
        # a key that reads B's earlier keys (I68) is read in the post-state at the post-state's words: those slots must
        # keep the pre-state's (framed), so that rewriting them turns the key back into the pre-state's key
        tpl = self.g.sec.blk[self.tag].get("tpl") or list(self.keys)
        var = re.compile(r"(?<![\w.])v(\d+)(?![\w{])")
        for m in range(n):
            for i in {int(x) for x in var.findall(tpl[m])}:
                if state[i] != self.same(i):
                    raise NoProof(f"{self.action}: B's key {self.keys[m]} reads the slot {self.keys[i]}, which a path of "
                                  "the action changes")

        def at(m: int, j: int) -> str:   # key m in the goal while component j is rewritten
            return var.sub(lambda q: f"M.sload(st, {self.keys[int(q.group(1))]})" if int(q.group(1)) < j else "_"
                           if int(q.group(1)) == j else f"M.sload(v_ov, {at(int(q.group(1)), j)})", tpl[m])
        for j in range(n - 1, -1, -1):
            args = [state[i] for i in range(j)] + ["_"] + [f"M.sload(v_ov, {at(i, j)})" for i in range(j + 1, n)]
            motive = f"{{D.blkv_{self.tag}({', '.join(args)}, D.d_time(e){self.g.targs}) == True{{}} : Bool}}"
            body = (f"(%Equal.sym(M.W, M.sload(v_ov, {self.keys[j]}), {state[j]}, inv{j}) "
                    f": {motive}\n      {body})")
        goal = (f"{{D.blk_{self.tag}(M.gh_get_st(M.gh_ok_{self.ab}(c, {rec_v}, {self.g.g_term()})), D.d_time(e)"
                f"{self.g.targs}) == True{{}} : Bool}}")
        self.defs.append(f"def {name}(c: Bool, {self.fixed_params()}{vp}, +hb: {{D.blk_{self.tag}(st, {self.T}{self.g.targs}) "
                         f"== True{{}} : Bool}}{ip}) -> {goal}:\n  match c:\n    case True{{}}:\n      hb\n"
                         f"    case False{{}}:\n      {body}\n")
        args = self.fixed_args() + "".join(f", {vals[f]}" for f in self.var_fields) + ", hb" + \
            "".join(f", {x}" for x, _r in invs)
        return f"{name}(M.u_nz({vals['cd']}), {args})"

    def transported(self, state: tuple) -> str:
        """{blkv(state's words, time) == True} from hb (B over the pre-state's words): a lemma by cases on the atoms of
        the two that are not closed (an atom over literal words only is left to Bend's evaluation)."""
        v = self.g.sec.blk[self.tag]["v"]
        T = "D.d_time(e)"
        old = v
        new = v
        for j in range(len(self.keys) - 1, -1, -1):
            old = re.sub(rf"(?<![\w.])v{j}(?![\w{{])", f"M.sload(st, {self.keys[j]})", old)
            new = re.sub(rf"(?<![\w.])v{j}(?![\w{{])", state[j], new)
        old, new = at_time(old, T), at_time(new, T)
        # (I68) a field of a packed slot the path wrote with masked writes reads as the word it wrote last there
        subs = []
        for j in range(len(self.keys)):
            if literal_word(state[j]) is not None or state[j] == self.same(j):
                continue
            i = new.find(f"M.w_and({state[j]}, ")
            while i >= 0:
                e = _match_close(new, i + len("M.w_and"))
                parts = split_top(new[i + len("M.w_and("):e])
                field = new[i:e + 1]
                r = bf_value(state[j], parts[1]) if len(parts) == 2 else None
                if r is not None and field not in [f for f, _l, _p in subs]:
                    subs.append((field, word_text(r[0]), r[1]))
                i = new.find(f"M.w_and({state[j]}, ", i + 1)
        full = new
        for field, lit, _p in subs:
            new = new.replace(field, lit)
        atoms: list = []
        so = skeleton(old, atoms, keep=_closed)
        sn = skeleton(new, atoms, keep=_closed)
        if len(atoms) > 10:
            raise NoProof(f"{self.action}: transport: B has too many atoms for a case split")
        self.br_count += 1
        nm = f"{self.p}_tr{self.br_count}"
        vs = [f"v{i}" for i in range(len(atoms))]
        head = (f"def {nm}(" + "".join(f"{x}: Bool, " for x in vs) + f"hb: {{{so} == True{{}} : Bool}}) -> "
                f"{{{sn} == True{{}} : Bool}}:\n")
        if not vs:
            self.defs.append(head + "  {==}\n")
        else:
            rows = [head, f"  match {' '.join(vs)}:\n"]
            for vals in itertools.product([True, False], repeat=len(vs)):
                val = dict(enumerate(vals))
                pat = " ".join("True{}" if x else "False{}" for x in vals)
                inst = lambda sk: re.sub(r"(?<![\w.])v(\d+)(?![\w{])", lambda m: "True{}" if val[int(m.group(1))] else
                                          "False{}", sk)   # noqa: E731
                if _bev_open(so, val) is False:
                    rows.append(f"    case {pat}:\n      efq({{{inst(sn)} == True{{}} : Bool}}, false_ne_true(hb))\n")
                else:
                    rows.append(f"    case {pat}:\n      {{==}}\n")
            self.defs.append("".join(rows))
        body = f"{nm}({''.join(a + ', ' for a in atoms)}hb)"
        for q in range(len(subs) - 1, -1, -1):
            cur = full
            for f, lit, _p in subs[:q]:
                cur = cur.replace(f, lit)
            field, lit, pf = subs[q]
            body = (f"(%Equal.sym(M.W, {field}, {lit}, {pf}) : {{{cur.replace(field, '_')} == True{{}} : Bool}}\n"
                    f"      {body})")
        return body

    # ------------------------------------------------------------------ the action's term
    def term(self) -> str:
        """The proof of the route's goal for the whole program, from x0 (variables st, ar, e, t, tables, G's fields,
        hb in scope)."""
        x0 = self.mi.x0_fields("st", "ar", "e", list(self.g.tabs))
        vals = self.check_fixed(x0)
        invs = []
        if self.route == "frame":
            invs = [("{==}", self.same(j)) for j in range(len(self.keys))]    # the overlay starts as the pre-state
        first = self.stmt(self.mi.first, tuple(r for _x, r in invs))
        return self.call(first, vals, invs)

    # ------------------------------------------------------------------ loops (I68, the loop frames L1)
    def loop(self, node: Loop, cur: dict, invs: list, carried: tuple = ()) -> str:
        """A loop statement lg_<a>_<n>: Bend reduces it to la_<a>_<n>(u_nz(code(y)), y) with y the loop's run
        lp_<a>_<L>(fuel, d, ls_<a>_<L>(x)). The loop's lemma (LoopProof) shows that y has x's fixed fields and, on a
        route that carries invariants, x's words at B's keys; a continuation lemma opens y, rewrites its fixed fields to
        the context's and steps la_<a>_<n> on the opened record (a revert keeps the state; otherwise the next
        statement)."""
        vals = self.check_fixed(node.rec.fields)
        new_invs = self.frame_invs(cur["ov"], vals["ov"], invs, carried) if self.tracks else invs
        conds = [c for _x, c in carried]
        lp = self.loop_proof(node.L)
        self.br_count += 1
        name = f"{self.p}_c{self.br_count}"
        X = f"M.X_{self.ab}"
        ys = {f: (f"y_{f}" if f in self.fixed else f"v_{f}") for f in self.fields}
        canon = [self.fixed[f] if f in self.fixed else f"v_{f}" for f in self.fields]
        keys = self.keys if self.tracks else []
        obs_y = lp.obs([ys[f] for f in lp.fixed_order], [f"M.sload(v_ov, {k})" for k in keys])
        obs_x = lp.obs([self.fixed[f] for f in lp.fixed_order], [f"M.sload(o1, {k})" for k in keys])
        # the opened record's fixed fields rewritten to the context's, one at a time (outermost first)
        inner = self.after_loop_lemma(node.n, name, [r for _x, r in new_invs], conds)
        args = self.fixed_args() + "".join(f", v_{f}" for f in self.var_fields) + self.hb_arg()
        for j, (k, (_x, r)) in enumerate(zip(keys, new_invs)):
            gi = len(lp.fixed_order) + j
            args += (f", Equal.trans(M.W, M.sload(v_ov, {k}), M.sload(o1, {k}), {r}, Equal.cong({lp.O}, M.W, "
                     f"{lp.getter(gi)}, {obs_y}, {obs_x}, hy), i{j})")
        args += "".join(f", hc{q}" for q in range(len(conds)))
        body = f"{inner}({args})"
        fs = [ys[f] for f in self.fields]
        for i in range(len(lp.fixed_order) - 1, -1, -1):
            f = lp.fixed_order[i]
            at = self.fields.index(f)
            hole = [canon[q] if q < at and self.fields[q] in self.fixed else fs[q] for q in range(len(fs))]
            hole[at] = "_"
            rec = f"{X}{{{', '.join(hole)}}}"
            ty = self.types[at]
            eq = (f"Equal.sym({ty}, {ys[f]}, {self.fixed[f]}, Equal.cong({lp.O}, {ty}, {lp.getter(i)}, {obs_y}, "
                  f"{obs_x}, hy))")
            body = f"(%{eq} : {self.goal(f'M.la_{self.ab}_{node.n}(M.u_nz(v_cd), {rec})')}\n      {body})"
        ip = "".join(f", +i{j}: {{M.sload(o1, {k}) == {r} : M.W}}" for j, (k, (_x, r)) in enumerate(zip(keys, new_invs)))
        pat = f"{X}{{{', '.join('+' + ys[f] for f in self.fields)}}}"
        self.defs.append(f"def {name}({self.fixed_params()}, +o1: M.HSt, y: {X}{self.hb_param()}{ip}"
                         f"{self.carried_params(conds)}, +hy: {{{lp.ob}(st{lp.xa}, y) == {obs_x} : {lp.O}}}) -> "
                         f"{self.goal(f'M.la_{self.ab}_{node.n}(M.u_nz(M.gx_{self.ab}_cd(y)), y)')}:\n"
                         f"  match y:\n    case {pat}:\n      {body}\n")
        ls = f"M.ls_{self.ab}_{node.L}({X}{{{', '.join(node.rec.fields)}}})"
        y = f"M.lp_{self.ab}_{node.L}({node.fuel}, {node.d}, {ls})"
        hy = f"{lp.lp}({node.fuel}, {node.d}, st{lp.xa}, {ls}, {lp.ob}(st{lp.xa}, {ls}), {{==}})"
        call = f"{name}({self.fixed_args()}, {vals['ov']}, {y}{self.hb_arg()}"
        call += "".join(f", {x}" for x, _r in new_invs) + "".join(f", {x}" for x, _c in carried) + f", {hy})"
        return call

    def after_loop_lemma(self, n: int, name: str, refs: list, conds: list = ()) -> str:
        """The lemma of la_<a>_<n> on the opened, rewritten record (its varying fields v_<f>; refs: the words at B's
        keys the overlay holds; conds: the passed checks carried): a statement lemma for the loop statement's exit."""
        nm = f"{name}a"
        rec = [self.fixed[f] if f in self.fixed else f"v_{f}" for f in self.fields]
        node = self.mi.after_loop(n, Record(f"X_{self.ab}", rec))
        invs = [(f"inv{j}", r) for j, r in enumerate(refs)] if self.tracks else []
        body = self.emit(node, {f: f"v_{f}" for f in self.var_fields}, invs,
                         carried=tuple((f"hc{q}", c) for q, c in enumerate(conds)))
        ip = "".join(f", +inv{j}: {{M.sload(v_ov, {kk}) == {r} : M.W}}" for j, ((_x, r), kk) in
                     enumerate(zip(invs, self.keys)))
        self.defs.append(f"def {nm}({self.fixed_params()}{self.var_params()}{self.hb_param()}{ip}"
                         f"{self.carried_params(conds)}) -> "
                         f"{self.goal(f'M.la_{self.ab}_{n}(M.u_nz(v_cd), M.X_{self.ab}{{{', '.join(rec)}}})')}:\n"
                         f"  {body}\n")
        return nm

    def loop_proof(self, L: int) -> "LoopProof":
        if L not in self.loops:
            lp = LoopProof(self.g, self.action, L, self.keys if self.tracks else [], f"{self.p}L{L}",
                           self.loop_extra if self.tracks else [])
            self.loops[L] = lp
            self.defs += lp.lemmas()
        return self.loops[L]


class LoopProof(ActionProof):
    """(I68, the loop frames L1) One loop lp_<a>_<L> of an action keeps the context's fixed fields (the store st, the
    arguments, the environment, the tables) and the word at each of the given keys of the overlay ov. Both are one
    observation ob(x) = Ob{st, ar, en, tables.., sload(ov, K)..} of the record, and the lemma is

      lp(f, d, x, o, h: {ob(x) == o}) : {ob(lp_<a>_<L>(f, d, x)) == o}

    by induction on the fuel f (a run out of fuel only sets the code), from one iteration's li(x, o, h) :
    {ob(li_<a>_<L>(x)) == o}. That one is the iteration stepped on the opened record: its head, the body's statement
    chain inside lb_<a>_<L> (statement lemmas whose goal is the observation of lb's result) and the exits, each leaf
    a record whose fixed fields are the context's and whose overlay keeps the words at the keys (frames by
    evaluation, as the frame route: a store at one of the keys is refused). Nothing here names a target."""

    def __init__(self, g: Gen, action: str, L: int, keys: list, prefix: str, extra: list = ()):
        self._common(g, action, "loop", prefix)
        self.tag = None
        # variables the keys mention besides st (I68, tag_exact's step key k): parameters of every lemma and of ob
        self.xp = "".join(f", +{n}: {t}" for n, t in extra)
        self.xa = "".join(f", {n}" for n, _t in extra)
        self.time = False
        self.T = "t"
        self.L = L
        # the keys as terms of s0, the context's pre-state (a key that reads B's earlier keys reads st, I68), so that
        # the iteration's lemmas keep them fixed whatever the record's own store field is called
        self.keys = [re.sub(r"(?<![\w.])st(?![\w{])", "s0", k) for k in keys]
        self.fixed_order = [f for f in self.fields if f in self.fixed]
        self.O = f"Ob_{prefix}"
        self.ob = f"ob_{prefix}"
        self.lb = f"M.lb_{self.ab}_{L}"
        self.lp = f"{prefix}_lp"
        for part in ("li", "lb", "ls"):
            if f"{part}_{self.ab}_{L}" not in self.mi.defs:
                raise NoProof(f"{action}: its loop {L} has no {part}_{self.ab}_{L}")

    # the observation and its parts
    def obs(self, fixed_vals: list, key_vals: list) -> str:
        return f"{self.O}{{{', '.join(list(fixed_vals) + list(key_vals))}}}"

    def getter(self, i: int) -> str:
        return f"{self.ob}_g{i}"

    def ref(self) -> str:
        """The observation the iteration keeps: the context's fixed fields and the words at the keys of o0."""
        return self.obs([self.fixed[f] for f in self.fixed_order], [f"M.sload(o0, {k})" for k in self.keys])

    # ActionProof's text pieces, without B
    def hb_param(self) -> str:
        return ""

    def hb_arg(self) -> str:
        return ""

    def fixed_params(self) -> str:
        return f"+st: M.HSt, +ar: M.AR_{self.ab}, +e: M.HEnv{self.g.tparams}, +o0: M.HSt, +s0: M.HSt{self.xp}"

    def fixed_args(self) -> str:
        return f"st, ar, e{self.g.targs}, o0, s0{self.xa}"

    def goal(self, x: str) -> str:
        """The observation of x, or of lb's result for a term of the body's statement chain."""
        head = re.match(r"M\.(\w+)\(", x.strip())
        own = head is not None and head.group(1).startswith(tuple(f"{q}_{self.ab}_" for q in LOOP_PARTS))
        t = x if own else f"{self.lb}({x})"
        return f"{{{self.ob}(s0{self.xa}, {t}) == {self.ref()} : {self.O}}}"

    def emit(self, node, cur: dict, invs: list, nonzero: str | None = None, carried: tuple = ()) -> str:
        if isinstance(node, Next):    # the body's chain (in lb: its result goes through the loop's exit)
            vals = self.check_fixed(node.fields)
            new_invs = self.frame_invs(cur["ov"], vals["ov"], invs)
            return self.call(self.stmt(node.j, tuple(r for _x, r in new_invs)), vals, new_invs)
        if isinstance(node, Final):   # the body's chain ended: lb on its record
            return self.emit(self.mi.apply(self.lb[2:], [Record(f"X_{self.ab}", node.fields)]), cur, invs)
        if isinstance(node, Record):  # an iteration's end: the observation of the record
            return self.leaf(node.fields, cur, invs)
        if isinstance(node, Loop):
            raise NoProof(f"{self.action}: a loop inside its loop {self.L}")
        return super().emit(node, cur, invs, nonzero)   # a branch (no convoy in a loop body)

    def leaf(self, fields: list, cur: dict, invs: list) -> str:
        vals = self.check_fixed(fields)
        new_invs = self.frame_invs(cur["ov"], vals["ov"], invs)
        ov = vals["ov"]
        n = len(self.keys)
        want = [r for _x, r in new_invs]
        fx = [self.fixed[f] for f in self.fixed_order]
        body = "{==}"
        for j in range(n - 1, -1, -1):
            comps = want[:j] + ["_"] + [f"M.sload({ov}, {self.keys[q]})" for q in range(j + 1, n)]
            body = (f"(%Equal.sym(M.W, M.sload({ov}, {self.keys[j]}), {want[j]}, {new_invs[j][0]}) : "
                    f"{{{self.obs(fx, comps)} == {self.ref()} : {self.O}}}\n      {body})")
        return body

    def lemmas(self) -> list:
        """The observation type, its getters, the iteration's lemmas and the fuel induction."""
        X = f"M.X_{self.ab}"
        tys = [self.types[self.fields.index(f)] for f in self.fixed_order] + ["M.W"] * len(self.keys)
        names = [f"x_{f}" for f in self.fields]
        pat = f"{X}{{{', '.join('+' + v for v in names)}}}"
        comps = [f"x_{f}" for f in self.fixed_order] + [f"M.sload(x_ov, {k})" for k in self.keys]
        out = [f"type {self.O} is Data:\n  {self.O}{{{', '.join(f'f{i}: {t}' for i, t in enumerate(tys))}}}\n",
               f"def {self.ob}(+s0: M.HSt{self.xp}, r: {X}) -> {self.O}:\n  match r:\n    case {pat}:\n      {self.obs(comps[:len(self.fixed_order)], comps[len(self.fixed_order):])}\n"]
        gs = ", ".join(f"+a{i}" for i in range(len(tys)))
        for i, t in enumerate(tys):
            out.append(f"def {self.getter(i)}(o: {self.O}) -> {t}:\n  match o:\n    case {self.O}{{{gs}}}:\n      a{i}\n")
        # one iteration from the opened record: li's head, the body's chain in lb, the exits
        rec = [self.fixed[f] if f in self.fixed else f"v_{f}" for f in self.fields]
        top = f"{self.p}_top"
        node = self.mi.apply(f"li_{self.ab}_{self.L}", [Record(f"X_{self.ab}", rec)])
        invs = [(f"inv{j}", f"M.sload(o0, {k})") for j, k in enumerate(self.keys)]
        body = self.emit(node, {f: f"v_{f}" for f in self.var_fields}, invs)
        ip = "".join(f", +inv{j}: {{M.sload(v_ov, {k}) == M.sload(o0, {k}) : M.W}}" for j, k in enumerate(self.keys))
        self.defs.append(f"def {top}({self.fixed_params()}{self.var_params()}{ip}) -> "
                         f"{self.goal(f'M.li_{self.ab}_{self.L}({X}{{{', '.join(rec)}}})')}:\n  {body}\n")
        xrec = f"{X}{{{', '.join(names)}}}"
        targs = "".join(f", x_{n}" for n in self.g.tabs)
        call = (f"{top}(x_st, x_ar, x_en{targs}, x_ov, s0{self.xa}" + "".join(f", x_{f}" for f in self.var_fields)
                + ", {==}" * len(self.keys) + ")")
        s0x = f"s0{self.xa}"
        li = (f"def {self.p}_li(+s0: M.HSt{self.xp}, +x: {X}, +o: {self.O}, h: {{{self.ob}({s0x}, x) == o : {self.O}}}) -> "
              f"{{{self.ob}({s0x}, M.li_{self.ab}_{self.L}(x)) == o : {self.O}}}:\n  match x:\n    case {pat}:\n"
              f"      Equal.trans({self.O}, {self.ob}({s0x}, M.li_{self.ab}_{self.L}({xrec})), {self.ob}({s0x}, {xrec}), o, "
              f"{call}, h)\n")
        ld = f"M.gx_{self.ab}_ld{self.L}"
        if f"gx_{self.ab}_ld{self.L}" not in self.mi.defs:
            raise NoProof(f"{self.action}: its loop {self.L} has no direction field ld{self.L}")
        lp = (f"def {self.lp}(f: Nat, +d: Nat, +s0: M.HSt{self.xp}, +x: {X}, +o: {self.O}, h: {{{self.ob}({s0x}, x) == o : "
              f"{self.O}}}) -> {{{self.ob}({s0x}, M.lp_{self.ab}_{self.L}(f, d, x)) == o : {self.O}}}:\n"
              f"  match f:\n    case 0n:\n      match d:\n        case 0n:\n          h\n        case 1n+q:\n"
              f"          match q:\n            case 0n:\n              match x:\n                case {pat}:\n"
              f"                  h\n            case 1n+s:\n              h\n"
              f"    case 1n+r:\n      match d:\n        case 0n:\n          h\n        case 1n+q:\n"
              f"          match q:\n            case 0n:\n"
              f"              {self.lp}(r, {ld}(M.li_{self.ab}_{self.L}(x)), {s0x}, M.li_{self.ab}_{self.L}(x), o, "
              f"{self.p}_li({s0x}, x, o, h))\n            case 1n+s:\n              h\n")
        return out + self.defs + [li, lp]


# ------------------------------------------------------------------------------------------------ time monotonicity
NOT_LEMMAS = ("def not_t(+x: Bool, e: {Bool.not(x) == True{} : Bool}) -> {x == False{} : Bool}:\n  match x:\n"
              "    case True{}:\n      efq({True{} == False{} : Bool}, false_ne_true(e))\n    case False{}:\n      {==}\n\n"
              "def f_not(+x: Bool, e: {x == False{} : Bool}) -> {Bool.not(x) == True{} : Bool}:\n  match x:\n"
              "    case True{}:\n      efq({Bool.not(True{}) == True{} : Bool}, true_ne_false(e))\n    case False{}:\n"
              "      {==}\n")


def _has_t(code: str) -> bool:
    return re.search(r"(?<![\w.])t(?![\w{])", code) is not None


def _sub_def(model_text: str, name: str):
    """(F, G) when the typed model defines name(a, b) as a signed difference S{w_lt(F(a), G(b)), w_sub(F(a), G(b))}."""
    m = re.search(rf"(?m)^def {re.escape(name)}\(\+a: \w+, \+b: \w+\) -> (\w+):\n  \1\{{w_lt\((\w+)\(a\), (\w+)\(b\)\), "
                  rf"w_sub\(\2\(a\), \3\(b\)\)\}}$", model_text)
    return (m.group(2), m.group(3)) if m else None


class TimeMono:
    """Time monotonicity for one blocked condition (BUILD_PLAN I31, the contract's "time monotonicity"): B at t and
    t <= t2 give B at t2, for a B whose clock atoms rise with time (D9: sign(B, time) is + for a state conjunct). Each
    clock atom gets a one-step proof from the word-order lemmas (holon.disch.order); the lemma tl_<n> combines them by
    cases on B's atoms. An atom form the route does not know is refused (named)."""

    def __init__(self, g: Gen, tag: str, name: str):
        self.g, self.tag, self.name = g, tag, name
        self.defs: list = []
        code = g.sec.blk[tag]["code"]
        atoms: list = []
        sk = skeleton(code, atoms)
        self.atoms = atoms
        self.tidx = [i for i, a in enumerate(atoms) if _has_t(a)]
        if not self.tidx:
            raise NoProof("time monotonicity: B reads no clock")
        # names: v<i> for every atom at t; w<i> for a clock atom at t2
        self.sk1 = sk
        self.sk2 = re.sub(r"(?<![\w.])v(\d+)", lambda m: f"w{m.group(1)}" if int(m.group(1)) in self.tidx else m.group(0), sk)
        self.monos = [self.mono(atoms[i], i) for i in self.tidx]
        self.defs.append(self.lemma())

    def mono(self, atom: str, i: int) -> tuple:
        """(direction, proof) of one clock atom, t written @T@ and t2 @T2@ (hle: {M.w_le(t, t2) == True} in scope):
        "up" when the atom rises with time (h: {atom(t) == True} gives {atom(t2) == True}), "down" when it falls (h:
        {atom(t2) == True} gives {atom(t) == True}); the proof is a function of h."""
        a = atom.strip()
        A1, A2 = at_time(a, "@T@"), at_time(a, "@T2@")
        c = as_call(a)
        le = "not_t(M.w_lt(@T2@, @T@), hle)"          # {w_lt(t2, t) == False}
        if c and c[2] == "(" and len(c[1]) == 2 and c[0] in ("M.w_lt", "M.w_gt", "M.w_le", "M.w_ge"):
            x, y = c[1][0].strip(), c[1][1].strip()
            if c[0] in ("M.w_gt", "M.w_ge"):
                x, y = y, x                     # w_gt(a, b) is w_lt(b, a); w_ge(a, b) is w_le(b, a)
            strict = c[0] in ("M.w_lt", "M.w_gt")
            if y == "t" and not _has_t(x):      # x < t, x <= t: rising
                if strict:
                    return "up", f"h => w_lt_le({x}, @T@, @T2@, h, {le})"
                return "up", (f"h => f_not(M.w_lt(@T2@, {x}), w_le_le({x}, @T@, @T2@, not_t(M.w_lt(@T@, {x}), h), "
                              f"{le}))")
            if x == "t" and not _has_t(y):      # t < y, t <= y: falling
                if strict:
                    return "down", f"h => w_le_lt(@T@, @T2@, {y}, {le}, h)"
                return "down", (f"h => f_not(M.w_lt({y}, @T@), w_le_le(@T@, @T2@, {y}, {le}, not_t(M.w_lt({y}, @T2@), "
                                f"h)))")
        # A >= t as a signed difference that realizes: is_some(realize(sub(A, T{t}))): falling
        m = re.fullmatch(r"M\.is_some_(\w+)\(M\.realize_(\w+)\(M\.sub_(\w+)\((.*), M\.(\w+)\{t\}\)\)\)", a)
        if m:
            fg = _sub_def(self.g.text, f"sub_{m.group(3)}")
            arg = m.group(4).strip()
            if fg and not _has_t(arg) and len(split_top(arg)) == 1:
                F = f"M.{fg[0]}({arg})"
                tz = f"tz_{m.group(1)}_{m.group(2)}"
                if not any(d.startswith(f"def {tz}(") for d in self.defs):
                    self.defs.append(f"def {tz}(c: Bool, +p: M.W) -> {{M.is_some_{m.group(1)}(M.rzg_{m.group(2)}(c, p)) "
                                     f"== Bool.not(c) : Bool}}:\n  match c:\n    case True{{}}:\n      {{==}}\n"
                                     f"    case False{{}}:\n      {{==}}\n")
                e1 = f"{tz}(M.w_lt({F}, @T@), M.w_sub({F}, @T@))"        # {A1 == not(w_lt(F, t))}
                e2 = f"{tz}(M.w_lt({F}, @T2@), M.w_sub({F}, @T2@))"      # {A2 == not(w_lt(F, t2))}
                n2 = (f"Equal.trans(Bool, Bool.not(M.w_lt({F}, @T2@)), {A2}, True{{}}, Equal.sym(Bool, {A2}, "
                      f"Bool.not(M.w_lt({F}, @T2@)), {e2}), h)")
                f1 = f"w_le_le(@T@, @T2@, {F}, {le}, not_t(M.w_lt({F}, @T2@), {n2}))"
                return "down", (f"h => Equal.trans(Bool, {A1}, Bool.not(M.w_lt({F}, @T@)), True{{}}, {e1}, "
                                f"f_not(M.w_lt({F}, @T@), {f1}))")
        raise NoProof(f"time monotonicity: a clock atom of B has a form the route does not know: {a[:160]}")

    def lemma(self) -> str:
        n = len(self.atoms)
        vs = [f"v{i}" for i in range(n)] + [f"w{i}" for i in self.tidx]
        dirs = dict(zip(self.tidx, (d for d, _p in self.monos)))
        ms = "".join((f", m{i}: {{v{i} == True{{}} : Bool}} -> {{w{i} == True{{}} : Bool}}" if dirs[i] == "up" else
                      f", m{i}: {{w{i} == True{{}} : Bool}} -> {{v{i} == True{{}} : Bool}}") for i in self.tidx)
        head = (f"def {self.name}(" + "".join(f"{v}: Bool, " for v in vs) + f"hb: {{{self.sk1} == True{{}} : Bool}}{ms}) "
                f"-> {{{self.sk2} == True{{}} : Bool}}:\n  match {' '.join(vs)}:\n")
        rows = []
        for vals in itertools.product([True, False], repeat=len(vs)):
            val = dict(zip(vs, vals))
            v1 = {i: val[f"v{i}"] for i in range(n)}
            v2 = {i: (val[f"w{i}"] if i in self.tidx else val[f"v{i}"]) for i in range(n)}
            pat = " ".join("True{}" if x else "False{}" for x in vals)
            goal = "{%s == True{} : Bool}" % re.sub(r"(?<![\w.])([vw]\d+)", lambda mm: "True{}" if val[mm.group(1)] else
                                                      "False{}", self.sk2)
            bad = [i for i in self.tidx if (val[f"v{i}"] and not val[f"w{i}"] if dirs[i] == "up" else
                                            val[f"w{i}"] and not val[f"v{i}"])]
            if not _bev(self.sk1, v1):
                body = f"efq({goal}, false_ne_true(hb))"
            elif bad:
                body = f"efq({goal}, false_ne_true(m{bad[0]}({{==}})))"
            elif _bev(self.sk1, v2):
                body = "{==}"
            else:
                raise NoProof("time monotonicity: B falls with time on a case of its atoms (not a rising condition)")
            rows.append(f"    case {pat}:\n      {body}")
        return head + "\n".join(rows) + "\n"

    def call(self, st_t: str, T2: str, hb: str) -> str:
        """{blk(st, T2) == True} from hb: {blk(st, t) == True} (hle in scope)."""
        a1 = [a for a in self.atoms]
        a2 = [at_time(self.atoms[i], T2) for i in self.tidx]
        monos = [m.replace("@T@", st_t).replace("@T2@", T2) for _d, m in self.monos]
        return f"{self.name}({''.join(x + ', ' for x in a1 + a2)}{hb}{''.join(', ' + m for m in monos)})"


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
    T = "D.d_time(e)"
    tm = None
    if g.sec.blk[tag]["time"]:
        # time monotonicity: B at the premise's t, with t <= time(e), gives B at time(e), where every route states it
        tm = TimeMono(g, tag, "tl_blk")
        defs += tm.defs + ([] if g.sk else [NOT_LEMMAS])   # (the structural library holds not_t and f_not)
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
        else:   # external_none: after the step B still holds (frame, transport) or the step reverts (the state is
            # kept, where B holds); either way c does not hold there, B and c being contradictory
            b_code, c_code = g.sec.blk[tag]["code"], g.sec.chk[tag]
            if tm is not None:
                b_code, c_code = at_time(b_code, T), at_time(c_code, T)
            r = contradicts(b_code, c_code)
            if r is None:
                raise NoProof(f"{act}: B and c are not contradictory by cases on their atoms")
            atoms, sb, sc, imps = r
            defs.append(nb_lemma(f"{p}_nbc", atoms, sb, sc, imps))
            if "not_of" not in "".join(defs):
                defs.append(NOT_OF)
            if route == "chain_revert":
                defs.append(go_rev_lemma(g, ab, f"{p}_go"))
                xr = f"M.xr_{ab}(st, ar, e{g.targs})"
                notc = (f"not_of(D.chk_{tag}(st, {T}{g.targs}), ec => {p}_nbc({''.join(a + ', ' for a in atoms)}hb, ec"
                        f"{imp_args(imps)}))")
                concl = (f"(%Equal.sym(M.GSt, M.gh_go_{ab}({xr}, {G}), {G}, {p}_go({xr}, {G}, {term})) : "
                         f"{{Bool.not(D.chk_{tag}(M.gh_get_st(_), {T}{g.targs})) == True{{}} : Bool}}\n  {notc})")
            else:   # the route's term: B in the post-state; the atoms over it
                post = f"M.gh_get_st(M.gh_step(D.d_env(M.A_{ab}{{ar, en}}, e), {G}{g.targs}))"
                on_post = lambda x: re.sub(r"(?<![\w.])st(?![\w{])", lambda _m: post, x)   # noqa: E731
                pimps = [(i, j, on_post(pr)) for i, j, pr in imps]
                concl = (f"not_of(D.chk_{tag}({post}, {T}{g.targs}), ec => {p}_nbc("
                         f"{''.join(on_post(a) + ', ' for a in atoms)}{term}, ec{imp_args(pimps)}))")
        member = "True{}" if sf == "revert" or act not in pred_actions else g.sec.perm_code(act)
        rest = f"Bool.and(D.blk_{tag}(st, t{g.targs}), M.w_le(t, {T}))"
        hsrc = "h" if member == "True{}" else f"and_r({member}, {rest}, h)"
        hb = f"and_l(D.blk_{tag}(st, t{g.targs}), M.w_le(t, {T}), {hsrc})"
        if tm is not None:     # B at time(e) (the routes' hypothesis) from B at t and t <= time(e)
            hle = f"and_r(D.blk_{tag}(st, t{g.targs}), M.w_le(t, {T}), {hsrc})"
            lets = f"  +hb0 = {hb}\n  +hle = {hle}\n  +hb = {tm.call('t', T, 'hb0')}\n"
        else:
            lets = f"  +hb = {hb}\n"
        aterm = f"M.A_{ab}{{ar, en}}"
        wn = f"{p}_w"
        defs.append(f"def {wn}(+st: M.HSt{g.g_params()}, +ar: M.AR_{ab}, +en: M.HEnv, +t: M.W, +e: M.HEnv"
                    f"{g.tparams}, +h: {{D.prem_{x}({aterm}, {G}, t, e{g.targs}) == True{{}} : Bool}}) -> "
                    f"{{D.concl_{x}({aterm}, {G}, e{g.targs}) == True{{}} : Bool}}:\n{lets}  {concl}\n")
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
            f"# routes: {', '.join(f'{k}: {v}' for k, v in sorted(routes.items()))}"
            + ("; time monotonicity" if tm is not None else ""), library(g.sk), ORDER.text("M.", g.sk)]
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
