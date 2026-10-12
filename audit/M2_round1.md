# Audit round 1, M2: iterations I6–I13

Same-family auditors (Q9 unanswered), so this round does not count toward convergence. Two auditor agents, one for I6–I9 and one for I10–I13, read each iteration's BUILD_PLAN §4 section, the whitepaper sections it realizes, its prompt, its report, its predictions and its tests. They attacked the code on scratch clones and never touched the working tree. Every finding marked *reproduced* was run; the others come from reading the code.

Audited HOLON commit: `e453c1eb60877dac62e884a4b16f77a638dcb6c2`. Machine-readable files: `audit/rounds/M2/round1.json`, and `audit/M2_findings.jsonl` with one finding per line.

**Why a separate findings file.** The I5 tests in `tests_m2/test_audit.py` are preregistered and scan `audit/findings.jsonl` with M0/M1 id patterns, so M2 findings go to `audit/M2_findings.jsonl`. `python -m holon audit status --findings audit/M2_findings.jsonl` summarises them.

## Verdicts by iteration

### Auditor A (I6–I9)

Verdicts by iteration:

**I7: broken in places, and the most urgent.**
- The schema has `statement.scope`, but the emitter, refuter and records ignore it. A bounded law (H=2) that is true within its horizon is REFUTED with a 3-step witness, and its record says `scope: unbounded`.
- The 0.3 `refs` are not transitive:
  - `cost`/`elapsed` do not cover `facts.disch`;
  - observers do not cover the facts defs or library builtins they call;
  - the `step` ref hashes every action's source span;
  - helpers have no `template_id`.
- The gate was never wired for holon-ir/0.3. A full gate on a toy 0.3 milestone fails four ways:
  - G2: hash computed without refs;
  - G1: compares 0 records, because the glob is `L_*.json`;
  - G9: requires `^L_` ids;
  - G4: `error: 'Header'`.
- The `p_ir03_import_depth` probe and `bend/notes/README.md` do not exist.
- The I7 report says record-ref types are in the schema; they are not.
- The ∃ negation is built by the pipeline at run time. It is not a frozen law.

**I8: shallow.**
- Reach, `reach_invariant` and the core-import probe verdicts are real and reproduce.
- The core library does no work:
  - no generated proof ever calls a core lemma;
  - its four proof classes cannot prove the transitivity or compositional lemmas that DISCH and I15's `coercion_guard` need (confirmed by Bend);
  - the core canary is in no gate.
- F-M1-05 (G11V trusts `reachable`) was assigned to I8 and is still open.

**I6: shallow.**
- The byte-identity pins hold.
- Three named deliverables are not done and not recorded:
  - mcanary still hardcodes Morph field names instead of deriving them from `Machine.reads`;
  - the `mreplay` op table is hand-written;
  - `deadline` matches one exact guard shape.
- The grep test covers only 11 files and its regex has no field names, so I6-P3 passes while mcanary holds Morph identifiers.

**I9: faithful.**
- The emitters are import-independent; the axiom audit, forbidden list, `maxRecDepth`, 120 s budget and 8/8 I2 all hold.
- Gaps: G7 passes vacuously when no record lists lean4, and the Lean canaries accept any rejection.

Most important to fix before I15: the gate wiring for 0.3 (G2/G1/G9/G4), G4 canary generation for 0.3 laws, `refs` correctness before the first 0.3 statements are frozen, `scope` semantics, and core-library sufficiency.

### Auditor B (I10–I13)

Verdict by iteration, most serious first. I10 is partly broken. The per-entry checks exist and its tests pass (13/13 re-run), but the lifecycle is not enforced. (1) Moving proofs into proofs/<law>/ removed Bend's own "PROOF.bend must import ./LAWS.bend" rule, and nothing replaced it. A proof that never imports its law passes bend and --verdict, and implication.prove / mpipeline record it as PROVED. Reproduced: a false strengthening was accepted. This also makes I10.md's claim "the separation does not make a law vacuous" false. (2) G2 validates the entries in STATEMENT_DIFF but never requires an entry when a statement hash changes. A weakened M1 law plus an updated registry passes with an empty log. (3) Binding changes still go through the free-text `holon bind --accept-change`. (4) The G3 law-in-proofs regex can be evaded. (5) Accepted entries are re-proved against the current facts, so they break after any later facts change, and the append-only log then keeps G2 red. (6) The implication check depends on binder names. I11 is faithful on the preregistered shapes; diagrams, honesty tests and review tests reproduce. It is shallow where I14/I15 depend on it: nothing in the gate covers gen/M2/diagram, perm_X is never generated, principal classes come from hand-written labels, carrier sort_ref is null, and seven builtins are over-approximated as `*`. I12 is faithful on fixture T12 only. There is no gen/M2/model and no spec/M2/facts, and spec/M2/lib/oracles.json can never apply to the Morph facts. I15's first generated laws would therefore be over the stand-in agg model, which is exactly what moving I12 earlier was meant to prevent. Those records would also show model_assumptions=[] where the M1 records of the same model list 11 entries. I13 is faithful to its frozen contract and reproduces byte for byte. It is thin for I15: 8 of 10 sites are unrefined with no obligation, including :636, which I15 predicts PROVED. Time−Dur carries no sign obligation. Definition sites name definitions instead of actions. Five sites are window-offset artifacts with no code subtraction at their span. The P4 union rests on a hand-chosen builtin name. Gate prerequisites for I15: `holon gate --milestone M2` has never run (it crashes without laws/M2/REGISTRY.json), and G2's IR-0.3 branch hashes laws differently from `holon run` (reproduced).

## Fix plan

- **Lane 1** (the I14 builder, after I14): the I10 lifecycle findings. A proof must import its law. G2 must tie a hash change to a STATEMENT_DIFF entry, and the binding_change channel must be wired. The comment-proof law scan, entry provenance, and implication binder renaming are fixed here, along with the import-depth probe.
- **Lane 2, foundation** (the I15-A builder, before any M2 law is derived):
  - gate wiring for IR 0.3 (G1, G2, G4 routing, G9), with refs fixed transitively before the first 0.3 hashes are frozen;
  - `statement.scope` enforced, and the 0.3 schema record refs;
  - a parametric Morph model for M2, with M2+ records keeping their ledger assumptions;
  - G1 regenerating the M2 diagram, sorts and oracle outputs;
  - site tagging (code subtraction vs model coordinate).
- **Lane 2, I15-B:** core-library composition classes (needed by `coercion_guard`), G4 canary kinds for 0.3 and Reach laws plus the core canary, `mcanary` live fields from `Machine.reads`, an exhaustive Morph-identifier grep, and G11V reachability recomputation (F-M1-05).
- **Debt or questions:** recorded per finding below and in the iteration reports.
- **I13 site obligations (F-M2 on :636 and Time−Dur).** The lead decides this in the I15 contract, without touching the frozen I13 assignment. Every code subtraction realized in Nat is a site with a sign obligation, whatever its sort. Solidity 0.8 checked arithmetic panics on every underflow. The sort classifies a site; it does not decide whether the site exists.

## Findings

### F-M2-01 (high, statement_fidelity; I7): statement.scope is ignored: a bounded law true within its horizon is REFUTED by a longer witness, and the record's scope comes from its status

