"""I21: audit round M2/2, the A2/A4 audit of extraction (whitepaper §9.5 auditors A2 and A4, Def 4.1 and §8.3 R^ext,
§12.3 (L21), L5, L19; BUILD_PLAN I21). This docstring is the contract.

Who does what
  A fresh auditor session writes the two attack instruments, runs them on the target commit, investigates every
  mismatch and files findings. It fixes nothing. It is the same model family as the builders (Q9 default,
  docs/HUMAN_ANSWERS.md), so the round is labelled "same" and does not count toward convergence; its findings still
  block. Separate fix sessions fix every high finding before I22 starts, each fix with a test (P6); medium and low
  findings get a fix_iteration.

Target commit and instrument
  target_commit is the commit of the project branch the round audits: one holding I20's outputs (at least
  results/M2/refinement/extracted.json and results/M2/differential.json), after I20 merges. It is an ancestor of the
  round's own commits. Every repository input below is read from that commit's tree. The instrument is the sidecar
  spec/M2/lib/audit_round2.json, frozen at the prereg (its sha256 is pinned below). Its doc field says how each value
  was computed from committed artifacts: the corpora, the seed, the surfaces with their call sites, methods and models,
  the attack ids, the hypothesis keys, the degenerate rule and the representative search bound. The prereg was written
  on the project branch at 90153fd: after the I19 follow-up (A19), whose regenerated documents the sidecar hashes, and
  after I59, whose committed replay (results/M2/historical/replay.json) fixes the real inputs of the go_consumer
  surface. The calldata and blobs of those inputs are read from the I59 snapshot (~/.holon/historical, outside the
  repository) through holon.historical, each object checked against its sha256 in results/M2/historical/index.json. A
  missing snapshot or a hash mismatch is a failure of the run and of --check, never a skip.

Outputs (canonical JSON: json.dumps(obj, indent=2, sort_keys=True) + "\n"; no timestamps)
  audit/rounds/M2/round2.json        the round, valid against spec/schemas/audit_round.schema.json (unchanged)
  audit/rounds/M2/round2/a2.json     auditor A2 (hostile input), written by `python -m holon audit hostile`
  audit/rounds/M2/round2/a4.json     auditor A4 (vacuity and over-strength), written by `python -m holon audit vacuity`
  audit/rounds/M2/round2/harness/    the Foundry and Go harness sources the instruments copy into scratch copies of
                                     the pinned checkout (nothing is ever written to /root/work/morph)
  audit/M2_round2.md                 the prose round: what each attack tried, what happened, reproductions
  audit/M2_findings.jsonl            the round's findings, appended. This file is not an outcome path, because other
                                     lanes append to it too; the round's lines are those with "round": "M2/round2".
  Findings do not go to audit/findings.jsonl: the preregistered I5 tests (tests_m2/test_audit.py) pin that file to
  M0/M1 ids, and audit round M2/1 started the separate M2 file. audit/rounds/M2/round1.json exists, so this is round 2.

CLIs (holon/audit/hostile.py and holon/audit/vacuity.py, dispatched by `python -m holon audit hostile|vacuity`)
  python -m holon audit hostile --milestone M2 --round 2 [--surface S ...] [--morph PATH] [--snapshot DIR] [--out FILE]
                                [--check]
  python -m holon audit vacuity --milestone M2 --round 2 [--out FILE] [--check]
  - Each output is a function of the target commit's tree, the sidecar, the pinned toolchain (config/holon.json
    replay.*: solc, forge, go, node, bend), the pinned morph checkout and (hostile, go_consumer) the I59 snapshot. It is
    byte-identical across runs.
  - --check reads target_commit from the committed file and materializes that commit's tree in a scratch directory
    (git archive). It reruns there and exits 0 iff the result equals the committed file byte for byte.
  - Model-side expectations come only from the extracted documents and the compiled models: holon.model_eval or
    holon.model_native (I16's machinery) for facts/morph_header.json and spec/M1/facts/morph_batchdata.json, and I20's
    gen/M2/extracted/model.bend with holon/replay_fragments.py for the rollup. Never from tests/reference/ (AGENTS
    rule 5).

a2.json
  {"round": 2, "milestone": "M2", "target_commit": "<40 hex>", "seed": 20261021,
   "corpora": {"header": "<sha256>", "act_header": "<sha256>", "encoder": "<sha256>"},
   "surfaces": {"<surface>": {
       "carrier": "<diagram document>:<carrier>",          the carrier the hostile inputs enter through
       "models": ["<path>[#<edge or predicate>]", ...],     what the real code is compared with
       "entry_points": [{"name", "site", "inputs", "dominated_by"}],
       "inputs": n, "abi_rejected": n,
       "outcomes": {"<label>": n},
       "paths": {"covered": n, "total": n} | null,
       "mismatches": [{"id", "model", "entry", "input", "expected", "real", "class", "explained_by", "why",
                       "finding"}],
       "panics": [{"function", "site", "site_status", "witness", "explained_by", "finding"}],
       "real_inputs": {...}}},                               go_consumer only, below
   "codec_labels": {"<CODEC edge id>": {"surface", "diagram_partial": bool, "real_partial": bool}},
   "mutants": [{"surface", "mutation", "detected": bool, "mismatches": n}],
   "target_findings": [{"id": "T<n>", "surface", "bin": "finding" | "known_limitation", "law": "<law id>" | null,
                        "entry_points": [...], "inputs": n, "batch_indices_sha256": "<sha256>" | null,
                        "solidity": "<outcome label>" | null, "go": "<outcome label>" | null, "why"}]}
  - corpora: the digest of each preregistered corpus as generated, by the sidecar's corpus_digest rule (the inputs in
    the sidecar's order, each as its 4-byte big-endian length followed by its bytes). They must equal the digests of
    the sidecar's definitions.
  - entry_points. name: the public function (Solidity), or the document's function key (Go, for example
    "(morph-l2/common/batch.BatchHeaderBytes).BatchIndex"). site: "<unit>:<line>" of the compared call site, or null.
    inputs: how many corpus inputs reached the site. dominated_by: the sites that every input passes first, else null.
  - inputs and outcomes count the well-formed inputs only (malformed encodings go to abi_rejected). outcomes lists
    only labels that occurred.
  - Outcome labels. Solidity: "ok" means the call went past the compared site: it succeeded, or it reverted with revert
    data that is none of the compared edge's reasons. "revert:<reason>" is an Error(string) reason of the compared
    edge; each occurs once in the pinned contracts (sidecar doc, item 3). Also "panic:<code>" and "empty" (a revert
    with empty data). Go: "ok" (a nil error, or no error result), "error" (a non-nil error) and "panic". For
    (*BatchInfo).ParseBatch (go_consumer) the error is split by the step that returned it: "error:header_index" (the
    BatchIndex call at batch_info.go:92:55; its message starts "decode batch header index error"),
    "error:header_total" (the TotalL1MessagePopped call at :96:69; "decode batch header totalL1MessagePopped
    error") and "error:other" (any later step).
  - A mismatch is an input whose real outcome differs from what a compared model gives for it, recorded once per
    (entry point, input, model). Against an extracted
    document, the expectation is the outcome of the unique path whose conditions the input satisfies; an input that
    satisfies no path, or more than one, is a mismatch too. On a Go "ok", the decoded value is compared as well, for
    every function in the document's codecs.decoders: be_uint is the big-endian unsigned of width bytes at offset,
    to_array the width bytes at offset, index the byte at offset. Against a frozen predicate, encoder or decoder,
    evaluated on the compiled model, the expectation is "ok" (true or defined) or "rejected" (false or undefined), and
    any real outcome other than "ok" counts as rejected. The frozen enc_sol is undefined where it returns the M0
    model's UNDEF sentinel, the one-cell byte list it returns outside version_le 2 (audit M2/1 F-M2-36). dec_go is
    undefined where it returns None.
  - class is one of:
      unexplained   nothing below explains it. finding names an entry of audit/M2_findings.jsonl.
      implicit      the real side reverts with empty data or a Panic where the compared document records no guard or
                    implicit check. explained_by is the document's A-implicit assumption. On rollup_act the
                    mismatch also carries "exemption", the A-implicit exemption it falls under: "abi_dynamic_calldata"
                    (offsets and lengths of dynamic calldata, and the Panic 0x41 of allocating a decoded value),
                    "narrow_array_element" (the range of an array element of a narrow type) or "out_of_gas". Since
                    A19 the rollup document records panics, calls (callok), callvalue, calldatasize and ABI range
                    checks, so a Panic or an empty revert outside these three is unexplained, not implicit.
      debt          the divergence lies in a statement listed as coverage debt (gen/M2/coverage.json, or a Go
                    document's go.coverage.debt). explained_by is that entry's src (Go: where).
      assumption    another assumption the compared document states explains it (A-env, A-loop, A-reentrancy, A-span,
                    go-nil-deref-not-modelled, ...). explained_by is its id.
    explained_by is null exactly for unexplained. why says, in one sentence, how the class applies.
  - Malformed ABI encodings, at least one of each kind in the sidecar's abi_malformed list per Solidity entry point,
    are outside the input type (§8.3: R^ext is the full input type at the interface). They count in abi_rejected. One
    is a mismatch only if the real side does anything but revert with empty data.
  - panics: every Go panic and every Solidity Panic observed. site is the document's site id, or the file:line:col of
    the panic when no site is recorded there. site_status is "safe", "open" or "unrecorded", as the target commit's
    document says. witness is the call sequence from a fresh state (Go: [{"call": "<function key>", "args": [...]}]),
    or the transaction (Solidity). A panic at an open site decides that site. One at a safe site is a mismatch of class
    unexplained.
  - codec_labels covers every CODEC edge of gen/M2/diagram/morph_header.json at the target commit. diagram_partial is
    the edge's partial flag there. real_partial is true iff the real code rejects some input of the edge's surface
    (revert, non-nil error or panic): enc_sol is sol_encoder, dec_go is go_header, enc_go_v0 and enc_go_v1 are
    go_encoders.
  - mutants test the instrument's own sensitivity (attack A9). Each surface has at least one planted partiality mutant:
    a scratch copy of a compared document or model with one condition, length constant, guard or site status changed.
    Mutants are never committed. A mutant is detected iff the rerun reports a mismatch the unmutated run did not.
  - target_findings are results about the target, binned by the finding filter (whitepaper §9.6). A real-code
    behaviour that agrees with the extracted documents but is an obstruction between the languages, shown by a
    schedule of public entry points on reachable inputs, is bin "finding" (a real input, or a hostile input that a
    public entry point of the other side accepts); one that needs an input no public entry point produces is
    "known_limitation". law names the HOLON law it realizes, if any. A target finding is not a defect of HOLON: it
    is not a line of audit/M2_findings.jsonl and it does not block I22. It is reported in audit/M2_round2.md and in
    docs/iterations/I21.md, for the human to decide on an upstream report. When the auditor judges that HOLON's
    model should have stated it and does not, that gap is a separate HOLON finding.

The surfaces (sidecar "surfaces"; these are minimum corpora, and more is allowed)
  sol_loader     morph_header:Bytes. The header corpus (2561 inputs) goes through each of the 9 non-dominated
                 Rollup._loadBatchHeader call sites, each by its public function: :230 importGenesisBatch, :259
                 commitBatch, :277 commitState, :402 and :414 commitBatchWithProof, :433 revertBatch, :600 proveState,
                 :627 finalizeBatch and :716 proveCommittedBatchState. The state, caller, value and blobs are set so
                 that every check before the call site passes. :309 is listed under the name _commitBatchWithBatchData with
                 dominated_by the :259, :277 and :402 sites, and needs no inputs. Compared with load_sol
                 (spec/M2/facts/morph_header.extracted.json) and the frozen ok_sol (facts/morph_header.json).
  sol_encoder    morph_rollup:Act. The encoder corpus (1024 variants of BatchDataInput's version and two state roots)
                 goes through commitBatch, commitState and commitBatchWithProof. Every other field, the state and the
                 blobs are valid. Compared with the extracted enc_sol and the frozen enc_sol.
  go_header      morph_header:Bytes. The header corpus goes through each exported BatchHeaderBytes method of
                 morph-l2/common/batch (16) and morph-l2/node/types (15), each called by its exported name. Compared
                 with the extracted paths of morph_batch.go.extracted.json and morph_nodetypes.go.extracted.json, and,
                 for common/batch, with the frozen ok_go (validate) and the frozen dec_go (getters). validate is
                 unexported: an in-package harness, like I16's, calls it for the ok_go comparison only.
  go_encoders    morph_header:Header. BatchHeaderV0.Bytes and BatchHeaderV1.Bytes, varying one field at a time from the
                 zero header: each uint64 field in {0, 1, 2^64 - 1} and each hash field in {0x00..00, 0xff..ff}, with
                 EncodedBytes in {nil, 1 byte, the encoder's own length}. Compared with the extracted encoder paths
                 and the frozen enc_go_v0 and enc_go_v1.
  rollup_act     morph_rollup:Act. Every action I20's extracted model compiles, at least the 8 modelled ones. Inputs
                 are applied from the post-genesis state and, per action, from a corpus state where it succeeds. They
                 run through I20's refinement harness (holon/replay_fragments.py) and compare I20's observables:
                 status, revert data, storage slots and events. Hostile inputs vary one parameter at a time from a
                 succeeding base input (parameters and their types from the document's actions[].params, A19):
                   every uint<w> parameter in {0, 1, 2^w - 2, 2^w - 1};
                   every bytes32 in {0, 1, 2^256 - 1};
                   every bool both ways;
                   every header argument over the act header corpus (51 inputs);
                   the caller: a satisfying and a failing caller of the action's extracted principal predicate, plus
                   address(0);
                   msg.value in {0, 1}.
                 Actions the model does not compile are listed in entry_points with inputs 0.
  batchdata_act  morph_batchdata:Act. From NewBatchData: every sequence of up to 3 Append calls, with block contexts of
                 length {0, 1, 58, 59, 60, 61, 120}, payloads of length {0, 1, 4096} and {0, 1, 2} L1 tx hashes. Then
                 each exported BatchData method is called once. Each method is also called on a nil *BatchData.
                 Compared with the batchdata model (append, txsPayloadV2) and with the extracted paths and sites of
                 the exported BatchData methods in morph_batch.go.extracted.json. When a path condition holds a term
                 that the evaluator cannot compute from the inputs (an opaque call's result), the input is compared
                 on panic versus no panic only.
  go_consumer    morph_header:Bytes, at its Go consumer: the node's derivation (morph-l2/node/derivation). Entry
                 points: (*Derivation).UnPackData (called by fetchRollupDataByTxHash, derivation.go:556:28) and
                 (*BatchInfo).ParseBatch (called by parseBatch, :715:32), both exported. An in-package harness builds a
                 Derivation whose four ABIs are loaded exactly as NewDerivationClient loads them (derivation.go:108-123)
                 and calls only these two methods. Inputs:
                   hostile: the header corpus as parentBatchHeader of an otherwise well-formed commitBatch calldata
                   under each of the four selectors UnPackData recognises (sidecar go_consumer.abis: 0x4a8d544f at
                   :617, 0xd63b3549 at :639, 0x428868b5 at :662, 0x41f756da at :664), 4 x 2561 inputs; ParseBatch gets
                   the unpacked batch with a one-blob sidecar of the zero blob;
                   real: the calldata and blobs of all 62172 commits of results/M2/historical/replay.json (I59), each
                   unpacked by UnPackData and parsed by ParseBatch with its own blobs.
                 Compared with the extracted paths of UnPackData (morph_derivation.go.extracted.json) and of the two
                 header methods ParseBatch calls first (BatchIndex at batch_info.go:92:55, TotalL1MessagePopped at
                 :96:69; morph_batch.go.extracted.json), and with the frozen ok_go. UnPackData is expected to return a
                 nil error with parentBatchHeader byte-identical to the input header; ParseBatch's header step is
                 expected to reject exactly the headers those paths reject. Only ParseBatch's header step is compared;
                 its later steps are recorded as outcomes (error:other, ok) and their panics as panics.
                 surfaces.go_consumer.real_inputs:
                   {"commits": n, "by_selector": {"<selector>": n},
                    "unpack": {"<outcome label>": n},          UnPackData's outcomes over the real commits
                    "parent_keccak_mismatches": [batch index], commits whose unpacked parentBatchHeader does not hash
                                                               to the parent keccak replay.json records
                    "parse": {"<outcome label>": n},           ParseBatch's outcomes over the real commits
                    "rejected": {"<label>": [batch index]},    for every ParseBatch label other than ok, the batch
                                                               indices of the commits with that outcome, ascending
                    "solidity_on_rejected": {"<label>": n}}    the parent headers of rejected["error:header_index"]
                                                               through Rollup.commitBatch's _loadBatchHeader call
                                                               (:259) by sol_loader's harness
                 Every rejected real commit is a candidate target finding and appears in target_findings.

a4.json
  {"round": 2, "milestone": "M2", "target_commit": "<40 hex>",
   "laws": {"<record path>": {"status", "premised": bool,
        "inhabitant": null | {"source": "record" | "search" | "counter_witness", "run_length": n,
                              "replayed": bool, "premises_hold": bool,
                              "site_operands": null | {"minuend": n, "subtrahend": n}},
        "satisfiable": true | false | null, "degenerate": true | false | null,
        "degenerate_reason": null | "initial_state" | "zero_subtrahend",
        "representative": null | {"run_length": n, "replayed": bool, "premises_hold": bool,
                                  "site_operands": null | {"minuend": n, "subtrahend": n}},
        "finding": null | "<id>"}},
   "hypotheses": {"<id>": {"verdict": "tested" | "untestable", "result": "pass" | "fail" | null,
        "implementation": "<what ran>" | null, "test": "<what was run>", "sample": n | null,
        "counterexample": null | <the violating case>, "reason": null | "<what is missing>", "finding": null | "<id>"}},
   "canaries": [{"kind": "unsatisfiable_premise" | "degenerate_inhabitant" | "false_hypothesis", "what",
                 "detected": bool}]}
  - laws covers every results/M2/L_*.json and results/M2/extracted_m1/L_*.json of the target commit, keyed by path.
    premised means the law's statement (laws/M2/<id>.json, or laws/M1/<id>.json for an extracted_m1 record) has an
    assume premise (cf and hyp premises are assume premises) or a Reach binder.
  - For a premised PROVED law, A4 takes the record's inhabitant, or searches one, and replays it on the compiled model
    the record names. replayed is true iff every step of its run succeeds. premises_hold is true iff every premise
    holds at the inhabitant. For a SORT-site law, the site is evaluated there and site_operands are its operands.
  - satisfiable is true iff replayed and premises_hold. It is false only when A4 shows the premises unsatisfiable
    (then a finding). It is null for laws that are not both PROVED and premised. A REFUTED law's counter-witness may
    stand as its inhabitant (source counter_witness); it is not judged degenerate.
  - degenerate applies the sidecar's degenerate_rule to PROVED premised laws with an inhabitant; it is null otherwise.
    It is true iff the inhabitant's run is empty (degenerate_reason "initial_state"), or the law is a SORT-site law
    whose site subtrahend is 0 there ("zero_subtrahend"). When both hold, initial_state wins. This is §12.3: A4 audits
    that the inhabitants are representative rather than degenerate.
  - representative: for every law whose inhabitant is degenerate, A4 runs the sidecar's representative_search (runs of
    at most 6 actions from the initial state, breadth-first) for an inhabitant that is not degenerate, replays it and
    checks its premises; the first one found is recorded, else null. It is null for laws that are not degenerate. A
    degenerate law with no representative is a vacuity finding (its premises may hold only in a corner); one with a
    representative is not.
  - hypotheses covers every key of results/M2/hypotheses.json at the target commit. "not_in_scope" there is I12's
    model status, not a verdict.
      tested: the hypothesis as stated (spec/M2/lib/oracles.json: its kind cf or hyp predicate, else its doc) runs
      against an implementation of the real oracle that is not part of holon/ or tests/. That is a contract or library
      of the pinned morph checkout, of its pinned dependencies (Go module graph, Solidity node_modules), or the EVM.
      implementation names it (path or module@version). result is "pass" iff no case of the sample violates the
      hypothesis. A "fail" gives one violating case and a finding.
      untestable: no implementation runs here. reason names what is missing.
  - canaries test A4's own sensitivity (attack A9): a scratch law with an unsatisfiable premise, a scratch inhabitant
    at the initial state, and a hypothesis entry altered to be false. They are never committed. A canary is detected
    iff A4 flags it.

round2.json
  round 2, milestone M2, target_commit as above, auditor {"session", "family": "same",
  "counts_toward_convergence": false}. attacks are the sidecar's A1..A10. These are ids of this round's entries; the
  whitepaper's auditor types are written "auditor A2" and "auditor A4".
    A1-A6   model_vs_code, one surface each (sol_loader, sol_encoder, go_header, go_encoders, rollup_act,
            batchdata_act);
    A7      vacuity (a4.laws);
    A8      bindings_ledger (a4.hypotheses);
    A9      mutation_adequacy (a2.mutants and a4.canaries);
    A10     determinism (--check of both CLIs);
    A11     model_vs_code, surface go_consumer (added at the rebase onto 90153fd, after I59).
  Each of A1-A6 and A11 lists the finding of every unexplained mismatch and every panic of its surface; A7 lists every law
  finding, and A8 every hypothesis finding. findings is the set of ids of the audit/M2_findings.jsonl lines with
  "round": "M2/round2".

audit/M2_findings.jsonl (append-only)
  - The round appends one line per finding. Ids are F-M2-NN, continuing the file's numbering and contiguous. A line
    holds {"id", "round": "M2/round2", "iteration_audited", "severity": high|medium|low, "category" (an audit_round
    category), "aspect", "title", "reproduction", "plan_or_paper_ref", "suggested_fix",
    "confirmed_by_reproduction": bool, "status": open|fixed|wontfix|duplicate, "fix_iteration": "I<n>", "fix_lane",
    "test"}.
  - A fixed finding names the test that pins its fix: tests_mN/test_x.py::Class or ::Class.method.
  - Earlier lines keep their ids and order. The round may update the fields of an earlier finding it resolves, adding
    "resolution". F-M2-36 (CODEC partiality, assigned to I21) is resolved by A1-A4: its resolution names round
    M2/round2, confirmed_by_reproduction says whether the round reproduced it, and it is not left open under I21.
  - Exit: zero open high findings in the file before I22. `python -m holon audit status --findings
    audit/M2_findings.jsonl` reports none blocking.

Rules
  - AGENTS.md is binding. The auditor writes only audit/ and its two instruments (holon/audit/hostile.py,
    holon/audit/vacuity.py, and the audit subcommand hunk of holon/__main__.py). It never edits facts/, spec/M1/facts/,
    laws/, a document under spec/M2/facts/, a generator or a test.
  - A same-family round is labelled "same" and does not count toward convergence. Its findings still block (Q9).
  - No tuning. A corpus is never shrunk after a run, and a mismatch is never reclassified to fit a prediction. A missed
    prediction is a Surprise in docs/iterations/I21.md.
"""
import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, load_json, run_holon, validate

