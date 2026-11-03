"""Rule V6: the versioned model, `python -m holon versions model [--check]`.

Every path version's document is compiled by holon.sorts.model3's compiler as it compiles the adopted document (its
word model, storage representation and hash parameters: model3.build_text), without the sort section (the frozen
assignment covers the adopted document only), into its own module <outputs.model_dir>/<stem>_<version>.bend, where
<stem> is the sidecar's model name made importable. A module is model3's untyped text of the document, whole: its
step_<a>/run_<a> per action, HAct, step and run. An action the compiler refuses (model3's GenError: a term outside its
language, a term whose value is unknown) is the version's model debt, with the compiler's message and the record that
holds the term; the module holds the other actions, and the versioned layer has no step for it (never smoothed).

The versioned layer <stem>.bend (linked as <model>.bend) imports the version modules and holds model3's fixed prelude
(holon.sorts.prelude3: W, HSt, HKB, .. of its own), the conversions between its values and each module's (the same
shapes, field by field), and, by the contract's names:
  VV, VSt{v, st}        the version (the placeholder or a path version) and one storage for every version
  VEnv                  a step's environment: the union of the modules' environment fields but the caller
  VStep                 C_<version>_<action>{ar: the module's argument record, cl: the caller, en: VEnv};
                        U_entry{c} and U_<a>_<b>{c}: a migration (A-proxy) along the entry edge or a MIG edge, c its call
                        (UN_<edge>{}: upgradeTo; UK_<edge>_<reinitializer>{ar, en}: upgradeToAndCall with a
                        reinitializer the edge introduces, run at the new version with the proxy admin as caller)
  vr0()                 the proxy's creation: the placeholder, every slot zero but the admin slot (the binding's admin)
  vstep(x, s, ..)       the state after step x (s itself when it reverts: a version mismatch, an action called by the
                        admin, a failing check or call), vok(x, s, ..) whether it succeeds, vrun(xs, s, ..)
  VReach<.., s>         VR0 | VRStep{x, p, r, e} from the proxy's creation
  vread(s, b, o, p, ..) the word at layout coordinate (b, o, p): the real slot b + o, then per mapping step VP{k, o'}
                        keccak256(k . slot) + o', through the hash table
  step_<version>, run_<version>   one step of an action of the version, a trace of its actions (its module's)
  ar_<version>_<action>(..)       the argument record of an action from its leaves in ABI order (words, byte lists)

<outputs.model_dir>/<model>.init.json records the versions, their modules and model debt, and vr0's admin. Byte-identical
across runs. Nothing here names a target.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from . import PLACEHOLDER, Ctx, Refused, VersionsError, render, sha256_bytes, sha256_file, vkey, write_or_check

MODEL_VERSION = "holon-versions-model/0.1"


def stem(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", model)


def module_name(model: str, vid: str) -> str:
    return f"{stem(model)}_{vid}.bend"


def alias(vid: str) -> str:
    return f"K_{re.sub(r'[^A-Za-z0-9_]', '_', vid)}"


def _comment(s) -> str:
    from ..machine_bend import comment
    return comment(s)


# ------------------------------------------------------------------------------------------------ one version
class Unit:
    """One path version compiled: its document, compiler information, module text and model debt."""

    def __init__(self, vid: str, rel: str):
        self.vid, self.rel = vid, rel
        self.doc = None
        self.sha = None
        self.info = None
        self.model = None          # holon.machine.ExtractedModel of the compiled actions
        self.debt: list = []
        self.actions: list = []
        self.hashes: list = []
        self.text = ""
        self.records: dict = {}
        self.env: list = []        # [(field, type, key)]


def version_info(ctx: Ctx, rel: str, doc: dict, doc_sha: str) -> dict:
    """holon.machine.compiler_info for the document's contract, compiled through its generated sidecar at the version's
    tree (the document's extraction inputs, checked unit by unit); cached under the build directory."""
    from ..bend import build_dir
    from ..frontends import ExtractionError, Refused as FRefused
    from ..frontends.solidity import compile as comp
    from ..machine import compiler_info
    from .extract import tree
    ext = doc.get("extraction") or {}
    srel = (ext.get("sidecar") or {}).get("path")
    if not isinstance(srel, str) or not (ctx.root / srel).is_file():
        raise Refused(f"{rel}: its extraction sidecar {srel!r} is missing")
    sdata = (ctx.root / srel).read_bytes()
    ssha = sha256_bytes(sdata)
    if ssha != (ext.get("sidecar") or {}).get("sha256"):
        raise Refused(f"{rel}: its extraction sidecar {srel} is not the one it records")
    cache = build_dir(ctx.root) / "versions" / "info" / f"{doc_sha[:16]}-{ssha[:8]}.json"
    if cache.is_file():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except ValueError:
            pass
    side = json.loads(sdata.decode("utf-8"))
    paths = (ctx.history.get("contract") or {}).get("build_paths") or ["."]
    t = tree(ctx, side["target"]["repo"], side["target"]["commit"], paths)
    try:
        compiled = comp.compile_sources(ctx.cfg, side, t, storage_layout=True)
    except (FRefused, ExtractionError) as e:
        raise Refused(f"{rel}: the extraction's compile failed: {e}") from e
    want = {i["unit"]: i["sha256"] for i in ext.get("inputs") or []}
    have = {u: sha256_bytes(b) for u, b in compiled.units.items()}
    bad = sorted(u for u in set(want) | set(have) if want.get(u) != have.get(u))
    if bad:
        raise Refused(f"{rel}: the compiled units are not the document's extraction inputs: {', '.join(bad[:6])}")
    info = compiler_info(compiled.asts, compiled.layouts, doc.get("contract"))
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_name(cache.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(info, sort_keys=True), encoding="utf-8")
    os.replace(tmp, cache)
    return info


_SECTIONS = ("guards", "checks", "panics", "calls", "writes", "events", "mstores", "loops", "effects", "post")


def refusal_site(action: dict, message: str) -> dict:
    """The record of the action that holds the term a refusal names: {"record", "src"} (a GenError message names the
    term by its head, or an unknown term by its canonical text)."""
    m = re.search(r"term '([^']+)' is outside", message)
    probe = None
    if m:
        probe = json.dumps(m.group(1))
    else:
        m = re.search(r'an unknown term (\["unknown",\s*"[^"]+")', message)
        if m:
            probe = m.group(1).replace(" ", "")
    if probe is None:
        return {"record": None, "src": action.get("src")}
    for sec in _SECTIONS:
        recs = action.get(sec)
        if not isinstance(recs, list):
            continue
        for i, r in enumerate(recs):
            if probe in json.dumps(r, separators=(",", ":")):
                src = r.get("src") if isinstance(r, dict) else None
                return {"record": f"{sec}[{i}]", "src": src or action.get("src")}
    return {"record": None, "src": action.get("src")}


def compile_unit(ctx: Ctx, vid: str, rel: str, p: Path) -> Unit:
    from ..machine import ExtractedModel
    from ..rules.sort import hash_functions
    from ..sorts import model3 as M3
    from ..sorts.evaluate3 import records as parse_records
    u = Unit(vid, rel)
    data = p.read_bytes()
    u.doc = json.loads(data.decode("utf-8"))
    u.sha = sha256_bytes(data)
    u.info = version_info(ctx, rel, u.doc, u.sha)
    full = ExtractedModel(u.doc, u.info, Path(rel), u.sha)
    u.hashes = hash_functions(u.doc) or ["keccak256"]
    acts = sorted(a for a in full.actions if full.params(a) is not None)
    refused = {}
    for a in acts:
        mm = M3.Model3(full, typed=False, sorts={}, seeds={}, init_storage={}, hashes=u.hashes)
        try:
            mm.compile_action(a)
        except M3.GenError as e:
            refused[a] = str(e)
    by = {a["name"]: a for a in u.doc.get("actions") or []}
    u.debt = [dict({"action": a, "reason": refused[a][:600]}, **refusal_site(by.get(a) or {}, refused[a]))
              for a in sorted(refused)]
    kept = dict(u.doc, actions=[a for a in u.doc.get("actions") or [] if a.get("name") not in refused])
    u.model = ExtractedModel(kept, u.info, Path(rel), u.sha)
    u.actions = [a for a in acts if a not in refused]
    header = [f"# GENERATED by holon.versions.model from {rel} (version {vid} of the deployed path), compiled by "
              "holon.sorts.model3 as it compiles the adopted document, untyped; do not edit (fix the generator instead).",
              f"# facts_sha256: {u.sha}",
              f"# model_version: {M3.MODEL3_VERSION} (untyped: the sort section off)",
              "# initial state: the zero storage (the versioned layer starts every trace at its vr0)",
              _comment(f"# model debt: {len(u.debt)} actions the compiler refuses"
                       + (": " + ", ".join(d["action"] for d in u.debt) if u.debt else "")),
              "# chk_<action>(st, ar, en, kh..): 0 when every check holds, k + 1 when check k is the first that fails;",
              f"#   {M3.CALL_CODE} when an external call term reverted, {M3.FUEL_CODE} when a loop ran past its fuel;",
              "# post_<action>, logs_<action>: its post-state and logs; step_<action>: the post-state when chk is 0, "
              "else st."]
    try:
        u.text, _mm = M3.build_text(u.model, typed=False, sorts={}, seeds={}, init={}, hashes=u.hashes, basis=None,
                                    site_rows=[], header=header)
    except M3.GenError as e:
        raise VersionsError(f"{vid}: the compiler refused the version's model after its debt was set aside: {e}") from e
    u.records = parse_records(u.text)
    u.env = [(f, ty, key) for f, ty in u.records.get("HEnv", [])
             for key in [dict(re.findall(r"(?m)^# HEnv\.(\w+): (.*)$", u.text)).get(f)]]
    return u


# ------------------------------------------------------------------------------------------------ the layer
_PRELUDE_TYPES = ("W", "KW", "HSt", "HKB", "HCall", "KB", "HLog", "HOut", "HAns", "DM")


class Layer:
    """The text of the versioned layer over the compiled units."""

    def __init__(self, ctx: Ctx, units: list, fields: dict, admin_slot: int, admin: int):
        self.ctx, self.units, self.fields = ctx, units, fields
        self.admin_slot, self.admin = admin_slot, admin
        self.by = {u.vid: u for u in units}
        self.tabs = [h for h in ("keccak256", "sha256") if any(h in u.hashes for u in units)] or ["keccak256"]
        self.out: list = []
        self.defined: set = set()
        self.venv = self._venv()
        self.debt: list = []      # [{"version", "action", "reason"}]: actions the layer gives no step
        self.claim_info: dict = {}  # init id -> {"function", "versions", "debt"} (claims)

    # -------------------------------------------------- helpers
    @staticmethod
    def tab(h: str) -> str:
        return "kh" if h == "keccak256" else "sh"

    def tab_params(self) -> str:
        return ", ".join(f"+{self.tab(h)}: List<&2, HKB>" for h in self.tabs)

    def tab_args(self) -> str:
        return ", ".join(self.tab(h) for h in self.tabs)

    def unit_tab_args(self, u: Unit) -> str:
        return ", ".join(f"ckh_{u.vid}({self.tab(h)})" for h in u.hashes)

    def emit(self, text: str) -> None:
        for n in re.findall(r"(?m)^(?:def|type)\s+([\w.]+)", text):
            if n in self.defined:
                raise VersionsError(f"the versioned layer would define {n} twice")
            self.defined.add(n)
        self.out.append(text.rstrip("\n") + "\n")

    @staticmethod
    def wlit(x: int) -> str:
        from ..sorts.model3 import wlit
        return wlit(x)

    def _venv(self) -> list:
        seen = {}
        for u in self.units:
            for f, ty, key in u.env:
                if key == "caller" or key is None:
                    continue
                if f in seen and seen[f][0] != ty:
                    raise VersionsError(f"the environment field {f} has type {seen[f][0]} in one version and {ty} in "
                                        f"{u.vid}")
                seen.setdefault(f, (ty, key))
        return sorted((f, ty, key) for f, (ty, key) in seen.items())

    # -------------------------------------------------- conversions
    def vm_type(self, ty: str) -> str:
        """The layer's type of a module's environment field type (the prelude's types are the layer's own)."""
        return ty

    def conv(self, ty: str, k: str, x: str, to: bool = True) -> str:
        """x converted from the layer's value of type ty to module k's (to) or back."""
        if ty in ("Bool", "U32", "List<&2, U32>", "List<&2, List<&2, U32>>"):
            return x
        if ty == "W":
            return f"{'cw' if to else 'wc'}_{k}({x})"
        if ty == "HSt":
            return f"{'cst' if to else 'stc'}_{k}({x})"
        m = re.fullmatch(r"List<&2, (\w+)>", ty)
        if m and m.group(1) in ("W", "KW", "HKB", "HCall", "KB") and to:
            return f"cl{m.group(1)}_{k}({x})"
        if m and m.group(1) == "KW" and not to:
            return f"lKW_{k}({x})"
        raise VersionsError(f"{k}: no conversion of a {ty} value")

    def conversions(self, u: Unit) -> None:
        k, K = u.vid, alias(u.vid)
        ls = ", ".join(f"l{i}" for i in range(8))
        self.emit(f"def cw_{k}(w: W) -> {K}.W:\n  match w:\n    case W{{{ls}}}:\n      {K}.W{{{ls}}}\n")
        self.emit(f"def wc_{k}(w: {K}.W) -> W:\n  match w:\n    case {K}.W{{{ls}}}:\n      W{{{ls}}}\n")
        elems = {"W": ("x", f"cw_{k}(x)"), "KW": ("KW{a, b}", f"{K}.KW{{cw_{k}(a), cw_{k}(b)}}"),
                 "HKB": ("HKB{a, b}", f"{K}.HKB{{a, cw_{k}(b)}}"),
                 "HCall": ("HCall{a, b, c, d}", f"{K}.HCall{{cw_{k}(a), b, c, d}}"),
                 "KB": ("KB{a, b}", f"{K}.KB{{cw_{k}(a), b}}")}
        for e, (pat, val) in elems.items():
            kt = f"{K}.{e}"
            if e == "W":
                body = f"Con{{{val}, cl{e}_{k}(t)}}"
                self.emit(f"def cl{e}_{k}(xs: List<&2, {e}>) -> List<&2, {kt}>:\n  match xs:\n    case Nil{{}}:\n"
                          f"      Nil{{}}\n    case Con{{x, t}}:\n      {body}\n")
                continue
            self.emit(f"def cl{e}_{k}(xs: List<&2, {e}>) -> List<&2, {kt}>:\n  match xs:\n    case Nil{{}}:\n"
                      f"      Nil{{}}\n    case Con{{h, t}}:\n      match h:\n        case {pat}:\n"
                      f"          Con{{{val}, cl{e}_{k}(t)}}\n")
        self.emit(f"def lKW_{k}(xs: List<&2, {K}.KW>) -> List<&2, KW>:\n  match xs:\n    case Nil{{}}:\n      Nil{{}}\n"
                  f"    case Con{{h, t}}:\n      match h:\n        case {K}.KW{{a, b}}:\n"
                  f"          Con{{KW{{wc_{k}(a), wc_{k}(b)}}, lKW_{k}(t)}}\n")
        self.emit(f"def cst_{k}(s: HSt) -> {K}.HSt:\n  match s:\n    case HSt{{sl}}:\n      {K}.HSt{{clKW_{k}(sl)}}\n")
        self.emit(f"def stc_{k}(s: {K}.HSt) -> HSt:\n  match s:\n    case {K}.HSt{{sl}}:\n      HSt{{lKW_{k}(sl)}}\n")
        self.emit(f"def ckh_{k}(xs: List<&2, HKB>) -> List<&2, {K}.HKB>:\n  clHKB_{k}(xs)\n")
        # the environment: the layer's VEnv to the module's HEnv, the caller set
        vfields = [f for f, _t, _k in self.venv]
        fs = []
        for f, ty, key in u.env:
            if key == "caller":
                fs.append(f"cw_{k}(cl)")
            elif f in vfields:
                fs.append(self.conv(ty, k, f))
            elif ty == "W":
                fs.append(f"{K}.w0()")
            else:
                raise VersionsError(f"{k}: the environment field {f} ({ty}) has no value in the layer")
        pat = "VEnv{" + ", ".join(vfields) + "}" if vfields else "VEnv{}"
        self.emit(f"def env_{k}(en: VEnv, +cl: W) -> {K}.HEnv:\n  match en:\n    case {pat}:\n"
                  f"      {K}.HEnv{{{', '.join(fs)}}}\n")
        self.emit(f"def vfin_{k}(o: {K}.HOut, f: VSt) -> VSt:\n  match o:\n    case {K}.HOut{{c, rv, po, lg, tw}}:\n"
                  f"      vpick(U32.is_eq(c, 0), VSt{{VV_{k}{{}}, stc_{k}(po)}}, f)\n")
        self.emit(f"def vokf_{k}(o: {K}.HOut) -> Bool:\n  match o:\n    case {K}.HOut{{c, rv, po, lg, tw}}:\n"
                  "      U32.is_eq(c, 0)\n")

    def vv(self) -> list:
        return [f"VV_{PLACEHOLDER}"] + [f"VV_{u.vid}" for u in self.units]

    # -------------------------------------------------- argument records
    def leaf_params(self, u: Unit, ty: str, n: list, depth: int = 0) -> tuple[list, str]:
        """([(param, layer type)], value code) of a module argument field of type ty, its leaves in ABI order."""
        k, K = u.vid, alias(u.vid)
        if ty in ("W",):
            p = f"p{len(n)}"
            n.append(p)
            return [(p, "W")], f"cw_{k}({p})"
        if ty in ("List<&2, U32>", "List<&2, List<&2, U32>>"):
            p = f"p{len(n)}"
            n.append(p)
            return [(p, ty)], p
        m = re.fullmatch(r"List<&2, W>", ty)
        if m:
            p = f"p{len(n)}"
            n.append(p)
            return [(p, ty)], f"clW_{k}({p})"
        if ty in u.records and ty.startswith("S_") and depth < 8:
            ps, vals = [], []
            for _f, t in u.records[ty]:
                a, v = self.leaf_params(u, t, n, depth + 1)
                ps += a
                vals.append(v)
            return ps, f"{K}.{ty}{{{', '.join(vals)}}}"
        raise VersionsError(f"no argument builder for a {ty} field")

    def builder(self, u: Unit, a: str) -> str:
        from ..machine_bend import bname
        K, ba = alias(u.vid), bname(a)
        rec = f"AR_{ba}"
        ps, vals, n = [], [], []
        for _f, t in u.records.get(rec, []):
            p, v = self.leaf_params(u, t, n)
            ps += p
            vals.append(v)
        sig = ", ".join(f"{p}: {t}" for p, t in ps)
        return f"def ar_{u.vid}_{ba}({sig}) -> {K}.{rec}:\n  {K}.{rec}{{{', '.join(vals)}}}\n"

    # -------------------------------------------------- the PAR-init claims
    def claims(self, acts: list) -> None:
        """For every basis element of rule PAR's init_chain over the versioned documents (holon.rules.par_init): its
        claim pinit_<F>_<o>_<o'>(a, s, e, ..), true unless a is a call of the root site's action at a version where
        it compiles, which succeeds at s with environment e and commits bytes whose cell o differs from their cell o'
        (the bytes the root site hashes: the root action's bytes parameter its committed value hashes). An element
        whose root site hashes anything else at some version, or whose shift is not a whole number of bytes, gets no
        claim (named in the init file: its law stays undecided)."""
        from ..machine_bend import bname
        from ..rules import par_init as PI
        self.claim_info = {}
        try:
            elements = PI.Versioned(self.ctx.milestone, self.ctx.root).basis()
        except (OSError, ValueError, KeyError) as e:
            self.claim_info["error"] = f"{type(e).__name__}: {e}"
            return
        have = {(u.vid, a) for u, a in acts}
        tp, ta = self.tab_params(), self.tab_args()
        for b in elements:
            tag = f"{bname(b['family'])}_{b['cell']}_{b['incr']}"
            info = {"function": f"pinit_{tag}", "versions": [], "debt": []}
            self.claim_info[b["init_id"]] = info
            sh = b["shift"]
            if sh % 8 or not 0 <= sh < 256:
                info["debt"].append(f"shift {sh} is not a whole number of bytes below 256")
                info["function"] = None
                continue
            n = 32 - sh // 8
            cases = []
            for u in self.units:
                if (u.vid, b["root_action"]) not in have:
                    continue
                ch = PI.chains(u.doc)
                fam = next((f for f in ch["families"] if f["family"] == b["family"]), None)
                site = next((r for r in (fam or {}).get("root_sites") or [] if r["action"] == b["root_action"]), None)
                act = next((a for a in u.doc.get("actions") or [] if a.get("name") == b["root_action"]), None)
                if site is None or act is None:
                    continue
                v = act["writes"][int(site["at"][len("writes["):-1])].get("value")
                X = v[1] if isinstance(v, list) and len(v) == 2 else None
                params = {p.get("name"): p for p in u.model.params(b["root_action"]) or []}
                if not (isinstance(X, list) and len(X) == 2 and X[0] == "param" and X[1] in params
                        and params[X[1]].get("type") == "bytes"):
                    info["debt"].append(f"{u.vid}: the root site hashes {json.dumps(X)[:120]}, not a bytes parameter")
                    continue
                info["versions"].append(u.vid)
                ba, K = bname(b["root_action"]), alias(u.vid)
                cases.append((u, ba, K, bname(X[1])))
            if info["debt"]:
                info["function"] = None
                continue
            self.emit(f"# the cells ({b['cell']}, {sh}) and ({b['incr']}, {sh}) of a root input are equal\n"
                      f"def pcell_{tag}(+x: List<&2, U32>) -> Bool:\n"
                      f"  b_eq(b_take({n}n, b_drop(x, {b['cell']}n), 0), b_take({n}n, b_drop(x, {b['incr']}n), 0))\n")
            body = ""
            for u, ba, K, pn in cases:
                self.emit(f"def pic_{u.vid}_{tag}(ok: Bool, ar: {K}.AR_{ba}) -> Bool:\n  match ok:\n"
                          f"    case True{{}}:\n      pcell_{tag}({K}.ga_{ba}_{pn}(ar))\n"
                          "    case False{}:\n      True{}\n")
                body += (f"    case C_{u.vid}_{ba}{{+ar, +cl, en}}:\n"
                         f"      pic_{u.vid}_{tag}(vok(C_{u.vid}_{ba}{{ar, cl, e}}, s, {ta}), ar)\n")
            self.emit(_comment(f"# init {b['init_id']}: a successful call of {b['root_action']} commits a header whose "
                               f"cell {b['cell']} equals its cell {b['incr']}") + "\n"
                      f"def pinit_{tag}(a: VStep, s: VSt, e: VEnv, {tp}) -> Bool:\n  match a:\n{body}"
                      "    case _:\n      True{}\n")

    # -------------------------------------------------- the text
    def edges(self) -> list:
        """[(constructor suffix, from, to, [(reinitializer, unit of the new version)])] of the entry edge and every MIG
        edge of the path."""
        out = []
        e = self.fields["entry"]
        if e:
            out.append(("entry", PLACEHOLDER, e["to"], [r["name"] for r in e["introduced"]]))
        for x in self.fields["edges"]:
            out.append((f"{x['from']}_{x['to']}", x["from"], x["to"], [r["name"] for r in x["introduced"]]))
        return out

    def text(self) -> str:
        from ..machine_bend import bname
        from ..sorts.prelude3 import PRELUDE
        ctx = self.ctx
        tp, ta = self.tab_params(), self.tab_args()
        head = [f"# GENERATED by holon.versions.model: the versioned layer of {ctx.model} over the deployed path "
                f"{', '.join(u.vid for u in self.units)}; do not edit (fix the generator instead).",
                f"# {MODEL_VERSION}; the modules are holon.sorts.model3's untyped models of the per-version documents",
                "# (see their headers); this file holds model3's prelude for its own values and the conversions to "
                "each module's.",
                "import Base"]
        for u in self.units:
            head.append(f"import ./{module_name(ctx.model, u.vid)[:-len('.bend')]}.bend as {alias(u.vid)}")
        self.out = ["\n".join(head) + "\n", PRELUDE]
        self.emit("type VV is Data:\n" + "".join(f"  {c}{{}}\n" for c in self.vv()))
        self.emit("# a state of the versioned machine: its version and the proxy's one storage\n"
                  "type VSt is Data:\n  VSt{v: VV, st: HSt}\n")
        self.emit("def vpick(c: Bool, a: VSt, b: VSt) -> VSt:\n  match c:\n    case True{}:\n      a\n"
                  "    case False{}:\n      b\n")
        vf = ", ".join(f"{f}: {self.vm_type(t)}" for f, t, _k in self.venv)
        doc = "".join(f"# VEnv.{f}: {key}\n" for f, _t, key in self.venv)
        self.emit("# a step's environment (A-env), every field of every version's but the caller (a step's own)\n" + doc
                  + f"type VEnv is Data:\n  VEnv{{{vf}}}\n")
        self.emit("# a mapping step of a layout coordinate: the key word and the slot offset inside the value\n"
                  "type VP is Data:\n  VP{k: W, o: W}\n")
        for c in self.vv():
            self.emit(f"def vis_{c[3:]}(v: VV) -> Bool:\n  match v:\n"
                      + "".join(f"    case {d}{{}}:\n      {'True' if d == c else 'False'}{{}}\n" for d in self.vv()))
        for u in self.units:
            self.conversions(u)
        # the step type
        steps, calls = [], {}
        for sfx, a, b, reinits in self.edges():
            ub = self.by[b]
            opts = []
            for r in reinits:
                if r in ub.actions:
                    opts.append(r)
                else:
                    self.debt.append({"version": b, "action": r, "reason": f"the reinitializer of edge {a}->{b} is "
                                      "model debt of its version: the migration has no call of it"})
            calls[sfx] = (a, b, opts)
            self.emit(f"type UC_{sfx} is Data:\n  UN_{sfx}{{}}\n"
                      + "".join(f"  UK_{sfx}_{bname(r)}{{ar: {alias(b)}.AR_{bname(r)}, en: VEnv}}\n" for r in opts))
            steps.append(f"  U_{sfx}{{c: UC_{sfx}}}\n")
        acts = []
        for u in self.units:
            for a in u.actions:
                try:
                    bt = self.builder(u, a)
                except VersionsError as e:
                    self.debt.append({"version": u.vid, "action": a, "reason": str(e)})
                    continue
                self.emit(bt)
                acts.append((u, a))
                steps.append(f"  C_{u.vid}_{bname(a)}{{ar: {alias(u.vid)}.AR_{bname(a)}, cl: W, en: VEnv}}\n")
        self.emit("# a step of the versioned machine: a migration (A-proxy) or an action of a version by its caller\n"
                  "type VStep is Data:\n" + "".join(steps))
        # the admin and vr0
        self.emit(f"def vadmin_slot() -> W:\n  {self.wlit(self.admin_slot)}\n")
        self.emit("# the proxy's creation: the placeholder version, every slot zero but the admin slot\n"
                  f"def vr0() -> VSt:\n  VSt{{VV_{PLACEHOLDER}{{}}, HSt{{[KW{{vadmin_slot(), {self.wlit(self.admin)}}}]}}}}\n")
        # migrations
        for sfx, a, b, opts in [(s, *calls[s]) for s, *_ in self.edges()]:
            ka = "VV_" + a
            cases = f"    case UN_{sfx}{{}}:\n      VSt{{VV_{b}{{}}, st}}\n"
            okc = f"    case UN_{sfx}{{}}:\n      True{{}}\n"
            ub = self.by[b]
            for r in opts:
                run = (f"{alias(b)}.run_{bname(r)}(cst_{b}(st), ar, env_{b}(en, sload(st, vadmin_slot())), "
                       f"{self.unit_tab_args(ub)})")
                cases += f"    case UK_{sfx}_{bname(r)}{{ar, en}}:\n      vfin_{b}({run}, VSt{{{ka}{{}}, st}})\n"
                okc += f"    case UK_{sfx}_{bname(r)}{{ar, en}}:\n      vokf_{b}({run})\n"
            self.emit(f"def vuc_{sfx}(+st: HSt, c: UC_{sfx}, {tp}) -> VSt:\n  match c:\n{cases}")
            self.emit(f"def vua_{sfx}(go: Bool, v: VV, +st: HSt, c: UC_{sfx}, {tp}) -> VSt:\n  match go:\n"
                      f"    case True{{}}:\n      vuc_{sfx}(st, c, {ta})\n    case False{{}}:\n      VSt{{v, st}}\n")
            self.emit(f"def vu_{sfx}(s: VSt, c: UC_{sfx}, {tp}) -> VSt:\n  match s:\n    case VSt{{+v, +st}}:\n"
                      f"      vua_{sfx}(vis_{a}(v), v, st, c, {ta})\n")
            self.emit(f"def vokuc_{sfx}(+st: HSt, c: UC_{sfx}, {tp}) -> Bool:\n  match c:\n{okc}")
            self.emit(f"def vokua_{sfx}(go: Bool, +st: HSt, c: UC_{sfx}, {tp}) -> Bool:\n  match go:\n"
                      f"    case True{{}}:\n      vokuc_{sfx}(st, c, {ta})\n    case False{{}}:\n      False{{}}\n")
            self.emit(f"def vok_u_{sfx}(s: VSt, c: UC_{sfx}, {tp}) -> Bool:\n  match s:\n    case VSt{{+v, +st}}:\n"
                      f"      vokua_{sfx}(vis_{a}(v), st, c, {ta})\n")
        # actions
        for u, a in acts:
            k, K, ba = u.vid, alias(u.vid), bname(a)
            sig = f"ar: {K}.AR_{ba}, +cl: W, en: VEnv, {tp}"
            go = "Bool.and(vis_{k}(v), Bool.not(w_eq(cl, sload(st, vadmin_slot()))))".format(k=k)
            run = f"{K}.run_{ba}(cst_{k}(st), ar, env_{k}(en, cl), {self.unit_tab_args(u)})"
            self.emit(f"def vca_{k}_{ba}(go: Bool, v: VV, +st: HSt, {sig}) -> VSt:\n  match go:\n"
                      f"    case True{{}}:\n      vfin_{k}({run}, VSt{{v, st}})\n    case False{{}}:\n"
                      "      VSt{v, st}\n")
            self.emit(f"def vc_{k}_{ba}(s: VSt, {sig}) -> VSt:\n  match s:\n    case VSt{{+v, +st}}:\n"
                      f"      vca_{k}_{ba}({go}, v, st, ar, cl, en, {ta})\n")
            self.emit(f"def vokca_{k}_{ba}(go: Bool, +st: HSt, {sig}) -> Bool:\n  match go:\n"
                      f"    case True{{}}:\n      vokf_{k}({run})\n    case False{{}}:\n      False{{}}\n")
            self.emit(f"def vok_c_{k}_{ba}(s: VSt, {sig}) -> Bool:\n  match s:\n    case VSt{{+v, +st}}:\n"
                      f"      vokca_{k}_{ba}({go}, st, ar, cl, en, {ta})\n")
        cases, okc = "", ""
        for sfx, *_ in self.edges():
            cases += f"    case U_{sfx}{{c}}:\n      vu_{sfx}(s, c, {ta})\n"
            okc += f"    case U_{sfx}{{c}}:\n      vok_u_{sfx}(s, c, {ta})\n"
        for u, a in acts:
            k, ba = u.vid, bname(a)
            cases += f"    case C_{k}_{ba}{{ar, cl, en}}:\n      vc_{k}_{ba}(s, ar, cl, en, {ta})\n"
            okc += f"    case C_{k}_{ba}{{ar, cl, en}}:\n      vok_c_{k}_{ba}(s, ar, cl, en, {ta})\n"
        self.emit("# the state after step x from s (s itself when the step reverts)\n"
                  f"def vstep(x: VStep, s: VSt, {tp}) -> VSt:\n  match x:\n{cases}")
        self.emit("# whether step x succeeds at s\n"
                  f"def vok(x: VStep, s: VSt, {tp}) -> Bool:\n  match x:\n{okc}")
        self.emit(f"def vrun(xs: List<&2, VStep>, s: VSt, {tp}) -> VSt:\n  match xs:\n    case Nil{{}}:\n      s\n"
                  f"    case Con{{x, rest}}:\n      vrun(rest, vstep(x, s, {ta}), {ta})\n")
        idx = ", ".join(f"-{self.tab(h)}: List<&2, HKB>" for h in self.tabs)
        ix = ", ".join(self.tab(h) for h in self.tabs)
        self.emit("# the reachable states of the versioned machine: the proxy's creation and one step of any kind\n"
                  f"type VReach<{idx}, -s: VSt> is Type:\n  VR0{{e: {{s == vr0() : VSt}}}}\n"
                  f"  VRStep{{x: VStep, p: VSt, r: VReach<{ix}, p>, e: {{s == vstep(x, p, {ix}) : VSt}}}}\n")
        kh = self.tab("keccak256")
        self.emit("# the real slot of a layout coordinate's mapping steps from slot l\n"
                  f"def vloc(p: List<&2, VP>, l: W, +{kh}: List<&2, HKB>) -> W:\n  match p:\n    case Nil{{}}:\n"
                  f"      l\n    case Con{{h, t}}:\n      match h:\n        case VP{{k, o}}:\n"
                  f"          vloc(t, w_add(h_get({kh}, List.append(&2, U32, b_of_w(k), b_of_w(l))), o), {kh})\n")
        self.emit("# the word at the storage location of layout coordinate (b, o, p)\n"
                  f"def vread(s: VSt, b: W, o: W, p: List<&2, VP>, {tp}) -> W:\n  match s:\n    case VSt{{v, st}}:\n"
                  f"      sload(st, vloc(p, w_add(b, o), {kh}))\n")
        self.claims(acts)
        for u in self.units:
            k, K = u.vid, alias(u.vid)
            args = self.unit_tab_args(u)
            self.emit(f"# one step of an action of {k} (its module's step), on the layer's storage\n"
                      f"def step_{k}(a: {K}.HAct, +s: HSt, {tp}) -> HSt:\n  stc_{k}({K}.step(a, cst_{k}(s), {args}))\n")
            self.emit(f"# a trace of actions of {k} (its module's run)\n"
                      f"def run_{k}(tr: List<&2, {K}.HAct>, s: HSt, {tp}) -> HSt:\n"
                      f"  stc_{k}({K}.run(tr, cst_{k}(s), {args}))\n")
        return "\n".join(p.rstrip("\n") + "\n" for p in self.out if p)


# ------------------------------------------------------------------------------------------------ build and CLI
def deployment_admin(ctx: Ctx) -> tuple[int, int]:
    slot = int(str(ctx.side["proxy"]["admin_slot"]), 16)
    rec = ctx.deployment_record()
    words = [int(str(v), 16) for k, v in (rec.get("storage") or {}).items() if int(str(k), 16) == slot]
    if len(words) != 1 or not words[0]:
        raise Refused(f"{ctx.inputs['deployment_record']} holds no proxy admin at the admin slot")
    return slot, words[0]


def build(ctx: Ctx, log=None) -> tuple[dict, list]:
    """({relative path: bytes} of every file model writes, the compiled units)."""
    vd = ctx.versions_doc()
    docs = ctx.documents()
    units = []
    for vid in vd["path"]:
        if vid not in docs:
            continue
        p, rel = docs[vid]
        u = compile_unit(ctx, vid, rel, p)
        units.append(u)
        if log:
            log(f"{vid}: {len(u.actions)} actions, {len(u.debt)} model debt"
                + (f" ({', '.join(d['action'] for d in u.debt)})" if u.debt else ""))
    slot, admin = deployment_admin(ctx)
    lay = Layer(ctx, units, vd, slot, admin)
    text = lay.text()
    md = ctx.out("model_dir")
    files = {f"{md}/{module_name(ctx.model, u.vid)}": u.text.encode("utf-8") for u in units}
    files[f"{md}/{stem(ctx.model)}.bend"] = text.encode("utf-8")
    init = {"model_version": MODEL_VERSION, "model": ctx.model, "versioned_document": {"path": ctx.out("versions"), "sha256": sha256_file(ctx.root / ctx.out("versions"))},
            "deployment_record": {"path": ctx.inputs["deployment_record"],
                                  "sha256": sha256_file(ctx.input_path("deployment_record"))},
            "vr0": {"version": PLACEHOLDER, "admin_slot": "0x%064x" % slot, "admin": "0x%064x" % admin},
            "hashes": lay.tabs,
            "layer": {"module": f"{stem(ctx.model)}.bend", "sha256": sha256_bytes(text.encode("utf-8")),
                      "debt": lay.debt, "venv": [list(x) for x in lay.venv], "claims": lay.claim_info},
            "versions": {u.vid: {"document": u.rel, "document_sha256": u.sha,
                                 "module": module_name(ctx.model, u.vid),
                                 "module_sha256": sha256_bytes(u.text.encode("utf-8")),
                                 "hashes": u.hashes, "actions": u.actions, "debt": u.debt} for u in units},
            "debt_versions": [d["version"] for d in vd.get("debt") or []]}
    files[f"{md}/{ctx.model}.init.json"] = render(init)
    return files, units


def link_name(ctx: Ctx) -> tuple[str, str]:
    md = ctx.out("model_dir")
    return f"{md}/{ctx.model}.bend", f"{stem(ctx.model)}.bend"


def run(ctx: Ctx, check: bool) -> int:
    files, _units = build(ctx, log=lambda m: print(f"holon versions model: {m}"))
    link, target = link_name(ctx)
    lp = ctx.root / link
    if check:
        bad = [rel for rel, data in sorted(files.items()) if not write_or_check(ctx.root / rel, data, True)]
        if not (lp.is_symlink() and os.readlink(lp) == target):
            bad.append(link)
        for rel in bad:
            print(f"holon versions model: {rel} differs from a fresh build", file=sys.stderr)
        print(f"holon versions model: {len(files) + 1 - len(bad)} of {len(files) + 1} files reproduce")
        return 1 if bad else 0
    md = ctx.root / ctx.out("model_dir")
    md.mkdir(parents=True, exist_ok=True)
    keep = {Path(rel).name for rel in files} | {Path(link).name}
    for p in sorted(md.iterdir()):
        if p.name not in keep and (p.suffix == ".bend" or p.name.endswith(".init.json")):
            p.unlink()
    for rel, data in sorted(files.items()):
        write_or_check(ctx.root / rel, data, False)
    if lp.is_symlink() or lp.exists():
        lp.unlink()
    os.symlink(target, lp)
    print(f"holon versions model: wrote {len(files)} files and the link {link}")
    return 0
