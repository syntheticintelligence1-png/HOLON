# AGENTS.md: rules for every agent session in this repo

You are building HOLON, a bug-finding factory. Untrusted generators (you) produce models, proofs and witnesses. A proof checker (Bend 2) and frozen tests decide what is true. Your job is to make the checker and the tests agree with reality. Making them agree with you does not count.

## Read first, every session

1. `docs/M0_SPEC.md`: the contract.
2. `docs/BEND_PRIMER.md`: verified Bend 2 facts and hazards.
3. The prompt for your session, in `prompts/`.

## Hard rules

1. **Do not edit frozen files.** They are listed in `FROZEN.sha256`:
   - `facts/`, `laws/M0/`, `predictions/`, `schemas/`, `tests/`, `bend/probes/`
   - `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`
   - `AGENTS.md`, `tools/freeze.py`

   Do not add files under those directories either. If a frozen file seems wrong, stop and write it up under "Questions for the human" in your PR. Never run `tools/freeze.py write`; only the human re-freezes.
2. **Never weaken a claim to make it pass.** You may not:
   - edit law statements;
   - drop premises from generated laws, or add new ones;
   - special-case law IDs in generators;
   - make tests skip.

   If a predicted outcome does not happen, report it. A surprising result is a result.
3. **No escape hatches in Bend**, even temporarily in committed code:
   - `?TODO` or `?name`
   - `@unsafe`, or `def f?(..)`
   - foreign `import "./x.c"`
   - laws without proofs
4. **Generate, don't hand-write.**
   - The model is generated from `facts/`.
   - Laws are generated from `laws/M0/*.json`.
   - Proofs come from proof generators, one per class of obligation.
   - A fix goes into a generator, never into a generated file.
5. **Witnesses come from the model, never from the oracle.**
   - `tests/reference/` is the test oracle: never import it, copy it, or call it from `holon/`.
   - The refuter must evaluate claims on the compiled Bend model.
6. **The checker's word is final.**
   - PROVED means Bend accepted the proof file and the expected law is present in it.
   - REFUTED means Bend accepted a counter-law with a concrete witness.
   - Anything else is UNKNOWN, recorded with what was tried.
7. **Determinism.** Generated files are byte-identical across runs: fixed seeds, sorted iteration, no timestamps.
8. **No `bunfig.toml` or `.env` anywhere in the repo.** Bun reads them and they can inject code into the checker.

## When using Bend

- Run `bend guide` to learn it. Bend 2 is newer than your training data, so trust the guide and `docs/BEND_PRIMER.md` over your priors.
- Use `LAWS.bend` for claims and `PROOF.bend` for proofs.
- Run the checker before committing. "ALL PROOFS CHECK" on a file with no laws proves nothing.

## Every PR description ends with

- **Done:** what changed, and which tests now pass. Paste the summary line of `python -m unittest discover -s tests -t . -v`.
- **Surprises:** anything that behaved differently from the spec, primer or predictions.
- **Questions for the human:** suspected errors in frozen files, ambiguous spec points.
- **Not done:** what you deliberately left for later.
