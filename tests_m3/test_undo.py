"""I27: the UNDO rule and static deadness, decided on the extracted real code (whitepaper §5.2, §10.6, Thm 6.9, §8.4 UNDO
row, §10.4 UNDO row, App. E UNDO row, App. F UNDO sketch, §2.3, §11.6 D5, §11.8; BUILD_PLAN I27; docs/HUMAN_ANSWERS.md
Q19: extracted facts are the input of every M3 law). This docstring is the contract.

Why. The M1 UNDO laws (laws/M1/L_undo_*) are statements over the hand abstraction, and I20 re-decided them over
gen/M2/extracted/m1_view.json, the hand abstraction minus the guard_missing requires. Both independent catalog reviews of
the mutation track (docs/iterations/I22_catalog_review.json, I60_catalog_review.json) found that this makes every
drop_delete and swap_cursor mutant of the real Rollup unkillable by construction: no law reads the real code's writes.
Here the undo pairs, the residues and their static classification are computed from the extracted transitions (written
values, deletes, guards, events), every law is stated over the extracted model (I30's typed model with Reach), decided
by the M3 pipeline, and every REFUTED law carries a witness that replays on the real contract. A real-code defect such as
a dropped delete must move a law: the Sensitivity clause makes that a test.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment in
spec/M3/amendments.jsonl): spec/M3/lib/undo.json (the UNDO sidecar: the model sidecar it builds on, the observation, the
premise, the search budget, the back-test map); spec/M3/lib/undo_basis.json (every pair, residue, classification, law and
predicted outcome on the rollup document, and the mutant's analysis, computed at the prereg by undo_basis_doc below,
which writes rules U1-U6 and D1-D3 a second time, independently of holon/); tests_m3/fixtures/undo/ (the planted ToyUndo,
its drop variant without one delete, their extraction sidecars and documents extracted by holon's frontend, bindings,
I30-format and UNDO sidecars and the toy harness; mutant/: the pinned Rollup without line 447, its extraction sidecar and
document); tests_m3/fixtures/undo/harness/*.txt (byte copies of the I20 step harness taken at this prereg, for the
independent replay below).

Scope and inputs
  - Milestone M3. The documents are the transitions documents of the model sidecar the UNDO sidecar names
    ("sort_types": spec/M3/lib/sort_types.json, I30's): spec/M2/facts/morph_rollup.extracted.json (I19/A19, adopted by
    I20; G1 re-extracts it). Its model is its file name without ".json": morph_rollup.extracted; its contract the
    document's "contract": Rollup. Reach's initial state, the witnesses' real side and the hash binders are I30's
    (tests_m3/test_sort_types.py, clauses N9, Refutation and Replay): the binding replay/M2/fragments.json.
  - No hand-written fact document is read by an I27 command (spec/M1/facts/, facts/, spec/M1/lib/, gen/M2/sorts/,
    gen/M2/extracted/m1_view.json). The back-test alone reads laws/M1/L_undo_*.json and results/M1/L_undo_*.json.
  - Never edit spec/M1/, spec/M2/facts/, spec/M2/lib/, laws/M0-M2, gen/M0-M2, results/M0-M2, replay/M1, replay/M2 or a
    frozen file. I20's differential (results/M2/differential.json, the M1 laws over m1_view) is not re-decided.

Registers and terms (U1)
  A register is a storage family of the document (storage and inherited_storage) at a key: a scalar family is one
  register; a mapping family's register at key k is its whole value there (a struct value with every member). A struct
  member path is part of its register. Compiler-generated getters of public state variables are not actions of the
  document and are not observed (they expose every family by construction; M1's UNDO laws excluded them too).
  In a holon-facts/0.3 document ["storage", F] denotes F's value before the transaction (assumption A-env), and the
  extractor resolves a read that follows a write in the same action to the value written. So every occurrence of
  ["storage", F], or of ["carried", span, ["storage", F]] inside a loop record, is a read of F's pre-transaction value;
  its key is the third element of the enclosing ["map", <that term>, key] (none for a bare scalar read).
  Conjuncts: a term ["&&", x, y, ..] splits recursively into the conjuncts of its operands; any other term is one.
  Guard reaches: guards[i].reaches[j] (kinds modifier, require, revert), each with expr and seq; "before" is a smaller
  seq (the extractor's walk order). A write record has family, path ([] a scalar, [["map", k]] a whole register, longer:
  a member), value, cond, seq and optionally loop (its loop record's seq). Its key is k (none for a scalar); it is whole
  when its path has at most one element; unconditional when cond is 1, or when it is in a loop whose cond is 1 and its
  cond equals the loop's head (the body, first iteration); final when no later write of the same action writes the same
  family whole at the syntactically same key. Keys of two different actions match unless both are integer literals that
  differ; a key is first normalized: ["iter", span] reads 0, ["carried", span, x] reads x, x + 0 reads x.

Undo pairs (U2-U4; whitepaper §5.2)
  U2 Pins. Action a pins register (F, k) to the literal c at a guard reach whose expr has a top-level conjunct
     ["==", R, c] or ["==", c, R] (c an integer literal), ["!", R] (c = 0), or, for a family of value type bool, R itself,
     ["!=", R, 0] or ["!=", 0, R] (c = 1); R is ["map", ["storage", F], k] (["storage", F] for a scalar F). A conjunct on a
     struct member does not pin the register. Record: {"family", "key", "literal", "seq", "at": "guards[i]"}.
  U3 Restores. ā restores a's write w (w final, cond 1) of register (F, k_a) when either
     literal: w is whole and fresh (its value reads no ["storage", F]), a pins (F, k_a) (the same key term) to c at a
        guard reach before w, w's value is not the literal c, and ā has an unconditional whole write of F whose value is
        the literal c at a key matching k_a ("how": "zero" when c is 0, else "literal"); or
     cursor: F is a scalar family of value type uint*, w's value is ["+", t, n] (either order; n an integer literal >= 1)
        where t is ["storage", F] or a guard reach of a before w has a top-level conjunct ["==", t, ["storage", F]] (either
        order), and ā has an unconditional write of F whose value is ["-", t', n] with the same n ("how": "cursor").
     Record: {"family", "a_write": "writes[i]", "undo_write": "writes[j]", "how", "pin": "guards[g]" or null}.
  U4 Detection. An ordered pair (a, ā) of distinct actions, neither of mutability view or pure, is an undo pair when ā
     restores at least one write of a and at least one criterion holds:
       guard   a guard reach of ā before one of its restoring writes reads the restored family at a key matching a's key
               of it (any read, for a scalar): ā's guard references a's write;
       cursor  a restore is a cursor restore: ā restores a cursor that a advanced;
       event   an event of a with cond 1 and an unconditional event of ā (as for writes: cond 1, or in a loop whose cond
               is 1 with cond equal to the loop's head) have different names, the same parameter type list (the
               signature's text inside the parentheses) and the same indexed flags: ā emits an inverse event.
     A pair with a restore and no criterion is rejected, reason "no_criterion". A pair (a, a) is never detected (gap G1).
  U5 Residues (Res(a, ā) of §5.2): the families of a's final writes that ā does not restore (U3) and that are not
     identity writes (a whole write whose value is exactly the read of its own register at its own key), sorted. ā's
     writes to registers a does not write are its side effects, not residues (the pair law covers them). I30's generated
     ghost companions are not registers of the document and are never residues (Prop 6.19; gap G2).
  U6 Residue bases: one per (ā, F) over the pairs that leave the residue F: "cursors" the families ā restores by cursor
     in those pairs, "zero" the mapping families G != F that ā writes whole with the literal 0 unconditionally, "pairs"
     the actions a; each sorted. The residue's context at a key k: C < k for each cursor C, G[k] == 0 for each zero family
     G (after ā the residue sits above the cursor ā restored, in a slot whose existence markers ā cleared).

Static deadness (D1-D3; whitepaper §10.6: a key-sensitive backward analysis, index variables kept symbolic)
  For a residue basis (ā, F, C, Z) every read of F in every action b of the document, views included, is located in a
  record of b; the records and their scanned fields, in scan order: guards[i].reaches[j] (expr, args), checks[i] (expr),
  panics[i] (expr, args), calls[i] (expr, args, receiver, value, cond), writes[i] (value, cond, path), events[i] (args,
  cond, topics), mstores[i] (value, cond, offset), loops[i] (head, cond, bound, count), then "returns" (the action's
  returns term, after every record). The other sections (post, cost, effects, edges, order, params, principal,
  modifiers) and the loop fields carried, next, exit, at_break, regions, returns and steps restate these and are not
  scanned.
  FalseAt(x, rho), for a read at key rho: x is ["==", rho, S], ["==", S, rho], ["<=", rho, S], ["<", rho, S],
  [">=", S, rho] or [">", S, rho] with S = ["storage", C] for a cursor C (rho <= C < k: a cursor form); or x is
  ["!=", Zr, 0], ["!=", 0, Zr], ["!", ["==", Zr, 0]] or ["!", ["==", 0, Zr]] with Zr = ["map", ["storage", G], rho] or
  ["member", ["map", ["storage", G], rho], m] for a zero family G (G[k] == 0: a zero form). rho is compared
  syntactically. The dominating conjuncts of a record: the top-level conjuncts of every guard reach of b with a smaller
  seq, of the record's own cond, and of the head and cond of its loop.
  A read at key rho is excluded by D1 (at or below the cursor) when rho is ["storage", C] for a cursor C or a dominating
  conjunct is FalseAt in a cursor form; else by D2 (dominated by a cleared marker) when a dominating conjunct is FalseAt in
  a zero form; else by D3 (masked) when an ancestor ["&&", ..] of the read has another operand one of whose top-level
  conjuncts is FalseAt (either form). A read without a key (scalar F) is never excluded. A record holding a read not
  excluded is a live reader {"action", "at"}; a record all of whose reads are excluded is listed in "excluded"
  {"action", "at", "rules": its rules, sorted}. Readers in scan order (document action order, then the order above).
  The residue is dead iff it has no live reader, else live. A pair is dead iff every residue of it is dead (a pair with
  no residue is dead). Soundness is not claimed: the context is assumed to persist until the residue is overwritten; the
  kernel decides, and a disagreement is reported (gap G6).

The analysis (holon/rules/undo.py: U1-U6; holon/analysis/deadness.py: D1-D3)
  python -m holon undo --milestone M [--root DIR] [--undo-sidecar PATH] [--facts PATH ..] [--out DIR] writes
  <out, default gen/<M>/undo>/<model>.json for every document of the sidecar (default spec/<M>/lib/undo.json), or of
  --facts (planted documents): {"document": "undo", "undo_version": "holon-undo/0.1", "milestone", "model", "contract",
  "facts", "facts_sha256", "inputs": [{"path", "sha256"}] sorted, "pairs": [{"a", "undo", "criteria", "restores",
  "residues", "class"}] sorted by (a, undo), "rejected": [{"a", "undo", "restores", "reason"}] sorted by (a, undo),
  "residues": [{"undo", "family", "pairs", "cursors", "zero", "class", "live_readers", "excluded"}] sorted by (undo,
  family)}; restores sorted by canonical JSON. Exit 0 written; 2 refused, nothing written (a sidecar or document missing
  or malformed); 1 an unreadable input. --classify writes results/<M>/undo/classification.json (after the run);
  --backtest writes results/M3/undo/backtest.json. Every file: json.dumps(obj, indent=2, sort_keys=True) + "\\n";
  deterministic, no timestamps, no absolute paths.

Laws (rule UNDO; law ids a deterministic function of rule, subform and basis, BUILD_PLAN §2.3)
  Catalog. holon/rules/__init__.py: CATALOGS gains "holon-rules/1.3", whose rules are those of the catalog M3 derives
  with before I27 (holon-rules/1.1's PAR producers and I30's SORT producers, the same producer objects) plus
  "UNDO": {"pair": .., "residue": ..} (holon.rules.undo.PRODUCERS); catalog_version("M3") == "holon-rules/1.3" (and
  for every later M<k>); every earlier version and M2's catalog unchanged; test milestones keep their catalog and take
  holon-rules/1.3 through derive's --catalog (T271, T272).
  L1 One pair law per undo pair: law id "L_undo_pair_<contract>_<a>_<undo>"; basis {"kind": "undo_pair", "model",
     "contract", "a", "undo", "criteria", "restores", "residues"}.
  L2 One residue law per residue basis: law id "L_undo_res_<contract>_<undo>_<family>"; basis {"kind": "undo_residue",
     "model", "contract", "undo", "family", "cursors", "zero", "pairs"}.
  Undo id "<model>:pair:<a>:<undo>" or "<model>:residue:<undo>:<family>". Two bases with one id: derive error, exit 3.
  Law IR (holon-ir/0.3, laws/<M>/<law_id>.json): {"ir_version": "holon-ir/0.3", "law_id", "milestone", "rule": "UNDO",
  "subform": "pair" | "residue", "rule_catalog_version": "holon-rules/1.3", "facts", "facts_sha256", "notes",
  "statement": {"binders": B, "assume": [], "claim": {"eq": [{"undo": <undo id>, "on": [{"var": b} for each binder b,
  in order]}, {"bool": true}]}, "scope": {"kind": "unbounded"}}}; no "evidence", no "predicted". B for a pair law:
  {"q": "forall", "name": n, "type": T} for (s, Reach), (x, Act), (y, Act), (t, Trace); for a residue law (s, Reach),
  (k, Word), (v, "Val[<family>]"), (t, Trace); then the hash binders exactly as I30's laws over the same document have
  them (one Fn binder per hash function the model threads). The undo term is new in IR 0.3 (additive: the IR 0.3 schema
  gains it; holon.ir.render_term renders undo_ok[ID](args)); it is hashed through the ref "undo:<ID>": the sha256 of
  canonical {"template": "holon.rules.undo/<subform>", "template_version": 1, "subform", "basis"}, recomputed from the
  document. canonical(o) = json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False) in UTF-8.
  Semantics of the generated Bool function undo_<x> (x the law id without "L_undo_"):
    pair      with s1 = after(s, x), s2 = after(s1, y): if NZ, x is a call of a, y a call of ā, both steps succeed and
              every register the pair restores (its family at a's write key, evaluated on s and x) holds in s2 its value
              in s, then obs(t, s2) == obs(t, s); otherwise true (App. F's undo law, Thm 6.9).
    residue   if NZ and the context holds at k in s, then obs(t, s) == obs(t, set_F(s, k, v)); otherwise true (Thm
              6.9(i): the relation "equal outside F at k" is a bisimulation; index-relative noninterference).
    obs(t, s) the observations of running t from s, one per step: a successful step {"status": "ok", "ret": its return
              data, "logs": the target's logs in order ({"topics", "data"}), "calls": the target's external calls in order
              ({"to", "data"})}; a reverted step {"status": "revert", "ret": its revert data, "logs": [], "calls": []}
              (bytes as lowercase 0x-hex; a view's return data is observed, gap G4). A reverted step leaves the state
              unchanged.
    NZ        no hash value the steps compute (x, y and t from both states) is the zero word: an unwritten slot reads 0
              and the code compares stored digests with 0 as "absent", so the zero word is the empty-slot sentinel. A
              local premise like CF(h, S) (Cor 6.16): satisfiable, no axiom; the real keccak256 and sha256 values a witness
              holds are nonzero.
    uhit_<x>  the premises alone; a reachable inhabitant of it is the G11V non-vacuity witness of a PROVED law.
  Generated files: gen/M3/undo/models/<model>.bend (the trace section over I30's typed model
  gen/M3/sorts/models/<model>.bend, imported as M: ret_<action> for every action whose document records returns, obs,
  run, set_<family>, and per law undo_<x> and uhit_<x>), gen/M3/laws/<id>/LAWS.bend, gen/M3/proofs/<id>/PROOF.bend for a
  PROVED law or gen/M3/proofs/<id>/witness/PROOF.bend (the counter-law) for a REFUTED one, gen/M3/<id>/nonvac/
  {LAWS,PROOF}.bend. The core library gen/M3/core gains the map lemmas the proofs use (a read at another key is
  unaffected by a write, a read at the written key gives the value, writing back a register's own value is the identity:
  set_d and nth_d), proved, never assumed. No hole, @unsafe, def f?, foreign import or law without proof under gen/M3.
  A PROVED residue law's PROOF.bend imports gen/M3/core/PROOF.bend (the map lemmas, BUILD_PLAN I27 deliverables).
  Each LAWS.bend of an UNDO law declares exactly one law, whose statement names undo_<x> (uhit_<x> in nonvac/); each
  PROOF.bend that decides an UNDO law (its proof, its counter-law under witness/, its nonvac proof) imports that
  LAWS.bend and only files under gen/M3, so a copy of gen/M3 alone checks it.
  DERIVATION.json entry: {"law_id", "rule": "UNDO", "subform", "facts", "basis", "static": residue {"class",
  "live_readers", "excluded"} or pair {"class", "residues": {family: class}}, "statement_hash"}.

Deciding (python -m holon run --milestone M3; a test milestone with --sidecar and --undo-sidecar)
  PROVED: a Bend- and BendTT-checked proof (generators: a pair with no residue, the restore proof; a residue law and a
  pair whose residues are all dead, the noninterference proof: step lemmas per action over the relation "equal outside F
  at k, context at k", with the map lemmas), and a checked reachable inhabitant of uhit_<x> (G11V).
  REFUTED: a Bend- and BendTT-checked counter-law at a concrete witness {"prefix": [steps], "x": step, "y": step,
  "t": [steps], "hashes": {"keccak256": [[key, word], ..], "sha256": ..}} (a residue witness also "k" and "v"), steps in
  I30's witness step format ({"action", "args", "calldata", "env": {"caller", "msg.value", "block.timestamp",
  "blobhash", "calls"}}); s is the state after prefix from Reach's initial state; the hash tables hold the real keccak256
  and sha256 of every key; block.timestamp is never 0 and never decreases along a run; external-call answers are what
  the deployment's dependencies answer. A residue witness is realized by one of its pairs: x is a call of one of its
  pairs' a, y a call of ā, k is x's write key of F and v the value F[k] holds after prefix, x, y; and on the model
  obs(t, set_F(s, k, v)) == obs(t, after(after(s, x), y)): the divergence is F's alone.
  The search (spec/M3/lib/undo.json "search"): I30's argument and environment variants; prefixes breadth first up to
  prefix_depth steps, at most max_prefixes; continuations of at most continuation_depth steps; at most max_candidates
  candidates per law; a deterministic order; the first witness found. UNKNOWN otherwise, the record naming the bound and
  the attempts.

Replay (replay/M3/undo/report.json, written by python -m holon replay --milestone M3, never by hand)
  laws[<id>] for every REFUTED UNDO law: {"with": {"trace": prefix + [x, y] + t, "model": [obs], "real": [obs]},
  "without": {"trace": prefix + t, "model": [obs], "real": [obs]}, "t_at": len(prefix) + 2, "diverges_at": i (the first
  index into t whose observations differ), "calls_agree": bool, "status": "passed" | "failed"}. Each run starts from the
  binding's deployment; the real side is the I20 step harness, one call step per step. passed iff model == real at every
  step of both runs, every external call each real step made equals the witness's env call in order, and t's
  observations first differ at diverges_at on both sides. G6 binds every REFUTED UNDO record to a passed entry.

Records (results/<M>/<law_id>.json): valid under v1 and v2; "undo": {"subform", "undo_id", "static": the DERIVATION
  entry's, "kernel": "dead" (PROVED) | "live" (REFUTED) | "unknown", "agree": static class == kernel}; "premises":
  ["nz:<hash function>" for each hash binder]; "witness" as above for a REFUTED law, else null; "artifacts" (the trace
  module, the law, the proof), "model_sha256" (the trace module's) and "coverage" (I19's field).

Classification and back-test
  results/<M>/undo/classification.json: {"document": "undo_classification", "milestone", "laws": {law_id: {"subform",
  "static", "kernel", "agree", "blocks": [] or ["shadow", "window"]}}, "disagreements": [law ids]}; "kernel" is read
  from the law's record (its status: PROVED dead, REFUTED live, anything else unknown), "static" from DERIVATION.json,
  and a law whose static class differs from its kernel class (unknown included) is a disagreement. The gate regenerates
  it (G1, also under --checks G1) from the records it finds and lists each disagreement under its report's "warnings"
  ({"check": "GUNDO", "law"}, sorted by law), whether or not any check fails; every gate report of M3 carries a
  "warnings" list (empty when nothing warns). A disagreement is a Surprise and blocks window and shadow generation for
  its law (BUILD_PLAN I27 risks and exit: "static and kernel classifications agree, or the gate warns").
  results/M3/undo/backtest.json: {"document": "undo_backtest", "against": "M1", "rows": [{"m1_law", "m1_status",
  "analogue", "analogue_status", "same_status", "reason"}] sorted by m1_law, "gaps": [m1 laws without an analogue]},
  by the frozen map spec/M3/lib/undo.json "backtest": an M1 residue law (undo action, family) or pair law (a, undo),
  names mapped, gives the law id L1/L2 would give; analogue null when laws/M3 holds no such law: a back-test miss, an
  open rule gap (never a hand-written law; M3 exit cannot be claimed while one is open).

Sensitivity (whitepaper §2.3: one live residue forces every future commit to reuse the reverted batch's blob)
  Planted toy, test milestones T271 and T272 (>= 30: I30's M3 machinery applies), catalog holon-rules/1.3 by --catalog,
  sidecars tests_m3/fixtures/undo/{sort_types_toy,undo_toy}.json and tests_m3/fixtures/undo/drop/{sort_types_toy,
  undo_toy}.json. Known by construction from U1-U6 and D1-D3:
    T271 (baseline): one pair (commit, revertLast), criteria [cursor, event, guard], restoring entries (zero, pinned by
      commit's guard "already committed"), pins (zero, pinned by "pinned") and last (cursor); residues roots (dead: D1,
      commit's guard reads it at the cursor) and stamps (dead: D2 for touch's event, behind entries[i] != 0; D3 for
      stampOf's return, masked by it); laws L_undo_pair_ToyUndo_commit_revertLast, L_undo_res_ToyUndo_revertLast_roots,
      L_undo_res_ToyUndo_revertLast_stamps: all PROVED.
    T272 (the one line `delete pins[i]; // RESIDUE-CLEARING DELETE` removed): the same pair and criteria, restoring
      entries and last; residues pins (live: commit's guard "pinned" reads it at last + 1), roots and stamps (dead); laws:
      the same pair law id REFUTED (commit with a nonzero pin, revertLast, then commit reverts "pinned" with the pair and
      succeeds without it), L_undo_res_ToyUndo_revertLast_pins REFUTED, roots and stamps PROVED. Every REFUTED toy
      witness replays on the real drop toy (checked independently of holon, through the harness copies): the two runs
      first differ at a commit step of t, which reverts "pinned" in the run with the pair and succeeds in the run
      without it.
  Real code, static: tests_m3/fixtures/undo/mutant/rollup_mutant.extracted.json is holon's frontend run on a copy of the
  pinned checkout without Rollup.sol:447 (`committedBatches[_batchIndex] = bytes32(0);`, revertBatch's delete of the
  register commit allocates), sidecar tests_m3/fixtures/undo/mutant/extract_rollup_mutant.json; `holon undo --milestone
  M3 --facts <it>` gives the pairs, rejected pairs and residues undo_basis.json "sensitivity" lists.

Gaps preregistered
  G1 Self pairs are not detected: a function whose branches undo each other (a pause flag set and cleared by one
     function, setPause(true) and setPause(false)) is one action.
  G2 The whitepaper's fourth residue, the tag, is a ghost of I30's typed model, not a register of the document: O26 is
     decided by I30's as_member laws, not here.
  G3 Balances and other A-env state are not registers: a value attached to a commit and kept after its revert is not seen.
  G4 Compiler-generated getters are not observed (as in M1); a declared view's return data is.
  G5 L_undo_cancel (challengeState, setPause) has no analogue: setPause's writes of inChallenge and challenges are
     conditional on its argument and on inChallenge (no restore, U3), and its guards read only _owner and _paused (no
     criterion, U4). A back-test miss and an open rule gap.
  G6 Static soundness is not claimed (above).

Rules (AGENTS.md is binding): generate, never hand-write (laws only from holon/rules, with DERIVATION.json); no target,
  family, action, span or law id under holon/; never tune to a prediction (the sidecars and budgets are fixed); witnesses
  come from the compiled model; the real contract decides replay; no skips.

Residual risk, stated: the tests_m2 helpers this file imports (tests_m2/_i15.py: the Foundry toolchain check;
  tests_m2/_i16.py: the pinned checkout; tests_m2/_keccak.py) are fingerprinted only under the M2 keys that preregistered
  them. The instrument below shares no code with holon/, but it was written by the same author as the contract.
"""
from __future__ import annotations

