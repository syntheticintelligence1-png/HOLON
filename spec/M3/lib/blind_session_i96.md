# Blind rerun: the session brief (I96)

You run HOLON's pipeline from code, on a sealed bundle, with no other source of knowledge. The coordinator gives you
three absolute paths:
- `PACK`: a tar file, `bundle.tar`. It holds `target/` (the target's code at one pinned commit), `tooling/` (HOLON's
  code: `holon/`, `tools/`, `config/`, `schemas/`, `.github/ci/`) and `tooling/whitepaper.md`;
- `SCOPE`: a directory holding `files/<path>` (the extraction-scope sidecars and the given inputs below) and
  `stripped.json` (the keys removed or blanked in them);
- `W`: your work directory.

The target is the repository `morph-l2/morph` at commit `3e44e795586af3e11285b603ab642c67823add51`.

**Given inputs.** Beside the extraction-scope sidecars, SCOPE gives:
- `spec/ledger/assumptions.json`: the assumption ledger that `holon run`'s records read, with its free text blanked;
- `spec/M3/lib/term_size.json`: FACT's term-size budget;
- `spec/M3/lib/binding.json`: the configuration of the deployment that `holon binding` re-runs (its harness, project,
  target and parameters);
- `spec/M3/lib/binding_facts.json`: a copy of the M1 facts' initial members that the binding's parameters read (facts);
- the three harness sources that `spec/M3/lib/binding.json` names, under `replay/M1/solidity/` and `replay/M2/solidity/`.
- `spec/M3/lib/fragments.json`: the fragments binding's declarations (its abstract facts, its window encodings and its
  document), from which `holon binding --fragments-out` derives the fragments binding;
- `spec/M1/facts/morph_rollup.json`, `spec/M1/lib/morph_rollup.lib.json` and `spec/M1/lib/morph_rollup.lean.json`: the
  M1 facts and the M1 model's definitions, which the step refinement's abstract rows and corpus read (facts and model
  definitions);
- `spec/M1/policy_hints.mjs`: the M1 corpus's search configuration (candidate actions from a decoded state).

They are given, not authored: never edit them, and log no `authored` line for them. Step 0 places them.

## Rules

1. **Read and write only inside `W`**, and read `PACK` and `SCOPE` once each, in step 0.
   - You may run the toolchain (`python3`, `bend`, `bun`, `node`, `go`, `git`, `tar`, `sha256sum`, `forge`, `solc`,
     `lean`, `lake` and the binaries `W/config/holon.json` names), but never browse its directories.
   - The one exception is step 3.6: you may read the Go toolchain's runtime sources under `go env GOROOT`.
   - Never open, list, search or run anything anywhere else. This includes every other checkout of HOLON or of the
     target, every `results/`, `laws/`, `spec/`, `docs/`, `audit/`, `facts/`, `gen/`, `replay/` or `prompts/`
     directory outside `W`, home-directory caches, and every git history other than the one commit you fetch.
2. **Network.** You may only:
   - `git fetch` the target at the pinned commit, with depth 1, and a gitlink its tree names, at the commit the tree
     names, when a step needs it;
   - let `go` download the modules of the target's own `go.mod` files.

   Use no web search and no web fetch.
3. **Paths.** `W`, `PACK` and `SCOPE` below stand for the absolute paths you were given; write them out.
   - Begin every shell command with `cd W && `. The first command of step 0 begins `mkdir -p W && cd W && `.
   - Give every file tool an absolute path under `W`.
   - Write no `..` path segment anywhere.
4. **Environment.** In every shell command that runs `holon`, set `BEND_NO_TELEMETRY=1 HOLON_BUILD_DIR=W/build
   HOLON_CACHE=W/cache`.
5. **Do not edit the tooling.**
   - Leave `W/holon`, `W/tools`, `W/schemas` and `W/.github` unchanged.
   - In `W/config/holon.json`, change paths only.
6. **Write no law, fact, proof, model or record by hand.** Everything under `W/laws`, `W/gen`, `W/results`,
   `W/replay` and every `*.extracted.json` is written by the commands below. The harness sources that SCOPE gives
   under `replay/` are placed by step 0.
