"""Q2 and Q1 (I40) on the laws of a holon-facts/0.1 codec document (facts/morph_header.json), following the compiled
model holon.gen.model generates from it, term for term:

  * the header is one 32-bit cell per byte (queries keep the cells byte-valued: the witness format writes bytes);
  * a Go encoder (go-bytes) is zeros(length) with its ops put in order; a Solidity encoder dispatches on the version
    byte: a version it handles is memory of evm_memory_size cells of 57005 (unwritten) with its ops put, then the
    first length_by_version[v] cells; any other version is [57005];
  * put(mem, off, bs) overwrites from off and keeps the length of mem;
  * a predicate reads its rules on the first byte (the empty input has its own rule); a decoder is Some of the getter
    slices its version selects when its guard accepts, else None; a projection lists the fields its version selects.

Equality is the model's: bytes by length and cells; field lists by count and each field; Maybe by definedness.
"""
from __future__ import annotations

from .. import facts as F
from .encode import Query, band, bnot, bor, eq, ite, lit

UNDEF = 57005


def w32(v: int) -> str:
    return lit(v, 32)


class Bs:
    def __init__(self, n, cells: list[str]):
        self.n, self.cells = n, cells      # n: an int (fixed length) or a 32-bit term


def _n(x) -> str:
    return w32(x) if isinstance(x, int) else x


def eq_bytes(a: Bs, b: Bs) -> str:
    if isinstance(a.n, int) and isinstance(b.n, int):
        if a.n != b.n:
            return "false"
        return band(*[eq(x, y) for x, y in zip(a.cells[:a.n], b.cells[:b.n]) if x != y])
    top = max(len(a.cells), len(b.cells))
    parts = [eq(_n(a.n), _n(b.n))]
    for i in range(top):
        x = a.cells[i] if i < len(a.cells) else w32(0)
        y = b.cells[i] if i < len(b.cells) else w32(0)
        if x != y:
            parts.append(f"(or (bvule {_n(a.n)} {w32(i)}) {eq(x, y)})")
    return band(*parts)


class Fields:
    """A field list whose shape depends on the version: alternatives [(cond, [Bs])]."""

    def __init__(self, alts: list):
        self.alts = alts


class Mb:
    def __init__(self, d: str, v):
        self.d, self.v = d, v


def eq_fields(a: Fields, b: Fields) -> str:
    out = []
    for ca, la in a.alts:
        for cb, lb in b.alts:
            if len(la) != len(lb):
                continue
            out.append(band(ca, cb, *[eq_bytes(x, y) for x, y in zip(la, lb)]))
    return bor(*out)


