"""Deciding the laws of a Go-op component (BUILD_PLAN row I67; whitepaper §5.1 PAR-totality, A2; the contract is rules
Y6 and Y7 of the docstring of tests_m3/test_go_loop.py; the component itself is holon.diagram.goops).

The model gen/<M>/model/<component>.bend, generated from the Go-op document alone (generate):

  * Out: OPanic (the op panics), OErr (it returns a non-nil error), ORet (it returns a nil error);
  * the carrier is the sequence of the array cells an op's loop body reads, List<&2, U32>, one node per iteration: cell
    k is the cell the body reads at iteration k (its affine read a*k + c of the op's one parameter);
  * an op is its one loop body (holon.frontends.go's loop_bodies), compiled to a structural recursion: step_<op> takes
    one node and the iteration index, a Nat, and body_<op> picks the body path the cell and the index satisfy (a
    comparison of the cell with a constant; an index bound a*iv + c REL C as a Nat threshold on the index), no U32
    arithmetic per iteration; run_<op> runs the loop's trip count of steps, the loop's exit outcome after the last;
  * ok_<op>(b) = not is_panic(<op>(b)), the op's domain; eq_out and eq_bool are the counter-laws' equality functions,
    untrusted (BEND_PRIMER 5.4).

An op outside this class (no loop body, more than one loop, a path reading a second cell or anything but the
induction variable and the parameter's cells, a non-affine index, an outcome that is not one of the three, body paths
that do not partition the cell and index values) is Unsupported, and the laws naming it are UNKNOWN with the reason.

Deciding (decide): the candidates are, per op by model name, the smallest panic witness its shape gives, then the
sequence of continue values; a law is REFUTED at the first candidate whose counter-law Bend accepts, else UNKNOWN (no
proof route for a forall law over cell sequences here: gap G6). Nothing here names a target: every constant (the trip
count, the stride, the thresholds, the cell values) is read from the document.
"""
from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .. import bend

ALIAS = "M"
ROOT = Path(__file__).resolve().parents[2]
OUTS = ("OPanic", "OErr", "ORet")
FLIP = {"==": "==", "!=": "!=", "<": ">", ">": "<", "<=": ">=", ">=": "<="}
U32_CMP = {"==": "U32.is_eq", "!=": "U32.is_ne", "<": "U32.is_lt", "<=": "U32.is_le", ">": "U32.is_gt",
           ">=": "U32.is_ge"}
RESERVED = {"Out", "St", "Res", "is_panic", "eq_out", "eq_bool", "is_true"}
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Unsupported(Exception):
    """A document or statement form this generator cannot express faithfully (the law stays UNKNOWN)."""


# ====================================================================== terms
def _const(t):
    if isinstance(t, list) and len(t) == 2 and t[0] == "const" and isinstance(t[1], int) and not isinstance(t[1], bool):
        return t[1]
    return None


def affine(t, iv: str):
    """(a, c) when t is a*iv + c over the symbolic induction variable ["iv", iv], else None."""
    if t == ["iv", iv]:
        return (1, 0)
    if not (isinstance(t, list) and len(t) == 4 and t[0] == "op"):
        return None
    o, x, y = t[1], t[2], t[3]
    if o == "*":
        for u, k in ((x, y), (y, x)):
            inner, n = affine(u, iv), _const(k)
            if inner is not None and n is not None:
                return (inner[0] * n, inner[1] * n)
        return None
    if o in ("+", "-"):
        for u, k, sign in ((x, y, 1), (y, x, 1)) if o == "+" else ((x, y, -1),):
            inner, n = affine(u, iv), _const(k)
            if inner is not None and n is not None:
                return (inner[0], inner[1] + sign * n)
    return None


def cell_read(t, iv: str, param: str):
    """(a, c) when t reads the cell param[a*iv + c] of the op's parameter (through a pointer to an array or not)."""
    if not (isinstance(t, list) and len(t) == 3 and t[0] == "index"):
        return None
    base = t[1]
    while isinstance(base, list) and len(base) == 2 and base[0] == "deref":
        base = base[1]
    if base != ["param", param]:
        return None
    return affine(t[2], iv)


