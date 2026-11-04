"""Rule D2 (I94): the slash laws' witness search over the compiled claims module, and the witnesses' Bend values.

Candidates: I83's inhabitant trace of the edge (results/<M>/versions/inflight.json) up to the edge's old version a,
with the first call's registry argument (the I94 sidecar's search.initializer_registry_argument) set to the a-callee's
address (the registry's initial state record), then a's commit (the inhabitant's own call at a) by each corpus role in
order. The trace runs on the versioned machine (holon.versions.machine) with every call into a callee answered by the
callee model's run at its state (its compiled module, holon.sorts.evaluate3) and every other call by I83's stand-in.
Each candidate whose commit succeeds is paired with every k of the in-flight window, increasing; u is the edge's
initializer with the cutover corpus step's arguments (the b-callee's address, the window's upper word); each callee's
environment answers ok every call its site's run makes. The claims are evaluated on the compiled claims module: a
probe module (the witness's values as Bend literals and one function per claim) compiled with `bend -o .mjs` and run
by node. The first candidate at which a claim is false is its witness. Nothing here names a target.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import Ctx, Refused, render, sha256_bytes  # noqa: F401
from .linked import rel_import, types_of


def h32(n: int) -> str:
    return "%064x" % n


def word_at(sl: list, slot: int) -> int:
    for k, v in sl:
        if k == slot:
            return v
    return 0


def keccak(b: bytes) -> int:
    from ..keccak import keccak256
    return int.from_bytes(keccak256(b), "big")


# ------------------------------------------------------------------------------------------------ callees
class Callee:
    """A model3 member model of the link at a state: its compiled module answers calls addressed to it."""

    def __init__(self, ctx: Ctx, spec: dict, storage: dict, address: int, immutables: dict):
        from ..machine import ExtractedModel
        from ..sorts.evaluate3 import Evaluator
        from . import model as MD
        self.spec, self.alias, self.member = spec, spec["alias"], spec["member"]
        rel = MD.document_rel(ctx, self.member)
        data = ctx.path(rel).read_bytes()
        self.doc = ExtractedModel(json.loads(data), MD.info_of(ctx, self.member), None, sha256_bytes(data))
        self.path = ctx.path(spec["module"])
        self.text = self.path.read_text(encoding="utf-8")
        self.ev = Evaluator.build(self.path, self.doc)
        self.sl = sorted((int(k, 16), int(v, 16)) for k, v in storage.items())
        self.address, self.immutables = address, immutables
        self.by_sel = {(a.get("selector") or "").lower(): a["name"] for a in self.doc.doc["actions"] if a.get("selector")}

    def close(self):
        self.ev.close()

    def env(self, caller: int, data: bytes, calls: list, block_number: int) -> dict:
        return {"caller": caller, "this": self.address, "msg.value": 0, "msg.data.length": len(data),
                "block.number": block_number, "immutable": dict(self.immutables), "code": {}, "calls": list(calls)}

    def run(self, data_hex: str, caller: int, calls: list, block_number: int) -> dict:
        """{"ok", "ret", "calls", "writes", "kh", "env", "action", "args"} of a call of this callee."""
        from ..machine_bend import bname
        from ..sorts.evaluate3 import word
        from ..versions.bendlit import Lit, py_args
        d = bytes.fromhex(data_hex[2:])
        act = self.by_sel.get("0x" + d[:4].hex())
        if act is None:
            raise Refused(f"{self.member} has no action at {d[:4].hex()}")
        args = py_args(self.doc.params(act) or [], Lit(self.alias).leaves(self.doc.params(act) or [], data_hex))
        hst = {"$r": "HSt", "f": {"sl": [{"$r": "KW", "f": {"k": word(k), "v": word(v)}} for k, v in self.sl]}}
        kh: dict = {}
        calls = list(calls)
        for _ in range(64):
            env = self.env(caller, d, calls, block_number)
            for _r in range(64):
                ans = self.ev.call(f"run_{bname(act)}", [hst, self.ev.args_in(act, args), self.ev.env_in(env),
                                                         self.ev.table(kh)])
                if "error" in ans:
                    raise Refused(f"{self.member}.{act}: {ans['error'][:300]}")
                new = [k for k in ans["keys"].get("kh") or [] if k not in kh]
                for k in new:
                    kh[k] = keccak(bytes.fromhex(k[2:]))
                if not new:
                    break
            known = {(c["to"], c["data"]) for c in calls}
            fresh = [(to, dd) for to, dd in ans.get("calls") or [] if (to, dd) not in known]
            if not fresh:
                break
            calls += [{"to": to, "data": dd, "ok": True, "ret": "0x"} for to, dd in fresh]
        f = ans["out"]["f"]
        rv = f["rv"].get("$b", "0x") if isinstance(f["rv"], dict) else "0x"
        post = [(int(kv["f"]["k"], 16), int(kv["f"]["v"], 16)) for kv in f["po"]["f"]["sl"]]
        writes = sorted({int(x, 16) for x in f["tw"]}) if int(f["c"]) == 0 else []
        return {"ok": int(f["c"]) == 0, "ret": rv, "calls": calls, "writes": writes, "post": post, "kh": kh,
                "env": self.env(caller, d, calls, block_number), "action": act, "args": args}


# ------------------------------------------------------------------------------------------------ the linked run
def linked_machine(ctx: Ctx, callees: list):
    """holon.versions.machine.Machine whose calls into a callee are answered by the callee's model."""
    from ..versions.machine import Machine, STANDIN_ANSWER, hx
    by_addr = {c.address: c for c in callees}

    class Linked(Machine):
        answered: list = []

        def code_table(self) -> dict:
            # the callees hold code (I83's labelled stand-in's), as a deployed member does
            code = Machine.code_table(self)
            for c in callees:
                code.setdefault(c.address, self.standin())
            return dict(sorted(code.items()))

        def run_action(self, vid, name, sl, caller, calldata):
            import hashlib as _h
            from ..machine_bend import bname
            from ..sorts.evaluate3 import word
            from ..keccak import keccak256
            ev = self.evaluator(vid)
            args = self.args(vid, name, calldata)
            hst = {"$r": "HSt", "f": {"sl": [{"$r": "KW", "f": {"k": word(k), "v": word(v)}} for k, v in sl]}}
            calls: list = []
            kh, sh = {}, {}
            hs = ev.hashes()
            for _ in range(64):
                env = self.env(vid, name, caller, calldata, calls)
                for _r in range(64):
                    a = [hst, ev.args_in(name, args), ev.env_in(env)]
                    if "keccak256" in hs:
                        a.append(ev.table(kh))
                    if "sha256" in hs:
                        a.append(ev.table(sh))
                    ans = ev.call(f"run_{bname(name)}", a)
                    new = False
                    for k in ans["keys"].get("kh") or []:
                        if k not in kh:
                            kh[k] = int.from_bytes(keccak256(bytes.fromhex(k[2:])), "big")
                            new = True
                    for k in ans["keys"].get("sh") or []:
                        if k not in sh:
                            sh[k] = int.from_bytes(_h.sha256(bytes.fromhex(k[2:])).digest(), "big")
                            new = True
                    if not new:
                        break
                known = {(c["to"], c["data"]) for c in calls}
                fresh = [(to, d) for to, d in ans.get("calls") or [] if (to, d) not in known]
                if not fresh:
                    break
                for to, d in fresh:
                    c = by_addr.get(int(to, 16)) if to else None
                    if c is not None:
                        r = c.run(d, int(self.dep["target"], 16) if isinstance(self.dep["target"], str)
                                  else int(self.dep["target"]), [], int(self.dep.get("number") or 0))
                        if r["writes"]:
                            raise Refused(f"{c.member}: a call that writes its state ({r['action']})")
                        calls.append({"to": to, "data": d, "ok": r["ok"], "ret": r["ret"]})
                        Linked.answered.append({"callee": c.alias, "to": to, "data": d, "ok": r["ok"],
                                                "ret": r["ret"], "action": r["action"], "args": r["args"],
                                                "env": r["env"], "kh": r["kh"]})
                    else:
                        calls.append({"to": to, "data": d, "ok": True, "ret": hx(STANDIN_ANSWER)})
            f = ans["out"]["f"]
            c = int(f["c"])
            rv = f["rv"].get("$b", "0x") if isinstance(f["rv"], dict) else "0x"
            base = {"kh": kh, "sh": sh, "calls": calls, "env": env, "code": c}
            if c != 0:
                return {"status": "revert", "revert": rv, "sl": list(sl), "writes": {}, **base}
            post = [(int(kv["f"]["k"], 16), int(kv["f"]["v"], 16)) for kv in f["po"]["f"]["sl"]]
            from ..versions.machine import storage_of
            view = storage_of(post)
            touched = sorted({int(x, 16) for x in f["tw"]})
            return {"status": "ok", "revert": "0x", "sl": post, "writes": {x: view.get(x, 0) for x in touched},
                    **base}
    return Linked(ctx.versions())


