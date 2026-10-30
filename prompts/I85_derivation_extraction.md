# I85 (= I39a): the Go derivation extracted and the product machine, no laws

Rendered from `docs/BUILD_PLAN.md` §4 I39 and its row I85 (whitepaper §5.1 consumer and cycle, §5.5, F11, §10.1 Go, §8.7 refinement), and from the human answers Q12 (real code over stand-ins) and Q19 (extracted facts are the input of every M3 law) in `docs/HUMAN_ANSWERS.md`. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first.

The exact rules (D1-D6, J1-J3, K1-K5, G1-G5, C1-C5), commands, formats, exit codes, shared files, commit rules and the definition of I85's own commits are in the docstring of `tests_m3/test_derivation_extraction.py`. The key's thresholds pin that docstring, the instrument `tests_m3/_i85.py`, the sidecar `spec/M3/lib/derivation.json` and five inputs by sha256. The base is `92c98e40`, the lead, with BUILD_PLAN's row I85 committed before C_K.

## Why a separate key

BUILD_PLAN I39 (Go derivation and product machine) predicts O7 REFUTED (PAR-cycle), the O8 law pair under HypC with a split, O24 REFUTED and the F11 L1-count law REFUTED. Those laws need three things that are not laws:
- `ParseBatch` as an extracted consumer, so a law over derivation is a law over the code's own control and data flow;
- the product machine, so a law can say "the Rollup committed this, and derivation made that of it";
- a Go replay through `BatchInfo.ParseBatch`, so the consumer model is refined on the real code before any witness depends on it.

