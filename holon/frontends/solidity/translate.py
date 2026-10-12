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
        self.guard_prov = []        # 'ast'|'spec' parallel to guards
        self.writes = []            # (family_kind, key, conds, expr)
        self.write_prov = []        # 'ast'|'spec' parallel to writes
        self.debt = []              # coverage debt items
        self.notes = []             # emitted notes attached to next require
        self.env = {}               # locals: name -> expr | Carrier | UNBOUND
        self.expr_lets = {}         # canon(expr) -> queue of names (spec let_names)
        self.let_exprs = {}         # canon(expr) -> bound name
        self.pending = []           # pending let/guard items before next emit
        self.established = []       # normalized established requires
        self.subst = {}             # var -> expr established equalities
        self.new_entry = None       # pending window-entry dict
        self.entry_prov = {}        # entry field -> 'ast'|'spec'
        self.lci_write = None       # last lci assignment expr
        self.ret = []               # (conds, expr) returns for view fns
        self.blob_lets_done = False
        self.blob_indices = []
        self.blob_emitted = set()
        self.fact_inputs = set()
        self.oracle_inputs = []     # input names an oracle emit asked to add (ordered)
        self.call_guards = {}       # fn key -> guards collected for call sites
        self.in_unchecked = False
        self.debt_keys = set()
        # mechanical let-hoisting state
        self.let_names = {}         # classifier -> [names] queue (spec-provided names)
        self.hoist_used = {}        # classifier -> count consumed
        self.hoist_bound = {}       # (classifier, canon) -> {'name','valid'}
        self.hoist_policy = {}      # 'def:<name>' -> 'always'|'value'
        self.in_require_arg = 0     # >0 while translating require(...) condition
        self.self_idx_alias = None  # self-carrier idx proven equal to new_idx

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
    def emit_let(self, name, expr, src=None, prov="ast"):
        item = {"let": name, "expr": expr, **({"src": src} if src else {})}
        self.guards.append(item)
        self.guard_prov.append(prov)
        self.let_exprs[canon(expr)] = name
        self.let_values[name] = expr
        g = getattr(self, "action_spec", {}).get("ghost_tag")
        if g and name == g.get("after"):
            gl = self._ghost_tag_let()
            if gl is not None:
                self.guards.append(gl)
                self.guard_prov.append("spec")
                self.let_exprs[canon(gl["expr"])] = gl["let"]

    def _vocab(self):
        """Names that are always bound in the emitted facts: params, state and
        ghost fields, defs, and the action's declared inputs."""
        if not hasattr(self, "_vocab_cache"):
            v = set((self.spec.get("params") or {}).keys())
            for sec in ("state", "ghost_state"):
                v |= {r[0] for r in (self.spec.get(sec) or [])}
            v |= set((self.spec.get("defs") or {}).keys())
            v |= set((self.spec.get("shadow") or {}).keys())
            v |= {x for x in (self.spec.get("env") or {}).values() if isinstance(x, str)}
            for r in (self.spec.get("reasons") or []):
                pass
            self._vocab_cache = v
        return self._vocab_cache

    def _resolve_local_names(self, e):
        """Substitute local_names model names in a spec expr with the local's
        current bound value. A spec name like `next` is only a bound name
        while its Solidity local was let-bound; when the local instead holds
        a plain value (e.g. `parent` after a mutation), the spec expr must
        carry that value, not the dead name."""
        rev = {}
        for sol, nm in (getattr(self, "local_names", None) or {}).items():
            rev.setdefault(nm, sol)
        def go(x):
            if isinstance(x, str) and x in rev and x not in self.let_values:
                # the spec name is not a bound let here — substitute the
                # local's concrete value; a local that is missing or env-bound
                # to a marker keeps the name so _unbound_names flags it (the
                # let is then dropped with a debt item)
                v = self.env.get(rev[x])
                return v if isinstance(v, (str, int, list)) else x
            if isinstance(x, list):
                return [go(y) for y in x]
            return x
        return go(e)

    def _ghost_tag_let(self):
        """The spec ghost_tag let, with its spec-name locals resolved.
        Returns None (and records debt) if a name stays unbound."""
        g = getattr(self, "action_spec", {}).get("ghost_tag") or {}
        if not g.get("name"):
            return None
        e = self._resolve_local_names(g["expr"])
        bad = self._unbound_names(e)
        if bad:
            self.add_debt(f"ghost_tag {g['name']}", "unbound_value",
                          f"ghost tag let dropped: name(s) {sorted(set(bad))} "
                          "have no bound model value")
            return None
        return {"let": g["name"], "expr": e}

    def _unbound_names(self, e, extra=()):
        """Str leaves that would surface in emitted facts with no binding:
        not an input/param/state/let name and env-bound to an unbound marker."""
        bad = []
        bound = self.fact_inputs | set(self.let_values) | self._vocab() | set(extra)
        OPS = {"call", "get", "mk", "with", "list", "?", "!", "&&", "||",
               "==", "!=", "<", "<=", ">", ">=", "+", "-", "*", "/"}

        def walk(x, skip=False):
            if isinstance(x, str):
                if skip or x in OPS or x in bound:
                    return
                v = self.env.get(x)
                if v is not None and not (isinstance(v, tuple) and v[0] == "unbound"):
                    return
                bad.append(x)
            elif isinstance(x, dict):
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                op = x[0] if x and isinstance(x[0], str) else None
                for j, y in enumerate(x):
                    if j == 0:
                        continue
                    # call name, get field, and mk/with type names are not vars
                    if op == "call" and j == 1:
                        continue
                    if op == "get" and j == 2:
                        continue
                    if op in ("mk", "with") and j == 1:
                        continue
                    walk(y)

        walk(e)
        return bad

    def _drain_pending(self):
        pnames = {it["let"] for it in self.pending if "let" in it}
        kept = []
        for it in self.pending:
            drop = False
            if "let" in it and "expr" in it:
                ubad = self._unbound_names(it["expr"], extra=pnames)
                if ubad:
                    self.add_debt(f"{it.get('src')} let {it['let']}", "unbound_value",
                              f"let dropped: name(s) {sorted(set(ubad))} have no bound "
                              "model value")
                    self.let_values.pop(it["let"], None)
                    drop = True
            if not drop:
                kept.append(it)
        self.pending = kept
        out = []
        g = getattr(self, "action_spec", {}).get("ghost_tag") or {}
        for it in self.pending:
            out.append(it)
            if it.get("let") == g.get("after") and g.get("name"):
                gl = self._ghost_tag_let()
                if gl is not None:
                    gl["__prov"] = "spec"
                    out.append(gl)
        self.pending = []
        for it in out:
            prov = it.pop("__prov", "ast")
            self.guards.append(it)
            self.guard_prov.append(prov)
            if "let" in it and "expr" in it:
                self.let_values[it["let"]] = it["expr"]

    def emit_require(self, expr, reason_str, src, note=None, site=None, prov="ast"):
        conds = getattr(self, "conds", [])
        e = simplify(expr)
        if conds:
            e = simplify(OR(NOT(AND(*conds)), e))
        e = self._ifcond_operands(e)
        if isinstance(e, list):
            e = self.rewrite_lets(e)
        self._drain_pending()
        bad = self._unbound_names(e)
        if bad:
            self.add_debt(f"{src} require {reason_str}", "unbound_guard",
                          f"guard dropped: name(s) {sorted(set(bad))} have no bound "
                          "model value (decoded from opaque header bytes or "
                          "unmodelled locals)")
            return
        rid = self.reason_id(reason_str)
        item = {"require": e, "reason": rid, "src": src}
        if site:
            item["site"] = site
        if note:
            item["note"] = note
        self.guards.append(item)
        self.guard_prov.append(prov)
        self.established.append(normalize(e))
        if isinstance(e, list) and e[0] == "==":
            if isinstance(e[1], str) and e[1].isidentifier():
                self.subst.setdefault(e[1], e[2])
        return item

    def W(self, *w, prov="ast"):
        w = list(w)
        if isinstance(w[-1], list):
            w[-1] = self.rewrite_lets(w[-1])
        self.writes.append(tuple(w))
        self.write_prov.append(prov)

    def reason_id(self, s):
        rs = self.reasons.setdefault(s, len(self.reasons) + 1)
        return rs

    def note(self, text):
        if self.pending_notes is not None:
            self.pending_notes.append(text)

    # -------------------------------------------------- mechanical hoisting
    def hoist(self, expr, classifier, src=None, prov="ast"):
        """Bind expr to a let name drawn from let_names[classifier] (a queue).

        The expr is always AST-derived; the spec only supplies the model's
        conventional names. Reuse the bound name while the binding is valid;
        a write to the underlying state invalidates it (see invalidate()).
        """
        c = canon(expr)
        key = (classifier, c)
        st = self.hoist_bound.get(key)
        if st is not None and st["valid"]:
            return st["name"]
        names = self.let_names.get(classifier)
        if names is None:
            return expr
        i = self.hoist_used.get(classifier, 0)
        if i >= len(names):
            return expr
        nm = names[i]
        self.hoist_used[classifier] = i + 1
        self.pending.append({"let": nm, "expr": expr, **({"src": src} if src else {}), "__prov": prov})
        self.let_exprs[c] = nm
        self.let_values[nm] = expr
        self.hoist_bound[key] = {"name": nm, "valid": True}
        return nm

    def invalidate(self, classifier):
        """Mark every binding of `classifier` stale: next read re-hoists a fresh name."""
        for k, v in self.hoist_bound.items():
            if k[0] == classifier:
                v["valid"] = False

    def _is_lci(self, e):
        return canon(e) == canon(self.lci_expr()) or e == self.let_exprs.get(canon(self.lci_expr()))

    def bind_or_let(self, expr, name=None, src=None):
        """Compat shim: hoist by generated classifier (no spec expr table)."""
        return self.hoist(expr, name or "gen", src=src)

    def maybe_name(self, expr, src=None):
        return expr

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
                return self.hoist(self.lci_expr(), "lci", src=self.src(n))
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

    def hoist_accessor(self, e, node=None):
        """Shadow-accessor calls (bvh_at/tag_at etc.) hoist in value contexts."""
        if isinstance(e, list) and is_call(e) and self.hoist_policy.get(f"def:{e[1]}") == "value" and not self.in_require_arg:
            return self.hoist(e, f"def:{e[1]}", src=self.src(node) if node is not None else None)
        return e

    def post_hoist(self, e, node=None):
        """Mechanical hoists applied to call-site results: lci reads and
        hoist_policy'd def calls whose classifier carries a spec name."""
        if (isinstance(e, list) and is_call(e) and e[1] == "nth"
                and len(e) == 4 and e[2] == "blobs" and isinstance(e[3], int)):
            self.blob(e[3], node)
        if isinstance(e, list) and canon(e) == canon(self.lci_expr()):
            return self.hoist(e, "lci", src=self.src(node) if node is not None else None)
        if isinstance(e, list) and is_call(e):
            cls = f"def:{e[1]}"
            pol = self.hoist_policy.get(cls)
            if pol and cls in self.let_names and (pol == "always" or not self.in_require_arg):
                return self.hoist(e, cls, src=self.src(node) if node is not None else None)
        return e

    def x_member(self, n):
        base = self.X(n["expression"])
        mem = n["memberName"]
        if isinstance(base, tuple) and base[0] == "map":
            f = self.fam(base[1])
            if f["kind"] == "queue" and mem == "length":
                return f["field"]
            self.add_debt(f"{self.src(n)} member {base[1]}.{mem}", "unmodelled_member", f"{base[1]}.{mem}")
            return ("unmodelled", f"{base[1]}.{mem}")
        if mem == "length" and isinstance(base, list) and base[:2] == ["call", "nthl"]:
            return ["call", "len", base]
        if isinstance(base, tuple) and base[0] == "abs_rec":
            _, f, k = base
            ctor = self.ctor_of(f["record"])
            m = (ctor or {}).get("member_fields", {}).get(mem)
            if m is None:
                self.add_debt(f"{self.src(n)} member {f['record']}.{mem}", "unmodelled_member", mem)
                return ("unmodelled", mem)
            call = ["call", "nth_ch" if f["record"] == "Ch" else "nth_rec", f["field"], k]
            if "ch" in self.let_names:
                base = self.hoist(call, "ch", src=self.src(n))
                return ["get", base, m]
            bound = self.let_exprs.get(canon(call))
            if bound is not None:
                return ["get", bound, m]
            e = ["get", call, m]
            if f"ch.{m}" in self.let_names:
                return self.hoist(e, f"ch.{m}", src=self.src(n))
            return e
        if isinstance(base, tuple) and base[0] == "shadow":
            _, nm, f, k, fields = base
            ctor = self.ctor_of(f["record"])
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
            _, _nm, k, f = base
            m = (f.get("fields") or {}).get(mem) if isinstance(f, dict) else None
            if m:
                return self.hoist_accessor(["get", ["call", "w", "lfi", "win", k], m], n)
            self.add_debt(f"{self.src(n)} member {base[1]}.{mem}", "unmodelled_member", mem)
            return ("unmodelled", mem)
        return base if isinstance(base, (str, int, bool, list)) else ("member", base, mem)

    def rec_expr(self, v, record=None):
        """Lower a record-ish value (shadow/abs_rec/mk/with/plain) to a record expression."""
        if isinstance(v, tuple) and v[0] == "shadow":
            _, nm, f, k, fields = v
            return ["with", f["record"], nm, dict(fields)]
        if isinstance(v, tuple) and v[0] == "abs_rec":
            _, f, k = v
            rec = f["record"]
            return ["call", "nth_ch" if rec == "Ch" else "nth_rec", f["field"], k]
        return v

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
            elif isinstance(inner, list) and inner[:2] == ["call", "nthl"]:
                # abs_map_list element read: lvv[k][i] is a record
                return ["call", "nthr", inner, self.rewrite_lets(k)]
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
            if f["field"] == "blobs" and isinstance(k, int):
                return self.blob(k, n)
            return ["call", "nth", f["field"], k]
        if kind == "abs_map_list":
            # mapping(K => V[]): nthl(field,k) is the whole V-list at k.
            return ["call", "nthl", f["field"], k]
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

    def ctor_of(self, record):
        """struct_ctors is keyed by Solidity struct name; resolve the model record
        name (e.g. 'Ch') via its 'record' field."""
        return self.spec["struct_ctors"].get(record) or next(
            (v for v in self.spec["struct_ctors"].values() if v.get("record") == record), None)

    def _last_bound(self, e):
        c = canon(e)
        return self.let_exprs.get(c, e)

    def x_binop(self, n):
        op = n["operator"]
        a = self.X(n["leftExpression"])
        b = self.X(n["rightExpression"])
        # address-atom comparisons: contract-address state is a Nat atom, not a struct
        if op in ("==", "!=", "<", "<=", ">", ">="):
            if isinstance(a, tuple) and a[0] == "addr":
                a = a[1]
            if isinstance(b, tuple) and b[0] == "addr":
                b = b[1]
        # commitment-map comparisons
        if isinstance(a, tuple) and a[0] == "commit" or isinstance(b, tuple) and b[0] == "commit":
            tok = a if isinstance(a, tuple) and a[0] == "commit" else b
            other = b if tok is a else a
            return ("commit_cmp", op, tok[1], other)
        if isinstance(a, tuple) and a[0] == "batch_entry" and isinstance(b, tuple) and b[0] == "hash":
            return ("honesty", n, b[1], a[2])
        if isinstance(b, tuple) and b[0] == "batch_entry" and isinstance(a, tuple) and a[0] == "hash":
            return ("honesty", n, a[1], b[2])
        a = self._lower(a)
        b = self._lower(b)
        if isinstance(a, tuple) and a[0] in ("unmodelled", "debt", "map") or isinstance(b, tuple) and b[0] in ("unmodelled", "debt", "map"):
            return ("unmodelled", "cmp")
        d = BINOP.get(op)
        if d in ("&&", "||", "!") or op in ("&&", "||"):
            aa = self.commit_atom(*a[1:]) if isinstance(a, tuple) and a[0] == "commit_cmp" else a
            bb = self.commit_atom(*b[1:]) if isinstance(b, tuple) and b[0] == "commit_cmp" else b
            if isinstance(aa, tuple) or isinstance(bb, tuple):
                return ("unmodelled", "cmp")
            a, b = aa, bb
        if d is None:
            self.add_debt(f"{self.src(n)} binop {op}", "untranslated_expr", f"binary op {op}")
            return ("debt", op)
        if d == "-" and not self.in_unchecked:
            self.panic_guard(a, b, n)
        return [d, self.rewrite_lets(a) if isinstance(a, list) else a, self.rewrite_lets(b) if isinstance(b, list) else b]

    def commit_atom(self, op, k, other):
        """commit_cmp folded inside a boolean context: committedBatches[k] is nonzero
        exactly on the window lfi..lci, so !=0 -> k>=lfi and ==0 -> k>lci."""
        if other != 0:
            return None
        lci = self._last_bound(self.lci_expr())
        if op == "!=":
            return [">=", k, "lfi"]
        if op == "==":
            return [">", k, lci]
        return None

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
            self.in_require_arg += 1
            cond = self.X(n["arguments"][0])
            self.in_require_arg -= 1
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
                f = self.fam(inner["name"])
                if f and f["kind"] == "queue" and mem == "push":
                    self.W("state", "qlen", list(self.conds), ["+", "qlen", 1])
                    return ("void", "push")
                lib = self.spec.get("contract_ifaces", {}).get(inner["name"], inner["name"])
                return self.call_named(f"{lib}.{mem}", n["arguments"], n)
            obj = self.X(inner)
            if isinstance(obj, tuple) and obj[0] == "contract":
                cname = self.spec.get("contract_ifaces", {}).get(obj[1], obj[1])
                return self.call_contract(f"{cname}.{mem}", cname, None, n["arguments"], n)
            if isinstance(obj, tuple) and obj[0] == "map":
                f = self.fam(obj[1])
                if f and f["kind"] == "queue" and mem == "push":
                    self.W("state", "qlen", list(self.conds), ["+", "qlen", 1])
                    return ("void", "push")
            if mem == "push" and isinstance(obj, list) and obj[:2] == ["call", "nthl"]:
                # abs_map_list push: lvv[k].push(x) -> lvv[k] = snoc(lvv[k], x)
                field, k = obj[2], obj[3]
                v = self.rec_expr(self._lower(self.X(n["arguments"][0])))
                self.W("state", field, list(self.conds), ["call", "set_l", field, k, ["call", "snoc", obj, v]])
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
        for j in self.blob_indices:
            if j not in self.blob_emitted:
                self.blob_emitted.add(j)
                self.pending.append({"let": f"b{j}", "expr": ["call", "nth", "blobs", j], "__prov": "ast"})
        return ["call", "nth", "blobs", i]

    def keccak(self, n):
        # inside _computeBlobVersionedHash the asm collects blob hashes -> agg(blobs)
        if self.cur_fn and self.cur_fn[1] == "_computeBlobVersionedHash":
            return ["call", "agg", "blobs"]
        if self.cur_fn and self.cur_fn[1] == "_verifyProof":
            return ("unmodelled", "public input hash")
        oc = self.spec.get("oracles", {}).get("keccak256")
        if oc and "emit" in oc:
            return self.oracle_emit(oc, n["arguments"], n)
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
                return self.oracle_emit(oc, args, node)
            if "guard" in oc:
                g = oc["guard"]
                self.emit_require(g["require"], g["reason"], g.get("src", self.src(node)))
                return ("guard", key)
            if "effects" in oc or "returns_unmodelled" in oc:
                for ef in oc.get("effects", []):
                    self.W("state", ef["field"], list(self.conds), self.subst_args(ef["expr"], args), prov="spec")
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

    def add_oracle_inputs(self, entries):
        """`add_inputs` entries: bare name (Nat) or typed [name, type] pair."""
        for e in entries:
            n, ty = (e if isinstance(e, list) else [e, "Nat"])
            if n not in self.fact_inputs:
                self.fact_inputs.add(n)
                self.oracle_inputs.append([n, ty])

    def oracle_emit(self, oc, args, node):
        """Oracle `emit` + `add_inputs`: a declared input name emitted by the
        oracle is a per-call input of the action (added to its inputs by the
        extractor), not a global param. `emit_overrides` can redirect the
        emitted name per action."""
        self.add_oracle_inputs(oc.get("add_inputs", []))
        emit = oc.get("emit")
        overrides = oc.get("emit_overrides", {})
        if isinstance(emit, str) and self.action_spec.get("name") in overrides:
            emit = overrides[self.action_spec["name"]]
        return self.post_hoist(self.subst_args(emit, args), node)

    def call_oracle(self, key, oc, args, node):
        return self.oracle_emit(oc, args, node)

    # ------------------------------------------------------- internal calls
    def find_fn(self, contract, name, arity=None):
        for path, c in self.spec["contracts"].items():
            if cname_eq(c.get("name"), contract) or contract is None:
                u = self.world.units.get(path)
                if u is None:
                    continue
                for n in u.find("FunctionDefinition", name=name):
                    if n.get("kind") == "modifier":
                        continue
                    if arity is not None and len(n.get("parameters", {}).get("parameters", [])) != arity:
                        continue
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
        return self.post_hoist(["call", dname, *call_args], node)

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
        for rp in fn.get("returnParameters", {}).get("parameters", []):
            newenv.setdefault(rp["name"], ("unbound", rp["name"]))
        self.env = newenv
        self.run_modifiers(fn)
        for st in fn.get("body", {}).get("statements", []):
            self.S(st)
        rets = self.ret
        self.env = saved_env
        self.ret = saved_ret
        self.cur_fn = saved_cur
        if len(rets) == 1 and rets[0][0] == []:
            return self.post_hoist(rets[0][1], node)
        if len(rets) > 1:
            e = rets[-1][1]
            for conds, val in reversed(rets[:-1]):
                e = simplify(["?", AND(*conds), val, e])
            return self.post_hoist(e, node)
        return ("void", fkey[1])

    def _modifier_debt(self, name, reason):
        a = getattr(self, "action_spec", None) or {}
        an = a.get("name") or (f"{self.cur_fn[0]}.{self.cur_fn[1]}" if self.cur_fn else "?")
        self.add_debt(f"action:{an}.modifier:{name}", "abstracted_modifier", reason)

    def run_modifiers(self, fn):
        for mi in fn.get("modifiers", []):
            ref = mi.get("modifierName", {})
            name = ref.get("name") or mi.get("kind", "")
            if name in self.spec.get("modifiers_abstracted", []):
                self._modifier_debt(name, "modifier body skipped: abstracted by spec")
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
                self._modifier_debt(name, "modifier definition not found in the AST")
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
                              note="_loadL1MessageHashes -> getCrossDomainMessage(i) requires i < messageQueue.length",
                              prov="spec")
            return ("unmodelled", "queue_read_range")
        if h == "pop_messages":
            bn = self.hoist(self.X(args[1]), "pop")
            btot = self.hoist(self.X(args[0]), "pop")
            hh = self.spec["handlers"]["_popL1Messages"]
            self.emit_require(OR(["==", bn, 0], ["==", "qpend", ["-", btot, bn]]),
                              "start index mismatch", hh["require_src"], note=hh.get("note"),
                              prov="spec")
            self.W("state", "qpend", list(self.conds), simplify(["?", ["==", bn, 0], "qpend", btot]), prov="spec")
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
            # `revert Err` under accumulated branch conds is a guarded-command require:
            # the branch must never be taken, so the require is NOT(conds).
            err = st.get("errorCall", {}).get("expression", {}).get("name") or "?"
            self.emit_require(["!", AND(*self.conds) if self.conds else True],
                              err, self.src(st))
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
                return self.hoist_accessor(["call", f["accessor"], "lfi", "win", f["shadow"], k])
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
        saved_pending = list(self.pending)
        self.conds = saved + [c]
        self.in_branch = getattr(self, "in_branch", 0) + 1
        for s in tstmt.get("statements", [tstmt] if tstmt and tstmt.get("nodeType") not in (None, "Block") else []):
            self.S(s)
        self.in_branch -= 1
        self.conds = saved
        # pending hoists emitted inside the branch are branch-local: resolve
        # their names back to exprs in the environment before merging.
        self._squash_branch_lets(saved_pending)
        then_env = dict(self.env)
        if fstmt is not None:
            self.env = dict(saved_env)
            self.conds = saved + [simplify(NOT(c))]
            self.in_branch += 1
            for s in fstmt.get("statements", [fstmt] if fstmt and fstmt.get("nodeType") not in (None, "Block") else []):
                self.S(s)
            self.in_branch -= 1
            self.conds = saved
            self._squash_branch_lets(saved_pending)
        else_env = self.env if fstmt is not None else dict(saved_env)
        # join: local names bound differently across branches become a ?-merge;
        # a branch established by an already-emitted require collapses to its value
        merged = dict(else_env)
        keys = set(then_env) | set(else_env)
        est = {canon(x) for x in self.established}
        for k in sorted(keys):
            def deref(v):
                if isinstance(v, str) and v in self.let_values:
                    return self.let_values[v]
                return v
            vt = deref(then_env.get(k, saved_env.get(k, ("unbound", k))))
            ve = deref(else_env.get(k, saved_env.get(k, ("unbound", k))))
            if canon(vt) == canon(ve) if isinstance(vt, list) or isinstance(ve, list) else vt == ve:
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
            elif isinstance(merged[k], list) and merged[k] and merged[k][0] == "?":
                cond = merged[k][1]
                cls = f"ifcond:{cond}" if isinstance(cond, str) else None
                if cls and cls in self.let_names:
                    merged[k] = self.hoist(merged[k], cls, src=self.src(tstmt))
        self.env = merged

    def _squash_branch_lets(self, saved_pending):
        for it in self.pending[len(saved_pending):]:
            self.let_values[it["let"]] = it["expr"]
            self.let_exprs.pop(canon(it["expr"]), None)
        del self.pending[len(saved_pending):]

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
        p = self.hoist(["-", "idx", "lfi"], "rev_p")
        moved = self.hoist(["call", "drop", "win", "p"], "rev_moved")
        self._drain_pending()
        lci = self._last_bound(self.lci_expr())
        self.W("state", "win", [], ["call", "take", "win", p], prov="spec")
        for s in ("s_csr", "s_bd", "s_bvh", "s_tag"):
            self.W("state", s, [], ["call", "concat", ["call", f"es_{s[2:]}", moved], s], prov="spec")
        self.W("state", "inch", [], simplify(["&&", "inch", ["!", ["call", "any_open", "chs", "idx", lci]]]), prov="spec")
        self.W("state", "chs", [], ["call", "clear_chs", "chs", "idx", lci], prov="spec")
        self.W("state", "rri", [], simplify(["?", ["&&", [">", "rri", 0], [">=", "rri", "idx"], ["<=", "rri", lci]], 0, "rri"]), prov="spec")
        self.add_debt(f"{self.src(st)} revert loop refunds", "unmodelled_write",
                      "batchChallengeReward += challengeDeposit inside the loop is reward accounting")

    def h_bump_loop(self, st):
        self.W("state", "win", [], ["call", "bump_f", "win", ["-", "idx", "lfi"], "W"], prov="spec")

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
            op = "nth_ch" if f["record"] == "Ch" else "nth_rec"
            self.pending.append({"let": nm, "expr": ["call", op, f["field"], k], "src": self.src(st), "__prov": "ast"})
            self.let_exprs[canon(["call", op, f["field"], k])] = nm
            self.env[name] = ("shadow", nm, f, k, {})
            self._drain_pending()
            return
        if isinstance(v, tuple):
            self.env[name] = v
            return
        nm = self.local_names.get(name)
        if nm and isinstance(v, list):
            self.pending.append({"let": nm, "expr": v, "src": self.src(st), "__prov": "ast"})
            self.let_exprs[canon(v)] = nm
            self.env[name] = nm
            self._drain_pending()
        elif isinstance(v, list) and self._heavy(v):
            nm = nm or f"v{name}"
            self.pending.append({"let": nm, "expr": v, "src": self.src(st), "__prov": "ast"})
            self.let_exprs[canon(v)] = nm
            self.env[name] = nm
            self._drain_pending()
        else:
            self.env[name] = v

    def _heavy(self, e):
        return isinstance(e, list)

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
            if (nm and canon(nv) != canon(name) and isinstance(nv, list)
                    and canon(nv) not in self.let_exprs and nm not in self.let_exprs.values()):
                self.emit_let(nm, nv, src=self.src_span(st))
                self.env[name] = nm
            return
        self.write_target(lhs, op, v, st)

    def write_target(self, lhs, op, v, st):
        t = lhs.get("nodeType")
        conds = list(self.conds)
        if t == "Identifier":
            name = lhs["name"]
            sow = self.spec.get("storage_on_write", {}).get(name)
            if sow is not None:
                # storage that is not otherwise modelled: the spec declares
                # which model registers the write moves (e.g. a contract-
                # registry swap redirecting an oracle carrier)
                self.add_oracle_inputs(sow.get("add_inputs", []))
                for eff in sow.get("effects", []):
                    nv = eff["expr"]
                    if op != "=":
                        nv = [op[0], eff["field"], nv]
                    self.W("state", eff["field"], conds, nv, prov="spec")
                self.add_debt(f"{self.src(st)} write {name}", "spec_bound", sow["note"])
                return
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
                ctor = self.ctor_of(f["record"])
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
                    ctor = self.ctor_of(f["record"])
                    m = (ctor or {}).get("member_fields", {}).get(mem)
                    if m is None:
                        self.add_debt(f"{self.src(st)} write {name}.{mem}", "unmodelled_write", mem)
                        return
                    call = ["call", "nth_ch", "chs", k]
                    if "ch" in self.let_names:
                        base_nm = self.hoist(call, "ch", src=self.src(st))
                    else:
                        base_nm = self.let_exprs.get(canon(call), call)
                    base = ["get", base_nm, m]
                    nv = v if op == "=" else [op[0], base, v]
                    rec = ["with", f["record"], base_nm, {m: nv}]
                    self.W("ch_rec", f, k, conds, rec)
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
            self.W("state", f["field"], conds, nv)
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
                self.W("ch_rec", f, k, conds, v)
            else:
                nv = v if op == "=" else [op[0], ["call", "nth", f["field"], k], v]
                if name == "messageEnqueueTime" and canon(k) == canon("qlen"):
                    self.W("state", "enq", conds, ["call", "snoc", "enq", v])
                else:
                    self.W("state", f["field"], conds, ["call", "set_nat", f["field"], k, nv])
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
            # membership write: m[k] = true adds k to the list (if absent); false removes it.
            field = f["field"]
            if v is True:
                nv = ["?", ["call", "mem", k, field], field, ["call", "snoc", field, k]]
            elif v is False:
                nv = ["call", "remove", k, field]
            else:
                nv = ["?", v, ["?", ["call", "mem", k, field], field, ["call", "snoc", field, k]], ["call", "remove", k, field]]
            self.W("state", field, conds, nv)
            return
        self.add_debt(f"{self.src(st)} write {name}", "unmodelled_write", kind)

    def entry_write(self, family_name, k, efield, v, conds):
        """Write to the batch-map entry: into new_entry when k names the entry under
        construction (new_idx, or the self-carrier index aliased to it by premise)."""
        if isinstance(v, list):
            v = self.rewrite_lets(v)
        if self.new_idx is not None and (canon(k) == canon(self.new_idx) or (
                self.self_idx_alias is not None and canon(k) == canon(self.self_idx_alias))):
            if self.new_entry is None:
                self.new_entry = {}
            self.new_entry[efield] = v
            self.entry_prov[efield] = "ast"
            g = self.action_spec.get("ghost_tag")
            if efield == "bvh" and g and "tag" not in self.new_entry:
                self.new_entry["tag"] = g["expr"]
                self.entry_prov["tag"] = "spec"
            return
        if family_name == "committedStateRoots" and canon(k) == canon(self._last_bound(self.lci_expr())):
            self.W("state", "win", conds, ["call", "set_last_csr", "win", v])
            return
        self.add_debt(f"batch entry {efield} write at {k!r}", "unmodelled_write", f"{family_name}[k].{efield} outside entry construction")

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
                field = f["field"]
                rec = f["record"]
                op = "set_ch" if rec == "Ch" else "set_rec"
                self.W("state", field, list(self.conds), ["call", op, field, k, ["call", "empty_" + rec.lower()]])
                return
            if f and f["kind"] == "abs_map":
                self.W("state", f["field"], list(self.conds), ["call", "set_nat", f["field"], k, 0])
                return
            if f and f["kind"] == "role_set":
                self.W("state", f["field"], list(self.conds), ["call", "remove", k, f["field"]])
                return
            if f and f["kind"] == "batch_map":
                # deleting batch entries at k: covered by the window drop when k == lfi
                self.batch_delete(k, st)
                return
            self.add_debt(f"{self.src(st)} delete {name}", "unmodelled_write", f"delete {name}")
            return
        self.add_debt(f"{self.src(st)} delete", "unmodelled_write", "delete")

    def batch_delete(self, k, st):
        """delete batch_map[k]: modelled as dropping the window's head entry when
        k is the current lfi (an established lfi+1 == idx premise covers k == idx-1).
        Subsequent deletes at the same head collapse into the one drop."""
        if getattr(self, "win_dropped", False):
            return
        if self._is_window_head(k):
            self.W("state", "win", list(self.conds), ["call", "drop", "win", 1])
            self.win_dropped = True
        else:
            self.add_debt(f"{self.src(st)} delete batch entry", "unmodelled_write",
                          f"batch entry delete away from the window head: {k!r}")

    def _is_window_head(self, k):
        if canon(k) == canon("lfi"):
            return True
        if canon(k) == canon(["-", "idx", 1]):
            return normalize(["==", ["+", "lfi", 1], "idx"]) in self.established
        return False

    def s_callstmt(self, st):
        r = self.X(st)
        if isinstance(r, tuple) and r[0] == "require":
            cond, msg, node = r[1], r[2], r[3]
            return self.s_require(cond, msg, node)
        if isinstance(r, tuple) and r[0] == "store":
            _, field, v = r
            if self.new_entry is None:
                self.new_entry = {}
            v = self.rewrite_lets(v) if isinstance(v, list) else v
            self.new_entry[field] = v
            self.entry_prov[field] = "ast"
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
                return self.s_honesty(cond, msg, node)
            if kind in ("unmodelled", "debt", "call"):
                self.add_debt(f"{self.src(node)} require {msg}", "unmodelled_require", f"require({msg}) not translated")
                return
        if self._carrier_eq_drop(cond, msg, node):
            return
        # tuple records comparisons etc.
        self._drain_pending()
        site = self.site_for(cond)
        note = None
        for nt in self.pending_notes:
            note = (note + " " if note else "") + nt
        self.pending_notes = []
        self.emit_require(cond, msg or "require", self.src(node), note=note, site=site)

    def s_honesty(self, cond, msg, node):
        """committedBatches[k] == hash(carrier): the carrier premise declares the
        presented header's hash equals the map entry, so the equality half is
        dropped as debt. For a self-carrier the *range* half (k committed)
        survives as `k <= lci` unless k already aliases the current lci."""
        _, _n, kind, k = cond
        self.add_debt(f"{self.src(node)} require {msg}", "subsumed_require",
                      "honest-carrier premise: the presented header's hash equals "
                      "committedBatches at its index by construction")
        if kind == "self":
            if self.self_idx_alias is not None and canon(k) == canon(self.self_idx_alias):
                return
            lci = self.hoist(self.lci_expr(), "lci", src=self.src(node))
            e = ["<=", k, lci]
            self._drain_pending()
            self.emit_require(e, msg, self.src(node),
                              note=self.spec["commit_notes"]["commit_hash"])
        return

    def _ifcond_operands(self, e):
        """A composite boolean operand containing `get <bound-let> .m` is a named
        reusable condition: hoist it under the 'ifcond' classifier when the
        action names one (e.g. proveState's timeout)."""
        if "ifcond" not in self.let_names or not isinstance(e, list) or e[0] not in ("||", "&&"):
            return e
        if self.hoist_used.get("ifcond", 0) >= len(self.let_names["ifcond"]):
            return e

        def bound_get(x):
            return isinstance(x, list) and (
                (x[0] == "get" and isinstance(x[1], str) and x[1] in self.let_values)
                or any(bound_get(y) for y in x[1:]))

        e = list(e)
        for j, op in enumerate(e[1:], 1):
            if (isinstance(op, list) and bound_get(op)
                    and canon(op) not in self.let_exprs):
                e[j] = self.hoist(op, "ifcond")
                break
        return e

    def _carrier_eq_drop(self, cond, msg, node):
        """`lci == idx` (self-carrier index vs lastCommittedBatchIndex): subsumed by
        the carrier premise; additionally proves idx == new_idx for entry writes."""
        if not (isinstance(cond, list) and cond[0] == "=="):
            return False
        a, b = cond[1], cond[2]
        self_idx = self.spec.get("carrier_idx", {}).get("self")
        if self_idx is None:
            return False
        if a == self_idx:
            other = b
        elif b == self_idx:
            other = a
        else:
            return False
        if not self._is_lci(other):
            return False
        self.add_debt(f"{self.src(node)} require {msg}", "subsumed_require",
                      "carrier premise: the presented header carries index LCI")
        if self.new_idx is not None:
            self.self_idx_alias = self.new_idx
        return True

    def site_for(self, cond):
        for s in self.spec.get("sites", []):
            if canon(s["expr"]) == canon(cond):
                return s["site"]
        return None

    def commit_require(self, cond, msg, node):
        _, op, k, other = cond
        notes = self.spec["commit_notes"]
        lci = self.hoist(self.lci_expr(), "lci", src=self.src(node))
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
        return isinstance(e, tuple) and e[0] in ("hash", "hash_tok") or isinstance(e, str)

    # ------------------------------------------------------------ walk entry
    def translate_fn(self, contract, name, env, local_names, expr_lets=None, conds=(),
                     let_names=None, hoist_policy=None):
        self.conds = list(conds)
        self.reasons = {}
        self.input_map = env
        self.input_names = set(v for v in env.values() if isinstance(v, str))
        self.local_names = local_names
        self.let_names = {k: list(v) for k, v in (let_names or {}).items()}
        self.hoist_used = {}
        self.hoist_bound = {}
        self.hoist_policy = dict(hoist_policy or {})
        self.in_require_arg = 0
        self.self_idx_alias = None
        self.let_values = {}
        self.expr_let_table = {}
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
