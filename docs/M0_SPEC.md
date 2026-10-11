# HOLON M0 specification: Morph header laws, end to end

M0 is the first milestone of HOLON v2 (whitepaper §15). Its purpose is to run the full factory loop once, on a small, known target:

> facts → model → frozen laws → proof or counter-law → gate (with canaries and tamper resistance) → replay on real code

Everything an agent needs is in this file, `docs/BEND_PRIMER.md`, and the frozen inputs. The whitepaper (`docs/HOLON_v2.md`, if present) is background. Do not build anything beyond M0.

## 1. Frozen inputs (never edit; `tools/freeze.py check` enforces this)

| Path | What it is |
|---|---|
| `facts/morph_header.json` | Hand-extracted facts for morph-l2/morph @ 3e44e79. Covers: the Solidity commit-path header encoder (`enc_sol`), the Go encoders (`enc_go_v0`, `enc_go_v1`), the length/version validators (`ok_sol`, `ok_go`), the Go getters (`dec_go`), and the expected decoded view (`view`). Each op carries the source line it models. |
| `laws/M0/L_*.json` | The 8 law statements, in law IR `holon-ir/0.1`. |
| `laws/M0/REGISTRY.json` | Statement hashes for those laws. |
| `predictions/M0.json` | Preregistered outcome per law. |
| `predictions/M0_mutations.json` | Planted bugs and how outcomes must move. |
| `schemas/*.schema.json` | Schemas for facts, law IR, result records, and the gate report. |
| `tests/` | Acceptance tests and the trusted oracle `tests/reference/`. |
| `bend/probes/` | Verified Bend probes. |
| `docs/BEND_PRIMER.md` | The Bend primer. |
| `docs/M0_SPEC.md` | This specification. |
| `AGENTS.md` | Standing agent rules. |

If you believe a frozen file is wrong, stop and report it. Do not work around it.

## 2. The eight laws and their predicted outcomes

| Law | Claim (premises in brackets) | Predicted |
|---|---|---|
| L_par_hdr_v0 | `enc_sol(h) == enc_go_v0(h)` [version=0, ssvh=0] | PROVED |
| L_par_hdr_v1 | `enc_sol(h) == enc_go_v1(h)` [version=1, ssvh=0] | PROVED |
| L_par_hdr_v2 | `enc_sol(h) == enc_go_v1(h)` [version=2, ssvh=0] | REFUTED: byte 0 is 2 vs 1 (finding) |
| L_par_hdr_ssvh | `enc_sol(h) == enc_go_v1(h)` [version=1] | REFUTED: first difference in bytes 185..216 (intent question) |
| L_dom_hdr | `ok_sol(b) == ok_go(b)` | REFUTED: a version-0 header longer than 249 bytes, Solidity true / Go false (finding) |
| L_rt_go_v0 | `dec_go(enc_sol(h)) == Some(view(h))` [version=0, ssvh=0] | PROVED |
| L_rt_go_v1 | same [version=1, ssvh=0] | PROVED |
| L_rt_go_v2 | same [version=2, ssvh=0] | PROVED |

ssvh means `sequencerSetVerifyHash`, which Solidity always writes as `bytes32(0)`.

## 3. Law IR (`holon-ir/0.1`)

```json
{"ir_version": "holon-ir/0.1", "law_id": "L_...", "milestone": "M0", "rule": "PAR",
 "facts": "facts/morph_header.json", "facts_sha256": "<hex>",
 "statement": {"forall": [{"name": "h", "type": "Header"}],
               "assume": [{"eq": [{"field": "version", "of": {"var": "h"}}, {"bytes": "0x01"}]}],
               "claim":  {"eq": [{"call": "enc_sol", "args": [{"var": "h"}]},
                                 {"call": "enc_go_v1", "args": [{"var": "h"}]}]}},
 "notes": "...", "evidence": ["E1"]}
```

- **Terms:** `{"var"}`, `{"bytes": "0x.."}`, `{"field", "of"}`, `{"call", "args"}` (calling a function from facts), `{"some"}`.
- **Propositions:** `{"eq": [a, b]}` only.
- **Binder types:** `Header` (a record of byte fields, widths in `facts.types.Header`) and `Bytes`.
- **Statement hash:** `"sha256:" + sha256(canonical_json({ir_version, law_id, rule, facts_sha256, statement}))`.
- **`canonical_json`:** `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`.
- `notes` and `evidence` are metadata and are not hashed.

## 4. Function semantics (what the model must compute)

`tests/reference/ref_model.py` is the normative interpreter. Your model must agree with it on every input.

