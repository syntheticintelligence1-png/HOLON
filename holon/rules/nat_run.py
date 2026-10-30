"""Rule NAT's analysis, claims module and decider over I28's versioned machine (BUILD_PLAN I29; the contract is the
docstring of tests_m3/test_nat.py, rules N4, N6-N8).

  python -m holon nat analyze [--check]     N2-N4 and N6: gen/<M>/nat/nat.json and the claims module
  python -m holon nat replay [--check]      N9: the REFUTED witnesses on the real code (holon.rules.nat_replay)
  python -m holon run --milestone M --laws <ids>   N7: the NAT laws of the list (holon.__main__ routes them here)

The claims module (gen/<M>/nat/models/<stem>_nat.bend) imports the versioned layer as M and holds, per basis element,
the square's claim function nat_sq_<a>_<b>_<op>(s, <the op's arguments>, cl, en, u, kh): the migration u then the op at
b, against the op at a then u, compared by version, by storage (every slot either storage list holds) and by the success
of the op and of u on each side. The decider searches the versioned machine (holon.versions.machine, evaluated, never
trusted) for a state and a square whose claim is false, writes the counter-law and its proof by computation over the
layer, and lets Bend decide (AGENTS rule 6). No generator proves a NAT law.

Nothing here names a target: the edges, functions, actions and arguments come from the versioned document, the
deployment record and the sidecars.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

from . import nat as N

SIDECAR = "spec/{}/lib/nat.json"
NAT_VERSION = "holon-nat/0.1"
GEN_NAT = ["holon/rules/nat.py", "holon/rules/nat_run.py", "holon/rules/par_init.py", "holon/versions/machine.py",
           "holon/versions/model.py", "holon/versions/proofs.py", "holon/versions/bendlit.py", "holon/versions/paths.py",
           "holon/versions/__init__.py"]
MASK = (1 << 256) - 1


class NatRefused(Exception):
    """Exit 2: an input is missing or is not the one the versioned document records; nothing is written."""


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------------ the context
class NatCtx:
    """The NAT sidecar, I28's versions context, and the paths NAT reads and writes."""

    def __init__(self, root: Path, milestone: str = "M3"):
        from ..versions import Ctx, Refused
        self.root = Path(root).resolve()
        self.milestone = milestone
        sp = self.root / SIDECAR.format(milestone)
        if not sp.is_file():
            raise NatRefused(f"{SIDECAR.format(milestone)} is missing")
        self.side = json.loads(sp.read_text(encoding="utf-8"))
        if self.side.get("nat_version") != NAT_VERSION:
            raise NatRefused(f"{SIDECAR.format(milestone)}: nat_version is not {NAT_VERSION}")
        try:
            self.vctx = Ctx(self.root, self.side["inputs"]["versions_sidecar"])
        except Refused as e:
            raise NatRefused(str(e)) from e

    def out(self, key: str) -> str:
        return self.side["outputs"][key]

    def layer_path(self) -> Path:
        from ..versions.model import stem
        return self.root / self.vctx.out("model_dir") / f"{stem(self.vctx.model)}.bend"

    def model_link(self) -> Path:
        return self.root / self.vctx.out("model_dir") / f"{self.vctx.model}.bend"

    def module_path(self) -> Path:
        return self.root / self.out("model_dir") / self.out("module")

    def versioned(self):
        try:
            return N.versioned(self.milestone, self.root)
        except (OSError, KeyError, ValueError) as e:
            raise NatRefused(f"the versioned document cannot be read: {type(e).__name__}: {e}") from e

    def gap_meta(self) -> dict:
        g = (self.side.get("gaps") or {}).get("native") or {}
        if "obligation" not in g or "question" not in g:
            raise NatRefused("sidecar gaps.native is missing its obligation or question")
        return {"obligation": g["obligation"], "question": g["question"], "status": "open"}


def rel_import(frm: Path, target: Path) -> str:
    from ..versions.proofs import rel_import as ri
    return ri(frm, target)


# ------------------------------------------------------------------------------------------------ the claims module
_AR = re.compile(r"(?m)^def ar_(\w+?)_(\w+)\((.*)\) -> ")
_CTOR = re.compile(r"(?m)^  (C_\w+)\{ar: ")
_VV = re.compile(r"(?ms)^type VV is Data:\n((?:  \w+\{\}\n)+)")


def claim_name(el: dict) -> str:
    from ..machine_bend import bname
    a, b = el["edge"].split("->")
    return f"nat_sq_{a}_{b}_{bname(el['op'])}"


def ar_params(layer_text: str, vid: str, op: str) -> list | None:
    """[(name, type)] of the layer's argument builder ar_<vid>_<op>, or None when the layer has none."""
    from ..machine_bend import bname
    m = re.search(rf"(?m)^def ar_{re.escape(vid)}_{re.escape(bname(op))}\((.*)\) -> ", layer_text)
    if m is None:
        return None
    ps = [x.strip() for x in re.split(r",\s*(?![^<]*>)", m.group(1)) if x.strip()]
    out = []
    for p in ps:
        n, t = p.split(":", 1)
        out.append((n.strip(), t.strip()))
    return out


