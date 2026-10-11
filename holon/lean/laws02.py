"""Law emitter for holon-ir/0.2 (state-machine laws) -> Lean 4.

Mirrors holon.gen.mlaws: every term/prop is translated 1:1; no law-ID special
cases. Proof classes mirrored from the Bend proof generators:
  - noninterference (proj under run): ni_exec_<a> + ni_step + induction on tr
  - nat_split (`forall n` on closed traces): `cases n <;> rfl`
  - rfl: any forall law whose claim is a closed equality
  - counter/exists: model witness discharged by `decide` (closed goal only)
A law whose proof template does not verify is recorded UNSUPPORTED by the
runner; statements are still emitted faithfully.
"""
from __future__ import annotations

from .machine import LMachine, ln, lt, lty

REC_DEPTH = 8192


class Unsupported(Exception):
    pass


def law_name(law_id: str, counter: bool = False) -> str:
    return ("cl_" if counter else "") + law_id.lower()


IR_TYPE = {"State": "HSt", "Trace": "List HAct", "Act": "HAct", "Nat": "Nat",
           "Bool": "Bool", "List<Nat>": "List Nat", "Obs": "List HObs"}


class LEmit:
    def __init__(self, m: LMachine):
        self.m = m
        self.views: dict[str, list] = {}
        fn_types = {"last_ok": "Bool", "runs_ok": "Bool", "no_code": "Bool", "perm": "Bool",
                    "cost": "Nat", "elapsed": "Nat"}
        for a in m.actions:
            fn_types[f"is_{a['name']}"] = "Bool"
        for c in m.f.get("consumers", {}):
            fn_types[c] = "List<Nat>"
        self.fn_types = fn_types

    def ty(self, t: str) -> str:
        return IR_TYPE.get(t) or t

    def view(self, fields: list) -> str:
        for f in fields:
            if f not in self.m.stypes or f == "log":
                raise Unsupported(f"cannot erase {f}")
        name = "V_" + "_".join(sorted(fields))
        self.views[name] = sorted(fields)
        return name

    def term(self, t: dict, env: dict, types: dict) -> tuple[str, str]:
        if "var" in t:
            return env[t["var"]], types[t["var"]]
        if "nat" in t:
            return str(int(t["nat"])), "Nat"
        if "bool" in t:
            return ("true" if t["bool"] else "false"), "Bool"
        if "nats" in t:
            xs = ", ".join(str(int(x)) for x in t["nats"])
            return f"([{xs}] : List Nat)", "List<Nat>"
        if "s0" in t:
            return "s0", "State"
        if "run" in t:
            tr, tt = self.term(t["run"], env, types)
            s, ts = self.term(t["from"], env, types)
            self.expect(tt, "Trace", t)
            self.expect(ts, "State", t)
            return f"(run {tr} {s})", "State"
        if "step" in t:
            a, ta = self.term(t["step"], env, types)
            s, ts = self.term(t["from"], env, types)
            self.expect(ta, "Act", t)
            self.expect(ts, "State", t)
            return f"(step {a} {s})", "State"
        if "obs" in t:
            tr, tt = self.term(t["obs"], env, types)
            s, ts = self.term(t["from"], env, types)
            self.expect(tt, "Trace", t)
            self.expect(ts, "State", t)
            return f"(obs {tr} {s})", "Obs"
        if "trace" in t:
            items = []
            for a in t["trace"]:
                x, ta = self.term(a, env, types)
                self.expect(ta, "Act", t)
                items.append(x)
            return f"([{', '.join(items)}] : List HAct)", "Trace"
        if "cat" in t:
            (x, tx), (y, ty_) = (self.term(z, env, types) for z in t["cat"])
            self.expect(tx, "Trace", t)
            self.expect(ty_, "Trace", t)
            return f"({x} ++ {y})", "Trace"
        if "act" in t:
            a = next((x for x in self.m.actions if x["name"] == t["act"]), None)
            if a is None:
                raise Unsupported(f"unknown action {t['act']}")
            args = []
            for n, ity in a["inputs"]:
                if n not in t["args"]:
                    raise Unsupported(f"{t['act']}: missing input {n}")
                x, tx = self.term(t["args"][n], env, types)
                self.expect(tx, ity, t)
                args.append(x)
            if set(t["args"]) - {n for n, _ in a["inputs"]}:
                raise Unsupported(f"{t['act']}: unknown inputs")
            sp = " ".join(f"({x})" for x in args)
            return f"(HAct.A_{a['name']} {sp})" if args else f"HAct.A_{a['name']}", "Act"
        if "proj" in t:
            s, ts = self.term(t["of"], env, types)
            self.expect(ts, "State", t)
            v = self.view(t["proj"])
            return f"(proj_{v} {s})", v
        if "obsv" in t:
            o = self.m.f.get("observers", {}).get(t["obsv"])
            if o is None:
                raise Unsupported(f"unknown observer {t['obsv']}")
            s, ts = self.term(t["of"], env, types)
            self.expect(ts, "State", t)
            return f"({t['obsv']} {s})", o["type"]
        if "mig" in t:
            mg = self.m.f.get("migrations", {}).get(t["mig"])
            if mg is None:
                raise Unsupported(f"unknown migration {t['mig']}")
            s, ts = self.term(t["of"], env, types)
            self.expect(ts, "State", t)
            args = []
            for (n, ity), x in zip(mg.get("inputs", []), t.get("args", [])):
                xt, tx = self.term(x, env, types)
                self.expect(tx, ity, t)
                args.append(xt)
            if len(args) != len(mg.get("inputs", [])):
                raise Unsupported(f"{t['mig']}: arity")
            return f"(mig_{t['mig']} {s}{' ' + ' '.join(args) if args else ''})", "State"
        if "fn" in t:
            name = t["fn"]
            if name not in self.fn_types:
                raise Unsupported(f"unknown model function {name}")
            args = [self.term(x, env, types)[0] for x in t["args"]]
            return f"({name} {' '.join(args)})", self.fn_types[name]
        if "plus" in t:
            (x, tx), (y, ty_) = (self.term(z, env, types) for z in t["plus"])
            self.expect(tx, "Nat", t)
            self.expect(ty_, "Nat", t)
            return f"(natAdd {x} {y})", "Nat"
        raise Unsupported(f"term {t}")

    @staticmethod
    def expect(got: str, want: str, t) -> None:
        if got != want:
            raise Unsupported(f"ill-typed term (got {got}, want {want}): {t}")

    def prop(self, p: dict, env: dict, types: dict) -> tuple[str, str, str]:
        if set(p) != {"eq"}:
            raise Unsupported(f"proposition {p}")
        (a, ta), (b, tb) = (self.term(x, env, types) for x in p["eq"])
        if ta != tb:
            raise Unsupported(f"equation sides differ in type: {ta} / {tb}")
        return a, b, ta

    def claims(self, st: dict, env: dict, types: dict) -> list:
        c = st["claim"]
        ps = c["all"] if "all" in c else [c]
        return [self.prop(p, env, types) for p in ps]

    def view_defs(self) -> list[str]:
        out = []
        for v, erased in sorted(self.views.items()):
            kept = [(n, t) for n, t in self.m.state if n not in erased]
            out += [f"structure {v} where"] + [f"  {ln(n)} : {lt(t)}" for n, t in kept] \
                + ["  deriving DecidableEq, BEq", "",
                   f"def proj_{v} (s : HSt) : {v} := {v}.mk {' '.join('s.' + ln(n) for n, _ in kept)}", ""]
        return out

    def statement(self, st: dict, counter: bool):
        """Returns (binders, assume, claims) as Lean texts; raises Unsupported."""
        binders = [(b["q"], ln(b["name"]), b["type"]) for b in st["binders"]]
        types = {n: t for _, n, t in binders}
        env = {n: n for _, n, _ in binders}
        has_exists = any(qq == "exists" for qq, _, _ in binders)
        if has_exists and (counter or st.get("assume")):
            raise Unsupported("exists laws with premises or counter-laws of exists laws are not in holon-ir/0.2")
        assume = [self.prop(p, env, types) for p in st.get("assume", [])]
        claims = self.claims(st, env, types)
        if counter and len(claims) != 1:
            raise Unsupported("counter-law of a conjunction")
        return binders, assume, claims

    # ------------------------------------------------------------ statements
    def emit_statement(self, law: dict, counter: bool) -> str:
        st = law["statement"]
        binders, assume, claims = self.statement(st, counter)
        if counter:
            ex = " ".join(f"({n} : {self.ty(t)})" for _, n, t in binders)
            parts = [f"({a} = {b})" for a, b, _ in assume]
            a, b, _ = claims[0]
            parts.append(f"(({a}) ≠ ({b}))")
            conj = " ∧ ".join(parts) if parts else "True"
            return f"∃ {ex}, {conj}" if ex else conj
        if any(qq == "exists" for qq, _, _ in binders):
            # an exists-binder law: binders keep their own quantifier (mlaws exs/for)
            qb = ", ".join(f"{'∃' if qq == 'exists' else '∀'} {n} : {self.ty(t)}" for qq, n, t in binders)
            inner = " ∧ ".join(f"({a} = {b})" for a, b, _ in claims)
            return f"{qb}, {inner}"
        qb = " ".join(f"({n} : {self.ty(t)})" for _, n, t in binders)
        prems = [f"({a} = {b})" for a, b, _ in assume]
        inner = " ∧ ".join(f"({a} = {b})" for a, b, _ in claims)
        goal = " → ".join(prems + [f"({inner})"])
        return f"∀ {qb}, {goal}" if qb else goal

    # ------------------------------------------------------------ witnesses
    def value_literal(self, ty: str, v) -> str:
        m = self.m
        if ty == "Nat":
            return str(int(v))
        if ty == "Bool":
            return "true" if v else "false"
        if ty == "Act":
            return m.act_literal(v)
        if ty == "Trace":
            items = [self.value_literal("Act", a) for a in v]
            return f"([{', '.join(items)}] : List HAct)"
        if ty == "State":
            if set(v) == {"run"}:
                return f"(run {self.value_literal('Trace', v['run'])} s0)"
            if set(v) == {"state"}:
                return m.state_literal(v["state"])
            raise Unsupported(f"state literal {v}")
        raise Unsupported(f"witness literal type {ty}")

    # ------------------------------------------------------------ proof templates
    def proof(self, law: dict, counter: bool, witness: dict | None) -> tuple[str, list[str]]:
        """Returns (proof_body, extra_defs). Body may be 'UNSUPPORTED:<reason>'."""
        st = law["statement"]
        binders, assume, claims = self.statement(st, counter)
        if counter or any(qq == "exists" for qq, _, _ in binders):
            if witness is None:
                return "UNSUPPORTED:no witness recorded", []
            try:
                wits = []
                for _, n, t in binders:
                    raw = witness.get(n) if n in witness else witness.get(self._unln(n))
                    if raw is None:
                        raise Unsupported(f"witness missing binder {n}")
                    wits.append(self.value_literal(t, raw))
            except Unsupported as e:
                return f"UNSUPPORTED:witness: {e}", []
            exact = ", ".join(wits) + (", " if wits else "")
            return f"exact ⟨{exact}by decide⟩", []

        # forall PROVED: detect statement class
        nat_binders = [n for _, n, t in binders if t == "Nat"]
        sig = [t for _, _, t in binders]
        if sig == ["Trace", "State", "State"] and len(assume) == 1 and len(claims) == 1 \
                and all(x.startswith("(proj_V_") for x, _, _ in assume + claims):
            return self._ni_proof(law, binders)
        intro = " ".join(n for _, n, _ in binders) + "".join(f" h{i}" for i, _ in enumerate(assume))
        if nat_binders and not any(t in ("State", "Trace", "Act") for _, _, t in binders):
            cs = "\n".join(f"cases {n} <;> rfl" for n in nat_binders)
            return f"intro {intro}\n{cs}", []
        if nat_binders:
            cs = "\n".join(f"cases {n} <;> rfl" for n in nat_binders)
            return f"intro {intro}\n{cs}", []
        return f"intro {intro}\nrfl", []

    @staticmethod
    def _unln(n: str) -> str:
        return n[:-1] if n.endswith("_") else n

    def _ni_proof(self, law: dict, binders):
        """ni_exec_<a> lemmas + ni_step + induction on the trace binder."""
        m = self.m
        (tr, s1, s2) = (b[1] for b in binders)
        vname = next(iter(self.views), None)
        if vname is None:
            return "UNSUPPORTED:ni: no view", []
        erased = self.views[vname]
        if len(erased) != 1:
            return f"UNSUPPORTED:ni: view erases {erased}", []
        ef = erased[0]
        kept = [n for n, _ in m.state if n != ef]
        for a in m.actions:
            if ef in (m.action_reads(a) or []):
                return f"UNSUPPORTED:ni: decide_{a['name']} reads erased field {ef}", []
        defs = []
        for a in m.actions:
            ins = a["inputs"]
            fparams = " ".join(f"({ln(n)} : {lt(t)})" for n, t in m.state if n != ef)
            ip = " ".join(f"({ln(n)} : {lt(t)})" for n, t in ins)
            lhs_args = " ".join(f"{ln(ef)}1" if n == ef else ln(n) for n, _ in m.state)
            rhs_args = " ".join(f"{ln(ef)}2" if n == ef else ln(n) for n, _ in m.state)
            ia = " ".join(ln(n) for n, _ in ins)
            et = lt(m.stypes[ef])
            defs += [
                f"theorem ni_exec_{a['name']} (d : Dec_{a['name']}) {fparams} ({ln(ef)}1 {ln(ef)}2 : {et}) {ip} :",
                f"    proj_{vname} (exec_{a['name']} d {lhs_args}{' ' + ia if ia else ''})"
                f" = proj_{vname} (exec_{a['name']} d {rhs_args}{' ' + ia if ia else ''}) := by",
                "  cases d <;> rfl", ""]
        kept = [n for n, _ in m.state if n != ef]
        kparams = " ".join(f"({ln(n)} : {lt(t)})" for n, t in m.state if n != ef)
        mk1 = " ".join(ln(ef) + "1" if n == ef else ln(n) for n, _ in m.state)
        mk2 = " ".join(ln(ef) + "2" if n == ef else ln(n) for n, _ in m.state)
        step_cases = []
        for a in m.actions:
            ins = [ln(n) for n, _ in a["inputs"]]
            dr = " ".join(ln(r) for r in m.action_reads(a))
            ip = " ".join(ins)
            kp = " ".join(ln(n) for n in kept)
            step_cases.append(
                f"  | A_{a['name']}{' ' + ' '.join(ins) if ins else ''} =>\n"
                f"      exact ni_exec_{a['name']} (decide_{a['name']} {dr}{' ' + ip if ip else ''})"
                f" {kp} {ln(ef)}1 {ln(ef)}2{' ' + ip if ip else ''}")
        defs += [
            f"theorem ni_step (a : HAct) {kparams} ({ln(ef)}1 {ln(ef)}2 : {lt(m.stypes[ef])}) :",
            f"    proj_{vname} (step a (HSt.mk {mk1})) = proj_{vname} (step a (HSt.mk {mk2})) := by",
            "  cases a with", *step_cases, ""]
        s1p = " ".join(ln(n) for n, _ in m.state)
        s2p = " ".join(ln(n) + "'" for n, _ in m.state)
        kept1 = " ".join(ln(n) for n in kept)
        body = (f"intro {tr} {s1} {s2} h\n"
                f"induction {tr} generalizing {s1} {s2} with\n"
                f"| nil => exact h\n"
                f"| cons a t ih =>\n"
                f"    cases {s1} with | mk {s1p} =>\n"
                f"    cases {s2} with | mk {s2p} =>\n"
                f"    simp only [proj_{vname}] at h\n"
                f"    cases h\n"
                f"    exact ih _ _ (ni_step a {kept1} {ln(ef)} {ln(ef)}')")
        return body, defs

    # ------------------------------------------------------------ top level
    def emit(self, law: dict, counter: bool, witness: dict | None):
        """Returns (statement_block_text, extra_def_texts, unsupported_reason_or_None)."""
        self.views = {}
        # first pass to register views
        binders, assume, claims = self.statement(law["statement"], counter)
        name = law_name(law["law_id"], counter)
        stmt = self.emit_statement(law, counter)
        body, defs = self.proof(law, counter, witness)
        unsupported = body.split(":", 1)[1] if body.startswith("UNSUPPORTED:") else None
        if unsupported is not None:
            body = "-- coverage debt: no faithful proof template for this statement class\nskip"
        head = [f"-- GENERATED by holon.lean.laws02 from the frozen law IR; do not edit.",
                f"-- law_id: {law['law_id']}   counter: {str(counter).lower()}",
                f"set_option maxRecDepth {REC_DEPTH}", "set_option maxHeartbeats 16000000", ""]
        block = head + [f"theorem {name} : {stmt} := by", "  " + body.replace("\n", "\n  ")]
        return "\n".join(block) + "\n", defs, unsupported