| Function | Signature | Semantics |
|---|---|---|
| `enc_sol` | `Header → Bytes` | EVM memory starts dirty (unknown). Apply `ops` in order: `mstore` writes 32 bytes, `mstore8` writes 1 byte. Ops with `"when": {"version_ge": k}` run only when `version ≥ k`. Output is the first `length_by_version[version]` bytes. Defined for version ≤ 2; version > 2 reverts. |
| `enc_go_v0`, `enc_go_v1` | `Header → Bytes` | Zero-initialized buffer of `length` bytes. Apply `set_byte` / `put_uint64_be` / `copy` at their offsets. The Header's `version` field is ignored: Go writes a constant. |
| `ok_sol`, `ok_go` | `Bytes → Bool` | First matching rule wins. `"empty"` applies when `len == 0`. `version_in` tests byte 0. `len_ge` / `len_eq` test the length. `"otherwise"`. |
| `dec_go` | `Bytes → Maybe<Fields>` | `None` if `ok_go(b)` is false. Otherwise `Some` of the getter slices `b[offset:offset+width]` in getter order, skipping getters whose `when` fails for version `b[0]`. |
| `view` | `Header → Fields` | The header fields named in `order`, as byte strings, skipping those whose `when` fails for the header's version. |

**Canonical JSON for values** (inputs, outputs, witnesses, `difference`):

| Value | JSON form |
|---|---|
| Bytes | `"0x" + lowercase hex` |
| Bool | `true` / `false` |
| Fields | list of hex strings |
| Maybe<Fields> | `null`, or the list |
| Header | an object of `field → hex`, with exactly the field widths |

## 5. Interfaces the tests call

### Python API (package `holon/`)

- `holon.layout.layout(facts: dict, fn: str, version: int) -> list[list]`
  - Returns a symbolic byte layout of an encoder. Each cell is one of:
    - `["field", name, k]`
    - `["const", v]` (zero padding is `["const", 0]`)
    - `["unknown"]` (dirty EVM memory)
  - Memory size is at least the output length.
- `holon.ir.canonical_json(obj) -> bytes`
- `holon.ir.statement_hash(law) -> str`
- `holon.ir.load_laws(milestone="M0", root=None) -> list[dict]`
- `holon.model_eval.eval_batch(fn: str, inputs: list, facts_path: str | None = None) -> dict`
  - Returns `{"engine": "bend-...", "source": <path to the generated model .bend>, "artifact": <compiled file actually executed>, "artifact_sha256": <hex>, "outputs": [canonical JSON values]}`.
  - The artifact must be the compilation of `source` with the pinned Bend (the test recompiles it and compares hashes). Evaluating in Python does not count.

### CLI

```
python -m holon run  --milestone M0 [--facts PATH] [--out DIR] [--gen-dir DIR] [--no-registry]
python -m holon gate --milestone M0 [--root DIR] [--report PATH]
```

**`run`:**
- Defaults: `--facts facts/morph_header.json`, `--out results/M0`, `--gen-dir gen/M0`.
- Exits 0 when every law ended in some status, including UNKNOWN.
- Without `--no-registry`, refuses to run if any statement hash or the facts hash differs from `REGISTRY.json`.
- With `--no-registry` (used by the mutation tests), sets each law's `facts_sha256` to the given facts' hash and recomputes statement hashes.

**`gate`:**
- Always writes the report: default `results/M0/gate_report.json`, valid against `schemas/gate_report.schema.json`.
- Exits 0 iff `passed`.
- Operates on `--root`, a full copy of the repo.

## 6. The pipeline (`run`)

For each law, in `law_id` order:

1. **Model.** Generate `GEN/model/morph_header.bend` from the facts. It must be generated (no hand-written model); see BEND_PRIMER §5.1.
2. **Proof attempt.**
   - Emit `GEN/<law_id>/LAWS.bend`, containing exactly one law named `law_id.lower()`, which imports `../model/morph_header.bend as M`.
   - Emit `GEN/<law_id>/PROOF.bend` from a **proof generator**. M0 needs only "open the record, then `{==}`".
   - Run Bend in that directory. PROVED iff exit 0, the first line is `ALL PROOFS CHECK`, and the law is present.
3. **Refutation.**
   - Search deterministically (fixed seeds) for a witness, evaluating the claim on the compiled model, never on the oracle.
   - On a hit, overwrite the directory with a counter-law `cl_<law_id.lower()>` in the `exs` form (BEND_PRIMER §5.4), with the witness as a literal.
   - REFUTED iff Bend accepts it.
