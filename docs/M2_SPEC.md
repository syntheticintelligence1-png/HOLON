# M2 spec: automated extraction and the replay harness (plus the parallel M3 groundwork)

Written by the lead before any M2 code. The whitepaper (`whitepaper.md`) is the authority; section numbers below refer to it.

## 1. Exit criterion (§15.2, preregistered here)

M2 is done when both of these hold:

1. **Zero unexplained replay disagreements over a historical window.**
   - **Window:** every `commitBatch*` transaction on the Morph mainnet L1 Rollup proxy in the 14 days before the corpus snapshot, while beacon blobs are still retained. At least 200 commits.
   - **Classification:** each disagreement is classified as an extraction defect, a real defect or an oracle mismatch (§8.7), and every one is explained in `replay/M2/report.json`.
2. **Mutation adequacy ≥ 0.80** (A1, §9.5, §12.1). Over the non-equivalent mutants of the in-scope code, at least 80% must surface as an obstruction after re-extraction. Every miss is labelled as an extraction gap or a rule gap.
   - **In-scope code:** the header codecs plus the M1 Rollup slice.
   - **Mutant set:** frozen in `spec/M2/mutants.json` before the run.
     Frozen 2026-10-11 with 45 mutants (14 Go codec, 11 Solidity codec/loader, 20 Rollup slice), sha256 `d08ec99d1806b0ed9c6b81d78de48978022fac617d7a07a3d89ab8e6a5163672`. The file defines how mutants are applied, the detection rule, miss labels and the evidence needed to call a mutant equivalent.

These thresholds are preregistered: if they are missed, the result is reported, never relaxed.

## 2. Rules for every unit

- **Follow AGENTS.md.** Frozen roots stay frozen. Don't touch `laws/M1`, `spec/M1`, `tests_m1` or `replay/M1`; an open PR is changing them.
- **New schemas:** go under `spec/M2/schemas/`, because `schemas/` is frozen.
- **Extractors and hand-written facts:** extractors never read hand-written facts to produce output. Hand-written facts are used only in tests, as the comparison target.
- **Coverage debt:** anything a frontend cannot translate is recorded as coverage debt, never approximated. Use one JSON file per frontend in `spec/M2/coverage/<frontend>.json`:
  `{"frontend": str, "target_commit": str, "items": [{"element": "<path>:<line> <kind> <name>", "kind": str, "reason": str}]}`, with items sorted by element.
- **Wiring:** don't edit `holon/__main__.py` or `holon/gate.py`. Expose `python -m holon.<pkg>` entry points; the lead wires the CLI and the gate at merge.
- **Targets:** Morph `morph-l2/morph` at `3e44e795586af3e11285b603ab642c67823add51`. Toolchain: `tools/setup_env.sh` (Bend 2.0.36 pinned, Lean 4.34.0), Go 1.24.x, Foundry with solc 0.8.24, Node 22.
- **Determinism:** fixed seeds, sorted output, no timestamps in committed files. Large downloaded data stays outside the repo (cache dir); commit manifests with hashes, plus small fixtures.
- **Branches and PRs:**
  - Branch: `devin/<unix-ts>-m2-<unit>`.
  - One PR against `main`. Do not merge it.
  - The PR body ends with Done / Surprises / Questions for the human / Not done.

## 3. Units (wave 1, parallel)

