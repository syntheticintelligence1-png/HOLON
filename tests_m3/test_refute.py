"""I40: refutation engines, the Appendix D encodings, BMC over the extracted TRANS edges, witness concretization, emitted
per-witness tests and the final finding filter (whitepaper §10.5, App. D, §10.2 "layout facts ... as solver queries",
§10.9, §9.6, Thm 6.15, Cor 6.16, Thm 6.17, §8.6, §10.11; BUILD_PLAN I40; docs/HUMAN_ANSWERS.md Q16 (pinned z3 under
~/.holon/tools) and Q19 (extracted facts are the input of every M3 question)). This docstring is the contract. Instruments
fixed at the prereg: spec/M3/lib/refute.json (pins, encodings, H, environment, principals, answers, targets, the I21
split, the fixture, and the computed classes, codec_laws, unknowns, records and unfalsified_reaches), tests_m3/_i40.py
(those computations, the final filter rule written out a second time, the toy and rollup replay instruments) and
tests_m3/fixtures/refute/ (src/ToyLock.sol in two variants extracted by holon-frontend-solidity/0.3 at the prereg, their
sidecars, a byte copy of the I20 step harness base and the toy's concrete harness). Do not edit them; a wrong instrument
is a Question and an amendment line in spec/M3/amendments.jsonl.

Principle (AGENTS rules 4-6, BUILD_PLAN §2.4, Thm 6.17, App. D last line)
  Solvers, fuzzers and BMC only PROPOSE. A candidate changes a status only through a counter-law that Bend accepts on the
  law's own compiled model (BendTT re-checks it), and becomes a finding only through a replay on the real code. A search
  that ends without either is UNKNOWN with its engine, bound, budget and reason; an exhausted budget (z3's rlimit) is
  UNKNOWN, never a pass and never "no path".

Scope and inputs
  - The rollup questions run over spec/M2/facts/morph_rollup.extracted.json (A19; adopted by I20 in
    spec/M2/lib/derive_extracted.json; G1 re-extracts it), never over spec/M1/facts (Q19). The codec questions run over
    each codec law's own model document (facts/morph_header.json for M0, the linked codec model
    gen/M3/codec/header_length.json for the M3 PAR laws, whose layouts come from spec/M2/facts/morph_header.extracted.json
    and the extracted Go documents).
  - Existing laws are decided on their own models: the re-find (Q1) and the UNKNOWNs of M2 (Q3) read the document each
    law's model was compiled from, exactly as that law's pipeline does, and derive no law. No I40 command derives a law.
  - I40 binds to I30's PREREGISTERED contract (prereg 499c70b; tests_m3/test_sort_types.py), never to its outputs: the
    typed model gen/M3/sorts/models/<model>.bend with Reach from the binding's deployment, its witness format
    ({"steps": [{"action", "args", "calldata", "env": {"caller", "msg.value", "block.timestamp", "blobhash", "calls"}}],
    "hashes": {"keccak256": [[key, word], ..], "sha256": ..}}), its counter-law generator, its replay through the I20 step
    harness, and its test milestones T<n> (n >= 30) run from their sidecars. BMC's initial state R0 is that Reach's
    initial state: the binding's deployment (replay/M2/fragments.json, refute.json "deployment").

Engines
  E-SMT  holon/smt/encode.py and holon/smt/run.py. Only the pinned z3 runs (refute.json "solver": version 4.16.0, the
         binary's and the library's sha256; random_seed 0 for smt and sat; one thread; z3's deterministic rlimit per
         query, never a wall-clock timeout). config/holon.json gains the same pin under "z3". A missing or different solver
         makes every engine result not_run with the reason (exit 2, nothing written). The encodings are refute.json
         "encodings" E1-E7 and NZ, all ground. Every query is a file under gen/M3/refute/smt/: SMT-LIB 2 text whose first
         line is "; holon-smt " + canonical JSON {"logic": "QF_AUFBV", "random_seed": 0, "rlimit": n, "terms": {fn: count of
         that function's terms}, "instances": {"cf": c, "nz": z, "vh_top": v, "dense": d, "time": t, "cost": k, "hypz": h}}
         (keys only for what the query uses), with cf = sum over the hash functions of n(n-1)/2 and nz = the number of
         keccak256 and sha256 terms. No emitted file holds "forall" or "exists". Declarations sorted; no timestamp.
         BMC's queries are the files under gen/M3/refute/smt/bmc/; their header also holds "steps": k (the unrolling
         depth) and their instances "time": k (E5: one non-decreasing constraint per step, the first against the
         deployment's clock) and "cost": the number of (step, action) pairs of the query whose action has a non-empty
         cost.terms in the document (E7; 0 is written, never omitted).
         holon.smt.encode.instances(terms: {fn: n}, hypz_K: int) -> {"cf", "nz", "vh_top", "dense", "hypz", ..} gives the
         instance counts a query over those terms gets (fn among keccak256, sha256, VH, blobhash (the vector's slots) and
         Enc; dense = slots - 1; hypz = Enc terms x (hypz_K + 1)), the same counts the header states.
  E-LAY  Layout facts as solver queries (§10.2): gen/M3/refute/smt/layouts/<function>.smt2 for each function of
         spec/M2/facts/morph_header.extracted.json (enc_sol, load_sol): enc_sol as the byte array a version's layout
         writes from the field values, load_sol as its definedness and field reads. The codec queries (Q2) of the M3 PAR
         laws use them.
  E-FUZZ holon/fuzz.py: refute.json "fuzz" (seed 20261014, 4096 candidates per law, boundary values first).
  E-BMC  holon/bmc.py: refute.json "bmc": H = 8 steps from R0, iterative deepening (one query per k = 1..8; the first sat
         k is the shortest path), each query sliced to the target's cone of influence over the edges' index-sensitive
         read and write sets; environment moves (time E5, blob hashes E3, msg.value, the caller) per step; callers only
         the principal table (owner 0x7fa9..1496, submitters 0x1002 and 0x1003, challenger 0x1004, anyone 0x1005; never
         the proxy admin); external-call answers constrained to the deployment's ("answers"); no enqueue move (the
         deployment's queue stays empty). A path is a witness in I30's format: every step a public call with calldata and
         environment, hash tables holding the real keccak256 / sha256 of every key (among them every header the path
         loads), block.timestamp never 0 and non-decreasing.
  Every candidate of every engine is listed with "accepted" (its counter-law, a Bend file on the law's compiled model,
  checked by Bend and by BendTT) or not, with the checker's output: a candidate is never dropped silently. A BMC path
  (a reach, a target, an I21 question) has no counter-law; it is replayed instead, and a path whose replay shows an
  external call answering otherwise than the answer table (calls_agree false) is discarded as env_mismatch: the
  question's verdict is then unknown with reason "env_mismatch: <call>", never path, never no_path.

Questions (outputs under results/M3/refute/; formats under Outputs)
  Q1 Re-find (refind.json). For each class of refute.json "classes" (26: one per REFUTED record at the prereg, one per
     checked entry point of a per-entry record) one SMT query on the class's TEMPLATE over the law's own model: the law's
     negation with the class's witness keys and skeleton fixed (the action of every step; every argument, environment
     value and hash free) for a trace class; with the class's differing byte positions required to differ for a codec
     class; with the version byte and the two definedness verdicts fixed for a domain class. A class is re-found when the
     query is sat within the rlimit, the decoded candidate's counter-law gen/M3/refute/refind/<id>/PROOF.bend (importing
     the record's artifacts.model as M and its artifacts.laws as Laws, defining Laws.<artifacts.law_name>, as the
     record's own counter-law does) is accepted by Bend and BendTT, and the candidate's signature is the class's (trace:
     the same skeleton; codec: its differing positions include the class's; domain: the same version byte and verdicts).
  Q2 Codec agreement (codec.json). For each of the 88 codec laws (refute.json "codec_laws": M0's 8 and the 80 M3 PAR
     laws) one query on the law's negation over its model (byte strings up to byte_length_max): sat with an accepted
     candidate, unsat, or unknown.
  Q3 UNKNOWNs (unknowns.json). For each record of refute.json "unknowns" (8): every engine that applies, with its bound,
     budget, result, candidates and reason: the hand-model laws of M2 (I15's two site laws) by SMT unrolled to
     hand_trace_bound steps of their instrumented model from its initial state, and fuzz; the width laws of M2 (I20's two,
     over the extracted document, whose M2 model has no Reach) by BMC over the extracted TRANS edges from R0 with the
     store's value >= 2^64 as the target; the PAR-weak laws of M3 (I24's three) by SMT and fuzz; I20's not-run L_tag_BVH
     view record by no engine (a law reading a hand-written ghost is not run: lead decision A3), recorded with that
     reason. A law an engine refutes gets its counter-law and its record through its own pipeline; one that stays
     UNKNOWN keeps its record unchanged (its I40 attempts live in unknowns.json only).
  Q4 Concretization (concretization.json), rules K1-K4 of tests_m3/_i40.py::concretization_kind (over a record's I4
     replay sides; a view record of results/M2/extracted_m1 takes the I4 sides of the M1 record of its law, which has
     the same witness; the kinds at the prereg are refute.json "records"):
       K1 bmc: a side ran on an internal harness or emulated storage, or the statement applies a migration, or the
          witness is a codec input whose claim is definedness: BMC searches refute.json "targets" (exactly those
          targets): dom_v0_long for M0/L_dom_hdr and M3/L_par_dom_BatchHeaderBytes_validate_ok_load_sol, eta2_state for
          M1/L_nat_eta2 and M2/extracted_m1/L_nat_eta2. Result path (with its witness), no_path (every k <= H unsat) or
          unknown;
       K2 go_only: every side is a Go library call: result null, reason "node-level public path needs I39";
       K3 commit_class: a codec witness comparing the EVM encoder with another: a commit of the witness's version from
          R0 (the M0 commit-path rule, holon.mreplay.m0_commit_sides): result path, length 1;
       K4 direct: the witness is a schedule of public calls (its environment steps: time and the messenger's enqueue, as
          the M1 harness's rows 9 and 10 give them): result path, its length.
     Every REFUTED record at HEAD (results/{M0,M1,M2,M2/extracted_m1,M3}, including records other M3 keys add) gets one
     entry. Each side the record's law claims (holon.evidence.claimed_sides; for the M3 PAR laws: go and solidity) gets an
     emitted test when its concretization has a path or the side is a Go library call; a claimed side with no test keeps
     its I4 side, or has none.
  Q5 Deep reaches (reaches.json). For each guard reach of refute.json "unfalsified_reaches" (the 120 I20's step
     refinement left unfalsified): BMC with the target "the reach's check fails at the last step" from R0: path (its
     witness, its length, its replay: every step but the last ok, the last reverting with the reach's revert key on the
     real Rollup, external-call answers agreeing), no_path, or unknown.
  Q6 I21 (i21.json): refute.json "i21": the EVM half of T1, T2 and F-M2-42 by BMC; the Go halves of T1 and T2 and
     F-M2-38..41 recorded out_of_scope with the sidecar's reasons.
  Q7 Fuzz (fuzz.json): per law fuzzed, the candidates tried and accepted.

Emitted tests (holon/gen/foundry.py, holon/gen/gotest.py; they replace the hand op tables of
replay/M1/solidity/HolonTraceReplay.t.sol step() and replay/M2/solidity/HolonExtractedStep.t.sol holonAbstract())
  - A Foundry test per EVM side with a path: gen/M3/tests/foundry/<dir>/<law_id>[__<entry>].t.sol, written from the
    witness's concrete calls (calldata from the document's action interface, never from a per-action table in holon/):
    the binding's deployment (or, for a test milestone with binding null, the contract created with no argument), then per
    step vm.warp, vm.blobhashes, vm.deal when needed, vm.prank and the call, asserting each step's outcome (ok, or the
    revert key) and the obstruction the law claims. A Go test per Go side: gen/M3/tests/go/<dir>/<law_id>_test.go, calling
    the extracted function or method on the witness's input. gen/M3/tests/manifest.json lists every test
    ({"tests": [{"path", "kind": "foundry" | "go", "record", "side", "steps"}]}, sorted by path). <dir> is the record dir
    with "/" replaced by "_".
  - `holon refute --milestone M3 --only emit` regenerates gen/M3/tests/ byte for byte.
  - No file under holon/gen/foundry.py, holon/gen/gotest.py, holon/smt/, holon/bmc.py or holon/fuzz.py names a target
    action, contract, family, law id or class id.

Replay (replay/M3/refute/report.json, written by `holon refute --only replay`, never by hand): {"toolchain", "morph_commit",
"records": {"<dir>/<law_id>": {"sides": {side: {"status": "passed" | "failed" | "not_run", "provenance":
"public_schedule" | "library_api", "obstruction_observed": bool, "test": path, "outcomes": [..], "calls_agree": bool}}}},
"reaches": {reach id: {"status", "outcomes", "calls_agree"}}, "i21": {"T2" | ..: {"status", "outcomes", "calls_agree"}},
"toys": {...}}, with one "reaches" entry per reach whose BMC verdict is path (or was, before an env_mismatch discard) and
one "i21" entry per I21 question with a path. Foundry runs use the pinned forge and solc and the pinned morph checkout;
Go runs the pinned go. A record side's status is "passed" iff every step's outcome is the witness's (ok, or its revert
key) and the obstruction the law claims is checked; otherwise "failed", whatever the cause, an external call of the
real deployment answering otherwise than the record's model included (the record's model chose that answer: a model
defect, not an env_mismatch, which only discards BMC paths); "not_run" only when the toolchain pin fails.

Final filter (§9.6; holon/filter.py gains final_bin(sides, concretization); bin_of stays I4's provisional rule unchanged)
  F1 model_defect: some side failed;
  F2 known_limitation: the kind is bmc and the result no_path (BMC showed no public path within H; the record names H);
  F3 finding: the kind is not go_only, its concretization has a path, some public_schedule side passed and observed the
     obstruction, every side that is not internal_harness or emulated_storage passed and observed it, and a blocking side
     is present only for kind bmc (a public path supersedes the construction);
  F4 pending: anything else.
  sides: the record's I4 sides (replay/<M>/report.json) with each side an emitted test replaced taking the emitted test's
  result (replay/M3/refute/report.json). tests_m3/_i40.py::expected_final_bin is the rule; final_bin must agree with it
  on every input of TestFilterRule.

Records and shared files
  - Every REFUTED record at HEAD carries "filter_bin" = the final bin and "concretization": {"kind", "result", "length",
    "bound": {"H", "rlimit"} | null, "target": refute.json target id | null, "tests": [paths], "sides": {side: {"status",
    "provenance", "obstruction_observed"}}, "reason"}; PROVED and UNKNOWN records carry neither (filter_bin null).
  - spec/schemas/result_record_v2.schema.json gains "known_limitation" in filter_bin's enum and the "concretization"
    property (additive; v1 and v2 validity of every record).
  - Shared, not outcome paths, and changed only so: the REFUTED record files of results/{M0,M1,M2,M2/extracted_m1,M3} in
    filter_bin and concretization (generator_sha256 and timing keys named "seconds" may churn, as every generator edit
    makes them); results/casestudy_coverage.json and docs/CASESTUDY.md (tools/casestudy.py: the bins); the fields of
    results/<M>/metrics.json derived from filter bins; config/holon.json ("z3"); the v2 schema; spec/M2/amendments.jsonl.
    No commit that writes an I40 outcome path changes laws/M0-M2, gen/M0-M2, replay/M0-M2, spec/M1/, spec/M2/facts/,
    spec/M2/lib/, gen/M3/sorts/, a frozen root, or an instrument (spec/M3/lib/refute.json, spec/M3/lib/sort_types.json,
    spec/M3/predictions.json, prompts/I40_refute.md, tests_m3/test_refute.py, tests_m3/_i40.py,
    tests_m3/fixtures/refute/); in every such commit each result record file of results/{M0,M1,M2,M2/extracted_m1,M3}
    it changes differs from its parent's version only in filter_bin, concretization, generator_sha256 and keys named
    seconds (an I40 commit adds or deletes no record); and every M0-M2 record differs from its prereg version only in
    those fields (all checked from git).

The fixture (refute.json "fixture"; test milestones T401 = variant a, T402 = variant b)
  I30's pipeline over each variant (holon sorts, types, derive, run with the toy's model sidecar) derives one realize law,
  L_sort_realize_toylock_53_941d10c2 (the sign site W + start - block.timestamp at src/ToyLock.sol:53, entry point fire).
  `holon refute --milestone T401 --sidecar tests_m3/fixtures/refute/a/refute_toy.json --results DIR --gen-dir GDIR
  --only bmc,emit,replay [--laws ID,..]` reads the records holon run wrote to DIR, runs BMC on every law there that is
  not PROVED and on every law --laws names (a control query: a PROVED law's record is never rewritten), writes
  DIR/refute.json ({"laws": {law_id: {"attempts": [as unknowns.json]}}}, the bmc attempt with "length" and "largest_k"),
  and rewrites the record of a law it refutes as I30's pipeline writes a REFUTED record (status, "witnesses"[entry] with
  I30's witness format, "checker", "verdict" and "replay", the counter-law GDIR/proofs/<law_id>/entry_<e>/PROOF.bend
  checked by Bend and BendTT, attempts gaining the bmc attempt); its emitted tests go under GDIR/tests/ and their replay
  into DIR/replay.json, and the record's per-entry "replay" is that replay's.

CLI
  python -m holon refute --milestone M [--root DIR] [--sidecar PATH] [--only STAGE,..] [--check] [--results DIR]
    [--gen-dir DIR] [--laws ID,..]; stages, in order: layouts, smt, fuzz, bmc, emit, replay, filter (default: all). M3 reads
    spec/M3/lib/refute.json; a test milestone needs --sidecar. --check recomputes the stages' files in memory and exits 1
    on any difference with the committed ones. Exit 0 ok; 1 unreadable input or a --check difference; 2 a solver pin
    mismatch (nothing written). Output canonical JSON (json.dumps(indent=2, sort_keys=True, ensure_ascii=False) + "\\n");
    two runs byte-identical; no wall-clock time in any file G1 compares.

Outputs (outcome paths: gen/M3/refute/, results/M3/refute/, replay/M3/refute/, gen/M3/tests/ and the report
docs/iterations/I40.md)
  results/M3/refute/refind.json {"document": "refind", "solver": {"name", "version", "random_seed", "rlimit"},
    "classes": {id: {"record", "law_id", "entry", "kind", "query", "result": "sat" | "unsat" | "unknown", "bound",
    "candidates": [{"witness", "signature", "counter_law", "checker": {"exit_code", "marker"}, "verdict": {"kernel",
    "marker"}, "accepted": bool, "reason"}], "refound": bool}}}
  results/M3/refute/codec.json {"document": "codec", "laws": {record: {"status", "solver": "sat" | "unsat" | "unknown",
    "query", "candidate": null | {"witness", "counter_law", "accepted"}}}}
  results/M3/refute/unknowns.json {"document": "unknowns", "laws": {record: {"status", "attempts": [{"engine": "smt" |
    "bmc" | "fuzz" | "none", "bound", "budget", "result": "sat" | "unsat" | "unknown" (smt), "path" | "no_path" |
    "unknown" (bmc), "found" | "none" (fuzz: a candidate violated the law on the compiled model, or none did), "not_run",
    "candidates": n, "accepted": n, "discarded": [{"witness", "checker": {"exit_code", "marker"}}], "reason", and for
    bmc "length" and "largest_k"}]}}}, with candidates == accepted + len(discarded). bound and budget, exactly: smt
    over a hand machine {"steps": hand_trace_bound}, smt over byte strings {"byte_length_max": 512}, each with budget
    {"rlimit": 200000000}; bmc {"H": 8} with budget {"rlimit": 200000000}; fuzz {"candidates": 4096, "seed":
    20261014} with budget {"candidates": 4096}; none: bound and budget null, result "not_run". A search that
    found nothing has candidates 0 and discarded [].
  results/M3/refute/concretization.json {"document": "concretization", "H": 8, "records": {record: the record's
    concretization plus "path": the witness steps | null}}
  results/M3/refute/reaches.json {"document": "reaches", "source": "results/M2/refinement/extracted.json", "H": 8,
    "reaches": {id: {"verdict": "path" | "no_path" | "unknown", "length": k | null, "path": steps | null, "largest_k":
    k, "reason"}}}
  results/M3/refute/i21.json {"document": "i21", "findings": {"T1" | "T2" | "F-M2-42": {"evm": {"verdict", "length",
    "path", "largest_k", "reason"}, "go": {"verdict": "out_of_scope", "reason"} | absent}, "out_of_scope": {id:
    reason}}}
  Every BMC path (reaches.json, i21.json, concretization.json of kind bmc) obeys the sidecar's environment: at most H
  steps; each caller one of refute.json bmc.principals (owner, submitters, challenger, anyone; never the proxy admin);
  block.timestamp an integer, never 0, at least deployment.deployed_at at the first step and non-decreasing (E5);
  blobhash a list of at most blob_count_max non-zero words whose top byte is 0x01 (E2, E3); msg.value at most 100
  ether.
  results/M3/refute/fuzz.json {"document": "fuzz", "seed", "laws": {record: {"tried", "accepted"}}} (one entry per
    record unknowns.json fuzzes, tried = 4096, accepted = that attempt's accepted)
  results/M3/refute/filter.json {"document": "filter", "rule": "holon-filter/1.0", "records": {record: {"before",
    "after", "kind", "result"}}} (one entry per REFUTED record at HEAD; before its bin at the I40 prereg, or null for a
    record added later; after its filter_bin at HEAD; kind and result its concretization's)

Rules
  - AGENTS.md is binding. Never edit facts/, spec/M1/, spec/M2/facts/, spec/M2/lib/, laws/M0-M2, gen/M0-M2, replay/M0-M2,
    gen/M3/sorts/ (I30's) or a frozen file. Do not edit another key's instruments (tests_m3/_m3.py, _i24*.py, _i26.py,
    _i31*.py; _i40.py imports _i26's step builders and replay instrument and never changes them).
  - Witnesses come from the compiled model; no file under holon/ imports tests/reference/.
  - No tuning: H, the rlimit, the seed, the environment, the principals, the answers and the targets are the sidecar's.
    A miss is a Surprise with its evidence. Never widen a budget or an environment after a result.
  - No skips. A missing toolchain or .git is a failure.

Gate: `holon gate --milestone M3` passes in full (it fails at the prereg: G6 and G4 do not handle the linked codec
model yet); G6 recomputes every REFUTED record's bin with the final rule (M0-M2 gates too); G1 regenerates
gen/M3/tests/ and the query files (the engines' results are checked by `holon refute --check`).

Expected amendments (known at the prereg; spec/M2/amendments.jsonl, kind foundation_conflict, iteration I4): I4's
tests_m2/test_filter.py::TestBins::test_records_follow_the_rule (it asserts known_limitation is never assigned and the
record's bin equals I4's provisional rule) and ::test_bins_of_recorded_replays (I4-P7 pins L_dom_hdr and L_nat_eta2 at
pending): the final filter replaces the provisional bin on those two M0/M1 records. Any other amendment is a Surprise
(tests_m2/test_i4_review.py's tamper tests rebin L_dom_hdr and L_nat_eta2 with I4's rule and assert only that G6 fails
with a given reason, so they are expected to pass unchanged; if one needs an amendment, it is reported).

Residual risk, stated: tests_m3/_i26.py is fingerprinted here as a helper this file imports through _i40.py, and under
its own key; tests_m2/_i15.py and _keccak.py only under their M2 keys. The re-find templates fix the action skeleton, so a re-found class shows the encodings' fidelity on that shape, not that the free
search would find it first. BMC's no_path is relative to R0, H, the principal table and the answer table. Only 30 of
the 120 reaches have a predicted verdict (P8); the other 90 are construction checks (a verdict each, every path
replayed and inside the environment). Every query is committed; their volume is a risk the build reports, never a
reason to drop queries, lower H or raise the rlimit.
"""
import itertools
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._util import ROOT, copy_repo, load_json, run_bend, run_holon  # frozen helpers
from tests.reference import mini_schema
from tests_m3 import _i40 as I40
from tests_m3._m3 import holon_module

