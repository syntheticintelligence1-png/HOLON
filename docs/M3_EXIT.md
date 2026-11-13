# M3 exit

**The M3 exit is met.** The rule is spec/M3/lib/blind_rerun.json's: "the M3 exit is met iff E1-E5 all hold". The lead
records the decision on 2026-11-11, on the lead as it stands after round 9's landing (#158). E1, E2 and E3 hold by
their instruments. E4 and E5 hold by the human's adjudications, HUMAN_ANSWERS Q44 and Q43, and not by their
instruments, as every report of this exit must say.
`tests_m3/test_m3_exit.py` recomputes each clause and checks this table against it.

| Clause | Text | Holds | How | Evidence |
|---|---|---|---|---|
| E1 | the comparison regenerates: `holon report --milestone M3 --check` prints REPORT OK on the final head | yes | instrument | REPORT OK on the lead after round 9's landing (#158), and on this record's own head |
| E2 | M3's blind_agreement >= 0.90 over at least 40 matched M3 classes | yes | instrument | `audit/blind/I96/compare.json`: 205 of 207 matched M3 classes agree (0.990). 207 of the lead's 275 M3 laws are matched (0.753), so the claim is scoped to the matched set. The blind session is of the builders' model family (Q9). |
| E3 | `results/M3/audit_status.json` has converged = true | yes | instrument | converged: 4 consecutive counted clean rounds (rounds 6, 7, 8 and 9; k = 3), 7 rounds counted, no open high-priority finding |
| E4 | `results/M3/backtest.json` has no exit_blockers | yes | adjudication (HUMAN_ANSWERS Q44) | The back-test's one blocker, `gap:M0:L_par_hdr_v2`, is closed by M3's real-path law `L_par_cc_BatchCache_createBatchHeaderWithSequencerSetHash_enc_sol_v2_pinned` (PROVED). The table still lists it: the back-test checked no implication. The closing law states the V2 header's encoding with its blob-hash field taken as given. How that field is aggregated is constrained by no M3 law (F-M3-45, open). |
| E5 | the reads check passes (the run is blind) | yes | adjudication (HUMAN_ANSWERS Q43) | I96's session, scored by both scorers: 19 flagged calls (preregistered) and 3 (amended), all judged harmless |

## Disclosures

1. **Same-family audit rounds (HUMAN_ANSWERS Q9b).** Every counted round was audited by a fresh agent session of the
   builders' model family, launched by the coordinator. Its independence is a fresh context only (whitepaper §9.5,
   L19).
2. **Same-family blind rerun (Q9).** I96's blind session is of the builders' family.
3. **A plain-language rule approval (Q42).** `PAR_record_round_trip`, the rule I100 adds, was admitted on the human's
   plain-language approval. The lead recorded it with the hash of the approved line (`spec/M3/lib/rule_approvals.json`).
   It is not a signature (whitepaper L7).
4. **E4 and E5 by adjudication (Q44, Q43),** disclosed in whitepaper §11.3 and L8. The records are
   `spec/M3/lib/exit_rulings.json`, bound to the back-test's exact blockers and to the blind run's sha256.

## The audit (E3)

