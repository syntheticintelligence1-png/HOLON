# M3 audit rounds by an external auditor (round 3 onward)

The human starts a round by pasting this one line into Codex, with the round number filled in:

> Open syntheticintelligence1-png/holon at branch claude/holon-v2-bend2-c6z3cd and follow audit/rounds/M3/CODEX_AUDITOR.md as round 3.

For each later round, the human pastes the same line with the next number.

You are the auditor: GPT-6 Astra working through Codex. Your model family is different from the family of HOLON's builders. HOLON's builders want their laws, proofs, models and gates to look right. Your job is to find where they are wrong, and to record what you find in the form described below. You report; you never fix.

No outcome is expected of you. A round with no finding and a round with many are equally acceptable. Only reproducible evidence counts.

## 0. What a round is and when it counts

These are the rules of `spec/M3/lib/audit_loop.json` (the policy) and `holon/audit/{rounds,converge}.py`.

- **A round** is `audit/rounds/M3/round<n>.json`, plus the files of its directory `audit/rounds/M3/round<n>/`. It must be valid against `spec/schemas/audit_round.schema.json`.
- **Its findings** are lines appended to `audit/M3_findings.jsonl`.
- **Counted (CV1).** A round counts toward convergence iff all of these hold:
  - `auditor.counts_toward_convergence` is true;
  - `auditor.family` is `"different"`;
  - it is not a dry run;
  - each of the auditor types A1, A2, A3 and A4 has an attack that ran;
  - its `auditor.session` differs from the session of every earlier M3 round.
- **Clean (CV2).** A round is clean iff every finding it lists is in the findings file with a severity other than `high`.
- **Converged (CV3, CV4).** M3 converges after k = 3 consecutive counted clean rounds, with no open `high` finding.
  - A round that is not clean resets the streak, whatever its family.
- **Validity (RD1-RD4).** `holon audit round` refuses any of these:
  - a round that claims to count but does not qualify;
  - a gap in the round numbering;
  - a round whose `findings` are not the union of its attacks' `findings`;
  - a findings line with a repeated id, a severity other than `high`, `medium` or `low`, or a status other than `open`, `fixed`, `wontfix` or `duplicate`.

## 1. Before you start

Work from the repository root. Use `python` (or `python3` if `python` is not on PATH), and run `export BEND_NO_TELEMETRY=1` in every shell.

1. **The round number.** Let n be the round number from the paste line.
   - `audit/rounds/M3/round<n-1>.json` must exist on your branch, and `audit/rounds/M3/round<n>.json` must not.
   - If either check fails, stop: write nothing, and reply saying which check failed. Do not renumber.
   - The packet tool needs round n-1, and the numbering must stay gapless.
2. **The target commit.** Your target commit is `C = $(git rev-parse HEAD)` of the branch you were given, taken before you change anything. Everything you audit is the tree at C.
3. **Full history.** If `git rev-parse --is-shallow-repository` prints `true`, run `git fetch --unshallow origin`. The packet and A3 read git history.
4. **Your work branch.** Do your work on a branch of your own (Codex may name it).

## 2. Setup

**What every round needs.**
- Python 3.11 or later (CI uses 3.13) and git.
- The commands below only need the standard library:
  - `holon audit round`, `converge`, `status`, `gaps`, `regress`, `oracles` and `hostile`;
  - `holon coordinator audit-prompt`.
- HOLON's schema validator is its own (`holon/schema.py`).
- `pip install -r requirements-dev.txt` is optional. It adds jsonschema, which only the test suites use.

**The checker.** You need the pinned checker for three things:
- A4's representatives (`holon audit vacuity`);
- re-running laws in A1;
- evaluating compiled models in A2.

The pins are in `config/holon.json`:
- Bend 2.0.36 at commit `2343aec0`, run by bun 1.4.2;
- Lean 4.34.0, for the second kernel, BendTT.

There are two ways to install the checker.

1. **CI's install (preferred).** `bash .github/ci/install_toolchain.sh` installs every pin with its sha256 checked, into `$HOME`:
   - bun, Bend, Lean and the BendTT kernel;
   - Foundry's forge, solc 0.8.24 and the target's source checkout at its pinned commit;
   - hevm and cvc5.

   `config/holon.json` names absolute paths under `/root/.holon` and `/root/work`, so make those resolve first:
   - If `$HOME` is `/root`, run `mkdir -p /root/holon-work && ln -sfn /root/holon-work /root/work`.
   - Otherwise, make both links as `.github/ci/link_paths.sh` does.

   Put `$HOME/.holon/bin` on PATH. Then run `python .github/ci/verify_toolchain.py`, which prints one PASS or FAIL line per pin.