M3 = "M3"
SIDECAR = ROOT / "spec" / "M3" / "lib" / "refute.json"
OUT = ROOT / "results" / "M3" / "refute"
GEN = ROOT / "gen" / "M3" / "refute"
TESTS = ROOT / "gen" / "M3" / "tests"
REPLAY = ROOT / "replay" / "M3" / "refute" / "report.json"
V1 = ROOT / "schemas" / "result_record.schema.json"
V2 = ROOT / "spec" / "schemas" / "result_record_v2.schema.json"
FIX = ROOT / "tests_m3" / "fixtures" / "refute"
FIX_REL = "tests_m3/fixtures/refute"
ROLLUP = "contracts/contracts/l1/rollup/Rollup.sol"
INIT_SOL = "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol"
CODEC0 = "contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol"
CODEC1 = "contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol"
TOY_LAW = "L_sort_realize_toylock_53_941d10c2"
H = 8

# ------------------------------------------------------------------ predictions (the key I40 repeats them)
# P7: the final bin of every REFUTED record at the prereg, with its concretization kind and BMC result
PREDICTED_BINS = {
    "M0/L_dom_hdr": ("bmc", "no_path", "known_limitation"),
    "M0/L_par_hdr_ssvh": ("commit_class", "path", "finding"),
    "M0/L_par_hdr_v2": ("commit_class", "path", "finding"),
    "M1/L_fact_Z": ("direct", "path", "pending"),
    "M1/L_nat_eta2": ("bmc", "no_path", "known_limitation"),
    "M1/L_own_txspayload": ("go_only", None, "pending"),
    "M1/L_sort_remaining": ("direct", "path", "finding"),
    "M1/L_sym_omega": ("direct", "path", "finding"),
    "M1/L_tag_BVH": ("direct", "path", "finding"),
    "M1/L_undo_BVH": ("direct", "path", "finding"),
    "M1/L_undo_cancel": ("direct", "path", "finding"),
    "M2/L_sort_site_rollup_363_1fc7f88a": ("direct", "path", "finding"),
    "M2/L_sort_site_rollup_636_e68daf06": ("direct", "path", "finding"),
    "M2/extracted_m1/L_disch_delay_nofree": ("direct", "path", "model_defect"),
    "M2/extracted_m1/L_fact_Z": ("direct", "path", "pending"),
    "M2/extracted_m1/L_nat_eta2": ("bmc", "no_path", "known_limitation"),
    "M2/extracted_m1/L_sort_remaining": ("direct", "path", "finding"),
    "M2/extracted_m1/L_sym_omega": ("direct", "path", "finding"),
    "M2/extracted_m1/L_undo_BVH": ("direct", "path", "finding"),
    "M2/extracted_m1/L_undo_cancel": ("direct", "path", "finding"),
    "M3/L_par_cc_BatchCache_createBatchHeaderWithSequencerSetHash_enc_sol_v2": ("commit_class", "path", "finding"),
    "M3/L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0": ("commit_class", "path", "finding"),
    "M3/L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1": ("commit_class", "path", "finding"),
    "M3/L_par_dom_BatchHeaderBytes_validate_ok_load_sol": ("bmc", "no_path", "known_limitation"),
}

