# HOLON v2: violations as obstructions to commutation, in Bend 2

**Status: M0 and M1 complete.**
- **M0:** the factory loop on the Morph batch-header codecs.
- **M1:** the Rollup state machine (UNDO, SORT, DISCH, FACT, SYM, NAT) plus the Go OWN aliasing law. 17 laws: 9 PROVED (dual-kernel) and 8 REFUTED, every refutation replayed on the real code. Details are in `docs/M1_REPORT.md`; the architecture is in `docs/ARCHITECTURE.md`.

M0 results:

| Law | Outcome | Second kernel (BendTT) | Replay on real code (morph `3e44e79`) |
|---|---|---|---|
| L_par_hdr_v0, L_par_hdr_v1 | PROVED | checked | n/a |
| L_rt_go_v0, L_rt_go_v1, L_rt_go_v2 | PROVED | checked | n/a |
| L_par_hdr_v2 | REFUTED (finding O2/F12.2) | checked | Go passed |
| L_dom_hdr | REFUTED (finding O1/F12.1) | checked | Go passed, Solidity passed |
| L_par_hdr_ssvh | REFUTED (intent question) | checked | Go passed |

```
tools/setup_env.sh                       # Bend 2.0.36 (pinned) + Lean 4.34.0 for --verdict
python -m holon run  --milestone M0      # facts -> model -> laws -> proofs / counter-laws -> records
python -m holon gate --milestone M0      # GENV, G1-G5, G7 (dual kernel), G11, 16 canaries
python -m unittest discover -s tests -t .

python -m holon run  --milestone M1      # 16 state-machine laws (spec/M1, laws/M1)
python -m holon gate --milestone M1      # incl. 21 canaries
python -m holon replay --milestone M1 --morph <morph checkout> --solc <solc 0.8.24>   # Foundry + go test
python -m unittest discover -s tests_m1 -t .    # HOLON_REPLAY=1 to include replay
```

The rest of this README is the original starter-kit guide that framed M0. It is kept for the session-by-session workflow.

---

## HOLON starter kit: milestone M0 (Morph header laws, end to end)

This kit turns the HOLON v2 whitepaper into work an agent can execute and you can review. M0 runs the whole factory loop once, on a small known target:

> facts → generated Bend model → frozen laws → kernel-checked proof **or** kernel-checked counter-law → gate (canaries + tamper resistance) → replay of witnesses on the real Morph code

## Should the agents study Bend 2 first?

Yes, but as one short empirical session (P0, 1–2 hours), not a study phase. Bend 2 was released on 17 Sep 2026, after the models' training data, so their instincts about "Bend" refer to Bend 1, a different language. The fix is cheap:

- The official guide is about 680 lines. Agents read all of it (`bend guide`).
- `docs/BEND_PRIMER.md` lists the gotchas I hit while verifying, and the exact patterns HOLON needs.
- `bend/probes/` contains 16 tiny Bend files. Each has a known verdict, and a frozen test re-runs them. An agent that misunderstands the language fails there, before it writes a generator.

## What I verified myself (Bend 2.0.36, `bendlang/bend@2343aec`)

**Bend behaviour:**
- **Headers.** The full 257-byte Morph v1 header, Solidity's overlapping `mstore` writes over dirty memory vs. Go's `PutUint64`/`copy`, proves equal by computation in about 0.3 s. The v2 version is rejected, and the error shows byte 0 as 2 vs. 1.
- **Refutations.** Counter-laws (refutations the kernel checks) work. A counter-law for an equal pair is rejected.
- **Hazards.** A file with **zero laws prints ALL PROOFS CHECK**. Proof files cannot redefine model defs. `?TODO`, open laws and `@unsafe` all fail the check.

**End-to-end check with a private implementation.** I wrote one to make sure the tests are passable and actually bite. It is not shipped, so the agents still do the real work. Results:
- **Predictions held.** All 8 preregistered M0 outcomes matched on the first mechanized run (5 PROVED, 3 REFUTED), in about 7 s.
- **Mutation tests passed.** All 4 planted bugs moved the outcomes exactly as predicted.
- **Gate passed** with 11 canaries, all rejected.
- **Cheating emitter caught.** An emitter that silently writes `{L == L}` passes every check *except* the canaries. That is why the canaries exist.
- **Real tamper vector caught.** A `bunfig.toml` preload in the repo can inject code into a checkout-based Bend. The gate now refuses to run in that case.

