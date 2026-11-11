# I56: bounded games (M5, L6)

Rendered from `docs/BUILD_PLAN.md` §4 I56 (milestone M5; depends on I32, I37 and I54), with the whitepaper's §12 row L6, §12.4, §11.4 N3 (O25), §11.3 O35 and §5.7 (DISCH). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first.

**Base.** The head of I54's branch `claude/i54-m5-definitions` (PR #134, not landed), `95a2288c`. The PR is opened against `claude/holon-v2-bend2-c6z3cd`, stacked on #134, and waits: the lead lands M4 and M5 code only after M3's exit. No M0-M3 result, law, record or generated file changes.

**The measure is I54's.** L6 is computed by I54's definition (key I54, `spec/M5/preregistration.json`), unchanged. I56 adds only what the lead's review of I54 (PR #134, comment 6800406794) requires of the next key that measures L6, before any record it scores:
- **V9 (condition 1).** The value-flow document covers every value-moving action and its coverage is reported; a target record that fails V9 is UNKNOWN; until V9 holds, L6's decided fraction is `not_judged`.
- **Corpus truth (condition 5).** No corpus item is scored until a separate corpus-truth key exists. Everything up to it is built; the scoring is listed as pending.
- Q11 is the lead's delegated answer (`docs/HUMAN_ANSWERS.md`): the stricter option applies.

## Goal (BUILD_PLAN I56)

- **Payoff facts.** `gen/M5/games/value_flows.json`, generated from the deployment's extracted documents only (VM1-VM4 of the key), with V9's coverage.
- **Strategies as checked programs.** One Bend module per game: the class verdicts computed inside Bend (for a control, a fuelled depth-first search over every schedule of distinct actions, so the universal claim is complete), and each rational class's strategy returned by an `exs` proof.
- **DISCH-econ laws.** O25/N3 read economically over I26's attribution witness (a rational recommitter refuses), and O35 read economically over I84's self-controlled law (the backlog that disables `challengeState` is payoff-free under P-gas).
- **Exit.** L6 is computed by I54's definition, over F(M3) and the 14 game controls.
- **Risk.** Rationality assumptions (P-gas, P-bond) are premises in the frozen statements, never facts.

## Fixed at this prereg (the instruments)

Pinned by sha256 in `tests_m5/test_m5_games.py` (`PINNED`):
- `tests_m5/_i56.py`: the key's definitions written out a second time, independently of `holon/games` (classes, claim ledgers, value-moving actions, the witness-form table, the flows on the model's run, the payoff classification, the witness game, the controls' truth by I54's enumeration, L6 with V9, the N3 and O35 readings).
- `spec/M5/lib/games_M3.json`: the deployment's documents (sha256), the run member and its initial state (sha256), the member-caller groups, every class with its trusted flag and reason, and the N3 and O35 anchors.
- This prompt.

The key `I56` (`spec/M5/predictions/I56.json`) holds the definitions (`thresholds.definitions`), the pins of I54's 14 game controls (truth pinning) and of the sidecar, and the gaps.

## Build (after the prereg is pushed)

- `holon/games/`, with the CLI `python -m holon games <command>`; every JSON file is `json.dumps(obj, indent=2, sort_keys=True) + "\n"`:
  - `flows [--check]`: `gen/M5/games/value_flows.json` and `results/M5/games/v9.json`;
  - `run [--check]`: the game documents, the Bend modules (checked), the law IR (`laws/M5/games/`), the game and econ records, `attempts.json`, `l6.json` and `summary.json`.
- The flows pin, `spec/M5/lib/games_M3_flows.json`, in its own commit before any game record (V8).
- `docs/iterations/I56.md`.

## Rules

- AGENTS.md's hard rules, all of them. Never weaken a claim. No file of M0-M4 (results, gen, laws, replay, spec, facts) changes, and no module of a generator closure.
- Generators are target-agnostic: no target name in `holon/games`; the target's facts come from the documents and the sidecar.
- No module of `holon/` other than `holon/m5/controls.py` holds a control's id or name token (I54's K4).
- The sealed held-out target is never read.
- A missed prediction is a Surprise. The key is never edited; a test that must be fixed gets a line in `spec/M5/amendments/I56.jsonl`.
