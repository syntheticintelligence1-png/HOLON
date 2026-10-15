# The compound collector's report (I48)

The verbatim final report of the fresh collector agent for `compound` (given only the frozen protocol, its index record from `holon eval index` and the instrument's commit check), as it handed back to the lead. Kept for provenance: it records the judgment calls, doubts and readings behind `spec/eval/candidates.json` that the candidate records themselves do not hold (I48 build review, finding M3). One edit only: the session's scratch directory prefix is written `<scratch>/`. Paths there are not part of the repository.

---

## Compound collector: done. 1 eligible candidate out of 104, stopped "exhausted"

The result is in `<scratch>/i48collect/compound/out/compound.json`. The script that builds it is `<scratch>/i48collect/compound/tools/build.py`. Each title and description is checked in code to be a verbatim excerpt of its report. Every fix commit was checked with `commit_check.py`.

**Per index:**
- **compound-ghsa:** the index tool listed 0 items, so `examined` is 0.
- **compound-audits:**
  - **Page snapshot:** the final URL after redirect is `https://docs.compound.xyz/v2/security/`, sha256 `2c1e5a42ceda081259fee65fb3018795ec38987a11e3a7005d16c5b9ee01b916`.
  - **Items:** 9 audit reports, all examined (`examined` 9). In examination order, with the number of findings:

| Report | Date | Findings |
|---|---|---|
| OpenZeppelin COMP Distribution | 2020-05-22 | 1 |
| OpenZeppelin Tether | 2020-04-26 | 4 |
| Trail of Bits Governance | 2020-02-28 | 3 |
| OpenZeppelin Alpha Governance | 2020-02-25 | 24 |
| OpenZeppelin MCD/DSR | 2020-02-09 | 11 |
| OpenZeppelin Timelock patch | 2019-10-23 | 6 |
| OpenZeppelin Compound Audit | 2019-08-23 | 40 |
| Trail of Bits compound-3 | 2019-08-16 | 5 |
| Trail of Bits compound-2 | 2019-04-08 | 10 |

**Candidates:** 104 in total.
- **Eligible:** 1.
- **commit_not_found:** 65. Most findings were never fixed in the public repository.
- **not_in_frontend_reach:** 25. The fix commits 55729b3, f5976a8, 681833a, bcf0bc7 and f830c48 all have reach false.
- **not_functional:** 13. These are documentation, style, build or gas fixes.
- No duplicates and no excluded_repo candidates.

**The eligible candidate is compound:099.** It is Trail of Bits compound-2 finding "18. Token migration results in orphaned balances". The fix commit is b198cb4dac977c61fa793ffe441c932438e83cdc, "Add sweepToken functionality (#97)", from 2021. It implements the report's recommendation of an admin function to withdraw unsupported ERC20 tokens, and it includes a hypothetical-migration scenario. The commit check found it reachable with reach true.

**Why stopped:** the indexes ran out with only 1 eligible candidate, far short of 8.

**Ambiguities, and how I read them:**
1. **Which commit a source "names":** the Alpha Governance [H02] finding says "Fixed in the follow-up commit f5976a8". That commit only skips a test; the actual code fix is 7158c05 ("Reject actions if they are already queued in the timelock"), which has reach true. I applied the rule literally and used f5976a8, so H02 is not_in_frontend_reach. With 7158c05 it would probably be a second eligible candidate.
   - I also read "names" as "names as the fix". Taken literally, "several: the earliest" would give every finding the earliest commit the report mentions (the audited commit f385d71), which makes no sense.
2. **Headings that are not findings:** I did not count headings that hold no finding of their own. These are the empty group heading "cToken Related Issues" in the OpenZeppelin Compound Audit (its four sub-findings are counted), and the two "Security assumptions" sections in the Tether report.
3. **Partly applied fixes:** when a commit applied a finding's recommendation only in part (for example some typos or one item of a list), I used the earliest default-branch commit with that partial change as the fix.
   - When nothing in the history implemented the recommendation, I used commit_not_found. The note says what I checked.
   - An exception is Trail of Bits compound-3 #24, where requireNoError was removed in the 2022 cleanup a3214f6; I counted that removal as the fix.
4. **Fix only on a side branch:** "earliest commit on the default branch" made me pick master commits even where an earlier commit exists only on another branch or tag. For example I used cce8c88 rather than 1cf0404 or 65e870f.
5. **Root commits:** `commit_check` reports found false for root commits such as f754de9. It did not matter here, because no fix lands in one.
6. **Report titles and dates:** an item's title is the report's own title (the OpenZeppelin page heading, which for the DSR report is just "Compound Finance"). Its date is the date on the report or blog post.
7. **Trail of Bits finding titles:** I took them from the table of contents, which is also verbatim. Two body headings come out of `pdftotext` with broken ligatures ("o f-chain", "ine ﬁcient").
