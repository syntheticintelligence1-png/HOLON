# I35: rule OWN from extracted backing identities

The plan is row I35 of `docs/BUILD_PLAN.md` and its section. Read `AGENTS.md`, `docs/M0_SPEC.md` and
`docs/BEND_PRIMER.md` first. The exact rules (W1-W16) are in the docstring of `tests_m3/test_own.py`; the key is
`iterations.I35` in `spec/M3/predictions.json`.

## Why

- **OWN is the one shape rule with no extracted law.** M1 stated `L_own_txspayload` over a hand-written heap model,
  and nothing states O37, the value-receiver header cache whose write is lost (whitepaper §5.8, case-study rows O36
  and O37).
- **The facts already exist.** I18's Go frontend extracts slice backing identities into the M3 Go document's
  `go.slices` section: which results alias which receiver field, which methods write a backing in place, which writes
  are lost.

## What I35 does

- **Carrier documents (W6).** `holon own --milestone M3` turns the Go document's slice facts into one
  `holon-own/0.1` document per type with a view or a lost write: BatchData, BatchHeaderV0, BatchHeaderV1.
- **Diagram and evidence (W7).** Each method becomes an `OWN.<method>` edge with the fields it reads and writes, so
  every OWN law gets a computed E2 atom.
- **Rule OWN (W8).** Four alias laws on BatchData (each view paired with a writer of the field it returns) and two
  lost-write laws (the headers' `Bytes` caches), under the next free catalog version after I71's.
- **The model (W9).** A generated Go heap model with Go 1.24's append growth (`spec/M3/lib/own.json`, assumption
  A-go-growth).
- **Deciding (W10).** A bounded witness search and counter-laws; heap_disjoint proofs for pairs that never overlap.
- **Replay (W12).** Every witness runs on the real Go code, with the capacities checked against the model's.

## Predictions (counted: P3-P7)

- **P3 (O37).** Both lost writes REFUTED and replayed: `EncodedBytes` stays empty after `Bytes()`.
- **P4 (O36 analogue).** (TxsPayloadV2, Append) REFUTED and replayed, capacities agreeing.
- **P5.** The two pairs that write only past the view's end, (TxsPayload, Append) and (TxsPayload,
  EstimateCompressedSizeWithNewPayload), PROVED by heap_disjoint in both kernels.
- **P6.** (TxsPayloadV2, TxsPayloadV2) UNKNOWN, naming the overlapping write of equal bytes.
- **P7.** Every OWN law has E2.

## Risks

- **heap_disjoint is new proof engineering** (an invariant over traces: distinct modelled fields never share a
  backing). If it slips, P5 misses and the laws stay UNKNOWN with the failing lemma named.
- **The catalog bump** re-derives every M3 law; the record re-make follows I28's and I71's order.
- **Go growth** is an oracle; a replay whose capacities disagree fails P4 and is reported, never tuned.

## Questions for the human (also in the key)

- **Q-I35a.** One writer per alias law (attribution).
- **Q-I35b.** Go's growth as a validated oracle.
- **Q-I35c.** No volatile-view exception until an intent contract declares one.