import hashlib
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
from tests_m2 import _i15 as I15   # I15's Foundry toolchain check (fixed at the I15 prereg)
from tests_m2._i16 import morph_checkout
from tests_m2._keccak import keccak256

M3 = "M3"
DOC_REL = "spec/M2/facts/morph_rollup.extracted.json"
MODEL = "morph_rollup.extracted"
CONTRACT = "Rollup"
UNDO_SIDECAR = "spec/M3/lib/undo.json"
SORT_SIDECAR = "spec/M3/lib/sort_types.json"
BASIS_REL = "spec/M3/lib/undo_basis.json"
CATALOG = "holon-rules/1.3"
SUBFORMS = ("pair", "residue")
LAWS3 = ROOT / "laws" / M3
RESULTS3 = ROOT / "results" / M3
GEN3 = ROOT / "gen" / M3
ANALYSIS = GEN3 / "undo" / f"{MODEL}.json"
CLASSIFICATION = RESULTS3 / "undo" / "classification.json"
BACKTEST = RESULTS3 / "undo" / "backtest.json"
REPLAY3 = ROOT / "replay" / M3 / "undo" / "report.json"
ROLLUP_SRC = "contracts/contracts/l1/rollup/Rollup.sol"

# the Morph predictions, as numbers (spec/M3/lib/undo_basis.json holds the full computation)
PAIRS = [("addChallenger", "removeChallenger"), ("commitBatch", "revertBatch"), ("commitBatchWithProof", "revertBatch"),
         ("commitState", "revertBatch"), ("removeChallenger", "addChallenger")]
REJECTED = [("challengeState", "proveState"), ("commitBatch", "finalizeBatch")]
RESIDUES = {("addChallenger", "removeChallenger"): [],
            ("commitBatch", "revertBatch"): ["batchBlobVersionedHashes", "batchDataStore", "committedStateRoots"],
            ("commitBatchWithProof", "revertBatch"): ["batchBlobVersionedHashes", "batchDataStore",
                                                      "committedStateRoots"],
            ("commitState", "revertBatch"): ["batchDataStore", "committedStateRoots"],
            ("removeChallenger", "addChallenger"): []}
