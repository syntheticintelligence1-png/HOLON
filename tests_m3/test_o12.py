"""I65 (= I33b): the O12 intent contract on M2's window view of the extracted Rollup (whitepaper §5.9 intent contracts,
§9.3 G10; docs/CASESTUDY.md N2 and O12; BUILD_PLAN §4 I33; docs/HUMAN_ANSWERS.md Q4, Q8 and the I33 scope answer of
2026-10-22). This docstring is the contract.

Scope. I65 is the second part of BUILD_PLAN I33 pulled forward under its own key, after I64 (= I33a, the machinery on
a toy). It registers the first real intent contract, C_o12, on M2's window view (gen/M2/extracted/m1_view.json, the M1
abstraction with the requires the extracted code lacks removed; holon.differential), where the undo pair
L_undo_cancel (challengeState, then setPause(true)) is REFUTED: pausing deletes the open challenge but keeps the +W
extensions it gave the other batches (O12). The contract's L_weak bounds them: every batch's finalize deadline is at
most its commit time plus F plus W for each challenge that succeeded so far. I65 builds the three things that needs: a
ghost counter (O1), a proof class for linear bounds over traces (O2), and the integration of a contract-derived law and
of marks into a real milestone (O4-O7). I33 keeps its number for the O12 contract on M3, which also needs 256-bit word
lemmas and the UNDO analogue of L_undo_cancel (I27 gap G5) after I26's catalog.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i65.py (O5 and O7, independently of holon/, over tests_m3/_i64.py for K1-K5) and
the fixture tests_m3/fixtures/o12/ (C_o12.json, the contract; C_o12_tight.json, a planted false bound; C_o12_open.json,
a second true claim for the class).

O1 Ghost terms. holon-ir/0.3 gains, additively, the term {"ghost": A, "add": E, "over": T, "from": S}:
   spec/schemas/law_ir_0_3.schema.json gains it (t_ghost: exactly these four keys, A an identifier), and
   docs/adoption/Q4/schemas/ follows the schema byte for byte (I64's K10). A names an action of the law's facts; E is a
   holon-facts/0.2 expression of type Nat over the state's fields, A's inputs and the facts' params; T is a Trace term
   and S a State term. Its value is the sum, over the steps of T run from S, of E in the state before the step with that
   step's inputs, for each step whose action is A and that succeeds (the model's last_ok after the step), and 0 for
   every other step. It is a history variable: it reads the run and never changes it. The emitter writes two statement
   helpers per distinct (A, E) in LAWS.bend, beside the ex_ helpers (part of the statement: a proof file can neither
   define nor change them): gh1_<12 hex>(a, st), one step's share, and gh_<12 hex>(tr, st), the sum, folding from the
   front of the trace. The refuter (holon/js/explore.mjs) evaluates the term through the same helpers compiled with the
   model. An unknown A, an E that is not Nat or that applies an oracle parameter, or a model that threads oracle tables
   makes the law unsupported (its record says why), never a silent 0. A law without ghost terms gets the LAWS.bend,
   model, compiled modules, search and record it got before (generator_sha256 aside).
O2 The class trace_bound. A proof generator in holon/gen/, appended to holon.gen.mproofs.GENERATORS (holon.mpipeline
   still tries coercion_guard, param_premise and reach_invariant after GENERATORS, as at the prereg), for a law with the
   binders "forall p: Trace" then zero or more "forall" Nat binders, no premise, and a claim that is a conjunction of
   props {expr: E_i, from: run(p, s0), bind: some of the Nat binders and ghost terms over (p, s0)} == true. Each E_i is
   a Bool combination (&&, ||, !) of Bool state fields and comparisons (<=, <, ==) of linear Nat sums; an atom of a sum
   is a Nat literal, a Nat state field or param, a bound name, or a Nat field of an element a target-library builtin of
   kind nth_default reads (get(call(f, list, index), field)). It proves the conjunction as an inductive invariant of
   every run from s0:
   - the invariant quantifies the Nat binders inside it (finalizeBatch's drop(win, 1) moves window position k + 1 to k,
     so a step needs the hypothesis at every position) and takes the ghost's running sum as a parameter;
   - the initial state by computation, splitting the Nat binders as far as the initial lists need;
   - one lemma per action over the result of the action's decision in the model: it walks the action's decide chain
     one guard at a time, keeping each guard's equation (Bend's convoy pattern), so that on the Ok branch the payload
     the effects read (the commits' prt, W + start - t under an open challenge) is known from the guards and lets; a
     reverting step keeps the state and adds 0 to the ghost;
   - each comparison carried through the action's effects by Nat lemmas and list lemmas for the builtins the effects
     apply: snoc, take, drop, tail, the target library's nth_default and set_default builtins, and the builtins
     without a kind (bump_f, clear_chs) through a pointwise sidecar, spec/M1/lib/morph_rollup.pointwise.json, which
     holon.records.generator_files adds to the holon-ir/0.2 and 0.3 generator closures; the ghost's share is added on
     a successful step of its action;
   - then induction on the trace, generalised over the start state and the ghost's running sum.
   Every lemma, the sidecar's statements included, is proved in the law's PROOF.bend (no axiom, no escape hatch:
   AGENTS rule 3); the byte-pinned core (gen/M2/core/, gen/M3/core/; I43-R1) does not change. It searches no
   strengthening: the claim must be inductive as stated. A law of another shape, or a comparison it cannot carry, gets
   no proof from it; Bend decides every proof it writes. No existing class changes, so no law an existing class
   decides changes; the refuter changes only by O1.
O3 The contract. laws/CONTRACTS/C_o12.json is tests_m3/fixtures/o12/C_o12.json (equal as JSON), valid (K1) and
   registered (K2: laws/CONTRACTS/REGISTRY.json). It is the only contract of M0-M3. Its L_weak, over p: Trace and k: Nat
   from s0, with g the ghost (challengeState, W): (a) at window position k, bdf <= bdo + F + g (an empty position reads
   the empty entry, 0 <= F + g); (b) !inch || W <= g; (c) !inch || nth_ch(chs, bc).s <= t. (b) and (c) are the facts
   (a)'s induction needs: a batch committed while a challenge is open gets the remaining window, W + start - t
   (Rollup.sol:360-364). The bound is loose by design: g counts W for every challenge that ever succeeded (BUILD_PLAN
   I33: f_j <= commit_j + F + W * #challenges), not the extensions one batch received. C_o12_open, a fixture never
   registered in the tree, is (b) and (c) over p alone: a second true claim that trace_bound must prove too (a
   construction check, not a prediction).
O4 The derived law is a law of M2. laws/M2/L_contract_C_o12.json is K3's derivation (facts
   gen/M2/extracted/m1_view.json, facts_sha256 that file's sha256 now).
   - Derive. `holon derive --milestone M2` writes holon.rules' laws as before, then the laws `holon contracts derive`
     writes (K3), into --out's directory when given, and lists them in laws/M2/REGISTRY.json: each statement hash, and
     each facts file with its sha256 in facts_files. The registry's facts and facts_sha256 stay the rules' primary
     facts, and DERIVATION.json lists the rules' laws only. holon/contracts.py does this, called from holon/__main__ and
     from G1's regeneration of laws/M2; holon/rules/ does not change, and no module of a generator closure imports
     holon/contracts.py (I64 K5).
   - The view is anchored to its abstraction. A facts document whose extraction block names a window declaration
     (holon.differential's view) takes the target libraries and search hints of the declaration's abstraction
     (spec/M1/facts/morph_rollup.json: spec/M1/lib/, spec/M1/policy_hints.mjs), as the differential's runs do. Its
     ledger bundle is generated, never hand-written, when a record's facts are the view itself (holon.records'
     bundle lookup, as I24's linked documents' bundles are): the abstraction's bundle with its M2 extension, re-keyed
     to the view's path and sha256, so the record's ledger_match is exact. The records of results/M2/extracted_m1,
     whose laws' facts are M1's, keep their derived bundle.
   - `holon run --milestone M2` decides it over the view (K4); the view takes no oracle table.
   - Every check of `holon gate --milestone M2` passes over it: G1 (derive, run and the outputs regenerate), G2
     (registry; spec/bindings/M2.json binds it; the statement-change log, where a new law is no change), G3, G4, G5,
     G6, G7, G8, G9 (its record valid against v1 and v2), G10 (O7), G11, G11V, GENV, GREF and GEVID.
   - GEVID enforces on it as on every M2 law: I65 adds no exemption, and I14's rule stands (tests_m2/test_evidence.py:
     from M2 on, an uncovered law, or metadata evidence its computed levels lack, fails). M2's evidence set models no
     window view, so the law (its contract's evidence, E2, copied by K3) is uncovered until a separately
     preregistered key models the view in gen/M2/evidence.json, as I20 covered its adopted documents (the human's
     Question Q62). I65's build does not merge while GEVID fails on the law; the record's evidence fields are those
     GEVID computes.
   - Lean (G7). Its lean4 entry comes from M2's own Lean directory (gen/M2/lean, the report of results/M2), never the
     view's (gen/M2/extracted/m1/lean): not_run with reason unsupported_form, the Lean emitters (holon.gen.lean_mlaws)
     raising lean_common.Unsupported on a ghost term. The directory's Lean model of the view,
     gen/M2/lean/models/m1_view.lean (I43 rule L4: a model file for every Bend model its laws use), is emitted and
     checked like the model of every attempted law, its Lean twin library taken from the view's abstraction
     (holon.gen.lean_machine.lib_twin, as the view anchor above).
   - What follows is regenerated, never hand-written: laws/M2/REGISTRY.json, spec/bindings/M2.json,
     results/M2/metrics.json, results/M2/historical/laws.json (`holon historical laws`: one entry per M2 record),
     gen/M2/model/m1_view.* (the run's model of the view), gen/M2/lean/ (`holon lean --milestone M2`), and every M1 and
     M2 record (generator_sha256 alone: I65 changes files of the holon-ir/0.2 and 0.3 closures). No M0 record changes.
O5 Record directories. A contract of milestone M marks records in M's record directories: results/M and, when it is a
   directory, results/M/extracted_m1 (holon.differential's records of the M1 laws over M's window view). A scope law
   with a record in both is ambiguous: `holon contracts apply` refuses it (exit 2, nothing written) and G10 fails naming
   it. A REFUTED record is licensed for a mark only when its facts_sha256 is the sha256 of the contract's facts file
   now: the L_weak and the law it bounds are statements about one model, and a record over other facts stays unmarked.
   Everything else is K5 (tests_m3/_i65.expected_marks, contracts_doc): the mark's fields, the least id, apply's
   unmark-then-mark, and results/M/contracts.json, whose marked lists the law ids of a proved contract's scope whose
   records it licenses.
O6 Keeping marks. The last step (K5's apply) runs after `holon run` and after `holon differential --milestone M`, which
   rewrites results/M/extracted_m1: both end with apply for M (in --out's tree when given). The differential writes
   each record without concretization, which the final filter of `holon refute` (holon/refute_m3.py) writes back: on a
   marked record it recomputes the bin into intended.replaces and keeps filter_bin intended_bounded and the mark, it
   writes the recomputed bin as the record's "after" in results/M3/refute/filter.json (which therefore does not
   change), and its --check compares the recomputed bin with intended.replaces. The gate's recomputed bin
   (holon/gate.py: G1's final overlay, G6) is compared with intended.replaces on a marked record. In the tree, the mark
   is written by apply after `holon run --milestone M2`; I65 regenerates no view record otherwise.
O7 G10. K6 over both directories (tests_m3/_i65.g10): every record of both is a JSON object, no scope law is ambiguous,
   and the marks of both are exactly the licensed ones. On M2 it passes and names the mark: "C_o12 proved, marks
   L_undo_cancel".
O8 Earlier tests, amended in this prereg, each narrowed to I65's outcomes and logged in its own key's amendments file:
   - I64-R1, tests_m3/test_contracts.py::TestRegressions.test_no_contract_on_the_real_milestones: a contract may name
     M2 exactly when the I65 key lists its id (C_o12);
   - I40, tests_m3/test_refute.py: TestConcretization.test_every_refuted_record_gets_its_predicted_bin,
     test_every_refuted_record_at_head_has_a_recomputed_bin and test_the_filter_document_lists_every_recomputed_bin
     read a marked record's intended.replaces where they read its filter_bin (the bin the final filter computes, O6);
     TestRecordsAndShared.test_earlier_records_change_only_in_the_filter_fields also lets a record gain "intended" when
     its filter_bin is intended_bounded;
   - I43, tests_m3/test_lean_promoted.py: laws of subform intended_weak (a contract's L_weak, K3) and their records are
     outside I43's promoted set. TestPreregInstruments.test_sidecar_is_the_computation recomputes over a copy of the
     tree without them (their law files, records and registry entries; the registry written as holon derive writes it),
     test_scope_counts leaves them out of the live PROVED set,
     TestRegressions.test_statuses_and_bend_files_are_unchanged lets their records carry a lean4 entry,
     TestGates.test_metrics_report_cross_kernel_coverage leaves their PROVED records out of the reported count, and
     TestCode.test_lean_check_is_deterministic_on_the_committed_tree and
     TestDifferential.test_every_emitted_lean_file_obeys_the_file_rules let a Lean directory also hold the model file of
     an intended_weak law's Bend model (rule L4), held to the model file rules;
   - I15, in spec/M2/amendments.jsonl, by a later commit of this prereg's pull request (a prereg commit may not touch
     tests_m2/): tests_m2/test_sort_site_outcomes.py TestRecords.test_every_m2_law_has_a_record_valid_under_v1_and_v2
     and test_proved_site_laws_are_not_vacuous treat an intended_weak law as no SORT-site law (DERIVATION.json does not
     list it), tests_m2/test_sort_sites.py TestDeriveContract.test_registry takes the registry's primary facts from the
     rules' laws and looks up DERIVATION.json for those laws alone, and
     TestPredictedDerivation.test_363_is_one_law_reached_from_the_three_commits_at_their_realization_checks leaves
     intended_weak laws out of the site laws it reads.
   At the prereg no law is intended_weak and no record is marked, so each amended test checks what it checked before
   (some fail there on unrelated records, as at the base: I40-P7's recorded MISS and I43's baselines of three typed M3
   records; the amendments neither cause nor hide that). No other earlier test is amended: one that fails on I65's
   outcomes is a miss, reported.
O9 Rules. I65 changes no law, record or generated file of M3 (results/M3/refute/filter.json included), no law of M0 or
   M1 and no M0 record, writes no frozen root (AGENTS rule 1), and names no contract or law id of its own in holon/
   (C_o12, C_o12_tight, C_o12_open, L_undo_cancel; AGENTS rule 2). Its outcome paths are narrow, so that a regeneration
   of M1 and M2 records on another lane never counts as an outcome written before this prereg: laws/CONTRACTS/,
   laws/M2/L_contract_C_o12.json, results/M2/L_contract_C_o12.json, results/M2/contracts.json, gen/M2/laws/L_contract_,
   gen/M2/proofs/L_contract_ and docs/iterations/I65.md. Its code (the ghost term, the class, the integration), the law
   IR schema's term and the pointwise sidecar are build commits. I26 (the other lane) shares
   spec/schemas/law_ir_0_3.schema.json (each adds a term), docs/adoption/Q4/schemas/ (byte-equal to it),
   holon/gen/mproofs.py and the regenerated M1 and M2 records: whichever lands second merges the other, keeps both
   terms, refreshes the Q4 copy and regenerates what the merge makes stale. I65's own commits are the non-merge commits
   of `git log --first-parent <prereg>..<end>`, end the first commit that adds docs/iterations/I65.md (I64-R2's scope).

Commands
  python -m holon contracts derive|apply --milestone M [--check]   K3, K5 (apply refuses an ambiguous scope law: O5)
  python -m holon derive --milestone M2                            O4 (with the contract laws, listed)
  python -m holon run --milestone M2 [--laws ID,..]                K4, with the last step
  python -m holon differential --milestone M2 [--reuse-view]       O6, with the last step
  python -m holon refute --milestone M3 --only filter [--check]    O6
  python -m holon gate --milestone M [--checks ...]                O4, O7
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m3._m3 import ROOT, copy_repo, file_sha256, item, load_json, predictions, run_bend, run_holon, validate

FX = ROOT / "tests_m3" / "fixtures" / "o12"
M = "M2"
VIEW_FACTS = "gen/M2/extracted/m1_view.json"
PRIMARY_FACTS = "spec/M1/facts/morph_rollup.json"   # the rules' primary facts of laws/M2/REGISTRY.json
LID = "L_contract_C_o12"
SCOPE = "L_undo_cancel"
VIEW_REC = Path("results") / M / "extracted_m1" / f"{SCOPE}.json"
LAW_IR = ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"
# the generators and the refuter that existed at the prereg (holon/gen/mproofs.py GENERATORS, holon/mpipeline.py), and
# the one class I65 adds (O2)
GENERATORS_AT_PREREG = ("evaluate", "nat_split", "noninterference", "deadline", "chain_revert", "act_split", "hyp",
                        "expr_open", "coercion_guard", "param_premise", "reach_invariant")
NEW_CLASS = "trace_bound"
REFUTERS_AT_PREREG = ("counter",)
# O9: ids of I65's own that holon/ never names (AGENTS rule 2)
OWN_IDS = re.compile(r"C_o12|L_undo_cancel")
# window-view actions with all guards met from s0 (gen/M2/extracted/m1_view.json: active [2, 3], chals [4], OWNER 1,
# DEP 1, genesis csr 100 at t = 10); fields in the facts' input order
C1 = "M.A_commitBatch{2n, 1n, 0n, 1n, 1n, 100n, 101n, [7n]}"
C2 = "M.A_commitBatch{2n, 1n, 1n, 1n, 2n, 101n, 102n, [8n]}"
CH1, CH2 = "M.A_challengeState{4n, 1n, 1n}", "M.A_challengeState{4n, 2n, 1n}"
PAUSE, UNPAUSE = "M.A_setPause{1n, True{}}", "M.A_setPause{1n, False{}}"
# O1: the ghost (challengeState, W) on traces from s0, W = 10: (trace, value)
GHOST_CASES = (
    ([], 0),                                        # nothing run
    ([CH1], 0),                                     # reverts: batch 1 is not committed (1 > LCI 0)
    ([C1, C2, CH1], 10),                            # one successful challenge
    ([C1, C2, CH1, CH2], 10),                       # the second reverts: a challenge is open
    ([C1, C2, CH1, PAUSE, UNPAUSE, CH2], 20),       # pausing cancels the first; the second succeeds
)
_RUNS: dict = {}


def instrument():
    import tests_m3._i65 as I
    return I


def contract(name="C_o12") -> dict:
    return load_json(FX / f"{name}.json")


def ghost_terms(x) -> list:
    """The distinct ghost terms (O1) under x, as sorted canonical JSON."""
    out = set()

    def walk(v):
        if isinstance(v, dict):
            if "ghost" in v:
                out.add(json.dumps(v, sort_keys=True))
            for w in v.values():
                walk(w)
        elif isinstance(v, list):
            for w in v:
                walk(w)
    walk(x)
    return sorted(out)


def untimed(x):
    """A record without its wall-clock fields (every key named "seconds")."""
    if isinstance(x, dict):
        return {k: untimed(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [untimed(v) for v in x]
    return x


def write_json(p: Path, doc) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def holon_ok(args, repo, what):
    p = run_holon(args, cwd=repo, timeout=7200)
    if p.returncode != 0:
        raise AssertionError(f"holon {' '.join(args)} ({what}) failed: {(p.stdout + p.stderr)[-3000:]}")
    return p


def git(*args, cwd=ROOT) -> str:
    p = subprocess.run(["git", "-C", str(cwd), "-c", "core.quotepath=false", *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I65 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and "I65" in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I65")


def own_commits() -> list:
    """I65's own commits (O9; I64-R2's scope): the non-merge commits of `git log --first-parent <prereg>..<end>`, end
    the first commit that adds docs/iterations/I65.md (HEAD while none does), oldest first, each with the (status,
    path) pairs it changes against its parent (renames counted at both ends)."""
    added = git("log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", "docs/iterations/I65.md").split()
    end = added[0] if added else "HEAD"
    commits, cur = [], None
    for ln in git("log", "--first-parent", "--no-merges", "--no-renames", "--reverse", "--format=@%H", "--name-status",
                  f"{prereg_commit()}..{end}").splitlines():
        if ln.startswith("@"):
            cur = (ln[1:], [])
            commits.append(cur)
        elif ln.strip() and cur is not None:
            st, path = ln.split("\t", 1)
            cur[1].append((st[0], path.strip()))
    return commits


def show(commit: str, rel: str):
    """The JSON of a repository file at a commit, or None when it does not exist there."""
    try:
        return json.loads(git("show", f"{commit}:{rel}"))
    except AssertionError:
        return None


def at_prereg(rel: str):
    """The JSON of a repository file at the I65 prereg commit, or None when it did not exist there."""
    return show(prereg_commit(), rel)


def register(repo: Path, c: dict) -> None:
    """Add (or replace) one contract in a copy's laws/CONTRACTS/ and its registry entry (K2)."""
    I = instrument()
    d = repo / "laws" / "CONTRACTS"
    write_json(d / f"{c['id']}.json", c)
    rp = d / "REGISTRY.json"
    reg = load_json(rp) if rp.is_file() else {"registry_version": "holon-contracts-registry/0.1", "contracts": {}}
    reg["contracts"][c["id"]] = {"milestone": c["milestone"], "kind": c["kind"], "sha256": I.content_sha256(c)}
    reg["contracts"] = dict(sorted(reg["contracts"].items()))
    write_json(rp, reg)


