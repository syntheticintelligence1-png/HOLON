"""Rule K2 (I94): the Bend linked layer, generated from a link spec alone.

A link spec (the I94 sidecar's `link`, spec/<M>/lib/slash_decide.json) names a caller and its callees. Each member is
a model3 member model (kind "plain": its store HSt and Reach) or a versioned layer (kind "versioned": its versioned
state VSt, its own version chain and VReach), given by its module and an alias; a callee also names the caller's
version at which it is linked and the caller's storage word that names it there. The layer imports every member's
module and defines, per callee X:
  - the conversions between the caller's module and X's of every prelude record both define (words, stores, hash
    tables, call answers, code tables, logs, outcomes, and for a versioned member its version tags and states),
    generated from the modules' own type definitions: <T>_to_<X> (caller to X) and <T>_of_<X> (X to caller), and the
    list maps of each;
  - for an environment record with a caller field and an answer list: env_caller_<X> (the environment with its caller
    replaced) and env_ok_<X> (every answer in it ok);
and the linked reachability LReach<kh, s, s_<X>..>: the caller's reachability of s (VReach or Reach) and each callee's
of its state, under the hash table converted to its module. Nothing here names a member, a version or a family: they
are the spec's. Exit codes as the package's.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import Ctx, Refused, render  # noqa: F401

PRELUDE = ("W", "KW", "HSt", "HKB", "HCall", "KB", "HLog", "HOut")
VERSIONED = ("VV", "VSt")
_TYPE = re.compile(r"^type (\w+) is Data:\n((?:  .*\n)+)", re.M)
_CTOR = re.compile(r"^  (\w+)\{(.*)\}$")


def split_top(s: str) -> list:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "<({[":
            depth += 1
        elif ch in ">)}]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def types_of(text: str) -> dict:
    """{type: [(constructor, [(field, field type)])]} of a module's plain data types."""
    out = {}
    for m in _TYPE.finditer(text):
        ctors = []
        for line in m.group(2).splitlines():
            c = _CTOR.match(line)
            if not c:
                continue
            fields = []
            for f in split_top(c.group(2)):
                name, _, ty = f.partition(":")
                fields.append((name.strip(), ty.strip()))
            ctors.append((c.group(1), fields))
        out[m.group(1)] = ctors
    return out


def rel_import(d: Path, p: Path) -> str:
    r = os.path.relpath(p, d).replace(os.sep, "/")
    return r if r.startswith(".") else "./" + r