- Aspect: correctness. Plan/paper: BUILD_PLAN I7 goal 'a scope separate from status', deliverable statement.scope in {unbounded, bounded{H}, at_state{ref}}; whitepaper 8.6 (scope orthogonal to status).
- Evidence (reproduced): In the clone, laws/T9/L3_small_bounded.json is a holon-ir/0.3 law over the toy queue: forall p:Trace. small(run(p,s0)) == true, with scope {kind: bounded, H: 2}. It is true for traces of at most 2 actions. `HOLON_BUILD_DIR=../b_scope python3 -m holon run --milestone T9 --no-registry --out ../t9_results --gen-dir ../t9_gen` printed `L3_small_bounded REFUTED checked finding`. The record has scope 'unbounded' and witness {'p': [push 1, push 1, push 1]} (3 actions > H). `grep -rn '"scope"' holon` shows statement.scope is read only when copying it into generated IR (mlaws.py:421, implication.py:61). mlaws.emit, explore.mjs and ir.render_statement never read it. mpipeline.py:505-508 sets rec['scope'] = 'bounded' iff the status is UNKNOWN, so scope is derived from status, the opposite of the plan's 'scope separate from status'. at_state{ref} is likewise ignored.
- Suggested fix: Emit bounded{H} as a premise len(p) <= H, or a bounded trace type, and bound the explorer by H. at_state needs the referenced state. Until then, reject (Unsupported) any law whose scope is not unbounded. Record statement.scope separately from status in the v2 record. Add a test_ir03 fixture: a bounded-true law must never be REFUTED by a witness longer than H.
- Status: open; fix iteration: I15 (foundation (lane 2, before I15-A)).

### F-M2-02 (high, gate_evasion; I7): The gate is not wired for holon-ir/0.3 milestones: G2, G1, G9 and G4 fail or check nothing on a toy 0.3 milestone

- Aspect: plan_fidelity. Plan/paper: BUILD_PLAN I7 (0.3 statement hash; 'prerequisite for every generated law'); I15 Exit 'Gate green for M2'; whitepaper App. G.
- Evidence (reproduced): In the clone, laws/T7 holds L3_and_true and L3_and_false (tests_m2/fixtures/ir03) on the toy queue, with the registry built from holon.gen.refs.law_hash. `holon run --milestone T7` gave PROVED and REFUTED. `holon gate --milestone T7` printed:
- `G2 FAIL hash mismatch: ['L3_and_false', 'L3_and_true']`. gate.py:644 compares ir.statement_hash(l) without refs; only the 0.2 path uses check_registry_multi.
- `G1 ... records: 0`. gate.py:215 norm_records globs `L_*.json`, so every L3_/L8_ record (ids the 0.3 schema allows: '^L[0-9]?_') goes uncompared. checker_upgrade.py:81 and metrics.py:42 use the same glob.
- `G9 FAIL L3_and_false: v2: ["$.law_id: 'L3_and_false' does not match '^L_[A-Za-z0-9_]+$'"]`.
- `G4 FAIL error: 'Header'`. gate.py:1001 routes only holon-ir/0.2 to g4_machine, so 0.3 falls into the M0 header-canary path.
No M2 or T gate was ever run; checkpoints I11 and I16 report only the M0 and M1 gates.
- Suggested fix: G2: use refs.law_hash(law, facts, oracles) for 0.3, or call check_registry_multi for both 0.2 and 0.3. G1, checker_upgrade, metrics and replay: glob law files the way ir.load_laws_any does ('L*.json'), or align the law_id patterns of IR 0.3 and record v2. G4: route 0.3 to g4_machine. Add a test that gates a toy 0.3 milestone end to end, skipping G6 for the toy.
- Status: open; fix iteration: I15 (foundation (lane 2, before I15-A)).

### F-M2-03 (high, statement_fidelity; I7): 0.3 refs miss what a statement depends on and over-cover what it does not: cost/elapsed ignore facts.disch, observers ignore the defs and library builtins they call

