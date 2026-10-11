"""Mechanical AST -> guarded-command translation for the Solidity frontend.

The translator walks solc AST statements/expressions and emits the
holon-facts/0.2 guarded-command stream: requires (ordered, with reason and
src), lets (named bindings), writes (state/entry/map effects, conditionalized
by path conditions), and coverage-debt items for constructs the frontend
cannot translate (never approximated).

Everything target-specific is data: storage families, oracle rules, header
carriers, input/member maps, named-let tables, composite handler config —
all declared in specs/*.spec.json.
"""
from __future__ import annotations

from .sexpr import AND, OR, NOT, simplify, normalize, is_call

BINOP = {"+": "+", "-": "-", "*": "*", "/": "/", "<": "<", "<=": "<=",
         ">": ">", ">=": ">=", "==": "==", "!=": "!=", "&&": "&&", "||": "||"}


def canon(e):
    return repr(normalize(simplify(e)))


def _subst_name(e, name, val):
    """Replace every leaf equal to `name` with `val` (def-guard param substitution)."""
    if e == name:
        return val
    if isinstance(e, list):
        return [_subst_name(x, name, val) for x in e]
    return e


def _contract_name(tname):
    """'contract ISubmitter' or 'type(contract ISubmitter)' -> 'ISubmitter'."""
    if "contract" not in tname:
        return None
    t = tname.replace("type(", "").rstrip(")")
    for w in t.split():
        if w not in ("contract", "interface", "library", "abstract"):
            return w.split(".")[-1]
    return None


class Carrier:
    """A presented batch header (honest-header premise)."""

    def __init__(self, kind, idx_expr):
        self.kind = kind          # 'parent' | 'self'
        self.idx = idx_expr       # DSL expr for the index the header names
        self.hash = ("hash", kind)

    def __repr__(self):
        return f"<Carrier {self.kind} idx={self.idx!r}>"