def element_debt(layer_text: str, el: dict) -> str | None:
    """Why the layer cannot state this square (an action or argument builder missing at either version), or None."""
    from ..machine_bend import bname
    a, b = el["edge"].split("->")
    ctors = set(_CTOR.findall(layer_text))
    for v in (a, b):
        if f"C_{v}_{bname(el['op'])}" not in ctors:
            return f"{el['op']} is no action of {v} in the versioned model (model debt)"
    pa, pb = ar_params(layer_text, a, el["op"]), ar_params(layer_text, b, el["op"])
    if pa is None or pb is None or [t for _, t in pa] != [t for _, t in pb]:
        return f"{el['op']}'s argument builders differ between {a} and {b} in the versioned model"
    if f"type UC_{a}_{b} is Data:" not in layer_text:
        return f"the versioned model has no migration step type UC_{a}_{b}"
    return None


def layer_type(t: str) -> str:
    """A layer parameter type as the claims module writes it (the layer's own types qualified by M)."""
    t = re.sub(r"\bW\b", "M.W", t)
    return t


def module_text(layer_text: str, layer_import: str, elements: list, model: str) -> str:
    from ..machine_bend import bname
    vv = _VV.search(layer_text)
    if vv is None:
        raise NatRefused("the versioned layer has no type VV")
    versions = re.findall(r"  (\w+)\{\}", vv.group(1))
    lines = [f"# GENERATED by holon.rules.nat_run: rule NAT's square claims over the versioned layer of {model}; do not "
             "edit (fix the generator instead).",
             "# A claim is true when, from the state, the migration then the op at the new version and the op at the old "
             "version then the migration end in the same version and storage, the op and the migration each succeeding "
             "on both sides or on neither.",
             "import Base", f"import {layer_import} as M", "",
             "def nat_vcode(v: M.VV) -> U32:", "  match v:"]
    for i, c in enumerate(versions):
        lines += [f"    case M.{c}{{}}:", f"      {i}"]
    lines += ["",
              "def nat_beq(a: Bool, b: Bool) -> Bool:", "  match a:", "    case True{}:", "      b", "    case False{}:",
              "      Bool.not(b)", "",
              "# every slot of the list reads the same word in both storages",
              "def nat_agree(xs: List<&2, M.KW>, +l: List<&2, M.KW>, +r: List<&2, M.KW>) -> Bool:", "  match xs:",
              "    case Nil{}:", "      True{}", "    case Con{h, t}:", "      match h:", "        case M.KW{+k, v}:",
              "          Bool.and(M.w_eq(M.kw_get(l, k), M.kw_get(r, k)), nat_agree(t, l, r))", "",
              "def nat_hst_eq(l: M.HSt, r: M.HSt) -> Bool:", "  match l r:", "    case M.HSt{+ls} M.HSt{+rs}:",
              "      Bool.and(nat_agree(ls, ls, rs), nat_agree(rs, ls, rs))", "",
              "def nat_vst_eq(l: M.VSt, r: M.VSt) -> Bool:", "  match l r:", "    case M.VSt{lv, ls} M.VSt{rv, rs}:",
              "      Bool.and(U32.is_eq(nat_vcode(lv), nat_vcode(rv)), nat_hst_eq(ls, rs))", "",
              "# the square's verdict: the two ends agree, the op's success agrees, the migration's success agrees",
              "def nat_cmp(l: M.VSt, r: M.VSt, lo: Bool, ro: Bool, lu: Bool, ru: Bool) -> Bool:",
              "  Bool.and(nat_vst_eq(l, r), Bool.and(nat_beq(lo, ro), nat_beq(lu, ru)))", ""]
    done = set()
    for el in elements:
        if element_debt(layer_text, el) or claim_name(el) in done:
            continue
        done.add(claim_name(el))   # one claim per square (edge, op): the laws of several in-flight types share it
        a, b = el["edge"].split("->")
        op = bname(el["op"])
        ps = ar_params(layer_text, a, el["op"])
        names = [f"p{i}" for i in range(len(ps))]
        sig = ", ".join([f"+s: M.VSt"] + [f"+{n}: {layer_type(t)}" for n, (_, t) in zip(names, ps)]
                        + ["+cl: M.W", "+en: M.VEnv", f"+u: M.UC_{a}_{b}", "+kh: List<&2, M.HKB>"])
        args = ", ".join(names)
        xa = f"M.C_{a}_{op}{{M.ar_{a}_{op}({args}), cl, en}}"
        xb = f"M.C_{b}_{op}{{M.ar_{b}_{op}({args}), cl, en}}"
        mu = f"M.U_{a}_{b}{{u}}"
        lines += [f"# the square of {el['op']} across {el['edge']}",
                  f"def {claim_name(el)}({sig}) -> Bool:",
                  f"  +l1 = M.vstep({mu}, s, kh)",
                  f"  +r1 = M.vstep({xa}, s, kh)",
                  f"  nat_cmp(M.vstep({xb}, l1, kh), M.vstep({mu}, r1, kh), M.vok({xb}, l1, kh), M.vok({xa}, s, kh), "
                  f"M.vok({mu}, s, kh), M.vok({mu}, r1, kh))", ""]
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------ analyze
def analysis_doc(nctx: NatCtx) -> tuple[dict, list]:
    vd = nctx.versioned()
    an = N.analysis(vd.doc, vd.docs, vd.model)
    meta = nctx.gap_meta()
    doc = {"nat_version": NAT_VERSION, "versioned": {"path": vd.rel, "sha256": vd.sha}, "model": vd.model,
           "composition": an["composition"], "naturality": an["naturality"],
           "native_gaps": [dict(g, **meta) for g in an["native_gaps"]]}
    return doc, N.elements(an)


