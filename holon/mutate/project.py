"""The projected header document (I61; the instrument's "projection"; contract: the "Projection" paragraph of
tests_m2/test_mutation_adequacy_i61.py).

    project(documents, header_facts, instrument=None) -> dict
    project_root(holon_root) -> dict
    python -m holon mutate project [--documents DIR] [--out PATH] [--check]

project composes the holon-facts/0.1 header document the 8 laws/M0 statements are decided on, from the extracted
documents of one source tree ({"spec/M2/facts/<name>.extracted.json": document}; the run passes every mutant's
re-extracted documents). types and functions.view are copied from the header facts (facts/morph_header.json: the
laws' binder type and the specification). Every other function of the header facts comes from the extracted document
its role names (instrument roles): a Solidity role from its edge (roles.solidity.<role>.edge), a Go role from the
functions the null mutant's names give it (roles.go.<role>.named), all of it read at run time, so this module names
nothing of the target.

The rules (instrument projection), as this module applies them:

  enc_sol (the encoder edge)  For every version v in 0..255 (the Header's 1-byte version field), the ok paths whose
      conditions are not false at v once every atom on another field is unknown (three-valued evaluation of the
      I17 DSL). The extracted version bound is domain.version_le, the largest such v. Each version up to it takes the
      length and ops of its ok paths (length_by_version; ops merged across versions in order, each op with a when:
      none when it runs at every version 0..version_le, {"version_ge": k} when its versions are those from k up,
      else {"version_in": [...]}). A version with no ok path, or whose ok paths disagree on length or ops (the bytes
      would then depend on unprojected fields), is undefined there: length 1 and no op (one unwritten, undefined
      byte, the M0 model's revert). An edge that is not exact (debt in its store sequences) has every cell
      undefined. A revert path whose failing condition (its last conjunct) names a field other than the version is
      not projected and is listed in the assumptions as P-unprojected:<edge>.
  cells  A field item {"field", "from", "len"} written with width w (the field's width in the extracted record: I17
      N1, shl(8k, v) gives w = 32 - k) is aligned big-endian onto the Header field of width W (the header facts):
      byte j of the w-byte value is byte W - w + j of the field, and the constant 0 when W - w + j < 0. A Go cell
      ["byte", T, k] of a receiver field (mapped to its Header field by the first word of that field's "go" text in
      the header facts, as I18 maps them) is byte k of the field: Go writes the field at its own width, which is the
      Header field's width W (the header facts declare each Header field as that Go field), so W - w + k = k
      (["byte_le", T, k]: byte W - 1 - k). A Solidity byte no op writes is undefined (memory_init dirty, A-dirty); a Go
      byte no op writes is 0 (the layout's ["const", 0]). A cell the projection cannot place (an unknown cell, a
      byte of a value that is not a mapped Header field) is undefined.
  enc_go_v0, enc_go_v1 (Go encoders)  The function's layout in go.codecs.encoders (result 0: the fresh buffer a
      nil-error path returns), as one copy of all its cells onto the zero buffer of its length. A function with no
      layout (missing, or every path panics or errs) projects to one undefined byte; layouts that disagree make the
      cells where they disagree undefined (or, with different lengths, one undefined byte).
  ok_sol (the loader edge) and ok_go (the Go predicate)  True exactly where some ok path (Solidity) or nil-error
      path (Go: end "return" with error "nil", or no error result) holds; a panicking path is not one, and a path
      whose condition reads an input byte past the end does not hold (Solidity's checked index reverts, Go's
      panics). The value on a non-empty input depends only on its first byte and its length when every length
      atom compares the length (or a Go capacity) with a constant: it is decided exactly on the lengths 1, 2, every
      constant c of the conditions with c - 1 and c + 1, and one length above them all (as holon.frontends.link
      probes a loader). Each version byte's accepted lengths become true, false, {"len_eq": k} or {"len_ge": k};
      versions with the same answer share one {"version_in": [...]} rule, and the answer at version 255 is the
      "otherwise" rule. The empty input is its own constant rule. Anything else (a condition this module cannot
      evaluate, lengths that are no such set, a Go predicate whose answer depends on the capacity) leaves the
      predicate without a holon-facts/0.1 form: MutateError.
  dec_go (the Go decoders, guarded by ok_go)  Getter i is the decoder roles.go.dec_go.named[i], named after the i-th
      field of view.order (the view lists the Header fields in getter order). Each nil-error path of the decoder
      whose returned value reads the input at constant offsets (a read go.codecs.decoders lists for it: b[k], or a
      constant slice b[lo:hi] under an integer or array conversion) gives one getter per (offset, width) read, with
      a when from the versions at which such a path and the guard both admit some input (the guard's own versions
      being every version: no when; a threshold within them: {"version_ge": k}; else {"version_in": [...]}). A
      decoder with no such path is an undefined getter {"name", "width": W, "undefined": true}, W its Header field's
      width.

Additive extensions of the M0 generator (holon.facts, holon.gen.model; refuter constants in holon.refute) carry the
forms the M0 facts language lacked: a when {"version_in": [...]}, a field cell slice, an undefined cell
({"undefined": n}) and an undefined getter. Where a role's function is missing or its paths cannot be projected,
the result is still deterministic, with undefined cells or getters (assumption P-undefined:<role>); MutateError is
raised only when a document itself is unusable (missing, malformed, not of its frontend) or a predicate has no
form. The output is canonical JSON (holon.mutate.common.dump); provenance (the documents read, their normalized
sha256) sits in the "extraction" block, which normalized_sha256 removes.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

from . import common as C

VERSION_FIELD = "version"   # the Header's version field: the holon-facts/0.1 convention (holon.gen.model)
SOL, GO = "solidity", "go"  # the instrument's role tables
VERSIONS = range(256)       # the values of the 1-byte version field
CMP = ("==", "!=", "<", "<=", ">", ">=")
EVM = 1 << 256
GO_INTS = {"uint8": (8, False), "byte": (8, False), "uint16": (16, False), "uint32": (32, False),
           "uint64": (64, False), "uint": (64, False), "uintptr": (64, False), "int8": (8, True),
           "int16": (16, True), "int32": (32, True), "int64": (64, True), "int": (64, True)}
UNDEFINED_VERSION = "undefined"


class _Cut(Exception):
    """A condition reads an input byte past the input's end: the execution stops there (revert or panic)."""