AUDIT = ROOT / "audit"
ROUND = AUDIT / "rounds" / "M2" / "round2.json"
A2 = AUDIT / "rounds" / "M2" / "round2" / "a2.json"
A4 = AUDIT / "rounds" / "M2" / "round2" / "a4.json"
PROSE = AUDIT / "M2_round2.md"
FINDINGS = AUDIT / "M2_findings.jsonl"
SIDECAR = ROOT / "spec" / "M2" / "lib" / "audit_round2.json"
SIDECAR_SHA256 = "dcc03fa1f4bb3f736b086c13cb0a5373c2866df4788436e29254ee38073558c0"
SCHEMA = ROOT / "spec" / "schemas" / "audit_round.schema.json"
ROLLUP = "contracts/contracts/l1/rollup/Rollup.sol"
FROZEN_HDR = "facts/morph_header.json"
EXTRACTED_HDR = "spec/M2/facts/morph_header.extracted.json"
SURFACES = ("sol_loader", "sol_encoder", "go_header", "go_encoders", "rollup_act", "batchdata_act", "go_consumer")
GO_SURFACES = ("go_header", "go_encoders", "batchdata_act", "go_consumer")
CLASSES = ("unexplained", "implicit", "debt", "assumption")
CATEGORIES = ("statement_fidelity", "gate_evasion", "model_vs_code", "vacuity", "determinism", "mutation_adequacy",
              "bindings_ledger")