class Model:
    def __init__(self, facts: dict, q: Query, maxlen: int):
        self.facts, self.q, self.maxlen = facts, q, maxlen
        self.w = F.widths(facts)

    def header(self, name: str) -> dict:
        out = {}
        for f in F.header_fields(self.facts):
            cells = []
            for k in range(int(f["width"])):
                c = self.q.const(f"h_{name}_{f['name']}_{k}", "(_ BitVec 32)")
                self.q.add(f"(bvult {c} {w32(256)})")
                cells.append(c)
            out[f["name"]] = cells
        return out

    def bytes_binder(self, name: str) -> Bs:
        n = self.q.const(f"n_{name}", "(_ BitVec 32)")
        self.q.add(f"(bvule {n} {w32(self.maxlen)})")
        cells = []
        for i in range(self.maxlen):
            c = self.q.const(f"b_{name}_{i}", "(_ BitVec 32)")
            self.q.add(f"(bvult {c} {w32(256)})")
            cells.append(c)
        return Bs(n, cells)

    # -------------------------------------------------------------- functions
    def _put(self, mem: list, off: int, cells: list) -> list:
        out = list(mem)
        for i, c in enumerate(cells):
            if off + i < len(out):
                out[off + i] = c
        return out

    def _cells(self, op: dict, h: dict) -> list[str]:
        out = []
        for c in F.src_cells(op["src"], self.w):
            if c[0] == "field":
                out.append(h[c[1]][int(c[2])])
            elif c[0] == "const":
                out.append(w32(int(c[1])))
            else:
                raise ValueError(f"cell {c}")
        return out

    def encoder(self, fn: str, h: dict) -> Bs:
        f = self.facts["functions"][fn]
        if f["lang"] == "go-bytes":
            mem = [w32(0)] * int(f["length"])
            for op in f["ops"]:
                mem = self._put(mem, int(op["offset"]), self._cells(op, h))
            return Bs(len(mem), mem)
        versions = F.encoder_versions(f)
        size = F.evm_memory_size(f, self.w)
        v = h["version"][0]
        alts = []
        for ver in versions:
            mem = [w32(UNDEF)] * size
            for op in f["ops"]:
                if F.when_ok(op.get("when"), ver):
                    mem = self._put(mem, int(op["offset"]), self._cells(op, h))
            mem = mem[:int(f["length_by_version"][str(ver)])]
            alts.append((eq(v, w32(ver)), mem))
        top = max(len(m) for _, m in alts)
        n = w32(1)
        cells = [w32(UNDEF)] + [w32(0)] * (top - 1)
        for c, m in reversed(alts):
            n = ite(c, w32(len(m)), n)
            cells = [ite(c, m[i] if i < len(m) else w32(0), cells[i]) for i in range(top)]
        return Bs(self.q.define(n, "(_ BitVec 32)", "en"), [self.q.define(x, "(_ BitVec 32)", "ec") for x in cells])

    def predicate(self, fn: str, b: Bs) -> str:
        """holon.gen.model.gen_predicate: the empty input takes its rule; otherwise the first rule, in order, whose
        version_in holds the first byte, or the first "otherwise"."""
        rules = self.facts["functions"][fn]["rules"]
        n = _n(b.n)
        empty = next(r for r in rules if r["if"] in ("empty", "otherwise"))
        if not isinstance(empty["then"], bool):
            raise ValueError(f"{fn}: the empty-input rule must be a constant")
        ver = b.cells[0]
        chain, rest = [], "false"
        for r in rules:
            c = r["if"]
            if c == "empty":
                continue
            if c == "otherwise":
                rest = self._then(r["then"], n)
                break
            chain.append((bor(*[eq(ver, w32(int(x))) for x in c["version_in"]]), self._then(r["then"], n)))
        res = rest
        for c, v in reversed(chain):
            res = ite(c, v, res)
        return self.q.define(ite(f"(= {n} {w32(0)})", "true" if empty["then"] else "false", res), "Bool", "pr")

    @staticmethod
    def _then(then, n: str) -> str:
        if isinstance(then, bool):
            return "true" if then else "false"
        if set(then) == {"len_ge"}:
            return f"(bvuge {n} {w32(int(then['len_ge']))})"
        if set(then) == {"len_eq"}:
            return eq(n, w32(int(then["len_eq"])))
        raise ValueError(f"rule result {then}")

    def _slice(self, b: Bs, off: int, w: int) -> Bs:
        cells = [b.cells[off + i] if off + i < len(b.cells) else w32(0) for i in range(w)]
        n = _n(b.n)
        ln = self.q.define(ite(f"(bvuge {n} {w32(off + w)})", w32(w),
                               ite(f"(bvuge {n} {w32(off)})", f"(bvsub {n} {w32(off)})", w32(0))),
                           "(_ BitVec 32)", "sl")
        return Bs(ln, cells)

    def decoder(self, fn: str, b: Bs) -> Mb:
        f = self.facts["functions"][fn]
        ok = self.predicate(f["guard"], b)
        getters = f["getters"]
        k = max([g["when"]["version_ge"] if g.get("when") else 0 for g in getters] + [0])
        ver = b.cells[0]
        alts = []
        for v in range(k + 2):
            gs = [self._slice(b, int(g["offset"]), int(g["width"])) for g in getters if F.when_ok(g.get("when"), v)]
            c = eq(ver, w32(v)) if v <= k else f"(bvugt {ver} {w32(k)})"
            alts.append((c, gs))
        return Mb(ok, Fields(alts))

    def projection(self, fn: str, h: dict) -> Fields:
        f = self.facts["functions"][fn]
        when = f.get("when", {})
        k = max([when[n]["version_ge"] if when.get(n) else 0 for n in f["order"]] + [0])
        ver = h["version"][0]
        alts = []
        for v in range(k + 2):
            items = [Bs(len(h[n]), h[n]) for n in f["order"] if F.when_ok(when.get(n), v)]
            c = eq(ver, w32(v)) if v <= k else f"(bvugt {ver} {w32(k)})"
            alts.append((c, items))
        return Fields(alts)

    def call(self, fn: str, args: list):
        kind = self.facts["functions"][fn]["kind"]
        return {"encoder": self.encoder, "predicate": self.predicate, "decoder": self.decoder,
                "projection": self.projection}[kind](fn, args[0])

    # -------------------------------------------------------------- terms
    def term(self, t, env: dict):
        if set(t) == {"var"}:
            return env[t["var"]]
        if set(t) == {"bytes"}:
            bs = bytes.fromhex(t["bytes"][2:])
            return Bs(len(bs), [w32(x) for x in bs])
        if set(t) == {"bool"}:
            return "true" if t["bool"] else "false"
        if set(t) == {"field", "of"}:
            cells = env[t["of"]["var"]][t["field"]]
            return Bs(len(cells), cells)
        if set(t) == {"call", "args"}:
            return self.call(t["call"], [self.term(a, env) for a in t["args"]])
        if set(t) == {"some"}:
            return Mb("true", self.term(t["some"], env))
        raise ValueError(f"term {t}")

    def equal(self, a, b) -> str:
        if isinstance(a, Mb) and isinstance(b, Mb):
            inner = self.equal(a.v, b.v)
            return band(eq(a.d, b.d) if (a.d, b.d) != ("true", "true") else "true", f"(=> {a.d} {inner})")
        if isinstance(a, Fields) and isinstance(b, Fields):
            return eq_fields(a, b)
        if isinstance(a, Bs) and isinstance(b, Bs):
            return eq_bytes(a, b)
        return eq(a, b)


