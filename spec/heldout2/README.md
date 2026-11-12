# spec/heldout2: I106's fresh sealed targets (sealed, not revealed)

HUMAN_ANSWERS Q54 (the lead's delegated ruling, 2026-11-12), docs/BUILD_PLAN.md §4 I106 and "M6: generality".

## State: SEALED

| Item | Value |
|---|---|
| Prereg | `7f0662ee` (key `spec/M6/predictions/I106.json`, candidates `spec/M6/lib/I106_candidates.json`, draw script `spec/M6/lib/I106_draw.py`), pushed 2026-11-12T04:02:29Z |
| T | 1794459600 (2026-11-12T05:00:00Z), 57 minutes after the prereg push |
| Beacon | Ethereum mainnet block 26396629, `0x55f21e8e8c5229de6211594bb794550a0539b9250c2ead9e9c67fe1136ec82dc`, timestamp 1794459611; its parent 26396628 has timestamp 1794459599 < T |
| sha256(salt) | `8c0a8625bf8f60785a0dfdcdeff8f7c116d0a6afbdfc79021fb65ccaf50d3e3c` (the prereg key's) |
| sha256(target.json) | `f74d45b02f0613f3a701beb24294df6fa53231bbd75ffb021ed5868696a78273` |

`commitment.json` holds these values. The salt and `target.json` (2 targets drawn from the 9 candidates, each pinned by
`git ls-remote` to a release tag or a default branch, with its commit) exist only in the sealer's session.

## The sole-reader rule

- **Before the reveal, nobody reads the plaintext:** not the lead, not a builder, not the coordinator. The plaintext is
  in no commit, PR, comment or message. The sealer read nothing of the targets beyond `git ls-remote`.
- **The reveal** comes only after I107's prereg (its predictions and thresholds) is committed and pushed, on "reveal"
  from the coordinator or the lead. The sealer then commits `target.json` (the same bytes) and `salt.txt` (64 hex
  characters and one newline) here.
- **After the reveal, only I107 reads the targets** (docs/iterations/I49.md's sole-reader rule): its session is their
  only reader until its results are recorded, with no subagents.
- Reads are checked from the transcripts, as in I49/I50's protocol.

## Checking the reveal

```
python3 spec/M6/lib/I106_draw.py verify --target spec/heldout2/target.json --salt spec/heldout2/salt.txt \
    --commitment spec/heldout2/commitment.json
python -m unittest tests_m6.test_i106_sealed -v
```

`verify` recomputes sha256(salt), the seed sha256(salt ‖ blockhash), the order, the draw of 2 and sha256(target.json),
and prints VERIFY OK. Anyone can recheck the beacon block on any explorer, and each pin by `git ls-remote`. A release
tag pushed after T is a residual risk: each target records its listing's UTC time.