SEVERITIES = ("high", "medium", "low")
STATUSES = ("open", "fixed", "wontfix", "duplicate")
ROUND1_IDS = [f"F-M2-{i:02d}" for i in range(1, 38)]
I20_OUTPUTS = ("results/M2/refinement/extracted.json", "results/M2/differential.json")
DATAHASH_SITE = "common/batch/batch_data.go:75:36:slice"
DATAHASH = "(*morph-l2/common/batch.BatchData).DataHash"
NEW_BATCH_DATA = "morph-l2/common/batch.NewBatchData"
ZERO_ROOT_REASONS = {"revert:previous state root is zero", "revert:new state root is zero"}
PASSING_HYPOTHESES = ("CF-agg", "CF-hdr", "Hyp-Z0-kzg", "Hyp-messenger")
DEGENERATE_SITE_LAWS = {"L_sort_site_def_bvh_at_": ("initial_state", 2), "L_sort_site_def_w_": ("initial_state", 1),
                        "L_sort_site_rollup_441_": ("zero_subtrahend", 1),
                        "L_sort_site_rollup_485_495_": ("zero_subtrahend", 1)}
REPRESENTATIVE_SITE_LAWS = {"L_sort_site_rollup_644_660_": 1}
GO_DOCS = ("morph_batch", "morph_blob", "morph_derivation", "morph_genesis", "morph_nodetypes")
UNPACK = "(*morph-l2/node/derivation.Derivation).UnPackData"
PARSE = "(*morph-l2/node/derivation.BatchInfo).ParseBatch"
IMPLICIT_EXEMPTIONS = ("abi_dynamic_calldata", "narrow_array_element", "out_of_gas")