def redecide(repo: Path, lids) -> None:
    """In a copy: holon derive --milestone M2 (the contract laws and the registry, O4), then holon run --milestone M2
    --laws <lids>, whose last step applies the contracts (K5)."""
    holon_ok(["derive", "--milestone", M], repo, "derive")
    holon_ok(["run", "--milestone", M, "--laws", ",".join(lids)], repo, "run")


def edit_view(repo: Path, fn) -> None:
    """Change the copy's window view (gen/M2/extracted/m1_view.json) with fn(document), in its own formatting."""
    p = repo / VIEW_FACTS
    old = p.read_text(encoding="utf-8")
    doc = json.loads(old)
    fn(doc)
    ea = json.dumps(json.loads(old), indent=2, sort_keys=True, ensure_ascii=True) + "\n" == old
    p.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=ea) + "\n", encoding="utf-8")


def gate(repo, m, checks="G10"):
    """holon gate --milestone m --checks <checks>, its report written outside the tree under check."""
    out = Path(tempfile.mkdtemp(prefix="i65-gate-")) / f"gate_{m}.json"
    p = run_holon(["gate", "--milestone", m, "--checks", checks, "--report", str(out)], cwd=repo, timeout=7200)
    rep = load_json(out) if out.is_file() else {}
    shutil.rmtree(out.parent, ignore_errors=True)
    return p, rep