7. **Authored inputs.** When a command needs an input that `W` does not hold, write it yourself and log it as
   authored, if the target code fixes its content. Such an input is:
   - a sidecar under `spec/<M>/lib/`, including the rule sidecars of steps 3.1 to 3.6, which `holon derive` reads;
   - a key that `stripped.json` lists;
   - a path in `config/holon.json`.

   Write it only from the target code under `W/target` and from the tooling's own code and docstrings under `W`. Each
   sidecar's loader in `W/holon` names the fields it reads. Never copy it from anywhere else.
8. **Inputs that are records, not code.** Never author:
   - a deployment's history or on-chain state;
   - a forge deployment record;
   - a corpus or binding of another milestone;
   - a hand-written fact document.

   When a step needs one, log it as `not_reproducible` and go on. The deployment record is never authored either:
   `holon binding` derives it (step 3.1).
9. **Keep the log `W/blind/log.jsonl`**: one JSON object per line, appended as you go.
   - `{"kind": "command", "cmd": "<the command>", "exit": <code>, "seconds": <s>}` for every command of the steps.
   - `{"kind": "authored", "path": "<path under W>", "sha256": "<hex>", "for": "<the command that needed it>"}` for
     every file you write or change by hand.
   - `{"kind": "not_reproducible", "milestone": "<M>", "step": "<step>", "what": "<the input>", "why": "<why the
     target code does not fix it>"}` for every input rule 8 covers.
   - `{"kind": "failed", "step": "<step>", "error": "<the last lines of its error>"}` for a step you could not make
     run for any other reason. Then go on to the next step.
10. **Run the steps in order.** For each `holon` subcommand, run it with `--help` first and pass the arguments its
    help names for that milestone.
    - Do not run `holon compare`, `holon report`, `holon rank`, `holon gate`, `holon audit` or `holon land`.
    - Do not push anything.

## Steps

### 0. Set up `W`

```
mkdir -p W && cd W && mkdir -p pack blind build cache && tar -xf PACK -C pack
cd W && cp -a pack/tooling/. .
cd W && git init -q target && git -C target fetch -q --depth 1 https://github.com/morph-l2/morph.git 3e44e795586af3e11285b603ab642c67823add51 && git -C target checkout -q FETCH_HEAD
cd W && diff -r -q -x .git pack/target target
cd W && cp -a SCOPE/files/. . && cp SCOPE/stripped.json blind/stripped.json
```

- The `diff` must report no difference other than an empty gitlink directory.
- Then point every target path of `W/config/holon.json` at `W/target` (log it as authored).
- Install nothing inside `W` but your own outputs.

### 1. Extract

Run, for milestone M2 and then M3:
- `python -m holon extract <frontend> ...` for each `W/spec/<M>/lib/extract_*.json`;
- `python -m holon extract go ...` for each `W/spec/<M>/lib/go_frontend.json`;
- `python -m holon link --milestone <M>`.

Then, for M3, in this order:
- `python -m holon codecs --milestone M3`;
- `python -m holon versions extract`, `versions model` and `versions analyze`;
- `python -m holon bundle extract`, `bundle model` and `bundle corpus`;
- `python -m holon bundle2 extract`, `bundle2 deploy`, `bundle2 model` and `bundle2 corpus`;
- `python -m holon derivation extract`, `derivation corpus` and `derivation product`.

### 2. M2 cannot be derived from code

M2's `sorts`, `diagram`, `evidence` and `derive` read hand-written fact documents: `facts/*.json`,
`spec/M1/facts/*.json`, and the documents of `spec/M2/facts/` other than `*.extracted.json`. The pack holds none of
them, and rule 6 forbids writing them.

- Do not run M2's `sorts`, `diagram`, `evidence`, `derive`, `run`, `bind` or `lean`.
- Log one `not_reproducible` line for M2 that names those documents, and go on.
- M2's extraction in step 1 still runs: M3 reads its `*.extracted.json` documents.

### 3. M3's derive inputs, in this order