# P8: the unfalsified reaches BMC falsifies (shortest path length, the revert key on both sides) ...
PATH_REACHES = {f"{a}#{ROLLUP}:132#0": (4, "pending revert request") for a in I40.TARGETS_132}
PATH_REACHES[f"initialize2#{INIT_SOL}:120#0"] = (2, "Initializable: contract is already initialized")
PATH_REACHES[f"initialize3#{INIT_SOL}:120#0"] = (2, "Initializable: contract is already initialized")
# ... and those it shows unreachable within H from R0 (no_path)
NO_PATH_REACHES = (
    [f"initialize#{INIT_SOL}:133#{i}" for i in range(4)]                 # constant condition 1
    + [f"initialize2#{ROLLUP}:189#0"]                                    # constant condition 1
    + [f"initialize#{ROLLUP}:169#0", f"initialize#{ROLLUP}:171#0"]        # the initializer stays closed (_initialized >= 1)
    + [f"initialize4#{INIT_SOL}:120#0"]                                  # _initialized never reaches 4
    + [f"initialize4#{ROLLUP}:{n}#0" for n in (211, 212, 213, 214)]       # only the proxy admin passes :210
    + [f"importGenesisBatch#{x}#0" for x in (f"{ROLLUP}:825", f"{ROLLUP}:826", f"{CODEC0}:32", f"{CODEC1}:35",
                                              f"{ROLLUP}:844", f"{ROLLUP}:233", f"{ROLLUP}:235", f"{ROLLUP}:237",
                                              f"{ROLLUP}:238", f"{ROLLUP}:239")]   # finalizedStateRoots[0] stays non-zero
)

# P4-P6 and R5: every UNKNOWN record stays UNKNOWN, with the engines that apply
UNKNOWN_ENGINES = {
    "M2/L_sort_site_def_lci_356891e4": ("smt", "fuzz"),
    "M2/L_sort_site_l1messagequeuewithgaspriceoracle_325_f89daf17": ("smt", "fuzz"),
    "M2/L_sort_width_batchheadercodecv0_144_1abeb29c": ("bmc",),
    "M2/L_sort_width_batchheadercodecv0_166_8ad80b42": ("bmc",),
    "M3/L_par_weak_BatchHeaderBytes_BlobCommitHash_BatchHeaderBytes_BlobHashesHash_v2": ("smt", "fuzz"),
    "M3/L_par_weak_BatchHeaderBytes_BlobCommitHash_BatchHeaderBytes_BlobVersionedHash_v0": ("smt", "fuzz"),
    "M3/L_par_weak_BatchHeaderBytes_BlobCommitHash_BatchHeaderBytes_BlobVersionedHash_v1": ("smt", "fuzz"),
    "M2/extracted_m1/L_tag_BVH": (),
}
NEGATIVE = {"smt": ("unsat",), "bmc": ("no_path",), "fuzz": ("none",)}


# ------------------------------------------------------------------ helpers
def need(p: Path) -> dict:
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def sidecar() -> dict:
    return load_json(SIDECAR)


def record_path(key: str, root: Path = ROOT) -> Path:
    d, lid = I40.split_key(key)
    return root / "results" / d / f"{lid}.json"


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def prereg_commit() -> str:
    """The commit that introduced the key I40 in spec/M3/predictions.json (oldest first), as holon audit prereg finds
    it. A missing .git or no such commit is a failure, never a skip."""
    for c in git("log", "--format=%H", "--reverse", "--topo-order", "--", "spec/M3/predictions.json").split():
        p = subprocess.run(["git", "-C", str(ROOT), "show", f"{c}:spec/M3/predictions.json"], capture_output=True,
                           text=True)
        if p.returncode == 0 and "I40" in (json.loads(p.stdout).get("iterations") or {}):
            return c
    raise AssertionError("no commit introduces the key I40 in spec/M3/predictions.json")


def tree_at(commit: str, paths: list[str]) -> Path:
    """The given paths of `commit` exported to a fresh directory (git archive)."""
    d = Path(tempfile.mkdtemp(prefix="holon-i40-tree-"))
    arc = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", commit, "--", *paths], capture_output=True)
    if arc.returncode != 0:
        shutil.rmtree(d, ignore_errors=True)
        raise AssertionError(f"git archive {commit[:12]}: {arc.stderr.decode(errors='replace')[-500:]}")
    subprocess.run(["tar", "-x", "-C", str(d)], input=arc.stdout, check=True)
    return d


def strip_seconds(o):
    if isinstance(o, dict):
        return {k: strip_seconds(v) for k, v in o.items() if k != "seconds"}
    if isinstance(o, list):
        return [strip_seconds(v) for v in o]
    return o


def final_sides(key: str, rep: dict | None = None) -> dict:
    """F1-F4's sides: the record's I4 sides (a view record of results/M2/extracted_m1 takes the I4 sides of the M1
    record of its law, as rule K1-K4 does), each one an emitted test replaced taking the emitted test's result."""
    allsides = I40.replay_sides(ROOT)
    i4 = allsides.get(key) or {}
    if not i4 and key.startswith("M2/extracted_m1/"):
        i4 = allsides.get("M1/" + key.rpartition("/")[2]) or {}
    rep = rep if rep is not None else need(REPLAY)
    gen = ((rep.get("records") or {}).get(key) or {}).get("sides") or {}
    return {**i4, **gen}


def bend_ok(path: Path) -> None:
    code, out = run_bend([path.name], cwd=path.parent, timeout=900)
    if code != 0 or "ALL PROOFS CHECK" not in out:
        raise AssertionError(f"Bend rejects {path.relative_to(ROOT)}: {out[-1500:]}")


def resolved_imports(path: Path) -> dict[str, Path]:
    """alias -> resolved path of every `import <rel> as <alias>` of a Bend file."""
    out = {}
    for m in re.finditer(r"(?m)^import\s+(\S+)\s+as\s+(\w+)\s*$", path.read_text()):
        out[m.group(2)] = (path.parent / m.group(1)).resolve()
    return out


def num(x) -> int:
    return int(str(x), 0)