def law_query(facts: dict, law: dict, rlimit: int, maxlen: int, template: dict | None = None):
    q = Query(rlimit)
    m = Model(facts, q, maxlen)
    st = law["statement"]
    binders = st.get("binders") or st.get("forall") or []
    env, dec = {}, {}
    for b in binders:
        if b["type"] == "Bytes":
            env[b["name"]] = m.bytes_binder(b["name"])
            dec[b["name"]] = ("bytes", env[b["name"]])
        else:
            env[b["name"]] = m.header(b["name"])
            dec[b["name"]] = ("record", env[b["name"]])
    for p in st.get("assume") or []:
        a, b = (m.term(x, env) for x in p["eq"])
        q.add(m.equal(a, b))
    a, b = (m.term(x, env) for x in st["claim"]["eq"])
    q.add(bnot(m.equal(a, b)))
    q.notes = [f"law {law['law_id']}: premises asserted, claim negated, over the 0.1 document's compiled model"]
    if template:
        if "diff_positions" in template:
            for i in template["diff_positions"]:
                ca = a.cells[i] if isinstance(a, Bs) and i < len(a.cells) else w32(UNDEF)
                cb = b.cells[i] if isinstance(b, Bs) and i < len(b.cells) else w32(UNDEF)
                q.add(bnot(band(f"(bvult {w32(i)} {_n(a.n)})", f"(bvult {w32(i)} {_n(b.n)})", eq(ca, cb))))
        if "version_byte" in template:
            bb = next(v for k, v in dec.values() if k == "bytes")
            q.add(f"(bvult {w32(0)} {bb.n})")
            q.add(eq(bb.cells[0], w32(int(template["version_byte"]))))
            q.add(a if template["lhs"] else bnot(a))
            q.add(b if template["rhs"] else bnot(b))
        q.notes.append(f"template: {sorted(template)}")
    dec["@sides"] = ("sides", (a, b))
    return q, dec


def decode(sess, dec: dict) -> dict:
    out = {}
    for name, (kind, v) in sorted(dec.items()):
        if kind == "sides":
            continue
        if kind == "record":
            terms = [c for cells in v.values() for c in cells]
            vals = sess.values(terms)
            out[name] = {f: "0x" + bytes(vals[c] for c in cells).hex() for f, cells in v.items()}
        else:
            n = sess.values([v.n])[v.n]
            vals = sess.values(v.cells[:n]) if n else {}
            out[name] = "0x" + bytes(vals[c] for c in v.cells[:n]).hex()
    return out


def side_values(sess, dec: dict) -> tuple:
    a, b = dec["@sides"][1]

    def one(x):
        if isinstance(x, Bs):
            n = x.n if isinstance(x.n, int) else sess.values([x.n])[x.n]
            vals = sess.values(x.cells[:n]) if n else {}
            return "0x" + "".join("%02x" % vals[c] if vals[c] < 256 else "??" for c in x.cells[:n])
        if isinstance(x, str):
            return bool(sess.values([x])[x]) if x not in ("true", "false") else x == "true"
        return None
    return one(a), one(b)