CLASSES = {"batchBlobVersionedHashes": "live", "batchDataStore": "live", "committedStateRoots": "dead"}
PREDICTED = {   # law id -> (subform, predicted status)
    "L_undo_pair_Rollup_addChallenger_removeChallenger": ("pair", "PROVED"),
    "L_undo_pair_Rollup_commitBatch_revertBatch": ("pair", "REFUTED"),
    "L_undo_pair_Rollup_commitBatchWithProof_revertBatch": ("pair", "REFUTED"),
    "L_undo_pair_Rollup_commitState_revertBatch": ("pair", "REFUTED"),
    "L_undo_pair_Rollup_removeChallenger_addChallenger": ("pair", "PROVED"),
    "L_undo_res_Rollup_revertBatch_batchBlobVersionedHashes": ("residue", "REFUTED"),
    "L_undo_res_Rollup_revertBatch_batchDataStore": ("residue", "REFUTED"),
    "L_undo_res_Rollup_revertBatch_committedStateRoots": ("residue", "PROVED"),
}
M1_UNDO = {"L_undo_BD": "PROVED", "L_undo_BVH": "REFUTED", "L_undo_CSR": "PROVED", "L_undo_cancel": "REFUTED"}
M1_UNDO_HASHES = {   # results/M1/L_undo_*.json statement_hash at the prereg
    "L_undo_BD": "sha256:3c8a37fdd3f483f21e5d91caa8ebf89b4e501e9bdd6d159559d87a5760dcfb47",
    "L_undo_BVH": "sha256:dcfe90c619bcc087d54a84b2f80b1b8b8f66ba395e22099ddd5c4db211a3c09e",
    "L_undo_CSR": "sha256:495a29ac6d11b350f95c4edc18fd0b7d9193c2f6a2f4b7e7a1d68156c221cf6b",
    "L_undo_cancel": "sha256:6f08f24ef596df34f2a4a2d295880a53ed3651416b77ff5d639c03a7d99665fc",
}

# the planted toy (Sensitivity)
FIX_REL = "tests_m3/fixtures/undo"
FIX = ROOT / FIX_REL
TOY = {"T271": {"dir": FIX_REL, "doc": f"{FIX_REL}/toyundo.extracted.json",
                "sort": f"{FIX_REL}/sort_types_toy.json", "undo": f"{FIX_REL}/undo_toy.json"},
       "T272": {"dir": f"{FIX_REL}/drop", "doc": f"{FIX_REL}/drop/toyundo.extracted.json",
                "sort": f"{FIX_REL}/drop/sort_types_toy.json", "undo": f"{FIX_REL}/drop/undo_toy.json"}}
TOY_MODEL = "toyundo.extracted"
TOY_PAIR = "L_undo_pair_ToyUndo_commit_revertLast"
TOY_LAWS = {"T271": {TOY_PAIR: "PROVED", "L_undo_res_ToyUndo_revertLast_roots": "PROVED",
                     "L_undo_res_ToyUndo_revertLast_stamps": "PROVED"},
            "T272": {TOY_PAIR: "REFUTED", "L_undo_res_ToyUndo_revertLast_pins": "REFUTED",
                     "L_undo_res_ToyUndo_revertLast_roots": "PROVED",
                     "L_undo_res_ToyUndo_revertLast_stamps": "PROVED"}}
TOY_DROP_LINE = "        delete pins[i]; // RESIDUE-CLEARING DELETE\n"
TOY_SHA256 = {f"{FIX_REL}/src/ToyUndo.sol": "9c38f07181ae56f3f18987f9fd885579cef4f0e46f0aa1c53ffb11cebd3c7ba0",
              f"{FIX_REL}/drop/src/ToyUndo.sol": "81317fb0e01afebc4416a87818e84eda68ef5b8b1123129da58fbf39e69a3391",
              f"{FIX_REL}/toyundo.extracted.json": "7cf791a97313c8f429c6048945ff51c5521535c0342d200550983654e78e32f0",
              f"{FIX_REL}/drop/toyundo.extracted.json":
                  "8aca30dd967b2fa04878010508598a21dc728d69431501d39365bce77a8a19a1",
              f"{FIX_REL}/HolonToyUndoStep.t.sol": "bf3795baacbf5c32edbcd4677cfc498dea5d46ab56d593f64b324be469b7f7ad"}
# the planted mutant of the real Rollup (Sensitivity, static)
MUTANT_REL = f"{FIX_REL}/mutant/rollup_mutant.extracted.json"
MUTANT_SIDECAR_REL = f"{FIX_REL}/mutant/extract_rollup_mutant.json"
MUTANT_LINE = (447, "committedBatches[_batchIndex] = bytes32(0);")
# the independent instrument: byte copies of the I20 step harness taken at this prereg (replay/M2/solidity/
# HolonStepBase.sol and HolonExtractedStep.t.sol, replay/M1/solidity/HolonTraceReplay.t.sol)
HARNESS = {"HolonStepBase.sol": "d6b490fad4b5da0ae4438c32be6dab6a3e301eff1a06b7b111b470a6874f6334",
           "HolonTraceReplay.t.sol": "3e651a254861603f30c9614ee85ccaa85b6b012d3c2bf88e2aa8813b26959853",
           "HolonExtractedStep.t.sol": "8a4e31d7cc0cfd7b86db08c71e7ad27c618ec75808b67afa1fc8eecfbfa8a5da"}
TOY_FOUNDRY = ("[profile.default]\nsrc = 'src'\nout = 'out'\nlibs = ['node_modules']\nevm_version = 'cancun'\n"
               "fs_permissions = [{ access = 'read-write', path = './' }]\n")
TOY_REMAP = "forge-std/=node_modules/forge-std/src/\nds-test/=node_modules/ds-test/src/\n"

# =============================================================================================== the instrument
# Rules U1-U6 and D1-D3 of the docstring, written out a second time, independently of holon/.
NOT_STATE = ("view", "pure")
SCAN = (("checks", ("expr",)), ("panics", ("expr", "args")), ("calls", ("expr", "args", "receiver", "value", "cond")),
        ("writes", ("value", "cond", "path")), ("events", ("args", "cond", "topics")),
        ("mstores", ("value", "cond", "offset")), ("loops", ("head", "cond", "bound", "count")))


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def ck(obj) -> str:
    return canonical(obj).decode("utf-8")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def is_op(t, op=None) -> bool:
    return isinstance(t, list) and bool(t) and isinstance(t[0], str) and (op is None or t[0] == op)


def is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def conjuncts(e) -> list:
    if is_op(e, "&&"):
        out = []
        for x in e[1:]:
            out += conjuncts(x)
        return out
    return [e]


def norm_key(t):
    """U1: ["iter", span] -> 0, ["carried", span, x] -> x, then x + 0 -> x."""
    if is_op(t, "iter"):
        return 0
    if is_op(t, "carried") and len(t) == 3:
        return norm_key(t[2])
    if isinstance(t, list):
        t = [norm_key(x) for x in t]
        if is_op(t, "+") and len(t) == 3:
            if t[2] == 0:
                return t[1]
            if t[1] == 0:
                return t[2]
    return t


def keys_match(k1, k2) -> bool:
    """Keys of two different actions match unless both are integer literals that differ."""
    k1, k2 = norm_key(k1), norm_key(k2)
    if is_int(k1) and is_int(k2):
        return k1 == k2
    return True


def reads(t, fam: str) -> bool:
    if isinstance(t, list):
        if len(t) == 2 and t[0] == "storage" and t[1] == fam:
            return True
        return any(reads(x, fam) for x in t)
    if isinstance(t, dict):
        return any(reads(v, fam) for v in t.values())
    return False


def occurrences(t, fam: str, anc: list, out: list) -> None:
    """Every read of fam in t: (key or None, ancestors)."""
    if isinstance(t, dict):
        for v in t.values():
            occurrences(v, fam, anc, out)
        return
    if not isinstance(t, list):
        return
    if is_op(t, "map") and len(t) == 3:
        b = t[1]
        if (is_op(b, "storage") and len(b) == 2 and b[1] == fam) or \
                (is_op(b, "carried") and len(b) == 3 and b[2] == ["storage", fam]):
            out.append((t[2], anc + [t]))
            occurrences(t[2], fam, anc + [t], out)
            return
    if is_op(t, "storage") and len(t) == 2 and t[1] == fam:
        out.append((None, anc + [t]))
        return
    for x in (t[1:] if is_op(t) else t):
        occurrences(x, fam, anc + [t], out)


class Doc:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.d = load_json(self.path)
        self.fams = {f["name"]: f for f in self.d["storage"] + self.d.get("inherited_storage", [])}
        self.actions = self.d["actions"]
        self.by = {a["name"]: a for a in self.actions}

    def value_type(self, f: str) -> str:
        return str(self.fams.get(f, {}).get("value", ""))

    def is_mapping(self, f: str) -> bool:
        return self.fams.get(f, {}).get("kind") == "mapping"

    def uint_scalar(self, f: str) -> bool:
        x = self.fams.get(f, {})
        return x.get("kind") == "scalar" and str(x.get("value", "")).startswith("uint")


def wkey(w: dict):
    path = w["path"]
    if not path:
        return None, True
    if is_op(path[0], "map"):
        return path[0][1], len(path) == 1
    return None, False


def reaches(a: dict) -> list:
    return [(gi, ri, r) for gi, g in enumerate(a["guards"]) for ri, r in enumerate(g["reaches"])]


def loop_of(a: dict, rec: dict | None):
    if rec is None or rec.get("loop") is None:
        return None
    for lp in a["loops"]:
        if lp["seq"] == rec["loop"]:
            return lp
    raise AssertionError(f"{a['name']}: no loop record with seq {rec['loop']}")


def unconditional(a: dict, rec: dict) -> bool:
    if rec.get("cond") == 1:
        return True
    lp = loop_of(a, rec)
    return lp is not None and lp["cond"] == 1 and ck(rec.get("cond")) == ck(lp["head"])


def final(a: dict, i: int) -> bool:
    w = a["writes"][i]
    k, _ = wkey(w)
    for w2 in a["writes"]:
        if w2 is w or w2["family"] != w["family"] or w2["seq"] <= w["seq"]:
            continue
        k2, whole2 = wkey(w2)
        if whole2 and ck(k2) == ck(k):
            return False
    return True


def pins(doc: Doc, a: dict) -> list:
    """U2."""
    out = []
    for gi, ri, r in reaches(a):
        for c in conjuncts(r["expr"]):
            cand = []
            if is_op(c, "==") and len(c) == 3:
                if is_int(c[2]):
                    cand.append((c[1], c[2]))
                if is_int(c[1]):
                    cand.append((c[2], c[1]))
            elif is_op(c, "!") and len(c) == 2:
                cand.append((c[1], 0))
            elif is_op(c, "!=") and len(c) == 3 and (c[2] == 0 or c[1] == 0) and not (c[1] == 0 and c[2] == 0):
                cand.append((c[1] if c[2] == 0 else c[2], "bool"))
            else:
                cand.append((c, "bool"))
            for R, lit in cand:
                if is_op(R, "map") and len(R) == 3 and is_op(R[1], "storage") and len(R[1]) == 2:
                    fam, key = R[1][1], R[2]
                elif is_op(R, "storage") and len(R) == 2:
                    fam, key = R[1], None
                else:
                    continue
                if fam not in doc.fams:
                    continue
                if lit == "bool":
                    if doc.value_type(fam) != "bool":
                        continue
                    lit = 1
                out.append({"family": fam, "key": key, "literal": lit, "seq": r["seq"], "at": f"guards[{gi}]"})
    return out


def restores(doc: Doc, a: dict, ab: dict) -> list:
    """U3: every restore of a write of a by ab."""
    out = []
    ps = pins(doc, a)
    for i, wa in enumerate(a["writes"]):
        if wa["cond"] != 1 or not final(a, i):
            continue
        ka, whole_a = wkey(wa)
        F = wa["family"]
        if whole_a and not reads(wa["value"], F):                       # literal
            for p in ps:
                if p["family"] != F or ck(p["key"]) != ck(ka) or p["seq"] >= wa["seq"] or wa["value"] == p["literal"]:
                    continue
                for j, wb in enumerate(ab["writes"]):
                    kb, whole_b = wkey(wb)
                    if wb["family"] != F or not whole_b or not unconditional(ab, wb):
                        continue
                    if not is_int(wb["value"]) or wb["value"] != p["literal"] or (ka is None) != (kb is None):
                        continue
                    if ka is not None and not keys_match(ka, kb):
                        continue
                    out.append({"family": F, "a_write": f"writes[{i}]", "undo_write": f"writes[{j}]",
                                "how": "zero" if p["literal"] == 0 else "literal", "pin": p["at"]})
        v = wa["value"]
        if ka is None and doc.uint_scalar(F) and is_op(v, "+") and len(v) == 3:  # cursor
            t, n = (v[1], v[2]) if is_int(v[2]) else (v[2], v[1])
            if not (is_int(n) and n >= 1):
                continue
            adv = ck(t) == ck(["storage", F])
            for _, _, r in reaches(a):
                if r["seq"] >= wa["seq"]:
                    continue
                for c in conjuncts(r["expr"]):
                    if is_op(c, "==") and len(c) == 3 and sorted([ck(c[1]), ck(c[2])]) == sorted(
                            [ck(t), ck(["storage", F])]):
                        adv = True
            if not adv:
                continue
            for j, wb in enumerate(ab["writes"]):
                vb = wb["value"]
                if wb["family"] != F or wb["path"] or not unconditional(ab, wb):
                    continue
                if is_op(vb, "-") and len(vb) == 3 and is_int(vb[2]) and vb[2] == n:
                    out.append({"family": F, "a_write": f"writes[{i}]", "undo_write": f"writes[{j}]",
                                "how": "cursor", "pin": None})
    return sorted(out, key=ck)


def sig_types(sig: str) -> str:
    m = re.match(r"^[^(]*\((.*)\)$", sig)
    return m.group(1) if m else sig


