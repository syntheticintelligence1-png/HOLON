# I12: hashes and oracles as parameters

Rendered from `docs/BUILD_PLAN.md` §4, I12. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, then `docs/iterations/I7.md` (Surprises) and the docstring of `holon/gen/mlaws.py`. The acceptance tests are `tests_m2/test_oracles.py`; its docstring is the contract (file formats, API, the term-size measure, the splits format). This iteration runs before any generated law, so no generated law has to be re-derived when hashes become parameters.

## What to build

- **Know the constraint first.** In Bend 2 a function value is `Type`, never `Data`. A law binder of function type can be erased (`for -h`) or affine, never reusable, and a model that applies `h` more than once cannot take `h` as a plain function argument (I7 Surprises; probe `bend/notes/p_ir03_fn_verdict`). Threading `h` through `step` and `run` as a Bend function is therefore likely impossible. The plan's fallback is the expected route: **an opaque oracle parameter held as Data (an oracle table), with CF over it.** The tests never look at the encoding; they read statuses, records, Bend's verdicts and BendTT kernel forms.
- **`spec/M2/lib/oracles.json`** (sidecar, `holon-oracles/0.1`; format in the test docstring). One entry per hypothesis: `{id, oracle, parameter, hypothesis, instance, status: modelled | not_in_scope, reason}`. It covers:
  - `agg`, the stand-in for keccak over blob hashes: a modelled kind-`cf` entry whose instance is the M1 template of `spec/M1/lib/morph_rollup.lib.json`;
  - `header_presentation`, CF(keccak, headers): modelled, kind `cf`;
  - `ISubmitter`, `verifier` (modelled, kind `hyp`: the `proof == 1` rule) and `messenger`;
  - the full §11.1 oracle list: `compression_codec`, `circuits`, `KZG`, `transaction_codec`, `L2_predeploys`, `fetcher`, `sealing_loop`.
  - The five M1 stand-ins (`CF-keccak-blobhashes`, `CF-keccak-headers`, `oracle-ISubmitter`, `oracle-verifier`, `oracle-messenger`) are cited in `ledger`. A not_in_scope entry states its reason.
- **Oracle sidecar lookup.** The sidecar of a facts file F is `F/../../lib/oracles.json`, next to its target libraries. M0 and M1 never read one.
- **`machine.py`.** For M2+ milestones (every milestone except M0 and M1), a facts call to the parameter of a modelled entry applies the model's oracle parameter, never a builtin; `step` and `run` thread the parameters. `agg` survives only as the instance used by the refuter and the inhabitants. `gen/M0` and `gen/M1` stay byte-identical.
- **`mlaws.py` and the IR.** A `Fn<A,B>` binder named like a parameter *is* that parameter. A `{"hyp": {"name": H}}` premise is rendered from H's predicate in the sidecar. A law file still imports Base and exactly one model module, as `M`.
- **Hash refs.** `holon.gen.refs.law_hash(law, facts, oracles=None)`: a hyp premise's ref is the content hash of its hypothesis's entry. Editing a hypothesis restales exactly the laws that name it.
- **Refuter and inhabitants.** They use the entries' concrete instances as candidates. A witness that takes an instance is recorded as `{"instance": <entry id>}`.
  - G11V: CF(h, S) is inhabited by h := `agg`, with CF(agg, S) discharged by evaluation.
  - A hyp premise is inhabited by the instance of the entry whose hypothesis it is.
  - Inhabitants keep I3's form: the inhabitant law states the parent's premise lines (`for hN: {X}` becomes `{X}`) under `exs` binders, and its proof supplies the instance.
  - A counter-law carries the law's hypothesis premises (`exs hN: {X}` lines, as M1 counter-laws do), so its witness satisfies them. A sidecar instance that violates its hypothesis does not stop a run; the inhabitant that would use it just fails to check (the tests run such a canary).
- **Records.** For M2+ laws, `model_assumptions` is exactly the set of hypothesis premises (§8.5): a `hyp` premise gives its name, and a `cf` premise gives the hypothesis id of its parameter's kind-`cf` entry.
- **Splits are law pairs.** `holon run` writes `<out>/splits.json` for M2+ milestones (format in the test docstring). Pairs come from statements, never from ids. `split` is true iff one variant is PROVED and another REFUTED.
- **`holon/oracle_check.py`.**
  - `validate(doc)`: G3 rejects a cf over `"*"` (global injectivity) in any predicate.
  - `check(sidecar, out_dir, root)`: tests each hypothesis against the real oracle where one is available here (A4). The verifier's `proof == 1` rule is labelled `untestable_here`. It also checks each instance (G11V): a generated Bend law states that the entry's concrete instance satisfies the predicate, written to `out_dir/<hypothesis id>/`; kind `cf` gets `per_premise`.
  - `python -m holon oracle check --milestone M2` writes `results/M2/hypotheses.json` and `gen/M2/oracles/`. It extends the file I3 wrote: the `Hyp-Z0-kzg` entry stays exactly as `holon oracle zero-blob` wrote it.
- **Fixtures** (frozen at the prereg):
  - `tests_m2/fixtures/oracles/`: toy facts, ledger, sidecar, and eight laws `L_orc_*` with their predicted statuses;
  - `tests_m2/fixtures/oracles_standin/`: the same facts, plus a library compiling each oracle as a stand-in builtin. This is the M1-encoding baseline for the term-size prediction.

## Rules

- **Never hand-write a law, proof, lemma or inhabitant.** A fix goes into a generator.
- **The fixtures, their predicted statuses and the term-size measure are frozen at the prereg.** A missed prediction is a Surprise. If the parameters break term-size limits, take the plan's fallback: an opaque state field holding an oracle table, with CF over it. Never take a stand-in.
- **No global injectivity anywhere.** A hash assumption is a CF premise over a finite set. An oracle assumption is a hypothesis premise.
- **No axioms.** A hypothesis is a premise, never a definition the checker trusts.
- **Do not touch M0 or M1:** `gen/M0`, `gen/M1`, `laws/M0`, `laws/M1`, their records and the 24 statement hashes.
- **Do not touch the `Hyp-Z0-kzg` entry** of `results/M2/hypotheses.json`.
- **No Morph identifiers in the generic generators** (`tests_m2/test_target_agnostic.py`). Instances come from the sidecar.