- Aspect: correctness. Plan/paper: BUILD_PLAN I7 'refs maps each referenced definition to the content hash of the construct that defines it: a facts or lib def ... generator-synthesized helpers map to {template_id, template_version}; no whole-bundle hashes'; whitepaper 8.9 references by hash, 9.4.
- Evidence (reproduced): holon/gen/refs.py:27,65,87-88: _TRACE_FNS (runs_ok, last_ok, no_code, perm, cost, elapsed) map to step_src = {state, initial, params, types, defs, actions}. machine.py:740-751 builds cost and elapsed from facts['disch'], which step_src omits. Reproduction on the M1 facts: a 0.3 law claiming cost(p) == 0. With disch.cost.sendMessage changed from 1 to 101, the hash is unchanged (sha256:3dfc1fa0... both times). Changing disch.delay also leaves the hash unchanged (True). refs.py:71: an obsv ref hashes only facts['observers'][NAME]. A law over lci_of(s) keeps the same hash after def lci drops its '- 1' ('hash equal? True'). refs() takes no library argument, so spec/M1/lib/*.lib.json builtins (nth_ch in kappa, win_last, hdr_of) are in no 0.3 hash. Over-coverage: editing only setPause's 'src' span changes the hash of L_disch_stale taken as 0.3 (True), because 'step' covers every action's source text. Under I13/I15 span keys, any re-extraction that shifts line numbers would therefore restale every site law. The plan's {template_id, template_version} for synthesized helpers, and diagram-element refs from I11, are not implemented. tests_m2/test_ir03 only tests ir.statement_hash with hand-given refs; nothing tests refs().
- Suggested fix: Compute refs as the transitive closure over the facts def graph and the library builtins (hash each lib builtin entry). Map cost and elapsed to facts.disch. Give synthesized helpers, including I15's at_site and site_hit, {template_id, template_version}. Exclude doc and src text from the step ref, or key it per action reached. Add refs unit tests: edit a def under an observer, a disch entry and a lib builtin (hash must change), and an unrelated action's src (hash must not). Do this before I15 freezes the first 0.3 hashes into REGISTRY.
- Status: open; fix iteration: I15 (foundation (lane 2, before I15-A)).

### F-M2-04 (high, statement_fidelity; I8): The core library cannot prove the lemmas DISCH and coercion guards need, and no generated proof uses it

- Aspect: plan_fidelity. Plan/paper: BUILD_PLAN I8 goal 'Shared lemmas are checked once and imported'; whitepaper 6 core library, 10.3; I15 deliverable mproofs.coercion_guard (idx-1 at :636 PROVED); I31 DISCH.
- Evidence (reproduced): holon/gen/core.py:25-40: the CATALOG has 9 lemmas. The proof classes absurd, nat1, nat2 and bool1 offer only {==}, a hypothesis, ex falso and the induction hypothesis. They never call another lemma and never match three binders. In the clone, each of the following was appended to CATALOG and core.solve() run; all failed with 'core: no candidate proves <name> case i': core_lt_of_le_lt and core_and_lt_add (both already used by mproofs.deadline, mproofs.py:409-433), core_le_trans, and core_one_le_of_lt (a<b -> 1<=b, the shape of the idx-1 guard). mproofs.py:409-433 and 557 still paste M1's hand-proved CORE (core_lt_of_le_lt, core_le_add_l, core_kappa_site, core_and_lt_add). `grep core_ holon/gen/mproofs.py` finds no generated proof calling the imported core (C.*). Every M2+ proof imports the core and none uses it, so the I8-P4 cost figure (import 0.87x paste) compares unused text. The I8 report's 'they switch to the core library with the first M2 DISCH law' cannot happen with these classes.
- Suggested fix: Add a proof class that composes catalog lemmas (candidates include calls to earlier lemmas, in catalog order). Add a 3-binder nat3 class and Nat.sub lemmas (sub_add, le_of_lt, lt_of_le_lt, le_trans). Move the pasted M1 CORE lemmas into the catalog and make the M2+ deadline, chain_revert and I15 coercion_guard generators call them through C. Test that a generated M2 proof calls a core lemma and fails when that lemma is omitted.
- Status: open; fix iteration: I15 (I15-B (proofs)).

### F-M2-05 (high, mutation_adequacy; I6): mcanary still hardcodes Morph state fields (LIVE_FIELDS); 'derive live fields from Machine.reads' was not done, yet I6-P3 was scored pass

- Aspect: honesty. Plan/paper: BUILD_PLAN I6 deliverable 'mcanary derives live fields from Machine.reads'; 1.3 V16; prediction I6-P3.
- Evidence (reproduced): holon/mcanary.py:20: LIVE_FIELDS = ["s_bvh", "s_tag", "t", "paused", "inch", "qlen"]. These are M1 Rollup state fields. mcanary.py is in the I6 test's GENERIC list, but the MORPH regex (test_target_agnostic.py:24-27) lists no field names, so I6-P3 'The generic generator modules hold no Morph identifier' passes. BUILD_PLAN line 202 (V16) names `mcanary.LIVE_FIELDS` as a Morph item for I6. Machine.reads exists (machine.py:217,583) and is unused here. Reproduction: the union of Machine.reads is ['q'] for the toy queue and ['classes','ctx','heap','txp'] for morph_batchdata, and LIVE_FIELDS present in state is [] for both. For any non-Morph target, the erase_live canary kind yields nothing. The I6 report does not mention mcanary.
- Suggested fix: Set LIVE_FIELDS to sorted(set().union(*cm.m.reads.values())) minus the law's erased fields, in facts state order. Add Morph state, def and observer names (derived from spec/M1/facts) to the grep regex. Re-score I6-P3 as a Surprise in docs/iterations/I6.md.
- Status: open; fix iteration: I15 (I15-B (G4 canaries)).

### F-M2-06 (high, gate_evasion; I7): G4 canary generation has no kinds for IR 0.3 or Reach law shapes and crashes on single-equation existential laws, so an M2 G4 cannot reach 10 canaries of 3 kinds

- Aspect: gate_evasion. Plan/paper: BUILD_PLAN I8 'a G4 canary leaves one core law unproved and must be rejected'; whitepaper 8.8 canary laws; I15 Exit 'Gate green for M2'.
- Evidence (reproduced): mcanary.candidates (mcanary.py:28-56) emits canaries only for subform dead_residue (erase_live, negated), Nat-only forall laws without premises (negated), and exists laws with Nat constants (pin_const). Run over every I6, I7 and I8 fixture with each record set to PROVED, it yields [] for L3_and_true, L3_and_false, L3_cf, L8_reach_{x,y,k,flag} and L_toy_small. Only L_toy_reach gives ['pin_const']. L3_exists_false (∃a. n_of(step(a,s0)) == 5) crashes with KeyError: 'all' at mcanary.py:54 (`m['statement']['claim']['all'][i]` on a claim with no 'all'). gate.g4_machine (gate.py:985) builds CompiledMachine.build(self.facts_path, self.cfg) without reach=, oracles= or a core dir, so canaries over Reach or oracle parameters cannot be emitted. The I8 core canary (core.emit(omit=...)) appears in no gate check; the I8 report admits 'not yet in a gate run'. Since MIN_CANARIES=10 and G4 needs at least 3 kinds, I15's per-site SORT laws (forall p:Trace with a premise) would produce no canaries.
- Suggested fix: Generalize mcanary:
- negate any PROVED forall law at a point where it holds (Act, Trace, Reach witnesses from the explorer);
- add flip and shift-constant mutations of 0.3 claims;
- fix the single-equation pin_const path.
Pass reach=m2plus, oracles and the core into g4_machine. Add the core-omit canary and require it rejected for M2+.
- Status: open; fix iteration: I15 (I15-B (G4 canaries)).

### F-M2-07 (high, gate_evasion; I10): Prover separation lets a proof that never imports its law pass: PROVED without the law being checked

- Aspect: correctness. Plan/paper: BUILD_PLAN I10 Prover separation; whitepaper §9.4 'Provers have no write access to LAWS/', L14; AGENTS.md rule 6.
- Evidence (reproduced): Under the separated layout (mpipeline.py:302-313), PROOF.bend lives in gen/proofs/<law>/ with no sibling LAWS.bend, so Bend's rule 'PROOF.bend must import ./LAWS.bend' no longer applies. separated_proof (mpipeline.py:316-321) only rewrites the import line with str.replace; if a generator omits it, nothing notices. Every acceptance point checks only rr.ok plus the LAWS text: implication.py:153, mpipeline.py:433, 475, 539, 569, 635. Probes in the scratch copy: proofs/l2/PROOF.bend = 'import Base\nimport ../../model/m.bend as M\ndef helper() -> Nat: 0n' gives 'ALL PROOFS CHECK' under bend and under --verdict (exit 0). The same file colocated with a LAWS.bend gives 'Error: PROOF.bend must import ./LAWS.bend'. End to end: replacing mproofs.GENERATORS with a generator returning 'import Base\n\ndef helper() -> Nat:\n  0n\n' makes statement_diff.check_entry(strengthening_false.json) return ok=True, 'strengthening: L10_sd_small => L10_sd_small checked by bend and BendTT --verdict (class forgetful)'. With the honest generators it is rejected. This contradicts AGENTS rule 6 ('the expected law is present in it') and I10.md's claim that 'the separation does not make a law vacuous'. That probe only covered a file that imports the law.
- Suggested fix: At every acceptance point (implication.prove, mpipeline run/param_search/reach_search/negation, G5 and G11 for M2+), require that PROOF.bend imports exactly the relative LAWS path as Laws and defines `def Laws.<law_name>`. Better, check `bend PROOF.bend -o` and require the law symbol to appear as a filled definition. Add a regression test in which the proof omits the import and must not be PROVED.
- Status: open; fix iteration: I14 (lane 1 after I14 (I10 lifecycle)).

### F-M2-08 (high, gate_evasion; I10): G2 never ties a statement-hash change to a STATEMENT_DIFF entry: weaken a law, update the registry, and G2 passes

- Aspect: gate_evasion. Plan/paper: BUILD_PLAN I10 Goal ('every statement change goes through an auditable channel ... enforced mechanically'); whitepaper §9.3 G2, §9.4.
- Evidence (reproduced): gate.py:586-623: G2 = registry hashes match plus check_file(STATEMENT_DIFF) accepts every line. Nothing compares the registry with its committed predecessor or requires an entry for a changed hash. In the clone, adding premise {eq:[{var:j},{nat:0}]} to laws/M1/L_undo_cancel.json and writing its new law_hash into laws/M1/REGISTRY.json gives Gate('M1').g2_registry() -> {'passed': True, 'detail': 'all statement and facts hashes match the registry'}, and check_file(STATEMENT_DIFF.jsonl) -> [] with the log empty. The remaining G2 part (bindings) is satisfied by re-running `holon bind --accept-change` and `holon run`. Whitepaper G2 is 'Statement hashes match the registry; changes only per §9.4', and the second half is missing. I10.md 'Not done' concedes A3 does not cross-reference. check_cross_milestone is not run by any gate check either. For M0/M1 the tests_m2 hash pins are the only backstop; laws/M2, which I15 creates, has none.
- Suggested fix: In G2, for every law whose registry hash differs from the registry at the last commit (read-only git cat-file, as check_file already does), or which was deleted, require an accepted STATEMENT_DIFF entry whose old/new carry exactly those statements. Fail otherwise. Run check_cross_milestone whenever a DERIVATION.json exists. Off git (a copied tree), say the check could not run instead of passing silently.
- Status: open; fix iteration: I14 (lane 1 after I14 (I10 lifecycle)).

### F-M2-09 (high, bindings_ledger; I10): binding_change rule is not wired: rebinding still goes through free-text `holon bind --accept-change`

- Aspect: gate_evasion. Plan/paper: BUILD_PLAN I10 binding_change; whitepaper §9.4, L22.
- Evidence (code reading): bindings.py:333-347: an existing binding whose kernel cone changed is rewritten when any non-empty --accept-change reason is given, and the reason is logged to spec/bindings/changes.jsonl. G2 (gate.py:596-623) then compares the bindings file with the derived ones and passes. It never consults STATEMENT_DIFF. I10 defines binding_change as needing 'a generated, kernel-checked equivalence law ... or a signature' (statement_diff.py:120-128), but that function is only reached for entries someone chose to write into STATEMENT_DIFF. The bindings.py docstring itself says the bindings are 'self-certified until the statement lifecycle (I10)', and I10 did not close it. Code reading only: I did not run a full M1 regeneration.
- Suggested fix: `holon bind` must refuse to change an existing binding unless STATEMENT_DIFF holds an accepted binding_change entry naming those laws and defs. G2 must check that every changes.jsonl change line after I10 maps to such an entry.
- Status: open; fix iteration: I14 (lane 1 after I14 (I10 lifecycle)).

### F-M2-10 (high, gate_evasion; I10): G2 hashes IR 0.3 laws without refs or oracles, so an M2 registry written by `holon run` always fails G2; no M2 gate has ever run

- Aspect: correctness. Plan/paper: BUILD_PLAN I15 Exit ('Gate green for M2'), I10 G2, I12 refs.law_hash with oracles.
- Evidence (reproduced): gate.py:625-651: only holon-ir/0.2 uses check_registry_multi. Every other version, 0.3 included, falls to the 0.1 branch: `ir.statement_hash(l)` with refs=None (line 644), and one facts sha for all laws (line 646). holon run checks the same registry with refs.law_hash(law, facts, oracles) (mpipeline.py:348, 664). Probe in the clone: laws/T9 holding fixture L3_and_true (IR 0.3, toy facts), with the registry written as law_hash. check_registry_multi passes ('holon run registry check: OK'), but Gate('T9').g2_registry() -> {'passed': False, 'detail': "hash mismatch: ['L3_and_true']; ..."} (law_hash c4f8e985... vs statement_hash 97f7b184...). The G2 0.2 call also passes no milestone, so hyp refs are ignored. `python -m holon gate --milestone M2 --checks G1 --report X` crashes with FileNotFoundError on laws/M2/REGISTRY.json. I12.md notes the G11V CORE_MODE mismatch for M2+ inhabitants as well. I15's exit is 'Gate green for M2'.
- Suggested fix: Route every IR version through check_registry_multi(laws, reg, self.m), which handles multiple facts files, refs and the oracle sidecar. Before I15, add a tests_m2 check that runs G2 (and G1, G11V) on a toy 0.3 milestone.
- Status: open; fix iteration: I15 (foundation (lane 2, before I15-A)).

### F-M2-11 (high, model_vs_code; I12): No parametric Morph model: gen/M2/model and spec/M2/facts do not exist, and the M2 sidecar can never reach the Morph facts

- Aspect: plan_fidelity. Plan/paper: BUILD_PLAN I12 Deliverables (machine.py threads h in gen/M2/model; full §11.1 coverage) and Milestone note; whitepaper §8.3 HASH and oracle rows, §8.5.
- Evidence (reproduced): Plan deliverable: 'machine.py threads h and the oracle parameters through step and run in gen/M2/model. agg survives only as the instance'. `ls gen/M2` shows only diagram, oracles and sorts. spec/M2/facts and laws/M2 do not exist. The sidecar is looked up at F/../../lib/oracles.json (oracles.py:49-51): Oracles.for_facts('spec/M1/facts/morph_rollup.json') looks for /home/user/HOLON/spec/M1/lib/oracles.json and returns None. The M1 library still compiles agg as the builtin Nat.add(AGG_BASE, b_enc(xs)) (spec/M1/lib/morph_rollup.lib.json:47). Two entries are marked 'modelled' but nothing in the Morph facts calls them. The verifier is an inline guard ["==","proof",1] with src 'oracle: IRollupVerifier.verifyAggregateProof' (morph_rollup.json around line 2054), and header presentation is direct equality. CF-agg and CF-hdr have no checked instance law ('per_premise', results/M2/hypotheses.json). I12.md 'Not done' says 'no model reads it yet'. Consequence: I15's first generated M2 laws would be over the stand-in model, which defeats I12's stated reason for coming first ('so no generated law has to be re-derived when hashes become parameters').
- Suggested fix: Decide (human question) how M2 models find their sidecar. One option is a milestone-level sidecar passed explicitly to CompiledMachine for M2 runs over spec/M1/facts. Another is pointing the Morph facts' verifier guard and header comparison at calls of the modelled parameters, which changes facts and so needs a new facts document, not an edit of spec/M1/facts. Until then, mark verifier and header_presentation as not_in_scope with the reason, not 'modelled'. I15 must not generate laws until its model is parametric in agg.
- Status: open; fix iteration: I15 (foundation (lane 2, before I15-A)).

### F-M2-12 (high, bindings_ledger; I12): For M2+ records, model_assumptions drops every ledger assumption, so the Morph M2 laws would claim none

- Aspect: honesty. Plan/paper: whitepaper §8.5 (model_assumptions = hypothesis premises holds only when the model has no hidden stand-ins), §8.6 result records; BUILD_PLAN I12.
- Evidence (reproduced): mpipeline.py:520-521 overwrites model_assumptions with O.hypothesis_premises(law, cm.oracles) for every m2plus milestone. No other v2 field keeps the ledger cone; ledger_match is the string 'exact'. results/M1/L_sort_remaining.json lists 11 (CF-keccak-blobhashes, CF-keccak-headers, Hyp-Z0-kzg, abs-absolute-index-arrays, abs-nat-tokens, ..., oracle-ISubmitter, oracle-messenger, oracle-verifier). The same law under an M2 milestone gets hypothesis_premises(law, Oracles.for_facts(...) = None) = [] (run in place). I12.md says so itself: 'The fixture ledger's abstraction entry meets every cone and is not listed.' The stand-ins kept inside the model as not_in_scope (ISubmitter, messenger) and abstractions such as abs-nat-tokens (Nat in place of uint256, central to SORT sign obligations) would vanish from I15's records.
- Suggested fix: Keep the ledger cone in a separate v2 field (e.g. ledger_assumptions), or let model_assumptions = hypothesis premises plus every ledger entry that meets the cone and is not a modelled parameter. Add a G9 check that an M2+ record over a model with ledger stand-ins never lists an empty assumption set.
- Status: open; fix iteration: I15 (foundation (lane 2, before I15-A)).

### F-M2-13 (medium, vacuity; I8): F-M1-05 (assigned to I8) is still open: G11V trusts the record's reachable flag, and an unreachable constructed inhabitant passes

- Aspect: debt_unrecorded. Plan/paper: audit/M1_round1.md F-M1-05; BUILD_PLAN I8 G11V 'Reach premises are inhabited by r0 or r_step chains'; whitepaper 12.3 (L21).
- Evidence (reproduced): audit/findings.jsonl F-M1-05 has fix_iteration I8. inhabit.py:491 only checks `nv.get('reachable') is not True`. The flag is never recomputed from the witness shape, and mlaws.value_literal (mlaws.py:554-556) accepts {'state': {...}} constructed states. Reproduction in the clone: the L_disch_stale non_vacuity witness was set to {'s': {'state': initial + {t:50, inch:true, bc:7}}, 'a': sendMessage} with reachable: true. That state is in a challenge with no challenge and no batch 7, so it is unreachable. The nonvac files were regenerated with inhabit.expected_texts, then inhabit.g11v(Gate('M1')) returned True: '4 premised PROVED laws inhabited (... reachable and non-degenerate ...)'. docs/iterations/I8.md does not mention F-M1-05.
- Suggested fix: In G11V, set reachable = all(state binder witnesses are {'run': ...}), and for Reach binders require the r0/r_step chain. Ignore the stored flag or require that it equals the recomputed one. Record the fix against F-M1-05 in findings.jsonl.
- Status: open; fix iteration: I15 (I15-B (G11V)).

### F-M2-14 (medium, model_vs_code; I6): The Morph-identifier grep test is not exhaustive: 11 hand-listed files and a regex without field names

- Aspect: test_weakness. Plan/paper: BUILD_PLAN I6 'test_target_agnostic.py (grep for Morph identifiers)'; plan scope 'all of holon/'.
- Evidence (reproduced): tests_m2/test_target_agnostic.py:28-30: GENERIC lists 11 files and silently skips any that is missing. It does not cover holon/gen/{core,implication,refs,targetlib,oracles,cdriver,lean_*}.py, holon/js/{policy_gen,houdini,machine,eval}.mjs, holon/sorts/*, holon/diagram/*, inhabit.py or records.py. diagram/access.py:19 already contains `win_at`. Mutation in the clone: appending `MORPH_SPECIAL = {"commitBatch": "win_at", "Rollup": "nth_ch"}` to holon/gen/core.py and a `commitBatch` special case to holon/js/policy_gen.mjs still gives `TestNoMorphInGenerators ... Ran 2 tests OK`. The regex also lacks state, def and observer names, which is how mcanary.LIVE_FIELDS survives. I15's new holon/rules/ and holon/sorts/sites.py would be unchecked.
- Suggested fix: Glob holon/**/*.py and holon/js/*.mjs, minus an explicit, reported allowlist of replay adapters (replay.py, mreplay.py, consumers.py, refinement.py, oracles/zero_blob.py, the m0 part of evidence.py, __main__ help text). Derive the identifier set from spec/M1/facts (state, defs, observers, actions, types) and the M1 libs' builtin names. Fail on a missing listed file.
- Status: open; fix iteration: I15 (I15-B (honesty grep)).

### F-M2-15 (medium, statement_fidelity; I6): mproofs.deadline matches one exact guard shape, not linear Nat conjunctions, and the I6 report does not say so

- Aspect: debt_unrecorded. Plan/paper: BUILD_PLAN I6 deliverable 'mproofs.deadline handles linear Nat conjunctions'; V16 'deadline'; whitepaper 5.7, Thm 6.10.
- Evidence (reproduced): mproofs.py:326-345: _kappa_shape accepts only ['&&', b, ['<', ['+', x, ['get', ['call', nth_default, chs, i], f]], t]]. mproofs.py:383 also requires the premise observer to be named 'perm'. Reproduction on the M1 facts with only the kappa body varied: the original form is recognised, but '(inch && !paused) && ...', a three-term sum 'W + D + start', swapped operands 'start + W', and a second deadline conjunct '&& F < t' all return None. The deadline class does not apply to any of them. docs/iterations/I6.md says only that the deadline class 'matches library kinds instead of names'.
- Suggested fix: Normalize kappa into a Bool conjunction plus linear Nat sums (commutative and associative flattening). Prove preservation per conjunct with core lemmas (which needs the core finding fixed). Until then, list the narrowing under Not done in I6.md, owned by I31.
- Status: open; fix iteration: I31 (debt, recorded in I6.md).

### F-M2-16 (medium, model_vs_code; I6): The mreplay op table is still hand-written; the plan's 'generated' deliverable is missing from the I6 report's Not done

- Aspect: debt_unrecorded. Plan/paper: BUILD_PLAN I6 deliverable 'The mreplay op table is generated'; V16; I40.
- Evidence (reproduced): holon/mreplay.py:39-40 hard-codes OPS = {"commitBatch": 1, ..., "wait": 10, "@legacy_eta2": 11}, and encode_step (mreplay.py:49-73) has one branch per Morph action. prompts/I6_target_agnostic.md moved the replay adapters out of scope and says 'moving them is listed as debt'. docs/iterations/I6.md Not done lists only the library format. BUILD_PLAN line 202 (V16) names `mreplay.OPS`. BUILD_PLAN I40 schedules holon/gen/{foundry.py, gotest.py} to replace the hand op tables.
- Suggested fix: Record the debt in I6.md (Not done) and in the V16 row, owned by I40. Optionally generate OPS and the encoding from facts.actions inputs now (action index plus inputs in facts order), since the harness already decodes a fixed-width row.
- Status: open; fix iteration: I40 (debt, recorded in I6.md).

### F-M2-17 (medium, statement_fidelity; I7): Probe p_ir03_import_depth and bend/notes/README.md do not exist; I7's exit criterion 'probe verdicts recorded' is unmet and the drop was not logged

- Aspect: plan_fidelity. Plan/paper: BUILD_PLAN I7 deliverable 'Probes bend/notes/p_ir03_fn_verdict and p_ir03_import_depth, verdicts recorded in bend/notes/README.md'; Exit 'Probe verdicts recorded'.
- Evidence (reproduced): `ls bend/notes/` lists c_probe, p_core_import, p_ir03_fn_verdict and scale_gen.py. There is no p_ir03_import_depth and no README.md. `grep -rn import_depth` matches only docs/BUILD_PLAN.md:561. prompts/I7_ir03.md names only p_ir03_fn_verdict, so the narrowing happened at prompt rendering, and neither amendments.jsonl nor I7.md records it. Verdicts appear only in probe headers and the iteration reports. The M2 layout (gen/proofs/<l>/PROOF.bend importing ../../laws, ../../model and ../../core/{PROOF,LAWS}) depends on import-path behaviour that no probe documents. Bend rejects './' segments ('an import path of plain names'), found while testing G3.
- Suggested fix: Add a hand-written probe bend/notes/p_ir03_import_depth with chains of relative imports (../../ depth 2 and 3, a PROOF importing a PROOF importing LAWS, './' segments rejected). Record its verdicts, plus those of p_ir03_fn_verdict, p_core_import and c_probe, in bend/notes/README.md. Log the prompt's narrowing as an amendment.
- Status: open; fix iteration: I14 (lane 1 after I14).

### F-M2-18 (medium, statement_fidelity; I7): The I7 report says record-ref binder types are in the 0.3 schema; the schema rejects them (and List<Nat>)

- Aspect: honesty. Plan/paper: BUILD_PLAN I7 deliverable 'Types: Nat, Bool, Bytes(n), Fn<A,B>, record refs, State, Trace, Act, Reach'.
- Evidence (reproduced): docs/iterations/I7.md Not done: 'Bytes(n) and record-ref binder types are in the schema only.' spec/schemas/law_ir_0_3.schema.json binder.type allows only the enum [State, Trace, Act, Nat, Bool, Reach] or the pattern ^(Fn<...>|Bytes\(n\))$. In the clone, validating L3_cf with one extra binder of each type gave: Bytes(32) valid, Fn<Nat,Nat> valid, Entry INVALID, Ch INVALID, Hdr INVALID, Rec<Entry> INVALID, List<Nat> INVALID. List<Nat> is a type mlaws.Emitter.ty supports. Bytes(n) has no emitter mapping (ty() passes the string through).
- Suggested fix: Add record refs (the facts type names, validated against the facts at load) and List<Nat> to the binder grammar. Have the emitter reject Bytes(n) as Unsupported. Correct the I7 report.
- Status: open; fix iteration: I15 (foundation (lane 2, before I15-A)).

### F-M2-19 (medium, statement_fidelity; I7): The negation of an ∃-law is not a frozen law: the pipeline generates it at run time, after the search fails, and writes the statement and its proof together

- Aspect: plan_fidelity. Plan/paper: BUILD_PLAN I7 'The rule that emits an ∃-law also emits its negation subform ∀¬P ... as its own frozen law'; 2.12; I10 prover separation (whitepaper 9.4 'Provers have no write access to LAWS/').
- Evidence (code reading): mpipeline.py:449-453: decide_negation runs only when the ∃-law is not PROVED. It builds the ∀¬ IR (mlaws.negation_ir, mlaws.py:400-423) inside the prover process and writes LAWS.bend and PROOF.bend into the same gen/<law>/neg/ directory (mpipeline.py:631-633; layout() docstring line 308-310). The negation's statement and hash live only inside the ∃-law's record. They are not in laws/<M>/, REGISTRY.json or DERIVATION.json, and G2 and STATEMENT_DIFF do not cover them. negation_ir drops every premise and turns mixed ∀∃ binders all ∀. That is sound, because the result is stronger, but it is not the subform the rule should emit. The I7-P3 test checks only negation.law_id.startswith(...) and status, never the negation's statement.
- Suggested fix: Until the rules engine exists: generate the negation at derive or registry time from the ∃ statement, freeze it in laws/<M>/ with its own REGISTRY hash, and run it as an ordinary law linked by negation_of/negation. Test that the negation statement equals the expected ∀¬ IR.
- Status: open; fix iteration: I24 (debt (rules engine)).

### F-M2-20 (medium, gate_evasion; I9): G7 passes vacuously when no M0 record lists lean4: the exit criterion 'G7 lists I2 for all 8 M0 laws' is not enforced

- Aspect: gate_evasion. Plan/paper: BUILD_PLAN I9 Exit 'G7 lists I2 for all 8 M0 laws'; whitepaper 8.8 dual kernel.
- Evidence (reproduced): gate.py:888 returns (True, 'Lean: no record lists lean4 as checked') when no record claims lean4. Reproduction in the clone: all lean4 kernel entries were stripped from results/M0/L_*.json and independence_class set to I1-shared, then `Gate('M0', root).g7_lean()` returned `(True, 'Lean: no record lists lean4 as checked')`. G1 compares only gen/**/*.bend and the records, so deleting gen/M0/lean/ (report.json and *.lean) and regenerating the records passes G1 and G7 together. Only tests_m2/test_lean.py::test_cross_kernel_agreement would notice. The I9 report raises this as Question 5, still unanswered.
- Suggested fix: For holon-ir/0.1 milestones, have G7 require lean4 checked and I2 for every decided law whenever the pinned toolchain is present. Report 'single-kernel' as a labelled failure, not a pass, when it is absent. Alternatively, have G1 compare gen/<m>/lean/report.json.
- Status: open; fix iteration: I43 (question for the human (G7 promotion, Q8)).