def line(rep, check="G10") -> dict:
    c = (rep.get("checks") or {}).get(check)
    return {"status": "PASS" if c["passed"] else "FAIL", "detail": c.get("detail", "")} if c else {}


def g10_both(test, repo, want: str) -> tuple:
    """G10 on M2 from the gate and from the instrument, both required to be want ("PASS" or "FAIL")."""
    _, rep = gate(repo, M)
    got = line(rep)
    ok, reasons = instrument().g10(M, repo)
    test.assertEqual(got.get("status"), want, rep)
    test.assertEqual("PASS" if ok else "FAIL", want, reasons)
    return got, reasons


def rechecked(test, repo, lid: str, rec: dict, allowed: tuple) -> None:
    """AGENTS rule 6, independently of the record: its PROOF.bend (a proof when PROVED, a counter-law when REFUTED) is
    accepted by Bend run here, imports exactly its LAWS.bend as Laws and states no law of its own; the LAWS.bend states
    exactly the law the status needs (l_<id> when PROVED, cl_l_<id> when REFUTED, lower-cased); and the attempt that
    decided it came from a generator in allowed."""
    status = rec.get("status")
    test.assertIn(status, ("PROVED", "REFUTED"), lid)
    art = rec.get("artifacts") or {}
    proof, laws = (Path(art.get(k) or "") for k in ("proof", "laws"))
    proof, laws = (p if p.is_absolute() else repo / p for p in (proof, laws))
    test.assertTrue(proof.is_file() and laws.is_file(), (lid, art))
    code, out = run_bend([proof.name], cwd=proof.parent, timeout=3600)
    test.assertEqual(code, 0, (lid, out[-1500:]))
    test.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), (lid, out[-1500:]))
    name = ("cl_" if status == "REFUTED" else "") + lid.lower()
    test.assertEqual(re.findall(r"^law\s+([A-Za-z0-9_.]+)\s*:", laws.read_text(), re.M), [name], lid)
    text = proof.read_text()
    want = Path(os.path.relpath(laws.resolve(), proof.resolve().parent)).as_posix()
    test.assertEqual(re.findall(r"^import\s+(\S+)\s+as\s+Laws\s*(?:#.*)?$", text, re.M), [want], lid)
    code_only = "\n".join(x.split("#", 1)[0] for x in text.splitlines())
    test.assertEqual(re.findall(r"(?<![\w.])law\s+[A-Za-z0-9_.]+\s*:", code_only), [], lid)
    kind = "proof" if status == "PROVED" else "counter-law"
    ok = [a for a in rec.get("attempts") or [] if a.get("kind") == kind and "error" not in a and a.get("exit_code") == 0]
    test.assertTrue(ok, (lid, rec.get("attempts")))
    test.assertIn(ok[-1].get("generator"), allowed, lid)