4. **Otherwise UNKNOWN.** Delete the directory and record `bound` (what was searched) and `attempts`.
5. **Record.** Write `OUT/<law_id>.json` (schema `result_record`), then `OUT/summary.json` = `{law_id: status}`.

**Result record rules:**
- Artifact paths are relative to the repo root when inside it, absolute otherwise.
- `kernel.version` = `bend version`.
- `premises` has one readable string per `assume` clause, at least.
- `difference` = `{"lhs": .., "rhs": ..}` at the witness, in canonical JSON.
- `replay.status` = `"not_run"` until P5.

**Triage:**
- REFUTED laws default to `"finding"`. Overrides live in `config/triage.json`: `{"M0": {"L_...": {"triage": "intent_question", "why": "..."}}}`. Triage is a recorded judgment with a reason, never silent.
- PROVED and UNKNOWN use `"none"`.

**Determinism:** two runs on the same inputs produce byte-identical files under `GEN/`. No timestamps, no unseeded randomness.

**Commit:** `gen/M0/` and `results/M0/`. Do not commit `build/`.

## 7. The gate (`gate`)

Checks run in this order. GENV runs first.

| Check | Passes when |
|---|---|
| GENV | No `bunfig.toml` or `.env` anywhere under root, and `bend version` equals the pinned version. **If either file exists, do not invoke Bend at all**: mark every other check failed ("skipped: unsafe environment") and write the report. |
| G2 | Every `laws/M0/L_*.json` hashes to `REGISTRY.json`, the registry lists exactly those laws, and the facts hash matches. |
| G1 | Regenerating into a temp dir yields identical `gen/M0/**/*.bend` files (same set, same bytes) and an identical `summary.json`. |
| G3 | No escape hatches in any generated `.bend` file: `@unsafe`, `def name?(`, `?name` / `?TODO`, `import "` foreign code. The checker output reports no TODO and no unsafe or foreign reliance. |
| G5 | Every PROVED or REFUTED law's `PROOF.bend` re-checks from scratch: exit 0 and `ALL PROOFS CHECK`. |
| G11 | Every law has a result record. Every checked `LAWS.bend` states exactly its expected law: `[law_id.lower()]` or `["cl_" + law_id.lower()]`. This guards against vacuous files (BEND_PRIMER §3.1). |
| G4 | At least 10 canaries of at least 3 kinds, all rejected by Bend. |

**Canaries (G4):**
- A canary is a law produced by mutating a PROVED law and emitting it through the same emitter and proof generator. It is kept only if the model gives a concrete counterexample.
- Required kinds: `pin_const` (change a pinned constant), `swap_fn` (swap a call for another function of the same type), and `negated` (a counter-law of a true law, at a point where it holds).
- Each report entry carries `law` (its IR), `negated`, `counterexample` (binder name → value), and `rejected`.
- Canaries are what catch an emitter that silently weakens statements. The other checks cannot.

**Tamper tests** (`tests/test_40_gate.py`) must make the gate fail:
- a `?TODO` in a proof
- an `@unsafe` def
- a deleted proof
- a lawless (vacuous) `LAWS.bend`
- an edited statement
- a `bunfig.toml`

## 8. Replay on real code (P5)

Write `replay/M0/report.json`:

```json
{"morph_commit": "<full sha of 3e44e79>",
 "laws": {"L_par_hdr_v2": {"go": {"status": "passed", "command": "...", "observed": "..."},
                            "solidity": {"status": "not_applicable", "observed": "needs full commitBatch deployment (M1)"}},
          "L_dom_hdr":    {"go": {...}, "solidity": {...}},
          "L_par_hdr_ssvh": {"go": {...}, "solidity": {...}}}}
```

**Go side** (required): run the witness through the real `common/batch` code at the pinned commit, using a test file in a scratch copy of the morph checkout.
- `L_par_hdr_v2`: `BatchHeaderV1{...}.Bytes()[0] == 1` for the witness.
- `L_dom_hdr`: `BatchHeaderBytes(witness).Hash()` returns `ErrInvalidBatchHeaderLength`.

**Solidity side** (required for `L_dom_hdr`): a Foundry harness that inherits `Rollup` and exposes `_loadBatchHeader`. It must not revert on the 250-byte witness.

**Statuses:**
- `passed`: the real code behaves as the model predicts.
- `failed`: it does not. This is a model defect; report it loudly.
- `not_applicable` or `not_run`: with a reason.

## 9. Non-goals in M0

- No automated extraction (facts are hand-written).
- No rules other than PAR.
- No state machines.
- No Lean export (`--verdict` covers the second kernel).
- No performance work.
- No changes to the IR format.