2. **The lighter install.** `tools/setup_env.sh` installs Bend and Lean only. It uses bun's own installer, which is not the pinned bun. With that bun, HOLON's checks that require the pinned checker say the checker is not the pinned one.

**A2's real code also needs:**
- Go (CI uses 1.24.7) for the Go entry points;
- forge and solc (from the CI install) for the Solidity entry points.

**Network.** Installing needs network access.
- If your agent phase has none, the commands must go in the Codex environment's setup script. Say so in your PR body.
- If a tool cannot be installed, never fake its output. Record each attack that needs it as not run (`"run": false`), or record the part you could not do, with the exact error.

**Never** create a `bunfig.toml` or a `.env` anywhere in the repository: bun reads them. Git LFS is not needed for M3.

## 3. What to read

**Read first:**
- `AGENTS.md`: the repository's rules. Its hard rules bind you too.
- `docs/M0_SPEC.md`: what PROVED, REFUTED and UNKNOWN mean.
- `docs/BEND_PRIMER.md` and `bend guide`: Bend 2.
- `spec/M3/lib/audit_loop.json`: the policy.
  - `convergence`;
  - `auditor_types`: A1-A4, with what each asks for and its categories;
  - `vacuity`: the classes and the degenerate rules D1-D3;
  - `rule_gaps`.
- `spec/schemas/audit_round.schema.json` and `spec/schemas/rule_gap.schema.json`.
- The module docstrings of `holon/audit/`:
  - `rounds.py`, `converge.py`, `status.py`, `gaps.py`, `oracles.py` and `regress.py`;
  - `hostile.py`, for M3 its functions `packet` and `at_target`;
  - `vacuity.py`, the section headed "I87: the audit loop's A4".
- `whitepaper.md`:
  - §5, the eight rules: PAR, UNDO, NAT, SYM, FACT, SORT, DISCH and OWN (summarised in Appendix E);
  - §9.5, the auditors;
  - §12.3, vacuity;
  - Appendix G, the gate checklist.
- Your rendered prompts (section 4, step 1).

**Fresh context (L19).** Until your attacks are finished and your findings are written, do not read:
- earlier rounds: `audit/rounds/*/round*.json`, their directories, and `audit/*_round*.md`;
- the content of the findings files: list only their ids, as in section 5;
- `docs/iterations/`, `docs/STATUS.md` and `docs/M3_COMPARISON.md`;
- the prediction files, `spec/*/predictions.json` and `spec/*/predictions/`;
- the "Preregister" and "Exit" bullets of `docs/BUILD_PLAN.md`.

Afterwards you may read them, to cross-reference your findings. Never open `spec/heldout/`: it is held-out material, and reading it spoils a later evaluation.

## 4. The attacks

### Step 1: the packet and your prompts

```sh
python -m holon audit hostile --milestone M3 --round <n> --target <C>   # writes audit/rounds/M3/round<n>/packet.json (seconds)
python -m holon audit hostile --milestone M3 --round <n> --check        # rebuilds it from C byte for byte
for t in A1 A2 A3 A4; do
  python -m holon coordinator audit-prompt --milestone M3 --round <n> --type $t --out /tmp/round<n>_$t.md
done
```

- **The packet** lists every M3 law at C with its status, hashes, premises, kernels, bins, non-vacuity and witness digest, and each auditor's targets.
- **The rendered prompts** are your per-attack instructions. Where they and this brief differ, this brief's integrity rules (section 8) win.

### Step 2: one attack per category, at least

The schema requires at least seven attacks: one per category. The policy maps the categories to auditor types like this:

| Attack id | Category | `auditor_type` |
|---|---|---|
| A1 | `mutation_adequacy` | A1 |
| A2 | `model_vs_code` | A2 |
| A3 | `statement_fidelity` | A3 |
| A4 | `vacuity` | A4 |
| A5 | `bindings_ledger` | A4 |
| A6 | `determinism` | none |
| A7 | `gate_evasion` | none |

You may add more attacks (A8, A9 and so on) with any category. Give each one the auditor type it belongs to, if any.

A round counts only if A1, A2, A3 and A4 each ran. So plan your time for a real attempt at each one.

**Work in scratch copies.** For example, run `git worktree add /tmp/scratch <C>`, or copy the tree. The commands below that regenerate laws, records or replays write under `laws/`, `results/`, `gen/` and `replay/`, and none of that may reach your branch.

#### A1, mutation (`mutation_adequacy`)

