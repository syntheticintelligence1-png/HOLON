"""Machine emitter: holon-facts/0.2 state machines -> Lean 4 (Lean core only).

Term-for-term mirror of holon.gen.machine (whitepaper §8.3, §8.9). The mapping:
  H<ty>            -> structure H<ty> (named fields)
  HObs O_Ok/O_Rev  -> inductive HObs
  HAct A_<a>       -> inductive HAct (one ctor per action, inputs as args)
  Dec_<a>          -> inductive Dec_<a> (Rev/Ok, carried lets as Ok args)
  decide_<a>       -> nested `let` / `cond` chain over the guard list
  exec_<a>         -> match on the decision, HSt.mk field-by-field
  step/run/obs/..  -> same names, same argument order as the Bend model
  `with` terms     -> Lean record update `{ e with f := v }`
  `?`/ite          -> `cond c x y`
Proof-facing note: `decide_<a>` takes only the guard-read state fields, so the
noninterference template can instantiate the *same* decision term on both sides.
"""
from __future__ import annotations

import re

from ..gen.machine import FactsError, Machine
from .prelude import GO_LIB, PRELUDE

# Lean reserved/keyword-ish identifiers we never emit as binders.
RESERVED = {
    "theorem", "def", "match", "with", "if", "then", "else", "do", "let", "in",
    "forall", "fun", "where", "end", "by", "have", "show", "structure",
    "inductive", "class", "instance", "import", "namespace", "open", "variable",
    "example", "axiom", "opaque", "abbrev", "universe", "Type", "Prop", "Sort",
    "to", "of", "from", "as", "at", "notation", "syntax", "macro",
    "attribute", "set_option", "deriving", "section", "mutual", "private",
    "protected", "partial", "noncomputable", "termination", "decreasing_by",
    "sorry", "admit", "decide", "native_decide", "unsafe", "implemented_by",
    "cases", "intro", "rfl", "exact", "apply", "constructor", "rw", "simp",
    "omega", "obtain", "rename_i", "next", "skip", "try", "catch", "finally",
    "unless", "return", "for", "infix", "infixl", "infixr", "prefix", "postfix",
    "macro_rules", "elab", "not", "and", "or", "xor", "mod", "div", "land",
    "lor", "lxor", "True", "False", "List", "Nat", "Bool", "Option",
}


def ln(n: str) -> str:
    return n + "_" if n in RESERVED else n


def lt(t: str) -> str:
    m = re.fullmatch(r"List<(.+)>", t)
    if m:
        return f"List ({lt(m.group(1))})"
    if t in ("Nat", "Bool"):
        return t
    if t == "State":
        return "HSt"
    if t == "Obs":
        return "HObs"
    if t == "Act":
        return "HAct"
    return "H" + t


def lty(t: str) -> str:
    """lt(t) parenthesized when used as an application argument."""
    return f"({lt(t)})" if " " in lt(t) else lt(t)


def elem(t: str) -> str:
    m = re.fullmatch(r"List<(.+)>", t)
    if not m:
        raise FactsError(f"not a list type: {t}")
    return m.group(1)


