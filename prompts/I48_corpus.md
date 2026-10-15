# I48: preregistered evaluation instrument

This first-commit package contains only `spec/M4/predictions.json`,
`spec/M4/lib/I48/instrument.json`, this prompt and `tests_m4/` acceptance
tests. The instrument fixes the sampling, labeling, renaming and control
rules before data collection. Neither a candidate nor a rater label is a
finding until independently checked. Do not edit this package to make a
surprising outcome pass; report deviations and seek a documented amendment.

## Corpus (VAL-I48-001 to 003)

After preregistration, use the frozen `corpus_protocol.deterministic_selection`
in the instrument, not a post-hoc candidate table. Pin and record each repository
head/ref before traversal. Walk each repository with `git log --topo-order
--date-order` from that head and inspect commits matching the instrument's
subject/body defect-fix regex in traversal order. Record every evaluated commit
through the quota-reaching candidate (or verified exhaustion), accepted or
rejected with one explicit disqualification reason. Select 8 Morph, 6
go-ethereum, 3 Solady, and 3 OpenZeppelin fixes. At least 12 must be non-rollup
fixes from at least two different non-rollup systems. No shortfall waiver is
allowed if 20 qualifying fixes exist in the pinned histories.
Use the local Morph checkout or an external clone, plus clones of the
non-rollup candidates in `/home/factory-user/.holon/corpus_m4/clones`.
Do not create clones inside the repository. Verify full commits, ancestry,
Verify full commits and that `pre_fix_sha` equals `git rev-parse <fix_sha>^1`,
not merely an ancestor. Require at least one non-test Go/Solidity source with
a non-comment/non-whitespace added or removed code line. Extract a primary file
or 1-3 file bundle at the same relative paths for both revisions. Check both
revisions with `gofmt -e` or Solidity parsing and record parser evidence and
source SHA-256 in `results/M4/I48/corpus_verification.json`. Materialize bundles at
No synthetic examples or unverified SHAs count. Report a shortfall rather
than silently substituting examples.

Each manifest entry has every `required_entry_fields` in the instrument,
plus `clone_path` (absolute path to the actual clone). `source_bundle` is the
repository-relative bundle directory. Bundle files `pre_fix` and `fix` are
the checked-out primary file bytes at the two revisions, with their original
Go/Solidity extension. `public_evidence` identifies an independently
checkable public bug-fix reference, not an invented narrative. The fixed
The verification report lives under `results/M4/I48/`. The manifest `defects` array is ordered by

## Blind labels (VAL-I48-004)

For each entry, produce `spec/eval/I48/packets/<defect_id>.json` containing
*only* `defect_metadata` (including exact SHAs, language and source files),
`commit_message`, `pre_fix_source_excerpt` (an actual substring of the
pre-fix source), `fix_diff` (the actual source-files diff), and
`neutral_classification_rubric` (the label-free instrument text). No forbidden
hint key or rule token from `forbidden_packet_tokens` may appear anywhere in
the packet. Never expose author predictions or pipeline results. Give all packets to two
fresh, independent read-only sessions. The raw outputs at
`results/M4/I48/raters/rater_a_raw.json` and `rater_b_raw.json` contain
`session_id`, `model`, `reasoning_effort`, `provider_family`,
`same_family_limitation_disclosed`, and a `labels` map keyed by defect ID,
with `label` and `confidence` for each packet. Each raw output also has
`session_metadata` containing distinct `rater_id`, isolation mode, the SHA-256
of concatenated lexicographically sorted packet SHA-256 digests, and completed defect count.
Do not rewrite their outputs
to make the rubric agree. Disclose same-family limitations.

`results/M4/I48/adjudication.json` contains `raw_agreement_rate`,
`cohen_kappa` and `defects` keyed by ID. Each adjudication row records
`rater_a_label`, `rater_b_label`, `agreement`, `primary_rule`,
`adjudication_rationale`, plus `final_label` equal to `primary_rule`.
When raters disagree and either confidence is low, use `UNCERTAIN`. If both
confidences are high or medium, choose one rater's label unless the rationale
explicitly names a frozen `labeling_rubric.tie_break_clauses` key. Report
the 0.70 descriptive agreement target, not as a prediction threshold.

## Renaming (VAL-I48-005)

Build `holon/eval/renaming.py` for deterministic, injective, binding-aware
Go and Solidity renaming of source *bundles*. Bound uses must track their
declarations across scopes. Leave keywords, primitive types, literals,
comments and strings untouched. `restore_bundle(rename_bundle(bundle))`
must exactly equal `bundle` in bytes. Record structural and token-binding
checks on **every source file** of every bundle and synthetic lexical-shadowing
edge cases in
`results/M4/I48/renaming_report.json`; a simple identifier regex does not
satisfy the contract. Both original and renamed Go/Solidity files must parse;
independent lexical binding signatures, comments and string tokens must agree.
Recompute the report's domain words, unchanged identifiers and alpha-equivalence
from the files; all domain words and unchanged user identifiers must be zero.
No renaming result is a HOLON detection verdict.

## Scale controls (VAL-I48-006)

Build `spec/eval/controls.json` with exactly the six matched pairs (C01-C12) in the
instrument (12 controls total). Each control row has `control_id`, `family`,
`known_outcome` (`known_true` or `known_false`), `standard_budget`,
`control_scale`, `seed` and, for false controls, `witness_scale` and a
concrete `witness`. True rows contain `invariant_justification`. The
verification report at `results/M4/I48/controls_report.json` has `controls`
keyed by ID, with a `verified` flag, `artifact` (under
`gen/eval/controls/<control_id>/`) and for false rows `passed_through_budget` and
`violates_at_witness`. Record checked Bend/Python evidence, not an asserted
label alone. Materialize `spec/eval/controls/<control_id>.json` for each row and
implement `holon.eval.controls.evaluate_control(control_id, budget_scale)`.
Run live evaluation at the standard budget for every control, at every scale
up to that budget for false controls, and at the larger witness scale. Bend
must accept every true proof and false concrete counter-law with its named law
present. Scan all `.py` and `.bend` under `holon/` outside `holon/eval/` and
`gen/M0` through `gen/M3` for evaluation/control references. Ordinary fixed
budgets remain unchanged.

## Acceptance

Run `python -m unittest tests_m4.test_eval_corpus tests_m4.test_eval_renaming
tests_m4.test_eval_controls -v`. The instrument tests pass immediately; the
outcome tests fail red until the build exists. I48 delivers instruments,
not corpus HOLON runs (I51), baseline comparisons (I52) or solver
calibration (I53).