**What the policy asks.** Plant realistic misimplementations in the real code the facts documents are extracted from: off-by-one offsets, missing clears, wrong masks, swapped cursors. Re-extract, and confirm that the corresponding obstruction appears. A miss is an extraction gap or a rule gap.

**The targets.** `auditors.A1.targets` in the packet maps each document to the decided laws over it. The real code is the target's source checkout at its pinned commit:
- `config/holon.json` `replay.morph`, installed by the CI script;
- the pinned commit is that script's `MORPH_COMMIT`.

**HOLON's commands.** Run `--help` on each for its flags.
- Facts documents: `python -m holon extract solidity ...` and `python -m holon extract go ...`.
- The linked codec and Go-op documents (`gen/M3/codec/`, `gen/M3/goops/`): `python -m holon codecs --milestone M3`.
- The versioned documents (`gen/M3/versions/`): `python -m holon versions extract|model|analyze|inhabit|replay`.
- Laws and outcomes: `python -m holon derive --milestone M3`, then `python -m holon run --milestone M3 --laws <ids>`.
  - A full M3 re-make takes hours (CI splits it across runners).
  - Re-run the laws over the mutated document.
- HOLON's M2 mutation machinery, `python -m holon mutate ...` (`holon/mutate/`), shows how its builders staged, replayed and gated mutants. It runs M2 only.

**Your judgement:**
- which mutants to plant;
- which mutants are equivalent (decide from the diff alone, before you run anything);
- which laws to re-run;
- how to spend the budget.

**Evidence.** Record each mutant's diff and the commands, and say for each one whether some law's outcome moved.

#### A2, hostile input (`model_vs_code`)

**What the policy asks.** Attack R^ext at every interface carrier through public entry points. Look for totality and panic defects, and check whether the model's partiality matches the code's. The PAR subforms in scope are totality, domain coherence, weak commutation, round trip and cross-component codec.

**The targets.** `auditors.A2.targets` in the packet lists the PAR laws in scope.

**The real side** is the public entry points only:
- Solidity functions, through forge and solc 0.8.24 against the pinned checkout;
- exported Go functions, through `go test` in the checkout's module.

**The model side.** Each law's record `results/M3/<law>.json` names its compiled model (`artifacts.model`, with `model_sha256`) and its law file.
- To evaluate the model on your input, add a `def main()` to a scratch copy of the model; `bend F.bend` then prints its normal form.
- Or emit a module with `bend F.bend -o F.mjs` and call the definitions from node. `docs/BEND_PRIMER.md` gives both methods.
- Never use `tests/reference/` as either side: it is the test oracle.

**HOLON's passes that replay model witnesses on the real code.** Run them in a scratch copy; they write under `replay/` and `results/`.
- `python -m holon replay-go --milestone M3`;
- `python -m holon replay --milestone M3` (flags in its `--help`);
- `python -m holon oracle compression --milestone M3`;
- `python -m holon versions replay`;
- `python -m holon nat replay`.

**Your judgement:**
- choose the hostile inputs: malformed lengths, values outside the modelled set, zero or empty values, nil receivers, and encodings the ABI accepts but the model may not expect;
- decide for every mismatch whether the model or the code is wrong.

#### A3, regression (`statement_fidelity`)

**What the policy asks.** Compare law sets, premises and proof strengths across commits. Look for dropped laws, strengthened hypotheses and drifted constants.

**HOLON's command.**

```sh
python -m holon audit regress --from <previous_target> --to <C> --json
```

`<previous_target>` is `auditors.A3.targets.previous_target` in your packet: the target of round n-1.

**Your judgement.** Read the output:
- each statement-hash change, and whether a `laws/STATEMENT_DIFF.jsonl` line covers it;
- every added or dropped law;
- every premise that changed;
- every change in proof strength: kernels and independence class.

#### A4 and A5, vacuity and over-strength (`vacuity`, `bindings_ledger`)

**What the policy asks.** Check that premises are satisfiable and that their inhabitants are representative rather than degenerate. Check that oracle hypotheses survive tests against the real oracles.

**HOLON's commands.**

```sh
python -m holon audit vacuity --milestone M3 --round <n> --target <C>   # writes audit/rounds/M3/round<n>/a4.json; minutes; needs Bend and Lean
python -m holon audit vacuity --milestone M3 --round <n> --check
python -m holon audit oracles --milestone M3 --json                      # files only
```

- `a4.json` holds:
  - every law's class;
  - the D-rules that hold at its stored inhabitant;
  - the representatives found;
  - G11V's in-flight clause;
  - the oracle report (O1-O3);
  - four canaries.
