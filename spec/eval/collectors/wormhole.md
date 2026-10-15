# The wormhole collector's report (I48)

The verbatim final report of the fresh collector agent for `wormhole` (given only the frozen protocol, its index record from `holon eval index` and the instrument's commit check), as it handed back to the lead. Kept for provenance: it records the judgment calls, doubts and readings behind `spec/eval/candidates.json` that the candidate records themselves do not hold (I48 build review, finding M3). One edit only: the session's scratch directory prefix is written `<scratch>/`. Paths there are not part of the repository.

---

I wrote the result to `<scratch>/i48collect/wormhole/out/wormhole.json`. Collection stopped at the 8th eligible candidate (`stopped: "eighth_eligible"`).

**Per index**
- **wormhole-ghsa:** 0 items (index.json lists none), so `examined` is 0 and there are no candidates.
- **wormhole-audits:** 17 reports. I examined 16 of them (`examined` 16), giving 102 candidates. The 17th report, the 2022-01 Neodyme audit, comes after the stop, so its `findings` is null.

**Candidates by report**

| Report | Candidates |
|---|---|
| OtterSec token2022 | 3 |
| OtterSec shims | 2 |
| OtterSec terra | 2 |
| Runtime Verification EVM | 0 (has a note) |
| OtterSec sui | 5 |
| Trail of Bits node | 17 |
| CertiK EVM | 12 |
| OtterSec aptos-nft | 3 |
| Zellic aptos | 6 |
| Hacken near | 1 |
| OtterSec aptos | 6 |
| Coinspect algorand | 5 |
| Trail of Bits solana+cosmwasm | 16 |
| OtterSec near | 14 |
| Kudelski algorand | 4 |
| Kudelski node | 6 of 71 (stopped here) |

**Eligible: 8**

| ID | Finding | Fix commit |
|---|---|---|
| wormhole:009 | Sui watcher "error" substring check | 3eefb74b |
| wormhole:015 | Nil pointer dereference in reloadPendingTransfer | d436ac21 |
| wormhole:016 | Unchecked type assertion in queryCoinGecko | a5092db9 |
| wormhole:019 | PolygonConnector does not handle Unsubscribe | 5d137b6d |
| wormhole:027 | Missing or wrong context | b5f16221 |
| wormhole:028 | defer inside an infinite loop | d8f47407 |
| wormhole:101 | Remote DoS with a single gRPC request | b18a6c8c |
| wormhole:102 | Polygon confirmations / checkpoint finality | ce1ca0b1 |

**Ineligible: 94**
- **commit_not_found (59):** most findings were acknowledged and never patched. Each has a note saying what I searched.
- **not_in_frontend_reach (26):** fixes in Rust, Move or Python.
- **not_functional (8):** documentation, refactoring or hardening suggestions, a dependency bump and a build fix.
- **other_repo (1):** a Kudelski finding fixed in randlabs/pricecaster-v2. That repository can't be cloned (it asks for credentials), so `fix_commit` is null.

**Ambiguities and how I read them**
1. **Report dates.** Several OtterSec reports give no cover date. I used the date they state for confirming patches (near: 2022-09-15, aptos: 2022-10-08, aptos-nft: 2023-02-09). Where there is none, I used the end of the assessment (sui: 2023-05-05, terra: 2024-01-16). Coinspect's "October 2022" became 2022-10-01. Reading the sui date as April 2023 would only swap the order of sui and the Trail of Bits node report; the eligible set would not change.
2. **Finding counts.**
   - CertiK: 12. Its 4 "Optimizations" are a separate section and the report counts them outside its 12 findings, so I left them out.
   - Kudelski node: 71 headed findings, although its summary says 1+2+16+53 = 72.
   - Zellic: its six "Discussion" points are the six findings it rates informational.
   - Trail of Bits node: the bullet list in Appendix C is not counted.
3. **Titles.** I used the heading as the report prints it, including its numbering ("3. Potential nil pointer…", "KS-WH-01 – …"). For CertiK and OtterSec I used the table-of-contents form, because the headings in the body are upper-case or wrapped across lines.
4. **Fix commits for squash merges.** Several reports name commits from an unmerged branch or a fork (OtterSec token2022, shims, near). Those commits can't be reached, so I used the earliest commit on the default branch that contains the fix. For Trail of Bits finding 13 (Go packages), I used the Go 1.20 upgrade d9d54810 because it is the first commit that contains the whole fix; the x/net bump came earlier. For finding 9 I used bd7262d8 and for finding 10 9af1fac9. These two picks are judgement calls, but both candidates are not_functional either way.
5. **Partial fixes.**
   - Finding 15 (wormhole:027): b5f16221 fixes only the Algorand part; the other watchers just got `nolint` comments.
   - Finding 8: the only related commit adds a TODO comment, so I recorded it as commit_not_found.
6. **Borderline judgements.**
   - **wormhole:019 (counted eligible):** Unsubscribe hangs if anyone calls it, but no caller in the code calls it today.
   - **wormhole:018 (counted not_functional):** the context leak only happens on panicking paths and clears when the timeout fires.

   Either call could reasonably go the other way.
7. **Other notes.**
   - I ran `commit_check.py` as the README tells me to. It imports its instrument from /home/user/HOLON-i48; I only ran it and did not read anything there.
   - One fix commit, 9af1fac9, mentions ChainIDScroll in its diff. It is ineligible, and neither its title nor its description names an excluded subject.

My working scripts and the converted texts are in the same workspace, under `tools/`, `txt/` and `cc/`.
