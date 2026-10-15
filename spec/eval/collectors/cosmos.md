# The cosmos collector's report (I48)

The verbatim final report of the fresh collector agent for `cosmos` (given only the frozen protocol, its index record from `holon eval index` and the instrument's commit check), as it handed back to the lead. Kept for provenance: it records the judgment calls, doubts and readings behind `spec/eval/candidates.json` that the candidate records themselves do not hold (I48 build review, finding M3). One edit only: the session's scratch directory prefix is written `<scratch>/`. Paths there are not part of the repository.

---

I wrote the cosmos result to <scratch>/i48collect/cosmos/out/cosmos.json. Collection stopped at the 8th eligible candidate ("eighth_eligible"), on the 13th item of the first index.

**Per index:**
- **cosmos-ghsa** (24 items): 13 items examined, giving 13 candidates (cosmos:001–013).
- **cosmos-sdk-audits** (2 reports): 0 examined. Both reports are still listed with their dates and titles, and findings is null.
- **ibc-go-audits** (7 reports): 0 examined. All seven are listed the same way.

**Eligible: 8.** These are cosmos:001, 005, 007, 008, 009, 010, 012 and 013. Every one has a fix commit the commit check found, with reach true.

**Ineligible: 5.**
- **cosmos:002, GHSA-56j4 (Babylon): other_repo.** The fix is babylonlabs-io/babylon fe67aebd; the commit check found it.
- **cosmos:003, GHSA-h2rp (cheqd upstream patch): other_repo.** The fix is cheqd/cheqd-node 5a58b08; the commit check found it.
- **cosmos:004, GHSA-4wf3 (ISA-2025-001): duplicate of cosmos:007.** The advisory names no commit. I searched ibc-go history around the March 12, 2025 releases. The fix on main is 4effdd6f, a "Merge commit from fork" that changes modules/core/04-channel/keeper/packet.go; the commit check found it, with reach true.
- **cosmos:006, GHSA-33cr (cheqd advisory): duplicate of cosmos:007.** Its named fix is ibc-go 59987d5, a backport of the same transfer ibc_module.go fix. Its fix date is later than 007's 9869b3c.
- **cosmos:011, GHSA-qjcv (Huckleberry): no_public_writeup.** The advisory's details only say ibc-go "is affected by" the Huckleberry vulnerability, without describing the defect.

**Ambiguities and how I read them:**
1. **cosmos:004 as a duplicate.** Its fix changes different code (core 04-channel) from 007's (the transfer app). But the advisory calls it an extension of the earlier patch, giving "full coverage against the reported issue", and it comes from the same HackerOne report. I treated it as the same root cause and same defect. If "same code" is required strictly, 004 would instead be eligible. That would not change the stop point, because the 8th eligible would then be cosmos:012.
2. **cheqd advisories naming no system-repo commit (cosmos:003).** I treated the fix as cheqd-node's own dependency-bump commit, so the candidate is other_repo. I did not trace it back to the upstream cosmos-sdk or ibc-go fix.
3. **cosmos:011's write-up.** Judging that one sentence naming a codename is not a description of the defect is my judgment call.
4. **Report dates for the unexamined audits** (used only to order the items):
   - **IBC-v2 Sherlock report:** it states only "Date Audited: February 12 - March 6, 2025", so I used the commit date that added the file, 2025-04-09.
   - **Halborn report:** I used its last revision date, 2023-02-28.
   - **Atredis channel-upgrade report (file named v1.1):** I used its stated date, March 7, 2024 (version 1.0).
5. **exclusion_note on other_repo candidates.** I set it to null when the fix commit is named, following the README.

The commit check script imports from /home/user/HOLON-i48. I ran it as the README instructs but read nothing under /home/user. I did not open any Scroll or Morph item.