class _Inexact(Exception):
    """The probed lengths do not decide a condition exactly."""


# ------------------------------------------------------------------------------------------------ evaluation
def _cmp(op: str, a: int, b: int) -> bool:
    return {"==": a == b, "!=": a != b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]


def _holds(conds: list, atom) -> bool | None:
    """Three-valued conjunction: False when an atom is false or the path reads past the input, None when no atom
    is false and one is unknown, else True."""
    unknown = False
    try:
        for c in conds:
            r = atom(c)
            if r is None:
                unknown = True
            elif not r:
                return False
    except _Cut:
        return False
    return None if unknown else True


class _GoEnv:
    """A Go input: a byte slice parameter of length n, first byte v and capacity cap."""

    def __init__(self, param: str, n: int, v: int, cap: int):
        self.param, self.n, self.v, self.cap = param, n, v, cap

    def term(self, t):
        if not isinstance(t, list) or not t:
            return None
        tag = t[0]
        if tag == "const" and len(t) == 2 and type(t[1]) is int:
            return t[1]
        if tag == "bool" and len(t) == 2 and isinstance(t[1], bool):
            return int(t[1])
        if tag in ("len", "cap") and len(t) == 2:
            if t[1] == ["param", self.param]:
                return self.n if tag == "len" else self.cap
            return None
        if tag == "index" and len(t) == 3 and t[1] == ["param", self.param]:
            k = self.term(t[2])
            if k is None:
                return None
            if not 0 <= k < self.n:
                raise _Cut
            return self.v if k == 0 else None
        if tag == "op" and len(t) == 4:
            return _go_arith(t[1], self.term(t[2]), self.term(t[3]))
        if tag == "convert" and len(t) == 3:
            x, spec = self.term(t[2]), GO_INTS.get(t[1])
            if x is None or spec is None:
                return None
            bits, signed = spec
            x %= 1 << bits
            return x - (1 << bits) if signed and x >= 1 << (bits - 1) else x
        return None

    def atom(self, a):
        if not isinstance(a, list) or not a:
            return None
        if a[0] in ("true", "false") and len(a) == 2:
            x = self.term(a[1])
            return None if x is None else (bool(x) == (a[0] == "true"))
        if a[0] in CMP and len(a) == 3:
            x, y = self.term(a[1]), self.term(a[2])
            return None if x is None or y is None else _cmp(a[0], x, y)
        return None


def _go_arith(op: str, a, b):
    if a is None or b is None:
        return None
    if op in ("/", "%"):
        if b == 0:
            return None
        q = abs(a) // abs(b) * (1 if (a >= 0) == (b >= 0) else -1)
        return q if op == "/" else a - q * b
    if op in ("<<", ">>") and b < 0:
        return None
    table = {"+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b, "&": lambda: a & b, "|": lambda: a | b,
             "^": lambda: a ^ b, "<<": lambda: a << b if b < 4096 else None, ">>": lambda: a >> b,
             "&^": lambda: a & ~b}
    return table[op]() if op in table else None


