# The optimism collector's report (I48)

The verbatim final report of the fresh collector agent for `optimism` (given only the frozen protocol, its index record from `holon eval index` and the instrument's commit check), as it handed back to the lead. Kept for provenance: it records the judgment calls, doubts and readings behind `spec/eval/candidates.json` that the candidate records themselves do not hold (I48 build review, finding M3). One edit only: the session's scratch directory prefix is written `<scratch>/`. Paths there are not part of the repository.

---

I collected the optimism candidates and wrote them to <scratch>/i48collect/optimism/out/optimism.json. I examined 51 candidates, 8 are eligible, and collection stopped at the 8th eligible one (`stopped: "eighth_eligible"`).

**Per index**
- **optimism-ghsa:** 1 item, 1 examined, 1 candidate, and it is eligible. It is GHSA-rv44-84c7-gvxx, the l2geth balance duplicated on self-destruct. The index names no fix commit, so I took the earliest default-branch commit that contains the fix: 9ef215b830f314739088f2ddb3d140ac30781595, from PR 2146, which the advisory references. Commit check says found and reach true.
- **optimism-security-reviews:** all 48 reports are listed. I dated them and sorted newest first; 3 are examined (`examined: 3`) and the other 45 have `findings: null`.
  - **2026_08-U20-Cantina** (14 findings): 4 eligible (3.1.2, 3.1.3, 3.1.5, 3.1.6). 9 are commit_not_found because OP Labs acknowledged them and did not fix them. 3.2.7 is not_in_frontend_reach, since its fix is docs-only.
  - **2026_06-Interop-L2-Contracts** (29 findings): 0 eligible. 20 are commit_not_found (acknowledged). 7 are not_functional: their fixes are documentation, tests or style changes, all in squash commit f58707536a. 2 are other_repo: the fix is ethereum-optimism/specs PR 916, commit 7b86586e82c5c57fdb4c159050cf5aed71696c07, and commit check found it.
  - **2026_06-OPCMv2-Cantina** (22 findings, 7 examined): 3 eligible: 3.1.1 (fix cadb73d9), 3.2.3 and 3.2.6 (both fix 56ee47e5). 3.2.1 is commit_not_found (acknowledged). 3.2.2, 3.2.4 and 3.2.5 are not_functional because they were resolved with documentation only. The 8th eligible candidate is 3.2.6, so the remaining 15 findings were not examined.
- **Eligible total:** 8, at candidate ids optimism:001, 003, 004, 006, 007, 045, 048 and 051.

**Ambiguities and how I read them**
1. **Short hashes that don't resolve.** The Interop-L2 report names short hashes (da3c4f4 and others) that resolve to nothing in a full clone of the public repo. I treated them as unnamable and used the earliest develop commit containing the fix, which is squash commit f58707536a (PR 21306). Each affected candidate's note says this.
2. **PR numbers instead of commits.** Where the report names only a PR, I used that PR's squash commit on develop: #19281 → cadb73d9, #19272 → 56ee47e5, #19271 → 5161204.
3. **Acknowledged findings.** I recorded these as commit_not_found with a note, after checking develop history. Two later commits looked related but I did not count them as fixes:
   - 2c5719ea removes the anchor allowance; it does not do what U20 finding 3.1.4 asks.
   - PR 23286 removes resendMessage (Interop-L2 3.2.17) as part of a feature redesign.
4. **Documentation-only fixes.** Where the fix commit changes .sol files but the change itself is only documentation, NatSpec, tests or error-declaration cleanup, the reach check passes, so I recorded these as not_functional (C2d).
5. **Judgment calls on functional defects.**
   - OPCMv2 3.2.6 (front-running makes a legitimate `deploy()` revert): I judged this a functional liveness or input-rejection defect.
   - OPCMv2 3.3.14, which I would also have judged functional, comes after the stop point, so it was never examined.
6. **Report dates.**
   - The three reports with no date of their own (2022_05-Bedrock_Contracts-Zeppelin, 2025_03-Interop-Portal-Wonderland, 2025_04-aleph_v) use the commit date that added them.
   - 2021_03 OpenZeppelin states only its audit start (2021-03-15), and I used that.
   - Dapphub "12.01.2021" I read as 2021-12-01, matching the "12/1/21" print header.
   - Report titles for items I did not examine come from the cover headings.
   - None of these affect what was examined.
7. **Exclusions.** No item or candidate named an excluded repo or subject.