### F-M2-21 (medium, gate_evasion; I10): laws_in_proofs regex misses a law declared with a comment between its name and the colon

- Aspect: gate_evasion. Plan/paper: BUILD_PLAN I10 'G3 rejects a law declaration in proofs/'.
- Evidence (reproduced): gate.py:134 `_LAW_DECL = ^[ \t]*law\s+[A-Za-z0-9_.]+\s*:`. Probe file proofs/L_x/PROOF.bend = 'import Base\n\nlaw sneaky # c\n:\n  {1n == 1n : Nat}\n\ndef sneaky():\n  {==}\n'. bend gives 'ALL PROOFS CHECK', `bend -o` lists `sneaky : {...} =`, and the false variant gives '1 TODO found', so Bend parses it as a law. holon.gate.laws_in_proofs(Path('../g3probe')) returns []. G1's byte-for-byte regeneration is the remaining backstop. test_statement_diff only exercises the plain 'law sneaky:' form.
- Suggested fix: Detect laws from the checker rather than by regex: run `bend F.bend -o F.bendtt` on each proofs/ file and fail on any top-level law symbol that is not Laws.*. At minimum, strip comments before matching. Add the comment form as a test.
- Status: open; fix iteration: I14 (lane 1 after I14 (I10 lifecycle)).