class _SolEnv:
    """A Solidity input: field values (an encoder edge; a field missing here is unknown) or the loader's input of
    length n and first byte v."""

    def __init__(self, fields: dict | None = None, n: int | None = None, v: int | None = None):
        self.fields, self.n, self.v = fields or {}, n, v

    def expr(self, e):
        if isinstance(e, bool):
            return int(e)
        if isinstance(e, int):
            return e
        if isinstance(e, str):
            return self.fields.get(e)
        if not isinstance(e, list) or not e:
            return None
        op = e[0]
        if op == "len" and len(e) == 2 and isinstance(e[1], str):
            return self.n
        if op == "byte" and len(e) == 3 and isinstance(e[1], str) and type(e[2]) is int:
            if self.n is None:
                return None
            if not 0 <= e[2] < self.n:
                raise _Cut
            return self.v if e[2] == 0 else None
        args = [self.expr(x) for x in e[1:]]
        if op == "!" and len(args) == 1:
            return None if args[0] is None else int(not args[0])
        if op == "&&":
            if any(x == 0 for x in args):
                return 0
            return None if any(x is None for x in args) else 1
        if op == "||":
            if any(x is not None and x != 0 for x in args):
                return 1
            return None if any(x is None for x in args) else 0
        if len(args) != 2 or args[0] is None or args[1] is None:
            return None
        a, b = args
        if op in CMP:
            return int(_cmp(op, a, b))
        return _evm_arith(op, a, b)

    def atom(self, c):
        x = self.expr(c)
        return None if x is None else x != 0


def _evm_arith(op: str, a: int, b: int):
    a, b = a % EVM, b % EVM
    table = {"+": lambda: (a + b) % EVM, "-": lambda: (a - b) % EVM, "*": lambda: (a * b) % EVM,
             "/": lambda: a // b if b else 0, "%": lambda: a % b if b else 0, "&": lambda: a & b,
             "|": lambda: a | b, "^": lambda: a ^ b, "<<": lambda: (a << b) % EVM if b < 256 else 0,
             ">>": lambda: a >> b if b < 256 else 0}
    return table[op]() if op in table else None


def _ints(x, out: set) -> set:
    """Every integer constant inside a condition (bools excluded)."""
    if isinstance(x, list):
        for y in x:
            _ints(y, out)
    elif type(x) is int:
        out.add(x)
    return out


def _length_atoms_simple(conds: list, go: bool) -> bool:
    """Every length (and Go capacity) term is an operand of a comparison with a constant: probing the constants is
    then exact."""
    def is_len(t):
        return isinstance(t, list) and len(t) == 2 and t[0] in (("len", "cap") if go else ("len",))

    def is_const(t):
        return (isinstance(t, list) and len(t) == 2 and t[0] == "const" and type(t[1]) is int) if go \
            else type(t) is int

    def ok(e, parent):
        if is_len(e):
            return isinstance(parent, list) and len(parent) == 3 and parent[0] in CMP \
                and any(is_const(x) for x in parent[1:])
        if isinstance(e, list) and e:
            return all(ok(x, e) for x in (e[1:] if isinstance(e[0], str) else e))
        return True
    return all(ok(c, None) for c in conds)


def _probes(consts: set) -> list:
    ps = {1, 2} | {c + d for c in consts for d in (-1, 0, 1) if c + d >= 1}
    return sorted(ps) + [max(ps) + 2]


def _length_form(admitted: list, probes: list):
    """true, false, {"len_eq": k} or {"len_ge": k}: the lengths >= 1 the admitted probes stand for. _Inexact when the
    probes do not decide the set, ValueError when it has none of these forms."""
    acc = set(admitted)
    runs = []
    for i, p in enumerate(probes):
        if i and (p in acc) != (probes[i - 1] in acc) and p != probes[i - 1] + 1:
            raise _Inexact(f"lengths {probes[i - 1]} and {p} differ with untested lengths between them")
        if p in acc:
            if runs and runs[-1][1] == probes[i - 1] and probes[i - 1] in acc:
                runs[-1][1] = p
            else:
                runs.append([p, p])
    if not runs:
        return False
    if len(runs) == 1:
        lo, hi = runs[0]
        if hi == probes[-1]:
            return True if lo == 1 else {"len_ge": lo}
        if lo == hi:
            return {"len_eq": lo}
    raise ValueError(f"accepted lengths {sorted(acc)} among the probes {probes}")


# ------------------------------------------------------------------------------------------------ predicates
class _Predicate:
    """A predicate role on byte strings: admit(n, v) on a non-empty input of length n and first byte v, empty() on
    the empty input, the versions it accepts some length at, and its holon-facts/0.1 rules."""

    def __init__(self, paths: list, env, consts: set, what: str, cap_free: bool = False):
        self.paths, self.env, self.what, self.cap_free = paths, env, what, cap_free
        self.probes = _probes(consts)
        self._memo: dict = {}

    def admit(self, n: int, v: int) -> bool:
        key = (n, v)
        if key not in self._memo:
            got = self._admit(n, v, n)
            if self.cap_free and got != self._admit(n, v, n + self.probes[-1]):
                raise C.MutateError(f"{self.what}: its answer at length {n}, first byte {v} depends on the capacity,"
                                    f" which a holon-facts/0.1 predicate cannot express")
            self._memo[key] = got
        return self._memo[key]

    def _admit(self, n: int, v: int, cap: int) -> bool:
        unknown = False
        for p in self.paths:
            r = _holds(p, self.env(n, v, cap).atom)
            if r is True:
                return True
            unknown = unknown or r is None
        if unknown:
            raise C.MutateError(f"{self.what}: a path condition cannot be evaluated at length {n}, first byte {v}")
        return False

    def versions(self) -> list:
        return [v for v in VERSIONS if any(self.admit(n, v) for n in self.probes)]

    def rules(self) -> list:
        forms = []
        for v in VERSIONS:
            try:
                forms.append(_length_form([n for n in self.probes if self.admit(n, v)], self.probes))
            except (_Inexact, ValueError) as e:
                raise C.MutateError(f"{self.what}: version byte {v} has no holon-facts/0.1 rule ({e})") from None
        other = forms[-1]
        key = lambda f: C.compact(f)  # noqa: E731
        top = max((v for v in VERSIONS if key(forms[v]) != key(other)), default=-1)
        groups: dict = {}
        for v in range(top + 1):
            if key(forms[v]) != key(other):
                groups.setdefault(key(forms[v]), (forms[v], []))[1].append(v)
        rules = [{"if": "empty", "then": self.admit_empty()}]
        rules += [{"if": {"version_in": vs}, "then": f} for f, vs in sorted(groups.values(), key=lambda g: g[1][0])]
        return rules + [{"if": "otherwise", "then": other}]

    def admit_empty(self) -> bool:
        return self._admit(0, 0, 0)