| Round | Family | Ruling | Counted | Clean | Target | A1 mutants (detected) | A2 cases | a4.json rebuilt from the target |
|---|---|---|---|---|---|---|---|---|
| 1 | same | none (I87's dry run) | no | yes | 2b4578af | 0 | 0 | not checked (not counted) |
| 2 | same (Devin; its model not attested) | none | no | yes | c3eda197 | 0 | 0 | not checked (not counted) |
| 3 | same | HUMAN_ANSWERS Q9b (by number) | yes | no | 5e2436f9 | 4 (0) | 60 | not checked (before the streak) |
| 4 | same | HUMAN_ANSWERS Q9b (by number) | yes | no | 4dada37b | 4 (2) | 17 | not checked (before the streak) |
| 5 | same | HUMAN_ANSWERS Q9b (by number) | yes | no | bc89b12d | 12 (6) | 53 | not checked (before the streak) |
| 6 | same | HUMAN_ANSWERS Q9b | yes | yes | ed893be8 | 12 (6) | 51 | identical |
| 7 | same | HUMAN_ANSWERS Q9b | yes | yes | ef39bed5 | 11 (6) | 52 | identical |
| 8 | same | HUMAN_ANSWERS Q9b | yes | yes | dadfb280 | 7 (5) | 54 | identical |
| 9 | same | HUMAN_ANSWERS Q9b | yes | yes | da95f80f | 17 (11) | 66 | identical |

- **No counted round of the streak is hollow** (F-M3-37). F-M3-27's evidence rule reads only the records' headers.
  So this record checks content directly:
  - each round's a4.json, rebuilt from its own target by `holon audit vacuity --round n --check`, is identical;
  - its A1 and A2 records hold the mutants and hostile cases that ran.
- **Open findings at the exit:** 17 medium and 6 low, none high-priority. Medium: F-M3-01, 02, 04, 05, 07, 09, 10, 11, 12, 15, 21, 24, 26, 36, 37, 44 and 45. Low: F-M3-03, 06, 08, 20, 38 and 42. None is high-priority.

## What changed after round 9's target

Round 9 audited `da95f80f`: #150's head, with #146's head merged in. Between that and the exit head, the files that
differ are:
- **No code.** No file under `holon/` or `tools/` differs, and the CI workflow is unchanged. Round 9 audited the code M3 exits on.
- **Audit files (92):** rounds 8 and 9's round files and evidence, and the findings and rule-gap ledgers with the lead's triage.
- **Generated outputs (67):** I100's landing re-make and the M1/M2/T32 re-stamp, the regenerated summaries (`docs/STATUS.md`, `docs/M3_COMPARISON.md`, `spec/M3/appendixA_map.json`), the 12 new laws' bindings (`spec/bindings/M3.json`, `spec/bindings/changes.jsonl`), and the convergence status.
- **Data and docs (3):** the Q44 row of `docs/HUMAN_ANSWERS.md`, E4's adjudication in `spec/M3/lib/exit_rulings.json`, and `whitepaper.md` §11.3.
- **Tests (1):** `tests_m3/test_exit_rulings.py`, covering E4's adjudication.
- **This record's own files:** `docs/M3_EXIT.md`, `tests_m3/test_m3_exit.py`, the CI audit job's module list, §11.3's scope note for Q44 (from F-M3-45), and the regenerated `docs/M3_COMPARISON.md` and `spec/M3/appendixA_map.json`.

## After the exit

These land after this record, in order:
1. #152, the prereg audit's `parallel_outcome` licence;
2. the test_derive_par / test_par_outcomes fix;
3. the M4 and M5 PRs.

Landed since, in order:
- #152, #162, the M5 stack (#163) and the M4 stack (#164).
- #165, I101: the post-exit fixes of F-M3-37 (the counted-round evidence rule reads each record's content, and CI rebuilds the streak's a4.json and packet.json from their targets: `audit-M3-evidence`), F-M3-38 (the rendered audit prompts state Q9b's rule) and F-M3-42 (a subset run keeps what it does not own).
- #166, I102: `holon audit regress` compares each commit with its own parents (F-M3-07 and its duplicate F-M3-30).
- With the lead's records PR: F-M3-08 marked fixed by I100, whose record laws and constant read-backs closed the back-test gaps `gap:M0:L_rt_go_v0`, `_v1` and `_v2` (the only exit blocker left is `gap:M0:L_par_hdr_v2`, closed by HUMAN_ANSWERS Q44).

None of these changes a clause of the decision above. E3 stays converged, with `results/M3/audit_status.json` byte for byte as at the exit. Open findings now: high 0, medium 15, low 3.

## Provisional caveat (2026-11-13, HUMAN_ANSWERS Q94)

**F-M6-01, high, open: a defect of HOLON's own extraction, found after this exit.** Until I117, the Go frontend's path
reasoner read Go integers as unbounded. It pruned branches reachable only through wraparound, and called index sites
safe that wrap out of bounds.
- **The documents.** I119's read-only audit and the lead's own re-extraction agree: 3 of Morph's 8 committed Go
  documents change under the opaque-arithmetic rule alone (`spec/M2/facts/morph_batch.go`,
  `spec/M3/facts/morph_blob.go` and `spec/M3/facts/morph_go03.go`).
- **The laws.** At least 28 of M3's 179 committed decided laws (PROVED and REFUTED together, Q56) read one of them
  through their decision traces. 79 more decided M3 laws, and every decided M0-M2 law, have no trace, so committed
  data does not say whether they read one. No law is named here; the list is in I119's vault.
- **What is provisional.** Until I119 (b) re-derives and re-decides these laws, their statuses are provisional, and so
  is every number in this record that rests on them.
- **The decision above** stands as recorded on 2026-11-11. Whether E1-E5 still hold, E3's "no open high-priority
  finding" included, is re-decided after I119 (b) and recorded here as an amendment.