# ------------------------------------------------------------------ helpers
def need(p: Path) -> dict:
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def side() -> dict:
    return load_json(SIDECAR)


def git(*args: str) -> str:
    """Read-only git on the real checkout. A missing repository or history is a failure, never a skip."""
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {p.stderr.strip()[-500:]}")
    return p.stdout


def target() -> str:
    t = need(ROUND)["target_commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", t or ""):
        raise AssertionError(f"target_commit {t!r} is not a 40-hex commit")
    return t


def at_target(path: str):
    return json.loads(git("show", f"{target()}:{path}"))


def target_paths(prefix: str) -> list[str]:
    return sorted(l for l in git("ls-tree", "-r", "--name-only", target(), prefix).splitlines() if l.strip())


def findings() -> list[dict]:
    if not FINDINGS.is_file():
        raise AssertionError(f"{FINDINGS.relative_to(ROOT)} is missing")
    return [json.loads(l) for l in FINDINGS.read_text(encoding="utf-8").splitlines() if l.strip()]


def round2_ids() -> set[str]:
    return {f["id"] for f in findings() if f.get("round") == "M2/round2"}


def surface(a2: dict, name: str) -> dict:
    s = a2.get("surfaces", {}).get(name)
    if s is None:
        raise AssertionError(f"a2.json has no surface {name}")
    return s


def entry(s: dict, name: str, site=None) -> dict:
    hits = [e for e in s["entry_points"] if e["name"] == name and (site is None or e.get("site") == site)]
    if len(hits) != 1:
        raise AssertionError(f"expected one entry point {name} {site or ''}, found {len(hits)}")
    return hits[0]


def exported(call: str) -> bool:
    m = re.search(r"\.([A-Za-z_][A-Za-z0-9_]*)$", call)
    return bool(m) and m.group(1)[0].isupper()


def _span(fb) -> list[int]:
    return list(range(fb["from"], fb["to"] + 1)) if isinstance(fb, dict) else list(fb)


def header_inputs(spec: dict, seed: int) -> list[bytes]:
    """The sidecar's header corpus, in its order: the empty string, then b0 ascending, then L as listed."""
    out = [b""] if spec["empty"] else []
    for b0 in _span(spec["first_bytes"]):
        for n in spec["lengths"]:
            body, k = b"", 0
            while len(body) < n - 1:
                body += hashlib.sha256(f"I21:{seed}:{b0}:{n}:{k}".encode()).digest()
                k += 1
            out.append(bytes([b0]) + body[:n - 1])
    return out


def encoder_inputs(spec: dict) -> list[bytes]:
    """The sidecar's encoder corpus: version byte, prevStateRoot, postStateRoot (32 bytes each), in its order."""
    root = {"0": bytes(32), "R1": hashlib.sha256(b"I21:prev").digest(), "R2": hashlib.sha256(b"I21:post").digest()}
    return [bytes([v]) + root[a] + root[b] for v in _span(spec["versions"]) for a, b in spec["roots"]]


def digest(inputs: list[bytes]) -> str:
    return hashlib.sha256(b"".join(len(x).to_bytes(4, "big") + x for x in inputs)).hexdigest()


def premised(statement: dict) -> bool:
    return bool(statement.get("assume")) or any(b.get("type") == "Reach" for b in statement.get("binders", []))


def law_file(record_path: str) -> str:
    stem = Path(record_path).stem
    return f"laws/M1/{stem}.json" if "/extracted_m1/" in record_path else f"laws/M2/{stem}.json"


# ------------------------------------------------------------------ the instrument
class TestSidecar(unittest.TestCase):
    def test_the_sidecar_is_the_preregistered_one(self):
        """Construction: spec/M2/lib/audit_round2.json is, byte for byte, the instrument frozen at the prereg."""
        self.assertEqual(hashlib.sha256(SIDECAR.read_bytes()).hexdigest(), SIDECAR_SHA256)


