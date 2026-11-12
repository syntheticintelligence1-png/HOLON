# I49 (M4): the held-out target, extraction, facts and diagram

Rendered from docs/BUILD_PLAN.md §4 I49/I50 and the coordinator's brief for the I49/I50 session (the seal protocol,
the lead's ruling). Read AGENTS.md, docs/M0_SPEC.md, docs/BEND_PRIMER.md, BUILD_PLAN §0.1, §0.2, §2, §3, the M4 header
and §4 I49/I50, whitepaper §13 and its threats ("fresh sealed targets", contamination), and docs/HUMAN_ANSWERS.md Q7,
Q9, Q11, Q19 and the lead's delegated answers.

Base: I47's branch `claude/i47-target-factory` at 7dc50894 (draft, not landed), which brings `targets/<name>/`.
The PR targets `claude/holon-v2-bend2-c6z3cd` and says it is stacked on I47's PR. Landing waits for M3's exit, like
all M4 code. Merge commits only; never squash or rebase these branches.

## The seal

The human sealed the held-out target in `spec/heldout/target.json` (Q7: "No agent reads it before I49's prereg").
This prereg is written **blind**: when it was committed and pushed, no session had read, listed, grepped, fetched or
cloned anything under `spec/heldout/` or from the sealed upstream. So it makes only target-agnostic predictions, and
every choice the run could otherwise tune to the target is fixed here by rule:

- `spec/M4/lib/heldout_protocol.json`: where the target lives (rule T1), the scope sidecar the extraction reads
  (rules S1-S6: the sealed source file, its stem as the contract, the verifier interfaces it imports as commit
  interfaces, the pinned solc and the development target's settings), the mapping of an extracted transitions
  document to a diagram (V1-V5, E1-E5), the four rows of the size report, and the target gate's checks.
- `spec/M4/lib/heldout_catalog_pin.json`: the rule catalog the held-out run uses is the one at the base commit,
  `holon-rules/1.15`. Its producers reach far beyond `holon/rules/`, so the pin is every file under `holon/` at the
  base commit, by sha256. Any later change or addition under `holon/` is disclosed in
  `spec/M4/lib/heldout_disclosures.jsonl` (path, phase `pre_seal` or `post_seal`, why, affects); a post-seal change
  adds the contamination caveat to every result it affects. `holon/rules/` and the catalog are never edited.
- The session that writes this prereg is the sole reader of the sealed target until I50's results are recorded. It
  uses no subagents, and the adversarial phase is its own.

## Goal (BUILD_PLAN I49)

Extraction, facts and the diagram for the sealed target, through `targets/<name>/` and HOLON's frontends. Generate,
don't hand-write: the facts are the pinned Solidity frontend's output over a checkout fetched only as the sealed file
pins it. Extraction gaps on the foreign codebase are coverage debt with reasons; no fact is written by hand and no gap
is excluded (Q19). The frontend is not changed for the target: its files are record-pinned (I47), and a change would
both move committed M2/M3 digests and tune the extractor to the target after the seal.

New commands (target-agnostic; nothing under `holon/` names a target):

- `holon target extract|coverage|diagram --target NAME [--check]`, `holon target sizes [--check]`,
  `holon target gate --target NAME`.
- The 0.3 diagram adapter (`holon-diagram-transitions/0.1`), written before the seal opens and validated on the
  development target's extracted rollup document, which is also the Morph M3 row of the size report.

The contract is the docstring of `tests_m4/test_i49_heldout.py` (H0-H6). The key is `I49` in
`spec/M4/predictions.json` (source `spec/M4/predictions/I49.json`).

## Predictions and regressions

Target-agnostic, as the brief requires: P1 the sealed contract extracts with the pinned frontend into a schema-valid
transitions document at the sealed commit, under a scope sidecar that follows the rules; P2 coverage regenerates and
accounts for every statement (gaps are debt with reasons); P3 the diagram builds with zero unmapped constructs and its
|V|, |E| equal the instrument's count from the document alone; P4 every check of the target gate passes, and four
tampers fail it; P5 the size report has the protocol's four rows in the |E|/|V| form, with obligation counts per rule,
and no linearity claim (the schema has no field for one); P6 extraction, coverage, diagrams and sizes are
byte-identical across runs. Regressions: R1 no generator digest moves; R2 no committed M0-M3 outcome changes; R3 the
target-agnostic scan, with the held-out target's names; R4 the seal order; R5 every change since the pin disclosed;
R6 the freeze check, and the report states the contamination caveat.

Not predicted (unknown before the seal, and none is a target-agnostic claim): the number of actions, families,
debt entries, |V| or |E| of the held-out document, or any per-rule obligation count (I50's prereg freezes those after
extraction, before any rule runs).

## Contamination caveat (stated before the seal opens)

The seal is a repository seal, not a seal on the builder's priors. The held-out target is a public repository older
than the builder's training data, so the builder's model family has likely seen its code and possibly write-ups of
its defects. Every held-out result carries the label "sealed in the repository, not sealed from the agent's priors".

## Environment

The pinned toolchain from `.github/ci/install_toolchain.sh` (bun, Bend 2.0.36, Lean 4.34.0 with BendTT, forge, solc
0.8.24, sol_deps, hevm, cvc5), the config paths linked as `.github/ci/link_paths.sh` does, `BEND_NO_TELEMETRY=1`.
Before this prereg the session read the documents above, I47's code and target files, the Solidity frontend, the
diagram builder and the development target's extracted rollup document, and ran `holon audit prereg --milestone M4`
and I47's closure probe at the base. It ran nothing on the held-out target, which it had not seen.

## The adversarial phase (folded before the prereg commit)

The builder read this prereg as a hostile reviewer would, before committing it. Folded:

- The sealed file's keys are unknown, so its values are found by shape (one repository, one 40-hex commit, one .sol
  source), and an ambiguous seal fails the tests instead of being resolved by judgment.
- The commit interfaces could be chosen to suit the target after the seal: rule S3 fixes them mechanically, and the
  test recomputes them with a regex walk that shares no code with the frontend.
- The diagram adapter could be shaped after seeing the target: its counting rules are fixed here and recomputed by
  the instrument from the document alone, and the same adapter makes the Morph M3 row.
- A wrong dependency version would pass silently (the frontend resolves imports through the pinned sol_deps of the
  development target): rule S6 reports every such unit as debt instead.
- A gate that only re-runs what it wrote is vacuous: four tampers (a bunfig, an edited document, a hand-written fact
  file, an edited diagram) must each fail it.
- The prereg commit itself could leak the target: H0 checks that it holds neither the sealed commit nor the sealed
  source path.

Not folded, stated instead: the instrument and the protocol are agent-writable until the human freezes them (Q1);
the order "prereg before reading" is checkable in git only as commit order, not as what a session read.

## Hard constraints

AGENTS.md's rules, all of them; nothing under `holon/` names a target; no model identifiers in any file, commit or PR
text; author commits as Claude <noreply@anthropic.com>; merge commits only; never run `tools/freeze.py write`.