def analyze(nctx: NatCtx, check: bool) -> int:
    from ..versions import write_or_check
    doc, els = analysis_doc(nctx)
    lp = nctx.layer_path()
    if not lp.is_file():
        raise NatRefused(f"{lp.relative_to(nctx.root)} is missing: run `holon versions model` first")
    mp = nctx.module_path()
    text = module_text(lp.read_text(encoding="utf-8"), rel_import(mp.parent, lp), els, nctx.vctx.model)
    ok1 = write_or_check(nctx.root / nctx.out("analysis"), dumps(doc).encode("utf-8"), check)
    ok2 = write_or_check(mp, text.encode("utf-8"), check)
    if check:
        ok = ok1 and ok2
        print(f"holon nat analyze: {nctx.out('analysis')} and {mp.relative_to(nctx.root)} "
              f"{'reproduce' if ok else 'differ from a fresh analysis'}")
        return 0 if ok else 1
    print(f"holon nat analyze: wrote {nctx.out('analysis')} ({len(doc['composition'])} composition, "
          f"{len(doc['naturality'])} naturality, {len(doc['native_gaps'])} native gaps) and "
          f"{mp.relative_to(nctx.root)}")
    return 0


# ------------------------------------------------------------------------------------------------ the search
def _storage(sl: list) -> dict:
    from ..versions.machine import storage_of
    return {k: v for k, v in storage_of(sl).items() if v}


def state_key(state: dict) -> tuple:
    return (state["version"], tuple(sorted(_storage(state["sl"]).items())))