def _sol_loader(edge: dict, what: str) -> _Predicate:
    oks = [p.get("cond") or [] for p in edge.get("paths") or [] if p.get("outcome") == "ok"]
    if not _length_atoms_simple([c for cs in oks for c in cs], go=False):
        raise C.MutateError(f"{what}: a length atom is not a comparison with a constant")
    return _Predicate(oks, lambda n, v, cap: _SolEnv(n=n, v=v), _ints(oks, set()), what)


def _nil_error(fn: dict, path: dict) -> bool:
    """A Go path that returns with a nil error (or returns, when the function has no error result)."""
    if path.get("end") != "return":
        return False
    has_error = bool(fn.get("results")) and fn["results"][-1] == "error"
    return path.get("error") == "nil" if has_error else path.get("error") is None


def _byte_param(fn: dict) -> str | None:
    ps = fn.get("params") or []
    return ps[0].get("name") if ps else None


def _go_predicate(doc: dict, fid: str, what: str) -> _Predicate:
    fn = _go_functions(doc).get(fid)
    if fn is None or fn.get("paths") is None:
        why = "missing" if fn is None else f"without paths ({fn.get('paths_reason')})"
        raise C.MutateError(f"{what}: the predicate {fid} is {why}; a predicate has no undefined form")
    conds = [p.get("cond") or [] for p in fn["paths"] if _nil_error(fn, p)]
    if not _length_atoms_simple([c for cs in conds for c in cs], go=True):
        raise C.MutateError(f"{what}: a length atom of {fid} is not a comparison with a constant")
    param = _byte_param(fn)
    return _Predicate(conds, lambda n, v, cap: _GoEnv(param, n, v, cap), _ints(conds, set()), what, cap_free=True)


# ------------------------------------------------------------------------------------------------ cells and items
def _items(cells: list, widths: dict) -> list:
    """Op source items of a cell list: runs of one field's consecutive bytes ({"field"} for the whole field in order,
    else a slice {"field", "from", "len"}), {"zeros": n}, {"const": b}, {"undefined": n}."""
    items: list = []
    for c in cells:
        last = items[-1] if items else None
        if c[0] == "const" and c[1] == 0:
            if last is not None and "zeros" in last:
                last["zeros"] += 1
            else:
                items.append({"zeros": 1})
        elif c[0] == "const":
            items.append({"const": c[1]})
        elif c[0] == "field":
            if last is not None and last.get("field") == c[1] and last["from"] + last["len"] == c[2]:
                last["len"] += 1
            else:
                items.append({"field": c[1], "from": c[2], "len": 1})
        else:
            if last is not None and "undefined" in last:
                last["undefined"] += 1
            else:
                items.append({"undefined": 1})
    for it in items:
        if "field" in it and it["from"] == 0 and it["len"] == widths[it["field"]]:
            del it["from"], it["len"]
    return items


def _sol_cells(op: dict, record: dict, widths: dict) -> list | None:
    """The cells of an extracted store op aligned onto the Header (module docstring, cells); None when the op is not
    a store of field, zero and constant items."""
    if op.get("op") not in ("mstore", "mstore8") or type(op.get("offset")) is not int or op["offset"] < 0:
        return None
    cells: list = []
    for it in op.get("src") or []:
        if "field" in it:
            a, n = it.get("from", 0), it.get("len")
            if type(a) is not int or type(n) is not int or a < 0 or n < 0:
                return None
            big, w = widths.get(it["field"]), record.get(it["field"])
            for j in range(a, a + n):
                if big is None or w is None or j >= w:
                    cells.append(["unknown"])
                    continue
                k = big - w + j
                cells.append(["const", 0] if k < 0 else ["field", it["field"], k])
        elif "zeros" in it and type(it["zeros"]) is int and it["zeros"] >= 0:
            cells += [["const", 0]] * it["zeros"]
        elif "const" in it and type(it["const"]) is int and 0 <= it["const"] <= 255:
            cells.append(["const", it["const"]])
        else:
            return None
    return cells