| Unit | Owns | Deliverable | Acceptance |
|---|---|---|---|
| S1 sol-transitions | `holon/frontends/solidity/` (transitions) | solc AST + Slither IR → transition facts for `Rollup.sol` and `L1MessageQueueWithGasPriceOracle.sol` in the `spec/M1/facts/morph_rollup.json` format → `spec/M2/extracted/morph_rollup.json` (§10.1): storage families, external functions, guards from require and modifiers, reads and writes, principal class | A differ against `spec/M1/facts/morph_rollup.json`: every hand-written guard and write is recovered or listed as debt with a reason; extraction is byte-deterministic |
| S2 sol-layout | `holon/frontends/solidity/layout*` | Straight-line `mstore` sequences in the BatchHeaderCodec libraries (Yul via `solc --ir-optimized`) → layout facts, plus a syntactic Yul→Bend translator for straight-line fragments | Layout-equal (`holon/layout.py`) to the Solidity encoders and decoders in `facts/morph_header.json`; the translated Bend agrees with the generated model on the M0 sample set |
| S3 go-ssa | `holon/frontends/go/` (a Go module using x/tools/go/ssa) | `binary.BigEndian`, constant-offset `copy` and `append` chains → codec facts; index and slice sites → partiality; slice headers → backing facts for OWN | Reproduces the Go side of `facts/morph_header.json` and `spec/M1/facts/morph_batchdata.json` (differ test); debt is recorded |
| S4 link-history | `holon/frontends/link/` | ABI bindings, shared constants (249, 257, Z, 4096×31) and event schemas → `spec/M2/extracted/links.json`. Deployment history from L1 (proxy `Upgraded` events, reinitializer versions, storage-layout diffs between implementations) → `spec/M2/extracted/migrations.json` (§10.1, for NAT in M3) | Every M0/M1 cross-language constant is linked; the migration list matches the on-chain upgrade events |
| S5 hist-corpus | `holon/hist/fetch*`, `replay/M2/corpus/` | Fetcher for the window in §1: tx calldata, blob sidecars (beacon API or blobscan), receipts, and the `committedBatches` / `committedStateRoots` storage after each commit. The corpus format is §4 below | A manifest of ≥ 200 commits with content hashes; re-running the fetch reproduces the manifest |
| S6 hist-replay | `holon/hist/replay*`, `replay/M2/report.json` | Replays the corpus through the compiled model: header decode/encode, batch hash, blob versioned-hash checks, the `commitBatch` transition from the reconstructed pre-state. Compares with the on-chain values and classifies every disagreement (§8.7) | Runs on S5's corpus; until S5 merges, it builds its own fixture of 5 commits in the same format; report per §1 |
| S7 native-harness | `holon/native/` | The compiled model as a callable library: a C library if Bend 2 can emit one (check `bend --help` / `bend guide` first), otherwise a long-lived Node worker speaking JSON lines. A Go harness (cgo or subprocess) and an EVM harness (forge) feed it input sources 1–3 of §8.7: grammar samples, sort boundaries, every witness. Writes per-edge refinement records `replay/M2/refinement/<edge>.json` with agreement counts | All M0 codec edges and the M1 transitions have refinement records, with zero unexplained disagreements |
| S8 lean-kernel | `holon/lean/`, `gen/lean/` | Law IR → Lean 4 emitter (§8.8, §8.9). Re-prove the M0 PAR and round-trip laws (`decide` / `bv_decide`); attempt the M1 unbounded laws. The result-record kernel list gains `lean`, and the independence class becomes I2 when both kernels agree | At least the 5 proved M0 laws re-proved in Lean from the same statement hash; no `sorry` or axioms (G3 extended to `.lean`); canaries rejected in Lean too |
| S9 gate-m2 | `holon/gate_m2.py`, `spec/M2/schemas/` | Result record v2 with the orthogonal fields of §8.6: status incl. split; law and model hash; premises; scope; kernels; independence class; refinement records; replay status; coverage. Gate checks G6 (every REFUTED replayed or labelled model-only), G8 (coverage report from `spec/M2/coverage/*.json`) and G9 (record completeness), each with negative tests | `python -m holon.gate_m2` passes on main and fails on each planted defect |
| S10 refute-engines | `holon/refute_engines/` | §10.5: QF_UFBV solver encoding (z3) of PAR and PAR-domain laws, plus grammar- and sort-boundary fuzzing of the compiled model. Every candidate witness is re-encoded as a counter-law and checked by evaluation | Re-finds the M0 refutations with the solver; finds nothing on proved laws; each witness is kernel-checked |

### Parallel M3 groundwork (Ultra)

| Unit | Deliverable |
|---|---|
| U1 auditor (round 1, §9.5 A3/A4 plus a facts audit) | `docs/audit/round1.md`: vacuity and over-strength of every M0/M1 premise; a source-line audit of `spec/M1/facts/*` against the code; dropped or weakened laws; ranked findings. Docs only |
| U2 M3 law authoring | `spec/M3/proposals/`: IR law drafts plus predictions transcribed from §11.8 for every O1–O37 row and Appendix A item not yet mechanized in M0/M1, each with source citations and the minimal rule. Nothing is frozen; the lead reviews |
| U3 SORT and refined sorts (§7, §7.8) | `holon/sorts/`: sort grammar, affine rules, widths, principal and amount sorts, writer provenance, inference over the extracted or hand facts; sorts compiled to Bend types with coercion obligations; a SORT law class covering O20, O21, O27 and O28 |

## 4. Historical corpus format (S5 writes, S6 reads)

`replay/M2/corpus/manifest.json`:

```
{"chain": "ethereum-mainnet", "rollup_proxy": "0x...", "window": {"from_block": n, "to_block": n},
 "commits": [{"batch_index": n, "tx": "0x..", "block": n, "method": "commitBatch|commitBatchWithProof|...",
   "calldata_sha256": "..", "blob_versioned_hashes": ["0x.."], "blobs_sha256": [".."],
   "post": {"committedBatches": "0x..", "committedStateRoots": "0x..", "lastCommittedBatchIndex": n}}]}
```

- Commits are sorted by `batch_index`.
- Raw calldata and blobs live in a cache dir (`$HOLON_CACHE`, default `~/.holon/cache/m2`), keyed by sha256.
- `replay/M2/corpus/fixtures/` holds at most 5 full commits for the tests.

## 5. Wave 2 (after the wave-1 review)

- The A1 mutation-adequacy harness, built on the S1–S3 extractors, against the frozen `spec/M2/mutants.json`.
- Linking the extracted facts into the model generator in place of the hand facts, with a refinement comparison.
- M3: NAT over `migrations.json`; FACT product programs; SYM; intent contracts (G10) and the intent lane; mechanizing the U2 laws.
