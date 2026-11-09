# I97: the F-M3-13 fix (BendTT/G7 on M3)

Round 3 of the M3 audit filed F-M3-13, and the lead ruled it high under Q8. Two things are wrong:
- **G7 cannot pass on M3.** Six decided REFUTED records have a BendTT rejection: bend2 accepts each proof, and BendTT
  reports the kernel mismatch.
- **CI never runs G7, G1, G4 or G6 on M3,** so a forged dual-kernel claim passes CI.

**The work.**
- **Minimize** each rejection to the smallest PROOF.bend/LAWS.bend pair that bend2 accepts and BendTT rejects, and
  name its construct.
- **Classify** each one by the lead's ruling:
  - an unsupported construct is recorded single-kernel (I1) with that reason, and G7 accepts it by reason;
  - a real disagreement takes the REFUTED verdict to UNKNOWN until both kernels agree. Disclose it, and never drop
    the law.
- **Put the classification in code.** It lives in the record-making code and the gate (holon/bend.py, the shared
  check, holon/gate.py), never in a record.
- **CI** runs G7 for M3, and G4 and G6 where the budget allows. Document any check left out.
- **A test** plants round 3's forged claim and shows the check set refusing it.
- **Hand the re-make to the lead.** Whatever moves is re-made by the lead, and the PR gives the exact plan.

The contract is the docstring of tests_m3/test_bendtt_i97.py. The predictions in the key are fixed before any build.