class Translator:
    def __init__(self, world, spec):
        self.world = world
        self.spec = spec
        self.guards = []            # emitted guard/let items
        self.writes = []            # (family_kind, key, conds, expr)
        self.debt = []              # coverage debt items
        self.notes = []             # emitted notes attached to next require
        self.env = {}               # locals: name -> expr | Carrier | UNBOUND
        self.expr_lets = {}         # canon(expr) -> queue of names
        self.let_exprs = {}         # canon(expr) -> bound name
        self.pending = []           # pending let/guard items before next emit
        self.established = []       # normalized established requires
        self.subst = {}             # var -> expr established equalities
        self.new_entry = None       # pending window-entry dict
        self.lci_write = None       # last lci assignment expr
        self.ret = []               # (conds, expr) returns for view fns
        self.blob_lets_done = False
        self.blob_indices = []
        self.call_guards = {}       # fn key -> guards collected for call sites
        self.in_unchecked = False
        self.debt_keys = set()

    # ---------------------------------------------------------------- utils
    def line(self, node):
        p, l = self.world.srcpos(node)
        return l

    def src(self, node):
        p, l = self.world.srcpos(node)
        return f"{self.world.repo_path(p)}:{l}"

    def src_span(self, node):
        p = node["__file"]
        a = self.world.line(node)
        b = self.world.line_end(node)
        return f"{self.world.repo_path(p)}:{a}-{b}" if b > a else f"{self.world.repo_path(p)}:{a}"

    def add_debt(self, element, kind, reason):
        k = (element, kind)
        if k not in self.debt_keys:
            self.debt_keys.add(k)
            self.debt.append({"element": element, "kind": kind, "reason": reason})

    # ------------------------------------------------------------ emission
    def emit_let(self, name, expr, src=None):
        self.guards.append({"let": name, "expr": expr, **({"src": src} if src else {})})
        self.let_exprs[canon(expr)] = name

    def _drain_pending(self):
        for it in self.pending:
            self.guards.append(it)
        self.pending = []

    def emit_require(self, expr, reason_str, src, note=None, site=None):
        conds = getattr(self, "conds", [])
        e = simplify(expr)
        if conds:
            e = simplify(OR(NOT(AND(*conds)), e))
        self._drain_pending()
        rid = self.reason_id(reason_str)
        item = {"require": e, "reason": rid, "src": src}
        if site:
            item["site"] = site
        if note:
            item["note"] = note
        self.guards.append(item)
        self.established.append(normalize(e))
        if isinstance(e, list) and e[0] == "==":
            if isinstance(e[1], str) and e[1].isidentifier():
                self.subst.setdefault(e[1], e[2])
        return item

    def reason_id(self, s):
        rs = self.reasons.setdefault(s, len(self.reasons) + 1)
        return rs

    def note(self, text):
        if self.pending_notes is not None:
            self.pending_notes.append(text)

    def bind_or_let(self, expr, name=None, src=None):
        """If expr has an expr_lets name -> emit let once and return the name."""
        c = canon(expr)
        if c in self.let_exprs:
            return self.let_exprs[c]
        names = self.expr_let_table.get(c)
        if names:
            nm = names.pop(0) if isinstance(names, list) else names
            self.pending.append({"let": nm, "expr": expr, **({"src": src} if src else {})})
            self.let_exprs[c] = nm
            return nm
        return None

    def maybe_name(self, expr, src=None):
        """Return let-name for expr when expr_lets says so (emitting the let); else expr."""
        n = self.bind_or_let(expr, src=src)
        return n if n is not None else expr

    def rewrite_lets(self, e):
        """Substitute subexprs equal to bound lets by their names (recursively, innermost)."""
        if not isinstance(e, list) or not e:
            return e
        c = canon(e)
        if c in self.let_exprs:
            return self.let_exprs[c]
        return [self.rewrite_lets(x) for x in e]

    # ------------------------------------------------------------- storage
    def fam(self, name):
        return self.spec["storage"].get(name)

    def lci_expr(self):
        return ["call", "lci", "lfi", "win"]

    def entry_read(self, family, k, field=None):
        if family.get("accessor"):
            return ["call", family["accessor"], "lfi", "win", family["shadow"], k]
        w = ["call", "w", "lfi", "win", k]
        return w if field is None else ["get", w, field]

    def ghost_read(self, family, k):
        return ["call", family["ghost_accessor"], "lfi", "win", family["ghost_shadow"], k]

    # ----------------------------------------------------------- expressions
    def X(self, n):
        """Translate an AST expression -> DSL expr (or Carrier / hash token)."""
        if n is None:
            return None
        t = n.get("nodeType")
        if t == "Literal":
            v = n.get("value")
            if n.get("kind") == "number":
                try:
                    return int(v)
                except (TypeError, ValueError):
                    try:
                        return int(v, 16)
                    except Exception:
                        return v
            if n.get("kind") == "bool":
                return v in ("true", "True", True)
            if n.get("kind") == "hexString" and (v or "").startswith("0x"):
                return int(v, 16) if len(v) <= 20 else v
            return v
        if t == "Identifier":
            return self.x_id(n)
        if t == "MemberAccess":
            return self.x_member(n)
        if t == "IndexAccess":
            return self.x_index(n)
        if t == "BinaryOperation":
            return self.x_binop(n)
        if t == "UnaryOperation":
            op = n["operator"]
            sub = self.X(n["subExpression"])
            if op == "!":
                return simplify(NOT(sub))
            if op == "-":
                return ["-", 0, sub]
            return sub
        if t == "Conditional":
            return simplify(["?", self.X(n["condition"]), self.X(n["trueExpression"]), self.X(n["falseExpression"])])
        if t == "FunctionCall":
            return self.x_call(n)
        if t == "TupleExpression":
            return self.X(n["components"][0]) if len(n["components"]) == 1 else None
        if t == "NewExpression":
            return self.X(n["arguments"][0]) if n.get("arguments") else None
        if t == "ElementaryTypeNameExpression":
            return None
        if t == "IndexRangeAccess":
            return self.X(n["baseExpression"])
        self.add_debt(f"{self.src(n)} expr {t}", "untranslated_expr", f"expr node {t} not translated")
        return ("debt", t)

    def x_id(self, n):
        name = n["name"]
        if name in self.env:
            v = self.env[name]
            if isinstance(v, tuple) and v[0] == "unbound":
                return name
            return v
        if name in self.input_map:
            v = self.input_map[name]
            if isinstance(v, dict):
                return v.get("_tok", name)
            return v
        f = self.fam(name)
        if f:
            k = f["kind"]
            if k == "scalar":
                return f["field"]
            if k == "const":
                return f["value"]
            if k == "derived_lci":
                return self.maybe_name(self.lci_expr())
            if k == "oracle_addr":
                return ("addr", name)
            if k == "immutable":
                return ("imm", name)
            if k == "unmodelled":
                self.add_debt(f"{self.src(n)} storage {name}", "unmodelled_read", f["why"])
                return ("unmodelled", name)
            if k in ("batch_map", "abs_map", "role_set", "queue", "commitment"):
                return ("map", name)
        if name in self.def_calls:
            return ("fncall", name)
        return name

    def x_member(self, n):
        base = self.X(n["expression"])
        mem = n["memberName"]
        if isinstance(base, tuple) and base[0] == "map":
            f = self.fam(base[1])
            if f["kind"] == "queue" and mem == "length":
                return f["field"]
            self.add_debt(f"{self.src(n)} member {base[1]}.{mem}", "unmodelled_member", f"{base[1]}.{mem}")
            return ("unmodelled", f"{base[1]}.{mem}")
        if isinstance(base, tuple) and base[0] == "abs_rec":
            _, f, k = base
            ctor = self.spec["struct_ctors"].get(f["record"]) or next(
                (v for v in self.spec["struct_ctors"].values() if v.get("record") == f["record"]), None)
            m = (ctor or {}).get("member_fields", {}).get(mem)
            if m is None:
                self.add_debt(f"{self.src(n)} member {f['record']}.{mem}", "unmodelled_member", mem)
                return ("unmodelled", mem)
            return ["get", ["call", "nth_ch", f["field"], k], m]
        if isinstance(base, tuple) and base[0] == "shadow":
            _, nm, f, k, fields = base
            ctor = self.spec["struct_ctors"].get(f["record"])
            m = (ctor or {}).get("member_fields", {}).get(mem)
            if m is None:
                self.add_debt(f"{self.src(n)} member {f['record']}.{mem}", "unmodelled_member", mem)
                return ("unmodelled", mem)
            if mem in fields or m in fields:
                return fields.get(m, fields.get(mem))
            return ["get", nm, m]
        if isinstance(base, tuple) and base[0] == "addr":
            return ("contract", base[1], mem)
        if isinstance(base, tuple) and base[0] == "contract":
            return ("lib", f"{base[1]}.{mem}")
        if base == ("imm", "msg") or n["expression"].get("nodeType") == "Identifier" and n["expression"].get("name") == "msg":
            return self.env_of(f"msg.{mem}", n)
        if isinstance(base, Carrier):
            return ("carrier_member", base, mem)
        key = None
        if n["expression"].get("nodeType") == "Identifier":
            key = f'{n["expression"]["name"]}.{mem}'
            if key in self.input_map:
                return self.input_map[key]
        if isinstance(base, tuple) and base[0] == "unbound":
            return base[1]
        if isinstance(base, tuple) and base[0] == "unmodelled":
            return base
        if isinstance(base, str):
            ek = f"{base}.{mem}"
            if ek in self.spec.get("env", {}):
                return self.spec["env"][ek]
        if mem in ("length",) and isinstance(base, str):
            return base
        if isinstance(base, tuple) and base[0] == "batch_entry":
            f = base[-1]
            m = (f.get("fields") or {}).get(mem) if isinstance(f, dict) else None
            if m or (isinstance(f, dict) and f.get("entry_field")):
                return ["get", self._lower(base), m or mem]
            self.add_debt(f"{self.src(n)} member {base[1]}.{mem}", "unmodelled_member", mem)
            return ("unmodelled", mem)
        return base if isinstance(base, (str, int, bool, list)) else ("member", base, mem)

    def env_of(self, key, n):
        m = self.spec["env"]
        if key in m:
            return m[key]
        return key

    def x_index(self, n):
        base = n["baseExpression"]
        k = self.X(n["indexExpression"])
        name = base.get("name") if base.get("nodeType") == "Identifier" else None
        f = self.fam(name) if name else None
        if not f:
            inner = self.X(base)
            if isinstance(inner, tuple) and inner[0] == "map":
                f = self.fam(inner[1])
                name = inner[1]
            else:
                self.add_debt(f"{self.src(n)} index {name or '?'}", "unmodelled_index", "index read of unmapped storage")
                return ("unmodelled", "idx")
        k = self.rewrite_lets(k)
        kind = f["kind"]
        if kind == "batch_map":
            if name == "committedStateRoots" and k == self._last_bound(self.lci_expr()):
                return ("entry_field", name, "csr", k)
            return ("batch_entry", name, k, f)
        if kind == "abs_map":
            if f.get("record"):
                return ("abs_rec", f, k)
            return ["call", "nth", f["field"], k]
        if kind == "role_set":
            return ["call", "mem", k, f["field"]]
        if kind == "commitment":
            return ("commit", k)
        if kind == "queue":
            return ("queue_entry", k)
        if kind == "unmodelled":
            self.add_debt(f"{self.src(n)} storage {name}", "unmodelled_read", f["why"])
            return ("unmodelled", name)
        if kind == "oracle_addr":
            return ("addr", name)
        return ("map", name)

    def _last_bound(self, e):
        c = canon(e)
        return self.let_exprs.get(c, e)

    def x_binop(self, n):
        op = n["operator"]
        a = self.X(n["leftExpression"])
        b = self.X(n["rightExpression"])
        # commitment-map comparisons
        if isinstance(a, tuple) and a[0] == "commit" or isinstance(b, tuple) and b[0] == "commit":
            tok = a if isinstance(a, tuple) and a[0] == "commit" else b
            other = b if tok is a else a
            return ("commit_cmp", op, tok[1], other)
        if isinstance(a, tuple) and a[0] == "batch_entry" and isinstance(b, tuple) and b[0] == "hash":
            return ("honesty", n)
        if isinstance(b, tuple) and b[0] == "batch_entry" and isinstance(a, tuple) and a[0] == "hash":
            return ("honesty", n)
        a = self._lower(a)
        b = self._lower(b)
        if isinstance(a, tuple) and a[0] in ("unmodelled", "debt", "map") or isinstance(b, tuple) and b[0] in ("unmodelled", "debt", "map"):
            return ("unmodelled", "cmp")
        d = BINOP.get(op)
        if d is None:
            self.add_debt(f"{self.src(n)} binop {op}", "untranslated_expr", f"binary op {op}")
            return ("debt", op)
        if d == "-" and not self.in_unchecked:
            self.panic_guard(a, b, n)
        return [d, self.rewrite_lets(a) if isinstance(a, list) else a, self.rewrite_lets(b) if isinstance(b, list) else b]

    def panic_guard(self, a, b, node):
        if b == 0:
            return
        e = normalize(["<=", self.rewrite_lets(b) if isinstance(b, list) else b, self.rewrite_lets(a) if isinstance(a, list) else a])
        if e in self.established:
            return
        site = None
        note = None
        for s in self.spec.get("sites", []):
            if canon(s["expr"]) == canon(["-", a, b]):
                site = s["site"]
                note = s.get("note")
        self.emit_require(["<=", self.rewrite_lets(b) if isinstance(b, list) else b, self.rewrite_lets(a) if isinstance(a, list) else a], "panic:0x11", self.src(node), note=note, site=site)

    # -------------------------------------------------------------- calls
    def x_call(self, n):
        ex = n["expression"]
        # require/assert
        if ex.get("nodeType") == "Identifier" and ex.get("name") in ("require", "assert"):
            cond = self.X(n["arguments"][0])
            msg = n["arguments"][1].get("value") if len(n["arguments"]) > 1 else None
            return ("require", cond, msg, n)
        # type conversions
        if ex.get("nodeType") == "ElementaryTypeNameExpression":
            tname = ex.get("typeDescriptions", {}).get("typeString", "")
            cname = _contract_name(tname)
            if cname:
                arg = self.X(n["arguments"][0])
                if isinstance(arg, tuple) and arg[0] in ("addr", "map"):
                    return ("addr", arg[1], cname)
                return ("addr", n["arguments"][0].get("name") or str(arg), cname)
            arg = self.X(n["arguments"][0])
            if arg == 0:
                return 0
            return arg
        # X(...).method(...)
        if ex.get("nodeType") == "MemberAccess":
            mem = ex["memberName"]
            inner = ex["expression"]
            if inner.get("nodeType") == "FunctionCall" and inner["expression"].get("typeDescriptions", {}).get("typeString", "").startswith(("type(contract", "contract ")):
                tname = inner["expression"].get("typeDescriptions", {}).get("typeString", "")
                cname = _contract_name(tname) or inner["expression"].get("name")
                key = f"{cname}.{mem}" if cname else None
                return self.call_contract(key, cname, None, n["arguments"], n)
            if inner.get("nodeType") == "Identifier":
                lib = self.spec.get("contract_ifaces", {}).get(inner["name"], inner["name"])
                return self.call_named(f"{lib}.{mem}", n["arguments"], n)
            obj = self.X(inner)
            if isinstance(obj, tuple) and obj[0] == "contract":
                cname = self.spec.get("contract_ifaces", {}).get(obj[1], obj[1])
                return self.call_contract(f"{cname}.{mem}", cname, None, n["arguments"], n)
            if isinstance(obj, tuple) and obj[0] == "map":
                f = self.fam(obj[1])
                if f and f["kind"] == "queue" and mem == "push":
                    self.writes.append(("state", "qlen", list(self.conds), ["+", "qlen", 1]))
                    return ("void", "push")
            return ("method", obj, mem, n["arguments"])
        if ex.get("nodeType") == "Identifier":
            name = ex["name"]
            tcname = _contract_name(ex.get("typeDescriptions", {}).get("typeString", ""))
            if tcname and name == tcname.split(".")[-1]:
                # ISubmitter(x): contract cast, not a function call
                arg = self.X(n["arguments"][0]) if n.get("arguments") else None
                if isinstance(arg, tuple) and arg[0] in ("addr", "map"):
                    return ("addr", arg[1], tcname)
                return ("addr", n["arguments"][0].get("name") or str(arg), tcname)
            if name == "blobhash":
                i = self.X(n["arguments"][0])
                return self.blob(i, n)
            if name == "keccak256":
                return self.keccak(n)
            if name in ("blockhash", "gasleft", "abi"):
                return ("unmodelled", name)
            if name == "revert":
                return ("revert", n["arguments"][0].get("name") if n["arguments"] else "?", n)
            return self.call_internal(name, n["arguments"], n)
        if ex.get("nodeType") == "IndexAccess":
            return ("method", self.X(ex), None, n["arguments"])
        return ("call", "unknown", n)

    def blob(self, i, n):
        if not self.blob_lets_done:
            self.blob_lets_done = True
            for j in self.blob_indices:
                self.pending.append({"let": f"b{j}", "expr": ["call", "nth", "blobs", j]})
        return ["call", "nth", "blobs", i] if isinstance(i, int) else ["call", "nth", "blobs", i]

    def keccak(self, n):
        # inside _computeBlobVersionedHash the asm collects blob hashes -> agg(blobs)
        if self.cur_fn and self.cur_fn[1] == "_computeBlobVersionedHash":
            return ["call", "agg", "blobs"]
        if self.cur_fn and self.cur_fn[1] == "_verifyProof":
            return ("unmodelled", "public input hash")
        self.add_debt(f"{self.src(n)} keccak256", "unmodelled_value", "hash contents")
        return ("unmodelled", "keccak256")

    def call_named(self, key, args, node):
        """Library or free-function calls: Codec.getX, Codec.storeX, AddressAliasHelper, handlers."""
        cf = self.spec.get("codec_fields", {})
        if key in cf or key.split(".")[-1] in cf:
            field = cf.get(key, cf.get(key.split(".")[-1]))
            ptr = self.X(args[0])
            if key.split(".")[-1].startswith("get"):
                if not isinstance(ptr, Carrier):
                    member = "batchIndex" if field == "INDEX" else field
                    if args and args[0].get("nodeType") == "Identifier":
                        mk = self.input_map.get(f"{args[0]['name']}.{member}")
                        if mk is not None:
                            return mk
                    self.add_debt(f"{self.src(node)} {key}", "unmodelled_value", "codec read of non-carrier")
                    return ("unmodelled", key)
                if field == "INDEX":
                    return ptr.idx
                if field is None:
                    self.add_debt(f"{self.src(node)} {key}", "unmodelled_value", f"header field {key} not modelled")
                    return ("unmodelled", key)
                return ["get", ["call", "w", "lfi", "win", ptr.idx], field]
            # storeX(ptr, value): writes into the entry under construction
            if len(args) < 2:
                self.add_debt(f"{self.src(node)} {key}", "unmodelled_value", "codec store without value arg")
                return ("store_drop", key)
            v = self._lower(self.X(args[1]))
            if field is None:
                return ("store_drop", key)
            return ("store", field, v)
        h = self.spec["handlers"].get(key.split(".")[-1]) or self.spec["handlers"].get(key)
        if h:
            return self.run_handler(h["handler"], args, node, key)
        oc = self.spec["oracles"].get(key)
        if oc:
            return self.call_oracle(key, oc, args, node)
        if key == "AddressAliasHelper.applyL1ToL2Alias":
            return self.X(args[0])
        self.add_debt(f"{self.src(node)} call {key}", "unmodelled_call", f"call {key} not translated")
        return ("unmodelled", key)

    def call_contract(self, key, cname, addr, args, node):
        oc = self.spec["oracles"].get(key) if key else None
        if oc:
            if "inline" in oc:
                return self.inline_fn(tuple(oc["inline"]), args, node)
            if "emit" in oc:
                return self.subst_args(oc["emit"], args)
            if "guard" in oc:
                g = oc["guard"]
                self.emit_require(g["require"], g["reason"], g.get("src", self.src(node)))
                return ("guard", key)
            if "effects" in oc or "returns_unmodelled" in oc:
                for ef in oc.get("effects", []):
                    self.writes.append(("state", ef["field"], list(self.conds), self.subst_args(ef["expr"], args)))
                if oc.get("note"):
                    self.add_debt(f"{self.src(node)} {key}", "unmodelled_value", oc["note"])
                return ("unmodelled", oc.get("returns_unmodelled", key))
            if "debt" in oc:
                self.add_debt(f"{self.src(node)} {key}", "unmodelled_call", oc["debt"])
                return ("unmodelled", key)
        fn = self.find_fn(cname, node["expression"]["expression"]["memberName"]) if cname else None
        if fn is not None:
            return self.inline_fn((cname, node["expression"]["expression"]["memberName"]), args, node)
        self.add_debt(f"{self.src(node)} call {key}", "unmodelled_call", f"contract call {key} not translated")
        return ("unmodelled", key)

    def subst_args(self, e, args):
        """Replace @a0..@aN placeholders with arg exprs."""
        if isinstance(e, str) and e.startswith("@a"):
            return self.X(args[int(e[2:])])
        if isinstance(e, list):
            return [self.subst_args(x, args) for x in e]
        return e

    def call_oracle(self, key, oc, args, node):
        return self.subst_args(oc.get("emit"), args)

    # ------------------------------------------------------- internal calls
    def find_fn(self, contract, name):
        for path, c in self.spec["contracts"].items():
            if cname_eq(c.get("name"), contract) or contract is None:
                u = self.world.units.get(path)
                if u is None:
                    continue
                for n in u.find("FunctionDefinition", name=name):
                    if n.get("kind") != "modifier":
                        return n
        return None

    def call_internal(self, name, args, node):
        if name + "()" in self.spec.get("env", {}):
            return self.spec["env"][name + "()"]
        ctor = self.spec.get("struct_ctors", {}).get(name)
        if ctor:
            vals = [self.X(a) for i, a in enumerate(args) if i not in ctor.get("skip_args", [])]
            if "record" in ctor:
                return ["mk", ctor["record"], dict(zip(ctor["fields"], vals))]
            # tuple-record ctor feeding the window entry (e.g. BatchData)
            return ("ctor_fields", ctor.get("entry_fields", []), vals)
        if name == "_loadBatchHeader":
            arg = args[0]
            kind = "parent"
            if isinstance(arg, dict) and arg.get("nodeType") == "Identifier":
                tok = self.input_map.get(arg["name"])
                if isinstance(tok, tuple) and tok[0] == "carrier_tok":
                    kind = tok[1]
            elif isinstance(arg, dict) and arg.get("nodeType") == "MemberAccess":
                tok = self.input_map.get(f'{arg["expression"].get("name")}.{arg["memberName"]}')
                if isinstance(tok, tuple) and tok[0] == "carrier_tok":
                    kind = tok[1]
            idx = self.spec.get("carrier_idx", {}).get(kind, kind)
            c = Carrier(kind, idx)
            return ("returns", [c, c.hash])
        h = self.spec["handlers"].get(name)
        if h:
            return self.run_handler(h["handler"], args, node, name)
        dk = (self.cur_fn[0] if self.cur_fn else None, name)
        for dname, d in self.spec["defs_from"].items():
            if d["fn"][1] == name:
                return self.def_call(dname, d, args, node)
        if name in self.spec.get("abstracted_fns", []):
            self.add_debt(f"{self.src(node)} call {name}", "abstracted_call", f"{name} handled by declared abstraction")
            return ("unmodelled", name)
        fn = self.find_fn(self.cur_fn[0] if self.cur_fn else None, name) or self.find_fn(None, name)
        if fn is None:
            self.add_debt(f"{self.src(node)} call {name}", "unmodelled_call", f"{name} not in scope contracts")
            return ("unmodelled", name)
        return self.inline_fn((self.cur_fn[0] if self.cur_fn else None, name), args, node, fn)

    def def_call(self, dname, d, args, node):
        """A defs_from function call at a use site: emit its collected guards, return call expr."""
        gkey = (d["fn"][0], d["fn"][1])
        info = self.call_guards.get(gkey, {})
        plist = info.get("params", [])
        resolved = [self.X(a) for a in args]
        amap = d.get("arg_map", {})
        for g in info.get("guards", []):
            e = g["expr"]
            for p, i in amap.items():
                if i < len(resolved) and resolved[i] is not None:
                    e = _subst_name(e, p, resolved[i])
            self.emit_require(self.rewrite_lets(e), g["reason"], g["src"], note=g.get("note"), site=g.get("site"))
        call_args = []
        for p, _t in d["params"]:
            i = amap.get(p)
            if i is not None and i < len(resolved) and resolved[i] is not None:
                call_args.append(resolved[i])
            else:
                call_args.append(p)
        return self.maybe_name(["call", dname, *call_args])

    def inline_fn(self, fkey, args, node, fn=None):
        fn = fn or self.find_fn(fkey[0], fkey[1])
        if fn is None:
            self.add_debt(f"{self.src(node)} call {fkey[1]}", "unmodelled_call", f"{fkey[1]} not found")
            return ("unmodelled", fkey[1])
        saved_env = self.env
        saved_ret = self.ret
        saved_cur = self.cur_fn
        self.ret = []
        self.cur_fn = fkey
        params = fn.get("parameters", {}).get("parameters", [])
        newenv = dict(saved_env)
        for i, p in enumerate(params):
            if i < len(args):
                newenv[p["name"]] = self.X(args[i])
        self.env = newenv
        self.run_modifiers(fn)
        for st in fn.get("body", {}).get("statements", []):
            self.S(st)
        rets = self.ret
        self.env = saved_env
        self.ret = saved_ret
        self.cur_fn = saved_cur
        if len(rets) == 1 and rets[0][0] == []:
            return rets[0][1]
        if len(rets) > 1:
            e = rets[-1][1]
            for conds, val in reversed(rets[:-1]):
                e = simplify(["?", AND(*conds), val, e])
            return e
        return ("void", fkey[1])

    def run_modifiers(self, fn):
        for mi in fn.get("modifiers", []):
            ref = mi.get("modifierName", {})
            name = ref.get("name") or mi.get("kind", "")
            if name in self.spec.get("modifiers_abstracted", []):
                continue
            mdef = None
            rid = ref.get("referencedDeclaration")
            for path in self.world.units:
                u = self.world.units[path]
                if rid in u.nodes:
                    mdef = u.nodes[rid]
                    break
            if mdef is None:
                for path, c in self.spec["contracts"].items():
                    u = self.world.units.get(path)
                    if u is not None:
                        for m in u.find("ModifierDefinition", name=name):
                            mdef = m
            if mdef is None:
                continue
            for st in mdef.get("body", {}).get("statements", []):
                self.S(st)

    # ------------------------------------------------------------ handlers
    def run_handler(self, h, args, node, key):
        if h == "queue_read_range":
            a = self.X(args[-1])           # _totalL1MessagesPoppedOverall
            b = self.X(args[-2])           # _numL1Messages
            self.emit_require(["<=", ["+", a, b], "qlen"], "message index out of range",
                              "contracts/contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol:108",
                              note="_loadL1MessageHashes -> getCrossDomainMessage(i) requires i < messageQueue.length")
            return ("unmodelled", "queue_read_range")
        if h == "pop_messages":
            btot = self.maybe_name(self.X(args[0]))
            bn = self.maybe_name(self.X(args[1]))
            hh = self.spec["handlers"]["_popL1Messages"]
            self.emit_require(OR(["==", bn, 0], ["==", "qpend", ["-", btot, bn]]),
                              "start index mismatch", hh["require_src"], note=hh.get("note"))
            self.writes.append(("state", "qpend", list(self.conds), simplify(["?", ["==", bn, 0], "qpend", btot])))
            return ("void", "pop_messages")
        if h == "asm_scan":
            return ("unmodelled", "asm")
        if h == "agg_or_drop":
            return self.keccak(node)
        if h == "unmodelled_value":
            self.add_debt(f"{self.src(node)} {key}", "unmodelled_value", key)
            return ("unmodelled", key)
        if h == "inline_through":
            fn = self.find_fn(self.cur_fn[0] if self.cur_fn else None, key.split(".")[-1]) or self.find_fn(None, key.split(".")[-1])
            if fn:
                return self.inline_fn((self.cur_fn[0] if self.cur_fn else "", key.split(".")[-1]), args, node, fn)
            return ("unmodelled", key)
        self.add_debt(f"{self.src(node)} handler {h}", "unhandled", f"handler {h} not implemented")
        return ("unmodelled", h)

    # ------------------------------------------------------------ statements
    def S(self, st):
        t = st.get("nodeType")
        if t in ("Block", "UncheckedBlock"):
            old = self.in_unchecked
            if t == "UncheckedBlock":
                self.in_unchecked = True
            for s in st.get("statements", []):
                self.S(s)
            self.in_unchecked = old
            return
        if t == "VariableDeclarationStatement":
            return self.s_decl(st)
        if t == "ExpressionStatement":
            return self.S(st["expression"])
        if t == "IfStatement":
            return self.s_if(st)
        if t == "ForStatement":
            return self.s_loop(st, "for")
        if t == "WhileStatement":
            return self.s_loop(st, "while")
        if t == "DoWhileStatement":
            return self.s_loop(st, "dowhile")
        if t == "Return":
            v = self.X(st["expression"]) if st.get("expression") else ("void",)
            self.ret.append((list(self.conds), v))
            return
        if t == "EmitStatement":
            return
        if t == "Break" or t == "Continue":
            self.add_debt(f"{self.src(st)} {t.lower()}", "loop_flow", f"{t} inside loop")
            return
        if t == "InlineAssembly":
            return self.s_asm(st)
        if t == "RevertStatement":
            self.add_debt(f"{self.src(st)} revert", "revert", "custom error revert")
            return
        if t == "VariableDeclarationStatement":
            return self.s_decl(st)
        if t == "Assignment":
            return self.s_assign(st)
        if t == "FunctionCall":
            return self.s_callstmt(st)
        if t == "UnaryOperation":
            return self.s_unary(st)
        if t == "PlaceholderStatement":
            return
        self.add_debt(f"{self.src(st)} stmt {t}", "untranslated_stmt", f"statement {t} not translated")

    def s_asm(self, st):
        if self.cur_fn and self.cur_fn[1] == "_computeBlobVersionedHash":
            self.add_debt(f"{self.src(st)} assembly", "abstracted_asm", "blobhash-collection loop -> blob_count/agg")
            self.env["_blobCount"] = ["call", "blob_count", "blobs"]
            self.env["_blobVersionedHash"] = ["call", "agg", "blobs"]
            return
        yul = (st.get("AST") or {}).get("statements")
        if yul is None:
            self.add_debt(f"{self.src(st)} assembly", "abstracted_asm", "inline assembly not translated")
            return
        ok = True
        for ys in yul:
            yt = ys.get("nodeType")
            if yt == "YulAssignment" and len(ys.get("variableNames", [])) == 1:
                tgt = ys["variableNames"][0]["name"]
                v = self.X_yul(ys["value"])
                if v is None:
                    ok = False
                    continue
                if isinstance(v, list):
                    v = self.rewrite_lets(v)
                self.env[tgt] = v
            elif yt == "YulExpressionStatement" and ys.get("expression", {}).get("functionName", {}).get("name") == "mstore" and ys["expression"]["arguments"][0].get("value") == "0x40":
                # free-memory pointer bump after an allocation
                continue
            else:
                ok = False
        if not ok:
            self.add_debt(f"{self.src(st)} assembly", "abstracted_asm", "asm statements outside the translated subset")

    def _lower(self, e):
        if isinstance(e, tuple) and e[0] in ("batch_entry", "entry_field"):
            f = e[-1]
            k = e[3] if e[0] == "entry_field" else e[2]
            if isinstance(f, dict) and f.get("accessor"):
                return ["call", f["accessor"], "lfi", "win", f["shadow"], k]
            field = e[2] if e[0] == "entry_field" else (f.get("entry_field") if isinstance(f, dict) else e[2])
            return ["get", ["call", "w", "lfi", "win", k], field]
        return e

    def X_yul(self, y):
        t = y.get("nodeType")
        if t == "YulIdentifier":
            return self.env.get(y["name"], y["name"])
        if t == "YulLiteral":
            v = y.get("value", "0")
            try:
                return int(v, 0)
            except ValueError:
                try:
                    return int(v, 16)
                except ValueError:
                    return None
        if t == "YulFunctionCall":
            fname = y["functionName"]["name"]
            op = {"add": "+", "sub": "-", "mul": "*", "div": "/"}.get(fname)
            if op is None:
                if fname == "mload" and y["arguments"][0].get("value") == "0x40" and self.new_idx is not None:
                    if self.new_entry is None:
                        self.new_entry = {}
                    return Carrier("self", self.new_idx)
                return None
            a = self.X_yul(y["arguments"][0])
            b = self.X_yul(y["arguments"][1])
            if a is None or b is None:
                return None
            return [op, a, b]
        return None

    def s_if(self, st):
        c = self.X(st["condition"])
        c = self.rewrite_lets(c) if isinstance(c, list) else c
        # if (c) { ... return X }  /  if (c) { stmt } else { stmt }
        tstmt = st.get("trueBody", {})
        fstmt = st.get("falseBody")
        tret = self._branch_returns(tstmt)
        if self._is_single_return(tstmt) and fstmt is None:
            # if (c) return v; -> record a guarded return; subsequent code runs under !c
            retst = tstmt["statements"][0]
            v = self.X(retst["expression"]) if retst.get("expression") else ("void",)
            self.ret.append(([c], v))
            self.conds.append(simplify(NOT(c)))
            return
        saved = list(self.conds)
        saved_env = dict(self.env)
        self.conds = saved + [c]
        self.in_branch = getattr(self, "in_branch", 0) + 1
        for s in tstmt.get("statements", []):
            self.S(s)
        self.in_branch -= 1
        self.conds = saved
        then_env = dict(self.env)
        if fstmt is not None:
            self.env = dict(saved_env)
            self.conds = saved + [simplify(NOT(c))]
            self.in_branch += 1
            for s in fstmt.get("statements", []):
                self.S(s)
            self.in_branch -= 1
            self.conds = saved
        else_env = self.env
        # join: local names bound differently across branches become a ?-merge;
        # a branch established by an already-emitted require collapses to its value
        merged = dict(else_env)
        keys = set(then_env) | set(else_env)
        est = {canon(x) for x in self.established}
        for k in sorted(keys):
            vt = then_env.get(k, saved_env.get(k, ("unbound", k)))
            ve = else_env.get(k, saved_env.get(k, ("unbound", k)))
            if vt == ve:
                merged[k] = vt
                continue
            if canon(NOT(c)) in est:
                merged[k] = self._lower(ve)
            elif canon(c) in est:
                merged[k] = self._lower(vt)
            else:
                merged[k] = ["?", c, self._lower(vt), self._lower(ve)]
            nm = self.local_names.get(k)
            if nm and isinstance(merged[k], list) and canon(merged[k]) not in self.let_exprs:
                self.emit_let(nm, merged[k], src=self.src_span(tstmt))
                merged[k] = nm
        self.env = merged

    def _is_single_return(self, body):
        ss = body.get("statements", [])
        return len(ss) == 1 and ss[0].get("nodeType") == "Return"

    def _branch_returns(self, body):
        return self._is_single_return(body)

    def s_loop(self, st, kind):
        fn = self.cur_fn[1] if self.cur_fn else ""
        # revertBatch while loop -> composite revert collapse
        if kind == "while" and fn == "revertBatch":
            return self.h_revert_loop(st)
        # challengeState for-loop -> bump_f
        if kind == "for" and fn == "challengeState":
            return self.h_bump_loop(st)
        # _loadL1MessageHashes for-loop inside unchecked (reached via inline_through)
        if fn == "_loadL1MessageHashes":
            return  # handled by queue_read_range at the call site
        self.add_debt(f"{self.src(st)} {kind}-loop", "untranslated_loop", f"{kind} loop in {fn} not translated")

    def h_revert_loop(self, st):
        p = self.maybe_name(["-", "idx", "lfi"])
        moved = self.maybe_name(["call", "drop", "win", "p"])
        self._drain_pending()
        self.writes.append(("state", "win", [], ["call", "take", "win", p]))
        for s in ("s_csr", "s_bd", "s_bvh", "s_tag"):
            self.writes.append(("state", s, [], ["call", "concat", ["call", f"es_{s[2:]}", moved], s]))
        self.writes.append(("state", "inch", [], simplify(["&&", "inch", ["!", ["call", "any_open", "chs", "idx", "lci"]]])))
        self.writes.append(("state", "chs", [], ["call", "clear_chs", "chs", "idx", "lci"]))
        self.writes.append(("state", "rri", [], simplify(["?", ["&&", [">", "rri", 0], [">=", "rri", "idx"], ["<=", "rri", "lci"]], 0, "rri"])))
        self.add_debt(f"{self.src(st)} revert loop refunds", "unmodelled_write",
                      "batchChallengeReward += challengeDeposit inside the loop is reward accounting")

    def h_bump_loop(self, st):
        self.writes.append(("state", "win", [], ["call", "bump_f", "win", ["-", "idx", "lfi"], "W"]))

    def s_decl(self, st):
        decls = st.get("declarations", [])
        init = st.get("initialValue")
        if len(decls) > 1 or (decls and decls[0] is None):
            # tuple assignment: (a, b) = f(...) — initialValue is a TupleExpression wrapper
            if init is not None and init.get("nodeType") == "TupleExpression":
                init = init["components"][0]
            v = self.X(init)
            names = [d["name"] for d in decls if d]
            if isinstance(v, tuple) and v and v[0] == "returns":
                for nm, val in zip(names, v[1]):
                    self.env[nm] = val
            else:
                for nm in names:
                    self.env[nm] = v
            return
        d = decls[0]
        name = d["name"]
        if init is None:
            self.env[name] = ("unbound", name)
            return
        v = self._lower(self.X(init))
        if isinstance(v, tuple) and v[0] == "abs_rec":
            # local record shadow: `Ch memory ch = challenges[k]`
            _, f, k = v
            nm = self.local_names.get(name, name)
            self.pending.append({"let": nm, "expr": ["call", "nth_ch", f["field"], k], "src": self.src(st)})
            self.let_exprs[canon(["call", "nth_ch", f["field"], k])] = nm
            self.env[name] = ("shadow", nm, f, k, {})
            self._drain_pending()
            return
        if isinstance(v, tuple):
            self.env[name] = v
            return
        atomic = isinstance(v, (int, bool, str)) and (not isinstance(v, str) or v in self.input_names or True)
        nm = self.local_names.get(name)
        if nm and isinstance(v, list):
            self.pending.append({"let": nm, "expr": v, "src": self.src(st)})
            self.let_exprs[canon(v)] = nm
            self.env[name] = nm
            self._drain_pending()
        elif isinstance(v, list) and self._heavy(v):
            nm = nm or f"v{name}"
            self.pending.append({"let": nm, "expr": v, "src": self.src(st)})
            self.let_exprs[canon(v)] = nm
            self.env[name] = nm
            self._drain_pending()
        else:
            self.env[name] = v
        if nm == "bvh":
            self.emit_ghost()

    def _heavy(self, e):
        return isinstance(e, list)

    def emit_ghost(self):
        g = self.action_spec.get("ghost_tag")
        if g:
            self.emit_let(g["name"], g["expr"])

    def s_assign(self, st):
        op = st["operator"]
        lhs = st["leftHandSide"]
        rhs = st["rightHandSide"]
        v = self._lower(self.X(rhs))
        # local var writes
        if lhs.get("nodeType") == "Identifier" and lhs["name"] in self.env:
            name = lhs["name"]
            if op == "=":
                nv = v
            else:
                nv = [op[0], self.env[name], v]
            if not getattr(self, "in_branch", 0) and self.conds:
                nv = simplify(["?", AND(*self.conds), nv, self.env[name]])
            nv = simplify(nv)
            self.env[name] = nv
            if getattr(self, "in_branch", 0):
                return
            nm = self.local_names.get(name)
            if nm and canon(nv) != canon(name) and isinstance(nv, list) and canon(nv) not in self.let_exprs:
                self.emit_let(nm, nv, src=self.src_span(st))
                self.env[name] = nm
                if nm == "bvh":
                    self.emit_ghost()
            return
        self.write_target(lhs, op, v, st)

    def write_target(self, lhs, op, v, st):
        t = lhs.get("nodeType")
        conds = list(self.conds)
        if t == "Identifier":
            name = lhs["name"]
            f = self.fam(name)
            if f is None:
                self.add_debt(f"{self.src(st)} write {name}", "unmodelled_write", f"{name} not mapped")
                return
            self.write_storage(name, None, f, op, v, st, conds)
            return
        if t == "IndexAccess":
            base = lhs["baseExpression"]
            name = base.get("name")
            k = self.rewrite_lets(self.X(lhs["indexExpression"]))
            f = self.fam(name)
            if f is None:
                self.add_debt(f"{self.src(st)} write {name}", "unmodelled_write", f"{name} not mapped")
                return
            self.write_storage(name, k, f, op, v, st, conds)
            return
        if t == "MemberAccess":
            inner = lhs["expression"]
            if inner.get("nodeType") == "Identifier" and isinstance(self.env.get(inner["name"]), tuple) and self.env[inner["name"]][0] == "shadow":
                sh = self.env[inner["name"]]
                _, nm, f, k, fields = sh
                ctor = self.spec["struct_ctors"].get(f["record"])
                m = (ctor or {}).get("member_fields", {}).get(lhs["memberName"])
                if m is None:
                    self.add_debt(f"{self.src(st)} write {inner['name']}.{lhs['memberName']}", "unmodelled_write", lhs["memberName"])
                    return
                nv = v if op == "=" else [op[0], ["get", nm, m], v]
                if conds:
                    nv = simplify(["?", AND(*conds), nv, ["get", nm, m]])
                fields[m] = nv
                return
            if inner.get("nodeType") == "IndexAccess":
                base = inner["baseExpression"]
                name = base.get("name")
                k = self.rewrite_lets(self.X(inner["indexExpression"]))
                f = self.fam(name)
                mem = lhs["memberName"]
                if f is None:
                    self.add_debt(f"{self.src(st)} write {name}.{mem}", "unmodelled_write", name)
                    return
                if f["kind"] == "batch_map" and mem in f.get("fields", {}):
                    ef = f["fields"][mem]
                    nv = v if op == "=" else [op[0], v]
                    self.entry_write(name, k, ef, nv, conds)
                    return
                if f["kind"] == "abs_map" and f.get("record"):
                    ctor = self.spec["struct_ctors"].get(f["record"])
                    m = (ctor or {}).get("member_fields", {}).get(mem)
                    if m is None:
                        self.add_debt(f"{self.src(st)} write {name}.{mem}", "unmodelled_write", mem)
                        return
                    base = ["get", ["call", "nth_ch", "chs", k], m]
                    nv = v if op == "=" else [op[0], base, v]
                    rec = ["with", f["record"], ["call", "nth_ch", "chs", k], {m: nv}]
                    self.writes.append(("ch_rec", f, k, conds, rec))
                    return
                self.add_debt(f"{self.src(st)} write {name}.{mem}", "unmodelled_write", f"{name}.{mem}")
                return
        self.add_debt(f"{self.src(st)} write", "unmodelled_write", t)

    def write_storage(self, name, k, f, op, v, st, conds):
        kind = f["kind"]
        if kind == "unmodelled":
            self.add_debt(f"{self.src(st)} write {name}", "unmodelled_write", f["why"])
            return
        if kind == "scalar":
            nv = v if op == "=" else [op[0], f["field"], v]
            self.writes.append(("state", f["field"], conds, nv))
            if name == "lastCommittedBatchIndex":
                self.lci_write = v
            return
        if kind == "derived_lci":
            self.lci_write = v
            return
        if kind == "abs_map":
            if f.get("record"):
                if isinstance(v, tuple) and v[0] == "shadow":
                    _, nm, _f, _k, fields = v
                    v = ["with", f["record"], nm, dict(fields)]
                self.writes.append(("ch_rec", f, k, conds, v))
            else:
                nv = v if op == "=" else [op[0], ["call", "nth", f["field"], k], v]
                if name == "messageEnqueueTime" and canon(k) == canon("qlen"):
                    self.writes.append(("state", "enq", conds, ["call", "snoc", "enq", v]))
                else:
                    self.writes.append(("state", f["field"], conds, ["call", "set_nat", f["field"], k, nv]))
            return
        if kind == "batch_map":
            if isinstance(v, tuple) and v[0] == "ctor_fields":
                for efield, val in zip(v[1], v[2]):
                    self.entry_write(name, k, efield, val, conds)
                return
            if name == "committedStateRoots":
                self.entry_write(name, k, "csr", v, conds)
                return
            if f.get("entry_field"):
                self.entry_write(name, k, f["entry_field"], v, conds)
                return
            self.add_debt(f"{self.src(st)} write {name}", "unmodelled_write", name)
            return
        if kind == "commitment":
            # covered by the window effect (snoc/take), under CF
            return
        if kind == "queue":
            return
        if kind == "role_set":
            self.add_debt(f"{self.src(st)} write {name}", "unmodelled_write", f"role set write {name}")
            return
        self.add_debt(f"{self.src(st)} write {name}", "unmodelled_write", kind)

    def entry_write(self, family_name, k, efield, v, conds):
        """Write to the batch-map entry: into new_entry when k == next, else win_set/last."""
        if self.new_idx is not None and canon(k) == canon(self.new_idx):
            if self.new_entry is None:
                self.new_entry = {}
            self.new_entry[efield] = v
            if efield == "bvh" and self.action_spec.get("ghost_tag") and "tag" not in self.new_entry:
                self.new_entry["tag"] = self.tag_expr()
            return
        if family_name == "committedStateRoots" and canon(k) == canon(self._last_bound(self.lci_expr())):
            self.writes.append(("state", "win", conds, ["call", "set_last_csr", "win", v]))
            return
        self.add_debt(f"batch entry {efield} write at {k!r}", "unmodelled_write", f"{family_name}[k].{efield} outside entry construction")

    def tag_expr(self):
        return self.action_spec.get("ghost_tag", {}).get("expr")

    def s_unary(self, st):
        if st["operator"] in ("++", "--", "delete"):
            if st["operator"] == "delete":
                return self.s_delete(st)
            op = "+" if st["operator"] == "++" else "-"
            lhs = st["subExpression"]
            v = ["%s" % op, self.X(lhs) if not isinstance(self.X(lhs), tuple) else lhs["name"], 1]
            if lhs.get("nodeType") == "Identifier" and lhs["name"] in self.env:
                self.env[lhs["name"]] = simplify([op, self.env[lhs["name"]], 1])
                return
            self.write_target(lhs, "=", [op, self.X(lhs), 1], st)
            return

    def s_delete(self, st):
        sub = st["subExpression"]
        if sub.get("nodeType") == "IndexAccess":
            name = sub["baseExpression"].get("name")
            k = self.rewrite_lets(self.X(sub["indexExpression"]))
            f = self.fam(name)
            if f and f["kind"] == "abs_map" and f.get("record"):
                self.writes.append(("state", "chs", list(self.conds), ["call", "set_ch", "chs", k, ["call", "empty_ch"]]))
                return
            if f and f["kind"] == "batch_map":
                # deleting batch entries at k: covered by the window drop when k == lfi
                self.batch_delete(k)
                return
            self.add_debt(f"{self.src(st)} delete {name}", "unmodelled_write", f"delete {name}")
            return
        self.add_debt(f"{self.src(st)} delete", "unmodelled_write", "delete")

    def batch_delete(self, k):
        self.deleted_batch = k

    def s_callstmt(self, st):
        r = self.X(st)
        if isinstance(r, tuple) and r[0] == "require":
            cond, msg, node = r[1], r[2], r[3]
            return self.s_require(cond, msg, node)
        if isinstance(r, tuple) and r[0] == "store":
            _, field, v = r
            if self.new_entry is None:
                self.new_entry = {}
            self.new_entry[field] = v
            return
        if isinstance(r, tuple) and r[0] in ("store_drop",):
            return
        if isinstance(r, tuple) and r[0] == "void":
            return
        if isinstance(r, tuple) and r[0] == "guard":
            return
        if isinstance(r, tuple) and r[0] == "revert":
            self.add_debt(f"{self.src(st)} revert", "revert", "custom revert")
            return
        if isinstance(r, tuple) and r[0] in ("unmodelled", "debt"):
            return
        return

    def s_require(self, cond, msg, node):
        cond = self.rewrite_lets(cond) if isinstance(cond, list) else cond
        if isinstance(cond, tuple):
            kind = cond[0]
            if kind == "commit_cmp":
                return self.commit_require(cond, msg, node)
            if kind == "honesty":
                dr = self._drop_rule(msg)
                if dr:
                    self.add_debt(f"{self.src(node)} require {msg}", "subsumed_require", dr["note"])
                    return
                self.add_debt(f"{self.src(node)} require {msg}", "subsumed_require", "honest-header premise")
                return
            if kind in ("unmodelled", "debt", "call"):
                self.add_debt(f"{self.src(node)} require {msg}", "unmodelled_require", f"require({msg}) not translated")
                return
        dr = self._drop_rule(msg)
        if dr:
            self.add_debt(f"{self.src(node)} require {msg}", "subsumed_require", dr["note"])
            return
        # tuple records comparisons etc.
        self._drain_pending()
        site = self.site_for(cond)
        note = None
        for nt in self.pending_notes:
            note = (note + " " if note else "") + nt
        self.pending_notes = []
        self.emit_require(cond, msg or "require", self.src(node), note=note, site=site)

    def _drop_rule(self, msg):
        for d in self.spec.get("drop_requires", []):
            if d["reason"] == msg:
                return d
        return None

    def site_for(self, cond):
        for s in self.spec.get("sites", []):
            if canon(s["expr"]) == canon(cond):
                return s["site"]
        return None

    def commit_require(self, cond, msg, node):
        _, op, k, other = cond
        notes = self.spec["commit_notes"]
        lci = self._last_bound(self.lci_expr())
        if op == "==" and other == 0:
            e = [">", k, lci]
            self._drain_pending()
            return self.emit_require(e, msg, self.src(node), note=notes["commit_zero"])
        if op == "!=" and other == 0:
            e = ["<=", k, lci]
            self._drain_pending()
            return self.emit_require(e, msg, self.src(node), note=notes["commit_neq"])
        if op == "==" and self._is_hash(other):
            e = ["<=", k, lci]
            self._drain_pending()
            return self.emit_require(e, msg, self.src(node), note=notes["commit_hash"])
        self.add_debt(f"{self.src(node)} committedBatches cmp", "unmodelled_require", f"{op} {other!r}")

    def _is_hash(self, e):
        return isinstance(e, tuple) and e[0] in ("hash",) or isinstance(e, str)

    # ------------------------------------------------------------ walk entry
    def translate_fn(self, contract, name, env, local_names, expr_lets, conds=()):
        self.conds = list(conds)
        self.reasons = {}
        self.input_map = env
        self.input_names = set(v for v in env.values() if isinstance(v, str))
        self.local_names = local_names
        self.expr_let_table = {}
        for el in expr_lets:
            self.expr_let_table[canon(el["expr"])] = (el["name"] if isinstance(el["name"], list) else [el["name"]])
        self.pending_notes = []
        self.cur_fn = (contract, name)
        self.new_entry = None
        fn = self.find_fn(contract, name)
        if fn is None:
            raise RuntimeError(f"fn {contract}.{name} not found")
        self.blob_indices = self.scan_blobs(fn)
        self.run_modifiers(fn)
        body = fn.get("body", {}).get("statements", [])
        for st in body:
            self.S(st)
        return self.guards, self.writes

    def scan_blobs(self, node):
        out = set()
        def w(n):
            if isinstance(n, dict):
                if n.get("nodeType") == "FunctionCall":
                    ex = n.get("expression", {})
                    if ex.get("nodeType") == "Identifier" and ex.get("name") == "blobhash":
                        a = n.get("arguments", [])
                        if a and a[0].get("nodeType") == "Literal":
                            try:
                                out.add(int(a[0]["value"]))
                            except (TypeError, ValueError):
                                pass
                for v in n.values():
                    w(v)
            elif isinstance(n, list):
                for v in n:
                    w(v)
        w(node)
        return sorted(out)


def cname_eq(a, b):
    return a == b or (a or "").lstrip("I") == (b or "").lstrip("I")