class Search:
    """Rule N7 over the versioned machine: the breadth-first states and the squares tried at them."""

    def __init__(self, nctx: NatCtx, m):
        self.nctx = nctx
        self.m = m
        self.budget = int((nctx.side.get("search") or {}).get("max_trace", 10))
        side = nctx.vctx.side
        self.args = dict((side.get("upgrade_path") or {}).get("arguments") or {})
        self.args.update({k: v for k, v in (side.get("inflight_arguments") or {}).items() if k != "doc"})
        self._levels = None

    # ---------------------------------------------------------- candidate steps
    def reinit_call(self, vid: str, name: str, state: dict) -> str | None:
        """The calldata of an initializer called at version vid: I28's upgrade-path arguments (inflight_arguments over
        them), else the deployment record's call of its selector; None when neither gives one."""
        from ..versions.paths import reinit_calldata
        fn = self.m.function(vid, name)
        if fn is None:
            return None
        if name in self.args:
            return reinit_calldata(self.m, vid, name, self.args[name], state)
        sel = (fn["selector"] or "").removeprefix("0x")
        for c in self.m.dep.get("calls") or []:
            if sel and c["data"][2:10] == sel:
                return c["data"]
        return None

    def migrations(self, a: str, b: str, state: dict) -> list:
        """The candidate migration steps along a -> b: upgradeToAndCall with each initializer the edge introduces, then
        upgradeTo."""
        e = self.m.edges[(a, b)]
        out = []
        for r in e.get("introduced") or []:
            if r["name"] not in self.m.actions(b):
                continue
            cd = self.reinit_call(b, r["name"], state)
            if cd is not None:
                out.append(self.m.migrate_step(a, b, r["name"], cd))
        out.append(self.m.migrate_step(a, b, None))
        return out

    def candidates(self, state: dict) -> list:
        from ..versions.machine import num
        m = self.m
        v = state["version"]
        out = []
        nxt = sorted(b for (a, b) in m.edges if a == v)
        if nxt:
            out += self.migrations(v, nxt[0], state)
        if v in m.path:
            for c in m.dep.get("calls") or []:
                for name in m.actions(v):
                    fn = m.function(v, name)
                    if fn and fn["selector"] and c["data"][2:10] == fn["selector"].removeprefix("0x"):
                        out.append(m.call_step(v, name, num(c["caller"]), c["data"]))
        return out

    def levels(self) -> list:
        """[[(trace, state)]] by trace length 0 .. max_trace, each state reached first there (breadth first)."""
        if self._levels is not None:
            return self._levels
        m = self.m
        s0 = m.initial()
        seen = {state_key(s0)}
        levels = [[([], s0)]]
        for _depth in range(self.budget):
            nxt = []
            for trace, state in levels[-1]:
                for st in self.candidates(state):
                    o = m.step(state, st)
                    if o["status"] != "ok":
                        continue
                    k = state_key(o["state"])
                    if k in seen:
                        continue
                    seen.add(k)
                    nxt.append((trace + [dict(st, ok=True)], o["state"]))
            levels.append(nxt)
        self._levels = levels
        return levels

    # ---------------------------------------------------------- the square
    def op_calls(self, vid: str, op: str, state: dict) -> list:
        """[(caller, calldata)] of the op's candidate calls at version vid (sidecar search.op_calls)."""
        from ..evm_abi import encode_call
        from ..versions.bendlit import Lit
        from ..versions.machine import num
        m = self.m
        fn = m.function(vid, op)
        if fn is None:
            return []
        calls = m.dep.get("calls") or []
        sel = (fn["selector"] or "").removeprefix("0x")
        rec = [(num(c["caller"]), c["data"]) for c in calls if sel and c["data"][2:10] == sel]
        if rec:
            return rec
        callers = []
        for c in calls:
            if num(c["caller"]) not in callers:
                callers.append(num(c["caller"]))
        first = callers[:1]
        if op in self.args:
            cd = self.reinit_call(vid, op, state)
            return [(first[0], cd)] if cd and first else []
        # the zero call, then each bytes argument of the deployment record's calls in every bytes parameter
        blobs = []
        for c in calls:
            v0 = m.path[0]
            for name in m.actions(v0):
                f = m.function(v0, name)
                if f and f["selector"] and c["data"][2:10] == f["selector"].removeprefix("0x"):
                    for node in Lit("M").leaves(f["inputs"], c["data"]):
                        if node[0] == "b" and node[1] not in blobs:
                            blobs.append(node[1])
        ins = fn["inputs"]

        def call(bs: bytes) -> str | None:
            vals = {}
            for p in ins:
                if p["type"] in ("bytes", "string"):
                    vals[p["name"]] = bs if p["type"] == "bytes" else bs.decode("latin-1")
                elif re.fullmatch(r"u?int\d*|address|bool|bytes\d+", p["type"]):
                    vals[p["name"]] = False if p["type"] == "bool" else (b"\0" * int(p["type"][5:])
                                                                      if p["type"].startswith("bytes") else 0)
                else:
                    return None
            try:
                return encode_call({"name": op, "inputs": ins}, vals)
            except Exception:  # noqa: BLE001  (a parameter shape this rule does not fill)
                return None
        cds = [cd for cd in [call(b"")] + [call(b) for b in blobs if any(p["type"] == "bytes" for p in ins)] if cd]
        seen, out = set(), []
        for cd in cds:
            for cl in callers:
                if (cl, cd) not in seen:
                    seen.add((cl, cd))
                    out.append((cl, cd))
        return out

    def square(self, state: dict, el: dict, caller: int, cd: str, mig: dict) -> dict:
        """The square at a state: its four steps' outcomes and whether its claim holds on the machine."""
        a, b = el["edge"].split("->")
        m = self.m
        xa = m.call_step(a, el["op"], caller, cd)
        xb = m.call_step(b, el["op"], caller, cd)
        l1 = m.step(state, mig)
        l2 = m.step(l1["state"], xb)
        r1 = m.step(state, xa)
        r2 = m.step(r1["state"], mig)
        L, R = l2["state"], r2["state"]
        same = L["version"] == R["version"] and _storage(L["sl"]) == _storage(R["sl"])
        holds = same and (l2["status"] == r1["status"]) and (l1["status"] == r2["status"])
        return {"holds": holds, "steps": {"mig": mig, "xa": xa, "xb": xb}, "outs": {"l1": l1, "l2": l2, "r1": r1,
                                                                                   "r2": r2}}

    def find(self, el: dict) -> tuple:
        """(the witness (trace, state, square) or None, what was tried)."""
        a, b = el["edge"].split("->")
        tried = {"states": 0, "squares": 0, "reached": 0}
        for lv in self.levels():
            tried["reached"] += len(lv)
            for trace, state in lv:
                if state["version"] != a:
                    continue
                tried["states"] += 1
                for caller, cd in self.op_calls(a, el["op"], state):
                    for mig in self.migrations(a, b, state):
                        tried["squares"] += 1
                        sq = self.square(state, el, caller, cd, mig)
                        if not sq["holds"]:
                            return (trace, state, sq), tried
        return None, tried


# ------------------------------------------------------------------------------------------------ the Bend files
def law_name(lid: str, counter: bool) -> str:
    return ("cl_" if counter else "") + lid.lower()


