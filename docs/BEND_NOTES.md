# Bend 2 notes (P0 calibration, measured in this repo)

Every claim here was produced by running the pinned checker. It answers the three open questions in BEND_PRIMER §6 and records what M1 needs to know.

**Environment.** Bend 2.0.36 (`bendlang/bend@2343aec`, which is also upstream HEAD on 2026-10-11), run as `bun 1.4.2 bend2/main.ts` via `tools/install_bend.sh`. Lean 4.34.0 for `--verdict`. Linux x86-64 container.

## 1. Does `--verdict` work? (BEND_PRIMER §6, Q1)

Yes. It needs Lean `v4.34.0` on PATH, either through elan or `$BENDTT`.

- **Kernel build.** The first `--verdict` run builds the BendTT kernel from `bend2/bendtt.lean`, which takes about 38 s. Later runs reuse the cached kernel.
- **Verdict on the probes:**

| Probe | `bend --verdict` | Wall time (cached kernel) |
|---|---|---|
| p01_law_refl | ALL PROOFS CHECK | 38.1 s (includes the kernel build) |
| p07_codec_equal | ALL PROOFS CHECK | 0.21 s |
| p09_counterlaw_forall | ALL PROOFS CHECK | 0.21 s |
| p11_counterlaw_exists | ALL PROOFS CHECK | 0.22 s |
| p12_fn_premise | ALL PROOFS CHECK | 0.20 s |
| p05_unsafe | SOME PROOFS FAIL ("2 defs rely on unsafe or foreign code") | 0.18 s |
| p02_false_refl | SOME PROOFS FAIL (bend2 rejects it before the kernel runs) | 0.18 s |

- **M0 results.** All 8 M0 proof and counter-law files pass `--verdict` in 0.8–1.2 s each, at Morph header scale (257 one-byte fields). `holon run` records `kernel.verdict = "checked"`, and gate check G7 re-runs it.
- **How it works.** `bend2/main.ts:cli_verdict` refuses any `@unsafe` or foreign def outside Base, then `Safe.safe_check` translates the book and checks it with the Lean-built kernel. A disagreement is reported as a bend2/kernel mismatch.
- **Install note.** In this sandbox, `release.lean-lang.org` and `bend-lang.com` are blocked by the proxy, so elan's own download fails. The workaround: download `lean-4.34.0-linux.tar.zst` from the GitHub release, extract it, then run `elan toolchain link leanprover/lean4:v4.34.0 <dir>`. `tools/setup_env.sh` automates this.

## 2. Installer binary vs. checkout (BEND_PRIMER §6, Q2)

**Not verified.** `https://bend-lang.com/install.sh` is blocked by this environment's proxy (`403` on CONNECT). The checkout runner at the pinned commit is the only one exercised here. All 16 probes pass with it (`tests/test_02_bend_probes.py`). The checkout runner reads `bunfig.toml` and `.env`, so GENV must stay first in the gate.

## 3. Scale limits (BEND_PRIMER §6, Q3)

Setup: `bend/notes/scale_gen.py N` generates an N-field `U32` record, an EVM-style encoder (overlapping 32-byte `put`s into dirty memory, then `take`), a Go-style encoder (direct `put`s into zeros), and the law that the two are equal, proved by `match` then `{==}`.

| N (fields = bytes) | `bend` check | `bend --verdict` |
|---|---|---|
| 300 | 0.34 s | 0.79 s |
| 1 000 | 0.85 s | 11.1 s |
| 3 000 | 6.7 s | 322 s |
| 10 000 | **fails**: "the machine stack overflowed (a deep recursion, or a literal too large to expand)" after 27 s | not run |

**Reading the numbers:**
- **bend2 cost.** bend2 is roughly linear up to 1 000 fields and degrades past that. Somewhere between 3 000 and 10 000 it overflows its stack: the term is too deep, not too slow.
- **BendTT cost.** The BendTT kernel is strongly superlinear, about ×13 from 300 to 1 000 fields and ×29 from 1 000 to 3 000. A dual-kernel certificate is cheap below about 1 000 terms per law and impractical above about 3 000.
- **Consequence for M1.** State-machine models must not flatten state into one wide record. The M1 model should keep register families as small records per index, write laws over a symbolic index (one batch `i`, plus its neighbours where a law needs them), and prove step lemmas per action rather than unfolding long traces. A single law should stay below about 1 000 fields so that G7 stays in the gate budget.

## 4. Things the primer gets wrong or leaves out

1. **Compiled `Bool` is a JS boolean.** In an ES module from `-o x.mjs`, a `Bool` crosses as JS `true`/`false`, not `{$: "True"}`. BEND_PRIMER §5.6 says otherwise. `holon/js/eval.mjs` handles booleans. Maybe and List are constructor objects as documented.
2. **Definitions are order-sensitive.** A def can only call defs written above it (only `@unsafe` defs may call forward). The model generator therefore topologically sorts fact functions: decoders come after their guards. Types are exempt.
3. **Nat patterns compose with literals.** A def that matches `0n / 1n / 2n / 3n+p` reduces on `U32.to_nat(1)` applied to a literal. This is what makes per-version dispatch provable by computation: `hdr_version(pin(h))` becomes `1n` after the binder is opened.
4. **Lemmas with explicit equality types work as proof helpers.** `PROOF.bend` can declare `def lemma(n: Nat, t: List<&2,U32>) -> {M.f_at(n, t) == M.g_at(n, t) : Bool}` and call it inside a law proof. It is a fresh name, so it cannot shadow the model. The `version_split` generator uses this to prove the domain-coherence law for all byte strings when the two validators agree (mutation MUT3 → PROVED).
5. **Undefinedness has to propagate.** The model encodes a revert or unwritten memory as a byte value ≥ 256. Composition does not propagate it automatically: `dec_go([0xDEAD])` is a well-defined `None`. The refuter therefore checks every intermediate subterm for definedness, not only the claim's two sides. The test oracle caught this; see `holon/refute.py:subterms`.
6. **The `--verdict` kernel is the expensive one.** See §3. Budget G7 separately from G5.