def env_violations(steps: list, side: dict) -> list[str]:
    """What a BMC path does outside the sidecar's environment (contract: "Every BMC path ... obeys")."""
    bad = []
    pr = side["bmc"]["principals"]
    callers = {pr["owner"].lower(), pr["challenger"].lower(), pr["anyone"].lower()} | {a.lower() for a in pr["submitters"]}
    if not steps or len(steps) > side["bmc"]["H"]:
        bad.append(f"length {len(steps or [])} not in 1..H")
    prev = side["deployment"]["deployed_at"]
    for i, s in enumerate(steps or []):
        env = s.get("env") or {}
        if str(env.get("caller", "")).lower() not in callers:
            bad.append(f"step {i}: caller {env.get('caller')} is not a principal")
        t = num(env.get("block.timestamp", 0))
        if t <= 0 or t < prev:
            bad.append(f"step {i}: block.timestamp {t} < {prev}")
        prev = max(prev, t)
        bh = env.get("blobhash")
        if not isinstance(bh, list) or len(bh) > side["blob_count_max"]:
            bad.append(f"step {i}: blobhash {bh!r}")
        else:
            for h in bh:
                v = num(h)
                if v == 0 or v >> 248 != 1:
                    bad.append(f"step {i}: blob hash {h} is zero or its top byte is not 0x01")
        if num(env.get("msg.value", 0)) > 100 * 10 ** 18:
            bad.append(f"step {i}: msg.value above 100 ether")
    return bad


class _Copy:
    def __init__(self):
        self.repo = copy_repo()
        self.tmp = Path(tempfile.mkdtemp(prefix="holon-i40-"))
        self.logs: list[str] = []

    def holon(self, args, timeout: int = 7200):
        p = run_holon([str(a) for a in args], cwd=self.repo, timeout=timeout)
        self.logs.append(f"$ holon {' '.join(map(str, args))}\n[{p.returncode}] {p.stdout[-1500:]}{p.stderr[-2500:]}")
        return p

    def log(self) -> str:
        return "\n".join(self.logs)[-6000:]

    def cleanup(self):
        shutil.rmtree(self.repo.parent, ignore_errors=True)
        shutil.rmtree(self.tmp, ignore_errors=True)


# ------------------------------------------------------------------ instruments (construction; pass at the prereg)
class TestInstruments(unittest.TestCase):
    def test_sidecar_computed_fields_are_the_computation_at_the_prereg(self):
        """refute.json's classes, codec_laws, unknowns, records, unfalsified_reaches and inputs are
        tests_m3/_i40.py::sidecar_doc over the prereg commit's tree (needs .git: a failure, never a skip)."""
        c = prereg_commit()
        side = sidecar()
        d = tree_at(c, [x["path"] for x in side["inputs"]])
        try:
            got = I40.sidecar_doc(d)
            for k in ("classes", "codec_laws", "unknowns", "records", "unfalsified_reaches", "inputs"):
                with self.subTest(field=k):
                    self.assertEqual(side[k], got[k])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_sidecar_counts(self):
        """The computed fields at the prereg: 26 classes (codec 5, domain 2, trace 19), 88 codec laws (78 PROVED, 7
        REFUTED, 3 UNKNOWN), 8 UNKNOWN records, 24 REFUTED records (kinds: 14 direct, 5 commit_class, 4 bmc, 1 go_only)
        and 120 unfalsified reaches, every predicted reach among them."""
        side = sidecar()
        kinds = [c["kind"] for c in side["classes"]]
        self.assertEqual((len(kinds), kinds.count("codec"), kinds.count("domain"), kinds.count("trace")), (26, 5, 2, 19))
        st = [x["status"] for x in side["codec_laws"]]
        self.assertEqual((len(st), st.count("PROVED"), st.count("REFUTED"), st.count("UNKNOWN")), (88, 78, 7, 3))
        self.assertEqual(sorted(u["record"] for u in side["unknowns"]), sorted(UNKNOWN_ENGINES))
        self.assertEqual({k: v["kind"] for k, v in side["records"].items()}, {k: v[0] for k, v in PREDICTED_BINS.items()})
        reaches = side["unfalsified_reaches"]
        self.assertEqual(len(reaches), 120)
        self.assertLessEqual(set(PATH_REACHES) | set(NO_PATH_REACHES), set(reaches))
        self.assertEqual((len(PATH_REACHES), len(NO_PATH_REACHES)), (8, 22))

    def test_solver_pin_is_the_installed_z3(self):
        """The pinned z3 binary and library are installed as pinned (tools/setup_env.sh --extract; Q16) and report 4.16.0;
        the pin's requirement is the hash-pinned line of tools/extract-requirements.txt."""
        s = sidecar()["solver"]
        self.assertEqual(I40.sha256_file(Path(s["binary"])), s["binary_sha256"])
        self.assertEqual(I40.sha256_file(Path(s["library"])), s["library_sha256"])
        v = subprocess.run([s["binary"], "--version"], capture_output=True, text=True).stdout
        self.assertIn(f"Z3 version {s['version']}", v)
        req = (ROOT / "tools" / "extract-requirements.txt").read_text()
        self.assertIn(s["requirement"], req)
        self.assertIn(s["wheel_sha256"], req)
        self.assertEqual(s["random_seed"], 0)

    def test_toy_fixtures_reextract_byte_for_byte(self):
        """Both ToyLock variants are holon-frontend-solidity/0.3's extraction of their sources, which differ on line 52
        only; the sign site's term and span are the fixture's."""
        a = (FIX / "a" / "src" / "ToyLock.sol").read_text().splitlines()
        b = (FIX / "b" / "src" / "ToyLock.sol").read_text().splitlines()
        self.assertEqual(len(a), len(b))
        self.assertEqual([i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y], [52])
        for v in ("a", "b"):
            with self.subTest(variant=v):
                p = run_holon(["extract", "solidity", "--sidecar", f"{FIX_REL}/{v}/extract_toylock.json", "--source",
                               f"{FIX_REL}/{v}", "--out", f"{FIX_REL}/{v}/toylock.extracted.json", "--check"])
                self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
                doc = load_json(FIX / v / "toylock.extracted.json")
                fire = next(x for x in doc["actions"] if x["name"] == "fire")
                node = ["-", ["+", ["storage", "W"], ["storage", "start"]], ["env", "block.timestamp"]]
                self.assertIn(node, [w.get("value") for w in fire["writes"]])
                self.assertEqual(I40.sha256_json(node)[:8], sidecar()["fixture"]["law"][-8:])
                self.assertEqual(sorted(x["name"] for x in doc["actions"]),
                                 ["arm", "fire", "s1", "s2", "s3", "s4", "s5", "setW"])

    def test_toy_chain_instrument_on_the_real_toy(self):
        """On the real ToyLock (pinned forge and solc): variant a, the seven-step chain with fire one second after arm
        ends in Panic 0x11, at the same second it succeeds, and fire after a three-step prefix reverts with "fire";
        variant b's chain reverts with "late" (no Panic)."""
        t0 = 1_700_000_000
        early = [I40.toy_step("arm", t0), I40.toy_step("s1", t0), I40.toy_step("s2", t0), I40.toy_step("fire", t0 + 5)]
        a = I40.toy_run("a", [I40.toy_chain(t0, 1), I40.toy_chain(t0, 0), early])
        self.assertEqual([r["outcomes"] for r in a], [["ok"] * 6 + ["rev panic:0x11"], ["ok"] * 7, ["ok"] * 3 + ["rev fire"]])
        b = I40.toy_run("b", [I40.toy_chain(t0, 1)])
        self.assertEqual(b[0]["outcomes"], ["ok"] * 6 + ["rev late"])

    def test_hand_built_rollup_paths_on_the_real_rollup(self):
        """On the real Rollup as the I20 binding deploys it (tests_m3/_i26.py::realized): the three-step revert-request
        prefix (commit, challenge, a timed-out proof) followed by each of the six actions reverts at the last step with
        "pending revert request"; initialize2 and initialize3, each called twice by an unprivileged caller, revert the
        second time with "Initializable: contract is already initialized"; one commit at version 1 with no blob succeeds
        and stores ZERO_VERSIONED_HASH (I21-T2's EVM half)."""
        from tests_m3 import _i26 as I26
        rr, ip = I40.revert_request_paths(), I40.initializer_paths()
        doc = I26.Doc(ROOT / "spec" / "M2" / "facts" / "morph_rollup.extracted.json")
        slot = I26.family_slot(doc, "batchBlobVersionedHashes", 1)
        traces = [rr[a] for a in I40.TARGETS_132] + [ip["initialize2"], ip["initialize3"], I40.zero_blob_commit()]
        res = I26.realized(traces, [slot])

        def outcome(s):
            return "ok" if s["status"] == "ok" else I40.revert_key(bytes.fromhex(s["ret"][2:]))
        for a, r in zip(I40.TARGETS_132, res[:6]):
            self.assertEqual([outcome(s) for s in r["steps"]], ["ok", "ok", "ok", "pending revert request"], a)
        for r in res[6:8]:
            self.assertEqual([outcome(s) for s in r["steps"]], ["ok", "Initializable: contract is already initialized"])
        z = res[8]["steps"][0]
        self.assertEqual(z["status"], "ok")
        self.assertEqual(z["slots"][slot], int(I26.ZVH, 16))