# ------------------------------------------------------------------ the round file (I21-R2)
class TestRound(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = need(ROUND)

    def test_round_validates_and_is_labelled_same_family(self):
        """I21-R2: round2.json validates against the unchanged schema; Q9's default label: same family, not counted
        toward convergence."""
        self.assertEqual(validate(self.r, SCHEMA), [])
        self.assertEqual(self.r["round"], 2)
        self.assertEqual(self.r["milestone"], "M2")
        self.assertEqual(self.r["auditor"]["family"], "same")
        self.assertIs(self.r["auditor"]["counts_toward_convergence"], False)

    def test_attacks_are_the_contracts(self):
        """I21-R2: the attacks are the sidecar's A1..A10 with their categories; each says what it tried; result and
        findings agree; every attack finding is a round finding."""
        got = {a["id"]: a for a in self.r["attacks"]}
        ids = set(self.r["findings"])
        for aid, want in side()["attacks"].items():
            with self.subTest(attack=aid):
                self.assertIn(aid, got)
                a = got[aid]
                self.assertEqual(a["category"], want["category"])
                self.assertTrue(a["tried"].strip())
                self.assertEqual(a["result"] == "finding", bool(a["findings"]))
                self.assertLessEqual(set(a["findings"]), ids)

    def test_surface_findings_are_listed_by_their_attack(self):
        """I21-R2: every unexplained mismatch and every panic finding of a surface is listed by that surface's
        attack; every A4 law and hypothesis finding by A7 and A8."""
        a2, a4 = need(A2), need(A4)
        got = {a["id"]: set(a["findings"]) for a in self.r["attacks"]}
        for aid, want in side()["attacks"].items():
            if "surface" not in want:
                continue
            s = surface(a2, want["surface"])
            fs = {m["finding"] for m in s["mismatches"] if m["class"] == "unexplained"}
            fs |= {p["finding"] for p in s["panics"] if p.get("finding")}
            with self.subTest(attack=aid):
                self.assertLessEqual(fs, got.get(aid, set()))
        self.assertLessEqual({v["finding"] for v in a4["laws"].values() if v.get("finding")}, got.get("A7", set()))
        self.assertLessEqual({v["finding"] for v in a4["hypotheses"].values() if v.get("finding")},
                             got.get("A8", set()))

    def test_round_findings_are_the_ledgers_round2_lines(self):
        """I21-R2: findings is exactly the set of audit/M2_findings.jsonl lines filed by this round."""
        self.assertEqual(sorted(self.r["findings"]), sorted(round2_ids()))

    def test_target_commit_is_an_ancestor_holding_the_i20_outputs(self):
        """I21-R2: the audited commit is an ancestor of HEAD and holds I20's outputs; a2.json and a4.json audit the
        same commit."""
        t = target()
        p = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", t, "HEAD"], capture_output=True)
        self.assertEqual(p.returncode, 0, f"{t} is not an ancestor of HEAD")
        for path in I20_OUTPUTS:
            with self.subTest(path=path):
                git("cat-file", "-e", f"{t}:{path}")
        self.assertEqual(need(A2)["target_commit"], t)
        self.assertEqual(need(A4)["target_commit"], t)

    def test_prose_round_exists(self):
        """I21-R2: the prose round states what was tried, not only the verdict, and carries the family label."""
        text = PROSE.read_text(encoding="utf-8") if PROSE.is_file() else ""
        self.assertGreater(len(text), 2000)
        self.assertIn("same", text)


# ------------------------------------------------------------------ the findings ledger (I21-R2, I21-R6)
class TestFindingsLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need(ROUND)
        cls.fs = findings()

    def test_earlier_lines_keep_their_ids_and_order(self):
        """I21-R2: the file is append-only: audit round M2/1's 37 findings keep their ids, in order."""
        self.assertEqual([f["id"] for f in self.fs[:37]], ROUND1_IDS)

    def test_round2_lines_are_well_formed(self):
        """I21-R2: the round's lines continue the numbering, contiguous, with the contract's fields."""
        ids = [f["id"] for f in self.fs]
        self.assertEqual(len(ids), len(set(ids)))
        mine = [f for f in self.fs if f.get("round") == "M2/round2"]
        nums = [int(f["id"].rsplit("-", 1)[1]) for f in mine]
        if nums:
            self.assertEqual(nums, list(range(nums[0], nums[0] + len(nums))))
            self.assertGreater(nums[0], 37)
        for f in mine:
            with self.subTest(finding=f["id"]):
                self.assertRegex(f["id"], r"^F-M2-\d{2}$")
                self.assertIn(f["severity"], SEVERITIES)
                self.assertIn(f["category"], CATEGORIES)
                self.assertIn(f["status"], STATUSES)
                self.assertRegex(f["fix_iteration"], r"^I\d+$")
                self.assertIsInstance(f["confirmed_by_reproduction"], bool)
                for k in ("title", "reproduction", "iteration_audited", "aspect"):
                    self.assertTrue(str(f.get(k) or "").strip(), k)

    def test_fixed_round2_findings_name_a_test(self):
        """I21-R2: a fixed finding names the test that pins its fix (P6)."""
        for f in self.fs:
            if f.get("round") != "M2/round2" or f["status"] != "fixed":
                continue
            with self.subTest(finding=f["id"]):
                m = re.fullmatch(r"(tests_m\d+/test_\w+\.py)::(\w+)(?:\.(\w+))?", f.get("test") or "")
                self.assertIsNotNone(m)
                src = (ROOT / m.group(1)).read_text(encoding="utf-8")
                self.assertRegex(src, rf"\b(class|def) {m.group(3) or m.group(2)}\b")

    def test_f_m2_36_is_resolved_by_the_round(self):
        """I21-R6: F-M2-36 (CODEC partiality, fix_iteration I21) is reproduced or refuted by A1-A4 and not left open
        under I21."""
        f = next(x for x in self.fs if x["id"] == "F-M2-36")
        self.assertIn("M2/round2", str(f.get("resolution") or ""))
        if f["status"] == "open":
            self.assertIs(f["confirmed_by_reproduction"], True)
            self.assertNotEqual(f["fix_iteration"], "I21")


class TestExit(unittest.TestCase):
    def test_no_open_high_finding(self):
        """I21-R6 (exit): zero open high-severity findings in audit/M2_findings.jsonl before I22."""
        need(ROUND)
        self.assertEqual([f["id"] for f in findings() if f["severity"] == "high" and f["status"] == "open"], [])

    def test_audit_status_reports_nothing_blocking(self):
        """I21-R6 (exit): `holon audit status --findings audit/M2_findings.jsonl` exits 0 with nothing blocking."""
        need(ROUND)
        p = run_holon(["audit", "status", "--findings", "audit/M2_findings.jsonl", "--json"])
        self.assertEqual(p.returncode, 0, p.stdout[-1000:] + p.stderr[-1000:])
        self.assertEqual(json.loads(p.stdout)["blocking"], [])


# ------------------------------------------------------------------ auditor A2: the header carrier
class TestHostileHeaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a2 = need(A2)
        cls.side = side()

    def test_solidity_loader_matches_its_extracted_and_frozen_partiality(self):
        """I21-P1: through each of the 9 non-dominated _loadBatchHeader call sites (:230 importGenesisBatch, :259
        commitBatch, :277 commitState, :402 and :414 commitBatchWithProof, :433 revertBatch, :600 proveState, :627
        finalizeBatch, :716 proveCommittedBatchState; :309 dominated), the real contract accepts or rejects each of
        the 2561 hostile headers exactly as the extracted load_sol path its bytes select, with that path's revert
        reason, and as the frozen ok_sol on the compiled model: 0 mismatches. The observed reverts are exactly the 4
        extracted reasons."""
        sc = self.side["surfaces"]["sol_loader"]
        s = surface(self.a2, "sol_loader")
        self.assertEqual(s["mismatches"], [])
        self.assertLessEqual({EXTRACTED_HDR + "#load_sol", FROZEN_HDR + "#ok_sol"}, set(s["models"]))
        n = self.side["header_corpus"]["size"]
        for cs in sc["call_sites"]:
            with self.subTest(site=cs["line"]):
                e = entry(s, cs["entry"], f"{ROLLUP}:{cs['line']}")
                self.assertGreaterEqual(e["inputs"], n)
                self.assertFalse(e.get("dominated_by"))
        for d in sc["dominated"]:
            e = entry(s, d["entry"], f"{ROLLUP}:{d['line']}")
            self.assertEqual(sorted(e["dominated_by"]), sorted(f"{ROLLUP}:{x}" for x in d["by"]))
        self.assertEqual(set(s["outcomes"]), {"ok"} | {"revert:" + r for r in sc["reasons"]})

    def test_go_header_methods_match_their_extracted_paths(self):
        """I21-P2: each of the 16 exported BatchHeaderBytes methods of morph-l2/common/batch and the 15 of
        morph-l2/node/types returns, on each of the 2561 hostile byte strings, what the extracted path its input
        selects says (nil or non-nil error; on a nil error, the value of the decoder's reads); validate agrees with the
        frozen ok_go and the getters with the frozen dec_go on the compiled model: 0 mismatches, 0 panics."""
        sc = self.side["surfaces"]["go_header"]
        s = surface(self.a2, "go_header")
        self.assertEqual(s["mismatches"], [])
        self.assertEqual(s["panics"], [])
        self.assertLessEqual(set(sc["models"]), set(s["models"]))
        self.assertLessEqual(set(s["outcomes"]), {"ok", "error"})
        n = self.side["header_corpus"]["size"]
        for pkg, v in sc["packages"].items():
            for m in v["methods"]:
                name = f"({pkg}.BatchHeaderBytes).{m}"
                with self.subTest(method=name):
                    self.assertGreaterEqual(entry(s, name)["inputs"], n)


# ------------------------------------------------------------------ auditor A2: codec partiality
class TestCodecPartiality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a2 = need(A2)

    def test_only_enc_sol_has_a_partiality_label_the_code_contradicts(self):
        """I21-P3: of the CODEC edges of gen/M2/diagram/morph_header.json, exactly CODEC.enc_sol has a partial label
        (false) the real code contradicts; dec_go (partial) and enc_go_v0/v1 (total) agree. This reproduces F-M2-36."""
        diag = at_target("gen/M2/diagram/morph_header.json")
        codec = {e["id"]: e["partial"] for e in diag["edges"] if e["kind"] == "CODEC"}
        labels = self.a2["codec_labels"]
        self.assertEqual(set(labels), set(codec))
        for k, v in labels.items():
            with self.subTest(edge=k):
                self.assertIs(v["diagram_partial"], codec[k])
                self.assertIsInstance(v["real_partial"], bool)
        self.assertEqual(sorted(k for k, v in labels.items() if v["diagram_partial"] != v["real_partial"]),
                         ["CODEC.enc_sol"])

    def test_enc_sol_is_extracted_exactly_and_the_frozen_domain_misses_only_zero_roots(self):
        """I21-P4: through commitBatch, commitState and commitBatchWithProof, the 1024 encoder inputs meet the
        extracted enc_sol exactly ('invalid version' :293, 'previous state root is zero' :294, 'new state root is
        zero' :295, else past): 0 mismatches. Against the frozen enc_sol the only mismatches are versions 0..2 with a
        zero state root (frozen defined, code reverts), 9 per entry point and 27 in all; versions 3..255 meet the
        frozen UNDEF sentinel."""
        sc = side()["surfaces"]["sol_encoder"]
        s = surface(self.a2, "sol_encoder")
        n = side()["encoder_corpus"]["size"]
        for name in sc["entry_points"]:
            with self.subTest(entry=name):
                self.assertGreaterEqual(entry(s, name)["inputs"], n)
        self.assertEqual(set(s["outcomes"]), {"ok"} | {"revert:" + r for r in sc["reasons"]})
        ext = [m for m in s["mismatches"] if m["model"].startswith(EXTRACTED_HDR)]
        froz = [m for m in s["mismatches"] if m["model"].startswith(FROZEN_HDR)]
        self.assertEqual(ext, [])
        self.assertEqual(len(froz), len(s["mismatches"]))
        for m in froz:
            with self.subTest(mismatch=m["id"]):
                self.assertLessEqual(int(m["input"]["version"]), 2)
                self.assertEqual(m["expected"], "ok")
                self.assertIn(m["real"], ZERO_ROOT_REASONS)
        self.assertEqual({m["real"] for m in froz}, ZERO_ROOT_REASONS)
        # every (entry point, input) with version 0..2 and a zero root, and nothing else: 3 versions x 3 zero patterns
        self.assertEqual(len(froz), 9 * len(sc["entry_points"]))
        self.assertEqual(len({(m["entry"], json.dumps(m["input"], sort_keys=True)) for m in froz}), len(froz))


# ------------------------------------------------------------------ auditor A2: the rollup Act carrier
class TestRollupAct(unittest.TestCase):
    def test_no_unexplained_mismatch_at_the_rollup_act_carrier(self):
        """I21-P5: over the hostile calldata corpus of every action I20's model compiles (at least the 8 modelled
        ones), every disagreement with the real contract on I20's observables is explained by an assumption the
        extracted rollup document states or a coverage-debt entry: 0 unexplained."""
        s = surface(need(A2), "rollup_act")
        reached = {e["name"] for e in s["entry_points"] if e["inputs"] > 0}
        self.assertLessEqual(set(side()["surfaces"]["rollup_act"]["modelled_actions"]), reached)
        assumptions = {a["id"] for a in at_target("spec/M2/facts/morph_rollup.extracted.json")["assumptions"]}
        debts = {d["src"] for doc in at_target("gen/M2/coverage.json")["documents"] for d in doc["debt"]}
        self.assertEqual([m["id"] for m in s["mismatches"] if m["class"] == "unexplained"], [])
        for m in s["mismatches"]:
            with self.subTest(mismatch=m["id"]):
                self.assertIn(m["class"], CLASSES)
                self.assertTrue(m["why"].strip())
                if m["class"] == "implicit":
                    self.assertEqual(m["explained_by"], "A-implicit")
                    self.assertIn("A-implicit", assumptions)
                    self.assertIn(m.get("exemption"), IMPLICIT_EXEMPTIONS)
                elif m["class"] == "debt":
                    self.assertIn(m["explained_by"], debts)
                else:
                    self.assertIn(m["explained_by"], assumptions)


# ------------------------------------------------------------------ auditor A2: the header carrier's Go consumer
class TestGoConsumer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a2 = need(A2)
        cls.sc = side()["surfaces"]["go_consumer"]

    def test_the_281_byte_parents_stop_the_derivation_consumer(self):
        """I21-P13: on the real calldata of the 62172 mainnet commits (I59), UnPackData returns a nil error for every
        one, by the selectors 0xd63b3549 (7574), 0x4a8d544f (12656), 0x428868b5 (40247) and 0x41f756da (1695), and its
        parentBatchHeader hashes to the parent keccak I59 recorded. ParseBatch rejects at its header step
        (BatchIndex, batch_info.go:92:55) exactly the 2954 commits of batches 2..7575 whose parent is a 281-byte
        version-0 header (2953 under 0xd63b3549, decoded at derivation.go:639; 1 under 0x4a8d544f, :617), and no
        commit at the TotalL1MessagePopped step. The pinned Rollup._loadBatchHeader accepts every one of those 2954
        parents. A2 records this as a target finding (bin finding, law L_dom_hdr)."""
        ri = surface(self.a2, "go_consumer")["real_inputs"]
        want = self.sc["real_inputs"]
        self.assertEqual(ri["commits"], want["commits"])
        self.assertEqual(ri["by_selector"], want["by_selector"])
        self.assertEqual(ri["unpack"], {"ok": want["commits"]})
        self.assertEqual(ri["parent_keccak_mismatches"], [])
        rej = ri["rejected"].get("error:header_index", [])
        self.assertEqual(rej, sorted(rej))
        self.assertEqual(len(rej), want["parent_281_v0"]["count"])
        self.assertEqual((rej[0], rej[-1]), (want["parent_281_v0"]["first_batch_index"],
                                             want["parent_281_v0"]["last_batch_index"]))
        sha = hashlib.sha256(",".join(map(str, rej)).encode()).hexdigest()
        self.assertEqual(sha, want["parent_281_v0"]["batch_indices_sha256"])
        self.assertEqual(ri["rejected"].get("error:header_total", []), [])
        self.assertEqual(ri["parse"].get("error:header_index"), len(rej))
        self.assertEqual(sum(ri["parse"].values()), want["commits"])
        self.assertEqual(ri["solidity_on_rejected"], {"ok": len(rej)})
        hits = [t for t in self.a2["target_findings"]
                if t["surface"] == "go_consumer" and t["batch_indices_sha256"] == sha]
        self.assertEqual(len(hits), 1, self.a2["target_findings"])
        t = hits[0]
        self.assertEqual((t["bin"], t["law"], t["inputs"]), ("finding", "L_dom_hdr", len(rej)))
        self.assertEqual((t["solidity"], t["go"]), ("ok", "error:header_index"))
        self.assertEqual(t["entry_points"], [UNPACK, PARSE])

    def test_the_consumer_agrees_with_the_extracted_paths(self):
        """I21-P14: the header corpus inside a well-formed commitBatch calldata under each of the 4 selectors, and the
        62172 real commits, reach UnPackData and ParseBatch. UnPackData returns a nil error with parentBatchHeader
        unchanged and panics at none of its 5 open sites; ParseBatch's header step rejects exactly what the extracted
        BatchIndex and TotalL1MessagePopped paths and the frozen ok_go reject, never at the TotalL1MessagePopped step:
        0 mismatches."""
        s = surface(self.a2, "go_consumer")
        n = side()["header_corpus"]["size"]
        real = self.sc["real_inputs"]["commits"]
        self.assertEqual(s["mismatches"], [])
        self.assertLessEqual(set(self.sc["models"]), set(s["models"]))
        self.assertGreaterEqual(entry(s, UNPACK)["inputs"], 4 * n + real)
        self.assertGreaterEqual(entry(s, PARSE)["inputs"], 4 * n + real)
        self.assertNotIn("error:header_total", s["outcomes"])
        self.assertIn("error:header_index", s["outcomes"])
        bad = [p for p in s["panics"] if p["function"] == UNPACK or p["site"] in self.sc["open_sites"]]
        self.assertEqual(bad, [])

    def test_target_findings_are_well_formed(self):
        """Construction: every target finding has a bin of the finding filter, a surface of the contract, entry points
        and a reason; every real commit the consumer rejects is covered by one."""
        for t in self.a2["target_findings"]:
            with self.subTest(target=t.get("id")):
                self.assertRegex(t["id"], r"^T\d+$")
                self.assertIn(t["bin"], ("finding", "known_limitation"))
                self.assertIn(t["surface"], SURFACES)
                self.assertTrue(t["entry_points"])
                self.assertGreaterEqual(t["inputs"], 1)
                self.assertTrue(t["why"].strip())
        ri = surface(self.a2, "go_consumer")["real_inputs"]
        n_rej = sum(len(v) for v in ri["rejected"].values())
        covered = sum(t["inputs"] for t in self.a2["target_findings"] if t["surface"] == "go_consumer")
        self.assertGreaterEqual(covered, n_rej)


# ------------------------------------------------------------------ auditor A2: Go sites
class TestGoSites(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a2 = need(A2)

    def test_the_open_data_hash_site_panics_through_exported_calls(self):
        """I21-P6: the open site common/batch/batch_data.go:75:36:slice of (*BatchData).DataHash is decided as a
        reachable panic, with a witness that starts at NewBatchData and calls only exported common/batch functions."""
        s = surface(self.a2, "batchdata_act")
        hits = [p for p in s["panics"] if p["site"] == DATAHASH_SITE]
        self.assertTrue(hits, s["panics"])
        p = hits[0]
        self.assertEqual(p["function"], DATAHASH)
        self.assertEqual(p["site_status"], "open")
        calls = [c["call"] for c in p["witness"]]
        self.assertEqual(calls[0], NEW_BATCH_DATA)
        self.assertTrue(calls[-1].endswith(").DataHash"), calls)
        for c in calls:
            with self.subTest(call=c):
                self.assertTrue(c.startswith(("morph-l2/common/batch.", "(*morph-l2/common/batch.",
                                              "(morph-l2/common/batch.")), c)
                self.assertTrue(exported(c), c)

    def test_no_panic_at_a_safe_site(self):
        """I21-P7: no hostile or real input makes a called Go function panic at a site the target commit's Go documents
        mark safe (go_header, go_encoders, batchdata_act, go_consumer); every panic's site_status is the documents'
        status."""
        status = {}
        for d in GO_DOCS:
            fs = at_target(f"spec/M2/facts/{d}.go.extracted.json")["go"]["functions"]
            for v in fs.values():
                for st in v.get("sites", []):
                    status[st["id"]] = st["status"]
        panics = [p for name in GO_SURFACES for p in surface(self.a2, name)["panics"]]
        for p in panics:
            with self.subTest(site=p["site"]):
                self.assertEqual(p["site_status"], status.get(p["site"], "unrecorded"))
        self.assertEqual([p["site"] for p in panics if p["site_status"] == "safe"], [])


# ------------------------------------------------------------------ auditor A2: corpora and records (I21-R3)
class TestCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a2 = need(A2)
        cls.side = side()

    def test_the_preregistered_corpora_are_the_ones_run(self):
        """I21-R3: a2.json names round 2 and the sidecar's seed, and its corpus digests are those of the sidecar's
        definitions (2561 header, 51 act header and 1024 encoder inputs)."""
        sd = self.side
        hdr, act = header_inputs(sd["header_corpus"], sd["seed"]), header_inputs(sd["act_header_corpus"], sd["seed"])
        enc = encoder_inputs(sd["encoder_corpus"])
        self.assertEqual((len(hdr), len(act), len(enc)), (2561, 51, 1024))
        self.assertEqual((self.a2["round"], self.a2["milestone"], self.a2["seed"]), (2, "M2", sd["seed"]))
        self.assertEqual(self.a2["corpora"], {"header": digest(hdr), "act_header": digest(act), "encoder": digest(enc)})

    def test_every_interface_carrier_is_attacked(self):
        """I21-R3: every carrier with interface: true in gen/M2/diagram at the target commit is the carrier of a
        surface that ran inputs; all six contract surfaces are present."""
        for name in SURFACES:
            surface(self.a2, name)
        attacked = {s["carrier"] for s in self.a2["surfaces"].values() if s["inputs"] > 0}
        for path in target_paths("gen/M2/diagram/"):
            if not path.endswith(".json"):
                continue
            doc = Path(path).stem
            for c in at_target(path)["carriers"]:
                if c.get("interface"):
                    with self.subTest(carrier=f"{doc}:{c['id']}"):
                        self.assertIn(f"{doc}:{c['id']}", attacked)

    def test_malformed_encodings_reach_every_solidity_entry_point(self):
        """I21-R3: at least one malformed ABI encoding of each kind per Solidity entry point."""
        kinds = len(self.side["abi_malformed"])
        for name in ("sol_loader", "sol_encoder"):
            s = surface(self.a2, name)
            live = [e for e in s["entry_points"] if not e.get("dominated_by")]
            with self.subTest(surface=name):
                self.assertGreaterEqual(s["abi_rejected"], kinds * len(live))

    def test_every_extracted_path_is_exercised(self):
        """I21-R3: the corpora exercise every extracted path: load_sol 6, enc_sol 5, and the 223 paths of the 31
        exported Go header methods."""
        want = {"sol_loader": self.side["surfaces"]["sol_loader"]["paths"],
                "sol_encoder": self.side["surfaces"]["sol_encoder"]["paths"],
                "go_header": self.side["surfaces"]["go_header"]["paths"]}
        self.assertEqual(want, {"sol_loader": 6, "sol_encoder": 5, "go_header": 223})
        for name, total in want.items():
            with self.subTest(surface=name):
                self.assertEqual(surface(self.a2, name)["paths"], {"covered": total, "total": total})

    def test_mismatch_and_panic_records_are_well_formed(self):
        """I21-R3: every mismatch has a contract class, an explanation exactly when explained, a reason, and a filed
        finding when unexplained; every panic has a site status and a witness."""
        ids = {f["id"] for f in findings()}
        for name, s in self.a2["surfaces"].items():
            for m in s["mismatches"]:
                with self.subTest(surface=name, mismatch=m.get("id")):
                    self.assertIn(m["class"], CLASSES)
                    self.assertEqual(m["explained_by"] is None, m["class"] == "unexplained")
                    self.assertTrue(m["why"].strip())
                    if m["class"] == "unexplained":
                        self.assertIn(m["finding"], ids)
            for p in s["panics"]:
                with self.subTest(surface=name, panic=p.get("site")):
                    self.assertIn(p["site_status"], ("safe", "open", "unrecorded"))
                    self.assertTrue(p["witness"])


# ------------------------------------------------------------------ auditor A4: premises and inhabitants
class TestVacuity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a4 = need(A4)

    def test_every_proved_premised_law_is_satisfiable(self):
        """I21-P8: every PROVED law with an assume premise or a Reach binder among results/M2/L_*.json and
        results/M2/extracted_m1/L_*.json at the target commit has an inhabitant that A4 replays on the compiled model,
        every step succeeding and every premise holding: no unsatisfiable premise."""
        recs = [p for p in target_paths("results/M2/")
                if re.fullmatch(r"results/M2/(extracted_m1/)?L_[^/]+\.json", p)]
        self.assertEqual(sorted(self.a4["laws"]), recs)
        n = 0
        for path in recs:
            v = self.a4["laws"][path]
            rec = at_target(path)
            stmt = at_target(law_file(path))["statement"]
            with self.subTest(record=path):
                self.assertEqual(v["status"], rec["status"])
                self.assertIs(v["premised"], premised(stmt))
                if v["status"] == "PROVED" and v["premised"]:
                    n += 1
                    self.assertIsNotNone(v["inhabitant"])
                    self.assertIs(v["inhabitant"]["replayed"], True)
                    self.assertIs(v["inhabitant"]["premises_hold"], True)
                    self.assertIs(v["satisfiable"], True)
        self.assertGreaterEqual(n, 6, "the 6 PROVED SORT-site laws at least are premised (Reach binders)")

    def test_site_law_inhabitants_are_degenerate_as_predicted(self):
        """I21-P9: under the degenerate rule, exactly 5 of the 6 PROVED SORT-site laws have degenerate inhabitants:
        both L_sort_site_def_bvh_at_* and L_sort_site_def_w_* (initial state), L_sort_site_rollup_441_* and
        L_sort_site_rollup_485_495_* (subtrahend lfi = 0). L_sort_site_rollup_644_660_* is not degenerate."""
        site = {Path(p).stem: v for p, v in self.a4["laws"].items()
                if re.fullmatch(r"results/M2/L_sort_site_[^/]+\.json", p) and v["status"] == "PROVED"}
        self.assertEqual(len(site), 6, sorted(site))
        seen = {}
        for law, v in site.items():
            with self.subTest(law=law):
                deg = [p for p in DEGENERATE_SITE_LAWS if law.startswith(p)]
                rep = [p for p in REPRESENTATIVE_SITE_LAWS if law.startswith(p)]
                self.assertEqual(len(deg) + len(rep), 1)
                if deg:
                    self.assertIs(v["degenerate"], True)
                    self.assertEqual(v["degenerate_reason"], DEGENERATE_SITE_LAWS[deg[0]][0])
                    seen[deg[0]] = seen.get(deg[0], 0) + 1
                else:
                    self.assertIs(v["degenerate"], False)
                    seen[rep[0]] = seen.get(rep[0], 0) + 1
        want = {p: c for p, (_, c) in DEGENERATE_SITE_LAWS.items()}
        want.update(REPRESENTATIVE_SITE_LAWS)
        self.assertEqual(seen, want)

    def test_every_degenerate_site_law_has_a_representative_inhabitant(self):
        """I21-P15: for each of the 5 SORT-site laws with a degenerate inhabitant, A4's representative search (runs of
        at most 6 actions) finds an inhabitant with a non-empty run and a nonzero subtrahend that replays with its
        premises holding; so none of them is a vacuity finding."""
        bound = side()["representative_search"]["max_run_length"]
        n = 0
        for path, v in self.a4["laws"].items():
            law = Path(path).stem
            if not (re.fullmatch(r"results/M2/L_sort_site_[^/]+\.json", path) and v["status"] == "PROVED"):
                continue
            if not any(law.startswith(p) for p in DEGENERATE_SITE_LAWS):
                continue
            n += 1
            with self.subTest(law=law):
                r = v["representative"]
                self.assertIsNotNone(r)
                self.assertTrue(1 <= r["run_length"] <= bound, r)
                self.assertIs(r["replayed"], True)
                self.assertIs(r["premises_hold"], True)
                self.assertGreater(r["site_operands"]["subtrahend"], 0)
                self.assertIsNone(v["finding"])
        self.assertEqual(n, 5)

    def test_degenerate_flags_follow_the_rule(self):
        """Construction: degenerate is the sidecar's rule applied to the recorded inhabitant (empty run, or a SORT-site
        subtrahend of 0), with initial_state winning; null where the rule does not apply."""
        for path, v in self.a4["laws"].items():
            inh = v.get("inhabitant")
            with self.subTest(record=path):
                if not (v["status"] == "PROVED" and v["premised"] and inh):
                    self.assertIsNone(v["degenerate"])
                    continue
                is_site = Path(path).stem.startswith("L_sort_site_")
                if is_site:
                    self.assertIsNotNone(inh["site_operands"])
                zero = is_site and inh["site_operands"]["subtrahend"] == 0
                want = "initial_state" if inh["run_length"] == 0 else ("zero_subtrahend" if zero else None)
                self.assertIs(v["degenerate"], want is not None)
                self.assertEqual(v["degenerate_reason"], want)
                if want is None:
                    self.assertIsNone(v["representative"])
                elif v["representative"] is None:
                    self.assertIsNotNone(v["finding"], "a degenerate inhabitant with no representative is a finding")


# ------------------------------------------------------------------ auditor A4: hypotheses against real oracles
class TestHypotheses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = need(A4)["hypotheses"]

    def test_every_hypothesis_has_a_verdict(self):
        """I21-P10: every key of results/M2/hypotheses.json at the target commit (at least the 12 at the prereg) is
        tested against an implementation of the real oracle outside holon/ and tests/, or labelled untestable with the
        missing piece named."""
        keys = set(at_target("results/M2/hypotheses.json"))
        self.assertLessEqual(set(side()["hypotheses"]), keys)
        self.assertEqual(set(self.h), keys)
        ids = {f["id"] for f in findings()}
        for k, v in self.h.items():
            with self.subTest(hypothesis=k):
                self.assertIn(v["verdict"], ("tested", "untestable"))
                if v["verdict"] == "tested":
                    self.assertIn(v["result"], ("pass", "fail"))
                    impl = (v.get("implementation") or "").strip()
                    self.assertTrue(impl)
                    self.assertFalse(impl.startswith(("holon/", "tests/")), impl)
                    self.assertNotIn("holon/keccak", impl)
                    self.assertTrue(v["test"].strip())
                    if v["result"] == "fail":
                        self.assertIsNotNone(v["counterexample"])
                        self.assertIn(v["finding"], ids)
                else:
                    self.assertIsNone(v["result"])
                    self.assertTrue((v.get("reason") or "").strip())

    def test_four_hypotheses_pass_against_real_oracles(self):
        """I21-P11: CF-agg (at least the 273-value sample), CF-hdr (at least 768 in-domain headers, Solidity and Go
        batch hashes), Hyp-Z0-kzg (the KZG library of the pinned Go module graph) and Hyp-messenger (the real
        messenger and message queue) are tested and pass."""
        for k in PASSING_HYPOTHESES:
            with self.subTest(hypothesis=k):
                self.assertEqual((self.h[k]["verdict"], self.h[k]["result"]), ("tested", "pass"))
        self.assertGreaterEqual(self.h["CF-agg"]["sample"], 273)
        self.assertGreaterEqual(self.h["CF-hdr"]["sample"], 768)

    def test_the_submitter_hypothesis_fails_against_submitter_sol(self):
        """I21-P12: Hyp-ISubmitter, tested against the real Submitter.sol, fails: a reachable Submitter state where
        isActive is not 'staked and unslashed', or challengeDeposit() is not its initial value; filed as a finding."""
        v = self.h["Hyp-ISubmitter"]
        self.assertEqual((v["verdict"], v["result"]), ("tested", "fail"))
        self.assertIn("Submitter.sol", v["implementation"])
        self.assertTrue(v["counterexample"])
        self.assertIn(v["finding"], round2_ids())


# ------------------------------------------------------------------ the instruments' sensitivity (I21-R4)
class TestSensitivity(unittest.TestCase):
    def test_every_surface_has_a_detected_mutant(self):
        """I21-R4: at least one planted partiality mutant per surface, and every planted mutant is detected."""
        ms = need(A2)["mutants"]
        for name in SURFACES:
            with self.subTest(surface=name):
                mine = [m for m in ms if m["surface"] == name]
                self.assertTrue(mine)
                for m in mine:
                    self.assertIs(m["detected"], True, m["mutation"])
                    self.assertGreaterEqual(m["mismatches"], 1)

    def test_every_a4_canary_is_detected(self):
        """I21-R4: the unsatisfiable-premise, degenerate-inhabitant and false-hypothesis canaries are all flagged."""
        cs = need(A4)["canaries"]
        self.assertLessEqual({"unsatisfiable_premise", "degenerate_inhabitant", "false_hypothesis"},
                             {c["kind"] for c in cs})
        for c in cs:
            with self.subTest(canary=c["kind"]):
                self.assertIs(c["detected"], True, c.get("what"))


# ------------------------------------------------------------------ determinism (I21-R5)
class TestDeterminism(unittest.TestCase):
    def test_hostile_reproduces_from_the_target_commit(self):
        """I21-R5: `holon audit hostile --check` rebuilds a2.json from the target commit byte for byte."""
        need(A2)
        p = run_holon(["audit", "hostile", "--milestone", "M2", "--round", "2", "--check"], timeout=7200)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])

    def test_vacuity_reproduces_from_the_target_commit(self):
        """I21-R5: `holon audit vacuity --check` rebuilds a4.json from the target commit byte for byte."""
        need(A4)
        p = run_holon(["audit", "vacuity", "--milestone", "M2", "--round", "2", "--check"], timeout=7200)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])


if __name__ == "__main__":
    unittest.main()