def _field_chain(t, params: list):
    """["field", ["field", ["param", p], a], b] -> [a, b] for a parameter p; None otherwise."""
    names = []
    while isinstance(t, list) and len(t) == 3 and t[0] == "field" and isinstance(t[2], str):
        names.append(t[2])
        t = t[1]
    if not (isinstance(t, list) and len(t) == 2 and t[0] == "param" and t[1] in params) or not names:
        return None
    return list(reversed(names))


def _go_cell(c, params: list, go_fields: dict, widths: dict) -> list:
    if isinstance(c, list) and len(c) == 2 and c[0] == "const" and type(c[1]) is int and 0 <= c[1] <= 255:
        return ["const", c[1]]
    if isinstance(c, list) and len(c) == 3 and c[0] in ("byte", "byte_le") and type(c[2]) is int:
        chain = _field_chain(c[1], params)
        name = go_fields.get(chain[-1]) if chain else None
        if name is not None:
            big = widths[name]
            k = c[2] if c[0] == "byte" else big - 1 - c[2]
            if 0 <= k < big:
                return ["field", name, k]
    return ["unknown"]


def go_field_map(header_facts: dict) -> dict:
    """{Go field name: Header field}: the first word of each Header field's "go" text in the header facts (I18's
    map)."""
    out: dict = {}
    for f in header_facts["types"]["Header"]["fields"]:
        words = str(f.get("go") or "").split()
        if words and re.fullmatch(r"[A-Za-z_]\w*", words[0]):
            if words[0] in out:
                raise C.MutateError(f"the header facts give the Go field {words[0]} to two Header fields")
            out[words[0]] = f["name"]
    return out


# ------------------------------------------------------------------------------------------------ the roles
def _when(versions: list, universe: list):
    """None (every version of the universe), {"version_ge": k} (a threshold within it) or {"version_in": [...]}."""
    vs = sorted(versions)
    if vs == sorted(universe):
        return None
    if vs and vs == [x for x in sorted(universe) if x >= vs[0]]:
        return {"version_ge": vs[0]}
    return {"version_in": vs}


def _merge(seqs: dict, top: int) -> list:
    """One op list for every version 0..top: each version's ops a subsequence, in its order; each op with its when."""
    merged: list = []  # [key, op, versions]
    for v in range(top + 1):
        pos = 0
        for op in seqs.get(v, []):
            key = C.compact(op)
            j = next((i for i in range(pos, len(merged)) if merged[i][0] == key), None)
            if j is None:
                merged.insert(pos, [key, op, set()])
                j = pos
            merged[j][2].add(v)
            pos = j + 1
    out = []
    for _, op, vs in merged:
        w = _when(vs, list(range(top + 1)))
        out.append({**op, "when": w} if w else dict(op))
    return out


def _names(e) -> set:
    """The field names a DSL condition reads."""
    if isinstance(e, str):
        return {e}
    if isinstance(e, list) and e and e[0] not in ("len", "byte"):
        return set().union(*[_names(x) for x in e[1:]]) if len(e) > 1 else set()
    return set()


def _sol_encoder(doc: dict, edge_name: str, base: dict, widths: dict, role: str):
    """(function, assumptions) of the encoder edge (module docstring, enc_sol)."""
    notes = []
    edge = (doc.get("functions") or {}).get(edge_name)
    f = {**base, "lang": "solidity-evm-memory", "memory_init": "dirty"}
    if not isinstance(edge, dict):
        notes.append({"id": f"P-undefined:{role}", "text": f"the document has no edge {edge_name}: every byte is "
                      f"undefined"})
        return {**f, "domain": {"version_le": 0}, "length_by_version": {"0": 1}, "ops": []}, notes
    f["lang"], f["memory_init"] = edge.get("lang", f["lang"]), edge.get("memory_init", f["memory_init"])
    rec = (doc.get("types") or {}).get(edge.get("from")) or {}
    record = {x["name"]: x["width"] for x in rec.get("fields") or [] if isinstance(x, dict) and "name" in x}
    paths = edge.get("paths") or []
    oks = [p for p in paths if p.get("outcome") == "ok"]
    exact = edge.get("exact") is True
    seen: dict = {}

    def behaviour(i: int):
        if i not in seen:
            p = oks[i]
            ops = [_sol_cells(op, record, widths) for op in p.get("ops") or []]
            if type(p.get("length")) is not int or p["length"] < 0 or any(c is None for c in ops):
                seen[i] = UNDEFINED_VERSION
            else:
                seen[i] = C.compact([p["length"], [{"op": op["op"], "offset": op["offset"],
                                                    "src": _items(cs, widths)}
                                                   for op, cs in zip(p.get("ops") or [], ops)]])
        return seen[i]

    per_v = {}
    for v in VERSIONS:
        env = _SolEnv(fields={VERSION_FIELD: v})
        cands = [i for i, p in enumerate(oks) if _holds(p.get("cond") or [], env.atom) is not False]
        if cands:
            bs = {behaviour(i) for i in cands}
            per_v[v] = bs.pop() if len(bs) == 1 and exact else UNDEFINED_VERSION
    top = max(per_v, default=0)
    lengths, seqs, undefined = {}, {}, []
    for v in range(top + 1):
        b = per_v.get(v, UNDEFINED_VERSION)
        if b == UNDEFINED_VERSION:
            lengths[str(v)], seqs[v] = 1, []
            undefined.append(v)
        else:
            length, ops = json.loads(b)
            lengths[str(v)], seqs[v] = length, ops
    if undefined:
        why = "the edge is not exact (debt in a store sequence)" if not exact else \
            "no ok path, or ok paths that disagree on length or ops"
        notes.append({"id": f"P-undefined:{role}", "versions": undefined,
                      "text": f"versions {undefined}: {why}; the projection is one undefined byte there"})
    unproj = []
    for p in paths:
        last = (p.get("cond") or [None])[-1]
        if p.get("outcome") == "revert" and _names(last) - {VERSION_FIELD}:
            unproj.append({k: p[k] for k in ("cond", "reason", "src") if k in p})
    if unproj:
        notes.append({"id": f"P-unprojected:{edge_name}", "paths": unproj,
                      "text": f"revert conditions of {edge_name} on fields other than {VERSION_FIELD} are not "
                              f"projected: the encoder is defined at every version of its domain"})
    return {**f, "domain": {"version_le": top}, "length_by_version": lengths, "ops": _merge(seqs, top)}, notes