class Gen:
    def __init__(self, root: Path, spec: dict, out: Path):
        self.root, self.spec, self.out = Path(root), spec, Path(out)
        self.caller = spec["caller"]
        self.callees = spec["callees"]
        self.text = {}
        for m in [self.caller] + list(self.callees):
            p = self.root / m["module"]
            if not p.is_file():
                raise Refused(f"{m['module']} is missing")
            self.text[m["alias"]] = p.read_text(encoding="utf-8")
        self.types = {a: types_of(t) for a, t in self.text.items()}
        self.defs: list = []

    def conv_names(self, x: str) -> list:
        """The record types converted between the caller and callee x: the prelude's, and for a versioned callee
        its version tags and states, each one both modules define with the same constructors and fields."""
        names = list(PRELUDE) + (list(VERSIONED) if self.kind(x) == "versioned" else [])
        P, X = self.caller["alias"], x
        out = []
        for n in names:
            a, b = self.types[P].get(n), self.types[X].get(n)
            if a is not None and b is not None and a == b:
                out.append(n)
        return out

    def kind(self, alias: str) -> str:
        return next(m["kind"] for m in [self.caller] + list(self.callees) if m["alias"] == alias)

    def field(self, ty: str, v: str, conv: set, fn) -> str:
        if ty in ("U32", "Bool", "Nat", "List<&2, U32>"):
            return v
        if ty in conv:
            return f"{fn(ty)}({v})"
        m = re.fullmatch(r"List<&2, (\w+)>", ty)
        if m and m.group(1) in conv:
            return f"{fn('l' + m.group(1))}({v})"
        raise Refused(f"no conversion of a field of type {ty}")

    def conversions(self, x: str) -> None:
        P = self.caller["alias"]
        names = self.conv_names(x)
        conv = set(names)
        for src, dst, suffix in ((P, x, f"_to_{x}"), (x, P, f"_of_{x}")):
            def fn(t, suffix=suffix):
                return f"{t}{suffix}"
            for n in names:
                cases = []
                for ctor, fields in self.types[src][n]:
                    vs = [f for f, _t in fields]
                    args = ", ".join(self.field(t, f, conv, fn) for f, t in fields)
                    pat = f"{src}.{ctor}{{{', '.join(vs)}}}" if vs else f"{src}.{ctor}{{}}"
                    cases.append(f"    case {pat}:\n      {dst}.{ctor}{{{args}}}")
                self.defs.append(f"def {n}{suffix}(v: {src}.{n}) -> {dst}.{n}:\n  match v:\n" + "\n".join(cases) + "\n")
                self.defs.append(f"def l{n}{suffix}(xs: List<&2, {src}.{n}>) -> List<&2, {dst}.{n}>:\n  match xs:\n"
                                 f"    case Nil{{}}:\n      Nil{{}}\n    case Con{{h, t}}:\n"
                                 f"      Con{{{n}{suffix}(h), l{n}{suffix}(t)}}\n")

    def env_helpers(self, x: str) -> None:
        for env in ("HEnv", "VEnv"):
            ctors = self.types[x].get(env)
            if not ctors or len(ctors) != 1:
                continue
            ctor, fields = ctors[0]
            names = [f for f, _t in fields]
            pat = f"{x}.{ctor}{{{', '.join(names)}}}"
            if "e_caller" in names:
                rebuilt = ", ".join("c" if f == "e_caller" else f for f in names)
                self.defs.append(f"def env_caller_{x}(e: {x}.{env}, c: {x}.W) -> {x}.{env}:\n  match e:\n"
                                 f"    case {pat}:\n      {x}.{ctor}{{{rebuilt}}}\n")
            if "e_calls" in names:
                self.defs.append(f"def calls_ok_{x}(xs: List<&2, {x}.HCall>) -> Bool:\n  match xs:\n"
                                 f"    case Nil{{}}:\n      True{{}}\n    case Con{{h, t}}:\n      match h:\n"
                                 f"        case {x}.HCall{{to, d, ok, ret}}:\n"
                                 f"          Bool.and(ok, calls_ok_{x}(t))\n")
                self.defs.append(f"def env_ok_{x}(e: {x}.{env}) -> Bool:\n  match e:\n    case {pat}:\n"
                                 f"      calls_ok_{x}(e_calls)\n")

    def reach_type(self) -> str:
        P = self.caller["alias"]
        st = {"versioned": ("VSt", "VReach"), "plain": ("HSt", "Reach")}
        cs, cr = st[self.caller["kind"]]
        idx = [f"-kh: List<&2, {P}.HKB>", f"-s: {P}.{cs}"]
        fields = [f"r: {P}.{cr}<kh, s>"]
        for c in self.callees:
            x = c["alias"]
            xs, xr = st[c["kind"]]
            idx.append(f"-s_{x}: {x}.{xs}")
            fields.append(f"r_{x}: {x}.{xr}<lHKB_to_{x}(kh), s_{x}>")
        return ("# the linked reachability: the caller's reachability of s and each callee's of its own state, under the "
                "hash table converted to its module\n"
                f"type LReach<{', '.join(idx)}> is Type:\n  LR{{{', '.join(fields)}}}\n")

    def text_of(self) -> str:
        d = self.out.parent
        mods = [self.caller] + [c for c in self.callees if c["alias"] != self.caller["alias"]]
        head = ["# GENERATED by holon.cutover.linked from a link spec; do not edit (fix the generator instead).",
                f"# caller {self.caller['member']} ({self.caller['kind']}); callees "
                + "; ".join(f"{c['member']} ({c['kind']}) at {c['at']} through {c['word']}" for c in self.callees),
                "import Base"]
        seen = set()
        for m in mods:
            if m["alias"] in seen:
                continue
            seen.add(m["alias"])
            head.append(f"import {rel_import(d, self.root / m['module'])} as {m['alias']}")
        for c in self.callees:
            if c["alias"] not in seen:
                seen.add(c["alias"])
                head.append(f"import {rel_import(d, self.root / c['module'])} as {c['alias']}")
        for c in self.callees:
            self.conversions(c["alias"])
            self.env_helpers(c["alias"])
        return "\n".join(head) + "\n\n" + "\n".join(self.defs) + "\n" + self.reach_type()


def write_layer(root: Path, spec: dict, out: Path) -> str:
    text = Gen(root, spec, out).text_of()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(text, encoding="utf-8")
    return text


def build(ctx: Ctx, log=print) -> dict:
    from .s0 import sidecar
    side = sidecar(ctx)
    rel = side["outputs"]["linked"]
    text = Gen(ctx.root, side["link"], ctx.path(rel)).text_of()
    log(f"{rel}: {len(side['link']['callees'])} callees")
    return {rel: text.encode("utf-8")}