class LMachine(Machine):
    """Lean-emitting twin of gen.machine.Machine; shares the facts parsing."""

    # ------------------------------------------------------------ expressions
    def ex(self, e, env: dict) -> tuple[str, str]:
        """env: name -> (lean_text, ir_type); returns (lean_text, ir_type)."""
        if isinstance(e, bool):
            return ("true" if e else "false"), "Bool"
        if isinstance(e, int):
            return str(e), "Nat"
        if isinstance(e, str):
            if e in env:
                return env[e]
            if e in self.params:
                return str(self.params[e]), "Nat"
            raise FactsError(f"unbound variable {e}")
        if not isinstance(e, list) or not e:
            raise FactsError(f"bad expression {e!r}")
        op, *a = e
        if op in ("+", "-"):
            (x, tx), (y, ty_) = self.ex(a[0], env), self.ex(a[1], env)
            self._need(op, tx, ty_)
            return f"({('natAdd' if op == '+' else 'Nat.sub')} {x} {y})", "Nat"
        cmp2 = {"<": "isLt", "<=": "isLe", ">": "isGt", ">=": "isGe", "==": "isEq"}
        if op in cmp2 or op == "!=":
            (x, tx), (y, ty_) = self.ex(a[0], env), self.ex(a[1], env)
            self._need(op, tx, ty_)
            if op == "!=":
                return f"(Bool.not (isEq {x} {y}))", "Bool"
            return f"({cmp2[op]} {x} {y})", "Bool"
        if op in ("&&", "||"):
            parts = [self.ex(x, env) for x in a]
            if any(t != "Bool" for _, t in parts):
                raise FactsError(f"{op} needs Bool operands: {e}")
            fn = " && " if op == "&&" else " || "
            out = parts[-1][0]
            for p, _ in reversed(parts[:-1]):
                out = f"({p}{fn}{out})"
            return out, "Bool"
        if op == "!":
            x, tx = self.ex(a[0], env)
            if tx != "Bool":
                raise FactsError(f"! needs Bool: {e}")
            return f"(Bool.not {x})", "Bool"
        if op == "?":
            (c, tc), (x, tx), (y, ty_) = (self.ex(z, env) for z in a)
            if tc != "Bool" or tx != ty_:
                raise FactsError(f"ill-typed conditional {e}")
            return f"(cond {c} {x} {y})", tx
        if op == "call":
            name, *args = a
            cargs = [self.ex(x, env) for x in args]
            if name in self.defs:
                d = self.defs[name]
                if len(d["params"]) != len(cargs):
                    raise FactsError(f"{name}: arity")
                for (pn, pt), (_, at) in zip(d["params"], cargs):
                    if pt != at:
                        raise FactsError(f"{name}: argument {pn} is {at}, expected {pt}")
                return f"(d_{name} {' '.join('(' + x + ')' for x, _ in cargs)})", d["type"]
            return self.builtin(name, cargs)
        if op == "get":
            x, tx = self.ex(a[0], env)
            fields = dict(self.types.get(tx, []))
            if a[1] not in fields:
                raise FactsError(f"{tx} has no field {a[1]}")
            return f"({x}).{ln(a[1])}", fields[a[1]]
        if op == "mk":
            ty, vals = a
            parts = []
            for fn, ft in self.types[ty]:
                if fn in vals:
                    x, tx = self.ex(vals[fn], env)
                    if tx != ft:
                        raise FactsError(f"{ty}.{fn} is {ft}, got {tx}")
                    parts.append(f"({x})")
                else:
                    parts.append("(false)" if ft == "Bool" else "0")
            return f"(H{ty}.mk {' '.join(parts)})", ty
        if op == "with":
            ty, base, vals = a
            bx, btyp = self.ex(base, env)
            if btyp != ty:
                raise FactsError(f"with: {btyp} is not {ty}")
            ups = []
            for k in sorted(vals):
                x, tx = self.ex(vals[k], env)
                if tx != dict(self.types[ty])[k]:
                    raise FactsError(f"with {ty}.{k}: {tx}")
                ups.append(f"{ln(k)} := {x}")
            return f"({{ {bx} with {', '.join(ups)} }} : H{ty})", ty
        if op == "list":
            ty, *items = a
            xs = []
            for it in items:
                x, tx = self.ex(it, env)
                if tx != ty:
                    raise FactsError(f"list elem is {tx}, want {ty}")
                xs.append(x)
            return f"([{', '.join(xs)}] : {lty('List<' + ty + '>')})", f"List<{ty}>"
        raise FactsError(f"unknown operator {op}")

    @staticmethod
    def _need(op, tx, ty_):
        if tx != "Nat" or ty_ != "Nat":
            raise FactsError(f"{op} needs Nat operands ({tx}, {ty_})")

    # ------------------------------------------------------------ builtins
    def builtin(self, name: str, args: list) -> tuple[str, str]:
        txt = [a for a, _ in args]
        ty = [t for _, t in args]

        def need(n):
            if len(args) != n:
                raise FactsError(f"{name} takes {n} arguments")

        if name == "len":
            need(1)
            return f"({txt[0]}).length", "Nat"
        if name in ("take", "drop"):
            need(2)
            return f"({txt[0]}.{name} {txt[1]})", ty[0]
        if name == "tail":
            need(1)
            return f"(tail0 {txt[0]})", ty[0]
        if name == "concat":
            need(2)
            return f"({txt[0]} ++ {txt[1]})", ty[0]
        if name == "snoc":
            need(2)
            return f"({txt[0]} ++ [{txt[1]}])", ty[0]
        if name == "win_at":
            need(2)
            return f"(nthD {txt[0]} {txt[1]} emptyEntry)", "Entry"
        if name == "win_last":
            need(1)
            return f"(lastD {txt[0]} emptyEntry)", "Entry"
        if name == "nth_ch":
            need(2)
            return f"(nthD {txt[0]} {txt[1]} emptyCh)", "Ch"
        if name == "set_ch":
            need(3)
            return f"(setD {txt[0]} {txt[1]} {txt[2]} emptyCh)", "List<Ch>"
        if name == "empty_entry":
            return "emptyEntry", "Entry"
        if name == "empty_ch":
            return "emptyCh", "Ch"
        if name == "agg":
            need(1)
            return f"(natAdd {self.params.get('AGG_BASE', 1000)} (bEnc {txt[0]}))", "Nat"
        if name == "go_read":
            need(2)
            return f"(bGoRead {txt[0]} {txt[1]})", "List<Nat>"
        if name == "go_append_slice":
            need(4)
            return f"(bGoAppendSlice {' '.join(txt)})", "Sl"
        if name == "go_append_heap":
            need(4)
            return f"(bGoAppendHeap {' '.join(txt)})", "List<Arr>"
        if name == "eq_nats":
            need(2)
            return f"(eqListNat {txt[0]} {txt[1]})", "Bool"
        fixed = {"nth": "bNth", "set_nat": "bSetNat", "mem": "bMem", "remove": "bRemove",
                 "blob_count": "bBlobCount", "zeros_like": "bZerosLike", "bump_f": "bBumpF",
                 "any_open": "bAnyOpen", "clear_chs": "bClearChs", "zero_csr": "bZeroCsr",
                 "set_last_csr": "bSetLastCsr", "tags_exact": "bTagsExact", "hdr_of": "bHdrOf"}
        rets = {"nth": "Nat", "set_nat": "List<Nat>", "mem": "Bool", "remove": "List<Nat>",
                "blob_count": "Nat", "zeros_like": "List<Nat>", "bump_f": "List<Entry>",
                "any_open": "Bool", "clear_chs": "List<Ch>", "zero_csr": "List<Entry>",
                "set_last_csr": "List<Entry>", "tags_exact": "Bool", "hdr_of": "List<Nat>"}
        for sf, field in (self.shadow or {}).items():
            fixed[f"es_{field}"] = f"bEs_{field}"
            rets[f"es_{field}"] = self.stypes[sf]
        if name in fixed:
            return f"({fixed[name]} {' '.join(txt)})", rets[name]
        raise FactsError(f"unknown function {name}")

    # ------------------------------------------------------------ types & lib
    def gen_types(self) -> list[str]:
        out = []
        for ty, fields in self.types.items():
            out.append(f"structure H{ty} where")
            out += [f"  {ln(f)} : {lt(t)}" for f, t in fields]
            out += ["  deriving DecidableEq, BEq", ""]
        out += ["inductive HObs where", "  | O_Ok : HObs", "  | O_Rev (code : Nat) : HObs",
                "  deriving DecidableEq, BEq", ""]
        out.append("structure HSt where")
        out += [f"  {ln(n)} : {lt(t)}" for n, t in self.state]
        out += ["  deriving DecidableEq, BEq", ""]
        out.append("inductive HAct where")
        for a in self.actions:
            ins = " ".join(f"({ln(n)} : {lt(t)})" for n, t in a["inputs"])
            out.append(f"  | A_{a['name']} {ins} : HAct" if ins else f"  | A_{a['name']} : HAct")
        out += ["  deriving DecidableEq, BEq", ""]
        return out

    def gen_record_lib(self) -> list[str]:
        def zero(t):
            return "false" if t == "Bool" else ("([] : " + lty(t) + ")" if t.startswith("List<") else "0")

        out = []
        for ty, fields in self.types.items():
            out += [f"def empty_{ty} : H{ty} := H{ty}.mk {' '.join(zero(t) for _, t in fields)}", ""]
        if "Sl" in self.types and "Arr" in self.types:
            out += ["def emptySl : HSl := empty_Sl", "def emptyArr : HArr := empty_Arr", ""] + GO_LIB.splitlines() + [""]
        if "Entry" not in self.types:
            return out
        E = dict(self.types["Entry"])
        out += ["def emptyEntry : HEntry := empty_Entry", ""]
        if "Ch" in self.types:
            out += ["def emptyCh : HCh := empty_Ch", ""]
        for sf, field in (self.shadow or {}).items():
            ef = dict(self.types["Entry"])
            if field in ef:
                body = f"e.{ln(field)}"
            else:
                # the shadow field is a record assembled from Entry fields named <field><sub>,
                # e.g. bd -> HBD{bdo, bdf, bdn, bds} (mirrors machine.gen_record_lib).
                et = elem(self.stypes[sf])
                parts = " ".join(f"e.{ln(field + sub)}" for sub, _ in self.types[et])
                body = f"(H{et}.mk {parts})"
            out += [f"def bEs_{field} (es : List HEntry) : {lt(self.stypes[sf])} := es.map fun e => {body}", ""]
        out += [
            "def bBumpGo : List HEntry -> Nat -> Nat -> Nat -> List HEntry",
            "  | [], _, _, _ => []",
            "  | e :: t, pos, skip, w =>",
            "      (if (isGt pos 0 && Bool.not (isEq pos skip)) then { e with bdf := natAdd e.bdf w } else e)",
            "        :: bBumpGo t (natAdd pos 1) skip w",
            "",
            "def bBumpF (es : List HEntry) (skip w : Nat) : List HEntry := bBumpGo es 0 skip w",
            "",
        ]
        if "Ch" in self.types:
            chf = list(dict(self.types["Ch"]))
            out += [
                "def bAnyGo : List HCh -> Nat -> Nat -> Nat -> Bool",
                "  | [], _, _, _ => false",
                "  | c :: t, i, lo, hi =>",
                "      (isGe i lo && isLe i hi && Bool.not (isEq c.c 0) && Bool.not c.f) || bAnyGo t (natAdd i 1) lo hi",
                "",
                "def bAnyOpen (cs : List HCh) (lo hi : Nat) : Bool := bAnyGo cs 0 lo hi",
                "",
                "def bClearGo : List HCh -> Nat -> Nat -> Nat -> List HCh",
                "  | [], _, _, _ => []",
                "  | c :: t, i, lo, hi =>",
                "      (if isGe i lo && isLe i hi then emptyCh else c) :: bClearGo t (natAdd i 1) lo hi",
                "",
                "def bClearChs (cs : List HCh) (lo hi : Nat) : List HCh := bClearGo cs 0 lo hi",
                "",
            ]
            del chf
        out += [
            "def bZeroCsr : List HEntry -> List HEntry",
            "  | [] => []",
            "  | e :: t => { e with csr := 0 } :: bZeroCsr t",
            "",
            "def bSetLastCsr : List HEntry -> Nat -> List HEntry",
            "  | [], _ => []",
            "  | [e], r => [{ e with csr := r }]",
            "  | e :: e2 :: t2, r => e :: bSetLastCsr (e2 :: t2) r",
            "",
            "def bTagsExact : List HEntry -> Bool",
            "  | [] => true",
            "  | e :: t => (isEq e.ver 2 == isEq e.tag 2) && bTagsExact t",
            "",
            "def bHdrOf (e : HEntry) : List Nat := [e.ver, e.tot, e.n, e.hb, e.prev, e.post, e.lbn]",
            "",
        ]
        return out

    def gen_defs(self) -> list[str]:
        out = []
        for name, d in self.defs.items():
            env = {p: (ln(p), t) for p, t in d["params"]}
            body, ty = self.ex(d["body"], env)
            if ty != d["type"]:
                raise FactsError(f"def {name}: body is {ty}, declared {d['type']}")
            params = " ".join(f"({ln(p)} : {lt(t)})" for p, t in d["params"])
            out += [f"def d_{name} {params} : {lt(d['type'])} :=", f"  {body}", ""]
        return out

    def action_reads(self, a: dict) -> list[str]:
        """State fields read by the action's guard list (lets don't count)."""
        guard_fv: set[str] = set()
        let_names = []
        for gd in a["guards"]:
            if "let" in gd:
                guard_fv |= self.fv(gd["expr"])
                let_names.append(gd["let"])
            else:
                guard_fv |= self.fv(gd["require"])
        return [n for n, _ in self.state if n in guard_fv and n not in let_names]

    # ------------------------------------------------------------ actions
    def gen_action(self, a: dict) -> list[str]:
        name, inputs, guards, effects = a["name"], a["inputs"], a["guards"], a["effects"]
        for f in effects:
            if f not in self.stypes or f == "log":
                raise FactsError(f"{name}: effect on unknown field {f}")
        lets_t: dict[str, str] = {}
        guard_fv: set[str] = set()
        let_names = []
        for gd in guards:
            if "let" in gd:
                guard_fv |= self.fv(gd["expr"])
                let_names.append(gd["let"])
            else:
                guard_fv |= self.fv(gd["require"])
        eff_fv = set().union(*(self.fv(e) for e in effects.values())) if effects else set()
        reads = self.action_reads(a)
        self.reads[name] = reads
        carried = [l for l in let_names if l in eff_fv]
        env: dict = {n: (ln(n), self.stypes[n]) for n in reads}
        env.update({n: (ln(n), t) for n, t in inputs})
        tenv = dict(env)
        for gd in guards:
            if "let" in gd:
                _, ty = self.ex(gd["expr"], tenv)
                tenv[gd["let"]] = (ln(gd["let"]), ty)
                lets_t[gd["let"]] = ty
            else:
                _, ty = self.ex(gd["require"], tenv)
                if ty != "Bool":
                    raise FactsError(f"{name}: require is {ty}")
        dec = f"Dec_{name}"
        out = [f"inductive {dec} where", f"  | Rev (code : Nat) : {dec}"]
        oks = " ".join(f"({ln(l)} : {lt(lets_t[l])})" for l in carried)
        out += [f"  | Ok {oks} : {dec}" if carried else f"  | Ok : {dec}", ""]

        def seq(i, env):
            lines = []
            while i < len(guards):
                gd = guards[i]
                if "let" in gd:
                    x, ty = self.ex(gd["expr"], env)
                    lines.append(("let", gd["let"], x))
                    env[gd["let"]] = (ln(gd["let"]), ty)
                    i += 1
                    continue
                cond, _ = self.ex(gd["require"], env)
                return lines + [("cond", cond, seq(i + 1, dict(env)), gd["reason"])]
            return lines + [("ok",)]

        def render(items, ind):
            s = ""
            for it in items:
                if it[0] == "let":
                    s += f"{ind}let {ln(it[1])} := {it[2]}\n"
                elif it[0] == "cond":
                    s += (f"{ind}cond ({it[1]})\n{ind}  (\n" + render(it[2], ind + "    ")
                          + f"{ind}  )\n{ind}  ({dec}.Rev {it[3]})\n")
                else:
                    tail = " " + " ".join(ln(l) for l in carried) if carried else ""
                    s += f"{ind}{dec}.Ok{tail}\n"
            return s

        dparams = " ".join(f"({ln(n)} : {lt(t)})" for n, t in [(r, self.stypes[r]) for r in reads] + inputs)
        out += [f"def decide_{name} {dparams} : {dec} :=\n" + render(seq(0, dict(env)), "  ").rstrip(), ""]
        # exec
        eenv = {n: (ln(n), t) for n, t in self.state}
        eenv.update({n: (ln(n), t) for n, t in inputs})
        eenv.update({l: (ln(l), lets_t[l]) for l in carried})
        new_fields = []
        for n, t in self.state:
            if n == "log":
                new_fields.append("((HObs.O_Ok) :: log)")
            elif n in effects:
                x, ty = self.ex(effects[n], eenv)
                if ty != t:
                    raise FactsError(f"{name}: effect on {n} is {ty}, field is {t}")
                new_fields.append(f"({x})")
            else:
                new_fields.append(ln(n))
        unchanged = ["((HObs.O_Rev code) :: log)" if n == "log" else ln(n) for n, _ in self.state]
        fparams = " ".join(f"({ln(n)} : {lt(t)})" for n, t in self.state)
        iparams = " ".join(f"({ln(n)} : {lt(t)})" for n, t in inputs)
        okpat = " ".join(ln(l) for l in carried)
        out += [
            f"def exec_{name} (d : {dec}) {fparams} {iparams} : HSt :=",
            "  match d with",
            f"  | .Rev code => HSt.mk {' '.join(unchanged)}",
            f"  | .Ok {okpat} => HSt.mk {' '.join(new_fields)}" if carried else f"  | .Ok => HSt.mk {' '.join(new_fields)}",
            "",
        ]
        dargs = " ".join([f"s.{ln(r)}" for r in reads] + [ln(n) for n, _ in inputs])
        fargs = " ".join(f"s.{ln(n)}" for n, _ in self.state)
        iargs = " ".join(ln(n) for n, _ in inputs)
        out += [
            f"def step_{name} (s : HSt){' ' + iparams if iparams else ''} : HSt :=",
            f"  exec_{name} (decide_{name} {dargs}) {fargs}{' ' + iargs if iargs else ''}",
            "",
        ]
        return out

    # ------------------------------------------------------------ dispatch
    def gen_dispatch(self) -> list[str]:
        out = ["def step (a : HAct) (s : HSt) : HSt :=", "  match a with"]
        for a in self.actions:
            ins = [ln(n) for n, _ in a["inputs"]]
            out.append(f"  | .A_{a['name']} {' '.join(ins)} => step_{a['name']} s{' ' + ' '.join(ins) if ins else ''}")
        out += ["", "def run : List HAct -> HSt -> HSt", "  | [], s => s", "  | a :: rest, s => run rest (step a s)", "",
                "def clear_log (s : HSt) : HSt := { s with log := [] }", "",
                "def log_of (s : HSt) : List HObs := s.log", "",
                "def obs (tr : List HAct) (s : HSt) : List HObs := log_of (run tr (clear_log s))", "",
                "def ok_head : List HObs -> Bool",
                "  | [] => false",
                "  | .O_Ok :: _ => true",
                "  | .O_Rev _ :: _ => false",
                "",
                "def last_ok (s : HSt) : Bool := ok_head s.log", "",
                "def all_ok : List HObs -> Bool",
                "  | [] => true",
                "  | .O_Ok :: t => all_ok t",
                "  | .O_Rev _ :: _ => false",
                "",
                "def runs_ok (tr : List HAct) (s : HSt) : Bool := all_ok (obs tr s)", "",
                "def no_code : List HObs -> Nat -> Bool",
                "  | [], _ => true",
                "  | .O_Ok :: t, k => no_code t k",
                "  | .O_Rev c :: t, k => Bool.not (isEq c k) && no_code t k",
                "",
                "def eq_obs : HObs -> HObs -> Bool",
                "  | .O_Ok, .O_Ok => true",
                "  | .O_Rev x, .O_Rev y => isEq x y",
                "  | _, _ => false",
                "",
                "def eq_obs_list : List HObs -> List HObs -> Bool",
                "  | [], [] => true",
                "  | x :: xt, y :: yt => eq_obs x y && eq_obs_list xt yt",
                "  | _, _ => false",
                ""]
        for a in self.actions:
            out += [f"def is_{a['name']} : HAct -> Bool"]
            for b in self.actions:
                pat = " ".join("_" for _ in b["inputs"])
                out.append(f"  | .A_{b['name']} {pat} => {'true' if b is a else 'false'}")
            out.append("")
        disch = self.f.get("disch", {})
        cost, delay = disch.get("cost", {}), disch.get("delay", {})
        for fname, pick in (("cost", lambda b: str(cost[b["name"]]) if b["name"] in cost else None),
                            ("elapsed", lambda b: ln(delay["input"]) if b["name"] == delay.get("action") else None)):
            out += [f"def {fname} : List HAct -> Nat", "  | [] => 0", "  | a :: rest =>"]
            out += [f"      match a with"]
            for b in self.actions:
                v = pick(b)
                ins = [ln(n) for n, _ in b["inputs"]]
                pat = " ".join(i if (v and i == v) else "_" for i in ins)
                out.append(f"      | .A_{b['name']} {pat} => natAdd {v or '0'} ({fname} rest)")
            out.append("")
        for cname, c in self.f.get("consumers", {}).items():
            ret = next((t for b in self.actions for n, t in b["inputs"] if n == c["input"]), "List<Nat>")
            out += [f"def {cname} : HAct -> {lt(ret)}", "  | a =>", "    match a with"]
            for b in self.actions:
                ins = [n for n, _ in b["inputs"]]
                pat = " ".join(ln(i) if i == c["input"] else "_" for i in ins)
                out.append(f"    | .A_{b['name']} {pat} => {ln(c['input']) if c['input'] in ins else '[]'}")
            out.append("")
        perm = [a["name"] for a in self.actions if a.get("principal", "").startswith(("anyone", "environment"))]
        out += ["def perm : HAct -> Bool"]
        for b in self.actions:
            pat = " ".join("_" for _ in b["inputs"])
            out.append(f"  | .A_{b['name']} {pat} => {'true' if b['name'] in perm else 'false'}")
        out.append("")
        return out

    # ------------------------------------------------------------ observers
    def gen_observers(self) -> list[str]:
        out = []
        env = {n: (f"s.{ln(n)}", t) for n, t in self.state}
        for name, o in self.f.get("observers", {}).items():
            body, ty = self.ex(o["body"], env)
            if ty != o["type"]:
                raise FactsError(f"observer {name}: {ty} vs {o['type']}")
            out += [f"def {name} (s : HSt) : {lt(ty)} :=", f"  {body}", ""]
        for name, m in self.f.get("migrations", {}).items():
            ins = [(n, t) for n, t in m.get("inputs", [])]
            env2 = {n: (f"s.{ln(n)}", t) for n, t in self.state}
            env2.update({n: (ln(n), t) for n, t in ins})
            ups = []
            for n, t in self.state:
                if n in m["effects"]:
                    x, ty = self.ex(m["effects"][n], env2)
                    if ty != t:
                        raise FactsError(f"migration {name}.{n}")
                    ups.append(f"{ln(n)} := {x}")
            ip = " ".join(f"({ln(n)} : {lt(t)})" for n, t in ins)
            body = "{ s with " + ", ".join(ups) + " }" if ups else "s"
            out += [f"def mig_{name} (s : HSt){' ' + ip if ip else ''} : HSt :=", f"  {body}", ""]
        return out

    # ------------------------------------------------------------ literals
    def literal(self, ty: str, v) -> str:
        if ty == "Nat":
            return str(int(v))
        if ty == "Bool":
            return "true" if v else "false"
        if ty.startswith("List<"):
            et = elem(ty)
            items = [self.literal(et, x) for x in v]
            return f"([{', '.join(items)}] : {lty(ty)})"
        if ty in self.types:
            return f"(H{ty}.mk {' '.join(self.literal(ft, v.get(fn, False if ft == 'Bool' else 0)) for fn, ft in self.types[ty])})"
        if ty == "Obs":
            if isinstance(v, dict):
                return "HObs.O_Ok" if v["$"] == "O_Ok" else f"(HObs.O_Rev {int(v['code'])})"
            return "HObs.O_Ok" if v == "ok" else f"(HObs.O_Rev {int(v)})"
        raise FactsError(f"no literal for {ty}")

    def act_literal(self, act: dict) -> str:
        a = next((x for x in self.actions if x["name"] == act["op"]), None)
        if a is None:
            raise FactsError(f"unknown action {act['op']}")
        args = " ".join(f"({self.literal(t, act[n])})" for n, t in a["inputs"])
        return f"(HAct.A_{a['name']} {args})" if args else "HAct.A_" + a["name"]

    def trace_literal(self, tr: list) -> str:
        items = [self.act_literal(a) for a in tr]
        return f"([{', '.join(items)}] : List HAct)"

    def state_literal(self, st: dict) -> str:
        return f"(HSt.mk {' '.join(self.literal(t, st.get(n, False if t == 'Bool' else 0)) for n, t in self.state)})"

    def gen_initial(self) -> list[str]:
        init = self.f["initial"]
        return ["def s0 : HSt := " + self.state_literal(init), ""]

    def generate(self, facts_sha256: str) -> str:
        body = []
        body += self.gen_types()
        body += self.gen_record_lib()
        body += self.gen_defs()
        for a in self.actions:
            body += self.gen_action(a)
        body += self.gen_dispatch()
        body += self.gen_observers()
        body += self.gen_initial()
        head = ["-- GENERATED by holon.lean.machine from facts; do not edit (fix the generator instead).",
                f"-- facts_sha256: {facts_sha256}", f"-- target: {self.f['target']['repo']} @ {self.f['target']['commit']}",
                "set_option linter.unusedVariables false", ""]
        text = head + [PRELUDE] + body
        return "\n".join(text).rstrip() + "\n"


def generate(facts: dict, facts_sha256: str) -> str:
    return LMachine(facts).generate(facts_sha256)