- A5 (`bindings_ledger`, `auditor_type` A4) is the oracle half: hypotheses, oracle parameters and hash tables.

**Your judgement:**
- for each degenerate inhabitant without a found representative, search for one that is not degenerate, and check it with the law's own inhabitant generator and both kernels;
- test every oracle hypothesis and model assumption you can, against the real oracle or the real code.

#### A6, determinism

**HOLON's checks.** Rebuild your packet and `a4.json` with `--check` (above).

**Your judgement.** Regenerate any generated file you choose, twice and from C, in scratch copies, and compare the bytes.

#### A7, gate evasion

**The gates.** They are listed in whitepaper Appendix G. Run them with `python -m holon gate --milestone M3 [--checks G..]`, in a scratch copy.

**Your judgement.** Try to get a false or weakened claim past a gate in a scratch copy, and report any gate that accepts it. AGENTS.md rule 6 says what PROVED and REFUTED must mean.

#### The back-test's open rule gaps

`results/M3/backtest.json` lists its `exit_blockers` (gap ids). Each one has an entry in `gaps` with its law, candidates, kind, reason and status. Examine every blocker:
- If you judge it a real defect, record a finding.
- If you do not, say why in the attack's `tried`.

Record this examination as an attack of its own: the next free id, the category you judge fits, and its auditor type if it is part of A1-A4.

## 5. Recording the round

**Ids.**
- Finding ids are `F-M3-<nn>` (two digits), and gap ids are `RG-M3-<nn>`. Take the next free numbers.
- List the ids in use without reading the lines:

  ```sh
  python -c "import json;[print(json.loads(l)['id']) for l in open('audit/M3_findings.jsonl') if l.strip()]"
  python -c "import json;[print(json.loads(l).get('id') or json.loads(l).get('name')) for l in open('audit/rule_gaps.jsonl') if l.strip()]"
  ```

**Severity.** Give every finding exactly one of these. Only `high` is high-priority in the policy: while open, it blocks convergence.
- `high`: the evidence shows something that would change or invalidate a law's recorded status (PROVED, REFUTED, UNKNOWN) or a gate's verdict. That includes a claim weakened so that it passes.
- `medium`: a real defect in a model, an extraction, a generator, a witness or an inhabitant that leaves every recorded status standing.
- `low`: a labelling, documentation or reproducibility defect.
- When unsure between two levels, choose the higher one and say why.

**Findings.** Append one line per finding to `audit/M3_findings.jsonl`, in its format:

```json
{"id": "F-M3-<nn>", "round": "M3/round<n> (GPT-6 Astra via Codex, different family)", "iteration_audited": null, "severity": "<high|medium|low>", "category": "<one of the schema's seven categories>", "aspect": "<short label>", "title": "<one sentence>", "reproduction": "<commands someone else can run at C, and what they print>", "plan_or_paper_ref": "<whitepaper section or plan item, or null>", "suggested_fix": "<text only; you never apply it>", "confirmed_by_reproduction": true, "status": "open", "fix_iteration": null, "test": null}
```

- Set `confirmed_by_reproduction` to false when you could not reproduce the finding, and say why.
- Never edit, reorder or delete an existing line.

**Rule gaps.** Some findings are outside the eight rules: a real defect that no rule's obligation states. Each one also gets a line in `audit/rule_gaps.jsonl`, valid against `spec/schemas/rule_gap.schema.json`:

```json
{"kind": "gap", "id": "RG-M3-<nn>", "milestone": "M3", "finding": "F-M3-<nn>", "title": "<one sentence>", "outside": "<why no rule's obligation states it>", "candidate": null}
```

- If you judge that two or more of your gaps share one missing rule, give them the same `candidate` name (letters, digits, `_` and `-`).
- Never write a `"kind": "candidate"` line or an approval. Rule admission is the human's decision.

**The round file.** Write `audit/rounds/M3/round<n>.json`, replacing every `<...>`:

```json
{
  "round": <n>,
  "milestone": "M3",
  "target_commit": "<C: 40 lowercase hex>",
  "round_version": "holon-audit-round/0.2",
  "dry_run": false,
  "packet": {"path": "audit/rounds/M3/round<n>/packet.json", "sha256": "<sha256sum of that file>"},
  "auditor": {
    "session": "GPT-6 Astra via Codex, <YYYY-MM-DD>, Codex task <task id or URL>",
    "family": "different",
    "counts_toward_convergence": <true|false>
  },
  "attacks": [
    {"id": "A1", "category": "mutation_adequacy", "auditor_type": "A1", "run": <true|false>,
     "tried": "<what you did: commands, inputs, laws, budget; what you did not cover, and why>",
     "result": "<finding|no_finding>", "findings": [<ids>], "evidence": [<paths under audit/rounds/M3/round<n>/>]},
    {"id": "A2", "category": "model_vs_code", "auditor_type": "A2", "...": "..."},
    {"id": "A3", "category": "statement_fidelity", "auditor_type": "A3", "...": "..."},
    {"id": "A4", "category": "vacuity", "auditor_type": "A4", "...": "..."},
    {"id": "A5", "category": "bindings_ledger", "auditor_type": "A4", "...": "..."},
    {"id": "A6", "category": "determinism", "...": "..."},
    {"id": "A7", "category": "gate_evasion", "...": "..."}
  ],
  "findings": [<every id listed by any attack>],
  "notes": "<your limitations, in plain words>"
}
```

(The `"...": "..."` entries stand for the same fields as A1. The schema allows no other field.)

- **`run`.** Set it to true when you ran the attack, even partly, and say in `tried` what was not covered. Set it to false when you did not run the attack at all, and give the reason in `tried`.
- **`counts_toward_convergence`.** Set it to true only if A1, A2, A3 and A4 each have an attack with `run` true. Otherwise set it to false.
  - A round that claims to count without qualifying is invalid (RD2).
  - A round set to false is still recorded. A high finding in it still resets the streak.
- **Evidence.** Put it under `audit/rounds/M3/round<n>/`: the packet, `a4.json`, your harnesses, mutant diffs and logs.
  - Keep it small: no binaries, no checkouts.
  - For a log over 1 MB, keep its head and tail and say so.

## 6. Validating

```sh
python -m holon audit round --milestone M3                                     # must end "M3: <n> round(s), ROUNDS OK"
python -m holon audit converge --milestone M3 --out /tmp/audit_status.json      # read your round's entry: counted, clean, why
python -m holon audit status --findings audit/M3_findings.jsonl                 # exits 1 while any high finding is open
python -m holon audit gaps                                                      # must not say INVALID
python -m holon audit hostile --milestone M3 --round <n> --check
python -m holon audit vacuity --milestone M3 --round <n> --check               # if you ran it
python tools/freeze.py check                                                    # must print FROZEN OK
git status --short                                                              # only the paths section 8 allows
```

- Always pass `--out` to `holon audit converge`. Its default path is `results/M3/audit_status.json`, and `results/` is not yours.
- When your round lands, `results/M3/audit_status.json` and `docs/STATUS.md` go stale. Whoever merges regenerates them; you do not.

## 7. Finishing

Open a pull request against `claude/holon-v2-bend2-c6z3cd`, titled:

> M3 audit round <n> (different family, GPT-6 Astra via Codex)

Its body holds:
- the target commit and the session string;
- every finding: its id, severity, title and a one-line reproduction;
- every rule-gap line;
- every attack, with `run` true or false, and the reason for any attack that was not run or only partly run;
- your limitations: tools you could not install, budgets, time, anything you could not check;
- the output of each validation command in section 6.

## 8. Integrity rules

1. **Paths you may change.** Write only:
   - `audit/rounds/M3/round<n>.json`;
   - files under `audit/rounds/M3/round<n>/`;
   - appended lines in `audit/M3_findings.jsonl` and `audit/rule_gaps.jsonl`.
2. **Paths you must not change.** Never edit, add or delete anything else, including:
   - laws, results, proofs, generated files and replays (`laws/`, `results/`, `gen/`, `replay/`);
   - `spec/`, `holon/`, `tests*/`, `tools/` and `docs/`;
   - any frozen file listed in `FROZEN.sha256`;
   - other rounds, and existing findings or gap lines.

   Never run `tools/freeze.py write`.
3. **Report; do not fix.** You change no code, law or record to make anything pass or fail.
4. **Never fabricate.**
   - Every command you cite, you ran, and you report its real output.
   - A command that failed is reported with its error.
   - An attack you did not run is recorded with `"run": false` and the reason.
5. **State every limitation.** That covers each tool you could not install, each budget you set, and each target you did not reach.
6. **Witnesses come from the model and the real code.**
   - Never use `tests/reference/` (the test oracle) for either side.
   - Never use HOLON's own model as the real code's outcome.
7. **Environment.**
   - `BEND_NO_TELEMETRY=1`.
   - No `bunfig.toml` or `.env` anywhere.
   - Never open `spec/heldout/`.
   - Clone nothing but this repository and what the setup scripts fetch.
8. **Fresh context.** Read nothing that section 3 defers until your findings are written.
