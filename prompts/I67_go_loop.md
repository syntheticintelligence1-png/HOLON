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
- `holon/codecrun.py` (how `holon run` decides codec laws) and `holon/refute_m3.py` (`i4_sides`, `kind_of`, the filter
  stage).

**The docstring of `tests_m3/test_go_loop.py` is the contract** (rules Y1-Y12).

Instruments fixed at the prereg (do not edit them; a wrong instrument is a Question and an amendment line in
`spec/M3/amendments.jsonl`):
- `tests_m3/_i67.py` and `tests_m3/fixtures/go_loop/holon_i67_instrument.go.txt`, written without holon/;
- the sidecars `spec/M3/lib/go_frontend.json` (config 0.2) and `spec/M3/lib/go_ops.json` (the component blob_ops and
  its interface carrier).

Feasibility, disclosed: before this prereg a hand-written spike of the model's shape (the cell sequence consumed one
node per iteration, the index a Nat, the open site a Nat threshold) checked `{ok(W) == False}` at 4096 cells in bend
(0.84 s) and in BendTT --verdict (2.75 s), where a flat array indexed with U32 arithmetic ran out of the kernel's fuel
at 2048 iterations. The opt-in frontend code of Y1 was drafted on the backup branch `claude/ci-i67-wip`; the build
re-does it on this key's base and is judged by the contract, not by the draft. No law of this key was derived, run or
replayed before the prereg; the real code's behaviour on the probes is I18's recorded O4, re-observed by the
instrument.

Deliverables:
- `holon/frontends/go/`: config 0.2 and `loop_bodies` (Y1), byte-identical 0.1 output;
- `spec/M3/facts/morph_blob.go.extracted.json` (Y2);
- `holon/diagram/goops.py`: the Go-op documents, their diagrams and atoms (Y3, Y4), written by `holon codecs`,
  `holon diagram` and `holon evidence` for M3;
- `holon/rules/__init__.py`: the Go-op components among `holon derive`'s committed PAR inputs (Y5); no change to
  `holon/rules/par.py` and no catalog change;
- `holon/gen/goloop.py`: the structural model, the candidates and the counter-laws (Y6, Y7); `holon/codecrun.py`: the
  goops kind (Y8); `holon/gen/refs.py`: statement hashes over a Go-op document;
- `holon replay-go --milestone M3`: the replay of Y9 and `replay/M3/goops/report.json`; `holon/refute_m3.py`'s
  `i4_sides` reads it (Y10);
- the four laws, their records, model and law directories, by the recipe of Y11; `docs/iterations/I67.md`.

Constraints:
- No edit of `holon/rules/par.py`, no rule-catalog change, no other M3 law or record changed (I67-R2).
- No target name in `holon/diagram/goops.py`, `holon/gen/goloop.py` or the frontend (I67-R3).
- A law Bend does not accept stays UNKNOWN with what was tried; the threshold is never lowered and N never reduced.
- Witnesses come from the compiled model; the instrument and the real code only judge them.
- Determinism: two runs write the same bytes (records equal up to seconds).
- Coordination (Y12): I28's build holds holon-rules/1.6. Whichever key merges second re-derives laws/M3 and re-makes
  what changes; tell the other session before merging.

Exit: `tests_m3/test_go_loop.py` green; the prereg audit for M3 passes; gate-M3-partial as at the base or better.
