"""Q2 (I40): the solver on a linked codec component's laws (holon-linked/0.1 documents, gen/<M>/codec/<role>.json;
holon.gen.linked compiles the same document to the model the laws are decided on).

The encoding follows the compiled model's semantics (holon.gen.linked, module docstring) term for term:
  * a record carrier is one 32-bit cell per byte (the witness format writes bytes, so the query's cells are < 256);
  * byte strings are a length and a list of 32-bit cells; a binder of the linked byte carrier has a symbolic length of
    at most byte_length_max and byte-valued cells;
  * an encoder is its layout, dispatched on its one-byte tag field when it has several (an unlisted tag: [57005]);
  * a decoder is Some(slice(b, offset, width)) when one of its ok paths holds on the length and the tag byte, else None;
    a predicate is that Bool; a loader's ok_<L> its domain predicate and L(b) = Some b when it holds;
  * equality of two sides is the model's: bytes by length and cells, Maybe by definedness then bytes, Bool by value.
The query asserts the premises and the negated claim; sat is a candidate witness (decoded in the witness format of the
records), which counts only through holon.gen.linked's counter-law, checked by Bend and BendTT.
"""
from __future__ import annotations

from .encode import Query, band, bnot, bor, eq, ite, lit

UNDEF = 57005


def w32(v: int) -> str:
    return lit(v, 32)


class Bs:
    """A byte list: n (a 32-bit term), cells (32-bit terms, the first len(cells) positions), nmax."""

    def __init__(self, n: str, cells: list[str]):
        self.n, self.cells = n, cells


class Mb:
    def __init__(self, d: str, v: Bs):
        self.d, self.v = d, v


def eq_bytes(a: Bs, b: Bs) -> str:
    top = max(len(a.cells), len(b.cells))
    parts = [eq(a.n, b.n)]
    for i in range(top):
        x = a.cells[i] if i < len(a.cells) else w32(0)
        y = b.cells[i] if i < len(b.cells) else w32(0)
        if x == y:
            continue
        parts.append(f"(or (bvule {a.n} {w32(i)}) {eq(x, y)})")
    return band(*parts)


class Codec:
    def __init__(self, doc: dict, q: Query, maxlen: int):
        self.doc, self.q, self.maxlen = doc, q, maxlen
        self.carriers = {k: v for k, v in doc["carriers"].items() if v.get("kind") == "record"}

    # ---------------------------------------------------------- binders
    def record(self, name: str, t: str) -> dict:
        out = {}
        for fl in self.carriers[t]["fields"]:
            cells = []
            for k in range(int(fl["width"])):
                c = self.q.const(f"r_{name}_{_ident(fl['name'])}_{k}", "(_ BitVec 32)")
                self.q.add(f"(bvult {c} {w32(256)})")
                cells.append(c)
            out[fl["name"]] = cells
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

    # ---------------------------------------------------------- functions
    def call(self, fn: str, args: list):
        if fn.startswith("ok_") and fn[3:] in self.doc["functions"]:
            f = self.doc["functions"][fn[3:]]
            return self.cond(f["ok"], args[0], sol=True)
        f = self.doc["functions"][fn]
        k = f["kind"]
        if k == "encoder":
            return self.encode(f, args[0])
        if k == "decoder":
            b = args[0]
            ok = self.cond(f["ok"], b, sol=False)
            rd = f["read"]
            off, w = int(rd["offset"]), int(rd["width"])
            cells = [b.cells[off + i] if off + i < len(b.cells) else w32(0) for i in range(w)]
            # slice(b, off, w): the w cells from off, fewer when b is shorter
            n = self.q.define(ite(f"(bvuge {b.n} {w32(off + w)})", w32(w),
                                  ite(f"(bvuge {b.n} {w32(off)})", f"(bvsub {b.n} {w32(off)})", w32(0))),
                              "(_ BitVec 32)", "sl")
            return Mb(ok, Bs(n, cells))
        if k == "predicate":
            return self.cond(f["ok"], args[0], sol=False)
        if k == "loader":
            ok = self.cond(f["ok"], args[0], sol=True)
            return Mb(ok, args[0])
        raise ValueError(f"function kind {k}")

    def encode(self, f: dict, rec: dict) -> Bs:
        lays = f["layouts"]

        def lay_cells(lay):
            out = []
            for item in lay:
                if item[0] == "const":
                    out.append(w32(int(item[1])))
                elif item[0] == "field":
                    out.append(rec[item[1]][int(item[2])])
                else:
                    raise ValueError(f"layout item {item}")
            return out
        if len(lays) == 1:
            cells = lay_cells(next(iter(lays.values())))
            return Bs(w32(len(cells)), cells)
        tag = self.tag_field(f)
        t = rec[tag][0]
        vs = sorted(int(v) for v in lays)
        options = [(eq(t, w32(v)), lay_cells(lays[str(v)])) for v in vs]
        n = w32(1)
        cells_n = max(len(c) for _, c in options)
        cells = [w32(UNDEF)] + [w32(0)] * (cells_n - 1)
        for c, cs in reversed(options):
            n = ite(c, w32(len(cs)), n)
            cells = [ite(c, cs[i] if i < len(cs) else w32(0), cells[i]) for i in range(cells_n)]
        return Bs(self.q.define(n, "(_ BitVec 32)", "en"), [self.q.define(x, "(_ BitVec 32)", "ec") for x in cells])

    def tag_field(self, f: dict) -> str:
        """The record's one-byte field at the document's tag index (holon.gen.linked.tag_field)."""
        from ..gen.linked import tag_field
        tf = tag_field(f, self.doc)
        if tf is None:
            raise ValueError("several layouts without a tag field")
        return tf

    def cond(self, paths: list, b: Bs, sol: bool) -> str:
        def term(e):
            if isinstance(e, bool):
                return "true" if e else "false"
            if isinstance(e, int):
                return w32(e)
            if isinstance(e, str):
                return b
            h = e[0]
            if h == "const":
                return w32(int(e[1]))
            if h == "param":
                return b
            if h == "len":
                return b.n
            if h in ("index", "byte"):
                # byte_at: byte k, or the sentinel 57005 past the end (never a byte)
                k = int(e[2]) if isinstance(e[2], int) else int(e[2][1])
                cell = b.cells[k] if k < len(b.cells) else w32(UNDEF)
                return ite(f"(bvult {w32(k)} {b.n})", cell, w32(UNDEF))
            if h == "!":
                return bnot(boolean(e[1]))
            if h == "&&":
                return band(*[boolean(x) for x in e[1:]])
            if h == "||":
                return bor(*[boolean(x) for x in e[1:]])
            x, y = term(e[1]), term(e[2])
            ops = {"==": eq(x, y), "!=": bnot(eq(x, y)), "<": f"(bvult {x} {y})", "<=": f"(bvule {x} {y})",
                   ">": f"(bvugt {x} {y})", ">=": f"(bvuge {x} {y})"}
            return ops[h]

        def boolean(e):
            v = term(e)
            if isinstance(v, Bs):
                raise ValueError("a byte string as a condition")
            return v
        return self.q.define(bor(*[band(*[boolean(c) for c in p]) for p in paths]), "Bool", "ok")

    # ---------------------------------------------------------- IR terms
    def term(self, t, env: dict, types: dict):
        if set(t) == {"var"}:
            return env[t["var"]]
        if set(t) == {"bytes"}:
            bs = bytes.fromhex(t["bytes"][2:])
            return Bs(w32(len(bs)), [w32(x) for x in bs])
        if set(t) == {"bool"}:
            return "true" if t["bool"] else "false"
        if set(t) == {"field", "of"}:
            cells = env[t["of"]["var"]][t["field"]]
            return Bs(w32(len(cells)), cells)
        if set(t) == {"call", "args"}:
            return self.call(t["call"], [self.term(a, env, types) for a in t["args"]])
        if set(t) == {"some"}:
            return Mb("true", self.term(t["some"], env, types))
        raise ValueError(f"term {t}")

    def equal(self, a, b) -> str:
        if isinstance(a, Mb) or isinstance(b, Mb):
            if not (isinstance(a, Mb) and isinstance(b, Mb)):
                raise ValueError("a Maybe compared with a value")
            return band(eq(a.d, b.d) if a.d not in ("true", "false") or b.d not in ("true", "false")
                        else ("true" if a.d == b.d else "false"),
                        f"(=> {a.d} {eq_bytes(a.v, b.v)})")
        if isinstance(a, Bs) and isinstance(b, Bs):
            return eq_bytes(a, b)
        return eq(a, b)


