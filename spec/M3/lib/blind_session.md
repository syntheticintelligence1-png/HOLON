# Blind rerun: the session brief

You run HOLON's pipeline from code, on a sealed bundle, with no other source of knowledge. The coordinator gives you
three absolute paths:
- `PACK`: a tar file, `bundle.tar`. It holds `target/` (the target's code at one pinned commit), `tooling/` (HOLON's
  code: `holon/`, `tools/`, `config/`, `schemas/`, `.github/ci/`) and `tooling/whitepaper.md`;
- `SCOPE`: a directory holding `files/<path>` (the extraction-scope sidecars) and `stripped.json` (the keys removed
  from them);
- `W`: your work directory, which does not exist yet.

The target is the repository `morph-l2/morph` at commit `3e44e795586af3e11285b603ab642c67823add51`.

## Rules

1. **Read and write only inside `W`**, and read `PACK` and `SCOPE` once each, in step 0.
   - You may run the toolchain (`python3`, `bend`, `bun`, `node`, `go`, `git`, `tar`, `sha256sum`, `forge`, `solc`,
     `lean`, `lake` and the binaries `W/config/holon.json` names), but never browse its directories.
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
   `W/replay` and every `*.extracted.json` is written by the commands below.
7. **Authored inputs.** When a command needs an input that `W` does not hold, write it yourself and log it as
   authored. Such an input is a sidecar under `spec/<M>/lib/`, a key that `stripped.json` lists, or a path in
   `config/holon.json`.
   - Write it only from the target code under `W/target` and from the tooling's own code and docstrings under `W`.
   - Never copy it from anywhere else.
8. **Keep the log `W/blind/log.jsonl`**: one JSON object per line, appended as you go.
   - `{"kind": "command", "cmd": "<the command>", "exit": <code>, "seconds": <s>}` for every command of the steps.
   - `{"kind": "authored", "path": "<path under W>", "sha256": "<hex>", "for": "<the command that needed it>"}` for
     every file you write or change by hand.
   - `{"kind": "failed", "step": "<step>", "error": "<the last lines of its error>"}` for a step you could not make
     run. Then go on to the next step.
9. **Run the steps in order.** For each `holon` subcommand, run it with `--help` first and pass the arguments its
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
- `python -m holon derivation extract`, `derivation corpus` and `derivation product`;
- `python -m holon own --milestone M3`.

### 2. Derive

For milestone M2 and then M3:
- `python -m holon sorts --milestone <M>`;
- `python -m holon diagram --milestone <M>`;
- `python -m holon evidence --milestone <M>`;
- `python -m holon derive --milestone <M>`.

Run `python -m holon lossy --milestone M3` before M3's `derive`.

### 3. Run

1. **M2:**
   ```
   python -m holon run --milestone M2
   python -m holon bind --milestone M2
   python -m holon lean --milestone M2
   python -m holon run --milestone M2
   ```
2. **M3, only the laws of the `par` job.** Compute the list with:
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

### 4. Replay

Run `python -m holon replay --milestone M2`, when its help names that milestone.

### 5. End

1. Write `W/blind/done.json`: `{"steps_failed": [<the steps you logged as failed>], "authored": [<the paths you logged as authored>]}`.
2. Stop.
   - Do not summarize statuses for anyone.
   - Do not read any file outside `W`.