def threshold(o: str, a: int, c: int, k: int):
    """The index condition equivalent to a*iv + c <o> k for a >= 1, as (Nat relation of iv, Nat bound): ("ge", t)
    for iv >= t, ("lt", t) for iv < t, ("eq", t) / ("ne", t), or ("never",) / ("always",)."""
    if a < 1:
        raise Unsupported(f"an index coefficient {a} (the class has a positive stride)")
    n = k - c
    if o == "<":
        return ("lt", max(-(-n // a), 0))
    if o == "<=":
        return ("lt", max(n // a + 1, 0))
    if o == ">=":
        return ("ge", max(-(-n // a), 0))
    if o == ">":
        return ("ge", max(n // a + 1, 0))
    if o in ("==", "!="):
        if n < 0 or n % a:
            return ("never",) if o == "==" else ("always",)
        return ("eq" if o == "==" else "ne", n // a)
    raise Unsupported(f"comparison {o}")


def holds_index(cond, i: int) -> bool:
    kind = cond[0]
    if kind == "always":
        return True
    if kind == "never":
        return False
    t = cond[1]
    return {"ge": i >= t, "lt": i < t, "eq": i == t, "ne": i != t}[kind]


def holds_cell(o: str, h: int, v: int) -> bool:
    return {"==": h == v, "!=": h != v, "<": h < v, "<=": h <= v, ">": h > v, ">=": h >= v}[o]


# ====================================================================== one op's shape
@dataclass
class Path_:
    cells: list            # [(op, value)]: comparisons of the cell with constants
    index: list            # [index condition] (threshold())
    outcome: str           # "continue" | an Out constructor
    site: str | None = None


@dataclass
class Shape:
    op: str
    param: str
    iv: str
    init: int
    n: int                 # the trip count: iterations from init while iv < limit
    read: tuple            # (a, c): cell k is param[a*k + c]
    paths: list            # [Path_], continue paths first, then by outcome and site
    exit: str              # the loop's exit outcome
    samples: list = field(default_factory=list)   # cell values that represent every class of the cell's atoms

    def pick(self, h: int, i: int) -> Path_:
        hits = [p for p in self.paths if all(holds_cell(o, h, v) for o, v in p.cells)
                and all(holds_index(c, i) for c in p.index)]
        if len(hits) != 1:
            raise Unsupported(f"{self.op}: {len(hits)} body paths hold at cell {h}, index {i}")
        return hits[0]

    def index_points(self) -> list[int]:
        pts = {self.init, self.init + self.n - 1}
        for p in self.paths:
            for c in p.index:
                if len(c) == 2:
                    pts |= {c[1] - 1, c[1], c[1] + 1}
        return sorted(x for x in pts if self.init <= x < self.init + self.n)


def _outcome(path: dict) -> str:
    if path["end"] == "continue":
        return "continue"
    if path["end"] == "panic":
        return "OPanic"
    err = path.get("error")
    if err == "nil":
        return "ORet"
    if err == "nonnil":
        return "OErr"
    raise Unsupported(f"a return path whose error is {err!r}")


def shape(name: str, op: dict) -> Shape:
    """The compiled shape of one op (rule Y6), or Unsupported."""
    if name in RESERVED or not IDENT.match(name):
        raise Unsupported(f"op name {name!r} is reserved or not an identifier")
    params = op.get("params") or []
    if len(params) != 1:
        raise Unsupported(f"{name}: {len(params)} parameters")
    param = params[0]["name"]
    lbs = op.get("loop_bodies")
    if not isinstance(lbs, list) or len(lbs) != 1:
        raise Unsupported(f"{name}: {0 if not lbs else len(lbs)} loop bodies (the class has one)")
    lb = lbs[0]
    iv, init, limit = lb.get("iv"), _const(lb.get("init")), _const(lb.get("limit"))
    if not iv or init is None or limit is None or init < 0 or lb.get("step") != 1 or lb.get("cmp") != "<" \
            or lb.get("paths") is None:
        raise Unsupported(f"{name}: not a counted loop from a constant to a constant bound, step 1, cmp <, with paths")
    n = limit - init
    if n < 1:
        raise Unsupported(f"{name}: a loop of {n} iterations")
    read, body, exits = None, [], []
    for p in lb["paths"]:
        cells, index, is_exit = [], [], False
        for atom in p["cond"]:
            if not (isinstance(atom, list) and len(atom) == 3 and atom[0] in FLIP):
                raise Unsupported(f"{name}: condition {atom!r} is not a comparison")
            o, x, y = atom
            ax, ay = affine(x, iv), affine(y, iv)
            if ax == (1, 0) and _const(y) is not None or ay == (1, 0) and _const(x) is not None:
                oo, k = (o, _const(y)) if ax == (1, 0) else (FLIP[o], _const(x))
                if (oo, k) in ((">=", init), ("<", limit)) or (oo == ">" and k == init - 1) \
                        or (oo == "<=" and k == limit - 1):
                    continue                                   # the loop's own range
                if (oo, k) in ((">=", limit), (">", limit - 1)):
                    is_exit = True
                    continue
            rx, ry = cell_read(x, iv, param), cell_read(y, iv, param)
            if (rx is not None and _const(y) is not None) or (ry is not None and _const(x) is not None):
                r, oo, k = (rx, o, _const(y)) if rx is not None else (ry, FLIP[o], _const(x))
                if read is not None and r != read:
                    raise Unsupported(f"{name}: the body reads two cells, {read} and {r}")
                read = r
                cells.append((oo, k))
                continue
            if ax is not None and _const(y) is not None or ay is not None and _const(x) is not None:
                (a, c), oo, k = (ax, o, _const(y)) if ax is not None else (ay, FLIP[o], _const(x))
                index.append(threshold(oo, a, c, k))
                continue
            raise Unsupported(f"{name}: condition {atom!r} reads more than the induction variable and the cells")
        out = _outcome(p)
        if is_exit:
            if cells:
                raise Unsupported(f"{name}: an exit path reads a cell")
            exits.append(out)
        else:
            body.append(Path_(cells, index, out, p.get("site")))
    if read is None or read[0] < 1 or read[1] < 0:
        raise Unsupported(f"{name}: no cell read of the parameter with a positive stride")
    if not exits or len(set(exits)) != 1 or exits[0] == "continue":
        raise Unsupported(f"{name}: the loop's exit paths end in {sorted(set(exits))} (the class has one outcome)")
    if not any(p.outcome == "continue" for p in body):
        raise Unsupported(f"{name}: no body path continues the loop")
    body.sort(key=lambda p: (p.outcome != "continue", p.outcome, p.site or "", repr(p.cells), repr(p.index)))
    consts = {v for p in body for _, v in p.cells}
    samples = sorted({x for v in consts for x in (v - 1, v, v + 1)} | {0, 255})   # a cell is a byte (rule Y7)
    sh = Shape(name, param, iv, init, n, read, body, exits[0], [x for x in samples if 0 <= x <= 255])
    for i in sh.index_points():   # the body paths partition (cell, index): exactly one holds at every class
        for h in sh.samples:
            sh.pick(h, i)
    return sh


def continue_value(sh: Shape, i: int) -> int:
    for h in sh.samples:
        if sh.pick(h, i).outcome == "continue":
            return h
    raise Unsupported(f"{sh.op}: no cell value continues the loop at index {i}")


def panic_witness(sh: Shape) -> list[int] | None:
    """The smallest panic witness (rule Y7): the first iteration k at which a panic path holds for some cell value;
    cells before k at a continue value, cell k at the smallest such value, cells after k at a continue value."""
    for k in range(sh.init, sh.init + sh.n):
        for h in sh.samples:
            if sh.pick(h, k).outcome == "OPanic":
                cells = [continue_value(sh, sh.init + j) for j in range(sh.n)]
                cells[k - sh.init] = h
                return cells
    return None


def all_continue(sh: Shape) -> list[int]:
    return [continue_value(sh, sh.init + j) for j in range(sh.n)]


def evaluate(sh: Shape, cells: list[int]) -> str:
    """The op's outcome on a cell sequence by its shape (the model's own semantics; a check of the generator, never
    a verdict: Bend's acceptance of the counter-law is)."""
    for j in range(sh.n):
        if j >= len(cells):
            return sh.exit
        o = sh.pick(cells[j], sh.init + j).outcome
        if o != "continue":
            return o
    return sh.exit


# ====================================================================== the model text
PRELUDE = '''\
type Out is Data:
  OPanic{}
  OErr{}
  ORet{}

# St{hs, i}: the cells left to read and the iteration index; a step either goes on or ends with an outcome
type St is Data:
  St{hs: List<&2, U32>, i: Nat}

type Res is Data:
  Next{st: St}
  Fin{o: Out}

def is_panic(o: Out) -> Bool:
  match o:
    case OPanic{}:
      True{}
    case OErr{}:
      False{}
    case ORet{}:
      False{}

# Equality functions used by counter-laws. They are not trusted: a counter-law whose sides are actually equal is
# rejected whatever these compute (BEND_PRIMER 5.4).
def eq_out(a: Out, b: Out) -> Bool:
  match a b:
    case OPanic{} OPanic{}:
      True{}
    case OErr{} OErr{}:
      True{}
    case ORet{} ORet{}:
      True{}
    case _ _:
      False{}

def eq_bool(a: Bool, b: Bool) -> Bool:
  match a b:
    case True{} True{}:
      True{}
    case False{} False{}:
      True{}
    case True{} False{}:
      False{}
    case False{} True{}:
      False{}

def is_true(b: Bool) -> Type:
  match b:
    case True{}:
      Unit
    case False{}:
      Empty
'''


def _and(xs: list[str]) -> str:
    if not xs:
        return "True{}"
    out = xs[-1]
    for x in reversed(xs[:-1]):
        out = f"Bool.and({x}, {out})"
    return out


def _index_test(c) -> str:
    kind = c[0]
    if kind == "always":
        return "True{}"
    if kind == "never":
        return "False{}"
    t = c[1]
    return {"ge": f"Nat.is_le({t}n, i)", "lt": f"Nat.is_lt(i, {t}n)", "eq": f"Nat.is_eq(i, {t}n)",
            "ne": f"Nat.is_ne(i, {t}n)"}[kind]


def _result(p: Path_) -> str:
    return "Next{nx}" if p.outcome == "continue" else f"Fin{{{p.outcome}{{}}}}"


def _test(p: Path_) -> str:
    return _and([f"{U32_CMP[o]}(h, {v})" for o, v in p.cells] + [_index_test(c) for c in p.index])


def op_text(sh: Shape) -> str:
    """One op's definitions. A match scrutinizes only a parameter or a field, so each body path's test is the Bool
    argument of a selector sel_<op>_<k>, whose False branch tries the next path; the last path needs no test (the
    paths partition the cell and index values, checked in shape()). Definitions precede their use."""
    op, ps = sh.op, sh.paths
    lines = [f"# {op}: cell k is {sh.param}[{sh.read[0]}*k + {sh.read[1]}], {sh.n} iterations from {sh.init}; exit "
             f"outcome {sh.exit}"]
    for k in range(len(ps) - 2, -1, -1):
        nxt = _result(ps[-1]) if k == len(ps) - 2 else f"sel_{op}_{k + 1}({_test(ps[k + 1])}, h, i, nx)"
        lines += [f"def sel_{op}_{k}(t: Bool, +h: U32, +i: Nat, +nx: St) -> Res:", "  match t:", "    case True{}:",
                  f"      {_result(ps[k])}", "    case False{}:", f"      {nxt}", ""]
    first = f"sel_{op}_0({_test(ps[0])}, h, i, nx)" if len(ps) > 1 else _result(ps[0])
    lines += [f"def body_{op}(+h: U32, +i: Nat, +nx: St) -> Res:", f"  {first}", "",
              f"def step_{op}(st: St) -> Res:", "  match st:", "    case St{hs, +i}:", "      match hs:",
              "        case Nil{}:", f"          Fin{{{sh.exit}{{}}}}", "        case Con{h, t}:",
              f"          body_{op}(h, i, St{{t, 1n+i}})", "",
              f"def run_{op}(fuel: Nat, r: Res) -> Out:", "  match fuel r:", "    case 0n Next{st}:",
              f"      {sh.exit}{{}}", "    case 0n Fin{o}:", "      o", "    case 1n+p Next{st}:",
              f"      run_{op}(p, step_{op}(st))", "    case 1n+p Fin{o}:", "      o", "",
              f"def {op}(hs: List<&2, U32>) -> Out:", f"  run_{op}({sh.n}n, Next{{St{{hs, {sh.init}n}}}})", "",
              f"def ok_{op}(hs: List<&2, U32>) -> Bool:", f"  Bool.not(is_panic({op}(hs)))", ""]
    return "\n".join(lines)


def shapes(doc: dict) -> dict:
    """{op: Shape | Unsupported} of every op of a Go-op document."""
    out = {}
    for name, op in sorted(doc["ops"].items()):
        try:
            out[name] = shape(name, op)
        except Unsupported as e:
            out[name] = e
    return out


def generate(doc: dict, sha: str) -> str:
    """The component model (rule Y6). An op outside the class gets no definitions, its reason a comment line."""
    head = [f"# GENERATED by holon.gen.goloop from the Go-op document {doc['component']} (sha256 {sha}); do not edit.",
            "import Base", "", PRELUDE]
    body = []
    for name, sh in shapes(doc).items():
        if isinstance(sh, Unsupported):
            body.append(f"# {name}: unsupported ({sh})\n")
        else:
            body.append(op_text(sh))
    return "\n".join(head) + "\n" + "\n".join(body)


class CompiledModel:
    """A component model compiled with the pinned Bend to an ES module (cached by the text's hash)."""

    def __init__(self, source: Path, artifact: Path, doc: dict, cfg: dict | None):
        self.source, self.artifact, self.doc, self.cfg = source, artifact, doc, cfg
        self.shapes = shapes(doc)

    @classmethod
    def build(cls, doc: dict, sha: str, name: str, cfg: dict | None = None) -> "CompiledModel":
        text = generate(doc, sha)
        h = hashlib.sha256(text.encode()).hexdigest()
        src = bend.build_dir(ROOT) / "goops" / h[:16] / f"{name}.bend"
        src.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists() or src.read_text() != text:
            src.write_text(text)
        art = src.with_suffix(".mjs")
        stamp = src.with_suffix(".src.sha256")
        if not (art.exists() and stamp.exists() and stamp.read_text() == h):
            r = bend.run([src.name, "-o", art.name], cwd=src.parent, cfg=cfg)
            if r.code != 0 or not art.exists():
                raise RuntimeError(f"bend failed to compile {src}: {r.out[:2000]}")
            stamp.write_text(h)
        return cls(src, art, doc, cfg)


# ====================================================================== laws
@dataclass
class Emitted:
    name: str
    text: str
    binder: str
    lhs: str
    rhs: str
    claim_type: str
    ops: list               # the ops the claim names


TYPE_TEXT = {"Out": f"{ALIAS}.Out", "Bool": "Bool"}   # a claim's type in LAWS.bend (the model's Out is imported)


def law_name(law_id: str, counter: bool = False) -> str:
    return ("cl_" if counter else "") + law_id.lower()


def _term(doc: dict, t, binder: str) -> tuple[str, str, str | None]:
    """(Bend text, type, op named) of a claim side: <op>(b) of type Out, ok_<op>(b) of type Bool, a Bool literal."""
    if isinstance(t, dict) and set(t) == {"bool"} and isinstance(t["bool"], bool):
        return ("True{}" if t["bool"] else "False{}"), "Bool", None
    if isinstance(t, dict) and set(t) == {"call", "args"} and t["args"] == [{"var": binder}]:
        f = t["call"]
        if f in doc["ops"]:
            return f"{ALIAS}.{f}({binder})", "Out", f
        if f.startswith("ok_") and f[3:] in doc["ops"]:
            return f"{ALIAS}.{f}({binder})", "Bool", f[3:]
    raise Unsupported(f"a claim side {t!r} is not an op, its domain or a Bool over the binder")


def emit(law: dict, doc: dict, model_import: str, counter: bool = False, note: str = "") -> Emitted:
    """LAWS.bend of a Go-op law, or its counter-law (the exs form of BEND_PRIMER 5.4)."""
    st = law["statement"]
    bs = st.get("binders") or []
    if len(bs) != 1 or bs[0].get("q") != "forall" or bs[0].get("type") != doc["carrier"]["id"] or st.get("assume"):
        raise Unsupported("a Go-op law has one forall binder over the carrier and no premise")
    if set(st.get("claim") or {}) != {"eq"}:
        raise Unsupported("a Go-op law states one equation")
    b = bs[0]["name"]
    (lhs, tl, ol), (rhs, tr, orr) = (_term(doc, x, b) for x in st["claim"]["eq"])
    if tl != tr:
        raise Unsupported(f"claim sides of two types: {tl} / {tr}")
    name = law_name(law["law_id"], counter)
    q, pre = ("exs", "") if counter else ("for", "+")
    lines = ["# GENERATED by holon.gen.goloop from the frozen law IR; do not edit.",
             f"# law_id: {law['law_id']}   statement_hash: {note}", "import Base", f"import {model_import} as {ALIAS}",
             "", f"law {name}:", f"  {q} {pre}{b}: List<&2, U32>",
             f"  {{{lhs} {'!=' if counter else '=='} {rhs} : {TYPE_TEXT[tl]}}}"]
    return Emitted(name, "\n".join(lines) + "\n", b, lhs, rhs, tl, sorted({o for o in (ol, orr) if o}))


def cells_literal(cells: list[int]) -> str:
    """A cell sequence as a Bend term: runs of one value as List.replicate, joined by List.append."""
    runs = []
    for v in cells:
        if runs and runs[-1][0] == v:
            runs[-1][1] += 1
        else:
            runs.append([v, 1])
    parts = [f"List.replicate(U32, {k}n, {v})" if k > 1 else f"[{v}]" for v, k in runs]
    out = parts[-1]
    for p in reversed(parts[:-1]):
        out = f"List.append(&2, U32, {p}, {out})"
    return out


EQ_FN = {"Out": "eq_out", "Bool": "eq_bool"}
HEADER = ["# GENERATED by holon.gen.goloop; untrusted, accepted only if Bend checks it.", "import Base"]


def counter_proof(em: Emitted, model_import: str, cells: list[int]) -> str:
    """The counter-law's proof at a concrete witness (BEND_PRIMER 5.4), its motive the model's equality at the lhs."""
    w = cells_literal(cells)
    at_lhs = re.sub(rf"(?<![\w.]){re.escape(em.binder)}(?![\w])", lambda _m: w, em.lhs)
    eq = f"{ALIAS}.{EQ_FN[em.claim_type]}"
    lines = HEADER + [f"import {model_import} as {ALIAS}", "import ./LAWS.bend as Laws", "",
                      "# class counter: a concrete cell sequence; the motive is Unit at the lhs and Empty at the rhs",
                      f"def Laws.{em.name}():", f"  ({w}, e => (%e : {ALIAS}.is_true({eq}(_, {at_lhs}))",
                      "  Unit{}))"]
    return "\n".join(lines) + "\n"


def side_value(sh_of: dict, term, binder: str, cells: list[int]):
    """A claim side's value at a cell sequence by the shapes' semantics (for the record's difference)."""
    if isinstance(term, dict) and "bool" in term:
        return term["bool"]
    f = term["call"]
    if f.startswith("ok_") and f[3:] in sh_of:
        return evaluate(sh_of[f[3:]], cells) != "OPanic"
    return evaluate(sh_of[f], cells)


@dataclass
class Decision:
    status: str
    em: Emitted | None = None
    statement: Emitted | None = None
    check: object = None
    witness: dict | None = None
    difference: dict | None = None
    bound: str | None = None
    attempts: list = field(default_factory=list)


def candidates(cm: CompiledModel) -> list[tuple[str, list[int]]]:
    """Rule Y7's candidates: per op by model name, its smallest panic witness; then the continue values (of the first
    op the class covers)."""
    out, first = [], None
    for name, sh in sorted(cm.shapes.items()):
        if isinstance(sh, Unsupported):
            continue
        first = first or sh
        w = panic_witness(sh)
        if w is not None:
            out.append((f"the smallest panic witness of {name}", w))
    if first is not None:
        out.append((f"the continue values of {first.op}", all_continue(first)))
    return out


def decide(law: dict, cm: CompiledModel, ld: Path, pd: Path, model_import_l: str, model_import_p: str, cfg: dict,
           shash: str, write_pair, accepted) -> Decision:
    """Rule Y7. Every status is Bend's: REFUTED only through a LAWS.bend / PROOF.bend pair Bend accepts."""
    doc = cm.doc
    try:
        stmt = emit(law, doc, model_import_l, note=shash)
        cem = emit(law, doc, model_import_l, counter=True, note=shash)
    except Unsupported as e:
        return Decision("UNKNOWN", attempts=[{"kind": "emit", "error": f"unsupported statement form: {e}"}],
                        bound="not searched: the emitter cannot express this statement faithfully")
    bad = {o: str(cm.shapes[o]) for o in cem.ops if isinstance(cm.shapes.get(o), Unsupported)}
    if bad:
        return Decision("UNKNOWN", statement=stmt, attempts=[{"kind": "model", "error": f"unsupported op: {bad}"}],
                        bound=f"not searched: the model class does not cover {sorted(bad)} (rule Y6)")
    sh_of = {o: s for o, s in cm.shapes.items() if not isinstance(s, Unsupported)}
    attempts, tried = [], []
    n_cells = {s.n for s in sh_of.values()}
    for what, cells in candidates(cm):
        tried.append(what)
        if len(n_cells) != 1:
            attempts.append({"kind": "refute", "candidate": what, "error": "the ops' loops differ in trip count"})
            continue
        for x in {ld, pd}:
            shutil.rmtree(x, ignore_errors=True)
        proof = counter_proof(cem, model_import_p, cells)
        pf = write_pair(ld, pd, cem.text, proof)
        rr = bend.check(pf, cfg)
        ok, why = accepted(rr, pf, ld / "LAWS.bend", cem, proof)
        attempts.append({"kind": "counter-law", "generator": "counter", "candidate": what, "exit_code": rr.code,
                         "marker": rr.marker, "seconds": rr.seconds, **({} if ok else {"error": why})})
        if ok:
            b = cem.binder
            lhs_t, rhs_t = law["statement"]["claim"]["eq"]
            diff = {"lhs": side_value(sh_of, lhs_t, b, cells), "rhs": side_value(sh_of, rhs_t, b, cells)}
            return Decision("REFUTED", em=cem, statement=stmt, check=rr,
                            witness={b: "0x" + bytes(cells).hex()}, difference=diff, attempts=attempts)
    for x in {ld, pd}:
        shutil.rmtree(x, ignore_errors=True)
    return Decision("UNKNOWN", statement=stmt, attempts=attempts,
                    bound=(f"no candidate refutes it in the compiled model (candidates: {'; '.join(tried)}); a forall "
                           "law over cell sequences has no proof route here (gap G6)"))