def criteria(a: dict, ab: dict, rs: list) -> list:
    """U4."""
    out = set()
    if any(r["how"] == "cursor" for r in rs):
        out.add("cursor")
    for r in rs:
        wa = a["writes"][int(r["a_write"][7:-1])]
        wb = ab["writes"][int(r["undo_write"][7:-1])]
        ka, _ = wkey(wa)
        for _, _, g in reaches(ab):
            if g["seq"] >= wb["seq"]:
                continue
            occ = []
            occurrences(g["expr"], r["family"], [], occ)
            if any(ka is None or k is None or keys_match(ka, k) for k, _ in occ):
                out.add("guard")
    for e in a["events"]:
        if e["cond"] != 1:
            continue
        for eb in ab["events"]:
            if not unconditional(ab, eb):
                continue
            if e["event"] != eb["event"] and sig_types(e["signature"]) == sig_types(eb["signature"]) \
                    and e["indexed"] == eb["indexed"]:
                out.add("event")
    return sorted(out)


def identity_write(w: dict) -> bool:
    k, whole = wkey(w)
    if not whole:
        return False
    return ck(w["value"]) == ck(["storage", w["family"]] if k is None else ["map", ["storage", w["family"]], k])


def residues_of(a: dict, rs: list) -> list:
    """U5."""
    restored = {r["a_write"] for r in rs}
    fams = set()
    for i, w in enumerate(a["writes"]):
        if not final(a, i) or f"writes[{i}]" in restored or identity_write(w):
            continue
        fams.add(w["family"])
    return sorted(fams)


def zero_families(doc: Doc, ab: dict, exclude: str) -> list:
    out = set()
    for w in ab["writes"]:
        k, whole = wkey(w)
        if k is None or not whole or w["family"] == exclude or not doc.is_mapping(w["family"]):
            continue
        if is_int(w["value"]) and w["value"] == 0 and unconditional(ab, w):
            out.add(w["family"])
    return sorted(out)


def false_at(x, rho, cursors: list, zero: list) -> bool:
    if rho is None or not is_op(x):
        return False
    R = ck(rho)
    if len(x) == 3:
        for C in cursors:
            S = ck(["storage", C])
            a, b = ck(x[1]), ck(x[2])
            if x[0] == "==" and sorted([a, b]) == sorted([R, S]):
                return True
            if x[0] in ("<=", "<") and a == R and b == S:
                return True
            if x[0] in (">=", ">") and a == S and b == R:
                return True
    for G in zero:
        zr = ck(["map", ["storage", G], rho])

        def zread(y) -> bool:
            return ck(y) == zr or (is_op(y, "member") and len(y) == 3 and ck(y[1]) == zr)
        if is_op(x, "!=") and len(x) == 3 and ((zread(x[1]) and x[2] == 0) or (zread(x[2]) and x[1] == 0)):
            return True
        if is_op(x, "!") and len(x) == 2 and is_op(x[1], "==") and len(x[1]) == 3 and (
                (zread(x[1][1]) and x[1][2] == 0) or (zread(x[1][2]) and x[1][1] == 0)):
            return True
    return False


def records_of(a: dict) -> list:
    out = []
    for gi, ri, r in reaches(a):
        out.append((f"guards[{gi}].reaches[{ri}]", r["seq"], [r.get("expr"), r.get("args")], None))
    for sec, fields in SCAN:
        for i, rec in enumerate(a.get(sec) or []):
            out.append((f"{sec}[{i}]", rec["seq"], [rec.get(f) for f in fields], rec))
    if a.get("returns") is not None:
        out.append(("returns", float("inf"), [a["returns"]], None))
    return out


def dominating(a: dict, seq, rec: dict | None) -> list:
    cs = []
    for _, _, r in reaches(a):
        if r["seq"] < seq:
            cs += conjuncts(r["expr"])
    if rec is not None:
        if rec.get("cond") is not None:
            cs += conjuncts(rec["cond"])
        lp = loop_of(a, rec)
        if lp is not None:
            cs += conjuncts(lp["head"]) + conjuncts(lp["cond"])
    return cs


def deadness(doc: Doc, F: str, cursors: list, zero: list) -> tuple[list, list]:
    """D1-D3: (live readers, excluded readers)."""
    live, excluded = [], []
    for b in doc.actions:
        for at, seq, terms, rec in records_of(b):
            occ = []
            for t in terms:
                occurrences(t, F, [], occ)
            if not occ:
                continue
            dom = dominating(b, seq, rec)
            rules = []
            for rho, anc in occ:
                rule = None
                if rho is not None and any(ck(rho) == ck(["storage", C]) for C in cursors):
                    rule = "D1"
                elif any(false_at(x, rho, cursors, []) for x in dom):
                    rule = "D1"
                elif any(false_at(x, rho, [], zero) for x in dom):
                    rule = "D2"
                else:
                    for i, node in enumerate(anc):
                        if is_op(node, "&&"):
                            child = anc[i + 1] if i + 1 < len(anc) else None
                            if any(op is not child and any(false_at(x, rho, cursors, zero) for x in conjuncts(op))
                                   for op in node[1:]):
                                rule = "D3"
                                break
                rules.append(rule)
            if all(rules):
                excluded.append({"action": b["name"], "at": at, "rules": sorted(set(rules))})
            else:
                live.append({"action": b["name"], "at": at})
    return live, excluded


def analyse(path: Path) -> dict:
    """The analysis document's pairs, rejected and residues for one document."""
    doc = Doc(path)
    pairs, rejected = [], []
    state = [a for a in doc.actions if a["mutability"] not in NOT_STATE]
    for a in state:
        for ab in state:
            if a is ab:
                continue
            rs = restores(doc, a, ab)
            if not rs:
                continue
            cr = criteria(a, ab, rs)
            if cr:
                pairs.append({"a": a["name"], "undo": ab["name"], "criteria": cr, "restores": rs,
                              "residues": residues_of(a, rs)})
            else:
                rejected.append({"a": a["name"], "undo": ab["name"], "restores": rs, "reason": "no_criterion"})
    bases = {}
    for p in pairs:
        for F in p["residues"]:
            b = bases.setdefault((p["undo"], F), {"pairs": set(), "cursors": set()})
            b["pairs"].add(p["a"])
            b["cursors"] |= {r["family"] for r in p["restores"] if r["how"] == "cursor"}
    residues = []
    for (ab, F), b in sorted(bases.items()):
        cursors, zero = sorted(b["cursors"]), zero_families(doc, doc.by[ab], F)
        live, excl = deadness(doc, F, cursors, zero)
        residues.append({"undo": ab, "family": F, "pairs": sorted(b["pairs"]), "cursors": cursors, "zero": zero,
                         "class": "live" if live else "dead", "live_readers": live, "excluded": excl})
    cls = {(r["undo"], r["family"]): r["class"] for r in residues}
    for p in pairs:
        p["class"] = "dead" if all(cls[(p["undo"], F)] == "dead" for F in p["residues"]) else "live"
    key = lambda x: (x["a"], x["undo"])  # noqa: E731
    return {"model": Path(path).name[:-len(".json")], "contract": doc.d["contract"], "pairs": sorted(pairs, key=key),
            "rejected": sorted(rejected, key=key), "residues": residues}


def laws_of(an: dict) -> dict:
    """L1, L2: law id -> {"subform", "undo_id", "basis", "static_class", "predicted"} (PROVED iff static dead: the
    prediction that the static and kernel classifications agree)."""
    out = {}
    m, c = an["model"], an["contract"]
    for p in an["pairs"]:
        lid = f"L_undo_pair_{c}_{p['a']}_{p['undo']}"
        basis = {"kind": "undo_pair", "model": m, "contract": c, "a": p["a"], "undo": p["undo"],
                 "criteria": p["criteria"], "restores": p["restores"], "residues": p["residues"]}
        out[lid] = {"subform": "pair", "undo_id": f"{m}:pair:{p['a']}:{p['undo']}", "basis": basis,
                    "static_class": p["class"], "predicted": "PROVED" if p["class"] == "dead" else "REFUTED"}
    for r in an["residues"]:
        lid = f"L_undo_res_{c}_{r['undo']}_{r['family']}"
        basis = {"kind": "undo_residue", "model": m, "contract": c, "undo": r["undo"], "family": r["family"],
                 "cursors": r["cursors"], "zero": r["zero"], "pairs": r["pairs"]}
        out[lid] = {"subform": "residue", "undo_id": f"{m}:residue:{r['undo']}:{r['family']}", "basis": basis,
                    "static_class": r["class"], "predicted": "PROVED" if r["class"] == "dead" else "REFUTED"}
    return dict(sorted(out.items()))


def undo_ref(subform: str, basis: dict) -> str:
    return hashlib.sha256(canonical({"template": f"holon.rules.undo/{subform}", "template_version": 1,
                                     "subform": subform, "basis": basis})).hexdigest()


def backtest_rows(root: Path, laws: dict) -> dict:
    """The predicted back-test rows by the frozen map (results/M1 statuses; predicted analogue statuses)."""
    bt = load_json(root / UNDO_SIDECAR)["backtest"]
    names = bt["names"]
    rows, gaps = [], []
    for m1, spec in sorted(bt["laws"].items()):
        if spec["subform"] == "residue":
            aid = f"L_undo_res_{CONTRACT}_{names[spec['undo']]}_{names[spec['family']]}"
        else:
            aid = f"L_undo_pair_{CONTRACT}_{names[spec['a']]}_{names[spec['undo']]}"
        m1_status = load_json(root / "results" / "M1" / f"{m1}.json")["status"]
        if aid in laws:
            st = laws[aid]["predicted"]
            rows.append({"m1_law": m1, "m1_status": m1_status, "analogue": aid, "analogue_status": st,
                         "same_status": st == m1_status})
        else:
            rows.append({"m1_law": m1, "m1_status": m1_status, "analogue": None, "analogue_status": None,
                         "same_status": False})
            gaps.append(m1)
    return {"rows": rows, "gaps": gaps}


def basis_inputs(root: Path) -> list:
    paths = [UNDO_SIDECAR, SORT_SIDECAR, DOC_REL, MUTANT_REL, MUTANT_SIDECAR_REL]
    bt = load_json(root / UNDO_SIDECAR)["backtest"]
    paths += [f"results/M1/{m}.json" for m in sorted(bt["laws"])]
    return [{"path": p, "sha256": sha256_file(root / p)} for p in sorted(paths)]


def undo_basis_doc(root: Path = ROOT) -> dict:
    """The content of spec/M3/lib/undo_basis.json without its "doc": rules U1-U6 and D1-D3 over the committed inputs
    listed with their sha256."""
    root = Path(root)
    an = analyse(root / DOC_REL)
    laws = laws_of(an)
    mut = analyse(root / MUTANT_REL)
    tot = {"pairs": len(an["pairs"]), "rejected": len(an["rejected"]), "residues": len(an["residues"]),
           "laws": {s: sum(1 for x in laws.values() if x["subform"] == s) for s in SUBFORMS},
           "predicted": {st: sum(1 for x in laws.values() if x["predicted"] == st) for st in ("PROVED", "REFUTED")}}
    return {"undo_basis_version": "holon-i27-undo-basis/0.1", "inputs": basis_inputs(root),
            "documents": {DOC_REL: {"model": an["model"], "contract": an["contract"],
                                    "facts_sha256": sha256_file(root / DOC_REL), "pairs": an["pairs"],
                                    "rejected": an["rejected"], "residues": an["residues"], "laws": laws}},
            "totals": tot, "backtest": backtest_rows(root, laws),
            "sensitivity": {"document": MUTANT_REL, "facts_sha256": sha256_file(root / MUTANT_REL),
                            "mutation": {"file": ROLLUP_SRC, "line": MUTANT_LINE[0], "text": MUTANT_LINE[1]},
                            "pairs": mut["pairs"], "rejected": mut["rejected"], "residues": mut["residues"],
                            "laws": {lid: {"subform": x["subform"], "static_class": x["static_class"]}
                                     for lid, x in laws_of(mut).items()}}}


def write_basis(root: Path = ROOT) -> None:
    """Writes spec/M3/lib/undo_basis.json (used once, at the prereg)."""
    p = root / BASIS_REL
    old = load_json(p) if p.exists() else {}
    obj = dict(undo_basis_doc(root), doc=old.get("doc", ""))
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


# ======================================================================================== shared test helpers
def need(p: Path) -> dict:
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT) if p.is_relative_to(ROOT) else p} is missing")
    return load_json(p)


def built() -> None:
    """Fail fast, before a repository copy, while the I27 modules do not exist."""
    for rel in ("holon/rules/undo.py", "holon/analysis/deadness.py"):
        if not (ROOT / rel).is_file():
            raise AssertionError(f"{rel} is missing")


def basis() -> dict:
    return load_json(ROOT / BASIS_REL)


def doc_basis() -> dict:
    return basis()["documents"][DOC_REL]


def undo_laws(root: Path = ROOT, milestone: str = M3) -> dict:
    return {p.stem: load_json(p) for p in sorted((root / "laws" / milestone).glob("L_undo_*.json"))}


def undo_records(root: Path = ROOT, milestone: str = M3) -> dict:
    return {p.stem: load_json(p) for p in sorted((root / "results" / milestone).glob("L_undo_*.json"))}


def derivation(root: Path = ROOT, milestone: str = M3) -> dict:
    return {e["law_id"]: e for e in need(root / "laws" / milestone / "DERIVATION.json")["laws"]}


def run_ok(test: unittest.TestCase, args: list, cwd: Path | None = None, timeout: int = 7200):
    p = run_holon(args, cwd=cwd, timeout=timeout)
    test.assertEqual(p.returncode, 0, f"holon {' '.join(args)}: {(p.stdout + p.stderr)[-3000:]}")
    return p


def m3_catalog() -> str:
    """The catalog version M3 derives with: holon-rules/1.3, or a later version that holds every producer of 1.3 (the
    same objects), so that a later rule does not turn these tests red."""
    import importlib
    rules = importlib.import_module("holon.rules")
    v = rules.catalog_version("M3")
    if v != CATALOG:
        base, cat = rules.CATALOGS[CATALOG], rules.CATALOGS[v]
        for rule, subs in base.items():
            for sub, prod in subs.items():
                if (cat.get(rule) or {}).get(sub) is not prod:
                    raise AssertionError(f"M3 derives with {v}, which drops {rule}/{sub} of {CATALOG}")
    return v


