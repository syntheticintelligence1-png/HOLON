# I52b (M4): the baselines on the held-out target

Rendered by the coordinator for this session from docs/BUILD_PLAN.md §4 I52 ("baselines on Morph, the corpus and the
held-out target"), whose Morph and corpus half is I52. The builder works alone, all the way to a draft PR; the
coordinator reads the PR and the lead reviews and lands it.

## The situation
- I52 (branch claude/i52-baselines, its PR not up yet) built the baseline runner (holon/eval/baselines/,
  `python -m holon eval baselines ...`) and runs it on Morph and the corpus. Its findings schema is
  spec/M4/lib/I52_findings.schema.json; its protocol (systems, budget, matching, statuses, determinism)
  spec/M4/lib/I52_baselines.json. Its runner refuses `--system heldout` until I50's labels and scope exist; enabling
  that system is this session's job.
- I49/I50 (#144, #145, branch claude/i50-heldout) are HOLON's sealed result on the held-out target, pinned by
  spec/heldout/target.json: I49 held 4 of 6 predictions; I50 derived no law (`holon sorts` refuses the frontend's
  `update` term). I50b (#151) is a contaminated rerun, still refused.
- The seal on readers has lifted (I50's results are recorded): spec/heldout/ and the I49/I50/I50b files may be read,
  and the target's code fetched only as spec/heldout/target.json pins it.

## Base and landing
- Merge claude/i52-baselines and claude/i50-heldout, merge commits only; merge I52 again whenever its head moves and
  before the final validation. Spec/M4 conflicts are mechanical: keep every key and line.
- Branch claude/i52b-heldout-baselines; one draft PR against claude/holon-v2-bend2-c6z3cd, stacked on I52's branch and
  #145; never merged by the builder.
- Nothing of M0-M3, nor I52's prereg files or its Morph and corpus results, changes; I52's tests stay green. The
  held-out system is enabled through I52b's own instrument (spec/M4/lib/I52b_heldout.json), changing the runner only as
  far as that needs, every changed file disclosed.

## The iteration
- Goal: I52's baselines (slither, echidna, medusa, hevm, halmos, Go native fuzzing, 2-cycle round-trip testing,
  frequency-based spec mining, agent-only review) at equal budget, in I52's schema, on the held-out target.
- Budget: the lead's rule, I52_baselines.json holon_budget.heldout ("I50's recorded wall clock"), applied as written.
  If it is degenerate, say so under Questions for the human. A second, larger budget only if the prereg fixes it
  before any run, and every record and table labels it secondary.
- Labels: what counts as a detection is fixed in the prereg before any run (for example I49/I50's preregistered rule
  classes and obligations, or the target's public defect history at the pinned commit); never from baseline output.
- Agent-only review: fresh reviewers given only the target's code and the same budget, never HOLON's outputs, the
  I49/I50 files or the labels; same-family reviewers labelled as such; no model identifier in any file.
- Contamination: the predictions are written after the seal lifted, by a builder who has seen I49/I50's results;
  disclosed beside every number.
- Exit: results/eval/heldout/<baseline>.json for every baseline, in the schema, with its timing; each run or recorded
  as missing with a reason.

## Process
1. Prereg first (§0.1): this prompt, the key spec/M4/predictions/I52b.json, the contract tests in tests_m4/ and the
   instruments they pin; outcome paths results/eval/heldout/ only; PREREG OK; committed and pushed before any baseline
   runs on the target.
2. The adversarial phase, run by the builder (no separate agent): try to inflate and to deflate the detections, check
   that the matching can fail, fold in the fixes. Subagents only for the agent-only review itself.
3. Run the baselines in parallel as far as one core per baseline allows; deterministic where the tools allow, seeds
   and versions recorded; then `assemble --system heldout --check`.
4. Validate: I52b's and I52's tests, `python tools/freeze.py check`, CI's gates with M0-M3 unchanged, the
   target-agnostic scan, the frozen suite if feasible.
5. Report docs/iterations/I52b.md and open the draft PR: first line `I52b ready: <one-line outcome>`, sections Done,
   Surprises, Questions for the human, Not done. Work in progress is pushed with [skip ci]; the final push without it.

## Hard constraints
- AGENTS.md's hard rules, all of them. Fetch only what spec/heldout/target.json pins; nothing under holon/ names the
  target. No model identifiers in any file, commit or PR text. Commits authored as Claude <noreply@anthropic.com>;
  never force-push, rebase or amend.