def without_laws(text: str) -> str:
    """A LAWS.bend without its law blocks (a line `law <name>:` and the indented or blank lines under it): its header,
    imports and statement helpers, in their order and bytes, which Bend checks with no open goal."""
    out, skip = [], False
    for ln in text.splitlines():
        if re.match(r"law\s", ln):
            skip = True
            continue
        if skip and (not ln.strip() or ln[0].isspace()):
            continue
        skip = False
        out.append(ln)
    return "\n".join(out).rstrip("\n") + "\n"


def copied() -> Path:
    """A throwaway copy of the repository (removed by tearDownModule)."""
    repo = copy_repo()
    _RUNS.setdefault("copies", []).append(repo.parent)
    return repo


def tearDownModule():
    for d in _RUNS.pop("copies", []):
        shutil.rmtree(d, ignore_errors=True)


def view_record(repo: Path = ROOT) -> dict:
    return load_json(repo / VIEW_REC)


def unmarked(rec: dict) -> dict:
    out = {k: v for k, v in rec.items() if k != "intended"}
    out["filter_bin"] = rec["intended"]["replaces"]
    return out


def is_record(rel: str) -> bool:
    """A result record: results/<M>/L*.json or results/<M>/extracted_m1/L*.json."""
    return re.fullmatch(r"results/M\d+/(?:extracted_m1/)?L[^/]*\.json", rel) is not None