### F-M2-22 (medium, statement_fidelity; I10): Accepted strengthening entries are re-proved against the current facts; any later facts change makes them invalid, and the append-only log then keeps G2 red

- Aspect: correctness. Plan/paper: BUILD_PLAN I10 STATEMENT_DIFF append-only; whitepaper §9.4.
- Evidence (reproduced): check_file (statement_diff.py:185-210) re-runs check_entry on every line at every G2. implication.prove rejects when the entry's facts_sha256 differs from the current file (implication.py:91-95, 116-119). Probe in the clone: strengthening_checked.json with facts_sha256 set as committed laws carry it gives check_file -> []. After a doc-only edit of the toy facts file it gives ['line 1: strengthening L10_sd_small: ... UNSUPPORTED: ... L10_sd_small names facts 8074f7dacecf.., but ... hashes to 1cb9183c176b..']. The log is append-only (check_file rejects a rewrite), so the line cannot be removed. The first reextraction after any accepted strengthening (I17-I20) would therefore break G2 permanently.
- Suggested fix: Check each entry once, against the tree at the commit that appended it (read-only git show of the facts and model at that commit), and record its proof's sha256 in the entry. Later gates should verify only lines added since the last committed version, plus the recorded hashes.
- Status: open; fix iteration: I14 (lane 1 after I14 (I10 lifecycle)).

