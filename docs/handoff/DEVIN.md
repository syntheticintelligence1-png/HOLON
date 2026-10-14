# Handoff: working on HOLON from a second agent platform (Devin)

The human runs two agent platforms on this repository:
- Claude Code (the lead) drives M3 on branch `claude/holon-v2-bend2-c6z3cd`.
- Devin starts on M5.

Devin never pushes to the lead's branch or to `main`. It opens pull requests into `claude/holon-v2-bend2-c6z3cd`, and the lead validates and merges them. The protocol below is what makes that safe.

## 1. Read first, in this order

1. `AGENTS.md`. Its hard rules bind every agent, whatever the platform: frozen files, never weakening a claim, generate rather than hand-write, the checker's word is final, and determinism.
2. `docs/M0_SPEC.md`, then `docs/BEND_PRIMER.md` (Bend 2 is newer than any model's training data).
3. `docs/BUILD_PLAN.md`:
   - §0, the preregistration and session protocol;
   - §3, the iteration map;
   - §4 "M5: intent lane, games, environment".
4. `docs/HUMAN_ANSWERS.md`. It holds the human's answers, plus the lead's delegated answers Q4–Q30. **Q11 defines L6 and L9.** I54 makes Q11 concrete, and I54 may not contradict it.
5. `whitepaper.md`, the sections the M5 plan entries cite.

## 2. Scope

| Work | Can start now? | Why |
|---|---|---|
| **I54**: L6/L9/L10 definitions, preregistered (BUILD_PLAN §4 I54) | **Yes** | It depends on nothing unbuilt. Q11 is answered. |
| I55: intent lane | No | Waits on M3's I33 (intent contracts) and the SYM rule. |
| I56: bounded games | No | Waits on M3's I32, I37 and I26. |
| I57: environment modules | No | Waits on M3's I26 and I27 (FACT and UNDO laws, made time-indexed). |
| I58: M5 report | No | Waits on everything above. |

Start with I54 only. The lead says in the PR thread when an M5 dependency lands.

## 3. How an iteration is done (the preregistration protocol)

Use **one pull request per iteration**, with the commits in this order:

1. **The prereg commit.** It holds only prereg paths:
   - the iteration's key in `spec/M5/predictions.json` (create the file in the format of `spec/M3/predictions.json`);
   - `prompts/I54_*.md`;
   - the tests in `tests_m5/`, with their contract docstrings;
   - any helpers, fixtures and frozen sidecars under `spec/M5/lib/`.

   The tests must be red for the right reason. Outcome paths must be narrow, complete, literal, key-specific prefixes, never a shared file.
2. **Adversarial review of the prereg, before any build commit.** Say so in the PR. The lead (or an independent reviewer) reviews it. Any amendment to the prereg is folded into that prereg commit before any build commit lands.
3. **The build commits.** They hold the code and outcomes. A prediction that does not come out is a **MISS** with evidence. Never tune toward a prediction, and never weaken a test. A change the contract genuinely forces is one append-only line in `spec/M5/amendments.jsonl`: `{"iteration","kind","test","why"}`.
4. **The report, `docs/iterations/I54.md`.** Include a prediction table (PASS or MISS for each id, with evidence), then Done, Surprises, Questions for the human, and Not done.

`python -m holon audit prereg --milestone M5` must print `PREREG OK` at every commit of the PR.

## 4. Never

- Push to `claude/holon-v2-bend2-c6z3cd` or to `main`. (`origin/main` is another agent's line: do not touch it, merge it or base on it.)
- Edit a frozen file, or add files under a frozen directory (`FROZEN.sha256`). Run `tools/freeze.py write`.
- Commit secrets. Commit `bunfig.toml` or `.env` anywhere. Commit caches. Keep tool installs in `~/.holon` or `/tmp`.
- Import or call `tests/reference/` from `holon/`.
- Rewrite history on the PR branch after the lead has reviewed it (no force-push). A merge commit keeps the review valid.
- Name a target (Morph, Rollup, contract or field names) in generic code under `holon/`. `tests_m2/test_target_agnostic_exhaustive.py` enforces this.

## 5. Pinned toolchain

The gates compare the environment against these pins (GENV), so a different version fails the gate.

| Tool | Pin |
|---|---|
| Bend 2 | 2.0.36, checkout commit `2343aec043b7967f2a6f653e7f2e3bcbe55c8c9a`, installed by `tools/install_bend.sh` into `~/.holon` |
| bun | 1.4.2. The checker fingerprint in `config/holon.json` hashes bun's version and bytes. |
| BendTT (second kernel) | Built by bend2 from the pinned `bendtt.lean`. Its sha256 is `bend.pinned_kernel_sha256` in `config/holon.json`. |
| Lean | leanprover/lean4:v4.34.0, through elan |
| Python | the repository's `requirements-dev.txt` |

If the fingerprint cannot match on your platform, say so in the PR. Never edit the pins to make a gate pass.

## 6. What the lead runs before merging

1. `python -m holon audit prereg --milestone M5`, and also `--milestone M2` and `--milestone M3`, to confirm nothing earlier broke.
2. `python tools/freeze.py check`.
3. The PR's own test modules.
4. The frozen suite: `python -m unittest discover -s tests -t . -v`.
5. `python -m holon gate --milestone M0`, `M1` and `M2`.
6. A review of the diff against AGENTS.md: generic code, no special-casing of law ids or targets, determinism, and no weakened claims.

The lead merges **with a merge commit**, never a squash or a rebase. Squashing would put the outcomes into the prereg commit, and the prereg audit would fail.

## 7. PR description

End it as AGENTS.md requires: **Done** (with the frozen suite's summary line), **Surprises**, **Questions for the human**, **Not done**.
