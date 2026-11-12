# I57: environment modules

Rendered from `docs/BUILD_PLAN.md` §4 I57 (milestone M5; depends on I12 and I54), with Q11 and I23a in `docs/HUMAN_ANSWERS.md`, the whitepaper's L9 row (§12), §5.2 (UNDO) and §5.5 (FACT), and the lead's review of I54 on PR #134 (its condition G3 binds this key). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first.

Base: `claude/i54-m5-definitions` at `95a2288c` (PR #134, not landed). The PR goes to `claude/holon-v2-bend2-c6z3cd`, stacked on #134, and waits for M3's exit.

## Goal

- Three environment modules, one per L9 category, from I54's three families (`spec/M5/lib/I57_modules.json`):
  - **da:** `env-da-retention`, a window of W = 131072 beacon slots (the consensus minimum, 4096 epochs);
  - **l1_chain:** `env-l1-confirmations`, a finality depth of d = 10 blocks (the target derivation's default confirmations);
  - **fetcher:** `env-fetch-archive`, availability: the blob archive returns exactly the committed blob.
- Every parameter is a premise from a cited specification or from the target's code. None is a fact about mainnet, and none is fitted.
- Time-indexed FACT and UNDO laws (`spec/M5/lib/I57_laws.json`), each in two forms:
  - module: the environment term is the module's model with its pinned parameter;
  - axiom: the same term is free (havoc), as `A-env` leaves it in the base records.
- L9 is computed by I54's definition, unchanged.

## Preregistered

**Which existing laws change outcome under retention and reorg: none (I57-R2).**
- The 222 environment-dependent M2 and M3 laws read the block, msg and tx members and `blobhash` at execution time.
- The modules constrain only three things: the query-time availability of a blob, the canonicity of an observed block, and a fetcher's answer.
- So a module premise neither adds a constraint on a base witness nor removes one from a base proof.
- None of the 222 becomes covered: that needs its record regenerated with a module premise, and I57 may not change M0-M3.

**The observation sets (the lead's G3):**
- They come only from `spec/M5/lib/I57_observe.py`, whose sha256 the key pins.
- The tool records its own producer, source sha256 and reads, and reads only the plan's three I23a hosts.
- Any other set is inadmissible: it is never passed to the metric, so its module fails R1.

**Predictions:** see the key. P1 and P4 are informed by a probe made before the prereg, and are reported but not counted.

## Build

- `holon/m5/env.py` and `python -m holon m5 env [--check]`. It writes:
  - the model `gen/M5/env/model/env.bend`, generated from the module records;
  - `gen/M5/env/<form>/<law>/LAWS.bend` and `PROOF.bend` for each form, from one proof generator per class (premise_rewrite, computation, bounded_cases, counter_witness);
  - `laws/M5/ENV.json`;
  - `results/M5/L_env_*.json` (one per law, carrying both forms' checker evidence);
  - `results/M5/env/sensitivity.json`.
- `python -m holon m5 l9 [--check]` writes `results/M5/l9_I57.json`:
  - inputs: the M2, M3 and M5 records, the classification, the module records, the admitted sets, the sensitivity pairs, I54's `base.l9_dependent` and the key's pinned parameters;
  - output: `holon.m5.metrics.l9` of those inputs, with the sha256 of each truth file.
- Observations: run `python -I spec/M5/lib/I57_observe.py <set>` for each set, after this prereg is pushed.
- `docs/iterations/I57.md`.

## Rules

- All of AGENTS.md's hard rules. Never weaken a claim.
- Change no file of M0-M4 and no I54 instrument, key or output.
- Never read the sealed held-out target.
- A miss is a Surprise. The key is never edited. A test that must be fixed gets a line in `spec/M5/amendments/I57.jsonl`.