So they go first, under their own key, as I69 (= I36a) and I80 (= I37a) did for Bundles I and II. I85 is numbered I85 only because prereg keys must be plain numbers (I80-I89 are this lane's sub-keys). I39 keeps its number, its plan text and its predictions.

## Dependencies

- **Done, read here:** I18 (the Go frontend and its derivation document), I20 (the adopted Rollup document, its harness rule for headers and its deployment), I67 (the M3 Go document; the frontend's 0.2 config, not used here), I80 (its deployment record of I20's deployment).
- **After I85:** I39 proper (the laws). A Bend product model, if a law needs one, is I39's.

## What I85 does

1. **The document (D1-D5).** `holon derivation extract` runs I18's frontend, unchanged, with I18's own config `spec/M2/lib/go_frontend.json`. From the same ssadump run it adds one key, `consumer`, to the `morph_derivation` document and writes `spec/M3/facts/morph_derivation.extracted.json` (the plan's name; the frontend's own `.go.extracted.json` name stays I18's). Less that key, the document is I18's byte for byte. The consumer section holds:
   - the SSA of `ParseBatch` and of every function it reaches by static calls inside the six extracted packages (I18's skeleton: `ParseBatch -> common/batch.RetrieveBlobBytes`, the header getters, the block-context decoder, the transaction queue);
   - the SSA of the join function `unpackModernRollupCall`;
   - the environment: every callee outside the closure, each named by kind:
     - Go standard-library semantics, holon/derivation's table: `fmt.Errorf`, `errors.New`, `bytes.NewReader`, `encoding/binary`, `math/big`;
     - the real library, the sidecar's boundary: the zstd decompressor (the decompression half of I38's HypZ) and the transaction-stream decoder (go-ethereum's codecs), answered by a generated Go helper;
   - its coverage: an instruction the interpreter cannot evaluate, or a callee or global of no kind, is listed as unaccounted, never dropped.
2. **The consumer model (G1-G3).** An interpreter of that SSA under `holon/derivation/`, outside every generator closure: Go integer, slice, struct, pointer and interface semantics, Go's runtime panics with their texts, and "unsupported" for anything else.
3. **The product machine (J1-J3, K1-K5).** Evaluator-level, as I80's linked machine is:
   - a commit step runs the adopted Rollup document's `commitBatch` through `holon.extracted_eval`, from I80's deployment record;
   - a committed batch is derived: its batch is made from the commit's input by the join, the field map the derivation's own calldata decoder writes, read from the document;
   - the next commit's parent header is the header the Solidity model committed: the argument of the keccak256 its `committedBatches` write stores. That is §5.1's cycle (`CB_i` re-presented as parent).
4. **The Go replay (G4-G5).** A test generated from the sidecar and the document runs the real `BatchInfo.ParseBatch` on every corpus batch, in a scratch copy of the pinned checkout. It records the status, the error and panic texts, and the receiver's dump.
5. **The corpus (C1-C3).** Fixed in the sidecar at this prereg by `tests_m3/_i85.py::corpus`:
   - 29 planted batches, chosen by reading `ParseBatch` to end at each of its returns and at the blob decoder's panic (O4's site, reached through derivation);
   - 120 random batches: well-formed, with at most one mutation;
   - 8 product traces of 20 commits.

   Raw payloads are compressed by the real compressor and packed into canonical blobs.
6. **The comparison (C4-C5).** Every case is compared on the model and on the real code: status, error text, panic text and the whole receiver.

The outcome paths are `spec/M3/facts/morph_derivation.extracted.json`, `gen/M3/derivation/`, `results/M3/derivation/`, `replay/M3/derivation/` and `docs/iterations/I85.md`.

## Deviations from the plan's text, and why

- **No laws.** The plan's predictions stay with I39.
- **The consumer is extracted as SSA, not as path summaries.** I18's frontend enumerates paths of loop-free functions only, and its 0.2 loop bodies (I67) treat loop-carried values as opaque. `ParseBatch` has two loops whose carried values (the compressed buffer, the queue's pointer, the transaction counts) decide its outputs. So the consumer is the dumped SSA itself, which the interpreter runs exactly. The frontend's document, including I18's skeleton edges, is kept unchanged beside it.
- **Two callees are answered by the real library.** These are the zstd decompressor (cgo over a Rust library: no Go to extract) and the transaction-stream decoder (go-ethereum's RLP and typed-transaction codecs). Both boundaries are named in the sidecar and listed in the document. The decoder's own stream rules are therefore the library's, not the model's. That matters to O8's in-stream trailing bytes, so it is a Question for I39.
- **The blob hash is a stand-in.** The derivation reads no blob hash, and the Rollup treats blob hashes as words. So the product hashes a blob as 0x01 followed by bytes 1..31 of its sha256, not by KZG. I39 may need the real versioned hash for O8's HypC (a Question).
- **The `node/` dependency risk.** The plan's fallback is "if the `node/` dependencies fail to download, laws stay UNKNOWN". The dependencies are in the module cache: `go build ./derivation/` in a scratch copy of `node/` succeeded with the proxy off before this prereg. If the build environment lacks the cache, the replay is refused (exit 2) and P5 and P6 are UNKNOWN, reported.

## What was known before this prereg (disclosed)

**Nothing was read from the network.** In `/root/work/morph`, a partial clone, every git command ran with `protocol.allow=never`. The Go build ran with `GOPROXY=off`.

**Sources read**, at the head `3e44e795`:
- `node/derivation/batch_info.go`, in full;
- in `node/derivation/derivation.go`: the fetch, `UnPackData`, `unpackModernRollupCall`, `parseBatch`, `handleL1Message`, `derive`;
- in `common/batch`: the `BatchHeaderBytes` getters and `validate`, `RetrieveBlobBytes`, `DecodeTxsFromBytes` and its helpers;
- `common/codec/zstd/codec.go`;
- `node/types` `DecodeBlockContext`;
- the go-ethereum fork's `RPCRollupBatch` and `SafeL2Data`, and the DA codec's Go binding, both in the module cache;
- in `Rollup.sol`: the commit path, `_commitBatch` and `_computeBlobVersionedHash`;
- the queue's `getFirstUnfinalizedMessageEnqueueTime`.

P1's closure and environment, P2's join, P3's read set and P6's live and dead returns come from these readings. They were not computed by running anything.

**Committed records read:**
- I18's derivation document: `ParseBatch` has paths null with reason "loop", and its sites;
- the adopted Rollup document's `commitBatch` record: its calls, its parameter, and its `committedBatches` write term, which holds the header as a memory region;
- I17's header document;
- I20's harness: its header rule, its genesis and its actors;
- I80's deployment record.

**Runs:**
- `go build ./derivation/` in a scratch copy of the workspace, to settle the plan's risk: 66 s, success;
- the instrument's corpus and genesis check: I20's genesis header hashes to the deployment's `committedBatches[0]`;
- an RLP self-check of the generated transactions with an independent decoder (session-only, not committed);
- `git show` of `batch_info.go` for the return lines;
- the generator closures, computed with holon's own functions.

**Never run on the target before this prereg:** ssadump, the frontend, the interpreter, the Go replay, the oracle, the compressor, or `holon.extracted_eval` on `commitBatch`.

**I39's outcomes and this key.** P3's read set shows by itself that `ParseBatch` never reads the batch's `NumL1Messages`. That is the observation behind F11's L1-count law. The plan stated I39's predictions before this key. The random corpus is not designed to decide I39's laws:
- every random batch is well-formed but for at most one error-making mutation;
- its L1 count is the contexts';
- no mutation moves the last block number or adds trailing transactions.

Still, I39's prereg must disclose what I85's records show.

## Risks for the build

1. **The interpreter's coverage.** An SSA construct it does not evaluate makes the case unsupported, which misses P5. The supported set is go/ssa's ops minus channels, maps, select, go and defer, none of which `ParseBatch`'s closure should hold. If one does, it is listed in P1's coverage, which misses P1.
2. **Go's exact texts.** `fmt.Errorf`'s verbs (`%v`, `%d`, `%x`) and the runtime's panic texts must be reproduced exactly, or P5 misses on that case.
3. **The dump.** Unexported fields are read by reflection in the Go test, and nil and empty slices differ. A dump difference is a disagreement.
4. **Inputs.** The corpus's transactions are generated RLP. A malformed one makes a product commit underivable, which misses P4. It is never repaired after the prereg.
5. **The product's Solidity half.** Every planned commit must pass the Rollup's checks under the declared environment, and an unsupported evaluator step misses P4.

## The build branch and commit sequence

1. `holon/derivation/`: `extract` (the document), the interpreter and natives, the oracle and replay generators, `corpus`, `product`, `refine`, and the dispatch line in `holon/__main__.py`.
2. The outputs: the document, the corpus, the product, the refinement and the replay report.
3. The report `docs/iterations/I85.md`, with every miss stated plainly.

No record is re-made: I85 moves no generator closure. CI runs the gates, which must not move.

## Predictions (key I85 in `spec/M3/predictions.json`)

- **P1, the consumer extracted as read.**
  - The document is I18's plus the consumer section.
  - The closure is the 14 functions of `thresholds.closure`.
  - The environment is the 13 callees of `thresholds.environment`, each of the predicted kind: 9 natives, 2 oracles, 1 slice length, 1 encoding.
  - Nothing is unaccounted.
- **P2, the join.** The seven rows of `thresholds.join`. Every member of the commit's input reaches the derived batch, and `withdrawalRoot` lands in `WithdrawRoot`.
- **P3, the read set.** `ParseBatch` reads `BlockContexts`, `LastBlockNumber`, `ParentBatchHeader`, `PostStateRoot`, `Sidecar.Blobs`, `Version` and `WithdrawRoot` of its batch. It never reads `NumL1Messages`, `PrevStateRoot`, `Hash`, `CurrentSequencerSetBytes` or `Signatures`.
- **P4, the product.**
  - Every planned commit of the 8 traces is ok on the Rollup document.
  - Every committed header hashes to the word written.
  - Each next parent is that header.
  - Every version 1 and 2 commit derives ok, with the committed index as `batchIndex`.
  - Every version 0 commit fails derivation with "invalid batch: zero block count": a modern commit carries no calldata contexts, so a version 0 batch has no blocks.
- **P5, refinement.** On all 169 cases (29 planted, 120 random, 20 product), the model agrees with the real `ParseBatch`, with 0 disagreements and 0 unsupported.
- **P6, reach.**
  - Each of `ParseBatch`'s 15 live returns ends at least one agreeing case.
  - Its 5 dead returns end none. They re-check what an earlier call validated, or decode exactly 60 bytes.
  - The blob decoder's panic, "runtime error: index out of range [126976] with length 126976", is reached through derivation.

**Regressions:**
- **R1.** I18's five Go documents and I67's M3 document re-extract byte for byte.
- **R2.** The commit rules: no closure file, frontend or spec file but the document, and nothing outside I85's paths.
- **R3.** Both prereg audits pass, and CI's gates do not move.
- **R4.** `holon/derivation/` is generic and outside every closure.

## Earlier tests amended at this prereg

None.

## Questions for the human

- **Q-I85-a (the decoder boundary).** The transaction-stream decoder is answered by the real library. Its own rule that a zero type byte ends the stream is therefore the library's, not the model's, and O8 concerns trailing payload. Should I39 extract `DecodeTxsFromBytes` too? That means an oracle for go-ethereum's RLP and typed-transaction decoding at the call sites of its helpers. Or is "the stream decoder is environment" an acceptable premise for the O8 pair?
- **Q-I85-b (blob hashes).** The product hashes blobs with a stand-in, not KZG. O8's HypC binds the blob through its versioned hash. Should I39 compute real versioned hashes, through the oracle and go-ethereum's `kzg4844`?
- **Q-I85-c (I39's prereg).** I85's records make F11's L1-count observation visible (P3), and possibly others. I39's prereg will disclose them. Do you want I39's counted predictions limited to what I85 does not show?

## Rules

- `AGENTS.md` throughout. Never edit a frozen file, the frontend, a closure file, `spec/` (but the document), `laws/`, `holon/rules/`, or any earlier key's output.
- The instrument and the sidecar are fixed at the prereg. A wrong instrument is a Question plus an amendment line in `spec/M3/amendments.jsonl`, never a silent edit.
- A missed prediction is a result. Report it; never adjust a rule, an input, the corpus or a budget to make it hold.
- The target repository is read through git objects with lazy fetching disabled, and is never written.
- Never fetch, clone or read `scroll-tech/*` or `spec/heldout/`.
