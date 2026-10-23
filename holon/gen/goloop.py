"""The Bend model of a Go counted loop over an array, from its extracted loop body (I67 = I38a).

A counted loop (holon.frontends.go: kind counted/range, step 1, a fuel = the trip count) whose body, per iteration,
reads one array cell indexed by an affine function of the induction variable and branches on a predicate of that cell
is compiled to a structural recursion over the sequence of those cells: the induction variable is a `Nat`, the cell
sequence a `List<&2, U32>` consumed one node per iteration, and a bound site that the real index can run past (an open
site, its bound `a*iv + b < C`) becomes a `Nat` threshold `ceil(C / a)` compared with the index. No per-step `U32`
index arithmetic is emitted: `iv * stride` never appears, so the BendTT kernel converts one list node per iteration
(the alternative, a flat array indexed by `iv * stride`, costs ~32 bit-operations per step through `Word(32n)` and
exhausts the kernel's fuel well before the real trip count). See docs/iterations and the I67 feasibility note.

  model_text(lb, blob_param, name)   -> the model: the cell sequence carrier, one `step`, a fuel `run`, `ok`
  witness_list(lb)                   -> the smallest cell sequence that reaches the open site (the counter-law witness)
  counter_law_text / proof_text      -> `{ ok(W) == False : Bool }` and its proof-by-computation

Nothing here names a target: every constant (the trip count, the stride, the threshold, the cell value that trips the
predicate) is read from the extracted loop body.
"""
from __future__ import annotations


class LoopShapeError(ValueError):
    """A loop body outside the class this module compiles (one affine-indexed cell read, a predicate on it, and
    affine-in-iv bound sites). The caller records it and leaves the law UNKNOWN."""


def _const(t):
    return t[1] if isinstance(t, list) and len(t) == 2 and t[0] == "const" else None


def _affine_iv(t, iv: str):
    """(a, b) when t is a*iv + b over the induction variable iv (a >= 1, b >= 0), else None. Handles iv,
    ["op","*",iv,k], ["op","+",<that>,c] and ["op","*",k,iv]."""
    if t == ["iv", iv]:
        return (1, 0)
    if not isinstance(t, list) or t[0] != "op" or len(t) != 4:
        return None
    op, x, y = t[1], t[2], t[3]
    if op == "*":
        if x == ["iv", iv] and _const(y) is not None:
            return (_const(y), 0)
        if y == ["iv", iv] and _const(x) is not None:
            return (_const(x), 0)
        return None
    if op == "+":
        inner = _affine_iv(x, iv)
        c = _const(y)
        if inner and c is not None:
            return (inner[0], inner[1] + c)
        inner = _affine_iv(y, iv)
        c = _const(x)
        if inner and c is not None:
            return (inner[0], inner[1] + c)
    return None


def _cell_read(t, iv: str, blob_param: str):
    """The affine index (a, b) when t reads the array cell blob[a*iv + b] of the loop's own array parameter, else
    None. The cell read is ["index", ["param", blob_param], <affine iv>]."""
    if isinstance(t, list) and len(t) == 3 and t[0] == "index" and t[1] == ["param", blob_param]:
        return _affine_iv(t[2], iv)
    return None


def _threshold(a: int, b: int, c: int, op: str) -> tuple[int, str]:
    """For the index bound `a*iv + b <OP> c` (OP the SAFE direction of an open site, "<" or "<="), the first index
    iv at which it FAILS (the real code runs off the array), and the Bend comparison that holds from there on.
    Safe `a*iv + b < c` fails at iv >= ceil((c - b)/a); safe `<=` fails at iv > floor((c - b)/a)."""
    if a <= 0:
        raise LoopShapeError(f"non-positive index coefficient {a}")
    n = c - b
    if op == "<":
        thr = (n + a - 1) // a           # ceil(n / a): first iv with a*iv + b >= c
    elif op == "<=":
        thr = n // a + 1                 # first iv with a*iv + b > c
    else:
        raise LoopShapeError(f"index bound operator {op} is not a safe-direction bound")
    return max(thr, 0), "Nat.is_le"


