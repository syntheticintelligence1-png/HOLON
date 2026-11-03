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
  sn_ok_<n>, sn_hit_<n> a sentinel law's claim (the act succeeds and block.timestamp >= 1 imply that the site's value is not
                        the register's constant) and its premises alone

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
        """A sentinel site whose value term is block.timestamp (the four Time sites): the act succeeds and its
        block.timestamp is at least 1 imply that the value is not the constant."""
        if value_term != ["env", "block.timestamp"]:
            raise ValueError(f"{lid}: the member section states a sentinel site whose value is block.timestamp; "
                             f"{value_term!r} is the link's (K3)")
        isd = self.is_def(action)
        c = f"A_{bname(action)}"
        prem = (f"Bool.and({isd}(x), Bool.and(U32.is_eq(M.chk_{bname(action)}(s, sn_ar_{n}(x), sy_en(x), kh), 0), "
                f"M.w_ge(M.ge_e_block_timestamp(sy_en(x)), {wlit(1)})))")
        arms = "".join(f"    case M.{k}{{ar, en}}:\n      {'ar' if k == c else f'sn_ar0_{n}()'}\n" for k in self.acts)
        ar_t = f"M.AR_{bname(action)}"
        self.add(f"def sn_ar0_{n}() -> {ar_t}:\n  {self._ar_zero(action)}\n")
        self.add(f"def sn_ar_{n}(x: M.HAct) -> {ar_t}:\n  match x:\n{arms}")
        self.add(f"# {lid}: the value the site writes is not the register's constant {constant} (K4)\n"
                 f"def sn_ok_{n}(+s: M.HSt, +x: M.HAct, +kh: List<&2, M.HKB>) -> Bool:\n"
                 f"  Bool.or(Bool.not({prem}), Bool.not(M.w_eq(M.ge_e_block_timestamp(sy_en(x)), {wlit(constant)})))\n")
        self.add(f"def sn_hit_{n}(+s: M.HSt, +x: M.HAct, +kh: List<&2, M.HKB>) -> Bool:\n  {prem}\n")

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
    """{path: bytes}: each member's section and gen/<M>/symb/sections/index.json {law: {"member", "kind", "n", "ok",
    "hit"}} (a law the member section cannot state, the lastIndex site whose value is the link's, is listed with kind
    "link" and no functions)."""
    import json
    from pathlib import Path
    from . import basis as B
    from .sorts import Solver
    from ..bundle import render
    sorts = json.loads((ctx.root / ctx.out("sorts.json")).read_text(encoding="utf-8"))
    laws = B.member_laws(ctx, sorts)
    files, index = {}, {}
    out = ctx.out("sections")
    for member in sorted(laws):
        v = laws[member]
        doc = ctx.bundle.load(ctx.side["members"][member]["document"])
        mrel = f"gen/{ctx.milestone}/bundle/models/{member}.bend"
        text = (ctx.root / mrel).read_text(encoding="utf-8")
        imp = Path("../../bundle/models") / f"{member}.bend"
        sec = Section(member, str(imp), text, doc, sorts["members"][member])
        sec.prelude()
        claims = None
        solver = Solver({member: doc}, {})
        solver.time[member] = set(sorts["members"][member]["time"])
        solver.idx[member] = set(sorts["members"][member]["idx"])
        acts = {a["name"]: a for a in doc["actions"]}
        n = 0
        c = v["contract"]
        for act in v["tau"]:
            n += 1
            lid = f"{B.PREFIX}tau_{c}_{act}"
            a = acts[act]
            view = a.get("mutability") in ("view", "pure") and a.get("returns") is not None
            treturn = view and solver.sort(member, a.get("returns")) == "time"
            ret_code = None
            if view:
                if claims is None:
                    from ..bundle.laws import Claims
                    mtext, mm = member_machine(ctx, member)
                    claims = Claims(mm, mtext)
                # qualify only qualifies a name before ( or {: ite's type argument is a model type too
                ret_code = re.sub(r"(?<![\w.])M\.ite\((\w+),",
                                  lambda mt: f"M.ite({'M.' if mt.group(1) in claims.names else ''}{mt.group(1)},",
                                  claims.compile(act, a.get("returns")))
            sec.tau(n, lid, act, treturn, ret_code)
            index[lid] = {"member": member, "kind": "tau", "n": n, "ok": f"sy_ok_{n}", "hit": f"sy_hit_{n}",
                          "time_return": treturn}
        for p, act, src, val, const in v["sentinels"]:
            line = re.search(r":(\d+)(?:-\d+)?$", src or "")
            lid = f"{B.PREFIX}sentinel_{c}_{p.replace('.', '_')}_{act}_{line.group(1) if line else 'x'}"
            if val == ["env", "block.timestamp"]:
                n += 1
                sec.sentinel(n, lid, act, val, const)
                index[lid] = {"member": member, "kind": "sentinel", "n": n, "ok": f"sn_ok_{n}", "hit": f"sn_hit_{n}"}
            else:
                index[lid] = {"member": member, "kind": "link", "n": None, "ok": None, "hit": None}
        for p, view, const in v["readers"]:
            lid = f"{B.PREFIX}sentinel_inv_{c}_{p.replace('.', '_')}_{view}"
            index[lid] = {"member": member, "kind": "versioned", "n": None, "ok": None, "hit": None}
        files[f"{out}/{member}.bend"] = sec.text_out().encode("utf-8")
        log(f"{member}: {n} laws stated in the section")
    files[f"{out}/index.json"] = render({"sections_version": "holon-symb-sections/0.1", "laws": index})
    return files


def main(ctx, check: bool, log) -> int:
    from ..bundle import write_or_check
    return write_or_check(ctx.bundle, build(ctx, log), check, owned=[ctx.out("sections")], log=log)
