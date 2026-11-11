"""The lane's model of a contract (key I55 design M1, S): generated from the factory's transitions document.

gen/M5/intent/model/<contract>.bend holds Base, the factory's 256-bit word prelude (holon.sorts.prelude3.PRELUDE,
raw), the record St of the contract's scalar storage (one W per scalar, pre-transaction storage being free under
A-env), per supported action a the record X_<a> (its parameters, the caller and the env terms it reads), chk_<a>
(0 when every check of a's program holds, else 1 + the index of the first that fails, in holon.machine's program
order), post_<a> (the post-state: the document's post terms, else the field unchanged) and ret_<a> (its one return
value), and the lane's statement helpers (HELPERS).

Terms. A model term is a JSON tree of the lane's statement language (tests_m5/_i55.term_problems): {"var"}, {"w": int}
(a 256-bit literal), {"u32": int}, {"nat": int}, {"bool": bool}, {"fn": Base function, "args"}, {"m": model function or
constructor, "args"}, {"act": action function, "args"}. The same trees state the laws (holon.intent.compile) and feed
the bool_cases proof class (holon.intent.run). Supported document terms: param, caller, scalar storage, env, integer
literals, + - * / % (a literal divisor below 2^16 divides limb by limb, w_div_small and w_mod_small, as the factory's
M3 generator does), == != < <= > >=, !, &&, ||, ?, and fits 256 of + - *. Anything else makes its action unsupported
(model_unsupported, with the construct named). A document term's arithmetic is exact; a fits-256 panic guards every
checked operation, so the wrapping word operation equals the exact value wherever the action does not revert.
"""
from __future__ import annotations

import re

from ..machine import Check, Event, Write, build_program

MASK = (1 << 256) - 1
BOOL_PRELUDE = frozenset(("w_eq", "w_lt", "w_le", "w_gt", "w_ge", "w_add_ok", "w_sub_ok", "w_mul_ok", "w_nz",
                          "ip_le_pct"))
HELPERS = """
# ---- intent lane: statement helpers (holon.intent.model HELPERS)
def ip_ite_w(c: Bool, a: W, b: W) -> W:
  ite(W, c, a, b)

def ip_ite_u(c: Bool, a: U32, b: U32) -> U32:
  ite(U32, c, a, b)

def ip_ite_b(c: Bool, a: Bool, b: Bool) -> Bool:
  ite(Bool, c, a, b)

def ip_lle(xs: List<&2, U32>, ys: List<&2, U32>, lo: Bool) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      lo
    case Nil{} Con{y, yt}:
      lo
    case Con{x, xt} Nil{}:
      lo
    case Con{+x, xt} Con{+y, yt}:
      ip_lle(xt, yt, Bool.or(U32.is_lt(x, y), Bool.and(U32.is_eq(x, y), lo)))

def ip_le_pct(+r: W, +n: U32, +a: W) -> Bool:
  ip_lle(l_mul1(w_limbs(r), 100, 0), l_mul1(w_limbs(a), n, 0), True{})

def ip_is_true(b: Bool) -> Type:
  match b:
    case True{}:
      Unit
    case False{}:
      Empty
"""


class Unsupported(Exception):
    pass


