# I67 (= I38a): Go codecs at loop granularity, and O4 at the real blob size

Rendered from `docs/BUILD_PLAN.md` §3 (row I67) and §4 I38. Milestone M3. I38 keeps its number for the compression
half (HypZ, HypZ_len) and for O5, O6, O28 and D3, which this key does not predict.

Whitepaper sources:
- §5.1 (PAR, "including definedness", and PAR-totality: equal definedness of clones over R^ext);
- A2 (hostile input: attack R^ext at every interface carrier; this finds totality and panic defects such as O4);
- §11.3 O4 and Appendix A F3 (the clone panics on a non-canonical element at index >= 3968);
- §10.1 (Go pipelines) and the I38 risk: the kernel must evaluate the real-size law, and 3968 is never re-parametrized
  to a smaller N.

Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md` and `docs/BEND_NOTES.md` first. Then read:
- `docs/iterations/I18.md` and the contract of `tests_m2/test_extract_go.py` (the Go frontend, its sites and O4's
  localization in M2);
- `docs/iterations/I24.md` and the contract of `tests_m3/test_derive_par.py` (the linked codec layer, PAR's producers
  P0-P12, rule X9);
- `docs/iterations/I66.md` and rule V7 of `tests_m3/test_view_evidence.py` (the re-make of M1, M2 and T32 records for a
  change of the generator closures);
- `holon/codecrun.py`, `holon/records.py` (ledger bundles), `holon/bindings.py` and `holon/refute_m3.py` (`i4_sides`,
  `kind_of`, the filter stage).

**The docstring of `tests_m3/test_go_loop.py` is the contract** (rules Y1-Y13).

Instruments fixed at the prereg (do not edit them; a wrong instrument is a Question and an amendment line in
`spec/M3/amendments.jsonl`):
- `tests_m3/_i67.py` and `tests_m3/fixtures/go_loop/holon_i67_instrument.go.txt`, written without holon/;
- the sidecars `spec/M3/lib/go_frontend.json` (config 0.2) and `spec/M3/lib/go_ops.json` (the component blob_ops and
  its interface carrier).

Feasibility, disclosed (the prereg review's finding M6; I67-R4 records it, not counted). Before this prereg, on the
draft branch `claude/ci-i67-wip`:
- **3f17e71, f87fdaa** (2026-10-23): the opt-in frontend code of Y1, run on common/batch and common/blob under config
  0.2. The batch clone's loop body had exactly one panic path, at `common/batch/blob.go:49:102:index`; the blob clone's
  had none. That is the shape I67-R4 records (it was prediction P6 in the reviewed draft).
- **959ef04** (2026-10-23): a model generated from those loop bodies by the draft's `holon/gen/goloop.py`. The
  counter-law `{ok(W) == False}` at 4096 cells checked in bend (3.9 s) and BendTT --verdict (3.7 s) for the batch clone,
  and the blob clone's counter-law failed. That is the model side of I67-P1 and I67-P4.
- A hand-written spike of the same shape: bend 0.84 s, BendTT 2.75 s. A flat array indexed with U32 arithmetic ran out
  of the kernel's fuel at 2048 iterations.

No law of this key was derived, recorded or replayed before the prereg. The weak and domain-coherence laws (I67-P2,
I67-P3) and the derivation (I67-P5) were never run. The real code's behaviour on the probes is I18's recorded O4,
re-observed by the instrument. The build re-does the draft's code on this key's base and is judged by the contract,
not by the draft.

Deliverables:
- `holon/frontends/go/`: config 0.2 and `loop_bodies` (Y1), byte-identical 0.1 output;
  `spec/schemas/facts_0_3_go.schema.json` extended additively;
- `spec/M3/facts/morph_blob.go.extracted.json` (Y2);
- `holon/diagram/goops.py`: the Go-op documents, their diagrams and atoms (Y3, Y4), written by `holon codecs`
  (`--goops-out`), `holon diagram` and `holon evidence` for M3; `spec/schemas/evidence.schema.json` admits
  holon-goops/0.1;
- `holon/rules/__init__.py`: the Go-op components among `holon derive`'s committed PAR inputs (Y5); no change to
  `holon/rules/par.py` and no catalog change;
- `holon/gen/goloop.py`: the structural model, the candidates, the counter-laws and the generated ledger bundle (Y6-Y8);
  `holon/codecrun.py`: the goops kind; `holon/gen/refs.py`, `holon/ir.py`, `holon/records.py` and `holon/bindings.py`:
  the statement refs, the binder type, the bundle and the bindings over a Go-op document (Y8);
- `holon replay-go --milestone M3` (`holon/goreplay.py`): the replay of Y9 and `replay/M3/goops/report.json`;
  `holon/refute_m3.py`'s `i4_sides` reads it and `kind_of` tests K2 before K1's definedness clause (Y10);
- the outputs, by the recipe of Y11, in its order; `docs/iterations/I67.md`.

The window between merges: after this prereg merges and before the build merges, M3's full-gate G1 reports
`spec/M3/facts/morph_blob.go.extracted.json` missing (the base frontend refuses config 0.2). CI runs no M3 G1.

Constraints:
- No edit of `holon/rules/par.py`, no rule-catalog change, nothing outside rule Y11's recipe changes (I67-R2, I67-R5).
- No target name in `holon/diagram/goops.py`, `holon/gen/goloop.py` or the frontend (I67-R3).
- No module of a generator closure comes to import one of I32's files.
- A law Bend does not accept stays UNKNOWN with what was tried; the threshold is never lowered and N never reduced.
- Witnesses come from the compiled model; the instrument and the real code only judge them.
- Determinism: two runs write the same bytes (records equal up to seconds); the replay report has no scratch path.
- Coordination (Y12): I28's build holds holon-rules/1.6 and re-makes the M3 records. Whichever key merges second
  re-derives laws/M3 and re-makes what changes; tell the other session before merging.

Exit: `tests_m3/test_go_loop.py` green; the earlier tests amended at this prereg green; the prereg audit for M3 passes;
CI's 11 jobs pass as at the base.
