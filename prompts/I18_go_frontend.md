# I18: Go frontend. Codecs, partiality, slice headers, pipelines, loop bounds

Rendered from `docs/BUILD_PLAN.md` §4, I18. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. Milestone M2 scope. It also extracts what M3's OWN and consumer rules need (I35, I38, I39), so M3 never transcribes it by hand. Whitepaper §10.1 Go (all four bullets: codecs from `binary.BigEndian`, constant-offset `copy` and `append` chains; index and slice sites as partiality; slice headers as backing-identity facts; pipelines as consumers), §10.2 (layout algebra, Go rows), §8.3 (partial edges return an option; loops become fuel), the translator rule of §10.1 (fragments the translator does not support become coverage debt, never silent approximations). Part of V10.

**The contract is the docstring of `tests_m2/test_extract_go.py`.** It fixes the CLI, the toolchain pin, the document format, the term/atom/cell grammar, every analysis rule and the honesty rules. `tests_m2/test_extract_go_toy.py` and `tests_m2/test_extract_go_honesty.py` read the same contract. `tests_m2/_i18.py`, `tests_m2/fixtures/go_frontend/` (the planted toy module, its config and the Go instrument) and `spec/M2/lib/go_frontend.json` are instruments and inputs fixed at the prereg. Do not edit them. If one is wrong, raise it as a Question and add an amendment to `spec/M2/amendments.jsonl`, reported under Surprises.

## Goal

Extract the following from go/ssa of the pinned Morph Go code (`/root/work/morph` at `3e44e79`, `config/holon.json` `replay.morph`) into five holon-facts/0.3 documents `spec/M2/facts/morph_{batch, blob, derivation, genesis, nodetypes}.go.extracted.json`:
- the Go header codecs `enc_go_v0`, `enc_go_v1` and `dec_go`, with their error and panic conditions as exact path sets;
- every bounds-checked site, with a status and, for loop sites, a witness range;
- backing identities `(backing, offset, len, cap)` of returned slices, in-place writes, stores and lost writes;
- call edges and producer-to-consumer flow skeletons;
- loop bounds as fuel terms.

None of it may be transcribed from the frozen facts: they are what the extraction is compared with.

## What to build

- **`holon/frontends/go/ssadump/{main.go, go.mod, go.sum}`.** A generic Go program, `ssadump -dir DIR PATTERN...`, pinning `golang.org/x/tools v0.36.0`.
  - It loads with `go/packages`, builds `go/ssa` and prints one deterministic JSON document (`holon-ssadump/0.1`): functions, blocks with dominators, instructions with operands, types, constants, positions relative to `-dir`, and the For/Range statements of each function.
  - **Verified at the prereg:** x/tools v0.36.0 resolves through the network proxy into a scratch module cache. The exact `go.sum` lines are in `tests_m2/_i18.py`. A toy probe of `go/packages` + `ssautil` worked on Go 1.24.7. So there is **no vendoring**: a `vendor/` directory under `holon/frontends/go` is a failure.
  - The extractor builds the helper into `~/.holon/tools/ssadump/<key>/ssadump` with `go build -trimpath` (`GOWORK=off GOFLAGS=-mod=readonly GOTOOLCHAIN=local`), never inside the repo.
  - **If the proxy ever becomes unreachable before the build:** you may fill the user's module cache from a file proxy (`GOPROXY=file://<dir>` holding the same module zips; go verifies them against the pinned go.sum, and nothing enters the repo). Otherwise stop and raise a Question. Do not vendor (the plan's vendoring fallback is a lead/human decision here, through an amendment). A vendored tree would need the human's acceptance, a hash pin of every vendored file, and the `.env` / `bunfig.toml` scan (frozen `tests/test_12_hygiene.py`).
- **`holon/frontends/go/extract.py` (+ `__init__.py`, and further modules of your own if you want them).** The analysis of the contract, in pure Python over the ssadump output:
  - path enumeration with inlining and local memory for loop-free functions;
  - the reasoner;
  - sites;
  - encoders, decoders and predicates, with their matches, absences and patches;
  - backing cases, writes, stores and lost writes;
  - call edges and flows;
  - loops;
  - coverage and assumptions.
  
  It also provides the CLI `python -m holon extract go ...` and the API `FRONTEND_VERSION`, `main`, `extract` and `render`.