# ------------------------------------------------------------------ engines (construction)
class TestEngines(unittest.TestCase):
    def test_queries_are_ground_and_say_their_instances(self):
        """Every emitted query declares its instances in its first line, uses QF_AUFBV, seed 0 and the sidecar's
        rlimit; cf is n(n-1)/2 per hash function and nz the number of hash terms; no file holds a quantifier."""
        files = sorted(GEN.rglob("*.smt2"))
        self.assertTrue(files, "no query under gen/M3/refute/")
        s = sidecar()["solver"]
        for f in files:
            with self.subTest(query=str(f.relative_to(ROOT))):
                text = f.read_text()
                head = text.splitlines()[0]
                self.assertTrue(head.startswith("; holon-smt "), head[:80])
                meta = json.loads(head[len("; holon-smt "):])
                self.assertEqual((meta["logic"], meta["random_seed"], meta["rlimit"]),
                                 ("QF_AUFBV", 0, s["rlimit_per_query"]))
                terms, inst = meta.get("terms") or {}, meta.get("instances") or {}
                hashes = {k: v for k, v in terms.items() if k in ("keccak256", "sha256")}
                if hashes:
                    self.assertEqual(inst.get("cf"), sum(n * (n - 1) // 2 for n in hashes.values()))
                    self.assertEqual(inst.get("nz"), sum(hashes.values()))
                body = re.sub(r";[^\n]*", "", text)
                self.assertIsNone(re.search(r"\((forall|exists)\b", body))

    def test_bmc_queries_encode_time_and_cost(self):
        """App. D E5 and E7 in BMC's queries (gen/M3/refute/smt/bmc/): each header states its depth "steps": k with
        instances "time" = k and "cost" present; some query of the rollup has a cost constraint (commitBatch,
        commitBatchWithProof, commitState and finalizeBatch have cost terms) and some a blob-hash vector (dense)."""
        files = sorted((GEN / "smt" / "bmc").rglob("*.smt2"))
        self.assertTrue(files, "no BMC query under gen/M3/refute/smt/bmc/")
        cost = dense = 0
        for f in files:
            with self.subTest(query=str(f.relative_to(ROOT))):
                meta = json.loads(f.read_text().splitlines()[0][len("; holon-smt "):])
                inst = meta.get("instances") or {}
                self.assertIsInstance(meta.get("steps"), int)
                self.assertGreaterEqual(meta["steps"], 1)
                self.assertLessEqual(meta["steps"], H)
                self.assertEqual(inst.get("time"), meta["steps"])
                self.assertIsInstance(inst.get("cost"), int)
                cost += inst["cost"] > 0
                dense += (inst.get("dense") or 0) > 0
        self.assertGreater(cost, 0, "no BMC query constrains cost (E7)")
        self.assertGreater(dense, 0, "no BMC query has a blob-hash vector (E3)")

    def test_config_pins_the_solver(self):
        """config/holon.json "z3" is the sidecar's pin (version, requirement, the binary's and the library's sha256,
        random_seed 0)."""
        s = sidecar()["solver"]
        z = load_json(ROOT / "config" / "holon.json").get("z3")
        self.assertIsInstance(z, dict, "config/holon.json has no z3 pin")
        for k in ("version", "requirement", "binary_sha256", "library_sha256", "random_seed"):
            with self.subTest(field=k):
                self.assertEqual(z.get(k), s[k])

    def test_layout_queries_exist_for_the_extracted_header_functions(self):
        """§10.2: one query per function of spec/M2/facts/morph_header.extracted.json."""
        fns = sorted(load_json(ROOT / "spec" / "M2" / "facts" / "morph_header.extracted.json")["functions"])
        self.assertEqual(fns, ["enc_sol", "load_sol"])
        for fn in fns:
            self.assertTrue((GEN / "smt" / "layouts" / f"{fn}.smt2").is_file(), fn)

    def test_encodings_on_a_synthetic_query(self):
        """E1-E4 and NZ through the encoder's API (holon.smt.encode.instances(terms) -> {"cf", "nz", "vh_top", "dense",
        "hypz"} counts for given term multisets): 3 keccak terms give cf 3 and nz 3; 2 VH terms give vh_top 2; a blob
        vector of 6 slots gives dense 5; 2 Enc terms under K = 31 give hypz 64."""
        E = holon_module("holon.smt.encode")
        got = E.instances({"keccak256": 3, "VH": 2, "blobhash": 6, "Enc": 2}, hypz_K=31)
        self.assertEqual({k: got[k] for k in ("cf", "nz", "vh_top", "dense", "hypz")},
                         {"cf": 3, "nz": 3, "vh_top": 2, "dense": 5, "hypz": 64})

    def test_every_candidate_is_accounted_for(self):
        """I40-P3 (discipline): every candidate of every engine is accepted (Bend and BendTT accept its counter-law) or
        not, with the checker's output; an accepted candidate names a counter-law file that exists."""
        for name in ("refind.json", "codec.json"):
            d = need(OUT / name)
            rows = d["classes"].values() if name == "refind.json" else d["laws"].values()
            for row in rows:
                cands = row.get("candidates") if "candidates" in row else ([row["candidate"]] if row.get("candidate")
                                                                         else [])
                for c in cands:
                    with self.subTest(file=name, row=row.get("record")):
                        self.assertIsInstance(c["accepted"], bool)
                        if c["accepted"]:
                            self.assertTrue((ROOT / c["counter_law"]).is_file())
                        else:
                            self.assertTrue(c.get("reason") or (c.get("checker") or {}).get("marker"))
        u = need(OUT / "unknowns.json")["laws"]
        self.assertEqual(sorted(u), sorted(x["record"] for x in sidecar()["unknowns"]))
        fz = need(OUT / "fuzz.json")
        self.assertEqual(fz["seed"], sidecar()["fuzz"]["seed"])
        fuzzed = {}
        for rec, row in u.items():
            for a in row["attempts"]:
                with self.subTest(file="unknowns.json", record=rec, engine=a["engine"]):
                    if a["engine"] == "none":
                        continue
                    self.assertIsInstance(a["candidates"], int)
                    self.assertIsInstance(a["accepted"], int)
                    self.assertEqual(a["candidates"], a["accepted"] + len(a["discarded"]))
                    for d in a["discarded"]:
                        self.assertTrue((d.get("checker") or {}).get("marker"), d)
                    if a["engine"] == "fuzz":
                        fuzzed[rec] = a["accepted"]
        self.assertEqual({k: (v["tried"], v["accepted"]) for k, v in fz["laws"].items()},
                         {k: (sidecar()["fuzz"]["candidates_per_law"], n) for k, n in fuzzed.items()})


# ------------------------------------------------------------------ Q1: re-find
class TestRefind(unittest.TestCase):
    def test_smt_refinds_every_existing_refuted_witness_class(self):
        """I40-P1: every class of refute.json (26) is re-found: its template query is sat within the rlimit, its first
        candidate's counter-law (gen/M3/refute/refind/<id>/PROOF.bend, importing the record's model and LAWS.bend and
        defining Laws.<law_name>) is accepted by Bend (re-run here) and BendTT, and the candidate has the class's
        signature."""
        d = need(OUT / "refind.json")
        for c in sidecar()["classes"]:
            with self.subTest(cls=c["id"], record=c["record"], entry=c["entry"]):
                row = d["classes"][c["id"]]
                self.assertEqual((row["record"], row["entry"], row["kind"]), (c["record"], c["entry"], c["kind"]))
                self.assertEqual((row["result"], row["refound"]), ("sat", True))
                cand = row["candidates"][0]
                self.assertTrue(cand["accepted"], cand.get("reason"))
                rec = load_json(record_path(c["record"]))
                art = rec["artifacts"]
                cl = ROOT / cand["counter_law"]
                self.assertEqual(cl, GEN / "refind" / c["id"] / "PROOF.bend")
                imp = resolved_imports(cl)
                self.assertEqual(imp.get("M"), (ROOT / art["model"]).resolve())
                laws = (rec.get("witnesses") or {}).get(c["entry"], {}).get("laws") if c["entry"] else None
                self.assertEqual(imp.get("Laws"), (ROOT / (laws or art["laws"])).resolve())
                self.assertRegex(cl.read_text(), rf"(?m)^def Laws\.{re.escape(art['law_name'])}\(")
                bend_ok(cl)
                self.assertIn("ALL PROOFS CHECK", (cand.get("verdict") or {}).get("marker", ""))
                sig = cand["signature"]
                if c["kind"] == "trace":
                    self.assertEqual(sig["skeleton"], c["signature"]["skeleton"])
                elif c["kind"] == "codec":
                    self.assertLessEqual(set(c["signature"]["diff_positions"]), set(sig["diff_positions"]))
                else:
                    self.assertEqual((sig["version_byte"], sig["lhs"], sig["rhs"]),
                                     (c["signature"]["version_byte"], c["signature"]["lhs"], c["signature"]["rhs"]))

    def test_no_candidate_is_discarded_on_the_templates(self):
        """I40-P3 (fidelity): on the 26 class templates every first candidate passes its counter-law (0 discarded): the
        Appendix D encodings agree with the compiled models on every shape that has a refutation."""
        d = need(OUT / "refind.json")
        discarded = {cid: [c.get("reason") for c in row["candidates"] if not c["accepted"]]
                     for cid, row in d["classes"].items()}
        self.assertEqual({k: v for k, v in discarded.items() if v}, {})


# ------------------------------------------------------------------ Q2: codec agreement
class TestCodecAgreement(unittest.TestCase):
    def test_the_solver_agrees_with_every_codec_status(self):
        """I40-P2: on the 88 codec laws the solver's verdict on the negation is the one the status implies: sat, with an
        accepted candidate, on exactly the 7 REFUTED laws (M0 L_dom_hdr, L_par_hdr_ssvh, L_par_hdr_v2; the three M3
        cross-component laws and the M3 domain law), unsat on the 78 PROVED laws and on the 3 PAR-weak UNKNOWN laws; no
        unknown."""
        d = need(OUT / "codec.json")["laws"]
        want = {x["record"]: x["solver"] for x in sidecar()["codec_laws"]}
        self.assertEqual(sorted(d), sorted(want))
        got = {k: v["solver"] for k, v in d.items()}
        self.assertEqual(got, want)
        for k, v in d.items():
            with self.subTest(record=k):
                if want[k] == "sat":
                    self.assertTrue(v["candidate"]["accepted"])
                else:
                    self.assertIsNone(v.get("candidate"))

    def test_no_proved_record_changes_status(self):
        """I40-R1 (part): every PROVED codec law is still PROVED: an accepted candidate on a PROVED law would be a
        kernel inconsistency (Thm 6.17)."""
        for x in sidecar()["codec_laws"]:
            if x["status"] == "PROVED":
                with self.subTest(record=x["record"]):
                    self.assertEqual(load_json(record_path(x["record"]))["status"], "PROVED")


# ------------------------------------------------------------------ Q3: the UNKNOWNs
class TestUnknowns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.u = need(OUT / "unknowns.json")["laws"]

    def _attempts(self, key: str) -> dict[str, dict]:
        return {a["engine"]: a for a in self.u[key]["attempts"]}

    def _stays_unknown(self, key: str, engines: tuple, smt_bound: dict | None = None) -> None:
        """The record stays UNKNOWN, every predicted engine ran with exactly the contract's bound and budget and found
        nothing (smt unsat, bmc no_path with largest_k H, fuzz none over its 4096 candidates), and the record is the
        prereg's (an UNKNOWN record keeps its record unchanged; its I40 attempts live in unknowns.json only)."""
        self.assertEqual(self.u[key]["status"], "UNKNOWN")
        at = self._attempts(key)
        self.assertEqual(sorted(e for e in at if e != "none"), sorted(engines))
        s = sidecar()
        rl = {"rlimit": s["solver"]["rlimit_per_query"]}
        want = {"smt": (smt_bound, rl), "bmc": ({"H": H}, rl),
                "fuzz": ({"candidates": s["fuzz"]["candidates_per_law"], "seed": s["fuzz"]["seed"]},
                         {"candidates": s["fuzz"]["candidates_per_law"]})}
        for e in engines:
            a = at[e]
            self.assertIn(a["result"], NEGATIVE[e], a)
            self.assertEqual((a["accepted"], a["candidates"], a["discarded"]), (0, 0, []), a)
            self.assertEqual((a["bound"], a["budget"]), want[e], a)
            self.assertTrue(a.get("reason"), a)
            if e == "bmc":
                self.assertEqual((a["largest_k"], a.get("length")), (H, None), a)
        r = load_json(record_path(key))
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertFalse(r.get("witness"))
        old = strip_seconds(json.loads(git("show", f"{prereg_commit()}:{record_path(key).relative_to(ROOT)}")))
        new = strip_seconds(r)
        self.assertEqual(sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k) and k != "generator_sha256"),
                         [], "an UNKNOWN record I40 leaves UNKNOWN keeps its prereg content")

    def test_the_i15_site_laws_stay_unknown(self):
        """I40-P4: L_sort_site_def_lci_356891e4 ((lfi + len(win)) - 1 needs lfi + len(win) >= 1: the window always holds
        the entry at LFI, so it holds in every reachable state) and
        L_sort_site_l1messagequeuewithgaspriceoracle_325_f89daf17 (btot - bn: a header's total is its parent's plus its
        own count, so btot >= bn for every header the model commits) stay UNKNOWN: SMT unrolled to 8 steps of their
        instrumented model from s0 is unsat (no candidate) and fuzz accepts none; I40 has no proof engine."""
        for k in ("M2/L_sort_site_def_lci_356891e4", "M2/L_sort_site_l1messagequeuewithgaspriceoracle_325_f89daf17"):
            with self.subTest(law=k):
                self._stays_unknown(k, UNKNOWN_ENGINES[k], {"steps": sidecar()["smt"]["hand_trace_bound"]})

    def test_the_i20_width_laws_stay_unknown(self):
        """I40-P5: the width laws at BatchHeaderCodecV0.sol:144 (batchIndex) and :166 (totalL1MessagePopped) stay
        UNKNOWN: BMC over the extracted TRANS edges from R0 shows no path to a stored value >= 2^64 within H = 8 (within H
        the stored batchIndex is at most 8, and totalL1MessagePopped stays 0 under the deployment's empty queue); a witness
        needs about 2^64 commits (batchIndex) or about 2^48 full commits after 2^64 / 65535 enqueued messages."""
        for k in ("M2/L_sort_width_batchheadercodecv0_144_1abeb29c", "M2/L_sort_width_batchheadercodecv0_166_8ad80b42"):
            with self.subTest(law=k):
                self._stays_unknown(k, UNKNOWN_ENGINES[k])

    def test_the_par_weak_laws_stay_unknown(self):
        """I40-P6: the three PAR-weak laws stay UNKNOWN: SMT on each negation is unsat (byte strings up to 512 bytes):
        BlobCommitHash dispatches by version to BlobHashesHash (>= 2) and BlobVersionedHash (< 2) in the extracted Go
        document (common/batch/batch_header.go:138-148), so under the tag premise both sides are one function; fuzz
        accepts none; the byte-string proof route stays absent (I24 gap G6)."""
        for k in UNKNOWN_ENGINES:
            if k.startswith("M3/L_par_weak_"):
                with self.subTest(law=k):
                    self._stays_unknown(k, UNKNOWN_ENGINES[k], {"byte_length_max": sidecar()["smt"]["byte_length_max"]})

    def test_the_ghost_reading_view_record_is_not_run(self):
        """I40-R5: I20's view record of L_tag_BVH stays UNKNOWN and not run (lead decision A3: a law that reads a
        hand-written ghost is not run on the view; I30's as_member law is its analogue): one attempt, engine none."""
        k = "M2/extracted_m1/L_tag_BVH"
        self.assertEqual(self.u[k]["status"], "UNKNOWN")
        self.assertEqual([a["engine"] for a in self.u[k]["attempts"]], ["none"])
        a = self.u[k]["attempts"][0]
        self.assertEqual((a["bound"], a["budget"], a["result"]), (None, None, "not_run"), a)
        self.assertTrue(a.get("reason"), a)
        self.assertEqual(load_json(record_path(k))["status"], "UNKNOWN")


