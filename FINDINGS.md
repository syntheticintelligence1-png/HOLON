# I67 (= I38a) feasibility findings — Bend model of the O4 loop at real size

## The question
O4 (common/batch.RetrieveBlobBytes) panics at field element 3968 (data[i*32], len(data)=126976,
i*32>=126976 iff i>=3968). The prereg prediction is O4 REFUTED at real 4096-element size. The risk
(BUILD_PLAN I38): the counter-law must check in bend2 AND BendTT (Q22: no fuel re-pin), and a naive
model is O(n^2) / blows the 4e8 kernel fuel.

## What blows the kernel fuel
bend2 FUEL is shared across the whole check (bendtt.lean FUEL=4e8, lazy wnf/conv, min-threaded).
- Pure Nat recursion: 16384 steps in 0.3 s (cheap).
- Per-step U32 arithmetic is the killer: U32 = Word(32n), so each U32 op (add/mul/compare) is ~32
  bit-level reductions, and it costs the same whether the value is 0 or large (add-zero is as slow as
  add-one). Measured (nested fuel loop, one U32 add/step): 4096 steps ok (~5s), 16384 FAIL (out of fuel).
  A flat-array model with i*32 / i*31 per step fails verdict at 2048 iterations.

## The design that works (both kernels, real size)
Consume the blob STRUCTURALLY as a List of 4096 field elements (one U32 per element = its high-order
byte, the only byte blob[i*32] reads). Carry the element index as a **Nat**, compare against the panic
threshold 3968n with Nat.is_le. Single fuel-driven `run` loop (Res = Next|Fin), non-recursive `step`
(no mutual recursion — Bend forbids it). No per-step U32 multiply.
  - Witness W = List.replicate(U32,3968n,0) ++ [1]  (byte 126976 nonzero, element 3968's high byte)
  - law cl_tot: { ok(W) == False : Bool }   (ok = not panic)
  - bend2: 0.84 s ; BendTT --verdict: 2.75 s   -> BOTH well within 120/180 s budget.
Spike: scratchpad/i67/struct/{M,LAWS,PROOF}.bend (ALL PROOFS CHECK in both).

## Consequence for the prereg
O4's 3 REFUTED laws (P6 totality batch, the P4 E6 clone-pair, P5 domain coherence) are both-kernel
feasible at real 4096 size -> predict REFUTED (not UNKNOWN). The 5 UNKNOWN are the positive/∀ totality
laws (no induction route, I24 gap G6) — unchanged.

## Bend gotchas hit
- defs must precede use; NO mutual recursion (fold the branch helpers into a single `run` over fuel).
- affine: a pattern binder reused (e.g. the index i used in both St{t,1n+i} and branch(...,i)) needs
  `case St{hs, +i}:`.
- List.concat is for a list-of-lists; use List.append(&2, T, a, b) for two lists.

## Model faithfulness note for the build
The structural list element = the field element's HIGH byte (blob[i*32]); the 31 payload bytes
(blob[i*32+1 : i*32+32]) are not read by the panic check, so the carrier for the O4 partiality law need
only carry the high bytes. The copy into data[i*31:i*31+31] is the safe site (proved elsewhere); the
open site is data[i*32] in the error-format path. The extractor (holon-go-frontend/0.2) still records the
real i*32 index arithmetic in the facts; the Bend GENERATOR compiles the counted loop to this structural
form (fuel = the loop's limit 4096, index as Nat), which is where the kernel-cost fix lives.