def ident(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


def W(k: int) -> dict:
    return {"w": int(k) & MASK}


def m(f: str, *args) -> dict:
    return {"m": f, "args": list(args)}


def fn(f: str, *args) -> dict:
    return {"fn": f, "args": list(args)}


def act(f: str, *args) -> dict:
    return {"act": f, "args": list(args)}


def var(v: str) -> dict:
    return {"var": v}


# ------------------------------------------------------------------ rendering
def wlit(k: int, prefix: str) -> str:
    return prefix + "W{" + ", ".join(str((k >> (32 * i)) & 0xFFFFFFFF) for i in range(8)) + "}"


def render(t: dict, prefix: str = "", sub: dict | None = None) -> str:
    """Bend text of a term; prefix qualifies model names ("M." in a law file); sub maps an act name to a binder."""
    if "var" in t:
        return t["var"]
    if "w" in t:
        return wlit(t["w"], prefix)
    if "u32" in t:
        return str(t["u32"])
    if "nat" in t:
        return f"{t['nat']}n"
    if "bool" in t:
        return "True{}" if t["bool"] else "False{}"
    args = ", ".join(render(a, prefix, sub) for a in t["args"])
    if "fn" in t:
        return f"{t['fn']}({args})"
    if "act" in t:
        if sub and t["act"] in sub:
            return f"{sub[t['act']]}({args})"
        return f"{prefix}{t['act']}({args})"
    name = t["m"]
    if name[:1].isupper():
        return f"{prefix}{name}{{{args}}}"
    return f"{prefix}{name}({args})"


# ------------------------------------------------------------------ the model of one contract
class Model:
    def __init__(self, doc: dict):
        self.doc = doc
        self.contract = doc["contract"] if isinstance(doc.get("contract"), str) else doc["contract"]["name"]
        self.scalars = []          # [(name, value type)]
        for s in doc.get("storage") or []:
            if s.get("kind") == "scalar":
                self.scalars.append((s["name"], s.get("value", "")))
        self.fields = {n: "f_" + ident(n) for n, _ in self.scalars}
        self.actions = {}          # name -> {"x": [(field, origin)], "chk", "post", "ret", "params"}
        self.unsupported = {}      # name -> reason
        for a in sorted(doc.get("actions") or [], key=lambda a: a["name"]):
            try:
                self.actions[a["name"]] = self._action(a)
            except Unsupported as e:
                self.unsupported[a["name"]] = str(e)
            except Exception as e:  # noqa: BLE001 - a document the program builder refuses is unsupported, named
                self.unsupported[a["name"]] = f"program: {type(e).__name__}: {str(e)[:200]}"

    def action_doc(self, name: str) -> dict:
        return next(a for a in self.doc["actions"] if a["name"] == name)

    def scalar_type(self, name: str) -> str | None:
        return dict(self.scalars).get(name)

    # -------------------------------------------------------------- terms
    def _action(self, a: dict) -> dict:
        name = a["name"]
        xs: list = [("p_" + ident(p["name"]), ["param", p["name"]]) for p in a.get("params") or []]
        xs.append(("caller", ["caller"]))

        def xfield(key: str, origin) -> dict:
            if key not in [k for k, _ in xs]:
                xs.append((key, origin))
            return m(f"x_{ident(name)}_{key}", var("x"))

        def word(t) -> dict:
            if isinstance(t, bool):
                return W(int(t))
            if isinstance(t, int):
                return W(t)
            if not isinstance(t, list) or not t or not isinstance(t[0], str):
                raise Unsupported(f"term {str(t)[:80]}")
            op = t[0]
            if op == "param":
                return xfield("p_" + ident(t[1]), t)
            if op == "caller":
                return xfield("caller", t)
            if op == "env":
                return xfield("e_" + ident(t[1]), t)
            if op == "storage":
                if t[1] not in self.fields:
                    raise Unsupported(f"storage {t[1]} is not a scalar of {self.contract}")
                return m("st_" + ident(t[1]), var("s"))
            if op in ("/", "%") and len(t) == 3 and isinstance(t[2], int) and not isinstance(t[2], bool) \
                    and 0 < t[2] < (1 << 16):
                # as the factory's M3 generator does (holon.sorts.model3 t_div, t_mod): a small literal divisor
                # divides limb by limb, which both kernels evaluate within budget; the value is the same
                return m("w_div_small" if op == "/" else "w_mod_small", word(t[1]), {"u32": t[2]})
            if op in ("+", "-", "*", "/", "%") and len(t) == 3:
                f = {"+": "w_add", "-": "w_sub", "*": "w_mul", "/": "w_div", "%": "w_mod"}[op]
                return m(f, word(t[1]), word(t[2]))
            if op == "?" and len(t) == 4:
                return m("ip_ite_w", boolean(t[1]), word(t[2]), word(t[3]))
            if op in ("==", "!=", "<", "<=", ">", ">=", "!", "&&", "||", "fits"):
                return m("w_b", boolean(t))
            raise Unsupported(f"operator {op}")

        def boolean(t) -> dict:
            if isinstance(t, bool):
                return {"bool": t}
            if isinstance(t, int):
                return {"bool": t != 0}
            if isinstance(t, list) and t and isinstance(t[0], str):
                op = t[0]
                cmp = {"==": "w_eq", "<": "w_lt", "<=": "w_le", ">": "w_gt", ">=": "w_ge"}
                if op in cmp and len(t) == 3:
                    return m(cmp[op], word(t[1]), word(t[2]))
                if op == "!=" and len(t) == 3:
                    return fn("Bool.not", m("w_eq", word(t[1]), word(t[2])))
                if op == "!" and len(t) == 2:
                    return fn("Bool.not", boolean(t[1]))
                if op in ("&&", "||") and len(t) == 3:
                    return fn("Bool.and" if op == "&&" else "Bool.or", boolean(t[1]), boolean(t[2]))
                if op == "?" and len(t) == 4:
                    return m("ip_ite_b", boolean(t[1]), boolean(t[2]), boolean(t[3]))
                if op == "fits":
                    inner = t[2] if len(t) == 3 else None
                    if t[1] == 256 and isinstance(inner, list) and inner and inner[0] in ("+", "-", "*") \
                            and len(inner) == 3:
                        f = {"+": "w_add_ok", "-": "w_sub_ok", "*": "w_mul_ok"}[inner[0]]
                        return m(f, word(inner[1]), word(inner[2]))
                    raise Unsupported(f"fits {str(t[1:])[:60]}")
            return m("w_nz", word(t))

        prog = build_program(a)
        conds = []
        for st in prog.steps:
            if isinstance(st, Check):
                if st.kind == "call":
                    raise Unsupported("an external call")
                conds.append(boolean(st.expr))
            elif isinstance(st, Write):
                if st.path or st.family not in self.fields:
                    raise Unsupported(f"a write of {st.family} (not a scalar of {self.contract})")
            elif not isinstance(st, Event):
                raise Unsupported(f"a {type(st).__name__} record")
        chk = {"u32": 0}
        for k in range(len(conds) - 1, -1, -1):
            chk = m("ip_ite_u", conds[k], chk, {"u32": k + 1})
        post_terms = a.get("post") or {}
        for fam in post_terms:
            if fam not in self.fields:
                raise Unsupported(f"post of {fam} (not a scalar of {self.contract})")
        post = m("St", *([word(post_terms[n]) if n in post_terms else m("st_" + ident(n), var("s"))
                          for n, _ in self.scalars] or [m("st_none", var("s"))]))
        ret, r = None, a.get("returns")
        if r is not None:
            if isinstance(r, list) and r and isinstance(r[0], list):
                if len(r) != 1:
                    raise Unsupported("more than one return value")
                r = r[0]
            ret = word(r)
        return {"x": xs, "chk": chk, "post": post, "ret": ret, "params": [p["name"] for p in a.get("params") or []]}

    # -------------------------------------------------------------- the Bend text
    def st_type(self) -> str:
        return "St"

    def x_type(self, a: str) -> str:
        return f"X_{ident(a)}"

    def text(self, prelude: str) -> str:
        out = ["import Base", "", prelude.rstrip("\n"), HELPERS.rstrip("\n"), "",
               f"# ---- intent lane: the model of {self.contract} (holon.intent.model)"]
        flds = [self.fields[n] for n, _ in self.scalars] or ["f_none"]
        out += ["type St is Data:", "  St{" + ", ".join(f"{f}: W" for f in flds) + "}", ""]
        for f in flds:
            out += [f"def st_{f[2:]}(s: St) -> W:", "  match s:", "    case St{" + ", ".join(flds) + "}:",
                    f"      {f}", ""]
        for a, info in sorted(self.actions.items()):
            xt = self.x_type(a)
            xf = [k for k, _ in info["x"]] or ["none"]
            out += [f"type {xt} is Data:", f"  {xt}{{" + ", ".join(f"{k}: W" for k in xf) + "}", ""]
            for k in xf:
                out += [f"def x_{ident(a)}_{k}(x: {xt}) -> W:", "  match x:", f"    case {xt}{{" + ", ".join(xf) + "}:",
                        f"      {k}", ""]
            out += [f"def chk_{ident(a)}(+s: St, +x: {xt}) -> U32:", "  " + render(info["chk"]), ""]
            out += [f"def post_{ident(a)}(+s: St, +x: {xt}) -> St:", "  " + render(info["post"]), ""]
            if info["ret"] is not None:
                out += [f"def ret_{ident(a)}(+s: St, +x: {xt}) -> W:", "  " + render(info["ret"]), ""]
        return "\n".join(out).rstrip("\n") + "\n"

    def x_fields(self, a: str) -> list[str]:
        return [k for k, _ in self.actions[a]["x"]] or ["none"]

    def st_fields(self) -> list[str]:
        return [self.fields[n] for n, _ in self.scalars] or ["f_none"]

    def literals(self, actions: list[str]) -> list[int]:
        """Every integer literal of the given actions' document terms (R2's candidate values)."""
        out = set()

        def walk(t):
            if isinstance(t, bool):
                return
            if isinstance(t, int):
                out.add(t & MASK)
            elif isinstance(t, list):
                for x in t:
                    walk(x)
            elif isinstance(t, dict):
                for v in t.values():
                    walk(v)
        for a in actions:
            ad = self.action_doc(a)
            for sec in ("checks", "panics"):
                for r in ad.get(sec) or []:
                    walk(r.get("expr"))
            for g in ad.get("guards") or []:
                for r in g.get("reaches") or []:
                    walk(r.get("expr"))
            walk(list((ad.get("post") or {}).values()))
            walk(ad.get("returns"))
        return sorted(out)