def _live_atoms(cond, iv: str, blob_param: str, limit: int):
    """A body path's conditions minus the structural loop-range conditions (0 <= iv, iv < limit), as
    ("cell", op, v) for a predicate op(blob[a*iv+b], v) and ("iv", thr) for an index-bound atom that the open site
    turns into a threshold. Raises LoopShapeError on anything else."""
    out = []
    for atom in cond:
        if not isinstance(atom, list) or len(atom) != 3:
            raise LoopShapeError(f"atom {atom!r} is not a comparison")
        op, x, y = atom
        # structural loop-range atoms: drop them (the list consumption and the fuel enforce 0 <= iv < limit)
        if _affine_iv(x, iv) and _const(y) == limit and op in ("<", "<="):
            continue
        if _const(x) == 0 and _affine_iv(y, iv) and op in ("<=", "<"):
            continue
        # a predicate on the cell read: op(blob[a*iv+b], v)
        read = _cell_read(x, iv, blob_param)
        if read is not None and _const(y) is not None:
            out.append(("cell", op, _const(y)))
            continue
        read = _cell_read(y, iv, blob_param)
        if read is not None and _const(x) is not None:
            out.append(("cell", {"<": ">", ">": "<", "<=": ">=", ">=": "<="}.get(op, op), _const(x)))
            continue
        # an index-bound atom a*iv+b OP c: the open site's bound, turned into a threshold on iv
        lin = _affine_iv(x, iv)
        if lin is not None and _const(y) is not None:
            thr, _ = _threshold(lin[0], lin[1], _const(y), op if op in ("<", "<=") else "<")
            out.append(("iv", thr, op, lin))
            continue
        raise LoopShapeError(f"atom {atom!r} is neither a cell predicate nor an index bound over {iv}")
    return out


_U32_VERB = {"!=": "U32.is_ne", "==": "U32.is_eq", "<": "U32.is_lt", "<=": "U32.is_le",
             ">": "U32.is_gt", ">=": "U32.is_ge"}


def _shape(lb: dict, blob_param: str) -> dict:
    """The compiled shape of a counted loop body: the trip count, the per-element cell predicate that leaves the
    straight-line (continue) path, the open-site threshold on the induction variable (or None), and the cell values
    that keep to the continue path and that trip the predicate. Raises LoopShapeError outside the class."""
    iv = lb.get("iv")
    limit = _const(lb.get("limit"))
    if not iv or limit is None:
        raise LoopShapeError("the loop has no named induction variable or constant limit")
    cont = None            # the continue path's cell atom (op, v): the straight-line case
    trip_atom = None       # a non-continue path's cell atom (op, v)
    thr = None             # the open-site threshold on iv (first index that runs off the array)
    panics = False         # whether a non-continue path ends in a panic
    for p in lb.get("paths") or []:
        atoms = _live_atoms(p["cond"], iv, blob_param, limit)
        ivs = [a for a in atoms if a[0] == "iv"]
        cells = [a for a in atoms if a[0] == "cell"]
        # the loop's normal exit: iv >= limit, no cell read (the Nil case)
        if not cells and any(a[1] == limit for a in ivs):
            continue
        if len(cells) != 1:
            raise LoopShapeError(f"a body path reads {len(cells)} cells, expected exactly one")
        _, op, v = cells[0]
        if p["end"] == "continue":
            cont = (op, v)
        else:
            trip_atom = (op, v)
            for a in ivs:
                if a[1] != limit:
                    thr = a[1]
            if p["end"] == "panic":
                panics = True
    if cont is None or trip_atom is None:
        raise LoopShapeError("the loop body has no continue path or no exit path")
    return {"iv": iv, "limit": limit, "cont": cont, "trip": trip_atom, "thr": thr, "panics": panics}


