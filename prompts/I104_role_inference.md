# I104: role inference (M6, generality)

Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, then this prompt (AGENTS.md, "Read first"), and
run `bend guide`: Bend 2 is newer than your training data.

Protocol (BUILD_PLAN §0.1 and §0.2):
1. Prereg first. Write the key `I104` into `spec/M6/predictions/I104.json` (aggregated into
   `spec/M6/predictions.json`) with this prompt and the acceptance tests `tests_m6/test_i104_roles.py`, in one commit.
   `python -m holon audit prereg --milestone M6` must print PREREG OK. Push it before any implementation.
2. Build. A fix goes into a generator, never into a generated file; outputs are byte-identical across runs; no frozen
   file is edited and no claim is weakened (AGENTS.md rules 1-4).
3. Report. `docs/iterations/I104.md` states each prediction held or missed with its evidence, the soundness argument,
   and ends with Done, Surprises, Questions for the human and Not done.

## The plan's text (BUILD_PLAN row I104)

**Role inference.** No rule producer takes a Go document without a target sidecar: PAR's Go sub-forms read hand
`go_laws.json` roles, and the codec layer reads hand link roles. Generators now write those roles and the typed
sidecars for any target. The deterministic static inferencer is the primary channel. An AI proposal channel is data, a
proposal file with its sha256, and every record derived from it carries `roles_source`. The checker decides: a wrong
role ends UNKNOWN, or REFUTED with a failed replay, which is a model defect, never a finding. Inference applies only
where no hand sidecar exists, or under `--roles auto`. On Morph, `--roles auto` is run against the hand roles and
reported, never substituted.

## The session brief (the coordinator's, in substance)

- Branch `claude/i104-role-inference`, based on the lead `claude/holon-v2-bend2-c6z3cd`, with the lead's M6 skeleton
  (`claude/ci-m6-skeleton`) merged before the prereg commit.
- The gap: the rule producers need per-target role sidecars that only Morph has, written by hand:
  `spec/M3/lib/go_laws.json` (PAR's Go sub-forms: the Go document and the recompute roles), `spec/M3/lib/link.json`
  (cross-language link roles), `spec/M3/lib/go_ops.json` (Go-op components: an interface carrier and its ops), and the
  typed sidecars (`disch.json`, `disch_profile.json`, `undo.json`, `undo_basis.json`, `fact.json`, `fact_basis.json`,
  `binding_facts.json`). They assign roles, never values.
- Build `holon roles`, which writes these sidecars for any target from its extracted documents:
  1. a deterministic static inferencer under `holon/` (the primary channel): codec pairs, Go-op components over every
     carrier type, cross-language links by layout and value, typed inputs from the transitions documents. Names are
     tie-breakers only, never the sole evidence. Every role carries its evidence (facts, rule of inference);
  2. an AI proposal channel: `spec/<M>/lib/roles_proposed.json`, written by an agent outside the gate, committed as
     data with its sha256 and model-free provenance (`proposer: "agent"`), merged deterministically (static wins on
     conflict). Proposals may be wrong; the checker decides, and a wrong role's laws end UNKNOWN or REFUTED with a
     failed replay, classified as role or model defects, never findings. Tested with planted wrong roles;
  3. wiring: generated roles are used only where a target has no hand sidecar, or under `--roles auto`; Morph's record
     is unchanged;
  4. every record derived through a generated role carries `roles_source` (`static`, `ai_proposal` or `hand`); both
     static-only and static+AI modes are runnable (I107 reports them separately).
- The measured experiment on Morph: `--roles auto` against Morph's documents without the hand sidecars; role precision
  and recall against the hand sidecars; how many of M3's decided laws are re-derived; how many new laws appear and what
  they decide. Reported, never substituted for Morph's record.
- The corpus smoke test (not a score): on I51's 9 extracted entries, the entries where `holon roles` yields at least
  one role and derive at least one law. I107 does the scored rerun.
- Invariants: AGENTS.md's hard rules; Morph's M0-M3 outputs byte-identical (re-stamp only); holon/ names no target;
  soundness over coverage (a fallback may only make a law weaker or UNKNOWN, never wrongly PROVED); never read
  `spec/heldout/`, `spec/heldout2/` or `scroll-tech/`; do not tune to the corpus; no model identifiers in any file.
- Exit: `holon roles` exists; the Morph auto-versus-hand table is reported; the planted-wrong-role soundness tests pass;
  M0-M3 byte-identical (re-stamp only); tests_m6 green.
