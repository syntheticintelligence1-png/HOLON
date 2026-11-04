"""K5's sections over the members' raw models: the Bend module that gives a member's tau and sentinel laws their meaning,
one per member, importing the member's bundle model (gen/<M>/bundle/models/<member>.bend) as M.

  gen/<M>/symb/sections/<member>.bend

What a section defines (M's types: HSt{sl: List<KW{k, v}>}, HAct = A_<action>{ar, en}, HOut{c, rv, po, lg, tw}, the hash
table List<HKB{b, v}>):

  sy_tk(kh, k)          a store key is a Time key: some hash-table entry gives k as the keccak256 of a 64-byte preimage
                        (a map key, then the map's base slot) whose base slot is one of the member's Time maps (K2)
  sy_tst(kh, s, d)      tau_d on a state: every Time word the store holds plus d; a key the store does not hold is not
                        translated (holon.gen.symsec's documented limit, kept by K5)
  sy_ten(en, d)         tau_d on an environment: block.timestamp plus d (no call answer of a member action is Time-sorted
                        under K2, so the recorded answers are unchanged)
  sy_fits_*             fits64: every Time word of the state and the environment, d, and their sums below 2^64
  sy_out_eq(a, b)       two runs agree: outcome code, return or revert data, logs, and every key either post-state holds
  sy_tout(kh, o, d, t)  tau_d on a run: its post-state, and its return word when t (the action's return term is Time, K2)
                        and the run succeeds with one word of return data (K5)
  sy_ok_<n>, sy_hit_<n> a tau law's claim (the premises imply that tau_d commutes with the step) and its premises alone
  sn_ok_<n>, sn_hit_<n> a sentinel law's claim (the act succeeds and block.timestamp >= 1, a nonzero word, imply that the
                        site's value is not the register's constant) and its premises alone
  sy_flip_<n>_<i>       a tau law's comparison site i decides differently on (s, x) and (tau_d s, tau_d x)
  sn_inv_<n>            a sentinel invariant's predicate on a state (the view's other conjunct implies R != c)

The versioned member (gen/<M>/symb/versioned/<member>.bend) and the link (gen/<M>/symb/link/<member>.bend) are written
by the same step (versioned_module, link_module).

Nothing here names a target: actions, registers, slots and sorts come from the member's document, its sorts
(gen/<M>/symb/sorts.json) and the model text.
"""
from __future__ import annotations

import re

W_ZERO = "M.W{0, 0, 0, 0, 0, 0, 0, 0}"


def wlit(n: int) -> str:
    """A W literal: eight little-endian 32-bit limbs."""
    limbs = [(n >> (32 * i)) & 0xFFFFFFFF for i in range(8)]
    return "M.W{" + ", ".join(str(x) for x in limbs) + "}"