def gate_g1(test: unittest.TestCase, repo: Path | None = None) -> dict:
    """The report of `holon gate --milestone M3 --checks G1` run on a copy of the tree (or on repo, a copy already
    made): G1 regenerates the UNDO classification and lists its disagreements under "warnings"."""
    own = repo is None
    repo = copy_repo() if own else repo
    try:
        rep = repo.parent / "gate_report_i27.json"
        p = run_holon(["gate", "--milestone", M3, "--root", str(repo), "--report", str(rep), "--checks", "G1"],
                      cwd=repo, timeout=7200)
        test.assertTrue(rep.is_file(), f"holon gate wrote no report: {(p.stdout + p.stderr)[-3000:]}")
        return load_json(rep)
    finally:
        if own:
            shutil.rmtree(repo.parent, ignore_errors=True)


def hash_binders_of_sort_laws(root: Path = ROOT) -> list | None:
    """The hash binders of I30's laws over the rollup document (the binders after s and a), or None."""
    for p in sorted((root / "laws" / M3).glob("L_sort_*.json")):
        law = load_json(p)
        if law.get("facts") == DOC_REL:
            return [b for b in law["statement"]["binders"] if str(b.get("type", "")).startswith("Fn<")]
    return None


# ------------------------------------------------------------------ a minimal ABI encoder (the harness's call step)
def _word(n: int) -> bytes:
    return int(n).to_bytes(32, "big")


def _hexb(v) -> bytes:
    if isinstance(v, (bytes, bytearray)):
        return bytes(v)
    s = str(v)
    return bytes.fromhex(s[2:] if s.startswith("0x") else s)


def _num(v) -> int:
    if isinstance(v, str):
        return int(v, 16) if v.lower().startswith("0x") else int(v)
    return int(v)


def abi_encode(types: list, values: list) -> bytes:
    """Static types (uintN, address, bool, bytes32) and the dynamic bytes and bytes32[]."""
    heads, tails, off = [], [], 32 * len(types)
    for t, v in zip(types, values):
        if t == "bytes":
            b = _hexb(v)
            enc = _word(len(b)) + b + b"\0" * ((-len(b)) % 32)
        elif t == "bytes32[]":
            enc = _word(len(v)) + b"".join(_hexb(x).rjust(32, b"\0") for x in v)
        else:
            if t == "bytes32":
                heads.append(_hexb(v).rjust(32, b"\0"))
            elif t == "bool":
                heads.append(_word(1 if v else 0))
            else:
                heads.append(_word(_num(v)))
            continue
        heads.append(_word(off))
        tails.append(enc)
        off += len(enc)
    return b"".join(heads) + b"".join(tails)


def selector(sig: str) -> bytes:
    return keccak256(sig.encode())[:4]


def call_step(step: dict) -> str:
    """The I20 step harness's call step: abi.encode(uint8 2, bool false, bytes payload), payload abi.encode(address
    caller, uint256 value, uint256 timestamp, bytes32[] blobhashes, address to (0: the target), bytes data)."""
    env = step.get("env") or {}
    payload = abi_encode(["address", "uint256", "uint256", "bytes32[]", "address", "bytes"],
                         [env["caller"], _num(env.get("msg.value", 0)), _num(env.get("block.timestamp", 0)),
                          list(env.get("blobhash") or []), 0, step["calldata"]])
    return "0x" + abi_encode(["uint8", "bool", "bytes"], [2, False, payload]).hex()


def _deployment_init() -> list[int]:
    """The I20 binding's deployment parameters, as holon fragments passes them (replay/M2/fragments.json "init")."""
    binding = load_json(ROOT / "replay" / "M2" / "fragments.json")
    initial = load_json(ROOT / binding["init"]["facts"])["initial"]
    out = []
    for k in binding["init"]["keys"]:
        name, _, idx = k.partition(".")
        out.append(int(initial[name][int(idx)] if idx else initial[name]))
    return out


def realized(traces: list[list[dict]], target: str = "rollup") -> list[list[dict]]:
    """Each trace on the REAL code through the harness copies taken at this prereg (independent of holon's replay), from
    a fresh deployment: target "rollup" the pinned Rollup as the I20 binding deploys it; "T271" or "T272" the planted toy
    variant. One observation per step: {"status": "ok" | "revert", "ret", "logs": [{"topics", "data"}], "calls":
    [{"to", "data"}]} (logs and calls empty for a revert). The toolchain is pinned (config replay): a missing or
    different forge, solc or dependency tree is a failure, never a skip."""
    if not traces:
        raise AssertionError("no trace to replay")
    cfg = I15._check_toolchain()
    for name, pin in HARNESS.items():
        if sha256_file(FIX / "harness" / f"{name}.txt") != pin:
            raise AssertionError(f"{FIX_REL}/harness/{name}.txt is not the harness copied at the I27 prereg")
    proj = Path(tempfile.mkdtemp(prefix="holon-i27-sol-"))
    try:
        (proj / "test").mkdir()
        shutil.copy(FIX / "harness" / "HolonStepBase.sol.txt", proj / "test" / "HolonStepBase.sol")
        if target == "rollup":
            morph = morph_checkout()
            shutil.copytree(morph / "contracts" / "contracts", proj / "contracts")
            for d in ("mock", "test"):
                shutil.rmtree(proj / "contracts" / d, ignore_errors=True)
            for f in ("foundry.toml", "remappings.txt"):
                shutil.copy(morph / "contracts" / f, proj / f)
            for name in ("HolonTraceReplay.t.sol", "HolonExtractedStep.t.sol"):
                shutil.copy(FIX / "harness" / f"{name}.txt", proj / "test" / name)
            init, contract = _deployment_init(), "HolonExtractedStepTest"
        else:
            if sha256_file(FIX / "HolonToyUndoStep.t.sol") != TOY_SHA256[f"{FIX_REL}/HolonToyUndoStep.t.sol"]:
                raise AssertionError("the toy harness is not the one written at the I27 prereg")
            shutil.copytree(ROOT / TOY[target]["dir"] / "src", proj / "src")
            shutil.copy(FIX / "HolonToyUndoStep.t.sol", proj / "test" / "HolonToyUndoStep.t.sol")
            (proj / "foundry.toml").write_text(TOY_FOUNDRY)
            (proj / "remappings.txt").write_text(TOY_REMAP)
            init, contract = [], "HolonToyUndoStepTest"
        shutil.copytree(Path(cfg["sol_deps"]) / "node_modules", proj / "node_modules", symlinks=False,
                        ignore=shutil.ignore_patterns(".git"))
        fin, fout = proj / "holon_i27_steps.json", proj / "holon_i27_steps.out"
        fin.write_text(json.dumps({"lens": [len(tr) for tr in traces],
                                   "steps": [call_step(s) for tr in traces for s in tr], "slots": [], "init": init}))
        env = {**os.environ, "HOLON_STEPS_IN": str(fin), "HOLON_STEPS_OUT": str(fout), "HOLON_LO": "0",
               "HOLON_HI": str(len(traces))}
        p = subprocess.run([cfg["forge"], "test", "--offline", "--use", cfg["solc"], "--match-contract",
                            f"^{contract}$", "--match-test", r"^test_steps\(\)$"], cwd=proj, env=env,
                           capture_output=True, text=True, timeout=3000)
        if p.returncode != 0 or not fout.exists():
            raise AssertionError(f"the raw-call instrument failed (exit {p.returncode}): {(p.stdout + p.stderr)[-2000:]}")
        obs: dict = {}
        for line in fout.read_text().splitlines():
            f = line.split(" ")
            if f[0] == "S" and len(f) == 14 and f[3] == "call" and f[2].isdigit():
                obs[(int(f[1]), int(f[2]))] = {"status": "ok" if f[5] == "1" else "revert", "ret": f[-1].lower(),
                                               "logs": [], "calls": []}
            elif f[0] == "L" and f[2].isdigit():
                o = obs.setdefault((int(f[1]), int(f[2])), {"logs": [], "calls": []})
                o["logs"].append({"topics": [] if f[3] == "-" else f[3].lower().split(","), "data": f[4].lower()})
            elif f[0] == "C" and f[2].isdigit():
                o = obs.setdefault((int(f[1]), int(f[2])), {"logs": [], "calls": []})
                o["calls"].append({"to": f[3].lower(), "data": f[4].lower()})
        out = []
        for tid, tr in enumerate(traces):
            row = []
            for i in range(len(tr)):
                o = obs.get((tid, i))
                if o is None or "status" not in o:
                    raise AssertionError(f"trace {tid} step {i}: no S line in the harness output")
                if o["status"] == "revert":
                    o = dict(o, logs=[], calls=[])
                row.append(o)
            out.append(row)
        return out
    finally:
        shutil.rmtree(proj, ignore_errors=True)


def toy_step(fn: str, args: list, ts: int, caller: str = "0x0000000000000000000000000000000000001001") -> dict:
    sigs = {"commit": ("commit(bytes32,bytes32,bytes32)", ["bytes32"] * 3), "revertLast": ("revertLast()", []),
            "touch": ("touch(uint256)", ["uint256"]), "stampOf": ("stampOf(uint256)", ["uint256"])}
    sig, types = sigs[fn]
    data = selector(sig) + abi_encode(types, args)
    return {"action": fn, "args": args, "calldata": "0x" + data.hex(),
            "env": {"caller": caller, "msg.value": 0, "block.timestamp": ts, "blobhash": [], "calls": []}}


def b32(n: int) -> str:
    return "0x" + n.to_bytes(32, "big").hex()


def witness_runs(w: dict) -> tuple[list, list]:
    """(the run with the pair, the run without it) of an UNDO witness."""
    pre, t = list(w.get("prefix") or []), list(w.get("t") or [])
    return pre + [w["x"], w["y"]] + t, pre + t


