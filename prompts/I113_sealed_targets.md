# I113 (M6 follow-on): fresh sealed targets, second draw, by commit-reveal

Rendered from the coordinator's I113 brief (2026-11-12), which relays HUMAN_ANSWERS Q86 (the lead's ruling for this
key, committed at the next landing) and binds Q54, Q55, Q56, Q71 and Q72. Read AGENTS.md, docs/BUILD_PLAN.md §0.1 and
§4 "M6: generality", docs/iterations/I106.md and I106's committed files (its forms are reused; its files are never
edited), and spec/eval/corpus.json (the corpus systems, all excluded).

Base: `claude/holon-v2-bend2-c6z3cd`. Branch `claude/i113-sealed-targets`; a draft PR against the lead. Merge commits
only, never rebase, amend or force-push. Commits authored as Claude <noreply@anthropic.com>.

## Why

I106's two targets (EigenLayer, Aave V3) are spent: they have since been run on openly. I110-I112 take down the
pipeline walls that made I107 derive 0 laws. I113 draws and seals 2 fresh, well-known systems nobody tuned HOLON on.
I114 preregisters the measurement blind, and only then are the targets revealed.

## Role

The sealer selects and seals. It never analyses a target and reads nothing of the candidates beyond `git ls-remote`
and what Q55 (1)'s membership check needs.

## Q86, the ruling for this key

1. **The list (Q54 (a)):** at least 8 candidates, fixed in the prereg before the beacon. Membership from a public
   ranking at a fixed snapshot date, by a stated criterion (DefiLlama's top 30 by TVL, or L2BEAT's top 20 by value
   secured). Scope: multi-component, an upgrade history, a public repository, an on-chain core in Solidity or Go.
   Excluded: I106's 9 candidates; the spent targets and their forks; I48's corpus systems; Morph, Scroll and
   across-protocol; the forks of all of these. Each entry gives a name and canonical GitHub URL only; the repos are
   not opened. Membership asserted from memory is checked as Q55 (1) says; a failure is disclosed, never a redraw.
2. **The draw and seal** follow Q54 (b)-(c) and Q55 (2): a new 32-byte salt; a new beacon, the first Ethereum mainnet
   block with timestamp >= T, T at least 20 minutes after the prereg push; the directory `spec/heldout3/`; branch only.
3. **Reads (Q54 (e), Q71):** from the list's push until the reveal only the sealer may read any candidate's repo,
   docs or audits, `target.json` or the salt. No subagent reads a drawn target.
4. **The reveal** comes only after I114's prereg (Q54 (d)).

## The procedure

**(a) Prereg, before any draw.** One commit, pushed after the coordinator's "receipts in" and at least 20 minutes
before T:
- `spec/M6/lib/I113_candidates.json`: the criteria, the snapshot date, the exclusions and the candidates.
- `spec/M6/lib/I113_draw.py`: I106's script generalized in a new file (standard library only): seed, order
  (sha256(seed || id) ascending), the first 2 resolvable candidates, the Q55 (2) pin rule, `seal` and `verify`.
- `spec/M6/predictions/I113.json`: T, the beacon rule, sha256(salt) and both sidecars' sha256s in thresholds.seal.
- `tests_m6/test_i113_sealed.py`: D1, D2, C1 and K1 green at the prereg; S1 (the seal) and R1 (the reveal) red.
- `python -m holon aggregate --milestone M6`, then `python -m holon audit prereg --milestone M6` prints PREREG OK.

The salt comes from `secrets.token_hex(32)` and is kept only in the sealer's session.

**(b) The draw, after T.** The first mainnet block with timestamp >= T, its number and hash, from a public source
(recorded). Seed = sha256(salt || blockhash). Run the committed script. Pin each drawn system by `git ls-remote` only
and record each listing's UTC time.

**(c) The seal.** target.json is built by `I113_draw.py seal` and kept uncommitted in the session. Commit
`spec/heldout3/commitment.json` and `spec/heldout3/README.md`, push, and send the coordinator
`I113 sealed: commitment <12 hex> at block <number>`, with no names.

**(d) The reveal,** on "reveal" from the coordinator or the lead, after I114's prereg is committed: commit
`spec/heldout3/target.json` (the same bytes) and `spec/heldout3/salt.txt`, plus a tests_m6 check that recomputes the
draw and both hashes without the draw script.

**(e) Reads.** Nothing of the candidates beyond `git ls-remote` and Q55's membership check.

**Rulings (Q76's relay rule).** Before the prereg commit, the draw and the reveal, pending messages are read in their
own step; a new ruling is applied and confirmed to the coordinator before going on.

## The PR

A draft against the lead. First line `I113 sealed: commitment <12 hex> at block <number>`, no names until the reveal.
Then Done, Surprises, Questions for the human, Not done. Never the salt or the plaintext before the reveal, in a
commit, PR, comment or message.
