# I103: Frontend reach

Rendered by `python -m holon coordinator prompt --key I103` (holon/coordinator.py) from `docs/BUILD_PLAN.md`
(§3, the map row I103). The human may edit it before the session starts; the key's prereg names it.

Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, then this prompt (AGENTS.md, "Read first"), and
run `bend guide`: Bend 2 is newer than your training data.

Protocol (BUILD_PLAN §0.1 and §0.2):
1. Prereg first. Write the key `I103` into `spec/<M>/predictions.json` (predictions, regressions, outcome_paths,
   tests, thresholds) with this prompt, the acceptance tests (red) and every instrument that decides a prediction, in
   one commit. `python -m holon audit prereg --milestone <M>` must print PREREG OK. Push it before any implementation.
2. Build. A fix goes into a generator, never into a generated file; outputs are byte-identical across runs; no frozen
   file is edited and no claim is weakened (AGENTS.md rules 1-4).
3. Report. `docs/iterations/I103.md` states each prediction held or missed with its evidence, and ends with Done,
   Surprises, Questions for the human and Not done.

## The plan's text

| I103 | (M6) | **Frontend reach.** I51 showed that each frontend accepts one pinned toolchain, so 11 of the 20 corpus entries never reach extraction: optimism's pragma 0.8.15 ×4, compound's ^0.5.16, arbitrum's go ≥ 1.25 ×3, and wormhole's go.work conflict ×3. It also showed that the sort pass refuses a whole document on its first unknown term. The fix:<br>- each document gets its toolchain from a pinned set: solc by pragma, from a new pinned list with sha256s, kept separate from the 13 CI pins, which stay unchanged; and go 1.25;<br>- go.work is resolved deterministically;<br>- the sort pass becomes total: an unknown term becomes an opaque fresh variable with a coverage-debt entry, and one run reports every unknown construct.<br>Morph's M0-M3 outputs stay byte-identical (re-stamp only) | M6 | I51, I52 | — | M6 |

---

## The session brief (the coordinator's, verbatim in substance)

- **Branch.** `claude/i103-frontend-reach`, based on the lead `claude/holon-v2-bend2-c6z3cd`, with the M6 skeleton
  (`claude/ci-m6-skeleton`) merged before the prereg commit. Runs in parallel with I104-I107; a draft PR against the
  lead, first line `I103 ready: <one-line outcome>`.
- **Why.** I51: 11 of 20 corpus entries never reached extraction (pragma 0.8.15 ×4, ^0.5.16, go ≥ 1.25 ×3, a generated
  go.work with conflicting replaces ×3); I50/I50b: the sort pass refused the whole held-out document on one unknown term
  (`update`, then `calldataload`).
- **D1, toolchains.** A pinned *set* of solc releases with sha256s (a new config/holon.json set; the 13 CI pins and
  `replay.solc` unchanged); the frontend picks the newest pinned release satisfying the unit's pragma, refuses a unit no
  release satisfies with that reason, and records the choice in the document. Pre-0.8 arithmetic is unchecked: say what
  the IR does (an explicit flag or an honest refusal), never silently 0.8. A pinned go 1.25.x next to 1.24.7, chosen by
  go.mod's `go` directive. go.work generated deterministically with a documented rule for conflicting `replace`s, or the
  conflict recorded per module as a reason. Morph's documents choose exactly the toolchains they use today.
- **D2, a total sort pass.** In a mode that is the default only where no Morph record depends on it, an unknown term
  becomes an opaque fresh variable of the least-informative sort, each occurrence written to a coverage-debt list (head,
  location, count); one run reports every unknown construct. Map the later stages that refuse whole documents on one
  construct (types, model, disch, derive) and fix or document each. Soundness: opaque means unconstrained; a PROVED law
  over an opaque value holds for every value; a REFUTED law still needs its replay.
- **Invariants.** AGENTS.md's hard rules; prereg first; Morph's M0-M3 outputs byte-identical (re-stamp only); inference
  and fallbacks only where no hand sidecar exists or under an explicit opt-in; holon/ names no target; soundness over
  coverage; never read `spec/heldout2/` or `scroll-tech/` (the committed I49/I50/I50b documents may be walked); no
  tuning to the corpus; no model identifiers in any file.
- **Exit.** Every I51 not_run entry either extracts or carries a per-document reason naming the missing toolchain or
  construct; the sort pass completes on every extracted document with its coverage-debt list; M0-M3 byte-identical
  (re-stamp only); tests_m6 green.
