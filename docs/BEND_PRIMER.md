# Bend 2 primer for HOLON (verified)

Everything here was checked by running Bend, not taken from memory or docs alone. Every pattern has a probe in `bend/probes/`, and `tests/test_02_bend_probes.py` re-runs all of them.

- **Version:** `bend 2.0.36`, repo `bendlang/bend` at commit `2343aec043b7967f2a6f653e7f2e3bcbe55c8c9a`, 2026-10-10.
- **Runner:** `bun 1.4.2 bend2/main.ts` from a checkout.

Bend 2 was released after most models' training data ends. **Do not trust your priors about its syntax.** Before writing any Bend:

1. Read `bend guide` in full. It is about 680 lines.
2. Run `bend base` to see the standard library.
3. Copy the patterns below.

Bend 1 (HigherOrderCO/Bend, interaction nets, `bend run-c`) is a different language.

## 1. Install and pin

| Option | Commands | Notes |
|---|---|---|
| Installer binary | `curl -fsSL https://bend-lang.com/install.sh \| sh`, then `bend version` | Installs the latest release. The binary ignores a project's `bunfig.toml` and `.env`. |
| Pinned checkout | `tools/install_bend.sh` | Clones `bendlang/bend` at the pinned commit and writes a `bend` wrapper that runs `bun bend2/main.ts`. This is what the probes were verified with. **Bun reads `bunfig.toml` and `.env` from the working directory**, so a `preload` there runs code inside the checker. The gate refuses to run Bend if either file exists anywhere in the repo. |

- `bend update` is the only way the installed version changes. The daily version check only prints a notice.
- Record the version in `config/holon.json` → `bend.pinned_version`. If you change it, re-run all probes.

## 2. The CLI facts the factory relies on

| Command | Behaviour |
|---|---|
| `bend F.bend` | Checks every law and def. Prints `ALL PROOFS CHECK` and exits 0 when every proof is valid. Otherwise prints `SOME PROOFS FAIL` plus an error block and exits 1. |
| `bend F.bend` (with `def main() -> T`, T not IO) | Normalizes `main` and prints the value, e.g. `[255, 3, 2, 1]` (probe p13). |
| `bend F.bend -o F.mjs` | Emits an ES module whose default export holds every non-IO def. Output is byte-deterministic (verified). |
| `bend F.bend -o F` / `-o F.c` | Native binary or C source. Needs a `main`. |
| `bend F.bend -o F.bendtt` | Writes the kernel-level (BendTT) translation of every def and law. Readable: `LAWS.double_zero : {(LAWS.double (.Zero, ())) == (.Zero, ()) : Nat} = {==}`. Does not need Lean. |
| `bend F.bend --verdict` | Re-checks with the BendTT kernel, whose soundness is proved in Lean (`bend2/bendtt.lean`). Needs elan with `leanprover/lean4:v4.34.0`, or `$BENDTT`. It also rejects `@unsafe` and foreign code. **Not verified in the kit's environment (Lean download was blocked); P0 must verify it.** This is HOLON's second kernel (whitepaper §8.8) at almost no cost. |
| `bend guide`, `bend base`, `bend base List` | Language guide and standard library. |

Measured timings:
- Full 257-byte Morph header equality, from overlapping EVM writes vs Go writes over a 257-field record: about 0.3 s.
- Counter-law: about 0.5 s.
- Compiled header encoder in node: about 0.1 ms per call.

## 3. Hazards found while verifying (read these)

1. **Vacuity.** A file with zero laws prints `ALL PROOFS CHECK` (probe p06). An exit code of 0 proves nothing about laws that are not in the file. Gates must check that the expected law names are present.
2. **Escape hatches.** Each of these makes the check print `SOME PROOFS FAIL`:

   | Escape hatch | Probe |
   |---|---|
   | `?TODO` | p04 |
   | `?name` | — |
   | A `law` with no def | p03 |
   | `@unsafe def` (or `def f?(..)`) | p05; reported as "N defs rely on unsafe or foreign code" |
   | Foreign `import "./x.c"` | — |

   Gates should also scan for them textually.
3. **Proof files cannot redefine the model.** `def Laws.double(..)` in `PROOF.bend` is refused: "a fresh name (Laws is an import's alias)", probe p15. A proof cannot change what a law is about. It *can* define helpers, so laws must reference model defs through the model module, never through `Laws.`.
4. **Bun config preload** (checkout runner only). See section 1.

## 4. Language gotchas (each cost a failed check)

- **Lists of `U32` must be written `List<&2, U32>`** (reusable). `List<U32>` means `List<&1, U32>`, and `List.replicate` returns `List<&2, ..>`, so mixing them fails with `expected : List<&1, U32>  observed : List<&2, U32>`.
- **Quantities.** Variables are affine (used at most once) by default.
  - Prefix a param with `+` to reuse it. The type must be `Data`, e.g. `def f(+xs: List<&2, U32>)`.
  - In patterns, `case Hdr{+v, +a}` makes fields reusable.
  - Dropping a variable is free.
- **No `if`.** Use `match` on `True{}` / `False{}`.
- `match` only inspects parameters or pattern-bound variables, never a computed value. To branch on `U32.to_nat(v)`, pass it to a helper def that matches on its parameter.
- **Termination.**
  - Recursive calls must shrink an argument. Arguments are read left to right: put the shrinking one first.
  - Mutual recursion is forbidden.
  - Nat patterns: `0n`, `1n+p`, `2n`, `3n+p` all work.