**Not verified here** (my sandbox blocked the downloads; P0 and P5 cover them):
- `bend --verdict`, the Lean-proven second kernel built into Bend. It needs Lean v4.34.0.
- The official installer binary.
- The Devin environment.
- Replay against the real Morph repo.
- The facts against the real repo. I extracted them from your audit bundle, not from the repo, and P5 audits them line by line.

## How to run it

1. **Create the repo.** Make an empty GitHub repo, copy this kit in, and commit. Optionally save the whitepaper as `docs/HOLON_v2.md`; it is background only.
2. **Protect the frozen paths.** Add branch protection on `main`, and ideally a CODEOWNERS file assigning `facts/ laws/ predictions/ schemas/ tests/ bend/probes/ docs/M0_SPEC.md docs/BEND_PRIMER.md AGENTS.md tools/freeze.py` to you.
3. **Run one Devin session per prompt, in order.** Paste the prompt file's contents as the task. One PR per session.

   | Session | Builds | Tests that must pass |
   |---|---|---|
   | `P0_bend_calibration.md` | install + pin Bend, verify `--verdict`, scale limits | 00, 01, 02 |
   | `P1_ir_and_layout.md` | `holon/ir.py`, `holon/layout.py` | 10, 11, 12 |
   | `P2_model_generator.md` | facts → Bend model, `eval_batch` via compiled JS | 20 |
   | `P3_pipeline.md` | emitter, proof generator, refuter, counter-laws, `holon run` | 30, 31 |
   | `P4_gate.md` | `holon gate`, canaries, tamper resistance | 40 (then all) |
   | `P5_replay.md` | facts audit + witness replay on real Go/Solidity | 50 (`HOLON_REPLAY=1`) |
   | `P6_audit.md` | adversarial audit, fresh session, different model if you can | writes `audit/M0_round1.md` |

4. **Review each PR quickly:**
   - `python tools/freeze.py digest` prints the digest pinned in the prompts: `f854d69b0b58b581eb205a657d6925cc1e1460141ef9626df89ea87de1594fd0`. If it differs, reject the PR. Only you run `tools/freeze.py write`.
   - The pasted test output matches what the session claims.
   - Read the "Surprises" and "Questions for the human" sections. Those are where the value is.

All tests use only the Python standard library:

```
python -m unittest discover -s tests -t . -v
```

## What the predictions say, and what a "finding" means

| Law | Predicted outcome | What it corresponds to in the earlier analysis |
|---|---|---|
| L_par_hdr_v2 | REFUTED | No Go encoder for version 2 (F12.2) |
| L_dom_hdr | REFUTED | Solidity accepts version-0 headers longer than 249 bytes; Go does not (F12.1) |
| L_par_hdr_ssvh | REFUTED | **Intent question, not a bug:** it surfaces the premise that Go producers must set `sequencerSetVerifyHash = 0` |
| The 5 others | PROVED | Certified absent, relative to the model |

None of this becomes a reportable finding until P5 replays the witness on the real code.

## After M0

M1 (whitepaper §15.2) is the rollup state-machine slice: UNDO, DISCH and NAT on commit/revert/challenge, where F2, F4, F7 and N1 live. It should start from the same factory. The P0 scale numbers tell you how big a model Bend handles comfortably.

## Layout

```
AGENTS.md            standing rules for every session (frozen)
FROZEN.sha256        manifest of protected files (tools/freeze.py)
docs/                M0_SPEC.md (contract), BEND_PRIMER.md (verified Bend notes)
facts/               morph_header.json, hand-extracted, with source references
laws/M0/             8 frozen law statements (holon-ir/0.1) + REGISTRY.json of hashes
predictions/         preregistered outcomes + planted-bug mutations
schemas/             facts, law IR, result record, gate report
bend/probes/         16 verified Bend probes + manifest
tests/               acceptance tests + tests/reference (the trusted oracle)
tools/               freeze.py, install_bend.sh
config/              holon.example.json (P0 creates holon.json)
prompts/             P0–P6 session prompts
```