- **`spec/schemas/facts_0_3_go.schema.json`.** The Go document. It must reject a bare envelope and another frontend. It uses only the keywords `tests/reference/mini_schema.py` supports.
- **The five committed documents.** Run `python -m holon extract go --milestone M2` and commit the output.
- **`docs/iterations/I18.md`.** Done, Surprises, Questions, Not done. Include:
  - the per-prediction outcome table;
  - the absences and matches;
  - every open site in `morph_batch` and `morph_derivation`, each with its witness when it has one;
  - the coverage debt counts;
  - the run time of one extraction.

## Predictions (spec/M2/predictions.json, key I18), frozen before the extractor first runs on Morph

| id | claim (short) | check |
|---|---|---|
| P1 | enc_go_v0/v1 layouts equal the frozen ones cell for cell; two return paths each (cache, layout) | `TestPredictedCodecs::test_encoder_layouts_equal_the_frozen_layouts` |
| P2 | decoder partiality = ok_go on every length constant ±1 (352 probes), getter reads = frozen | `...::test_decoder_partiality_equals_ok_go_on_every_length_constant_plus_minus_one` |
| P3 | 14 header decoders; BlobVersionedHash v<2, BlobHashesHash v≥2, BlobCommitHash = ok_go | `...::test_the_other_header_getters` |
| P4 | O2 as an absence: no (2, 257) encoder in common/batch; node/types has three absences | `...::test_no_v2_encoder_in_the_codec_package` |
| P5 | **new**: GenesisBatchHeader (ops/l2-genesis) is a standalone v2 encoder | `...::test_a_standalone_version_2_encoder_exists_outside_the_codec_package` |
| P6 | D3: height decoder reads (0, 8) iff len = 60; both block-context encoders' layouts | `...::test_block_context_codec` |
| P7 | node/types' deprecated decoder decodes exactly like common/batch | `...::test_node_types_decodes_like_common_batch` |
| P8 | O36's precondition: TxsPayloadV2 shares blockContexts' spare capacity; Append writes it next | `TestPredictedSlices::test_txspayloadv2_result_shares_the_spare_capacity_of_block_contexts` |
| P9 | batch_data.go writes into parameter-rooted backings: exactly five appends | `...::test_batch_data_write_inventory` |
| P10 | O37: the two EncodedBytes cache writes are lost | `...::test_value_receiver_cache_writes_are_lost` |
| P11 | **O4 localized**: common/batch RetrieveBlobBytes `data[i*32]` (blob.go:49) open for i in 3968..4095; common/blob's copy safe | `TestPredictedPartiality::...from_word_3968` |
| P12 | the derivation loop reaches that site (Start$1 → … → ParseBatch → RetrieveBlobBytes, in the blob loop) | `TestPredictedCalls::test_the_derivation_loop_reaches_the_open_site` |
| P13 | TxsPayloadV2's consumers: common/blob.CompressBatchBytes → zstd → external codec | `...::test_txspayloadv2_consumers` |
| P14 | the loop table (fuel terms, exits, the one unbounded loop as debt) | `TestPredictedLoops::test_loop_bounds` |

Regressions and construction checks R1–R9 are in the key (R9, the real retrieval panicking from word 3968, was a prediction in the draft; its outcome is already recorded in whitepaper App. A F3 and docs/build_plan/gap_map.json, so the prereg review made it a regression): M0/M1/M2 outputs unchanged; the v2 patch and the immediate consumption of TxsPayloadV2 views (both already recorded); format and determinism; toolchain pin; the toy; honesty; soundness against the real decoders.

## Rules

