# The go-ethereum collector's report (I48)

The verbatim final report of the fresh collector agent for `go-ethereum` (given only the frozen protocol, its index record from `holon eval index` and the instrument's commit check), as it handed back to the lead. Kept for provenance: it records the judgment calls, doubts and readings behind `spec/eval/candidates.json` that the candidate records themselves do not hold (I48 build review, finding M3). One edit only: the session's scratch directory prefix is written `<scratch>/`. Paths there are not part of the repository.

---

I finished the go-ethereum collection. It stopped at the 8th eligible candidate (`stopped`: "eighth_eligible"), on the 9th item of the first index. The result is in <scratch>/i48collect/go-ethereum/out/go-ethereum.json.

**Per index:**
- **geth-vulnerabilities:** 9 of 12 items examined, giving 9 candidates (go-ethereum:001 to 009). 8 are eligible and 1 is not.
- **go-ethereum-ghsa:** 0 of 28 items examined (`examined` 0), because the stop came in the first index. Its full item list is still recorded.

**Candidates:**

| Id | Entry | Fix commit | Result |
|---|---|---|---|
| 001 | GETH-2024-01 | 84b12df09e0a (#29534) | eligible |
| 002 | GETH-2023-01 | 7ec60d5f0c45 (#27887) | eligible |
| 003 | GETH-2022-01 | 870b4505a05c (#24507) | eligible |
| 004 | GETH-2021-03 | 3a6fe69f2356 (#23657) | eligible |
| 005 | GETH-2021-02 | 1d995731923c (#23381) | eligible |
| 006 | GETH-2021-01 | ff4ff30a68b6 (#23176, London block) | not_functional |
| 007 | GETH-2020-05 | bddd103a9f0a (#21896) | eligible |
| 008 | GETH-2020-06 | 87c0ba92136a (#21080) | eligible |
| 009 | GETH-2020-01 | 567d41d93637 | eligible |

- Only GETH-2020-01 had a fix named by the index tool. For the other eight I found the earliest master commit that contains the fix with git, using the pull requests and releases the entries and their advisories cite.
- For GETH-2021-02 and GETH-2020-06 the actual fix sits inside a larger squashed PR. I checked the diffs: #23381 is the only core/vm change between v1.10.7 and v1.10.8 and contains the fix; #21080 contains the `createObject` fix.
- Every commit check returned found true and reach true.
- I found no duplicates among the nine.

**Where I had to interpret the protocol:**
1. **Crashes and memory exhaustion as defects.** I counted DoS, crash and out-of-memory bugs as functional under C2d ("fail liveness").
2. **The London entry (GETH-2021-01).** It is an upgrade notice, not a code defect. I named the commit that scheduled the London block (#23176) as its "fix" and excluded it as not_functional, with an exclusion note. The alternative reading would have recorded it as commit_not_found. Either way it is ineligible.
3. **GETH-2020-06.** Its description names commit 223b9509, but as the commit that caused the bug, not the fix. I read "the commit the first source names" as meaning a commit named as the fix, so I used the general rule instead.
4. **GETH-2020-01 (CorruptedDAG).** The commit named in its links is 567d41d, a 2017 ethash refactor. That is probably not the real fix, which looks like d990df9 (#21793). I kept 567d41d because the index rule says to use the named commit "even when a source names a commit that is not the fix". It is the 8th eligible candidate, so this choice decides where the collection stopped.
5. **Supplementary sources.** I gave each link a kind: GHSA and geth vulnerability pages as advisory, pull requests as issue, postmortem pages as postmortem. I left out release and spec links, which match no kind. I also added the fix PRs the linked advisories cite as issue sources, after the item itself.
6. **Write-ups.** Some entries are short, for example "Full details will be available at the Github security advisory". I still judged that each describes the defect itself (for example, crafted p2p messages making the node use very large amounts of memory), so none failed C2a.

The go-ethereum clones are under `clones/` in the workspace. My build script is <scratch>/i48scripts/build_geth.py.