# ------------------------------------------------------------------ Q4: concretization and the final bins
class TestFilterRule(unittest.TestCase):
    def test_final_bin_agrees_with_the_rule_on_all_small_inputs(self):
        """holon.filter.final_bin(sides, concretization) agrees with tests_m3/_i40.py::expected_final_bin on every
        combination of up to two sides (status x observed x provenance) and every concretization (kind x result), and
        holon.filter.bin_of is still I4's rule (tests_m2/_i4.py::expected_bin) on one side."""
        F = holon_module("holon.filter")
        from tests_m2._i4 import expected_bin
        sts = ("passed", "failed", "not_applicable", "not_run")
        pvs = ("public_schedule", "internal_harness", "emulated_storage", "library_api")
        one = [{"status": s, "obstruction_observed": o, "provenance": p}
               for s, o, p in itertools.product(sts, (True, False), pvs)]
        concs = [{"kind": k, "result": r} for k, r in itertools.product(
            ("direct", "commit_class", "bmc", "go_only"), ("path", "no_path", "unknown", None))]
        for c in concs:
            self.assertEqual(F.final_bin({}, dict(c)), I40.expected_final_bin({}, c), c)
            for a in one:
                self.assertEqual(F.final_bin({"x": dict(a)}, dict(c)), I40.expected_final_bin({"x": a}, c), (a, c))
            for a, b in itertools.product(one[::3], one[1::3]):
                ss = {"x": dict(a), "y": dict(b)}
                self.assertEqual(F.final_bin(ss, dict(c)), I40.expected_final_bin({"x": a, "y": b}, c), (ss, c))
        for a in one:
            self.assertEqual(F.bin_of({"x": dict(a)}), expected_bin({"x": a}))

    def test_the_predicted_bins_follow_from_the_rule(self):
        """Construction: the rule gives PREDICTED_BINS from the predicted concretizations and the sides as the
        prereg's replays and the predicted emitted tests give them (the instrument agrees with itself)."""
        side = sidecar()
        i4 = I40.replay_sides(ROOT)
        for key, (kind, result, want) in PREDICTED_BINS.items():
            ss = dict(i4.get(key) or i4.get("M1/" + key.rpartition("/")[2]) or {}) \
                if key.startswith("M2/extracted_m1/") else dict(i4.get(key) or {})
            if key == "M2/extracted_m1/L_disch_delay_nofree":
                ss = {"solidity": {"status": "failed", "obstruction_observed": False, "provenance": "public_schedule"}}
            if key.startswith("M3/L_par_cc_"):
                ok = {"status": "passed", "obstruction_observed": True}
                ss = {"go": {**ok, "provenance": "library_api"}, "solidity": {**ok, "provenance": "public_schedule"}}
            if key == "M3/L_par_dom_BatchHeaderBytes_validate_ok_load_sol":
                ss = {"go": {"status": "passed", "obstruction_observed": True, "provenance": "library_api"}}
            with self.subTest(record=key):
                self.assertEqual(side["records"][key]["kind"], kind)
                self.assertEqual(I40.expected_final_bin(ss, {"kind": kind, "result": result}), want)


class TestConcretization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = need(OUT / "concretization.json")
        cls.rep = need(REPLAY)

    def test_every_refuted_record_gets_its_predicted_bin(self):
        """I40-P7: the 24 REFUTED records at the prereg get these concretizations and final bins: 16 finding (M0
        L_par_hdr_ssvh, L_par_hdr_v2; M1 L_sort_remaining, L_sym_omega, L_tag_BVH, L_undo_BVH, L_undo_cancel; M2's two site
        laws; the view's L_sort_remaining, L_sym_omega, L_undo_BVH, L_undo_cancel; the three M3 cross-component laws),
        4 known_limitation (M0 L_dom_hdr and M3 L_par_dom: no successful public step loads a version-0 header longer than
        249 bytes within H, every load being authenticated against committedBatches; M1 and view L_nat_eta2:
        committedStateRoots[0] is never zero while batch 1 is unfinalized), 1 model_defect (the view's
        L_disch_delay_nofree: its last commit, which the view accepts, reverts on the real Rollup, whose queue holds one
        message), 3 pending (M1 and view L_fact_Z: ParseBatch rejects both sidecars, HypZ; M1 L_own_txspayload: Go only,
        a node-level path needs I39)."""
        recs = self.c["records"]
        for key, (kind, result, want) in PREDICTED_BINS.items():
            with self.subTest(record=key):
                x = recs[key]
                self.assertEqual((x["kind"], x["result"]), (kind, result))
                r = load_json(record_path(key))
                self.assertEqual(r["filter_bin"], want)
                self.assertEqual(r["concretization"]["kind"], kind)
                if kind == "go_only":
                    self.assertEqual((x["result"], x["reason"]), (None, "node-level public path needs I39"))
                if kind == "bmc":
                    self.assertEqual(x["bound"], {"H": H, "rlimit": sidecar()["solver"]["rlimit_per_query"]})
                    self.assertIsNone(x.get("path"))
                    tgt = {"M0/L_dom_hdr": "dom_v0_long", "M3/L_par_dom_BatchHeaderBytes_validate_ok_load_sol":
                           "dom_v0_long"}.get(key, "eta2_state")
                    self.assertEqual(x["target"], tgt)
                if kind == "commit_class":
                    self.assertEqual(x["length"], 1)

    def test_every_refuted_record_at_head_has_a_recomputed_bin(self):
        """Construction (BUILD_PLAN I40 exit: every record's bin recomputed): every REFUTED record at HEAD, those other
        M3 keys add included, carries a concretization and the final bin F1-F4 gives on its sides; no PROVED or UNKNOWN
        record carries either."""
        for key, r in I40.record_files(ROOT).items():
            with self.subTest(record=key):
                if r.get("status") != "REFUTED":
                    self.assertIsNone(r.get("filter_bin"))
                    self.assertNotIn("concretization", r)
                    continue
                conc = r["concretization"]
                self.assertEqual(r["filter_bin"], I40.expected_final_bin(final_sides(key, self.rep), conc))
                self.assertIn(key, self.c["records"])

    def test_the_filter_document_lists_every_recomputed_bin(self):
        """Construction: results/M3/refute/filter.json has one entry per REFUTED record at HEAD: before (its bin at the
        prereg, refute.json records, or null for a record added later), after (its filter_bin at HEAD), and its
        concretization's kind and result; every BMC path of concretization.json obeys the sidecar's environment."""
        f = need(OUT / "filter.json")
        self.assertEqual(f["rule"], "holon-filter/1.0")
        side = sidecar()
        refuted = {k: r for k, r in I40.record_files(ROOT).items() if r.get("status") == "REFUTED"}
        self.assertEqual(sorted(f["records"]), sorted(refuted))
        for key, r in refuted.items():
            with self.subTest(record=key):
                x = f["records"][key]
                before = (side["records"].get(key) or {}).get("filter_bin")
                self.assertEqual((x["before"], x["after"], x["kind"], x["result"]),
                                 (before, r["filter_bin"], r["concretization"]["kind"], r["concretization"]["result"]))
        for key, x in self.c["records"].items():
            if x.get("kind") == "bmc" and x.get("path"):
                with self.subTest(path=key):
                    self.assertEqual(env_violations(x["path"], side), [])

    def test_emitted_tests_reproduce_the_hand_harness_sides(self):
        """I40-P11: the emitted tests replace the hand op tables: for each of the 16 public_schedule and library_api
        sides of the 13 records with I4 replay entries, the emitted test's side has the I4 side's status and
        obstruction_observed."""
        i4 = I40.replay_sides(ROOT)
        n = 0
        for key, ss in sorted(i4.items()):
            for name, s in sorted(ss.items()):
                if s.get("provenance") not in ("public_schedule", "library_api"):
                    continue
                n += 1
                with self.subTest(record=key, side=name):
                    g = self.rep["records"][key]["sides"][name]
                    self.assertEqual((g["status"], g["obstruction_observed"], g["provenance"]),
                                     (s["status"], s["obstruction_observed"], s["provenance"]))
                    self.assertTrue((ROOT / g["test"]).is_file())
        self.assertEqual(n, 16)

    def test_emitted_tests_and_manifest(self):
        """Construction: gen/M3/tests/manifest.json lists every emitted test (sorted, existing, nothing else under
        gen/M3/tests/); a Foundry test runs its calls as their callers (vm.prank) from calldata, never through the hand
        harness's abstract-row translation (holonAbstract, or an op-code switch)."""
        m = need(TESTS / "manifest.json")["tests"]
        self.assertTrue(m)
        self.assertEqual([t["path"] for t in m], sorted(t["path"] for t in m))
        on_disk = sorted(str(f.relative_to(ROOT)) for f in TESTS.rglob("*") if f.is_file() and f.name != "manifest.json")
        self.assertEqual(on_disk, [t["path"] for t in m])
        for t in m:
            with self.subTest(test=t["path"]):
                p = ROOT / t["path"]
                self.assertIn(t["kind"], ("foundry", "go"))
                self.assertTrue(p.name.endswith(".t.sol" if t["kind"] == "foundry" else "_test.go"))
                text = p.read_text()
                if t["kind"] == "foundry":
                    self.assertIn("prank", text)
                    self.assertNotIn("holonAbstract", text)
                    self.assertIsNone(re.search(r"\bop\s*==\s*\d+", text))