def laws_text(law: dict, sh: str, layer_import: str, module_import: str, el: dict, params: list, counter: bool) -> str:
    a, b = el["edge"].split("->")
    q = "exs" if counter else "for"
    names = [f"p{i}" for i in range(len(params))]
    lines = ["# GENERATED by holon.rules.nat_run from the frozen law IR; do not edit.",
             f"# law_id: {law['law_id']}   statement_hash: {sh}", "import Base", f"import {layer_import} as M",
             f"import {module_import} as N", "", f"law {law_name(law['law_id'], counter)}:",
             f"  {q} kh: List<&2, M.HKB>", f"  {q} s: M.VSt", f"  {q} r: M.VReach<kh, s>"]
    lines += [f"  {q} {n}: {layer_type(t)}" for n, (_, t) in zip(names, params)]
    lines += [f"  {q} cl: M.W", f"  {q} e: M.VEnv", f"  {q} u: M.UC_{a}_{b}",
              f"  {{N.{claim_name(el)}(s, {', '.join(names + ['cl', 'e', 'u', 'kh'])}) {'!=' if counter else '=='} "
              f"True{{}} : Bool}}", ""]
    return "\n".join(lines)


def law_file(law: dict, milestone: str, root, statement_hash: str, counter: bool, gen: Path | None = None) -> str:
    """A NAT law's LAWS.bend as the decider writes it under gen/<M>/laws/<id>/ (laws_text over the layer and the claims
    module): the bound statement and counter-law (holon.bindings)."""
    root = Path(root)
    nctx = NatCtx(root, milestone)
    e = nat_entries(milestone, root).get(law["law_id"])
    if e is None:
        raise KeyError(f"{law['law_id']} is not a NAT law of {milestone}")
    el = e["basis"]
    layer_text = nctx.layer_path().read_text(encoding="utf-8")
    d = (Path(gen) if gen else root / "gen" / milestone) / "laws" / law["law_id"]
    params = ar_params(layer_text, el["edge"].split("->")[0], el["op"]) or []
    return laws_text(law, statement_hash, rel_import(d, nctx.layer_path()), rel_import(d, nctx.module_path()), el,
                     params, counter)


def venv_union(envs: list) -> dict:
    """One environment for several runs of the same call: the first's fields, every run's external calls (each once,
    in first-seen order) and every run's code table."""
    base = dict(envs[0])
    calls, seen, code = [], set(), {}
    for e in envs:
        for c in e.get("calls") or []:
            k = (c.get("to"), c.get("data"))
            if k not in seen:
                seen.add(k)
                calls.append(c)
        code.update(e.get("code") or {})
    base["calls"] = calls
    base["code"] = dict(sorted(code.items()))
    return base


def uc_literal(lit, m, mig: dict, env: dict | None) -> str:
    from ..machine_bend import bname
    p = lit.p
    sfx = "entry" if mig["label"] == "entry" else mig["label"].replace("->", "_")
    if not mig.get("call"):
        return f"{p}.UN_{sfx}{{}}"
    b, r = mig["version"], mig["call"]
    fn = m.function(b, r)
    args = ", ".join(lit.arg_literals(lit.leaves(fn["inputs"], mig["calldata"])))
    return f"{p}.UK_{sfx}_{bname(r)}{{{p}.ar_{b}_{bname(r)}({args}), {lit.venv(m.venv_fields(), env)}}}"


def counter_proof(law: dict, el: dict, m, imports: tuple, trace: list, outs: list, kh: dict, sq: dict,
                  params: list) -> str:
    from ..versions.bendlit import Lit
    from ..versions.proofs import reach_def, trace_defs
    from ..versions.machine import num
    layer_import, module_import, laws_import = imports
    lit = Lit("M")
    n = len(trace)
    st = sq["steps"]
    o = sq["outs"]
    env_x = venv_union([x["env"] for x in (o["r1"], o["l2"]) if x.get("env")] or [{}])
    env_u = venv_union([x["env"] for x in (o["l1"], o["r2"]) if x.get("env")] or [{}]) if st["mig"].get("call") else None
    vals = lit.arg_literals(lit.leaves(m.function(el["edge"].split("->")[0], el["op"])["inputs"], st["xa"]["calldata"]))
    lines = ["# GENERATED by holon.rules.nat_run; untrusted, accepted only if Bend checks it.", "import Base",
             f"import {layer_import} as M", f"import {module_import} as N", f"import {laws_import} as Laws", ""]
    defs = trace_defs(lit, m, trace, outs, kh) if n else [
        f"def t_kh() -> List<&2, M.HKB>:\n  {lit.table(kh)}\n", "def s_0() -> M.VSt:\n  M.vr0()\n"]
    defs.append(reach_def("M", n, "reach_w"))
    names = []
    for i, ((_, t), v) in enumerate(zip(params, vals)):
        defs.append(f"def p_{i}() -> {layer_type(t)}:\n  {v}\n")
        names.append(f"p_{i}()")
    defs.append(f"def c_w() -> M.W:\n  {lit.word(num(st['xa']['caller']))}\n")
    defs.append(f"def e_w() -> M.VEnv:\n  {lit.venv(m.venv_fields(), env_x)}\n")
    a, b = el["edge"].split("->")
    defs.append(f"def u_w() -> M.UC_{a}_{b}:\n  {uc_literal(lit, m, st['mig'], env_u)}\n")
    call = f"N.{claim_name(el)}(s_{n}(), {', '.join(names + ['c_w()', 'e_w()', 'u_w()', 't_kh()'])})"
    defs.append(f"def cz() -> {{{call} == False{{}} : Bool}}:\n  {{==}}\n")
    defs.append("def is_true(b: Bool) -> Type:\n  match b:\n    case True{}:\n      Unit\n    case False{}:\n"
                "      Empty\n")
    defs.append("def true_ne_false(p: {True{} == False{} : Bool}) -> Empty:\n  (%p : is_true(_)\n  Unit{})\n")
    wit = ["t_kh()", f"s_{n}()", "reach_w()"] + names + ["c_w()", "e_w()", "u_w()"]
    body = "e => true_ne_false((%e : {_ == False{} : Bool}\n  cz()))"
    for w in reversed(wit):
        body = f"({w}, {body})"
    defs.append(f"def Laws.{law_name(law['law_id'], True)}():\n  {body}\n")
    return "\n".join(lines) + "\n" + "\n".join(defs)