def _pred_bend(op: str, v: int, var: str = "h") -> str:
    verb = _U32_VERB.get(op)
    if verb is None:
        raise LoopShapeError(f"cell-predicate operator {op} unsupported")
    return f"{verb}({var}, {v})"


def model_text(lb: dict, blob_param: str) -> str:
    """The Bend model of the loop: Out (OPanic | OExit), the cell-sequence carrier, one `step`, a fuel `run`, `ok`,
    and the witness W (the smallest carrier that reaches a panic, or an all-continue carrier when the loop never
    panics)."""
    s = _shape(lb, blob_param)
    # the cell predicate that leaves the continue path is the negation of the continue path's own cell atom
    neg = {"==": "!=", "!=": "==", "<": ">=", ">=": "<", "<=": ">", ">": "<="}
    op_cont, v_cont = s["cont"]
    pred = _pred_bend(neg[op_cont], v_cont)              # True -> the non-continue branch
    thr = s["thr"]
    fuel = s["limit"] + 8
    if s["panics"] and thr is not None:
        cell_true = f"split2(Nat.is_le({thr}n, i))"       # non-continue: panic iff iv >= threshold
        trip = v_cont + 1 if op_cont == "==" else v_cont   # a cell value that trips the predicate
        wit = (f'List.append(&2, U32, List.replicate(U32, {thr}n, {v_cont}), [{trip}])'
               if thr > 0 else f"[{v_cont + 1}]")
    else:
        cell_true = "Fin{OExit{}}"                         # no open site: the non-continue branch never panics
        wit = f"List.replicate(U32, {s['limit']}n, {v_cont})"
    return (
        "# GENERATED by holon.gen.goloop from the extracted loop body; do not edit.\n"
        "import Base\n\n"
        "type Out is Data:\n  OPanic{}\n  OExit{}\n\n"
        "type St is Data:\n  St{hs: List<&2, U32>, i: Nat}\n\n"
        "type Res is Data:\n  Next{st: St}\n  Fin{o: Out}\n\n"
        "def split2(b: Bool) -> Res:\n"
        "  match b:\n    case True{}:\n      Fin{OPanic{}}\n    case False{}:\n      Fin{OExit{}}\n\n"
        "def cell(p: Bool, nx: St, +i: Nat) -> Res:\n"
        f"  match p:\n    case True{{}}:\n      {cell_true}\n    case False{{}}:\n      Next{{nx}}\n\n"
        "def step(st: St) -> Res:\n"
        "  match st:\n    case St{hs, +i}:\n      match hs:\n        case Nil{}:\n          Fin{OExit{}}\n"
        f"        case Con{{h, t}}:\n          cell({pred}, St{{t, 1n+i}}, i)\n\n"
        "def run(fuel: Nat, r: Res) -> Out:\n"
        "  match fuel r:\n    case 0n _:\n      OExit{}\n    case 1n+p Next{st}:\n      run(p, step(st))\n"
        "    case 1n+p Fin{o}:\n      o\n\n"
        f"def retrieve(hs: List<&2, U32>) -> Out:\n  run({fuel}n, Next{{St{{hs, 0n}}}})\n\n"
        "def is_panic(o: Out) -> Bool:\n"
        "  match o:\n    case OPanic{}:\n      True{}\n    case _:\n      False{}\n\n"
        "def ok(hs: List<&2, U32>) -> Bool:\n  Bool.not(is_panic(retrieve(hs)))\n\n"
        f"def W() -> List<&2, U32>:\n  {wit}\n"
    )


def counter_law_text(model_import: str = "./M.bend") -> str:
    return ("import Base\n"
            f"import {model_import} as M\n\n"
            "law cl_tot:\n  {M.ok(M.W()) == False{} : Bool}\n")


def proof_text(laws_import: str = "./LAWS.bend", model_import: str = "./M.bend") -> str:
    return ("import Base\n"
            f"import {laws_import} as Laws\n"
            f"import {model_import} as M\n\n"
            "def Laws.cl_tot():\n  {==}\n")