def _go_functions(doc: dict) -> dict:
    return ((doc.get("go") or {}).get("functions")) or {}


def _go_codecs(doc: dict, key: str) -> list:
    return [x for x in (((doc.get("go") or {}).get("codecs") or {}).get(key) or []) if isinstance(x, dict)]


def _undefined_encoder(base: dict, role: str, why: str):
    return ({**base, "lang": "go-bytes", "memory_init": "zeros", "length": 1,
             "ops": [{"op": "copy", "offset": 0, "src": [{"undefined": 1}]}]},
            [{"id": f"P-undefined:{role}", "text": f"{why}: the projection is one undefined byte"}])


def _go_encoder(doc: dict, fid: str, base: dict, go_fields: dict, widths: dict, role: str):
    """(function, assumptions) of a Go encoder role (module docstring)."""
    fn = _go_functions(doc).get(fid)
    if fn is None:
        return _undefined_encoder(base, role, f"the document has no function {fid}")
    lays = sorted({C.compact([e.get("length"), e.get("cells")]) for e in _go_codecs(doc, "encoders")
                   if e.get("function") == fid and e.get("result", 0) == 0})
    if not lays:
        return _undefined_encoder(base, role, f"{fid} has no layout (no nil-error path returns a fresh buffer)")
    lays = [json.loads(x) for x in lays]
    if len({x[0] for x in lays}) != 1 or type(lays[0][0]) is not int \
            or any(not isinstance(x[1], list) or len(x[1]) != x[0] for x in lays):
        return _undefined_encoder(base, role, f"{fid} has layouts of different lengths")
    length = lays[0][0]
    cells = [c[0] if all(C.compact(x) == C.compact(c[0]) for x in c) else ["unknown"]
             for c in zip(*[x[1] for x in lays])]
    params = [p.get("name") for p in fn.get("params") or []]
    mapped = [_go_cell(c, params, go_fields, widths) for c in cells]
    notes = []
    if len(lays) > 1:
        notes.append({"id": f"P-undefined:{role}", "text": f"{fid} has {len(lays)} layouts: the cells where they "
                                                          f"differ are undefined"})
    ops = [{"op": "copy", "offset": 0, "src": _items(mapped, widths)}] if length else []
    return {**base, "lang": "go-bytes", "memory_init": "zeros", "length": length, "ops": ops}, notes


def _reads(t, param: str, known: set) -> set:
    """The reads of the input parameter inside a returned value: b[k] -> (k, 1) and b[lo:hi] -> (lo, hi - lo), kept
    when go.codecs.decoders lists them for the function."""
    out: set = set()
    if isinstance(t, list) and t:
        p = ["param", param]
        if t[0] == "index" and len(t) == 3 and t[1] == p and isinstance(t[2], list) and t[2][:1] == ["const"]:
            out.add((t[2][1], 1))
        if t[0] == "slice" and len(t) >= 4 and t[1] == p:
            lo = 0 if t[2] is None else (t[2][1] if isinstance(t[2], list) and t[2][:1] == ["const"] else None)
            hi = t[3][1] if isinstance(t[3], list) and t[3][:1] == ["const"] else None
            if type(lo) is int and type(hi) is int and hi > lo:
                out.add((lo, hi - lo))
        for x in (t[1:] if isinstance(t[0], str) else t):  # a term's operands, or every element of a list of terms
            out |= _reads(x, param, known)
    return {r for r in out if r in known}


