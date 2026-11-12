# I106 (M6, generality): fresh sealed targets, by commit-reveal

Rendered from docs/BUILD_PLAN.md §4 I106 and the "M6: generality" section, and the coordinator's I106 brief
(2026-11-12), which relays HUMAN_ANSWERS Q54 (the lead's delegated ruling on this procedure). Read AGENTS.md,
BUILD_PLAN §0.1, §4 I49/I50 and "M6: generality", HUMAN_ANSWERS Q7 (the first sealing), docs/iterations/I49.md
(the sole-reader rule) and spec/eval/corpus.json (the corpus systems, all excluded).

Base: the lead's M6 skeleton, `claude/ci-m6-skeleton`, merged onto `claude/holon-v2-bend2-c6z3cd`. Branch
`claude/i106-sealed-targets`; a draft PR against `claude/holon-v2-bend2-c6z3cd`. Merge commits only, never force-push.

## Role

The sealer selects and seals. It never analyses a target and reads nothing of one beyond `git ls-remote`.

## The procedure

**(a) Prereg, before any draw.** One commit, pushed at least 20 minutes before T:
- `spec/M6/lib/I106_candidates.json`: the criteria (C1 well-known by a named list at a fixed snapshot, C2
  multi-component, C3 upgrade history, C4 public repo, C5 Solidity or Go) and at least 8 candidates by name and
  canonical URL, written without opening any repository. Excluded: Morph, Scroll, I48's corpus systems and their
  forks, across-protocol.
- `spec/M6/lib/I106_draw.py`: standard library only. The seed, the order (sha256(seed || id) ascending), the draw of
  the first 2 resolvable candidates, the pin rule (the greatest strict MAJOR.MINOR.PATCH release tag in the
  ls-remote listing, peeled; else the default branch's HEAD), `seal` and `verify`.
- `spec/M6/predictions/I106.json`: T, the beacon rule, sha256(salt) and both sidecars' sha256s in thresholds.seal.
- `tests_m6/test_i106_sealed.py`: D1, D2, C1 and K1 green at the prereg; S1 (the seal) and R1 (the reveal) red.
- `python -m holon audit prereg --milestone M6` prints PREREG OK.

The salt is 32 bytes from `secrets.token_hex(32)`, kept only in the sealer's session.

**(b) The draw, after T.** The first mainnet block with timestamp >= T, its number and hash, from a public source
(recorded). Seed = sha256(salt || blockhash). Run the committed script. Pin each drawn system by `git ls-remote`
only; record the listing's UTC time.

**(c) The seal.** target.json is built by `I106_draw.py seal` and kept uncommitted in the session.
Commit `spec/heldout2/commitment.json` (sha256 of target.json's exact bytes, sha256(salt), T, the block number, hash,
timestamp and source) and `spec/heldout2/README.md` (the sealed state, the sole-reader rule).

**(d) The reveal,** on "reveal" from the coordinator or the lead, after I107's prereg is committed: commit
`spec/heldout2/target.json` (the same bytes) and `spec/heldout2/salt.txt`; TestReveal turns green.

**(e) Reads.** Nothing of the targets beyond `git ls-remote`.

## The PR

First line `I106 sealed: commitment <sha256 of target.json, first 12 hex> at block <number>`; the names are not in
it until the reveal. Then Done, Surprises, Questions for the human, Not done. Never the salt or the plaintext before
the reveal, in a commit, PR, comment or message.