class TestInstrument(unittest.TestCase):
    """The instruments are what the key says."""

    def test_the_key_pins_the_instruments(self):
        th = predictions("I65")["thresholds"]
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i65.py"), th["instrument_sha256"])
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i64.py"), th["i64_instrument_sha256"])
        doc = __doc__
        self.assertEqual(__import__("hashlib").sha256(doc.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        got = {str(p.relative_to(ROOT)): file_sha256(p) for p in sorted(FX.glob("*.json"))}
        self.assertEqual(got, th["fixture_sha256"])

    def test_the_fixture_states_the_planned_bound(self):
        """The fixture contracts are the ones the key describes, each over the view and scoping L_undo_cancel: C_o12's
        L_weak over (p: Trace, k: Nat) a conjunction of three expr props with one ghost term (challengeState, W) over
        (p, s0); C_o12_tight the same binders, one prop with the ghost (challengeState, 1); C_o12_open, over p alone,
        C_o12's second and third props."""
        c, t, o = contract(), contract("C_o12_tight"), contract("C_o12_open")
        for x in (c, t, o):
            self.assertEqual((x["milestone"], x["facts"], x["scope"], x["rule"]),
                             (M, VIEW_FACTS, {"laws": [SCOPE]}, "UNDO"))
        for x in (c, t):
            self.assertEqual([(b["q"], b["name"], b["type"]) for b in x["l_weak"]["binders"]],
                             [("forall", "p", "Trace"), ("forall", "k", "Nat")])
        self.assertEqual([(b["q"], b["name"], b["type"]) for b in o["l_weak"]["binders"]], [("forall", "p", "Trace")])
        g = {"ghost": "challengeState", "add": "W", "over": {"var": "p"}, "from": {"s0": {}}}
        self.assertEqual(len(c["l_weak"]["claim"]["all"]), 3)
        self.assertEqual(ghost_terms(c["l_weak"]), [json.dumps(g, sort_keys=True)])
        self.assertIn("eq", t["l_weak"]["claim"])
        self.assertEqual(ghost_terms(t["l_weak"]), [json.dumps(dict(g, add=1), sort_keys=True)])
        self.assertEqual(o["l_weak"]["claim"], {"all": c["l_weak"]["claim"]["all"][1:]})
        self.assertEqual(ghost_terms(o["l_weak"]), [json.dumps(g, sort_keys=True)])


class TestGhost(unittest.TestCase):
    """O1."""

    def test_the_schema_admits_the_ghost_term_and_nothing_looser(self):
        I = instrument()
        for name in ("C_o12", "C_o12_tight", "C_o12_open"):
            with self.subTest(contract=name):
                self.assertEqual(validate(I.derived_law(contract(name), ROOT), LAW_IR), [])
        good = {"ghost": "challengeState", "add": "W", "over": {"var": "p"}, "from": {"s0": {}}}
        bad = [{k: v for k, v in good.items() if k != "add"},
               dict(good, when="ok"),
               dict(good, ghost=7),
               {k: v for k, v in good.items() if k != "over"},
               {"ghost": {"act": "challengeState", "add": "W"}, "trace": {"var": "p"}, "from": {"s0": {}}}]
        lw = lambda t: {"binders": [{"q": "forall", "name": "p", "type": "Trace"}],   # noqa: E731
                        "claim": {"eq": [t, {"nat": 0}]}}
        self.assertEqual(validate(I.derived_law(dict(contract(), l_weak=lw(good)), ROOT), LAW_IR), [])
        for i, b in enumerate(bad):
            with self.subTest(bad=i):
                self.assertNotEqual(validate(I.derived_law(dict(contract(), l_weak=lw(b)), ROOT), LAW_IR), [])
        adopt = ROOT / "docs" / "adoption" / "Q4" / "schemas" / "law_ir_0_3.schema.json"
        self.assertEqual(adopt.read_bytes(), LAW_IR.read_bytes())

    def test_the_ghost_counts_successful_challenges(self):
        """The committed L_contract_C_o12's LAWS.bend states one law and defines exactly one ghost pair, gh1_<h> and
        gh_<h>, and Bend computes gh_<h> on the view model from s0 as GHOST_CASES say (a reverted challenge counts 0;
        one cancelled by a pause still counts W). The check file is that LAWS.bend without its law (its imports and
        statement helpers, byte for byte) plus one equation per case, so it has no open goal; and each value plus one is
        refused on the value (Bend's expected and observed lines, and no TODO), so the check is not vacuous."""
        rec = load_json(ROOT / "results" / M / f"{LID}.json")
        text = (ROOT / rec["artifacts"]["laws"]).read_text()
        names = sorted(set(re.findall(r"^def (gh_[0-9a-f]{12})\(", text, re.M)))
        self.assertEqual(len(names), 1, names)
        gh = names[0]
        self.assertEqual(re.findall(r"^def (gh1_[0-9a-f]{12})\(", text, re.M), ["gh1_" + gh[3:]])
        self.assertEqual(len(re.findall(r"^law\s", text, re.M)), 1)
        self.assertEqual(len(re.findall(r"^import\s+(\S+)\s+as\s+M\s*$", text, re.M)), 1)
        helpers = without_laws(text)
        self.assertNotRegex(helpers, r"(?m)^law\s")
        self.assertIn(f"def {gh}(", helpers)
        d = (copied() / rec["artifacts"]["laws"]).parent

        def case(i: int, tr: list, v: int) -> str:
            lst = "[" + ", ".join(tr) + "]" if tr else "Nil{}"
            return f"def ghost_case_{i}() -> {{{gh}({lst}, M.s0()) == {v}n : Nat}}:\n  {{==}}\n"
        f = d / "GHOST_CHECK.bend"
        f.write_text(helpers + "\n" + "\n".join(case(i, tr, v) for i, (tr, v) in enumerate(GHOST_CASES)))
        code, msg = run_bend([f.name], cwd=d, timeout=3600)
        self.assertEqual(code, 0, msg[-2000:])
        self.assertTrue(msg.strip().startswith("ALL PROOFS CHECK"), msg[-2000:])
        for i, (tr, v) in enumerate(GHOST_CASES):   # a wrong value is refused on the value
            with self.subTest(case=i):
                g = d / f"GHOST_WRONG_{i}.bend"
                g.write_text(helpers + "\n" + case(i, tr, v + 1))
                code, msg = run_bend([g.name], cwd=d, timeout=3600)
                self.assertNotEqual(code, 0, msg[-1000:])
                self.assertNotIn("TODO", msg, msg[-1000:])
                self.assertRegex(msg, rf"-\s*expected\s*:\s*{v}n\b", msg[-1000:])
                self.assertRegex(msg, rf"-\s*observed\s*:\s*{v + 1}n\b", msg[-1000:])


class TestContract(unittest.TestCase):
    """O3, O4."""

    def test_the_contract_is_committed_registered_and_alone(self):
        I = instrument()
        c = load_json(ROOT / "laws" / "CONTRACTS" / "C_o12.json")
        self.assertEqual(c, contract())
        self.assertEqual(I.problems(c, ROOT, "C_o12"), [])
        reg = load_json(ROOT / "laws" / "CONTRACTS" / "REGISTRY.json")
        self.assertEqual(reg["contracts"].get("C_o12"), {"milestone": M, "kind": "intended",
                                                          "sha256": I.content_sha256(c)})
        named = sorted(x.get("id") for _, x in I.contract_docs(ROOT)
                       if isinstance(x, dict) and x.get("milestone") in ("M0", "M1", "M2", "M3"))
        self.assertEqual(named, ["C_o12"])

    def test_the_derived_law_is_a_law_of_m2(self):
        """O4: the law is K3's derivation; laws/M2/REGISTRY.json lists its statement hash (its record's) and the view in
        facts_files, its primary facts unchanged; DERIVATION.json does not list it; spec/bindings/M2.json binds it; its
        record's ledger_match is exact and its one lean4 entry not_run with reason unsupported_form, gen/M2/lean holding
        the model file of its Bend model and no law file for it; holon contracts derive --check passes; and holon
        derive, in a copy, writes laws/M2 byte for byte."""
        I = instrument()
        law = load_json(ROOT / "laws" / M / f"{LID}.json")
        self.assertEqual(law, I.derived_law(contract(), ROOT))
        rec = load_json(ROOT / "results" / M / f"{LID}.json")
        reg = load_json(ROOT / "laws" / M / "REGISTRY.json")
        self.assertEqual(reg["statements"].get(LID), rec["statement_hash"])
        self.assertEqual(reg["facts_files"].get(VIEW_FACTS), file_sha256(ROOT / VIEW_FACTS))
        self.assertEqual((reg["facts"], reg["facts_sha256"]), (PRIMARY_FACTS, file_sha256(ROOT / PRIMARY_FACTS)))
        self.assertNotIn(LID, [e["law_id"] for e in load_json(ROOT / "laws" / M / "DERIVATION.json")["laws"]])
        self.assertIn(LID, load_json(ROOT / "spec" / "bindings" / f"{M}.json")["laws"])
        self.assertEqual(rec.get("ledger_match"), "exact")
        lean = [k for k in rec.get("kernels") or [] if k.get("name") == "lean4"]
        self.assertEqual([(k.get("result"), k.get("reason")) for k in lean], [("not_run", "unsupported_form")])
        model = Path(rec["artifacts"]["model"]).stem
        self.assertTrue((ROOT / "gen" / M / "lean" / "models" / f"{model}.lean").is_file(), model)
        self.assertFalse((ROOT / "gen" / M / "lean" / f"{LID}.lean").exists())
        p = run_holon(["contracts", "derive", "--milestone", M, "--check"], cwd=ROOT, timeout=3600)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        repo = copied()
        before = {q.name: q.read_bytes() for q in sorted((repo / "laws" / M).glob("*.json"))}
        holon_ok(["derive", "--milestone", M], repo, "derive")
        after = {q.name: q.read_bytes() for q in sorted((repo / "laws" / M).glob("*.json"))}
        self.assertEqual(sorted(after), sorted(before))
        for name in sorted(before):
            with self.subTest(file=name):
                self.assertEqual(after[name], before[name])


class TestPredictions(unittest.TestCase):

    def test_p1_the_l_weak_is_proved_by_trace_bound(self):
        """I65-P1: L_contract_C_o12 is PROVED over the view by trace_bound, re-checked by Bend here; G2, G3, G5 and G9
        pass on M2 (GEVID is R1's, O4)."""
        item("I65", "I65-P1")
        rec = load_json(ROOT / "results" / M / f"{LID}.json")
        self.assertEqual(rec.get("status"), "PROVED", rec.get("attempts"))
        self.assertEqual(rec.get("facts_sha256"), file_sha256(ROOT / VIEW_FACTS))
        rechecked(self, ROOT, LID, rec, (NEW_CLASS,))
        _, rep = gate(ROOT, M, "G2,G3,G5,G9")
        for c in ("G2", "G3", "G5", "G9"):
            with self.subTest(check=c):
                self.assertEqual(line(rep, c).get("status"), "PASS", line(rep, c))

    def test_p2_the_mark_lands_on_the_view_record_alone(self):
        """I65-P2: exactly one record of M0-M3 is marked, results/M2/extracted_m1/L_undo_cancel.json, by C_o12,
        replacing "finding"; unmarked it is its prereg self but for generator_sha256 and wall-clock fields;
        contracts.json is the instrument's; results/M1/L_undo_cancel.json carries no mark; G10 on M2 passes from the
        gate and the instrument, naming the mark."""
        item("I65", "I65-P2")
        I = instrument()
        want = {f"extracted_m1/{SCOPE}": {"filter_bin": "intended_bounded", "contract": "C_o12", "l_weak": LID}}
        self.assertEqual(I.marks(M, ROOT), want)
        for m in ("M0", "M1", "M3"):
            with self.subTest(milestone=m):
                self.assertEqual(I.marks(m, ROOT), {})
        rec = view_record()
        self.assertEqual(rec.get("intended"), {"contract": "C_o12", "l_weak": LID, "replaces": "finding"})
        old = at_prereg(VIEW_REC.as_posix())
        self.assertIsNotNone(old)
        strip = lambda r: {k: v for k, v in untimed(r).items() if k != "generator_sha256"}   # noqa: E731
        self.assertEqual(strip(unmarked(rec)), strip(old))
        self.assertEqual(load_json(ROOT / "results" / M / "contracts.json"), I.contracts_doc(M, ROOT))
        got, _ = g10_both(self, ROOT, "PASS")
        self.assertEqual(got.get("detail"), f"C_o12 proved, marks {SCOPE}")

    def test_p3_a_false_bound_is_refuted_and_marks_nothing(self):
        """I65-P3: with C_o12_tight registered beside C_o12, its L_weak is REFUTED by the existing refuter (the
        generator counter, whose search evaluates ghost terms by O1; re-checked by Bend), it marks nothing, the view
        record keeps C_o12's mark, and G10 fails naming C_o12_tight, from the gate and the instrument."""
        item("I65", "I65-P3")
        I = instrument()
        repo = copied()
        register(repo, contract("C_o12_tight"))
        redecide(repo, ["L_contract_C_o12_tight"])
        rec = load_json(repo / "results" / M / "L_contract_C_o12_tight.json")
        self.assertEqual(rec.get("status"), "REFUTED", rec.get("attempts"))
        rechecked(self, repo, "L_contract_C_o12_tight", rec, REFUTERS_AT_PREREG)
        self.assertEqual(I.marks(M, repo), {f"extracted_m1/{SCOPE}": {"filter_bin": "intended_bounded",
                                                                        "contract": "C_o12", "l_weak": LID}})
        doc = load_json(repo / "results" / M / "contracts.json")
        self.assertEqual(doc, I.contracts_doc(M, repo))
        row = next(r for r in doc["contracts"] if r["id"] == "C_o12_tight")
        self.assertEqual((row["state"], row["marked"]), ("not proved: REFUTED", []))
        got, reasons = g10_both(self, repo, "FAIL")
        self.assertIn("C_o12_tight: not proved: REFUTED", got.get("detail"))
        self.assertIn("C_o12_tight: not proved: REFUTED", reasons)

    def test_p4_a_view_change_needs_a_new_proof(self):
        """I65-P4: a change to the view makes C_o12 stale (G10 fails). (a) A change of a doc string only: after derive
        and run, L_contract_C_o12 is PROVED again, but the view record, decided over the old view, is not licensed: no
        record is marked and G10 passes. (b) challengeState extending by W + 1: L_contract_C_o12 is REFUTED (re-checked
        by Bend), nothing is marked and G10 fails. The gate and the instrument agree at every step."""
        item("I65", "I65-P4")
        I = instrument()
        for case, fn in (("doc", lambda d: d["initial"].__setitem__("doc", d["initial"]["doc"] + " (I65-P4)")),
                         ("bump", _bump_w_plus_one)):
            with self.subTest(case=case):
                repo = copied()
                edit_view(repo, fn)
                _, reasons = g10_both(self, repo, "FAIL")
                self.assertTrue(any(r.startswith("C_o12: stale") for r in reasons), reasons)
                redecide(repo, [LID])
                rec = load_json(repo / "results" / M / f"{LID}.json")
                self.assertEqual(rec.get("facts_sha256"), file_sha256(repo / VIEW_FACTS))
                self.assertEqual(I.marks(M, repo), {})
                self.assertNotIn("intended", view_record(repo))
                self.assertEqual(view_record(repo).get("filter_bin"), "finding")
                if case == "doc":
                    self.assertEqual(rec.get("status"), "PROVED", rec.get("attempts"))
                    rechecked(self, repo, LID, rec, (NEW_CLASS,))
                    got, _ = g10_both(self, repo, "PASS")
                    self.assertEqual(got.get("detail"), "C_o12 proved")
                else:
                    self.assertEqual(rec.get("status"), "REFUTED", rec.get("attempts"))
                    rechecked(self, repo, LID, rec, REFUTERS_AT_PREREG)
                    got, reasons = g10_both(self, repo, "FAIL")
                    self.assertIn("C_o12: not proved: REFUTED", reasons)


def _bump_w_plus_one(doc: dict) -> None:
    a = next(x for x in doc["actions"] if x["name"] == "challengeState")
    eff = a["effects"]["win"]
    assert eff[:2] == ["call", "bump_f"] and eff[-1] == "W", eff
    a["effects"]["win"] = eff[:-1] + [["+", "W", 1]]


class TestMachinery(unittest.TestCase):
    """O2, O5-O7 and O9 (construction checks; each needs the built tree, its derived law, record or mark, so each fails
    before the build)."""

    def test_the_class_proves_a_second_claim(self):
        """O2, O3: C_o12_open (C_o12's (b) and (c) over p alone), registered in a copy, is PROVED by trace_bound
        (re-checked by Bend): the class is not fitted to one claim's shape. Not a prediction."""
        repo = copied()
        register(repo, contract("C_o12_open"))
        redecide(repo, ["L_contract_C_o12_open"])
        rec = load_json(repo / "results" / M / "L_contract_C_o12_open.json")
        self.assertEqual(rec.get("status"), "PROVED", rec.get("attempts"))
        rechecked(self, repo, "L_contract_C_o12_open", rec, (NEW_CLASS,))

    def test_holon_names_no_i65_id(self):
        """O9 (AGENTS rule 2): no file under holon/ names C_o12, C_o12_tight, C_o12_open or L_undo_cancel."""
        self.assertIn("intended", view_record())   # the built tree
        hits = []
        for p in sorted((ROOT / "holon").rglob("*")):
            if p.is_file() and p.suffix in (".py", ".mjs", ".js", ".json", ".bend", ".lean"):
                for i, ln in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if OWN_IDS.search(ln):
                        hits.append(f"{p.relative_to(ROOT)}:{i}")
        self.assertEqual(hits, [])

    def test_an_ambiguous_scope_law_is_refused(self):
        repo = copied()
        shutil.copy(repo / VIEW_REC, repo / "results" / M / f"{SCOPE}.json")
        p = run_holon(["contracts", "apply", "--milestone", M], cwd=repo, timeout=3600)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(view_record(repo), view_record())   # nothing written
        got, reasons = g10_both(self, repo, "FAIL")
        self.assertTrue(any(r.startswith(f"{SCOPE}: a scope law with a record in more than one") for r in reasons),
                        reasons)
        self.assertIn(f"{SCOPE}: a scope law with a record in more than one", got.get("detail"))

    def test_a_record_over_other_facts_is_not_licensed(self):
        repo = copied()
        r = view_record(repo)
        r["facts_sha256"] = "0" * 64
        write_json(repo / VIEW_REC, r)
        g10_both(self, repo, "FAIL")   # the mark is no longer licensed
        holon_ok(["contracts", "apply", "--milestone", M], repo, "apply")
        self.assertNotIn("intended", view_record(repo))
        self.assertEqual(view_record(repo).get("filter_bin"), "finding")
        got, _ = g10_both(self, repo, "PASS")
        self.assertEqual(got.get("detail"), "C_o12 proved")

    def test_g10_fails_on_a_tampered_or_missing_view_mark(self):
        for case in ("missing", "other contract", "half"):
            with self.subTest(case=case):
                repo = copied()
                r = view_record(repo)
                if case == "missing":
                    r = unmarked(r)
                elif case == "other contract":
                    r["intended"]["contract"] = "C_other"
                else:
                    r.pop("intended")
                write_json(repo / VIEW_REC, r)
                g10_both(self, repo, "FAIL")

    def test_the_differential_keeps_the_mark(self):
        """O6: in a copy, holon differential --reuse-view rewrites results/M2/extracted_m1 (records without
        concretization) and ends with apply, and holon refute's final filter writes each record's concretization and
        bin back: every view record then has the committed filter_bin, intended and concretization, and G10 passes.
        Only these fields are compared: the differential's other fields follow the generator, and I65 regenerates no
        view record (O6)."""
        self.assertIn("intended", view_record())   # the built tree carries the mark
        repo = copied()
        holon_ok(["differential", "--milestone", M, "--reuse-view"], repo, "differential")
        holon_ok(["refute", "--milestone", "M3", "--only", "filter"], repo, "refute filter")
        d0, d1 = ROOT / VIEW_REC.parent, repo / VIEW_REC.parent
        names = sorted(p.name for p in d0.glob("L*.json"))
        self.assertEqual(sorted(p.name for p in d1.glob("L*.json")), names)
        keep = ("filter_bin", "intended", "concretization")
        for n in names:
            with self.subTest(record=n):
                a, b = load_json(d0 / n), load_json(d1 / n)
                self.assertEqual({k: b.get(k) for k in keep}, {k: a.get(k) for k in keep})
        g10_both(self, repo, "PASS")

    def test_refute_keeps_the_mark(self):
        """O6: holon refute's final filter, with --check on the tree and run in a copy, keeps the mark and the
        record."""
        self.assertIn("intended", view_record())   # the built tree carries the mark
        p = run_holon(["refute", "--milestone", "M3", "--only", "filter", "--check"], cwd=ROOT, timeout=7200)
        self.assertEqual(p.returncode, 0, (p.stdout + p.stderr)[-3000:])
        repo = copied()
        holon_ok(["refute", "--milestone", "M3", "--only", "filter"], repo, "refute filter")
        self.assertEqual(untimed(view_record(repo)), untimed(view_record()))


class TestRegressions(unittest.TestCase):
    """What is already recorded must not change but as O8 allows."""

    def test_r1_g10_on_every_milestone(self):
        """I65-R1 (part): G10 is not applicable on M0 and M1, and passes on M3 with no contract (on M2, P2 checks it).
        The rest of R1 (the full gates of M0-M2, the M3 gate's failing items, the frozen suite, freeze-check and both
        prereg audits) is checked by CI and the audits on the build head, named in the report."""
        item("I65", "I65-R1")
        for m in ("M0", "M1"):
            with self.subTest(milestone=m):
                _, rep = gate(ROOT, m)
                self.assertIn("G10", rep.get("not_applicable", {}), rep)
        _, rep = gate(ROOT, "M3")
        self.assertEqual(line(rep), {"status": "PASS", "detail": "no intent contract on M3 (laws/CONTRACTS/ holds none "
                                                                 "for it)"})

    def test_r2_records_and_laws_change_only_as_allowed(self):
        """I65-R2: each of I65's own commits (O9), against its parent, deletes no law or record; adds none but
        laws/CONTRACTS/C_o12.json, laws/M2/L_contract_C_o12.json, results/M2/L_contract_C_o12.json and
        results/M2/contracts.json (I65's own files, judged at HEAD by P1 and P2, which later own commits may change);
        changes no other law file but laws/M2/REGISTRY.json (only by that law's statement hash and the view's facts file)
        and laws/CONTRACTS/REGISTRY.json; and changes any other record only keeping its status, in generator_sha256,
        wall-clock fields, prover from absent to "generator", and, on results/M2/extracted_m1/L_undo_cancel.json alone,
        P2's mark. At least one own commit adds the derived law."""
        item("I65", "I65-R2")
        commits = own_commits()
        added_ok = {"laws/CONTRACTS/C_o12.json", f"laws/M2/{LID}.json", f"results/M2/{LID}.json",
                    "results/M2/contracts.json"}
        self.assertTrue([c for c, ch in commits if ("A", f"laws/M2/{LID}.json") in ch], "no own commit adds the law")
        for c, ch in commits:
            for st, f in ch:
                if not f.startswith(("laws/", "results/")):
                    continue
                if not (st in "AD" or f.startswith("laws/") or is_record(f)):
                    continue   # a modified summary or document (metrics.json, historical/, contracts.json)
                with self.subTest(commit=c[:12], path=f):
                    self.assertNotEqual(st, "D")
                    if st == "A" or f in added_ok:   # I65's own files: P1 and P2 judge them at HEAD
                        self.assertIn(f, added_ok)
                        continue
                    new, old = show(c, f), show(f"{c}^", f)
                    if f.startswith("laws/"):
                        self.assertIn(f, ("laws/M2/REGISTRY.json", "laws/CONTRACTS/REGISTRY.json"))
                        if f == "laws/M2/REGISTRY.json":
                            for k, extra in (("statements", LID), ("facts_files", VIEW_FACTS)):
                                self.assertEqual({x: v for x, v in new[k].items() if x != extra},
                                                 {x: v for x, v in old[k].items() if x != extra})
                            rest = lambda r: {k: v for k, v in r.items()   # noqa: E731
                                              if k not in ("statements", "facts_files")}
                            self.assertEqual(rest(new), rest(old))
                        continue
                    if f == VIEW_REC.as_posix() and "intended" in new and "intended" not in old:
                        self.assertEqual(new.get("filter_bin"), "intended_bounded")
                        new = unmarked(new)
                    self.assertEqual(new.get("status"), old.get("status"))
                    keys = {k for k in set(new) | set(old) if untimed(new.get(k)) != untimed(old.get(k))}
                    if "prover" in keys and "prover" not in old and new.get("prover") == "generator":
                        keys.discard("prover")
                    self.assertLessEqual(keys, {"generator_sha256"}, keys)

    def test_r3_no_frozen_root_and_no_m3_generated_file(self):
        """I65-R3: no commit of I65's own (O9) changes a frozen root, a law, record or generated file of M3, an M0
        record or generated file, or a law of M0 or M1; I64's amended R1 holds (no contract but C_o12 names M0-M3)."""
        item("I65", "I65-R3")
        frozen = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "AGENTS.md",
                  "tools/freeze.py", "docs/M0_SPEC.md", "docs/BEND_PRIMER.md", "FROZEN.sha256")
        other = ("laws/M1/", "laws/M3/", "results/M0/", "results/M3/", "gen/M0/", "gen/M3/")
        commits = own_commits()
        self.assertTrue(commits, "no commit of I65's own")
        for c, ch in commits:
            with self.subTest(commit=c[:12]):
                self.assertEqual([f for _, f in ch if f.startswith(frozen + other)], [])
        I = instrument()
        named = sorted(x.get("id") for _, x in I.contract_docs(ROOT)
                       if isinstance(x, dict) and x.get("milestone") in ("M0", "M1", "M2", "M3"))
        self.assertEqual(named, ["C_o12"])


if __name__ == "__main__":
    unittest.main()
