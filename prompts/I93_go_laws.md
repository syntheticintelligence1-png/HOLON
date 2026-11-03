# I93 (= I38d): O5, O6 and D3 as laws over a Go part of rule PAR, with the frontend 0.3 config

Read first: `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`, the I93 row of `docs/BUILD_PLAN.md`, the contract
(the docstring of `tests_m3/test_go_laws.py`, rules G1-G12), the key `iterations.I93` of `spec/M3/predictions.json`,
and `docs/iterations/I91.md` (HypZ, HypZ_len, the K bound, the expansion at the limit, the Questions).

## What to build

1. **Frontend 0.3** (`holon/frontends/go/`, G1). Gate every addition on `config_version == "holon-go-frontend/0.3"`;
   a 0.1 or 0.2 config must extract byte for byte what it extracts today (P1 re-extracts both milestones' configs).
   - compare: where paths.py and flow.py write `("unknown", "compare")`, write the comparison term.
   - carried: in `run_loop`, the header phis other than the induction variable are carried; record their entry value,
     the back-edge value per continue path (`updates`), and read `["carried", name]` for the phi.
   - varargs: a call's variadic slice built at the call site (an allocation of n elements filled by n stores) is
     `["varargs", [terms]]`.
   - fill_bytes: a primitive kind with a site of kind `fill_bytes`, status `unknown`.
   Then `holon extract go --milestone M3 --config spec/M3/lib/go_frontend_03.json` (G2).
2. **The Go part of rule PAR** (`holon/rules/gox.py`, `holon/gox/`, G3-G7), on the next catalog version. Mirror I92's
   SYMB part (`holon/rules/symb.py`, `holon/symb/`): the producers, `gox_ok[ID]` in holon.ir, the closure in
   holon.gen.refs, the `t_gox` term in both law_ir_0_3 schemas, holon.bindings, holon.land's group, holon.gate's
   G11V routing, `holon run` routing. The part writes `gen/M3/gox/basis.json`.
3. **Models, decider, replays** (G8-G11): `gen/M3/gox/<law>.bend`, `holon/gox/lawrun.py` (prove or refute, records),
   `holon/gox/replay.py` (Go internal tests in the target's package; a forge harness inheriting the pinned contract
   for the Solidity side, offline, through `holon.replay_fragments`). Records with the pinned checker only on CI
   (`holon land plan`); never commit a record made with the local checker.
4. **Report** `docs/iterations/I93.md` with Done, Surprises, Questions for the human and Not done, then land with
   `holon land`.

## Rules that bite here

- Witnesses come from the model. The go_branch witness is the smallest blob count with |X| at the bound; the replay
  only chooses X's bytes (the compression sidecar's stream kind) and must confirm the violation on the real code.
- Never weaken a law to make it pass: if a prediction misses, report it. HypZ is not a premise of go_branch (the
  estimators never decode); say so under Surprises if you find a reason it should be.
- No target names in holon/ (G12): every function, package, field and constant comes from the sidecars and documents.
- Keep Bend literals small (BendTT rejects large terms): byte cells as variables, lengths as Nat.
