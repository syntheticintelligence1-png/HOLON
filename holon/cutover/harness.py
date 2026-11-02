"""Rule L2: the cutover harness (replay/<M>/cutover/HolonCutover.t.sol on I69's generic step base) and its runs.

The scratch project is the target's Foundry tree at the pinned checkout (holon.replay_fragments.harness_project), with
the harness files under test/: I69's generic multi-target step base, I20's M1 trace harness (its header and commit
helpers) and the cutover harness. The input carries the creation codes the harness deploys from (holon.cutover.build),
the deployment's init values and the steps (I69's step encoding: 1 an abstract row, 2 a call). A first run with no step
gives the deployment record; each trace then runs from a fresh deployment. The output lines are I69's
(holon.bundle.harness.parse).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from . import BundleError, Ctx

HARNESS_CONTRACT = "HolonCutoverTest"
BASE = "replay/M3/bundle/HolonBundleBase.sol"
M1 = "replay/M1/solidity/HolonTraceReplay.t.sol"


def harness_files(ctx: Ctx) -> list:
    return [BASE, M1, f"{ctx.out('harness')}/HolonCutover.t.sol"]


def project(ctx: Ctx, work: Path, tc: dict) -> Path:
    from ..replay_fragments import forge_build, harness_project
    binding = {"project": {"kind": "checkout", "foundry_dir": "contracts", "drop": ["mock", "test"]},
               "harness": {"files": harness_files(ctx)}}
    proj = harness_project(binding, work, ctx.root, Path(ctx.bundle().source_repo()), tc)
    forge_build(proj, tc)
    return proj


def run(proj: Path, tc: dict, doc: dict, tag: str, log=print) -> list:
    """One forge run of the input document's traces; the parsed traces (holon.bundle.harness.parse)."""
    from ..bundle.harness import parse
    fin, fout = proj / f"holon_{tag}.json", proj / f"holon_{tag}.out"
    fin.write_text(json.dumps(doc))
    fout.unlink(missing_ok=True)
    n = len(doc["lens"])
    cmd = ["nice", "-n", "10", tc["forge"], "test", "--match-contract", f"^{HARNESS_CONTRACT}$", "--match-test",
           "^test_steps\\(\\)$", "--offline", "--use", tc["solc"]]
    env = {**os.environ, "HOLON_STEPS_IN": fin.name, "HOLON_STEPS_OUT": fout.name, "HOLON_LO": "0", "HOLON_HI": str(n)}
    p = subprocess.run(cmd, cwd=proj, env=env, capture_output=True, text=True, timeout=7200)
    text = fout.read_text() if fout.exists() else ""
    if p.returncode != 0 or not text.rstrip().endswith(f"DONE 0 {n}"):
        raise BundleError(f"the cutover harness failed (exit {p.returncode}): {(p.stdout + p.stderr)[-3000:]}")
    fin.unlink(missing_ok=True)
    fout.unlink(missing_ok=True)
    log(f"harness: {n} traces run")
    return parse(text), runtimes(text)


def runtimes(text: str) -> dict:
    """{tag: runtime code hex} of the harness's R lines (the creation codes' deployed runtimes, trace 0)."""
    out = {}
    for ln in text.splitlines():
        f = ln.split(" ")
        if f[0] == "R" and len(f) == 4:
            out[f[2]] = f[3].lower()
    return out


def input_doc(codes: list, init: list, watch: list, traces: list) -> dict:
    """The harness input: per trace its encoded steps (hex), every trace from a fresh deployment."""
    steps, lens = [], []
    for t in traces:
        lens.append(len(t))
        steps.extend("0x" + s.hex() for s in t)
    return {"codes": ["0x" + c.hex() for c in codes], "init": list(init), "watch": list(watch), "lens": lens,
            "steps": steps}
