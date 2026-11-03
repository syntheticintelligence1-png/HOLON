# I94 (= I36d, "I70b"): O13 and O20's economic half decided by the checker; model3 clears deleted bytes members

You are the one builder in the holon-05 lane. **Cost discipline is a hard requirement:**
- spawn NO subagents;
- keep outputs short;
- never poll;
- batch pushes.

**Time box: about 6 hours of build after the prereg.** If the linked layer does not converge inside the box, stop. Record the laws UNKNOWN with the debt named construct by construct, which is honest, and report.

## Context
You built I70 (landed via #92, lead c3eda197). Its two laws are UNKNOWN as model debt:
- `L_nat_slash_Rollup_V10_V11_proveState` (O13);
- `L_sort_slash_Rollup_V10_V11_proveState` (O20's economic half).

F10 is observed on real code (results/M3/cutover/steps.json). Your I70 report's "Not done" is this key's scope:
- the Bend linked layer: the type conversions for the registry modules;
- a VReach witness through V3..V10 whose registry address and staker match the registry s0;
- the claims module, the .mjs search, the counter-law and the RP1 replay;
- `register` model debt;
- the model3 defect M2 found: a deleted struct's dynamic `bytes` member is not cleared (claimWithdrawal), affecting only L1Staking's `stakers`.

**I70-Q1 (how to reach V10): take option (a).** Go through the deployed path V3..V10 as I83's inhabitants do, with the registry's initial state taken from the harness after the stakers registered. This keeps the laws' quantification domain, so no amendment to their statements.

## Setup
- **Key:** I94 (= I36d), milestone M3. I92 and I93 are the lead's planned keys.
- **Branch:** `claude/brave-wright-2c5d0o-i94` from the lead `origin/claude/holon-v2-bend2-c6z3cd` (9df9ddec or later). Your I70 worktree `/home/user/HOLON-i70` may be reused if clean; otherwise make `/home/user/HOLON-i94`.
- **Pipeline v2:** per-key sources, `holon aggregate`, scheme 2. The lead lands with `holon land`. Your report goes on your own branch.

## Process
1. **Prereg (C_K) first, pushed before any build.** The BUILD_PLAN row I94 is its own commit, then the key; PREREG OK required.
   - Predict each law's verdict: REFUTED if the witness is found on the compiled model and replays on real code; otherwise UNKNOWN with the named debt.
   - Name the witness shape you expect from F10's steps (T1 at V10, T2 at V11), without running any of the new code before C_K.
   - Disclose what you read: I70's records and steps.json.
2. **Build:**
   - The model3 fix: a deleted struct clears its dynamic members' length slot and data slots. Keep it generic.
     - model3.py is a closure file, so the landing needs a re-stamp.
     - Prove every earlier model3 output byte-identical, except the L1Staking model, whose disagreement must disappear.
     - Re-run I70's M2 refinement and report it.
   - The linked layer, claims, search, counter-law, Bend + BendTT (`--verdict`) and the RP1 replay on real code. Decide both laws.
   - REFUTED needs a counter-law Bend accepts, at a witness found on the compiled model, replayed on real code.
3. **Re-make plan.** Give me the recipe for the lead: which laws, which jobs, and the re-stamp.
4. **Report:** docs/iterations/I94.md on your branch, with the four sections. Then FROZEN, PREREG, AGGREGATES, target-agnostic and your test module.
5. **Push.** Send me `ready <PR> <sha>` plus at most 6 lines. Send me the draft PR number right after the prereg push.

## Identity
- Commit as Claude <noreply@anthropic.com>, ending every commit message with:
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01RRZzUYr9B7nYqGJvuGoLkE
- PR bodies end with:
  🤖 Generated with [Claude Code](https://claude.com/claude-code)

  https://claude.ai/code/session_01RRZzUYr9B7nYqGJvuGoLkE
- Set BEND_NO_TELEMETRY=1. Never touch scroll-tech/* or spec/heldout/. Never edit frozen files.