def _ident(s: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in s)


def law_query(doc: dict, law: dict, rlimit: int, maxlen: int, template: dict | None = None) -> tuple[Query, dict]:
    """The query of a law's negation over the component (premises asserted, the claim negated) and how to decode a
    model: {binder: ("record", {field: cells}) | ("bytes", Bs)}."""
    q = Query(rlimit)
    c = Codec(doc, q, maxlen)
    st = law["statement"]
    env, dec = {}, {}
    types = {b["name"]: b["type"] for b in st["binders"]}
    for b in st["binders"]:
        if b["type"] == doc.get("linked_carrier") or doc["carriers"].get(b["type"], {}).get("kind") == "bytes":
            env[b["name"]] = c.bytes_binder(b["name"])
            dec[b["name"]] = ("bytes", env[b["name"]])
        else:
            env[b["name"]] = c.record(b["name"], b["type"])
            dec[b["name"]] = ("record", env[b["name"]])
    for p in st.get("assume") or []:
        a, b = (c.term(x, env, types) for x in p["eq"])
        q.add(c.equal(a, b))
    a, b = (c.term(x, env, types) for x in st["claim"]["eq"])
    q.add(bnot(c.equal(a, b)))
    q.notes = [f"law {law['law_id']}: premises asserted, claim negated, over {doc.get('component')}"]
    if template:
        # a witness class's template (Q1): the class's differing byte positions differ (codec), or the version byte
        # and the two sides' verdicts are the class's (domain)
        if "diff_positions" in template:
            xa, xb = (x.v if isinstance(x, Mb) else x for x in (a, b))
            for i in template["diff_positions"]:
                ca = xa.cells[i] if i < len(xa.cells) else w32(UNDEF)
                cb = xb.cells[i] if i < len(xb.cells) else w32(UNDEF)
                q.add(bnot(band(f"(bvult {w32(i)} {xa.n})", f"(bvult {w32(i)} {xb.n})", eq(ca, cb))))
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
    """A model's binders in the witness format of the records ({field: "0x.."} or "0x..")."""
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
    """The model's two claim sides: bytes as hex (None for an undefined Maybe), Bools as bools."""
    a, b = dec["@sides"][1]

    def one(x):
        if isinstance(x, Mb):
            d = sess.values([x.d])[x.d] if x.d not in ("true", "false") else int(x.d == "true")
            return one(x.v) if d else None
        if isinstance(x, Bs):
            n = sess.values([x.n])[x.n]
            vals = sess.values(x.cells[:n]) if n else {}
            return "0x" + "".join("%02x" % (vals[c] & 0xFF) if vals[c] < 256 else "??" for c in x.cells[:n])
        return bool(sess.values([x])[x]) if x not in ("true", "false") else x == "true"
    return one(a), one(b)