def set_arg(cd: str, i: int, value: int) -> str:
    b = bytearray(bytes.fromhex(cd[2:]))
    b[4 + 32 * i:4 + 32 * (i + 1)] = value.to_bytes(32, "big")
    return "0x" + b.hex()


# ------------------------------------------------------------------------------------------------ the search
class Search:
    def __init__(self, ctx: Ctx, log=print):
        from .claims import Claims
        from .s0 import sidecar
        self.ctx, self.log = ctx, log
        self.side = sidecar(ctx)
        self.cl = Claims(ctx)
        self.link = self.side["link"]
        self.s0 = ctx.load(self.side["outputs"]["registry_s0"])
        self.dep = ctx.load(ctx.out("deployment"))
        self.edge = self.side["search"]["edge"]
        self.a, self.b = self.edge.split("->")
        inf = ctx.load(self.side["inputs"]["inhabitants"])
        self.inhabitant = next(e for e in inf["edges"] if e["edge"] == self.edge)

    def callee_states(self) -> dict:
        out = {}
        for c in self.link["callees"]:
            if c["member"] == self.s0["member"]:
                st, addr = self.s0["storage"], int(self.s0["address"], 16)
            else:
                m = self.dep["members"][c["member"]]
                st, addr = m["storage"], int(m["address"], 16)
            imm = {k: int(v, 16) for k, v in (self.dep["members"][c["member"]].get("immutables") or {}).items()}
            out[c["alias"]] = (st, addr, imm)
        return out

    def window(self, sl: list) -> tuple:
        lo, hi = self.cl.window
        d = self.cl.docs[self.a]
        from .claims import family
        return word_at(sl, int(family(d, lo)["slot"])), word_at(sl, int(family(d, hi)["slot"]))

    def close(self) -> None:
        for c in getattr(self, "_callees", []):
            c.close()
        if getattr(self, "m", None) is not None:
            self.m.close()

    def run(self, keep: bool = False) -> dict:
        states = self.callee_states()
        ca = next(c for c in self.link["callees"] if c["at"] == self.a)
        cb = next(c for c in self.link["callees"] if c["at"] == self.b)
        callees = [Callee(self.ctx, c, states[c["alias"]][0], states[c["alias"]][1], states[c["alias"]][2])
                   for c in self.link["callees"]]
        m = linked_machine(self.ctx, callees)
        self.m, self._callees = m, callees
        self._callee_docs = [{"alias": c.alias, "doc": c.doc} for c in callees]
        try:
            tr = self.inhabitant["trace"]
            i_commit = next(i for i, s in enumerate(tr) if s["kind"] == "call" and s["version"] == self.a)
            prefix = [dict(s) for s in tr[:i_commit]]
            first = next(i for i, s in enumerate(prefix) if s["kind"] == "call")
            prefix[first]["calldata"] = set_arg(prefix[first]["calldata"],
                                                int(self.side["search"]["initializer_registry_argument"]),
                                                states[ca["alias"]][1])
            commit = dict(tr[i_commit])
            roles = self.s0["stakers"]
            tried, found = [], {}
            n = 0
            for role in sorted(roles):
                st = dict(commit, caller=roles[role])
                trace = prefix + [st]
                type(m).answered = []
                outs, kh, _sh = m.run(trace)
                answered = list(type(m).answered)
                for x in answered:
                    kh.update(x["kh"])
                if not all(o["status"] == "ok" for o in outs):
                    tried.append({"committer": role, "result": "the commit does not succeed"})
                    continue
                s = outs[-1]["state"]
                lo, hi = self.window(s["sl"])
                for k in range(lo + 1, hi + 1):
                    n += 1
                    if n > int(self.side["search"]["max_candidates"]):
                        break
                    w = self.witness(m, callees, ca, cb, trace, outs, kh, s, k, hi, role)
                    w["answered"] = answered
                    tried.append({"committer": role, "k": k, "claims": w["claims"]})
                    for rule, v in w["claims"].items():
                        if v is False and rule not in found:
                            found[rule] = w
                if found:
                    break
            return {"tried": tried, "found": found}
        finally:
            if not keep:
                self.close()

    def migration_step(self, m, k_hi: int, cb: dict, states: dict) -> dict:
        tr = self.inhabitant["trace"]
        mig = dict(next(s for s in tr if s["kind"] == "migrate" and s["label"] == self.edge))
        step = [x for x in self.ctx.side["corpus"]["traces"].values() for x in x if x.startswith("cutover by")]
        mt = re.search(r"\((\w+), (\w+)\)\)", step[0]) if step else None
        if not mt:
            raise Refused("the corpus's cutover step names no initializer arguments")
        cd = set_arg(set_arg(mig["calldata"], 0, states[cb["alias"]][1]), 1, k_hi)
        mig["calldata"] = cd
        return mig

    def witness(self, m, callees, ca, cb, trace, outs, kh, s, k, hi, role) -> dict:
        states = self.callee_states()
        A = next(c for c in callees if c.alias == ca["alias"])
        B = next(c for c in callees if c.alias == cb["alias"])
        rollup = word_at(A.sl, self.caller_slot(ca))
        mig = self.migration_step(m, hi, cb, states)
        mo = m.step(s, mig)
        kh = dict(kh, **mo["kh"])
        s1 = mo["state"]
        site_a = self.cl.pairs[0]["a"][0]
        site_b = self.cl.pairs[0]["b"][0]
        arg_a = self.read_member(s["sl"], self.a, site_a["reads"][0], k, kh)
        arg_b = self.read_member(s1["sl"], self.b, site_b["reads"][0], k, kh)
        from .lawrun import _action_of
        sel_a = next(a.get("selector") for a in A.doc.doc["actions"] if a["name"] == _action_of(site_a["fn"]))
        sel_b = next(a.get("selector") for a in B.doc.doc["actions"] if a["name"] == _action_of(site_b["fn"]))
        bn = int(self.s0["block_number"])
        ra = A.run(sel_a + h32(arg_a), rollup, [], bn)
        rb = B.run(sel_b + h32(arg_b), rollup, [], bn)
        kh.update({kk: vv for kk, vv in ra["kh"].items()})
        kh.update({kk: vv for kk, vv in rb["kh"].items()})
        wa = int(ra["ret"][2:66] or "0", 16) if ra["ret"] != "0x" else 0
        wb = int(rb["ret"][2:66] or "0", 16) if rb["ret"] != "0x" else 0
        w = {"trace": trace, "outs": outs, "kh": dict(sorted(kh.items())), "s": s, "s1": s1, "k": k, "mig": mig,
             "env_u": mo["env"], "committer": role, "ea": ra["env"], "eb": rb["env"], "rollup": rollup,
             "left": {"ok": rb["ok"], "ret": wb}, "right": {"ok": ra["ok"], "ret": wa}, "args": [arg_a, arg_b]}
        w["claims"] = self.evaluate(m, w)
        return w

    def caller_slot(self, c: dict) -> int:
        from .claims import family
        caller = self.link["caller"]["member"]
        fams = sorted({kk.split(".", 1)[1] for side in ("a", "b") for kk, v in
                       (self.ctx.side["link"][side].get("wiring") or {}).items()
                       if kk.startswith(c["member"] + ".") and v == caller})
        return int(family(self.cl.callee_doc(c), fams[0])["slot"])

    def read_member(self, sl: list, v: str, name: str, k: int, kh: dict) -> int:
        from .claims import family
        fam, mem = name.split(".", 1)
        f = family(self.cl.docs[v], fam)
        fld = next(x for x in f["fields"] if x["name"] == mem)
        key = k.to_bytes(32, "big") + int(f["slot"]).to_bytes(32, "big")
        kh["0x" + key.hex()] = keccak(key)
        slot = (keccak(key) + int(fld["slot"])) % (1 << 256)
        val = word_at(sl, slot)
        width = int(fld.get("width", 256))
        return val & ((1 << width) - 1)

    # ---------------------------------------------------------- literals and the compiled probe
    def literals(self, m, w: dict) -> list:
        from ..versions.bendlit import Lit
        from ..versions.proofs import reach_def, trace_defs
        from ..rules.nat_run import uc_literal
        P = self.link["caller"]["alias"]
        lit = Lit(P)
        defs = trace_defs(lit, m, w["trace"], w["outs"], w["kh"])
        n = len(w["trace"])
        defs.append(reach_def(P, n, "reach_w"))
        a, b = self.a, self.b
        defs.append(f"def k_w() -> {P}.W:\n  {lit.word(w['k'])}\n")
        defs.append(f"def u_w() -> {P}.UC_{a}_{b}:\n  {uc_literal(lit, m, w['mig'], w['env_u'])}\n")
        for c in self.link["callees"]:
            x = c["alias"]
            st = self.callee_states()[x][0]
            sl = sorted((int(kk, 16), int(vv, 16)) for kk, vv in st.items())
            defs.append(f"def s_{x}() -> {x}.HSt:\n  {Lit(x).storage(sl)}\n")
            env = w["ea"] if c["at"] == a else w["eb"]
            defs.append(f"def e_{x}() -> {x}.HEnv:\n  {self.henv(x, env)}\n")
        return defs

    def henv(self, x: str, env: dict) -> str:
        from ..versions.bendlit import Lit
        from ..versions.machine import cd_bytes, num
        lit = Lit(x)
        c = next(c for c in self.link["callees"] if c["alias"] == x)
        text = (self.ctx.root / c["module"]).read_text(encoding="utf-8")
        keys = dict(re.findall(r"(?m)^# HEnv\.(\w+): (.*)$", text))
        fields = types_of(text)["HEnv"][0][1]
        vals = []
        for f, ty in fields:
            key = keys.get(f, f)
            if key == "calls":
                cs = [f"{x}.HCall{{{lit.word(num(cc.get('to') or 0))}, {lit.blist(cd_bytes(cc.get('data') or '0x'))}, "
                      f"{'True' if cc.get('ok') else 'False'}{{}}, {lit.blist(cd_bytes(cc.get('ret') or '0x'))}}}"
                      for cc in env.get("calls") or []]
                vals.append("[" + ", ".join(cs) + "]" if cs else "Nil{}")
            elif key == "code":
                cs = [f"{x}.KB{{{lit.word(kk)}, {lit.blist(bb)}}}" for kk, bb in sorted((env.get("code") or {}).items())]
                vals.append("[" + ", ".join(cs) + "]" if cs else "Nil{}")
            elif key.startswith("immutable."):
                vals.append(lit.word(num((env.get("immutable") or {}).get(key[len("immutable."):], 0))))
            elif ty == "W":
                vals.append(lit.word(num(env.get(key) or 0)))
            else:
                raise Refused(f"no literal of {x}'s environment field {f} ({ty})")
        return f"{x}.HEnv{{{', '.join(vals)}}}"

    def imports(self, d: Path) -> list:
        side = self.side
        out = ["import Base", f"import {rel_import(d, self.ctx.root / self.link['caller']['module'])} as "
                              f"{self.link['caller']['alias']}"]
        for c in self.link["callees"]:
            out.append(f"import {rel_import(d, self.ctx.root / c['module'])} as {c['alias']}")
        out.append(f"import {rel_import(d, self.ctx.root / side['outputs']['linked'])} as L")
        out.append(f"import {rel_import(d, self.ctx.root / side['outputs']['claims'])} as C")
        return out

    def evaluate(self, m, w: dict) -> dict:
        """{rule: the claim's value} on the compiled claims module (bend -o .mjs, run by node)."""
        from .. import bend
        from ..rules import slash as S
        d = self.ctx.root / Path(self.side["outputs"]["claims"]).parent
        n = len(w["trace"])
        p = self.cl.pairs[0]
        a, b = p["edge"].split("->")
        xs = [f"s_{c['alias']}()" for c in self.link["callees"]]
        es = [f"e_{c['alias']}()" for c in self.link["callees"]]
        args = ", ".join([f"s_{n}()"] + xs + ["k_w()", "u_w()"] + es + ["t_kh()"])
        with tempfile.TemporaryDirectory(dir=d, prefix="probe-") as td:
            tdp = Path(td)
            defs = self.literals(m, w)
            for rule in S.RULES:
                defs.append(f"def probe_{rule.lower()}() -> Bool:\n  C.slash_{rule.lower()}_{a}_{b}_{p['op']}({args})\n")
            src = tdp / "probe.bend"
            src.write_text("\n".join(self.imports(tdp)) + "\n\n" + "\n".join(defs), encoding="utf-8")
            r = bend.run([src.name, "-o", "probe.mjs"], cwd=tdp, timeout=3600)
            if r.code != 0 or not (tdp / "probe.mjs").is_file():
                raise Refused(f"the probe does not compile: {(r.out or '')[-800:]}")
            js = tdp / "run.mjs"
            js.write_text("import m from './probe.mjs';\n" + "".join(
                f"console.log('{rule}', JSON.stringify(m['probe_{rule.lower()}']()));\n" for rule in S.RULES),
                encoding="utf-8")
            node = bend.config().get("node", "node")
            out = subprocess.run([node, "--stack-size=65500", js.name], cwd=tdp, capture_output=True, text=True,
                                 timeout=3600)
            if out.returncode != 0:
                raise Refused(f"the probe does not run: {out.stderr[-800:]}")
            w["compiled_sha256"] = sha256_bytes((tdp / "probe.mjs").read_bytes())
            w["probe"] = src.read_text(encoding="utf-8")
            vals = {}
            for line in out.stdout.splitlines():
                rule, _, v = line.partition(" ")
                vals[rule] = "True" in v if ("True" in v or "False" in v) else (v.strip() == "true")
            self.log(f"candidate {w['committer']} k={w['k']}: {vals}")
            return vals


def build(ctx: Ctx, log=print) -> dict:
    res = Search(ctx, log).run()
    out = {"search_version": "holon-cutover-search/0.1", "tried": res["tried"],
           "found": {r: {"committer": w["committer"], "k": w["k"], "left": w["left"], "right": w["right"],
                         "compiled_sha256": w["compiled_sha256"]} for r, w in res["found"].items()}}
    from .s0 import sidecar
    return {sidecar(ctx)["outputs"]["search"]: render(out)}
