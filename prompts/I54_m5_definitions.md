# I54: L6, L9 and L10 definitions, preregistered

Rendered from `docs/BUILD_PLAN.md` §4 I54 (milestone M5), with Q11 in `docs/HUMAN_ANSWERS.md` and the whitepaper's L6, L9 and L10 rows (§12, §12.4), §5.7 (DISCH), §5.9–§5.10 (intent contracts and the intent lane) and §13. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first.

**Q11's provenance.** `docs/HUMAN_ANSWERS.md` records Q11 among the answers that the human delegated to the lead on 2026-10-13 ("These answers are the lead's, made under that delegation, not the human's own"). This session's brief calls it the human's own answer. The definitions follow the recorded text either way; the discrepancy is a question for the human.

## Goal

Fix, before I55–I57 build anything that the metrics score, exactly how L6 (can versus will), L9 (environment) and L10 (consistently wrong code) are measured:
- the population of each metric;
- the records it reads;
- the validity rules a record must pass;
- each reported measure and its formula;
- the truth it is scored against, and when that truth is admissible;
- the thresholds and how they are judged.

The metrics are target-agnostic. They are measured against ground truth that HOLON does not produce, and never against HOLON's own outputs alone:
- constructed controls, with truth recomputed by an independent interpreter;
- the I48 corpus, through a frozen truth protocol;
- recorded history, through admissible observation sets.

The contract is the docstring of `tests_m5/test_m5_definitions.py`. The definitions are the `thresholds.definitions` of the key `I54` (`spec/M5/predictions/I54.json`). The prereg audit makes the key immutable, so the definitions cannot move after this commit. `spec/M5/preregistration.json` is rendered from the key in the build, so I55–I58 read one file.

## Fixed at this prereg (the instruments)

These are pinned by sha256 in the test module (`PINNED`):
- `tests_m5/_i54.py`. It writes the definitions out a second time, independently of `holon/`:
  - the control documents, and an explicit-state interpreter for the game controls' truth;
  - the census rule;
  - a reference computation of every measure;
  - the fixtures: honest, gaming and clean records.
- `tests_m5/_m5.py` (shared readers, a read-only git view) and `tests_m5/__init__.py` (empty).
- `spec/M5/lib/environment_classes.json`. This is L9's classification of every assumption id that the M2 and M3 records hold at the base. Environment means exactly L1 chain, DA and fetcher. Every other id is listed with its reason.
- `spec/M5/lib/inputs.schema.json`: the records that the metrics read.
- `spec/M5/lib/truth_protocol.json` and `truth_prompt.md`: the corpus truth procedure. It is defined here and run later, under its own key, before the first record that it scores.
- This prompt.

## Build (after the prereg is pushed)

- `holon/m5/`, with the CLI `python -m holon m5 <command>`. Every JSON file is written as `json.dumps(obj, indent=2, sort_keys=True) + "\n"`.
  - `prereg [--check]`. It writes `spec/M5/preregistration.json`, holding:
    - `{"key": "I54"}`;
    - `"definitions"`: the key's;
    - `"base"`: `{commit, l6_findings, l9_dependent}`, read from the base commit through git;
    - `"instruments"`: path to sha256.
  - `controls [--check]`. It writes `spec/M5/controls/games/<id>.json`, `spec/M5/controls/intent/<id>.json` and `<id>.sol`, exactly the instrument's documents. holon computes the truth with its own solver.
  - `census [--check]`. It writes `results/M5/l10_census_base.json`: the census of M3's scope at the base, read through git from the checkout that `config/holon.json` `extract.sources` names.
  - `metrics --inputs FILE [--out FILE]`. It computes `{"L6", "L9", "L10"}` from an inputs document (the fixtures' form).
  - `metrics --base [--check]`. It writes `results/M5/definitions_base.json`: L6 and L9 over the base's committed records, with no game, module or intent record (so L6's decided count is 0 of 49, and L9's coverage is 0 of 222), and L10's census size.
- `docs/iterations/I54.md`.

## Rules

- AGENTS.md's hard rules, all of them. Never weaken a claim. No file of M0–M4 (results, gen, laws, replay, spec, facts) changes. No module of a generator closure changes.
- The sealed held-out target is never read.
- No module of `holon/` other than `holon/m5/controls.py` holds a control's id or name token.
- A miss of P1–P3 is a Surprise. The key is never edited. A test that must be fixed gets a line in `spec/M5/amendments/I54.jsonl`.