# ------------------------------------------------------------------ Q5: deep reaches
class TestReaches(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = need(OUT / "reaches.json")

    def test_every_unfalsified_reach_has_a_verdict(self):
        """Construction: every one of the 120 reaches has a verdict; an unknown names the largest k decided and its
        reason."""
        self.assertEqual((self.r["H"], self.r["source"]), (H, "results/M2/refinement/extracted.json"))
        self.assertEqual(sorted(self.r["reaches"]), sorted(sidecar()["unfalsified_reaches"]))
        for rid, x in self.r["reaches"].items():
            with self.subTest(reach=rid):
                self.assertIn(x["verdict"], ("path", "no_path", "unknown"))
                if x["verdict"] == "unknown":
                    self.assertTrue(x.get("reason"))
                    self.assertIsInstance(x.get("largest_k"), int)
                if x["verdict"] == "no_path":
                    self.assertEqual(x.get("largest_k"), H)
                if x["verdict"] == "path":
                    self.assertEqual(len(x["path"]), x["length"])
                    self.assertEqual(env_violations(x["path"], sidecar()), [])
                    g = need(REPLAY)["reaches"][rid]
                    self.assertIn(g["status"], ("passed", "failed"))
                    self.assertTrue(g["calls_agree"], "a path whose calls disagree is discarded as env_mismatch")

    def test_bmc_falsifies_the_revert_request_and_reinitializer_reaches(self):
        """I40-P8 (paths): the six "pending revert request" reaches (Rollup.sol:132 in challengeState, commitBatch,
        commitBatchWithProof, commitState, finalizeBatch, proveState) get shortest paths of 4 steps (a commit, a
        challenge, a proof after the proof window: proveState's timeout branch sets revertReqIndex; then the action), and
        initialize2's and initialize3's reinitializer reaches (Initializable.sol:120) paths of 2 steps (a reinitializer
        call, then the action); each path replays on the real Rollup (holon's replay, and independently here through
        tests_m3/_i26.py::realized): every step but the last ok, the last reverting with the reach's reason, the
        external-call answers agreeing."""
        from tests_m3 import _i26 as I26
        paths = {}
        for rid, (k, reason) in PATH_REACHES.items():
            with self.subTest(reach=rid):
                x = self.r["reaches"][rid]
                self.assertEqual((x["verdict"], x["length"]), ("path", k))
                self.assertEqual(x["path"][-1]["action"], rid.split("#")[0])
                g = self.r_replay(rid)
                self.assertEqual(g["outcomes"], ["ok"] * (k - 1) + [f"rev {reason}"])
                self.assertTrue(g["calls_agree"])
                paths[rid] = x["path"]
        ids = sorted(paths)
        res = I26.realized([paths[i] for i in ids], [])
        for rid, r in zip(ids, res):
            with self.subTest(independent=rid):
                outs = ["ok" if s["status"] == "ok" else I40.revert_key(bytes.fromhex(s["ret"][2:])) for s in r["steps"]]
                self.assertEqual(outs, ["ok"] * (PATH_REACHES[rid][0] - 1) + [PATH_REACHES[rid][1]])

    def r_replay(self, rid: str) -> dict:
        return need(REPLAY)["reaches"][rid]

    def test_bmc_shows_the_closed_reaches_unreachable_within_h(self):
        """I40-P8 (no_path): within H = 8 from R0 BMC shows no path to the 22 closed reaches: the five constant-condition
        reaches of initialize (Initializable.sol:133) and initialize2 (Rollup.sol:189); initialize's :169 and :171 (its
        initializer check needs _initialized < 1, and every writer of _initialized only raises it); initialize4's
        reinitializer reach and :211-:214 (_initialized never reaches 4, and only the proxy admin, who is no caller,
        passes :210); importGenesisBatch's ten reaches after :228 (finalizedStateRoots[0] is the genesis root and nothing
        writes index 0 again)."""
        for rid in NO_PATH_REACHES:
            with self.subTest(reach=rid):
                x = self.r["reaches"][rid]
                self.assertEqual(x["verdict"], "no_path", x.get("reason"))
                self.assertEqual(x.get("largest_k"), H)


# ------------------------------------------------------------------ Q6: I21
class TestI21(unittest.TestCase):
    def test_i21_findings_split(self):
        """I40-P10: T2's EVM half has a path of 1 step (a commit at version 0 or 1 carrying no blob, which stores
        ZERO_VERSIONED_HASH) that replays; T1's EVM half (a successful public step loading a 281-byte version-0 header) and
        F-M2-42 (a version-2 commit whose blob-hash vector has a zero before a non-zero entry: E3 makes the vector a dense
        prefix) have no path within H; the Go halves of T1 and T2 and F-M2-38..41 are out_of_scope with the sidecar's
        reasons (T1's node-side reachability needs I39, which does not exist)."""
        d = need(OUT / "i21.json")["findings"]
        self.assertEqual((d["T2"]["evm"]["verdict"], d["T2"]["evm"]["length"]), ("path", 1))
        self.assertEqual(env_violations(d["T2"]["evm"]["path"], sidecar()), [])
        for t in ("T1", "F-M2-42"):
            self.assertEqual((d[t]["evm"]["verdict"], d[t]["evm"]["largest_k"]), ("no_path", H), d[t]["evm"])
        self.assertNotIn("go", d["F-M2-42"])
        for t in ("T1", "T2"):
            self.assertEqual(d[t]["go"]["verdict"], "out_of_scope")
            self.assertEqual(d[t]["go"]["reason"], sidecar()["i21"][t]["go"])
        oos = need(OUT / "i21.json")["out_of_scope"]
        self.assertEqual(oos, sidecar()["i21"]["out_of_scope"])
        st = d["T2"]["evm"]["path"][0]
        self.assertIn(st["action"], ("commitBatch", "commitBatchWithProof"))
        self.assertEqual(st["env"]["blobhash"], [])
        # the path replays (holon's replay, and independently here): one ok step storing ZERO_VERSIONED_HASH at the
        # index it commits (batch 1, the deployment's first commit)
        g = need(REPLAY)["i21"]["T2"]
        self.assertEqual((g["status"], g["outcomes"], g["calls_agree"]), ("passed", ["ok"], True))
        from tests_m3 import _i26 as I26
        doc = I26.Doc(ROOT / "spec" / "M2" / "facts" / "morph_rollup.extracted.json")
        slot = I26.family_slot(doc, "batchBlobVersionedHashes", 1)
        z = I26.realized([d["T2"]["evm"]["path"]], [slot])[0]["steps"][0]
        self.assertEqual(z["status"], "ok")
        self.assertEqual(z["slots"][slot], int(I26.ZVH, 16))


# ------------------------------------------------------------------ the fixture: depth sensitivity
class TestFixture(unittest.TestCase):
    """I40-P9 on the planted ToyLock (refute.json "fixture"): the sign site's only counterexample is a seven-step chain;
    the current refuter (I30's S1-S3 with the rollup's budget: traces of at most 4 steps, S3 needs another entry point)
    leaves it UNKNOWN, BMC (H = 8) finds it, and its witness replays on the real toy; the guarded variant has no path."""

    def pipeline(self, c: _Copy, v: str, n: int) -> dict:
        ms = f"{FIX_REL}/{v}/sort_types_toy.json"
        facts = f"{FIX_REL}/{v}/toylock.extracted.json"
        out_s = c.repo / "gen" / f"T{n}" / "sorts"
        for args in (["sorts", "--milestone", f"T{n}", "--root", c.repo, "--sidecar", ms, "--facts", facts, "--out", out_s],
                     ["types", "--milestone", f"T{n}", "--root", c.repo, "--sidecar", ms, "--facts", facts, "--out", out_s],
                     ["derive", "--milestone", f"T{n}", "--root", c.repo, "--sidecar", ms, "--facts", facts, "--out",
                      c.repo / "laws" / f"T{n}", "--obstructions", out_s / "obstructions.json"]):
            p = c.holon(args)
            self.assertEqual(p.returncode, 0, c.log())
        dv = {e["law_id"]: e for e in load_json(c.repo / "laws" / f"T{n}" / "DERIVATION.json")["laws"]}
        self.assertIn(TOY_LAW, dv, c.log())
        self.assertEqual((dv[TOY_LAW]["subform"], dv[TOY_LAW]["entry_points"]), ("realize", ["fire"]))
        p = c.holon(["run", "--milestone", f"T{n}", "--sidecar", ms, "--out", c.tmp / f"r{n}", "--gen-dir",
                     c.tmp / f"g{n}", "--laws", TOY_LAW])
        self.assertEqual(p.returncode, 0, c.log())
        return load_json(c.tmp / f"r{n}" / f"{TOY_LAW}.json")

    def test_bmc_finds_the_seven_step_chain_the_current_refuter_misses(self):
        c = _Copy()
        try:
            before = self.pipeline(c, "a", 401)
            self.assertEqual(before["status"], "UNKNOWN", c.log())
            self.assertFalse(before.get("witness"))
            p = c.holon(["refute", "--milestone", "T401", "--sidecar", f"{FIX_REL}/a/refute_toy.json", "--results",
                         c.tmp / "r401", "--gen-dir", c.tmp / "g401", "--only", "bmc,emit,replay"])
            self.assertEqual(p.returncode, 0, c.log())
            after = load_json(c.tmp / "r401" / f"{TOY_LAW}.json")
            self.assertEqual(after["status"], "REFUTED", c.log())
            e = after["witnesses"]["fire"]
            self.assertEqual(e["status"], "REFUTED")
            steps = e["witness"]["steps"]
            self.assertEqual([s["action"] for s in steps], sidecar()["fixture"]["chain"])
            ts = [int(str(s["env"]["block.timestamp"]), 0) for s in steps]
            self.assertTrue(all(t > 0 for t in ts) and ts == sorted(ts) and ts[-1] > ts[0], ts)
            self.assertIn("ALL PROOFS CHECK", (e.get("checker") or {}).get("marker", ""))
            cl = c.tmp / "g401" / "proofs" / TOY_LAW / "entry_fire" / "PROOF.bend"
            code, out = run_bend([cl.name], cwd=cl.parent, timeout=900)
            self.assertEqual(code, 0, out[-1500:])
            self.assertIn("ALL PROOFS CHECK", out)
            self.assertEqual(e["replay"]["status"], "passed")
            real = I40.toy_run("a", [[{"action": s["action"], "calldata": s["calldata"], "env": s["env"]}
                                      for s in steps]])
            self.assertEqual(real[0]["outcomes"], ["ok"] * 6 + ["rev panic:0x11"])
            self.assertTrue(list((c.tmp / "g401" / "tests").rglob("*.t.sol")), "no emitted test for the toy")
            att = {a["engine"]: a for a in load_json(c.tmp / "r401" / "refute.json")["laws"][TOY_LAW]["attempts"]}
            self.assertEqual((att["bmc"]["result"], att["bmc"]["length"]), ("path", 7))
        finally:
            c.cleanup()

    def test_the_guarded_variant_has_no_path(self):
        c = _Copy()
        try:
            before = self.pipeline(c, "b", 402)
            self.assertNotEqual(before["status"], "REFUTED", c.log())
            p = c.holon(["refute", "--milestone", "T402", "--sidecar", f"{FIX_REL}/b/refute_toy.json", "--results",
                         c.tmp / "r402", "--gen-dir", c.tmp / "g402", "--only", "bmc", "--laws", TOY_LAW])
            self.assertEqual(p.returncode, 0, c.log())
            after = load_json(c.tmp / "r402" / f"{TOY_LAW}.json")
            self.assertEqual(after["status"], before["status"])
            att = {a["engine"]: a for a in load_json(c.tmp / "r402" / "refute.json")["laws"][TOY_LAW]["attempts"]}
            self.assertEqual((att["bmc"]["result"], att["bmc"]["largest_k"]), ("no_path", H), att.get("bmc"))
        finally:
            c.cleanup()


# ------------------------------------------------------------------ records, shared files, git
class TestRecordsAndShared(unittest.TestCase):
    def test_records_are_valid_and_the_schema_knows_the_final_bins(self):
        """Every record valid under v1 and v2; v2's filter_bin enum holds known_limitation; concretization is a v2
        property."""
        v2 = load_json(V2)
        self.assertIn("known_limitation", v2["properties"]["filter_bin"]["enum"])
        self.assertIn("concretization", v2["properties"])
        for key, r in I40.record_files(ROOT).items():
            with self.subTest(record=key):
                self.assertEqual(mini_schema.errors(r, load_json(V1)), [])
                self.assertEqual(mini_schema.errors(r, v2), [])

    def test_earlier_records_change_only_in_the_filter_fields(self):
        """I40-R2: every M0-M2 record file at the prereg differs at HEAD only in filter_bin, concretization,
        generator_sha256 and keys named seconds; at least one of them changed (needs .git: a failure, never a skip)."""
        c = prereg_commit()
        allowed = {"filter_bin", "concretization", "generator_sha256"}
        changed = 0
        for d in ("M0", "M1", "M2", "M2/extracted_m1"):
            for n in git("ls-tree", "--name-only", f"{c}:results/{d}").split():
                if not (n.startswith("L") and n.endswith(".json")):
                    continue
                old = strip_seconds(json.loads(git("show", f"{c}:results/{d}/{n}")))
                new = strip_seconds(load_json(ROOT / "results" / d / n))
                diff = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
                with self.subTest(record=f"{d}/{n}"):
                    self.assertLessEqual(set(diff), allowed, diff)
                changed += bool(set(diff) & {"filter_bin", "concretization"})
        self.assertGreater(changed, 0, "no M0-M2 record carries a recomputed bin yet")

    def test_outcome_commits_touch_no_earlier_milestone(self):
        """I40-R2: no commit that writes an I40 outcome path changes laws/M0-M2, gen/M0-M2, replay/M0-M2, spec/M1/,
        spec/M2/facts/, spec/M2/lib/, gen/M3/sorts/ or a frozen root; at least one such commit exists."""
        outs = load_json(ROOT / "spec" / M3 / "predictions.json")["iterations"]["I40"]["outcome_paths"]
        forbidden = ("laws/M0/", "laws/M1/", "laws/M2/", "gen/M0/", "gen/M1/", "gen/M2/", "replay/M0/", "replay/M1/",
                     "replay/M2/", "spec/M1/", "spec/M2/facts/", "spec/M2/lib/", "gen/M3/sorts/", "facts/",
                     "predictions/", "schemas/", "tests/", "bend/probes/", "AGENTS.md", "tools/freeze.py",
                     "docs/M0_SPEC.md", "docs/BEND_PRIMER.md", "FROZEN.sha256",
                     # the instruments of this key and the typed-model sidecar it binds to
                     "spec/M3/lib/refute.json", "spec/M3/lib/sort_types.json", "spec/M3/predictions.json",
                     "prompts/I40_refute.md", "tests_m3/test_refute.py", "tests_m3/_i40.py", "tests_m3/fixtures/refute/")
        commits, cur = [], None
        for line in git("log", "--no-merges", "--format=@%H", "--name-only", "HEAD").splitlines():
            if line.startswith("@"):
                cur = (line[1:], [])
                commits.append(cur)
            elif line.strip() and cur is not None:
                cur[1].append(line.strip())
        commits = [(c, names) for c, names in commits if any(n.startswith(tuple(outs)) for n in names)]
        self.assertTrue(commits, "no commit writes an I40 outcome path")
        rec = re.compile(r"^results/(M0|M1|M2|M2/extracted_m1|M3)/L[^/]*\.json$")
        allowed = {"filter_bin", "concretization", "generator_sha256"}
        for c, names in commits:
            self.assertEqual([n for n in names if n.startswith(forbidden)], [], f"commit {c[:12]}")
            # the shared record files: changed only in the filter fields, none added or deleted
            for n in names:
                if not rec.match(n):
                    continue
                with self.subTest(commit=c[:12], record=n):
                    new = subprocess.run(["git", "-C", str(ROOT), "show", f"{c}:{n}"], capture_output=True, text=True)
                    old = subprocess.run(["git", "-C", str(ROOT), "show", f"{c}^:{n}"], capture_output=True, text=True)
                    self.assertEqual((old.returncode, new.returncode), (0, 0), "an I40 commit adds or deletes a record")
                    o, w = strip_seconds(json.loads(old.stdout)), strip_seconds(json.loads(new.stdout))
                    self.assertLessEqual({k for k in set(o) | set(w) if o.get(k) != w.get(k)}, allowed)

    def test_m0_m2_statuses_and_witnesses_unchanged(self):
        """I40-R1: every M0-M2 record keeps its status, statement hash and witness (results/M2/extracted_m1 included)."""
        c = prereg_commit()
        for d in ("M0", "M1", "M2", "M2/extracted_m1"):
            for n in git("ls-tree", "--name-only", f"{c}:results/{d}").split():
                if n.startswith("L") and n.endswith(".json"):
                    old = json.loads(git("show", f"{c}:results/{d}/{n}"))
                    new = load_json(ROOT / "results" / d / n)
                    with self.subTest(record=f"{d}/{n}"):
                        self.assertEqual((new["status"], new.get("statement_hash"), new.get("witness")),
                                         (old["status"], old.get("statement_hash"), old.get("witness")))


# ------------------------------------------------------------------ determinism, generic code, gate
class TestDeterminism(unittest.TestCase):
    def test_emitted_tests_regenerate_byte_identically(self):
        """Construction (BUILD_PLAN I40 exit): two runs of `holon refute --milestone M3 --only emit` in a copy write
        gen/M3/tests/ byte for byte as committed."""
        c = _Copy()
        try:
            snaps = []
            for _ in range(2):
                p = c.holon(["refute", "--milestone", "M3", "--root", c.repo, "--only", "emit"], timeout=3600)
                self.assertEqual(p.returncode, 0, c.log())
                snaps.append({str(f.relative_to(c.repo)): f.read_bytes() for f in sorted((c.repo / "gen" / "M3" /
                                                                                       "tests").rglob("*")) if f.is_file()})
            self.assertEqual(snaps[0], snaps[1])
            self.assertEqual(snaps[0], {str(f.relative_to(ROOT)): f.read_bytes() for f in sorted(TESTS.rglob("*"))
                                        if f.is_file()})
        finally:
            c.cleanup()

    def test_refute_check_reproduces_every_committed_output(self):
        """Construction: `holon refute --milestone M3 --check` in a copy recomputes every stage's files (queries,
        results, tests, the replay, the records' filter fields) and finds no difference."""
        c = _Copy()
        try:
            p = c.holon(["refute", "--milestone", "M3", "--root", c.repo, "--check"], timeout=7200 * 3)
            self.assertEqual(p.returncode, 0, c.log())
        finally:
            c.cleanup()


class TestGenericCode(unittest.TestCase):
    def test_no_target_identifier_in_the_engines(self):
        """No target action, contract, family, law id or class id in holon/smt/, holon/bmc.py, holon/fuzz.py,
        holon/gen/foundry.py or holon/gen/gotest.py; none imports tests/reference."""
        files = [ROOT / "holon" / "bmc.py", ROOT / "holon" / "fuzz.py", ROOT / "holon" / "gen" / "foundry.py",
                 ROOT / "holon" / "gen" / "gotest.py"] + sorted((ROOT / "holon" / "smt").glob("*.py"))
        doc = load_json(ROOT / "spec" / "M2" / "facts" / "morph_rollup.extracted.json")
        names = ({a["name"] for a in doc["actions"]} | {s["name"] for s in doc["storage"]}
                 | {"Rollup", "Morph", "morph", "ToyLock", "BatchHeader", "Submitter", "L1MessageQueue"})
        names = {n for n in names if len(n) >= 5 and n not in ("owner", "paused", "receive")}
        for f in files:
            with self.subTest(file=str(f.relative_to(ROOT))):
                self.assertTrue(f.is_file())
                text = f.read_text()
                self.assertNotIn("tests.reference", text)
                self.assertNotIn("tests/reference", text)
                self.assertEqual(sorted(n for n in names if re.search(rf"\b{re.escape(n)}\b", text)), [])
                self.assertIsNone(re.search(r"\bL_(sort|par|undo|fact|disch|nat|sym|own|tag|dom|rt)_\w+", text))
                self.assertIsNone(re.search(r"\bC\d\d\b", text))


class TestGate(unittest.TestCase):
    def gates(self, ms: tuple) -> None:
        c = _Copy()
        try:
            for m in ms:
                rp = c.tmp / f"gate_{m}.json"
                p = c.holon(["gate", "--milestone", m, "--root", c.repo, "--report", rp], timeout=7200)
                self.assertEqual(p.returncode, 0, c.log())
                g = load_json(rp)
                self.assertTrue(g["checks"]["G6"]["passed"], g["checks"]["G6"].get("detail"))
        finally:
            c.cleanup()

    def test_gates_m0_m2_pass_with_the_final_filter(self):
        """I40-R1: holon gate passes for M0, M1 and M2 on a copy, G6 recomputing every REFUTED record's bin with the
        final rule (they pass at the prereg with I4's rule)."""
        self.gates(("M0", "M1", "M2"))

    def test_gate_m3_passes_with_the_final_filter(self):
        """Construction (I40-R4): the full holon gate --milestone M3 passes on a copy, its G6 over every REFUTED M3
        record with the final rule. At the prereg it fails (G6: the linked codec document names no target commit; G4:
        no canary over the linked model): I30's gate wiring and I40's G6 make it pass."""
        self.gates(("M3",))


if __name__ == "__main__":
    unittest.main()
