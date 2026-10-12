# Bend notes: hand-written probes and their verdicts

Probes under `bend/notes/` are hand-written Bend files that record how the pinned checker (Bend 2.0.36, the
fingerprint in `config/holon.json`) behaves on a question a generator depends on. Unlike `bend/probes/` (frozen,
M0 contract), these are agent-written and not frozen. Each verdict below was re-run on 2026-10-12 with
`bend FILE` and `bend FILE --verdict` from the file's own directory; both kernels agree on every file.

| Probe | Question | Verdict (bend, --verdict) | Used by |
|---|---|---|---|
| `p_ir03_fn_verdict/` | Does a `Fn<A,B>` binder with pairwise collision-freedom premises over a finite set check, and does `a != b` agree with `Nat.is_eq(a, b) == False{}`? | `PROOF.bend`: ALL PROOFS CHECK (exit 0), both kernels | I7-P1 (`tests_m2/test_ir03.py::TestFnProbe`); holon.gen.mlaws (erased Fn binders, decidable inequality) |
| `p_ir03_import_depth/` | Do the M2+ prover-separation imports work (`gen/proofs/<law>/PROOF.bend` importing `../../laws/<law>/LAWS.bend`), and what does a proof that does not import its law prove? | see below; recorded in `RESULT.json`, re-run by `run.py` | holon.mpipeline.layout, law_import_problem (audit F-M2-07); holon.gate.laws_in_proofs (F-M2-21) |
| `p_core_import/a` | Can a user proof use an unproved core law through `import ../core/LAWS.bend`? | `core/PROOF.bend`: SOME PROOFS FAIL, 1 TODO (the open law `c_open`); `user/PROOF.bend`: SOME PROOFS FAIL, "expected: a filled definition (an unfilled law is a dead claim: live code cannot use it)", observed `C.c_open` | I8 (holon.gen.core: a core LAWS module is imported only beside its PROOF; G3 `bare_laws_imports`) |
| `p_core_import/b` | Is a core lemma checked once when imported beside its PROOF, and does a wrong helper in the imported PROOF surface in the user's check? | `core_ok/PROOF.bend` and `user/PROOF.bend`: ALL PROOFS CHECK; `core_bad/PROOF.bend` and `user_bad/PROOF.bend` (which imports `core_bad`): SOME PROOFS FAIL, expected `1n`, observed `0n` | I8 (core library import mode) |
| `c_probe/` | Does the C backend build and run a codec in the shape of the M0 model? Where is its arity limit? | `README.md` and `RESULT.json` in the directory: emits C, builds, runs; a segment over 247 parameters fails ("an arity over 247") | I16 (`tests_m2/test_native.py`) |
| `scale_gen.py` | (a generator of scale probes, not a probe) | n/a | `docs/BEND_NOTES.md` calibration |

## p_ir03_import_depth (BUILD_PLAN I7; audit F-M2-17)

Layout: `model/m.bend` (two defs), `laws/a/LAWS.bend` (law `l_a: M.g(1n) == 3n`, importing the model by
`../../`), and one `proofs/<case>/PROOF.bend` per question. `python bend/notes/p_ir03_import_depth/run.py` re-runs
every file and compares with `RESULT.json` (`--write` records it); `tests_m2/test_bend_notes.py` runs it.

| Case | File | Verdict | What it settles |
|---|---|---|---|
| depth 2 | `proofs/a/PROOF.bend` imports `../../laws/a/LAWS.bend` and `../../model/m.bend` | ALL PROOFS CHECK | the M2+ layout (`gen/<m>/proofs/<law>/` beside `gen/<m>/laws/<law>/`) |
| depth 3 | `proofs/deep/x/PROOF.bend` imports by `../../../` | ALL PROOFS CHECK | deeper chains resolve the same way |
| leading `./` | `proofs/dotlead/PROOF.bend` imports `./../../laws/...` | ALL PROOFS CHECK | a leading `./` is accepted (the M0/M1 `import ./LAWS.bend` form) |
| inner `./` | `proofs/dotmid/PROOF.bend` imports `../.././laws/...` | SOME PROOFS FAIL: "expected: an import path of plain names" | a `./` segment inside a path is rejected: generators write normalised relative paths (os.path.relpath) |
| no law import | `proofs/noimport/PROOF.bend` imports only the model | **ALL PROOFS CHECK** (exit 0) | apart from its LAWS.bend, a proof that never imports its law checks vacuously: Bend's own "PROOF.bend must import ./LAWS.bend" rule applies only to files side by side. Every acceptance point must therefore check the import (holon.mpipeline.law_import_problem; audit F-M2-07) |
| law imported, not filled | `proofs/unfilled/PROOF.bend` | SOME PROOFS FAIL: 1 TODO found | importing the law module is enough to make Bend demand its proof: the import check plus Bend's verdict means "the expected law is present and proved" (AGENTS rule 6) |
| wrong proof | `proofs/wrong/PROOF.bend` fills `l_a` with a proof of `g(2) == 4` | SOME PROOFS FAIL: expected `{3n == 3n}`, observed `{4n == 4n}` | the filled law is type-checked against its statement |
| PROOF importing a PROOF, refilling | `proofs/chain/PROOF.bend` imports `../a/PROOF.bend` and refills `Laws.l_a` | SOME PROOFS FAIL: "expected: a fresh name (Laws is an import's alias)" | a law has one proof; a second fill is rejected |
| PROOF importing a PROOF, not refilling | `proofs/chain_reuse/PROOF.bend` imports `../a/PROOF.bend` and the law, fills nothing | ALL PROOFS CHECK | an imported PROOF that fills the law discharges it (sound: that file is checked as part of the import). This is how the I8 core library is used (`import ../../core/PROOF.bend as CP` beside `../../core/LAWS.bend as C`) |
| law declared in a proof | `proofs/law_in_proof/PROOF.bend` declares `law sneaky # a comment` + newline + `: {1n == 2n}` | SOME PROOFS FAIL: 1 TODO found | Bend parses a law across a comment and a line break, so a G3 regex anchored on `law NAME:` misses it; holon.gate.laws_in_proofs removes comments first (audit F-M2-21) |

Both kernels (`bend`, `bend --verdict`) give the same verdict and exit code on every case.