def _go_getters(doc: dict, fid: str, name: str, guard: _Predicate, universe: list) -> list:
    """The getters of one decoder (module docstring, dec_go); [] when it has none."""
    fn = _go_functions(doc).get(fid)
    if fn is None or fn.get("paths") is None:
        return []
    entries = [d for d in _go_codecs(doc, "decoders") if d.get("function") == fid]
    if len(entries) != 1:
        return []
    param = entries[0].get("param") or _byte_param(fn)
    known = {(r.get("offset"), r.get("width")) for r in entries[0].get("reads") or []}
    by_read: dict = {}
    for p in fn["paths"]:
        if _nil_error(fn, p) and p.get("returns"):
            for r in _reads(p["returns"][0], param, known):
                by_read.setdefault(r, []).append(p.get("cond") or [])
    conds = [c for cs in by_read.values() for c in cs]
    if not _length_atoms_simple([a for c in conds for a in c], go=True):
        return []
    probes = _probes(_ints(conds, set()) | set(guard.probes))
    out = []
    for (off, width), cs in sorted(by_read.items()):
        vs = [v for v in universe
              if any(guard.admit(n, v) and any(_holds(c, _GoEnv(param, n, v, cap).atom) is not False for c in cs)
                     for n in probes for cap in (n, n + probes[-1]))]
        if vs:
            g = {"name": name, "offset": off, "width": width}
            w = _when(vs, universe)
            out.append((vs[0], off, width, {**g, "when": w} if w else g))
    return [g for *_, g in sorted(out, key=lambda x: x[:3])]


def _go_decoder(doc: dict, fids: list, base: dict, order: list, widths: dict, guard: _Predicate, role: str):
    if len(fids) != len(order):
        raise C.MutateError(f"{role}: {len(fids)} decoders for the {len(order)} fields of the view")
    universe = guard.versions()
    getters, undefined = [], []
    for fid, name in zip(fids, order):
        gs = _go_getters(doc, fid, name, guard, universe)
        if not gs:
            gs = [{"name": name, "undefined": True, "width": widths[name]}]
            undefined.append(fid)
        getters += gs
    notes = [{"id": f"P-undefined:{role}", "decoders": undefined,
              "text": "decoders with no nil-error path that reads the input at constant offsets: their getters are "
                      "undefined"}] if undefined else []
    return {**base, "lang": "go", "getters": getters}, notes


# ------------------------------------------------------------------------------------------------ the document
def _role_tables(inst: dict) -> dict:
    roles = inst.get("roles") or {}
    if not isinstance(roles.get(SOL), dict) or not isinstance(roles.get(GO), dict):
        raise C.MutateError("the instrument has no roles.solidity and roles.go tables")
    return {SOL: roles[SOL], GO: roles[GO]}


def _document(documents: dict, path: str, frontend: str) -> dict:
    doc = documents.get(path)
    if not isinstance(doc, dict):
        raise C.MutateError(f"the document {path} is missing")
    ext = doc.get("extraction") or {}
    if doc.get("facts_version") != "holon-facts/0.3" or not isinstance(ext, dict) or ext.get("frontend") != frontend:
        raise C.MutateError(f"{path} is not a holon-facts/0.3 document of the {frontend} frontend")
    if frontend == GO and not isinstance(doc.get("go"), dict):
        raise C.MutateError(f"{path} has no go section")
    if frontend == SOL and not isinstance(doc.get("functions"), dict):
        raise C.MutateError(f"{path} has no functions")
    return doc


