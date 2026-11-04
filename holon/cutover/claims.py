"""Rule K3 (I94): the slash laws' claims module, generated from the documents, the link spec and the site pairs.

For each site pair of holon.rules.slash (edge a->b, op) and each rule (NAT, SORT) the module defines the claim
slash_<rule>_<a>_<b>_<op>(s, s_<X>.., k, u, e_<X>.., kh) over the caller's versioned state s, each callee's state
and environment, the batch key k, the edge's migration choice u and the hash table:
  - a site's answer at version v: the callee the link spec links at v (its storage word the site's receiver) runs the
    site's action on the site's one argument, the retyped member read from the caller's storage at the key k by v's
    layout (holon's vread), with its environment's caller set to the Rollup's address (each callee's caller word, the
    cutover sidecar's wiring); the answer is (the run's status is ok, its first return word);
  - premises: s at a; k in flight (the window the cutover sidecar's search names: lower < k <= upper, both scalar
    families of a); u succeeds (the migration's state is at b); the receiver word read at a names the a-callee (its
    environment's address) and the one read after u the b-callee's; both callees' caller words are equal; every answer
    in each environment is ok. A claim whose premises fail is true;
  - NAT: the b-site's answer after u equals the a-site's at s; SORT: a nonzero a-site word implies a nonzero b-site
    word.
Nothing here names a target: families, members, actions, versions and aliases come from the documents and specs.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import Ctx, Refused, render  # noqa: F401
from .linked import rel_import, types_of

WINDOW = re.compile(r"\((\w+) < k <= (\w+)\)")


def wlit(alias: str, v: int) -> str:
    limbs = [(v >> (32 * i)) & 0xFFFFFFFF for i in range(8)]
    return f"{alias}.w_of_limbs([{', '.join(str(x) for x in limbs)}])"


def family(doc: dict, name: str) -> dict:
    f = next((x for x in doc.get("storage") or [] if x.get("name") == name), None)
    if f is None:
        f = next((x for x in doc.get("inherited_storage") or [] if x.get("name") == name), None)
    if f is None:
        raise Refused(f"no storage family {name}")
    return f


def mask(alias: str, width: int, code: str) -> str:
    return code if int(width) >= 256 else f"{alias}.w_and({code}, {wlit(alias, (1 << int(width)) - 1)})"


class Claims:
    def __init__(self, ctx: Ctx):
        from ..rules import slash as S
        from .s0 import sidecar
        self.ctx, self.root = ctx, ctx.root
        self.side = sidecar(ctx)
        self.link = self.side["link"]
        self.S = S
        _rel, _sha, self.vdoc, self.docs, self.model = S.read_inputs(ctx.milestone, ctx.root)
        self.pairs = S.pairs_of(self.vdoc, self.docs)
        m = WINDOW.search(ctx.side["search"]["doc"])
        if m is None:
            raise Refused("the cutover sidecar's search names no in-flight window")
        self.window = (m.group(1), m.group(2))
        self.P = self.link["caller"]["alias"]
        self.defs: list = []
        self.texts = {c["alias"]: (self.root / c["module"]).read_text(encoding="utf-8") for c in self.link["callees"]}

    def callee(self, v: str, word: str) -> dict:
        c = next((c for c in self.link["callees"] if c["at"] == v and c["word"] == word), None)
        if c is None:
            raise Refused(f"the link spec links no callee at {v} through {word}")
        return c

    def callee_doc(self, c: dict) -> dict:
        rel = (self.ctx.side["inputs"].get("documents") or {}).get(c["member"])
        if not rel:
            raise Refused(f"no document for {c['member']}")
        return json.loads((self.root / rel).read_text(encoding="utf-8"))

    def caller_word(self, c: dict) -> str:
        """The callee's storage word that names the caller (the cutover sidecar's wiring), read from its state, as a
        caller word."""
        caller = self.link["caller"]["member"]
        fams = sorted({k.split(".", 1)[1] for side in ("a", "b") for k, v in
                       (self.ctx.side["link"][side].get("wiring") or {}).items()
                       if k.startswith(c["member"] + ".") and v == caller})
        if len(fams) != 1:
            raise Refused(f"{c['member']}: {len(fams)} words name {caller} in the wiring")
        f = family(self.callee_doc(c), fams[0])
        if int(f.get("offset", 0)):
            raise Refused(f"{c['member']}.{fams[0]} is packed")
        x = c["alias"]
        word = f"{x}.sload(s_{x}, {wlit(x, int(f['slot']))})"
        return f"L.W_of_{x}({mask(x, f.get('width', 256), word)})"

    def read(self, v: str, s: str, name: str, k: str | None) -> str:
        P, doc = self.P, self.docs[v]
        if "." in name:
            fam, mem = name.split(".", 1)
            f = family(doc, fam)
            fld = next((x for x in f.get("fields") or [] if x["name"] == mem), None)
            if f.get("kind") != "mapping" or fld is None or k is None:
                raise Refused(f"{v}: {name} is not a member of a mapping family")
            if int(fld.get("offset", 0)) or int(f.get("offset", 0)):
                raise Refused(f"{v}: {name} is packed")
            code = (f"{P}.vread({s}, {wlit(P, int(f['slot']))}, {P}.w0(), [{P}.VP{{{k}, {wlit(P, int(fld['slot']))}}}], "
                    "kh)")
            return mask(P, fld.get("width", 256), code)
        f = family(doc, name)
        if f.get("kind") != "scalar" or int(f.get("offset", 0)):
            raise Refused(f"{v}: {name} is not an unpacked scalar")
        return mask(P, f.get("width", 256), f"{P}.vread({s}, {wlit(P, int(f['slot']))}, {P}.w0(), Nil{{}}, kh)")

    def site(self, tag: str, v: str, site: dict, s: str) -> str:
        """def site_<tag>(...) -> Ans: the site's answer at v on caller state s."""
        c = self.callee(v, site["receiver"])
        x = c["alias"]
        act = self.S_action(site["fn"])
        ar = types_of(self.texts[x]).get(f"AR_{act}")
        if not ar or len(ar) != 1 or len(ar[0][1]) != 1 or ar[0][1][0][1] != "W" or len(site["reads"]) != 1:
            raise Refused(f"{c['member']}.{act}: the site's call is not one word argument")
        arg = self.read(v, s, site["reads"][0], "k")
        st = "HSt" if c["kind"] == "plain" else "VSt"
        self.defs.append(
            f"def site_{tag}(+s: {self.P}.VSt, +s_{x}: {x}.{st}, +k: {self.P}.W, +e_{x}: {x}.HEnv, +rw: {self.P}.W, "
            f"+kh: List<&2, {self.P}.HKB>) -> Ans:\n"
            f"  ans_{x}({x}.run_{act}(s_{x}, {x}.{ar[0][0]}{{L.W_to_{x}({arg})}}, L.env_caller_{x}(e_{x}, L.W_to_{x}(rw)), "
            f"L.lHKB_to_{x}(kh)))\n")
        return x

    @staticmethod
    def S_action(fn: str) -> str:
        from .lawrun import _action_of
        return _action_of(fn)

    def text_of(self) -> str:
        P = self.P
        out = self.root / self.side["outputs"]["claims"]
        d = out.parent
        head = ["# GENERATED by holon.cutover.claims: the slash laws' claims over the linked layer; do not edit (fix "
                "the generator instead).", "import Base",
                f"import {rel_import(d, self.root / self.link['caller']['module'])} as {P}"]
        for c in self.link["callees"]:
            head.append(f"import {rel_import(d, self.root / c['module'])} as {c['alias']}")
        head.append(f"import {rel_import(d, self.root / self.side['outputs']['linked'])} as L")
        self.defs.append(f"# a site's answer: its run's status is ok, and its first return word\n"
                         f"type Ans is Data:\n  Ans{{ok: Bool, w: {P}.W}}\n")
        self.defs.append("def beq(a: Bool, b: Bool) -> Bool:\n  match a:\n    case True{}:\n      b\n    case False{}:\n"
                         "      Bool.not(b)\n")
        self.defs.append(f"def ans_eq(a: Ans, b: Ans) -> Bool:\n  match a:\n    case Ans{{ok, w}}:\n      match b:\n"
                         f"        case Ans{{ok2, w2}}:\n          Bool.and(beq(ok, ok2), {P}.w_eq(w, w2))\n")
        self.defs.append(f"def ans_w(a: Ans) -> {P}.W:\n  match a:\n    case Ans{{ok, w}}:\n      w\n")
        self.defs.append(f"def vv_of(s: {P}.VSt) -> {P}.VV:\n  match s:\n    case {P}.VSt{{v, st}}:\n      v\n")
        for c in self.link["callees"]:
            x = c["alias"]
            self.defs.append(f"def ans_{x}(o: {x}.HOut) -> Ans:\n  match o:\n    case {x}.HOut{{c, rv, po, lg, tw}}:\n"
                             f"      Ans{{U32.is_eq(c, 0), L.W_of_{x}({x}.b_word(rv, 0n))}}\n")
        for p in self.pairs:
            a, b = p["edge"].split("->")
            op = p["op"]
            if len(p["a"]) != 1 or len(p["b"]) != 1:
                raise Refused(f"{p['edge']} {op}: not one site per side")
            xa = self.site(f"{a}_{b}_{op}_a", a, p["a"][0], "s")
            xb = self.site(f"{a}_{b}_{op}_b", b, p["b"][0], "s")
            ca = next(c for c in self.link["callees"] if c["alias"] == xa)
            cb = next(c for c in self.link["callees"] if c["alias"] == xb)
            lo, hi = self.window
            ra, rb = p["a"][0]["receiver"], p["b"][0]["receiver"]
            sig = (f"+s: {P}.VSt, +s_{xa}: {xa}.HSt, +s_{xb}: {xb}.HSt, +k: {P}.W, +u: {P}.UC_{a}_{b}, "
                   f"+e_{xa}: {xa}.HEnv, +e_{xb}: {xb}.HEnv, +kh: List<&2, {P}.HKB>")
            prem = [f"{P}.vis_{a}(vv_of(s))",
                    f"{P}.w_lt({self.read(a, 's', lo, None)}, k)", f"{P}.w_le(k, {self.read(a, 's', hi, None)})",
                    f"{P}.vis_{b}(vv_of(s1))",
                    f"{P}.w_eq({self.read(a, 's', ra, None)}, L.W_of_{xa}({xa}.ge_e_this(e_{xa})))",
                    f"{P}.w_eq({self.read(b, 's1', rb, None)}, L.W_of_{xb}({xb}.ge_e_this(e_{xb})))",
                    f"{P}.w_eq(rw, {self.caller_word(cb)})", f"L.env_ok_{xa}(e_{xa})", f"L.env_ok_{xb}(e_{xb})"]
            pre = prem[0]
            for q in prem[1:]:
                pre = f"Bool.and({pre}, {q})"
            rwc = self.caller_word(ca)
            prem = [q.replace("rw,", f"{rwc},") if q.startswith(f"{P}.w_eq(rw") else q for q in prem]
            pre = prem[0]
            for q in prem[1:]:
                pre = f"Bool.and({pre}, {q})"
            mig = f"{P}.vstep({P}.U_{a}_{b}{{u}}, s, kh)"
            args = f"s, s_{xa}, s_{xb}, k, u, e_{xa}, e_{xb}, kh"
            for rule in self.S.RULES:
                concl = ("ans_eq(xb, xa)" if rule == "NAT" else
                         f"Bool.or(Bool.not({P}.w_nz(ans_w(xa))), {P}.w_nz(ans_w(xb)))")
                name = f"slash_{rule.lower()}_{a}_{b}_{op}"
                # the core takes the migrated state and both answers as arguments, so that a proof can give each its
                # own lemma (the kernel's budget is per definition) and the claim is the core applied to them
                # the core takes the migrated state and the old site's answer as arguments (each evaluated once:
                # the migration is not recomputed for the new site, whose answer the core computes from s1)
                self.defs.append(f"# {rule} slash at {p['edge']} {op}, its core: premises -> conclusion (true when a "
                                 f"premise fails), over the migrated state s1 and the old site's answer xa (at {a})\n"
                                 f"def {name}_core({sig}, +s1: {P}.VSt, +xa: Ans) -> Bool:\n"
                                 f"  +xb = {{site_{a}_{b}_{op}_b(s1, s_{xb}, k, e_{xb}, {rwc}, kh) : Ans}}\n"
                                 f"  Bool.or(Bool.not({pre}), {concl})\n")
                self.defs.append(f"def {name}({sig}) -> Bool:\n"
                                 f"  {name}_core({args}, {mig}, site_{a}_{b}_{op}_a(s, s_{xa}, k, e_{xa}, {rwc}, kh))\n")
        return "\n".join(head) + "\n\n" + "\n".join(self.defs)


def claim_name(law: dict) -> str:
    """The claims module's function of a slash law (its rule, edge and op from the law's slash id)."""
    sid = law["statement"]["claim"]["eq"][0]["slash"]
    _model, rest = sid.split(":", 1)
    sub, a, b, op = rest.split(":")
    return f"{sub}_{a}_{b}_{op}"


def build(ctx: Ctx, log=print) -> dict:
    c = Claims(ctx)
    rel = c.side["outputs"]["claims"]
    text = c.text_of()
    log(f"{rel}: {len(c.pairs)} site pairs")
    return {rel: text.encode("utf-8")}
