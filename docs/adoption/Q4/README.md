# Q4 adoption package: `result_record_v2` and `law_ir_0_3` into the frozen `schemas/`

Prepared by I64 (= I33a), rule K10 of `tests_m3/test_contracts.py`. It answers human answer Q4 (`docs/HUMAN_ANSWERS.md`): the two v2 schemas are adopted into the frozen `schemas/` at I33's adoption step, and **the human runs the freeze**. Under AGENTS.md rule 1, no agent writes under `schemas/` or runs `tools/freeze.py write`. That is why this is a package of files and steps, not a commit that does it.

## What is adopted

| File in this package | Copied to | What it is |
|---|---|---|
| `schemas/result_record_v2.schema.json` | `schemas/result_record_v2.schema.json` | The v2 result record, additive to the frozen v1 `schemas/result_record.schema.json`. Since I64 it admits `filter_bin: "intended_bounded"` and the field `intended {contract, l_weak, replaces}` on REFUTED records (K8). |
| `schemas/law_ir_0_3.schema.json` | `schemas/law_ir_0_3.schema.json` | The IR 0.3 law format, including the INTENT rule. |

Both files are byte-equal to `spec/schemas/` at the head of the I64 build; `TestSchemaAndAdoption.test_the_q4_package` checks this.

The adoption adds two files beside the frozen v1 schemas. It edits none of the v1 schemas: the v1 `triage` enum stays as it is (Q4), and the frozen tests read only the v1 schemas (`tests/_util.py`).

## Steps (the human)

1. **Review** the two files in `docs/adoption/Q4/schemas/`. Compare each with `spec/schemas/` at the commit you adopt from; they must be byte-equal.
2. **Copy** them into the frozen root:
   ```
   cp docs/adoption/Q4/schemas/result_record_v2.schema.json schemas/
   cp docs/adoption/Q4/schemas/law_ir_0_3.schema.json schemas/
   ```
3. **Re-freeze**, which only the human may do:
   ```
   python tools/freeze.py write
   python tools/freeze.py check      # FROZEN OK
   python tools/freeze.py digest     # the new manifest digest
   ```
   `write` adds the two files to `FROZEN.sha256`.
4. **Move the CI digest pin** (Q40). In `.github/workflows/holon-ci.yml`, job `freeze-check`, replace the pinned digest with the one step 3 printed:
   ```
   test "$(python tools/freeze.py digest)" = "<new digest>" || { echo "FROZEN.sha256 digest differs from the pinned seed freeze"; exit 1; }
   ```
   The pin is `f854d69b0b58b581eb205a657d6925cc1e1460141ef9626df89ea87de1594fd0` at the I64 build. Moving it is the visible change Q40 asks for. Without this step, CI's freeze-check fails on the new manifest.
5. **Commit** `schemas/`, `FROZEN.sha256` and `.github/workflows/holon-ci.yml` together, in one commit, and push it. CI's freeze-check job then runs `check` and the new pin.

## Optional: freeze the intent contracts too

Contracts in `laws/CONTRACTS/` are pinned by their registry hashes (K2). That pin is self-certified, not frozen, because an agent can edit a contract and its registry entry together (BUILD_PLAN §2 invariant 11; Q1). To freeze them, do this before step 3, in the same commit:
- add `"laws/CONTRACTS"` to `FROZEN_ROOTS` in `tools/freeze.py`, which is itself frozen and so is a human edit;
- then run step 3: `write` records every contract file and `REGISTRY.json` in `FROZEN.sha256`.

After that, a new or changed contract is a frozen-file change for the human to review and re-freeze, like the schemas.

## After the freeze (agent work, not part of this package)

- The gate's G9 and `holon oracle check` read `spec/schemas/` today. An agent session then points them at the frozen copies in `schemas/`. After that, a change to a v2 schema is a frozen-file change like any other: a Question, then a new package.
- `spec/schemas/` keeps the working copies until that switch.