def project(documents: dict, header_facts: dict, instrument: dict | None = None) -> dict:
    """The holon-facts/0.1 header document of the extracted documents (module docstring). documents:
    {"spec/M2/facts/<name>.extracted.json": document}; header_facts: the parsed facts/morph_header.json; instrument:
    the parsed instrument (default: this checkout's)."""
    inst = instrument if instrument is not None else C.instrument()
    tables = _role_tables(inst)
    fns = header_facts["functions"]
    widths = {f["name"]: f["width"] for f in header_facts["types"]["Header"]["fields"]}
    if widths.get(VERSION_FIELD) != 1:
        raise C.MutateError(f"the header facts have no 1-byte {VERSION_FIELD} field")
    views = sorted(n for n, f in fns.items() if f.get("kind") == "projection")
    if len(views) != 1:
        raise C.MutateError(f"the header facts have {len(views)} projections, not one")
    order = fns[views[0]]["order"]
    go_fields = go_field_map(header_facts)
    read: dict = {}
    out: dict = {}
    notes: list = []
    predicates: dict = {}

    def doc_of(lang: str, role: str) -> dict:
        path = tables[lang][role].get("document")
        read[path] = _document(documents, path, lang)
        return read[path]

    def predicate(role: str) -> _Predicate:
        if role not in predicates:
            if role in tables[SOL]:
                d = doc_of(SOL, role)
                edge = (d.get("functions") or {}).get(tables[SOL][role].get("edge"))
                if not isinstance(edge, dict):
                    raise C.MutateError(f"{role}: the document has no edge {tables[SOL][role].get('edge')}; a "
                                        f"predicate has no undefined form")
                predicates[role] = _sol_loader(edge, role)
            elif role in tables[GO]:
                named = tables[GO][role].get("named") or []
                if len(named) != 1:
                    raise C.MutateError(f"{role}: the instrument names {len(named)} functions, not one")
                predicates[role] = _go_predicate(doc_of(GO, role), named[0], role)
            else:
                raise C.MutateError(f"{role}: no role of the instrument plays it")
        return predicates[role]

    for name in sorted(fns):
        f = fns[name]
        kind = f.get("kind")
        base = {"kind": kind, "from": f.get("from"), "to": f.get("to")}
        if kind == "projection":
            out[name] = copy.deepcopy(f)
        elif kind == "predicate":
            p = predicate(name)
            out[name] = {**base, "lang": SOL if name in tables[SOL] else GO, "rules": p.rules(),
                         "meaning": "true iff some ok (Solidity) or nil-error (Go) path of the role admits b"}
        elif kind == "encoder" and name in tables[SOL]:
            fn, ns = _sol_encoder(doc_of(SOL, name), tables[SOL][name].get("edge"), base, widths, name)
            out[name] = fn
            notes += ns
        elif kind == "encoder" and name in tables[GO]:
            named = tables[GO][name].get("named") or []
            if len(named) != 1:
                raise C.MutateError(f"{name}: the instrument names {len(named)} functions, not one")
            fn, ns = _go_encoder(doc_of(GO, name), named[0], base, go_fields, widths, name)
            out[name] = fn
            notes += ns
        elif kind == "decoder" and name in tables[GO]:
            guard = f.get("guard")
            fn, ns = _go_decoder(doc_of(GO, name), tables[GO][name].get("named") or [],
                                 {**base, "guard": guard}, order, widths, predicate(guard), name)
            fn["meaning"] = f"None unless {guard} accepts b, else the getters whose when holds, in order"
            out[name] = fn
            notes += ns
        else:
            raise C.MutateError(f"{name}: a {kind} with no projection rule for its role")
    assumptions = [{**a, "document": path} for path in sorted(read) for a in read[path].get("assumptions") or []
                   if isinstance(a, dict)]
    assumptions += sorted(notes, key=lambda a: a["id"])
    sol_docs = sorted(p for p in read if read[p].get("extraction", {}).get("frontend") == SOL)
    tgt = read[sol_docs[0]].get("target") if sol_docs else header_facts.get("target")
    return {"facts_version": "holon-facts/0.1",
            "target": {"repo": (tgt or {}).get("repo"), "commit": (tgt or {}).get("commit"),
                       "scope": "the M0 header roles, projected from the extracted documents (I61)"},
            "extraction": {"method": "projected", "by": "holon.mutate.project",
                           "inputs": [{"path": p, "normalized_sha256": C.normalized_sha256(read[p])}
                                      for p in sorted(read)],
                           "header_facts": {"path": C.HEADER_FACTS.as_posix(),
                                            "normalized_sha256": C.normalized_sha256(header_facts)}},
            "types": copy.deepcopy(header_facts["types"]),
            "functions": out,
            "assumptions": assumptions}


def documents_in(directory, instrument: dict) -> dict:
    """{"spec/M2/facts/<name>": document} of a documents directory: the documents the instrument's roles name and
    every Go document (*.go.extracted.json); the rollup transitions document is not read."""
    d = Path(directory)
    tables = _role_tables(instrument)
    names = {Path(r["document"]).name for t in tables.values() for r in t.values() if isinstance(r, dict)
             and isinstance(r.get("document"), str)}
    names |= {p.name for p in d.glob("*.go.extracted.json")}
    out = {}
    for n in sorted(names):
        p = d / n
        try:
            out[(C.FACTS2 / n).as_posix()] = C.load_json(p)
        except (OSError, ValueError) as e:
            raise C.MutateError(f"cannot read {p}: {e}") from None
    return out


def project_root(holon_root) -> dict:
    """The projection of holon_root/spec/M2/facts/*.extracted.json with holon_root/facts/morph_header.json."""
    root = Path(holon_root)
    inst = C.instrument(root)
    return project(documents_in(root / C.FACTS2, inst), C.load_json(root / C.HEADER_FACTS), inst)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon mutate project",
                                 description="the projected header document the laws/M0 statements are decided on")
    ap.add_argument("--documents", help="the extracted documents (default: spec/M2/facts)")
    ap.add_argument("--out", help=f"default: {C.PROJECTED.as_posix()}")
    ap.add_argument("--check", action="store_true", help="exit 1 when --out differs; write nothing")
    a = ap.parse_args(argv)
    out = Path(a.out) if a.out else C.ROOT / C.PROJECTED
    try:
        inst = C.instrument()
        docs = documents_in(Path(a.documents) if a.documents else C.ROOT / C.FACTS2, inst)
        text = C.dump(project(docs, C.load_json(C.ROOT / C.HEADER_FACTS), inst))
    except (C.MutateError, OSError, ValueError, KeyError, TypeError) as e:
        print(f"holon mutate project: refused: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    if a.check:
        same = out.is_file() and out.read_text() == text
        print(f"holon mutate project: {out} {'reproduces' if same else 'differs from'} the projection")
        return 0 if same else 1
    C.write_text(out, text)
    print(f"holon mutate project: wrote {out}")
    return 0