# ------------------------------------------------------------------------------------------------ deciding
def generator_sha256(root: Path) -> str:
    """The digest of the NAT deciders' closure: these modules, their holon imports and I30's runner closure."""
    from ..records import _holon_imports
    from ..sorts.run3 import GEN3
    seen, todo = set(), list(GEN_NAT) + list(GEN3)
    while todo:
        r = todo.pop()
        if r in seen or not (root / r).is_file():
            continue
        seen.add(r)
        if r.endswith(".py"):
            todo.extend(sorted(_holon_imports(r, root) - seen))
    h = hashlib.sha256()
    for r in sorted(seen):
        h.update(r.encode() + b"\0" + (root / r).read_bytes() + b"\0")
    return h.hexdigest()


def nat_entries(milestone: str, root: Path) -> dict:
    try:
        dv = json.loads((Path(root) / "laws" / milestone / "DERIVATION.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {e["law_id"]: e for e in dv.get("laws") or [] if isinstance(e, dict) and e.get("rule") == N.RULE}


def model_debt(nctx: NatCtx, vid: str) -> list:
    init = json.loads((nctx.root / nctx.vctx.out("model_dir") / f"{nctx.vctx.model}.init.json").read_text())
    return [d["action"] for d in ((init.get("versions") or {}).get(vid) or {}).get("debt") or []]


class Decider:
    def __init__(self, nctx: NatCtx, results: Path, gen: Path):
        from ..versions.machine import Machine
        from .. import ir
        self.nctx = nctx
        self.root = nctx.root
        self.results = results
        self.gen = gen
        self.m = Machine(nctx.vctx)
        self.search = Search(nctx, self.m)
        self.registry = ir.load_registry(nctx.milestone, self.root)
        self.entries = nat_entries(nctx.milestone, self.root)
        self.layer_text = nctx.layer_path().read_text(encoding="utf-8")

    def close(self):
        self.m.close()

    def rel(self, p: Path) -> str:
        p = Path(p)
        try:
            return (p.parent.resolve() / p.name).relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return p.as_posix()

    def check(self, proof: Path) -> dict:
        from .. import bend
        r = bend.check(proof)
        out = {"exit_code": r.code, "marker": r.marker, "seconds": r.seconds}
        verdict = "not_run"
        if r.ok and bend.verdict_enabled():
            v = bend.check_verdict(proof)
            verdict = "checked" if v.ok else "failed"
            out["verdict"] = {"exit_code": v.code, "marker": v.marker, "seconds": v.seconds}
        return {"checker": out, "ok": r.ok and verdict != "failed", "verdict": verdict,
                "detail": (r.out or "")[-1500:] if not r.ok else ""}

    def law_file(self, law: dict, el: dict, counter: bool) -> str:
        sh = self.registry["statements"][law["law_id"]]
        d = self.gen / "laws" / law["law_id"]
        params = ar_params(self.layer_text, el["edge"].split("->")[0], el["op"]) or []
        return laws_text(law, sh, rel_import(d, self.nctx.layer_path()), rel_import(d, self.nctx.module_path()), el,
                         params, counter)

    def no_inflight(self, el: dict) -> str:
        """The reason no in-flight object of a naturality square's type is reachable: the source version's successor
        site actions (PI1) that are model debt."""
        from ..versions.inhabit import successor_actions
        a = el["edge"].split("->")[0]
        debt = set(model_debt(self.nctx, a))
        succ = successor_actions(self.m, a)
        gone = [x for x in succ if x in debt]
        if succ and len(gone) == len(succ):
            return (f"no in-flight object is reachable at {a}: its successor-site actions {', '.join(succ)} are model "
                    f"debt of the versioned model (holon.versions.model), so no batch is committed before {el['edge']}")
        return f"the successor-site actions of {a} that are model debt: {', '.join(gone) or 'none'}"

    def decide(self, lid: str) -> dict:
        from ..bend import escape_hatches
        t0 = time.monotonic()
        law = json.loads((self.root / "laws" / self.nctx.milestone / f"{lid}.json").read_text(encoding="utf-8"))
        e = self.entries.get(lid)
        if e is None:
            raise NatRefused(f"{lid} is not a NAT law of {self.nctx.milestone}")
        el = e["basis"]
        laws_dir = self.gen / "laws" / lid
        proof_dir = self.gen / "proofs" / lid
        laws_dir.mkdir(parents=True, exist_ok=True)
        lp = laws_dir / "LAWS.bend"
        pp = proof_dir / "PROOF.bend"
        attempts, witness, prim, status = [], None, None, "UNKNOWN"
        debt = element_debt(self.layer_text, el)
        bound = None
        if debt:
            attempts.append({"kind": "refute", "engine": "holon.rules.nat_run", "found": False, "reason": debt})
            bound = debt
        else:
            found, tried = self.search.find(el)
            sd = self.nctx.side.get("search") or {}
            attempts.append({"kind": "refute", "engine": "holon.rules.nat_run", "found": found is not None,
                             "budget": {"max_trace": self.search.budget},
                             "bound": (f"{tried['squares']} squares at {tried['states']} states of version "
                                       f"{el['edge'].split('->')[0]} among {tried['reached']} states reached by traces "
                                       f"of at most {self.search.budget} steps ({sd.get('doc', '')[:0]}rule N7)")})
            if found is not None:
                trace, _state, sq = found
                outs, kh, _sh = self.m.run(trace)
                for x in sq["outs"].values():
                    kh.update(x.get("kh") or {})
                kh = dict(sorted(kh.items()))
                lp.write_text(self.law_file(law, el, True), encoding="utf-8")
                proof_dir.mkdir(parents=True, exist_ok=True)
                params = ar_params(self.layer_text, el["edge"].split("->")[0], el["op"]) or []
                pp.write_text(counter_proof(law, el, self.m, (rel_import(proof_dir, self.nctx.layer_path()),
                                                              rel_import(proof_dir, self.nctx.module_path()),
                                                              rel_import(proof_dir, lp)),
                                            trace, outs, kh, sq, params), encoding="utf-8")
                hits = escape_hatches(pp.read_text(encoding="utf-8"))
                chk = self.check(pp)
                attempts.append({"kind": "counter", "evaluator": "the square's claim is false at the witness",
                                 "checker": chk["checker"], "verdict": chk["verdict"] if chk["ok"] else "failed"})
                if chk["ok"] and not hits:
                    status = "REFUTED"
                    o, s = sq["outs"], sq["steps"]

                    def done(st: dict, x: dict) -> dict:
                        return dict(st, ok=x["status"] == "ok", revert=x.get("revert") or "0x")
                    witness = {"trace": trace,
                               "square": {"edge": el["edge"], "op": el["op"],
                                          "left": [done(s["mig"], o["l1"]), done(s["xb"], o["l2"])],
                                          "right": [done(s["xa"], o["r1"]), done(s["mig"], o["r2"])]}}
                    prim = {"proof": self.rel(pp), "checker": chk["checker"], "verdict": chk["verdict"]}
                else:
                    attempts[-1]["detail"] = chk["detail"] or f"escape hatches {hits}"
            else:
                bound = attempts[0]["bound"]
                if el["subform"] == "naturality":
                    bound = f"{bound}; {self.no_inflight(el)}"
        if status != "REFUTED":
            lp.write_text(self.law_file(law, el, False), encoding="utf-8")
            if pp.exists():
                pp.unlink()
            if proof_dir.exists() and not any(proof_dir.iterdir()):
                proof_dir.rmdir()
            bound = bound or "; ".join(str(a.get("bound") or a.get("reason") or a.get("detail") or "")
                                       for a in attempts)
        rec = self.record(law, el, status, witness, attempts, lp, prim, bound)
        rec["seconds"] = round(time.monotonic() - t0, 3)
        return rec

    def model_text(self) -> str:
        """The claims module and the layer, as one text for the cone (the module's M. names are the layer's)."""
        return self.nctx.module_path().read_text(encoding="utf-8") + "\n" + self.layer_text

    def record(self, law: dict, el: dict, status: str, witness: dict | None, attempts: list, lp: Path,
               prim: dict | None, bound: str | None) -> dict:
        from .. import records as R
        from . import nat_replay as NR
        lid = law["law_id"]
        sh = self.registry["statements"][lid]
        st_text = re.sub(r"(?<![\w.])N\.", "M.", lp.read_text(encoding="utf-8"))
        cone = R.cone(st_text, self.model_text())
        rec = {"law_id": lid, "statement_hash": sh, "facts_sha256": law["facts_sha256"], "status": status,
               "scope": "unbounded", "premises": [],
               "kernel": {"name": "bend", "version": bend_version(), "verdict": (prim or {}).get("verdict", "not_run")},
               "artifacts": {"laws": self.rel(lp), "proof": (prim or {}).get("proof"),
                             "model": self.rel(self.nctx.module_path()),
                             "law_name": law_name(lid, status == "REFUTED")},
               "checker": (prim or {}).get("checker") or {"exit_code": None, "marker": "not_run"},
               "triage": "finding" if status == "REFUTED" else "none",
               "replay": (NR.replay_status(self.nctx, NR.load(self.nctx), lid, witness) if status == "REFUTED" else
                          {"status": "not_applicable", "detail": f"{status}: no witness to replay"}),
               "attempts": attempts, "rule": law["rule"], "subform": law["subform"], "witness": witness,
               "bound": None if status != "UNKNOWN" else bound}
        if status == "REFUTED":
            rec["difference"] = {"lhs": False, "rhs": True}
        try:
            b, match = R.resolve_bundle(rec["facts_sha256"], law["facts"], self.root, self.model_text(), set(cone),
                                        self.nctx.milestone)
            assumptions = R.model_assumptions(b["facts_sha256"], set(cone), self.root, law["facts"])
        except R.LedgerError:
            match, assumptions = "none", []
        vid = el["edge"].split("->")[0]
        rec.update({"record_version": R.RECORD_VERSION, "prover": "generator",
                    "model_sha256": sha256_file(self.nctx.module_path()),
                    "compiled_sha256": sha256_file(self.m.evaluator(vid).compiled()),
                    "generator_sha256": generator_sha256(self.root), "cone": cone, "ledger_match": match,
                    "model_assumptions": assumptions, "scope_v2": R.scope_v2(law, rec), "kernels": R.kernels(rec),
                    "independence_class": R.independence_class(rec), "refinement_refs": [], "coverage": None,
                    "non_vacuity": {"status": "counter_witness" if status == "REFUTED" else "unknown",
                                    "law": self.rel(lp) if status == "REFUTED" else None, "witness": None,
                                    "reachable": None, "degenerate": None, "parent_statement_hash": sh,
                                    "bound": "the accepted counter-law inhabits the premises" if status == "REFUTED"
                                    else "no proof"},
                    "witness_provenance": {"solidity": "internal_harness"} if status == "REFUTED" else None,
                    "filter_bin": "finding" if status == "REFUTED" else None,
                    **R.evidence_fields(law, {"status": status}, self.root)})
        rec["ledger_assumptions"] = sorted(rec["model_assumptions"])
        rec["model_assumptions"] = []
        rec["statement"] = law.get("notes", "")
        return rec


def bend_version() -> str:
    from ..sorts.run3 import bend_version as bv
    return bv()


# ------------------------------------------------------------------------------------------------ routing
def _arg(argv: list, name: str):
    for i, x in enumerate(argv):
        if x == name and i + 1 < len(argv):
            return argv[i + 1]
        if x.startswith(name + "="):
            return x.split("=", 1)[1]
    return None


def ids_of(argv: list, root: Path | None = None):
    """(the NAT law ids, the other ids) of a `run --laws` argv, or None when it names none."""
    from ..versions import ROOT
    m, laws = _arg(argv, "--milestone"), _arg(argv, "--laws")
    if argv[:1] != ["run"] or not m or not laws:
        return None
    ids = [x.strip() for x in laws.split(",") if x.strip()]
    mine = nat_entries(m, Path(_arg(argv, "--root") or root or ROOT))
    nids = [i for i in ids if i in mine]
    if not nids:
        return None
    return nids, [i for i in ids if i not in mine]


def strip_args(argv: list, names: tuple) -> list:
    from ..versions.run import strip_args as sa
    return sa(argv, names)


def run_main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="holon run (NAT laws)")
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--laws", required=True)
    ap.add_argument("--root")
    ap.add_argument("--out", help="the results directory (default results/<M>)")
    ap.add_argument("--gen-dir", help="the generated files' directory (default gen/<M>)")
    a, _rest = ap.parse_known_args(argv)
    from ..versions import ROOT, Refused, VersionsError
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        nctx = NatCtx(root, a.milestone)
        results = Path(a.out) if a.out else root / "results" / a.milestone
        gen = Path(a.gen_dir) if a.gen_dir else root / "gen" / a.milestone
        d = Decider(nctx, results, gen)
        try:
            for lid in [x.strip() for x in a.laws.split(",") if x.strip()]:
                rec = d.decide(lid)
                results.mkdir(parents=True, exist_ok=True)
                (results / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
                print(f"{lid}: {rec['status']} ({rec['seconds']} s)")
        finally:
            d.close()
        return 0
    except (NatRefused, Refused) as e:
        print(f"holon run: refused: {e}", file=sys.stderr)
        return 2
    except VersionsError as e:
        print(f"holon run: error: {e}", file=sys.stderr)
        return 3


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="holon nat", description="rule NAT over the versioned machine (I29)")
    ap.add_argument("what", choices=["analyze", "replay"])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--milestone", default="M3")
    ap.add_argument("--root")
    a = ap.parse_args(argv)
    from ..versions import ROOT, Refused, VersionsError
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        nctx = NatCtx(root, a.milestone)
        if a.what == "analyze":
            return analyze(nctx, a.check)
        from . import nat_replay
        return nat_replay.run(nctx, a.check)
    except (NatRefused, Refused) as e:
        print(f"holon nat: refused: {e}", file=sys.stderr)
        return 2
    except VersionsError as e:
        print(f"holon nat: error: {e}", file=sys.stderr)
        return 3
