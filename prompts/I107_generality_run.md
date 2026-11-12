# I107 (M6 exit): the generality run

You are a HOLON builder for iteration **I107**, the measurement that closes M6 (docs/BUILD_PLAN.md §3 row I107, §4
"M6: generality"). Branch `claude/i107-generality-run`. You are the sole reader of I106's sealed targets, and only
after the reveal.

## Base
Start from the lead `claude/holon-v2-bend2-c6z3cd`. Merge I103 (`claude/i103-frontend-reach`), I104
(`claude/i104-role-inference`) and I105 (`claude/i105-go-machines`) before the measured runs, and again whenever they
move; merge the lead whenever it moves. Merge commits only.

## Order (strict)
1. **The prereg, before the reveal:** this prompt, `spec/M6/predictions/I107.json` (then
   `python -m holon aggregate --milestone M6`), the contract `tests_m6/test_i107_generality.py`, and the run protocol
   `spec/M6/lib/i107_protocol.json` with its run protocols and the scope instrument. Predictions and thresholds are
   written blind to the targets (target-agnostic for the sealed ones). `python -m holon audit prereg --milestone M6`
   must print PREREG OK. Push, then send the coordinator one line: `I107 prereg pushed: <sha>`.
2. **After the reveal** (`spec/heldout2/target.json` and `salt.txt` on `claude/i106-sealed-targets`): verify the
   commitment, then fetch each target only as target.json pins it.
3. **The runs:** (a) the corpus rerun, all 20 I48 entries, labelled `contaminated: post-I51`; (b) the fresh sealed
   targets, the full route plus the preregistered baselines; (c) Morph under `--roles auto`, reported, never
   substituted for Morph's record.
4. **The report:** docs/iterations/I107.md and `results/eval/generality/` (generated), one table per run against I51,
   I52/I52b and I53; every miss with its stage and reason. Then a draft PR whose first line is
   `I107 ready: <one-line outcome>`, followed by Done, Surprises, Questions for the human, and Not done.

## Scoring
Matching to I48's labels by I51's instrument; a blinded adjudicator for sealed-target findings, as I52 did; the deltas
against the baselines; static-only and static+AI reported separately.

## Responsible disclosure (the repository is public)
A finding on a sealed target that the adjudicator does not classify as a model defect or an intended asymmetry is a
potential real vulnerability: commit no witness, exploit trace, replay test or plaintext description of it; commit
only a record with its id, a sha256 commitment of the withheld finding, its class and
`withheld: pending coordinated disclosure`; keep the plaintext in the session only and send the coordinator one line
`I107: potential vulnerability withheld, <target name>, <law id>, commitment <sha256>`. Withheld findings count by class
only. Corpus entries (public, fixed defects) are exempt.

## Invariants
AGENTS.md's hard rules, all of them. Morph's M0-M3 outputs stay byte-identical. No hand-written target file. The AI
proposal channel: one fresh subagent proposes roles from the target's code only, committed as data with its sha256,
labelled same-family. Never tune the tools during the run: a tool bug that blocks a run is a miss with its reason. No
model identifier in any file, commit or PR text. Author commits as Claude <noreply@anthropic.com>; never force-push,
rebase or amend; work in progress carries `[skip ci]`.

## Toolchain and budget
`.github/ci/install_toolchain.sh` as CI runs it, `python .github/ci/verify_toolchain.py` PINS ALL PASS (13/13),
BEND_NO_TELEMETRY=1; I103's sets (`tools/install_toolchain_sets.sh`) and I52's baselines
(`.github/ci/install_baselines.sh`). Machine time is no object; tokens are limited: subagents only for the AI role
proposals and the blinded adjudication. Target the report by about 12:00 UTC; what isn't done is reported under Not
done.
