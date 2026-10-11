"""Build the callable native library for a generated Bend model.

Pipeline per model (m0 | rollup | batchdata):
    driver.bend  --bend-->  model.mjs   (loaded by holon/native/js/worker.mjs)

C emission is rejected by the codec model: its 257-field record constructor
exceeds the C backend's arity cap ("an arity over 247"), so the library is
the emitted .mjs and the worker marshals JSON-lines calls into it.

Layout under build/native/<name>/: model.bend (copied), driver.bend
(generated), model.mjs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import drivergen, models

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "native"

def bend_bin() -> str:
    for cand in (Path.home() / ".holon" / "bin" / "bend", Path("/usr/local/bin/bend")):
        if cand.exists():
            return str(cand)
    return shutil.which("bend") or "bend"


def go_bin() -> str:
    for cand in ("/usr/local/go/bin/go",):
        if Path(cand).exists():
            return cand
    return shutil.which("go") or "go"


def build_model(name: str, work: Path | None = None) -> dict:
    spec = models.MODELS[name]
    d = (work or BUILD / name)
    d.mkdir(parents=True, exist_ok=True)
    model_dst = d / spec["model"].name
    shutil.copy(spec["model"], model_dst)
    driver = drivergen.emit_driver(model_dst.name, spec["flat_ops"], spec["trace_ops"],
                                   helpers=spec["helpers"])
    (d / "driver.bend").write_text(driver)

    bend = bend_bin()
    subprocess.run([bend, "driver.bend", "-o", "model.mjs"], cwd=d, check=True,
                   capture_output=True, text=True)
    src = (d / "model.mjs").read_text()
    for fn in ("hcall", "hcall2"):
        if f'"{fn}":' not in src:
            raise RuntimeError(f"dispatcher {fn} not exported from {name}")
    return {"dir": str(d), "lib": str(d / "model.mjs")}


def build_all(names: list[str] | None = None, work: Path | None = None) -> dict:
    names = names or list(models.MODELS)
    return {n: build_model(n, Path(work) / n if work else None) for n in names}
