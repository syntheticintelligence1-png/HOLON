# spec/heldout3: I113's fresh sealed targets (sealed)

HUMAN_ANSWERS Q54, Q55, Q56, Q71, Q72 and Q86 (the lead's ruling for this key, relayed in the I113 brief), and
docs/BUILD_PLAN.md §3 row I113 and §4 "M6: generality".

## State: SEALED

| Item | Value |
|---|---|
| Prereg | `b302002a` (key `spec/M6/predictions/I113.json`, candidates `spec/M6/lib/I113_candidates.json`, draw script `spec/M6/lib/I113_draw.py`), pushed 2026-11-12T18:58:54Z |
| T | 1794512700 (2026-11-12T19:45:00Z), 46 minutes after the prereg push |
| Beacon | Ethereum mainnet block 26401039, `0xe9d679ec321dfecd76598b593f71edbd1cb27df0e70208f90c04a76098678521`, timestamp 1794512711; its parent 26401038 has timestamp 1794512699 < T; finalized before use |
| sha256(salt) | `4028e6d29269f58efb6942389bf6391db989e7d42f2b01bbe30b128587e8408d` (the prereg key's) |
| sha256(target.json) | `1f3a5a78182def11ab880bbaf5fe673287f64bef7af739afca62de2d102c0f04` |

`commitment.json` holds these values. The salt and `target.json` (2 targets drawn from the 9 candidates, each pinned
by `git ls-remote` to a release tag or a default branch, with its commit and its listing's UTC time) exist only in the
sealer's session until the reveal.

## The sole-reader rule

- **From the candidate list's push until the reveal, only the sealer may read** any candidate's repository, docs or
  audits, `target.json` or the salt (Q86 (3)). No builder, not the coordinator and not the lead. The sealer read
  nothing of the candidates beyond `git ls-remote` (and what Q55 (1)'s membership check needs). The plaintext is in no
  commit, PR, comment or message.
- **No subagent reads a drawn target** (Q71). This README allows no preregistered channel's subagents: any later key
  that reads these targets runs without subagents while its sole-reader rule applies.
- **The reveal** comes only after I114's prereg (its predictions and thresholds) is committed and pushed, on "reveal"
  from the coordinator or the lead (Q54 (d)). The sealer then commits `target.json` (the same bytes) and `salt.txt`
  (64 hex characters and one newline) here.
- **After the reveal,** who reads the targets is the lead's ruling for I114, the measuring key (as for I107 under
  docs/iterations/I49.md's sole-reader rule). Findings on them follow Q56 (embargo) and Q72.
- Reads are checked from the transcripts, as in I49/I50's protocol.

## Checking the reveal

```
python3 spec/M6/lib/I113_draw.py verify --target spec/heldout3/target.json --salt spec/heldout3/salt.txt \
    --commitment spec/heldout3/commitment.json
python -m unittest tests_m6.test_i113_sealed -v
```

`verify` recomputes sha256(salt), the seed sha256(salt ‖ blockhash), the order, the draw of 2 and sha256(target.json),
and prints VERIFY OK. Anyone can recheck the beacon block on any explorer, and each pin by `git ls-remote`. A release
tag pushed after T is a residual risk: each target records its listing's UTC time.
