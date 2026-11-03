# I95 (= I46b): moving I46's E2 with the lead's rulings

You are the builder of I95, milestone M3. I46's comparison of record agrees on 160 of 189 matched M3 classes (0.847).
Every disagreement is a lead decision that the blind run left UNKNOWN:

| Cause | Laws |
|---|---|
| binding | 17 |
| DISCH search budget | 8 |
| budget and clock atoms | 3 |
| clock atoms | 1 |

## The lead's rulings (2026-11-03)

1. **Binding.** Derive it inside the pack with a holon step from code. Never ship the deployment record as an input.
   - `python -m holon binding --milestone M3` re-runs the existing forge deployment (holon.sorts.deploy3, the M2
     harness) on the pinned checkout.
   - It writes gen/M3/binding/<document stem>.json. `--check` reproduces it from a fresh forge run.
   - The pack gives the harness sources and spec/M3/lib/binding.json, which holds configuration only.
   - The scorer adds the binding row: the re-derived record's sha256 against the committed one.
   - **Fallback, only if forge cannot run blind:** a declared input with its sha256 and its generating command,
     disclosed, excluded from the agreement count, with E2 reported both ways.
2. **DISCH budget.** The brief names spec/M3/lib/disch.json's search section. The budget comes from it, not from the
   tooling default.
3. **The clock-atom route.** DISCH's time-monotonicity route handles clock arithmetic written as fixed-width words
   (w_add, w_sub_ok).
   - It stays generic and additive.
   - holon/disch is a closure file, so the landing re-stamps M1/M2/T32.
4. **The scorer.** The amended reads scorer (tests_m3/_i46_reads.py::reads_problems) is preregistered on this key, and
   E5 is reported under both scorers.

## Stage 1: prereg, then build, in one PR

1. **The prereg (C_K) comes first.** The key I95, this prompt, tests_m3/test_blind_rerun_i95.py,
   tests_m3/_i95.py and spec/M3/lib/blind_rerun_i95.json.
2. **Then the build:**
   - the binding step, target-agnostic, with a reproducing `--check`;
   - the clock-atom route;
   - the brief spec/M3/lib/blind_session_i95.md;
   - the binding spec and its committed record;
   - the scorer row.
3. **Checks:**
   - FROZEN, PREREG and AGGREGATES;
   - the target-agnostic test (base items only);
   - this key's tests;
   - a dry run of the binding step in a pack-like sandbox, without reading outcomes.

## Stage 2: after the landing

1. The pack of the lead at the commit that lands I95.
2. A fresh pack-only blind session, launched by the coordinator.
3. Runner jobs from a pack-only orphan branch.
4. `holon compare --blind`, labelled same (Q9).
5. The report docs/iterations/I95.md.