# =========================================================================================== the tests
class TestInstrument(unittest.TestCase):
    """Construction checks of the instruments fixed at this prereg (not predictions)."""

    def test_the_basis_sidecar_is_the_computation(self):
        """I27-R4 (part): spec/M3/lib/undo_basis.json equals undo_basis_doc over the committed inputs, whose sha256 it
        lists; its totals are the contract's numbers."""
        b = basis()
        for x in b["inputs"]:
            self.assertEqual(sha256_file(ROOT / x["path"]), x["sha256"], x["path"])
        got = undo_basis_doc(ROOT)
        self.assertEqual(ck({k: v for k, v in b.items() if k != "doc"}), ck(got))
        self.assertEqual(b["totals"], {"laws": {"pair": 5, "residue": 3}, "pairs": 5, "predicted":
                                       {"PROVED": 3, "REFUTED": 5}, "rejected": 2, "residues": 3})
        self.assertEqual({lid: (x["subform"], x["predicted"]) for lid, x in doc_basis()["laws"].items()}, PREDICTED)

    def test_the_toy_fixtures_are_one_delete_apart(self):
        """I27-R4 (part): the drop variant is the baseline without exactly the one line marked RESIDUE-CLEARING DELETE;
        the committed files are the ones written at the prereg (sha256)."""
        for rel, pin in TOY_SHA256.items():
            self.assertEqual(sha256_file(ROOT / rel), pin, rel)
        base = (FIX / "src" / "ToyUndo.sol").read_text().splitlines(keepends=True)
        drop = (FIX / "drop" / "src" / "ToyUndo.sol").read_text().splitlines(keepends=True)
        self.assertEqual([x for x in base if x != TOY_DROP_LINE], drop)
        self.assertEqual(sum(1 for x in base if x == TOY_DROP_LINE), 1)

    def test_the_planted_documents_reproduce_with_holons_frontend(self):
        """I27-R4 (part): holon's Solidity frontend re-extracts both toy variants and the Rollup mutant (a copy of the
        pinned checkout without Rollup.sol:447 and nothing else) byte for byte."""
        tmp = Path(tempfile.mkdtemp(prefix="holon-i27-extract-"))
        try:
            for name, (side, src, doc) in {
                    "toy": (f"{FIX_REL}/extract_toyundo.json", FIX, TOY["T271"]["doc"]),
                    "drop": (f"{FIX_REL}/drop/extract_toyundo.json", FIX / "drop", TOY["T272"]["doc"])}.items():
                out = tmp / f"{name}.json"
                run_ok(self, ["extract", "solidity", "--sidecar", side, "--source", str(src), "--out", str(out)])
                self.assertEqual(out.read_bytes(), (ROOT / doc).read_bytes(), name)
            mut = tmp / "morph"
            (mut / "contracts").mkdir(parents=True)
            shutil.copytree(morph_checkout() / "contracts" / "contracts", mut / "contracts" / "contracts")
            sol = mut / ROLLUP_SRC
            lines = sol.read_text().split("\n")
            self.assertEqual(lines[MUTANT_LINE[0] - 1].strip(), MUTANT_LINE[1])
            del lines[MUTANT_LINE[0] - 1]
            sol.write_text("\n".join(lines))
            out = tmp / "mutant.json"
            run_ok(self, ["extract", "solidity", "--sidecar", MUTANT_SIDECAR_REL, "--source", str(mut), "--out",
                          str(out)])
            self.assertEqual(out.read_bytes(), (ROOT / MUTANT_REL).read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_toy_variants_behave_as_designed_on_the_real_toy(self):
        """I27-R4 (part): the raw-call instrument on the real toys: commit (nonzero pin), revertLast, commit succeeds on
        the baseline and reverts "pinned" on the drop variant; without the pair the last commit succeeds on both."""
        with_pair = [toy_step("commit", [b32(0xe1), b32(0x71), b32(0x91)], 1700000001),
                     toy_step("revertLast", [], 1700000002),
                     toy_step("commit", [b32(0xe2), b32(0x72), b32(0x92)], 1700000003)]
        without = [with_pair[2]]
        for target, last in (("T271", "ok"), ("T272", "revert")):
            runs = realized([with_pair, without], target)
            self.assertEqual([o["status"] for o in runs[0]], ["ok", "ok", last], target)
            self.assertEqual([o["status"] for o in runs[1]], ["ok"], target)
            if last == "revert":
                self.assertIn(b"pinned", bytes.fromhex(runs[0][2]["ret"][2:]))
            else:
                self.assertEqual(runs[0][2], runs[1][0])


    def test_the_rollup_instrument_runs_on_the_real_contract(self):
        """I27-R4 (part): the raw-call instrument P7 uses works now on the pinned Rollup as the I20 binding deploys it:
        a call of the view batchInsideChallengeWindow(1) (no batch 1 in the deployment) succeeds and returns false."""
        data = selector("batchInsideChallengeWindow(uint256)") + abi_encode(["uint256"], [1])
        step = {"action": "batchInsideChallengeWindow", "args": [1], "calldata": "0x" + data.hex(),
                "env": {"caller": "0x0000000000000000000000000000000000001001", "msg.value": 0,
                        "block.timestamp": 1700000001, "blobhash": [], "calls": []}}
        real = realized([[step]], "rollup")
        self.assertEqual(real, [[{"status": "ok", "ret": "0x" + "00" * 32, "logs": [], "calls": []}]])


class TestAnalysis(unittest.TestCase):
    """holon undo over the extracted rollup document (U1-U6, D1-D3)."""

    @classmethod
    def setUpClass(cls):
        built()
        cls.an = need(ANALYSIS)

    def test_the_analysis_document(self):
        """I27-R4 (part): gen/M3/undo/morph_rollup.extracted.json has the contract's keys and inputs; two runs of holon
        undo are byte-identical and equal the committed file."""
        self.assertEqual(self.an["document"], "undo")
        self.assertEqual(self.an["undo_version"], "holon-undo/0.1")
        self.assertEqual((self.an["milestone"], self.an["model"], self.an["contract"], self.an["facts"]),
                         (M3, MODEL, CONTRACT, DOC_REL))
        self.assertEqual(self.an["facts_sha256"], sha256_file(ROOT / DOC_REL))
        paths = [x["path"] for x in self.an["inputs"]]
        self.assertIn(DOC_REL, paths)
        self.assertIn(UNDO_SIDECAR, paths)
        self.assertFalse([p for p in paths if p.startswith(("spec/M1/", "facts/", "gen/M2/"))], paths)
        tmp = Path(tempfile.mkdtemp(prefix="holon-i27-undo-"))
        try:
            run_ok(self, ["undo", "--milestone", M3, "--out", str(tmp / "a")])
            run_ok(self, ["undo", "--milestone", M3, "--out", str(tmp / "b")])
            a = (tmp / "a" / f"{MODEL}.json").read_bytes()
            self.assertEqual(a, (tmp / "b" / f"{MODEL}.json").read_bytes())
            self.assertEqual(a, ANALYSIS.read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_undo_pairs_on_the_extracted_rollup(self):
        """I27-P1: exactly five undo pairs. (commitBatch, revertBatch), (commitState, revertBatch) and
        (commitBatchWithProof, revertBatch), criteria [cursor, event, guard], each restoring committedBatches (zero,
        pinned by the "batch already committed" guard Rollup.sol:311, revertBatch's loop write :447) and
        lastCommittedBatchIndex (cursor: :373 writes parent index + 1 under :312's equality, :443 writes header index -
        1); (addChallenger, removeChallenger) and (removeChallenger, addChallenger), criterion [guard], restoring
        isChallenger. Rejected (a restore, no criterion): exactly (challengeState, proveState) [inChallenge] and
        (commitBatch, finalizeBatch) [batchBlobVersionedHashes]. (challengeState, setPause) is not a candidate (gap
        G5)."""
        exp = doc_basis()
        self.assertEqual(self.an["pairs"], exp["pairs"])
        self.assertEqual(self.an["rejected"], exp["rejected"])
        self.assertEqual([(p["a"], p["undo"]) for p in self.an["pairs"]], PAIRS)
        self.assertEqual([(p["a"], p["undo"]) for p in self.an["rejected"]], REJECTED)
        for p in self.an["pairs"]:
            if p["undo"] == "revertBatch":
                self.assertEqual(p["criteria"], ["cursor", "event", "guard"])
                self.assertEqual(sorted((r["family"], r["how"]) for r in p["restores"]),
                                 [("committedBatches", "zero"), ("lastCommittedBatchIndex", "cursor")])
            else:
                self.assertEqual(p["criteria"], ["guard"])
                self.assertEqual([r["family"] for r in p["restores"]], ["isChallenger"])
        self.assertNotIn(("challengeState", "setPause"),
                         [(p["a"], p["undo"]) for p in self.an["pairs"] + self.an["rejected"]])

    def test_residues_and_residue_bases(self):
        """I27-P2: Res(commitBatch, revertBatch) = {batchBlobVersionedHashes, batchDataStore, committedStateRoots} at
        the commit's index lastCommittedBatchIndex + 1 (the plan's {CSR, BD, BVH}; no tag: gap G2);
        Res(commitState, revertBatch) = {batchDataStore, committedStateRoots} (commitState's write of
        batchBlobVersionedHashes at :359 is the identity copy); Res(commitBatchWithProof, revertBatch) = {BVH, BD, CSR};
        the challenger pairs leave none. Three residue bases, all with undo revertBatch, cursors
        [lastCommittedBatchIndex] and zero [challenges, committedBatches]."""
        self.assertEqual({(p["a"], p["undo"]): p["residues"] for p in self.an["pairs"]}, RESIDUES)
        self.assertEqual(self.an["residues"], doc_basis()["residues"])
        # "at lastCommittedBatchIndex + 1": each residue of a commit pair has a final whole write in a at the key of
        # the committedBatches register the pair restores, the key a's guard :311 pins (parent index + 1, the parent
        # index being equated with the cursor by :312)
        doc = Doc(ROOT / DOC_REL)
        for p in self.an["pairs"]:
            if p["undo"] != "revertBatch":
                continue
            a = doc.by[p["a"]]
            cb = next(r for r in p["restores"] if r["family"] == "committedBatches")
            kc = wkey(a["writes"][int(cb["a_write"][len("writes["):-1])])[0]
            self.assertIn(ck(kc), [ck(x["key"]) for x in pins(doc, a) if x["at"] == cb["pin"]], p["a"])
            for F in p["residues"]:
                self.assertTrue(any(w["family"] == F and final(a, i) and wkey(w) == (kc, True)
                                    for i, w in enumerate(a["writes"])), (p["a"], F))
        self.assertEqual([(r["undo"], r["family"], r["cursors"], r["zero"]) for r in self.an["residues"]],
                         [("revertBatch", f, ["lastCommittedBatchIndex"], ["challenges", "committedBatches"])
                          for f in ("batchBlobVersionedHashes", "batchDataStore", "committedStateRoots")])

    def test_static_classification(self):
        """I27-P3: committedStateRoots dead (4 readers, each excluded by D1: the :314 guard of commitBatch, commitState
        and commitBatchWithProof dominated by :312's equality with the cursor, and initialize2's write condition at key
        lastCommittedBatchIndex); batchBlobVersionedHashes live (17 live readers, first commitBatch's guard :261 "commitBatch
        requires no stored blob hash"); batchDataStore live through exactly one reader, the return of the view
        batchInsideChallengeWindow (Rollup.sol:709-711), with 15 readers excluded (6 D1, 6 D2, 3 D3). The plan said BD is
        dead; on the extracted code a declared view returns it (gap G4)."""
        res = {r["family"]: r for r in self.an["residues"]}
        self.assertEqual({f: r["class"] for f, r in res.items()}, CLASSES)
        csr = res["committedStateRoots"]
        self.assertEqual(csr["live_readers"], [])
        self.assertEqual([(x["action"], x["rules"]) for x in csr["excluded"]],
                         [("commitBatch", ["D1"]), ("commitBatchWithProof", ["D1"]), ("commitState", ["D1"]),
                          ("initialize2", ["D1"])])
        bvh = res["batchBlobVersionedHashes"]
        self.assertEqual(len(bvh["live_readers"]), 17)
        self.assertEqual(bvh["live_readers"][0], {"action": "commitBatch", "at": "guards[7].reaches[0]"})
        bd = res["batchDataStore"]
        self.assertEqual(bd["live_readers"], [{"action": "batchInsideChallengeWindow", "at": "returns"}])
        rules = [r for x in bd["excluded"] for r in x["rules"]]
        self.assertEqual((len(bd["excluded"]), rules.count("D1"), rules.count("D2"), rules.count("D3")), (15, 6, 6, 3))
        self.assertEqual({p["a"]: p["class"] for p in self.an["pairs"]},
                         {"addChallenger": "dead", "commitBatch": "live", "commitBatchWithProof": "live",
                          "commitState": "live", "removeChallenger": "dead"})


class TestRegistry(unittest.TestCase):
    """The catalog, the producers and derive (construction checks)."""

    def test_catalogs(self):
        """I27-R4 (part): holon-rules/1.3 holds UNDO's two producers and every producer of each earlier M3 catalog
        (holon-rules/1.1's PAR, I30's SORT), the same objects; M3 derives with it; M2's catalog is unchanged."""
        built()
        import importlib
        rules = importlib.import_module("holon.rules")
        undo = importlib.import_module("holon.rules.undo")
        m3_catalog()
        self.assertEqual(rules.catalog_version("M2"), "holon-rules/1.0")
        cat = rules.CATALOGS[CATALOG]
        self.assertEqual(sorted(cat["UNDO"]), sorted(SUBFORMS))
        self.assertEqual(dict(cat["UNDO"]), dict(undo.PRODUCERS))
        self.assertIn("PAR", cat)
        self.assertIn("SORT", cat)
        self.assertLessEqual({"realize", "as_member"}, set(cat["SORT"]))  # I30's subforms on the rollup
        earlier = [v for v in rules.CATALOGS if re.fullmatch(r"holon-rules/1\.([12])", v)]
        self.assertIn("holon-rules/1.1", earlier)
        for v in earlier:
            for rule, subs in rules.CATALOGS[v].items():
                for sub, prod in subs.items():
                    self.assertIs(cat[rule][sub], prod, f"{v}: {rule}/{sub}")

    def test_new_code_names_no_target(self):
        """I27-R4 (part, AGENTS rules 2 and 4): holon/rules/undo.py and holon/analysis/deadness.py hold no action,
        family, contract, span or law id of the documents they read."""
        built()
        names = set()
        for rel in (DOC_REL, TOY["T271"]["doc"]):
            d = load_json(ROOT / rel)
            names |= {a["name"] for a in d["actions"]} | {f["name"] for f in d["storage"]} | {d["contract"]}
        names |= {"Rollup.sol", "L_undo_", "ToyUndo", "morph"}
        # ordinary words the generic code may use (a variable "pins", a comment on "entries") are not identifiers here
        names -= {"owner", "paused", "receive", "initialize", "last", "touch", "commit", "entries", "roots", "stamps",
                  "pins", "verifier"}
        for rel in ("holon/rules/undo.py", "holon/analysis/deadness.py"):
            text = (ROOT / rel).read_text()
            hits = sorted(n for n in names if re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", text))
            self.assertEqual(hits, [], rel)
        # AGENTS rule 2 (never special-case law ids): no file under holon/ names an I27 law id, an undo id or the
        # undo: ref of one (Rollup's or the toy's), nor the planted mutant's line
        ids = set(PREDICTED) | {lid for v in TOY_LAWS.values() for lid in v}
        bad = ids | {x["undo_id"] for x in doc_basis()["laws"].values()} | {MUTANT_LINE[1]}
        bad |= {undo_ref(x["subform"], x["basis"]) for x in doc_basis()["laws"].values()}
        for p in sorted((ROOT / "holon").rglob("*")):
            if p.suffix not in (".py", ".mjs", ".js", ".json") or not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            hits = sorted(b for b in bad if b in text)
            self.assertEqual(hits, [], str(p.relative_to(ROOT)))


class TestDerivation(unittest.TestCase):
    """laws/M3 L_undo_* (L1, L2)."""

    @classmethod
    def setUpClass(cls):
        built()
        cls.laws = undo_laws()
        cls.der = derivation()

    def test_the_undo_laws(self):
        """I27-P4: holon derive --milestone M3 emits exactly the eight UNDO laws undo_basis.json lists, all over the
        extracted rollup document: five pair laws (the pairs of P1) and three residue laws (revertBatch x {BVH, BD,
        CSR}); law IR, bases, binders, claim and DERIVATION entries as the contract states; refs "undo:<id>" hash the
        template, version, subform and basis."""
        exp = doc_basis()["laws"]
        self.assertEqual(sorted(self.laws), sorted(exp))
        hb = hash_binders_of_sort_laws()
        # I30's contract (preregistered at 499c70b, merged before I27 builds) derives SORT laws over this document
        self.assertIsNotNone(hb, f"no laws/M3/L_sort_*.json over {DOC_REL}: I30's hash binders are unknown")
        cv = m3_catalog()
        for lid, law in self.laws.items():
            e = exp[lid]
            self.assertEqual((law["ir_version"], law["rule"], law["subform"], law["milestone"],
                              law["rule_catalog_version"], law["facts"]),
                             ("holon-ir/0.3", "UNDO", e["subform"], M3, cv, DOC_REL), lid)
            self.assertEqual(law["facts_sha256"], sha256_file(ROOT / DOC_REL))
            self.assertNotIn("evidence", law)
            self.assertNotIn("predicted", law)
            st = law["statement"]
            names = [(b["name"], b["type"]) for b in st["binders"]]
            fam = e["basis"].get("family")
            head = ([("s", "Reach"), ("x", "Act"), ("y", "Act"), ("t", "Trace")] if e["subform"] == "pair" else
                    [("s", "Reach"), ("k", "Word"), ("v", f"Val[{fam}]"), ("t", "Trace")])
            self.assertEqual(names[:4], head, lid)
            tail = st["binders"][4:]
            self.assertTrue(tail and all(b["type"].startswith("Fn<") and b["name"] in ("keccak256", "sha256")
                                         for b in tail), tail)
            self.assertEqual(tail, hb, lid)
            self.assertEqual(st["assume"], [])
            self.assertEqual(st["claim"], {"eq": [{"undo": e["undo_id"], "on": [{"var": b["name"]}
                                                                                for b in st["binders"]]},
                                                  {"bool": True}]})
            self.assertEqual(st["scope"], {"kind": "unbounded"})
            d = self.der[lid]
            self.assertEqual((d["rule"], d["subform"], d["facts"]), ("UNDO", e["subform"], DOC_REL))
            self.assertEqual(d["basis"], e["basis"], lid)
            self.assertEqual(d["static"]["class"], e["static_class"], lid)
            refs = __import__("importlib").import_module("holon.gen.refs")
            self.assertEqual(refs.refs(law, load_json(ROOT / DOC_REL)).get(f"undo:{e['undo_id']}"),
                             undo_ref(e["subform"], e["basis"]), lid)

    def test_derive_reproduces_the_committed_m3_laws(self):
        """I27-R5 (part): holon derive --milestone M3 in a repository copy reproduces laws/M3 (every file) byte for
        byte; holon undo and derive read no hand-written fact document."""
        repo = copy_repo()
        try:
            shutil.rmtree(repo / "laws" / M3)
            run_ok(self, ["derive", "--milestone", M3], cwd=repo)
            for p in sorted(LAWS3.glob("*.json")):
                self.assertEqual((repo / "laws" / M3 / p.name).read_bytes(), p.read_bytes(), p.name)
            self.assertEqual(sorted(x.name for x in (repo / "laws" / M3).glob("*.json")),
                             sorted(x.name for x in LAWS3.glob("*.json")))
            der = load_json(repo / "laws" / M3 / "DERIVATION.json")
            ins = [x["path"] for x in der.get("inputs", [])]
            self.assertFalse([p for p in ins if p.startswith(("spec/M1/facts", "facts/"))], ins)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestOutcomes(unittest.TestCase):
    """holon run, records, the replay report and the independent real-side replay."""

    @classmethod
    def setUpClass(cls):
        built()
        cls.rec = undo_records()

    def _status(self, lid):
        r = self.rec.get(lid)
        self.assertIsNotNone(r, f"results/M3/{lid}.json is missing")
        return r["status"]

    def _refuted(self, lid):
        r = self.rec[lid]
        self.assertEqual(r["status"], "REFUTED", r.get("attempts"))
        w = r.get("witness") or {}
        for k in ("x", "y", "t", "hashes"):
            self.assertIn(k, w, lid)
        self.assertTrue(w["t"], lid)
        rep = ((need(REPLAY3).get("laws") or {}).get(lid))
        self.assertIsNotNone(rep, f"replay/M3/undo/report.json has no entry {lid}")
        self.assertEqual(rep["status"], "passed", rep)
        self.assertIs(rep["calls_agree"], True)
        with_run, without = witness_runs(w)
        self.assertEqual(rep["with"]["trace"], with_run)
        self.assertEqual(rep["without"]["trace"], without)
        self.assertEqual(rep["with"]["model"], rep["with"]["real"])
        self.assertEqual(rep["without"]["model"], rep["without"]["real"])
        self.assertEqual(rep["t_at"], len(w.get("prefix") or []) + 2)
        i = rep["diverges_at"]
        self.assertNotEqual(rep["with"]["real"][rep["t_at"] + i], rep["without"]["real"][len(w.get("prefix") or []) + i])
        return r, w, rep

    def test_residue_law_outcomes(self):
        """I27-P5: L_undo_res_Rollup_revertBatch_committedStateRoots is PROVED (a checked proof and a reachable inhabitant
        of its premises, G11V); L_undo_res_Rollup_revertBatch_batchBlobVersionedHashes is REFUTED by a witness realized
        by (commitBatch or commitBatchWithProof, revertBatch) whose divergent step is a call of commitBatch, commitState or
        commitBatchWithProof (the live readers' actions); L_undo_res_Rollup_revertBatch_batchDataStore is REFUTED by a
        witness whose divergent step is a call of batchInsideChallengeWindow returning true with the pair and false
        without it (the M1 analogue L_undo_BD was PROVED: I27-P9)."""
        lid = "L_undo_res_Rollup_revertBatch_committedStateRoots"
        self.assertEqual(self._status(lid), "PROVED", self.rec.get(lid, {}).get("attempts"))
        nv = self.rec[lid].get("non_vacuity") or {}
        self.assertEqual((nv.get("status"), nv.get("reachable")), ("inhabited", True), nv)
        for lid, pairs, readers in (
                ("L_undo_res_Rollup_revertBatch_batchBlobVersionedHashes", ("commitBatch", "commitBatchWithProof"),
                 ("commitBatch", "commitState", "commitBatchWithProof")),
                ("L_undo_res_Rollup_revertBatch_batchDataStore",
                 ("commitBatch", "commitBatchWithProof", "commitState"), ("batchInsideChallengeWindow",))):
            r, w, rep = self._refuted(lid)
            self.assertIn(w["x"]["action"], pairs, lid)
            self.assertEqual(w["y"]["action"], "revertBatch", lid)
            self.assertIn("k", w)
            self.assertIn("v", w)
            self.assertIn(w["t"][rep["diverges_at"]]["action"], readers, lid)
        r, w, rep = self._refuted("L_undo_res_Rollup_revertBatch_batchDataStore")
        i = rep["diverges_at"]
        self.assertEqual([rep["with"]["real"][rep["t_at"] + i]["ret"], rep["without"]["real"][len(w.get("prefix") or []) + i]["ret"]],
                         ["0x" + "00" * 31 + "01", "0x" + "00" * 32])

    def test_pair_law_outcomes(self):
        """I27-P6: the pair laws of (commitBatch, revertBatch), (commitState, revertBatch) and (commitBatchWithProof,
        revertBatch) are REFUTED, each with a witness whose x and y are calls of its pair and whose divergent step is a
        call of an action that reads one of its live residues (commitBatch, commitState or commitBatchWithProof for BVH;
        batchInsideChallengeWindow for BD); the two challenger pair laws are PROVED (no residue: the restore proof), each
        with a reachable inhabitant. The (commitBatch, revertBatch) law is the analogue of L_undo_BVH (App. F's undo_bvh)."""
        for lid in ("L_undo_pair_Rollup_addChallenger_removeChallenger",
                    "L_undo_pair_Rollup_removeChallenger_addChallenger"):
            self.assertEqual(self._status(lid), "PROVED", self.rec.get(lid, {}).get("attempts"))
            nv = self.rec[lid].get("non_vacuity") or {}
            self.assertEqual((nv.get("status"), nv.get("reachable")), ("inhabited", True), nv)
        live_readers = {"batchBlobVersionedHashes": ("commitBatch", "commitState", "commitBatchWithProof"),
                        "batchDataStore": ("batchInsideChallengeWindow",)}
        for (a, ab), fams in RESIDUES.items():
            if ab != "revertBatch":
                continue
            lid = f"L_undo_pair_Rollup_{a}_{ab}"
            r, w, rep = self._refuted(lid)
            self.assertEqual((w["x"]["action"], w["y"]["action"]), (a, ab), lid)
            ok = {act for f in fams for act in live_readers.get(f, ())}
            self.assertIn(w["t"][rep["diverges_at"]]["action"], ok, lid)

    def test_refuted_witnesses_replay_on_the_real_contract(self):
        """I27-P7: every REFUTED UNDO witness, both runs (with the pair and without it), replayed independently of holon
        on the real Rollup at the pinned commit (the harness copies taken at this prereg, the binding's deployment): the
        real observations equal the replay report's at every step, and the continuation's observations differ at
        diverges_at."""
        refuted = sorted(lid for lid, r in self.rec.items() if r["status"] == "REFUTED")
        self.assertEqual(refuted, sorted(lid for lid, (_, st) in PREDICTED.items() if st == "REFUTED"))
        traces, meta = [], []
        rep = need(REPLAY3)["laws"]
        for lid in refuted:
            w = self.rec[lid]["witness"]
            with_run, without = witness_runs(w)
            traces += [with_run, without]
            meta.append((lid, len(w.get("prefix") or [])))
        real = realized(traces, "rollup")
        for n, (lid, pre) in enumerate(meta):
            rw, rwo = real[2 * n], real[2 * n + 1]
            self.assertEqual(rw, rep[lid]["with"]["real"], lid)
            self.assertEqual(rwo, rep[lid]["without"]["real"], lid)
            i = rep[lid]["diverges_at"]
            self.assertEqual(rw[pre + 2:pre + 2 + i], rwo[pre:pre + i], lid)
            self.assertNotEqual(rw[pre + 2 + i], rwo[pre + i], lid)

    def test_static_and_kernel_classifications_agree(self):
        """I27-P8 (exit): results/M3/undo/classification.json has the eight UNDO laws, static == kernel for every one
        (5 live = REFUTED, 3 dead = PROVED), no disagreement, no blocked law; `holon gate --milestone M3 --checks G1`
        on a copy writes a report whose "warnings" list holds no GUNDO entry."""
        c = need(CLASSIFICATION)
        self.assertEqual(c["document"], "undo_classification")
        self.assertEqual(sorted(c["laws"]), sorted(PREDICTED))
        for lid, x in c["laws"].items():
            want = "dead" if PREDICTED[lid][1] == "PROVED" else "live"
            self.assertEqual((x["static"], x["kernel"], x["agree"], x["blocks"]), (want, want, True, []), lid)
        self.assertEqual(c["disagreements"], [])
        for lid, r in self.rec.items():
            u = r.get("undo") or {}
            self.assertIs(u.get("agree"), True, lid)
        rep = gate_g1(self)
        self.assertIsInstance(rep.get("warnings"), list, "the M3 gate report carries no warnings list")
        self.assertEqual([w for w in rep["warnings"] if w.get("check") == "GUNDO"], [])

    def test_a_disagreement_warns_and_blocks(self):
        """I27-R5 (part, the exit's "or the gate warns"; construction): in a copy whose CSR residue record is made
        UNKNOWN (no witness), the regenerated classification lists exactly that law as a disagreement (static dead,
        kernel unknown, blocks ["shadow", "window"]) and the M3 gate (G1) lists exactly one GUNDO warning, for it."""
        lid = "L_undo_res_Rollup_revertBatch_committedStateRoots"
        repo = copy_repo()
        try:
            p = repo / "results" / M3 / f"{lid}.json"
            r = need(p)
            r["status"] = "UNKNOWN"
            r["witness"] = None
            r["undo"] = dict(r.get("undo") or {}, kernel="unknown", agree=False)
            p.write_text(json.dumps(r, indent=2, sort_keys=True) + "\n")
            run_ok(self, ["undo", "--milestone", M3, "--root", str(repo), "--out", str(repo / "gen" / M3 / "undo"),
                          "--classify"], cwd=repo)
            c = load_json(repo / "results" / M3 / "undo" / "classification.json")
            self.assertEqual(c["disagreements"], [lid])
            x = c["laws"][lid]
            self.assertEqual((x["static"], x["kernel"], x["agree"], x["blocks"]),
                             ("dead", "unknown", False, ["shadow", "window"]))
            self.assertEqual(sorted(k for k, v in c["laws"].items() if v["blocks"]), [lid])
            rep = gate_g1(self, repo)
            self.assertEqual([w for w in rep.get("warnings") or [] if w.get("check") == "GUNDO"],
                             [{"check": "GUNDO", "law": lid}])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_undo_proofs_check_independently(self):
        """I27-R5 (part; AGENTS rule 6, construction): for every UNDO record, Bend run here on a copy of gen/M3 accepts
        the files that decide it: a PROVED law's gen/M3/proofs/<id>/PROOF.bend and its nonvac PROOF.bend, a REFUTED law's
        gen/M3/proofs/<id>/witness/PROOF.bend; each imports its law file, which declares exactly one law naming
        undo_<x> (uhit_<x> for nonvac); a PROVED residue law's proof imports the core library (the map lemmas); no file
        of an UNDO law holds a hole, @unsafe, def f?, or a foreign import."""
        self.assertEqual(sorted(self.rec), sorted(PREDICTED))
        hatch = re.compile(r"\?[A-Za-z_]|@unsafe|def\s+\w+\?|import\s+\"[^\"]*\.c\"")
        work = Path(tempfile.mkdtemp(prefix="holon-i27-bend-"))
        try:
            shutil.copytree(GEN3, work / "M3")
            for lid, r in self.rec.items():
                x = lid[len("L_undo_"):]
                files = [("laws/" + lid + "/LAWS.bend", "proofs/" + lid + (
                    "/PROOF.bend" if r["status"] == "PROVED" else "/witness/PROOF.bend"), f"undo_{x}")]
                if r["status"] == "PROVED":
                    files.append((f"{lid}/nonvac/LAWS.bend", f"{lid}/nonvac/PROOF.bend", f"uhit_{x}"))
                for law_rel, proof_rel, name in files:
                    law_f, proof_f = work / "M3" / law_rel, work / "M3" / proof_rel
                    self.assertTrue(law_f.is_file() and proof_f.is_file(), f"{lid}: gen/M3/{proof_rel}")
                    lt, pt = law_f.read_text(), proof_f.read_text()
                    self.assertEqual(len(re.findall(r"(?m)^law\s+\w+", lt)), 1, f"gen/M3/{law_rel}")
                    self.assertRegex(lt, r"\b" + re.escape(name) + r"\(", f"gen/M3/{law_rel}")
                    imp = os.path.relpath(law_f, proof_f.parent)
                    self.assertRegex(pt, r"(?m)^import\s+(\./)?" + re.escape(imp) + r"\s", f"gen/M3/{proof_rel}")
                    for t, rel in ((lt, law_rel), (pt, proof_rel)):
                        code_only = re.sub(r"#[^\n]*", "", t)
                        self.assertIsNone(hatch.search(code_only), f"gen/M3/{rel}")
                    if r["status"] == "PROVED" and PREDICTED[lid][0] == "residue" and name.startswith("undo_"):
                        core = os.path.relpath(work / "M3" / "core" / "PROOF.bend", proof_f.parent)
                        self.assertRegex(pt, r"(?m)^import\s+" + re.escape(core) + r"\s", f"{lid}: the map lemmas")
                    code, out = run_bend([proof_f.name], cwd=proof_f.parent, timeout=3600)
                    self.assertEqual(code, 0, f"{lid} gen/M3/{proof_rel}: {out[-2000:]}")
                    self.assertIn("ALL PROOFS CHECK", out, f"{lid} gen/M3/{proof_rel}")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_every_undo_law_has_a_valid_record(self):
        """I27-R5 (part): every UNDO law has a record valid under v1 and v2, with its registry hash, the undo field, the
        nz premise per hash binder, a witness exactly when REFUTED and coverage; the predicted statuses: 3 PROVED, 5
        REFUTED, 0 UNKNOWN."""
        self.assertEqual(sorted(self.rec), sorted(PREDICTED))
        reg = need(LAWS3 / "REGISTRY.json")["statements"]
        v1 = load_json(ROOT / "schemas" / "result_record.schema.json")
        v2 = load_json(ROOT / "spec" / "schemas" / "result_record_v2.schema.json")
        laws = undo_laws()
        for lid, r in self.rec.items():
            self.assertEqual(mini_schema.errors(r, v1), [], lid)
            self.assertEqual(mini_schema.errors(r, v2), [], lid)
            self.assertEqual(r["statement_hash"], reg.get(lid), lid)
            u = r["undo"]
            self.assertEqual((u["subform"], u["undo_id"]), (PREDICTED[lid][0], doc_basis()["laws"][lid]["undo_id"]))
            hb = [b["name"] for b in laws[lid]["statement"]["binders"] if b["type"].startswith("Fn<")]
            self.assertEqual(r["premises"], [f"nz:{h}" for h in hb], lid)
            self.assertEqual(r["witness"] is None, r["status"] != "REFUTED", lid)
            self.assertIn("coverage", r)
        self.assertEqual({lid: r["status"] for lid, r in self.rec.items()}, {lid: st for lid, (_, st) in PREDICTED.items()})


class TestBacktest(unittest.TestCase):
    """results/M3/undo/backtest.json against the M1 UNDO laws."""

    @classmethod
    def setUpClass(cls):
        built()
        cls.bt = need(BACKTEST)

    def test_backtest_table(self):
        """I27-P9: the back-test pairs three of the four M1 UNDO laws: L_undo_CSR -> L_undo_res_Rollup_revertBatch_
        committedStateRoots (PROVED, same), L_undo_BVH -> L_undo_pair_Rollup_commitBatch_revertBatch (REFUTED, same),
        L_undo_BD -> L_undo_res_Rollup_revertBatch_batchDataStore (REFUTED where M1 had PROVED: the extracted document's
        view batchInsideChallengeWindow returns the residue, an action the hand document lacks); L_undo_cancel has no
        analogue (a back-test miss, an open rule gap: gap G5)."""
        self.assertEqual(self.bt["document"], "undo_backtest")
        self.assertEqual(self.bt["against"], "M1")
        exp = basis()["backtest"]
        got = [{k: x[k] for k in ("m1_law", "m1_status", "analogue", "analogue_status", "same_status")}
               for x in self.bt["rows"]]
        self.assertEqual(got, exp["rows"])
        self.assertEqual(self.bt["gaps"], ["L_undo_cancel"])
        bd = next(x for x in self.bt["rows"] if x["m1_law"] == "L_undo_BD")
        self.assertEqual((bd["m1_status"], bd["analogue_status"], bd["same_status"]), ("PROVED", "REFUTED", False))
        self.assertTrue(all(x.get("reason") for x in self.bt["rows"]))

    def test_matched_m1_outcomes_are_identical(self):
        """I27-R2: the analogues of L_undo_CSR and L_undo_BVH keep their M1 outcomes (PROVED, REFUTED)."""
        rows = {x["m1_law"]: x for x in self.bt["rows"]}
        for m1, st in (("L_undo_CSR", "PROVED"), ("L_undo_BVH", "REFUTED")):
            self.assertEqual((rows[m1]["m1_status"], rows[m1]["analogue_status"], rows[m1]["same_status"]),
                             (st, st, True), m1)
            rec = need(RESULTS3 / f"{rows[m1]['analogue']}.json")
            self.assertEqual(rec["status"], st)


class TestSensitivity(unittest.TestCase):
    """A dropped delete moves a law (whitepaper §2.3)."""

    def test_dropping_the_residue_clearing_delete_flips_the_law(self):
        """I27-P10: on the planted toy, derived and run as T271 (baseline) and T272 (without the one delete) under
        holon-rules/1.3: T271 gives exactly the pair law and the roots and stamps residue laws, all PROVED; T272 gives
        the same pair law id REFUTED, the new residue law L_undo_res_ToyUndo_revertLast_pins REFUTED, roots and stamps
        PROVED; the analysis of each variant is what undo_basis_doc's rules give it; both T272 REFUTED witnesses replay
        on the real drop toy, independently of holon: the run with the pair and the run without it first differ at a
        commit step of t, which reverts "pinned" with the pair and succeeds without it."""
        built()
        repo = copy_repo()
        tmp = repo.parent
        try:
            recs = {}
            for ms, t in TOY.items():
                out_s = repo / "gen" / ms / "sorts"
                for args in (["sorts", "--milestone", ms, "--root", repo, "--sidecar", t["sort"], "--out", out_s],
                             ["types", "--milestone", ms, "--root", repo, "--sidecar", t["sort"], "--out", out_s],
                             ["undo", "--milestone", ms, "--root", repo, "--undo-sidecar", t["undo"], "--out",
                              repo / "gen" / ms / "undo"],
                             ["derive", "--milestone", ms, "--root", repo, "--catalog", CATALOG, "--sidecar", t["sort"],
                              "--undo-sidecar", t["undo"], "--out", repo / "laws" / ms, "--obstructions",
                              out_s / "obstructions.json"]):
                    run_ok(self, [str(a) for a in args], cwd=repo)
                an = load_json(repo / "gen" / ms / "undo" / f"{TOY_MODEL}.json")
                exp = analyse(ROOT / t["doc"])
                self.assertEqual((an["pairs"], an["rejected"], an["residues"]),
                                 (exp["pairs"], exp["rejected"], exp["residues"]), ms)
                laws = undo_laws(repo, ms)
                self.assertEqual(sorted(laws), sorted(TOY_LAWS[ms]), ms)
                self.assertEqual(sorted(laws), sorted(laws_of(exp)), ms)
                run_ok(self, ["run", "--milestone", ms, "--sidecar", t["sort"], "--undo-sidecar", t["undo"], "--laws",
                              ",".join(sorted(laws)), "--out", str(tmp / f"results_{ms}"), "--gen-dir",
                              str(tmp / f"gen_{ms}")], cwd=repo)
                recs[ms] = {q.stem: load_json(q) for q in sorted((tmp / f"results_{ms}").glob("L_undo_*.json"))}
                self.assertEqual({lid: r["status"] for lid, r in recs[ms].items()}, TOY_LAWS[ms], ms)
            for ms in TOY:
                for lid, r in recs[ms].items():
                    if r["status"] == "PROVED":
                        nv = r.get("non_vacuity") or {}
                        self.assertEqual((nv.get("status"), nv.get("reachable")), ("inhabited", True), f"{ms} {lid}")
            rec = recs["T272"]
            for lid in (TOY_PAIR, "L_undo_res_ToyUndo_revertLast_pins"):
                w = rec[lid]["witness"] or {}
                self.assertEqual((w["x"]["action"], w["y"]["action"]), ("commit", "revertLast"), lid)
                self.assertTrue(w.get("t"), lid)
                if lid != TOY_PAIR:
                    self.assertIn("k", w, lid)
                    self.assertIn("v", w, lid)
                with_run, without = witness_runs(w)
                real = realized([with_run, without], "T272")
                pre = len(w.get("prefix") or [])
                self.assertEqual(real[0][:pre], real[1][:pre], lid)
                cont_with, cont_without = real[0][pre + 2:], real[1][pre:]
                diff = [i for i in range(len(w["t"])) if cont_with[i] != cont_without[i]]
                self.assertTrue(diff, f"{lid}: the runs do not differ on the real drop toy")
                i = diff[0]
                self.assertEqual(w["t"][i]["action"], "commit", lid)
                self.assertEqual(cont_with[i]["status"], "revert", lid)
                self.assertIn(b"pinned", bytes.fromhex(cont_with[i]["ret"][2:]), lid)
                self.assertEqual(cont_without[i]["status"], "ok", lid)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_dropping_revertbatchs_delete_adds_a_live_residue(self):
        """I27-P11: on the Rollup mutant without Rollup.sol:447 (holon's frontend on a planted copy of the checkout),
        holon undo finds the same five pairs, but the three commit pairs now restore only lastCommittedBatchIndex
        (criteria [cursor, event]: the guard criterion no longer fires) and leave a fourth residue, committedBatches,
        statically live (14 live readers, among them commitBatch's guard Rollup.sol:311 "batch already committed");
        batchDataStore's live readers grow from 1 to 6 (its masking marker committedBatches is no longer cleared);
        committedStateRoots stays dead. Exactly as undo_basis.json "sensitivity" lists."""
        built()
        exp = basis()["sensitivity"]
        tmp = Path(tempfile.mkdtemp(prefix="holon-i27-mutant-"))
        try:
            run_ok(self, ["undo", "--milestone", M3, "--facts", MUTANT_REL, "--out", str(tmp)])
            an = load_json(tmp / "rollup_mutant.extracted.json")
            self.assertEqual((an["pairs"], an["rejected"], an["residues"]),
                             (exp["pairs"], exp["rejected"], exp["residues"]))
            res = {r["family"]: r for r in an["residues"]}
            self.assertEqual({f: r["class"] for f, r in res.items()},
                             dict(CLASSES, committedBatches="live"))
            self.assertEqual(len(res["committedBatches"]["live_readers"]), 14)
            self.assertIn({"action": "commitBatch", "at": "guards[14].reaches[0]"}, res["committedBatches"]["live_readers"])
            self.assertEqual(len(res["batchDataStore"]["live_readers"]), 6)
            for p in an["pairs"]:
                if p["undo"] == "revertBatch":
                    self.assertEqual(p["criteria"], ["cursor", "event"])
                    self.assertIn("committedBatches", p["residues"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestRegressions(unittest.TestCase):
    """Outcomes already recorded that I27 must not change."""

    def test_m1_undo_records_unchanged(self):
        """I27-R1 (part): results/M1/L_undo_* keep their statuses (CSR, BD PROVED; BVH, cancel REFUTED) and laws/M1
        their statement hashes; I20's differential still records the four on m1_view as before (not re-decided)."""
        reg = load_json(ROOT / "laws" / "M1" / "REGISTRY.json")
        for lid, st in M1_UNDO.items():
            r = load_json(ROOT / "results" / "M1" / f"{lid}.json")
            self.assertEqual((r["status"], r["statement_hash"]), (st, M1_UNDO_HASHES[lid]), lid)
            self.assertIn(M1_UNDO_HASHES[lid], json.dumps(reg), lid)
        diff = load_json(ROOT / "results" / "M2" / "differential.json")["laws"]
        for lid, st in M1_UNDO.items():
            self.assertEqual((diff[lid]["m1"], diff[lid]["extracted"]), (st, st), lid)

    def test_pre_i27_m3_records_keep_their_status(self):
        """I27-R3: every M3 record that is not an UNDO law keeps the status it had before I27's first outcome commit
        (read from git: the parent of the oldest commit adding results/M3/L_undo_*); the PAR and SORT laws change only in
        rule_catalog_version. Needs the real checkout's history: a missing .git is a failure, never a skip."""
        def git(*args):
            p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                               env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
            if p.returncode != 0:
                raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
            return p.stdout
        first = git("log", "--diff-filter=A", "--format=%H", "--reverse", "--", "results/M3/L_undo_*").split()
        self.assertTrue(first, "no commit adds results/M3/L_undo_*")
        base = first[0] + "^"
        names = [n for n in git("ls-tree", "--name-only", f"{base}:results/M3").split()
                 if n.startswith("L") and n.endswith(".json") and not n.startswith("L_undo_")]
        self.assertTrue(names, "no M3 record before I27's first outcome commit (I24 and I30 merge first)")
        for n in names:
            old = json.loads(git("show", f"{base}:results/M3/{n}"))
            new = need(RESULTS3 / n)
            self.assertEqual(new["status"], old["status"], n)
            ol = json.loads(git("show", f"{base}:laws/M3/{n}"))
            nl = need(LAWS3 / n)
            self.assertEqual({k: v for k, v in nl.items() if k != "rule_catalog_version"},
                             {k: v for k, v in ol.items() if k != "rule_catalog_version"}, n)


if __name__ == "__main__":
    unittest.main()
