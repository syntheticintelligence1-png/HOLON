# The arbitrum collector's report (I48)

The verbatim final report of the fresh collector agent for `arbitrum` (given only the frozen protocol, its index record from `holon eval index` and the instrument's commit check), as it handed back to the lead. Kept for provenance: it records the judgment calls, doubts and readings behind `spec/eval/candidates.json` that the candidate records themselves do not hold (I48 build review, finding M3). One edit only: the session's scratch directory prefix is written `<scratch>/`. Paths there are not part of the repository.

---

The arbitrum collection is finished and stopped at the 8th eligible candidate (`stopped: "eighth_eligible"`). Result: <scratch>/i48collect/arbitrum/out/arbitrum.json

**Per index**
- **arbitrum-ghsa:** the index tool's list has 0 items, so 0 were examined and there are 0 candidates.
- **arbitrum-audits:** I fetched the page once (final URL https://docs.arbitrum.io/audit-reports, sha256 8e41c4ff9f7f2a78cc42721a404df3125710963ed602fd6ae8be52d7003b52d7). It links 48 PDF reports, all published before the cutoff, and all 48 are listed. I examined the first 18 and recorded 98 candidates. The stopping item is the ArbOS 40 Nitro report (2025-05-06): it holds 6 findings, and its 5th gave the 8th eligible candidate, so it yields 5 candidates.

**Eligible candidates (8)**
| id | finding | fix commit |
|---|---|---|
| arbitrum:008 | ArbOS 60/61: non-deterministic map iteration in multi-gas constraint precompiles | nitro 90213f9d |
| arbitrum:011 | ArbOS 60/61: RevertToSnapshot after Finalise panics in the extraPostTxFilter error path | nitro fb4e3b9b |
| arbitrum:020 | External DA: missing validations in executeValidatePreimage | nitro-contracts 76c5e0a0 |
| arbitrum:021 | External DA: missing sequencer message length checks | nitro 8dff9a2c |
| arbitrum:023 | External DA: unclear behavior during sequencer message parsing | nitro 4074e407 |
| arbitrum:084 | ArbOS 50/51: possible underflow in the gas charging hook | nitro 60ba39af |
| arbitrum:095 | ArbOS 40: missing deployment of the EIP-2935 contract | nitro 77da75a6 |
| arbitrum:098 | ArbOS 40: error handling issue in Code retrieval | nitro 56c19624 |

**Ineligible candidates (90)**
- **other_repo, 65:** the findings sit in token-bridge-contracts, stylus-sdk-rs, ArbitrumFoundation/governance, fund-distribution-contracts, genesis-file-generator, OffchainLabs/go-ethereum or sys-asm. Every named fix commit passed `commit_check`; where none could be named the field is null and a note says why.
- **commit_not_found, 21:** no public fix exists. Examples are the private OSP guard repo, unfixed ArbOS 60/61 findings 3 and 5–9, and the mint/burn findings the client marked as intended behavior. Each has a note saying what I searched.
- **not_functional, 4:** gas-charge ordering, a comment-only fix, an unused constant, and a duplicate-of-nothing check is not needed here. There are 0 duplicates.

**Ambiguities and how I read them**
1. **Report date.** I used each report's own cover date, not the page's date. Seven reports differ from the page:
   - the sequencer liveness and custom fee ERC-20 bridge reports are dated 2025-03-31;
   - four reports are dated 2025-03-12;
   - the Nova fee router report is dated 2024-03-20.
   I turned month-only dates into the 1st of the month: ConsenSys "May 2022" became 2022-05-01 and "November 2021" became 2021-11-01. Same-date ties are ordered by item URL.
2. **What counts as a finding.** I counted only numbered findings (ToB "N.", OZ "C/H/M/L/N-xx"). Unnumbered code-quality bullet points in appendices are not counted. So Sequencer Feed Ticketing, Upgrade Executor and Block Hash Pusher have findings 0 with a note. Tip Collection Toggler and the 3.2.0 Upgrade Action also have 0, because they report no issues.
3. **Fix commit when the report names only a PR.** I took the earliest commit on the default branch that contains the fix, or the squash or merge commit when the PR was squashed.
   - For YBB finding 3, I picked the fixup commit 5260704d because it completes both checks; 800b4bfc added only the ETH check, one day earlier.
   - For ArbOS50-6, the fix 7f8f60fa is reachable only from feature branches, not the default branch. That does not matter, since the candidate is not_functional.
4. **Judgment calls you may want to look at.**
   - arbitrum:011: the panic can't happen in the shipped code, because extraPostTxFilter is a no-op. I counted it as a liveness defect for chains that implement the hook.
   - arbitrum:095: I counted "missing contract deployment" as functional, since EIP-2935 history calls fail without it.
   - arbitrum:098: I counted the silent success when caching a program with empty code as accepting an input it should reject.
5. **Descriptions.** Each is one contiguous excerpt that avoids page footers and zero-width characters. Where the first paragraph only gave context, I used the paragraph that states the defect. That applies to YBB-3, Quorum-2, ArbOS60-2, ArbOS50-1, ArbOS50-2, ArbOS40-1 and EXTDA-2.

**Other notes**
- `commit_check.py` imports code from /home/user/HOLON-i48. I ran it as instructed but never read anything under /home/user.
- No Scroll or Morph material appeared anywhere.
- My working clones, PDFs and scripts are under /tmp/arbcollect.