### F-M2-23 (medium, statement_fidelity; I10): Implication generator depends on binder names and one facts file, so cross-milestone links between independently generated laws cannot be discharged

- Aspect: plan_fidelity. Plan/paper: BUILD_PLAN I10 cross_milestone; whitepaper L22.
- Evidence (reproduced): implication.py:44-51 requires S' binders to be S binders with the same name and type, and the same facts path. Probe: cross_with_implication.json passes (check_cross_milestone -> []). With the new law's binder alpha-renamed a->b2 (same statement), it gives "cross_milestone without a checked L10_xm_new2 => L10_xm_old (UNSUPPORTED: ... binder b2: Act of L10_xm_new2 is not a binder of L10_xm_old with that type)". Laws from holon derive (I15) and the rules engine (I24) get binder names from their own generators, and M3 laws are over extracted facts files. So with no keys/, every back-test link in DERIVATION.json will need a signed weakening and be rejected. check_cross_milestone is also not called by the gate (I10.md 'Not done').
- Suggested fix: Match binders up to renaming: unify by position and type, or take an explicit binder map from the DERIVATION link. Add refinement-map support across facts files later (I20/I24). Wire check_cross_milestone into G2 as soon as DERIVATION.json exists.
- Status: open; fix iteration: I14 (lane 1 after I14 (I10 lifecycle)).

### F-M2-24 (medium, gate_evasion; I10): I10 tests stay green when the soundness guard of the implication obligation is deleted; the 'false strengthening' fixture relies on the prover being incomplete

- Aspect: test_weakness. Plan/paper: BUILD_PLAN I10 Preregister I10-P2; tests_m2/test_statement_diff.py.
- Evidence (reproduced): In the clone: replacing implication.py `missing = premises_included(old, new, cm.m)` with `missing = []` makes an entry whose new statement is the old one plus an extra premise (n_of(step(a,s0)) == 7, i.e. a weakening) accepted: 'strengthening: L10_sd_small => L10_sd_small checked by bend and BendTT --verdict (class hyp)'. `python -m unittest tests_m2.test_statement_diff tests_m2.test_cross_milestone` -> 'Ran 8 tests ... OK'. Unmutated, it is rejected as UNSUPPORTED. strengthening_false.json drops a conjunct that is true on the toy model, so S'⇒S is valid, and the test passes only because no proof class proves it (I10.md Surprises and Questions). The pick class is not exercised by any committed test. test_strengthening... asserts only `'law ' in laws`.
- Suggested fix: Add tests (new names, no edits to preregistered ones): an added premise must be rejected, a proof that omits the Laws import must be rejected, and pick on a 3-vs-2-conjunct pair. Answer the human question by amending strengthening_false to drop a conjunct that is false on the model (e.g. eq_nat(n_of(step(a,s0)),1) == false), logged in amendments.jsonl.
- Status: open; fix iteration: I14 (lane 1 after I14 (I10 lifecycle)).

### F-M2-25 (medium, determinism; I11): No gate check covers gen/M2/diagram, gen/M2/sorts or gen/M2/oracles; I11's exit 'G1 green' is unmet, and I14/I15 would build on outputs no gate regenerates