def bname(n: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", n)


def data_fields(model_text: str, tname: str) -> list[str]:
    """The field names of a one-constructor data type `type T is Data:\\n  T{f: ty, ...}`."""
    m = re.search(rf"^type {re.escape(tname)} is Data:\n  {re.escape(tname)}\{{(.*)\}}$", model_text, re.M)
    if not m:
        raise ValueError(f"the model defines no one-constructor type {tname}")
    out, depth, cur = [], 0, ""
    for ch in m.group(1):
        if ch in "<{(":
            depth += 1
        elif ch in ">})":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return [f.split(":", 1)[0].strip() for f in out]


def act_constructors(model_text: str) -> list[str]:
    """HAct's constructors, in the model's order (A_<action>)."""
    m = re.search(r"^type HAct is Data:\n((?:  A_\w+\{[^\n]*\}\n)+)", model_text, re.M)
    if not m:
        raise ValueError("the model defines no HAct")
    return re.findall(r"^  (A_\w+)\{", m.group(1), re.M)


def time_bases(doc: dict, sorts: dict) -> list[int]:
    """The base slots of the member's Time maps: the storage families K2 sorts Time whose layout is a mapping."""
    fams = {p.split(".")[0] for p in sorts.get("time") or []}
    out = []
    for s in doc["storage"]:
        if s["name"] in fams and s.get("kind") == "mapping":
            out.append(int(s["slot"]))
    return sorted(out)


class Section:
    """One member's section. laws: [(n, kind, action, extra)], kind "tau" (extra: the return term is Time) or
    "sentinel" (extra: (the site's value term, the register's constant))."""

    def __init__(self, member: str, model_import: str, model_text: str, doc: dict, sorts: dict):
        self.member, self.model_import, self.text, self.doc, self.sorts = member, model_import, model_text, doc, sorts
        self.env_fields = data_fields(model_text, "HEnv")
        if "e_block_timestamp" not in self.env_fields:
            raise ValueError(f"{member}: the model's environment has no block.timestamp")
        self.acts = act_constructors(model_text)
        self.bases = time_bases(doc, sorts)
        self.defs: list[str] = []

    def add(self, s: str) -> None:
        self.defs.append(s.rstrip("\n") + "\n")

    # ------------------------------------------------------------------------------------------------- the prelude
    def prelude(self) -> None:
        base = "False{}"
        for b in reversed(self.bases):
            base = f"Bool.or(M.w_eq(b, {wlit(b)}), {base})" if base != "False{}" else f"M.w_eq(b, {wlit(b)})"
        self.add(f"# the base slots of the member's Time maps (K2): {self.bases}\n"
                 f"def sy_tbase(+b: M.W) -> Bool:\n  {base}\n")
        self.add("def sy_pre_tk_at(c: Bool, +bs: List<&2, U32>) -> Bool:\n"
                 "  match c:\n    case True{}:\n      sy_tbase(M.b_word(bs, 32n))\n    case False{}:\n      False{}\n")
        self.add("def sy_pre_tk(+bs: List<&2, U32>) -> Bool:\n"
                 "  sy_pre_tk_at(U32.is_eq(U32.from_nat(List.length(&2, U32, bs)), 64), bs)\n")
        self.add("# a store key is a Time key: a hash-table entry gives it from a map key and a Time map's base slot\n"
                 "def sy_tk(kh: List<&2, M.HKB>, +k: M.W) -> Bool:\n"
                 "  match kh:\n    case Nil{}:\n      False{}\n    case Con{h, t}:\n"
                 "      match h:\n        case M.HKB{b, v}:\n"
                 "          Bool.or(Bool.and(M.w_eq(v, k), sy_pre_tk(b)), sy_tk(t, k))\n")
        self.add("def sy_tv(c: Bool, +v: M.W, +d: M.W) -> M.W:\n"
                 "  match c:\n    case True{}:\n      M.w_add(v, d)\n    case False{}:\n      v\n")
        self.add("def sy_tkws(+kh: List<&2, M.HKB>, xs: List<&2, M.KW>, +d: M.W) -> List<&2, M.KW>:\n"
                 "  match xs:\n    case Nil{}:\n      Nil{}\n    case Con{h, t}:\n"
                 "      match h:\n        case M.KW{+k, v}:\n"
                 "          Con{M.KW{k, sy_tv(sy_tk(kh, k), v, d)}, sy_tkws(kh, t, d)}\n")
        self.add("# tau_d on a state (K5): the Time words the store holds; an absent key is not translated\n"
                 "def sy_tst(+kh: List<&2, M.HKB>, s: M.HSt, +d: M.W) -> M.HSt:\n"
                 "  match s:\n    case M.HSt{sl}:\n      M.HSt{sy_tkws(kh, sl, d)}\n")
        fs = self.env_fields
        pat = ", ".join(("+" + f) if f == "e_block_timestamp" else f for f in fs)
        out = ", ".join("M.w_add(e_block_timestamp, d)" if f == "e_block_timestamp" else f for f in fs)
        self.add("# tau_d on an environment: block.timestamp plus d\n"
                 f"def sy_ten(en: M.HEnv, +d: M.W) -> M.HEnv:\n  match en:\n    case M.HEnv{{{pat}}}:\n"
                 f"      M.HEnv{{{out}}}\n")
        two64 = wlit(1 << 64)
        self.add(f"def sy_fit(+v: M.W, +d: M.W) -> Bool:\n"
                 f"  Bool.and(M.w_lt(v, {two64}), Bool.and(M.w_lt(d, {two64}), M.w_lt(M.w_add(v, d), {two64})))\n")
        self.add("def sy_fits_kws(+kh: List<&2, M.HKB>, xs: List<&2, M.KW>, +d: M.W) -> Bool:\n"
                 "  match xs:\n    case Nil{}:\n      True{}\n    case Con{h, t}:\n"
                 "      match h:\n        case M.KW{+k, +v}:\n"
                 "          Bool.and(Bool.or(Bool.not(sy_tk(kh, k)), sy_fit(v, d)), sy_fits_kws(kh, t, d))\n")
        self.add("def sy_fits_st(+kh: List<&2, M.HKB>, s: M.HSt, +d: M.W) -> Bool:\n"
                 "  match s:\n    case M.HSt{sl}:\n      sy_fits_kws(kh, sl, d)\n")
        self.add("def sy_fits_en(+en: M.HEnv, +d: M.W) -> Bool:\n  sy_fit(M.ge_e_block_timestamp(en), d)\n")
        self.add("# every key of xs reads the same word in s\n"
                 "def sy_kws_in(xs: List<&2, M.KW>, +s: M.HSt) -> Bool:\n"
                 "  match xs:\n    case Nil{}:\n      True{}\n    case Con{h, t}:\n"
                 "      match h:\n        case M.KW{+k, v}:\n"
                 "          Bool.and(M.w_eq(M.sload(s, k), v), sy_kws_in(t, s))\n")
        self.add("def sy_st_eq(+a: M.HSt, +b: M.HSt) -> Bool:\n"
                 "  match a b:\n    case M.HSt{xa} M.HSt{xb}:\n"
                 "      Bool.and(sy_kws_in(xa, b), sy_kws_in(xb, a))\n")
        self.add("def sy_ws_eq(a: List<&2, M.W>, b: List<&2, M.W>) -> Bool:\n"
                 "  match a b:\n    case Nil{} Nil{}:\n      True{}\n    case Nil{} Con{y, ys}:\n      False{}\n"
                 "    case Con{x, xs} Nil{}:\n      False{}\n"
                 "    case Con{x, xs} Con{y, ys}:\n      Bool.and(M.w_eq(x, y), sy_ws_eq(xs, ys))\n")
        self.add("def sy_log_eq(a: M.HLog, b: M.HLog) -> Bool:\n"
                 "  match a b:\n    case M.HLog{t1, d1} M.HLog{t2, d2}:\n"
                 "      Bool.and(sy_ws_eq(t1, t2), M.b_eq(d1, d2))\n")
        self.add("def sy_logs_eq(a: List<&2, M.HLog>, b: List<&2, M.HLog>) -> Bool:\n"
                 "  match a b:\n    case Nil{} Nil{}:\n      True{}\n    case Nil{} Con{y, ys}:\n      False{}\n"
                 "    case Con{x, xs} Nil{}:\n      False{}\n"
                 "    case Con{x, xs} Con{y, ys}:\n      Bool.and(sy_log_eq(x, y), sy_logs_eq(xs, ys))\n")
        self.add("def sy_out_eq(a: M.HOut, b: M.HOut) -> Bool:\n"
                 "  match a b:\n    case M.HOut{c1, r1, p1, l1, t1} M.HOut{c2, r2, p2, l2, t2}:\n"
                 "      Bool.and(U32.is_eq(c1, c2), Bool.and(M.b_eq(r1, r2), Bool.and(sy_logs_eq(l1, l2), "
                 "sy_st_eq(p1, p2))))\n")
        self.add("def sy_trv_at(k: Bool, +rv: List<&2, U32>, +d: M.W) -> List<&2, U32>:\n"
                 "  match k:\n    case True{}:\n      M.b_of_w(M.w_add(M.b_word(rv, 0n), d))\n    case False{}:\n      rv\n")
        self.add("# tau_d on a run: the post-state, and the return word when t, the run succeeds and returns one word\n"
                 "def sy_trv(t: Bool, +c: U32, +rv: List<&2, U32>, +d: M.W) -> List<&2, U32>:\n"
                 "  sy_trv_at(Bool.and(t, Bool.and(U32.is_eq(c, 0), "
                 "U32.is_eq(U32.from_nat(List.length(&2, U32, rv)), 32))), rv, d)\n")
        self.add("def sy_tout(+kh: List<&2, M.HKB>, o: M.HOut, +d: M.W, t: Bool) -> M.HOut:\n"
                 "  match o:\n    case M.HOut{+c, +rv, po, lg, tw}:\n"
                 "      M.HOut{c, sy_trv(t, c, rv, d), sy_tst(kh, po, d), lg, tw}\n")
        # the act dispatchers, one arm per constructor
        arms_is = lambda hit: "".join(  # noqa: E731
            f"    case M.{c}{{ar, en}}:\n      {'True{}' if c == hit else 'False{}'}\n" for c in self.acts)
        self._is_defs = {}
        arms_tx = "".join(f"    case M.{c}{{ar, en}}:\n      M.{c}{{ar, sy_ten(en, d)}}\n" for c in self.acts)
        arms_run = "".join(f"    case M.{c}{{ar, en}}:\n      M.run_{c[2:]}(s, ar, en, kh)\n" for c in self.acts)
        arms_en = "".join(f"    case M.{c}{{ar, en}}:\n      en\n" for c in self.acts)
        self.add(f"def sy_tx(x: M.HAct, +d: M.W) -> M.HAct:\n  match x:\n{arms_tx}")
        self.add(f"def sy_run(x: M.HAct, +s: M.HSt, +kh: List<&2, M.HKB>) -> M.HOut:\n  match x:\n{arms_run}")
        self.add(f"def sy_en(x: M.HAct) -> M.HEnv:\n  match x:\n{arms_en}")
        self._arms_is = arms_is

    def is_def(self, action: str) -> str:
        c = f"A_{bname(action)}"
        if c not in self.acts:
            raise ValueError(f"{self.member}: the model has no action {action}")
        name = f"sy_is_{bname(action)}"
        if name not in self._is_defs:
            self._is_defs[name] = True
            self.add(f"def {name}(x: M.HAct) -> Bool:\n  match x:\n{self._arms_is(c)}")
        return name

    # ------------------------------------------------------------------------------------------------- the laws
    def tau(self, n: int, lid: str, action: str, time_return: bool, ret_code: str | None = None) -> None:
        """A tau law. A view's return word (model3 writes no return data) is computed from its return term (ret_code,
        compiled by the member's generator over s, ar, en, kh) and compared too, translated when time_return (K5)."""
        isd = self.is_def(action)
        prem = f"Bool.and({isd}(x), Bool.and(sy_fits_st(kh, s, d), sy_fits_en(sy_en(x), d)))"
        eq = (f"sy_out_eq(sy_run(sy_tx(x, d), sy_tst(kh, s, d), kh), "
              f"sy_tout(kh, sy_run(x, s, kh), d, False{{}}))")
        if ret_code is not None:
            c = f"A_{bname(action)}"
            ar_t = f"M.AR_{bname(action)}"
            self.add(f"def sy_ret_{n}(+s: M.HSt, +ar: {ar_t}, +en: M.HEnv, +kh: List<&2, M.HKB>) -> M.W:\n"
                     f"  {ret_code}\n")
            arms = "".join(f"    case M.{k}{{ar, en}}:\n      "
                           f"{f'sy_ret_{n}(s, ar, en, kh)' if k == c else W_ZERO}\n" for k in self.acts)
            self.add(f"def sy_rw_{n}(x: M.HAct, +s: M.HSt, +kh: List<&2, M.HKB>) -> M.W:\n  match x:\n{arms}")
            want = f"M.w_add(sy_rw_{n}(x, s, kh), d)" if time_return else f"sy_rw_{n}(x, s, kh)"
            eq = f"Bool.and({eq}, M.w_eq(sy_rw_{n}(sy_tx(x, d), sy_tst(kh, s, d), kh), {want}))"
        self.add(f"# {lid}: tau_d commutes with a step of {action} (K5)\n"
                 f"def sy_ok_{n}(+s: M.HSt, +x: M.HAct, +d: M.W, +kh: List<&2, M.HKB>) -> Bool:\n"
                 f"  Bool.or(Bool.not({prem}), {eq})\n")
        self.add(f"def sy_hit_{n}(+s: M.HSt, +x: M.HAct, +d: M.W, +kh: List<&2, M.HKB>) -> Bool:\n  {prem}\n")

    def sentinel(self, n: int, lid: str, action: str, value_term, constant: int) -> None:
        """A sentinel site whose value term is block.timestamp (the Time sites): the act succeeds and its
        block.timestamp is at least 1 (a nonzero word) imply that the value is not the constant. For the constant 0 the
        claim is the value's non-zeroness itself, so that at the site's action the claim is ux(c, p) =
        Bool.or(Bool.not(Bool.and(c, p)), p) (holon.symb.lawrun's sentinel proof)."""
        if value_term != ["env", "block.timestamp"]:
            raise ValueError(f"{lid}: the member section states a sentinel site whose value is block.timestamp; "
                             f"{value_term!r} is the link's (K3)")
        isd = self.is_def(action)
        c = f"A_{bname(action)}"
        clock = "M.ge_e_block_timestamp(sy_en(x))"
        prem = (f"Bool.and({isd}(x), Bool.and(U32.is_eq(M.chk_{bname(action)}(s, sn_ar_{n}(x), sy_en(x), kh), 0), "
                f"M.w_nz({clock})))")
        concl = f"M.w_nz({clock})" if constant == 0 else f"Bool.not(M.w_eq({clock}, {wlit(constant)}))"
        arms = "".join(f"    case M.{k}{{ar, en}}:\n      {'ar' if k == c else f'sn_ar0_{n}()'}\n" for k in self.acts)
        ar_t = f"M.AR_{bname(action)}"
        self.add(f"def sn_ar0_{n}() -> {ar_t}:\n  {self._ar_zero(action)}\n")
        self.add(f"def sn_ar_{n}(x: M.HAct) -> {ar_t}:\n  match x:\n{arms}")
        self.add(f"# {lid}: the value the site writes is not the register's constant {constant} (K4)\n"
                 f"def sn_ok_{n}(+s: M.HSt, +x: M.HAct, +kh: List<&2, M.HKB>) -> Bool:\n"
                 f"  Bool.or(Bool.not({prem}), {concl})\n")
        self.add(f"def sn_hit_{n}(+s: M.HSt, +x: M.HAct, +kh: List<&2, M.HKB>) -> Bool:\n  {prem}\n")

    def cmp_sites(self, n: int, action: str, codes: list) -> None:
        """The comparison sites of a tau law's action (a Time-sorted term against a constant), each compiled by the
        member's generator: sy_cmp_<n>_<i> over (s, ar, en, kh), and sy_flip_<n>_<i>(s, x, d, kh), true when the site
        decides differently on (s, x) and on (tau_d s, tau_d x): the site a witness crosses (K6)."""
        c = f"A_{bname(action)}"
        ar_t = f"M.AR_{bname(action)}"
        if codes and "sy_xor" not in "".join(self.defs):
            self.add("def sy_xor(+a: Bool, +b: Bool) -> Bool:\n  Bool.or(Bool.and(a, Bool.not(b)), Bool.and(Bool.not(a), b))\n")
        for i, code in codes:
            self.add(f"def sy_cmp_{n}_{i}(+s: M.HSt, +ar: {ar_t}, +en: M.HEnv, +kh: List<&2, M.HKB>) -> Bool:\n"
                     f"  {code}\n")
            arms = "".join(f"    case M.{k}{{ar, en}}:\n      "
                           f"{f'sy_cmp_{n}_{i}(s, ar, en, kh)' if k == c else 'False{}'}\n" for k in self.acts)
            self.add(f"def sy_cmpx_{n}_{i}(x: M.HAct, +s: M.HSt, +kh: List<&2, M.HKB>) -> Bool:\n  match x:\n{arms}")
            self.add(f"def sy_flip_{n}_{i}(+s: M.HSt, +x: M.HAct, +d: M.W, +kh: List<&2, M.HKB>) -> Bool:\n"
                     f"  sy_xor(sy_cmpx_{n}_{i}(x, s, kh), sy_cmpx_{n}_{i}(sy_tx(x, d), sy_tst(kh, s, d), kh))\n")

    def invariant(self, n: int, lid: str, g_code: str, r_code: str) -> None:
        """A sentinel invariant's predicate on a state (K4): the view's other conjunct G implies R != c."""
        self.add(f"# {lid}: the view's other conjunct implies the sentinel register differs from its constant (K4)\n"
                 f"def sn_g_{n}(+s: M.HSt, +kh: List<&2, M.HKB>) -> Bool:\n  {g_code}\n")
        self.add(f"def sn_rne_{n}(+s: M.HSt, +kh: List<&2, M.HKB>) -> Bool:\n  {r_code}\n")
        self.add(f"def sn_inv_{n}(+s: M.HSt, +kh: List<&2, M.HKB>) -> Bool:\n"
                 f"  Bool.or(Bool.not(sn_g_{n}(s, kh)), sn_rne_{n}(s, kh))\n")

    def _ar_zero(self, action: str) -> str:
        """A literal argument record of the action (every field zero, a list empty), for the arms that are not its act;
        the premise's action test makes their value irrelevant."""
        tname = f"AR_{bname(action)}"
        m = re.search(rf"^type {tname} is Data:\n  {tname}\{{(.*)\}}$", self.text, re.M)
        if not m:
            raise ValueError(f"the model defines no {tname}")
        body = m.group(1).strip()
        if not body:
            return f"M.{tname}{{}}"
        vals = []
        for f in re.split(r",\s*(?![^<]*>)", body):
            ty = f.split(":", 1)[1].strip()
            vals.append(W_ZERO if ty == "W" else ("Nil{}" if ty.startswith("List") else "0n" if ty == "Nat" else
                                                  "False{}" if ty == "Bool" else W_ZERO))
        return f"M.{tname}{{{', '.join(vals)}}}"

    def text_out(self) -> str:
        head = (f"# GENERATED by holon.symb.sections (I92, K5) for the member {self.member}; do not edit.\n"
                f"import Base\nimport {self.model_import} as M\n\n")
        return head + "\n".join(self.defs)


# ---------------------------------------------------------------------------------------------------- the step
def _walk(e):
    if isinstance(e, list):
        yield e
        for x in e[1:] if e and isinstance(e[0], str) else e:
            yield from _walk(x)
    elif isinstance(e, dict):
        for x in e.values():
            yield from _walk(x)


def time_compares(a: dict, member: str, solver) -> list:
    """The comparisons of a Time-sorted term against an integer constant an action decides on, in document order and
    without repeats: [(term, src, where)] (where: guard, check, return or write)."""
    import json
    out, seen = [], set()

    def scan(e, src, where):
        for x in _walk(e):
            if len(x) == 3 and x[0] in ("==", "!=", "<", "<=", ">", ">="):
                for t, c in ((x[1], x[2]), (x[2], x[1])):
                    if isinstance(c, int) and not isinstance(c, bool) and solver.sort(member, t) == "time":
                        k = json.dumps(x, sort_keys=True)
                        if k not in seen:
                            seen.add(k)
                            out.append((x, src or a.get("src"), where))
                        break
    for g in a.get("guards") or []:
        scan(g.get("expr"), g.get("src"), "guard")
    for c in a.get("checks") or []:
        scan(c.get("expr"), c.get("src"), "check")
    if a.get("mutability") in ("view", "pure"):
        scan(a.get("returns"), a.get("src"), "return")
    for w in a.get("writes") or []:
        scan(w.get("cond"), w.get("src"), "write")
    return out


def _conj(e) -> list:
    if isinstance(e, list) and e[:1] == ["&&"]:
        return [y for x in e[1:] for y in _conj(x)]
    return [e]


def _qualify_ite(code: str, names: set, alias: str = "M") -> str:
    """qualify only qualifies a name before ( or {: ite's type argument is a model type too."""
    return re.sub(rf"(?<![\w.]){alias}\.ite\((\w+),",
                  lambda mt: f"{alias}.ite({alias + '.' if mt.group(1) in names else ''}{mt.group(1)},", code)


def _conv_defs(src: str, dst: str, name: str) -> list:
    """Word, store-pair and hash-table conversions from module src's records to module dst's (the same definitions)."""
    limbs = ", ".join(f"a{i}" for i in range(8))
    return [f"def {name}_w(w: {src}.W) -> {dst}.W:\n  match w:\n    case {src}.W{{{limbs}}}:\n      {dst}.W{{{limbs}}}\n",
            f"def {name}_kws(xs: List<&2, {src}.KW>) -> List<&2, {dst}.KW>:\n  match xs:\n    case Nil{{}}:\n      Nil{{}}\n"
            f"    case Con{{h, t}}:\n      match h:\n        case {src}.KW{{k, v}}:\n"
            f"          Con{{{dst}.KW{{{name}_w(k), {name}_w(v)}}, {name}_kws(t)}}\n",
            f"def {name}_kh(xs: List<&2, {src}.HKB>) -> List<&2, {dst}.HKB>:\n  match xs:\n    case Nil{{}}:\n      Nil{{}}\n"
            f"    case Con{{h, t}}:\n      match h:\n        case {src}.HKB{{b, v}}:\n"
            f"          Con{{{dst}.HKB{{b, {name}_w(v)}}, {name}_kh(t)}}\n"]


def versioned_module(member: str, legacy_import: str, head_import: str, section_import: str, eta: dict) -> str:
    """The versioned member (K3): the legacy version's reachability, the upgrade eta (every legacy register keeps its
    slot, so eta is the store's list of slot-word pairs read in the head's module, and the registers the legacy layout
    lacks hold nothing), then head steps whose block.timestamp is at least 1 (K4's premise; the legacy model reads no
    clock)."""
    moved = [m["register"] for m in eta["map"] if int(m["from_slot"]) != int(m["to_slot"])]
    if moved or not eta.get("inherited"):
        raise ValueError(f"{member}: eta moves {moved or 'the inherited layout'}: not the identity on the store")
    lines = [f"# GENERATED by holon.symb.sections (I92, K3) for the versioned member {member}; do not edit.",
             f"# eta: {eta['from']['tag']} ({eta['from']['commit']}) -> the head; fresh registers {eta['fresh']}",
             "import Base", f"import {legacy_import} as L", f"import {head_import} as M", f"import {section_import} as U",
             ""]
    lines += _conv_defs("L", "M", "eta") + _conv_defs("M", "L", "inv")
    lines += ["# eta (K3): the legacy store as the head's (the same slots)\n"
              "def eta(s: L.HSt) -> M.HSt:\n  match s:\n    case L.HSt{sl}:\n      M.HSt{eta_kws(sl)}\n",
              "# the versioned reachability: a legacy-reachable state upgraded (VUp), then head steps at a nonzero clock\n"
              "type VReach<-kh: List<&2, M.HKB>, -s: M.HSt> is Type:\n"
              "  VUp{l: L.HSt, r: L.Reach<inv_kh(kh), l>, e: {s == eta(l) : M.HSt}}\n"
              "  VStep{a: M.HAct, p: M.HSt, r: VReach<kh, p>, "
              "t: {M.w_nz(M.ge_e_block_timestamp(U.sy_en(a))) == True{} : Bool}, e: {s == M.step(a, p, kh) : M.HSt}}\n"]
    return "\n".join(lines)


def link_module(caller: str, callee: str, caller_import: str, callee_import: str, section_import: str,
                defs: list) -> str:
    """The members' link in I94's form (K3): the caller's reachability of s and the callee's of q (its own deployment
    and steps), under the hash table read in the callee's module, and the caller's call answers at a site read from
    the callee's state (defs: the answer and the site's functions)."""
    lines = [f"# GENERATED by holon.symb.sections (I92, K3) for the link {caller} -> {callee}; do not edit.",
             "import Base", f"import {caller_import} as M", f"import {callee_import} as Q", f"import {section_import} as U",
             ""]
    lines += _conv_defs("M", "Q", "q") + _conv_defs("Q", "M", "m")
    lines += ["# the linked reachability: the caller's of s and the callee's of q\n"
              "type LReach<-kh: List<&2, M.HKB>, -s: M.HSt, -q: Q.HSt> is Type:\n"
              "  LR{rs: M.Reach<kh, s>, rq: Q.Reach<q_kh(kh), q>}\n"]
    return "\n".join(lines + defs)


def _claims(ctx, member: str, cache: dict):
    if member not in cache:
        from ..bundle.laws import Claims
        mtext, mm = member_machine(ctx, member)
        cache[member] = Claims(mm, mtext)
    return cache[member]


def _compile(cl, action: str, term, kind: str = "w", view: str = "s", alias: str = "M") -> str:
    code = _qualify_ite(cl.compile(action, term, kind, view=view), cl.names)
    if alias != "M":
        code = re.sub(r"(?<![\w.])M\.", f"{alias}.", code)
        code = _qualify_ite(code, cl.names, alias)
    return code


def member_machine(ctx, name: str):
    """(text, generator) of a member's bundle model, built as holon.bundle.model builds it (model3 with EXT1); the text
    must equal the committed model, so that a term compiled by the generator names the model's own functions."""
    import json
    from ..machine import ExtractedModel
    from ..rules.sort import DocBasis, hash_functions
    from ..sorts import model3
    from ..sorts.typed_sidecar import load as load_ts
    from ..bundle import members as MB, sha256_bytes
    from ..bundle.model import init_of
    b = ctx.bundle
    rel = b.document_rel(b.member(name))
    data = b.path(rel).read_bytes()
    doc = json.loads(data)
    seeds = json.loads(load_ts(b.milestone, b.root, None).seeds.read_text(encoding="utf-8"))
    mname = model3.model_name(rel)
    assignment = {"models": {mname: {"assignment": {}}}, "sorts_sha256": None, "sites": []}
    init = init_of(b, name)
    storage = {int(k, 16): int(v, 16) for k, v in init["storage"].items()}
    header = [f"# GENERATED by holon.bundle.model (holon.sorts.model3) from {rel}; do not edit.",
              f"# facts_sha256: {sha256_bytes(data)}",
              f"# model_version: {model3.MODEL3_VERSION} (untyped: the sort section off)",
              f"# initial state: the deployment of {init['binding']} "
              f"({len([v for v in storage.values() if v])} non-zero slots)",
              "# model debt (actions left out): none"]
    em = ExtractedModel(doc, MB.info(b, name), None, sha256_bytes(data))
    text, mm = model3.build_text(em, typed=False, sorts={}, seeds=seeds, init=storage,
                                 hashes=hash_functions(doc) or ["keccak256"],
                                 basis=DocBasis(rel, doc, mname, assignment, seeds), site_rows=[], header=header,
                                 ext1=True)
    committed = (b.root / f"gen/{b.milestone}/bundle/models/{name}.bend").read_text(encoding="utf-8")
    if text != committed:
        raise ValueError(f"{name}: the generator's model differs from the committed bundle model (holon bundle model)")
    return text, mm


def build(ctx, log=print) -> dict:
    """{path: bytes}: each member's section, the versioned member and the link modules, and
    gen/<M>/symb/sections/index.json {law: {"member", "kind", "n", "ok", "hit", ...}}: kind tau (with its comparison
    sites "cmps": [{"i", "term", "src", "where", "flip"}]), sentinel, link (the module and its functions) or versioned
    (the module and the invariant's functions)."""
    import json
    from pathlib import Path
    from . import basis as B
    from .sorts import Solver
    from ..bundle import render
    sorts = json.loads((ctx.root / ctx.out("sorts.json")).read_text(encoding="utf-8"))
    laws = B.member_laws(ctx, sorts)
    files, index, cl = {}, {}, {}
    out = ctx.out("sections")
    lg = ctx.side.get("legacy") or {}
    docs = {m: ctx.bundle.load(ctx.side["members"][m]["document"]) for m in sorted(ctx.side["members"])}
    for member in sorted(laws):
        v = laws[member]
        doc = docs[member]
        mrel = f"gen/{ctx.milestone}/bundle/models/{member}.bend"
        text = (ctx.root / mrel).read_text(encoding="utf-8")
        imp = Path("../../bundle/models") / f"{member}.bend"
        sec = Section(member, str(imp), text, doc, sorts["members"][member])
        sec.prelude()
        solver = Solver({member: doc}, {})
        solver.time[member] = set(sorts["members"][member]["time"])
        solver.idx[member] = set(sorts["members"][member]["idx"])
        acts = {a["name"]: a for a in doc["actions"]}
        n = 0
        c = v["contract"]
        link_defs = []
        for act in v["tau"]:
            n += 1
            lid = f"{B.PREFIX}tau_{c}_{act}"
            a = acts[act]
            view = a.get("mutability") in ("view", "pure") and a.get("returns") is not None
            treturn = view and solver.sort(member, a.get("returns")) == "time"
            ret_code = _compile(_claims(ctx, member, cl), act, a.get("returns")) if view else None
            sec.tau(n, lid, act, treturn, ret_code)
            cmps, codes = [], []
            for i, (term, src, where) in enumerate(time_compares(a, member, solver)):
                try:
                    codes.append((i, _compile(_claims(ctx, member, cl), act, term, "bool")))
                except Exception as e:  # noqa: BLE001  (a site the generator cannot compile is listed as such)
                    cmps.append({"i": i, "term": term, "src": src, "where": where, "flip": None,
                                 "error": f"{type(e).__name__}: {e}"[:300]})
                    continue
                cmps.append({"i": i, "term": term, "src": src, "where": where, "flip": f"sy_flip_{n}_{i}"})
            sec.cmp_sites(n, act, codes)
            index[lid] = {"member": member, "kind": "tau", "n": n, "ok": f"sy_ok_{n}", "hit": f"sy_hit_{n}",
                          "time_return": treturn, "ret": f"sy_rw_{n}" if view else None, "cmps": cmps}
        for path, act, src, val, const in v["sentinels"]:
            line = re.search(r":(\d+)(?:-\d+)?$", src or "")
            lid = f"{B.PREFIX}sentinel_{c}_{path.replace('.', '_')}_{act}_{line.group(1) if line else 'x'}"
            n += 1
            if val == ["env", "block.timestamp"]:
                sec.sentinel(n, lid, act, val, const)
                index[lid] = {"member": member, "kind": "sentinel", "n": n, "ok": f"sn_ok_{n}", "hit": f"sn_hit_{n}",
                              "action": act, "constant": const}
                continue
            # a value reading a callee's answer: stated over the link (K3), in the link module
            calls = sorted({x[1] for x in _walk(val) if len(x) == 2 and x[0] == "call" and isinstance(x[1], str)})
            callee = next((m for m in sorted(docs) if m != member and all(
                any(b["name"] == fn.rsplit(".", 1)[-1] and b.get("returns") is not None for b in docs[m]["actions"])
                for fn in calls)), None)
            if callee is None or not calls:
                raise ValueError(f"{lid}: no member answers the value's calls {calls}")
            k = len(link_defs)
            for j, fn in enumerate(calls):
                ca = next(b for b in docs[callee]["actions"] if b["name"] == fn.rsplit(".", 1)[-1])
                qcode = _compile(_claims(ctx, callee, cl), ca["name"], ca["returns"], view="q", alias="Q")
                link_defs.append(f"# the callee's answer to {fn}: {ca['name']}'s return word on q\n"
                                 f"def lk_q_{n}_{j}(+q: Q.HSt, +kh: List<&2, Q.HKB>) -> Q.W:\n  {qcode}\n")
                acode = _compile(_claims(ctx, member, cl), act, ["call", fn])
                link_defs.append(f"def lk_ans_{n}_{j}(+s: M.HSt, +ar: M.AR_{bname(act)}, +en: M.HEnv, "
                                 f"+kh: List<&2, M.HKB>) -> M.W:\n  {acode}\n")
            vcode = _compile(_claims(ctx, member, cl), act, val)
            ar_t = f"M.AR_{bname(act)}"
            link_defs.append(f"def lk_val_{n}(+s: M.HSt, +ar: {ar_t}, +en: M.HEnv, +kh: List<&2, M.HKB>) -> M.W:\n"
                             f"  {vcode}\n")
            ans = " ".join(f"Bool.and(M.w_eq(lk_ans_{n}_{j}(s, ar, en, kh), m_w(lk_q_{n}_{j}(q, q_kh(kh)))),"
                           for j in range(len(calls)))
            close = ")" * len(calls)
            concl = (f"M.w_nz(lk_val_{n}(s, ar, en, kh))" if const == 0 else
                     f"Bool.not(M.w_eq(lk_val_{n}(s, ar, en, kh), {wlit(const)}))")
            body = (f"Bool.or(Bool.not({ans} U32.is_eq(M.chk_{bname(act)}(s, ar, en, kh), 0){close}), {concl})")
            arms = "".join(f"    case M.{kc}{{ar, en}}:\n      {body if kc == f'A_{bname(act)}' else 'True{}'}\n"
                           for kc in sec.acts)
            link_defs.append(f"# {lid}: over the link, the value the site writes is not the register's constant {const}"
                             f" (K4)\ndef lk_ok_{n}(+s: M.HSt, +q: Q.HSt, +x: M.HAct, +kh: List<&2, M.HKB>) -> Bool:\n"
                             f"  match x:\n{arms}")
            index[lid] = {"member": member, "kind": "link", "n": n, "ok": f"lk_ok_{n}", "hit": None, "callee": callee,
                          "calls": calls, "action": act, "constant": const,
                          "module": ctx.out("link", f"{member}.bend"), "defs_from": k}
        for path, view, const in v["readers"]:
            lid = f"{B.PREFIX}sentinel_inv_{c}_{path.replace('.', '_')}_{view}"
            n += 1
            r = acts[view]["returns"]
            conj = _conj(r[1])
            from .sorts import register_of
            rne = next(x for x in conj if isinstance(x, list) and len(x) == 3 and x[0] == "!=" and
                       ((register_of(x[1]) == path and x[2] == const) or (register_of(x[2]) == path and x[1] == const)))
            rest = [x for x in conj if x is not rne]
            g = rest[0] if len(rest) == 1 else ["&&", *rest]
            cla = _claims(ctx, member, cl)
            g_code, r_code = _compile(cla, view, g, "bool"), _compile(cla, view, rne, "bool")
            for code in (g_code, r_code):
                if re.search(r"(?<![\w.])(ar|en)(?![\w])", code):
                    raise ValueError(f"{lid}: the view's conjuncts read its arguments or environment")
            sec.invariant(n, lid, g_code, r_code)
            entry = {"member": member, "kind": "versioned", "n": n, "ok": f"sn_inv_{n}", "hit": None, "view": view,
                     "constant": const, "g": f"sn_g_{n}", "rne": f"sn_rne_{n}"}
            if lg.get("member") == member:
                eta = json.loads((ctx.root / ctx.out(f"eta_{lg.get('eta', 'enq')}.json")).read_text(encoding="utf-8"))
                vrel = ctx.out("versioned", f"{member}.bend")
                files[vrel] = versioned_module(member, f"../legacy/{member}.bend", f"../../bundle/models/{member}.bend",
                                               f"../sections/{member}.bend", eta).encode("utf-8")
                entry["module"] = vrel
            index[lid] = entry
        files[f"{out}/{member}.bend"] = sec.text_out().encode("utf-8")
        if link_defs:
            callee = next(e["callee"] for e in index.values() if e["member"] == member and e["kind"] == "link")
            files[ctx.out("link", f"{member}.bend")] = link_module(
                member, callee, f"../../bundle/models/{member}.bend", f"../../bundle/models/{callee}.bend",
                f"../sections/{member}.bend", link_defs).encode("utf-8")
        log(f"{member}: {n} laws stated")
    files[f"{out}/index.json"] = render({"sections_version": "holon-symb-sections/0.2", "laws": index})
    return files


def main(ctx, check: bool, log) -> int:
    from ..bundle import write_or_check
    return write_or_check(ctx.bundle, build(ctx, log), check,
                          owned=[ctx.out("sections"), ctx.out("versioned"), ctx.out("link")], log=log)