- **Equality.**
  - `{a == b : T}` is a *type*. Value equality is a call: `U32.is_eq(a, b)` returns `Bool`.
  - Operators need a type: `(a + b : U32)`.
- **Literals.**
  - Numbers are decimal; `U32` values like `57005` work.
  - Nat literals above `256n` work up to `4294967295n`.
  - Lists: `[a, b]`, `Nil{}`, `Con{h, t}`.
- **Bytes.** Base has no `U8` or `U64`. HOLON models one byte as one `U32` and a k-byte field as k `U32` fields of a record. Unknown or dirty EVM memory is the sentinel `57005` (0xDEAD), which lies outside the byte range, so an unwritten byte can never equal a real one.
- **Modules.**
  - `import ../model/m.bend as M` works, including `..`.
  - Types and constructors are qualified: `M.Hdr`, `M.Hdr{..}`. `Some{..}`, `None{}`, `True{}` come from Base.
  - Laws live in `LAWS.bend`. `PROOF.bend` does `import ./LAWS.bend as Laws` and fills each law with `def Laws.<name>(..)`. Bend refuses a `PROOF.bend` that sits beside a `LAWS.bend` without importing it.

## 5. Patterns HOLON uses

### 5.1 Codec models from write sequences

```python
def overlay(mem: List<&2, U32>, bs: List<&2, U32>) -> List<&2, U32>:   # replace prefix, keep length
  match mem bs:
    case Nil{} _:
      Nil{}
    case Con{h, t} Nil{}:
      Con{h, t}
    case Con{h, t} Con{b, r}:
      Con{b, overlay(t, r)}

def put(mem: List<&2, U32>, off: Nat, bs: List<&2, U32>) -> List<&2, U32>:   # mstore / copy at offset
  match mem off:
    case Nil{} _:
      Nil{}
    case Con{h, t} 0n:
      overlay(Con{h, t}, bs)
    case Con{h, t} 1n+p:
      Con{h, put(t, p, bs)}
```

- **EVM encoder:**
  1. `m0 = List.replicate(U32, SIZE, 57005)` (dirty memory).
  2. One `put` per `mstore`: a 32-byte word, e.g. `[f_0..f_7] ++ 24 zeros` for `shl(192, x)`.
  3. `List.take(&2, U32, m, LEN)`.
- **Go encoder:** `zeros(LEN)`, then one `put` per `PutUint64` / `copy` / byte assignment.

See probe p07. The full 257-byte Morph header works the same way, with one `U32` record field per byte.

### 5.2 Premises `field == const` by pinning

Generate `pin(h)`, which rebuilds the record with the pinned fields replaced by constants, and state the law over `pin(h)`. This is equivalent to assuming the premise: pin is onto the premise set and is the identity there.

### 5.3 Proof by computation

Open the record, then reflexivity:

```python
def Laws.l_par_hdr_v1(h):
  match h:
    case M.Hdr{version_0, batchIndex_0, ...}:
      {==}
```

Opening the record is what lets the encoders reduce. Without the `match`, the terms are stuck on the variable `h`.

### 5.4 Counter-laws (kernel-checked refutations)

`{a != b : T}` is `{a == b : T} -> Empty`. With a concrete witness `W`, a model equality function `eqT`, and `is_true(True)=Unit`, `is_true(False)=Empty`:

```python
law cl_x:
  exs h: M.Hdr
  {L(pin(h)) != R(pin(h)) : T}

def Laws.cl_x():
  (W, e => (%e : M.is_true(M.eqT(_, L(Laws.pin(W))))
  Unit{}))
```

- `%e : P` rewrites with `e : {a == b}`, where `P` is the goal with `_` marking `b`. The goal becomes `P` with `a` in that position.
- The motive at `R(W)` is `is_true(False) = Empty`, which is the goal. At `L(W)` it is `is_true(True) = Unit`.
- If the sides are actually equal, the check fails no matter how `eqT` is written (p10, p16). So `eqT` is not trusted.
- A for-all version that uses a discriminator on one byte (p09) is stronger but needs symbolic reasoning. M0 requires only the `exs` form.

### 5.5 Hypotheses, not axioms

`for cf: {h(x) == h(y) : U32} -> {x == y : U32}` (p12). Function-typed binders (`for -h: U32 -> U32`) work. There is no `axiom` keyword. Every assumption is a visible premise.

### 5.6 Evaluating the model from Python

- **Slow path:** write `def main() -> T` and parse the printed value.
- **Fast path:** `bend model.bend -o model.mjs`, then in node:

```js
import M from "./model.mjs";
const toList = xs => xs.reduceRight((t, h) => ({$: "Con", head: h, tail: t}), {$: "Nil"});
const h = {$: "Hdr", version_0: 1, /* ...one key per field... */};
M.enc_sol(h)   // returns {$:"Con", head: 1, tail: {...}}
```

Value encoding:

| Bend value | JS value |
|---|---|
| `U32` | JS number |
| constructor | `{$: "Name", field: value}` |
| `Nat` | `BigInt` |
| `Bool` | `{$: "True"}` / `{$: "False"}` |
| `Maybe` | `{$: "Some", value}` / `{$: "None"}` |

## 6. Open questions for P0 to answer and record in `docs/BEND_NOTES.md`

- Does `--verdict` pass on p01, p07, p09, p11 with Lean v4.34.0? How long does it take?
- Does the installer binary report the same version and pass every probe?
- What is the largest record or list size before checking slows down? (Needed for M1 state machines.)