- Aspect: plan_fidelity. Plan/paper: BUILD_PLAN I11 Deliverables ('writes gen/M2/diagram/*.json, covered by G1') and Exit; I13 frozen assignment; I14 frozen evidence set.
- Evidence (reproduced): G1 (gate.py:652-700) regenerates only through `holon run` and compares only *.bend and *.defs.json, so the diagram and sorts JSON are never compared. gen/M2/oracles/HypV-proof1/*.bend is written by `holon oracle check` (oracle_check.py:427), not by `holon run`, so a future M2 G1 would report it as an extra file. There is no M2 gate at all: `holon gate --milestone M2` -> FileNotFoundError laws/M2/REGISTRY.json. Byte identity rests on tests_m2 only (test_regeneration_is_byte_identical, test_two_runs_are_byte_identical...); I re-ran both and they pass. I11.md 'Not done' admits it. The I14 plan freezes gen/M2/evidence.json from this diagram, and I13's 'frozen assignment' (Thm 6.18) has no gate either.
- Suggested fix: Extend G1 for m2plus milestones: regenerate diagram, sorts, oracle check outputs (and evidence.json from I14) into the temp dir and compare all JSON byte for byte. Add an M2 gate smoke test once laws/M2 exists.
- Status: open; fix iteration: I15 (foundation (lane 2, before I15-A)).

### F-M2-26 (medium, model_vs_code; I11): Principal classes come from hand-written labels and perm_X is never generated; a dropped permission guard is masked

- Aspect: plan_fidelity. Plan/paper: BUILD_PLAN I11 Principal classes ('A generated perm_X(a, who) replaces the string-prefix perm in M2+ models'); whitepaper §8.3, Def 4.2.
- Evidence (reproduced): principals.py:28-34, 64-71: the class is the action's `principal` label up to its parenthetical, and the predicate is read afterwards. Experiment in the clone: removing commitBatch's reason-1 guard mem(who,active) and running `holon diagram`. Class active_submitter keeps [commitBatch, commitState, proveState] with predicate None (erased for all three) and permissionless False, and only a PRINCIPAL debt line is recorded. machine.py:759-765 still emits the M1 string-prefix `perm` (startswith('anyone','environment')) for every milestone, and mproofs.py:416 uses the same prefix. `grep -rn perm_ holon/` finds no generator of perm_X. So the M2 model I15 generates first would inherit label-based perm, and a missing modifier would stay invisible to DISCH laws.
- Suggested fix: For m2plus models, generate perm_<class>(a, who) from the diagram predicates and stop using the label prefix. Classify actions by their permission guard and treat the label only as a name. A label/guard disagreement should fail the build (or be a finding), not be debt that erases the predicate.
- Status: open; fix iteration: I19 (debt (principals and linking, I19)).

### F-M2-27 (medium, model_vs_code; I13): Only 2 of 10 sites carry an obligation; :636 (predicted PROVED by coercion_guard in I15) and every Time−Dur subtraction get none

- Aspect: plan_fidelity. Plan/paper: whitepaper §7.2 ('A signed sort realized in unsigned arithmetic generates a sign obligation'), §5.6; BUILD_PLAN I15 Preregister (:636 PROVED by coercion_guard).
- Evidence (reproduced): gen/M2/sorts/assignment.json sites: :363 SDur sign, L1MessageQueue...:325 SIdx[queue] sign, and 8 sites 'Nat (unrefined)' with obligation null (:441, :485-495, :636, :644-660, w, lci, bvh_at x2), because sort_seeds.json has no batch-index rule. grammar.py:221-234: ROLE_TABLE '-' (P,G) -> Time for the T pair, with no sign, while Idx−Cnt -> SIdx is signed. Experiment in the clone: planting guards `t - D > 0`, `W - D > 0` and `btot - qpend > 0` in finalizeBatch gives sites 'Time None', 'SDur sign' and 'SCnt[queue] sign'. So `block.timestamp - x`, realized in uint256, gets no SORT law. I15's goal 'one obligation per signed-to-unsigned site, whether or not a human modelled a require' and its prediction for :636 cannot be met against this frozen assignment (I13.md Questions 1 and 3).
- Suggested fix: Human decision before the I15 prereg. Either (a) emit a sign obligation for every Nat subtraction whose sort is unrefined or Time−Dur (conservative), or (b) add an STime sort and a batch-index lexical rule in a new seed-sidecar version, under a new prereg. The I15 prereg must list per-site outcomes against whichever assignment is frozen, and must not tune it.
- Status: open; fix iteration: I15 (decided by the lead in the I15 contract (every code subtraction is a site)).

### F-M2-28 (medium, model_vs_code; I13): Site list mixes model window-offset artifacts with code subtractions; definition sites name definitions, not entry actions

- Aspect: plan_fidelity. Plan/paper: BUILD_PLAN I13 'Sites are keyed by source span'; I15 sites.py (one law per source span, one witness per entry point).
- Evidence (reproduced): Definition sites have entry_points ['w'], ['lci'], ['bvh_at'] and pseudo-spans 'morph_rollup:w' etc. (assign.py:186-196). Walking the facts call graph: w is reached by 6 actions, lci by 7 actions plus observer lci_of, bvh_at by the 3 commits. In the pinned source /root/work/morph@3e44e79, Rollup.sol:441 is `require(_batchIndex > lastFinalizedBatchIndex)` with no subtraction (the facts' `idx - lfi` is a window position). Likewise :485-495, w, lci and bvh_at are window/shadow coordinates. Real subtractions :443 `_batchIndex - 1` (checked), :461, :742, :746-747 (unchecked) and :794 have no site and are recorded as no debt. The btot−bn site is spanned at L1MessageQueueWithGasPriceOracle.sol:325, which is `require(pendingQueueIndex == _startIndex)`; the subtraction is Rollup.sol:742, inside unchecked, so it wraps instead of raising Panic 0x11. I15's plan replays witnesses 'as Panic 0x11 at' the span and derives law ids from spans.
- Suggested fix: For I15: give each definition site the transitive calling actions as entry_points. Tag each site as code_subtraction (with checked/unchecked) or model_coordinate. List the code subtractions in the modelled functions that have no facts site as SORT coverage debt. The I15 prereg should predict outcomes only for code_subtraction sites and should not expect a Panic replay for unchecked or artifact sites.
- Status: open; fix iteration: I15 (I15-A (sites)).

### F-M2-29 (medium, model_vs_code; I13): The I13-P4 union Dig[VH]+Dig[Agg] rests on a seed rule matching the hand-chosen stand-in builtin name 'agg'; the honesty test never renames builtins

- Aspect: honesty. Plan/paper: BUILD_PLAN I13 Goal ('Infer refined sorts mechanically'); prompts/I13_sorts.md 'Lexical seeds are generic'; whitepaper §7.4, §7.7.
- Evidence (reproduced): spec/M2/lib/sort_seeds.json lex-aggregate {match: builtin, pattern: '^agg$'}. 'agg' is the M1 author's stand-in name (morph_rollup.lib.json:47), not a real-code identifier. Experiment in the clone: renaming builtin agg to zz_fn in the library and the facts calls, then `holon diagram` and `holon sorts`, gives Entry.bvh, s_bvh and Entry.hb 'Dig[VH]' (baseline 'Dig[Agg] + Dig[VH]'), and unions.json is empty. test_sorts_honesty.rename_identifiers renames only facts state, inputs, lets and def params, never library builtin names, so the test cannot see this. The prompt allows 'library builtin names', but its examples are real-code identifiers. I14's preregistered E5 claim for L_tag_BVH depends on this union.
- Suggested fix: Human decision. Either accept builtin-name seeds as hand vocabulary and say so in I13.md (P4 then 'passes on a stand-in name'), or seed Dig[Agg] from a real-code identifier (keccak256 over blob hashes in the builtin's doc or source) in a new sidecar version. Add a builtin-rename mutation to the honesty suite as a new test.
- Status: open; fix iteration: I30 (question for the human).

### F-M2-30 (medium, model_vs_code; I11): E5 and E2 inputs for I14 are not ready: carriers have no sort_ref, 91/142 rollup keys are unrefined, and seven builtins are accessed whole ('*')

- Aspect: plan_fidelity. Plan/paper: BUILD_PLAN I14 (E2 write-then-read, E5 equal refined sorts from I13); whitepaper Def 4.1 (σ_v on every carrier), Def 4.5.
- Evidence (code reading): Every diagram carrier has sort_ref null (I11.md, I13-R2). assignment.json keys are facts binders ('Entry.bvh', 'Ch.s'), not carrier ids (win is one List<Entry> carrier), and nothing maps one to the other. morph_rollup assignment: 91 of 142 keys are 'Nat (unrefined)', so 'identical refined sorts' would hold trivially between unrefined endpoints. The diagram records 7 ACCESS debts: bump_f, clear_chs, any_open, zero_csr, set_last_csr, win_last, tags_exact plus the go_* builtins are over-approximated as whole-field '*' reads and writes (e.g. TRANS.finalizeBatch writes ['win','*']). A write at '*' matches any read, so E2 (strong) evidence could be inflated and turn intent questions into findings.
- Suggested fix: In I14: define the carrier-to-sort mapping explicitly (record fields to assignment keys) and treat 'Nat (unrefined)' as no E5 evidence. Count an E2 match through a '*' term as at most E6, or as a separate unknown, until the library declares access kinds (I11 Q3; changing the library changes M1 generator_sha256, so it needs a human answer).
- Status: open; fix iteration: I14 (I14 (evidence inputs)).

### F-M2-31 (low, vacuity; I7): The I7 CF and ∃ fixtures test little: L3_cf proves P ⇒ P, its inhabitant is the identity rather than the model's hash stand-in, and the I7-P2 and I7-P3 checks are shallow

- Aspect: vacuity. Plan/paper: BUILD_PLAN I7 G11V 'CF(h, S) is inhabited by h := agg with CF(agg, S) discharged by evaluation'; whitepaper Cor 6.16.
- Evidence (code reading): tests_m2/fixtures/ir03/L3_cf.json renders as '∀ h: Fn<Nat,Nat>. CF(h, {1, 2}) ⇒ eq_nat(h(1), h(2)) == false'. Its claim is its premise, and it is PROVED by mproofs 'hyp' (return the hypothesis). The inhabitant is h := id from the explorer's family {id, zero, succ} (explore.mjs:121). The plan asked for h := agg with CF(agg, S) discharged by evaluation; the prompt changed this without logging it. test_ir03: I7-P2 covers only failing_conjunct == 0; I7-P3 checks negation.law_id prefix and status, not the ∀¬ statement; I7-P5 checks only non_vacuity.status == 'inhabited'. No fixture uses CF inside a model step.
- Suggested fix: Add a fixture whose claim depends on CF through the model (a step that applies h at two points). Inhabit the CF premise with the sidecar's concrete hash instance (I12) or the stand-in. Assert the negation's IR and a failing_conjunct index other than 0.
- Status: open; fix iteration: I24 (debt).

### F-M2-32 (low, gate_evasion; I9): Lean canaries count as rejected for any reason (parse error included), and the I9-P4 test also passes when Lean is unavailable

- Aspect: test_weakness. Plan/paper: BUILD_PLAN I9 prediction 'a flipped-equality Lean canary is rejected'; whitepaper 8.8.
- Evidence (code reading): gate.py:921-925 counts a canary as rejected when r['result'] == 'rejected', whatever the reason. Unlike Bend G4 (which requires '- expected :'), it does not check for a semantic error such as a definitional mismatch. The I9 report (Surprise 4) shows the flip canary is rejected for a shallow reason ('Expected the goal to be a binary relation'). tests_m2/test_lean.py::test_flipped_equality_canary_is_rejected asserts assertNotEqual(r['result'], 'checked'), so 'unavailable', 'forbidden' or 'timeout' also pass. FORBIDDEN (lean.py:47-50) does not list #eval, which runs IO during the lake build. That is low risk because `import` is forbidden.
- Suggested fix: Require the canary's Lean error to be a type or definitional mismatch (e.g. 'not definitionally equal' or 'type mismatch'), not a parse or elaboration-shape error. Have the test assert result == 'rejected'. Consider adding #eval to FORBIDDEN.
- Status: open; fix iteration: I43 (debt).

### F-M2-33 (low, statement_fidelity; I13): R5's label branch is dead under R2/R3; P3 scoring stands, but the frozen contract needs an amendment

- Aspect: plan_fidelity. Plan/paper: whitepaper §7.3, §7.4; I13 contract R2/R3/R5.
- Evidence (code reading): Contract R5 (tests_m2/test_sorts_morph.py docstring) lists 'Idx[k] with distinct labels' as a union case, while R2 makes labels a property of the register, never of the value, so the branch cannot fire. Under the other reading, qpend := (bn==0 ? qpend : btot) would be Idx[queue]_fin + Idx[queue]_inc and P3 would miss. Whitepaper §7.3 names the queue cursors' sorts directly ('refine to Idx[queue]_fin (P) and Idx[queue]_inc (T)'), and §7.8 types P as Idx_fin. So R2/R3 match the paper's intent, and P3 passing is defensible, not post hoc. The literal §7.3 condition 'no value flow between them' is weaker than R3's SCC reading, but R3 was frozen before the results.
- Suggested fix: Human\: confirm R2/R3 and log an amendment deleting R5's label branch (or restating it as 'never arises in I13').
- Status: open; fix iteration: I15 (question for the human; amendment proposed).

### F-M2-34 (low, statement_fidelity; I10): A3 (audit regress) reports hash changes and commit order only, not proof strengths, status changes, additions or STATEMENT_DIFF coverage

- Aspect: whitepaper_depth. Plan/paper: whitepaper §9.5 A3.
- Evidence (reproduced): regress.py: hash_changes skips laws added in A..B ('A law added in A..B is not a change') and never reads results/<M> status, kernels or independence_class. It also does not say which STATEMENT_DIFF entry covers each change. It runs and reproduces R1 ('A3 8a1dbe7..e453c1e: 0 statement-hash changes; 24 laws: prediction_first 8, result_same_commit_prediction_later_or_together 16'). Whitepaper §9.5 A3: 'Compare law sets, premises and proof strengths across commits'.
- Suggested fix: Add law-set additions, per-law status/kernel/independence transitions, and a covered_by STATEMENT_DIFF line for each hash change.
- Status: open; fix iteration: I45 (debt).

### F-M2-35 (low, model_vs_code; I12): I12-P1's 1.5x term-size pass is dominated by a unary literal in the stand-in, so the measure says little about parameter cost

- Aspect: vacuity. Plan/paper: BUILD_PLAN I12 Preregister (1.5x term size); whitepaper §9.5 A4.
- Evidence (code reading): I12.md: ratios 0.30-0.34, because the stand-in's AGG_BASE = 1000 is printed in unary (15,474 of about 20,900 characters). With AGG_BASE = 1 (scratch) the ratio is 1.07-1.08. The prediction was scored on the preregistered measure, as written, and the report discloses this, so this is not a scoring error. The CF-agg A4 'checked' is also a 273-sample collision test of holon's own keccak256, which cannot fail in practice.
- Suggested fix: None for I12. When the Morph model becomes parametric (see the high I12 finding), report its term size per law against the stand-in model with the literal normalized.
- Status: open; fix iteration: I20 (debt).

### F-M2-36 (low, model_vs_code; I11): CODEC partiality is the option-codomain test only; enc_sol's out-of-domain revert is modelled as an UNDEF sentinel and marked total

- Aspect: plan_fidelity. Plan/paper: whitepaper Def 4.2, §8.3, §9.5 A2.
- Evidence (code reading): I11.md Surprises/Q1: partial iff the facts' codomain is Maybe<T>, so only dec_go is partial. enc_sol has domain guard version <= 2, the Solidity code reverts outside it, and the M0 model returns a one-cell UNDEF byte list. §8.3 says 'partial edges return an option type, so definedness is explicit', so a sentinel is exactly what that rule excludes. A2 (I21) must check 'that the model's partiality matches the code's', and the diagram currently says enc_sol is total.
- Suggested fix: Human answer to I11 Q1. If partial means 'not total on the carrier type', mark enc_sol partial with its domain, and have I21 test both.
- Status: open; fix iteration: I21 (question for the human (I11 Q1)).

### F-M2-37 (low, model_vs_code; I13): Grammar has Prin/Amt/Ver/records as text only; inference never produces them (no role labels)

- Aspect: whitepaper_depth. Plan/paper: whitepaper §7.1, §7.5, §7.7 step 2.
- Evidence (code reading): assignment.json morph_rollup: 13 Time, 7 Dur, 8 Bool, Idx/Cnt[queue], Dig, 91 unrefined; no Prin[role], Amt, Ver or record sort anywhere. The caller input who and the deposit DEP stay 'Nat (unrefined)', and the I11 principal classes are not used as role seeds. §7.7 step 2 says 'carrying writer and role labels'. §7.5 is outside I13's Realizes line, so this is depth debt, not a plan miss.
- Suggested fix: Seed Prin[role] from the diagram's principal classes and Amt from the cost terms when sorts III (nominal types) lands, and record the debt in I13.md 'Not done'.
- Status: open; fix iteration: I30 (debt).