1. **The binding, then the sorts.**
   - In the typed-sorts sidecar `spec/M3/lib/sort_types.json`, set `binding` to `spec/M3/lib/binding.json`.
   - Run `python -m holon binding --milestone M3`. It re-runs the binding's deployment, by forge on the pinned
     checkout, and writes `gen/M3/binding/`. Never write that record by hand.
   - Run `python -m holon binding --fragments-out --milestone M3`. It derives the fragments binding
     (`replay/M2/fragments.json`) from the declared `spec/M3/lib/fragments.json` and the binding spec. Never write that
     binding by hand.
   - Run `python -m holon sorts --milestone M3`. It reads the typed-sorts sidecar and the seeds that sidecar names.
   - Run `python -m holon refinement --milestone M3`. It runs the step refinement against the real contract, by forge,
     with the typed model as its evaluator, and writes `results/M3/sorts/refinement/hints.json` and `keys.json`: the
     real target's external-call answers and the keys the model took. The searches of `holon run` read them. Never
     write either file by hand.
2. `python -m holon diagram --milestone M3`.
3. `python -m holon evidence --milestone M3`.
4. **DISCH.**
   - Write the DISCH sidecar `spec/M3/lib/disch.json`. `python -m holon disch --help` and `W/holon/analysis/closure.py`
     name its fields: documents, r0, hypotheses, hypothesis_verdicts, inputs.
   - Do not write `r0` or `model_sidecar`. r0 is the deployment's abstraction, and it is derived, not authored: once
     the sidecar's other fields are written, run `python -m holon disch-r0 --milestone M3`. It reads the deployment
     record that `python -m holon binding --milestone M3` wrote (gen/M3/binding/) through the document's layout, and
     writes the sidecar's `r0` and `model_sidecar` (the typing sidecar `spec/M3/lib/sort_types.json`). Never write
     them by hand; `python -m holon disch-r0 --milestone M3 --check` exits 0 on what it wrote.
   - Its `binding` is `spec/M3/lib/binding.json`.
   - Its `search` section is this budget, spec/M3/lib/disch.json's at the pack commit (the budget comes from it, not
     from the tooling default): `max_prefixes`: 3000, `neighbourhood_insertion_length_max`: 2, `neighbourhood_prefixes_per_entry_point_max`: 20000, `prefix_depth`: 3.
   - Then run `python -m holon disch --milestone M3`.
5. **UNDO and FACT.** Write the UNDO sidecar `spec/M3/lib/undo.json` and the FACT sidecar `spec/M3/lib/fact.json`.
   Their loaders, in `W/holon/rules/undo.py` and `W/holon/rules/fact.py`, name their fields. The FACT sidecar's
   `binding` is `spec/M3/lib/binding.json`.
6. **Optional parts of derive.** Each is derived only when its sidecar exists:
   - OWN: `spec/M3/lib/own.json`, then `python -m holon own --milestone M3`. Its Go slice-growth constants come from
     the Go toolchain's runtime sources under `go env GOROOT`.
   - NAT and PAR-init: the versions sidecar.
   - PAR's link_domain and the bundle laws: the bundle-laws sidecars.

   Write one only when the target code fixes its content. Otherwise log it as `not_reproducible`.

### 4. Derive M3

Run `python -m holon derive --milestone M3`. Then run `python -m holon coverage --milestone M3`: it writes
`gen/M3/coverage.json`, which `holon run`'s records read.

If it refuses, its message names the input it needs.
- Write that input under rule 7, or log it under rule 8.
- Then run `derive` again.

### 5. Run M3: the laws of the `par` job only

Compute the list with:
```
python3 -c 'import json; from pathlib import Path; from holon.land import jobs_for; ls = sorted(p.stem for p in Path("laws/M3").glob("L*.json")); print(next((j["laws"] for j in jobs_for(Path("."), "M3", ls, False) if j["name"] == "par"), ""))'
```

Then run:
```
python -m holon run --milestone M3 --laws <that list>
python -m holon lean --milestone M3
python -m holon run --milestone M3 --laws <that list>
```

Leave every other M3 law to the runners: the coordinator's builder re-makes them from your tree.

### 6. Lossy

Run `python -m holon lossy --milestone M3`. It reads the component model that `holon run` writes, so it runs after
step 5.

### 7. Replay

There is no local replay step. M3's replays are the runners' final filter stage, and M2 has no law.

### 8. End

1. Write `W/blind/done.json`: `{"steps_failed": [<the steps you logged as failed>], "not_reproducible": [<the steps you
   logged as not_reproducible>], "authored": [<the paths you logged as authored>]}`.
2. Stop.
   - Do not summarize statuses for anyone.
   - Do not read any file outside `W`.