- **Generate, don't hand-write.** The five documents come only from `python -m holon extract go`, byte for byte. Never edit them. A fix goes into the extractor.
- **Never tune to a prediction.**
  - Do not special-case function names, packages, files, lines, lengths (249, 257), blob sizes (4096, 126976, 131072) or field names. Everything target-specific comes from the sidecar or from the code.
  - The rules of the contract are fixed: what counts as an encoder, a decoder, a predicate, a patch, a view, a lost write, an open site; the reasoner's facts; the fuel normal forms; `max_paths` 512, `inline_depth` 4, `flow_depth` 3.
  - A predicted outcome that does not come out is a Surprise, reported with the extracted entry that contradicts it.
- **Inputs are the code.** The extractor reads exactly these: the config, the file its `source` names (`config/holon.json`), the source tree (copied to a temp workspace) and the ssadump output. It never reads `facts/`, `spec/M1/`, `spec/M2/facts/` (its own earlier outputs included), `laws/`, `results/`, `gen/`, `replay/`, `docs/` or `tests*/`. An audit hook checks this on the Morph run.
- **No target vocabulary in `holon/frontends/go/`**, not in docstrings either: no package path, document stem or primitive name of the sidecar, no Morph identifier, no header or blob constant, no source span. Standard-library semantics (`encoding/binary`, `copy`, `append`, `len`, `cap`, `errors.New`, `fmt.Errorf`) are generic and belong in the code. Dependency semantics (`BytesToHash`, `Keccak256Hash`, `Hash.Bytes`) belong only in the sidecar, and each one used becomes a `go-prim:` assumption.
- **No silent approximation.** These all go to coverage debt:
  - unbounded loops;
  - functions over the path limit;
  - inexact layouts;
  - SSA constructs path enumeration does not model.
- **The pinned checkout is never written.** Work on a scratch copy. Skip `.git`, `node_modules`, `.env*` and `bunfig.toml`.
- **Determinism.** Sorted keys and lists as the contract says, relative paths, no timestamps, no absolute paths in the documents.
- **Hygiene.** No `.env` or `bunfig.toml` anywhere, no tool installs or binaries in the repo, no `node_modules`.

## Parallel build with I17 (separate worktrees; the lead merges)

- **I18 owns:**
  - `holon/frontends/go/`;
  - `spec/schemas/facts_0_3_go.schema.json`;
  - the five `spec/M2/facts/*.go.extracted.json`;
  - `docs/iterations/I18.md`.
- **I17 owns:**
  - `spec/schemas/facts_0_3.schema.json` (the shared envelope);
  - `holon/frontends/__init__.py`;
  - the `extract` dispatch in `holon/__main__.py`;
  - the `.extracted.json` exclusion in `holon.diagram.fact_documents`;
  - `spec/M2/facts/morph_header.extracted.json`.
- **The CLI dispatch (agreed with I17 at the prereg).** `holon extract <frontend> ...` goes through I17's generic `holon.frontends.main`, which imports `holon.frontends.<frontend>` and calls its `main`; there is no registry. So `holon/frontends/go/__init__.py` must expose `main`. If I17 has not landed in your worktree, add exactly the minimal versions the contract gives (the dispatch block, the generic `main`, the one-line exclusion), each in its own hunk. The lead keeps I17's at the merge.
- **The shared envelope (agreed with I17 at the prereg).** It is the contract's "Shared holon-facts/0.3 envelope": envelope keys plus all Go content under `go`; I17's schema has a `go` branch for it and I17's own tests check that branch. After the merge, `TestExtraction::test_documents_validate_against_the_shared_envelope_whenever_it_exists` checks the Go documents against I17's schema. A mismatch is the lead's to reconcile, never a reason to change a prediction.
- **G1.** The Go documents are not regenerated by G1 in I18 (your sidecar is not an `extract_*.json`; lead decision at the prereg). Your byte-identity test against the committed files stands in until an iteration reads them as inputs.
- **Never commit the other iteration's outcome paths.**

## Before committing

1. Run every suite: `tests`, `tests_m1`, `tests_m2`.
2. Run `holon gate` for M0, M1 and M2. Pass `--report` to a scratch path; I18 commits no gate report.
3. Run `python tools/freeze.py check` and `python -m holon audit prereg --milestone M2`.
4. Report in `docs/iterations/I18.md`.

The extraction needs the Go toolchain and the module cache. A missing toolchain is a failure with a message, never a skip.
